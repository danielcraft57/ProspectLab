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

