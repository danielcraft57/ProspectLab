#!/usr/bin/env python3
"""Probe rapide des cles Gemini (masquees). Usage: python scripts/probe_gemini_keys.py"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except Exception:
    pass

from services.gemini_client import BASE_URL, gemini_config, get_gemini_api_keys
import requests


def main() -> int:
    """
    Teste chaque cle Gemini avec un appel generateContent minimal.

    @returns: 0 si au moins une cle OK, 1 sinon
    """
    keys = get_gemini_api_keys()
    cfg = gemini_config()
    model = cfg.get('model') or 'gemini-3.8-flash'
    print(f'cles_chargees={len(keys)} model={model}')
    if not keys:
        print('Aucune cle trouvee')
        return 1

    url = f'{BASE_URL}/models/{model}:generateContent'
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': 'Reponds uniquement: OK'}]}],
        'generationConfig': {'maxOutputTokens': 16, 'temperature': 0},
    }

    ok_count = 0
    for i, key in enumerate(keys, 1):
        masked = f'{key[:6]}...{key[-4:]}' if len(key) > 12 else '***'
        t0 = time.time()
        try:
            r = requests.post(url, params={'key': key}, json=payload, timeout=45)
            ms = int((time.time() - t0) * 1000)
            body = (r.text or '')[:180].replace('\n', ' ')
            status = r.status_code
            if status == 200:
                ok_count += 1
                print(f'KEY_{i} {masked} OK {ms}ms')
                continue
            low = body.lower()
            kind = 'ERR'
            if status == 401 or 'api_key_invalid' in low:
                kind = 'INVALID'
            elif status == 429:
                kind = 'QUOTA_429'
            elif status == 503 or 'high demand' in low or 'unavailable' in low:
                kind = 'OVERLOAD_503'
            elif status == 403:
                kind = 'FORBIDDEN_403'
            print(f'KEY_{i} {masked} {kind} http={status} {ms}ms body={body}')
        except Exception as exc:
            ms = int((time.time() - t0) * 1000)
            print(f'KEY_{i} {masked} EXCEPTION {ms}ms {type(exc).__name__}: {exc}')

    print(f'resume ok={ok_count}/{len(keys)}')
    return 0 if ok_count else 1


if __name__ == '__main__':
    raise SystemExit(main())
