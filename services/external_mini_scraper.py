"""
Mini-scraping des sites externes (liens sortants) : homepage + pages de 1er niveau
(même domaine), extraction titre, meta, Open Graph, images, téléphones, indices d’adresse.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from services.logging_config import setup_logger


def _mini_scrape_log_level() -> int:
    """Niveau de log : EXTERNAL_MINI_SCRAPE_LOG_LEVEL ou AGENCY_MINI_SCRAPE_LOG_LEVEL (défaut INFO)."""
    raw = (
        os.environ.get('EXTERNAL_MINI_SCRAPE_LOG_LEVEL')
        or os.environ.get('AGENCY_MINI_SCRAPE_LOG_LEVEL')
        or 'INFO'
    ).strip().upper()
    return getattr(logging, raw, logging.INFO)


logger = setup_logger(__name__, 'external_mini_scraper.log', level=_mini_scrape_log_level())


def _ext_mini_env(name: str, default: str) -> str:
    """Préfère ``EXTERNAL_MINI_SCRAPE_*``, retombe sur ``AGENCY_MINI_SCRAPE_*`` (compat)."""
    v = os.environ.get(f'EXTERNAL_MINI_SCRAPE_{name}')
    if v is not None and str(v).strip() != '':
        return str(v).strip()
    legacy = os.environ.get(f'AGENCY_MINI_SCRAPE_{name}')
    if legacy is not None and str(legacy).strip() != '':
        return str(legacy).strip()
    return default


_DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
}

_BLOCKLIST_SUFFIXES = frozenset({
    'google.com', 'google.fr', 'gstatic.com', 'googleusercontent.com', 'googleapis.com',
    'googletagmanager.com', 'google-analytics.com', 'doubleclick.net', 'googleadservices.com',
    'facebook.com', 'fb.com', 'instagram.com', 'linkedin.com', 'twitter.com', 'x.com',
    'youtube.com', 'youtu.be', 'tiktok.com', 'pinterest.com', 'schema.org', 'w3.org',
    'goo.gl', 'bit.ly', 't.co', 'ow.ly', 'tinyurl.com',
})

_SKIP_PATH_SUFFIXES = (
    '.pdf', '.zip', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.css', '.js',
    '.mp4', '.mp3', '.woff', '.woff2',
)

_PRIORITY_PATH_FRAGMENTS = (
    'contact', 'nous-contacter', 'about', 'a-propos', 'apropos', 'qui-sommes', 'mentions',
    'legal', 'legals', 'equipe', 'team', 'adresse', 'l-agence', 'lagence', 'studio', 'cabinet',
    'impressum', 'privacy', 'confidentialite', 'services', 'realisations', 'portfolio',
)

_PHONE_RE = re.compile(
    r'(?:\+33[\s.\-]?|0)\d(?:[\s.\-]?\d){8,}',
    re.I,
)


def _host_key(netloc: str) -> str:
    h = (netloc or '').lower().split(':')[0]
    if h.startswith('www.'):
        h = h[4:]
    return h


def _blocked_host(host_key: str) -> bool:
    if not host_key:
        return True
    for suf in _BLOCKLIST_SUFFIXES:
        if host_key == suf or host_key.endswith('.' + suf):
            return True
    return False


def _normalize_internal_url(abs_url: str) -> Optional[str]:
    try:
        p = urlparse(abs_url)
        if p.scheme not in ('http', 'https'):
            return None
        path = (p.path or '/')[:500]
        low = path.lower()
        if any(low.endswith(s) for s in _SKIP_PATH_SUFFIXES):
            return None
        # Sans fragment ; query conservée (pagination rare sur mini-scrape)
        clean = urlunparse((p.scheme, p.netloc.lower(), path.rstrip('/') or '/', '', p.query, ''))
        return clean
    except Exception:
        return None


def _path_priority_score(path: str) -> int:
    p = (path or '').lower()
    return sum(1 for frag in _PRIORITY_PATH_FRAGMENTS if frag in p)


def _favicon_href_is_usable(abs_u: str) -> bool:
    """Évite les URL de services tiers (Google, etc.) — même logique que le scraper principal."""
    low = abs_u.lower()
    if 'gstatic.com' in low or 'google.com/s2/favicons' in low or 'faviconV2' in low:
        return False
    try:
        hk = _host_key(urlparse(abs_u).netloc)
    except Exception:
        return False
    return not _blocked_host(hk)


def _extract_favicon_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """``<link rel=icon>`` / apple-touch-icon, ou ``/favicon.ico`` par défaut."""
    candidates: List[Tuple[int, str]] = []
    for link in soup.find_all('link', href=True):
        href = (link.get('href') or '').strip()
        if not href:
            continue
        rel = link.get('rel')
        if rel is None:
            continue
        rel_list = [rel] if isinstance(rel, str) else list(rel)
        rel_s = ' '.join(rel_list).lower()
        prio = 99
        if 'apple-touch-icon' in rel_s:
            prio = 0
        elif 'icon' in rel_s or 'shortcut' in rel_s:
            prio = 1 if 'shortcut' in rel_s else 2
        else:
            continue
        abs_u = urljoin(base_url, href)
        if not abs_u.startswith('http'):
            continue
        if not _favicon_href_is_usable(abs_u):
            continue
        candidates.append((prio, abs_u[:2000]))
    if candidates:
        candidates.sort(key=lambda x: (x[0], len(x[1])))
        return candidates[0][1]
    try:
        p = urlparse(base_url)
        if p.scheme and p.netloc:
            return f'{p.scheme}://{p.netloc}/favicon.ico'
    except Exception:
        pass
    return None


def _pick_site_preview_urls(
    home_profile: Dict[str, Any], soup: BeautifulSoup, final_url: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Retourne (thumbnail_préféré, og_image_url, favicon_url).
    Ordre : og:image, twitter:image, 1ère image page, favicon.
    """
    og = home_profile.get('open_graph') or {}
    og_img = (og.get('og:image') or og.get('og:image:url') or '').strip()
    if og_img:
        og_img = urljoin(final_url, og_img)[:2000]
    tw = soup.find('meta', attrs={'name': re.compile(r'^twitter:image$', re.I)})
    tw_u = None
    if tw and tw.get('content'):
        tw_u = urljoin(final_url, str(tw['content']).strip())[:2000]
    imgs = home_profile.get('image_urls') or []
    first_img = (imgs[0] if imgs else None) or None
    if first_img:
        first_img = str(first_img).strip()[:2000]
    fav = _extract_favicon_url(soup, final_url)
    thumb = og_img or tw_u or first_img or fav
    return thumb, og_img, fav


