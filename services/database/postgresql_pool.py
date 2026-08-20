"""
Pool de connexions PostgreSQL (ThreadedConnectionPool) pour la production.

Réduit l'ouverture/fermeture TCP répétée sous Gunicorn + workers Celery en threads.
Les connexions obtenues via Database.get_connection() sont renvoyées au pool
lorsque ``close()`` est appelé (comportement inchangé pour le reste du code).

Sous Gunicorn/eventlet, plusieurs requêtes concurrentes (dashboard, API, websockets)
peuvent occuper tout le pool. ``getconn`` attend alors une place au lieu d'échouer
immédiatement avec « connection pool exhausted ».
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_pools: Dict[str, Any] = {}
_pools_lock = threading.Lock()


def postgresql_pool_enabled() -> bool:
    """
    Indique si le pool PostgreSQL doit être utilisé.

    @returns: True si APP_ENV=production (ou DATABASE_POOL_ENABLED explicite).
    """
    explicit = (os.environ.get('DATABASE_POOL_ENABLED') or '').strip().lower()
    if explicit in ('0', 'false', 'no', 'off'):
        return False
    if explicit in ('1', 'true', 'yes', 'on'):
        return True
    app_env = (os.environ.get('APP_ENV') or '').strip().lower()
    return app_env in ('production', 'prod')


def _pool_bounds() -> tuple[int, int]:
    """
    Bornes min/max du pool (variables d'environnement).

    @returns: Couple (minconn, maxconn).
    """
    minconn = max(1, int(os.environ.get('DATABASE_POOL_MIN', '2')))
    maxconn = max(minconn, int(os.environ.get('DATABASE_POOL_MAX', '20')))
    return minconn, maxconn


def _pool_wait_sec() -> float:
    """
    Durée max d'attente d'une connexion libre.

    @returns: Timeout en secondes (défaut 20).
    """
    try:
        return max(1.0, float(os.environ.get('DATABASE_POOL_WAIT_SEC', '20') or '20'))
    except ValueError:
        return 20.0


def _is_pool_exhausted(exc: BaseException) -> bool:
    """
    Détecte l'erreur « pool exhausted » de psycopg2.

    @param exc: Exception levée par getconn.
    @returns: True si le pool n'a plus de connexion disponible.
    """
    name = type(exc).__name__
    if name == 'PoolError':
        return True
    msg = str(exc).lower()
    return 'pool exhausted' in msg or 'connection pool exhausted' in msg


def get_postgresql_pool(database_url: str):
    """
    Retourne un ThreadedConnectionPool partagé par URL (ou None si désactivé).

    @param database_url: URL postgresql://...
    @returns: Pool psycopg2 ou None.
    """
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
                'Pool PostgreSQL actif (min=%s max=%s wait=%ss)',
                minconn,
                maxconn,
                _pool_wait_sec(),
            )
            return pool
        except Exception as exc:
            logger.error('Impossible de créer le pool PostgreSQL: %s', exc)
            return None


def acquire_pool_connection(pool):
    """
    Prend une connexion dans le pool, en attendant si toutes sont occupées.

    Écarte les connexions déjà fermées (fuite / kill réseau) pour ne pas
    les redistribuer aux requêtes.

    @param pool: ThreadedConnectionPool psycopg2.
    @returns: Connexion psycopg2 brute.
    @throws: Dernière erreur pool si le timeout d'attente est dépassé.
    """
    deadline = time.monotonic() + _pool_wait_sec()
    delay = 0.05
    last_exc: Optional[BaseException] = None
    logged_wait = False

    while time.monotonic() < deadline:
        try:
            conn = pool.getconn()
        except Exception as exc:
            if not _is_pool_exhausted(exc):
                raise
            last_exc = exc
            if not logged_wait:
                logged_wait = True
                logger.warning(
                    'Pool PostgreSQL saturé, attente jusqu\'à %.0fs (max=%s)',
                    _pool_wait_sec(),
                    _pool_bounds()[1],
                )
            time.sleep(delay)
            delay = min(delay * 1.6, 0.4)
            continue

        if getattr(conn, 'closed', 0):
            logger.warning('Connexion pool déjà fermée, on la jette')
            try:
                pool.putconn(conn, close=True)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
            continue

        try:
            if not getattr(conn, 'autocommit', False):
                conn.rollback()
        except Exception:
            try:
                pool.putconn(conn, close=True)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
            continue

        return conn

    logger.error(
        'Pool PostgreSQL toujours saturé après %.0fs (max=%s)',
        _pool_wait_sec(),
        _pool_bounds()[1],
    )
    if last_exc is not None:
        raise last_exc
    raise RuntimeError('connection pool exhausted')


def pool_overflow_enabled() -> bool:
    """
    Autorise une connexion hors pool si le pool reste saturé.

    Évite un 500 dashboard (connection pool exhausted) sous pic eventlet.

    @returns: True par défaut (désactiver avec DATABASE_POOL_OVERFLOW=0).
    """
    explicit = (os.environ.get('DATABASE_POOL_OVERFLOW') or '').strip().lower()
    if explicit in ('0', 'false', 'no', 'off'):
        return False
    return True


class PooledConnection:
    """Proxy : ``close()`` renvoie la connexion au pool au lieu de la détruire."""

    __slots__ = ('_conn', '_pool', '_returned')

    def __init__(self, conn, pool) -> None:
        object.__setattr__(self, '_conn', conn)
        object.__setattr__(self, '_pool', pool)
        object.__setattr__(self, '_returned', False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value) -> None:
        if name in self.__slots__:
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def close(self) -> None:
        """
        Rend la connexion au pool (rollback d'une transaction orpheline).

        Idempotent : un second close() ne fait rien.
        """
        if self._returned:
            return
        self._returned = True
        conn = self._conn
        pool = self._pool
        broken = bool(getattr(conn, 'closed', 0))
        if not broken:
            try:
                conn.autocommit = False
                conn.rollback()
            except Exception:
                broken = True
        try:
            pool.putconn(conn, close=broken)
        except Exception as exc:
            logger.warning('putconn pool PostgreSQL: %s', exc)
            try:
                conn.close()
            except Exception:
                pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
