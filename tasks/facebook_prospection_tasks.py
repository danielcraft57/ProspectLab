"""
Taches Celery : prospection Facebook (local Playwright ou SSH serv1/serv2).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from celery_app import celery
from config import FACEBOOK_PROSPECTION_ENABLED
from services.database import Database
from services.facebook_prospection.entreprise_payload import (
    build_facebook_search_payload_from_entreprise,
    build_prospect_payload_from_entreprise,
    default_prospect_message,
)
from services.facebook_prospection.job_runner import FacebookProspectionJobRunner
from services.facebook_prospection.prospect_result import (
    normalize_prospect_flow_result,
    prospect_flow_job_status,
)
from services.facebook_prospection.remote import (
    FacebookProspectionRemote,
    FacebookRemoteRole,
    _host_for_role,
    remote_host_short_label,
    resolve_remote_host_override,
)

logger = logging.getLogger(__name__)


def _runner() -> FacebookProspectionJobRunner:
    return FacebookProspectionJobRunner()


def _meta_from_job(job: dict[str, Any]) -> dict[str, Any]:
    """Parse meta_json du job."""
    raw = job.get('meta_json')
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _payload_for_job(db: Database, job: dict[str, Any]) -> dict[str, Any]:
    """Construit le payload distant/local a partir du job BDD."""
    job_type = str(job.get('job_type') or '')
    entreprise_id = int(job.get('entreprise_id') or 0)
    query = (job.get('search_query') or '').strip()
    meta = _meta_from_job(job)
    payload: dict[str, Any] = {'entreprise_id': entreprise_id}
    if query:
        payload['query'] = query
    if entreprise_id:
        ent = db.get_entreprise(entreprise_id)
        if ent:
            nom = (
                ent.get('nom')
                or ent.get('name')
                or ent.get('raison_sociale')
                or ent.get('nom_entreprise')
                or ''
            ).strip()
            if nom:
                payload['target_name'] = nom
                if not query:
                    payload['query'] = nom
            if job_type == 'prospect_flow':
                return build_prospect_payload_from_entreprise(
                    ent or {},
                    message_text=meta.get('message_text'),
                    send=bool(meta.get('send')),
                    headless=meta.get('headless', False),
                    db=db,
                )
            if job_type == 'search' and ent:
                return build_facebook_search_payload_from_entreprise(
                    ent,
                    headless=meta.get('headless', False),
                    db=db,
                )
            if job_type == 'scrape_page' and ent:
                fb_url = (meta.get('fb_url') or ent.get('facebook_page_url') or '').strip()
                payload_scrape = {
                    'fb_url': fb_url,
                    'page_url': fb_url,
                    'headless': meta.get('headless', False),
                }
                if fb_url:
                    return payload_scrape
    return payload


def _job_result_dict(job: dict[str, Any] | None) -> dict[str, Any]:
    """Parse result_json d'un job Facebook."""
    if not job:
        return {}
    raw = job.get('result_json')
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def execute_facebook_prospection_job(job_id: int) -> dict[str, Any]:
    """
    Execute un job Facebook deja cree en base (Celery ou retry).

    @param job_id: ID facebook_prospection_jobs
    @returns: Resume {ok, job_id, ...}
    """
    db = Database()
    job = db.get_facebook_prospection_job(job_id)
    if not job:
        return {'ok': False, 'error': 'job introuvable', 'job_id': job_id}

    if not FACEBOOK_PROSPECTION_ENABLED:
        db.update_facebook_prospection_job_status(
            job_id,
            'failed',
            error_message='FACEBOOK_PROSPECTION_ENABLED=false sur le worker Celery',
        )
        return {'ok': False, 'error': 'FACEBOOK_PROSPECTION_ENABLED=false', 'job_id': job_id}

    job_type = str(job.get('job_type') or '')
    entreprise_id = int(job.get('entreprise_id') or 0)
    meta = _meta_from_job(job)
    payload = _payload_for_job(db, job)
    host_override = resolve_remote_host_override(meta)
    role = FacebookRemoteRole.MESSENGER if job_type == 'messenger_inbox' else FacebookRemoteRole.SEARCH
    host_label = remote_host_short_label(host_override, role)

    def on_progress(evt: dict[str, Any]) -> None:
        if not isinstance(evt, dict):
            return
        extra = {key: val for key, val in evt.items() if key not in ('step', 'detail')}
        db.append_facebook_job_progress(
            job_id,
            str(evt.get('step') or 'log'),
            str(evt.get('detail') or ''),
            extra or None,
        )

    db.append_facebook_job_progress(job_id, 'queue', 'Worker Celery a pris le job')
    db.update_facebook_prospection_job_status(job_id, 'running')
    if payload.get('website_scraped'):
        bits = []
        if payload.get('address_hint'):
            bits.append('adresse')
        if payload.get('phone_hint'):
            bits.append('tel')
        if payload.get('website_domain'):
            bits.append(str(payload.get('website_domain')))
        extra = ''
        urls = payload.get('known_facebook_urls') or []
        if urls:
            extra = ' + lien FB deja vu sur le site'
        db.append_facebook_job_progress(
            job_id,
            'site',
            'Scrape site deja en base, on s en sert pour matcher (' + ', '.join(bits or ['fiche']) + ')' + extra,
        )
    else:
        db.append_facebook_job_progress(
            job_id,
            'site',
            'Pas de scrape site en base: matching surtout sur le nom',
        )
    db.append_facebook_job_progress(job_id, 'ssh', 'Connexion SSH vers ' + host_label + '...')
    try:
        parsed = _runner().run(
            job_type,
            payload,
            on_progress=on_progress,
            remote_host_override=host_override,
        )
    except Exception as exc:
        logger.exception('Job Facebook %s plante', job_id)
        db.update_facebook_prospection_job_status(
            job_id,
            'failed',
            error_message=str(exc)[:500],
        )
        return {'ok': False, 'job_id': job_id, 'error': str(exc)[:500]}
    if not isinstance(parsed, dict):
        parsed = {'ok': False, 'error': 'reponse invalide'}

    if job_type == 'prospect_flow':
        parsed = normalize_prospect_flow_result(parsed)

    saved_page = None
    if job_type in ('search', 'prospect_flow', 'scrape_page') and entreprise_id:
        saved_page = db.persist_facebook_page_from_job(
            entreprise_id,
            job_id,
            job_type,
            parsed,
        )

    if entreprise_id and parsed.get('profile'):
        db.merge_facebook_page_scrape_profile(entreprise_id, parsed.get('profile') or {})

    if job_type in ('search', 'prospect_flow') and parsed.get('candidates'):
        db.save_facebook_page_candidates(
            job_id,
            entreprise_id,
            list(parsed.get('candidates') or []),
        )

    conv_out = None
    if job_type == 'prospect_flow' and entreprise_id:
        meta = _meta_from_job(job)
        msg_text = (meta.get('message_text') or parsed.get('message_text') or '').strip()
        if not msg_text:
            ent = db.get_entreprise(entreprise_id)
            nom = (ent.get('nom') or ent.get('name') or '') if ent else ''
            msg_text = default_prospect_message(nom)
        conv_out = db.persist_prospect_flow_outreach(
            entreprise_id,
            job_id,
            parsed,
            message_text=msg_text,
        )

    if job_type == 'prospect_flow':
        db_status, err_msg = prospect_flow_job_status(parsed)
    elif parsed.get('ok'):
        db_status, err_msg = 'completed', None
    else:
        db_status, err_msg = 'failed', str(parsed.get('error') or 'echec job Facebook')[:500]

    previous = _job_result_dict(db.get_facebook_prospection_job(job_id))
    if previous.get('progress') and not parsed.get('progress'):
        parsed['progress'] = previous.get('progress')

    if db_status in ('completed', 'partial'):
        db.update_facebook_prospection_job_status(
            job_id,
            db_status,
            error_message=err_msg,
            result_json=parsed,
        )
        out = {
            'ok': True,
            'job_id': job_id,
            'result': parsed,
            'job_status': db_status,
        }
        if saved_page:
            out['facebook_page_url'] = saved_page.get('url')
        if conv_out:
            out['conversation'] = conv_out
        return out

    db.update_facebook_prospection_job_status(
        job_id,
        'failed',
        error_message=err_msg,
        result_json=parsed,
    )
    return {'ok': False, 'job_id': job_id, 'error': err_msg or 'echec job Facebook'}


