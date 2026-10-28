"""
API REST prospection Facebook.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from config import FACEBOOK_PROSPECTION_ENABLED
from services.auth import login_required
from services.database import Database
from services.facebook_prospection.entreprise_payload import (
    build_facebook_search_payload_from_entreprise,
    build_prospect_payload_from_entreprise,
    default_prospect_message,
)
from services.facebook_prospection.job_runner import FacebookProspectionJobRunner
from tasks.facebook_prospection_tasks import facebook_prospection_run_job_task

api_facebook_prospection_bp = Blueprint(
    'api_facebook_prospection',
    __name__,
    url_prefix='/api/facebook-prospection',
)


def _require_enabled():
    if not FACEBOOK_PROSPECTION_ENABLED:
        return jsonify({'success': False, 'error': 'Prospection Facebook desactivee (env).'}), 503
    return None


@api_facebook_prospection_bp.route('/queue', methods=['GET'])
@login_required
def facebook_prospection_queue():
    """Etat global de la file jobs Facebook (pending / running)."""
    blocked = _require_enabled()
    if blocked:
        return blocked
    db = Database()
    return jsonify({'success': True, 'queue': db.get_facebook_prospection_queue_snapshot()})


@api_facebook_prospection_bp.route('/jobs', methods=['POST'])
@login_required
def create_facebook_job():
    """
    Cree un job et l'enfile sur Celery.

    Body JSON : { entreprise_id, job_type, query? }
    """
    blocked = _require_enabled()
    if blocked:
        return blocked

    data = request.get_json(silent=True) or {}
    entreprise_id = data.get('entreprise_id')
    job_type = (data.get('job_type') or 'search').strip()
    query = (data.get('query') or '').strip() or None

    if not entreprise_id:
        return jsonify({'success': False, 'error': 'entreprise_id requis'}), 400
    if job_type not in ('search', 'scrape_page', 'messenger_inbox', 'prospect_flow'):
        return jsonify({'success': False, 'error': 'job_type invalide'}), 400

    meta: dict[str, Any] = {'source': 'api'}
    fb_url = (data.get('fb_url') or '').strip()
    if fb_url:
        meta['fb_url'] = fb_url

    db = Database()
    assigned_node = db.auto_assign_facebook_remote_node(job_type)
    meta['remote_node'] = assigned_node
    job_id = db.create_facebook_prospection_job(
        int(entreprise_id),
        job_type,
        query=query,
        meta=meta,
    )
    queue = db.get_facebook_prospection_queue_snapshot(job_id)
    async_result = facebook_prospection_run_job_task.apply_async(args=[job_id])
    return jsonify(
        {
            'success': True,
            'job_id': job_id,
            'job_type': job_type,
            'celery_task_id': async_result.id,
            'queue': queue,
            'remote_node': assigned_node,
        }
    )


@api_facebook_prospection_bp.route('/jobs/<int:job_id>', methods=['GET'])
@login_required
def get_facebook_job(job_id: int):
    """Detail d'un job + candidats pages si recherche."""
    blocked = _require_enabled()
    if blocked:
        return blocked

    db = Database()
    job = db.get_facebook_prospection_job(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Job introuvable'}), 404
    candidates = db.list_facebook_page_candidates(job_id)
    fb_page = None
    ent_id = job.get('entreprise_id')
    if ent_id:
        fb_page = db.get_facebook_prospection_selected_page(int(ent_id))
    return jsonify(
        {
            'success': True,
            'job': job,
            'candidates': candidates,
            'facebook_page': fb_page,
        }
    )


@api_facebook_prospection_bp.route('/jobs/<int:job_id>/retry', methods=['POST'])
@login_required
def retry_facebook_job(job_id: int):
    """
    Relance un job encore en file ou en echec (Celery n'a pas mis a jour la BDD).

    @param job_id: ID facebook_prospection_jobs
    """
    blocked = _require_enabled()
    if blocked:
        return blocked

    db = Database()
    job = db.get_facebook_prospection_job(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Job introuvable'}), 404
    status = str(job.get('status') or '').lower()
    if status not in ('pending', 'failed'):
        return jsonify(
            {
                'success': False,
                'error': f'Relance impossible (statut {status})',
            }
        ), 409
    db.update_facebook_prospection_job_status(job_id, 'pending', error_message=None)
    async_result = facebook_prospection_run_job_task.apply_async(args=[job_id])
    return jsonify(
        {
            'success': True,
            'job_id': job_id,
            'job_type': job.get('job_type'),
            'celery_task_id': async_result.id,
        }
    )


@api_facebook_prospection_bp.route('/search-sync', methods=['POST'])
@login_required
def search_facebook_sync():
    """
    Recherche pages Facebook en synchrone (tests / debug, runner local prioritaire).

    Body : { query, target_name?, entreprise_id? }
    """
    blocked = _require_enabled()
    if blocked:
        return blocked

    data = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip()
    target_name = (data.get('target_name') or '').strip() or None
    entreprise_id = data.get('entreprise_id')

    db = Database()
    ent = None
    if entreprise_id:
        ent = db.get_entreprise(int(entreprise_id))
        if ent and not query:
            query = (ent.get('nom') or ent.get('name') or '').strip()
            target_name = target_name or query
    if not query:
        return jsonify({'success': False, 'error': 'query ou entreprise_id requis'}), 400

    if ent:
        payload = build_facebook_search_payload_from_entreprise(ent, db=db)
        if target_name:
            payload['target_name'] = target_name
    else:
        payload = {'query': query, 'target_name': target_name}
    result = FacebookProspectionJobRunner().run('search', payload, force_remote=True)
    saved_url = None
    if entreprise_id and isinstance(result, dict):
        picked = db.persist_facebook_page_from_job(
            int(entreprise_id),
            0,
            'search',
            result,
        )
        if picked:
            saved_url = picked.get('url')
    return jsonify(
        {
            'success': bool(result.get('ok')),
            'result': result,
            'facebook_page_url': saved_url,
        }
    )


@api_facebook_prospection_bp.route('/entreprise/<int:entreprise_id>/jobs', methods=['GET'])
@login_required
def list_facebook_jobs(entreprise_id: int):
    """Historique des jobs pour une entreprise."""
    blocked = _require_enabled()
    if blocked:
        return blocked

    db = Database()
    jobs = db.list_facebook_prospection_jobs(entreprise_id)
    fb_page = db.get_facebook_prospection_selected_page(entreprise_id)
    ent = db.get_entreprise(entreprise_id)
    return jsonify(
        {
            'success': True,
            'jobs': jobs,
            'facebook_page': fb_page,
            'facebook_page_url': (ent or {}).get('facebook_page_url'),
        }
    )


@api_facebook_prospection_bp.route('/entreprise/<int:entreprise_id>/page', methods=['GET'])
@login_required
def get_entreprise_facebook_page(entreprise_id: int):
    """Lien page Facebook retenue pour une entreprise."""
    blocked = _require_enabled()
    if blocked:
        return blocked

    db = Database()
    ent = db.get_entreprise(entreprise_id)
    if not ent:
        return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404
    fb_page = db.get_facebook_prospection_selected_page(entreprise_id)
    conversations = db.list_facebook_prospection_conversations(entreprise_id, limit=5)
    return jsonify(
        {
            'success': True,
            'facebook_page_url': ent.get('facebook_page_url'),
            'facebook_page': fb_page,
            'conversations': conversations,
        }
    )


@api_facebook_prospection_bp.route(
    '/entreprise/<int:entreprise_id>/conversations/<int:conversation_id>/messages',
    methods=['GET'],
)
@login_required
def list_facebook_conversation_messages(entreprise_id: int, conversation_id: int):
    """Messages enregistres d'un fil Messenger."""
    blocked = _require_enabled()
    if blocked:
        return blocked

    db = Database()
    convs = db.list_facebook_prospection_conversations(entreprise_id, limit=100)
    if not any(int(c.get('id') or 0) == conversation_id for c in convs):
        return jsonify({'success': False, 'error': 'Conversation introuvable'}), 404
    messages = db.list_facebook_prospection_messages(conversation_id)
    return jsonify({'success': True, 'messages': messages})


@api_facebook_prospection_bp.route('/entreprise/<int:entreprise_id>/prospect', methods=['POST'])
@login_required
def prospect_entreprise_facebook(entreprise_id: int):
    """
    Flux complet serv1 : recherche page (score adresse), suivre, ouvrir Messenger.

    Body JSON : { send?: bool, message_text?: str }
    Par defaut send=false (dry-run : suit + compose sans envoyer).
    """
    blocked = _require_enabled()
    if blocked:
        return blocked

    db = Database()
    ent = db.get_entreprise(entreprise_id)
    if not ent:
        return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404

    data = request.get_json(silent=True) or {}
    send = bool(data.get('send'))
    message_text = (data.get('message_text') or '').strip() or None
    nom = (ent.get('nom') or ent.get('name') or '').strip()

    meta: dict = {'source': 'api_prospect', 'send': send}
    if message_text:
        meta['message_text'] = message_text

    assigned_node = db.auto_assign_facebook_remote_node('prospect_flow')
    meta['remote_node'] = assigned_node

    job_id = db.create_facebook_prospection_job(
        int(entreprise_id),
        'prospect_flow',
        query=nom or None,
        meta=meta,
    )
    queue = db.get_facebook_prospection_queue_snapshot(job_id)
    async_result = facebook_prospection_run_job_task.apply_async(args=[job_id])
    preview = build_prospect_payload_from_entreprise(
        ent,
        message_text=message_text,
        send=send,
        db=db,
    )
    return jsonify(
        {
            'success': True,
            'job_id': job_id,
            'celery_task_id': async_result.id,
            'send': send,
            'queue': queue,
            'remote_node': assigned_node,
            'message_preview': preview.get('message_text') or default_prospect_message(nom),
            'address_hint': preview.get('address_hint'),
        }
    )
