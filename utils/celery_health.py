"""
Vérifications légères du broker Celery (Redis).

Évite celery.control.inspect().active() à chaque événement WebSocket : sous charge
(20–50 analyses d'affilée), inspect interroge tous les workers et peut saturer Redis
ou bloquer longtemps — surtout avec Gunicorn + eventlet (un seul cœur logique).

Un simple PING Redis valide que les tâches peuvent être enfilées ; la présence de
workers actifs doit être assurée côté ops (systemd, -Q celery,heavy).
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

_broker_cache: dict = {"ts": 0.0, "ok": True}
_broker_lock = threading.Lock()

_workers_cache: dict = {"ts": 0.0, "count": 0}
_workers_lock = threading.Lock()


def broker_ping_ok(ttl_seconds: float = 5.0) -> bool:
    """
    True si Redis (broker) répond au PING. Résultat mis en cache ttl_seconds
    pour limiter la charge quand le front envoie beaucoup d'événements Socket.IO.
    """
    now = time.time()
    with _broker_lock:
        if now - float(_broker_cache["ts"]) < ttl_seconds:
            return bool(_broker_cache["ok"])
        ok = _redis_ping()
        _broker_cache["ts"] = now
        _broker_cache["ok"] = ok
        if not ok:
            logger.warning("Broker Redis injoignable (ping échoué) — tâches Celery non enfilables")
        return ok


def _redis_ping() -> bool:
    try:
        import redis
        from config import CELERY_BROKER_URL

        r = redis.Redis.from_url(
            CELERY_BROKER_URL,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        return bool(r.ping())
    except Exception as e:
        logger.debug("Redis ping error: %s", e)
        return False


def invalidate_broker_cache() -> None:
    """Après redémarrage Redis, forcer un nouveau ping au prochain appel."""
    with _broker_lock:
        _broker_cache["ts"] = 0.0


def online_workers_count(ttl_seconds: float = 5.0, timeout: float = 1.0) -> int:
    """
    Nombre de workers Celery en ligne (nodes qui répondent).

    Important: c'est plus lourd qu'un ping Redis, donc c'est mis en cache.
    On l'utilise surtout pour afficher une info UI (preview), pas à haute fréquence.
    """
    now = time.time()
    with _workers_lock:
        if now - float(_workers_cache["ts"]) < ttl_seconds:
            return int(_workers_cache["count"])

        count = _inspect_online_workers_count(timeout=timeout)
        _workers_cache["ts"] = now
        _workers_cache["count"] = int(count)
        return int(count)


def _inspect_online_workers_count(timeout: float = 1.0) -> int:
    try:
        from celery_app import celery

        insp = celery.control.inspect(timeout=timeout)
        replies = insp.ping() or {}
        if isinstance(replies, dict):
            return len(replies.keys())
        return 0
    except Exception as e:
        logger.debug("Celery inspect ping error: %s", e)
        return 0
