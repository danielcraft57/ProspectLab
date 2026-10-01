#!/usr/bin/env python3
"""
Répare les URLs dans emails_envoyes :
- TLD tronqués ``*.f`` → ``*.fr``
- query ``website=http://`` → ``https://`` (formes plain / encodées)

Usage (prod)::

    cd /opt/prospectlab
    /opt/prospectlab/env/bin/python scripts/linux/repair_truncated_tracking_urls.py
    /opt/prospectlab/env/bin/python scripts/linux/repair_truncated_tracking_urls.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

env_path = ROOT / '.env'
if env_path.is_file():
    for raw in env_path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        key, val = line.split('=', 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

from config import repair_truncated_danielcraft_urls  # noqa: E402
import psycopg2  # noqa: E402


def _repair_website_schemes_in_html(html: str) -> str:
    """
    Remonte http → https dans les query website= (formes plain et encodées).

    @param html: Contenu email stocké
    @returns: HTML avec schémas website normalisés
    """
    if not html:
        return html
    out = html
    replacements = (
        ('website=http%3A%2F%2F', 'website=https%3A%2F%2F'),
        ('website=http%253A%252F%252F', 'website=https%253A%252F%252F'),
        ('website%3Dhttp%253A%252F%252F', 'website%3Dhttps%253A%252F%252F'),
        ('website%3Dhttp%3A%2F%2F', 'website%3Dhttps%3A%2F%2F'),
        ('website=http://', 'website=https://'),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def main() -> int:
    """
    Scan / corrige ``contenu_envoye`` (TLD .f + website=http).

    @returns: Code retour shell (0 ok)
    """
    parser = argparse.ArgumentParser(
        description='Répare URLs tronquées / http dans emails_envoyes'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Écrit les corrections en base (sinon dry-run)',
    )
    args = parser.parse_args()

    db_url = (os.environ.get('DATABASE_URL') or '').strip()
    if not db_url:
        print('DATABASE_URL manquant', file=sys.stderr)
        return 1

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, contenu_envoye
        FROM emails_envoyes
        WHERE contenu_envoye IS NOT NULL
          AND (
            contenu_envoye ~ '\\.f([^r]|$)'
            OR contenu_envoye ILIKE '%website=http%'
            OR contenu_envoye ILIKE '%website%3Dhttp%'
          )
        ORDER BY id
        """
    )
    rows = cur.fetchall()
    print(f'Candidats: {len(rows)}')

    updated = 0
    for email_id, html in rows:
        original = html or ''
        fixed = repair_truncated_danielcraft_urls(original)
        fixed = _repair_website_schemes_in_html(fixed)
        if fixed == original:
            continue
        updated += 1
        if args.apply:
            cur.execute(
                'UPDATE emails_envoyes SET contenu_envoye = %s WHERE id = %s',
                (fixed, email_id),
            )
        if updated <= 5:
            print(f'  id={email_id} réparé')

    if args.apply:
        conn.commit()
        print(f'Appliqué: {updated} mails mis à jour')
    else:
        print(f'Dry-run: {updated} mails seraient mis à jour (relancer avec --apply)')

    cur.close()
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