def _extract_open_graph(soup: BeautifulSoup) -> Dict[str, str]:
    og: Dict[str, str] = {}
    for meta in soup.find_all('meta', attrs={'property': True}):
        prop = meta.get('property')
        if not prop or not str(prop).strip().lower().startswith('og:'):
            continue
        content = meta.get('content')
        if content is None:
            continue
        key = str(prop).strip()
        og[key] = str(content).strip()[:2000]
    return og


def _extract_image_urls(soup: BeautifulSoup, base_url: str, limit: int = 14) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for sel in (
        {'property': re.compile(r'^og:image$', re.I)},
        {'name': re.compile(r'^twitter:image$', re.I)},
    ):
        m = soup.find('meta', attrs=sel)
        if m and m.get('content'):
            u = urljoin(base_url, str(m['content']).strip())
            if u.startswith('http') and u not in seen:
                seen.add(u)
                out.append(u[:2000])
        if len(out) >= limit:
            return out[:limit]
    for img in soup.find_all('img', src=True):
        src = (img.get('src') or '').strip()
        if not src or src.startswith('data:'):
            continue
        u = urljoin(base_url, src)
        if not u.startswith('http'):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u[:2000])
        if len(out) >= limit:
            break
    return out[:limit]


def _extract_phones(soup: BeautifulSoup) -> List[str]:
    found: List[str] = []
    seen: Set[str] = set()
    for a in soup.find_all('a', href=True):
        href = (a.get('href') or '').strip()
        if not href.lower().startswith('tel:'):
            continue
        raw = href[4:].strip()
        digits = re.sub(r'\D', '', raw)
        if len(digits) >= 8:
            norm = raw[:80]
            if norm not in seen:
                seen.add(norm)
                found.append(norm)
    text = soup.get_text(' ', strip=True)[:12000]
    for m in _PHONE_RE.finditer(text):
        chunk = re.sub(r'\s+', ' ', m.group(0).strip())[:40]
        d = re.sub(r'\D', '', chunk)
        if len(d) >= 10 and chunk not in seen:
            seen.add(chunk)
            found.append(chunk)
        if len(found) >= 12:
            break
    return found


