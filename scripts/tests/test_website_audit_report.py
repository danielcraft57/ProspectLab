#!/usr/bin/env python
"""
Tests unitaires et smoke API pour les rapports d'audit site (API publique).

Usage:
    python scripts/tests/test_website_audit_report.py
    python -m unittest scripts.tests.test_website_audit_report -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('PUBLIC_WEBSITE_AUDIT_LEAD_KEY', 'test-audit-lead-key-unit')


def _make_api_public_test_app():
    """App Flask minimale (évite l'import complet de app.py / bcrypt)."""
    from flask import Flask
    from routes.api_public import api_public_bp

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(api_public_bp)
    return app


def _has_reportlab() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


class TestAuditHelpers(unittest.TestCase):
    def test_score_status_high_good(self):
        from services.website_audit_data import _score_status

        self.assertEqual(_score_status(80), 'on_track')
        self.assertEqual(_score_status(50), 'in_progress')
        self.assertEqual(_score_status(20), 'at_risk')
        self.assertEqual(_score_status(None), 'unknown')

    def test_score_status_pentest_risk(self):
        from services.website_audit_data import _score_status

        self.assertEqual(_score_status(20, high_good=False), 'on_track')
        self.assertEqual(_score_status(55, high_good=False), 'in_progress')
        self.assertEqual(_score_status(90, high_good=False), 'at_risk')

    def test_audit_data_ready(self):
        from services.website_audit_data import audit_data_ready, audit_missing_modules

        pipeline = {
            'scraping': {'status': 'done'},
            'technical': {'status': 'done'},
            'seo': {'status': 'done'},
            'pentest': {'status': 'done'},
        }
        self.assertTrue(audit_data_ready(pipeline, 'simple'))
        self.assertEqual(audit_missing_modules(pipeline, 'simple'), [])

        partial = dict(pipeline)
        partial['pentest'] = {'status': 'never'}
        self.assertFalse(audit_data_ready(partial, 'simple'))
        self.assertEqual(audit_missing_modules(partial, 'simple'), ['pentest'])

    def test_cursor_usage_limit_detection(self):
        from services.cursor_usage_limit import contains_cursor_usage_limit

        self.assertTrue(contains_cursor_usage_limit("You've hit your usage limit Get Cursor Pro"))
        self.assertFalse(contains_cursor_usage_limit('connection timeout'))

    def test_pending_agent_job_roundtrip(self):
        from services.website_audit_pending import load_pending_agent_job, save_pending_agent_job

        pid = save_pending_agent_job({
            'status': 'paused_agent',
            'website': 'https://example-test-pending.local',
            'recipient_email': 'a@b.com',
            'entreprise_id': 1,
        })
        loaded = load_pending_agent_job(pending_id=pid, website='https://example-test-pending.local')
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.get('status'), 'paused_agent')
        self.assertEqual(loaded.get('pending_id'), pid)
        self.assertTrue((loaded.get('resume_token') or '').strip())

    def test_validate_pending_resume_token(self):
        from services.website_audit_pending import (
            save_pending_agent_job,
            validate_pending_resume_token,
        )

        pid = save_pending_agent_job({
            'status': 'paused_agent',
            'website': 'https://resume-token-test.local',
            'recipient_email': 'a@b.com',
            'entreprise_id': 1,
        })
        from services.website_audit_pending import load_pending_agent_job

        loaded = load_pending_agent_job(pending_id=pid)
        token = loaded['resume_token']
        self.assertTrue(validate_pending_resume_token(pending_id=pid, resume_token=token))
        self.assertFalse(validate_pending_resume_token(pending_id=pid, resume_token='wrong'))

    def test_fit_pdf_image_size_caps_height(self):
        from reportlab.lib.units import cm
        from services.website_audit_pdf import _fit_pdf_image_size

        w, h = _fit_pdf_image_size(17 * cm, 3.0, max_display_height=20 * cm)
        self.assertLessEqual(h, 20 * cm + 0.01)
        self.assertLess(w, 17 * cm)

    def test_essential_vs_full_detail_tables(self):
        from services.website_audit_data import build_audit_detail_tables

        pipeline = {'technical': {'status': 'done', 'security_score': 80}}
        self.assertEqual(len(build_audit_detail_tables(pipeline, tier='essential')), 0)
        self.assertGreater(len(build_audit_detail_tables(pipeline, tier='full')), 0)

    def test_build_audit_detail_tables(self):
        from services.website_audit_data import build_audit_detail_tables

        pipeline = {
            'scraping': {
                'status': 'done',
                'emails_count': 2,
                'sample_emails': ['contact@example.com'],
            },
            'technical': {
                'status': 'done',
                'security_score': 80,
                'seo_meta': {'meta_title': 'Accueil', 'meta_title_length': 42},
                'technical_flags': {'sitemap_exists': True},
            },
            'seo': {'status': 'done', 'score': 65, 'issues': ['Améliorer les titres']},
            'pentest': {'status': 'done', 'risk_score': 30, 'vulnerabilities_count': 1},
        }
        tables = build_audit_detail_tables(pipeline)
        self.assertGreaterEqual(len(tables), 3)
        ids = {t['id'] for t in tables}
        self.assertIn('scraping', ids)
        self.assertIn('technical', ids)
        self.assertIn('seo', ids)

    def test_context_for_agent_prompt(self):
        from services.website_audit_data import context_for_agent_prompt

        ctx = {
            'website': 'https://example.com',
            'company_name': 'Example SAS',
            'recipient_email': 'lead@example.com',
            'pipeline': {
                'technical': {'status': 'done', 'security_score': 72},
                'screenshots': {
                    'latest': {
                        'desktop': {'file_path': '/tmp/d.png'},
                    },
                },
            },
            'health_rows': [{'label': 'SEO', 'score': 60}],
            'executive_summary': 'Synthèse test',
            'quick_wins': ['Corriger les titres'],
        }
        out = context_for_agent_prompt(ctx)
        self.assertEqual(out['website'], 'https://example.com')
        self.assertIn('desktop', out['screenshot_file_paths'])
        self.assertEqual(out['pipeline']['technical']['security_score'], 72)

    def test_build_audit_report_prompt(self):
        from services.website_audit_prompt import build_audit_report_prompt

        prompt = build_audit_report_prompt(
            website='https://example.com',
            company_name='Example',
            recipient_email='lead@example.com',
            audit_payload={'pipeline': {'seo': {'status': 'done', 'score': 55}}},
            remote_output_dir=r'C:\Temp\cursor_generated_audit_reports\run-1',
        )
        self.assertIn('https://example.com', prompt)
        self.assertIn('lead@example.com', prompt)
        self.assertIn('"score": 55', prompt)
        self.assertIn('8 à 15 pages', prompt)
        self.assertIn('run-1', prompt)


