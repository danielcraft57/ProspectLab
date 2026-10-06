# -*- coding: utf-8 -*-
"""
Tests unitaires du payload public Gemini (sans serveur HTTP).

Verifie que GET /api/public/.../gemini-report expose bien indicateurs,
textes et bons/mauvais points comme l'onglet site.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


class TestPublicGeminiReportPayload(unittest.TestCase):
    """Construit le JSON public a partir d'un rapport hydrate."""

    def test_never_sans_rapport(self):
        from routes.api_public import _build_public_gemini_report_payload

        with patch('routes.api_public.database') as db:
            db.get_latest_entreprise_gemini_report.return_value = None
            payload = _build_public_gemini_report_payload(42)

        self.assertTrue(payload['success'])
        self.assertEqual(payload['status'], 'never')
        self.assertEqual(payload['entreprise_id'], 42)
        self.assertEqual(payload['indicators'], {})
        self.assertEqual(payload['what_works'], [])
        self.assertEqual(payload['whats_wrong'], [])
        self.assertIsNone(payload['report'])

    def test_done_avec_indicateurs_et_listes(self):
        from routes.api_public import _build_public_gemini_report_payload

        latest = {
            'id': 9,
            'status': 'done',
            'overall_score': 42,
            'refonte_recommendation': 'partielle',
            'source': 'gemini',
            'analyzed_at': '2026-04-01 12:00:00',
            'executive_summary': 'Resume court',
            'commercial_pitch': 'Pitch commercial',
            'screenshot_set_id': 3,
            'error_message': None,
            'report': {
                'overall_score': 42,
                'refonte_recommendation': 'partielle',
                'executive_summary': 'Resume court',
                'commercial_pitch': 'Pitch commercial',
                'what_works': ['Logo clair'],
                'whats_wrong': ['CTA invisible'],
                'priority_actions': ['Refonte hero'],
                'improvements': [
                    {'area': 'seo', 'priority': 'haute', 'action': 'Titles uniques'},
                ],
                'modules': {
                    'design': {'score': 38, 'notes': 'Contraste faible'},
                    'seo': {'score': 30, 'notes': 'H1 manquant'},
                },
                'design_analysis': {
                    'score': 35,
                    'summary': 'UI vieillissante',
                    'ux_notes': 'Nav confuse',
                    'ui_notes': 'Typo datee',
                    'to_keep': ['Logo'],
                    'to_redo': ['Hero'],
                },
                'source': 'gemini',
            },
        }

        with patch('routes.api_public.database') as db:
            db.get_latest_entreprise_gemini_report.return_value = latest
            payload = _build_public_gemini_report_payload(123)

        self.assertEqual(payload['status'], 'done')
        self.assertEqual(payload['overall_score'], 42)
        self.assertEqual(payload['executive_summary'], 'Resume court')
        self.assertEqual(payload['commercial_pitch'], 'Pitch commercial')
        self.assertEqual(payload['what_works'], ['Logo clair'])
        self.assertEqual(payload['whats_wrong'], ['CTA invisible'])
        self.assertEqual(payload['priority_actions'], ['Refonte hero'])
        self.assertEqual(payload['indicators']['design']['score'], 38)
        self.assertEqual(payload['indicators']['seo']['notes'], 'H1 manquant')
        self.assertEqual(payload['design_analysis']['to_keep'], ['Logo'])
        self.assertEqual(payload['report']['modules']['design']['score'], 38)
        self.assertNotIn('report_document', payload)
        self.assertNotIn('latest', payload)

    def test_include_document_et_raw(self):
        from routes.api_public import _build_public_gemini_report_payload

        latest = {
            'id': 1,
            'status': 'done',
            'overall_score': 10,
            'refonte_recommendation': 'totale',
            'source': 'heuristic',
            'analyzed_at': None,
            'executive_summary': '',
            'commercial_pitch': '',
            'report_document': '# Titre\n\nCorps',
            'screenshot_set_id': None,
            'error_message': None,
            'report': {
                'what_works': [],
                'whats_wrong': [],
                'priority_actions': [],
                'improvements': [],
                'modules': {},
                'design_analysis': None,
                'report_document': '# Titre\n\nCorps',
            },
        }

        with patch('routes.api_public.database') as db:
            db.get_latest_entreprise_gemini_report.return_value = latest
            payload = _build_public_gemini_report_payload(
                7,
                include_document=True,
                include_raw=True,
            )

        self.assertEqual(payload['report_document'], '# Titre\n\nCorps')
        self.assertEqual(payload['report']['report_document'], '# Titre\n\nCorps')
        self.assertIs(payload['latest'], latest)


if __name__ == '__main__':
    unittest.main()