def _collect_level1_urls(soup: BeautifulSoup, final_url: str, site_key: str, max_urls: int) -> List[str]:
    """URLs même registrable (site_key), triées par pertinence (contact, à propos, …)."""
    candidates: List[Tuple[int, str]] = []
    seen: Set[str] = set()
    for a in soup.find_all('a', href=True):
        href = (a.get('href') or '').strip()
        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
            continue
        abs_u = urljoin(final_url, href)
        nu = _normalize_internal_url(abs_u)
        if not nu:
            continue
        try:
            hk = _host_key(urlparse(nu).netloc)
        except Exception:
            continue
        if hk != site_key:
            continue
        if nu in seen:
            continue
        seen.add(nu)
        if nu.rstrip('/') == final_url.rstrip('/'):
            continue
        sc = _path_priority_score(urlparse(nu).path)
        candidates.append((sc, nu))
    candidates.sort(key=lambda x: (-x[0], len(x[1]), x[1]))
    return [u for _, u in candidates[:max_urls]]


def _profile_page(
    soup: BeautifulSoup,
    page_url: str,
    depth: int,
    http_status: Optional[int],
    fetch_error: Optional[str],
) -> Dict[str, Any]:
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()[:500]
    desc = None
    dm = soup.find('meta', attrs={'name': re.compile(r'^description$', re.I)})
    if dm and dm.get('content'):
        desc = str(dm['content']).strip()[:1200]
    if not desc:
        ogd = soup.find('meta', attrs={'property': re.compile(r'^og:description$', re.I)})
        if ogd and ogd.get('content'):
            desc = str(ogd['content']).strip()[:1200]
    og = _extract_open_graph(soup)
    images = _extract_image_urls(soup, page_url)
    phones = _extract_phones(soup)
    loc = None
    try:
        from services.location_harvest import finalize_scraped_location, harvest_locations_from_page

        hits = harvest_locations_from_page(soup, page_url, depth)
        loc = finalize_scraped_location(hits)
    except Exception as e:
        logger.debug('[external_mini_scrape] location page %s: %s', page_url, e)

    return {
        'page_url': page_url,
        'depth': depth,
        'http_status': http_status,
        'title': title,
        'meta_description': desc,
        'open_graph': og,
        'image_urls': images,
        'phones': phones,
        'scraped_location': loc,
        'fetch_error': fetch_error,
        'fetched_at': datetime.now(timezone.utc).isoformat(),
    }


