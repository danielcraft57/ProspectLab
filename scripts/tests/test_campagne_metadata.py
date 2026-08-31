#!/usr/bin/env python
"""Tests métadonnées ciblage campagne."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.campagne_metadata import (
    enrich_campagne_from_params,
    extract_groupe_ids_from_payload,
    normalize_groupe_ids,
)


class TestCampagneMetadata(unittest.TestCase):
    def test_normalize_groupe_ids(self):
        self.assertEqual(normalize_groupe_ids([1, '2', None]), [1, 2])
        self.assertEqual(normalize_groupe_ids('3'), [3])

    def test_extract_from_ciblage(self):
        data = {'ciblage': {'mode': 'groupes', 'groupe_ids': [5, 6]}}
        self.assertEqual(extract_groupe_ids_from_payload(data), [5, 6])

    def test_enrich_campagne(self):
        import json
        camp = {
            'id': 1,
            'plan_hebdo_id': 2,
            'campaign_params_json': json.dumps({
                'groupe_ids': [10],
                'rotation_mode': 'split',
                'ciblage': {'mode': 'groupes'},
            }),
        }
        enrich_campagne_from_params(camp)
        self.assertEqual(camp['groupe_ids'], [10])
        self.assertEqual(camp['rotation_mode'], 'split')
        self.assertEqual(camp['plan_hebdo_id'], 2)


if __name__ == '__main__':
    unittest.main()
