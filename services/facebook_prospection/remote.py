"""
Execution distante des scripts SocialDesk facebook-playwright via SSH.

serv1 : recherche et scrape (worker).
serv2 : Messenger (messenger).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any

from config import (
    FACEBOOK_PROSPECTION_ACCOUNT,
    FACEBOOK_PROSPECTION_REMOTE_FB_DIR,
    FACEBOOK_PROSPECTION_REMOTE_HOST_MESSENGER,
    FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH,
    FACEBOOK_PROSPECTION_REMOTE_TIMEOUT_SEC,
    FACEBOOK_PROSPECTION_REMOTE_WRAPPER,
    LANDING_VARIANTS_SSH_KEY_PATH,
)

logger = logging.getLogger(__name__)


class FacebookRemoteRole(str, Enum):
    """Noeud Windows cible pour un job Playwright."""

    SEARCH = 'search'
    MESSENGER = 'messenger'


def _ssh_bin() -> str:
    explicit = (os.environ.get('SSH_BIN') or '').strip()
    if explicit and os.path.isfile(explicit):
        return explicit
    found = shutil.which('ssh')
    if found:
        return found
    for candidate in ('/usr/bin/ssh', '/bin/ssh'):
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        'Client ssh introuvable (PATH ou SSH_BIN). Sur le Pi : sudo apt install -y openssh-client'
    )


def _host_for_role(role: FacebookRemoteRole) -> str:
    if role == FacebookRemoteRole.MESSENGER:
        return FACEBOOK_PROSPECTION_REMOTE_HOST_MESSENGER
    return FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH


def _build_ssh_base(host: str) -> list[str]:
    cmd = [_ssh_bin(), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=25']
    key = (LANDING_VARIANTS_SSH_KEY_PATH or '').strip()
    if key:
        cmd.extend(['-i', key])
    cmd.append(host)
    return cmd


@dataclass
class FacebookRemoteResult:
    """Resultat d'un appel SSH distant."""

    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    parsed: dict[str, Any] | None = None


class FacebookProspectionRemote:
    """
    Lance le wrapper ProspectLab sur serv1 ou serv2.

    Le wrapper Python sur le Pi appelle ce service ; le script distant
    `run_socialdesk_facebook_remote.py` fera le pont vers Node SocialDesk.
    """

    def run_job(
        self,
        role: FacebookRemoteRole,
        job_type: str,
        payload: dict[str, Any],
    ) -> FacebookRemoteResult:
        """
        Execute un job Facebook distant.

        @param role: SEARCH (serv1) ou MESSENGER (serv2)
        @param job_type: search | scrape_page | messenger_inbox | check_session
        @param payload: parametres JSON (entreprise_id, query, fb_url, etc.)
        @returns: FacebookRemoteResult avec JSON parse si stdout est du JSON
        """
        host = _host_for_role(role)
        body = {
            'account': FACEBOOK_PROSPECTION_ACCOUNT,
            'job_type': job_type,
            'payload': payload,
            'facebook_module_dir': FACEBOOK_PROSPECTION_REMOTE_FB_DIR,
        }
        payload_b64 = base64.b64encode(
            json.dumps(body, ensure_ascii=False).encode('utf-8')
        ).decode('ascii')
        remote_inner = (
            f'python "{FACEBOOK_PROSPECTION_REMOTE_WRAPPER}" --payload-b64 {payload_b64}'
        )
        remote_cmd = f'powershell -NoProfile -Command "{remote_inner}"'
        ssh_cmd = _build_ssh_base(host) + [remote_cmd]
        logger.info('Facebook remote %s@%s type=%s', role.value, host, job_type)
        try:
            proc = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=FACEBOOK_PROSPECTION_REMOTE_TIMEOUT_SEC,
                encoding='utf-8',
                errors='replace',
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return FacebookRemoteResult(
                ok=False,
                exit_code=124,
                stdout=(exc.stdout or '') if isinstance(exc.stdout, str) else '',
                stderr=(exc.stderr or '') if isinstance(exc.stderr, str) else 'timeout',
            )
        merged = (proc.stdout or '').strip()
        parsed = None
        if merged.startswith('{'):
            try:
                parsed = json.loads(merged)
            except json.JSONDecodeError:
                parsed = None
        ok = proc.returncode == 0 and (parsed is None or bool(parsed.get('ok')))
        return FacebookRemoteResult(
            ok=ok,
            exit_code=int(proc.returncode or 0),
            stdout=proc.stdout or '',
            stderr=proc.stderr or '',
            parsed=parsed,
        )

    def check_session(self, role: FacebookRemoteRole) -> FacebookRemoteResult:
        """
        Verifie la session Facebook danielcraft sur le noeud cible.

        @param role: SEARCH ou MESSENGER
        @returns: Resultat SSH (check-session SocialDesk)
        """
        return self.run_job(role, 'check_session', {})
