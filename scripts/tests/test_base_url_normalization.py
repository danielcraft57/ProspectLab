#!/usr/bin/env python3
"""Tests de normalisation BASE_URL / domaines CTA / réparation .f."""

from __future__ import annotations

import unittest

from config import (
    normalize_brand_host,
    normalize_public_base_url,
    normalize_website_url_for_query,
    repair_truncated_danielcraft_urls,
)
from services.email_tracker import EmailTracker


class TestBaseUrlNormalization(unittest.TestCase):
    """Vérifie la réparation de la troncature .f → .fr et des domaines CTA."""

    def test_normalize_repairs_truncated_campaigns_host(self) -> None:
        """BASE_URL campaigns.danielcraft.f doit devenir .fr."""
        out = normalize_public_base_url('https://campaigns.danielcraft.f/')
        self.assertEqual(out, 'https://campaigns.danielcraft.fr')

    def test_normalize_keeps_valid_fr(self) -> None:
        """Une BASE_URL déjà correcte ne change pas."""
        out = normalize_public_base_url('https://campaigns.danielcraft.fr')
        self.assertEqual(out, 'https://campaigns.danielcraft.fr')

    def test_repair_html_hrefs_and_src(self) -> None:
        """Les href/src tronqués dans le HTML sont réparés."""
        html = (
            '<a href="https://campaigns.danielcraft.f/track/click/x">'
            '<img src="https://campaigns.danielcraft.f/track/pixel/x" />'
        )
        fixed = repair_truncated_danielcraft_urls(html)
        self.assertIn('campaigns.danielcraft.fr/track/click', fixed)
        self.assertIn('campaigns.danielcraft.fr/track/pixel', fixed)
        self.assertNotIn('danielcraft.f/', fixed)

    def test_email_tracker_normalizes_base_url(self) -> None:
        """EmailTracker refuse de garder une base tronquée."""
        tracker = EmailTracker(base_url='https://campaigns.danielcraft.f')
        self.assertEqual(tracker.base_url, 'https://campaigns.danielcraft.fr')
        html = tracker.process_email_content(
            '<a href="https://danielcraft.fr/desabonnement">x</a>',
            'TOK',
        )
        self.assertIn('https://campaigns.danielcraft.fr/track/click/TOK', html)
        self.assertNotIn('danielcraft.f/', html)

    def test_normalize_brand_host_repairs_truncation(self) -> None:
        """Un domain_name marque tronqué (cimeria.f) redevient .fr."""
        self.assertEqual(normalize_brand_host('cimeria.f'), 'cimeria.fr')
        self.assertEqual(normalize_brand_host('https://pastele.f/'), 'pastele.fr')

    def test_normalize_website_upgrades_http_to_https(self) -> None:
        """Les websites http:// passent en https:// dans les query CTA."""
        self.assertEqual(
            normalize_website_url_for_query('http://capaxion.fr/'),
            'https://capaxion.fr/',
        )
        self.assertEqual(
            normalize_website_url_for_query('capaxion.fr'),
            'https://capaxion.fr/',
        )


if __name__ == '__main__':
    unittest.main()
