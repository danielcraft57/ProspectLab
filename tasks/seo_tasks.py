"""
Tâches Celery pour les analyses SEO

Ces tâches permettent d'exécuter les analyses SEO de manière asynchrone,
avec sauvegarde automatique dans la base de données et logs dédiés.
"""

from celery_app import celery
from services.seo_analyzer import SEOAnalyzer
from services.database import Database
from services.logging_config import setup_logger
import logging

# Configurer le logger pour cette tâche avec un fichier dédié
logger = setup_logger(__name__, 'seo_tasks.log', level=logging.INFO)


@celery.task(bind=True)
def seo_analysis_task(self, url, entreprise_id=None, use_lighthouse=True):
    """
    Tâche Celery pour effectuer une analyse SEO d'un site web
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        url (str): URL du site à analyser
        entreprise_id (int, optional): ID de l'entreprise associée
        use_lighthouse (bool): Utiliser Lighthouse si disponible
        
    Returns:
        dict: Résultats de l'analyse SEO avec analysis_id
        
    Example:
        >>> result = seo_analysis_task.delay('https://example.com', entreprise_id=1)
    """
    try:
        logger.info(f'Démarrage analyse SEO pour {url} (entreprise_id={entreprise_id})')
        
        database = Database()
        
        # Vérifier si une analyse existe déjà
        existing = database.get_seo_analysis_by_url(url)
        if existing:
            logger.debug(f'Analyse SEO existante pour {url} (id={existing.get("id")})')
            # Si une analyse existe et qu'on a un entreprise_id, mettre à jour le lien
            if entreprise_id and existing.get('entreprise_id') != entreprise_id:
                conn = database.get_connection()
                cursor = conn.cursor()
                database.execute_sql(cursor, 'UPDATE analyses_seo SET entreprise_id = ? WHERE id = ?', (entreprise_id, existing['id']))
                conn.commit()
                conn.close()
                logger.debug(f'Analyse SEO mise à jour avec entreprise_id={entreprise_id}')
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 5, 'message': 'Initialisation de l\'analyse SEO...'}
        )
        
        analyzer = SEOAnalyzer()
        try:
            diag = analyzer.get_diagnostic()
            logger.info(f'Diagnostic SEO: {diag.get("message", "")} (outils={len(diag.get("tools_available", []))})')
        except Exception as e:
            logger.debug(f'Diagnostic SEO: {e}')
        
        # Callback pour mettre à jour la progression
        current_progress = 5
        def progress_update(message):
            nonlocal current_progress
            current_progress = min(current_progress + 10, 95)
            self.update_state(
                state='PROGRESS',
                meta={'progress': current_progress, 'message': message}
            )
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Démarrage de l\'analyse SEO...'}
        )
        
        # Lancer l'analyse SEO
        seo_data = analyzer.analyze_seo(
            url,
            progress_callback=progress_update,
            use_lighthouse=use_lighthouse
        )
        
        if seo_data.get('error'):
            logger.error(f'Erreur analyse SEO pour {url}: {seo_data["error"]}')
            raise Exception(seo_data['error'])
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 90, 'message': 'Sauvegarde des résultats...'}
        )
        
        # Sauvegarder ou mettre à jour dans la base de données
        if existing:
            analysis_id = database.update_seo_analysis(existing['id'], seo_data)
        else:
            analysis_id = database.save_seo_analysis(entreprise_id, url, seo_data)
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Analyse SEO terminée!'}
        )
        
        logger.info(f'Analyse SEO terminée pour {url} (id={analysis_id})')
        
        return {
            'success': True,
            'url': url,
            'entreprise_id': entreprise_id,
            'analysis_id': analysis_id,
            'summary': seo_data.get('summary', {}),
            'score': seo_data.get('score', 0),
            'updated': existing is not None
        }
        
    except Exception as e:
        logger.error(f'Erreur analyse SEO pour {url}: {e}', exc_info=True)
        raise
