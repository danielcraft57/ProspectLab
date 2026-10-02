"""
Client Gemini (Google AI Studio) avec rotation multi-cles / multi-comptes.

Pattern :
- bascule sequentielle immediate de compte en compte (429/503 → suivant, 0s)
- 429 RPM → saute au compte suivant (pas de blacklist)
- 429 RPD reel (retry long) → cle ignoree jusqu'au reset Pacific
- 503 / high demand → fallback modele sur la meme cle (GEMINI_FALLBACK_MODELS),
  puis cle suivante ; apres N cles 503 d'affilee (GEMINI_503_MAX_CONSECUTIVE_KEYS),
  stop precoce + pause courte au lieu de bruler tout le pool
- 401/403 invalide → cle ignoree jusqu'au redemarrage process
- toutes en quota → pause GEMINI_QUOTA_RETRY_MS puis nouvel essai
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Sequence

import requests

try:
    from services.logging_config import setup_logger
    logger = setup_logger(__name__, 'gemini_full_report_tasks.log', console=False)
except Exception:
    logger = logging.getLogger(__name__)

BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
DEFAULT_TIMEOUT_MS = 60_000

# Cles revoquees (403/401) pour la duree du process
_revoked_keys: set[str] = set()
# Cles en quota journalier (RPD) : timestamp unix jusqu'auquel on les ignore
_rpd_exhausted_until: Dict[str, float] = {}
_preferred_key_index: int = 0
_keys_lock = threading.Lock()


class GeminiClientError(Exception):
    """Erreur d'appel Gemini apres epuisement des cles / retries."""


class GeminiQuotaError(GeminiClientError):
    """Toutes les cles ont renvoye 429 (quota RPM/RPD epuise)."""


def is_gemini_quota_error(exc_or_msg) -> bool:
    """
    Detecte un epuisement de quota Gemini (429 / RESOURCE_EXHAUSTED).

    @param exc_or_msg: Exception ou message
    @returns: True si quota
    """
    if isinstance(exc_or_msg, GeminiQuotaError):
        return True
    text = str(exc_or_msg or '').lower()
    markers = (
        '429',
        'quota',
        'resource_exhausted',
        'resource exhausted',
        'rate limit',
        'rate_limit',
        'too many requests',
        'generate_content_free_tier',
    )
    return any(m in text for m in markers)


def _next_pacific_midnight_ts() -> float:
    """
    Timestamp du prochain reset RPD Gemini (~minuit Pacific + 5 min).

    @returns: Unix timestamp
    """
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        pt = ZoneInfo('America/Los_Angeles')
        now = datetime.now(pt)
        nxt = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
        return float(nxt.timestamp())
    except Exception:
        return time.time() + 12 * 3600


def _is_daily_quota_body(raw: str) -> bool:
    """
    Detecte un 429 de quota journalier (RPD) vs RPM ponctuel.

    Google ment souvent : le corps peut contenir ``PerDay`` / ``limit: 20``
    alors que le message dit ``Please retry in 58s`` (RPM). Dans ce cas
    on NE blacklist PAS la cle jusqu'au reset Pacific.

    @param raw: Corps reponse API
    @returns: True seulement si RPD reel (pas de retry court)
    """
    import re

    low = (raw or '').lower()
    compact = low.replace('_', '').replace('-', '').replace(' ', '')

    # Retry court (secondes / quelques minutes) → RPM, jamais blacklist jour
    m = re.search(r'retry in\s+([\d.]+)\s*(s|sec|second|seconds|m|min|minute|minutes)?', low)
    if m:
        val = float(m.group(1))
        unit = (m.group(2) or 's').lower()
        sec = val * 60.0 if unit.startswith('m') else val
        if sec < 600:  # < 10 min → RPM / fenetre courte
            return False

    # Minute explicite → jamais un blacklist jour
    if any(
        x in low or x in compact
        for x in (
            'perminute',
            'per minute',
            'requestsperminute',
            'generaterequestsperminute',
            'quotaid":"generaterequestsperminute',
        )
    ):
        return False

    # Marqueurs jour explicites + pas de retry court (deja filtre)
    if any(
        x in low or x in compact
        for x in (
            'perday',
            'per day',
            'requestsperday',
            'generaterequestsperday',
            'dailyquota',
            'quotaid":"generaterequestsperday',
        )
    ):
        return True

    # Details JSON Google (quotaId)
    try:
        data = json.loads(raw)
        blob = json.dumps(data).lower().replace('_', '').replace('-', '')
        if 'perminute' in blob:
            return False
        if 'perday' in blob or 'requestsperday' in blob:
            # Re-check retry court dans le JSON complet
            m2 = re.search(
                r'retry in\s+([\d.]+)\s*(s|sec|second|seconds|m|min|minute|minutes)?',
                blob,
            )
            if m2:
                val = float(m2.group(1))
                unit = (m2.group(2) or 's').lower()
                sec = val * 60.0 if unit.startswith('m') else val
                if sec < 600:
                    return False
            return True
    except Exception:
        pass

    # Ambigu → RPM (on tourne a la cle suivante, pas de blacklist jour)
    return False


