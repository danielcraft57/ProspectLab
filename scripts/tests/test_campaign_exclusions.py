#!/usr/bin/env python
"""
Tests unitaires : exclusions campagne (désabonné, bounce).

Usage:
    python -m unittest scripts.tests.test_campaign_exclusions -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.campaign_exclusions import (
    entreprise_statut_excluded,
    entreprise_tags_excluded,
    is_recipient_excluded,
    split_recipients_for_rotation,
)
from utils.campaign_recipients import filter_campagne_recipients


class TestCampaignExclusions(unittest.TestCase):
    """Règles métier désabonnement / bounce."""

    def test_statut_desabonne_excluded(self):
        self.assertTrue(entreprise_statut_excluded('Désabonné'))
        self.assertTrue(entreprise_statut_excluded('Bounce'))
        self.assertFalse(entreprise_statut_excluded('Actif'))

    def test_tags_bounce_excluded(self):
        self.assertTrue(entreprise_tags_excluded('["bounce"]'))
        self.assertTrue(entreprise_tags_excluded('["desabonne"]'))
        self.assertFalse(entreprise_tags_excluded('["formation"]'))

    def test_is_recipient_excluded_entreprise(self):
        excluded, reason = is_recipient_excluded(
            {'email': 'a@acme.fr', 'entreprise_id': 5},
            excluded_entreprise_ids={5},
            bounced_emails=set(),
        )
        self.assertTrue(excluded)
        self.assertEqual(reason, 'unsub_or_bounce_entreprise')

    def test_is_recipient_excluded_bounced_email(self):
        excluded, reason = is_recipient_excluded(
            {'email': 'bounce@acme.fr', 'entreprise_id': 9},
            excluded_entreprise_ids=set(),
            bounced_emails={'bounce@acme.fr'},
        )
        self.assertTrue(excluded)
        self.assertEqual(reason, 'bounce_email')

    def test_split_recipients_rotation(self):
        recipients = [{'email': f'u{i}@x.fr', 'entreprise_id': i} for i in range(5)]
        chunks = split_recipients_for_rotation(recipients, 3)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(sum(len(c) for c in chunks), 5)

    @patch('utils.campaign_recipients.load_campaign_exclusion_data')
    def test_filter_drops_unreachable(self, mock_load):
        mock_load.return_value = {
            'excluded_entreprise_ids': {2},
            'bounced_emails': {'old@bounce.fr'},
        }
        recipients = [
            {'email': 'ok@acme.fr', 'entreprise_id': 1},
            {'email': 'des@firm.fr', 'entreprise_id': 2},
            {'email': 'old@bounce.fr', 'entreprise_id': 3},
        ]
        out, stats = filter_campagne_recipients(
            recipients,
            exclude_risky=False,
            max_emails_per_entreprise=0,
            exclude_unreachable=True,
        )
        emails = {r['email'] for r in out}
        self.assertEqual(emails, {'ok@acme.fr'})
        self.assertEqual(stats['dropped_unreachable'], 2)


if __name__ == '__main__':
    unittest.main()
