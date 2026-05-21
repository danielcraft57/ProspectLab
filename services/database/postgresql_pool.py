"""
Pool de connexions PostgreSQL (ThreadedConnectionPool) pour la production.

Réduit l'ouverture/fermeture TCP répétée sous Gunicorn + workers Celery en threads.
Les connexions obtenues via Database.get_connection() sont renvoyées au pool
lorsque ``close()`` est appelé (comportement inchangé pour le reste du code).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_pools: Dict[str, Any] = {}
_pools_lock = threading.Lock()


def postgresql_pool_enabled() -> bool:
    explicit = (os.environ.get('DATABASE_POOL_ENABLED') or '').strip().lower()
    if explicit in ('0', 'false', 'no', 'off'):
        return False
    if explicit in ('1', 'true', 'yes', 'on'):
        return True
    app_env = (os.environ.get('APP_ENV') or '').strip().lower()
    return app_env in ('production', 'prod')


def _pool_bounds() -> tuple[int, int]:
    minconn = max(1, int(os.environ.get('DATABASE_POOL_MIN', '2')))
    maxconn = max(minconn, int(os.environ.get('DATABASE_POOL_MAX', '20')))
    return minconn, maxconn


def get_postgresql_pool(database_url: str):
    """Retourne un ThreadedConnectionPool partagé par URL (ou None si désactivé)."""
    if not database_url or not database_url.startswith('postgresql://'):
        return None
    if not postgresql_pool_enabled():
        return None

    with _pools_lock:
        pool = _pools.get(database_url)
        if pool is not None:
            return pool
        try:
            from psycopg2.pool import ThreadedConnectionPool
        except ImportError:
            logger.warning('psycopg2 pool indisponible — connexions PostgreSQL sans pool')
            return None

        minconn, maxconn = _pool_bounds()
        connect_timeout = max(3, int(os.environ.get('DATABASE_CONNECT_TIMEOUT_SEC', '10')))
        kwargs: dict = {'connect_timeout': connect_timeout}
        stmt_ms = (os.environ.get('DATABASE_STATEMENT_TIMEOUT_MS') or '').strip()
        if stmt_ms.isdigit() and int(stmt_ms) > 0:
            kwargs['options'] = f'-c statement_timeout={int(stmt_ms)}'

        try:
            pool = ThreadedConnectionPool(minconn, maxconn, database_url, **kwargs)
            _pools[database_url] = pool
            logger.info(
                'Pool PostgreSQL actif (min=%s max=%s)',
                minconn,
                maxconn,
            )
            return pool
        except Exception as exc:
            logger.error('Impossible de créer le pool PostgreSQL: %s', exc)
            return None


class PooledConnection:
    """Proxy : ``close()`` renvoie la connexion au pool au lieu de la détruire."""

    __slots__ = ('_conn', '_pool', '_returned')

    def __init__(self, conn, pool) -> None:
        object.__setattr__(self, '_conn', conn)
        object.__setattr__(self, '_pool', pool)
        object.__setattr__(self, '_returned', False)

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value) -> None:
        if name in self.__slots__:
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def close(self) -> None:
        if self._returned:
            return
        self._returned = True
        try:
            if not getattr(self._conn, 'closed', False):
                self._conn.autocommit = False
                self._conn.rollback()
        except Exception:
            pass
        try:
            self._pool.putconn(self._conn)
        except Exception as exc:
            logger.warning('putconn pool PostgreSQL: %s', exc)
            try:
                self._conn.close()
            except Exception:
                pass
