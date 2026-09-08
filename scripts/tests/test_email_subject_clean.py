#!/usr/bin/env python
"""
Tests unitaires : nettoyage des sujets de campagne.

Usage:
    python -m unittest scripts.tests.test_email_subject_clean -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.email_subject import (
    clean_email_subject,
    humanize_template_name,
    infer_subject_from_html,
    normalize_template_subject,
    normalize_template_value,
    strip_template_title_prefix,
)


class TestEmailSubjectClean(unittest.TestCase):
    """Parentheses vides, fallbacks et separateurs orphelins."""

    def test_empty_parens(self):
        """Les () vides disparaissent du sujet."""
        self.assertEqual(
            clean_email_subject('Sécu : clanche ouverte () Services'),
            'Sécu : clanche ouverte Services',
        )
        self.assertEqual(clean_email_subject('Hello ( ) world'), 'Hello world')

    def test_orphan_separators(self):
        """Tirets / pipes orphelins en fin de sujet."""
        self.assertEqual(clean_email_subject('Un mot pour  - '), 'Un mot pour')
        self.assertEqual(clean_email_subject('Titre | '), 'Titre')

    def test_normalize_template_value(self):
        """None / N/A / votre entreprise deviennent fallback."""
        self.assertEqual(normalize_template_value(None, fallback='x'), 'x')
        self.assertEqual(normalize_template_value('N/A', fallback=''), '')
        self.assertEqual(normalize_template_value('Acme SARL', fallback=''), 'Acme SARL')

    def test_format_then_clean(self):
        """Cas campagne : entreprise vide -> pas de ()."""
        tpl = 'Sécu : ton site laisse la clanche ouverte ({entreprise})'
        ent = normalize_template_value('', fallback='')
        raw = tpl.format(entreprise=ent)
        self.assertEqual(
            clean_email_subject(raw),
            'Sécu : ton site laisse la clanche ouverte',
        )

    def test_strip_objet_prefix(self):
        """Retire Objet: des titres HTML."""
        self.assertEqual(
            normalize_template_subject('Objet: Un site clair pour ton commerce'),
            'Un site clair pour ton commerce',
        )
        self.assertEqual(
            strip_template_title_prefix('OBJET : Test'),
            'Test',
        )

    def test_humanize_template_name(self):
        """Nom UI sans Objet:, placeholders ni ()."""
        self.assertEqual(
            humanize_template_name(
                'Objet: Garage / atelier : un modèle deja pret ({secteur_label})',
                'html_dc_echantillons_auto',
            ),
            'Garage / atelier : un modèle deja pret',
        )
        self.assertEqual(
            humanize_template_name(
                'Sécu : ton site laisse la porte ouverte ({entreprise})',
                'html_dc_secu_clanche',
            ),
            'Ton site laisse la porte ouverte',
        )
        self.assertEqual(
            humanize_template_name(
                'Ta porte web est un peu ouverte ({entreprise})',
                'html_dc_clanche',
            ),
            'Ta porte web est un peu ouverte',
        )
        self.assertEqual(
            humanize_template_name(
                'Objet: Un modèle resto pour {entreprise} - jette un oeil',
                'html_dc_echantillons_restauration',
            ),
            'Un modèle resto — jette un oeil',
        )
        self.assertEqual(
            humanize_template_name('{nom}, ton rapport est prêt - jette un oeil', 'html_dc_audit_rapport'),
            'Ton rapport est prêt - jette un oeil',
        )
        self.assertEqual(
            humanize_template_name('3 notes sur {entreprise} - une est pas terrible', 'html_dc_scores'),
            '3 notes - une est pas terrible',
        )

    def test_infer_subject_from_html(self):
        """Préfère le commentaire SUBJECT au title."""
        html = (
            '<title>Objet: Vieux titre</title>'
            '<!-- SUBJECT: Un modèle resto pour {entreprise} - jette un oeil -->'
        )
        self.assertEqual(
            infer_subject_from_html(html),
            'Un modèle resto pour {entreprise} - jette un oeil',
        )


if __name__ == '__main__':
    unittest.main()
