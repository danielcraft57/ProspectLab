"""
Tâches Celery pour les captures d'écran de sites (desktop/tablet/mobile).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from io import BytesIO
from pathlib import Path
import time
from urllib.parse import urlparse

from celery_app import celery
from config import (
    WEBSITE_SCREENSHOT_BLOCK_TRACKERS,
    WEBSITE_SCREENSHOT_CLEANUP_BATCH_SIZE,
    WEBSITE_SCREENSHOT_CAPTURE_FORMAT,
    WEBSITE_SCREENSHOT_DEVICE_SCALE_FACTOR,
    WEBSITE_SCREENSHOT_DISABLE_ANIMATIONS,
    WEBSITE_SCREENSHOT_GOTO_TIMEOUT_MS,
    WEBSITE_SCREENSHOT_GOTO_WAIT_UNTIL,
    WEBSITE_SCREENSHOT_JPEG_QUALITY,
    WEBSITE_SCREENSHOT_KEEP_SETS,
    WEBSITE_SCREENSHOT_MAX_WIDTH_DESKTOP,
    WEBSITE_SCREENSHOT_MAX_WIDTH_MOBILE,
    WEBSITE_SCREENSHOT_MAX_WIDTH_TABLET,
    WEBSITE_SCREENSHOT_PARALLEL,
    WEBSITE_SCREENSHOT_REDUCED_MOTION,
    WEBSITE_SCREENSHOT_TRIM_WHITE_BOTTOM,
    WEBSITE_SCREENSHOT_TRIM_WHITE_MIN_TRAILING_RATIO,
    WEBSITE_SCREENSHOT_TRIM_WHITE_PADDING_PX,
    WEBSITE_SCREENSHOT_TRIM_WHITE_THRESHOLD,
    WEBSITE_SCREENSHOT_VIEWPORT_DESKTOP_HEIGHT,
    WEBSITE_SCREENSHOT_VIEWPORT_DESKTOP_WIDTH,
    WEBSITE_SCREENSHOT_VIEWPORT_MOBILE_HEIGHT,
    WEBSITE_SCREENSHOT_VIEWPORT_MOBILE_WIDTH,
    WEBSITE_SCREENSHOT_VIEWPORT_TABLET_HEIGHT,
    WEBSITE_SCREENSHOT_VIEWPORT_TABLET_WIDTH,
    WEBSITE_SCREENSHOT_WAIT_MS,
    WEBSITE_SCREENSHOT_WEBP_QUALITY,
    WEBSITE_SCREENSHOTS_BASE_URL,
    WEBSITE_SCREENSHOTS_DIR,
)
from services.database import Database
from services.logging_config import setup_logger
from utils.url_utils import canonical_website_https_url

logger = setup_logger(__name__, 'screenshot_tasks.log')

# Chromium : options courantes pour headless plus léger / moins de bruit réseau inutile.
_CHROMIUM_LAUNCH_ARGS = (
    '--disable-dev-shm-usage',
    '--disable-extensions',
    '--disable-default-apps',
    '--mute-audio',
    '--no-first-run',
    '--disable-background-networking',
)

# Sous-chaînes d’URL (analytics / pub) — bloque surtout scripts / pixels, accélère le chargement.
_TRACKER_URL_MARKERS: tuple[str, ...] = (
    'google-analytics.com',
    'googletagmanager.com',
    'googleadservices.com',
    'doubleclick.net',
    'googlesyndication.com',
    'pagead2.googlesyndication',
    'adservice.google',
    'connect.facebook.net',
    'facebook.net/tr',
    'hotjar.com',
    'clarity.ms',
    'linkedin.com/px',
    'bat.bing.com',
    'scorecardresearch.com',
    'quantserve.com',
    'mxpnl.com',
    'cdn.mxpnl.com',
    'segment.io',
    'cdn.segment.com',
    'plausible.io',
    'browser.sentry-cdn.com',
    'ingest.sentry.io',
)


def _url_matches_tracker(url: str) -> bool:
    u = url.lower()
    return any(m in u for m in _TRACKER_URL_MARKERS)


def _route_abort_tracker_sync(route) -> None:
    if _url_matches_tracker(route.request.url):
        route.abort()
    else:
        route.continue_()


async def _route_abort_tracker_async(route) -> None:
    if _url_matches_tracker(route.request.url):
        await route.abort()
    else:
        await route.continue_()


def _browser_context_kwargs(device: dict) -> dict:
    opts: dict = {
        'viewport': {'width': int(device['width']), 'height': int(device['height'])},
        'is_mobile': bool(device['is_mobile']),
        'has_touch': bool(device['has_touch']),
        'device_scale_factor': float(WEBSITE_SCREENSHOT_DEVICE_SCALE_FACTOR),
    }
    if WEBSITE_SCREENSHOT_REDUCED_MOTION:
        opts['reduced_motion'] = 'reduce'
    return opts


def _viewport_screenshot_kwargs() -> dict:
    kw: dict = {'full_page': False}
    if WEBSITE_SCREENSHOT_DISABLE_ANIMATIONS:
        kw['animations'] = 'disabled'
    fmt = WEBSITE_SCREENSHOT_CAPTURE_FORMAT
    if fmt in ('jpeg', 'jpg'):
        kw['type'] = 'jpeg'
        kw['quality'] = int(WEBSITE_SCREENSHOT_JPEG_QUALITY)
    else:
        kw['type'] = 'png'
    return kw


def _screenshot_viewport_sync(page) -> bytes:
    kw = _viewport_screenshot_kwargs()
    try:
        return page.screenshot(**kw)
    except TypeError:
        kw.pop('animations', None)
        return page.screenshot(**kw)


async def _screenshot_viewport_async(page) -> bytes:
    kw = _viewport_screenshot_kwargs()
    try:
        return await page.screenshot(**kw)
    except TypeError:
        kw.pop('animations', None)
        return await page.screenshot(**kw)


def _safe_slug_from_url(url: str) -> str:
    host = (urlparse(url).netloc or '').strip().lower()
    if host.startswith('www.'):
        host = host[4:]
    cleaned = ''.join(ch if ch.isalnum() or ch in ('-', '_', '.') else '-' for ch in host)
    return cleaned[:120] or 'site'


def _public_url_for_file(file_path: Path) -> str | None:
    try:
        rel = file_path.resolve().relative_to(WEBSITE_SCREENSHOTS_DIR.resolve())
    except Exception:
        return None
    rel_url = str(rel.as_posix()).lstrip('/')
    base = str(WEBSITE_SCREENSHOTS_BASE_URL or '/static/screenshots/website_previews').rstrip('/')
    return f'{base}/{rel_url}'


def _save_webp_from_image_bytes(
    image_bytes: bytes,
    target_path: Path,
    quality: int = 80,
    max_width: int | None = None,
) -> None:
    """
    Convertit des bytes image (PNG ou JPEG depuis Playwright) en WEBP (optionnellement redimensionné).
    """
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError(
            "Pillow n'est pas installé. Installez-le pour générer des screenshots WEBP."
        ) from exc

    q = max(40, min(int(quality or 80), 95))
    with Image.open(BytesIO(image_bytes)) as image:
        # Option anti "gros blanc" : coupe la partie basse quasi blanche
        # quand elle représente une grande partie du viewport.
        if WEBSITE_SCREENSHOT_TRIM_WHITE_BOTTOM:
            rgb = image.convert('RGB')
            px = rgb.load()
            w, h = rgb.size
            threshold = int(WEBSITE_SCREENSHOT_TRIM_WHITE_THRESHOLD)
            y_last_nonwhite = -1
            for y in range(h - 1, -1, -1):
                has_nonwhite = False
                for x in range(w):
                    r, g, b = px[x, y]
                    if not (r >= threshold and g >= threshold and b >= threshold):
                        has_nonwhite = True
                        break
                if has_nonwhite:
                    y_last_nonwhite = y
                    break

            if y_last_nonwhite >= 0:
                trailing_ratio = (h - 1 - y_last_nonwhite) / float(h)
                if trailing_ratio >= float(WEBSITE_SCREENSHOT_TRIM_WHITE_MIN_TRAILING_RATIO):
                    crop_bottom = min(
                        h,
                        y_last_nonwhite + 1 + int(WEBSITE_SCREENSHOT_TRIM_WHITE_PADDING_PX),
                    )
                    # Garde-fou : ne jamais couper à moins de 35% de la hauteur initiale.
                    crop_bottom = max(crop_bottom, int(h * 0.35))
                    if crop_bottom < h:
                        image = image.crop((0, 0, w, crop_bottom))

        mw = int(max_width) if max_width else None
        if mw and image.width > mw:
            new_h = max(1, int(round(image.height * (mw / float(image.width)))))
            # BOX sur fort rétrécissement : plus rapide ; sinon LANCZOS.
            if image.width > mw * 2:
                image = image.resize((mw, new_h), Image.Resampling.BOX)
            else:
                image = image.resize((mw, new_h), Image.Resampling.LANCZOS)

        if image.mode in ('RGBA', 'P'):
            rgba = image.convert('RGBA') if image.mode == 'P' else image
            alpha = rgba.split()[-1]
            if alpha.getextrema() == (255, 255):
                image = rgba.convert('RGB')
            else:
                image = rgba

        # method 4 = encodage plus rapide que 6 (fichiers un peu plus gros).
        image.save(str(target_path), format='WEBP', quality=q, method=4)


def _cleanup_old_screenshot_sets(database: Database, entreprise_id: int, keep_last: int = 5) -> int:
    """
    Garde les N derniers sets, supprime les anciens fichiers et lignes BDD.
    """
    deleted_rows = database.prune_entreprise_screenshot_sets(entreprise_id=entreprise_id, keep_last=keep_last)
    if not deleted_rows:
        return 0

    deleted_files = 0
    for row in deleted_rows:
        for key in ('desktop_file_path', 'tablet_file_path', 'mobile_file_path'):
            fp = row.get(key)
            if not fp:
                continue
            try:
                p = Path(str(fp))
                if p.exists() and p.is_file():
                    p.unlink()
                    deleted_files += 1
                # Nettoyage best-effort des dossiers vides proches.
                parent = p.parent
                for _ in range(3):
                    if parent == WEBSITE_SCREENSHOTS_DIR:
                        break
                    try:
                        parent.rmdir()
                    except Exception:
                        break
                    parent = parent.parent
            except Exception as exc:
                logger.debug('Suppression fichier screenshot ignorée (%s): %s', fp, exc)
    logger.info(
        'Cleanup screenshots entreprise_id=%s keep_last=%s deleted_sets=%s deleted_files=%s',
        entreprise_id,
        keep_last,
        len(deleted_rows),
        deleted_files,
    )
    return deleted_files


@celery.task(bind=True, name='screenshot.cleanup_old_screenshot_sets')
def cleanup_old_screenshot_sets_task(self, keep_last: int | None = None, batch_size: int | None = None):
    """
    Nettoyage périodique global des anciens screenshots (fichiers + BDD) pour toutes les entreprises.
    """
    keep = max(1, int(keep_last if keep_last is not None else WEBSITE_SCREENSHOT_KEEP_SETS))
    batch = max(10, min(int(batch_size if batch_size is not None else WEBSITE_SCREENSHOT_CLEANUP_BATCH_SIZE), 10000))

    t0 = time.monotonic()
    database = Database()
    entreprise_ids = database.list_entreprise_ids_with_screenshots(limit=batch)
    total = len(entreprise_ids)
    logger.info(
        'Cleanup global screenshots start keep_last=%s batch_size=%s entreprises_found=%s',
        keep,
        batch,
        total,
    )
    if total == 0:
        logger.info('Cleanup global screenshots: nothing to do')
        return {'success': True, 'processed': 0, 'deleted_files': 0, 'keep_last': keep}

    deleted_files = 0
    processed = 0
    for idx, entreprise_id in enumerate(entreprise_ids, start=1):
        try:
            deleted_files += _cleanup_old_screenshot_sets(
                database=database,
                entreprise_id=int(entreprise_id),
                keep_last=keep,
            )
            processed += 1
        except Exception as exc:
            logger.warning('Cleanup screenshots échoué pour entreprise %s: %s', entreprise_id, exc)
        if idx % 25 == 0:
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': int((idx * 100) / total),
                    'processed': idx,
                    'total': total,
                    'message': 'Nettoyage screenshots en cours...',
                },
            )

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        'Cleanup global screenshots done processed=%s total=%s deleted_files=%s elapsed_ms=%s',
        processed,
        total,
        deleted_files,
        elapsed_ms,
    )
    return {
        'success': True,
        'processed': processed,
        'total': total,
        'deleted_files': deleted_files,
        'keep_last': keep,
        'elapsed_ms': elapsed_ms,
    }


def _run_screenshots_sequential(
    *,
    self,
    website: str,
    devices: list[dict],
    base_dir: Path,
    slug: str,
    goto_wait: str,
    goto_timeout_ms: int,
    wait_timeout: int,
) -> tuple[list[dict], list[dict], dict[str, dict]]:
    """Playwright sync : une capture après l’autre."""
    from playwright.sync_api import sync_playwright

    captures: list[dict] = []
    errors: list[dict] = []
    capture_by_device: dict[str, dict] = {}
    total = len(devices)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=list(_CHROMIUM_LAUNCH_ARGS))
        try:
            for idx, device in enumerate(devices, start=1):
                device_type = device['type']
                progress = min(10 + int((idx - 1) * 80 / total), 90)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': progress,
                        'step': 'capture',
                        'device': device_type,
                        'message': f'Capture {device_type}...',
                    },
                )
                target_path = base_dir / f'{slug}.{device_type}.webp'
                try:
                    logger.info(
                        'Screenshot start mode=sequential device=%s website=%s viewport=%sx%s',
                        device_type,
                        website,
                        int(device['width']),
                        int(device['height']),
                    )
                    context = browser.new_context(**_browser_context_kwargs(device))
                    page = context.new_page()
                    try:
                        if WEBSITE_SCREENSHOT_BLOCK_TRACKERS:
                            page.route('**/*', _route_abort_tracker_sync)
                        page.goto(website, wait_until=goto_wait, timeout=goto_timeout_ms)
                        if wait_timeout > 0:
                            page.wait_for_timeout(wait_timeout)
                        shot_bytes = _screenshot_viewport_sync(page)
                    finally:
                        context.close()
                    _save_webp_from_image_bytes(
                        image_bytes=shot_bytes,
                        target_path=target_path,
                        quality=int(device['webp_quality']),
                        max_width=int(device['max_width']) if device.get('max_width') else None,
                    )
                    public_url = _public_url_for_file(target_path)
                    file_size = target_path.stat().st_size if target_path.exists() else 0
                    logger.info(
                        'Screenshot success mode=sequential device=%s file=%s bytes=%s public_url=%s',
                        device_type,
                        str(target_path),
                        file_size,
                        public_url or '',
                    )
                    capture_by_device[device_type] = {
                        'file_path': str(target_path),
                        'public_url': public_url,
                        'error': None,
                        'viewport': {'width': int(device['width']), 'height': int(device['height'])},
                    }
                    captures.append(
                        {
                            'device_type': device_type,
                            'file_path': str(target_path),
                            'public_url': public_url,
                            'viewport': {'width': int(device['width']), 'height': int(device['height'])},
                        }
                    )
                except Exception as exc:
                    err = str(exc)
                    errors.append({'device_type': device_type, 'error': err})
                    logger.warning('Capture %s échouée (%s): %s', device_type, website, err)
                    capture_by_device[device_type] = {
                        'file_path': str(target_path),
                        'public_url': None,
                        'error': err,
                        'viewport': {'width': int(device['width']), 'height': int(device['height'])},
                    }
        finally:
            browser.close()

    return captures, errors, capture_by_device


def _run_screenshots_parallel(
    *,
    self,
    website: str,
    devices: list[dict],
    base_dir: Path,
    slug: str,
    goto_wait: str,
    goto_timeout_ms: int,
    wait_timeout: int,
) -> tuple[list[dict], list[dict], dict[str, dict]]:
    """Playwright async : un navigateur, 3 contextes en parallèle."""

    async def _run() -> list[object]:
        from playwright.async_api import async_playwright

        async with async_playwright() as ap:
            browser = await ap.chromium.launch(headless=True, args=list(_CHROMIUM_LAUNCH_ARGS))
            try:

                async def capture_one(device: dict) -> dict:
                    device_type = device['type']
                    target_path = base_dir / f'{slug}.{device_type}.webp'
                    logger.info(
                        'Screenshot start mode=parallel device=%s website=%s viewport=%sx%s',
                        device_type,
                        website,
                        int(device['width']),
                        int(device['height']),
                    )
                    context = await browser.new_context(**_browser_context_kwargs(device))
                    try:
                        page = await context.new_page()
                        if WEBSITE_SCREENSHOT_BLOCK_TRACKERS:
                            await page.route('**/*', _route_abort_tracker_async)
                        await page.goto(website, wait_until=goto_wait, timeout=goto_timeout_ms)
                        if wait_timeout > 0:
                            await page.wait_for_timeout(wait_timeout)
                        shot_bytes = await _screenshot_viewport_async(page)
                    finally:
                        await context.close()
                    mw = int(device['max_width']) if device.get('max_width') else None
                    await asyncio.to_thread(
                        _save_webp_from_image_bytes,
                        shot_bytes,
                        target_path,
                        int(device['webp_quality']),
                        mw,
                    )
                    public_url = _public_url_for_file(target_path)
                    file_size = target_path.stat().st_size if target_path.exists() else 0
                    logger.info(
                        'Screenshot success mode=parallel device=%s file=%s bytes=%s public_url=%s',
                        device_type,
                        str(target_path),
                        file_size,
                        public_url or '',
                    )
                    return {
                        'device_type': device_type,
                        'file_path': str(target_path),
                        'public_url': public_url,
                        'viewport': {'width': int(device['width']), 'height': int(device['height'])},
                    }

                return await asyncio.gather(
                    *[capture_one(d) for d in devices],
                    return_exceptions=True,
                )
            finally:
                await browser.close()

    self.update_state(
        state='PROGRESS',
        meta={
            'progress': 40,
            'step': 'capture',
            'message': 'Captures desktop / tablette / mobile en parallèle...',
        },
    )

    raw = asyncio.run(_run())

    captures: list[dict] = []
    errors: list[dict] = []
    capture_by_device: dict[str, dict] = {}

    for device, result in zip(devices, raw):
        device_type = device['type']
        target_path = base_dir / f'{slug}.{device_type}.webp'
        if isinstance(result, BaseException):
            err = str(result)
            errors.append({'device_type': device_type, 'error': err})
            logger.warning('Capture %s échouée (%s): %s', device_type, website, err)
            capture_by_device[device_type] = {
                'file_path': str(target_path),
                'public_url': None,
                'error': err,
                'viewport': {'width': int(device['width']), 'height': int(device['height'])},
            }
            continue
        capture_by_device[device_type] = {
            'file_path': result['file_path'],
            'public_url': result['public_url'],
            'error': None,
            'viewport': result['viewport'],
        }
        captures.append(
            {
                'device_type': result['device_type'],
                'file_path': result['file_path'],
                'public_url': result['public_url'],
                'viewport': result['viewport'],
            }
        )

    return captures, errors, capture_by_device


@celery.task(bind=True)
def website_screenshot_task(
    self,
    url: str,
    entreprise_id: int,
    analysis_id: int | None = None,
    full_page: bool = False,
    wait_ms: int | None = None,
):
    """
    Capture 3 screenshots d'un site (desktop/tablet/mobile) et les enregistre en BDD.
    Toujours viewport uniquement (pas de full page) pour vitesse et poids disque.
    """
    # Paramètre ignoré : plus de capture pleine page.
    full_page = False

    t0 = time.monotonic()
    website = canonical_website_https_url(url)
    if not website:
        raise ValueError('URL invalide pour screenshot')

    eid = int(entreprise_id)
    aid = int(analysis_id) if analysis_id is not None else None
    wait_timeout = int(wait_ms if wait_ms is not None else WEBSITE_SCREENSHOT_WAIT_MS)
    wait_timeout = max(0, min(wait_timeout, 15000))
    goto_timeout_ms = max(8000, min(int(WEBSITE_SCREENSHOT_GOTO_TIMEOUT_MS), 120000))

    goto_wait = WEBSITE_SCREENSHOT_GOTO_WAIT_UNTIL
    if goto_wait not in ('commit', 'domcontentloaded', 'load', 'networkidle'):
        goto_wait = 'domcontentloaded'

    def _max_w(v: int) -> int | None:
        n = int(v)
        return n if n > 0 else None

    base_q = WEBSITE_SCREENSHOT_WEBP_QUALITY
    devices = [
        {
            'type': 'desktop',
            'width': WEBSITE_SCREENSHOT_VIEWPORT_DESKTOP_WIDTH,
            'height': WEBSITE_SCREENSHOT_VIEWPORT_DESKTOP_HEIGHT,
            'is_mobile': False,
            'has_touch': False,
            'max_width': _max_w(WEBSITE_SCREENSHOT_MAX_WIDTH_DESKTOP),
            'webp_quality': max(40, min(base_q, 95)),
        },
        {
            'type': 'tablet',
            'width': WEBSITE_SCREENSHOT_VIEWPORT_TABLET_WIDTH,
            'height': WEBSITE_SCREENSHOT_VIEWPORT_TABLET_HEIGHT,
            'is_mobile': True,
            'has_touch': True,
            'max_width': _max_w(WEBSITE_SCREENSHOT_MAX_WIDTH_TABLET),
            'webp_quality': max(40, min(base_q - 3, 95)),
        },
        {
            'type': 'mobile',
            'width': WEBSITE_SCREENSHOT_VIEWPORT_MOBILE_WIDTH,
            'height': WEBSITE_SCREENSHOT_VIEWPORT_MOBILE_HEIGHT,
            'is_mobile': True,
            'has_touch': True,
            'max_width': _max_w(WEBSITE_SCREENSHOT_MAX_WIDTH_MOBILE),
            'webp_quality': max(40, min(base_q - 5, 95)),
        },
    ]

    task_id = getattr(getattr(self, 'request', None), 'id', None)
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    slug = _safe_slug_from_url(website)
    base_dir = Path(WEBSITE_SCREENSHOTS_DIR) / f'entreprise_{eid}' / ts
    base_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        'Screenshot task start task_id=%s entreprise_id=%s analysis_id=%s website=%s parallel=%s wait_until=%s goto_timeout_ms=%s wait_ms=%s out_dir=%s',
        task_id,
        eid,
        aid,
        website,
        WEBSITE_SCREENSHOT_PARALLEL,
        goto_wait,
        goto_timeout_ms,
        wait_timeout,
        str(base_dir),
    )

    self.update_state(
        state='PROGRESS',
        meta={'progress': 5, 'step': 'init', 'message': 'Préparation des screenshots...'},
    )

    database = Database()
    captures: list[dict] = []
    errors: list[dict] = []
    capture_by_device: dict[str, dict] = {}

    try:
        import playwright  # noqa: F401
    except Exception as exc:
        logger.error('Playwright indisponible: %s', exc)
        raise RuntimeError(
            "Playwright n'est pas installé. Installez-le puis lancez: python -m playwright install chromium"
        ) from exc

    if WEBSITE_SCREENSHOT_PARALLEL:
        captures, errors, capture_by_device = _run_screenshots_parallel(
            self=self,
            website=website,
            devices=devices,
            base_dir=base_dir,
            slug=slug,
            goto_wait=goto_wait,
            goto_timeout_ms=goto_timeout_ms,
            wait_timeout=wait_timeout,
        )
    else:
        captures, errors, capture_by_device = _run_screenshots_sequential(
            self=self,
            website=website,
            devices=devices,
            base_dir=base_dir,
            slug=slug,
            goto_wait=goto_wait,
            goto_timeout_ms=goto_timeout_ms,
            wait_timeout=wait_timeout,
        )

    screenshot_set_id = database.save_entreprise_screenshot_set(
        entreprise_id=eid,
        analysis_id=aid,
        source_task_id=task_id,
        page_url=website,
        full_page=bool(full_page),
        desktop_file_path=(capture_by_device.get('desktop') or {}).get('file_path'),
        desktop_public_url=(capture_by_device.get('desktop') or {}).get('public_url'),
        tablet_file_path=(capture_by_device.get('tablet') or {}).get('file_path'),
        tablet_public_url=(capture_by_device.get('tablet') or {}).get('public_url'),
        mobile_file_path=(capture_by_device.get('mobile') or {}).get('file_path'),
        mobile_public_url=(capture_by_device.get('mobile') or {}).get('public_url'),
        desktop_error=(capture_by_device.get('desktop') or {}).get('error'),
        tablet_error=(capture_by_device.get('tablet') or {}).get('error'),
        mobile_error=(capture_by_device.get('mobile') or {}).get('error'),
    )
    deleted_files = _cleanup_old_screenshot_sets(
        database=database,
        entreprise_id=eid,
        keep_last=WEBSITE_SCREENSHOT_KEEP_SETS,
    )

    self.update_state(
        state='PROGRESS',
        meta={'progress': 100, 'step': 'done', 'message': 'Screenshots terminés.'},
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        'Screenshot task done task_id=%s entreprise_id=%s screenshot_set_id=%s captured=%s errors=%s deleted_files=%s elapsed_ms=%s',
        task_id,
        eid,
        screenshot_set_id,
        len(captures),
        len(errors),
        deleted_files,
        elapsed_ms,
    )
    return {
        'success': True,
        'screenshot_set_id': screenshot_set_id,
        'url': website,
        'entreprise_id': eid,
        'analysis_id': aid,
        'captures': captures,
        'errors': errors,
        'captured_count': len(captures),
        'retention_keep_sets': WEBSITE_SCREENSHOT_KEEP_SETS,
        'retention_deleted_files': deleted_files,
        'parallel_devices': WEBSITE_SCREENSHOT_PARALLEL,
        'browser_capture_format': (
            'jpeg' if WEBSITE_SCREENSHOT_CAPTURE_FORMAT in ('jpeg', 'jpg') else 'png'
        ),
        'block_trackers': WEBSITE_SCREENSHOT_BLOCK_TRACKERS,
        'device_scale_factor': WEBSITE_SCREENSHOT_DEVICE_SCALE_FACTOR,
        'elapsed_ms': elapsed_ms,
    }
