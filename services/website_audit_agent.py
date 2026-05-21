"""
Invocation du générateur de rapport d'audit PDF via agent Cursor distant.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    LANDING_VARIANTS_MODEL,
    LANDING_VARIANTS_REMOTE_CURSOR_COMMAND,
    LANDING_VARIANTS_REMOTE_HOST,
    LANDING_VARIANTS_REMOTE_WORKSPACE,
    LANDING_VARIANTS_SSH_KEY_PATH,
    WEBSITE_AUDIT_AGENT_REMOTE_OUTPUT_ROOT,
    WEBSITE_AUDIT_AGENT_REMOTE_TEMP_ROOT,
    WEBSITE_AUDIT_AGENT_SCRIPT_PATH,
    WEBSITE_AUDIT_AGENT_TIMEOUT,
)
from services.cursor_usage_limit import CursorUsageLimitError, contains_cursor_usage_limit
from services.logging_config import setup_logger
from services.website_audit_data import write_audit_context_json
from services.website_audit_pending import audit_site_slug

logger = setup_logger(__name__, 'website_audit_agent.log')

_BASELINE_PDF_NAME = 'audit_report_reference_baseline.pdf'
_AGENT_FAILURE_MARKERS = ('AGENT_FAILURE:', '[ssh]', '[prepare]', '[upload]', '[run]', '[fetch]')


def _extract_agent_failure_detail(merged: str) -> str:
    """Extrait la vraie cause (souvent noyée après des lignes INFO du script)."""
    lines = [ln.strip() for ln in (merged or '').splitlines() if ln.strip()]
    for line in reversed(lines):
        if line.startswith('AGENT_FAILURE:'):
            return line[len('AGENT_FAILURE:'):].strip()
        if 'openssh-client' in line.lower() or 'commande « ssh » introuvable' in line.lower():
            return line
        if 'FileNotFoundError' in line and 'ssh' in line.lower():
            return 'Client SSH absent sur le serveur (sudo apt install -y openssh-client)'
        if any(marker in line for marker in _AGENT_FAILURE_MARKERS[1:]):
            return line
    for line in reversed(lines):
        if 'ERROR' in line or 'Echec' in line:
            return line
    return (merged or '')[-2500:].strip()
_AGENT_PDF_NAME = 'audit_report.pdf'


def build_agent_pdf_command(
    *,
    url: str,
    audit_json_path: Path,
    company_name: str,
    recipient_email: str,
    output_dir: Path,
    extra_instructions: Optional[str] = None,
    local_baseline_pdf: Optional[Path] = None,
) -> List[str]:
    """Construit la ligne de commande du script de génération PDF par agent."""
    cmd = [
        sys.executable,
        str(Path(WEBSITE_AUDIT_AGENT_SCRIPT_PATH)),
        '--url',
        url,
        '--audit-json',
        str(audit_json_path),
        '--company',
        company_name or '',
        '--recipient-email',
        recipient_email or '',
        '--remote-host',
        LANDING_VARIANTS_REMOTE_HOST,
        '--remote-cursor-command',
        LANDING_VARIANTS_REMOTE_CURSOR_COMMAND,
        '--model',
        LANDING_VARIANTS_MODEL,
        '--agent-timeout',
        str(WEBSITE_AUDIT_AGENT_TIMEOUT),
        '--remote-temp-root',
        WEBSITE_AUDIT_AGENT_REMOTE_TEMP_ROOT,
        '--remote-output-root',
        WEBSITE_AUDIT_AGENT_REMOTE_OUTPUT_ROOT,
        '--output-dir',
        str(output_dir),
        '--log-level',
        'INFO',
    ]
    if LANDING_VARIANTS_REMOTE_WORKSPACE.strip():
        cmd.extend(['--remote-workspace', LANDING_VARIANTS_REMOTE_WORKSPACE.strip()])
    if LANDING_VARIANTS_SSH_KEY_PATH.strip():
        cmd.extend(['--ssh-key-path', LANDING_VARIANTS_SSH_KEY_PATH.strip()])
    if extra_instructions:
        cmd.extend(['--extra-instructions', str(extra_instructions)])
    if local_baseline_pdf and Path(local_baseline_pdf).is_file():
        cmd.extend(['--local-baseline-pdf', str(Path(local_baseline_pdf).resolve())])
    return cmd


def resolve_agent_audit_pdf(
    website: str,
    output_dir: Path,
    *,
    hinted_path: Optional[Path] = None,
) -> Path:
    """
    Retourne le PDF produit par l'agent (pas le baseline interne de référence).
    """
    slug = audit_site_slug(website)
    candidates: List[Path] = []
    if hinted_path and hinted_path.is_file():
        candidates.append(Path(hinted_path))
    candidates.extend([
        output_dir / slug / _AGENT_PDF_NAME,
        output_dir / slug / 'audit_report_agent.pdf',
        output_dir / _AGENT_PDF_NAME,
    ])
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        if not path.is_file():
            continue
        if path.name == _BASELINE_PDF_NAME:
            continue
        if path.stat().st_size < 512:
            continue
        return path
    raise RuntimeError(
        f'PDF agent introuvable pour {website}. Vérifiez exports/audit_reports/{slug}/audit_report.pdf'
    )


def generate_audit_pdf_via_agent(
    context: Dict[str, Any],
    *,
    output_dir: Path,
    extra_instructions: Optional[str] = None,
) -> Path:
    """
    Lance le script agent distant et retourne le chemin du PDF local.

    Raises:
        CursorUsageLimitError: quota Cursor atteint.
        RuntimeError: autre échec de génération.
    """
    url = (context.get('website') or '').strip()
    if not url:
        raise ValueError('website manquant dans le contexte')

    script_path = Path(WEBSITE_AUDIT_AGENT_SCRIPT_PATH)
    if not script_path.is_file():
        raise RuntimeError(
            f'Script agent introuvable: {script_path}. '
            'Vérifiez le déploiement (git pull) : scripts/experiments/gen_audit_report/ '
            'doit être versionné et présent sur le serveur.'
        )

    company = (context.get('company_name') or '').strip()
    recipient = (context.get('recipient_email') or '').strip()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.json',
        delete=False,
        encoding='utf-8',
        prefix='audit_ctx_',
    ) as tmp:
        audit_json_path = Path(tmp.name)
    try:
        write_audit_context_json(context, audit_json_path)
        local_pdf = (context.get('local_pdf_path') or '').strip()
        local_path = Path(local_pdf) if local_pdf else None
        cmd = build_agent_pdf_command(
            url=url,
            audit_json_path=audit_json_path,
            company_name=company,
            recipient_email=recipient,
            output_dir=output_dir,
            extra_instructions=extra_instructions,
            local_baseline_pdf=local_path,
        )
        logger.info('Lancement génération PDF audit par agent: %s', url)
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=False,
            timeout=max(600, WEBSITE_AUDIT_AGENT_TIMEOUT + 600),
            encoding='utf-8',
            errors='replace',
        )
        merged = f"{proc.stdout or ''}\n{proc.stderr or ''}".strip()
        if proc.returncode != 0:
            detail = _extract_agent_failure_detail(merged)
            logger.error(
                'Agent audit échoué (code=%s) pour %s: %s',
                proc.returncode,
                url,
                detail,
            )
            if contains_cursor_usage_limit(merged):
                raise CursorUsageLimitError(
                    'Cursor usage limit',
                    detail=detail,
                )
            raise RuntimeError(
                f'Agent audit failed (code={proc.returncode}): {detail}'
            )

        pdf_path: Optional[Path] = None
        for line in reversed((proc.stdout or '').splitlines()):
            line = line.strip()
            if not line.startswith('{'):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get('success') and payload.get('pdf_path'):
                pdf_path = Path(str(payload['pdf_path']))
                break

        hinted = Path(str(pdf_path)) if pdf_path else None
        try:
            return resolve_agent_audit_pdf(url, output_dir, hinted_path=hinted)
        except RuntimeError:
            pass

        raise RuntimeError(f'PDF agent introuvable après génération. Sortie: {merged[-1500:]}')
    finally:
        try:
            audit_json_path.unlink(missing_ok=True)
        except OSError:
            pass


# Rétrocompatibilité (anciens imports)
generate_audit_pdf_on_serv1 = generate_audit_pdf_via_agent
_build_command = build_agent_pdf_command
