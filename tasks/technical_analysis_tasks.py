"""
Tâches Celery pour les analyses techniques, OSINT et Pentest

Ces tâches permettent d'exécuter les analyses techniques de manière asynchrone,
avec sauvegarde automatique dans la base de données.
"""

from celery_app import celery
from services.technical_analyzer import TechnicalAnalyzer
from services.osint_analyzer import OSINTAnalyzer
from services.pentest_analyzer import PentestAnalyzer
from services.database import Database
from services.logging_config import setup_logger
import logging
import json

# Configurer le logger pour cette tâche
logger = setup_logger(__name__, 'technical_analysis_tasks.log', level=logging.DEBUG)


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
        logger.info(f'[Technical Analysis] Démarrage pour {url} (entreprise_id={entreprise_id}, enable_nmap={enable_nmap})')
        
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
                logger.info(f'[Technical Analysis] Analyse sauvegardée (id={analysis_id}) pour {url} (entreprise_id={entreprise_id})')
            else:
                logger.info(f'[Technical Analysis] Analyse sauvegardée (id={analysis_id}) pour {url} (sans entreprise)')
        except Exception as e:
            logger.error(f'[Technical Analysis] Erreur lors de la sauvegarde pour {url}: {str(e)}', exc_info=True)
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
        logger.error(f'Erreur lors de l\'analyse technique de {url}: {e}', exc_info=True)
        raise


@celery.task(bind=True)
def osint_analysis_task(self, url, entreprise_id=None, people_from_scrapers=None):
    """
    Tâche Celery pour effectuer une analyse OSINT d'un site web
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        url (str): URL du site à analyser
        entreprise_id (int, optional): ID de l'entreprise associée
        people_from_scrapers (list, optional): Liste des personnes trouvées par les scrapers
        
    Returns:
        dict: Résultats de l'analyse OSINT avec analysis_id
        
    Example:
        >>> result = osint_analysis_task.delay('https://example.com', entreprise_id=1)
    """
    try:
        logger.info(f'Démarrage de l\'analyse OSINT pour {url}')
        
        database = Database()
        
        # Vérifier si une analyse existe déjà
        existing = database.get_osint_analysis_by_url(url)
        if existing:
            # Si une analyse existe et qu'on a un entreprise_id, mettre à jour le lien
            if entreprise_id and existing.get('entreprise_id') != entreprise_id:
                conn = database.get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE analyses_osint SET entreprise_id = ? WHERE id = ?', (entreprise_id, existing['id']))
                conn.commit()
                conn.close()
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 5, 'message': 'Initialisation de l\'analyse OSINT...'}
        )
        
        analyzer = OSINTAnalyzer()
        
        # Callback pour mettre à jour la progression
        def progress_update(message):
            self.update_state(
                state='PROGRESS',
                meta={'progress': 20, 'message': message}
            )
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 20, 'message': 'Découverte de sous-domaines...'}
        )
        
        # Récupérer les personnes trouvées par les scrapers si nécessaire
        if not people_from_scrapers and entreprise_id:
            try:
                scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                people_from_scrapers = []
                for scraper in scrapers:
                    if scraper.get('people'):
                        people_list = scraper['people'] if isinstance(scraper['people'], list) else json.loads(scraper['people'])
                        people_from_scrapers.extend(people_list)
            except Exception as e:
                logger.warning(f'Erreur lors de la récupération des personnes des scrapers: {e}')
                people_from_scrapers = []
        
        # Lancer l'analyse OSINT avec callback de progression et personnes des scrapers
        osint_data = analyzer.analyze_osint(url, progress_callback=progress_update, people_from_scrapers=people_from_scrapers)
        
        if osint_data.get('error'):
            raise Exception(osint_data['error'])
        
        # Sauvegarder les personnes enrichies dans la table personnes
        if entreprise_id and osint_data.get('people'):
            try:
                people_data = osint_data['people']
                if isinstance(people_data, dict) and 'from_scrapers' in people_data:
                    enriched_people = people_data['from_scrapers']
                elif isinstance(people_data, dict) and 'people' in people_data:
                    enriched_people = people_data['people']
                else:
                    enriched_people = []
                
                for person in enriched_people:
                    # Extraire prénom et nom
                    full_name = person.get('name', '')
                    name_parts = full_name.split(' ', 1)
                    prenom = name_parts[0] if len(name_parts) > 0 else None
                    nom = name_parts[1] if len(name_parts) > 1 else full_name
                    
                    database.save_personne(
                        entreprise_id=entreprise_id,
                        nom=nom,
                        prenom=prenom,
                        titre=person.get('title'),
                        role=person.get('role'),
                        email=person.get('email'),
                        telephone=person.get('phone'),
                        linkedin_url=person.get('linkedin_url'),
                        linkedin_profile_data=person.get('linkedin_profile_data'),
                        social_profiles=person.get('social_profiles'),
                        osint_data=person,
                        niveau_hierarchique=person.get('niveau_hierarchique'),
                        manager_id=None,
                        source='osint_enriched'
                    )
            except Exception as e:
                logger.warning(f'Erreur lors de la sauvegarde des personnes: {e}')
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 90, 'message': 'Sauvegarde des résultats...'}
        )
        
        # Sauvegarder ou mettre à jour dans la base de données
        if existing:
            analysis_id = database.update_osint_analysis(existing['id'], osint_data)
        else:
            analysis_id = database.save_osint_analysis(entreprise_id, url, osint_data)
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Analyse OSINT terminée!'}
        )
        
        logger.info(f'Analyse OSINT terminée pour {url} (analysis_id: {analysis_id})')
        
        return {
            'success': True,
            'url': url,
            'entreprise_id': entreprise_id,
            'analysis_id': analysis_id,
            'summary': osint_data.get('summary', {}),
            'updated': existing is not None
        }
        
    except Exception as e:
        logger.error(f'Erreur lors de l\'analyse OSINT de {url}: {e}', exc_info=True)
        raise


