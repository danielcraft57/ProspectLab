"""
Re-scans techniques / SEO pour générer de nouveaux snapshots métriques (Sprint 3).

La tâche orchestre uniquement l’enqueue des analyses existantes ; l’enregistrement
des snapshots reste dans les hooks d’analyse (technical / SEO).
"""

from __future__ import annotations

import logging

from celery_app import celery
from config import SEO_USE_LIGHTHOUSE_DEFAULT
from services.database import Database
from services.logging_config import setup_logger
from tasks.heavy_schedule import BulkSubtaskStagger
from tasks.seo_tasks import seo_analysis_task
from tasks.technical_analysis_tasks import technical_analysis_task

logger = setup_logger(__name__, 'metric_rescan_tasks.log', level=logging.INFO)


def _normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    u = str(url).strip()
    if not u:
        return None
    if not u.startswith(('http://', 'https://')):
        u = 'https://' + u
    return u


def enqueue_metric_rescan_for_entreprise(
    entreprise_id: int,
    run_technical: bool = True,
    run_seo: bool = True,
    enable_nmap: bool = False,
    use_lighthouse=None,
) -> dict:
    """
    Enfile les analyses technique et/ou SEO (nouveaux snapshots). Utilisable depuis Flask ou Celery.
    """
    database = Database()
    ent = database.get_entreprise(int(entreprise_id))
    if not ent:
        logger.warning('metric_rescan: entreprise %s introuvable', entreprise_id)
        return {'success': False, 'error': 'entreprise_not_found', 'entreprise_id': entreprise_id}

    website = _normalize_website(ent.get('website'))
    if not website:
        logger.warning('metric_rescan: pas de site pour entreprise %s', entreprise_id)
        return {'success': False, 'error': 'no_website', 'entreprise_id': entreprise_id}

    if use_lighthouse is None:
        use_lighthouse = SEO_USE_LIGHTHOUSE_DEFAULT

    eid = int(entreprise_id)
    out: dict = {'success': True, 'entreprise_id': eid, 'website': website, 'tasks': {}}
    st = BulkSubtaskStagger()

    if run_technical:
        try:
            t = technical_analysis_task.apply_async(
                kwargs=dict(url=website, entreprise_id=eid, enable_nmap=bool(enable_nmap)),
                countdown=st.next_countdown(),
                queue='technical',
            )
            out['tasks']['technical_task_id'] = t.id
        except Exception as exc:
            logger.exception('metric_rescan: enqueue technique échoué pour %s', eid)
            out['tasks']['technical_error'] = str(exc)

    if run_seo:
        try:
            t2 = seo_analysis_task.apply_async(
                kwargs=dict(url=website, entreprise_id=eid, use_lighthouse=use_lighthouse),
                countdown=st.next_countdown(),
                queue='seo',
            )
            out['tasks']['seo_task_id'] = t2.id
        except Exception as exc:
            logger.exception('metric_rescan: enqueue SEO échoué pour %s', eid)
            out['tasks']['seo_error'] = str(exc)

    logger.info('metric_rescan entreprise=%s technical=%s seo=%s', eid, run_technical, run_seo)
    return out


@celery.task(bind=True)
def metric_rescan_entreprise_task(
    self,
    entreprise_id: int,
    run_technical: bool = True,
    run_seo: bool = True,
    enable_nmap: bool = False,
    use_lighthouse=None,
):
    """
    Relance analyse technique et/ou SEO pour une entreprise (nouveaux snapshots).

    Args:
        entreprise_id: ID entreprise
        run_technical: enqueue technical_analysis_task
        run_seo: enqueue seo_analysis_task
        enable_nmap: passé à l’analyse technique
        use_lighthouse: défaut SEO_USE_LIGHTHOUSE_DEFAULT si None
    """
    return enqueue_metric_rescan_for_entreprise(
        entreprise_id,
        run_technical=run_technical,
        run_seo=run_seo,
        enable_nmap=enable_nmap,
        use_lighthouse=use_lighthouse,
    )
