"""
Execution locale des jobs Facebook (Playwright Python, session SocialDesk).
"""

from __future__ import annotations

import logging
from typing import Any

from config import FACEBOOK_PROSPECTION_ACCOUNT

from .browser import facebook_browser_context, has_stored_session
from .facebook_ui import goto_facebook, is_logged_in_url
from .page_scrape import scrape_public_page
from .page_search import search_facebook_pages

logger = logging.getLogger(__name__)


class FacebookProspectionLocalRunner:
    """
    Runner local inspire SocialDesk (sans Node distant).

    Responsabilites : search et scrape_page sur la machine courante
    avec les cookies synchronises depuis facebook-playwright.
    """

    def __init__(self, account_id: str | None = None) -> None:
        self.account_id = (account_id or FACEBOOK_PROSPECTION_ACCOUNT or 'danielcraft').strip()

    def session_available(self) -> bool:
        """True si storage-state ou cookies.json est present."""
        return has_stored_session(self.account_id)

    def run_search(
        self,
        query: str,
        *,
        target_name: str | None = None,
        search_queries: list[str] | None = None,
        keywords: list[str] | None = None,
        headless: bool | None = None,
    ) -> dict[str, Any]:
        """
        Recherche des pages Facebook pour une requete.

        @param query: Texte recherche principal
        @param target_name: Nom entreprise pour le scoring
        @param search_queries: Variantes (scrape CRM) essayees dans l ordre
        @param keywords: Mots-cles secteur / OG pour affiner le score
        @param headless: Mode navigateur
        @returns: {ok, job_type, query, candidates}
        """
        ordered: list[str] = []
        for q in list(search_queries or []) + [query]:
            text = (q or '').strip()
            if text and text not in ordered:
                ordered.append(text)
        if not ordered:
            return {'ok': False, 'error': 'query vide', 'job_type': 'search'}
        if not self.session_available():
            return {
                'ok': False,
                'error': 'session Facebook locale absente (sync SocialDesk)',
                'job_type': 'search',
            }

        with facebook_browser_context(self.account_id, headless=headless) as (_, context):
            page = context.new_page()
            goto_facebook(page)
            if not is_logged_in_url(page.url):
                return {'ok': False, 'error': 'Session Facebook expiree', 'job_type': 'search'}
            best: dict[str, Any] | None = None
            kw = [str(k).lower() for k in (keywords or []) if k]
            for q in ordered:
                candidates = search_facebook_pages(
                    page,
                    q,
                    target_name=target_name,
                    keywords=kw,
                )
                top_score = float(candidates[0].get('score') or 0) if candidates else 0.0
                logger.info(
                    'Facebook search local: %s candidats score=%s pour %r',
                    len(candidates),
                    top_score,
                    q,
                )
                if candidates and top_score >= 0.65:
                    return {
                        'ok': True,
                        'job_type': 'search',
                        'account': self.account_id,
                        'query': q,
                        'search_queries_tried': ordered,
                        'candidates': candidates,
                        'runner': 'local',
                    }
                if not best or top_score > float(
                    (best.get('candidates') or [{}])[0].get('score') or 0
                ):
                    best = {
                        'ok': True,
                        'job_type': 'search',
                        'account': self.account_id,
                        'query': q,
                        'search_queries_tried': ordered,
                        'candidates': candidates,
                        'runner': 'local',
                    }
            if best:
                return best
            return {
                'ok': True,
                'job_type': 'search',
                'account': self.account_id,
                'query': ordered[0],
                'search_queries_tried': ordered,
                'candidates': [],
                'runner': 'local',
            }

    def run_scrape_page(self, fb_url: str, *, headless: bool | None = None) -> dict[str, Any]:
        """
        Scrape une URL de page Facebook.

        @param fb_url: URL page
        @param headless: Mode navigateur
        @returns: {ok, profile}
        """
        url = (fb_url or '').strip()
        if not url:
            return {'ok': False, 'error': 'fb_url requis', 'job_type': 'scrape_page'}
        if not self.session_available():
            return {'ok': False, 'error': 'session locale absente', 'job_type': 'scrape_page'}

        with facebook_browser_context(self.account_id, headless=headless) as (_, context):
            page = context.new_page()
            goto_facebook(page)
            if not is_logged_in_url(page.url):
                return {'ok': False, 'error': 'Session expiree', 'job_type': 'scrape_page'}
            profile = scrape_public_page(page, url)
            return {
                'ok': True,
                'job_type': 'scrape_page',
                'account': self.account_id,
                'profile': profile,
                'runner': 'local',
            }

    def run_job(self, job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Point d'entree generique job local.

        @param job_type: search | scrape_page
        @param payload: Parametres (query, fb_url, target_name, ...)
        @returns: Resultat JSON serialisable
        """
        if job_type == 'search':
            return self.run_search(
                str(payload.get('query') or ''),
                target_name=payload.get('target_name') or payload.get('company_name'),
                search_queries=payload.get('search_queries'),
                keywords=payload.get('keywords'),
            )
        if job_type == 'scrape_page':
            url = payload.get('fb_url') or payload.get('page_url')
            return self.run_scrape_page(str(url or ''))
        if job_type == 'messenger_inbox':
            return {
                'ok': False,
                'error': 'messenger_inbox : utiliser runner remote (serv2) pour l instant',
                'job_type': job_type,
            }
        return {'ok': False, 'error': f'job_type local inconnu: {job_type}'}