@celery.task(bind=True)
def pentest_analysis_task(self, url, entreprise_id=None, options=None):
    """
    Tâche Celery pour effectuer une analyse Pentest d'un site web
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        url (str): URL du site à analyser
        entreprise_id (int, optional): ID de l'entreprise associée
        options (dict, optional): Options pour l'analyse (scan_sql, scan_xss, etc.)
        
    Returns:
        dict: Résultats de l'analyse Pentest avec analysis_id
        
    Example:
        >>> result = pentest_analysis_task.delay('https://example.com', entreprise_id=1, options={'scan_sql': True})
    """
    try:
        logger.info(f'Démarrage de l\'analyse Pentest pour {url}')
        
        database = Database()
        
        # Vérifier si une analyse existe déjà
        existing = database.get_pentest_analysis_by_url(url)
        if existing:
            # Si une analyse existe et qu'on a un entreprise_id, mettre à jour le lien
            if entreprise_id and existing.get('entreprise_id') != entreprise_id:
                conn = database.get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE analyses_pentest SET entreprise_id = ? WHERE id = ?', (entreprise_id, existing['id']))
                conn.commit()
                conn.close()
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 5, 'message': 'Initialisation de l\'analyse de sécurité...'}
        )
        
        analyzer = PentestAnalyzer()
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 20, 'message': 'Scan de vulnérabilités en cours...'}
        )
        
        # Lancer l'analyse Pentest
        if options is None:
            options = {}
        pentest_data = analyzer.analyze_pentest(url, options)
        
        if pentest_data.get('error'):
            raise Exception(pentest_data['error'])
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 90, 'message': 'Sauvegarde des résultats...'}
        )
        
        # Sauvegarder ou mettre à jour dans la base de données
        if existing:
            analysis_id = database.update_pentest_analysis(existing['id'], pentest_data)
        else:
            analysis_id = database.save_pentest_analysis(entreprise_id, url, pentest_data)
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Analyse de sécurité terminée!'}
        )
        
        logger.info(f'Analyse Pentest terminée pour {url} (analysis_id: {analysis_id})')
        
        return {
            'success': True,
            'url': url,
            'entreprise_id': entreprise_id,
            'analysis_id': analysis_id,
            'summary': pentest_data.get('summary', {}),
            'risk_score': pentest_data.get('risk_score', 0),
            'updated': existing is not None
        }
        
    except Exception as e:
        logger.error(f'Erreur lors de l\'analyse Pentest de {url}: {e}', exc_info=True)
        raise


@celery.task(bind=True)
def advanced_technical_analysis_task(self, url):
    """
    Analyse technique avancée (SSL, robots.txt, services tiers).
    """
    try:
        self.update_state(state='PROGRESS', meta={'progress': 5, 'message': 'Analyse SSL...'})
        parsed = url if url.startswith(('http://', 'https://')) else f'https://{url}'
        domain = parsed.split('//', 1)[1].split('/')[0]
        ssl_info = analyze_ssl_certificate(domain)

        self.update_state(state='PROGRESS', meta={'progress': 40, 'message': 'Analyse robots.txt...'})
        robots_info = analyze_robots_txt(parsed)

        self.update_state(state='PROGRESS', meta={'progress': 70, 'message': 'Analyse services tiers...'})
        services_info = {}
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(parsed, timeout=10)
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

