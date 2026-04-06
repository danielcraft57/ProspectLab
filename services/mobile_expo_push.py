"""
Push notifications mobile via Expo Push Service (Android / iOS).

Enregistrement des jetons Expo par token API (table mobile_expo_push_registrations).
Envoi HTTP vers https://exp.host/--/api/v2/push/send

Usage côté applicatif (ex. Celery, route interne) :
    from services.mobile_expo_push import notify_api_token_devices
    notify_api_token_devices(api_token_id=12, title="Analyse terminée", body="…")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import requests

from services.database import Database

LOG = logging.getLogger(__name__)

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'

_EXPO_TOKEN_RE = re.compile(r'^ExponentPushToken\[[^\]]+\]$')


def _is_valid_expo_push_token(value: str) -> bool:
    return bool(value and _EXPO_TOKEN_RE.match(value.strip()))


def register_device(
    api_token_id: int,
    expo_push_token: str,
    platform: str = 'android',
    installation_id: Optional[str] = None,
) -> None:
    token = (expo_push_token or '').strip()
    if not _is_valid_expo_push_token(token):
        raise ValueError('expo_push_token invalide (format ExponentPushToken[...] attendu)')

    plat = (platform or 'android').strip().lower()[:32] or 'android'
    inst = (installation_id or '').strip()[:128] or None

    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # Même jeton Expo → un seul compte API à la fois
        db.execute_sql(
            cursor,
            'DELETE FROM mobile_expo_push_registrations WHERE expo_push_token = ?',
            (token,),
        )
        if inst:
            db.execute_sql(
                cursor,
                '''
                DELETE FROM mobile_expo_push_registrations
                WHERE api_token_id = ? AND installation_id = ?
                ''',
                (api_token_id, inst),
            )

        db.execute_sql(
            cursor,
            '''
            INSERT INTO mobile_expo_push_registrations
                (api_token_id, expo_push_token, platform, installation_id, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''',
            (api_token_id, token, plat, inst),
        )
        conn.commit()
    finally:
        conn.close()


def unregister_device(api_token_id: int, expo_push_token: str) -> bool:
    token = (expo_push_token or '').strip()
    if not token:
        return False

    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        db.execute_sql(
            cursor,
            '''
            DELETE FROM mobile_expo_push_registrations
            WHERE api_token_id = ? AND expo_push_token = ?
            ''',
            (api_token_id, token),
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        return bool(deleted)
    finally:
        conn.close()


def list_expo_push_tokens_for_api_token(api_token_id: int) -> list[str]:
    """Jetons Expo pour un token API, uniquement si le token API est encore actif."""
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        db.execute_sql(
            cursor,
            '''
            SELECT r.expo_push_token
            FROM mobile_expo_push_registrations r
            INNER JOIN api_tokens t ON t.id = r.api_token_id
            WHERE r.api_token_id = ? AND t.is_active = 1
            ''',
            (api_token_id,),
        )
        rows = cursor.fetchall()
        out = []
        for row in rows:
            if isinstance(row, dict):
                out.append(row['expo_push_token'])
            else:
                out.append(row[0])
        return out
    finally:
        conn.close()


def send_expo_push_messages(messages: list[dict[str, Any]], timeout_sec: float = 30.0) -> dict:
    """
    Envoie un lot de messages au service Expo.

    Chaque élément doit respecter le schéma Expo (clé ``to``, ``title``, ``body``, etc.).
    """
    if not messages:
        return {'data': []}

    resp = requests.post(
        EXPO_PUSH_URL,
        json=messages,
        headers={
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/json',
        },
        timeout=timeout_sec,
    )
    try:
        data = resp.json()
    except Exception:
        data = {'raw': resp.text}

    if resp.status_code >= 400:
        LOG.warning('Expo push HTTP %s: %s', resp.status_code, data)
        raise RuntimeError(f'Expo push erreur HTTP {resp.status_code}')

    return data if isinstance(data, dict) else {'data': data}


def notify_api_token_devices(
    api_token_id: int,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    *,
    sound: Optional[str] = 'default',
    channel_id: Optional[str] = 'default',
) -> dict:
    """
    Notifie tous les appareils Expo enregistrés pour ce token API (actif).

    Pour ouvrir la fiche entreprise au tap (app mobile), utiliser des **valeurs string**
    dans ``data``, par exemple après analyse site::

        data={
            "type": "website_analysis_ready",
            "entreprise_id": str(entreprise_id),
            "website": "https://exemple.fr",  # optionnel, repli si pas d'id
        }

    Returns:
        Réponse JSON brute d'Expo (champ ``data`` avec les statuts par message).
    """
    tokens = list_expo_push_tokens_for_api_token(api_token_id)
    if not tokens:
        return {'data': [], 'skipped': True}

    payload_base: dict[str, Any] = {
        'title': title,
        'body': body,
        'sound': sound,
        'channelId': channel_id,
    }
    if data is not None:
        payload_base['data'] = data

    messages = [{**payload_base, 'to': t} for t in tokens]
    return send_expo_push_messages(messages)


def notify_devices_for_api_token_string(
    api_token_secret: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    *,
    sound: Optional[str] = 'default',
    channel_id: Optional[str] = 'default',
) -> dict:
    """
    Même chose que ``notify_api_token_devices``, mais avec la chaîne secrète du token API
    (utile depuis un job qui n'a que le secret, pas l'id en base).
    """
    from services.api_auth import APITokenManager

    row = APITokenManager().validate_token(api_token_secret)
    if not row or not row.get('id'):
        return {'data': [], 'skipped': True, 'reason': 'invalid_token'}
    return notify_api_token_devices(
        int(row['id']),
        title,
        body,
        data,
        sound=sound,
        channel_id=channel_id,
    )
