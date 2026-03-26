"""
Planification étalée des sous-tâches Celery (files « heavy »).

Évite d'enfiler d'un coup scraping + technique + SEO + OSINT + pentest
sur le broker quand une seule route API lance tout le pack.
"""

from __future__ import annotations

import os

try:
    from config import CELERY_BULK_STAGGER_SEC, CELERY_BULK_STAGGER_SLOT_MODULO
except ImportError:
    CELERY_BULK_STAGGER_SEC = float(os.environ.get('CELERY_BULK_STAGGER_SEC', '0.75'))
    CELERY_BULK_STAGGER_SLOT_MODULO = max(1, int(os.environ.get('CELERY_BULK_STAGGER_SLOT_MODULO', '400')))

# Limite "sécurité" : évite de planifier des centaines de tâches à plusieurs heures.
# L’objectif est de garder l’exécution visible rapidement sur Raspberry Pi.
_STAGGER_MAX_SEC = float(os.environ.get('CELERY_STAGGER_MAX_SEC', '120'))

# Client Redis réutilisé pour l'INCR global (évite 50× from_url en rafale WebSocket).
_stagger_redis = None


def _stagger_redis_client():
    global _stagger_redis
    if _stagger_redis is None:
        import redis

        from config import CELERY_BROKER_URL

        _stagger_redis = redis.Redis.from_url(
            CELERY_BROKER_URL,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            health_check_interval=30,
        )
    return _stagger_redis


class BulkSubtaskStagger:
    """
    Compteur pour apply_async(..., countdown=index * CELERY_BULK_STAGGER_SEC).
    Réutilisable sur un même flux (scraping multi-entreprises, pack website-analysis, etc.).
    """

    def __init__(self) -> None:
        self._i = 0
        self._sec = float(CELERY_BULK_STAGGER_SEC)

    def next_countdown(self) -> float:
        # Cycle modulo pour borner la valeur max (et donc la latence de visibilité).
        idx = self._i
        self._i += 1
        slot = int(idx % max(1, int(CELERY_BULK_STAGGER_SLOT_MODULO)))
        c = float(slot) * float(self._sec)
        return float(min(c, _STAGGER_MAX_SEC))


def next_global_stagger_countdown() -> float:
    """
    Compteur Redis partagé (tous les clients / onglets / workers Flask).

    Les lancements via WebSocket utilisaient .delay() sans étalement : 50 analyses SEO
    enfilées d'un coup sur la file « heavy » et 50 threads de polling AsyncResult.

    INCR sur Redis → slot = (idx - 1) % CELERY_BULK_STAGGER_SLOT_MODULO pour borner le délai max
    (ex. sans modulo, idx=10000 → 7500 s de countdown : aucune exécution visible tout de suite).
    """
    try:
        r = _stagger_redis_client()
        idx = r.incr("prospectlab:heavy:stagger:seq")
        if idx == 1:
            r.expire("prospectlab:heavy:stagger:seq", 86400)
        mod = max(1, int(CELERY_BULK_STAGGER_SLOT_MODULO))
        slot = int((idx - 1) % mod)
        # float : évite de tronquer des sous-secondes (ex. 0.75 s)
        return float(slot) * float(CELERY_BULK_STAGGER_SEC)
    except Exception:
        return 0.0


# Stagger par session WebSocket : évite les délais aléatoires du compteur global Redis.
# Quand un user lance technique + SEO + pentest d'un coup, chacun reçoit 0, 0.75, 1.5 s
# au lieu de délais pouvant aller jusqu'à ~300 s si le slot global tombe mal.
import threading
import time

_ws_stagger: dict = {}  # session_id -> {"idx": int, "ts": float}
_ws_stagger_lock = threading.Lock()
_ws_stagger_ttl = 30.0


def next_websocket_stagger_countdown(session_id: str) -> float:
    """
    Compteur par session pour les handlers WebSocket (start_technical, start_seo, start_pentest, start_osint).
    Le premier événement reçoit 0, le suivant 0.75 s, puis 1.5 s, etc. Pas de délai aléatoire lié au global.
    """
    now = time.time()
    with _ws_stagger_lock:
        for sid in list(_ws_stagger.keys()):
            if now - _ws_stagger[sid].get("ts", 0) > _ws_stagger_ttl:
                _ws_stagger.pop(sid, None)
        entry = _ws_stagger.get(session_id)
        if not entry:
            entry = {"idx": 0, "ts": now}
            _ws_stagger[session_id] = entry
        idx = entry["idx"]
        entry["idx"] = idx + 1
        entry["ts"] = now
    # Bornage : modulo pour éviter les grands retards sur des sessions très longues.
    mod = max(1, int(CELERY_BULK_STAGGER_SLOT_MODULO))
    slot = int(idx % mod)
    c = float(slot) * float(CELERY_BULK_STAGGER_SEC)
    return float(min(c, _STAGGER_MAX_SEC))
