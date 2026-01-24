"""
Module de gestion des personnes
Contient toutes les méthodes liées aux personnes et leurs données OSINT enrichies
"""

import json
import logging
from typing import Dict, List
from .base import DatabaseBase

logger = logging.getLogger(__name__)


class PersonneManager(DatabaseBase):
    """
    Gère toutes les opérations sur les personnes
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module personnes"""
        super().__init__(*args, **kwargs)
    
    def save_personne(self, entreprise_id: int, nom: str = None, prenom: str = None, 
                     titre: str = None, role: str = None, email: str = None, 
                     telephone: str = None, linkedin_url: str = None, 
                     linkedin_profile_data: Dict = None, social_profiles: Dict = None,
                     osint_data: Dict = None, niveau_hierarchique: int = None,
                     manager_id: int = None, source: str = None) -> int:
        """
        Sauvegarde une personne dans la base de données
        
        Args:
            entreprise_id: ID de l'entreprise
            nom: Nom de famille
            prenom: Prénom
            titre: Titre du poste
            role: Rôle
            email: Email
            telephone: Téléphone
            linkedin_url: URL LinkedIn
            linkedin_profile_data: Données du profil LinkedIn
            social_profiles: Profils sociaux
            osint_data: Données OSINT brutes
            niveau_hierarchique: Niveau hiérarchique (1-5)
            manager_id: ID du manager
            source: Source des données
            
        Returns:
            int: ID de la personne créée ou existante
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Chercher si la personne existe déjà (par email ou nom+prenom)
            personne_id = None
            if email:
                self.execute_sql(cursor,'SELECT id FROM personnes WHERE entreprise_id = ? AND email = ?', 
                             (entreprise_id, email))
                row = cursor.fetchone()
                if row:
                    personne_id = row['id']
            
            if not personne_id and nom and prenom:
                self.execute_sql(cursor,'SELECT id FROM personnes WHERE entreprise_id = ? AND nom = ? AND prenom = ?',
                             (entreprise_id, nom, prenom))
                row = cursor.fetchone()
                if row:
                    personne_id = row['id']
            
            # Préparer les données
            linkedin_data_json = json.dumps(linkedin_profile_data) if linkedin_profile_data else None
            social_profiles_json = json.dumps(social_profiles) if social_profiles else None
            osint_data_json = json.dumps(osint_data) if osint_data else None
            
            if personne_id:
                # Mettre à jour
                self.execute_sql(cursor,'''
                    UPDATE personnes SET
                        titre = COALESCE(?, titre),
                        role = COALESCE(?, role),
                        email = COALESCE(?, email),
                        telephone = COALESCE(?, telephone),
                        linkedin_url = COALESCE(?, linkedin_url),
                        linkedin_profile_data = COALESCE(?, linkedin_profile_data),
                        social_profiles = COALESCE(?, social_profiles),
                        osint_data = COALESCE(?, osint_data),
                        niveau_hierarchique = COALESCE(?, niveau_hierarchique),
                        manager_id = COALESCE(?, manager_id),
                        source = COALESCE(?, source)
                    WHERE id = ?
                ''', (titre, role, email, telephone, linkedin_url, linkedin_data_json,
                      social_profiles_json, osint_data_json, niveau_hierarchique, manager_id, source, personne_id))
            else:
                # Créer
                self.execute_sql(cursor,'''
                    INSERT INTO personnes (
                        entreprise_id, nom, prenom, titre, role, email, telephone,
                        linkedin_url, linkedin_profile_data, social_profiles, osint_data,
                        niveau_hierarchique, manager_id, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (entreprise_id, nom, prenom, titre, role, email, telephone,
                      linkedin_url, linkedin_data_json, social_profiles_json, osint_data_json,
                      niveau_hierarchique, manager_id, source))
                personne_id = cursor.lastrowid
            
            conn.commit()
            return personne_id
        except Exception as e:
            logger.error(f'Erreur lors de la sauvegarde de la personne: {e}')
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_personnes_by_entreprise(self, entreprise_id: int) -> List[Dict]:
        """
        Récupère toutes les personnes d'une entreprise
        
        Args:
            entreprise_id: ID de l'entreprise
            
        Returns:
            Liste de dictionnaires avec les informations des personnes
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        
        try:
            self.execute_sql(cursor,'''
                SELECT id, entreprise_id, nom, prenom, titre, role, email, telephone,
                       linkedin_url, linkedin_profile_data, social_profiles, osint_data,
                       niveau_hierarchique, manager_id, source, date_created, date_updated
                FROM personnes
                WHERE entreprise_id = ?
                ORDER BY nom, prenom
            ''', (entreprise_id,))
            
            personnes = cursor.fetchall()
            
            # Parser les champs JSON
            for personne in personnes:
                if personne.get('linkedin_profile_data'):
                    try:
                        personne['linkedin_profile_data'] = json.loads(personne['linkedin_profile_data'])
                    except:
                        pass
                if personne.get('social_profiles'):
                    try:
                        personne['social_profiles'] = json.loads(personne['social_profiles'])
                    except:
                        pass
                if personne.get('osint_data'):
                    try:
                        personne['osint_data'] = json.loads(personne['osint_data'])
                    except:
                        pass
            
            return personnes
        except Exception as e:
            logger.error(f'Erreur lors de la récupération des personnes: {e}')
            return []
        finally:
            conn.close()
    
    def save_person_osint_details(self, personne_id: int, enriched_data: Dict):
        """
        Sauvegarde les données OSINT enrichies d'une personne dans les tables normalisées
        
        Args:
            personne_id: ID de la personne
            enriched_data: Dictionnaire avec les données enrichies (photos, location, hobbies, etc.)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Sauvegarder les détails OSINT principaux
            if self.is_postgresql():
                self.execute_sql(cursor,'''
                    INSERT INTO personnes_osint_details (
                        personne_id, location, location_city, location_country, location_address,
                        location_latitude, location_longitude, age_range, birth_date,
                        hobbies, interests, education, professional_history, family_members,
                        data_breaches, photos_urls, bio, languages, skills, certifications
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (personne_id) DO UPDATE SET
                        location = EXCLUDED.location,
                        location_city = EXCLUDED.location_city,
                        location_country = EXCLUDED.location_country,
                        location_address = EXCLUDED.location_address,
                        location_latitude = EXCLUDED.location_latitude,
                        location_longitude = EXCLUDED.location_longitude,
                        age_range = EXCLUDED.age_range,
                        birth_date = EXCLUDED.birth_date,
                        hobbies = EXCLUDED.hobbies,
                        interests = EXCLUDED.interests,
                        education = EXCLUDED.education,
                        professional_history = EXCLUDED.professional_history,
                        family_members = EXCLUDED.family_members,
                        data_breaches = EXCLUDED.data_breaches,
                        photos_urls = EXCLUDED.photos_urls,
                        bio = EXCLUDED.bio,
                        languages = EXCLUDED.languages,
                        skills = EXCLUDED.skills,
                        certifications = EXCLUDED.certifications
                ''', (
                    personne_id,
                    enriched_data.get('location'),
                    enriched_data.get('location_city'),
                    enriched_data.get('location_country'),
                    enriched_data.get('location_address'),
                    enriched_data.get('location_latitude'),
                    enriched_data.get('location_longitude'),
                    enriched_data.get('age_range'),
                    enriched_data.get('birth_date'),
                    json.dumps(enriched_data.get('hobbies', [])) if enriched_data.get('hobbies') else None,
                    json.dumps(enriched_data.get('interests', [])) if enriched_data.get('interests') else None,
                    enriched_data.get('education'),
                    json.dumps(enriched_data.get('professional_history', [])) if enriched_data.get('professional_history') else None,
                    json.dumps(enriched_data.get('family_members', [])) if enriched_data.get('family_members') else None,
                    json.dumps(enriched_data.get('data_breaches', [])) if enriched_data.get('data_breaches') else None,
                    json.dumps(enriched_data.get('photos', [])) if enriched_data.get('photos') else None,
                    enriched_data.get('bio'),
                    json.dumps(enriched_data.get('languages', [])) if enriched_data.get('languages') else None,
                    json.dumps(enriched_data.get('skills', [])) if enriched_data.get('skills') else None,
                    json.dumps(enriched_data.get('certifications', [])) if enriched_data.get('certifications') else None
                ))
            else:
                self.execute_sql(cursor,'''
                    INSERT OR REPLACE INTO personnes_osint_details (
                        personne_id, location, location_city, location_country, location_address,
                        location_latitude, location_longitude, age_range, birth_date,
                        hobbies, interests, education, professional_history, family_members,
                        data_breaches, photos_urls, bio, languages, skills, certifications
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    personne_id,
                    enriched_data.get('location'),
                    enriched_data.get('location_city'),
                    enriched_data.get('location_country'),
                    enriched_data.get('location_address'),
                    enriched_data.get('location_latitude'),
                    enriched_data.get('location_longitude'),
                    enriched_data.get('age_range'),
                    enriched_data.get('birth_date'),
                    json.dumps(enriched_data.get('hobbies', [])) if enriched_data.get('hobbies') else None,
                    json.dumps(enriched_data.get('interests', [])) if enriched_data.get('interests') else None,
                    enriched_data.get('education'),
                    json.dumps(enriched_data.get('professional_history', [])) if enriched_data.get('professional_history') else None,
                    json.dumps(enriched_data.get('family_members', [])) if enriched_data.get('family_members') else None,
                    json.dumps(enriched_data.get('data_breaches', [])) if enriched_data.get('data_breaches') else None,
                    json.dumps(enriched_data.get('photos', [])) if enriched_data.get('photos') else None,
                    enriched_data.get('bio'),
                    json.dumps(enriched_data.get('languages', [])) if enriched_data.get('languages') else None,
                    json.dumps(enriched_data.get('skills', [])) if enriched_data.get('skills') else None,
                    json.dumps(enriched_data.get('certifications', [])) if enriched_data.get('certifications') else None
                ))
            
            # Sauvegarder les photos dans la table normalisée
            photos = enriched_data.get('photos', [])
            if photos:
                for photo_url in photos:
                    if photo_url:
                        self.execute_sql(cursor,'''
                            INSERT OR IGNORE INTO personnes_photos (personne_id, photo_url, source)
                            VALUES (?, ?, ?)
                        ''', (personne_id, photo_url, 'osint'))
            
            # Sauvegarder les lieux
            if enriched_data.get('location_city') or enriched_data.get('location_address'):
                self.execute_sql(cursor,'''
                    INSERT INTO personnes_locations (
                        personne_id, location_type, address, city, country,
                        latitude, longitude, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    personne_id,
                    'residence',
                    enriched_data.get('location_address'),
                    enriched_data.get('location_city'),
                    enriched_data.get('location_country'),
                    enriched_data.get('location_latitude'),
                    enriched_data.get('location_longitude'),
                    'osint'
                ))
            
            # Sauvegarder les hobbies
            hobbies = enriched_data.get('hobbies', [])
            if hobbies:
                for hobby in hobbies:
                    if hobby:
                        self.execute_sql(cursor,'''
                            INSERT OR IGNORE INTO personnes_hobbies (personne_id, hobby_name, source)
                            VALUES (?, ?, ?)
                        ''', (personne_id, hobby, 'osint'))
            
            # Sauvegarder l'historique professionnel
            professional_history = enriched_data.get('professional_history', [])
            if professional_history:
                for job in professional_history:
                    if isinstance(job, dict):
                        self.execute_sql(cursor,'''
                            INSERT INTO personnes_professional_history (
                                personne_id, company_name, position, start_date, end_date, description, source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            personne_id,
                            job.get('company'),
                            job.get('position'),
                            job.get('start_date'),
                            job.get('end_date'),
                            job.get('description'),
                            'osint'
                        ))
            
            # Sauvegarder les membres de la famille
            family_members = enriched_data.get('family_members', [])
            if family_members:
                for member in family_members:
                    if isinstance(member, dict):
                        self.execute_sql(cursor,'''
                            INSERT INTO personnes_family (
                                personne_id, family_member_name, relationship, age, location, source
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            personne_id,
                            member.get('name'),
                            member.get('relationship'),
                            member.get('age'),
                            member.get('location'),
                            'osint'
                        ))
            
            # Sauvegarder les fuites de données
            data_breaches = enriched_data.get('data_breaches', [])
            if data_breaches:
                for breach in data_breaches:
                    if isinstance(breach, dict):
                        self.execute_sql(cursor,'''
                            INSERT INTO personnes_data_breaches (
                                personne_id, breach_name, breach_date, data_leaked, source
                            ) VALUES (?, ?, ?, ?, ?)
                        ''', (
                            personne_id,
                            breach.get('name'),
                            breach.get('breach_date'),
                            json.dumps(breach.get('data_classes', [])),
                            'osint'
                        ))
            
            conn.commit()
        except Exception as e:
            logger.error(f'Erreur lors de la sauvegarde des détails OSINT pour la personne {personne_id}: {e}')
            conn.rollback()
        finally:
            conn.close()
