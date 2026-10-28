#!/usr/bin/env python3
"""
Indexe le catalogue intents (patterns + reponses) dans Qdrant node15.

Utile quand l'API catalogue n'indexe pas Qdrant : les nouveaux intents existent
en base mais pas dans intents_outbound_commercial.

Usage :
  python scripts/facebook_prospection/sync_vocalguard_qdrant.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if not os.environ.get('QDRANT_URL'):
    os.environ['QDRANT_URL'] = 'http://node15.lan:6333'

from config import VOCALGUARD_KB_PROFILE
from services.facebook_prospection.qdrant import FacebookProspectionQdrant
from services.facebook_prospection.vocalguard_client import list_intents
from services.facebook_prospection.vocalguard_embed import embed_text


def _texts(intent: dict, key: str) -> list[str]:
    """
    Extraie les chaines d'un intent (patterns ou responses).

    @param intent: Intent VocalGuard
    @param key: patterns | responses
    @returns: Textes non vides
    """
    out: list[str] = []
    for item in intent.get(key) or []:
        if isinstance(item, str):
            txt = item.strip()
        elif isinstance(item, dict):
            txt = str(item.get('text') or item.get('pattern') or '').strip()
        else:
            txt = ''
        if txt:
            out.append(txt)
    return out


def main() -> int:
    profile = VOCALGUARD_KB_PROFILE or 'outbound_commercial'
    intents = list_intents(profile=profile)
    if not intents:
        print('Aucun intent dans le catalogue (URL API catalogue dans .env ?)')
        return 1
    store = FacebookProspectionQdrant(profile=profile)
    if not store.enabled():
        print('QDRANT_URL manquant')
        return 1
    n = 0
    for intent in intents:
        tag = str(intent.get('tag') or '').strip()
        if not tag:
            continue
        for pattern in _texts(intent, 'patterns'):
            store.upsert_intent_text(tag, 'pattern', pattern, embed_text(pattern, dim=store.dims))
            n += 1
        for response in _texts(intent, 'responses'):
            store.upsert_intent_text(tag, 'response', response, embed_text(response, dim=store.dims))
            n += 1
        print('ok', tag)
    print(f'{n} points upsertes dans {store.collection}')
    print(store.collection_info())
    return 0


if __name__ == '__main__':
    sys.exit(main())
