"""
Module de gestion des entreprises
Contient les méthodes pour la gestion des entreprises et leurs données OpenGraph
"""

import json
import math
import logging
import re
from typing import Optional
from urllib.parse import urljoin
from utils.url_utils import normalize_website_domain
from .base import DatabaseBase

logger = logging.getLogger(__name__)

# Statuts "métier" supportés pour le suivi commercial et la délivrabilité.
# IMPORTANT: ces valeurs sont consommées par l'UI (filtres) et par l'API publique.
ENTERPRISE_STATUSES: set[str] = {
    # Pipeline commercial historique
    'Nouveau',
    'À qualifier',
    'Relance',
    'Gagné',
    'Perdu',
    # Statuts liés aux retours campagnes / délivrabilité / opt-out
    'Désabonné',
    'Réponse négative',
    'Réponse positive',
    'Bounce',
    'Plainte spam',
    'Ne pas contacter',
    'À rappeler',
}

# Importer le calculateur d'opportunité
try:
    from services.opportunity_calculator import OpportunityCalculator
except ImportError:
    OpportunityCalculator = None
    logger.warning('OpportunityCalculator non disponible')


class EntrepriseManager(DatabaseBase):
    """
    Gère les entreprises et leurs données associées
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module entreprises"""
        super().__init__(*args, **kwargs)

    @staticmethod
    def _truthy_filter(filters, key):
        """True si le filtre booléen (query string) est activé : 1, true, yes."""
        if not filters:
            return False
        v = filters.get(key)
        if v is None:
            return False
        return str(v).lower() in ('1', 'true', 'yes')
    
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
        # Au moins nom ou website requis pour chercher un doublon
        if not nom and not website:
            return None
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Normaliser les valeurs pour la comparaison
        # - nom / adresses : minuscules + trim
        # - website : domaine normalisé (ignorer http/https, www., slash de fin)
        def normalize_text(value):
            if not value:
                return None
            return str(value).lower().strip()

        nom_norm = normalize_text(nom)
        website_norm = normalize_website_domain(website)
        address_1_norm = normalize_text(address_1)
        address_2_norm = normalize_text(address_2)
        
        # Critère 1: domaine du site unique (indépendamment du nom/adresse)
        if website_norm:
            try:
                self.execute_sql(cursor, 'SELECT id, website FROM entreprises WHERE website IS NOT NULL')
                rows = cursor.fetchall()
                for row in rows:
                    # sqlite3.Row / tuple / dict (RealDictRow) -> normaliser l'accès
                    try:
                        if isinstance(row, dict):
                            existing_id = row.get('id')
                            existing_website = row.get('website')
                        else:
                            existing_id = row[0]
                            existing_website = row[1] if len(row) > 1 else None
                    except (KeyError, IndexError, TypeError):
                        continue
                    existing_domain = normalize_website_domain(existing_website)
                    if existing_domain and existing_domain == website_norm:
                        conn.close()
                        return existing_id
            except Exception:
                # En cas de problème de lecture, on retombe sur les critères suivants
                pass
        
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
        
        params = (
            analyse_id,
            nom,
            website,
            secteur,
            (entreprise_data.get('statut') or 'Nouveau'),
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
        )

        # IMPORTANT :
        # - En SQLite, on peut utiliser cursor.lastrowid après INSERT.
        # - En PostgreSQL, cursor.lastrowid n'est pas fiable : il faut utiliser RETURNING id.
        if self.is_postgresql():
            insert_sql = '''
                INSERT INTO entreprises (
                    analyse_id, nom, website, secteur, statut, opportunite,
                    email_principal, responsable, taille_estimee, hosting_provider,
                    framework, score_securite, telephone, pays, address_1, address_2,
                    longitude, latitude, note_google, nb_avis_google, resume, og_image, favicon, logo
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
            '''
            cursor.execute(insert_sql, params)
            row = cursor.fetchone()
            if not row:
                entreprise_id = None
            elif isinstance(row, dict):
                # Avec RealDictCursor (psycopg2) on reçoit un dict
                entreprise_id = row.get('id')
            else:
                # Fallback tuple (id, ...)
                entreprise_id = row[0]
        else:
            # Mode SQLite (ou autre) : on garde execute_sql + lastrowid
            self.execute_sql(cursor, '''
                INSERT INTO entreprises (
                    analyse_id, nom, website, secteur, statut, opportunite,
                    email_principal, responsable, taille_estimee, hosting_provider,
                    framework, score_securite, telephone, pays, address_1, address_2,
                    longitude, latitude, note_google, nb_avis_google, resume, og_image, favicon, logo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', params)
            entreprise_id = cursor.lastrowid
        
        # Sauvegarder les données OpenGraph normalisées si présentes
        if og_tags:
            self._save_og_data_in_transaction(cursor, entreprise_id, og_tags)
        
        conn.commit()
        conn.close()
        
        # Calculer et mettre à jour l'opportunité si le calculateur est disponible
        # (fait après le commit pour éviter les problèmes de transaction)
        if OpportunityCalculator:
            try:
                # Attendre un peu pour s'assurer que les données sont bien sauvegardées
                import time
                time.sleep(0.1)
                self.update_opportunity_score(entreprise_id)
            except Exception as e:
                logger.warning(f'Erreur lors du calcul initial de l\'opportunité pour entreprise {entreprise_id}: {e}')
        
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
        
        # Insérer les données principales (PostgreSQL : RETURNING id car lastrowid n'existe pas)
        if self.is_postgresql():
            self.execute_sql(cursor, '''
                INSERT INTO entreprise_og_data (
                    entreprise_id, page_url, og_title, og_type, og_url, og_description,
                    og_determiner, og_locale, og_site_name, og_audio, og_video
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            ''', (
                entreprise_id, page_url, og_title, og_type, og_url, og_description,
                og_determiner, og_locale, og_site_name, og_audio, og_video
            ))
            result = cursor.fetchone()
            og_data_id = result.get('id') if isinstance(result, dict) else (result[0] if result else None)
        else:
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
        
        if not og_data_id:
            return
        
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
            og_data['images'] = [self.clean_row_dict(dict(row)) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_videos WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['videos'] = [self.clean_row_dict(dict(row)) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_audios WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['audios'] = [self.clean_row_dict(dict(row)) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT locale FROM entreprise_og_locales WHERE og_data_id = ? ORDER BY locale', (og_data_id,))
            og_data['locales_alternate'] = [row['locale'] for row in cursor.fetchall()]
            
            conn.close()
            return og_data
        
        # Plusieurs OG : retourner une liste
        all_og_data = []
        for og_row in og_rows:
            og_data = dict(og_row)
            og_data_id = og_data['id']
            
            # Récupérer les images, vidéos, audios, locales pour cet OG
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_images WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['images'] = [self.clean_row_dict(dict(row)) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_videos WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['videos'] = [self.clean_row_dict(dict(row)) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT * FROM entreprise_og_audios WHERE og_data_id = ? ORDER BY id', (og_data_id,))
            og_data['audios'] = [self.clean_row_dict(dict(row)) for row in cursor.fetchall()]
            
            self.execute_sql(cursor,'SELECT locale FROM entreprise_og_locales WHERE og_data_id = ? ORDER BY locale', (og_data_id,))
            og_data['locales_alternate'] = [row['locale'] for row in cursor.fetchall()]
            
            all_og_data.append(og_data)
        
        conn.close()
        return all_og_data
    
    def get_entreprises(self, analyse_id=None, filters=None, limit=None, offset=None, include_og=True):
        """
        Récupère les entreprises avec filtres optionnels
        
        Args:
            analyse_id: ID de l'analyse (optionnel)
            filters: Dictionnaire de filtres (secteur, statut, opportunite, favori, search,
                     security_min, security_max, pentest_min, pentest_max)
            limit: Nombre maximum de résultats (optionnel)
            offset: Offset pour la pagination (optionnel)

        Returns:
            Liste des entreprises avec, optionnellement, leurs données OG et score pentest / SEO (derniers scores disponibles)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        has_security_filters = filters and (
            any(filters.get(k) is not None for k in ('security_min', 'security_max'))
            or EntrepriseManager._truthy_filter(filters, 'security_null')
        )
        has_pentest_filters = filters and (
            any(filters.get(k) is not None for k in ('pentest_min', 'pentest_max'))
            or EntrepriseManager._truthy_filter(filters, 'pentest_null')
        )
        has_seo_filters = filters and (
            any(filters.get(k) is not None for k in ('seo_min', 'seo_max'))
            or EntrepriseManager._truthy_filter(filters, 'seo_null')
        )
        wrap_subquery = has_security_filters or has_pentest_filters or has_seo_filters

        inner_query = '''
            SELECT e.*,
                   (SELECT risk_score
                    FROM analyses_pentest
                    WHERE entreprise_id = e.id
                    ORDER BY date_analyse DESC
                    LIMIT 1) as score_pentest,
                   (SELECT score
                    FROM analyses_seo
                    WHERE entreprise_id = e.id
                    ORDER BY date_analyse DESC
                    LIMIT 1) as score_seo
            FROM entreprises e
            WHERE 1=1
        '''
        params = []

        if analyse_id:
            inner_query += ' AND e.analyse_id = ?'
            params.append(analyse_id)

        if filters:
            if filters.get('secteur'):
                inner_query += ' AND e.secteur = ?'
                params.append(filters['secteur'])
            if filters.get('statut'):
                statut_val = filters['statut']
                if isinstance(statut_val, (list, tuple, set)):
                    statut_list = [s for s in statut_val if s is not None and str(s).strip() != '']
                    if statut_list:
                        placeholders = ','.join(['?' for _ in statut_list])
                        inner_query += f' AND e.statut IN ({placeholders})'
                        params.extend(statut_list)
                else:
                    inner_query += ' AND e.statut = ?'
                    params.append(statut_val)
            if filters.get('opportunite'):
                inner_query += ' AND e.opportunite = ?'
                params.append(filters['opportunite'])
            if filters.get('favori'):
                inner_query += ' AND e.favori = 1'
            # Filtrer par appartenance à un groupe spécifique
            if filters.get('groupe_id') is not None:
                inner_query += ' AND e.id IN (SELECT entreprise_id FROM entreprise_groupes WHERE groupe_id = ?)'
                params.append(filters['groupe_id'])
            # Filtrer les entreprises qui n'appartiennent à aucun groupe
            if str(filters.get('no_group', '')).lower() in ('1', 'true', 'yes'):
                inner_query += ' AND e.id NOT IN (SELECT entreprise_id FROM entreprise_groupes)'
            if str(filters.get('has_email', '')).lower() in ('1', 'true', 'yes'):
                # "has_email" côté UI veut dire "entreprise avec au moins un email connu".
                # Sources prises en compte: email principal, scraper_emails,
                # personnes.email, scraper_people.email et emails OSINT.
                inner_query += """
                    AND (
                        (e.email_principal IS NOT NULL AND TRIM(e.email_principal) <> '')
                        OR EXISTS (
                            SELECT 1
                            FROM scraper_emails se
                            WHERE se.entreprise_id = e.id
                              AND se.email IS NOT NULL
                              AND TRIM(se.email) <> ''
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM personnes p
                            WHERE p.entreprise_id = e.id
                              AND p.email IS NOT NULL
                              AND TRIM(p.email) <> ''
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM scraper_people sp
                            WHERE sp.entreprise_id = e.id
                              AND sp.email IS NOT NULL
                              AND TRIM(sp.email) <> ''
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM analyses_osint ao
                            JOIN analysis_osint_emails aoe ON aoe.analysis_id = ao.id
                            WHERE ao.entreprise_id = e.id
                              AND aoe.email IS NOT NULL
                              AND TRIM(aoe.email) <> ''
                        )
                    )
                """
            # Nouveaux filtres de segmentation
            if filters.get('cms'):
                cms_val = filters['cms']
                if isinstance(cms_val, (list, tuple, set)):
                    placeholders = ','.join(['?' for _ in cms_val])
                    inner_query += f' AND e.cms IN ({placeholders})'
                    params.extend(list(cms_val))
                else:
                    inner_query += ' AND e.cms = ?'
                    params.append(cms_val)
            if filters.get('framework'):
                fw_val = filters['framework']
                if isinstance(fw_val, (list, tuple, set)):
                    placeholders = ','.join(['?' for _ in fw_val])
                    inner_query += f' AND e.framework IN ({placeholders})'
                    params.extend(list(fw_val))
                else:
                    inner_query += ' AND e.framework = ?'
                    params.append(fw_val)
            if str(filters.get('has_blog', '')).lower() in ('1', 'true', 'yes'):
                inner_query += ' AND e.has_blog = 1'
            if str(filters.get('has_form', '')).lower() in ('1', 'true', 'yes'):
                inner_query += ' AND e.has_contact_form = 1'
            if str(filters.get('has_tunnel', '')).lower() in ('1', 'true', 'yes'):
                inner_query += ' AND e.has_checkout = 1'
            if filters.get('performance_min') is not None:
                inner_query += ' AND e.performance_score IS NOT NULL AND e.performance_score >= ?'
                params.append(int(filters['performance_min']))
            if filters.get('performance_max') is not None:
                inner_query += ' AND e.performance_score IS NOT NULL AND e.performance_score <= ?'
                params.append(int(filters['performance_max']))
            if filters.get('search'):
                # Recherche full-text simple, insensible à la casse, multi-mots.
                # Exemple: "boulanger metz" doit matcher nom + ville/adresse.
                raw_search = str(filters['search']).strip()
                tokens = [t.lower() for t in re.split(r'\s+', raw_search) if t.strip()]
                for token in tokens:
                    like = f"%{token}%"
                    inner_query += '''
                        AND (
                            LOWER(e.nom) LIKE ?
                            OR LOWER(e.secteur) LIKE ?
                            OR LOWER(COALESCE(e.email_principal, '')) LIKE ?
                            OR EXISTS (
                                SELECT 1
                                FROM scraper_emails se
                                WHERE se.entreprise_id = e.id
                                  AND se.email IS NOT NULL
                                  AND LOWER(se.email) LIKE ?
                            )
                            OR LOWER(COALESCE(e.responsable, '')) LIKE ?
                            OR LOWER(COALESCE(e.website, '')) LIKE ?
                            OR LOWER(COALESCE(e.address_1, '')) LIKE ?
                            OR LOWER(COALESCE(e.address_2, '')) LIKE ?
                            OR LOWER(COALESCE(e.tags, '')) LIKE ?
                        )
                    '''
                    # Même token appliqué sur tous les champs cibles
                    params.extend([like] * 9)

            # Filtres sur les tags (JSON/texte)
            if filters.get('tags_contains'):
                inner_query += ' AND e.tags LIKE ?'
                params.append('%' + str(filters['tags_contains']) + '%')
            if filters.get('tags_any'):
                values = filters['tags_any']
                if isinstance(values, str):
                    values = [v.strip() for v in values.split(',') if v.strip()]
                conditions = []
                for v in values:
                    conditions.append('e.tags LIKE ?')
                    params.append('%' + str(v) + '%')
                if conditions:
                    inner_query += ' AND (' + ' OR '.join(conditions) + ')'
            if filters.get('tags_all'):
                values = filters['tags_all']
                if isinstance(values, str):
                    values = [v.strip() for v in values.split(',') if v.strip()]
                for v in values:
                    inner_query += ' AND e.tags LIKE ?'
                    params.append('%' + str(v) + '%')

        if wrap_subquery:
            # Filtres plage : analyses non faites = score 0 via COALESCE (exclure avec min > 0).
            # Filtres *_null : uniquement entreprises sans analyse (score IS NULL en base / sous-requête).
            query = 'SELECT sub.* FROM (' + inner_query + ') sub WHERE 1=1'
            if has_security_filters:
                if EntrepriseManager._truthy_filter(filters, 'security_null'):
                    query += ' AND sub.score_securite IS NULL'
                else:
                    if filters.get('security_min') is not None:
                        query += ' AND (COALESCE(sub.score_securite, 0) >= ?)'
                        params.append(filters['security_min'])
                    if filters.get('security_max') is not None:
                        query += ' AND (COALESCE(sub.score_securite, 0) <= ?)'
                        params.append(filters['security_max'])
            if has_pentest_filters:
                if EntrepriseManager._truthy_filter(filters, 'pentest_null'):
                    query += ' AND sub.score_pentest IS NULL'
                else:
                    if filters.get('pentest_min') is not None:
                        query += ' AND (COALESCE(sub.score_pentest, 0) >= ?)'
                        params.append(filters['pentest_min'])
                    if filters.get('pentest_max') is not None:
                        query += ' AND (COALESCE(sub.score_pentest, 0) <= ?)'
                        params.append(filters['pentest_max'])
            if has_seo_filters:
                if EntrepriseManager._truthy_filter(filters, 'seo_null'):
                    query += ' AND sub.score_seo IS NULL'
                else:
                    if filters.get('seo_min') is not None:
                        query += ' AND (COALESCE(sub.score_seo, 0) >= ?)'
                        params.append(filters['seo_min'])
                    if filters.get('seo_max') is not None:
                        query += ' AND (COALESCE(sub.score_seo, 0) <= ?)'
                        params.append(filters['seo_max'])

            # Tri par pertinence si recherche textuelle présente
            if filters and filters.get('search'):
                search_full = str(filters['search']).strip().lower()
                prefix = f"{search_full}%"
                like_full = f"%{search_full}%"
                query += '''
                    ORDER BY
                        sub.favori DESC,
                        CASE
                            WHEN LOWER(sub.nom) = ? THEN 5
                            WHEN LOWER(sub.nom) LIKE ? THEN 4
                            WHEN LOWER(COALESCE(sub.website, '')) LIKE ? THEN 3
                            WHEN LOWER(COALESCE(sub.address_1, '')) LIKE ?
                                 OR LOWER(COALESCE(sub.address_2, '')) LIKE ? THEN 2
                            ELSE 0
                        END DESC,
                        sub.date_analyse DESC
                '''
                params.extend([search_full, prefix, like_full, like_full, like_full])
            else:
                query += ' ORDER BY sub.favori DESC, sub.date_analyse DESC'
        else:
            # Pas de sous-requête: mêmes règles de tri mais en se basant directement sur e.*
            if filters and filters.get('search'):
                search_full = str(filters['search']).strip().lower()
                prefix = f"{search_full}%"
                like_full = f"%{search_full}%"
                query = inner_query + '''
                    ORDER BY
                        e.favori DESC,
                        CASE
                            WHEN LOWER(e.nom) = ? THEN 5
                            WHEN LOWER(e.nom) LIKE ? THEN 4
                            WHEN LOWER(COALESCE(e.website, '')) LIKE ? THEN 3
                            WHEN LOWER(COALESCE(e.address_1, '')) LIKE ?
                                 OR LOWER(COALESCE(e.address_2, '')) LIKE ? THEN 2
                            ELSE 0
                        END DESC,
                        e.date_analyse DESC
                '''
                params.extend([search_full, prefix, like_full, like_full, like_full])
            else:
                query = inner_query + ' ORDER BY e.favori DESC, e.date_analyse DESC'

        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        if offset:
            query += ' OFFSET ?'
            params.append(offset)

        self.execute_sql(cursor, query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Importer la fonction de nettoyage depuis les utils
        from utils.helpers import clean_json_dict
        
        # Parser les tags et, optionnellement, charger les données OpenGraph pour chaque entreprise
        entreprises = []
        import logging
        logger = logging.getLogger(__name__)

        for row in rows:
            entreprise = self.clean_row_dict(dict(row))
            
            if entreprise.get('tags'):
                try:
                    entreprise['tags'] = json.loads(entreprise['tags']) if isinstance(entreprise['tags'], str) else entreprise['tags']
                except Exception:
                    entreprise['tags'] = []
            else:
                entreprise['tags'] = []
            
            if include_og:
                # Charger les données OpenGraph depuis les tables normalisées
                try:
                    entreprise['og_data'] = self.get_og_data(entreprise['id'])
                except Exception as og_error:
                    # Sur certains environnements anciens, les tables OG peuvent ne pas encore exister.
                    logger.warning(f"[Database] Erreur lors du chargement des données OG pour entreprise {entreprise.get('id')}: {og_error}")
                    entreprise['og_data'] = None
            
            entreprises.append(entreprise)
        
        # Nettoyer toutes les entreprises en une seule fois (double sécurité)
        entreprises = clean_json_dict(entreprises)
        
        return entreprises

    def count_entreprises(self, analyse_id=None, filters=None):
        """
        Compte le nombre total d'entreprises correspondant aux filtres.
        Utilise la même logique de filtres que get_entreprises, mais sans charger les données OG.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        has_security_filters = filters and (
            any(filters.get(k) is not None for k in ('security_min', 'security_max'))
            or EntrepriseManager._truthy_filter(filters, 'security_null')
        )
        has_pentest_filters = filters and (
            any(filters.get(k) is not None for k in ('pentest_min', 'pentest_max'))
            or EntrepriseManager._truthy_filter(filters, 'pentest_null')
        )
        has_seo_filters = filters and (
            any(filters.get(k) is not None for k in ('seo_min', 'seo_max'))
            or EntrepriseManager._truthy_filter(filters, 'seo_null')
        )
        wrap_subquery = has_security_filters or has_pentest_filters or has_seo_filters

        inner_query = '''
            SELECT e.*,
                   (SELECT risk_score
                    FROM analyses_pentest
                    WHERE entreprise_id = e.id
                    ORDER BY date_analyse DESC
                    LIMIT 1) as score_pentest,
                   (SELECT score
                    FROM analyses_seo
                    WHERE entreprise_id = e.id
                    ORDER BY date_analyse DESC
                    LIMIT 1) as score_seo
            FROM entreprises e
            WHERE 1=1
        '''
        params = []

        if analyse_id:
            inner_query += ' AND e.analyse_id = ?'
            params.append(analyse_id)

        if filters:
            if filters.get('secteur'):
                inner_query += ' AND e.secteur = ?'
                params.append(filters['secteur'])
            if filters.get('statut'):
                statut_val = filters['statut']
                if isinstance(statut_val, (list, tuple, set)):
                    statut_list = [s for s in statut_val if s is not None and str(s).strip() != '']
                    if statut_list:
                        placeholders = ','.join(['?' for _ in statut_list])
                        inner_query += f' AND e.statut IN ({placeholders})'
                        params.extend(statut_list)
                else:
                    inner_query += ' AND e.statut = ?'
                    params.append(statut_val)
            if filters.get('opportunite'):
                inner_query += ' AND e.opportunite = ?'
                params.append(filters['opportunite'])
            if filters.get('favori'):
                inner_query += ' AND e.favori = 1'
            # Filtrer par appartenance à un groupe spécifique
            if filters.get('groupe_id') is not None:
                inner_query += ' AND e.id IN (SELECT entreprise_id FROM entreprise_groupes WHERE groupe_id = ?)'
                params.append(filters['groupe_id'])
            # Filtrer les entreprises qui n'appartiennent à aucun groupe
            if str(filters.get('no_group', '')).lower() in ('1', 'true', 'yes'):
                inner_query += ' AND e.id NOT IN (SELECT entreprise_id FROM entreprise_groupes)'
            if str(filters.get('has_email', '')).lower() in ('1', 'true', 'yes'):
                # Même logique que dans get_entreprises:
                # email principal + scraping + personnes + OSINT.
                inner_query += """
                    AND (
                        (e.email_principal IS NOT NULL AND TRIM(e.email_principal) <> '')
                        OR EXISTS (
                            SELECT 1
                            FROM scraper_emails se
                            WHERE se.entreprise_id = e.id
                              AND se.email IS NOT NULL
                              AND TRIM(se.email) <> ''
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM personnes p
                            WHERE p.entreprise_id = e.id
                              AND p.email IS NOT NULL
                              AND TRIM(p.email) <> ''
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM scraper_people sp
                            WHERE sp.entreprise_id = e.id
                              AND sp.email IS NOT NULL
                              AND TRIM(sp.email) <> ''
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM analyses_osint ao
                            JOIN analysis_osint_emails aoe ON aoe.analysis_id = ao.id
                            WHERE ao.entreprise_id = e.id
                              AND aoe.email IS NOT NULL
                              AND TRIM(aoe.email) <> ''
                        )
                    )
                """
            # Nouveaux filtres de segmentation (même logique que get_entreprises)
            if filters.get('cms'):
                cms_val = filters['cms']
                if isinstance(cms_val, (list, tuple, set)):
                    placeholders = ','.join(['?' for _ in cms_val])
                    inner_query += f' AND e.cms IN ({placeholders})'
                    params.extend(list(cms_val))
                else:
                    inner_query += ' AND e.cms = ?'
                    params.append(cms_val)
            if filters.get('framework'):
                fw_val = filters['framework']
                if isinstance(fw_val, (list, tuple, set)):
                    placeholders = ','.join(['?' for _ in fw_val])
                    inner_query += f' AND e.framework IN ({placeholders})'
                    params.extend(list(fw_val))
                else:
                    inner_query += ' AND e.framework = ?'
                    params.append(fw_val)
            if str(filters.get('has_blog', '')).lower() in ('1', 'true', 'yes'):
                inner_query += ' AND e.has_blog = 1'
            if str(filters.get('has_form', '')).lower() in ('1', 'true', 'yes'):
                inner_query += ' AND e.has_contact_form = 1'
            if str(filters.get('has_tunnel', '')).lower() in ('1', 'true', 'yes'):
                inner_query += ' AND e.has_checkout = 1'
            if filters.get('performance_min') is not None:
                inner_query += ' AND e.performance_score IS NOT NULL AND e.performance_score >= ?'
                params.append(int(filters['performance_min']))
            if filters.get('performance_max') is not None:
                inner_query += ' AND e.performance_score IS NOT NULL AND e.performance_score <= ?'
                params.append(int(filters['performance_max']))
            if filters.get('search'):
                # Même logique de recherche que dans get_entreprises :
                # multi-mots, insensible à la casse, plusieurs champs.
                raw_search = str(filters['search']).strip()
                tokens = [t.lower() for t in re.split(r'\s+', raw_search) if t.strip()]
                for token in tokens:
                    like = f"%{token}%"
                    # Doit être strictement aligné sur get_entreprises (même champs, même ordre des ?)
                    inner_query += '''
                        AND (
                            LOWER(e.nom) LIKE ?
                            OR LOWER(e.secteur) LIKE ?
                            OR LOWER(COALESCE(e.email_principal, '')) LIKE ?
                            OR EXISTS (
                                SELECT 1
                                FROM scraper_emails se
                                WHERE se.entreprise_id = e.id
                                  AND se.email IS NOT NULL
                                  AND LOWER(se.email) LIKE ?
                            )
                            OR LOWER(COALESCE(e.responsable, '')) LIKE ?
                            OR LOWER(COALESCE(e.website, '')) LIKE ?
                            OR LOWER(COALESCE(e.address_1, '')) LIKE ?
                            OR LOWER(COALESCE(e.address_2, '')) LIKE ?
                            OR LOWER(COALESCE(e.tags, '')) LIKE ?
                        )
                    '''
                    params.extend([like] * 9)

            # Filtres sur les tags (même logique que get_entreprises)
            if filters.get('tags_contains'):
                inner_query += ' AND e.tags LIKE ?'
                params.append('%' + str(filters['tags_contains']) + '%')
            if filters.get('tags_any'):
                values = filters['tags_any']
                if isinstance(values, str):
                    values = [v.strip() for v in values.split(',') if v.strip()]
                conditions = []
                for v in values:
                    conditions.append('e.tags LIKE ?')
                    params.append('%' + str(v) + '%')
                if conditions:
                    inner_query += ' AND (' + ' OR '.join(conditions) + ')'
            if filters.get('tags_all'):
                values = filters['tags_all']
                if isinstance(values, str):
                    values = [v.strip() for v in values.split(',') if v.strip()]
                for v in values:
                    inner_query += ' AND e.tags LIKE ?'
                    params.append('%' + str(v) + '%')

        # Pour éviter toute divergence avec get_entreprises, on compte
        # toujours à partir de la même sous-requête (inner_query) qui
        # applique déjà TOUS les filtres, y compris la recherche multi-mots.
        query = 'SELECT COUNT(*) as count FROM (' + inner_query + ') sub WHERE 1=1'
        if has_security_filters:
            if EntrepriseManager._truthy_filter(filters, 'security_null'):
                query += ' AND sub.score_securite IS NULL'
            else:
                if filters.get('security_min') is not None:
                    query += ' AND (COALESCE(sub.score_securite, 0) >= ?)'
                    params.append(filters['security_min'])
                if filters.get('security_max') is not None:
                    query += ' AND (COALESCE(sub.score_securite, 0) <= ?)'
                    params.append(filters['security_max'])
        if has_pentest_filters:
            if EntrepriseManager._truthy_filter(filters, 'pentest_null'):
                query += ' AND sub.score_pentest IS NULL'
            else:
                if filters.get('pentest_min') is not None:
                    query += ' AND (COALESCE(sub.score_pentest, 0) >= ?)'
                    params.append(filters['pentest_min'])
                if filters.get('pentest_max') is not None:
                    query += ' AND (COALESCE(sub.score_pentest, 0) <= ?)'
                    params.append(filters['pentest_max'])
        if has_seo_filters:
            if EntrepriseManager._truthy_filter(filters, 'seo_null'):
                query += ' AND sub.score_seo IS NULL'
            else:
                if filters.get('seo_min') is not None:
                    query += ' AND (COALESCE(sub.score_seo, 0) >= ?)'
                    params.append(filters['seo_min'])
                if filters.get('seo_max') is not None:
                    query += ' AND (COALESCE(sub.score_seo, 0) <= ?)'
                    params.append(filters['seo_max'])

        self.execute_sql(cursor, query, params)
        row = cursor.fetchone()
        conn.close()
        return row['count'] if row else 0
    
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
                    LIMIT 1) as score_pentest,
                   (SELECT score
                    FROM analyses_seo
                    WHERE entreprise_id = e.id
                    ORDER BY date_analyse DESC
                    LIMIT 1) as score_seo
            FROM entreprises e
            WHERE e.id = ?
        ''', (entreprise_id,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        entreprise = self.clean_row_dict(dict(row))
        
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
        # Compteurs pour la modale (images = toutes sources, pages = nb d'OG)
        og_data = entreprise['og_data']
        entreprise['pages_count'] = len(og_data) if isinstance(og_data, list) else (1 if og_data else 0)
        try:
            images_list = self.get_images_by_entreprise(entreprise_id)
            entreprise['images_count'] = len(images_list) if images_list else 0
        except Exception:
            entreprise['images_count'] = 0
        
        # Nettoyer les valeurs NaN avant de retourner (double sécurité)
        from utils.helpers import clean_json_dict
        entreprise = clean_json_dict(entreprise)
        
        conn.close()
        return entreprise
    
    def update_opportunity_score(self, entreprise_id):
        """
        Met à jour le score d'opportunité d'une entreprise en utilisant toutes les analyses disponibles
        
        Args:
            entreprise_id: ID de l'entreprise
            
        Returns:
            dict: Résultat du calcul d'opportunité ou None si erreur
        """
        if not OpportunityCalculator:
            logger.warning('OpportunityCalculator non disponible, impossible de calculer l\'opportunité')
            return None
        
        try:
            # Récupérer les données de l'entreprise
            entreprise = self.get_entreprise(entreprise_id)
            if not entreprise:
                logger.warning(f'Entreprise {entreprise_id} introuvable')
                return None
            
            # Calculer le score d'opportunité
            # Passer self qui hérite de tous les managers nécessaires
            calculator = OpportunityCalculator(database=self)
            opportunity_result = calculator.calculate_opportunity_from_entreprise(entreprise)
            
            # Mettre à jour l'opportunité dans la base de données
            conn = self.get_connection()
            cursor = conn.cursor()
            
            self.execute_sql(cursor,
                'UPDATE entreprises SET opportunite = ? WHERE id = ?',
                (opportunity_result['opportunity'], entreprise_id)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f'Opportunité mise à jour pour entreprise {entreprise_id}: {opportunity_result["opportunity"]} (score: {opportunity_result["score"]})')
            
            # Mettre à jour des tags intelligents basés sur les analyses (SEO, Pentest, technique)
            try:
                self._update_intelligent_tags_from_analyses(entreprise_id, opportunity_result)
            except Exception as tag_err:
                logger.warning(f"Erreur lors de la mise à jour des tags intelligents pour entreprise {entreprise_id}: {tag_err}")
            
            return opportunity_result
        except Exception as e:
            logger.error(f'Erreur lors du calcul de l\'opportunité pour entreprise {entreprise_id}: {e}', exc_info=True)
            return None
    
    def _update_intelligent_tags_from_analyses(self, entreprise_id, opportunity_result=None):
        """
        Met à jour automatiquement certains tags d'entreprise à partir des dernières analyses.
        
        Tags gérés ici (ajout/suppression automatique) :
        - risque_cyber_eleve
        - seo_a_ameliorer
        - perf_lente
        - site_sans_https
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Charger les tags existants
        self.execute_sql(cursor, 'SELECT tags FROM entreprises WHERE id = ?', (entreprise_id,))
        row = cursor.fetchone()
        raw_tags = None
        if row:
            try:
                raw_tags = row['tags'] if isinstance(row, dict) else row[0]
            except Exception:
                raw_tags = None
        
        tags = []
        if raw_tags:
            try:
                tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
            except Exception:
                tags = []
        if not isinstance(tags, list):
            tags = []
        
        intelligent_tags = {
            'risque_cyber_eleve',
            'seo_a_ameliorer',
            'perf_lente',
            'site_sans_https',
            'lang_fr',
            'lang_en',
            'lang_de',
            'lang_es',
            'lang_it',
            'lang_nl',
            'lang_pt',
            'lang_autre',
        }
        
        # Retirer d'abord tous les anciens tags "intelligents" pour les recalculer proprement
        tags = [t for t in tags if t not in intelligent_tags]
        
        # 1) Pentest : risque_cyber_eleve
        try:
            pentest_risk_high = False
            if hasattr(self, 'get_pentest_analysis_by_entreprise'):
                pentest = self.get_pentest_analysis_by_entreprise(entreprise_id)
                if pentest:
                    rs = pentest.get('risk_score')
                    if isinstance(rs, (int, float)) and rs >= 70:
                        pentest_risk_high = True
            if pentest_risk_high:
                tags.append('risque_cyber_eleve')
        except Exception:
            pass
        
        # 2) SEO : seo_a_ameliorer
        try:
            seo_low = False
            if hasattr(self, 'get_seo_analyses_by_entreprise'):
                try:
                    seo_list = self.get_seo_analyses_by_entreprise(entreprise_id, limit=1)
                except TypeError:
                    seo_list = self.get_seo_analyses_by_entreprise(entreprise_id)
                if seo_list:
                    seo_score = seo_list[0].get('score')
                    if isinstance(seo_score, (int, float)) and seo_score < 50:
                        seo_low = True
            if seo_low:
                tags.append('seo_a_ameliorer')
        except Exception:
            pass
        
        # 3) Performance / HTTPS / langue principale
        try:
            perf_lente = False
            site_sans_https = False
            main_lang = None
            if hasattr(self, 'get_technical_analysis'):
                tech = self.get_technical_analysis(entreprise_id)
                if tech:
                    perf_score = tech.get('performance_score')
                    if isinstance(perf_score, (int, float)) and perf_score < 50:
                        perf_lente = True
                    ssl_valid = tech.get('ssl_valid')
                    tech_url = tech.get('url') or ''
                    if ssl_valid is False or (isinstance(tech_url, str) and tech_url.startswith('http://')):
                        site_sans_https = True
                    # Langue principale détectée (depuis technical_details.main_language)
                    details = tech.get('technical_details')
                    if isinstance(details, dict):
                        main_lang = details.get('main_language')
            if perf_lente:
                tags.append('perf_lente')
            if site_sans_https:
                tags.append('site_sans_https')
            if main_lang:
                code = str(main_lang).split('-', 1)[0].lower()
                lang_tag_map = {
                    'fr': 'lang_fr',
                    'en': 'lang_en',
                    'de': 'lang_de',
                    'es': 'lang_es',
                    'it': 'lang_it',
                    'nl': 'lang_nl',
                    'pt': 'lang_pt',
                }
                tags.append(lang_tag_map.get(code, 'lang_autre'))
        except Exception:
            pass
        
        # Nettoyer les doublons
        seen = set()
        deduped = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        tags = deduped
        
        # Sauvegarder les tags mis à jour
        self.execute_sql(
            cursor,
            'UPDATE entreprises SET tags = ? WHERE id = ?',
            (json.dumps(tags) if tags else None, entreprise_id)
        )
        conn.commit()
        conn.close()
    
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

    def add_entreprise_tag(self, entreprise_id: int, tag: str) -> bool:
        """
        Ajoute un tag (sans doublon) à une entreprise.

        Args:
            entreprise_id (int): ID de l'entreprise
            tag (str): Tag à ajouter

        Returns:
            bool: True si une mise à jour a été faite, False sinon
        """
        if not entreprise_id:
            return False
        t = (tag or '').strip()
        if not t:
            return False

        conn = self.get_connection()
        cursor = conn.cursor()

        self.execute_sql(cursor, 'SELECT tags FROM entreprises WHERE id = ?', (entreprise_id,))
        row = cursor.fetchone()
        raw_tags = None
        if row:
            try:
                raw_tags = row.get('tags') if isinstance(row, dict) else row[0]
            except Exception:
                raw_tags = None

        tags: list[str] = []
        if raw_tags:
            try:
                tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
            except Exception:
                tags = []
        if not isinstance(tags, list):
            tags = []

        before = set(str(x).strip() for x in tags if isinstance(x, str) and str(x).strip())
        if t in before:
            conn.close()
            return False

        tags.append(t)
        # dédoublonnage conservant l'ordre
        seen = set()
        deduped: list[str] = []
        for x in tags:
            xs = str(x).strip()
            if not xs or xs in seen:
                continue
            seen.add(xs)
            deduped.append(xs)

        self.execute_sql(
            cursor,
            'UPDATE entreprises SET tags = ? WHERE id = ?',
            (json.dumps(deduped) if deduped else None, entreprise_id),
        )
        conn.commit()
        updated = int(getattr(cursor, 'rowcount', 0) or 0) > 0
        conn.close()
        return updated
    
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
    
    def update_entreprise_statut(self, entreprise_id, statut):
        """
        Met à jour le statut d'une entreprise (pipeline commercial).

        Args:
            entreprise_id: ID de l'entreprise
            statut: Nouveau statut (voir ENTERPRISE_STATUSES)
        """
        if not statut or statut not in ENTERPRISE_STATUSES:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor, 'UPDATE entreprises SET statut = ? WHERE id = ?', (statut, entreprise_id))
        conn.commit()
        conn.close()
        return True

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

    def count_nearby_entreprises(self, latitude, longitude, radius_km=10, secteur=None):
        """Nombre d'entreprises avec coordonnées dans un rayon (Haversine), sans limite autre que le rayon."""
        conn = self.get_connection()
        cursor = conn.cursor()
        haversine_where = '''
            longitude IS NOT NULL
            AND latitude IS NOT NULL
            AND (
                6371 * acos(
                    cos(radians(?)) * cos(radians(latitude)) *
                    cos(radians(longitude) - radians(?)) +
                    sin(radians(?)) * sin(radians(latitude))
                )
            ) <= ?
        '''
        params: list = [latitude, longitude, latitude, radius_km]
        if secteur:
            q = f'SELECT COUNT(*) AS n FROM entreprises WHERE {haversine_where} AND secteur = ?'
            params.append(secteur)
        else:
            q = f'SELECT COUNT(*) AS n FROM entreprises WHERE {haversine_where}'
        self.execute_sql(cursor, q, tuple(params))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return 0
        try:
            return int(row['n'] if isinstance(row, dict) else row[0])
        except (TypeError, ValueError, KeyError, IndexError):
            return 0

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

    def get_statistics(self, days: int | None = None, offset_days: int = 0):
        """
        Récupère les statistiques globales de l'application.
        
        Returns:
            dict: Dictionnaire avec les statistiques
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()
        
        stats = {}

        # Calcul de la fenêtre temporelle pour les statistiques filtrables.
        # - days=None => pas de filtre temps
        # - days=30, offset_days=0 => [now-30, now]
        # - days=30, offset_days=30 => [now-60, now-30] (période précédente)
        since = None
        until = None
        if days and days > 0:
            try:
                from datetime import datetime, timedelta
                now_dt = datetime.utcnow()
                offset = max(0, int(offset_days or 0))
                until_dt = now_dt - timedelta(days=offset)
                since_dt = until_dt - timedelta(days=days)
                # Format ISO compatible avec SQLite et PostgreSQL
                since = since_dt.isoformat(sep=' ', timespec='seconds')
                until = until_dt.isoformat(sep=' ', timespec='seconds')
            except Exception:
                since = None
                until = None
        
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

        # Entreprises avec au moins un email (principal OU scraping)
        try:
            self.execute_sql(cursor, '''
                SELECT COUNT(DISTINCT e.id) as count
                FROM entreprises e
                WHERE
                    (e.email_principal IS NOT NULL AND TRIM(e.email_principal) != '')
                    OR EXISTS (
                        SELECT 1
                        FROM scraper_emails se
                        WHERE se.entreprise_id = e.id
                          AND se.email IS NOT NULL
                          AND TRIM(se.email) != ''
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM personnes p
                        WHERE p.entreprise_id = e.id
                          AND p.email IS NOT NULL
                          AND TRIM(p.email) != ''
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM scraper_people sp
                        WHERE sp.entreprise_id = e.id
                          AND sp.email IS NOT NULL
                          AND TRIM(sp.email) != ''
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM analyses_osint ao
                        JOIN analysis_osint_emails aoe ON aoe.analysis_id = ao.id
                        WHERE ao.entreprise_id = e.id
                          AND aoe.email IS NOT NULL
                          AND TRIM(aoe.email) != ''
                    )
            ''')
            stats['entreprises_avec_email'] = cursor.fetchone()['count']
        except Exception:
            stats['entreprises_avec_email'] = 0
        
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

        # Tags (champ JSON stocké en texte, agrégation côté Python pour compat SQLite/PostgreSQL)
        try:
            self.execute_sql(cursor, '''
                SELECT tags
                FROM entreprises
                WHERE tags IS NOT NULL AND tags != ''
            ''')
            tags_count: dict[str, int] = {}
            for row in cursor.fetchall() or []:
                raw = None
                try:
                    raw = row['tags'] if isinstance(row, dict) else (row[0] if row else None)
                except Exception:
                    raw = None

                if not raw:
                    continue

                tags_list = []
                try:
                    tags_list = json.loads(raw) if isinstance(raw, str) else (raw or [])
                except Exception:
                    tags_list = []

                if not isinstance(tags_list, list):
                    continue

                for t in tags_list:
                    tag = (str(t).strip() if t is not None else '')
                    if not tag:
                        continue
                    tags_count[tag] = tags_count.get(tag, 0) + 1

            stats['par_tags'] = dict(sorted(tags_count.items(), key=lambda kv: (-kv[1], kv[0].lower())))
            stats['top_tags'] = [{'tag': k, 'count': v} for k, v in list(stats['par_tags'].items())[:20]]
        except Exception:
            stats['par_tags'] = {}
            stats['top_tags'] = []

        # Secteurs les plus représentés parmi les prospects gagnés (optionnellement filtrés par période)
        try:
            base_sql = '''
                SELECT secteur, COUNT(*) as count
                FROM entreprises
                WHERE statut = 'Gagné'
                  AND secteur IS NOT NULL
                  AND secteur != ''
            '''
            params = []
            if since:
                base_sql += ' AND date_analyse >= ?'
                params.append(since)
                if until:
                    base_sql += ' AND date_analyse < ?'
                    params.append(until)
            base_sql += ' GROUP BY secteur ORDER BY count DESC LIMIT 5'

            self.execute_sql(cursor, base_sql, params)
            secteurs_gagnes = []
            for row in cursor.fetchall():
                d = dict(row)
                secteurs_gagnes.append({
                    'secteur': d.get('secteur'),
                    'count': d.get('count', 0),
                })
            stats['secteurs_gagnes'] = secteurs_gagnes
        except Exception:
            stats['secteurs_gagnes'] = []

        # Emails envoyés / ouverts / cliqués (toutes campagnes confondues, filtrables par période)
        try:
            sql = '''
                SELECT COUNT(*) as count
                FROM emails_envoyes
                WHERE statut = 'sent'
            '''
            params: list[object] = []
            if since:
                sql += ' AND date_envoi >= ?'
                params.append(since)
                if until:
                    sql += ' AND date_envoi < ?'
                    params.append(until)

            self.execute_sql(cursor, sql, params)
            total_emails_sent = cursor.fetchone()['count']
        except Exception:
            total_emails_sent = 0

        stats['emails_envoyes'] = total_emails_sent

        total_emails_opened = 0
        total_emails_clicked = 0
        try:
            # Emails qui ont au moins un open
            sql_open = '''
                SELECT COUNT(DISTINCT email_id) as count
                FROM email_tracking_events
                WHERE event_type = 'open'
            '''
            params_open: list[object] = []
            if since:
                sql_open += ' AND date_event >= ?'
                params_open.append(since)
                if until:
                    sql_open += ' AND date_event < ?'
                    params_open.append(until)

            self.execute_sql(cursor, sql_open, params_open)
            row = cursor.fetchone()
            total_emails_opened = row['count'] if row and 'count' in row.keys() else 0
        except Exception:
            total_emails_opened = 0

        try:
            # Emails qui ont au moins un clic
            sql_click = '''
                SELECT COUNT(DISTINCT email_id) as count
                FROM email_tracking_events
                WHERE event_type = 'click'
            '''
            params_click: list[object] = []
            if since:
                sql_click += ' AND date_event >= ?'
                params_click.append(since)
                if until:
                    sql_click += ' AND date_event < ?'
                    params_click.append(until)

            self.execute_sql(cursor, sql_click, params_click)
            row = cursor.fetchone()
            total_emails_clicked = row['count'] if row and 'count' in row.keys() else 0
        except Exception:
            total_emails_clicked = 0

        stats['emails_ouverts'] = total_emails_opened
        stats['emails_cliqués'] = total_emails_clicked

        if total_emails_sent > 0:
            stats['open_rate'] = round((total_emails_opened / total_emails_sent) * 100, 1)
            stats['click_rate'] = round((total_emails_clicked / total_emails_sent) * 100, 1)
        else:
            stats['open_rate'] = 0.0
            stats['click_rate'] = 0.0

        # Campagnes email (optionnellement filtrées par période)
        try:
            sql_campagnes = 'SELECT COUNT(*) as count FROM campagnes_email'
            params_campagnes: list[object] = []
            if since:
                sql_campagnes += ' WHERE date_creation >= ?'
                params_campagnes.append(since)
                if until:
                    sql_campagnes += ' AND date_creation < ?'
                    params_campagnes.append(until)

            self.execute_sql(cursor, sql_campagnes, params_campagnes)
            stats['total_campagnes'] = cursor.fetchone()['count']
        except Exception:
            stats['total_campagnes'] = 0

        # Dernières campagnes (vue synthétique)
        try:
            sql_recent_camp = '''
                SELECT id, nom, statut, total_destinataires, total_envoyes, total_reussis, date_creation
                FROM campagnes_email
            '''
            params_recent_camp: list[object] = []
            if since:
                sql_recent_camp += ' WHERE date_creation >= ?'
                params_recent_camp.append(since)
                if until:
                    sql_recent_camp += ' AND date_creation < ?'
                    params_recent_camp.append(until)
            sql_recent_camp += ' ORDER BY date_creation DESC LIMIT 5'

            self.execute_sql(cursor, sql_recent_camp, params_recent_camp)
            recent_campagnes = []
            for row in cursor.fetchall():
                d = dict(row)
                recent_campagnes.append({
                    'id': d.get('id'),
                    'nom': d.get('nom'),
                    'statut': d.get('statut'),
                    'total_destinataires': d.get('total_destinataires'),
                    'total_envoyes': d.get('total_envoyes'),
                    'total_reussis': d.get('total_reussis'),
                    'date_creation': d.get('date_creation'),
                })
            stats['recent_campagnes'] = recent_campagnes
        except Exception:
            stats['recent_campagnes'] = []

        # Dernières entreprises gagnées (optionnellement filtrées par période)
        try:
            sql_recent_gagnes = '''
                SELECT id, nom, secteur, website, statut, date_analyse
                FROM entreprises
                WHERE statut = 'Gagné'
            '''
            params_recent_gagnes: list[object] = []
            if since:
                sql_recent_gagnes += ' AND date_analyse >= ?'
                params_recent_gagnes.append(since)
                if until:
                    sql_recent_gagnes += ' AND date_analyse < ?'
                    params_recent_gagnes.append(until)
            sql_recent_gagnes += ' ORDER BY date_analyse DESC LIMIT 5'

            self.execute_sql(cursor, sql_recent_gagnes, params_recent_gagnes)
            recent_gagnes = []
            for row in cursor.fetchall():
                d = dict(row)
                recent_gagnes.append({
                    'id': d.get('id'),
                    'nom': d.get('nom'),
                    'secteur': d.get('secteur'),
                    'website': d.get('website'),
                    'statut': d.get('statut'),
                    'date_analyse': d.get('date_analyse'),
                })
            stats['recent_gagnes'] = recent_gagnes
        except Exception:
            stats['recent_gagnes'] = []
        
        conn.close()
        return stats

    def get_mobile_dashboard_overview(self, trend_days: int = 7) -> dict:
        """
        Statistiques compactes pour clients mobiles (KPI + série journalière).

        Args:
            trend_days: nombre de jours (inclus) pour la série \"nouvelles entreprises\" par jour.

        Returns:
            dict avec totaux, emails envoyés, tendance journalière.
        """
        from datetime import datetime, timedelta

        conn = self.get_connection()
        cursor = conn.cursor()
        n = max(1, min(int(trend_days or 7), 90))
        out: dict = {
            'total_entreprises': 0,
            'total_analyses': 0,
            'total_campagnes': 0,
            'total_emails': 0,
            'emails_envoyes': 0,
            'trend_entreprises': [],
        }
        def _count_c(row) -> int:
            if not row:
                return 0
            try:
                d = dict(row)
                return int(d.get('c') or 0)
            except Exception:
                try:
                    return int(row['c'])
                except Exception:
                    return 0

        try:
            self.execute_sql(cursor, 'SELECT COUNT(*) as c FROM entreprises')
            out['total_entreprises'] = _count_c(cursor.fetchone())
        except Exception:
            pass
        try:
            self.execute_sql(cursor, 'SELECT COUNT(*) as c FROM analyses')
            out['total_analyses'] = _count_c(cursor.fetchone())
        except Exception:
            pass
        try:
            self.execute_sql(cursor, 'SELECT COUNT(*) as c FROM campagnes_email')
            out['total_campagnes'] = _count_c(cursor.fetchone())
        except Exception:
            pass
        try:
            self.execute_sql(cursor, '''
                SELECT COUNT(*) as c FROM scraper_emails
                WHERE email IS NOT NULL AND TRIM(email) != ''
            ''')
            out['total_emails'] = _count_c(cursor.fetchone())
        except Exception:
            pass
        try:
            self.execute_sql(cursor, '''
                SELECT COUNT(*) as c FROM emails_envoyes WHERE statut = 'sent'
            ''')
            out['emails_envoyes'] = _count_c(cursor.fetchone())
        except Exception:
            pass

        start = datetime.utcnow().date() - timedelta(days=n - 1)
        start_str = start.isoformat()
        rows_map: dict[str, int] = {}
        try:
            if self.is_postgresql():
                self.execute_sql(cursor, '''
                    SELECT CAST(date_analyse AS DATE) AS d, COUNT(*)::bigint AS c
                    FROM entreprises
                    WHERE date_analyse IS NOT NULL
                      AND CAST(date_analyse AS DATE) >= CAST(? AS DATE)
                    GROUP BY CAST(date_analyse AS DATE)
                    ORDER BY 1
                ''', (start_str,))
            else:
                self.execute_sql(cursor, '''
                    SELECT date(date_analyse) AS d, COUNT(*) AS c
                    FROM entreprises
                    WHERE date_analyse IS NOT NULL
                      AND date(date_analyse) >= date(?)
                    GROUP BY date(date_analyse)
                    ORDER BY 1
                ''', (start_str,))
            for row in cursor.fetchall() or []:
                d = dict(row) if not isinstance(row, dict) else row
                dk = d.get('d')
                if hasattr(dk, 'isoformat'):
                    key = dk.isoformat()
                else:
                    key = str(dk)[:10]
                rows_map[key] = int(d.get('c') or 0)
        except Exception:
            pass

        trend: list[dict] = []
        for i in range(n):
            dday = start + timedelta(days=i)
            key = dday.isoformat()
            trend.append({'date': key, 'count': int(rows_map.get(key, 0))})
        out['trend_entreprises'] = trend

        conn.close()
        return out
    
    def get_ciblage_suggestions(self):
        """
        Retourne les valeurs distinctes pour l'autocomplétion des critères de ciblage
        (secteur, opportunité, statut, tags).

        Returns:
            dict: {"secteurs": [...], "opportunites": [...], "statuts": [...], "tags": [...]}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        result = {"secteurs": [], "opportunites": [], "statuts": [], "tags": []}
        try:
            self.execute_sql(cursor, '''
                SELECT secteur FROM entreprises
                WHERE secteur IS NOT NULL AND secteur != ''
                GROUP BY secteur ORDER BY secteur
            ''')
            result["secteurs"] = [row["secteur"] for row in cursor.fetchall()]
        except Exception:
            pass
        try:
            self.execute_sql(cursor, '''
                SELECT opportunite FROM entreprises
                WHERE opportunite IS NOT NULL AND opportunite != ''
                GROUP BY opportunite ORDER BY opportunite
            ''')
            result["opportunites"] = [row["opportunite"] for row in cursor.fetchall()]
        except Exception:
            pass
        try:
            self.execute_sql(cursor, '''
                SELECT statut FROM entreprises
                WHERE statut IS NOT NULL AND statut != ''
                GROUP BY statut ORDER BY statut
            ''')
            result["statuts"] = [row["statut"] for row in cursor.fetchall()]
        except Exception:
            pass
        try:
            self.execute_sql(cursor, 'SELECT tags FROM entreprises WHERE tags IS NOT NULL AND tags != ""')
            tags_set = set()
            for row in cursor.fetchall():
                raw = row.get("tags")
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(parsed, list):
                        for t in parsed:
                            if isinstance(t, str) and t.strip():
                                tags_set.add(t.strip())
                except Exception:
                    pass
            result["tags"] = sorted(tags_set)
        except Exception:
            pass
        conn.close()
        return result

    def get_ciblage_suggestions_with_counts(self):
        """
        Retourne les valeurs distinctes avec effectifs pour l'autocomplétion (secteur, opportunité, statut, tags).

        Returns:
            dict: {"secteurs": [{"value": str, "count": int}], ...}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        result = {"secteurs": [], "opportunites": [], "statuts": [], "tags": []}

        def row_get(row, key, default=None):
            """
            Extrait une valeur de ligne SQL (sqlite3.Row / RealDictCursor).
            """
            try:
                return row[key]
            except Exception:
                try:
                    if hasattr(row, 'get'):
                        return row.get(key, default)
                except Exception:
                    pass
                return default
        try:
            self.execute_sql(cursor, '''
                SELECT secteur as value, COUNT(*) as count FROM entreprises
                WHERE secteur IS NOT NULL AND secteur != ''
                GROUP BY secteur ORDER BY count DESC, secteur
            ''')
            result["secteurs"] = [{"value": row["value"], "count": row["count"]} for row in cursor.fetchall()]
        except Exception:
            pass
        try:
            self.execute_sql(cursor, '''
                SELECT opportunite as value, COUNT(*) as count FROM entreprises
                WHERE opportunite IS NOT NULL AND opportunite != ''
                GROUP BY opportunite ORDER BY count DESC, opportunite
            ''')
            result["opportunites"] = [{"value": row["value"], "count": row["count"]} for row in cursor.fetchall()]
        except Exception:
            pass
        try:
            self.execute_sql(cursor, '''
                SELECT statut as value, COUNT(*) as count FROM entreprises
                WHERE statut IS NOT NULL AND statut != ''
                GROUP BY statut ORDER BY count DESC, statut
            ''')
            result["statuts"] = [{"value": row["value"], "count": row["count"]} for row in cursor.fetchall()]
        except Exception:
            pass
        try:
            # 1) Tags "manuels" déjà stockés dans la colonne tags
            self.execute_sql(cursor, 'SELECT tags FROM entreprises WHERE tags IS NOT NULL AND tags != ""')
            tags_count = {}
            for row in cursor.fetchall():
                raw = row_get(row, "tags")
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(parsed, list):
                        for t in parsed:
                            if isinstance(t, str) and t.strip():
                                key = t.strip()
                                tags_count[key] = tags_count.get(key, 0) + 1
                except Exception:
                    # On ignore les lignes mal formées
                    pass

            # 2) Tags dérivés des champs de résumé technique
            # Ces champs sont censés exister même si la colonne tags n'a pas été mise à jour partout.
            def norm_lower(val):
                return str(val).strip().lower()

            # CMS distincts
            try:
                self.execute_sql(cursor, '''
                    SELECT cms as value, COUNT(*) as count
                    FROM entreprises
                    WHERE cms IS NOT NULL AND cms != ''
                    GROUP BY cms
                ''')
                for row in cursor.fetchall():
                    if not row_get(row, 'value'):
                        continue
                    tags_count[f"cms:{norm_lower(row_get(row, 'value'))}"] = row_get(row, 'count', 0)
            except Exception:
                pass

            # Framework distincts
            try:
                self.execute_sql(cursor, '''
                    SELECT framework as value, COUNT(*) as count
                    FROM entreprises
                    WHERE framework IS NOT NULL AND framework != ''
                    GROUP BY framework
                ''')
                for row in cursor.fetchall():
                    if not row_get(row, 'value'):
                        continue
                    tags_count[f"framework:{norm_lower(row_get(row, 'value'))}"] = row_get(row, 'count', 0)
            except Exception:
                pass

            # Performance dérivée
            try:
                self.execute_sql(cursor, '''
                    SELECT
                        SUM(CASE WHEN performance_score IS NOT NULL AND performance_score < 40 THEN 1 ELSE 0 END) as low_count,
                        SUM(CASE WHEN performance_score IS NOT NULL AND performance_score >= 70 THEN 1 ELSE 0 END) as good_count
                    FROM entreprises
                ''')
                perf_row = cursor.fetchone()
                if perf_row:
                    low_count = row_get(perf_row, 'low_count') or 0
                    good_count = row_get(perf_row, 'good_count') or 0
                    # match avec technical.py: perf:low / perf:good
                    tags_count['perf:low'] = int(low_count)
                    tags_count['perf:good'] = int(good_count)
            except Exception:
                pass

            # Blog / contact_form / ecommerce
            try:
                self.execute_sql(cursor, '''
                    SELECT
                        SUM(CASE WHEN has_blog = 1 THEN 1 ELSE 0 END) as blog_count,
                        SUM(CASE WHEN has_contact_form = 1 THEN 1 ELSE 0 END) as form_count,
                        SUM(CASE WHEN has_checkout = 1 THEN 1 ELSE 0 END) as checkout_count
                    FROM entreprises
                ''')
                row = cursor.fetchone()
                if row:
                    tags_count['blog'] = int(row_get(row, 'blog_count') or 0)
                    tags_count['contact_form'] = int(row_get(row, 'form_count') or 0)
                    tags_count['ecommerce'] = int(row_get(row, 'checkout_count') or 0)
            except Exception:
                pass

            # 3) Tags "connus" (pour lesquels on veut aussi proposer une suggestion à 0)
            # On évite d'y remettre cms:* / framework:* / perf:* car on les dérive déjà du résumé technique ci-dessus.
            important_tags = [
                "refonte",
                "fort_potentiel_refonte",
                "https",
                "site_sans_https",
                "risque",
                "risque_cyber_eleve",
                "seo",
                "seo_a_ameliorer",
                "perf_lente",
                "lang_fr",
                "lang_en",
            ]
            for tag in important_tags:
                tags_count.setdefault(tag, 0)

            result["tags"] = [
                {"value": v, "count": c}
                for v, c in sorted(tags_count.items(), key=lambda x: (-x[1], x[0]))
            ]
        except Exception:
            pass
        conn.close()
        return result

    def get_entreprises_with_emails(self):
        """
        Récupère toutes les entreprises avec leurs emails disponibles pour les campagnes.

        Returns:
            list[dict]: Liste des entreprises avec leurs emails (depuis scraper_emails)
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()

        # Récupérer les entreprises avec leurs emails (tri: personne en priorité, puis date)
        self.execute_sql(cursor,'''
            SELECT
                e.id,
                e.nom,
                e.secteur,
                e.responsable,
                se.email,
                se.name_info as email_nom,
                se.page_url as source,
                se.entreprise_id,
                COALESCE(se.is_person, 0) as is_person,
                se.domain,
                se.date_found
            FROM entreprises e
            INNER JOIN scraper_emails se ON e.id = se.entreprise_id
            WHERE se.email IS NOT NULL AND se.email != ''
            ORDER BY e.nom, COALESCE(se.is_person, 0) DESC, se.date_found DESC, se.id
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
                    'responsable': row['responsable'] or None,
                    'emails': []
                }

            # Utiliser page_url comme source si disponible, sinon 'scraper'
            source = row['source'] if row['source'] else 'scraper'
            if source == 'scraper' and row['source']:
                source = row['source']
            
            # Formater le nom depuis name_info (JSON)
            from utils.name_formatter import format_name
            email_nom = format_name(row['email_nom'])

            # Éviter les doublons (même email pour une entreprise) en gardant le premier (prioritaire)
            emails_list = entreprises_dict[entreprise_id]['emails']
            if not any(em['email'] == row['email'] for em in emails_list):
                is_person = bool(row['is_person']) if 'is_person' in row.keys() else False
                domain = row['domain'] if 'domain' in row.keys() and row['domain'] else None
                if not domain and row['email']:
                    domain = row['email'].split('@')[-1] if '@' in row['email'] else None
                emails_list.append({
                    'email': row['email'],
                    'nom': email_nom,
                    'source': source,
                    'entreprise_id': row['entreprise_id'],
                    'is_person': is_person,
                    'domain': domain
                })

        result = list(entreprises_dict.values())
        
        # Nettoyer les valeurs NaN pour la sérialisation JSON
        from utils.helpers import clean_json_dict
        result = clean_json_dict(result)
        
        return result
    
    def get_entreprises_for_campagne(self, filters=None):
        """
        Récupère les entreprises avec emails pour une campagne, avec filtres de ciblage.
        
        Args:
            filters: Dictionnaire optionnel de filtres :
                - secteur: valeur exacte
                - secteur_contains: sous-chaîne (LIKE)
                - opportunite: liste de valeurs (ex. ["Très élevée", "Élevée"])
                - statut: valeur exacte
                - tags_contains: sous-chaîne dans les tags (JSON)
                - favori: True pour favoris uniquement
                - search: recherche dans nom, secteur, email_principal, responsable
                - score_securite_max: score sécurité <= cette valeur
                - exclude_already_contacted: True pour exclure les entreprises déjà contactées
                - groupe_ids: liste d'IDs de groupes d'entreprises (filtre par appartenance à au moins un groupe)
        
        Returns:
            list[dict]: Même format que get_entreprises_with_emails (id, nom, secteur, emails)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        base_sql = '''
            SELECT
                e.id,
                e.nom,
                e.secteur,
                e.responsable,
                se.email,
                se.name_info as email_nom,
                se.page_url as source,
                se.entreprise_id,
                COALESCE(se.is_person, 0) as is_person,
                se.domain,
                se.date_found
            FROM entreprises e
            INNER JOIN scraper_emails se ON e.id = se.entreprise_id
            WHERE se.email IS NOT NULL AND se.email != ''
        '''
        params = []
        
        if filters:
            # Filtre par groupes d'entreprises (si groupe_ids fourni)
            if filters.get('groupe_ids') and isinstance(filters['groupe_ids'], list) and len(filters['groupe_ids']) > 0:
                placeholders = ','.join(['?' for _ in filters['groupe_ids']])
                base_sql += f' AND e.id IN (SELECT entreprise_id FROM entreprise_groupes WHERE groupe_id IN ({placeholders}))'
                params.extend(filters['groupe_ids'])
            if filters.get('secteur'):
                base_sql += ' AND e.secteur = ?'
                params.append(filters['secteur'])
            if filters.get('secteur_contains'):
                base_sql += ' AND e.secteur LIKE ?'
                params.append('%' + str(filters['secteur_contains']) + '%')
            if filters.get('opportunite') and isinstance(filters['opportunite'], list):
                placeholders = ','.join(['?' for _ in filters['opportunite']])
                base_sql += f' AND e.opportunite IN ({placeholders})'
                params.extend(filters['opportunite'])
            elif filters.get('opportunite') and isinstance(filters['opportunite'], str):
                base_sql += ' AND e.opportunite = ?'
                params.append(filters['opportunite'])
            if filters.get('statut'):
                statut_val = filters['statut']
                if isinstance(statut_val, (list, tuple, set)):
                    statut_list = [s for s in statut_val if s is not None and str(s).strip() != '']
                    if statut_list:
                        placeholders = ','.join(['?' for _ in statut_list])
                        base_sql += f' AND e.statut IN ({placeholders})'
                        params.extend(statut_list)
                else:
                    base_sql += ' AND e.statut = ?'
                    params.append(statut_val)
            if filters.get('tags_contains'):
                base_sql += ' AND e.tags LIKE ?'
                params.append('%' + str(filters['tags_contains']) + '%')
            if filters.get('tags_any'):
                values = filters['tags_any']
                if isinstance(values, str):
                    values = [v.strip() for v in values.split(',') if v.strip()]
                conditions = []
                for v in values:
                    conditions.append('e.tags LIKE ?')
                    params.append('%' + str(v) + '%')
                if conditions:
                    base_sql += ' AND (' + ' OR '.join(conditions) + ')'
            if filters.get('favori'):
                base_sql += ' AND e.favori = 1'
            # Nouveaux filtres de segmentation réutilisés pour les campagnes
            if filters.get('cms'):
                cms_val = filters['cms']
                if isinstance(cms_val, (list, tuple, set)):
                    placeholders = ','.join(['?' for _ in cms_val])
                    base_sql += f' AND e.cms IN ({placeholders})'
                    params.extend(list(cms_val))
                else:
                    base_sql += ' AND e.cms = ?'
                    params.append(cms_val)
            if filters.get('framework'):
                fw_val = filters['framework']
                if isinstance(fw_val, (list, tuple, set)):
                    placeholders = ','.join(['?' for _ in fw_val])
                    base_sql += f' AND e.framework IN ({placeholders})'
                    params.extend(list(fw_val))
                else:
                    base_sql += ' AND e.framework = ?'
                    params.append(fw_val)
            if str(filters.get('has_blog', '')).lower() in ('1', 'true', 'yes'):
                base_sql += ' AND e.has_blog = 1'
            if str(filters.get('has_form', '')).lower() in ('1', 'true', 'yes'):
                base_sql += ' AND e.has_contact_form = 1'
            if str(filters.get('has_tunnel', '')).lower() in ('1', 'true', 'yes'):
                base_sql += ' AND e.has_checkout = 1'
            if filters.get('performance_max') is not None:
                base_sql += ' AND e.performance_score IS NOT NULL AND e.performance_score <= ?'
                params.append(int(filters['performance_max']))
            if filters.get('search'):
                # Même logique de recherche que sur la liste d'entreprises :
                # insensible à la casse, multi-mots, plusieurs colonnes.
                raw_search = str(filters['search']).strip()
                tokens = [t.lower() for t in re.split(r'\s+', raw_search) if t.strip()]
                for token in tokens:
                    like = f"%{token}%"
                    base_sql += '''
                        AND (
                            LOWER(e.nom) LIKE ?
                            OR LOWER(e.secteur) LIKE ?
                            OR LOWER(COALESCE(e.email_principal, '')) LIKE ?
                            OR LOWER(COALESCE(e.responsable, '')) LIKE ?
                            OR LOWER(COALESCE(e.website, '')) LIKE ?
                            OR LOWER(COALESCE(e.address_1, '')) LIKE ?
                            OR LOWER(COALESCE(e.address_2, '')) LIKE ?
                        )
                    '''
                    params.extend([like] * 7)
            if filters.get('score_securite_max') is not None:
                base_sql += ' AND e.score_securite IS NOT NULL AND e.score_securite <= ?'
                params.append(int(filters['score_securite_max']))
            if filters.get('exclude_already_contacted'):
                base_sql += ' AND e.id NOT IN (SELECT entreprise_id FROM emails_envoyes WHERE entreprise_id IS NOT NULL)'
        
        base_sql += ' ORDER BY e.nom, COALESCE(se.is_person, 0) DESC, se.date_found DESC, se.id'
        
        self.execute_sql(cursor, base_sql, tuple(params) if params else None)
        rows = cursor.fetchall()
        conn.close()
        
        entreprises_dict = {}
        for row in rows:
            r = dict(row)
            entreprise_id = r['id']
            if entreprise_id not in entreprises_dict:
                entreprises_dict[entreprise_id] = {
                    'id': entreprise_id,
                    'nom': r['nom'],
                    'secteur': r['secteur'],
                    'responsable': r.get('responsable') or None,
                    'emails': []
                }
            source = r['source'] if r['source'] else 'scraper'
            from utils.name_formatter import format_name
            email_nom = format_name(r['email_nom'])
            emails_list = entreprises_dict[entreprise_id]['emails']
            if not any(em['email'] == r['email'] for em in emails_list):
                domain = r.get('domain') or (r['email'].split('@')[-1] if r.get('email') else None)
                emails_list.append({
                    'email': r['email'],
                    'nom': email_nom,
                    'source': source,
                    'entreprise_id': r['entreprise_id'],
                    'is_person': bool(r.get('is_person')),
                    'domain': domain
                })
        
        result = list(entreprises_dict.values())
        from utils.helpers import clean_json_dict
        result = clean_json_dict(result)
        return result
