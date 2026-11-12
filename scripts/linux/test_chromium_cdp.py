#!/usr/bin/env python3
"""Lance Chromium systeme (CDP) puis Playwright connect_over_cdp — contourne l'ecart de version."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from tasks.screenshot_tasks import _CHROMIUM_LAUNCH_ARGS, _resolve_chromium_executable


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return int(s.getsockname()[1])


def main() -> int:
    exe = _resolve_chromium_executable() or '/usr/lib/chromium/chromium'
    port = _free_port()
    args = [
        exe,
        '--headless=new',
        f'--remote-debugging-port={port}',
        '--remote-debugging-address=127.0.0.1',
        *list(_CHROMIUM_LAUNCH_ARGS),
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.time() + 25.0
        while time.time() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.3):
                    break
            except OSError:
                if proc.poll() is not None:
                    err = (proc.stderr.read() if proc.stderr else '')[:4000]
                    print('chromium exit', proc.returncode, err)
                    return 1
                time.sleep(0.2)
        else:
            print('timeout waiting CDP port', port)
            return 1
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            page.goto('https://example.com', timeout=30_000)
            print('title:', page.title())
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print('OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
