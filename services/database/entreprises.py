"""
Module de gestion des entreprises
Contient les méthodes pour la gestion des entreprises et leurs données OpenGraph
"""

import json
import math
import logging
from urllib.parse import urljoin
from .base import DatabaseBase

logger = logging.getLogger(__name__)


class EntrepriseManager(DatabaseBase):
    """
    Gère les entreprises et leurs données associées
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module entreprises"""
        super().__init__(*args, **kwargs)
    
    def find_duplicate_entreprise(self, nom, website=None, address_1=None, address_2=None):
        """
        Recherche si une entreprise similaire existe déjà dans la base
        
        Critères de détection de doublon (par ordre de priorité) :
        1. Nom + website identiques (le plus fiable)
        2. Nom + address_1 + address_2 identiques (si pas de website)
        3. Website seul (si nom manquant mais website présent)
        
        Args:
            nom (str): Nom de l'entreprise
            website (str, optional): Site web
            address_1 (str, optional): Adresse ligne 1
            address_2 (str, optional): Adresse ligne 2
        
        Returns:
            int or None: ID de l'entreprise existante si doublon trouvé, None sinon
        """
        if not nom:
            return None
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Normaliser les valeurs pour la comparaison (minuscules, espaces supprimés)
        def normalize(value):
            if not value:
                return None
            return str(value).lower().strip()
        
        nom_norm = normalize(nom)
        website_norm = normalize(website)
        address_1_norm = normalize(address_1)
        address_2_norm = normalize(address_2)
        
        # Critère 1: Nom + website identiques
        if nom_norm and website_norm:
            self.execute_sql(cursor,'''
                SELECT id FROM entreprises 
                WHERE LOWER(TRIM(nom)) = ? 
                AND LOWER(TRIM(website)) = ?
                LIMIT 1
            ''', (nom_norm, website_norm))
            row = cursor.fetchone()
            if row:
                conn.close()
                return row['id']
        
        # Critère 2: Nom + address_1 + address_2 identiques (si pas de website ou website différent)
        if nom_norm and address_1_norm and address_2_norm:
            self.execute_sql(cursor,'''
                SELECT id FROM entreprises 
                WHERE LOWER(TRIM(nom)) = ? 
                AND LOWER(TRIM(address_1)) = ?
                AND LOWER(TRIM(address_2)) = ?
                LIMIT 1
            ''', (nom_norm, address_1_norm, address_2_norm))
            row = cursor.fetchone()
            if row:
                conn.close()
                return row['id']
        
        conn.close()
        return None
    
    def save_entreprise(self, analyse_id, entreprise_data, skip_duplicates=True):
        """
        Sauvegarde une entreprise analysée
        
        Args:
            analyse_id (int): ID de l'analyse associée
            entreprise_data (dict): Données de l'entreprise
            skip_duplicates (bool): Si True, ne pas insérer si doublon trouvé (retourne l'ID existant)
        
        Returns:
            int or None: ID de l'entreprise (nouvelle ou existante), None si doublon et skip_duplicates=True
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Mapper les champs Excel vers les champs de la base de données
        nom = entreprise_data.get('name') or entreprise_data.get('nom')
        if not nom:
            nom = entreprise_data.get('website') or 'Entreprise inconnue'
        website = entreprise_data.get('website')
        secteur = entreprise_data.get('secteur') or entreprise_data.get('category_translate') or entreprise_data.get('category')
        telephone = entreprise_data.get('phone_number') or entreprise_data.get('telephone')
        pays = entreprise_data.get('country') or entreprise_data.get('pays')
        address_1 = entreprise_data.get('address_1')
        address_2 = entreprise_data.get('address_2')
        
        # Si address_full existe mais pas address_1/address_2, utiliser address_full pour address_1
        if not address_1 and not address_2:
            address_full = entreprise_data.get('address_full')
            if address_full:
                address_1 = address_full
        
        # Vérifier les doublons si activé
        if skip_duplicates and nom:
            duplicate_id = self.find_duplicate_entreprise(nom, website, address_1, address_2)
            if duplicate_id:
                # Mettre à jour analyse_id même pour les doublons pour que le scraping puisse les trouver
                if analyse_id:
                    try:
                        self.execute_sql(cursor, 'UPDATE entreprises SET analyse_id = ? WHERE id = ?', (analyse_id, duplicate_id))
                        conn.commit()
                    except Exception as e:
                        logger.warning(f'Erreur lors de la mise à jour de analyse_id pour entreprise {duplicate_id}: {e}')
                conn.close()
                return duplicate_id
        
        # Gérer longitude et latitude
        longitude = entreprise_data.get('longitude')
        if longitude is not None:
            try:
                longitude = float(longitude)
            except (ValueError, TypeError):
                longitude = None
        
        latitude = entreprise_data.get('latitude')
        if latitude is not None:
            try:
                latitude = float(latitude)
            except (ValueError, TypeError):
                latitude = None
        
        # Gérer rating et reviews_count
        note_google = entreprise_data.get('rating')
        if note_google is not None:
            try:
                note_google = float(note_google)
            except (ValueError, TypeError):
                note_google = None
        
        nb_avis_google = entreprise_data.get('reviews_count')
        if nb_avis_google is not None:
            try:
                nb_avis_google = int(nb_avis_google)
            except (ValueError, TypeError):
                nb_avis_google = None
        
        # Récupérer le résumé
        resume = entreprise_data.get('resume')
        try:
            if resume is not None:
                if isinstance(resume, float) and math.isnan(resume):
                    resume = None
                elif isinstance(resume, str) and resume.strip() == '':
                    resume = None
        except Exception:
            if isinstance(resume, str) and resume.strip() == '':
                resume = None
        
        # Récupérer les images et icônes depuis les métadonnées
        metadata = entreprise_data.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        
        icons = metadata.get('icons', {}) if isinstance(metadata, dict) else {}
        og_tags = metadata.get('open_graph', {}) if isinstance(metadata, dict) else {}
        
        # Extraire les URLs d'images
        og_image = icons.get('og_image') or None
        favicon = icons.get('favicon') or None
        logo = icons.get('logo') or None
        
        # Si les URLs sont relatives, les convertir en absolues avec le website
        if website:
            if og_image and not og_image.startswith(('http://', 'https://')):
                og_image = urljoin(website, og_image)
            if favicon and not favicon.startswith(('http://', 'https://')):
                favicon = urljoin(website, favicon)
            if logo and not logo.startswith(('http://', 'https://')):
                logo = urljoin(website, logo)
        
        self.execute_sql(cursor, '''
            INSERT INTO entreprises (
                analyse_id, nom, website, secteur, statut, opportunite,
                email_principal, responsable, taille_estimee, hosting_provider,
                framework, score_securite, telephone, pays, address_1, address_2,
                longitude, latitude, note_google, nb_avis_google, resume, og_image, favicon, logo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analyse_id,
            nom,
            website,
            secteur,
            entreprise_data.get('statut'),
            entreprise_data.get('site_opportunity'),
            entreprise_data.get('email_principal'),
            entreprise_data.get('responsable'),
            entreprise_data.get('taille_estimee'),
            entreprise_data.get('hosting_provider'),
            entreprise_data.get('framework'),
            entreprise_data.get('security_score'),
            telephone,
            pays,
            entreprise_data.get('address_1'),
            entreprise_data.get('address_2'),
            longitude,
            latitude,
            note_google,
            nb_avis_google,
            resume,
            og_image,
            favicon,
            logo
        ))
        
        entreprise_id = cursor.lastrowid
        
        # Sauvegarder les données OpenGraph normalisées si présentes
        if og_tags:
            self._save_og_data_in_transaction(cursor, entreprise_id, og_tags)
        
        conn.commit()
        conn.close()
        
        return entreprise_id
    
    def _save_og_data_in_transaction(self, cursor, entreprise_id, og_tags, page_url=None):
        """
        Sauvegarde les données OpenGraph normalisées dans les tables dédiées.
        Inspiré de https://ogp.me/
        
        Args:
            cursor: Curseur SQLite dans une transaction
            entreprise_id: ID de l'entreprise
            og_tags: Dictionnaire contenant les tags OpenGraph
            page_url: URL de la page d'où proviennent ces OG (optionnel)
        """
        # Extraire les propriétés de base
        og_title = og_tags.get('og:title') or og_tags.get('title')
        og_type = og_tags.get('og:type') or og_tags.get('type') or 'website'
        og_url = og_tags.get('og:url') or og_tags.get('url')
        og_description = og_tags.get('og:description') or og_tags.get('description')
        og_determiner = og_tags.get('og:determiner') or og_tags.get('determiner')
        og_locale = og_tags.get('og:locale') or og_tags.get('locale')
        og_site_name = og_tags.get('og:site_name') or og_tags.get('site_name')
        og_audio = og_tags.get('og:audio') or og_tags.get('audio')
        og_video = og_tags.get('og:video') or og_tags.get('video')
        
        # Supprimer les OG existants
        if page_url:
            self.execute_sql(cursor, 'DELETE FROM entreprise_og_data WHERE entreprise_id = ? AND page_url = ?', (entreprise_id, page_url))
        else:
            self.execute_sql(cursor, 'DELETE FROM entreprise_og_data WHERE entreprise_id = ? AND page_url IS NULL', (entreprise_id,))
        
        # Insérer les données principales
        self.execute_sql(cursor, '''
            INSERT INTO entreprise_og_data (
                entreprise_id, page_url, og_title, og_type, og_url, og_description,
                og_determiner, og_locale, og_site_name, og_audio, og_video
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entreprise_id, page_url, og_title, og_type, og_url, og_description,
            og_determiner, og_locale, og_site_name, og_audio, og_video
        ))
        
        og_data_id = cursor.lastrowid
        
        # Traiter les images
        images = []
        if 'og:image' in og_tags:
            img = og_tags['og:image']
            if isinstance(img, str):
                images.append({'url': img})
            elif isinstance(img, list):
                images.extend([{'url': i} if isinstance(i, str) else i for i in img])
            elif isinstance(img, dict):
                images.append(img)
        elif 'image' in og_tags:
            img = og_tags['image']
            if isinstance(img, str):
                images.append({'url': img})
            elif isinstance(img, list):
                images.extend([{'url': i} if isinstance(i, str) else i for i in img])
            elif isinstance(img, dict):
                images.append(img)
        
        for img_data in images:
            if isinstance(img_data, dict):
                image_url = img_data.get('og:image:url') or img_data.get('url') or img_data.get('og:image')
                if image_url:
                    self.execute_sql(cursor,'''
                        INSERT INTO entreprise_og_images (
                            entreprise_id, og_data_id, image_url, secure_url,
                            image_type, width, height, alt_text
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        entreprise_id,
                        og_data_id,
                        image_url,
                        img_data.get('og:image:secure_url') or img_data.get('secure_url'),
                        img_data.get('og:image:type') or img_data.get('type'),
                        img_data.get('og:image:width') or img_data.get('width'),
                        img_data.get('og:image:height') or img_data.get('height'),
                        img_data.get('og:image:alt') or img_data.get('alt')
                    ))
        
        # Traiter les vidéos
        videos = []
        if 'og:video' in og_tags:
            vid = og_tags['og:video']
            if isinstance(vid, str):
                videos.append({'url': vid})
            elif isinstance(vid, list):
                videos.extend([{'url': v} if isinstance(v, str) else v for v in vid])
            elif isinstance(vid, dict):
                videos.append(vid)
        elif 'video' in og_tags:
            vid = og_tags['video']
            if isinstance(vid, str):
                videos.append({'url': vid})
            elif isinstance(vid, list):
                videos.extend([{'url': v} if isinstance(v, str) else v for v in vid])
            elif isinstance(vid, dict):
                videos.append(vid)
        
        for vid_data in videos:
            if isinstance(vid_data, dict):
                video_url = vid_data.get('og:video:url') or vid_data.get('url') or vid_data.get('og:video')
                if video_url:
                    self.execute_sql(cursor,'''
                        INSERT INTO entreprise_og_videos (
                            entreprise_id, og_data_id, video_url, secure_url,
                            video_type, width, height
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        entreprise_id,
                        og_data_id,
                        video_url,
                        vid_data.get('og:video:secure_url') or vid_data.get('secure_url'),
                        vid_data.get('og:video:type') or vid_data.get('type'),
                        vid_data.get('og:video:width') or vid_data.get('width'),
                        vid_data.get('og:video:height') or vid_data.get('height')
                    ))
        
        # Traiter les audios
        audios = []
        if 'og:audio' in og_tags:
            aud = og_tags['og:audio']
            if isinstance(aud, str):
                audios.append({'url': aud})
            elif isinstance(aud, list):
                audios.extend([{'url': a} if isinstance(a, str) else a for a in aud])
            elif isinstance(aud, dict):
                audios.append(aud)
        elif 'audio' in og_tags:
            aud = og_tags['audio']
            if isinstance(aud, str):
                audios.append({'url': aud})
            elif isinstance(aud, list):
                audios.extend([{'url': a} if isinstance(a, str) else a for a in aud])
            elif isinstance(aud, dict):
                audios.append(aud)
        
        for aud_data in audios:
            if isinstance(aud_data, dict):
                audio_url = aud_data.get('og:audio:url') or aud_data.get('url') or aud_data.get('og:audio')
                if audio_url:
                    self.execute_sql(cursor,'''
                        INSERT INTO entreprise_og_audios (
                            entreprise_id, og_data_id, audio_url, secure_url, audio_type
                        ) VALUES (?, ?, ?, ?, ?)
                    ''', (
                        entreprise_id,
                        og_data_id,
                        audio_url,
                        aud_data.get('og:audio:secure_url') or aud_data.get('secure_url'),
                        aud_data.get('og:audio:type') or aud_data.get('type')
                    ))
        
        # Traiter les locales alternatives
        locales = og_tags.get('og:locale:alternate') or og_tags.get('locale:alternate') or []
        if isinstance(locales, str):
            locales = [locales]
        for locale in locales:
            if locale:
                self.execute_sql(cursor,'''
                    INSERT OR IGNORE INTO entreprise_og_locales (entreprise_id, og_data_id, locale)
                    VALUES (?, ?, ?)
                ''', (entreprise_id, og_data_id, locale))
    
    def _save_multiple_og_data_in_transaction(self, cursor, entreprise_id, og_data_by_page):
        """
        Sauvegarde plusieurs données OpenGraph (une par page) dans les tables dédiées.
        
        Args:
            cursor: Curseur SQLite dans une transaction
            entreprise_id: ID de l'entreprise
            og_data_by_page: Dictionnaire {page_url: og_tags} contenant les OG de chaque page
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f'[Database] Sauvegarde de {len(og_data_by_page)} page(s) avec OG pour entreprise {entreprise_id}')
        
        # Supprimer tous les OG existants pour cette entreprise avant d'insérer les nouveaux
        self.execute_sql(cursor,'DELETE FROM entreprise_og_data WHERE entreprise_id = ?', (entreprise_id,))
        deleted_count = cursor.rowcount
        
        # Sauvegarder chaque OG
        saved_count = 0
        for page_url, og_tags in og_data_by_page.items():
            if og_tags:
                try:
                    self._save_og_data_in_transaction(cursor, entreprise_id, og_tags, page_url=page_url)
                    saved_count += 1
                except Exception as e:
                    logger.error(f'[Database] Erreur lors de la sauvegarde de l\'OG pour entreprise {entreprise_id}, page {page_url}: {e}', exc_info=True)
        
        logger.info(f'[Database] {saved_count} OG sauvegardé(s) avec succès pour entreprise {entreprise_id}')
    
    def get_og_data(self, entreprise_id):
        """
        Récupère toutes les données OpenGraph normalisées pour une entreprise.
        Retourne une liste d'OG (un par page) ou un seul OG si page_url est NULL (compatibilité).
        
        Returns:
            list ou dict: Liste de dictionnaires contenant toutes les données OG structurées par page,
                         ou un seul dictionnaire si un seul OG existe (compatibilité)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Récupérer toutes les données principales (une par page)
        self.execute_sql(cursor,'''
            SELECT * FROM entreprise_og_data WHERE entreprise_id = ?
            ORDER BY page_url IS NULL DESC, page_url ASC, date_creation ASC
        ''', (entreprise_id,))
        og_rows = cursor.fetchall()
        
        if not og_rows:
            conn.close()
            return None
        
        # Si un seul OG sans page_url (ancien format), retourner un dict pour compatibilité
        if len(og_rows) == 1 and og_rows[0]['page_url'] is None:
            og_data = dict(og_rows[0])
            og_data_id = og_data['id']
            
            # Récupérer les images, vidéos, audios, locales pour cet OG
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_images WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['images'] = [dict(row) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_videos WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['videos'] = [dict(row) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_audios WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['audios'] = [dict(row) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT locale FROM entreprise_og_locales WHERE og_data_id = ? ORDER BY locale', (og_data_id,))
            og_data['locales_alternate'] = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            return og_data
        
        # Plusieurs OG : retourner une liste
        all_og_data = []
        for og_row in og_rows:
            og_data = dict(og_row)
            og_data_id = og_data['id']
            
            # Récupérer les images, vidéos, audios, locales pour cet OG
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_images WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['images'] = [dict(row) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_videos WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['videos'] = [dict(row) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_audios WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['audios'] = [dict(row) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT locale FROM entreprise_og_locales WHERE og_data_id = ? ORDER BY locale', (og_data_id,))
            og_data['locales_alternate'] = [row[0] for row in cursor.fetchall()]
            
            all_og_data.append(og_data)
        
        conn.close()
        return all_og_data
    
    def get_entreprises(self, analyse_id=None, filters=None, limit=None, offset=None):
        """
        Récupère les entreprises avec filtres optionnels
        
        Args:
            analyse_id: ID de l'analyse (optionnel)
            filters: Dictionnaire de filtres (secteur, statut, opportunite, favori, search)
            limit: Nombre maximum de résultats (optionnel)
            offset: Offset pour la pagination (optionnel)
        
        Returns:
            Liste des entreprises avec leurs données OG et score pentest (dernier score disponible)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Récupérer le dernier score pentest pour chaque entreprise via une sous-requête
        query = '''
            SELECT e.*, 
                   (SELECT risk_score 
                    FROM analyses_pentest 
                    WHERE entreprise_id = e.id 
                    ORDER BY date_analyse DESC 
                    LIMIT 1) as score_pentest
            FROM entreprises e
            WHERE 1=1
        '''
        params = []
        
        if analyse_id:
            query += ' AND e.analyse_id = ?'
            params.append(analyse_id)
        
        if filters:
            if filters.get('secteur'):
                query += ' AND e.secteur = ?'
                params.append(filters['secteur'])
            if filters.get('statut'):
                query += ' AND e.statut = ?'
                params.append(filters['statut'])
            if filters.get('opportunite'):
                query += ' AND e.opportunite = ?'
                params.append(filters['opportunite'])
            if filters.get('favori'):
                query += ' AND e.favori = 1'
            if filters.get('search'):
                search_term = f"%{filters['search']}%"
                query += ' AND (e.nom LIKE ? OR e.secteur LIKE ? OR e.email_principal LIKE ? OR e.responsable LIKE ?)'
                params.extend([search_term, search_term, search_term, search_term])
        
        query += ' ORDER BY e.favori DESC, e.date_analyse DESC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        if offset:
            query += ' OFFSET ?'
            params.append(offset)
        
        self.execute_sql(cursor,query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Parser les tags et charger les données OpenGraph pour chaque entreprise
        entreprises = []
        for row in rows:
            entreprise = dict(row)
            if entreprise.get('tags'):
                try:
                    entreprise['tags'] = json.loads(entreprise['tags']) if isinstance(entreprise['tags'], str) else entreprise['tags']
                except:
                    entreprise['tags'] = []
            else:
                entreprise['tags'] = []
            
            # Charger les données OpenGraph depuis les tables normalisées
            entreprise['og_data'] = self.get_og_data(entreprise['id'])
            
            entreprises.append(entreprise)
        
        return entreprises
    
    def get_entreprise(self, entreprise_id):
        """
        Récupère une entreprise par son ID avec ses données complètes.
        
        Args:
            entreprise_id (int): ID de l'entreprise
            
        Returns:
            dict|None: Dictionnaire avec les données de l'entreprise, None si non trouvée
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT e.*, 
                   (SELECT risk_score 
                    FROM analyses_pentest 
                    WHERE entreprise_id = e.id 
                    ORDER BY date_analyse DESC 
                    LIMIT 1) as score_pentest
            FROM entreprises e
            WHERE e.id = ?
        ''', (entreprise_id,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        entreprise = dict(row)
        
        # Parser les tags
        if entreprise.get('tags'):
            try:
                entreprise['tags'] = json.loads(entreprise['tags']) if isinstance(entreprise['tags'], str) else entreprise['tags']
            except:
                entreprise['tags'] = []
        else:
            entreprise['tags'] = []
        
        # Charger les données OpenGraph
        entreprise['og_data'] = self.get_og_data(entreprise_id)
        
        conn.close()
        return entreprise
    
    def update_entreprise_tags(self, entreprise_id, tags):
        """
        Met à jour les tags d'une entreprise
        
        Args:
            entreprise_id: ID de l'entreprise
            tags: Liste de tags ou chaîne JSON
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            UPDATE entreprises SET tags = ? WHERE id = ?
        ''', (json.dumps(tags) if isinstance(tags, list) else tags, entreprise_id))
        
        conn.commit()
        conn.close()
    
    def update_entreprise_notes(self, entreprise_id, notes):
        """
        Met à jour les notes d'une entreprise
        
        Args:
            entreprise_id: ID de l'entreprise
            notes: Texte des notes
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            UPDATE entreprises SET notes = ? WHERE id = ?
        ''', (notes, entreprise_id))
        
        conn.commit()
        conn.close()
    
    def toggle_favori(self, entreprise_id):
        """
        Bascule le statut favori d'une entreprise
        
        Args:
            entreprise_id: ID de l'entreprise
        
        Returns:
            bool: True si maintenant favori, False sinon
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'SELECT favori FROM entreprises WHERE id = ?', (entreprise_id,))
        current = cursor.fetchone()[0]
        new_value = 0 if current else 1
        
        self.execute_sql(cursor,'UPDATE entreprises SET favori = ? WHERE id = ?', (new_value, entreprise_id))
        conn.commit()
        conn.close()
        
        return new_value == 1
    
    def get_nearby_entreprises(self, latitude, longitude, radius_km=10, secteur=None, limit=50):
        """
        Trouve les entreprises proches d'un point géographique
        
        Utilise la formule de Haversine pour calculer la distance en kilomètres
        entre deux points sur la surface de la Terre.
        
        Args:
            latitude (float): Latitude du point de référence
            longitude (float): Longitude du point de référence
            radius_km (float): Rayon de recherche en kilomètres (défaut: 10 km)
            secteur (str, optional): Filtrer par secteur d'activité
            limit (int): Nombre maximum de résultats (défaut: 50)
        
        Returns:
            list: Liste de dictionnaires contenant les entreprises avec leur distance
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Formule de Haversine pour calculer la distance en km
        haversine_query = '''
            SELECT 
                id, nom, website, secteur, statut, opportunite,
                email_principal, telephone, address_1, address_2, pays,
                longitude, latitude, note_google, nb_avis_google,
                (
                    6371 * acos(
                        cos(radians(?)) * cos(radians(latitude)) *
                        cos(radians(longitude) - radians(?)) +
                        sin(radians(?)) * sin(radians(latitude))
                    )
                ) AS distance_km
            FROM entreprises
            WHERE longitude IS NOT NULL 
                AND latitude IS NOT NULL
                AND (
                    6371 * acos(
                        cos(radians(?)) * cos(radians(latitude)) *
                        cos(radians(longitude) - radians(?)) +
                        sin(radians(?)) * sin(radians(latitude))
                    )
                ) <= ?
        '''
        
        params = [latitude, longitude, latitude, latitude, longitude, latitude, radius_km]
        
        if secteur:
            haversine_query += ' AND secteur = ?'
            params.append(secteur)
        
        haversine_query += ' ORDER BY distance_km ASC LIMIT ?'
        params.append(limit)
        
        self.execute_sql(cursor,haversine_query, params)
        
        rows = cursor.fetchall()
        conn.close()
        
        entreprises = []
        for row in rows:
            entreprise = dict(row)
            entreprise['distance_km'] = round(entreprise['distance_km'], 2)
            entreprises.append(entreprise)
        
        return entreprises
    
    def get_entreprises_by_secteur_nearby(self, secteur, latitude, longitude, radius_km=10, limit=50):
        """
        Trouve les entreprises d'un secteur spécifique proches d'un point
        
        Utile pour analyser la concurrence locale dans un secteur donné.
        
        Args:
            secteur (str): Secteur d'activité
            latitude (float): Latitude du point de référence
            longitude (float): Longitude du point de référence
            radius_km (float): Rayon de recherche en kilomètres (défaut: 10 km)
            limit (int): Nombre maximum de résultats (défaut: 50)
        
        Returns:
            list: Liste de dictionnaires contenant les entreprises avec leur distance
        """
        return self.get_nearby_entreprises(latitude, longitude, radius_km, secteur, limit)
    
    def get_competition_analysis(self, entreprise_id, radius_km=10):
        """
        Analyse la concurrence locale pour une entreprise donnée
        
        Trouve les entreprises du même secteur dans un rayon donné.
        
        Args:
            entreprise_id (int): ID de l'entreprise de référence
            radius_km (float): Rayon de recherche en kilomètres (défaut: 10 km)
        
        Returns:
            dict: Analyse de la concurrence avec statistiques
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Récupérer l'entreprise de référence
        self.execute_sql(cursor,'''
            SELECT secteur, longitude, latitude FROM entreprises WHERE id = ?
        ''', (entreprise_id,))
        
        entreprise_ref = cursor.fetchone()
        if not entreprise_ref or not entreprise_ref['longitude'] or not entreprise_ref['latitude']:
            conn.close()
            return {'error': 'Entreprise introuvable ou sans coordonnées géographiques'}
        
        secteur = entreprise_ref['secteur']
        latitude = entreprise_ref['latitude']
        longitude = entreprise_ref['longitude']
        
        conn.close()
        
        # Trouver les concurrents
        concurrents = self.get_entreprises_by_secteur_nearby(
            secteur, latitude, longitude, radius_km, limit=100
        )
        
        # Filtrer l'entreprise de référence
        concurrents = [c for c in concurrents if c['id'] != entreprise_id]
        
        # Calculer les statistiques
        stats = {
            'entreprise_id': entreprise_id,
            'secteur': secteur,
            'rayon_km': radius_km,
            'total_concurrents': len(concurrents),
            'concurrents': concurrents[:20],
            'distance_moyenne': round(sum(c['distance_km'] for c in concurrents) / len(concurrents), 2) if concurrents else 0,
            'distance_min': round(min(c['distance_km'] for c in concurrents), 2) if concurrents else 0,
            'distance_max': round(max(c['distance_km'] for c in concurrents), 2) if concurrents else 0,
            'note_moyenne': round(sum(c.get('note_google', 0) or 0 for c in concurrents) / len([c for c in concurrents if c.get('note_google')]), 2) if concurrents else 0,
            'nb_avis_total': sum(c.get('nb_avis_google', 0) or 0 for c in concurrents)
        }
        
        return stats

    def get_statistics(self):
        """
        Récupère les statistiques globales de l'application.
        
        Returns:
            dict: Dictionnaire avec les statistiques
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total analyses
        try:
            self.execute_sql(cursor,'SELECT COUNT(*) as count FROM analyses')
            stats['total_analyses'] = cursor.fetchone()['count']
        except Exception:
            stats['total_analyses'] = 0
        
        # Total entreprises
        try:
            self.execute_sql(cursor,'SELECT COUNT(*) as count FROM entreprises')
            stats['total_entreprises'] = cursor.fetchone()['count']
        except Exception:
            stats['total_entreprises'] = 0
        
        # Favoris
        try:
            self.execute_sql(cursor,'SELECT COUNT(*) as count FROM entreprises WHERE favori = 1')
            stats['favoris'] = cursor.fetchone()['count']
        except Exception:
            stats['favoris'] = 0
        
        # Par statut
        try:
            self.execute_sql(cursor,'''
                SELECT statut, COUNT(*) as count 
                FROM entreprises 
                WHERE statut IS NOT NULL AND statut != ''
                GROUP BY statut
            ''')
            stats['par_statut'] = {row['statut']: row['count'] for row in cursor.fetchall()}
        except Exception:
            stats['par_statut'] = {}
        
        # Par secteur
        try:
            self.execute_sql(cursor,'''
                SELECT secteur, COUNT(*) as count 
                FROM entreprises 
                WHERE secteur IS NOT NULL AND secteur != ''
                GROUP BY secteur
                ORDER BY count DESC
            ''')
            stats['par_secteur'] = {row['secteur']: row['count'] for row in cursor.fetchall()}
        except Exception:
            stats['par_secteur'] = {}
        
        # Par opportunité
        try:
            self.execute_sql(cursor,'''
                SELECT opportunite, COUNT(*) as count 
                FROM entreprises 
                WHERE opportunite IS NOT NULL AND opportunite != ''
                GROUP BY opportunite
                ORDER BY count DESC
            ''')
            stats['par_opportunite'] = {row['opportunite']: row['count'] for row in cursor.fetchall()}
        except Exception:
            stats['par_opportunite'] = {}
        
        conn.close()
        return stats
    
    def get_entreprises_with_emails(self):
        """
        Récupère toutes les entreprises avec leurs emails disponibles pour les campagnes.

        Returns:
            list[dict]: Liste des entreprises avec leurs emails (depuis scraper_emails)
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()

        # Récupérer les entreprises avec leurs emails depuis scraper_emails
        self.execute_sql(cursor,'''
            SELECT DISTINCT
                e.id,
                e.nom,
                e.secteur,
                se.email,
                se.name_info as email_nom,
                se.page_url as source,
                se.entreprise_id
            FROM entreprises e
            INNER JOIN scraper_emails se ON e.id = se.entreprise_id
            WHERE se.email IS NOT NULL AND se.email != ''
            ORDER BY e.nom, se.email
        ''')

        rows = cursor.fetchall()
        conn.close()

        # Grouper par entreprise
        entreprises_dict = {}
        for row in rows:
            entreprise_id = row['id']
            if entreprise_id not in entreprises_dict:
                entreprises_dict[entreprise_id] = {
                    'id': entreprise_id,
                    'nom': row['nom'],
                    'secteur': row['secteur'],
                    'emails': []
                }

            # Utiliser page_url comme source si disponible, sinon 'scraper'
            source = row['source'] if row['source'] else 'scraper'
            if source == 'scraper' and row['source']:
                source = row['source']
            
            # Formater le nom depuis name_info (JSON)
            from utils.name_formatter import format_name
            email_nom = format_name(row['email_nom'])

            entreprises_dict[entreprise_id]['emails'].append({
                'email': row['email'],
                'nom': email_nom,
                'source': source,
                'entreprise_id': row['entreprise_id']
            })

        return list(entreprises_dict.values())