def _clear_rpd_mark(api_key: str) -> None:
    """Retire le marqueur RPD d'une cle (apres probe OK / RPM)."""
    _rpd_exhausted_until.pop(api_key, None)


def _probe_revive_rpd_keys(api_keys: Sequence[str], model: str) -> List[str]:
    """
    Si toutes les cles sont en RPD memoire, re-teste-les en live.

    Evite le piege : un faux RPD (ou un reset Google deja passe) laisse
    ``active`` vide et on ne tourne plus jamais les cles jusqu'au restart.

    @param api_keys: Cles configurees
    @param model: Modele a sonder
    @returns: Cles remises actives (eventuellement vide)
    """
    revived: List[str] = []
    body = {
        'contents': [{'role': 'user', 'parts': [{'text': 'OK'}]}],
        'generationConfig': {
            'maxOutputTokens': 4,
            'temperature': 0,
            'thinkingConfig': {'thinkingLevel': 'low'},
        },
    }
    for i, api_key in enumerate(api_keys):
        if api_key in _revoked_keys:
            continue
        if api_key not in _rpd_exhausted_until and api_key not in revived:
            # Deja active
            revived.append(api_key)
            continue
        tag = _key_tag(api_key, i + 1, len(api_keys))
        try:
            status, raw = _request_gemini(
                api_key=api_key,
                model=model,
                body=body,
                timeout_ms=20_000,
            )
        except Exception as exc:
            logger.warning('[Gemini] probe %s — reseau %s', tag, exc)
            continue

        if status == 200:
            _clear_rpd_mark(api_key)
            revived.append(api_key)
            logger.warning('[Gemini] probe %s — OK, cle remotivee', tag)
            continue

        if status == 429:
            # Sur probe : on ne re-confirme un RPD QUE si PerDay est explicite.
            # Sinon on leve le blacklist memoire (souvent un faux RPD / RPM).
            if _is_daily_quota_body(raw):
                _mark_key_rpd_exhausted(api_key, tag)
                logger.warning('[Gemini] probe %s — RPD confirme (PerDay)', tag)
            else:
                _clear_rpd_mark(api_key)
                revived.append(api_key)
                logger.warning(
                    '[Gemini] probe %s — 429 ambigu/RPM, blacklist leve → remotivee',
                    tag,
                )
            continue

        if status in (401, 403):
            lowered = (raw or '').lower()
            if status == 401 or 'denied' in lowered or 'api key not valid' in lowered:
                _revoked_keys.add(api_key)
                _clear_rpd_mark(api_key)
                logger.warning('[Gemini] probe %s — %s, ignoree', tag, status)
            else:
                _clear_rpd_mark(api_key)
                revived.append(api_key)
            continue

        # 503 / autre : on retente la cle (pas un RPD)
        _clear_rpd_mark(api_key)
        revived.append(api_key)
        logger.warning('[Gemini] probe %s — status %s, cle remotivee pour retry', tag, status)

    return revived


def _mark_key_rpd_exhausted(api_key: str, tag: str) -> None:
    """
    Ignore une cle jusqu'au reset Pacific (evite de cramer les autres projets).

    @param api_key: Cle API
    @param tag: Label log
    """
    until = _next_pacific_midnight_ts()
    _rpd_exhausted_until[api_key] = until
    left_h = max(0.1, (until - time.time()) / 3600.0)
    logger.warning(
        '[Gemini] %s — RPD/jour epuise, ignoree ~%.1fh (protege les autres comptes)',
        tag,
        left_h,
    )


def _active_api_keys(api_keys: Sequence[str]) -> List[str]:
    """
    Filtre cles revoquees + RPD epuisees (purge les expirations).

    @param api_keys: Liste brute
    @returns: Cles utilisables maintenant
    """
    now = time.time()
    expired = [k for k, until in list(_rpd_exhausted_until.items()) if until <= now]
    for k in expired:
        _rpd_exhausted_until.pop(k, None)
    out: List[str] = []
    for k in api_keys:
        if k in _revoked_keys:
            continue
        until = _rpd_exhausted_until.get(k)
        if until and until > now:
            continue
        out.append(k)
    return out


def get_gemini_api_keys() -> List[str]:
    """
    Collecte les cles Gemini depuis l'environnement.

    Ordre : GEMINI_API_KEYS (CSV) puis GEMINI_API_KEY + GEMINI_API_KEY_2 … _9.

    @returns: Liste de cles uniques non vides
    @raises GeminiClientError: Aucune cle configuree
    """
    keys: List[str] = []

    def _push(value: Optional[str]) -> None:
        key = (value or '').strip()
        if key and key not in keys:
            keys.append(key)

    csv_list = (os.environ.get('GEMINI_API_KEYS') or '').strip()
    if csv_list:
        for part in csv_list.replace(';', ',').replace('\n', ',').split(','):
            _push(part)

    _push(os.environ.get('GEMINI_API_KEY'))
    for i in range(2, 10):
        _push(os.environ.get(f'GEMINI_API_KEY_{i}'))

    if not keys:
        raise GeminiClientError(
            'Cle Gemini manquante — GEMINI_API_KEY ou GEMINI_API_KEYS dans .env'
        )
    return keys


