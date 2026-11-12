#!/usr/bin/env python3
"""Mini test Playwright (meme binaire que screenshot_tasks) pour diagnostic Pi."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from tasks.screenshot_tasks import _chromium_launch_kwargs, _resolve_chromium_executable


def main() -> int:
    exe = _resolve_chromium_executable()
    kw = _chromium_launch_kwargs()
    print('executable:', exe)
    print('launch kwargs keys:', sorted(kw.keys()))
    with sync_playwright() as p:
        browser = p.chromium.launch(**kw)
        page = browser.new_page()
        page.goto('https://example.com', timeout=30_000)
        print('title:', page.title())
        browser.close()
    print('OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
