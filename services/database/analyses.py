"""
Module de gestion des analyses générales
Contient les méthodes pour les analyses de base
"""

import json
from .base import DatabaseBase


class DatabaseAnalyses(DatabaseBase):
    """
    Gère les analyses générales (pas techniques/OSINT/Pentest)
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module analyses"""
        super().__init__(*args, **kwargs)
    
    def save_analysis(self, filename, output_filename, total, parametres, duree=None):
        """
        Sauvegarde une analyse dans la base
        
        Args:
            filename: Nom du fichier d'entrée
            output_filename: Nom du fichier de sortie
            total: Nombre total d'entreprises
            parametres: Paramètres de l'analyse (dict)
            duree: Durée en secondes (optionnel)
        
        Returns:
            ID de l'analyse créée
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Utiliser RETURNING pour PostgreSQL, sinon lastrowid pour SQLite
        import logging
        logger = logging.getLogger(__name__)
        
        if self.is_postgresql():
            logger.info(f'save_analysis PostgreSQL: insertion en cours...')
            self.execute_sql(cursor,'''
                INSERT INTO analyses (filename, output_filename, total_entreprises, parametres, statut, duree_secondes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (filename, output_filename, total, json.dumps(parametres), 'Terminé', duree))
            result = cursor.fetchone()
            logger.info(f'save_analysis PostgreSQL: result={result}, type={type(result)}')
            # Avec RealDictCursor, result est un dictionnaire
            if result:
                if isinstance(result, dict):
                    analysis_id = result.get('id')
                else:
                    # Fallback si ce n'est pas un dict
                    analysis_id = result[0] if hasattr(result, '__getitem__') else None
                logger.info(f'save_analysis PostgreSQL: analysis_id extrait={analysis_id}')
            else:
                analysis_id = None
                logger.error(f'save_analysis PostgreSQL: result est None!')
        else:
            self.execute_sql(cursor,'''
                INSERT INTO analyses (filename, output_filename, total_entreprises, parametres, statut, duree_secondes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (filename, output_filename, total, json.dumps(parametres), 'Terminé', duree))
            analysis_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        # Log pour déboguer
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'save_analysis: analysis_id={analysis_id}, filename={filename}, is_postgresql={self.is_postgresql()}')
        
        if not analysis_id or analysis_id == 0:
            logger.error(f'ERREUR: save_analysis a retourné un ID invalide: {analysis_id}')
        
        return analysis_id
    
    def get_analyses(self, limit=50):
        """
        Récupère les analyses récentes
        
        Args:
            limit: Nombre maximum d'analyses à retourner
        
        Returns:
            Liste des analyses
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT * FROM analyses
            ORDER BY date_creation DESC
            LIMIT ?
        ''', (limit,))
        
        analyses = []
        for row in cursor.fetchall():
            analysis = dict(row)
            if analysis.get('parametres'):
                try:
                    analysis['parametres'] = json.loads(analysis['parametres'])
                except:
                    pass
            analyses.append(analysis)
        
        conn.close()
        return analyses

