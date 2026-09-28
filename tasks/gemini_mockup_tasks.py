# -*- coding: utf-8 -*-
"""
Taches Celery : generation de maquettes Gemini (images) depuis un rapport.
"""

from __future__ import annotations

from celery_app import celery
from services.database import Database
from services.gemini_mockup_service import generate_mockups_for_entreprise
from services.logging_config import setup_logger

logger = setup_logger(__name__, 'gemini_mockup_tasks.log')


@celery.task(bind=True, name='gemini_mockups.generate_for_entreprise')
def generate_entreprise_gemini_mockups_task(self, entreprise_id: int):
    """
    Genere des maquettes Gemini pour une entreprise (rapport requis).

    @param entreprise_id: ID entreprise
    @returns: Dict resultat
    """
    eid = int(entreprise_id)
    logs = []

    def _progress(message: str, pct: int = 0) -> None:
        line = str(message or '').strip()
        if line:
            logs.append(line)
        try:
            self.update_state(
                state='PROGRESS',
                meta={
                    'entreprise_id': eid,
                    'progress': int(pct),
                    'message': line,
                    'logs': logs[-60:],
                },
            )
        except Exception:
            pass

    _progress('Demarrage generation maquettes…', 3)
    database = Database()
    result = generate_mockups_for_entreprise(
        database=database,
        entreprise_id=eid,
        progress_cb=_progress,
    )
    if not result.get('success'):
        err = result.get('error') or 'Echec maquettes'
        _progress(err, 100)
        logger.warning('Gemini mockups fail entreprise_id=%s: %s', eid, err)
        return {
            'success': False,
            'entreprise_id': eid,
            'error': err,
            'logs': logs[-60:],
        }

    _progress('Maquettes terminees.', 100)
    logger.info(
        'Gemini mockups done entreprise_id=%s count=%s',
        eid,
        len(result.get('mockups') or []),
    )
    return {
        **result,
        'logs': logs[-60:],
    }
