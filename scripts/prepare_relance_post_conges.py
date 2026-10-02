#!/usr/bin/env python3
"""
Liste les leads chauds post-campagnes DC (opens/clicks non suspects) et
prepare une campagne programmee (dry-run par defaut).

Usage:
  python scripts/prepare_relance_post_conges.py
  python scripts/prepare_relance_post_conges.py --campagne-ids 111,112
  python scripts/prepare_relance_post_conges.py --create --scheduled-at 2026-09-01T08:00:00+02:00
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.database import Database  # noqa: E402
from services.database.campagnes import CampagneManager  # noqa: E402
from utils.campaign_recipients import filter_campagne_recipients  # noqa: E402
from utils.tracking_suspect import event_data_is_suspect  # noqa: E402

# Leads manuels du rapport 111 (a prioriser)
PRIORITY_EMAILS = {
    'boisdelorraine@orange.fr',
    'contact@inova-web.fr',
    'murielle@mgi.lu',
    'info@mgi.lu',
    'fontainesandro@gmail.com',
    'contact@titelive.com',
}

EXCLUDE_ENTREPRISE_MARKERS = (
    'lycée', 'lycee', 'athénée', 'athenee', 'éducation', 'education',
    'préfecture', 'prefecture', 'département', 'departement', 'gouv',
    'cgie', 'intesa', 'banque', 'bank', 'fdc55', 'fédération', 'federation',
    'communauté', 'communaute', 'agglomération', 'agglomeration',
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Prepare relance post-conges.')
    p.add_argument('--campagne-ids', type=str, default='111,112', help='IDs CSV campagnes source')
    p.add_argument('--template-id', type=str, default='html_dc_relance', help='Template relance')
    p.add_argument('--sujet', type=str, default='Petit rappel — {entreprise}', help='Sujet template')
    p.add_argument(
        '--scheduled-at',
        type=str,
        default='2026-09-01T08:00:00+02:00',
        help='ISO datetime programmation (Europe/Paris ok avec offset)',
    )
    p.add_argument('--create', action='store_true', help='Cree la campagne programmee en BDD')
    p.add_argument('--limit', type=int, default=40, help='Max destinataires')
    return p.parse_args()


def _load_engaged(db: Database, campagne_ids: List[int]) -> List[Dict[str, Any]]:
    """Charge les emails engages (open/click) hors events suspects."""
    if not campagne_ids:
        return []
    conn = db.get_connection()
    cur = conn.cursor()
    placeholders = ','.join(['?'] * len(campagne_ids))
    db.execute_sql(
        cur,
        f'''
        SELECT ee.id, ee.email, ee.nom_destinataire, ee.entreprise, ee.entreprise_id, ee.campagne_id,
               et.event_type, et.event_data
        FROM emails_envoyes ee
        JOIN email_tracking_events et ON et.email_id = ee.id
        WHERE ee.campagne_id IN ({placeholders})
          AND ee.statut = 'sent'
          AND et.event_type IN ('open', 'click')
        ORDER BY ee.id DESC
        ''',
        tuple(campagne_ids),
    )
    rows = [dict(r) for r in (cur.fetchall() or [])]
    conn.close()

    by_email: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if event_data_is_suspect(r.get('event_data')):
            continue
        email = (r.get('email') or '').strip().lower()
        if not email:
            continue
        cur_rec = by_email.get(email)
        score = 2 if r.get('event_type') == 'click' else 1
        if email in PRIORITY_EMAILS:
            score += 5
        if not cur_rec or score > cur_rec.get('_score', 0):
            by_email[email] = {
                'email': r.get('email'),
                'nom': r.get('nom_destinataire') or '',
                'entreprise': r.get('entreprise') or '',
                'entreprise_id': r.get('entreprise_id'),
                '_score': score,
                '_from_campagne': r.get('campagne_id'),
            }
    # Prioriser aussi les emails manuels meme sans tracking
    for pe in PRIORITY_EMAILS:
        if pe not in by_email:
            by_email[pe] = {
                'email': pe,
                'nom': '',
                'entreprise': '',
                'entreprise_id': None,
                '_score': 5,
                '_from_campagne': None,
            }
    ordered = sorted(by_email.values(), key=lambda x: (-x.get('_score', 0), x.get('email') or ''))
    return ordered


def main() -> int:
    args = parse_args()
    campagne_ids = [int(x.strip()) for x in (args.campagne_ids or '').split(',') if x.strip().isdigit()]
    db = Database()
    engaged = _load_engaged(db, campagne_ids)
    recipients_raw = []
    for r in engaged:
        ent = (r.get('entreprise') or '').lower()
        if any(m in ent for m in EXCLUDE_ENTREPRISE_MARKERS):
            continue
        recipients_raw.append(
            {
                'email': r['email'],
                'nom': r.get('nom') or '',
                'entreprise': r.get('entreprise') or '',
                'entreprise_id': r.get('entreprise_id'),
            }
        )
    recipients, stats = filter_campagne_recipients(
        recipients_raw,
        exclude_risky=True,
        max_emails_per_entreprise=1,
    )
    if args.limit and args.limit > 0:
        recipients = recipients[: int(args.limit)]

    print('=== LEADS ===')
    for r in recipients:
        src = next((e for e in engaged if (e.get('email') or '').lower() == (r.get('email') or '').lower()), {})
        print(
            f"{r.get('email')} | {r.get('entreprise')} | score={src.get('_score')} | from={src.get('_from_campagne')}"
        )
    print('=== FILTER ===', stats, 'final', len(recipients))

    if not args.create:
        print('Dry-run. Relancer avec --create pour programmer la campagne.')
        return 0

    if not recipients:
        print('Aucun destinataire, abort.')
        return 1

    # Normaliser scheduled_at en UTC Z pour create_campagne scheduled
    raw = args.scheduled_at.strip()
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            from datetime import timezone as tz

            dt = dt.replace(tzinfo=tz.utc)
        scheduled_at_str = dt.astimezone(__import__('datetime').timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%S.000Z'
        )
    except Exception as e:
        print('scheduled-at invalide:', e)
        return 1

    cm = CampagneManager()
    params = {
        'recipients': recipients,
        'template_id': args.template_id,
        'subject': args.sujet,
        'custom_message': None,
        'delay': 2,
        'mail_account_id': None,
    }
    nom = f'Relance post-conges ({len(recipients)})'
    cid = cm.create_campagne(
        nom=nom,
        template_id=args.template_id,
        sujet=args.sujet,
        total_destinataires=len(recipients),
        statut='scheduled',
        scheduled_at=scheduled_at_str,
        campaign_params_json=json.dumps(params, ensure_ascii=False),
    )
    print(f'Campagne programmee id={cid} at={scheduled_at_str} recipients={len(recipients)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
