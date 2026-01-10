"""
Tâches Celery pour l'analyse technique avancée
Utilise TechnicalAnalyzerAdvanced et sauvegarde en base si un entreprise_id est fourni.
"""

from celery_app import celery
from services.database import Database
from services import technical_analyzer_advanced as taa
from services.logging_config import setup_logger
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Configurer le logger pour cette tâche
logger = setup_logger(__name__, 'technical_advanced_tasks.log', level=logging.DEBUG)


@celery.task(bind=True)
def technical_advanced_analysis_task(self, url, entreprise_id=None):
    """
    Analyse technique avancée d'un site web.
    Agrège les fonctions disponibles dans technical_analyzer_advanced.
    """
    try:
        if not url:
            raise ValueError("URL requise")

        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Initialisation de l’analyse technique avancée...'}
        )

        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]

        # Récupérer la page
        resp = requests.get(url, timeout=15, allow_redirects=True)
        html = resp.text
        headers = resp.headers
        soup = BeautifulSoup(html, 'html.parser')

        self.update_state(
            state='PROGRESS',
            meta={'progress': 30, 'message': 'Analyse en cours...'}
        )

        results = {}
        try:
            results['ssl'] = taa.analyze_ssl_certificate(domain)
        except Exception as e:
            results['ssl_error'] = str(e)

        try:
            results['robots'] = taa.analyze_robots_txt(url)
        except Exception as e:
            results['robots_error'] = str(e)

        try:
            results['sitemap'] = taa.analyze_sitemap(url)
        except Exception as e:
            results['sitemap_error'] = str(e)

        try:
            results['security_headers'] = taa.analyze_security_headers(headers)
        except Exception as e:
            results['security_headers_error'] = str(e)

        try:
            results['performance_hints'] = taa.analyze_performance_hints(headers, html)
        except Exception as e:
            results['performance_hints_error'] = str(e)

        try:
            results['content_structure'] = taa.analyze_content_structure(soup, html)
        except Exception as e:
            results['content_structure_error'] = str(e)

        try:
            results['dns'] = taa.analyze_dns_advanced(domain)
        except Exception as e:
            results['dns_error'] = str(e)

        try:
            results['security_advanced'] = taa.analyze_security_advanced(url, headers, html)
        except Exception as e:
            results['security_advanced_error'] = str(e)

        try:
            results['mobile_accessibility'] = taa.analyze_mobile_accessibility(soup, html)
        except Exception as e:
            results['mobile_accessibility_error'] = str(e)

        self.update_state(
            state='PROGRESS',
            meta={'progress': 80, 'message': 'Sauvegarde des résultats...'}
        )

        database = Database()
        analysis_id = None
        if entreprise_id:
            analysis_id = database.save_technical_analysis(entreprise_id, url, results)

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Analyse technique avancée terminée!'}
        )

        logger.info(f'Analyse technique avancée terminée pour {url} (analysis_id: {analysis_id})')

        return {
            'success': True,
            'url': url,
            'entreprise_id': entreprise_id,
            'analysis_id': analysis_id,
            'results': results
        }

    except Exception as e:
        logger.error(f'Erreur lors de l’analyse technique avancée de {url}: {e}', exc_info=True)
        raise

