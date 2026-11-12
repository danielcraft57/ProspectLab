#!/usr/bin/env python3
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto('https://example.com', timeout=30000)
    print('title', pg.title())
    b.close()
print('OK')
