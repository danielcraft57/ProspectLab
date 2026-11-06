"""
Client HTTP VocalGuard (tchat KB + catalogue intents).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from config import VOCALGUARD_INTERNAL_TOKEN, VOCALGUARD_KB_PROFILE, VOCALGUARD_URL

logger = logging.getLogger(__name__)


def vocalguard_configured() -> bool:
    """True si une URL VocalGuard est definie."""
    return bool((VOCALGUARD_URL or '').strip())


def _base() -> str:
    return (VOCALGUARD_URL or '').strip().rstrip('/')


def _headers() -> dict[str, str]:
    token = (VOCALGUARD_INTERNAL_TOKEN or '').strip()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if token:
        headers['X-VocalGuard-Internal'] = token
    return headers


def chat_turn(
    text: str,
    *,
    top_k: int = 8,
    recent_replies: list[str] | None = None,
    recent_tags: list[str] | None = None,
    recent_user_texts: list[str] | None = None,
    profile: str | None = None,
    timeout: float = 6.0,
) -> dict[str, Any] | None:
    """
    Un tour de tchatche VocalGuard (persona + Qdrant).

    Essaie /api/v1/internal/kb/chat puis /api/v1/kb/chat.

    @param text: Message utilisateur
    @param top_k: Nombre d'intents voisins
    @param recent_replies: Dernieres reponses bot
    @param recent_tags: Derniers tags
    @param recent_user_texts: Derniers textes user
    @param timeout: Timeout HTTP
    @returns: JSON VocalGuard ou None
    """
    base = _base()
    if not base:
        return None
    body = {
        'text': (text or '').strip(),
        'top_k': int(top_k),
        'recent_replies': list(recent_replies or []),
        'recent_tags': list(recent_tags or []),
        'recent_user_texts': list(recent_user_texts or []),
        'profile': (profile or VOCALGUARD_KB_PROFILE or 'outbound_commercial'),
    }
    if not body['text']:
        return None
    paths = ('/api/v1/internal/kb/chat', '/api/v1/kb/chat')
    last_err = ''
    for path in paths:
        try:
            resp = requests.post(
                f'{base}{path}',
                json=body,
                headers=_headers(),
                timeout=timeout,
            )
        except requests.RequestException as exc:
            last_err = str(exc)
            logger.warning('VocalGuard %s injoignable: %s', path, exc)
            continue
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                data['_path'] = path
            return data
        last_err = f'HTTP {resp.status_code} {resp.text[:160]}'
        if resp.status_code in (401, 403, 404, 405):
            continue
        logger.warning('VocalGuard chat %s: %s', path, last_err)
        return None
    if last_err:
        logger.warning('VocalGuard chat KO: %s', last_err)
    return None


def list_intents(*, profile: str | None = None, timeout: float = 10.0) -> list[dict[str, Any]]:
    """
    Catalogue intents (patterns + reponses).

    @param profile: inbound | outbound_commercial
    @param timeout: Timeout HTTP
    @returns: Liste d'intents
    """
    from services.facebook_prospection.vocalguard_kb_db import list_intents_from_db, vocalguard_db_configured

    if vocalguard_db_configured():
        items = list_intents_from_db(profile=profile, enabled_only=True)
        if items:
            return items

    base = _base()
    if not base:
        return []
    params = {
        'enabled_only': 'true',
        'profile': profile or VOCALGUARD_KB_PROFILE or 'outbound_commercial',
    }
    paths = ('/api/v1/internal/kb/intents', '/api/v1/kb/intents')
    for path in paths:
        try:
            resp = requests.get(
                f'{base}{path}',
                params=params,
                headers=_headers(),
                timeout=timeout,
            )
        except requests.RequestException as exc:
            logger.warning('VocalGuard intents %s: %s', path, exc)
            continue
        if resp.status_code != 200:
            continue
        data = resp.json() or {}
        items = data.get('intents') if isinstance(data, dict) else data
        if isinstance(items, list):
            return items
    return []
