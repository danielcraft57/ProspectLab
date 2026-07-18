"""
Tâches Celery pour les analyses UX (@clea_ux).
"""

from celery_app import celery
from services.ux_analyzer import UXAnalyzer
from services.database import Database
from services.logging_config import setup_logger

logger = setup_logger(__name__, 'ux_tasks.log')


@celery.task(bind=True)
def ux_analysis_task(self, url, entreprise_id=None, options=None):
    """
    Tâche Celery : analyse UX d'un site (heuristiques + corpus transcripts).

    @param self: Instance tâche Celery.
    @param url: URL du site.
    @param entreprise_id: ID entreprise optionnel.
    @param options: Dict outil -> bool (optionnel).
    @returns: Dict success, analysis_id, score, summary.
    @example
        >>> ux_analysis_task.delay('https://example.com', entreprise_id=1)
    """
    try:
        logger.info(
            'Démarrage analyse UX pour %s (entreprise_id=%s)',
            url,
            entreprise_id,
        )
        database = Database()

        existing = database.get_ux_analysis_by_url(url)
        if existing and entreprise_id and existing.get('entreprise_id') != entreprise_id:
            conn = database.get_connection()
            cursor = conn.cursor()
            database.execute_sql(
                cursor,
                'UPDATE analyses_ux SET entreprise_id = ? WHERE id = ?',
                (entreprise_id, existing['id']),
            )
            conn.commit()
            conn.close()

        self.update_state(
            state='PROGRESS',
            meta={'progress': 5, 'message': "Initialisation de l'analyse UX…"},
        )

        analyzer = UXAnalyzer()
        try:
            diag = analyzer.get_diagnostic()
            logger.info(
                'Diagnostic UX: %s (outils=%s, transcripts=%s)',
                diag.get('message'),
                len(diag.get('tools_available') or []),
                (diag.get('corpus') or {}).get('transcript_count'),
            )
        except Exception as e:
            logger.debug('Diagnostic UX: %s', e)

        current_progress = 5

        def progress_update(message):
            nonlocal current_progress
            current_progress = min(current_progress + 3, 90)
            self.update_state(
                state='PROGRESS',
                meta={'progress': current_progress, 'message': message},
            )

        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': "Démarrage de l'analyse UX…"},
        )

        ux_data = analyzer.analyze_ux(
            url,
            options=options,
            progress_callback=progress_update,
        )

        if ux_data.get('error'):
            logger.error('Erreur analyse UX pour %s: %s', url, ux_data['error'])
            raise Exception(ux_data['error'])

        self.update_state(
            state='PROGRESS',
            meta={'progress': 92, 'message': 'Sauvegarde des résultats UX…'},
        )

        if existing:
            analysis_id = database.update_ux_analysis(existing['id'], ux_data)
        else:
            analysis_id = database.save_ux_analysis(entreprise_id, url, ux_data)

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Analyse UX terminée !'},
        )

        logger.info('Analyse UX terminée pour %s (id=%s)', url, analysis_id)
        return {
            'success': True,
            'url': url,
            'entreprise_id': entreprise_id,
            'analysis_id': analysis_id,
            'score': ux_data.get('score', 0),
            'summary': ux_data.get('summary', {}),
            'findings_count': len(ux_data.get('findings') or []),
            'updated': existing is not None,
        }
    except Exception as e:
        logger.error('Erreur analyse UX pour %s: %s', url, e, exc_info=True)
        raise
