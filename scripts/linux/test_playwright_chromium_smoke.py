#!/usr/bin/env python3
"""Smoke test Chromium Playwright (ARM: evite headless_shell)."""
from __future__ import annotations

from playwright.sync_api import sync_playwright

from tasks.screenshot_tasks import _chromium_launch_kwargs


def main() -> None:
    kw = _chromium_launch_kwargs()
    print('executable_path:', kw.get('executable_path'))
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(**kw)
        ctx = browser.new_context(viewport={'width': 800, 'height': 600})
        page = ctx.new_page()
        page.goto('about:blank', timeout=15000)
        ctx.close()
        browser.close()
        print('OK')
    finally:
        pw.stop()


if __name__ == '__main__':
    main()
