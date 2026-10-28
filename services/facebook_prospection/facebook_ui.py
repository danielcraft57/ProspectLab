"""
Navigation Facebook et popins cookies (inspire facebook-ui.mjs).
"""

from __future__ import annotations

import time
from typing import Any

_COOKIE_SELECTORS = (
    'button[data-cookiebanner="accept_button"]',
    'button[data-cookiebanner="accept_only_essential_button"]',
    '[aria-label="Autoriser tous les cookies"]',
    '[aria-label="Allow all cookies"]',
)


def dismiss_cookie_banners(page: Any) -> None:
    """
    Accepte les bandeaux cookies Meta si visibles.

    @param page: Page Playwright
    """
    for _ in range(3):
        for selector in _COOKIE_SELECTORS:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0 and locator.is_visible(timeout=500):
                    locator.click(timeout=3000)
                    time.sleep(0.6)
            except Exception:
                continue
        try:
            page.get_by_role('button', name='Autoriser tous les cookies').click(timeout=1500)
        except Exception:
            pass
        try:
            page.get_by_role('button', name='Accept All').click(timeout=1500)
        except Exception:
            pass
        time.sleep(0.4)


def goto_facebook(page: Any, url: str = 'https://www.facebook.com/') -> None:
    """
    Ouvre Facebook et ferme les popins courantes.

    @param page: Page Playwright
    @param url: URL de depart
    """
    page.goto(url, wait_until='domcontentloaded', timeout=90_000)
    time.sleep(2.0)
    dismiss_cookie_banners(page)


def is_logged_in_url(url: str) -> bool:
    """
    Heuristique URL connecte (hors login / checkpoint).

    @param url: URL courante
    @returns: True si pas sur ecran login evident
    """
    low = (url or '').lower()
    if 'login' in low or 'checkpoint' in low:
        return False
    return 'facebook.com' in low