def gemini_fallback_models(primary: Optional[str] = None) -> List[str]:
    """
    Chaine de modeles a essayer (primaire puis fallbacks) en cas de 503.

    Ordre : modele demande, puis GEMINI_FALLBACK_MODELS
    (defaut ``gemini-flash-latest,gemini-3.5-flash``).

    @param primary: Modele principal (sinon config)
    @returns: Liste ordonnee sans doublons
    """
    cfg_model = (
        primary
        or os.environ.get('GEMINI_DESIGN_MODEL')
        or os.environ.get('GEMINI_MODEL')
        or 'gemini-3.8-flash'
    )
    models: List[str] = []

    def _push(value: Optional[str]) -> None:
        name = (value or '').strip()
        if name and name not in models:
            models.append(name)

    _push(cfg_model)
    raw = (os.environ.get('GEMINI_FALLBACK_MODELS') or 'gemini-flash-latest,gemini-3.5-flash').strip()
    for part in raw.replace(';', ',').replace('\n', ',').split(','):
        _push(part)
    return models


def gemini_config() -> Dict[str, Any]:
    """
    Lit la configuration Gemini depuis l'environnement.

    @returns: Dict model / quota_retry_ms / quota_retry_rounds / fallbacks / concurrent
    """
    return {
        'model': (
            os.environ.get('GEMINI_DESIGN_MODEL')
            or os.environ.get('GEMINI_MODEL')
            or 'gemini-3.8-flash'
        ),
        # Pause seulement quand TOUS les comptes ont rate (pas entre chaque cle)
        'quota_retry_ms': int(os.environ.get('GEMINI_QUOTA_RETRY_MS') or 35_000),
        'quota_retry_rounds': int(os.environ.get('GEMINI_QUOTA_RETRY_ROUNDS') or 3),
        # Pause courte sur pure surcharge 503 (defaut 25s, plus 90s)
        'transient_retry_ms': int(os.environ.get('GEMINI_TRANSIENT_RETRY_MS') or 25_000),
        # Apres N cles 503 d'affilee, stop precoce du tour
        'max_consecutive_503_keys': int(os.environ.get('GEMINI_503_MAX_CONSECUTIVE_KEYS') or 2),
        # 2 Vision en parallele : accelere sans cramer autant qu'avec 5
        'max_concurrent_full_reports': int(os.environ.get('GEMINI_FULL_REPORT_MAX_CONCURRENT') or 2),
        'fallback_models': gemini_fallback_models(),
    }


def _key_tag(api_key: str, num: int, total: int) -> str:
    """Label court pour les logs (jamais la cle entiere)."""
    tail = api_key[-4:] if len(api_key) >= 4 else '????'
    return f'cle {num}/{total} (…{tail})'


