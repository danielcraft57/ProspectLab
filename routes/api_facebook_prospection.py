"""
API REST prospection Facebook.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from config import FACEBOOK_PROSPECTION_ENABLED
from services.auth import login_required
from services.database import Database
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
    if job_type not in ('search', 'scrape_page', 'messenger_inbox'):
        return jsonify({'success': False, 'error': 'job_type invalide'}), 400

    db = Database()
    job_id = db.create_facebook_prospection_job(
        int(entreprise_id),
        job_type,
        query=query,
        meta={'source': 'api'},
    )
    async_result = facebook_prospection_run_job_task.apply_async(args=[job_id])
    return jsonify(
        {
            'success': True,
            'job_id': job_id,
            'celery_task_id': async_result.id,
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
    return jsonify({'success': True, 'job': job, 'candidates': candidates})


@api_facebook_prospection_bp.route('/entreprise/<int:entreprise_id>/jobs', methods=['GET'])
@login_required
def list_facebook_jobs(entreprise_id: int):
    """Historique des jobs pour une entreprise."""
    blocked = _require_enabled()
    if blocked:
        return blocked

    db = Database()
    jobs = db.list_facebook_prospection_jobs(entreprise_id)
    return jsonify({'success': True, 'jobs': jobs})
