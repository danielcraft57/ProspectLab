# -*- coding: utf-8 -*-
"""
File d'attente globale pour les rapports Gemini (20+ lancements).

Espace les demarrages via Redis pour respecter le free tier (RPM/RPD),
deduplique les entreprises deja en file, et expose position / ETA.

Quand toutes les cles sont en 429, un circuit breaker coupe la file :
plus de pauses inutiles, les jobs encore en countdown sont revoques.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_redis_client = None

# Delai entre deux demarrages de rapport (Vision). Free tier : ~60-90s safe.
_DEFAULT_SPACING = int(os.environ.get('GEMINI_JOB_SPACING_SEC') or 90)
_PENDING_TTL = int(os.environ.get('GEMINI_QUEUE_PENDING_TTL_SEC') or 7200)
_NEXT_TS_KEY = 'prospectlab:gemini:queue:next_start_ts'
_PENDING_KEY = 'prospectlab:gemini:queue:pending_entreprises'
_TASK_IDS_KEY = 'prospectlab:gemini:queue:task_ids'
_CIRCUIT_KEY = 'prospectlab:gemini:quota_circuit'
# Cooldown court si RPM (pas RPD) : inutile d'attendre 90s × N jobs
_DEFAULT_RPM_CIRCUIT_SEC = int(os.environ.get('GEMINI_QUOTA_CIRCUIT_RPM_SEC') or 180)


def _redis():
    """Client Redis lazy (broker Celery)."""
    global _redis_client
    if _redis_client is None:
        import redis
        from config import CELERY_BROKER_URL
        _redis_client = redis.Redis.from_url(
            CELERY_BROKER_URL or 'redis://127.0.0.1:6379/0',
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
    return _redis_client


def gemini_job_spacing_sec() -> int:
    """
    Intervalle min entre deux demarrages de rapport Gemini.

    @returns: Secondes (>= 30)
    """
    return max(30, int(os.environ.get('GEMINI_JOB_SPACING_SEC') or _DEFAULT_SPACING))


def reserve_gemini_queue_slot(entreprise_id: int) -> Dict[str, Any]:
    """
    Reserve une place dans la file Gemini (atomique Redis).

    Refuse si le circuit breaker quota est ouvert (toutes cles a plat).

    @param entreprise_id: ID entreprise
    @returns: Dict countdown, position, eta_sec, already_pending, spacing_sec
              ou circuit_open=True si quota epuise
    """
    circuit = get_gemini_quota_circuit()
    if circuit:
        return {
            'already_pending': False,
            'countdown': 0,
            'position': 0,
            'eta_sec': 0,
            'spacing_sec': gemini_job_spacing_sec(),
            'circuit_open': True,
            'circuit': circuit,
        }

    eid = str(int(entreprise_id))
    spacing = gemini_job_spacing_sec()
    now = time.time()
    script = """
local next_key = KEYS[1]
local pending_key = KEYS[2]
local eid = ARGV[1]
local spacing = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

if redis.call('sismember', pending_key, eid) == 1 then
  return {-1, 0, 0}
end

redis.call('sadd', pending_key, eid)
redis.call('expire', pending_key, ttl)

local next_ts = tonumber(redis.call('get', next_key) or '0')
if (not next_ts) or next_ts < now then
  next_ts = now
end
local countdown = next_ts - now
if countdown < 0 then countdown = 0 end
local new_next = next_ts + spacing
redis.call('set', next_key, string.format('%.3f', new_next), 'EX', ttl)

