"""
Tâches Celery pour les analyses techniques

Ces tâches permettent d'exécuter les analyses techniques de manière asynchrone,
avec sauvegarde automatique dans la base de données.

Note: Les tâches Pentest sont dans tasks/pentest_tasks.py
"""

from celery_app import celery
from services.technical_analyzer import TechnicalAnalyzer
from services.database import Database
from services.logging_config import setup_logger
from utils.url_utils import normalize_url_for_analysis
import logging

# Configurer le logger pour cette tâche (niveau INFO pour limiter le bruit)
logger = setup_logger(__name__, 'technical_analysis_tasks.log', level=logging.INFO)


@celery.task(bind=True)
def technical_analysis_task(self, url, entreprise_id=None, enable_nmap=False):
    """
    Tâche Celery pour effectuer une analyse technique complète d'un site web
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        url (str): URL du site à analyser
        entreprise_id (int, optional): ID de l'entreprise associée
        enable_nmap (bool, optional): Activer le scan Nmap (plus long)
        
    Returns:
        dict: Résultats de l'analyse technique avec analysis_id
        
    Example:
        >>> result = technical_analysis_task.delay('https://example.com', entreprise_id=1)
    """
    try:
        input_url = url
        url = normalize_url_for_analysis(url) or url
        if url != input_url:
            logger.info('Analyse technique: URL resolue %s -> %s', input_url, url)

        logger.info(f'Demarrage de l analyse technique pour {url} (entreprise_id={entreprise_id}, enable_nmap={enable_nmap})')
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Initialisation de l\'analyse technique...'}
        )
        
        analyzer = TechnicalAnalyzer()
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 30, 'message': 'Analyse en cours...'}
        )
        
        # Analyse technique complète (réduire à 5 pages pour accélérer, max_depth=1)
        results = analyzer.analyze_site_overview(url, max_pages=5, max_depth=1, enable_nmap=enable_nmap)
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 80, 'message': 'Sauvegarde des résultats...'}
        )
        
        # Sauvegarder dans la base de données (même sans entreprise_id)
        database = Database()
        analysis_id = None
        
        try:
            analysis_id = database.save_technical_analysis(entreprise_id, url, results)
            if entreprise_id:
                logger.info(f'Analyse technique sauvegardee (id={analysis_id}) pour {url} (entreprise_id={entreprise_id})')
            else:
                logger.info(f'Analyse technique sauvegardee (id={analysis_id}) pour {url} (sans entreprise)')
        except Exception as e:
            logger.error(f'Erreur lors de la sauvegarde de l analyse technique pour {url}: {str(e)}', exc_info=True)
            raise
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Analyse technique terminée!'}
        )
        
        return {
            'success': True,
            'url': url,
            'entreprise_id': entreprise_id,
            'analysis_id': analysis_id,
            'results': results
        }
        
    except Exception as e:
        logger.error(f'Erreur lors de l analyse technique de {url}: {e}', exc_info=True)
        raise


@celery.task(bind=True)
def advanced_technical_analysis_task(self, url):
    """
    Analyse technique avancée (SSL, robots.txt, services tiers).
    """
    try:
        input_url = url
        nav_url = normalize_url_for_analysis(url) or url
        if nav_url != input_url:
            logger.info('Analyse technique avancee: URL resolue %s -> %s', input_url, nav_url)

        self.update_state(state='PROGRESS', meta={'progress': 5, 'message': 'Analyse SSL...'})
        parsed = nav_url if nav_url.startswith(('http://', 'https://')) else f'https://{nav_url}'
        domain = parsed.split('//', 1)[1].split('/')[0]
        ssl_info = analyze_ssl_certificate(domain)

        self.update_state(state='PROGRESS', meta={'progress': 40, 'message': 'Analyse robots.txt...'})
        robots_info = analyze_robots_txt(parsed)

        self.update_state(state='PROGRESS', meta={'progress': 70, 'message': 'Analyse services tiers...'})
        services_info = {}
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(parsed, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                services_info = detect_third_party_services(soup, resp.text)
        except Exception as e:
            services_info = {'error': str(e)}

        self.update_state(state='PROGRESS', meta={'progress': 100, 'message': 'Analyse avancée terminée'})

        return {
            'success': True,
            'url': url,
            'ssl': ssl_info,
            'robots': robots_info,
            'services': services_info
        }
    except Exception as e:
        logger.error(f'Erreur analyse technique avancée {url}: {e}', exc_info=True)
        raise

