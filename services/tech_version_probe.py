"""
Va chercher les versions (RSS WP, readme, tete des JS) quand le HTML ne les montre pas.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests

from services.tech_fingerprint import (
    _VER,
    _asset_urls,
    detect_site_technologies,
    merge_technology_maps,
    split_tech_label,
    versions_from_file_banner,
)

logger = logging.getLogger(__name__)

_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

FetchFn = Callable[..., tuple[str | None, dict[str, Any]]]


def _origin(page_url: str) -> str:
    parsed = urlparse(page_url if '://' in (page_url or '') else f'https://{page_url}')
    scheme = parsed.scheme or 'https'
    netloc = parsed.netloc or parsed.path.split('/')[0]
    return f'{scheme}://{netloc}'


def _tech_version(tech_map: dict[str, list], category: str, name: str) -> str | None:
    target = name.lower()
    for raw in tech_map.get(category) or []:
        label_name, version = split_tech_label(str(raw))
        if label_name.lower() == target:
            return version
    return None


def _has_tech(tech_map: dict[str, list], category: str, name: str) -> bool:
    target = name.lower()
    for raw in tech_map.get(category) or []:
        label_name, _version = split_tech_label(str(raw))
        if label_name.lower() == target:
            return True
    return False


def default_fetch(url: str, max_bytes: int | None = None, timeout: int = 6) -> tuple[str | None, dict[str, Any]]:
    """
    GET simple pour les sondes de version.

    @param url: URL a tirer
    @param max_bytes: Tronque le corps (tete de fichier JS)
    @param timeout: Timeout secondes
    @returns: (texte, headers) ou (None, {})
    """
    headers = {'User-Agent': _UA, 'Accept': '*/*'}
    if max_bytes:
        headers['Range'] = f'bytes=0-{max_bytes}'
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        raw = response.content or b''
        if max_bytes:
            raw = raw[:max_bytes]
        text = raw.decode(response.encoding or 'utf-8', errors='replace')
        return text, dict(response.headers or {})
    except Exception as exc:
        logger.info('[tech-probe] Echec %s: %s', url, exc)
        return None, {}


def complete_technology_versions(
    page_url: str,
    html: str | None,
    headers: dict[str, Any] | None,
    existing: dict[str, list] | None,
    fetch_fn: FetchFn | None = None,
) -> dict[str, list[str]]:
    """
    Complete les versions manquantes via RSS WP, readme, et commentaires des JS.

    @param page_url: Page de depart
    @param html: HTML deja telecharge (ou None)
    @param headers: Headers de cette page
    @param existing: Technologies deja vues
    @param fetch_fn: GET custom (tests / scraper)
    @returns: Carte fusionnee avec versions
    """
    fetch = fetch_fn or default_fetch
    found = merge_technology_maps(existing, {})
    if html:
        found = merge_technology_maps(found, detect_site_technologies(html, headers or {}))

    origin = _origin(page_url or '')
    if not origin or origin == 'https://':
        return found

    html_low = (html or '').lower()
    has_wp = (
        _has_tech(found, 'cms', 'WordPress')
        or '/wp-content/' in html_low
        or '/wp-includes/' in html_low
    )
    wp_ver = _tech_version(found, 'cms', 'WordPress')
    extra_urls: list[str] = []
    if has_wp and not wp_ver:
        extra_urls.extend(
            [
                origin + '/feed/',
                origin + '/?feed=rss2',
                origin + '/readme.html',
            ]
        )
    if _has_tech(found, 'cms', 'Drupal') and not _tech_version(found, 'cms', 'Drupal'):
        extra_urls.append(origin + '/core/misc/drupal.js')

    for extra in extra_urls:
        text, hdrs = fetch(extra, max_bytes=12000)
        if not text:
            continue
        found = merge_technology_maps(found, detect_site_technologies(text, hdrs))
        if extra.endswith('readme.html'):
            match = re.search(rf'<h1[^>]*>\s*Version\s+{_VER}', text, re.I)
            if not match:
                match = re.search(rf'\bVersion\s+{_VER}', text, re.I)
            if match:
                found = merge_technology_maps(found, {'cms': [f'WordPress {match.group(1)}']})
        if _tech_version(found, 'cms', 'WordPress'):
            break

    if html:
        wanted: list[str] = []
        for src in _asset_urls(html):
            low = src.lower()
            abs_src = urljoin(page_url if '://' in (page_url or '') else origin + '/', src)
            if 'jquery' in low and 'migrate' not in low and not _tech_version(found, 'library', 'jQuery'):
                wanted.append(abs_src)
            elif 'bootstrap' in low and not _tech_version(found, 'css', 'Bootstrap'):
                wanted.append(abs_src)
            elif re.search(r'vue(?:\.min)?\.js|vue\.global|vue\.runtime', low) and not _tech_version(
                found, 'framework', 'Vue.js'
            ):
                wanted.append(abs_src)
            elif 'react' in low and not _tech_version(found, 'framework', 'React'):
                wanted.append(abs_src)
        seen = set()
        for src in wanted:
            if src in seen:
                continue
            seen.add(src)
            if len(seen) > 6:
                break
            text, _hdrs = fetch(src, max_bytes=2500)
            if text:
                found = merge_technology_maps(found, versions_from_file_banner(src, text))

    return found


def probe_site_versions(url: str, existing: dict[str, list] | None = None) -> dict[str, list[str]]:
    """
    Telecharge la home puis complete les versions.

    @param url: Site a sonder
    @param existing: Technos deja en base
    @returns: Carte fusionnee
    """
    if not url:
        return existing or {}
    page = url if '://' in url else 'https://' + url
    html, headers = default_fetch(page, timeout=8)
    return complete_technology_versions(page, html, headers, existing, default_fetch)