@celery.task(name='facebook_prospection.run_job', bind=True)
def facebook_prospection_run_job_task(self, job_id: int) -> dict[str, Any]:
    """
    Tache Celery : execute un job Facebook deja cree en base.

    @param job_id: ID facebook_prospection_jobs
    @returns: Resume {ok, job_id, ...}
    """
    return execute_facebook_prospection_job(int(job_id))


@celery.task(name='facebook_prospection.check_sessions')
def facebook_prospection_check_sessions_task() -> dict[str, Any]:
    """
    Verifie les sessions FB (local + serv1 Windows si remote actif).

    @returns: Etat par canal
    """
    if not FACEBOOK_PROSPECTION_ENABLED:
        return {'ok': True, 'skipped': True}

    out: dict[str, Any] = {'local': _runner().run('check_session', {})}
    remote = FacebookProspectionRemote()
    for role in (FacebookRemoteRole.SEARCH, FacebookRemoteRole.MESSENGER):
        target = _host_for_role(role)
        if role == FacebookRemoteRole.MESSENGER and 'serv2' in target.lower():
            logger.info(
                'Skip check-session Messenger sur %s (serv2 = messagerie plus tard, pas Playwright)',
                target,
            )
            out[role.value] = {'ok': True, 'skipped': True, 'reason': 'serv2_messaging_later'}
            continue
        res = remote.check_session(role)
        out[role.value] = {
            'ok': res.ok,
            'exit_code': res.exit_code,
            'parsed': res.parsed,
        }
        if not res.ok:
            logger.warning('Session Facebook %s KO: %s', role.value, (res.stderr or '')[:300])

    all_ok = bool(out.get('local', {}).get('ok')) or all(
        item.get('ok') for key, item in out.items() if key != 'local' and isinstance(item, dict)
    )
    return {'ok': all_ok, 'hosts': out}
