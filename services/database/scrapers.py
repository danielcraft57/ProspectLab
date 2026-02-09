"""
Module de gestion des scrapers
Contient toutes les méthodes liées aux scrapers et leurs données normalisées
"""

import json
import logging
from .base import DatabaseBase

logger = logging.getLogger(__name__)


class ScraperManager(DatabaseBase):
    """
    Gère toutes les opérations sur les scrapers
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module scrapers"""
        super().__init__(*args, **kwargs)
    
    def save_scraper(self, entreprise_id, url, scraper_type, emails=None, people=None, phones=None, 
                     social_profiles=None, technologies=None, metadata=None, images=None, forms=None,
                     visited_urls=0, total_emails=0, total_people=0, total_phones=0,
                     total_social_profiles=0, total_technologies=0, total_metadata=0, total_images=0, total_forms=0, duration=0,
                     email_analyses=None):
        """
        Sauvegarde ou met à jour un scraper dans la base de données.
        Si un scraper existe déjà pour cette entreprise/URL/type, il est mis à jour.
        Sinon, un nouveau scraper est créé.
        
        Args:
            entreprise_id: ID de l'entreprise
            url: URL scrapée
            scraper_type: Type de scraper ('emails', 'people', 'phones', 'social', 'technologies', 'metadata', 'unified', 'global')
            emails: Liste des emails trouvés (JSON string ou list)
            people: Liste des personnes trouvées (JSON string ou list)
            phones: Liste des téléphones trouvés (JSON string ou list)
            social_profiles: Dictionnaire des réseaux sociaux (JSON string ou dict)
            technologies: Dictionnaire des technologies (JSON string ou dict)
            metadata: Dictionnaire des métadonnées (JSON string ou dict)
            images: Liste des images trouvées (list de dicts {url, alt, page_url, width, height})
            forms: Liste des formulaires trouvés (list de dicts avec détails des formulaires)
            visited_urls: Nombre d'URLs visitées
            total_emails: Nombre total d'emails
            total_people: Nombre total de personnes
            total_phones: Nombre total de téléphones
            total_social_profiles: Nombre total de réseaux sociaux
            total_technologies: Nombre total de technologies
            total_metadata: Nombre total de métadonnées
            total_images: Nombre total d'images
            total_forms: Nombre total de formulaires
            duration: Durée du scraping en secondes
            email_analyses: Dict avec email comme clé et analyse comme valeur (optionnel)
        
        Returns:
            int: ID du scraper créé ou mis à jour
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convertir en JSON si nécessaire
        emails_json = json.dumps(emails) if emails and not isinstance(emails, str) else (emails or None)
        people_json = json.dumps(people) if people and not isinstance(people, str) else (people or None)
        phones_json = json.dumps(phones) if phones and not isinstance(phones, str) else (phones or None)
        social_json = json.dumps(social_profiles) if social_profiles and not isinstance(social_profiles, str) else (social_profiles or None)
        tech_json = json.dumps(technologies) if technologies and not isinstance(technologies, str) else (technologies or None)
        metadata_json = json.dumps(metadata) if metadata and not isinstance(metadata, str) else (metadata or None)
        
        # Vérifier si un scraper existe déjà pour cette entreprise/URL/type
        self.execute_sql(cursor,'''
            SELECT id FROM scrapers 
            WHERE entreprise_id = ? AND url = ? AND scraper_type = ?
        ''', (entreprise_id, url, scraper_type))
        
        existing = cursor.fetchone()
        logger.debug(f'save_scraper: db_type={self.db_type}, entreprise_id={entreprise_id}, existing={existing is not None}')
        
        if existing:
            # UPDATE: mettre à jour le scraper existant
            if isinstance(existing, dict):
                scraper_id = existing.get('id')
            else:
                scraper_id = existing[0] if existing else None
            self.execute_sql(cursor,'''
                UPDATE scrapers SET
                    emails = ?,
                    people = ?,
                    phones = ?,
                    social_profiles = ?,
                    technologies = ?,
                    metadata = ?,
                    visited_urls = ?,
                    total_emails = ?,
                    total_people = ?,
                    total_phones = ?,
                    total_social_profiles = ?,
                    total_technologies = ?,
                    total_metadata = ?,
                    total_images = ?,
                    total_forms = ?,
                    duration = ?,
                    date_modification = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                emails_json, people_json, phones_json, social_json, tech_json, metadata_json,
                visited_urls, total_emails, total_people, total_phones,
                total_social_profiles, total_technologies, total_metadata, total_images, total_forms, duration,
                scraper_id
            ))
        else:
            # INSERT: créer un nouveau scraper
            # PostgreSQL : lastrowid n'existe pas, on utilise RETURNING id
            if self.is_postgresql():
                self.execute_sql(cursor,'''
                    INSERT INTO scrapers (
                        entreprise_id, url, scraper_type, emails, people, phones, social_profiles,
                        technologies, metadata, visited_urls, total_emails, total_people, total_phones,
                        total_social_profiles, total_technologies, total_metadata, total_images, total_forms, duration,
                        date_creation, date_modification
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id
                ''', (
                    entreprise_id, url, scraper_type, emails_json, people_json, phones_json,
                    social_json, tech_json, metadata_json, visited_urls, total_emails, total_people,
                    total_phones, total_social_profiles, total_technologies, total_metadata, total_images, total_forms, duration
                ))
                result = cursor.fetchone()
                scraper_id = result.get('id') if isinstance(result, dict) else (result[0] if result else None)
            else:
                self.execute_sql(cursor,'''
                    INSERT INTO scrapers (
                        entreprise_id, url, scraper_type, emails, people, phones, social_profiles,
                        technologies, metadata, visited_urls, total_emails, total_people, total_phones,
                        total_social_profiles, total_technologies, total_metadata, total_images, total_forms, duration,
                        date_creation, date_modification
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (
                    entreprise_id, url, scraper_type, emails_json, people_json, phones_json,
                    social_json, tech_json, metadata_json, visited_urls, total_emails, total_people,
                    total_phones, total_social_profiles, total_technologies, total_metadata, total_images, total_forms, duration
                ))
                scraper_id = cursor.lastrowid
        
        logger.debug(f'save_scraper: scraper_id={scraper_id}, total_images={total_images}, nb_images_list={len(images) if images else 0}')
        
        # Sauvegarder les données normalisées dans les tables séparées (au lieu de JSON)
        try:
            if emails:
                self._save_scraper_emails_in_transaction(cursor, scraper_id, entreprise_id, emails, email_analyses)
            if phones:
                self._save_scraper_phones_in_transaction(cursor, scraper_id, entreprise_id, phones)
            if social_profiles:
                self._save_scraper_social_profiles_in_transaction(cursor, scraper_id, entreprise_id, social_profiles)
            if technologies:
                self._save_scraper_technologies_in_transaction(cursor, scraper_id, entreprise_id, technologies)
            if people:
                self._save_scraper_people_in_transaction(cursor, scraper_id, entreprise_id, people)
            
            # Sauvegarder les images dans la table séparée
            if images and isinstance(images, list) and len(images) > 0:
                self._save_images_in_transaction(cursor, entreprise_id, scraper_id, images)
            
            # Sauvegarder les formulaires dans la table séparée
            if forms and isinstance(forms, list) and len(forms) > 0:
                logger.info(f'Sauvegarde de {len(forms)} formulaire(s) pour le scraper {scraper_id} (entreprise {entreprise_id})')
                self._save_scraper_forms_in_transaction(cursor, scraper_id, entreprise_id, forms)
            else:
                logger.warning(f'Aucun formulaire à sauvegarder pour le scraper {scraper_id} (forms={forms})')
        except Exception as e:
            logger.error(f'Erreur lors de la sauvegarde des données normalisées pour scraper {scraper_id}: {e}', exc_info=True)
        
        conn.commit()
        conn.close()
        
        # Recalculer l'opportunité après le scraping (si données importantes trouvées)
        if entreprise_id and (emails or people or phones):
            try:
                from services.database.entreprises import EntrepriseManager
                entreprise_manager = EntrepriseManager()
                entreprise_manager.update_opportunity_score(entreprise_id)
            except Exception as e:
                logger.warning(f'Erreur lors du recalcul de l\'opportunité après scraping: {e}')
        
        return scraper_id
    
    def _save_scraper_emails_in_transaction(self, cursor, scraper_id, entreprise_id, emails, email_analyses=None):
        """
        Sauvegarde les emails dans la transaction en cours
        
        Args:
            cursor: Curseur de la transaction
            scraper_id: ID du scraper
            entreprise_id: ID de l'entreprise
            emails: Liste d'emails (string ou list)
            email_analyses: Dict avec email comme clé et analyse comme valeur (optionnel)
        """
        if not emails:
            return
        
        # Supprimer les anciens emails de ce scraper
        self.execute_sql(cursor,'DELETE FROM scraper_emails WHERE scraper_id = ?', (scraper_id,))
        
        # Désérialiser si nécessaire
        if isinstance(emails, str):
            try:
                emails = json.loads(emails)
            except:
                return
        
        if not isinstance(emails, list):
            return
        
        # Préparer le dict des analyses (email -> analyse)
        analyses_dict = {}
        if email_analyses:
            if isinstance(email_analyses, dict):
                analyses_dict = email_analyses
            elif isinstance(email_analyses, list):
                for analysis in email_analyses:
                    if isinstance(analysis, dict) and 'email' in analysis:
                        analyses_dict[analysis['email']] = analysis
        
        # Insérer les nouveaux emails avec leurs analyses
        for email in emails:
            if isinstance(email, dict):
                email_str = email.get('email') or email.get('value') or str(email)
                page_url = email.get('page_url')
            else:
                email_str = str(email)
                page_url = None
            
            if email_str:
                # Récupérer l'analyse si elle existe
                analysis = analyses_dict.get(email_str)
                
                if analysis:
                    # Sauvegarder avec les données d'analyse
                    if self.is_postgresql():
                        self.execute_sql(cursor,'''
                            INSERT INTO scraper_emails
                            (scraper_id, entreprise_id, email, page_url,
                             provider, type, format_valid, mx_valid,
                             risk_score, domain, name_info, is_person, analyzed_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (scraper_id, email) DO UPDATE SET
                                page_url = EXCLUDED.page_url,
                                provider = EXCLUDED.provider,
                                type = EXCLUDED.type,
                                format_valid = EXCLUDED.format_valid,
                                mx_valid = EXCLUDED.mx_valid,
                                risk_score = EXCLUDED.risk_score,
                                domain = EXCLUDED.domain,
                                name_info = EXCLUDED.name_info,
                                is_person = EXCLUDED.is_person,
                                analyzed_at = EXCLUDED.analyzed_at
                        ''', (
                            scraper_id, entreprise_id, email_str, page_url,
                            analysis.get('provider'),
                            analysis.get('type'),
                            1 if analysis.get('format_valid') else 0,
                            1 if analysis.get('mx_valid') is True else (0 if analysis.get('mx_valid') is False else None),
                            analysis.get('risk_score'),
                            analysis.get('domain'),
                            json.dumps(analysis.get('name_info')) if analysis.get('name_info') else None,
                            1 if analysis.get('is_person') else 0,
                            analysis.get('analyzed_at')
                        ))
                    else:
                        self.execute_sql(cursor,'''
                            INSERT OR REPLACE INTO scraper_emails
                            (scraper_id, entreprise_id, email, page_url,
                             provider, type, format_valid, mx_valid,
                             risk_score, domain, name_info, is_person, analyzed_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            scraper_id, entreprise_id, email_str, page_url,
                            analysis.get('provider'),
                            analysis.get('type'),
                            1 if analysis.get('format_valid') else 0,
                            1 if analysis.get('mx_valid') is True else (0 if analysis.get('mx_valid') is False else None),
                            analysis.get('risk_score'),
                            analysis.get('domain'),
                            json.dumps(analysis.get('name_info')) if analysis.get('name_info') else None,
                            1 if analysis.get('is_person') else 0,
                            analysis.get('analyzed_at')
                        ))
                else:
                    # Sauvegarder sans analyse
                    self.execute_sql(cursor,'''
                        INSERT OR IGNORE INTO scraper_emails (scraper_id, entreprise_id, email, page_url)
                        VALUES (?, ?, ?, ?)
                    ''', (scraper_id, entreprise_id, email_str, page_url))
    
    def save_scraper_emails(self, scraper_id, entreprise_id, emails):
        """
        Sauvegarde les emails dans la table scraper_emails (normalisation BDD)
        
        Args:
            scraper_id: ID du scraper
            entreprise_id: ID de l'entreprise
            emails: Liste d'emails (string ou list)
        """
        if not emails:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_emails_in_transaction(cursor, scraper_id, entreprise_id, emails)
        conn.commit()
        conn.close()
    
    def _save_scraper_phones_in_transaction(self, cursor, scraper_id, entreprise_id, phones):
        """Sauvegarde les téléphones dans la transaction en cours"""
        if not phones:
            return
        
        self.execute_sql(cursor,'DELETE FROM scraper_phones WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(phones, str):
            try:
                phones = json.loads(phones)
            except:
                return
        
        if not isinstance(phones, list):
            return
        
        for phone in phones:
            if isinstance(phone, dict):
                phone_str = phone.get('phone') or phone.get('value') or str(phone)
                page_url = phone.get('page_url')
            else:
                phone_str = str(phone)
                page_url = None
            
            if phone_str:
                self.execute_sql(cursor,'''
                    INSERT OR IGNORE INTO scraper_phones (scraper_id, entreprise_id, phone, page_url)
                    VALUES (?, ?, ?, ?)
                ''', (scraper_id, entreprise_id, phone_str, page_url))
    
    def save_scraper_phones(self, scraper_id, entreprise_id, phones):
        """Sauvegarde les téléphones dans la table scraper_phones (normalisation BDD)"""
        if not phones:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_phones_in_transaction(cursor, scraper_id, entreprise_id, phones)
        conn.commit()
        conn.close()
    
    def _save_scraper_social_profiles_in_transaction(self, cursor, scraper_id, entreprise_id, social_profiles):
        """Sauvegarde les profils sociaux dans la transaction en cours"""
        if not social_profiles:
            return
        
        self.execute_sql(cursor,'DELETE FROM scraper_social_profiles WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(social_profiles, str):
            try:
                social_profiles = json.loads(social_profiles)
            except:
                return
        
        if not isinstance(social_profiles, dict):
            return
        
        for platform, urls in social_profiles.items():
            if not urls:
                continue
            
            if not isinstance(urls, list):
                urls = [urls]
            
            for url_data in urls:
                if isinstance(url_data, dict):
                    url_str = url_data.get('url') or str(url_data)
                    page_url = url_data.get('page_url')
                else:
                    url_str = str(url_data)
                    page_url = None
                
                if url_str:
                    self.execute_sql(cursor,'''
                        INSERT OR IGNORE INTO scraper_social_profiles (scraper_id, entreprise_id, platform, url, page_url)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (scraper_id, entreprise_id, platform, url_str, page_url))
    
    def save_scraper_social_profiles(self, scraper_id, entreprise_id, social_profiles):
        """Sauvegarde les profils sociaux dans la table scraper_social_profiles (normalisation BDD)"""
        if not social_profiles:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_social_profiles_in_transaction(cursor, scraper_id, entreprise_id, social_profiles)
        conn.commit()
        conn.close()
    
    def _save_scraper_technologies_in_transaction(self, cursor, scraper_id, entreprise_id, technologies):
        """Sauvegarde les technologies dans la transaction en cours"""
        if not technologies:
            return
        
        self.execute_sql(cursor,'DELETE FROM scraper_technologies WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(technologies, str):
            try:
                technologies = json.loads(technologies)
            except:
                return
        
        if not isinstance(technologies, dict):
            return
        
        for category, techs in technologies.items():
            if not techs:
                continue
            
            if not isinstance(techs, list):
                techs = [techs]
            
            for tech in techs:
                tech_name = str(tech)
                if tech_name:
                    self.execute_sql(cursor,'''
                        INSERT OR IGNORE INTO scraper_technologies (scraper_id, entreprise_id, category, name)
                        VALUES (?, ?, ?, ?)
                    ''', (scraper_id, entreprise_id, category, tech_name))
    
    def save_scraper_technologies(self, scraper_id, entreprise_id, technologies):
        """Sauvegarde les technologies dans la table scraper_technologies (normalisation BDD)"""
        if not technologies:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_technologies_in_transaction(cursor, scraper_id, entreprise_id, technologies)
        conn.commit()
        conn.close()
    
    def _save_scraper_people_in_transaction(self, cursor, scraper_id, entreprise_id, people):
        """Sauvegarde les personnes dans la transaction en cours"""
        if not people:
            return
        
        self.execute_sql(cursor,'DELETE FROM scraper_people WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(people, str):
            try:
                people = json.loads(people)
            except:
                return
        
        if not isinstance(people, list):
            return
        
        for person in people:
            if not isinstance(person, dict):
                continue
            
            name = person.get('name')
            title = person.get('title')
            email = person.get('email')
            linkedin_url = person.get('linkedin_url')
            page_url = person.get('page_url')
            person_id = person.get('person_id')
            
            if name or email:
                self.execute_sql(cursor,'''
                    INSERT OR IGNORE INTO scraper_people (scraper_id, entreprise_id, person_id, name, title, email, linkedin_url, page_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (scraper_id, entreprise_id, person_id, name, title, email, linkedin_url, page_url))
    
    def save_scraper_people(self, scraper_id, entreprise_id, people):
        """Sauvegarde les personnes dans la table scraper_people (normalisation BDD)"""
        if not people:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_people_in_transaction(cursor, scraper_id, entreprise_id, people)
        conn.commit()
        conn.close()
    
    def _save_images_in_transaction(self, cursor, entreprise_id, scraper_id, images):
        """Sauvegarde les images dans la transaction en cours"""
        if not images or not isinstance(images, list):
            return
        
        for img in images:
            url = img.get('url')
            if not url:
                continue
            
            self.execute_sql(cursor,'''
                INSERT OR IGNORE INTO images (entreprise_id, scraper_id, url, alt_text, page_url, width, height)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                entreprise_id,
                scraper_id,
                url,
                img.get('alt') or None,
                img.get('page_url') or None,
                img.get('width'),
                img.get('height')
            ))
    
    def save_images(self, entreprise_id, scraper_id, images):
        """
        Sauvegarde les images dans la table images (optimisation BDD)
        
        Args:
            entreprise_id: ID de l'entreprise
            scraper_id: ID du scraper (optionnel, pour la traçabilité)
            images: Liste d'objets {url, alt, page_url, width, height}
        """
        if not images or not isinstance(images, list):
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_images_in_transaction(cursor, entreprise_id, scraper_id, images)
        conn.commit()
        conn.close()
    
    def _save_scraper_forms_in_transaction(self, cursor, scraper_id, entreprise_id, forms):
        """Sauvegarde les formulaires dans la transaction en cours"""
        if not forms:
            return
        
        self.execute_sql(cursor,'DELETE FROM scraper_forms WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(forms, str):
            try:
                forms = json.loads(forms)
            except:
                return
        
        if not isinstance(forms, list):
            return
        
        for form in forms:
            if not isinstance(form, dict):
                continue
            
            page_url = form.get('page_url')
            if not page_url:
                continue
            
            action_url = form.get('action_url') or form.get('action')
            method = form.get('method', 'GET').upper()
            enctype = form.get('enctype', 'application/x-www-form-urlencoded')
            has_csrf = 1 if form.get('has_csrf', False) else 0
            has_file_upload = 1 if form.get('has_file_upload', False) else 0
            fields = form.get('fields', [])
            fields_count = len(fields) if isinstance(fields, list) else 0
            fields_data = json.dumps(fields) if fields else None
            
            self.execute_sql(cursor,'''
                INSERT OR IGNORE INTO scraper_forms (
                    scraper_id, entreprise_id, page_url, action_url, method, enctype,
                    has_csrf, has_file_upload, fields_count, fields_data
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                scraper_id, entreprise_id, page_url, action_url, method, enctype,
                has_csrf, has_file_upload, fields_count, fields_data
            ))
    
    def save_scraper_forms(self, scraper_id, entreprise_id, forms):
        """Sauvegarde les formulaires dans la table scraper_forms (normalisation BDD)"""
        if not forms:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_forms_in_transaction(cursor, scraper_id, entreprise_id, forms)
        conn.commit()
        conn.close()
    
    def get_scraper_forms(self, scraper_id):
        """
        Récupère les formulaires d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des formulaires (dicts)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT page_url, action_url, method, enctype, has_csrf, has_file_upload, 
                   fields_count, fields_data
            FROM scraper_forms WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        forms = []
        for row in rows:
            form = {
                'page_url': row['page_url'],
                'action_url': row['action_url'],
                'method': row['method'],
                'enctype': row['enctype'],
                'has_csrf': bool(row['has_csrf']),
                'has_file_upload': bool(row['has_file_upload']),
                'fields_count': row['fields_count']
            }
            
            if row['fields_data']:
                try:
                    form['fields'] = json.loads(row['fields_data'])
                except:
                    form['fields'] = []
            else:
                form['fields'] = []
            
            forms.append(form)
        
        return forms
    
    def get_images_by_scraper(self, scraper_id):
        """
        Récupère toutes les images d'un scraper
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des images
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT id, entreprise_id, scraper_id, url, alt_text, page_url, width, height, date_found
            FROM images
            WHERE scraper_id = ?
            ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_scraper_emails(self, scraper_id):
        """
        Récupère les emails d'un scraper depuis la table normalisée avec leurs analyses
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des emails avec leurs analyses (dict ou string si pas d'analyse)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT email, page_url, provider, type, format_valid, 
                   mx_valid, risk_score, domain, name_info, analyzed_at
            FROM scraper_emails WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        emails = []
        for row in rows:
            email_data = {
                'email': row['email'],
                'page_url': row['page_url']
            }
            
            # Ajouter les données d'analyse si elles existent
            if row['provider'] is not None:
                email_data['analysis'] = {
                    'provider': row['provider'],
                    'type': row['type'],
                    'format_valid': bool(row['format_valid']) if row['format_valid'] is not None else None,
                    'mx_valid': bool(row['mx_valid']) if row['mx_valid'] is not None else None,
                    'risk_score': row['risk_score'],
                    'domain': row['domain'],
                    'name_info': json.loads(row['name_info']) if row['name_info'] else None,
                    'analyzed_at': row['analyzed_at']
                }
            
            emails.append(email_data)
        
        return emails
    
    def get_scraper_phones(self, scraper_id):
        """
        Récupère les téléphones d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des téléphones (dicts avec phone et page_url)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT phone, page_url FROM scraper_phones WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{'phone': row['phone'], 'page_url': row['page_url']} for row in rows]
    
    def get_scraper_social_profiles(self, scraper_id):
        """
        Récupère les profils sociaux d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            dict: Dictionnaire {platform: [urls]}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT platform, url FROM scraper_social_profiles WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        social_profiles = {}
        for row in rows:
            platform = row['platform']
            url = row['url']
            if platform not in social_profiles:
                social_profiles[platform] = []
            social_profiles[platform].append({'url': url})
        
        return social_profiles
    
    def get_scraper_technologies(self, scraper_id):
        """
        Récupère les technologies d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            dict: Dictionnaire {category: [names]}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT category, name FROM scraper_technologies WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        technologies = {}
        for row in rows:
            category = row['category']
            name = row['name']
            if category not in technologies:
                technologies[category] = []
            technologies[category].append(name)
        
        return technologies
    
    def get_scraper_people(self, scraper_id):
        """
        Récupère les personnes d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des personnes (dicts)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT person_id, name, title, email, linkedin_url, page_url 
            FROM scraper_people WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_images_by_entreprise(self, entreprise_id):
        """
        Récupère toutes les images d'une entreprise depuis toutes les sources disponibles :
        - Table images (scrapées)
        - Table entreprise_og_images (OpenGraph)
        - Champs og_image, logo, favicon de la table entreprises
        
        Args:
            entreprise_id: ID de l'entreprise
            
        Returns:
            list: Liste des images avec leurs métadonnées
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        images = []
        
        # 1. Récupérer les images depuis la table images (scrapées)
        self.execute_sql(cursor,'''
            SELECT id, entreprise_id, scraper_id, url, alt_text, page_url, width, height, date_found
            FROM images
            WHERE entreprise_id = ?
            ORDER BY date_found DESC
        ''', (entreprise_id,))
        
        rows = cursor.fetchall()
        for row in rows:
            img = self.clean_row_dict(dict(row))
            images.append(img)
        
        # 2. Récupérer les images depuis entreprise_og_images (OpenGraph)
        self.execute_sql(cursor,'''
            SELECT image_url as url, alt_text, secure_url, image_type, width, height
            FROM entreprise_og_images
            WHERE entreprise_id = ?
            ORDER BY id DESC
        ''', (entreprise_id,))
        
        og_rows = cursor.fetchall()
        for row in og_rows:
            img = self.clean_row_dict(dict(row))
            # S'assurer que l'URL est complète
            if img.get('url'):
                images.append(img)
        
        # 3. Récupérer les images depuis les champs de la table entreprises
        self.execute_sql(cursor,'''
            SELECT og_image, logo, favicon
            FROM entreprises
            WHERE id = ?
        ''', (entreprise_id,))
        
        entreprise_row = cursor.fetchone()
        if entreprise_row:
            entreprise_data = self.clean_row_dict(dict(entreprise_row))
            
            if entreprise_data.get('og_image'):
                images.append({
                    'url': entreprise_data['og_image'],
                    'alt_text': 'Image OpenGraph',
                    'source': 'og_image'
                })
            if entreprise_data.get('logo'):
                images.append({
                    'url': entreprise_data['logo'],
                    'alt_text': 'Logo',
                    'source': 'logo'
                })
            if entreprise_data.get('favicon'):
                images.append({
                    'url': entreprise_data['favicon'],
                    'alt_text': 'Favicon',
                    'source': 'favicon'
                })
        
        conn.close()
        
        # Supprimer les doublons basés sur l'URL
        seen_urls = set()
        unique_images = []
        for img in images:
            url = img.get('url')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_images.append(img)
        
        return unique_images
    
    def get_scrapers_by_entreprise(self, entreprise_id):
        """
        Récupère tous les scrapers d'une entreprise avec leurs données normalisées
        
        Args:
            entreprise_id: ID de l'entreprise
        
        Returns:
            list: Liste des scrapers avec leurs données chargées depuis les tables normalisées
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT * FROM scrapers WHERE entreprise_id = ? 
            ORDER BY COALESCE(date_modification, date_creation) DESC
        ''', (entreprise_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        scrapers = []
        for row in rows:
            scraper = dict(row)
            scraper_id = scraper['id']
            
            # Charger depuis les tables normalisées
            scraper['emails'] = self.get_scraper_emails(scraper_id)
            scraper['phones'] = self.get_scraper_phones(scraper_id)
            scraper['social_profiles'] = self.get_scraper_social_profiles(scraper_id)
            scraper['technologies'] = self.get_scraper_technologies(scraper_id)
            scraper['people'] = self.get_scraper_people(scraper_id)
            
            # Charger les images depuis la table images
            scraper['images'] = self.get_images_by_scraper(scraper_id)
            
            # Metadata reste en JSON pour l'instant (structure complexe)
            if scraper.get('metadata'):
                try:
                    scraper['metadata'] = json.loads(scraper['metadata'])
                except:
                    pass
            
            scrapers.append(scraper)
        
        return scrapers
    
    def get_scraper_by_url(self, url, scraper_type):
        """
        Récupère un scraper par URL et type avec ses données normalisées
        
        Args:
            url: URL scrapée
            scraper_type: Type de scraper
        
        Returns:
            dict: Scraper ou None avec ses données chargées depuis les tables normalisées
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT * FROM scrapers WHERE url = ? AND scraper_type = ? 
            ORDER BY COALESCE(date_modification, date_creation) DESC LIMIT 1
        ''', (url, scraper_type))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            scraper = dict(row)
            scraper_id = scraper['id']
            
            # Charger depuis les tables normalisées
            scraper['emails'] = self.get_scraper_emails(scraper_id)
            scraper['phones'] = self.get_scraper_phones(scraper_id)
            scraper['social_profiles'] = self.get_scraper_social_profiles(scraper_id)
            scraper['technologies'] = self.get_scraper_technologies(scraper_id)
            scraper['people'] = self.get_scraper_people(scraper_id)
            
            # Metadata reste en JSON pour l'instant (structure complexe)
            if scraper.get('metadata'):
                try:
                    scraper['metadata'] = json.loads(scraper['metadata'])
                except:
                    pass
            
            return scraper
        
        return None
    
    def update_scraper(self, scraper_id, emails=None, people=None, visited_urls=None, total_emails=None, total_people=None, duration=None):
        """
        Met à jour un scraper existant
        
        Args:
            scraper_id: ID du scraper
            emails: Liste des emails (optionnel)
            people: Liste des personnes (optionnel)
            visited_urls: Nombre d'URLs visitées (optionnel)
            total_emails: Nombre total d'emails (optionnel)
            total_people: Nombre total de personnes (optionnel)
            duration: Durée du scraping (optionnel)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        if emails is not None:
            updates.append('emails = ?')
            values.append(json.dumps(emails))
        
        if people is not None:
            updates.append('people = ?')
            values.append(json.dumps(people))
        
        if visited_urls is not None:
            updates.append('visited_urls = ?')
            values.append(visited_urls)
        
        if total_emails is not None:
            updates.append('total_emails = ?')
            values.append(total_emails)
        
        if total_people is not None:
            updates.append('total_people = ?')
            values.append(total_people)
        
        if duration is not None:
            updates.append('duration = ?')
            values.append(duration)
        
        if updates:
            values.append(scraper_id)
            self.execute_sql(cursor,f'''
                UPDATE scrapers SET {', '.join(updates)} WHERE id = ?
            ''', values)
            
            conn.commit()
        
        conn.close()
    
    def delete_scraper(self, scraper_id):
        """
        Supprime un scraper
        
        Args:
            scraper_id: ID du scraper à supprimer
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'DELETE FROM scrapers WHERE id = ?', (scraper_id,))
        
        conn.commit()
        conn.close()
    
    def clean_duplicate_scraper_data(self):
        """
        Nettoie les doublons dans les tables scraper_* en gardant le plus récent.
        Cette fonction peut être appelée périodiquement pour maintenir l'intégrité des données.
        
        Returns:
            dict: Statistiques du nettoyage (nombre de doublons supprimés par table)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        stats = {}
        
        try:
            # Nettoyer scraper_emails
            self.execute_sql(cursor,'''
                DELETE FROM scraper_emails
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM scraper_emails
                    GROUP BY scraper_id, email
                )
            ''')
            stats['scraper_emails'] = cursor.rowcount
            
            # Nettoyer scraper_phones
            self.execute_sql(cursor,'''
                DELETE FROM scraper_phones
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM scraper_phones
                    GROUP BY scraper_id, phone
                )
            ''')
            stats['scraper_phones'] = cursor.rowcount
            
            # Nettoyer scraper_social_profiles
            self.execute_sql(cursor,'''
                DELETE FROM scraper_social_profiles
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM scraper_social_profiles
                    GROUP BY scraper_id, platform, url
                )
            ''')
            stats['scraper_social_profiles'] = cursor.rowcount
            
            # Nettoyer scraper_technologies
            self.execute_sql(cursor,'''
                DELETE FROM scraper_technologies
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM scraper_technologies
                    GROUP BY scraper_id, category, name
                )
            ''')
            stats['scraper_technologies'] = cursor.rowcount
            
            # Nettoyer scraper_people (garder le plus récent par scraper_id, name, email)
            self.execute_sql(cursor,'''
                DELETE FROM scraper_people
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM scraper_people
                    GROUP BY scraper_id, COALESCE(name, ''), COALESCE(email, '')
                )
            ''')
            stats['scraper_people'] = cursor.rowcount
            
            # Nettoyer scraper_forms (garder le plus récent par scraper_id, page_url, action_url)
            self.execute_sql(cursor,'''
                DELETE FROM scraper_forms
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM scraper_forms
                    GROUP BY scraper_id, page_url, COALESCE(action_url, '')
                )
            ''')
            stats['scraper_forms'] = cursor.rowcount
            
            conn.commit()
            
            total_removed = sum(stats.values())
            if total_removed > 0:
                logger.info(f'Nettoyage des doublons terminé: {total_removed} entrée(s) supprimée(s) - {stats}')
            else:
                logger.info('Aucun doublon trouvé dans les tables scraper_*')
            
        except Exception as e:
            logger.error(f'Erreur lors du nettoyage des doublons: {e}', exc_info=True)
            conn.rollback()
        finally:
            conn.close()
        
        return stats
