"""
API REST prospection Facebook.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from config import FACEBOOK_PROSPECTION_ENABLED, FACEBOOK_MESSENGER_SYNC_MAX_THREADS
from services.auth import login_required
from services.database import Database
from services.facebook_prospection.entreprise_payload import (
    build_facebook_search_payload_from_entreprise,
    build_prospect_payload_from_entreprise,
    default_prospect_message,
)
from services.facebook_prospection.job_runner import FacebookProspectionJobRunner
from tasks.facebook_prospection_tasks import (
    facebook_messenger_reply_task,
    facebook_messenger_sync_inbox_task,
    facebook_prospection_run_job_task,
)
from services.facebook_prospection.messenger_qa import answer_user_turn, kb_status
from services.facebook_prospection.messenger_suggestions import build_reply_suggestions
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
    if job_type not in (
        'search',
        'scrape_page',
        'messenger_inbox',
        'messenger_sync',
        'messenger_reply',
        'prospect_flow',
    ):
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


@api_facebook_prospection_bp.route('/messenger/summary', methods=['GET'])
@login_required
def facebook_messenger_summary():
    """Compteurs non lus pour notifications UI."""
    blocked = _require_enabled()
    if blocked:
        return blocked
    db = Database()
    summary = db.get_facebook_messenger_summary()
    latest = db.list_facebook_messenger_threads(unread_only=True, limit=5)
    return jsonify({'success': True, 'summary': summary, 'latest_unread': latest})


@api_facebook_prospection_bp.route('/messenger/conversations', methods=['GET'])
@login_required
def facebook_messenger_conversations():
    """
    Liste des fils synchronises.

    Query : entreprise_id?, unread_only=1
    """
    blocked = _require_enabled()
    if blocked:
        return blocked
    db = Database()
    ent_raw = request.args.get('entreprise_id')
    entreprise_id = int(ent_raw) if ent_raw and str(ent_raw).isdigit() else None
    unread_only = request.args.get('unread_only', '').lower() in ('1', 'true', 'yes')
    limit = min(100, max(1, int(request.args.get('limit', 40) or 40)))
    threads = db.list_facebook_messenger_threads(
        entreprise_id=entreprise_id,
        unread_only=unread_only,
        limit=limit,
    )
    return jsonify({'success': True, 'threads': threads})


@api_facebook_prospection_bp.route('/messenger/conversations/<int:thread_id>/messages', methods=['GET'])
@login_required
def facebook_messenger_thread_messages(thread_id: int):
    """Messages d'un fil Messenger synchronise."""
    blocked = _require_enabled()
    if blocked:
        return blocked
    db = Database()
    messages = db.list_facebook_messenger_messages(thread_id)
    if not messages:
        threads = db.list_facebook_messenger_threads(limit=500)
        if not any(int(t.get('id') or 0) == thread_id for t in threads):
            return jsonify({'success': False, 'error': 'Fil introuvable'}), 404
    return jsonify({'success': True, 'messages': messages})


@api_facebook_prospection_bp.route('/messenger/conversations/<int:thread_id>/read', methods=['POST'])
@login_required
def facebook_messenger_mark_read(thread_id: int):
    """Marque un fil comme lu dans ProspectLab."""
    blocked = _require_enabled()
    if blocked:
        return blocked
    db = Database()
    if not db.mark_facebook_messenger_thread_read(thread_id):
        return jsonify({'success': False, 'error': 'Fil introuvable'}), 404
    return jsonify({'success': True, 'thread_id': thread_id})


@api_facebook_prospection_bp.route('/tchatche/status', methods=['GET'])
@login_required
def facebook_tchatche_status():
    """Etat Qdrant + config tchatche (pas besoin du flag Facebook)."""
    info = kb_status()
    return jsonify({'success': True, **info})


@api_facebook_prospection_bp.route('/tchatche', methods=['POST'])
@login_required
def facebook_tchatche_turn():
    """
    Un tour de tchatche virtuel (KB Messenger / Qdrant).

    Body : { text, recent_replies?, recent_tags?, recent_user_texts?, top_k?, entreprise_id? }
    """
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'success': False, 'error': 'text requis'}), 400
    entreprise_id = data.get('entreprise_id')
    try:
        entreprise_id = int(entreprise_id) if entreprise_id else None
    except (TypeError, ValueError):
        entreprise_id = None
    turn = answer_user_turn(
        text,
        recent_replies=list(data.get('recent_replies') or []),
        recent_tags=list(data.get('recent_tags') or []),
        recent_user_texts=list(data.get('recent_user_texts') or []),
        top_k=int(data.get('top_k') or 8),
        profile=str(data.get('profile') or '').strip() or None,
        entreprise_id=entreprise_id,
    )
    return jsonify({'success': True, **turn})


