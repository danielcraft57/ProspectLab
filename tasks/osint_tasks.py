"""
Tâches Celery pour les analyses OSINT

Ces tâches permettent d'exécuter les analyses OSINT de manière asynchrone,
avec sauvegarde automatique dans la base de données et logs dédiés.
"""

from celery_app import celery
from services.osint_analyzer import OSINTAnalyzer
from services.database import Database
from services.logging_config import setup_logger
import logging
import json
from typing import Dict, List, Optional

# Configurer le logger pour cette tâche avec un fichier dédié (niveau info pour limiter le bruit)
logger = setup_logger(__name__, 'osint_tasks.log', level=logging.INFO)


@celery.task(bind=True)
def osint_analysis_task(self, url, entreprise_id=None, people_from_scrapers=None, 
                        emails_from_scrapers=None, social_profiles_from_scrapers=None, 
                        phones_from_scrapers=None):
    """
    Tâche Celery pour effectuer une analyse OSINT d'un site web
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        url (str): URL du site à analyser
        entreprise_id (int, optional): ID de l'entreprise associée
        people_from_scrapers (list, optional): Liste des personnes trouvées par les scrapers
        emails_from_scrapers (list, optional): Liste des emails trouvés par les scrapers
        social_profiles_from_scrapers (list, optional): Liste des profils sociaux trouvés par les scrapers
        phones_from_scrapers (list, optional): Liste des téléphones trouvés par les scrapers
        
    Returns:
        dict: Résultats de l'analyse OSINT avec analysis_id
        
    Example:
        >>> result = osint_analysis_task.delay('https://example.com', entreprise_id=1)
    """
    try:
        logger.info(f'Démarrage analyse OSINT pour {url} (entreprise_id={entreprise_id})')
        
        database = Database()
        
        # Vérifier si une analyse existe déjà
        existing = database.get_osint_analysis_by_url(url)
        if existing:
            logger.debug(f'Analyse OSINT existante pour {url} (id={existing.get("id")})')
            # Si une analyse existe et qu'on a un entreprise_id, mettre à jour le lien
            if entreprise_id and existing.get('entreprise_id') != entreprise_id:
                conn = database.get_connection()
                cursor = conn.cursor()
                database.execute_sql(cursor, 'UPDATE analyses_osint SET entreprise_id = ? WHERE id = ?', (entreprise_id, existing['id']))
                conn.commit()
                conn.close()
                logger.debug(f'Analyse OSINT mise à jour avec entreprise_id={entreprise_id}')
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 5, 'message': 'Initialisation de l\'analyse OSINT...'}
        )
        
        analyzer = OSINTAnalyzer()
        
        # Callback pour mettre à jour la progression
        current_progress = 5
        def progress_update(message):
            nonlocal current_progress
            current_progress = min(current_progress + 5, 95)
            self.update_state(
                state='PROGRESS',
                meta={'progress': current_progress, 'message': message}
            )
        
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Préparation des données du scraper...'}
        )
        
        # Récupérer les personnes depuis la table personnes (priorité) ou depuis les scrapers
        if not people_from_scrapers and entreprise_id:
            try:
                # D'abord, récupérer les personnes déjà enregistrées dans la table personnes
                personnes_db = database.get_personnes_by_entreprise(entreprise_id)
                if personnes_db:
                    people_from_scrapers = []
                    for personne in personnes_db:
                        if personne.get('prenom') and personne.get('nom'):
                            people_from_scrapers.append({
                                'name': f"{personne.get('prenom')} {personne.get('nom')}",
                                'email': personne.get('email'),
                                'linkedin_url': personne.get('linkedin_url'),
                                'title': personne.get('titre'),
                                'role': personne.get('role')
                            })
                
                # Si pas de personnes en BDD, récupérer depuis les scrapers
                if not people_from_scrapers:
                    scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                    for scraper in scrapers:
                        if scraper.get('people'):
                            people_list = scraper['people'] if isinstance(scraper['people'], list) else json.loads(scraper['people'])
                            people_from_scrapers.extend(people_list)
                    
                    # Aussi récupérer les personnes depuis les emails avec is_person=True
                    for scraper in scrapers:
                        scraper_emails = database.get_scraper_emails(scraper['id'])
                        for email_data in scraper_emails:
                            if email_data.get('is_person') and email_data.get('name_info'):
                                try:
                                    name_info = email_data.get('name_info')
                                    if isinstance(name_info, str):
                                        name_info = json.loads(name_info)
                                    if name_info and name_info.get('first_name') and name_info.get('last_name'):
                                        people_from_scrapers.append({
                                            'name': f"{name_info.get('first_name')} {name_info.get('last_name')}",
                                            'email': email_data.get('email'),
                                            'title': None,
                                            'role': None
                                        })
                                except Exception:
                                    pass
            except Exception as e:
                logger.warning(f'Erreur lors de la récupération des personnes: {e}')
                people_from_scrapers = []
        
        # Filtrer les personnes avec des noms invalides
        if people_from_scrapers:
            from services.name_validator import is_valid_human_name
            original_count = len(people_from_scrapers)
            people_from_scrapers = [
                person for person in people_from_scrapers
                if person.get('name') and is_valid_human_name(person.get('name', ''))
            ]
            filtered_count = len(people_from_scrapers)
            if original_count != filtered_count:
                logger.debug(f'Filtrage: {filtered_count}/{original_count} personne(s) valide(s)')
        
        # Extraire les emails et les noms associés depuis les scrapers
        emails_from_scrapers = emails_from_scrapers or []
        names_from_scraper_emails = []  # Liste des noms extraits des emails du scraper
        
        # Toujours extraire les noms depuis les emails du scraper si disponible
        if entreprise_id:
            try:
                from services.name_validator import filter_valid_names
                
                scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                for scraper in scrapers:
                    scraper_emails = database.get_scraper_emails(scraper['id'])
                    for email_data in scraper_emails:
                        # Extraire les noms depuis name_info si disponible
                        name_info = email_data.get('analysis', {}).get('name_info') if isinstance(email_data.get('analysis'), dict) else None
                        if not name_info and email_data.get('name_info'):
                            try:
                                if isinstance(email_data['name_info'], str):
                                    name_info = json.loads(email_data['name_info'])
                                else:
                                    name_info = email_data['name_info']
                            except:
                                name_info = None
                        
                        if name_info and isinstance(name_info, dict):
                            first_name = name_info.get('first_name') or name_info.get('firstname')
                            last_name = name_info.get('last_name') or name_info.get('lastname')
                            if first_name and last_name:
                                # Éviter les doublons temporairement
                                full_name = f'{first_name} {last_name}'
                                if not any(n.get('full_name') == full_name for n in names_from_scraper_emails):
                                    names_from_scraper_emails.append({
                                        'first_name': first_name,
                                        'last_name': last_name,
                                        'full_name': full_name
                                    })
                
                # Filtrer les noms invalides après extraction
                names_from_scraper_emails = filter_valid_names(names_from_scraper_emails)
            except Exception as e:
                logger.warning(f'Erreur lors de l extraction des noms depuis les emails: {e}')
        
        # Récupérer les emails si pas déjà fournis
        if not emails_from_scrapers and entreprise_id:
            try:
                scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                for scraper in scrapers:
                    scraper_emails = database.get_scraper_emails(scraper['id'])
                    for email_data in scraper_emails:
                        email_str = email_data.get('email') or email_data.get('value') or str(email_data)
                        if email_str:
                            emails_from_scrapers.append(email_str)
                            
                            # Extraire les noms depuis name_info si disponible
                            name_info = email_data.get('analysis', {}).get('name_info') if isinstance(email_data.get('analysis'), dict) else None
                            if not name_info and email_data.get('name_info'):
                                try:
                                    if isinstance(email_data['name_info'], str):
                                        name_info = json.loads(email_data['name_info'])
                                    else:
                                        name_info = email_data['name_info']
                                except:
                                    name_info = None
                            
                            if name_info and isinstance(name_info, dict):
                                first_name = name_info.get('first_name') or name_info.get('firstname')
                                last_name = name_info.get('last_name') or name_info.get('lastname')
                                if first_name and last_name:
                                    names_from_scraper_emails.append({
                                        'first_name': first_name,
                                        'last_name': last_name,
                                        'full_name': f'{first_name} {last_name}'
                                    })
            except Exception as e:
                logger.warning(f'Erreurs lors de la récupération des emails des scrapers: {e}')
                emails_from_scrapers = []
        
        if not social_profiles_from_scrapers and entreprise_id:
            try:
                scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                social_profiles_from_scrapers = []
                for scraper in scrapers:
                    social_profiles = database.get_scraper_social_profiles(scraper['id'])
                    social_profiles_from_scrapers.extend(social_profiles)
            except Exception as e:
                logger.warning(f'Erreurs lors de la récupération des profils sociaux des scrapers: {e}')
                social_profiles_from_scrapers = []
        
        if not phones_from_scrapers and entreprise_id:
            try:
                scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                phones_from_scrapers = []
                for scraper in scrapers:
                    phones = database.get_scraper_phones(scraper['id'])
                    for phone_data in phones:
                        phone_str = phone_data.get('phone') or phone_data.get('value') or str(phone_data)
                        if phone_str:
                            phones_from_scrapers.append(phone_str)
            except Exception as e:
                logger.warning(f'Erreurs lors de la récupération des téléphones des scrapers: {e}')
                phones_from_scrapers = []
        
        logger.info(
            f'Données scraper: {len(people_from_scrapers or [])} personne(s), '
            f'{len(emails_from_scrapers or [])} email(s), '
            f'{len(social_profiles_from_scrapers or [])} réseau(x) social, '
            f'{len(phones_from_scrapers or [])} téléphone(s)'
        )
        osint_data = analyzer.analyze_osint(
            url, 
            progress_callback=progress_update, 
            people_from_scrapers=people_from_scrapers,
            emails_from_scrapers=emails_from_scrapers,
            social_profiles_from_scrapers=social_profiles_from_scrapers,
            phones_from_scrapers=phones_from_scrapers,
            names_from_scraper_emails=names_from_scraper_emails  # Passer les noms extraits des emails
        )
        
        if osint_data.get('error'):
            logger.error(f'Erreur analyse OSINT pour {url}: {osint_data["error"]}')
            raise Exception(osint_data['error'])
        
        # Sauvegarder les personnes enrichies dans la table personnes avec données OSINT
        if entreprise_id and osint_data.get('people'):
            try:
                people_data = osint_data['people']
                if isinstance(people_data, dict) and 'from_scrapers' in people_data:
                    enriched_people = people_data['from_scrapers']
                elif isinstance(people_data, dict) and 'people' in people_data:
                    enriched_people = people_data['people']
                else:
                    enriched_people = []
                
                # Sauvegarder aussi les données OSINT enrichies si disponibles
                people_osint_data = osint_data.get('people_osint', {})
                
                # Sauvegarder aussi les données OSINT enrichies si disponibles
                people_osint_data = osint_data.get('people_osint', {})
                
                for person in enriched_people:
                    # Extraire prénom et nom
                    full_name = person.get('name', '')
                    name_parts = full_name.split(' ', 1)
                    prenom = name_parts[0] if len(name_parts) > 0 else None
                    nom = name_parts[1] if len(name_parts) > 1 else full_name
                    
                    # Sauvegarder la personne de base
                    personne_id = database.save_personne(
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
                    
                    # Sauvegarder les données OSINT enrichies si disponibles
                    if personne_id:
                        person_key = full_name or person.get('email', '')
                        if person_key and person_key in people_osint_data:
                            enriched_data = people_osint_data[person_key]
                            try:
                                database.save_person_osint_details(
                                    personne_id=personne_id,
                                    enriched_data=enriched_data
                                )
                            except Exception as e:
                                logger.debug(f'Erreur sauvegarde détails OSINT pour {person_key}: {e}')
            except Exception as e:
                logger.warning(f'Erreur sauvegarde personnes: {e}')
        
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
        
        logger.info(f'Analyse OSINT terminée pour {url} (id={analysis_id})')
        
        return {
            'success': True,
            'url': url,
            'entreprise_id': entreprise_id,
            'analysis_id': analysis_id,
            'summary': osint_data.get('summary', {}),
            'updated': existing is not None
        }
        
    except Exception as e:
        logger.error(f'Erreur analyse OSINT pour {url}: {e}', exc_info=True)
        raise


