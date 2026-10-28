#!/usr/bin/env python3
"""
Wrapper Windows appele via SSH depuis node15 ou le poste dev.

Installe sur serv1/serv2 sous :
  SocialDesk/deploy/scripts/prospectlab_facebook_remote.py
(deploy : scripts/facebook_prospection/deploy_to_serv1.ps1)
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any


def _emit_json(obj: dict[str, Any]) -> None:
    """Ecrit du JSON ASCII-safe (PowerShell/SSH cassent l'UTF-8)."""
    print(json.dumps(obj, ensure_ascii=True), flush=True)


def _emit_progress(obj: dict[str, Any]) -> None:
    """Relaye une ligne de progression ASCII-safe."""
    print('#PROGRESS:' + json.dumps(obj, ensure_ascii=True), flush=True)


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
    """Appelle prospectlab-facebook-job.mjs (JSON sur stdin). Relaye PROGRESS sur stdout."""
    script = module_dir / 'src' / 'prospectlab-facebook-job.mjs'
    if not script.is_file():
        return {'ok': False, 'error': f'script absent: {script}'}
    payload = json.dumps(body, ensure_ascii=False)
    proc = subprocess.Popen(
        ['node', str(script)],
        cwd=str(module_dir),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None
    proc.stdin.write(payload)
    proc.stdin.close()

    def _pump_stderr() -> None:
        for line in proc.stderr:
            text = line.strip()
            if not text.startswith('PROGRESS '):
                continue
            raw = text[len('PROGRESS ') :].strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {'step': 'log', 'detail': raw[:300]}
            if not isinstance(payload, dict):
                payload = {'step': 'log', 'detail': str(payload)[:300]}
            _emit_progress(payload)

    err_thread = threading.Thread(target=_pump_stderr, daemon=True)
    err_thread.start()
    stdout_chunks: list[str] = []
    for line in proc.stdout:
        stdout_chunks.append(line)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return {'ok': False, 'error': 'timeout node facebook job', 'exit_code': 124}
    err_thread.join(timeout=2)
    stdout = ''.join(stdout_chunks).strip()
    json_start = stdout.find('{')
    if json_start >= 0:
        try:
            parsed = json.loads(stdout[json_start:])
            parsed.setdefault('exit_code', proc.returncode)
            return parsed
        except json.JSONDecodeError:
            pass
    return {
        'ok': proc.returncode == 0,
        'exit_code': proc.returncode,
        'stdout_tail': stdout[-2000:],
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
        _emit_json({'ok': False, 'error': f'facebook_module_dir introuvable: {fb_dir}'})
        return 1

    if job_type == 'check_session':
        out = handle_check_session(fb_dir, account)
        _emit_json(out)
        return 0 if out.get('ok') else 2

    if job_type in ('search', 'scrape_page', 'messenger_inbox', 'prospect_flow'):
        body = {
            'job_type': job_type,
            'account': account,
            'payload': payload,
        }
        out = run_prospectlab_job(fb_dir, body)
        _emit_json(out)
        return 0 if out.get('ok') else 3

    _emit_json({'ok': False, 'error': f'job_type inconnu: {job_type}'})
    return 1


if __name__ == '__main__':
    sys.exit(main())