def _scraped_location_quality(loc: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    """Plus haut = meilleur : préfère les sources non-regex, puis le nombre de champs remplis."""
    if not isinstance(loc, dict) or not loc:
        return (-1, -1)
    src = str(loc.get('source') or '').lower()
    regex_only = 'regex' in src
    n = sum(
        1
        for k in ('street_address', 'postal_code', 'locality', 'country', 'latitude', 'longitude')
        if loc.get(k) not in (None, '')
    )
    prio = 0 if regex_only else 1
    return (prio, n)


def _pick_best_scraped_location(pages: List[Any]) -> Optional[Dict[str, Any]]:
    """Meilleur lieu parmi la homepage et les pages niveau 1 (ex. JSON-LD sur /contact)."""
    best: Optional[Dict[str, Any]] = None
    best_q = (-1, -1)
    for pg in pages or []:
        if not isinstance(pg, dict):
            continue
        loc = pg.get('scraped_location')
        q = _scraped_location_quality(loc)
        if q > best_q:
            best_q = q
            best = loc if isinstance(loc, dict) else None
    return best


def enrich_external_links_in_place(
    external_links_list: List[Dict[str, Any]],
    progress_callback: Optional[Callable[[str], None]] = None,
) -> int:
    """
    Mini-GET homepage par domaine externe : ``external_snapshot`` + classification
    (agence, asso, admin, personne, etc.). Par défaut tous les domaines (plafond env),
    sauf si ``EXTERNAL_MINI_SCRAPE_CREDIT_ONLY=1`` (crédits / likely_credit seuls).

    Returns:
        Nombre de domaines distincts effectivement interrogés.
    """
    co = (
        os.environ.get('EXTERNAL_MINI_SCRAPE_CREDIT_ONLY')
        or os.environ.get('AGENCY_MINI_SCRAPE_CREDIT_ONLY')
        or ''
    )
    credit_only = str(co).strip().lower() in ('1', 'true', 'yes', 'on')
    try:
        max_dom = max(0, int(_ext_mini_env('MAX', '28')))
    except ValueError:
        max_dom = 28
    delay = float(_ext_mini_env('DELAY_SEC', '0.35'))
    if max_dom <= 0 or not external_links_list:
        logger.debug(
            '[external_mini_scrape] enrich_external_links_in_place: rien à faire (max_dom=%s, liens=%s)',
            max_dom,
            len(external_links_list) if external_links_list else 0,
        )
        return 0

    by_dom: Dict[str, str] = {}
    dom_has_credit: Dict[str, bool] = {}
    for it in external_links_list:
        if not isinstance(it, dict):
            continue
        d = (it.get('domain') or '').strip()
        u = (it.get('url') or '').strip()
        if not d or not u or _blocked_host(d):
            continue
        if credit_only and not it.get('likely_credit'):
            continue
        if d not in by_dom:
            by_dom[d] = u
        if it.get('likely_credit'):
            dom_has_credit[d] = True

    def _sort_domains(items: List[Tuple[str, str]]) -> List[str]:
        return [
            d for d, _ in sorted(
                items,
                key=lambda x: (not dom_has_credit.get(x[0], False), x[0].lower()),
            )
        ]

    domains = _sort_domains(list(by_dom.items()))[:max_dom]
    logger.info(
        '[external_mini_scrape] enrich démarrage: credit_only=%s max_dom=%s delay_sec=%s domaines_distincts=%s '
        '(parmi %s candidats)',
        credit_only,
        max_dom,
        delay,
        len(domains),
        len(by_dom),
    )
    if progress_callback and domains:
        try:
            progress_callback(f'Mini-scan des sites externes ({len(domains)} domaine(s))…')
        except Exception:
            pass

    for i, dom in enumerate(domains):
        if i > 0:
            time.sleep(delay)
        seed = by_dom[dom]
        logger.info(
            '[external_mini_scrape] domaine %s/%s : %s (seed=%s)',
            i + 1,
            len(domains),
            dom,
            seed[:120] + ('…' if len(seed) > 120 else ''),
        )
        try:
            snap = mini_scrape_external_homepage(seed)
        except Exception as e:
            logger.warning('[external_mini_scrape] domaine %s exception: %s', dom, e, exc_info=True)
            snap = {'seed_url': seed, 'error': str(e)[:300]}
        err = snap.get('error') if isinstance(snap, dict) else None
        if err:
            logger.warning('[external_mini_scrape] domaine %s échec: %s', dom, err)
        else:
            n_pages = len(snap.get('pages') or []) if isinstance(snap, dict) else 0
            n_port = snap.get('portfolio_hosts_count') if isinstance(snap, dict) else None
            title = (snap.get('title') or '')[:80] if isinstance(snap, dict) else ''
            logger.info(
                '[external_mini_scrape] domaine %s OK final_url=%s pages=%s portfolio_hosts=%s title=%r',
                dom,
                (snap.get('final_url') or '')[:200] if isinstance(snap, dict) else '',
                n_pages,
                n_port,
                title,
            )
        for it in external_links_list:
            if it.get('domain') == dom:
                it['external_snapshot'] = snap

    logger.info('[external_mini_scrape] enrich terminé: %s domaine(s) scanné(s)', len(domains))
    return len(domains)


def _http_get(url: str, timeout: float) -> Tuple[Optional[requests.Response], Optional[str]]:
    logger.debug('[external_mini_scrape] GET %s (timeout=%s)', url, timeout)
    try:
        r = requests.get(url, headers=_DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        logger.debug(
            '[external_mini_scrape] GET %s → HTTP %s',
            url,
            getattr(r, 'status_code', '?'),
        )
        return r, None
    except requests.RequestException as e:
        logger.debug('[external_mini_scrape] GET %s exception: %s', url, e)
        return None, str(e)[:500]


def mini_scrape_external_homepage(seed_url: str) -> Dict[str, Any]:
    """
    GET homepage puis pages internes de 1er niveau (même domaine), avec extraction
    structurée par page (titre, description, OG, images, téléphones, lieu).

    Returns:
        dict avec final_url, title, description (homepage), portfolio_hosts, pages[], classification, …
    """
    timeout = float(_ext_mini_env('TIMEOUT_SEC', '8'))
    max_hosts = max(5, int(_ext_mini_env('MAX_PORTFOLIO_HOSTS', '60')))
    try:
        max_pages = max(1, int(_ext_mini_env('MAX_PAGES', '8')))
    except ValueError:
        max_pages = 8
    try:
        max_level1 = max(0, int(_ext_mini_env('MAX_LEVEL1_URLS', '7')))
    except ValueError:
        max_level1 = 7
    page_delay = float(_ext_mini_env('PAGE_DELAY_SEC', '0.28'))
    level1_enabled = str(_ext_mini_env('LEVEL1', '1')).strip().lower() not in (
        '0', 'false', 'no', 'off',
    )

    out: Dict[str, Any] = {
        'seed_url': seed_url,
        'final_url': None,
        'title': None,
        'description': None,
        'portfolio_hosts': [],
        'portfolio_hosts_count': 0,
        'pages': [],
        'error': None,
        'fetched_at': datetime.now(timezone.utc).isoformat(),
    }

    if not seed_url or not str(seed_url).startswith(('http://', 'https://')):
        out['error'] = 'URL invalide'
        logger.warning('[external_mini_scrape] URL invalide: %r', seed_url)
        return out

    logger.info(
        '[external_mini_scrape] homepage début seed=%s timeout=%s max_pages=%s level1=%s',
        seed_url[:200],
        timeout,
        max_pages,
        level1_enabled,
    )

    resp, err = _http_get(seed_url, timeout)
    if err or resp is None:
        out['error'] = err or 'requête vide'
        logger.warning('[external_mini_scrape] requête homepage échouée %s : %s', seed_url, out['error'])
        return out

    try:
        resp.raise_for_status()
    except requests.RequestException as e:
        out['error'] = str(e)[:500]
        logger.warning(
            '[external_mini_scrape] HTTP erreur homepage %s : %s',
            getattr(resp, 'url', seed_url),
            out['error'],
        )
        return out

    final = resp.url
    out['final_url'] = final
    parsed_final = urlparse(final)
    external_host_key = _host_key(parsed_final.netloc)
    if not external_host_key:
        out['error'] = 'Hôte vide après redirection'
        logger.warning('[external_mini_scrape] hôte vide après redirection: %s', final)
        return out

    ctype = (resp.headers.get('Content-Type') or '').lower()
    if 'html' not in ctype and 'text/plain' not in ctype:
        out['error'] = f'Content-Type non HTML: {ctype[:80]}'
        logger.warning('[external_mini_scrape] Content-Type rejeté %s : %s', final, ctype[:120])
        return out

    soup = BeautifulSoup(resp.text, 'html.parser')
    home_profile = _profile_page(soup, final, 0, resp.status_code, None)
    out['pages'].append(home_profile)
    out['title'] = home_profile.get('title')
    out['description'] = home_profile.get('meta_description')
    thumb, og_img, fav = _pick_site_preview_urls(home_profile, soup, final)
    out['thumbnail_url'] = thumb
    out['og_image_url'] = og_img
    out['favicon_url'] = fav

    try:
        from services.external_site_classifier import classify_external_homepage

        out['classification'] = classify_external_homepage(
            soup,
            out.get('title'),
            out.get('description'),
            final or seed_url,
        )
    except Exception as e:
        logger.debug('[external_mini_scrape] classification: %s', e)

    hosts: Set[str] = set()
    for a in soup.find_all('a', href=True):
        href = (a.get('href') or '').strip()
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:')):
            continue
        abs_u = urljoin(final, href)
        try:
            p = urlparse(abs_u)
        except Exception:
            continue
        if p.scheme not in ('http', 'https'):
            continue
        hk = _host_key(p.netloc)
        if not hk or hk == external_host_key:
            continue
        if _blocked_host(hk):
            continue
        hosts.add(hk)
        if len(hosts) >= max_hosts:
            break
    out['portfolio_hosts'] = sorted(hosts)
    out['portfolio_hosts_count'] = len(hosts)

    extra_budget = min(max_level1, max(0, max_pages - 1))
    if level1_enabled and extra_budget > 0:
        to_fetch = _collect_level1_urls(soup, final, external_host_key, extra_budget)
        logger.info(
            '[external_mini_scrape] niveau 1: %s URL(s) à fetch (budget=%s, page_delay=%s)',
            len(to_fetch),
            extra_budget,
            page_delay,
        )
        for j, u in enumerate(to_fetch):
            if j > 0:
                time.sleep(page_delay)
            logger.debug('[external_mini_scrape] niveau 1 [%s/%s] %s', j + 1, len(to_fetch), u)
            r2, e2 = _http_get(u, timeout)
            if e2 or r2 is None:
                out['pages'].append({
                    'page_url': u,
                    'depth': 1,
                    'http_status': None,
                    'title': None,
                    'meta_description': None,
                    'open_graph': {},
                    'image_urls': [],
                    'phones': [],
                    'scraped_location': None,
                    'fetch_error': e2,
                    'fetched_at': datetime.now(timezone.utc).isoformat(),
                })
                continue
            try:
                r2.raise_for_status()
            except requests.RequestException as ex:
                out['pages'].append({
                    'page_url': u,
                    'depth': 1,
                    'http_status': getattr(r2, 'status_code', None),
                    'title': None,
                    'meta_description': None,
                    'open_graph': {},
                    'image_urls': [],
                    'phones': [],
                    'scraped_location': None,
                    'fetch_error': str(ex)[:500],
                    'fetched_at': datetime.now(timezone.utc).isoformat(),
                })
                continue
            ct2 = (r2.headers.get('Content-Type') or '').lower()
            if 'html' not in ct2:
                out['pages'].append({
                    'page_url': r2.url,
                    'depth': 1,
                    'http_status': r2.status_code,
                    'title': None,
                    'meta_description': None,
                    'open_graph': {},
                    'image_urls': [],
                    'phones': [],
                    'scraped_location': None,
                    'fetch_error': f'non-HTML: {ct2[:60]}',
                    'fetched_at': datetime.now(timezone.utc).isoformat(),
                })
                continue
            sp = BeautifulSoup(r2.text, 'html.parser')
            out['pages'].append(_profile_page(sp, r2.url, 1, r2.status_code, None))
            logger.debug(
                '[external_mini_scrape] niveau 1 OK %s HTTP %s',
                r2.url[:160],
                r2.status_code,
            )

    best_loc = _pick_best_scraped_location(out.get('pages') or [])
    if best_loc:
        out['scraped_location'] = best_loc
        for pg in out.get('pages') or []:
            if not isinstance(pg, dict) or int(pg.get('depth') or 0) != 0:
                continue
            cur = pg.get('scraped_location')
            if _scraped_location_quality(best_loc) > _scraped_location_quality(cur):
                pg['scraped_location'] = best_loc
            break

    logger.info(
        '[external_mini_scrape] homepage fin host=%s pages=%s portfolio_hosts=%s seed=%s',
        external_host_key,
        len(out.get('pages') or []),
        out.get('portfolio_hosts_count'),
        seed_url[:160],
    )
    return out
