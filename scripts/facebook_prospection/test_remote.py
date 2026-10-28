#!/usr/bin/env python3
"""
Test jobs Facebook sur serv1 via SSH (depuis PC ou node15).

Exemples :
  python scripts/facebook_prospection/test_remote.py search "boulangerie metz"
  python scripts/facebook_prospection/test_remote.py prospect --entreprise-id 40
  python scripts/facebook_prospection/test_remote.py prospect --query "Hotel des Ventes de Metz" --address-hint "43 Rue Dupont des Loges, 57000 Metz"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (
    FACEBOOK_PROSPECTION_REMOTE_HEADLESS,
    FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH,
)
from services.database import Database
from services.facebook_prospection.entreprise_payload import build_prospect_payload_from_entreprise
from services.facebook_prospection.job_runner import FacebookProspectionJobRunner


def _run(job_type: str, payload: dict) -> int:
    print(f'Hote: {FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH} | job={job_type}')
    print('Chrome sur serv1 (RDP) si headless=false.')
    out = FacebookProspectionJobRunner().run(job_type, payload, force_remote=True)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get('ok') else 2


def cmd_search(args: argparse.Namespace) -> int:
    payload = {
        'query': args.query.strip(),
        'target_name': (args.target_name or '').strip() or None,
        'address_hint': (args.address_hint or '').strip() or None,
        'headless': True if args.headless else FACEBOOK_PROSPECTION_REMOTE_HEADLESS,
    }
    return _run('search', payload)


def cmd_prospect(args: argparse.Namespace) -> int:
    headless = True if args.headless else FACEBOOK_PROSPECTION_REMOTE_HEADLESS
    if args.entreprise_id:
        ent = Database().get_entreprise(int(args.entreprise_id))
        if not ent:
            print('Entreprise introuvable', file=sys.stderr)
            return 1
        payload = build_prospect_payload_from_entreprise(
            ent,
            send=bool(args.send),
            headless=headless,
        )
    else:
        q = (args.query or '').strip()
        if not q:
            print('--query ou --entreprise-id requis', file=sys.stderr)
            return 1
        payload = {
            'query': q,
            'target_name': q,
            'address_hint': (args.address_hint or '').strip(),
            'message_text': (args.message_text or '').strip()
            or 'Bonjour, test ProspectLab prospect_flow (dry-run).',
            'send': bool(args.send),
            'headless': headless,
        }
    return _run('prospect_flow', payload)


def main() -> int:
    parser = argparse.ArgumentParser(description='Test Facebook Playwright sur serv1 (SSH)')
    sub = parser.add_subparsers(dest='command', required=True)

    p_search = sub.add_parser('search', help='Recherche pages FB')
    p_search.add_argument('query', help='Texte de recherche')
    p_search.add_argument('--target-name', default='')
    p_search.add_argument('--address-hint', default='')
    p_search.add_argument('--headless', action='store_true')
    p_search.set_defaults(func=cmd_search)

    p_prospect = sub.add_parser('prospect', help='Flux prospect_flow')
    p_prospect.add_argument('--entreprise-id', type=int, default=0)
    p_prospect.add_argument('--query', default='')
    p_prospect.add_argument('--address-hint', default='')
    p_prospect.add_argument('--message-text', default='')
    p_prospect.add_argument('--send', action='store_true')
    p_prospect.add_argument('--headless', action='store_true')
    p_prospect.set_defaults(func=cmd_prospect)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == '__main__':
    sys.exit(main())
