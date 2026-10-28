#!/usr/bin/env python3
"""
Indexe les intents FAQ ProspectLab dans Qdrant (collection prospectlab_facebook_messaging).

Usage :
  python scripts/facebook_prospection/seed_qdrant_collection.py
  python scripts/facebook_prospection/seed_qdrant_collection.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.facebook_prospection.qdrant import FacebookProspectionQdrant


def embed_text(text: str, dims: int) -> list[float]:
    """
    Embedding Gemini text-embedding-004 (768d par defaut).

    @param text: Texte a vectoriser
    @param dims: Dimension attendue
    @returns: Vecteur float
    @raises RuntimeError: Si GEMINI_API_KEY manquant ou API en echec
    """
    import requests

    api_key = (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or '').strip()
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY ou GOOGLE_API_KEY requis pour --apply')
    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        'text-embedding-004:embedContent?key=' + api_key
    )
    resp = requests.post(
        url,
        json={'content': {'parts': [{'text': text[:6000]}]}},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'Gemini embed HTTP {resp.status_code}: {resp.text[:200]}')
    values = (resp.json().get('embedding') or {}).get('values') or []
    if len(values) < dims:
        raise RuntimeError(f'vecteur trop court ({len(values)}/{dims})')
    return [float(x) for x in values[:dims]]


def main() -> int:
    parser = argparse.ArgumentParser(description='Seed Qdrant Facebook prospection')
    parser.add_argument('--apply', action='store_true', help='Ecrit dans Qdrant (sinon dry-run)')
    parser.add_argument(
        '--seed',
        default=str(ROOT / 'data' / 'facebook_prospection' / 'qdrant_seed_faq.json'),
    )
    args = parser.parse_args()

    seed_path = Path(args.seed)
    data = json.loads(seed_path.read_text(encoding='utf-8'))
    brand_id = data.get('brand_id') or 'danielcraft'
    store = FacebookProspectionQdrant(brand_id=brand_id)
    if not store.enabled():
        print('QDRANT_URL non configure — rien a faire.')
        return 1

    if args.apply:
        store.ensure_collection()

    points = 0
    for intent in data.get('intents') or []:
        intent_id = intent['intent_id']
        definition = intent.get('definition') or ''
        for example in intent.get('examples') or []:
            points += 1
            if args.apply:
                vec = embed_text(example, store.dims)
                store.upsert_point(
                    'intent_example',
                    f'{intent_id}::ex::{example[:40]}',
                    example,
                    vec,
                    {'intent_id': intent_id},
                )
        for reply in intent.get('replies') or []:
            points += 1
            if args.apply:
                vec = embed_text(reply, store.dims)
                store.upsert_point(
                    'intent_reply',
                    f'{intent_id}::rep::{reply[:40]}',
                    reply,
                    vec,
                    {'intent_id': intent_id},
                )
        points += 1
        if args.apply and definition:
            vec = embed_text(definition, store.dims)
            store.upsert_point(
                'intent_def',
                f'{intent_id}::def',
                definition,
                vec,
                {'intent_id': intent_id},
            )

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'{mode}: {points} points prepares depuis {seed_path.name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
