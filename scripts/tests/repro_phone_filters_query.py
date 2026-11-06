#!/usr/bin/env python
"""Repro requête liste entreprises avec filtres téléphone (sans charger Flask)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.database import Database  # noqa: E402


def main():
    db = Database()
    filters = {
        'no_group': 'true',
        'statut': 'Nouveau',
        'has_phone': 'true',
        'phone_line_type': 'mobile',
        'security_max': 20,
        'seo_max': 50,
        'pentest_max': 70,
    }
    try:
        items, total = db.get_entreprises(
            filters=filters,
            limit=5,
            offset=0,
            include_og=False,
            with_total=True,
        )
        print('OK total=', total, 'items=', len(items))
    except Exception as exc:
        print('ERR', type(exc).__name__, exc)
        raise


if __name__ == '__main__':
    main()
