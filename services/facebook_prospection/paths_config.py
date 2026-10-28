"""
Chemins session Facebook (inspire SocialDesk facebook-playwright/paths.mjs).
"""

from __future__ import annotations

from pathlib import Path

from config import (
    APP_DIR,
    FACEBOOK_PROSPECTION_ACCOUNT,
    FACEBOOK_PROSPECTION_REMOTE_FB_DIR,
    FACEBOOK_PROSPECTION_SESSION_DIR,
)


def facebook_playwright_root() -> Path:
    """
    Racine du module facebook-playwright SocialDesk.

    @returns: Chemin du dossier facebook-playwright
    """
    return Path(FACEBOOK_PROSPECTION_REMOTE_FB_DIR).expanduser()


def account_data_dir(account_id: str | None = None) -> Path:
    """
    Dossier data du compte (storage-state, cookies, chrome-profile).

    @param account_id: Identifiant compte (defaut config danielcraft)
    @returns: Chemin data/accounts/<account> ou data/ pour loic
    """
    account = (account_id or FACEBOOK_PROSPECTION_ACCOUNT or 'danielcraft').strip()
    if FACEBOOK_PROSPECTION_SESSION_DIR.strip():
        return Path(FACEBOOK_PROSPECTION_SESSION_DIR.strip()).expanduser()
    root = facebook_playwright_root()
    if account == 'loic':
        return root / 'data'
    return root / 'data' / 'accounts' / account


def storage_state_path(account_id: str | None = None) -> Path:
    """Fichier storage-state.json Playwright."""
    return account_data_dir(account_id) / 'storage-state.json'


def cookies_json_path(account_id: str | None = None) -> Path:
    """Export cookies.json (Cookie-Editor / sync Chrome)."""
    return account_data_dir(account_id) / 'cookies.json'


def prospectlab_fb_data_dir() -> Path:
    """Donnees locales ProspectLab (rapports de test, pas les cookies)."""
    return Path(APP_DIR) / 'data' / 'facebook_prospection'