@api_facebook_prospection_bp.route('/tchatche/entreprises', methods=['GET'])
@login_required
def facebook_tchatche_entreprises():
    """
    Recherche d'entreprises pour personnaliser le tchatche.

    Query : q (texte), limit (defaut 12)
    """
    q = (request.args.get('q') or request.args.get('search') or '').strip()
    try:
        limit = max(1, min(30, int(request.args.get('limit') or 12)))
    except (TypeError, ValueError):
        limit = 12
    db = Database()
    filters = {'search': q} if q else None
    rows = db.get_entreprises(
        filters=filters,
        limit=limit,
        include_og=False,
    ) or []
    items = []
    for row in rows:
        items.append(
            {
                'id': row.get('id'),
                'nom': row.get('nom'),
                'ville': row.get('ville'),
                'website': row.get('website'),
            }
        )
    return jsonify({'success': True, 'items': items})


@api_facebook_prospection_bp.route('/messenger/conversations/<int:thread_id>/suggestions', methods=['POST'])
@login_required
def facebook_messenger_suggestions(thread_id: int):
    """
    Propositions de reponse (Qdrant) pour un fil.

    Body JSON optionnel : { text?: str } sinon dernier inbound en base
    """
    blocked = _require_enabled()
    if blocked:
        return blocked
    db = Database()
    thread = db.get_facebook_messenger_thread(thread_id)
    if not thread:
        return jsonify({'success': False, 'error': 'Fil introuvable'}), 404

    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        last = db.get_last_inbound_facebook_messenger_message(thread_id)
        text = (last.get('body_text') if last else '') or (thread.get('preview') or '')

    suggestions = build_reply_suggestions(
        text,
        contact_name=thread.get('contact_name'),
        entreprise_id=thread.get('entreprise_id'),
        limit=int(data.get('limit') or 5),
    )
    return jsonify(
        {
            'success': True,
            'query': text[:500],
            'suggestions': suggestions,
            'qdrant': bool(suggestions) or bool((thread.get('preview') or text).strip()),
        }
    )


@api_facebook_prospection_bp.route('/messenger/conversations/<int:thread_id>/reply', methods=['POST'])
@login_required
def facebook_messenger_send_reply(thread_id: int):
    """
    Compose / envoie une reponse Messenger sur serv1.

    Body : { message_text, send?: bool, async?: bool }
    """
    blocked = _require_enabled()
    if blocked:
        return blocked

    data = request.get_json(silent=True) or {}
    message_text = (data.get('message_text') or '').strip()
    if not message_text:
        return jsonify({'success': False, 'error': 'message_text requis'}), 400
    send = bool(data.get('send'))
    use_async = data.get('async', True)

    db = Database()
    thread = db.get_facebook_messenger_thread(thread_id)
    if not thread:
        return jsonify({'success': False, 'error': 'Fil introuvable'}), 404

    if use_async:
        async_result = facebook_messenger_reply_task.apply_async(
            kwargs={
                'thread_id': int(thread_id),
                'message_text': message_text,
                'send': send,
            }
        )
        return jsonify(
            {
                'success': True,
                'celery_task_id': async_result.id,
                'send': send,
                'thread_id': thread_id,
            }
        )

    from services.facebook_prospection.messenger_reply import execute_messenger_reply

    result = execute_messenger_reply(db, thread_id, message_text, send=send)
    ok = bool(result.get('ok'))
    return jsonify({'success': ok, 'result': result}), (200 if ok else 502)


@api_facebook_prospection_bp.route('/messenger/sync', methods=['POST'])
@login_required
def facebook_messenger_sync():
    """
    Enfile une sync inbox (lecture seule serv1).

    Body JSON optionnel : { entreprise_id?, max_threads?, async?: true }
    """
    blocked = _require_enabled()
    if blocked:
        return blocked

    data = request.get_json(silent=True) or {}
    max_threads = data.get('max_threads') or FACEBOOK_MESSENGER_SYNC_MAX_THREADS
    use_async = data.get('async', True)
    entreprise_id = data.get('entreprise_id')

    if use_async:
        db = Database()
        if entreprise_id:
            meta: dict[str, Any] = {
                'source': 'api_messenger_sync',
                'max_threads': int(max_threads),
                'headless': False,
            }
            assigned_node = db.auto_assign_facebook_remote_node('messenger_sync')
            meta['remote_node'] = assigned_node
            job_id = db.create_facebook_prospection_job(
                int(entreprise_id),
                'messenger_sync',
                meta=meta,
            )
            queue = db.get_facebook_prospection_queue_snapshot(job_id)
            async_result = facebook_prospection_run_job_task.apply_async(args=[job_id])
            return jsonify(
                {
                    'success': True,
                    'job_id': job_id,
                    'job_type': 'messenger_sync',
                    'celery_task_id': async_result.id,
                    'queue': queue,
                    'remote_node': assigned_node,
                }
            )
        async_result = facebook_messenger_sync_inbox_task.apply_async(
            kwargs={'max_threads': int(max_threads)}
        )
        return jsonify(
            {
                'success': True,
                'job_type': 'messenger_sync',
                'celery_task_id': async_result.id,
                'async': True,
            }
        )

    from tasks.facebook_prospection_tasks import run_facebook_messenger_sync

    stats = run_facebook_messenger_sync(int(max_threads))
    ok = bool(stats.get('ok'))
    code = 200 if ok else 502
    return jsonify({'success': ok, 'sync': stats}), code


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
