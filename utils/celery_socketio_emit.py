"""
Emissions Socket.IO depuis un worker Celery (processus séparé du serveur Flask).

Nécessite que ``SocketIO`` ait été créé avec ``message_queue`` pointant vers le même
Redis que ``CELERY_BROKER_URL`` / ``SOCKETIO_MESSAGE_QUEUE`` (voir ``app.py``).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def emit_from_celery_worker(event_name: str, payload: Dict[str, Any]) -> bool:
    """
    Publie un événement vers tous les clients Socket.IO connectés (broadcast).

    @param event_name: nom de l'événement côté client (ex. ``external_mini_scrape_complete``).
    @param payload: dict sérialisable JSON.
    @returns: True si l'émission a été acceptée par la file Redis.
    """
    try:
        mq = (os.environ.get('SOCKETIO_MESSAGE_QUEUE') or '').strip()
        if not mq:
            try:
                from config import SOCKETIO_MESSAGE_QUEUE as _cfg_mq

                mq = (_cfg_mq or '').strip()
            except Exception:
                mq = ''
        if not mq:
            mq = (os.environ.get('CELERY_BROKER_URL') or '').strip()
        if os.environ.get('SOCKETIO_DISABLE_MESSAGE_QUEUE', '').strip().lower() in (
            '1',
            'true',
            'yes',
            'on',
        ):
            logger.debug('emit_from_celery_worker: SOCKETIO_DISABLE_MESSAGE_QUEUE, skip %s', event_name)
            return False
        if not mq:
            logger.debug('emit_from_celery_worker: pas de Redis URL, skip %s', event_name)
            return False

        from flask_socketio import SocketIO

        sio = SocketIO(message_queue=mq)
        # Sans ``to`` / ``room`` : envoi à tous les clients (équivalent broadcast).
        sio.emit(event_name, payload, namespace='/')
        logger.info(
            '[ws emit celery] %s (tous clients) keys=%s',
            event_name,
            list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
        )
        return True
    except Exception as e:
        logger.warning('emit_from_celery_worker %s: %s', event_name, e, exc_info=True)
        return False
