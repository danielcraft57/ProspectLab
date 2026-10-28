"""
Lancement Playwright Chromium avec session SocialDesk (storage-state).
"""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from typing import Any, Generator

from config import FACEBOOK_PROSPECTION_HEADLESS, FACEBOOK_PROSPECTION_USE_CHROME_CHANNEL

from .paths_config import cookies_json_path, storage_state_path

logger = logging.getLogger(__name__)

_FACEBOOK_DOMAIN = re.compile(r'facebook\.com|fb\.com', re.I)

_CHROMIUM_ARGS = (
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-blink-features=AutomationControlled',
)


def has_stored_session(account_id: str | None = None) -> bool:
    """
    True si storage-state ou cookies.json existe pour le compte.

    @param account_id: Compte Facebook (danielcraft, etc.)
    @returns: Session potentiellement utilisable
    """
    return storage_state_path(account_id).is_file() or cookies_json_path(account_id).is_file()


def _load_cookies_from_json(path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        domain = str(item.get('domain') or '')
        if not _FACEBOOK_DOMAIN.search(domain):
            continue
        cookie: dict[str, Any] = {
            'name': item.get('name'),
            'value': item.get('value'),
            'domain': domain,
            'path': item.get('path') or '/',
        }
        if item.get('expirationDate'):
            cookie['expires'] = float(item['expirationDate'])
        if 'httpOnly' in item:
            cookie['httpOnly'] = bool(item['httpOnly'])
        if 'secure' in item:
            cookie['secure'] = bool(item['secure'])
        out.append(cookie)
    return out


@contextmanager
def facebook_browser_context(
    account_id: str | None = None,
    *,
    headless: bool | None = None,
) -> Generator[tuple[Any, Any], None, None]:
    """
    Context manager : (playwright, browser_context) pret pour Facebook.

    @param account_id: Compte session SocialDesk
    @param headless: Surcharge headless (defaut config)
    @yields: Tuple (playwright handle, BrowserContext)
    @raises RuntimeError: Playwright absent ou session introuvable
    """
    from playwright.sync_api import sync_playwright

    state_file = storage_state_path(account_id)
    cookies_file = cookies_json_path(account_id)
    if not state_file.is_file() and not cookies_file.is_file():
        raise RuntimeError(
            f'Session Facebook introuvable ({state_file}). '
            f'Lancez sync-chrome-session danielcraft sur SocialDesk.'
        )

    use_headless = FACEBOOK_PROSPECTION_HEADLESS if headless is None else headless
    launch_kwargs: dict[str, Any] = {'headless': use_headless, 'args': list(_CHROMIUM_ARGS)}
    if FACEBOOK_PROSPECTION_USE_CHROME_CHANNEL:
        launch_kwargs['channel'] = 'chrome'

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_kwargs)
        context_kwargs: dict[str, Any] = {
            'locale': 'fr-FR',
            'timezone_id': 'Europe/Paris',
            'viewport': {'width': 1400, 'height': 900},
        }
        if state_file.is_file():
            context_kwargs['storage_state'] = str(state_file)
        context = browser.new_context(**context_kwargs)
        if not state_file.is_file() and cookies_file.is_file():
            cookies = _load_cookies_from_json(cookies_file)
            if cookies:
                context.add_cookies(cookies)
        try:
            yield playwright, context
        finally:
            context.close()
            browser.close()