local position = math.floor(countdown / spacing) + 1
if position < 1 then position = 1 end
return {countdown, position, new_next}
"""
    try:
        raw = _redis().eval(
            script,
            2,
            _NEXT_TS_KEY,
            _PENDING_KEY,
            eid,
            spacing,
            now,
            _PENDING_TTL,
        )
        countdown = float(raw[0] or 0)
        if countdown < 0:
            # deja en file
            return {
                'already_pending': True,
                'countdown': 0,
                'position': 0,
                'eta_sec': 0,
                'spacing_sec': spacing,
            }
        position = int(raw[1] or 1)
        return {
            'already_pending': False,
            'countdown': max(0.0, countdown),
            'position': max(1, position),
            'eta_sec': max(0.0, countdown),
            'spacing_sec': spacing,
        }
    except Exception as exc:
        logger.warning('reserve_gemini_queue_slot fallback: %s', exc)
        # Sans Redis : petit stagger local aleatoire faible
        return {
            'already_pending': False,
            'countdown': 0.0,
            'position': 1,
            'eta_sec': 0.0,
            'spacing_sec': spacing,
            'fallback': True,
        }


def register_gemini_queue_task(entreprise_id: int, task_id: str) -> None:
    """
    Associe un task Celery a une entreprise en file (pour revoke au circuit).

    @param entreprise_id: ID entreprise
    @param task_id: UUID Celery
    """
    tid = str(task_id or '').strip()
    if not tid:
        return
    try:
        r = _redis()
        r.hset(_TASK_IDS_KEY, str(int(entreprise_id)), tid)
        r.expire(_TASK_IDS_KEY, _PENDING_TTL)
    except Exception as exc:
        logger.debug('register_gemini_queue_task ignore: %s', exc)


def release_gemini_queue_slot(entreprise_id: int) -> None:
    """
    Retire l'entreprise de la file pending (fin / erreur / annulation).

    @param entreprise_id: ID entreprise
    """
    eid = str(int(entreprise_id))
    try:
        r = _redis()
        r.srem(_PENDING_KEY, eid)
        r.hdel(_TASK_IDS_KEY, eid)
    except Exception as exc:
        logger.debug('release_gemini_queue_slot ignore: %s', exc)


def get_gemini_quota_circuit() -> Optional[Dict[str, Any]]:
    """
    Lit le circuit breaker quota Gemini (ouvert = toutes cles a plat).

    @returns: Dict reason/kind/until_ts ou None si ferme
    """
    try:
        raw = _redis().get(_CIRCUIT_KEY)
        if not raw:
            return None
        data = json.loads(raw)
        until = float(data.get('until_ts') or 0)
        if until and until <= time.time():
            clear_gemini_quota_circuit()
            return None
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.debug('get_gemini_quota_circuit ignore: %s', exc)
        return None


def is_gemini_quota_circuit_open() -> bool:
    """
    True si le circuit breaker quota est ouvert.

    @returns: bool
    """
    return get_gemini_quota_circuit() is not None


def arm_gemini_quota_circuit(
    reason: str,
    *,
    kind: str = 'rpm',
    until_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Ouvre le circuit breaker (partage entre workers via Redis).

    @param reason: Message court (ex: toutes les cles en 429)
    @param kind: 'rpm' (cooldown court) ou 'rpd' (jusqu'au reset Pacific)
    @param until_ts: Fin du blocage (unix). Defaut selon kind.
    @returns: Payload circuit enregistre
    """
    kind_norm = 'rpd' if str(kind or '').lower() == 'rpd' else 'rpm'
    if until_ts is None:
        if kind_norm == 'rpd':
            try:
                from services.gemini_client import _next_pacific_midnight_ts
                until_ts = float(_next_pacific_midnight_ts())
            except Exception:
                until_ts = time.time() + 12 * 3600
        else:
            until_ts = time.time() + max(60, _DEFAULT_RPM_CIRCUIT_SEC)

    until_ts = float(until_ts)
    ttl = max(30, int(until_ts - time.time()) + 5)
    payload = {
        'reason': str(reason or 'Quota Gemini epuise')[:400],
        'kind': kind_norm,
        'until_ts': until_ts,
        'armed_at': time.time(),
    }
    try:
        r = _redis()
        r.set(_CIRCUIT_KEY, json.dumps(payload, ensure_ascii=False), ex=ttl)
        logger.warning(
            '[Gemini queue] circuit OPEN kind=%s ttl=%ss — %s',
            kind_norm,
            ttl,
            payload['reason'][:120],
        )
    except Exception as exc:
        logger.warning('arm_gemini_quota_circuit Redis KO: %s', exc)
    return payload


def clear_gemini_quota_circuit() -> None:
    """Ferme le circuit breaker quota."""
    try:
        _redis().delete(_CIRCUIT_KEY)
    except Exception as exc:
        logger.debug('clear_gemini_quota_circuit ignore: %s', exc)


