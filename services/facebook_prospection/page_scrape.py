"""
Scrape leger d'une page Facebook publique.
"""

from __future__ import annotations

import time
from typing import Any

from .facebook_ui import dismiss_cookie_banners


def scrape_public_page(page: Any, url: str) -> dict[str, Any]:
    """
    Lit titre, extrait texte et liens externes.

    @param page: Page Playwright
    @param url: URL page Facebook
    @returns: Dict profile (title, about_preview, external_links, page_url)
    """
    page.goto(url, wait_until='domcontentloaded', timeout=90_000)
    time.sleep(2.5)
    dismiss_cookie_banners(page)
    data = page.evaluate(
        """() => {
        const title =
            document.querySelector('h1')?.innerText?.trim() ||
            document.querySelector('[data-pagelet="page"] h1')?.innerText?.trim() ||
            document.title;
        const about =
            document.querySelector('[data-pagelet*="ProfileTilesFeed"]')?.innerText?.slice(0, 2000) ||
            document.body?.innerText?.slice(0, 1500) ||
            '';
        const links = [...document.querySelectorAll('a[href^="http"]')]
            .map((a) => ({
                text: (a.innerText || '').trim().slice(0, 80),
                href: a.href,
            }))
            .filter((l) => l.href && !/facebook\\.com/i.test(l.href))
            .slice(0, 15);
        return {
            title: (title || '').slice(0, 200),
            about_preview: about.replace(/\\s+/g, ' ').trim().slice(0, 1200),
            external_links: links,
            page_url: location.href,
        };
    }"""
    )
    return dict(data or {})
