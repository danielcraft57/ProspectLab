#!/usr/bin/env python
# Exécution : conda run -n prospectlab python scripts/tests/test_entreprise_phone_filters.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.database.entreprises import EntrepriseManager  # noqa: E402


def test_has_phone_sql_fragment():
    """Le prédicat has_phone couvre le téléphone principal et scraper_phones."""
    sql = EntrepriseManager._has_phone_sql_fragment()
    assert 'e.telephone' in sql
    assert 'scraper_phones' in sql


def test_mobile_sql_uses_line_type_and_heuristic():
    """Filtre portable : line_type OSINT ou heuristique FR."""
    sql = EntrepriseManager._sql_entreprise_has_mobile_phone()
    assert 'MOBILE' in sql
    assert 'FIXED_LINE_OR_MOBILE' in sql
    assert '336%%' in sql or '06%%' in sql


def test_fixed_sql_excludes_mobile_heuristic():
    """Filtre fixe : types FIXED_LINE et exclusion heuristique mobile."""
    sql = EntrepriseManager._sql_entreprise_has_fixed_phone()
    assert 'FIXED_LINE' in sql
    assert 'NOT' in sql.upper()


if __name__ == '__main__':
    test_has_phone_sql_fragment()
    test_mobile_sql_uses_line_type_and_heuristic()
    test_fixed_sql_excludes_mobile_heuristic()
    print('OK test_entreprise_phone_filters')
