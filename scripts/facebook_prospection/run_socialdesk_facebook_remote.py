#!/usr/bin/env python3
"""
Wrapper Windows appele via SSH depuis node15.

Pont vers facebook-playwright (SocialDesk) : check-session, puis a terme
prospectlab-facebook-job.mjs pour search / scrape / messenger.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Job Facebook SocialDesk pour ProspectLab')
    parser.add_argument('--payload-b64', required=True, help='JSON job encode en base64')
    return parser.parse_args()


def run_node(module_dir: Path, args: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    """Lance node dans le repertoire facebook-playwright."""
    cmd = ['node', *args]
    return subprocess.run(
        cmd,
        cwd=str(module_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding='utf-8',
        errors='replace',
        check=False,
    )


def run_prospectlab_job(module_dir: Path, body: dict[str, Any], timeout: int = 900) -> dict[str, Any]:
    """Appelle prospectlab-facebook-job.mjs (JSON sur stdin)."""
    script = module_dir / 'src' / 'prospectlab-facebook-job.mjs'
    if not script.is_file():
        return {'ok': False, 'error': f'script absent: {script}'}
    payload = json.dumps(body, ensure_ascii=False)
    proc = subprocess.run(
        ['node', str(script)],
        cwd=str(module_dir),
        input=payload,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding='utf-8',
        errors='replace',
        check=False,
    )
    stdout = (proc.stdout or '').strip()
    if stdout.startswith('{'):
        try:
            parsed = json.loads(stdout)
            parsed.setdefault('exit_code', proc.returncode)
            return parsed
        except json.JSONDecodeError:
            pass
    return {
        'ok': proc.returncode == 0,
        'exit_code': proc.returncode,
        'stdout_tail': stdout[-2000:],
        'stderr_tail': (proc.stderr or '')[-1000:],
    }


def handle_check_session(module_dir: Path, account: str) -> dict[str, Any]:
    proc = run_node(
        module_dir,
        ['src/check-session.mjs', f'--account={account}', '--quick'],
        timeout=120,
    )
    ok = proc.returncode == 0
    return {
        'ok': ok,
        'exit_code': proc.returncode,
        'stdout_tail': (proc.stdout or '')[-1500:],
        'stderr_tail': (proc.stderr or '')[-800:],
    }


def main() -> int:
    args = parse_args()
    raw = base64.b64decode(args.payload_b64.encode('ascii'))
    job = json.loads(raw.decode('utf-8'))
    job_type = str(job.get('job_type') or '')
    account = str(job.get('account') or 'danielcraft')
    payload = job.get('payload') or {}
    fb_dir = Path(str(job.get('facebook_module_dir') or '')).expanduser()
    if not fb_dir.is_dir():
        print(
            json.dumps(
                {
                    'ok': False,
                    'error': f'facebook_module_dir introuvable: {fb_dir}',
                },
                ensure_ascii=False,
            )
        )
        return 1

    if job_type == 'check_session':
        out = handle_check_session(fb_dir, account)
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out.get('ok') else 2

    if job_type in ('search', 'scrape_page', 'messenger_inbox'):
        body = {
            'job_type': job_type,
            'account': account,
            'payload': payload,
        }
        out = run_prospectlab_job(fb_dir, body)
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out.get('ok') else 3

    print(json.dumps({'ok': False, 'error': f'job_type inconnu: {job_type}'}, ensure_ascii=False))
    return 1


if __name__ == '__main__':
    sys.exit(main())
