"""
Taches Celery : rapport d'audit complet Gemini (screenshots + modules).
"""

from __future__ import annotations

from typing import List, Optional

from celery_app import celery
from services.database import Database
from services.gemini_full_report_service import build_full_report_for_entreprise
from services.logging_config import setup_logger

logger = setup_logger(__name__, 'gemini_full_report_tasks.log')


@celery.task(bind=True, name='gemini_full_report.analyze_entreprise')
def analyze_entreprise_gemini_full_report_task(
    self,
    entreprise_id: int,
    ensure_screenshots: bool = True,
):
    """
    Genere et persiste un rapport Gemini complet pour une entreprise.

    Capture les screenshots s'ils manquent (ou fichiers absents), puis
    injecte tech / SEO / OSINT / pentest + images dans Gemini Vision.

    @param self: Instance Celery
    @param entreprise_id: ID entreprise
    @param ensure_screenshots: True pour capturer si besoin
    @returns: Dict resultat
    """
    database = Database()
    eid = int(entreprise_id)
    logs: List[str] = []

    def _progress(message: str, pct: Optional[int] = None) -> None:
        """Pousse un message dans le journal PROGRESS (visible cote UI)."""
        msg = str(message or '').strip()
        if not msg:
            return
        if not logs or logs[-1] != msg:
            logs.append(msg)
            logger.info('[gemini-report %s] %s', eid, msg)
        try:
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': int(pct) if pct is not None else min(95, 5 + len(logs) * 3),
                    'step': 'analyze',
                    'message': msg,
                    'logs': logs[-60:],
                },
            )
        except Exception:
            pass

    _progress('Demarrage rapport Gemini…', 3)

    try:
        result = build_full_report_for_entreprise(
            database,
            eid,
            ensure_screenshots=bool(ensure_screenshots),
            progress_cb=_progress,
        )
    except Exception as exc:
        logger.exception('gemini full report task failed entreprise_id=%s', eid)
        _progress(f'Erreur fatale: {exc}', 100)
        try:
            database.save_entreprise_gemini_report(
                entreprise_id=eid,
                status='failed',
                error_message=str(exc)[:2000],
                source='error',
            )
        except Exception:
            pass
        return {
            'success': False,
            'entreprise_id': eid,
            'error': str(exc),
            'logs': logs[-60:],
        }

    if not result.get('success'):
        err = result.get('error') or 'Echec rapport'
        _progress(f'Echec: {err}', 100)
        try:
            database.save_entreprise_gemini_report(
                entreprise_id=eid,
                status='failed',
                error_message=str(err)[:2000],
                source='error',
            )
        except Exception:
            pass
        return {**result, 'logs': logs[-60:]}

    _progress('Persistance du rapport en base…', 96)
    report = result.get('report') or {}
    report_id = database.save_entreprise_gemini_report(
        entreprise_id=eid,
        report=report,
        overall_score=result.get('overall_score'),
        refonte_recommendation=result.get('refonte_recommendation'),
        source=result.get('source'),
        status='done',
        modules_used=result.get('modules_used'),
        screenshot_set_id=result.get('screenshot_set_id'),
        analyzed_at=result.get('analyzed_at'),
    )
    _progress(f'Rapport enregistre (id={report_id})', 98)

    # Tag commercial si refonte forte
    try:
        refonte = str(result.get('refonte_recommendation') or '')
        if refonte in ('partielle', 'totale') and hasattr(database, 'add_entreprise_tag'):
            database.add_entreprise_tag(eid, 'fort_potentiel_refonte')
            _progress('Tag fort_potentiel_refonte pose', 99)
        elif refonte in ('partielle', 'totale'):
            ent = database.get_entreprise(eid) or {}
            tags = list(ent.get('tags') or [])
            if 'fort_potentiel_refonte' not in tags:
                tags.append('fort_potentiel_refonte')
                if hasattr(database, 'update_entreprise_tags'):
                    database.update_entreprise_tags(eid, tags)
                    _progress('Tag fort_potentiel_refonte pose', 99)
    except Exception as tag_exc:
        logger.warning('Tag fort_potentiel_refonte non pose: %s', tag_exc)
        _progress(f'Tag refonte non pose: {tag_exc}', 99)

    _progress('Rapport termine.', 100)
    logger.info(
        'Gemini full report done entreprise_id=%s report_id=%s score=%s source=%s',
        eid,
        report_id,
        result.get('overall_score'),
        result.get('source'),
    )
    return {
        'success': True,
        'entreprise_id': eid,
        'report_id': report_id,
        'overall_score': result.get('overall_score'),
        'refonte_recommendation': result.get('refonte_recommendation'),
        'source': result.get('source'),
        'report': report,
        'screenshot_set_id': result.get('screenshot_set_id'),
        'modules_used': result.get('modules_used'),
        'analyzed_at': result.get('analyzed_at'),
        'logs': logs[-60:],
    }
