"""
Classement de la page d'accueil : site joignable, ou code HTTP / panne reseau.

Sert a poser les tags `http:404`, `http:502`, `http:timeout`, etc.
et le tag de filtre `site_injoignable` (« Ne répond pas »).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# Tags techniques qu'on retire quand la page d'accueil ne repond pas :
# un score a 0 sur une erreur n'est pas une perf faible ni un potentiel de refonte.
NOISE_TAGS_WHEN_UNREACHABLE = frozenset({
    'fort_potentiel_refonte',
    'perf:low',
    'perf:good',
    'perf_lente',
})

SITE_UNREACHABLE_TAG = 'site_injoignable'

# Le serveur repond : succes, redirections, ou protection (WAF). Pas « site mort ».
REACHABLE_STATUS_CODES = frozenset({401, 403})


def is_site_reachable_status(status_code: Any) -> bool:
    """
    True si le serveur a repondu (meme en 403 bot/WAF).

    @param status_code: Code HTTP ou None
    @returns: Joignable au sens ProspectLab (pas tag « Ne repond pas »)
    """
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return False
    if 200 <= code < 400:
        return True
    if code in REACHABLE_STATUS_CODES:
        return True
    return False


def _fail(status_code: Optional[int], kind: str, tag: str, detail: str = '') -> dict:
    """
    Construit un resultat « le site n'a pas repondu correctement ».

    @param status_code: Code HTTP si on en a un
    @param kind: http, timeout, dns, ssl, connection ou error
    @param tag: Tag a poser (http:404, http:timeout, ...)
    @param detail: Message court, optionnel
    @returns: Dict exploitable par sync_reachability_tags
    """
    return {
        'ok': False,
        'status_code': status_code,
        'kind': kind,
        'tag': tag,
        'detail': (detail or '')[:240],
    }


def outcome_from_status(status_code: Any, detail: str = '') -> dict:
    """
    Traduit un code HTTP en resultat de joignabilite.

    2xx et 3xx : le site repond. 4xx et 5xx : tag `http:<code>`.

    @param status_code: Code HTTP
    @param detail: Precision optionnelle
    @returns: Dict avec ok, status_code, kind, tag
    """
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return _fail(None, 'error', 'http:injoignable', detail or 'code HTTP illisible')
    if is_site_reachable_status(code):
        return {
            'ok': True,
            'status_code': code,
            'kind': 'ok',
            'tag': None,
            'detail': (detail or '')[:240],
        }
    if code >= 400:
        return _fail(code, 'http', f'http:{code}', detail)
    return _fail(code, 'error', 'http:injoignable', detail or f'code {code}')


def outcome_from_error_message(message: str) -> dict:
    """
    Devine la panne a partir du texte d'exception (timeout, DNS, SSL, refus).

    @param message: str(exception) ou champ error d'une page technique
    @returns: Dict de joignabilite, jamais ok
    """
    msg = (message or '').lower()
    if 'timed out' in msg or 'read timeout' in msg or 'connect timeout' in msg:
        return _fail(None, 'timeout', 'http:timeout', message)
    if 'ssl' in msg or 'certificate' in msg or 'tls' in msg:
        return _fail(None, 'ssl', 'http:ssl', message)
    if (
        'name or service not known' in msg
        or 'nodename nor servname' in msg
        or 'getaddrinfo' in msg
        or 'name resolution' in msg
        or 'failed to resolve' in msg
        or 'temporary failure in name resolution' in msg
        or 'errno -2' in msg
        or 'errno 11001' in msg
    ):
        return _fail(None, 'dns', 'http:dns', message)
    code_match = re.search(r'(?:HTTPError|status code|http)\s*[=:]?\s*([45]\d{2})\b', msg, re.I)
    if not code_match:
        code_match = re.search(r'\b([45][0-9]{2})\b', message or '')
    if code_match:
        return outcome_from_status(int(code_match.group(1)), message)
    return _fail(None, 'connection', 'http:injoignable', message)


def outcome_from_exception(exc: BaseException) -> dict:
    """
    Classe une exception requests (ou proche) en tag HTTP.

    @param exc: Exception levee pendant le GET
    @returns: Dict de joignabilite
    """
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None) if response is not None else None
    if isinstance(exc, requests.HTTPError) and status is not None:
        return outcome_from_status(status, str(exc))
    if isinstance(exc, (requests.Timeout, TimeoutError)):
        return _fail(None, 'timeout', 'http:timeout', str(exc))
    if isinstance(exc, requests.exceptions.SSLError):
        return _fail(None, 'ssl', 'http:ssl', str(exc))
    return outcome_from_error_message(str(exc))


def _normalize_page_dict(raw: Any) -> Optional[dict]:
    """Parse une ligne page technique (dict ou JSON string)."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _page_url_key(page: dict) -> str:
    return str(page.get('url') or page.get('page_url') or '').strip().lower()


