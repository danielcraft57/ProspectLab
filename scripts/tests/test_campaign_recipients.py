#!/usr/bin/env python
"""
Tests unitaires : filtrage destinataires campagne (serveur).

Usage:
    python -m unittest scripts.tests.test_campaign_recipients -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.campaign_recipients import filter_campagne_recipients


class TestCampaignRecipients(unittest.TestCase):
    """Filet serveur exclude risky + plafond."""

    def test_drops_risky_and_caps(self):
        """Gouv / support exclus, max 2 par entreprise."""
        recipients = [
            {'email': 'a@meuse.gouv.fr', 'entreprise_id': 1, 'entreprise': 'Pref'},
            {'email': 'ok1@acme.fr', 'entreprise_id': 2, 'entreprise': 'Acme', 'is_principal': True},
            {'email': 'ok2@acme.fr', 'entreprise_id': 2, 'entreprise': 'Acme', 'is_person': True},
            {'email': 'ok3@acme.fr', 'entreprise_id': 2, 'entreprise': 'Acme'},
            {'email': 'helpdesk@cgie.lu', 'entreprise_id': 3, 'entreprise': 'CGIE'},
            {'email': 'solo@boutique.fr', 'entreprise_id': 4, 'entreprise': 'Boutique'},
        ]
        out, stats = filter_campagne_recipients(recipients, exclude_risky=True, max_emails_per_entreprise=2)
        emails = {(r.get('email') or '').lower() for r in out}
        self.assertNotIn('a@meuse.gouv.fr', emails)
        self.assertNotIn('helpdesk@cgie.lu', emails)
        self.assertIn('ok1@acme.fr', emails)
        self.assertIn('ok2@acme.fr', emails)
        self.assertNotIn('ok3@acme.fr', emails)
        self.assertIn('solo@boutique.fr', emails)
        self.assertEqual(stats['output'], 3)
        self.assertGreaterEqual(stats['dropped_risky'], 2)
        self.assertEqual(stats['dropped_cap'], 1)


if __name__ == '__main__':
    unittest.main()
