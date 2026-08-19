#!/usr/bin/env python
"""
Tests unitaires : heuristiques tracking suspect (proxy / bots / prefetch).

Usage:
    python -m unittest scripts.tests.test_tracking_suspect -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.tracking_suspect import (
    build_tracking_event_meta,
    classify_open_hit,
    decide_pixel_event,
    event_data_is_suspect,
    is_cloud_scanner_ip,
    is_prefetch_request,
    is_proxy_or_bot_user_agent,
)


class TestTrackingSuspect(unittest.TestCase):
    """IP cloud, UA proxy, event_data suspect."""

    def test_cloud_ip(self):
        """IPs AWS / Google image proxy detectees."""
        self.assertTrue(is_cloud_scanner_ip('54.184.212.196'))
        self.assertTrue(is_cloud_scanner_ip('66.249.93.202'))
        self.assertFalse(is_cloud_scanner_ip('176.138.223.14'))
        self.assertFalse(is_cloud_scanner_ip('127.0.0.1'))

    def test_proxy_ua(self):
        """UA proxy mail."""
        self.assertTrue(is_proxy_or_bot_user_agent('Mozilla/5.0 GoogleImageProxy'))
        self.assertTrue(is_proxy_or_bot_user_agent('Some Prefetch Agent'))
        self.assertFalse(is_proxy_or_bot_user_agent('Mozilla/5.0 (Windows NT 10.0) Chrome/120'))

    def test_gmail_proxy_is_real_open(self):
        """Gmail ImageProxy compte comme ouverture, pas comme prefetch."""
        meta = build_tracking_event_meta('66.249.93.202', 'Mozilla/5.0 GoogleImageProxy')
        self.assertTrue(meta.get('proxy'))
        self.assertFalse(meta.get('prefetch'))
        self.assertFalse(meta.get('suspect'))
        decided = decide_pixel_event(
            ip_address='66.249.93.202',
            user_agent='Mozilla/5.0 GoogleImageProxy',
            http_method='GET',
            seconds_after_send=5,
        )
        self.assertEqual(decided.get('event_type'), 'open')

    def test_build_meta_cloud_chrome_is_prefetch(self):
        """IP cloud + Chrome = prefetch scanner."""
        meta = build_tracking_event_meta(
            '54.1.2.3',
            'Mozilla/5.0 (Windows NT 10.0) Chrome/120',
        )
        self.assertTrue(meta.get('suspect'))
        self.assertTrue(event_data_is_suspect(meta))
        self.assertTrue(event_data_is_suspect('{"suspect": true, "proxy": true}'))
        self.assertFalse(event_data_is_suspect('{"url": "https://x"}'))
        self.assertFalse(event_data_is_suspect(None))

    def test_prefetch_headers_and_head(self):
        """HEAD et Sec-Fetch-Dest empty = prefetch HTTP."""
        self.assertTrue(is_prefetch_request('HEAD', {}))
        self.assertTrue(is_prefetch_request('GET', {'Purpose': 'prefetch'}))
        self.assertTrue(is_prefetch_request('GET', {'Sec-Fetch-Dest': 'empty'}))
        self.assertFalse(is_prefetch_request('GET', {'Sec-Fetch-Dest': 'image'}))

    def test_apple_mpp_is_prefetch(self):
        """IP Apple = Mail Privacy Protection, pas une ouverture."""
        classified = classify_open_hit(
            ip_address='17.22.14.10',
            user_agent='Mozilla/5.0',
            http_method='GET',
            seconds_after_send=3600,
        )
        self.assertTrue(classified.get('prefetch'))
        self.assertEqual(classified.get('reason'), 'apple_mpp')

    def test_first_ambiguous_hit_is_prefetch(self):
        """Premier hit sans signal humain = non confirme."""
        decided = decide_pixel_event(
            ip_address='176.138.223.14',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            http_method='GET',
            seconds_after_send=200,
        )
        self.assertEqual(decided.get('event_type'), 'prefetch')
        self.assertEqual(decided.get('reason'), 'unconfirmed_first_hit')

    def test_second_hit_confirms_open(self):
        """Un 2e hit apres le prefetch confirme l'ouverture."""
        decided = decide_pixel_event(
            ip_address='176.138.223.14',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            http_method='GET',
            seconds_after_send=400,
            prior_prefetch_count=1,
            seconds_since_first_hit=120,
        )
        self.assertEqual(decided.get('event_type'), 'open')
        self.assertEqual(decided.get('reason'), 'confirmed_after_prefetch')

    def test_ip_burst_is_prefetch(self):
        """Meme IP sur plusieurs emails = scanner de campagne."""
        decided = decide_pixel_event(
            ip_address='176.138.223.14',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120',
            http_method='GET',
            headers={
                'Accept-Language': 'fr-FR,fr;q=0.9',
                'Accept': 'image/png,image/*',
                'Sec-Fetch-Dest': 'image',
            },
            seconds_after_send=900,
            distinct_emails_same_ip=5,
        )
        self.assertEqual(decided.get('event_type'), 'prefetch')
        self.assertEqual(decided.get('reason'), 'ip_burst')

    def test_human_headers_count_as_open(self):
        """Navigateur avec Accept-Language + image = ouverture."""
        decided = decide_pixel_event(
            ip_address='176.138.223.14',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120',
            http_method='GET',
            headers={
                'Accept-Language': 'fr-FR,fr;q=0.9',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                'Sec-Fetch-Dest': 'image',
            },
            seconds_after_send=200,
        )
        self.assertEqual(decided.get('event_type'), 'open')
        self.assertEqual(decided.get('reason'), 'human_headers')


if __name__ == '__main__':
    unittest.main()