class TestAuditRequestBasics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _make_api_public_test_app()

    def test_missing_website(self):
        from routes.api_public import _audit_request_basics

        with self.app.app_context():
            basics, err = _audit_request_basics({'email': 'a@b.com'})
            self.assertIsNone(basics)
            self.assertIsNotNone(err)
            resp, code = err
            self.assertEqual(code, 400)
            data = json.loads(resp.get_data(as_text=True))
            self.assertFalse(data['success'])
            self.assertIn('website', data['error'])

    def test_missing_email(self):
        from routes.api_public import _audit_request_basics

        with self.app.app_context():
            basics, err = _audit_request_basics({'website': 'https://example.com'})
            self.assertIsNone(basics)
            self.assertIsNotNone(err)
            _, code = err
            self.assertEqual(code, 400)

    def test_ok(self):
        from routes.api_public import _audit_request_basics

        basics, err = _audit_request_basics({
            'website': 'example.com',
            'email': 'Lead@Example.COM',
        })
        self.assertIsNone(err)
        website, recipient = basics
        self.assertTrue(website.startswith('http'))
        self.assertEqual(recipient, 'lead@example.com')


class TestAuditPublicEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _make_api_public_test_app()
        cls.client = cls.app.test_client()
        cls.headers = {'X-Website-Audit-Key': 'test-audit-lead-key-unit'}

    def test_unauthorized_without_key(self):
        r = self.client.post(
            '/api/public/website-audit-report',
            json={'website': 'https://example.com', 'email': 'a@b.com'},
        )
        self.assertEqual(r.status_code, 401)

    @patch('routes.api_public._resolve_entreprise_for_audit', return_value=42)
    @patch('tasks.website_audit_report_tasks.website_audit_simple_report_task.apply_async')
    def test_simple_post_accepted(self, mock_apply, _mock_ent):
        mock_apply.return_value = MagicMock(id='task-simple-abc')

        r = self.client.post(
            '/api/public/website-audit-report',
            json={'website': 'https://example.com', 'email': 'lead@example.com'},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 202)
        data = r.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['mode'], 'simple')
        self.assertEqual(data['task_id'], 'task-simple-abc')
        self.assertEqual(data['pdf_engine'], 'local')
        self.assertIn('scraping', data['analysis_modules'])
        self.assertIn('technical', data['analysis_modules'])
        self.assertIn('pentest', data['analysis_modules'])
        mock_apply.assert_called_once()
        kwargs = mock_apply.call_args.kwargs.get('kwargs') or mock_apply.call_args[1].get('kwargs')
        self.assertEqual(kwargs['recipient_email'], 'lead@example.com')
        self.assertEqual(kwargs['entreprise_id'], 42)

    @patch('routes.api_public._resolve_entreprise_for_audit', return_value=99)
    @patch('tasks.website_audit_report_tasks.website_audit_complete_report_task.apply_async')
    def test_complete_post_accepted(self, mock_apply, _mock_ent):
        mock_apply.return_value = MagicMock(id='task-complete-xyz')

        r = self.client.post(
            '/api/public/website-audit-report/complete',
            json={
                'website': 'example.org',
                'email': 'ceo@example.org',
                'max_depth': 3,
                'extra_instructions': 'Insister sur accessibilité',
            },
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 202)
        data = r.get_json()
        self.assertEqual(data['mode'], 'complete')
        self.assertEqual(data['pdf_engine'], 'expert')
        self.assertIn('pentest', data['analysis_modules'])
        kwargs = mock_apply.call_args.kwargs.get('kwargs') or mock_apply.call_args[1].get('kwargs')
        self.assertEqual(kwargs['extra_instructions'], 'Insister sur accessibilité')
        self.assertEqual(kwargs['max_depth'], 3)

    @patch('celery.result.AsyncResult')
    @patch('tasks.website_audit_report_tasks.website_audit_complete_resume_task.apply_async')
    def test_resume_get_duplicate_does_not_enqueue_twice(self, mock_apply, mock_async_result):
        from services.website_audit_pending import load_pending_agent_job, save_pending_agent_job

        inst = MagicMock()
        inst.state = 'PROGRESS'
        mock_async_result.return_value = inst
        mock_apply.return_value = MagicMock(id='task-resume-1')

        pid = save_pending_agent_job({
            'status': 'paused_agent',
            'website': 'https://danielcraft.fr',
            'recipient_email': 'lead@example.com',
            'entreprise_id': 2,
        })
        token = load_pending_agent_job(pending_id=pid)['resume_token']

        r1 = self.client.get(
            f'/api/public/website-audit-report/complete/resume'
            f'?pending_id={pid}&resume_token={token}',
        )
        self.assertEqual(r1.status_code, 202, r1.get_data(as_text=True))
        mock_apply.assert_called_once()

        r2 = self.client.get(
            f'/api/public/website-audit-report/complete/resume'
            f'?pending_id={pid}&resume_token={token}',
        )
        self.assertIn(r2.status_code, (200, 202), r2.get_data(as_text=True))
        mock_apply.assert_called_once()
        html = r2.get_data(as_text=True).lower()
        self.assertTrue('déjà' in html or 'double' in html or 'rafraîchir' in html)

    @patch('tasks.website_audit_report_tasks.website_audit_complete_resume_task.apply_async')
    def test_resume_get_with_resume_token(self, mock_apply):
        from services.website_audit_pending import load_pending_agent_job, save_pending_agent_job

        pid = save_pending_agent_job({
            'status': 'paused_agent',
            'website': 'https://danielcraft.fr',
            'recipient_email': 'lead@example.com',
            'entreprise_id': 2,
        })
        token = load_pending_agent_job(pending_id=pid)['resume_token']
        mock_apply.return_value = MagicMock(id='task-resume-1')

        r = self.client.get(
            f'/api/public/website-audit-report/complete/resume'
            f'?pending_id={pid}&resume_token={token}',
        )
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))
        mock_apply.assert_called_once()

    @patch('celery.result.AsyncResult')
    def test_status_pending(self, mock_async_result):
        inst = MagicMock()
        inst.state = 'PENDING'
        inst.ready.return_value = False
        inst.successful.return_value = None
        inst.result = None
        mock_async_result.return_value = inst

        r = self.client.get(
            '/api/public/website-audit-report/task-123',
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data['state'], 'PENDING')
        self.assertFalse(data['ready'])


class TestCeleryAuditTasksRegistered(unittest.TestCase):
    @unittest.skipUnless(_has_reportlab(), 'reportlab requis pour enregistrer les tâches audit')
    def test_audit_tasks_registered(self):
        import importlib

        importlib.reload(__import__('celery_app', fromlist=['celery']))
        from celery_app import celery
        import tasks.website_audit_report_tasks  # noqa: F401

        for name in (
            'tasks.website_audit_report_tasks.website_audit_simple_report_task',
            'tasks.website_audit_report_tasks.website_audit_complete_report_task',
            'tasks.website_audit_report_tasks.website_audit_complete_resume_task',
        ):
            with self.subTest(task=name):
                self.assertIn(name, celery.tasks, msg=f'Tâche manquante: {name}')
        from tasks import website_audit_report_tasks

        self.assertIs(
            website_audit_report_tasks.website_audit_report_task,
            website_audit_report_tasks.website_audit_complete_report_task,
        )


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