def resolve_reachability_from_pages(pages: Any, preferred_url: Optional[str] = None) -> Optional[dict]:
    """
    Decide si le site repond a partir de toutes les pages d'une analyse.

    Une seule page en 200/304/403 suffit : on ne se base plus sur la
    premiere ligne BDD (souvent une 404 de sous-lien).

    @param pages: Liste de pages (technique ou scrape)
    @param preferred_url: URL d'accueil attendue (analyses_techniques.url)
    @returns: Dict joignabilite, ou None
    """
    if not isinstance(pages, list) or not pages:
        return None
    pref = (preferred_url or '').strip().lower().rstrip('/')
    normalized: list[dict] = []
    for item in pages:
        p = _normalize_page_dict(item)
        if p:
            normalized.append(p)
    if not normalized:
        return None

    def _matches_preferred(p: dict) -> bool:
        if not pref:
            return False
        u = _page_url_key(p).rstrip('/')
        return u == pref or u.startswith(pref + '/')

    for p in normalized:
        sc = p.get('status_code')
        if sc is not None and is_site_reachable_status(sc):
            ok = outcome_from_status(sc)
            ok['detail'] = (_page_url_key(p) or '')[:240]
            return ok

    errors: list[tuple[Optional[int], dict]] = []
    for p in normalized:
        sc = p.get('status_code')
        if sc is not None:
            try:
                code = int(sc)
            except (TypeError, ValueError):
                continue
            if code >= 400:
                errors.append((code, p))
        elif p.get('error'):
            errors.append((None, p))

    if not errors:
        return None

    # Erreur sur l'URL d'accueil en priorite
    errors.sort(
        key=lambda pair: (
            0 if _matches_preferred(pair[1]) else 1,
            0 if pair[0] and pair[0] >= 500 else 1,
            pair[0] if pair[0] is not None else 999,
        ),
    )
    code, page = errors[0]
    if code is not None:
        return outcome_from_status(code, str(page.get('error') or ''))
    err = page.get('error')
    if err:
        return outcome_from_error_message(str(err))
    return None


def outcome_from_pages(pages: Any, preferred_url: Optional[str] = None) -> Optional[dict]:
    """
    Alias : analyse multipages complete.

    @param pages: Liste de pages
    @param preferred_url: URL racine optionnelle
    @returns: Dict ou None
    """
    return resolve_reachability_from_pages(pages, preferred_url=preferred_url)


def outcome_from_stored_page(status_code: Any, details: Any) -> Optional[dict]:
    """
    Compatibilite : une seule ligne BDD (eviter si possible, preferer toutes les pages).

    @param status_code: Colonne status_code
    @param details: JSON de la page
    @returns: Dict ou None
    """
    page = _normalize_page_dict(details) or {}
    if status_code is not None and str(status_code).strip() != '':
        page.setdefault('status_code', status_code)
    return resolve_reachability_from_pages([page] if page else [], preferred_url=page.get('url'))


def outcome_from_scrape_evidence(
    visited_urls: Any,
    total_emails: Any = 0,
    homepage_reachability: Any = None,
) -> Optional[dict]:
    """
    Si le scraping a vraiment recupere du contenu, le site repond.

    @param visited_urls: Nombre ou liste d'URLs avec reponse HTML
    @param total_emails: Emails trouves
    @param homepage_reachability: Metadata scrape precedente
    @returns: Dict ok, ou None pour laisser la metadata decider
    """
    visited = 0
    if isinstance(visited_urls, list):
        visited = len(visited_urls)
    elif visited_urls is not None:
        try:
            visited = int(visited_urls)
        except (TypeError, ValueError):
            visited = 0
    try:
        emails = int(total_emails or 0)
    except (TypeError, ValueError):
        emails = 0
    if emails > 0:
        return outcome_from_status(200, 'emails_scrapes')
    if isinstance(homepage_reachability, dict) and homepage_reachability.get('ok'):
        return dict(homepage_reachability)
    # visited_urls seul n'est pas suffisant (on ajoute l'URL meme quand le GET echoue)
    return None


def _read_tags(db, cursor, entreprise_id: int) -> list:
    """
    Charge la liste de tags d'une entreprise.

    @param db: Instance Database (execute_sql)
    @param cursor: Curseur ouvert
    @param entreprise_id: ID entreprise
    @returns: Liste de chaines
    """
    db.execute_sql(cursor, 'SELECT tags FROM entreprises WHERE id = ?', (entreprise_id,))
    row = cursor.fetchone()
    raw = None
    if row is not None:
        try:
            raw = row['tags'] if isinstance(row, dict) or hasattr(row, 'keys') else row[0]
        except Exception:
            raw = None
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(t).strip() for t in parsed if str(t).strip()]


def sync_reachability_tags(db, cursor, entreprise_id: int, outcome: Optional[dict]) -> bool:
    """
    Pose ou retire les tags HTTP selon la page d'accueil.

    Site OK : on enleve http:* et site_injoignable.
    Site en erreur : on pose http:XXX + site_injoignable, et on retire
    fort_potentiel_refonte / perf faible, qui n'ont pas de sens sans reponse.

    @param db: Instance Database
    @param cursor: Curseur de la transaction en cours
    @param entreprise_id: ID entreprise
    @param outcome: Resultat outcome_from_*
    @returns: True si les tags ont ete reecrits
    """
    if not entreprise_id or not isinstance(outcome, dict) or 'ok' not in outcome:
        return False
    try:
        tags = _read_tags(db, cursor, entreprise_id)
        kept = []
        for tag in tags:
            if tag == SITE_UNREACHABLE_TAG or tag.startswith('http:'):
                continue
            if not outcome.get('ok') and tag in NOISE_TAGS_WHEN_UNREACHABLE:
                continue
            kept.append(tag)
        if not outcome.get('ok'):
            specific = str(outcome.get('tag') or 'http:injoignable').strip()
            if not specific.startswith('http:'):
                specific = 'http:injoignable'
            kept.append(specific)
            kept.append(SITE_UNREACHABLE_TAG)
        seen = set()
        deduped = []
        for tag in kept:
            if tag in seen:
                continue
            seen.add(tag)
            deduped.append(tag)
        db.execute_sql(
            cursor,
            'UPDATE entreprises SET tags = ? WHERE id = ?',
            (json.dumps(deduped) if deduped else None, entreprise_id),
        )
        return True
    except Exception as exc:
        logger.warning(
            'Tags joignabilite non mis a jour pour entreprise %s: %s',
            entreprise_id,
            exc,
        )
        return False
