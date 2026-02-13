"""
Module de gestion des analyses SEO
Contient toutes les méthodes liées aux analyses SEO
"""

import json
import logging
from urllib.parse import urlparse
from .base import DatabaseBase

logger = logging.getLogger(__name__)


class SEOManager(DatabaseBase):
    """
    Gère toutes les opérations sur les analyses SEO
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module SEO"""
        super().__init__(*args, **kwargs)
    
    def save_seo_analysis(self, entreprise_id, url, seo_data):
        """
        Sauvegarde une analyse SEO avec normalisation des données
        
        Args:
            entreprise_id: ID de l'entreprise
            url: URL analysée
            seo_data: Dictionnaire avec les données SEO
            
        Returns:
            int: ID de l'analyse créée
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        domain_clean = domain.replace('www.', '') if domain else ''
        
        # Sauvegarder l'analyse principale
        if self.is_postgresql():
            self.execute_sql(cursor,'''
                INSERT INTO analyses_seo (
                    entreprise_id, url, domain, meta_tags_json,
                    headers_json, structure_json, sitemap_json,
                    robots_json, lighthouse_json, issues_json,
                    score, seo_details
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                entreprise_id,
                url,
                domain_clean,
                json.dumps(seo_data.get('meta_tags', {})) if seo_data.get('meta_tags') else None,
                json.dumps(seo_data.get('headers', {})) if seo_data.get('headers') else None,
                json.dumps(seo_data.get('structure', {})) if seo_data.get('structure') else None,
                json.dumps(seo_data.get('sitemap')) if seo_data.get('sitemap') else None,
                json.dumps(seo_data.get('robots')) if seo_data.get('robots') else None,
                json.dumps(seo_data.get('lighthouse')) if seo_data.get('lighthouse') else None,
                json.dumps(seo_data.get('issues', [])) if seo_data.get('issues') else None,
                seo_data.get('score', 0),
                json.dumps(seo_data) if seo_data else None
            ))
            result = cursor.fetchone()
            analysis_id = result['id'] if result else None
        else:
            self.execute_sql(cursor,'''
                INSERT INTO analyses_seo (
                    entreprise_id, url, domain, meta_tags_json,
                    headers_json, structure_json, sitemap_json,
                    robots_json, lighthouse_json, issues_json,
                    score, seo_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entreprise_id,
                url,
                domain_clean,
                json.dumps(seo_data.get('meta_tags', {})) if seo_data.get('meta_tags') else None,
                json.dumps(seo_data.get('headers', {})) if seo_data.get('headers') else None,
                json.dumps(seo_data.get('structure', {})) if seo_data.get('structure') else None,
                json.dumps(seo_data.get('sitemap')) if seo_data.get('sitemap') else None,
                json.dumps(seo_data.get('robots')) if seo_data.get('robots') else None,
                json.dumps(seo_data.get('lighthouse')) if seo_data.get('lighthouse') else None,
                json.dumps(seo_data.get('issues', [])) if seo_data.get('issues') else None,
                seo_data.get('score', 0),
                json.dumps(seo_data) if seo_data else None
            ))
            analysis_id = cursor.lastrowid
        
        # Sauvegarder les meta tags normalisés
        meta_tags = seo_data.get('meta_tags', {})
        if meta_tags:
            for tag_name, tag_value in meta_tags.items():
                if tag_value:
                    tag_type = 'og' if tag_name.startswith('og:') else 'twitter' if tag_name.startswith('twitter:') else 'standard'
                    if self.is_postgresql():
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_seo_meta_tags (analysis_id, tag_name, tag_value, tag_type)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                        ''', (analysis_id, tag_name, str(tag_value), tag_type))
                    else:
                        self.execute_sql(cursor,'''
                            INSERT OR IGNORE INTO analysis_seo_meta_tags (analysis_id, tag_name, tag_value, tag_type)
                            VALUES (?, ?, ?, ?)
                        ''', (analysis_id, tag_name, str(tag_value), tag_type))
        
        # Sauvegarder les headers normalisés
        headers = seo_data.get('headers', {})
        if headers:
            for header_name, header_value in headers.items():
                if header_value:
                    if self.is_postgresql():
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_seo_headers (analysis_id, header_name, header_value)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (analysis_id, header_name) DO UPDATE SET header_value = EXCLUDED.header_value
                        ''', (analysis_id, header_name, str(header_value)))
                    else:
                        self.execute_sql(cursor,'''
                            INSERT OR REPLACE INTO analysis_seo_headers (analysis_id, header_name, header_value)
                            VALUES (?, ?, ?)
                        ''', (analysis_id, header_name, str(header_value)))
        
        # Sauvegarder les issues
        issues = seo_data.get('issues', [])
        if issues:
            for issue in issues:
                if isinstance(issue, dict):
                    issue_type = issue.get('type', 'info')
                    category = issue.get('category', '')
                    message = issue.get('message', '')
                    impact = issue.get('impact', 'low')
                    
                    self.execute_sql(cursor,'''
                        INSERT INTO analysis_seo_issues (analysis_id, issue_type, category, message, impact)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (analysis_id, issue_type, category, message, impact))
        
        conn.commit()
        conn.close()
        
        logger.info(f'Analyse SEO sauvegardée: id={analysis_id}, url={url}')
        return analysis_id
    
    def update_seo_analysis(self, analysis_id, seo_data):
        """
        Met à jour une analyse SEO existante
        
        Args:
            analysis_id: ID de l'analyse
            seo_data: Dictionnaire avec les nouvelles données SEO
            
        Returns:
            int: ID de l'analyse mise à jour
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Mettre à jour l'analyse principale
        if self.is_postgresql():
            self.execute_sql(cursor,'''
                UPDATE analyses_seo SET
                    meta_tags_json = %s,
                    headers_json = %s,
                    structure_json = %s,
                    sitemap_json = %s,
                    robots_json = %s,
                    lighthouse_json = %s,
                    issues_json = %s,
                    score = %s,
                    seo_details = %s
                WHERE id = %s
            ''', (
                json.dumps(seo_data.get('meta_tags', {})) if seo_data.get('meta_tags') else None,
                json.dumps(seo_data.get('headers', {})) if seo_data.get('headers') else None,
                json.dumps(seo_data.get('structure', {})) if seo_data.get('structure') else None,
                json.dumps(seo_data.get('sitemap')) if seo_data.get('sitemap') else None,
                json.dumps(seo_data.get('robots')) if seo_data.get('robots') else None,
                json.dumps(seo_data.get('lighthouse')) if seo_data.get('lighthouse') else None,
                json.dumps(seo_data.get('issues', [])) if seo_data.get('issues') else None,
                seo_data.get('score', 0),
                json.dumps(seo_data) if seo_data else None,
                analysis_id
            ))
        else:
            self.execute_sql(cursor,'''
                UPDATE analyses_seo SET
                    meta_tags_json = ?,
                    headers_json = ?,
                    structure_json = ?,
                    sitemap_json = ?,
                    robots_json = ?,
                    lighthouse_json = ?,
                    issues_json = ?,
                    score = ?,
                    seo_details = ?
                WHERE id = ?
            ''', (
                json.dumps(seo_data.get('meta_tags', {})) if seo_data.get('meta_tags') else None,
                json.dumps(seo_data.get('headers', {})) if seo_data.get('headers') else None,
                json.dumps(seo_data.get('structure', {})) if seo_data.get('structure') else None,
                json.dumps(seo_data.get('sitemap')) if seo_data.get('sitemap') else None,
                json.dumps(seo_data.get('robots')) if seo_data.get('robots') else None,
                json.dumps(seo_data.get('lighthouse')) if seo_data.get('lighthouse') else None,
                json.dumps(seo_data.get('issues', [])) if seo_data.get('issues') else None,
                seo_data.get('score', 0),
                json.dumps(seo_data) if seo_data else None,
                analysis_id
            ))
        
        # Supprimer les données normalisées existantes
        self.execute_sql(cursor, 'DELETE FROM analysis_seo_meta_tags WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor, 'DELETE FROM analysis_seo_headers WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor, 'DELETE FROM analysis_seo_issues WHERE analysis_id = ?', (analysis_id,))
        
        # Réinsérer les données normalisées (même code que save_seo_analysis)
        meta_tags = seo_data.get('meta_tags', {})
        if meta_tags:
            for tag_name, tag_value in meta_tags.items():
                if tag_value:
                    tag_type = 'og' if tag_name.startswith('og:') else 'twitter' if tag_name.startswith('twitter:') else 'standard'
                    if self.is_postgresql():
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_seo_meta_tags (analysis_id, tag_name, tag_value, tag_type)
                            VALUES (%s, %s, %s, %s)
                        ''', (analysis_id, tag_name, str(tag_value), tag_type))
                    else:
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_seo_meta_tags (analysis_id, tag_name, tag_value, tag_type)
                            VALUES (?, ?, ?, ?)
                        ''', (analysis_id, tag_name, str(tag_value), tag_type))
        
        headers = seo_data.get('headers', {})
        if headers:
            for header_name, header_value in headers.items():
                if header_value:
                    if self.is_postgresql():
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_seo_headers (analysis_id, header_name, header_value)
                            VALUES (%s, %s, %s)
                        ''', (analysis_id, header_name, str(header_value)))
                    else:
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_seo_headers (analysis_id, header_name, header_value)
                            VALUES (?, ?, ?)
                        ''', (analysis_id, header_name, str(header_value)))
        
        issues = seo_data.get('issues', [])
        if issues:
            for issue in issues:
                if isinstance(issue, dict):
                    issue_type = issue.get('type', 'info')
                    category = issue.get('category', '')
                    message = issue.get('message', '')
                    impact = issue.get('impact', 'low')
                    
                    self.execute_sql(cursor,'''
                        INSERT INTO analysis_seo_issues (analysis_id, issue_type, category, message, impact)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (analysis_id, issue_type, category, message, impact))
        
        conn.commit()
        conn.close()
        
        logger.info(f'Analyse SEO mise à jour: id={analysis_id}')
        return analysis_id
    
    def get_seo_analysis_by_url(self, url):
        """
        Récupère une analyse SEO par URL
        
        Args:
            url: URL analysée
            
        Returns:
            dict: Analyse SEO ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor, 'SELECT * FROM analyses_seo WHERE url = ? ORDER BY date_analyse DESC LIMIT 1', (url,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_seo_analysis_by_id(self, analysis_id):
        """
        Récupère une analyse SEO par ID
        
        Args:
            analysis_id: ID de l'analyse
            
        Returns:
            dict: Analyse SEO ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor, 'SELECT * FROM analyses_seo WHERE id = ?', (analysis_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_seo_analyses_by_entreprise(self, entreprise_id, limit=10):
        """
        Récupère les analyses SEO d'une entreprise
        
        Args:
            entreprise_id: ID de l'entreprise
            limit: Nombre maximum d'analyses à retourner
            
        Returns:
            list: Liste des analyses SEO
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor, '''
            SELECT * FROM analyses_seo 
            WHERE entreprise_id = ? 
            ORDER BY date_analyse DESC 
            LIMIT ?
        ''', (entreprise_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_all_seo_analyses(self, limit=50):
        """
        Récupère toutes les analyses SEO
        
        Args:
            limit: Nombre maximum d'analyses à retourner
            
        Returns:
            list: Liste des analyses SEO
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor, '''
            SELECT * FROM analyses_seo 
            ORDER BY date_analyse DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
