#!/usr/bin/env python3
"""
Probe la collection Qdrant KB Messenger (intents_outbound_commercial).

Usage :
  python scripts/facebook_prospection/seed_qdrant_collection.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.facebook_prospection.qdrant import FacebookProspectionQdrant


def main() -> int:
    store = FacebookProspectionQdrant()
    if not store.enabled():
        print('QDRANT_URL non configure — rien a faire.')
        return 1
    info = store.collection_info()
    print(json.dumps(info, ensure_ascii=False, indent=2))
    if not info.get('ok'):
        print(
            'Collection absente ou Qdrant KO. Verifie node15:6333 et '
            'FACEBOOK_PROSPECTION_QDRANT_COLLECTION (doc TCHATCHE_KB.md).'
        )
        return 2
    print('OK — utilise cette collection pour le tchatche / suggestions Messenger.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