def abort_pending_gemini_queue(
    reason: str = 'Quota Gemini epuise — file annulee',
    *,
    exclude_entreprise_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Annule la file Gemini : reset ETA, revoke tasks en countdown, clear pending.

    @param reason: Motif (logs / UI)
    @param exclude_entreprise_id: Ne pas revoquer la task courante
    @returns: Dict aborted_ids, revoked_task_ids, reason
    """
    aborted: List[int] = []
    revoked: List[str] = []
    exclude = str(int(exclude_entreprise_id)) if exclude_entreprise_id is not None else None
    try:
        r = _redis()
        pending = list(r.smembers(_PENDING_KEY) or [])
        task_map = r.hgetall(_TASK_IDS_KEY) or {}
        # Reset file (plus de countdown inutile)
        r.delete(_NEXT_TS_KEY)
        r.delete(_PENDING_KEY)

        for eid_raw in pending:
            eid_s = str(eid_raw)
            if exclude and eid_s == exclude:
                continue
            try:
                aborted.append(int(eid_s))
            except (TypeError, ValueError):
                continue

        # Revoke Celery (countdown non demarre) — terminate=False = soft
        try:
            from celery_app import celery
            for eid_s, tid in task_map.items():
                if exclude and eid_s == exclude:
                    continue
                tid = str(tid or '').strip()
                if not tid:
                    continue
                try:
                    celery.control.revoke(tid, terminate=False)
                    revoked.append(tid)
                except Exception as rev_exc:
                    logger.debug('revoke %s ignore: %s', tid, rev_exc)
        except Exception as celery_exc:
            logger.warning('abort_pending_gemini_queue revoke KO: %s', celery_exc)

        # Nettoie le map sauf la task courante
        if exclude and exclude in task_map:
            keep = task_map.get(exclude)
            r.delete(_TASK_IDS_KEY)
            if keep:
                r.hset(_TASK_IDS_KEY, exclude, keep)
                r.expire(_TASK_IDS_KEY, _PENDING_TTL)
        else:
            r.delete(_TASK_IDS_KEY)

        logger.warning(
            '[Gemini queue] abort file — %s entreprise(s), %s task(s) revokees — %s',
            len(aborted),
            len(revoked),
            str(reason)[:120],
        )
    except Exception as exc:
        logger.warning('abort_pending_gemini_queue: %s', exc)

    return {
        'aborted_ids': aborted,
        'revoked_task_ids': revoked,
        'reason': str(reason or '')[:400],
    }


def format_gemini_queue_message(info: Dict[str, Any]) -> str:
    """
    Message UI pour une reservation de file.

    @param info: Resultat reserve_gemini_queue_slot
    @returns: Texte court FR
    """
    if info.get('circuit_open'):
        circuit = info.get('circuit') or {}
        kind = str(circuit.get('kind') or 'rpm')
        if kind == 'rpd':
            return 'Quota Gemini journalier epuise — reessaie demain (reset Pacific)'
        return 'Quota Gemini epuise — file en pause, reessaie dans quelques minutes'
    if info.get('already_pending'):
        return 'Deja en file Gemini pour cette fiche'
    pos = int(info.get('position') or 1)
    eta = int(info.get('eta_sec') or 0)
    if pos <= 1 and eta < 5:
        return 'Rapport Gemini demarre…'
    mins = max(1, (eta + 59) // 60)
    return f'En file Gemini (#{pos}) — ~{mins} min'


def format_gemini_circuit_message(circuit: Optional[Dict[str, Any]] = None) -> str:
    """
    Message UI pour un circuit ouvert.

    @param circuit: Payload get_gemini_quota_circuit (optionnel)
    @returns: Texte FR
    """
    data = circuit if isinstance(circuit, dict) else get_gemini_quota_circuit()
    if not data:
        return 'Quota Gemini epuise'
    kind = str(data.get('kind') or 'rpm')
    until = float(data.get('until_ts') or 0)
    left = max(0, int(until - time.time()))
    if kind == 'rpd':
        hrs = max(1, (left + 3599) // 3600)
        return (
            f'Quota Gemini journalier epuise (toutes les cles). '
            f'Reessaie dans ~{hrs}h (reset Pacific). File annulee.'
        )
    mins = max(1, (left + 59) // 60)
    return (
        f'Quota Gemini epuise (toutes les cles en 429). '
        f'Reessaie dans ~{mins} min. File annulee — pas la peine d\'attendre.'
    )
