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
    if 200 <= code < 400:
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
    code_match = re.search(r'\b([45]\d{2})\b', message or '')
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


def outcome_from_pages(pages: Any) -> Optional[dict]:
    """
    Lit la premiere page analysee (page d'accueil) et en sort un resultat.

    @param pages: Liste de pages (analyse technique)
    @returns: Dict, ou None si on n'a aucune info fiable
    """
    if not isinstance(pages, list) or not pages:
        return None
    first = pages[0]
    if not isinstance(first, dict):
        return None
    if first.get('status_code') is not None:
        return outcome_from_status(first.get('status_code'), str(first.get('error') or ''))
    err = first.get('error')
    if err:
        return outcome_from_error_message(str(err))
    return None


def outcome_from_stored_page(status_code: Any, details: Any) -> Optional[dict]:
    """
    Meme lecture, depuis une ligne analysis_technique_pages deja en base.

    @param status_code: Colonne status_code
    @param details: JSON de la page (peut contenir error)
    @returns: Dict, ou None si la ligne ne dit rien
    """
    if status_code is not None and str(status_code).strip() != '':
        return outcome_from_status(status_code)
    payload = details
    if isinstance(payload, str) and payload.strip():
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {'error': payload}
    if isinstance(payload, dict):
        err = payload.get('error')
        if err:
            return outcome_from_error_message(str(err))
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
