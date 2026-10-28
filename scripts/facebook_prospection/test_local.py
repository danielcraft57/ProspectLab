#!/usr/bin/env python3
"""
Test recherche Facebook en local (RUNNER=local, session SocialDesk).

  python scripts/facebook_prospection/test_local.py "Boulangerie Metz"
  python scripts/facebook_prospection/test_local.py --entreprise-id 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.database import Database
from services.facebook_prospection.job_runner import FacebookProspectionJobRunner
from services.facebook_prospection.paths_config import storage_state_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Test recherche Facebook locale')
    parser.add_argument('query', nargs='?', default='', help='Requete de recherche')
    parser.add_argument('--entreprise-id', type=int, default=0)
    args = parser.parse_args()

    query = (args.query or '').strip()
    target = None
    if args.entreprise_id:
        db = Database()
        ent = db.get_entreprise(args.entreprise_id)
        if not ent:
            print('Entreprise introuvable', file=sys.stderr)
            return 1
        target = (ent.get('nom') or ent.get('name') or '').strip()
        query = query or target

    if not query:
        parser.print_help()
        return 1

    print('Session:', storage_state_path())
    out = FacebookProspectionJobRunner().run('search', {'query': query, 'target_name': target})
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get('ok') else 2


if __name__ == '__main__':
    sys.exit(main())
