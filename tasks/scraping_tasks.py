"""
Tâches Celery pour le scraping de sites web

Ces tâches permettent d'exécuter le scraping de manière asynchrone,
évitant ainsi de bloquer l'application Flask principale.
"""

from celery_app import celery
from services.unified_scraper import UnifiedScraper
from services.database import Database
from services.logging_config import setup_logger
import logging
import json
from typing import Dict

# Configurer le logger pour cette tâche
logger = setup_logger(__name__, 'scraping_tasks.log', level=logging.DEBUG)


def _safe_update_state(task, task_id, **kwargs):
    """
    Met à jour l'état d'une tâche Celery seulement si un task_id est disponible.
    
    Args:
        task: Instance de la tâche Celery
        task_id: ID connu de la tâche
        **kwargs: Arguments passés à update_state
    """
    try:
        effective_id = getattr(task.request, 'id', None) or task_id
        if not effective_id:
            return
        task.update_state(task_id=effective_id, **kwargs)
    except Exception as exc:
        logger.warning(f'update_state impossible: {exc}')


@celery.task(bind=True)
def scrape_emails_task(self, url, max_depth=3, max_workers=5, max_time=300, 
                       max_pages=50, on_email_found=None, on_person_found=None,
                       on_phone_found=None, on_social_found=None, entreprise_id=None):
    """
    Tâche Celery pour scraper les emails d'un site web
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        url (str): URL de départ pour le scraping
        max_depth (int): Profondeur maximale de navigation (défaut: 3)
        max_workers (int): Nombre de threads parallèles (défaut: 5)
        max_time (int): Temps maximum en secondes (défaut: 300)
        max_pages (int): Nombre maximum de pages à scraper (défaut: 50)
        on_email_found (callable, optional): Callback quand un email est trouvé
        on_person_found (callable, optional): Callback quand une personne est trouvée
        on_phone_found (callable, optional): Callback quand un téléphone est trouvé
        on_social_found (callable, optional): Callback quand un réseau social est trouvé
        entreprise_id (int, optional): ID de l'entreprise pour sauvegarder en BDD
        
    Returns:
        dict: Résultats du scraping avec emails, personnes, téléphones, etc.
        
    Example:
        >>> result = scrape_emails_task.delay('https://example.com')
        >>> result.get()  # Attendre le résultat
    """
    try:
        logger.info(f'Démarrage du scraping pour {url}')
        
        def progress_callback(message):
            """Callback pour mettre à jour la progression de la tâche"""
            self.update_state(
                state='PROGRESS',
                meta={'message': message}
            )
        
        scraper = UnifiedScraper(
            base_url=url,
            max_workers=max_workers,
            max_depth=max_depth,
            max_time=max_time,
            max_pages=max_pages,
            progress_callback=progress_callback,
            on_email_found=on_email_found,
            on_person_found=on_person_found,
            on_phone_found=on_phone_found,
            on_social_found=on_social_found
        )
        
        results = scraper.scrape()
        
        # Sauvegarder en BDD si une entreprise est fournie
        if entreprise_id:
            try:
                db = Database()
                social_profiles = results.get('social_links')
                visited_urls = results.get('visited_urls', 0)
                if isinstance(visited_urls, list):
                    visited_urls_count = len(visited_urls)
                else:
                    visited_urls_count = visited_urls or 0
                
                metadata_value = results.get('metadata', {})
                metadata_total = len(metadata_value) if isinstance(metadata_value, dict) else 0
                
                db.save_scraper(
                    entreprise_id=entreprise_id,
                    url=url,
                    scraper_type='unified_scraper',
                    emails=results.get('emails'),
                    people=results.get('people'),
                    phones=results.get('phones'),
                    social_profiles=social_profiles,
                    technologies=results.get('technologies'),
                    metadata=metadata_value,
                    images=results.get('images'),
                    visited_urls=visited_urls_count,
                    total_emails=results.get('total_emails', 0),
                    total_people=results.get('total_people', 0),
                    total_phones=results.get('total_phones', 0),
                    total_social_profiles=results.get('total_social_platforms', 0),
                    total_technologies=results.get('total_technologies', 0),
                    total_metadata=metadata_total,
                    total_images=results.get('total_images', 0),
                    duration=results.get('duration', 0)
                )
            except Exception as e:
                logger.warning(f'Erreur lors de la sauvegarde du scraper pour {url}: {e}')
        
        logger.info(f'Scraping terminé pour {url}: {len(results.get("emails", []))} emails trouvés')
        
        return {
            'success': True,
            'url': url,
            'results': results,
            'entreprise_id': entreprise_id
        }
        
    except Exception as e:
        logger.error(f'Erreur lors du scraping de {url}: {e}', exc_info=True)
        raise


