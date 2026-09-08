#!/usr/bin/env python
"""
Tests unitaires : classification IMAP / mapping Brevo.

Usage:
    python -m unittest scripts.tests.test_inbox_classification -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.inbox_classification import classify_imap_reply, map_brevo_event_to_category


class TestInboxClassification(unittest.TestCase):
    """Regles deterministes OOO / ticket / noise / human."""

    def test_ooo(self):
        """Absences automatiques."""
        self.assertEqual(
            classify_imap_reply(subject='Automatic reply: Hello', preview='I am away'),
            'auto_ooo',
        )
        self.assertEqual(
            classify_imap_reply(subject='Re: test', preview='Je suis absente du bureau'),
            'auto_ooo',
        )

    def test_ticket(self):
        """Tickets helpdesk / ePagine."""
        self.assertEqual(
            classify_imap_reply(
                subject='Votre demande d assistance',
                preview='Ticket n 159423 epagine',
                from_addr='support@epagine.fr',
            ),
            'ticket_auto',
        )

    def test_noise(self):
        """Notifications systeme."""
        self.assertEqual(
            classify_imap_reply(
                subject='Run failed: CD Node15',
                from_addr='notifications@github.com',
            ),
            'noise',
        )

    def test_human_reply(self):
        """Reponse humaine campagne."""
        self.assertEqual(
            classify_imap_reply(
                subject='Re: Sécu : ton site',
                preview='Bonjour, on peut en parler',
                from_addr='marie@acme.fr',
                looks_like_campaign_reply=True,
            ),
            'human_reply',
        )

    def test_brevo_mapping(self):
        """Mapping events Brevo."""
        self.assertEqual(map_brevo_event_to_category('hardBounces'), 'bounce_hard')
        self.assertEqual(map_brevo_event_to_category('loadedByProxy'), 'open_proxy')
        self.assertEqual(map_brevo_event_to_category('blocked'), 'blocked')
        self.assertIsNone(map_brevo_event_to_category('delivered'))


if __name__ == '__main__':
    unittest.main()
