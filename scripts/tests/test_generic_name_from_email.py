#!/usr/bin/env python3
"""Tests : ne pas dériver un prénom depuis contact@ / info@."""

from __future__ import annotations

import unittest

from services.email_analyzer import EmailAnalyzer
from utils.name_formatter import (
    format_name,
    is_generic_display_name,
    is_generic_email_for_name,
)


class TestGenericNameFromEmail(unittest.TestCase):
    """Couvre extraction + filtre d'affichage."""

    def test_generic_email_detected(self):
        self.assertTrue(is_generic_email_for_name('contact@vitallsecurite.fr'))
        self.assertTrue(is_generic_email_for_name('info@exemple.fr'))
        self.assertTrue(is_generic_email_for_name('SUPPORT@exemple.fr'))
        self.assertFalse(is_generic_email_for_name('jean.dupont@exemple.fr'))

    def test_generic_display_name(self):
        self.assertTrue(is_generic_display_name('Contact'))
        self.assertTrue(is_generic_display_name('info@domaine.fr'))
        self.assertTrue(is_generic_display_name('Monsieur/Madame'))
        self.assertFalse(is_generic_display_name('Jean Dupont'))

    def test_format_name_rejects_contact(self):
        self.assertEqual(format_name('Contact'), 'N/A')
        self.assertEqual(format_name({'full_name': 'Contact'}), 'N/A')
        self.assertEqual(format_name('Marie Curie'), 'Marie Curie')

    def test_extract_name_from_email_skips_generic(self):
        analyzer = EmailAnalyzer()
        self.assertIsNone(analyzer.extract_name_from_email('contact@exemple.fr'))
        self.assertIsNone(analyzer.extract_name_from_email('info@exemple.fr'))
        self.assertIsNone(analyzer.extract_name_from_email('contact.commercial@exemple.fr'))
        person = analyzer.extract_name_from_email('jean.dupont@exemple.fr')
        self.assertIsNotNone(person)
        self.assertEqual(person['first_name'], 'Jean')
        self.assertEqual(person['last_name'], 'Dupont')


if __name__ == '__main__':
    unittest.main()