def _parse_gemini_content(raw: str) -> str:
    """
    Extrait le texte de reponse generateContent.

    @param raw: Corps JSON brut
    @returns: Texte concatene des parts
    @raises GeminiClientError: JSON invalide ou contenu vide
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeminiClientError(f'Gemini — reponse JSON invalide: {raw[:200]}') from exc

    parts = (
        (data.get('candidates') or [{}])[0]
        .get('content', {})
        .get('parts')
        or []
    )
    content = ''.join((p.get('text') or '') for p in parts).strip()
    if not content:
        reason = (
            (data.get('candidates') or [{}])[0].get('finishReason')
            or (data.get('promptFeedback') or {}).get('blockReason')
            or 'inconnu'
        )
        raise GeminiClientError(f'Gemini — contenu vide ({reason})')
    return content


def _request_gemini(
    *,
    api_key: str,
    model: str,
    body: Dict[str, Any],
    timeout_ms: int,
) -> tuple[int, str]:
    """
    Execute un appel HTTP generateContent.

    @returns: (status_code, body_text)
    """
    url = f'{BASE_URL}/models/{model}:generateContent'
    resp = requests.post(
        url,
        params={'key': api_key},
        headers={'Content-Type': 'application/json'},
        json=body,
        timeout=max(5, timeout_ms / 1000.0),
    )
    return resp.status_code, resp.text or ''


def _is_transient_overload_body(status: int, raw: str) -> bool:
    """
    Detecte une surcharge temporaire Gemini (503 / high demand / UNAVAILABLE).

    Ce n'est PAS un quota journalier : il faut attendre et reessayer,
    pas basculer tout de suite en heuristique.

    @param status: Code HTTP
    @param raw: Corps reponse
    @returns: True si surcharge temporaire
    """
    if status == 503:
        return True
    low = (raw or '').lower()
    markers = (
        'high demand',
        'currently experiencing',
        'try again later',
        'unavailable',
        'overloaded',
    )
    if status >= 500 and any(m in low for m in markers):
        return True
    if status == 429 and 'high demand' in low:
        return True
    return False


def _notify_progress(progress_cb, message: str, pct: Optional[int] = None) -> None:
    """
    Pousse un message vers le journal UI (PROGRESS Celery) si callback fourni.

    @param progress_cb: Callable (message, pct?) ou None
    @param message: Ligne de log visible dans la fiche
    @param pct: Progression optionnelle 0-100
    """
    if not progress_cb:
        return
    msg = str(message or '').strip()
    if not msg:
        return
    try:
        progress_cb(msg, pct)
    except TypeError:
        try:
            progress_cb(msg)
        except Exception:
            pass
    except Exception:
        pass


def _call_one_key(
    *,
    api_key: str,
    tag: str,
    idx: int,
    model: str,
    body: Dict[str, Any],
    timeout_ms: int,
) -> Dict[str, Any]:
    """
    Un seul essai HTTP sur une cle (pas de pause longue : bascule rapide).

    @param api_key: Cle API
    @param tag: Label log
    @param idx: Index dans la liste active
    @param model: Modele Gemini
    @param body: Corps generateContent
    @param timeout_ms: Timeout HTTP
    @returns: Dict outcome (ok/content ou flags erreur)
    """
    try:
        status, raw = _request_gemini(
            api_key=api_key,
            model=model,
            body=body,
            timeout_ms=timeout_ms,
        )
    except requests.RequestException as exc:
        logger.warning('[Gemini] %s — reseau: %s → compte suivant', tag, exc)
        return {
            'ok': False,
            'api_key': api_key,
            'tag': tag,
            'idx': idx,
            'error': GeminiClientError(f'Gemini reseau: {exc}'),
            'saw_429': False,
            'saw_transient': False,
        }

    if status == 200:
        try:
            content = _parse_gemini_content(raw)
        except GeminiClientError as exc:
            logger.warning('[Gemini] %s — 200 mais parse KO: %s → compte suivant', tag, exc)
            return {
                'ok': False,
                'api_key': api_key,
                'tag': tag,
                'idx': idx,
                'error': exc,
                'saw_429': False,
                'saw_transient': False,
            }
        return {
            'ok': True,
            'api_key': api_key,
            'tag': tag,
            'idx': idx,
            'content': content,
        }

    last_error = GeminiClientError(f'Gemini {status}: {(raw or "")[:400]}')

    if status == 429:
        is_rpd = _is_daily_quota_body(raw or '')
        with _keys_lock:
            if is_rpd:
                _mark_key_rpd_exhausted(api_key, tag)
        logger.warning(
            '[Gemini] %s — %s → saute au compte suivant',
            tag,
            'RPD jour (blacklist)' if is_rpd else '429 quota/RPM',
        )
        return {
            'ok': False,
            'api_key': api_key,
            'tag': tag,
            'idx': idx,
            'error': last_error,
            'saw_429': True,
            'saw_transient': False,
            'is_rpd': is_rpd,
            'raw': raw or '',
        }

    if status == 401:
        with _keys_lock:
            _revoked_keys.add(api_key)
        logger.warning('[Gemini] %s — 401, ignoree → compte suivant', tag)
        return {
            'ok': False,
            'api_key': api_key,
            'tag': tag,
            'idx': idx,
            'error': last_error,
            'saw_429': False,
            'saw_transient': False,
        }

    if status == 403:
        lowered = (raw or '').lower()
        hard_revoke = (
            'api key not valid' in lowered
            or 'api_key_invalid' in lowered
            or 'invalid api key' in lowered
            or 'permission_denied' in lowered
            or 'denied access' in lowered
            or 'has been denied' in lowered
        )
        if hard_revoke:
            with _keys_lock:
                _revoked_keys.add(api_key)
            logger.warning('[Gemini] %s — 403 refuse → compte suivant', tag)
        else:
            logger.warning('[Gemini] %s — 403 → compte suivant: %s', tag, (raw or '')[:180])
        return {
            'ok': False,
            'api_key': api_key,
            'tag': tag,
            'idx': idx,
            'error': last_error,
            'saw_429': False,
            'saw_transient': False,
        }

    if _is_transient_overload_body(status, raw or '') or status >= 500:
        logger.warning(
            '[Gemini] %s — surcharge/erreur %s → saute au compte suivant',
            tag,
            status,
        )
        return {
            'ok': False,
            'api_key': api_key,
            'tag': tag,
            'idx': idx,
            'error': last_error,
            'saw_429': False,
            'saw_transient': True,
        }

    logger.warning('[Gemini] %s — erreur %s → compte suivant', tag, status)
    return {
        'ok': False,
        'api_key': api_key,
        'tag': tag,
        'idx': idx,
        'error': last_error,
        'saw_429': False,
        'saw_transient': False,
    }


def _try_all_keys(
    *,
    api_keys: Sequence[str],
    model: str,
    body: Dict[str, Any],
    timeout_ms: int,
    progress_cb=None,
) -> Dict[str, Any]:
    """
    Bascule immediate de compte en compte (pas de parallele, pas d'attente 60s).

    Une requete Vision = 1 cle a la fois. Sur 503 : essaie les modeles
    de repli sur la meme cle, puis passe a la suivante. Apres N cles
    503 d'affilee, stop precoce pour eviter de bruler tout le pool.

    @param api_keys: Cles configurees
    @param model: Modele Gemini primaire
    @param body: Corps generateContent
    @param timeout_ms: Timeout HTTP par cle
    @param progress_cb: Callback journal UI (message, pct)
    @returns: Dict avec content ou error / saw_429 / saw_transient / early_stop_503
    """
    global _preferred_key_index

    cfg = gemini_config()
    model_chain = gemini_fallback_models(model)
    max_consec_503 = max(1, int(cfg.get('max_consecutive_503_keys') or 2))

    active = _active_api_keys(api_keys)
    if not active and _rpd_exhausted_until:
        logger.warning(
            '[Gemini] %s cle(s) en RPD memoire — probe live avant d\'abandonner…',
            len(_rpd_exhausted_until),
        )
        _notify_progress(
            progress_cb,
            f'Reveil de {len(_rpd_exhausted_until)} compte(s) marques RPD…',
            66,
        )
        active = _probe_revive_rpd_keys(api_keys, model)

    n = len(active)
    if not n:
        rpd_n = len(_rpd_exhausted_until)
        if rpd_n:
            msg = (
                f'Gemini — aucune cle active ({rpd_n} compte(s) en RPD jusqu\'au reset Pacific)'
            )
        else:
            msg = 'Gemini — aucune cle active (toutes revoquees 403 ?)'
        _notify_progress(progress_cb, msg, 68)
        return {
            'error': GeminiQuotaError(msg) if rpd_n else GeminiClientError(msg),
            'saw_429': bool(rpd_n),
            'saw_transient': False,
            'all_keys_exhausted': True,
            'early_stop_503': False,
        }

    # Prefere la derniere cle OK, puis tourne sur les autres
    start = _preferred_key_index % n
    order = list(range(start, n)) + list(range(0, start))

    logger.warning(
        '[Gemini] rotation sequentielle: %s compte(s) actif(s) / %s, debut=%s, modeles=%s',
        n,
        len(api_keys),
        start + 1,
        ' → '.join(model_chain),
    )
    _notify_progress(
        progress_cb,
        f'Rotation multi-comptes : {n} actif(s) — fallback modele si 503…',
        66,
    )

    last_error: Optional[Exception] = None
    saw_429 = False
    saw_transient = False
    keys_attempted = 0
    consecutive_503 = 0
    early_stop_503 = False
    tried_tags: List[str] = []

    for pos, idx in enumerate(order):
        api_key = active[idx]
        tag = _key_tag(api_key, pos + 1, n)
        keys_attempted += 1
        tried_tags.append(tag)
        logger.warning('[Gemini] essai compte %s/%s — %s', pos + 1, n, tag)
        _notify_progress(
            progress_cb,
            f'Essai compte {pos + 1}/{n} ({tag})…',
            min(78, 66 + pos),
        )

        key_transient_only = False
        outcome: Dict[str, Any] = {}

        for mid, try_model in enumerate(model_chain):
            if mid > 0:
                logger.warning(
                    '[Gemini] %s — fallback modele %s (apres 503)',
                    tag,
                    try_model,
                )
                _notify_progress(
                    progress_cb,
                    f'{tag} — fallback modele {try_model}…',
                    min(78, 66 + pos),
                )

            outcome = _call_one_key(
                api_key=api_key,
                tag=f'{tag}/{try_model}',
                idx=idx,
                model=try_model,
                body=body,
                timeout_ms=timeout_ms,
            )
            if outcome.get('saw_429'):
                saw_429 = True
            if outcome.get('saw_transient'):
                saw_transient = True
            if outcome.get('error'):
                last_error = outcome['error']

            if outcome.get('ok'):
                with _keys_lock:
                    _preferred_key_index = idx
                if mid > 0 or pos > 0:
                    logger.warning(
                        '[Gemini] OK avec %s modele=%s (bascule)',
                        tag,
                        try_model,
                    )
                    _notify_progress(
                        progress_cb,
                        f'OK avec {tag} ({try_model})',
                        80,
                    )
                else:
                    logger.warning('[Gemini] OK avec %s', tag)
                    _notify_progress(progress_cb, f'OK avec {tag}', 80)
                return {
                    'content': outcome['content'],
                    'model_used': try_model,
                }

            # 429 / 401 / 403 / autre : pas de fallback modele, cle suivante
            if not outcome.get('saw_transient'):
                key_transient_only = False
                break

            # 503 : essaie le modele suivant sur la meme cle
            key_transient_only = True
            if mid + 1 < len(model_chain):
                continue
            break

        if outcome.get('saw_429'):
            consecutive_503 = 0
            why = 'RPD' if outcome.get('is_rpd') else '429'
            _notify_progress(
                progress_cb,
                f'{tag} — {why}, saute au compte suivant…',
                min(78, 66 + pos),
            )
        elif key_transient_only:
            consecutive_503 += 1
            _notify_progress(
                progress_cb,
                f'{tag} — 503 sur tous les modeles ({consecutive_503}/{max_consec_503})…',
                min(78, 66 + pos),
            )
            if consecutive_503 >= max_consec_503:
                early_stop_503 = True
                logger.warning(
                    '[Gemini] stop precoce apres %s cle(s) 503 d\'affilee (max=%s)',
                    consecutive_503,
                    max_consec_503,
                )
                _notify_progress(
                    progress_cb,
                    f'Stop precoce : {consecutive_503} comptes 503 d\'affilee — pause courte…',
                    79,
                )
                break
        else:
            consecutive_503 = 0
            _notify_progress(
                progress_cb,
                f'{tag} — echec, saute au compte suivant…',
                min(78, 66 + pos),
            )

    logger.warning(
        '[Gemini] fin de tour (%s comptes, early_stop_503=%s) — %s',
        keys_attempted,
        early_stop_503,
        ', '.join(tried_tags),
    )
    if not early_stop_503:
        _notify_progress(
            progress_cb,
            f'Tous les comptes ont echoue ({keys_attempted})',
            79,
        )
    return {
        'error': last_error or GeminiClientError('Gemini — echec inconnu'),
        'saw_429': saw_429,
        'saw_transient': saw_transient,
        'all_keys_exhausted': not early_stop_503,
        'early_stop_503': early_stop_503,
    }


def gemini_generate_content(
    *,
    parts: List[Dict[str, Any]],
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    json_mode: bool = False,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    quota_retry_rounds: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    progress_cb=None,
) -> str:
    """
    Appel Gemini generateContent avec rotation de cles.

    @param parts: Parts utilisateur (text et/ou inline_data)
    @param system_instruction: Instruction systeme optionnelle
    @param model: Modele (defaut GEMINI_DESIGN_MODEL / GEMINI_MODEL)
    @param max_tokens: Limite de tokens de sortie
    @param temperature: Temperature de generation
    @param json_mode: Force responseMimeType application/json
    @param timeout_ms: Timeout HTTP en ms
    @param quota_retry_rounds: Tours de pause apres epuisement 429
    @param tools: Outils Gemini optionnels (ex: [{"url_context": {}}])
    @param progress_cb: Callback journal UI (message, pct)
    @returns: Texte de reponse
    @raises GeminiClientError: Echec apres retries
    """
    cfg = gemini_config()
    resolved_model = model or cfg['model']
    rounds = (
        quota_retry_rounds
        if quota_retry_rounds is not None
        else cfg['quota_retry_rounds']
    )
    api_keys = get_gemini_api_keys()

    # thinkingLevel low : gemini-3.x flash peut sinon "réfléchir" 30-60s pour un JSON simple
    body: Dict[str, Any] = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {
            'temperature': temperature,
            'maxOutputTokens': max_tokens,
            'thinkingConfig': {'thinkingLevel': 'low'},
        },
    }
    if system_instruction:
        body['systemInstruction'] = {'parts': [{'text': system_instruction}]}
    if json_mode:
        body['generationConfig']['responseMimeType'] = 'application/json'
    if tools:
        body['tools'] = tools

    # Circuit ouvert (autre job a deja epuise toutes les cles) → stop immediat
    try:
        from services.gemini_queue import (
            is_gemini_quota_circuit_open,
            format_gemini_circuit_message,
        )
        if is_gemini_quota_circuit_open():
            msg = format_gemini_circuit_message()
            _notify_progress(progress_cb, msg, 70)
            raise GeminiQuotaError(msg)
    except GeminiQuotaError:
        raise
    except Exception:
        pass

    last_error: Optional[Exception] = None
    for round_idx in range(rounds + 1):
        result = _try_all_keys(
            api_keys=api_keys,
            model=resolved_model,
            body=body,
            timeout_ms=timeout_ms,
            progress_cb=progress_cb,
        )
        if result.get('content'):
            return result['content']

        last_error = result.get('error')
        # Toutes les cles en RPD memoire : pause inutile (reset demain seulement)
        active_left = _active_api_keys(api_keys)
        all_rpd = (
            bool(result.get('saw_429'))
            and bool(result.get('all_keys_exhausted'))
            and not active_left
        )
        if all_rpd:
            logger.warning(
                '[Gemini] toutes les cles en RPD — skip pauses, circuit breaker'
            )
            _notify_progress(
                progress_cb,
                'Quota Gemini journalier epuise (toutes les cles) — arret des retries',
                70,
            )
            break
        # 429 RPM/RPD OU 503 (y compris stop precoce apres N cles) : pause puis nouvel essai
        can_wait = (
            (result.get('saw_429') or result.get('saw_transient'))
            and (result.get('all_keys_exhausted') or result.get('early_stop_503'))
            and round_idx < rounds
            and cfg['quota_retry_ms'] > 0
        )
        if not can_wait:
            break
        # Surcharge modele : pause plus courte que l'ancien 90s
        wait_ms = int(cfg['quota_retry_ms'])
        if result.get('saw_transient') and not result.get('saw_429'):
            wait_ms = int(cfg.get('transient_retry_ms') or 25_000)
        secs = round(wait_ms / 1000)
        why = 'surcharge 503' if result.get('saw_transient') and not result.get('saw_429') else 'quota 429'
        # Prochain tour : demarrer sur le 1er fallback si stop precoce 503
        if result.get('early_stop_503') or (
            result.get('saw_transient') and not result.get('saw_429')
        ):
            chain = gemini_fallback_models(resolved_model)
            if len(chain) > 1 and chain[1] != resolved_model:
                resolved_model = chain[1]
                logger.warning(
                    '[Gemini] prochain tour commence par modele fallback %s',
                    resolved_model,
                )
                _notify_progress(
                    progress_cb,
                    f'Prochain essai sur modele {resolved_model}…',
                    70,
                )
        logger.warning(
            '[Gemini] pause %ss (%s) puis nouvel essai…',
            secs,
            why,
        )
        _notify_progress(
            progress_cb,
            f'Pause {secs}s ({why}) puis nouvel essai…',
            70,
        )
        time.sleep(wait_ms / 1000.0)

    hint = (
        f' ({len(api_keys)} cles configurees)'
        if len(api_keys) > 1
        else ''
    )
    # Dernier tour encore en 429 sur toutes les cles → erreur quota explicite
    if last_error and is_gemini_quota_error(last_error):
        kind = 'rpd' if not _active_api_keys(api_keys) else 'rpm'
        try:
            from services.gemini_queue import (
                arm_gemini_quota_circuit,
                abort_pending_gemini_queue,
            )
            arm_gemini_quota_circuit(
                f'Quota Gemini atteint — toutes les cles en 429{hint}',
                kind=kind,
            )
            abort_pending_gemini_queue(
                f'Quota Gemini atteint — toutes les cles en 429{hint}'
            )
        except Exception as circ_exc:
            logger.debug('circuit breaker arm ignore: %s', circ_exc)
        raise GeminiQuotaError(
            f'Quota Gemini atteint — toutes les cles en 429{hint}. '
            f'Reessayer dans quelques minutes (reset RPM) ou demain (reset RPD Pacific). '
            f'Detail: {last_error}'
        )
    # 503 persistant apres retries → message clair (pas confondre avec quota)
    err_txt = str(last_error or '')
    if '503' in err_txt or 'high demand' in err_txt.lower():
        raise GeminiClientError(
            f'Gemini surcharge temporaire (503 high demand){hint}. '
            f'Reessayer dans quelques minutes — ce n\'est pas un quota journalier. '
            f'Detail: {last_error}'
        )
    raise GeminiClientError(f'{last_error}{hint}' if last_error else f'Gemini echec{hint}')


def _parse_gemini_parts(raw: str) -> List[Dict[str, Any]]:
    """
    Extrait toutes les parts (texte + inline_data) d'une reponse generateContent.

    @param raw: Corps JSON brut
    @returns: Liste de parts
    @raises GeminiClientError: JSON invalide ou aucune part
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeminiClientError(f'Gemini — reponse JSON invalide: {raw[:200]}') from exc

    parts = (
        (data.get('candidates') or [{}])[0]
        .get('content', {})
        .get('parts')
        or []
    )
    if not parts:
        reason = (
            (data.get('candidates') or [{}])[0].get('finishReason')
            or (data.get('promptFeedback') or {}).get('blockReason')
            or 'inconnu'
        )
        raise GeminiClientError(f'Gemini — contenu vide ({reason})')
    return parts


def gemini_generate_images(
    *,
    prompt: str,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    aspect_ratio: str = '16:9',
    timeout_ms: int = 120_000,
    reference_images: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Genere une ou plusieurs images via Gemini (Nano Banana / flash-image).

    @param prompt: Consigne texte
    @param system_instruction: Instruction systeme optionnelle
    @param model: Modele image (defaut GEMINI_IMAGE_MODEL)
    @param aspect_ratio: 1:1|3:4|4:3|9:16|16:9
    @param timeout_ms: Timeout HTTP
    @param reference_images: Images de reference optionnelles
        [{bytes|data_b64, mime_type, device?}]
    @returns: Liste {mime_type, data_b64, bytes}
    @raises GeminiClientError: Echec API
    """
    cfg = gemini_config()
    resolved_model = (
        model
        or os.environ.get('GEMINI_IMAGE_MODEL')
        or 'gemini-2.5-flash-image'
    )
    api_keys = get_gemini_api_keys()

    parts: List[Dict[str, Any]] = [{'text': prompt}]
    for img in reference_images or []:
        mime = str(img.get('mime_type') or 'image/webp')
        raw_b = img.get('bytes')
        if raw_b is None and img.get('data_b64'):
            raw_b = base64.b64decode(img['data_b64'])
        if not raw_b:
            continue
        parts.append({
            'inline_data': {
                'mime_type': mime,
                'data': base64.b64encode(raw_b).decode('ascii'),
            },
        })

    body: Dict[str, Any] = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {
            'responseModalities': ['TEXT', 'IMAGE'],
            'imageConfig': {
                'aspectRatio': aspect_ratio if aspect_ratio in (
                    '1:1', '3:4', '4:3', '9:16', '16:9'
                ) else '16:9',
            },
        },
    }
    if system_instruction:
        body['systemInstruction'] = {'parts': [{'text': system_instruction}]}

    last_error: Optional[Exception] = None
    active = _active_api_keys(api_keys)
    if not active:
        rpd_n = len(_rpd_exhausted_until)
        if rpd_n:
            raise GeminiQuotaError(
                f'Gemini image — aucune cle active ({rpd_n} compte(s) en RPD)'
            )
        raise GeminiClientError('Gemini — aucune cle active pour image gen')

    global _preferred_key_index
    n = len(active)
    for offset in range(n):
        idx = (_preferred_key_index + offset) % n
        api_key = active[idx]
        tag = _key_tag(api_key, offset + 1, len(api_keys))
        try:
            status, raw = _request_gemini(
                api_key=api_key,
                model=resolved_model,
                body=body,
                timeout_ms=timeout_ms,
            )
        except requests.RequestException as exc:
            last_error = GeminiClientError(f'Gemini reseau: {exc}')
            logger.warning('[GeminiImg] %s — reseau, cle suivante…', tag)
            continue

        if status == 200:
            try:
                resp_parts = _parse_gemini_parts(raw)
            except GeminiClientError as exc:
                last_error = exc
                continue
            images: List[Dict[str, Any]] = []
            for p in resp_parts:
                inline = p.get('inline_data') or p.get('inlineData') or {}
                data_b64 = inline.get('data')
                mime = inline.get('mime_type') or inline.get('mimeType') or 'image/png'
                if not data_b64:
                    continue
                try:
                    raw_bytes = base64.b64decode(data_b64)
                except Exception:
                    continue
                images.append({
                    'mime_type': mime,
                    'data_b64': data_b64,
                    'bytes': raw_bytes,
                })
            if images:
                _preferred_key_index = idx
                if offset > 0:
                    logger.warning('[GeminiImg] OK avec %s (%s image(s))', tag, len(images))
                return images
            last_error = GeminiClientError('Gemini image — aucune image dans la reponse')
            continue

        last_error = GeminiClientError(f'Gemini {status}: {raw[:400]}')
        if status == 429:
            if _is_daily_quota_body(raw):
                _mark_key_rpd_exhausted(api_key, tag)
            else:
                logger.warning('[GeminiImg] %s — quota RPM 429, cle suivante…', tag)
            continue
        if status in (401, 403):
            lowered = (raw or '').lower()
            if status == 401 or 'api key not valid' in lowered or 'api_key_invalid' in lowered:
                _revoked_keys.add(api_key)
                logger.warning('[GeminiImg] %s — cle ignoree (%s)', tag, status)
            else:
                logger.warning('[GeminiImg] %s — %s, cle suivante…', tag, status)
            continue
        logger.warning('[GeminiImg] %s — erreur %s', tag, status)

    raise GeminiClientError(str(last_error) if last_error else 'Gemini image echec')


def gemini_vision_json(
    *,
    prompt: str,
    image_bytes: bytes,
    mime_type: str = 'image/webp',
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyse une image via Gemini Vision et parse la reponse JSON.

    @param prompt: Consigne utilisateur
    @param image_bytes: Contenu binaire de l'image
    @param mime_type: MIME (image/webp, image/jpeg, …)
    @param system_instruction: Instruction systeme
    @param model: Modele optionnel
    @returns: Dict JSON parse
    @raises GeminiClientError: Echec API ou JSON invalide
    """
    return gemini_vision_multi_json(
        prompt=prompt,
        images=[{'bytes': image_bytes, 'mime_type': mime_type}],
        system_instruction=system_instruction,
        model=model,
        max_tokens=2048,
    )


def gemini_vision_multi_json(
    *,
    prompt: str,
    images: List[Dict[str, Any]],
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    tools: Optional[List[Dict[str, Any]]] = None,
    quota_retry_rounds: Optional[int] = None,
    progress_cb=None,
) -> Dict[str, Any]:
    """
    Analyse multimodale (plusieurs images + texte) via Gemini, reponse JSON.

    @param prompt: Consigne utilisateur
    @param images: Liste de dicts {bytes|image_bytes, mime_type?}
    @param system_instruction: Instruction systeme
    @param model: Modele optionnel
    @param max_tokens: Limite de sortie
    @param timeout_ms: Timeout HTTP en ms
    @param tools: Outils Gemini optionnels (ex. url_context)
    @param quota_retry_rounds: Tours de pause 429 (defaut config)
    @param progress_cb: Callback journal UI (message, pct)
    @returns: Dict JSON parse
    @raises GeminiClientError: Echec API ou JSON invalide
    """
    parts: List[Dict[str, Any]] = [{'text': prompt}]
    for img in images or []:
        raw = img.get('bytes') or img.get('image_bytes')
        if not raw:
            continue
        mime = (img.get('mime_type') or img.get('mime') or 'image/webp').strip()
        b64 = base64.b64encode(raw).decode('ascii')
        parts.append({
            'inline_data': {
                'mime_type': mime,
                'data': b64,
            }
        })
    raw = gemini_generate_content(
        parts=parts,
        system_instruction=system_instruction,
        model=model,
        json_mode=True,
        temperature=0.25,
        max_tokens=max_tokens,
        timeout_ms=timeout_ms,
        tools=tools,
        quota_retry_rounds=quota_retry_rounds,
        progress_cb=progress_cb,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find('{')
        end = raw.rfind('}')
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise GeminiClientError(f'Gemini Vision multi — JSON invalide: {raw[:300]}')
