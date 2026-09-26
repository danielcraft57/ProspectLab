"""
Taches Celery : analyse design UX/UI des screenshots (Gemini Vision).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from celery_app import celery
from services.database import Database
from services.design_review_service import (
    analyze_screenshot_design,
    serialize_design_review,
)
from services.logging_config import setup_logger

logger = setup_logger(__name__, 'design_review_tasks.log')


@celery.task(bind=True, name='design_review.analyze_screenshot_design')
def analyze_screenshot_design_task(
    self,
    entreprise_id: int,
    screenshot_set_id: Optional[int] = None,
):
    """
    Analyse le design du dernier (ou d'un) set de screenshots d'une entreprise.

    @param self: Instance Celery (bind)
    @param entreprise_id: ID entreprise
    @param screenshot_set_id: ID set optionnel (sinon latest)
    @returns: Dict resultat
    """
    database = Database()
    eid = int(entreprise_id)

    self.update_state(
        state='PROGRESS',
        meta={'progress': 10, 'step': 'load', 'message': 'Chargement screenshot…'},
    )

    row = None
    if screenshot_set_id:
        rows = database.list_entreprise_screenshots(eid, limit=50)
        for r in rows or []:
            if int(r.get('id') or 0) == int(screenshot_set_id):
                row = r
                break
    if not row:
        latest = database.get_latest_entreprise_screenshots(eid)
        if not latest or not latest.get('id'):
            return {
                'success': False,
                'error': 'Aucun screenshot disponible',
                'entreprise_id': eid,
            }
        # Recharger la ligne complete (chemins fichiers)
        rows = database.list_entreprise_screenshots(eid, limit=1)
        row = rows[0] if rows else None
        if not row:
            return {
                'success': False,
                'error': 'Aucun screenshot disponible',
                'entreprise_id': eid,
            }

    set_id = int(row.get('id'))
    file_path = (
        row.get('desktop_file_path')
        or row.get('tablet_file_path')
        or row.get('mobile_file_path')
    )
    if not file_path or not Path(str(file_path)).is_file():
        return {
            'success': False,
            'error': 'Fichier screenshot introuvable sur le disque',
            'entreprise_id': eid,
            'screenshot_set_id': set_id,
        }

    entreprise = database.get_entreprise(eid) or {}
    self.update_state(
        state='PROGRESS',
        meta={'progress': 40, 'step': 'analyze', 'message': 'Analyse design en cours…'},
    )

    result = analyze_screenshot_design(
        image_path=str(file_path),
        page_url=row.get('page_url') or entreprise.get('website'),
        site_age_score=entreprise.get('site_age_score'),
        site_indicators=entreprise.get('site_indicators'),
        http_last_modified=entreprise.get('http_last_modified'),
        tags=entreprise.get('tags') if isinstance(entreprise.get('tags'), list) else None,
    )

    database.update_entreprise_screenshot_design(
        screenshot_set_id=set_id,
        design_review_json=serialize_design_review(result.get('design_review')),
        design_score=result.get('design_score'),
        design_source=result.get('design_source'),
        design_analyzed_at=result.get('design_analyzed_at'),
    )

    self.update_state(
        state='PROGRESS',
        meta={'progress': 100, 'step': 'done', 'message': 'Analyse design terminee.'},
    )
    logger.info(
        'Design review done entreprise_id=%s set_id=%s score=%s source=%s',
        eid,
        set_id,
        result.get('design_score'),
        result.get('design_source'),
    )
    return {
        'success': True,
        'entreprise_id': eid,
        'screenshot_set_id': set_id,
        'design_score': result.get('design_score'),
        'design_source': result.get('design_source'),
        'design_review': result.get('design_review'),
        'design_analyzed_at': result.get('design_analyzed_at'),
    }
