#!/usr/bin/env python
"""
Tests unitaires pour la normalisation d'URL / recherche entreprise par site.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.url_utils import canonical_website_https_url, website_lookup_candidates


class TestWebsiteLookupCandidates(unittest.TestCase):
    """Vérifie que les variantes couvrent les formes stockées en base (slash final, www)."""

    def test_trailing_slash_in_candidates(self):
        """Les URLs canoniques sans slash doivent matcher les fiches avec slash final."""
        url = 'https://leolagrange-crecheleslucioles.org/'
        candidates = website_lookup_candidates(url)
        self.assertIn('https://leolagrange-crecheleslucioles.org/', candidates)
        self.assertIn('https://leolagrange-crecheleslucioles.org', candidates)

    def test_canonical_without_trailing_slash(self):
        self.assertEqual(
            canonical_website_https_url('https://www.Example.fr/path'),
            'https://example.fr',
        )

    def test_domain_only_input(self):
        candidates = website_lookup_candidates('danielcraft.fr')
        self.assertIn('https://danielcraft.fr/', candidates)
        self.assertIn('danielcraft.fr', candidates)


class TestFindDuplicateEntrepriseWebsite(unittest.TestCase):
    """Smoke test SQLite : recherche par site avec slash final en base."""

    def setUp(self):
        os.environ['DATABASE_URL'] = ''
        os.environ['USE_SQLITE'] = '1'
        from services.database import Database

        self.db = Database()
        conn = self.db.get_connection()
        cur = conn.cursor()
        self.db.execute_sql(
            cur,
            '''
            INSERT INTO entreprises (nom, website, statut)
            VALUES (?, ?, ?)
            ''',
            ('Crèche test', 'https://leolagrange-crecheleslucioles.org/', 'Nouveau'),
        )
        conn.commit()
        conn.close()

    def test_find_by_canonical_url_without_slash(self):
        canonical = canonical_website_https_url('https://leolagrange-crecheleslucioles.org/')
        found = self.db.find_duplicate_entreprise(nom='', website=canonical)
        self.assertIsNotNone(found)


if __name__ == '__main__':
    unittest.main()
