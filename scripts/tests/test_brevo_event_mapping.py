#!/usr/bin/env python
"""
Tests unitaires : mapping Brevo + insert inbox idempotent (mocks).

Usage:
    python -m unittest scripts.tests.test_brevo_event_mapping -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.inbox_classification import map_brevo_event_to_category


class TestBrevoEventMapping(unittest.TestCase):
    """Sync Brevo sans appel reseau / DB reels."""

    def test_map_categories(self):
        """Categories bounce / proxy / blocked."""
        self.assertEqual(map_brevo_event_to_category('hardBounces'), 'bounce_hard')
        self.assertEqual(map_brevo_event_to_category('softBounces'), 'bounce_soft')
        self.assertEqual(map_brevo_event_to_category('loadedByProxy'), 'open_proxy')

    @patch('services.inbox_sync.BrevoClient', create=True)
    @patch('services.inbox_sync.CampagneManager', create=True)
    def test_sync_brevo_hardbounce_marks(self, _cm_unused, _bc_unused):
        """hardBounces appelle mark_latest_email_bounced_for_recipient."""
        from services import inbox_sync

        cm = MagicMock()
        cm.insert_inbox_event_if_new.return_value = True
        cm.mark_latest_email_bounced_for_recipient.return_value = 42

        client = MagicMock()
        client.get_blocked_contacts.return_value = {'data': {'contacts': []}}
        client.get_recent_smtp_events.return_value = {
            'data': {
                'events': [
                    {
                        'event': 'hardBounces',
                        'email': 'rh.fr@eni.com',
                        'messageId': '<abc>',
                        'date': '2026-08-16T08:00:00+02:00',
                        'reason': '550 Access denied',
                        'subject': 'Test',
                    }
                ]
            }
        }

        with patch.object(inbox_sync, 'BrevoClient', return_value=client, create=True):
            with patch('services.database.campagnes.CampagneManager', return_value=cm):
                with patch('services.brevo_client.BrevoClient', return_value=client):
                    summary = inbox_sync.sync_brevo_events(limit=10)

        self.assertGreaterEqual(summary.get('inserted', 0), 1)
        self.assertGreaterEqual(summary.get('bounced', 0), 1)
        cm.mark_latest_email_bounced_for_recipient.assert_called()
        # Idempotence : second insert ignore
        cm.insert_inbox_event_if_new.return_value = False
        with patch('services.database.campagnes.CampagneManager', return_value=cm):
            with patch('services.brevo_client.BrevoClient', return_value=client):
                summary2 = inbox_sync.sync_brevo_events(limit=10)
        self.assertGreaterEqual(summary2.get('skipped', 0), 1)


if __name__ == '__main__':
    unittest.main()
