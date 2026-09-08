#!/usr/bin/env python
"""
Tests unitaires : filtres email campagne (email_quality).

Usage:
    python -m unittest scripts.tests.test_email_quality -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.email_quality import (
    is_campaign_risky_email,
    is_excluded_campaign_domain,
    is_file_like_email,
    is_placeholder_email,
    is_role_or_support_localpart,
)


class TestEmailQuality(unittest.TestCase):
    """Couvre placeholders, gouv, SaaS et localparts support."""

    def test_file_like_and_placeholder(self):
        """Les faux emails assets / demos sont rejetes."""
        self.assertTrue(is_file_like_email('logo@2x.png'))
        self.assertTrue(is_placeholder_email('info@exemple.fr'))
        self.assertFalse(is_placeholder_email('contact@danielcraft.fr'))

    def test_excluded_gouv_education(self):
        """Institutionnel et education exclus des campagnes."""
        self.assertTrue(is_excluded_campaign_domain('pref@meuse.gouv.fr'))
        self.assertTrue(is_excluded_campaign_domain('marc@education.lu'))
        self.assertTrue(is_excluded_campaign_domain('info@cgie.lu'))
        self.assertFalse(is_excluded_campaign_domain('contact@boutique-locale.fr'))

    def test_saas_and_support(self):
        """SaaS / support / helpdesk exclus."""
        self.assertTrue(is_campaign_risky_email('support@epagine.fr'))
        self.assertTrue(is_campaign_risky_email('helpdesk@cgie.lu'))
        self.assertTrue(is_role_or_support_localpart('api-services-support@amazon.com'))
        self.assertTrue(is_campaign_risky_email('noreply@acme.fr'))
        self.assertFalse(is_campaign_risky_email('marie.dupont@acme.fr'))


if __name__ == '__main__':
    unittest.main()
