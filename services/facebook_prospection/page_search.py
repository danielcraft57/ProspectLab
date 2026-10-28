"""
Recherche de pages Facebook (inspire facebook-search.mjs + prospectlab-facebook-job).
"""

from __future__ import annotations

import time
import urllib.parse
from typing import Any

from .facebook_ui import dismiss_cookie_banners, is_logged_in_url
from .text_match import group_name_score, name_matches


def _search_urls(query: str) -> list[str]:
    q = urllib.parse.quote(query)
    return [
        f'https://www.facebook.com/search/pages/?q={q}',
        f'https://www.facebook.com/search/top/?q={q}',
        f'https://www.facebook.com/pages/search/pages/?q={q}',
    ]


def _click_pages_filter(page: Any) -> None:
    for locator_factory in (
        lambda: page.get_by_role('link', name='Pages'),
        lambda: page.get_by_role('tab', name='Pages'),
        lambda: page.locator('a[href*="/search/pages"]').first,
    ):
        try:
            loc = locator_factory()
            if loc.count() > 0 and loc.is_visible(timeout=800):
                loc.click(timeout=4000)
                time.sleep(1.5)
                return
        except Exception:
            continue


def open_pages_search(page: Any, query: str) -> str:
    """
    Ouvre l'onglet recherche Pages pour une requete.

    @param page: Page Playwright
    @param query: Texte de recherche
    @returns: URL utilisee
    """
    last = ''
    for url in _search_urls(query):
        page.goto(url, wait_until='domcontentloaded', timeout=90_000)
        time.sleep(2.5)
        dismiss_cookie_banners(page)
        if '/search/top/' in url:
            _click_pages_filter(page)
        last = url
        body = page.locator('body').inner_text(timeout=5000).lower()
        if 'aucun résultat' in body or 'no results' in body:
            continue
        if page.locator('a[href*="facebook.com"]').count() > 2:
            return url
    return last


def scroll_search_results(page: Any, rounds: int = 2) -> None:
    """
    Scroll le fil de resultats pour charger plus de cartes.

    @param page: Page Playwright
    @param rounds: Nombre de passes scroll
    """
    for _ in range(max(1, rounds)):
        page.evaluate(
            """() => {
            const main = document.querySelector('[role="main"]') || document.body;
            main.scrollTop += 1400;
            window.scrollBy(0, 1400);
        }"""
        )
        try:
            page.mouse.wheel(0, 1400)
        except Exception:
            pass
        time.sleep(1.0)


def collect_page_candidates(page: Any) -> list[dict[str, str]]:
    """
    Extrait les liens pages / profils pro depuis le DOM.

    @param page: Page Playwright
    @returns: Liste {name, url}
    """
    try:
        page.wait_for_selector('a[href*="facebook.com"]', timeout=15_000)
    except Exception:
        pass
    rows = page.evaluate(
        """() => {
        const skipPath = /\\/(search|groups|friends|messages|watch|gaming|marketplace|help|policies|privacy)\\//i;
        const badName = /^(pages|voir tout|see all|suivre|follow|message)$/i;
        const out = [];
        const seen = new Set();
        const roots = [
            document.querySelector('[role="main"]'),
            document.querySelector('[data-pagelet*="SearchResults"]'),
            document.body,
        ].filter(Boolean);
        for (const root of roots) {
            for (const a of root.querySelectorAll('a[href]')) {
                let href = a.getAttribute('href') || '';
                if (!href) continue;
                if (href.startsWith('/')) href = 'https://www.facebook.com' + href;
                if (!/facebook\\.com/i.test(href)) continue;
                if (skipPath.test(href)) continue;
                if (/\\/l\\.php\\?/i.test(href)) continue;
                const key = href.split('?')[0].replace(/\\/$/, '');
                if (seen.has(key)) continue;
                if (!/(profile\\.php\\?id=|\\/pages\\/|\\/[A-Za-z0-9][A-Za-z0-9._-]{2,})/i.test(key)) continue;
                seen.add(key);
                const name = (a.innerText || a.getAttribute('aria-label') || '')
                    .trim()
                    .split('\\n')
                    .map((s) => s.trim())
                    .find((s) => s.length > 1 && !badName.test(s)) || '';
                if (!name || name.length < 2) continue;
                out.push({ name: name.slice(0, 120), url: key });
                if (out.length >= 30) break;
            }
            if (out.length >= 10) break;
        }
        return out;
    }"""
    )
    return list(rows or [])


def score_candidates(
    rows: list[dict[str, str]],
    query: str,
    target_name: str | None = None,
    keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Ajoute un score de pertinence a chaque candidat.

    @param rows: Candidats bruts
    @param query: Requete utilisateur
    @param target_name: Nom entreprise pour affiner le score
    @returns: Candidats avec score, tries desc
    """
    target = (target_name or query or '').strip()
    scored: list[dict[str, Any]] = []
    denom = max(1, len([w for w in target.split() if len(w) > 3]))
    for row in rows:
        name = row.get('name') or ''
        url = row.get('url') or ''
        if name_matches(name, target):
            score = 1.0
        else:
            score = group_name_score(name, target) / denom
        if keywords:
            name_low = (name or '').lower()
            hits = sum(1 for kw in keywords if kw and kw in name_low)
            if hits:
                score = min(1.0, float(score) + min(0.25, hits * 0.06))
        scored.append({'name': name, 'url': url, 'score': round(float(score), 3)})
    scored.sort(key=lambda item: item['score'], reverse=True)
    return scored


def search_facebook_pages(
    page: Any,
    query: str,
    *,
    target_name: str | None = None,
    scroll_rounds: int = 2,
    keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Pipeline complet recherche pages.

    @param page: Page Playwright connectee
    @param query: Requete
    @param target_name: Nom legal / commercial pour scoring
    @param scroll_rounds: Scrolls supplementaires
    @returns: Candidats scores
    @raises RuntimeError: Session expiree
    """
    if not is_logged_in_url(page.url):
        goto_check = page.url
        if 'login' in (goto_check or '').lower():
            raise RuntimeError('Session Facebook expiree — sync cookies danielcraft')

    open_pages_search(page, query)
    scroll_search_results(page, scroll_rounds)
    raw = collect_page_candidates(page)
    return score_candidates(raw, query, target_name, keywords=keywords)
