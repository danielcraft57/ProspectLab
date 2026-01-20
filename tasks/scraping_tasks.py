"""
Tâches Celery pour le scraping de sites web

Ces tâches permettent d'exécuter le scraping de manière asynchrone,
évitant ainsi de bloquer l'application Flask principale.
"""

from celery_app import celery
from services.unified_scraper import UnifiedScraper
from services.database import Database
from services.logging_config import setup_logger
from services.name_validator import is_valid_human_name, validate_name_pair
import logging
import json
from typing import Dict

# Configurer le logger pour cette tâche (niveau INFO pour limiter le bruit)
logger = setup_logger(__name__, 'scraping_tasks.log', level=logging.INFO)


def _safe_update_state(task, task_id, **kwargs):
    """
    Met à jour l'état d'une tâche Celery seulement si un task_id est disponible.
    
    Args:
        task: Instance de la tâche Celery (bindée avec bind=True)
        task_id: ID connu de la tâche (optionnel, utilisé pour vérification)
        **kwargs: Arguments passés à update_state (state, meta, etc.)
    """
    try:
        # Pour une tâche bindée, task.request.id devrait être disponible
        # Si ce n'est pas le cas, on essaie avec task_id en paramètre
        if hasattr(task, 'request') and hasattr(task.request, 'id') and task.request.id:
            # La tâche est bindée et a un ID, on peut utiliser update_state directement
            task.update_state(**kwargs)
        elif task_id:
            # On a un task_id en paramètre, on peut quand même essayer
            task.update_state(**kwargs)
        else:
            # Pas de task_id disponible, on ne peut pas mettre à jour l'état
            # On ne log pas pour éviter de polluer les logs
            return
    except Exception as exc:
        # Ne log que si ce n'est pas une erreur de task_id vide
        if 'task_id' not in str(exc).lower() and 'empty' not in str(exc).lower():
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
def scrape_analysis_task(self, analysis_id: int, max_depth: int = 2, max_workers: int = 5,
                         max_time: int = 180, max_pages: int = 30) -> Dict:
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
    logger.info(f'Demarrage du scraping pour l analyse {analysis_id}')
    task_id = getattr(self.request, 'id', None)
    if not task_id:
        logger.debug('task_id introuvable au demarrage de scrape_analysis_task')
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
        logger.info(f'Aucune entreprise avec website pour l analyse {analysis_id}')
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
    tech_tasks = []  # Stocker les tâches d'analyse technique lancées
    osint_tasks = []  # Stocker les tâches d'analyse OSINT lancées
    pentest_tasks = []  # Stocker les tâches d'analyse Pentest lancées
    
    # Lancer TOUTES les analyses techniques en parallèle AVANT de commencer le scraping
    from tasks.technical_analysis_tasks import technical_analysis_task
    logger.info(f'[Scraping Analyse {analysis_id}] Lancement de toutes les analyses techniques en parallèle...')
    for entreprise_id, nom, website in rows:
        website_str = str(website or '').strip()
        entreprise_name = nom or 'Entreprise inconnue'
        if website_str:
            try:
                tech_task = technical_analysis_task.delay(url=website_str, entreprise_id=entreprise_id)
                tech_tasks.append({
                    'task': tech_task,
                    'entreprise_id': entreprise_id,
                    'url': website_str,
                    'nom': entreprise_name
                })
                logger.info(f'[Scraping Analyse {analysis_id}] Analyse technique lancée pour {entreprise_name} ({website_str}) - task_id={tech_task.id}')
            except Exception as e:
                logger.warning(f'[Scraping Analyse {analysis_id}] Erreur lors du lancement de l\'analyse technique pour {entreprise_name}: {e}')
    
    logger.info(f'[Scraping Analyse {analysis_id}] {len(tech_tasks)} analyses techniques lancées en parallèle, démarrage du scraping...')
    
    # Inclure les IDs des tâches techniques dans le meta pour le monitoring en temps réel
    tech_tasks_launched_ids = [{'task_id': t['task'].id, 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']} for t in tech_tasks]
    
    def update_progress(message: str, current_index: int, entreprise_name: str, website: str,
                        current_stats: Dict, extra_meta: Dict = None):
        """Met à jour la progression globale pour l'UI."""
        # Recalculer les IDs OSINT à chaque fois car ils sont ajoutés progressivement
        osint_tasks_launched_ids = [{'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']} for t in osint_tasks]
        
        meta = {
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
            'tech_tasks_launched_ids': tech_tasks_launched_ids,  # Inclure les IDs pour le monitoring
            'osint_tasks_launched_ids': osint_tasks_launched_ids,  # Inclure les IDs OSINT pour le monitoring (recalculé à chaque fois)
            'pentest_tasks_launched_ids': [{'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']} for t in pentest_tasks]  # Inclure les IDs Pentest
        }
        if extra_meta and isinstance(extra_meta, dict):
            meta.update(extra_meta)
        _safe_update_state(self, task_id, state='PROGRESS', meta=meta)
    
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
            
            # Analyser les emails trouvés avant de sauvegarder
            emails_found = results.get('emails', [])
            email_analyses = {}
            
            if emails_found:
                logger.info(
                    f'[Scraping Analyse {analysis_id}] {len(emails_found)} email(s) trouvé(s) pour {entreprise_name}, '
                    f'lancement de l\'analyse...'
                )
                try:
                    from services.email_analyzer import EmailAnalyzer
                    
                    # Extraire les emails sous forme de liste de strings
                    emails_list = []
                    for email in emails_found:
                        if isinstance(email, dict):
                            email_str = email.get('email') or email.get('value') or str(email)
                        else:
                            email_str = str(email)
                        if email_str:
                            emails_list.append(email_str)
                    
                    # Analyser directement les emails (sans passer par une tâche Celery)
                    analyzer = EmailAnalyzer()
                    analyzed_count = 0
                    
                    for idx, email_str in enumerate(emails_list, start=1):
                        try:
                            logger.debug(
                                f'[Scraping Analyse {analysis_id}] Analyse de {email_str} ({idx}/{len(emails_list)}) pour {entreprise_name}'
                            )
                            analysis = analyzer.analyze_email(email_str, source_url=website_str)
                            if analysis:
                                email_analyses[email_str] = analysis
                                analyzed_count += 1
                                logger.debug(
                                    f'[Scraping Analyse {analysis_id}] ✓ {email_str} analysé: '
                                    f'type={analysis.get("type")}, provider={analysis.get("provider")}, '
                                    f'mx_valid={analysis.get("mx_valid")}'
                                )
                        except Exception as email_error:
                            logger.warning(
                                f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors de l\'analyse de {email_str}: {email_error}'
                            )
                    
                    logger.info(
                        f'[Scraping Analyse {analysis_id}] ✓ Analyse des emails terminée pour {entreprise_name}: '
                        f'{analyzed_count}/{len(emails_list)} email(s) analysé(s)'
                    )
                except Exception as email_error:
                    logger.error(
                        f'[Scraping Analyse {analysis_id}] ✗ Erreur lors de l\'analyse des emails pour {entreprise_name}: {email_error}',
                        exc_info=True
                    )
            else:
                logger.info(
                    f'[Scraping Analyse {analysis_id}] Aucun email trouvé pour {entreprise_name}, '
                    f'pas d\'analyse nécessaire'
                )
            
            # Sauvegarder les résultats complets en BDD avec les analyses
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
                    forms=results.get('forms'),
                    visited_urls=visited_urls_count,
                    total_emails=results.get('total_emails', 0),
                    total_people=results.get('total_people', 0),
                    total_phones=results.get('total_phones', 0),
                    total_social_profiles=results.get('total_social_platforms', 0),
                    total_technologies=results.get('total_technologies', 0),
                    total_metadata=metadata_total,
                    total_images=results.get('total_images', 0),
                    total_forms=results.get('total_forms', 0),
                    duration=results.get('duration', 0),
                    email_analyses=email_analyses if email_analyses else None
                )
                
                # Enregistrer les personnes détectées depuis les emails dans la table personnes
                if email_analyses:
                    people_saved = 0
                    for email_str, analysis in email_analyses.items():
                        if analysis.get('is_person') and analysis.get('name_info'):
                            name_info = analysis['name_info']
                            first_name = name_info.get('first_name')
                            last_name = name_info.get('last_name')
                            
                            if first_name and last_name:
                                # Valider que c'est bien un nom humain avant de sauvegarder
                                validated = validate_name_pair(first_name, last_name)
                                if not validated:
                                    # Si validate_name_pair échoue, essayer avec is_valid_human_name
                                    full_name = f'{first_name} {last_name}'
                                    if not is_valid_human_name(full_name):
                                        logger.debug(
                                            f'[Scraping Analyse {analysis_id}] ⚠ Nom invalide ignoré depuis email: '
                                            f'{first_name} {last_name} ({email_str})'
                                        )
                                        continue
                                    # Valider chaque partie individuellement
                                    if not is_valid_human_name(first_name) or not is_valid_human_name(last_name):
                                        logger.debug(
                                            f'[Scraping Analyse {analysis_id}] ⚠ Nom invalide ignoré depuis email: '
                                            f'{first_name} {last_name} ({email_str})'
                                        )
                                        continue
                                else:
                                    # Utiliser les versions validées
                                    first_name, last_name = validated
                                
                                try:
                                    personne_id = db.save_personne(
                                        entreprise_id=entreprise_id,
                                        prenom=first_name,
                                        nom=last_name,
                                        email=email_str,
                                        source='scraper_email'
                                    )
                                    people_saved += 1
                                    logger.debug(
                                        f'[Scraping Analyse {analysis_id}] ✓ Personne enregistrée: '
                                        f'{first_name} {last_name} ({email_str})'
                                    )
                                except Exception as person_error:
                                    logger.warning(
                                        f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors de l\'enregistrement '
                                        f'de la personne {first_name} {last_name}: {person_error}'
                                    )
                    
                    if people_saved > 0:
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] ✓ {people_saved} personne(s) enregistrée(s) '
                            f'depuis les emails pour {entreprise_name}'
                        )
                
                # Enregistrer les personnes trouvées dans les textes des pages
                scraper_people = results.get('people', [])
                if scraper_people:
                    people_from_text_saved = 0
                    for person in scraper_people:
                        person_name = person.get('name', '')
                        first_name = person.get('first_name')
                        last_name = person.get('last_name')
                        
                        # Si on a first_name et last_name séparés, les utiliser
                        if not first_name or not last_name:
                            # Essayer de séparer le nom
                            name_parts = person_name.split()
                            if len(name_parts) >= 2:
                                first_name = name_parts[0]
                                last_name = ' '.join(name_parts[1:])
                            else:
                                continue
                        
                        # Valider que c'est bien un nom humain avant de sauvegarder
                        if first_name and last_name:
                            # Valider avec validate_name_pair (plus strict)
                            validated = validate_name_pair(first_name, last_name)
                            if not validated:
                                # Si validate_name_pair échoue, essayer avec is_valid_human_name sur le nom complet
                                full_name = f'{first_name} {last_name}'
                                if not is_valid_human_name(full_name):
                                    logger.debug(
                                        f'[Scraping Analyse {analysis_id}] ⚠ Nom invalide ignoré: '
                                        f'{first_name} {last_name}'
                                    )
                                    continue
                                # Si is_valid_human_name passe mais pas validate_name_pair, 
                                # valider chaque partie individuellement
                                if not is_valid_human_name(first_name) or not is_valid_human_name(last_name):
                                    logger.debug(
                                        f'[Scraping Analyse {analysis_id}] ⚠ Nom invalide ignoré: '
                                        f'{first_name} {last_name}'
                                    )
                                    continue
                            else:
                                # Utiliser les versions validées
                                first_name, last_name = validated
                            
                            try:
                                personne_id = db.save_personne(
                                    entreprise_id=entreprise_id,
                                    prenom=first_name,
                                    nom=last_name,
                                    email=person.get('email'),
                                    telephone=person.get('phone'),
                                    linkedin_url=person.get('linkedin_url'),
                                    titre=person.get('title'),
                                    source=person.get('source', 'website_scraping')
                                )
                                people_from_text_saved += 1
                                logger.debug(
                                    f'[Scraping Analyse {analysis_id}] ✓ Personne trouvée dans le texte: '
                                    f'{first_name} {last_name}'
                                )
                            except Exception as person_error:
                                logger.warning(
                                    f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors de l\'enregistrement '
                                    f'de la personne {first_name} {last_name}: {person_error}'
                                )
                    
                    if people_from_text_saved > 0:
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] ✓ {people_from_text_saved} personne(s) enregistrée(s) '
                            f'depuis les textes des pages pour {entreprise_name}'
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
                
                # Lancer l'analyse OSINT après le scraper (utilise les données du scraper)
                try:
                    from tasks.osint_tasks import osint_analysis_task
                    from tasks.pentest_tasks import pentest_analysis_task
                    
                    # Préparer les données du scraper pour l'OSINT
                    people_from_scrapers = results.get('people', [])
                    emails_from_scrapers = []
                    for email_data in results.get('emails', []):
                        if isinstance(email_data, dict):
                            email_str = email_data.get('email') or email_data.get('value') or str(email_data)
                        else:
                            email_str = str(email_data)
                        if email_str:
                            emails_from_scrapers.append(email_str)
                    
                    social_profiles_from_scrapers = results.get('social_links', [])
                    phones_from_scrapers = results.get('phones', [])
                    
                    logger.info(
                        f'[Scraping Analyse {analysis_id}] Lancement de l analyse OSINT pour {entreprise_name} '
                        f'avec {len(people_from_scrapers)} personne(s), {len(emails_from_scrapers)} email(s), '
                        f'{len(social_profiles_from_scrapers)} reseau(x) social/social, {len(phones_from_scrapers)} telephone(s) du scraper'
                    )
                    
                    # Lancer la tâche OSINT en arrière-plan (ne pas attendre)
                    osint_task = osint_analysis_task.delay(
                        url=website_str,
                        entreprise_id=entreprise_id,
                        people_from_scrapers=people_from_scrapers,
                        emails_from_scrapers=emails_from_scrapers,
                        social_profiles_from_scrapers=social_profiles_from_scrapers,
                        phones_from_scrapers=phones_from_scrapers
                    )
                    
                    # Stocker la tâche OSINT pour le monitoring
                    osint_tasks.append({
                        'task': osint_task,
                        'task_id': osint_task.id,
                        'entreprise_id': entreprise_id,
                        'url': website_str,
                        'nom': entreprise_name
                    })
                    
                    logger.info(
                        f'[Scraping Analyse {analysis_id}] ✓ Analyse OSINT lancee pour {entreprise_name} '
                        f'(task_id={osint_task.id})'
                    )
                except Exception as osint_error:
                    logger.warning(
                        f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors du lancement de l analyse OSINT pour {entreprise_name}: {osint_error}',
                        exc_info=True
                    )

                # Lancer l'analyse Pentest après le scraper (tâche dédiée)
                try:
                    logger.info(
                        f'[Scraping Analyse {analysis_id}] Lancement de l analyse Pentest pour {entreprise_name} ({website_str})'
                    )

                    pentest_task = pentest_analysis_task.delay(
                        url=website_str,
                        entreprise_id=entreprise_id,
                        options={},
                        forms_from_scrapers=results.get('forms')
                    )

                    pentest_tasks.append({
                        'task': pentest_task,
                        'task_id': pentest_task.id,
                        'entreprise_id': entreprise_id,
                        'url': website_str,
                        'nom': entreprise_name
                    })

                    logger.info(
                        f'[Scraping Analyse {analysis_id}] ✓ Analyse Pentest lancee pour {entreprise_name} (task_id={pentest_task.id})'
                    )
                except Exception as pentest_error:
                    logger.warning(
                        f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors du lancement de l analyse Pentest pour {entreprise_name}: {pentest_error}',
                        exc_info=True
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
                f'Scraping et analyse terminés pour {entreprise_name}',
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
        'stats': global_stats,
        'tech_tasks': [{'task_id': t['task'].id, 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']} for t in tech_tasks],
        'osint_tasks': [{'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']} for t in osint_tasks],
        'pentest_tasks': [{'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']} for t in pentest_tasks]                                                                                            
    }

