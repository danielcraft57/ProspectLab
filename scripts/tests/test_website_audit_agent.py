#!/usr/bin/env python
"""
Tests unitaires : génération PDF audit par agent Cursor (script distant + service).

Usage:
    python scripts/tests/test_website_audit_agent.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCRIPT_PATH = ROOT / 'scripts' / 'experiments' / 'gen_audit_report' / 'generate_website_audit_cursor_remote.py'


class TestExtractPdfPaths(unittest.TestCase):
    def test_extract_paths_from_agent_text(self):
        if not SCRIPT_PATH.is_file():
            self.skipTest('script absent')
        import importlib.util

        spec = importlib.util.spec_from_file_location('audit_remote', SCRIPT_PATH)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        text = (
            'Livrable: C:\\Temp\\cursor_generated_audit_reports\\audit_danielcraft.fr\\audit_report.pdf\n'
            '16 pages'
        )
        paths = mod._extract_pdf_paths_from_text(text)
        self.assertTrue(paths)
        self.assertIn('audit_report.pdf', paths[0].lower())


class TestAgentStdoutDetection(unittest.TestCase):
    def test_stdout_mentions_remote_pdf(self):
        if not SCRIPT_PATH.is_file():
            self.skipTest('script absent')
        import importlib.util

        spec = importlib.util.spec_from_file_location('audit_remote', SCRIPT_PATH)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        text = (
            'Livrable: C:\\Temp\\cursor_generated_audit_reports\\audit_danielcraft.fr\\audit_report.pdf\n'
            '16 pages'
        )
        self.assertTrue(
            mod._stdout_mentions_remote_pdf(
                text,
                r'C:\Temp\cursor_generated_audit_reports\audit_danielcraft.fr',
            )
        )
        self.assertFalse(mod._stdout_mentions_remote_pdf('erreur timeout', r'C:\Temp\out'))


class TestScpRemotePaths(unittest.TestCase):
    def test_format_scp_windows_drive(self):
        if not SCRIPT_PATH.is_file():
            self.skipTest('script absent')
        import importlib.util

        spec = importlib.util.spec_from_file_location('audit_remote', SCRIPT_PATH)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        self.assertEqual(
            mod.format_scp_remote_path(r'C:\Temp\cursor_generated_audit_reports\audit_danielcraft.fr\file.pdf'),
            '/C:/Temp/cursor_generated_audit_reports/audit_danielcraft.fr/file.pdf',
        )
        self.assertEqual(
            mod.scp_target('user@host', r'C:\Temp\out.pdf'),
            'user@host:/C:/Temp/out.pdf',
        )


class TestRemoteScriptCli(unittest.TestCase):
    def test_script_accepts_local_baseline_pdf_arg(self):
        if not SCRIPT_PATH.is_file():
            self.skipTest('script generate_website_audit_cursor_remote.py absent')
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf = Path(tmp.name)
            pdf.write_bytes(b'%PDF-1.4 minimal')
        try:
            import subprocess

            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), '--help'],
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('--local-baseline-pdf', proc.stdout)
        finally:
            pdf.unlink(missing_ok=True)

class TestAgentService(unittest.TestCase):
    def test_build_agent_pdf_command_includes_baseline(self):
        from services.website_audit_agent import build_agent_pdf_command

        with tempfile.TemporaryDirectory() as td:
            audit_json = Path(td) / 'ctx.json'
            audit_json.write_text('{}', encoding='utf-8')
            baseline = Path(td) / 'baseline.pdf'
            baseline.write_bytes(b'%PDF')
            out = Path(td) / 'out'
            cmd = build_agent_pdf_command(
                url='https://example.com',
                audit_json_path=audit_json,
                company_name='Ex',
                recipient_email='a@b.com',
                output_dir=out,
                local_baseline_pdf=baseline,
            )
            self.assertIn('--local-baseline-pdf', cmd)
            idx = cmd.index('--local-baseline-pdf')
            self.assertTrue(Path(cmd[idx + 1]).is_file())

    @patch('services.website_audit_agent.subprocess.run')
    @patch('services.website_audit_agent.write_audit_context_json')
    def test_generate_success_parses_stdout_json(self, mock_write, mock_run):
        from services.website_audit_agent import generate_audit_pdf_via_agent

        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / 'site' / 'audit_report.pdf'
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b'%PDF-1.4\n' + b'0' * 600)
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({'success': True, 'pdf_path': str(pdf)}) + '\n',
                stderr='',
            )
            out = generate_audit_pdf_via_agent(
                {'website': 'https://example.com', 'company_name': 'Ex', 'recipient_email': 'a@b.com'},
                output_dir=Path(td),
            )
            self.assertEqual(out, pdf)

    @patch('services.website_audit_agent.subprocess.run')
    @patch('services.website_audit_agent.write_audit_context_json')
    def test_generate_raises_cursor_usage_limit(self, mock_write, mock_run):
        from services.cursor_usage_limit import CursorUsageLimitError
        from services.website_audit_agent import generate_audit_pdf_via_agent

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr="You've hit your usage limit Get Cursor Pro",
        )
        with self.assertRaises(CursorUsageLimitError):
            generate_audit_pdf_via_agent(
                {'website': 'https://example.com'},
                output_dir=Path(tempfile.mkdtemp()),
            )


class TestAgentPromptPayload(unittest.TestCase):
    def test_context_for_agent_prompt_includes_local_pdf(self):
        from services.website_audit_data import context_for_agent_prompt

        out = context_for_agent_prompt({
            'website': 'https://example.com',
            'local_pdf_path': '/tmp/baseline.pdf',
            'pipeline': {},
        })
        self.assertEqual(out['local_pdf_path'], '/tmp/baseline.pdf')

    def test_prompt_mentions_baseline_combine(self):
        from services.website_audit_prompt import build_audit_report_prompt

        text = build_audit_report_prompt(
            website='https://example.com',
            company_name='Ex',
            recipient_email='a@b.com',
            audit_payload={'local_pdf_path': '/x.pdf'},
            remote_output_dir='C:\\Temp\\out',
        )
        self.assertIn('combiner', text.lower())
        self.assertIn('local_pdf_path', text)


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
