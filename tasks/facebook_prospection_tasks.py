"""
Taches Celery : prospection Facebook via serv1 / serv2.
"""

from __future__ import annotations

import logging
from typing import Any

from celery_app import celery
from config import FACEBOOK_PROSPECTION_ENABLED
from services.database import Database
from services.facebook_prospection.remote import FacebookProspectionRemote, FacebookRemoteRole

logger = logging.getLogger(__name__)


def _remote() -> FacebookProspectionRemote:
    return FacebookProspectionRemote()


@celery.task(name='facebook_prospection.run_job', bind=True)
def facebook_prospection_run_job_task(self, job_id: int) -> dict[str, Any]:
    """
    Execute un job Facebook deja cree en base.

    @param job_id: ID facebook_prospection_jobs
    @returns: Resume {ok, job_id, ...}
    """
    if not FACEBOOK_PROSPECTION_ENABLED:
        return {'ok': False, 'error': 'FACEBOOK_PROSPECTION_ENABLED=false'}

    db = Database()
    job = db.get_facebook_prospection_job(job_id)
    if not job:
        return {'ok': False, 'error': 'job introuvable', 'job_id': job_id}

    job_type = str(job.get('job_type') or '')
    entreprise_id = int(job.get('entreprise_id') or 0)
    query = (job.get('search_query') or '').strip()

    role = FacebookRemoteRole.MESSENGER if job_type == 'messenger_inbox' else FacebookRemoteRole.SEARCH
    payload: dict[str, Any] = {'entreprise_id': entreprise_id}
    if query:
        payload['query'] = query

    db.update_facebook_prospection_job_status(job_id, 'running')
    result = _remote().run_job(role, job_type, payload)
    parsed = result.parsed or {}

    if job_type == 'search' and parsed.get('candidates'):
        db.save_facebook_page_candidates(
            job_id,
            entreprise_id,
            list(parsed.get('candidates') or []),
        )

    if result.ok and parsed.get('ok', True):
        db.update_facebook_prospection_job_status(
            job_id,
            'completed',
            result_json=parsed,
        )
        return {'ok': True, 'job_id': job_id, 'result': parsed}

    err = parsed.get('error') or (result.stderr or '')[:500] or 'echec distant'
    db.update_facebook_prospection_job_status(job_id, 'failed', error_message=err, result_json=parsed)
    return {'ok': False, 'job_id': job_id, 'error': err}


@celery.task(name='facebook_prospection.check_sessions')
def facebook_prospection_check_sessions_task() -> dict[str, Any]:
    """
    Verifie les sessions FB danielcraft sur serv1 et serv2 (apres refresh SocialDesk 5h).

    @returns: Etat par role
    """
    if not FACEBOOK_PROSPECTION_ENABLED:
        return {'ok': True, 'skipped': True}

    remote = _remote()
    out: dict[str, Any] = {}
    for role in (FacebookRemoteRole.SEARCH, FacebookRemoteRole.MESSENGER):
        res = remote.check_session(role)
        out[role.value] = {
            'ok': res.ok,
            'exit_code': res.exit_code,
            'parsed': res.parsed,
        }
        if not res.ok:
            logger.warning('Session Facebook %s KO: %s', role.value, res.stderr[:300])

    all_ok = all(item.get('ok') for item in out.values())
    return {'ok': all_ok, 'hosts': out}
