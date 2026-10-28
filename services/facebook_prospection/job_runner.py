"""
Choix local vs SSH (serv1 Windows) pour un job Facebook.
"""

from __future__ import annotations

from typing import Any

from config import FACEBOOK_PROSPECTION_RUNNER

from .local_runner import FacebookProspectionLocalRunner
from .remote import FacebookProspectionRemote, FacebookRemoteRole


def _resolve_runner_mode() -> str:
    """Retourne local, remote ou auto."""
    mode = (FACEBOOK_PROSPECTION_RUNNER or 'remote').strip().lower()
    if mode in ('local', 'remote'):
        return mode
    # auto : recherche/scrape sur serv1, pas sur le Pi / poste dev
    return 'remote'


class FacebookProspectionJobRunner:
    """
    Facade unique pour les taches Celery et l'API.

    Par defaut (RUNNER=remote) : search, scrape et Messenger Playwright sur serv1.
    serv2 (Debian) : messagerie dediee prevue plus tard, pas encore branchee.
    RUNNER=local : Playwright Python sur la machine qui execute ProspectLab.
    """

    def __init__(self) -> None:
        self._local = FacebookProspectionLocalRunner()
        self._remote = FacebookProspectionRemote()

    def run(
        self,
        job_type: str,
        payload: dict[str, Any],
        *,
        force_remote: bool = False,
        on_progress: Any = None,
        remote_host_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute un job et retourne le JSON resultat.

        @param job_type: Type SocialDesk / ProspectLab
        @param payload: Parametres
        @param force_remote: Ignorer le runner local
        @returns: Dict avec cle ok
        """
        mode = _resolve_runner_mode()
        use_remote = force_remote or mode == 'remote' or job_type == 'messenger_inbox'
        if not use_remote and mode == 'local':
            if job_type == 'check_session':
                return {
                    'ok': self._local.session_available(),
                    'job_type': 'check_session',
                    'runner': 'local',
                    'hint': 'storage-state ou cookies.json SocialDesk',
                }
            return self._local.run_job(job_type, payload)

        role = FacebookRemoteRole.MESSENGER if job_type == 'messenger_inbox' else FacebookRemoteRole.SEARCH
        remote_res = self._remote.run_job(
            role,
            job_type,
            payload,
            on_progress=on_progress,
            host_override=remote_host_override,
        )
        parsed = remote_res.parsed or {}
        if parsed:
            parsed.setdefault('runner', 'remote')
            return parsed
        return {
            'ok': remote_res.ok,
            'runner': 'remote',
            'stderr': (remote_res.stderr or '')[-500:],
            'stdout': (remote_res.stdout or '')[-500:],
        }
