"""
Execution distante des scripts SocialDesk facebook-playwright via SSH.

serv1 : Windows + Chrome — recherche, scrape, prospect (compose page FB).
serv2 : Debian + Playwright headless — inbox Messenger (aligne SocialDesk messenger).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import subprocess
import time
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from config import (
    FACEBOOK_PROSPECTION_ACCOUNT,
    FACEBOOK_PROSPECTION_REMOTE_FB_DIR,
    FACEBOOK_PROSPECTION_REMOTE_HEADLESS,
    FACEBOOK_PROSPECTION_REMOTE_HOST_MESSENGER,
    FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH,
    FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH_ALT,
    FACEBOOK_PROSPECTION_REMOTE_MESSENGER_FB_DIR,
    FACEBOOK_PROSPECTION_REMOTE_MESSENGER_WRAPPER,
    FACEBOOK_PROSPECTION_REMOTE_TIMEOUT_SEC,
    FACEBOOK_PROSPECTION_REMOTE_WRAPPER,
    LANDING_VARIANTS_SSH_KEY_PATH,
)

logger = logging.getLogger(__name__)


class FacebookRemoteRole(str, Enum):
    """Noeud cible pour un job Playwright (serv1 search / serv2 messenger)."""

    SEARCH = 'search'
    MESSENGER = 'messenger'


def _remote_stack(role: FacebookRemoteRole) -> tuple[str, str]:
    """
    Chemins wrapper + facebook-playwright selon le role.

    @returns: (facebook_module_dir, wrapper_script)
    """
    if role == FacebookRemoteRole.MESSENGER:
        return (
            FACEBOOK_PROSPECTION_REMOTE_MESSENGER_FB_DIR,
            FACEBOOK_PROSPECTION_REMOTE_MESSENGER_WRAPPER,
        )
    return FACEBOOK_PROSPECTION_REMOTE_FB_DIR, FACEBOOK_PROSPECTION_REMOTE_WRAPPER


def _ssh_uses_linux_shell(host: str, role: FacebookRemoteRole) -> bool:
    """True si la commande distante doit passer par bash (serv2 Debian)."""
    if role == FacebookRemoteRole.MESSENGER:
        return True
    low = (host or '').lower()
    return 'serv2' in low or host.startswith('pi@')


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


def resolve_remote_host_override(meta: dict[str, Any] | None) -> str | None:
    """
    Choix serv1 vs alt pour un job (meta.remote_node).

    @param meta: meta_json du job
    @returns: Host SSH complet ou None (defaut selon role)
    """
    if not meta:
        return None
    node = str(meta.get('remote_node') or meta.get('remote_host') or '').strip().lower()
    alt = (FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH_ALT or '').strip()
    if alt and node in ('alt', 'secondary', 'serv1_b', 'win2'):
        return alt
    if node in ('serv2', 'messenger', '2', 'serv2.lan'):
        return FACEBOOK_PROSPECTION_REMOTE_HOST_MESSENGER
    if node in ('serv1', 'search', '1', 'serv1.lan', 'primary'):
        return FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH
    return None


def remote_host_short_label(host: str | None, role: FacebookRemoteRole) -> str:
    """Etiquette lisible serv1 / alt pour logs UI."""
    if not host:
        host = _host_for_role(role)
    low = host.lower()
    alt = (FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH_ALT or '').strip()
    if alt and host == alt:
        return 'alt'
    if 'serv1' in low:
        return 'serv1'
    if 'serv2' in low:
        return 'serv2'
    return host.split('@')[-1] if '@' in host else host


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
        on_progress: Callable[[dict[str, Any]], None] | None = None,
        host_override: str | None = None,
    ) -> FacebookRemoteResult:
        """
        Execute un job Facebook distant.

        @param role: SEARCH (serv1) ou MESSENGER (serv2)
        @param job_type: search | scrape_page | messenger_* | check_session | cookies_refresh
        @param payload: parametres JSON (entreprise_id, query, fb_url, etc.)
        @param host_override: Force l'hote SSH (switch serv1/serv2)
        @returns: FacebookRemoteResult avec JSON parse si stdout est du JSON
        """
        host = (host_override or '').strip() or _host_for_role(role)
        fb_dir, wrapper = _remote_stack(role)
        remote_payload = dict(payload or {})
        if 'headless' not in remote_payload:
            remote_payload['headless'] = (
                True if role == FacebookRemoteRole.MESSENGER else FACEBOOK_PROSPECTION_REMOTE_HEADLESS
            )
        body = {
            'account': FACEBOOK_PROSPECTION_ACCOUNT,
            'job_type': job_type,
            'payload': remote_payload,
            'facebook_module_dir': fb_dir,
        }
        payload_b64 = base64.b64encode(
            json.dumps(body, ensure_ascii=False).encode('utf-8')
        ).decode('ascii')
        if _ssh_uses_linux_shell(host, role):
            remote_cmd = (
                f'PYTHONUNBUFFERED=1 PYTHONUTF8=1 python3 -u {wrapper!r} --payload-b64 {payload_b64}'
            )
        else:
            remote_inner = (
                f"$env:PYTHONUNBUFFERED='1'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; "
                f'python -u "{wrapper}" --payload-b64 {payload_b64}'
            )
            remote_cmd = f'powershell -NoProfile -Command "{remote_inner}"'
        ssh_cmd = _build_ssh_base(host) + [remote_cmd]
        logger.info('Facebook remote %s@%s type=%s', role.value, host, job_type)
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        try:
            proc = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
            )
            assert proc.stdout is not None
            assert proc.stderr is not None

            def _drain_stderr() -> None:
                try:
                    for err_line in proc.stderr:
                        stderr_chunks.append(err_line)
                except Exception:
                    return

            err_thread = threading.Thread(target=_drain_stderr, daemon=True)
            err_thread.start()

            def _kill_on_timeout() -> None:
                time.sleep(FACEBOOK_PROSPECTION_REMOTE_TIMEOUT_SEC)
                if proc.poll() is None:
                    proc.kill()

            threading.Thread(target=_kill_on_timeout, daemon=True).start()
            for line in proc.stdout:
                stripped = line.strip()
                if stripped.startswith('#PROGRESS:'):
                    raw = stripped[len('#PROGRESS:') :].strip()
                    if on_progress and raw:
                        try:
                            on_progress(json.loads(raw))
                        except json.JSONDecodeError:
                            on_progress({'step': 'log', 'detail': raw[:300]})
                    continue
                stdout_chunks.append(line)
            try:
                proc.wait(timeout=FACEBOOK_PROSPECTION_REMOTE_TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                proc.kill()
                return FacebookRemoteResult(
                    ok=False,
                    exit_code=124,
                    stdout=''.join(stdout_chunks),
                    stderr='timeout',
                )
            err_thread.join(timeout=2)
        except Exception as exc:
            return FacebookRemoteResult(
                ok=False,
                exit_code=1,
                stdout=''.join(stdout_chunks),
                stderr=str(exc)[:800],
            )
        merged = ''.join(stdout_chunks).strip()
        parsed = None
        json_start = merged.find('{')
        if json_start >= 0:
            try:
                parsed = json.loads(merged[json_start:])
            except json.JSONDecodeError:
                parsed = None
        code = int(proc.returncode or 0)
        ok = code == 0 and (parsed is None or bool(parsed.get('ok')))
        return FacebookRemoteResult(
            ok=ok,
            exit_code=code,
            stdout=merged,
            stderr=''.join(stderr_chunks),
            parsed=parsed,
        )

    def check_session(self, role: FacebookRemoteRole) -> FacebookRemoteResult:
        """
        Verifie la session Facebook danielcraft sur le noeud cible.

        @param role: SEARCH ou MESSENGER
        @returns: Resultat SSH (check-session SocialDesk)
        """
        return self.run_job(role, 'check_session', {})
