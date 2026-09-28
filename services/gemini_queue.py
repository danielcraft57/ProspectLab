# -*- coding: utf-8 -*-
"""
File d'attente globale pour les rapports Gemini (20+ lancements).

Espace les demarrages via Redis pour respecter le free tier (RPM/RPD),
deduplique les entreprises deja en file, et expose position / ETA.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_redis_client = None

# Delai entre deux demarrages de rapport (Vision). Free tier : ~60-90s safe.
_DEFAULT_SPACING = int(os.environ.get('GEMINI_JOB_SPACING_SEC') or 90)
_PENDING_TTL = int(os.environ.get('GEMINI_QUEUE_PENDING_TTL_SEC') or 7200)
_NEXT_TS_KEY = 'prospectlab:gemini:queue:next_start_ts'
_PENDING_KEY = 'prospectlab:gemini:queue:pending_entreprises'


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

    @param entreprise_id: ID entreprise
    @returns: Dict countdown, position, eta_sec, already_pending, spacing_sec
    """
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


def release_gemini_queue_slot(entreprise_id: int) -> None:
    """
    Retire l'entreprise de la file pending (fin / erreur / annulation).

    @param entreprise_id: ID entreprise
    """
    try:
        _redis().srem(_PENDING_KEY, str(int(entreprise_id)))
    except Exception as exc:
        logger.debug('release_gemini_queue_slot ignore: %s', exc)


def format_gemini_queue_message(info: Dict[str, Any]) -> str:
    """
    Message UI pour une reservation de file.

    @param info: Resultat reserve_gemini_queue_slot
    @returns: Texte court FR
    """
    if info.get('already_pending'):
        return 'Deja en file Gemini pour cette fiche'
    pos = int(info.get('position') or 1)
    eta = int(info.get('eta_sec') or 0)
    if pos <= 1 and eta < 5:
        return 'Rapport Gemini demarre…'
    mins = max(1, (eta + 59) // 60)
    return f'En file Gemini (#{pos}) — ~{mins} min'
