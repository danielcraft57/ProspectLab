"""
Utilitaires d'URL / domaine.

Objectif: normaliser les sites web pour la déduplication (unicité par domaine/host),
en évitant les variations (http/https, www., chemins, ports).
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse


_EMPTY_MARKERS = {"", "nan", "none", "null", "n/a", "na"}


def normalize_website_domain(raw: object) -> Optional[str]:
    """
    Retourne un host normalisé (sans schéma/chemin), ou None si vide.

    Règles:
    - retire http/https et le chemin (ne garde que le host)
    - retire un éventuel user:pass@
    - retire le port par défaut (:80/:443)
    - retire le préfixe "www."
    - lowercase + trim + retire le point final
    """
    if raw is None:
        return None

    s = str(raw).strip()
    if not s or s.lower() in _EMPTY_MARKERS:
        return None

    s = s.strip().lower()

    # Préfixer pour permettre un parsing correct si schéma absent
    candidate = s if s.startswith(("http://", "https://")) else f"http://{s}"
    try:
        parsed = urlparse(candidate)
    except Exception:
        return s

    host = parsed.netloc or parsed.path or ""
    host = host.strip().lower()
    if not host:
        return None

    # Retirer credentials si présents
    if "@" in host:
        host = host.split("@", 1)[1]

    host = host.rstrip(".")

    # Retirer port par défaut
    if ":" in host:
        h, port = host.rsplit(":", 1)
        if port in ("80", "443"):
            host = h

    if host.startswith("www."):
        host = host[4:]

    host = host.strip()
    return host or None


def website_lookup_candidates(raw: object) -> list[str]:
    """
    Variantes de ``entreprises.website`` pour une recherche indexée PostgreSQL
    (évite le scan complet de la table en prod).
    """
    host = normalize_website_domain(raw)
    if not host:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for variant in (
        host,
        f'www.{host}',
        f'https://{host}',
        f'http://{host}',
        f'https://www.{host}',
        f'http://www.{host}',
    ):
        key = variant.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def canonical_website_https_url(raw: object) -> Optional[str]:
    """
    URL HTTPS unique pour lancer les analyses et stocker `entreprises.website` :
    même host que ``normalize_website_domain`` (sans ``www.``, minuscules),
    forme ``https://exemple.fr`` (évite les doublons ``www`` / apex).
    """
    host = normalize_website_domain(raw)
    if not host:
        return None
    return f"https://{host}"


def _navigation_url_candidates(raw: object) -> list[str]:
    """
    Candidats d'URL a tester (https puis http, apex puis www).

    @param raw: Site brut
    @returns: Liste d'URLs absolues
    """
    host = normalize_website_domain(raw)
    if not host:
        return []
    # Garder un chemin non trivial si fourni (hors /)
    path = "/"
    try:
        s = str(raw or "").strip()
        if s and not s.lower().startswith(("http://", "https://")):
            s = f"https://{s.lstrip('/')}"
        parsed = urlparse(s)
        if parsed.path and parsed.path not in ("", "/"):
            path = parsed.path if parsed.path.startswith("/") else f"/{parsed.path}"
    except Exception:
        path = "/"
    hosts = [host]
    if not host.startswith("www."):
        hosts.append(f"www.{host}")
    out: list[str] = []
    seen: set[str] = set()
    for h in hosts:
        for scheme in ("https", "http"):
            url = f"{scheme}://{h}{path}"
            key = url.lower()
            if key not in seen:
                seen.add(key)
                out.append(url)
    return out


def resolve_website_url_following_redirects(
    raw: object,
    *,
    timeout: float = 10.0,
) -> Optional[str]:
    """
    Suit les redirections HTTP pour obtenir l'URL navigable (Playwright / scrape).

    Utile quand ``https://domaine.fr`` est mort mais ``http://domaine.fr``
    redirige vers un sous-domaine vivant (ex. ``https://spider.domaine.fr``).

    @param raw: Site brut ou URL
    @param timeout: Timeout requests (secondes)
    @returns: URL finale (de preference https), ou canonical https si tout echoue
    @example
        resolve_website_url_following_redirects('pps4.fr')
        # -> 'https://spider.pps4.fr/' (si la redirect HTTP apex existe)
    """
    fallback = canonical_website_https_url(raw)
    candidates = _navigation_url_candidates(raw)
    if not candidates:
        return fallback

    try:
        import requests
    except Exception:
        return fallback

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; ProspectLab/1.0; +https://danielcraft.fr)"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    for url in candidates:
        try:
            # GET stream : certains hebergeurs refusent HEAD
            resp = requests.get(
                url,
                allow_redirects=True,
                timeout=timeout,
                headers=headers,
                stream=True,
            )
            try:
                final = (resp.url or "").strip()
                code = int(resp.status_code or 0)
            finally:
                resp.close()
            if not final:
                continue
            # Accepte succes, redirects resolues, et 401/403 (WAF = serveur vivant)
            if 200 <= code < 400 or code in (401, 403):
                if final.lower().startswith("http://"):
                    # Preferer https sur l'hote final si possible
                    https_final = f"https://{final[7:]}"
                    try:
                        probe = requests.get(
                            https_final,
                            allow_redirects=True,
                            timeout=min(timeout, 6.0),
                            headers=headers,
                            stream=True,
                        )
                        try:
                            if int(probe.status_code or 0) in set(range(200, 400)) | {401, 403}:
                                return (probe.url or https_final).strip()
                        finally:
                            probe.close()
                    except Exception:
                        pass
                return final
        except Exception:
            continue

    return fallback


def resolve_navigation_url(
    raw: object,
    *,
    timeout: float = 10.0,
) -> Optional[str]:
    """
    Alias pour la navigation (Playwright, scrape, audits, technique).

    @param raw: Site brut ou URL
    @param timeout: Timeout requests (secondes)
    @returns: URL finale navigable ou None
    """
    return resolve_website_url_following_redirects(raw, timeout=timeout)


def normalize_url_for_analysis(
    raw: object,
    *,
    timeout: float = 10.0,
) -> Optional[str]:
    """
    URL cible pour toutes les analyses (scraping, technique, SEO, screenshots, Gemini).

    Suit les redirections HTTP ; si tout echoue, retombe sur ``canonical_website_https_url``.

    @param raw: Champ website ou URL utilisateur
    @param timeout: Timeout par candidat (secondes)
    @returns: URL absolue https (ou http si seul scheme viable) ou None
    @example
        normalize_url_for_analysis('pps4.fr')
        # -> 'https://spider.pps4.fr' si la redirect apex http existe
    """
    s = str(raw or "").strip()
    if not s:
        return None
    return resolve_website_url_following_redirects(s, timeout=timeout) or canonical_website_https_url(s)


def coerce_website_to_navigable_url(
    raw: object,
    *,
    timeout: float = 10.0,
) -> Optional[str]:
    """
    Valide un champ ``entreprises.website`` puis retourne l'URL navigable.

    Rejette les placeholders / domaines invalides avant resolution.

    @param raw: Valeur BDD
    @param timeout: Timeout resolution
    @returns: URL pour pipeline d'analyse ou None
    """
    s = str(raw or "").strip()
    if not s or s.lower() == "website":
        return None
    try:
        parsed = urlparse(s if "://" in s else f"https://{s}")
        host = (parsed.netloc or "").split(":")[0]
        if not host and "." not in s:
            return None
        if " " in s:
            return None
    except Exception:
        return None
    return normalize_url_for_analysis(s, timeout=timeout)

