#!/usr/bin/env python
"""
Tests : detection domaines cross-linked.

Usage:
    python -m unittest scripts.tests.test_crosslinked_domains -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.domain_match import domains_compatible


class TestCrosslinkedDomains(unittest.TestCase):
    """Compatibilite domaine site / email."""

    def test_compatible(self):
        self.assertTrue(domains_compatible('fdc55.com', 'fdc55.com'))
        self.assertTrue(domains_compatible('fdc55.com', 'mail.fdc55.fr'))
        self.assertTrue(domains_compatible('acme.fr', 'gmail.com'))  # webmail ok
        self.assertTrue(domains_compatible('cma-alsace-moselle-grandest.fr', 'cma-moselle.fr'))

    def test_mismatch(self):
        self.assertFalse(domains_compatible('fdc55.com', 'meuse.gouv.fr'))
        self.assertFalse(domains_compatible('fdc55.com', 'epagine.fr'))
        self.assertFalse(domains_compatible('boutique.fr', 'amazon.com'))


if __name__ == '__main__':
    unittest.main()