@celery.task(bind=True)
def scrape_analysis_task(self, analysis_id: int, max_depth: int = 3, max_workers: int = 5,
                         max_time: int = 300, max_pages: int = 50) -> Dict:
    """
    Tâche Celery pour scraper automatiquement toutes les entreprises d'une analyse.
    
    Cette tâche utilise UnifiedScraper pour chaque entreprise ayant un site web,
    sauvegarde les résultats complets en base (emails, personnes, téléphones,
    réseaux sociaux, technologies, métadonnées, images) et remonte une
    progression détaillée.
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        analysis_id (int): ID de l'analyse (table analyses)
        max_depth (int): Profondeur maximale de navigation
        max_workers (int): Nombre de workers parallèles
        max_time (int): Temps max par site en secondes
        max_pages (int): Nombre max de pages par site
    
    Returns:
        dict: Statistiques globales du scraping pour cette analyse.
    """
    logger.info(f'Démarrage du scraping pour l\'analyse {analysis_id}')
    task_id = getattr(self.request, 'id', None)
    if not task_id:
        logger.warning('task_id introuvable au démarrage de scrape_analysis_task')
    db = Database()
    conn = db.get_connection()
    conn.row_factory = None  # tuples simples
    cursor = conn.cursor()
    
    cursor.execute(
        '''
        SELECT id, nom, website
        FROM entreprises
        WHERE analyse_id = ?
          AND website IS NOT NULL
          AND TRIM(website) <> ''
        ''',
        (analysis_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        logger.info(f'Aucune entreprise avec website pour l\'analyse {analysis_id}')
        return {
            'success': True,
            'analysis_id': analysis_id,
            'scraped_count': 0,
            'stats': {
                'total_emails': 0,
                'total_people': 0,
                'total_phones': 0,
                'total_social_platforms': 0,
                'total_technologies': 0,
                'total_images': 0
            }
        }
    
    total = len(rows)
    scraped_count = 0
    global_stats = {
        'total_emails': 0,
        'total_people': 0,
        'total_phones': 0,
        'total_social_platforms': 0,
        'total_technologies': 0,
        'total_images': 0
    }
    
    def update_progress(message: str, current_index: int, entreprise_name: str, website: str,
                        current_stats: Dict):
        """Met à jour la progression globale pour l'UI."""
        _safe_update_state(
            self,
            task_id,
            state='PROGRESS',
            meta={
                'current': current_index,
                'total': total,
                'message': message,
                'entreprise': entreprise_name,
                'url': website,
                'total_emails': current_stats['total_emails'],
                'total_people': current_stats['total_people'],
                'total_phones': current_stats['total_phones'],
                'total_social_platforms': current_stats['total_social_platforms'],
                'total_technologies': current_stats['total_technologies'],
                'total_images': current_stats['total_images'],
            }
        )
    
    for idx, (entreprise_id, nom, website) in enumerate(rows):
        current_index = idx + 1
        entreprise_name = nom or 'Entreprise inconnue'
        website_str = str(website or '').strip()
        
        if not website_str:
            continue
        
        logger.info(f'[Scraping Analyse {analysis_id}] {current_index}/{total} - {entreprise_name} ({website_str})')
        
        scraper = None
        
        def progress_callback(message: str):
            """Callback appelé par UnifiedScraper pour cette entreprise."""
            nonlocal scraper
            try:
                # Récupérer des compteurs en temps réel depuis le scraper pour cette entreprise uniquement
                # Ne pas ajouter aux global_stats ici car ils seront mis à jour après le scraping complet
                if scraper:
                    with scraper.lock:
                        emails_count = len(scraper.emails)
                        people_count = len(scraper.people)
                        phones_count = len(scraper.phones)
                        social_count = len(scraper.social_links)
                        tech_count = sum(
                            len(v) if isinstance(v, list) else 1
                            for v in scraper.technologies.values()
                        )
                        images_count = len(scraper.images)
                else:
                    emails_count = people_count = phones_count = social_count = tech_count = images_count = 0
                
                # Formater le message avec les compteurs de cette entreprise uniquement
                # Les totaux globaux sont passés séparément dans global_stats
                current_stats_str = f"{emails_count} emails, {people_count} personnes, {phones_count} téléphones, {social_count} réseaux sociaux"
                if tech_count > 0:
                    current_stats_str += f", {tech_count} technos"
                if images_count > 0:
                    current_stats_str += f", {images_count} images"
                
                # Message formaté : entreprise actuelle | total cumulé
                total_stats_str = f"{global_stats['total_emails']} emails, {global_stats['total_people']} personnes, {global_stats['total_phones']} téléphones"
                if global_stats['total_social_platforms'] > 0:
                    total_stats_str += f", {global_stats['total_social_platforms']} réseaux sociaux"
                if global_stats['total_technologies'] > 0:
                    total_stats_str += f", {global_stats['total_technologies']} technos"
                if global_stats['total_images'] > 0:
                    total_stats_str += f", {global_stats['total_images']} images"
                
                message_with_counters = f"{message} - {current_stats_str} | Total: {total_stats_str}"
                
                # Utiliser les totaux globaux actuels (sans ajouter les compteurs de cette entreprise)
                # car cette entreprise n'est pas encore terminée
                update_progress(message_with_counters, current_index, entreprise_name, website_str, global_stats)
            except Exception as e:
                logger.warning(f'Erreur dans progress_callback pour {website_str}: {e}')
        
        try:
            scraper = UnifiedScraper(
                base_url=website_str,
                max_workers=max_workers,
                max_depth=max_depth,
                max_time=max_time,
                max_pages=max_pages,
                progress_callback=progress_callback
            )
            
            results = scraper.scrape()
            
            
            # Sauvegarder les résultats complets en BDD
            try:
                db = Database()
                social_profiles = results.get('social_links')
                visited_urls = results.get('visited_urls', 0)
                if isinstance(visited_urls, list):
                    visited_urls_count = len(visited_urls)
                else:
                    visited_urls_count = visited_urls or 0
                
                metadata_value = results.get('metadata', {})
                metadata_total = len(metadata_value) if isinstance(metadata_value, dict) else 0
                
                
                scraper_id = db.save_scraper(
                    entreprise_id=entreprise_id,
                    url=website_str,
                    scraper_type='unified_scraper',
                    emails=results.get('emails'),
                    people=results.get('people'),
                    phones=results.get('phones'),
                    social_profiles=social_profiles,
                    technologies=results.get('technologies'),
                    metadata=metadata_value,
                    images=results.get('images'),
                    visited_urls=visited_urls_count,
                    total_emails=results.get('total_emails', 0),
                    total_people=results.get('total_people', 0),
                    total_phones=results.get('total_phones', 0),
                    total_social_profiles=results.get('total_social_platforms', 0),
                    total_technologies=results.get('total_technologies', 0),
                    total_metadata=metadata_total,
                    total_images=results.get('total_images', 0),
                    duration=results.get('duration', 0)
                )
                logger.info(
                    f'Scraper sauvegardé (id={scraper_id}) pour entreprise {entreprise_id} '
                    f'avec {results.get("total_emails", 0)} emails, '
                    f'{results.get("total_people", 0)} personnes, '
                    f'{results.get("total_phones", 0)} téléphones, '
                    f'{results.get("total_social_platforms", 0)} réseaux sociaux, '
                    f'{results.get("total_technologies", 0)} technos, '
                    f'{results.get("total_images", 0)} images'
                )
                
                # Mettre à jour l'entreprise avec resume, logo, favicon, og_image depuis les résultats du scraper
                # Les données OpenGraph sont sauvegardées dans les tables normalisées
                try:
                    resume = results.get('resume', '')
                    metadata_dict = metadata_value if isinstance(metadata_value, dict) else {}
                    icons = metadata_dict.get('icons', {}) if isinstance(metadata_dict, dict) else {}
                    logo = icons.get('logo') if isinstance(icons, dict) else None
                    favicon = icons.get('favicon') if isinstance(icons, dict) else None
                    og_image = icons.get('og_image') if isinstance(icons, dict) else None
                    
                    # Récupérer les OG de toutes les pages scrapées
                    og_data_by_page = results.get('og_data_by_page', {})
                    logger.info(f'[Scraping Analyse {analysis_id}] OG récupérés pour {entreprise_name}: {len(og_data_by_page)} page(s) depuis le scraper')
                    
                    if not og_data_by_page:
                        # Fallback : utiliser les OG de la page d'accueil si disponibles
                        og_tags = metadata_dict.get('open_graph', {}) if isinstance(metadata_dict, dict) else {}
                        if og_tags:
                            og_data_by_page = {website_str: og_tags}
                            logger.info(f'[Scraping Analyse {analysis_id}] Utilisation des OG de la page d\'accueil pour {entreprise_name} (fallback)')
                        else:
                            logger.warning(f'[Scraping Analyse {analysis_id}] ⚠ Aucun OG trouvé pour {entreprise_name} (ni dans og_data_by_page ni dans metadata)')
                    else:
                        # Log des URLs des pages avec OG
                        page_urls = list(og_data_by_page.keys())
                        logger.info(f'[Scraping Analyse {analysis_id}] Pages avec OG pour {entreprise_name}: {len(page_urls)} page(s) - {page_urls[:3]}...' if len(page_urls) > 3 else f'[Scraping Analyse {analysis_id}] Pages avec OG pour {entreprise_name}: {page_urls}')
                    
                    # Convertir les URLs relatives en absolues si nécessaire
                    if website_str:
                        from urllib.parse import urljoin
                        if logo and not logo.startswith(('http://', 'https://')):
                            logo = urljoin(website_str, logo)
                        if favicon and not favicon.startswith(('http://', 'https://')):
                            favicon = urljoin(website_str, favicon)
                        if og_image and not og_image.startswith(('http://', 'https://')):
                            og_image = urljoin(website_str, og_image)
                    
                    # Mettre à jour la table entreprises (resume, logo, favicon, og_image)
                    conn_update = db.get_connection()
                    cursor_update = conn_update.cursor()
                    cursor_update.execute('''
                        UPDATE entreprises 
                        SET resume = ?, logo = ?, favicon = ?, og_image = ?
                        WHERE id = ?
                    ''', (resume, logo, favicon, og_image, entreprise_id))
                    
                    # Sauvegarder toutes les données OpenGraph de toutes les pages dans les tables normalisées
                    if og_data_by_page:
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] Sauvegarde de {len(og_data_by_page)} page(s) avec OG pour entreprise {entreprise_id} ({entreprise_name})'
                        )
                        try:
                            db._save_multiple_og_data_in_transaction(cursor_update, entreprise_id, og_data_by_page)
                            logger.info(
                                f'[Scraping Analyse {analysis_id}] ✓ OG sauvegardés avec succès pour entreprise {entreprise_id}: {len(og_data_by_page)} page(s)'
                            )
                        except Exception as og_error:
                            logger.error(
                                f'[Scraping Analyse {analysis_id}] ✗ Erreur lors de la sauvegarde des OG pour entreprise {entreprise_id}: {og_error}',
                                exc_info=True
                            )
                    
                    conn_update.commit()
                    conn_update.close()
                    
                    logger.info(
                        f'Entreprise {entreprise_id} mise à jour: resume={bool(resume)}, '
                        f'logo={bool(logo)}, favicon={bool(favicon)}, og_image={bool(og_image)}, '
                        f'og_pages={len(og_data_by_page)}'
                    )
                except Exception as e:
                    logger.error(f'Erreur lors de la mise à jour de l\'entreprise {entreprise_id} (resume/logo/favicon/og_data): {e}', exc_info=True)
            except Exception as e:
                logger.warning(f'Erreur lors de la sauvegarde du scraper (analyse {analysis_id}, entreprise {entreprise_id}): {e}')
            
            # Mettre à jour les stats globales à partir des résultats finaux
            global_stats['total_emails'] += results.get('total_emails', 0)
            global_stats['total_people'] += results.get('total_people', 0)
            global_stats['total_phones'] += results.get('total_phones', 0)
            global_stats['total_social_platforms'] += results.get('total_social_platforms', 0)
            global_stats['total_technologies'] += results.get('total_technologies', 0)
            global_stats['total_images'] += results.get('total_images', 0)
            
            scraped_count += 1
            
            # Mise à jour de progression après l'entreprise
            update_progress(
                f'Scraping terminé pour {entreprise_name}',
                current_index,
                entreprise_name,
                website_str,
                global_stats
            )
        
        except Exception as e:
            logger.error(f'Erreur lors du scraping de {website_str}: {e}', exc_info=True)
            update_progress(
                f'Erreur lors du scraping de {entreprise_name}: {e}',
                current_index,
                entreprise_name,
                website_str,
                global_stats
            )
    
    logger.info(
        f'Scraping terminé pour l\'analyse {analysis_id}: '
        f'{scraped_count}/{total} entreprises traitées'
    )
    
    return {
        'success': True,
        'analysis_id': analysis_id,
        'scraped_count': scraped_count,
        'total_entreprises': total,
        'stats': global_stats
    }

