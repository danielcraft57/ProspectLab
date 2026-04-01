"""
Cache réponse JSON (GET) pour l'API publique /api/public.

- Mémoire processus, TTL configurable, eviction LRU.
- Clé = id token API + chemin + query string (données isolées par token).
- Seules les réponses HTTP 200 avec corps JSON (dict ou list) sont mises en cache.

Désactiver : PUBLIC_API_RESPONSE_CACHE=false
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Optional, Tuple

from flask import jsonify, request


def _enabled() -> bool:
    return os.environ.get('PUBLIC_API_RESPONSE_CACHE', 'true').lower() in ('1', 'true', 'yes', 'on')


def _default_ttl() -> float:
    return max(1.0, float(os.environ.get('PUBLIC_API_CACHE_TTL_DEFAULT', '30')))


def _max_entries() -> int:
    return max(16, int(os.environ.get('PUBLIC_API_CACHE_MAX_ENTRIES', '512')))


_lock = threading.RLock()
_store: OrderedDict[str, Tuple[float, Any, int]] = OrderedDict()


def _cache_get(key: str) -> Optional[Tuple[Any, int]]:
    now = time.time()
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        exp, body, status = entry
        if now > exp:
            del _store[key]
            return None
        _store.move_to_end(key)
        return body, status


def _cache_set(key: str, body: Any, status: int, ttl: float) -> None:
    deadline = time.time() + ttl
    max_n = _max_entries()
    with _lock:
        if key in _store:
            del _store[key]
        while len(_store) >= max_n:
            _store.popitem(last=False)
        _store[key] = (deadline, body, status)


def _make_key() -> str:
    td = getattr(request, 'api_token', None) or {}
    token_id = td.get('id')
    qs = request.query_string.decode('utf-8') if getattr(request, 'query_string', None) else ''
    return f'{token_id}|{request.path}|{qs}'


def _unpack_json_response(resp: Any) -> Optional[Tuple[Any, int]]:
    if isinstance(resp, tuple):
        r = resp[0]
        status = int(resp[1]) if len(resp) > 1 else 200
    else:
        r = resp
        status = 200
    if status != 200:
        return None
    if hasattr(r, 'get_json'):
        data = r.get_json(silent=True)
        if isinstance(data, (dict, list)):
            return data, status
    return None


def public_response_cache(ttl_seconds: Optional[float] = None) -> Callable:
    """
    À placer sous @api_token_required et @require_api_permission (au-dessus de def).

    ttl_seconds: durée en secondes (sinon PUBLIC_API_CACHE_TTL_DEFAULT).
    """
    ttl = float(ttl_seconds) if ttl_seconds is not None else _default_ttl()

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not _enabled() or request.method != 'GET':
                return f(*args, **kwargs)

            cache_key = _make_key()
            hit = _cache_get(cache_key)
            if hit is not None:
                body, _st = hit
                return jsonify(body)

            resp = f(*args, **kwargs)
            parsed = _unpack_json_response(resp)
            if parsed:
                body, status = parsed
                _cache_set(cache_key, body, status, ttl)
            return resp

        return wrapped

    return decorator
