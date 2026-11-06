#!/usr/bin/env python3
"""
Liste les intents Qdrant sans reponse (catalogue ou template ProspectLab).

Usage (racine projet) :
  python scripts/facebook_prospection/list_kb_coverage.py
  python scripts/facebook_prospection/list_kb_coverage.py --json
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

if not os.environ.get('QDRANT_URL'):
    os.environ['QDRANT_URL'] = 'http://node15.lan:6333'

from services.facebook_prospection.kb_coverage import kb_coverage_report


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit Q/R KB Messenger')
    parser.add_argument('--json', action='store_true', help='Sortie JSON')
    args = parser.parse_args()
    report = kb_coverage_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print('=== Couverture Q/R tchatche ===')
    print(f"Profil        : {report.get('profile')}")
    print(f"Catalogue API : {'oui' if report.get('catalog_configured') else 'non'} ({report.get('catalog_intent_count')} intents)")
    print(f"Qdrant        : {'ok' if report.get('qdrant_ok') else 'ko'} ({report.get('qdrant_tag_count')} tags)")
    print(f"Templates PL  : {', '.join(report.get('local_template_tags') or [])}")
    print(f"Trous (Qdrant sans phrase) : {report.get('gap_count')}")
    print('')
    gaps = report.get('gaps') or []
    if not gaps:
        print('Rien a signaler : chaque tag Qdrant a un catalogue ou un template local.')
        return 0
    print('Tags a corriger (editer VocalGuard ou reply_vars.py INTENT_TEMPLATES) :')
    for row in gaps:
        print(f"  - {row.get('tag')}")
    print('')
    print('Doc : docs/guides/TCHATCHE_KB.md section Revoir les Q/R')
    return 0


if __name__ == '__main__':
    sys.exit(main())
