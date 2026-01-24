"""
Module de base pour la gestion de la base de données
Contient la classe Database de base avec la connexion et les méthodes communes
Supporte SQLite (dev) et PostgreSQL (prod)
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, Union, Any
from urllib.parse import urlparse

# Charger les variables d'environnement depuis .env si disponible
# Important : charger avant toute initialisation de DatabaseBase
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv n'est pas installé, on continue sans
    pass


class DatabaseBase:
    """
    Classe de base pour la gestion de la base de données
    Gère la connexion et l'initialisation
    Supporte SQLite (dev) et PostgreSQL (prod) via détection automatique
    """
    
    def __init__(self, db_path: Optional[str] = None, database_url: Optional[str] = None):
        """
        Initialise la connexion à la base de données
        
        Args:
            db_path: Chemin vers le fichier de base de données SQLite (optionnel, pour dev)
            database_url: URL de connexion PostgreSQL (optionnel, pour prod)
                          Format: postgresql://user:password@host:port/database
        """
        # Détecter le type de base de données
        self.database_url = database_url or os.environ.get('DATABASE_URL')
        
        if self.database_url and self.database_url.startswith('postgresql://'):
            # Mode PostgreSQL (prod)
            self.db_type = 'postgresql'
            self.db_path = None
        else:
            # Mode SQLite (dev)
            self.db_type = 'sqlite'
            
        if db_path is None:
            # Vérifier si un chemin est défini dans les variables d'environnement
            env_db_path = os.environ.get('DATABASE_PATH')
            if env_db_path:
                db_path = env_db_path
            else:
                app_dir = Path(__file__).parent.parent.parent
                db_path = app_dir / 'prospectlab.db'
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
    
    def get_connection(self) -> Union[sqlite3.Connection, Any]:
        """
        Obtient une connexion à la base de données
        
        Returns:
            Connexion SQLite ou PostgreSQL selon la configuration
        """
        if self.db_type == 'postgresql':
            return self._get_postgres_connection()
        else:
            return self._get_sqlite_connection()
    
    def _get_sqlite_connection(self) -> sqlite3.Connection:
        """
        Obtient une connexion SQLite
        
        Returns:
            Connexion SQLite avec row_factory configuré
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # Activer les foreign keys pour que CASCADE fonctionne
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
    
    def _get_postgres_connection(self):
        """
        Obtient une connexion PostgreSQL
        
        Returns:
            Connexion PostgreSQL avec un adaptateur pour compatibilité row_factory
        """
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise ImportError(
                "psycopg2-binary n'est pas installé. "
                "Installez-le avec: pip install psycopg2-binary"
            )
        
        conn = psycopg2.connect(self.database_url)
        # Utiliser RealDictCursor pour avoir un comportement similaire à sqlite3.Row
        conn.cursor_factory = RealDictCursor
        return conn
    
    def is_postgresql(self) -> bool:
        """
        Indique si on utilise PostgreSQL
        
        Returns:
            True si PostgreSQL, False si SQLite
        """
        return self.db_type == 'postgresql'
    
    def is_sqlite(self) -> bool:
        """
        Indique si on utilise SQLite
        
        Returns:
            True si SQLite, False si PostgreSQL
        """
        return self.db_type == 'sqlite'
    
    def adapt_sql(self, sql: str) -> str:
        """
        Adapte une requête SQL selon le type de base de données
        
        Args:
            sql: Requête SQL écrite pour SQLite
            
        Returns:
            Requête SQL adaptée pour PostgreSQL si nécessaire, sinon inchangée
        """
        if self.db_type == 'postgresql':
            import re
            # Normaliser d'abord les espaces multiples et retours à la ligne pour faciliter la détection
            # On garde une copie originale pour la structure, mais on normalise pour la détection
            sql_for_detection = re.sub(r'\s+', ' ', sql)
            
            # Remplacer AUTOINCREMENT par SERIAL
            sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            sql = sql.replace('AUTOINCREMENT', '')
            # Remplacer CURRENT_TIMESTAMP par NOW()
            sql = sql.replace('DEFAULT CURRENT_TIMESTAMP', 'DEFAULT NOW()')
            # Remplacer TEXT par VARCHAR ou TEXT (Postgres accepte TEXT)
            # On garde TEXT car Postgres le supporte
            # Remplacer REAL par DOUBLE PRECISION pour plus de précision
            sql = sql.replace('REAL', 'DOUBLE PRECISION')
            # Corriger les valeurs par défaut pour les BOOLEAN (0 -> FALSE, 1 -> TRUE)
            sql = sql.replace('BOOLEAN DEFAULT 0', 'BOOLEAN DEFAULT FALSE')
            sql = sql.replace('BOOLEAN DEFAULT 1', 'BOOLEAN DEFAULT TRUE')
            # Supprimer les PRAGMA (spécifiques à SQLite)
            sql = sql.replace('PRAGMA foreign_keys = ON;', '')
            sql = sql.replace('PRAGMA foreign_keys = ON', '')
            
            # Remplacer INSERT OR IGNORE par INSERT ... ON CONFLICT DO NOTHING
            # Remplacer INSERT OR REPLACE par INSERT ... ON CONFLICT DO UPDATE
            # Pour PostgreSQL, ON CONFLICT nécessite une contrainte unique
            # Pattern pour détecter INSERT OR REPLACE (utiliser la version normalisée pour la détection)
            if 'INSERT OR REPLACE' in sql_for_detection.upper():
                # Remplacer INSERT OR REPLACE par INSERT (gère les retours à la ligne)
                sql = re.sub(r'INSERT\s+OR\s+REPLACE', 'INSERT', sql, flags=re.IGNORECASE | re.DOTALL)
                # Ajouter ON CONFLICT DO UPDATE à la fin de la requête
                if 'ON CONFLICT' not in sql.upper():
                    # Normaliser la requête pour faciliter l'extraction (remplacer retours à la ligne par espaces)
                    sql_normalized_for_extract = re.sub(r'\s+', ' ', sql)
                    # Extraire les colonnes de la clause INSERT
                    # Pattern: INSERT INTO table (col1, col2, col3) VALUES (...)
                    insert_match = re.search(r'INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)', sql_normalized_for_extract, re.IGNORECASE)
                    if insert_match:
                        table_name = insert_match.group(1)
                        columns_str = insert_match.group(2)
                        columns = [col.strip() for col in columns_str.split(',')]
                        
                        # Déterminer les colonnes de conflit selon la table
                        # Pour les tables avec analysis_id, généralement (analysis_id, autre_colonne)
                        conflict_cols = []
                        update_set = []
                        
                        if 'analysis_id' in columns:
                            # Tables d'analyse : contrainte sur (analysis_id, autre_colonne)
                            if 'header_name' in columns:
                                # analysis_pentest_security_headers, analysis_technique_security_headers
                                conflict_cols = ['analysis_id', 'header_name']
                                if 'status' in columns:
                                    update_set.append('status = EXCLUDED.status')
                                if 'header_value' in columns:
                                    update_set.append('header_value = EXCLUDED.header_value')
                            elif 'name' in columns:
                                # analysis_pentest_vulnerabilities, etc.
                                conflict_cols = ['analysis_id', 'name']
                                for col in columns:
                                    if col not in ['id', 'analysis_id', 'name']:
                                        update_set.append(f'{col} = EXCLUDED.{col}')
                            elif 'port' in columns:
                                # analysis_pentest_open_ports
                                conflict_cols = ['analysis_id', 'port']
                                if 'service' in columns:
                                    update_set.append('service = EXCLUDED.service')
                            else:
                                # Fallback : utiliser les deux premières colonnes (généralement analysis_id et une autre)
                                conflict_cols = columns[:2] if len(columns) >= 2 else columns
                                for col in columns[2:]:
                                    update_set.append(f'{col} = EXCLUDED.{col}')
                        else:
                            # Autres tables : utiliser toutes les colonnes sauf l'ID comme contrainte
                            non_id_cols = [col for col in columns if col.lower() != 'id']
                            if non_id_cols:
                                conflict_cols = non_id_cols
                                # Mettre à jour toutes les colonnes
                                for col in columns:
                                    if col.lower() != 'id':
                                        update_set.append(f'{col} = EXCLUDED.{col}')
                        
                        # Construire la clause ON CONFLICT
                        if conflict_cols and update_set:
                            conflict_str = ', '.join(conflict_cols)
                            update_str = ', '.join(update_set)
                            on_conflict = f' ON CONFLICT ({conflict_str}) DO UPDATE SET {update_str}'
                        elif conflict_cols:
                            # Si pas de colonnes à mettre à jour, utiliser DO NOTHING
                            conflict_str = ', '.join(conflict_cols)
                            on_conflict = f' ON CONFLICT ({conflict_str}) DO NOTHING'
                        else:
                            # Fallback générique
                            on_conflict = ' ON CONFLICT DO UPDATE SET status = EXCLUDED.status'
                        
                        # Ajouter à la fin de la requête
                        if sql.rstrip().endswith(';'):
                            sql = sql.rstrip()[:-1] + on_conflict + ';'
                        else:
                            sql = sql.rstrip() + on_conflict
                    else:
                        # Fallback si on ne peut pas extraire les colonnes
                        # Utiliser un pattern générique
                        if sql.rstrip().endswith(';'):
                            sql = sql.rstrip()[:-1] + ' ON CONFLICT DO UPDATE SET status = EXCLUDED.status;'
                        else:
                            sql = sql.rstrip() + ' ON CONFLICT DO UPDATE SET status = EXCLUDED.status'
            # Pattern pour détecter INSERT OR IGNORE
            elif 'INSERT OR IGNORE' in sql.upper():
                # Remplacer INSERT OR IGNORE par INSERT
                sql = re.sub(r'INSERT\s+OR\s+IGNORE', 'INSERT', sql, flags=re.IGNORECASE)
                # Ajouter ON CONFLICT DO NOTHING à la fin de la requête (avant le point-virgule ou à la fin)
                # On cherche la fin de la requête (avant ; ou fin de ligne)
                if 'ON CONFLICT' not in sql.upper():
                    # Trouver la fin de la requête et ajouter ON CONFLICT DO NOTHING
                    # Approche simple: ajouter avant le point-virgule final ou à la fin
                    if sql.rstrip().endswith(';'):
                        sql = sql.rstrip()[:-1] + ' ON CONFLICT DO NOTHING;'
                    else:
                        sql = sql.rstrip() + ' ON CONFLICT DO NOTHING'
        return sql
    
    def handle_operational_error(self, error: Exception) -> bool:
        """
        Gère les erreurs OperationalError selon le type de base
        
        Args:
            error: Exception levée
            
        Returns:
            True si l'erreur peut être ignorée (ex: colonne existe déjà), False sinon
        """
        error_str = str(error).lower()
        
        if self.db_type == 'sqlite':
            # SQLite: "duplicate column name" ou "already exists"
            return 'duplicate column' in error_str or 'already exists' in error_str
        else:
            # PostgreSQL: "column ... already exists" ou "relation ... already exists" ou "does not exist" (table pas encore créée)
            return 'already exists' in error_str or 'duplicate' in error_str or 'does not exist' in error_str
    
    def execute_sql(self, cursor, sql: str, params=None):
        """
        Exécute une requête SQL en l'adaptant selon le type de base
        
        Args:
            cursor: Curseur de base de données
            sql: Requête SQL (écrite pour SQLite avec placeholders ?)
            params: Paramètres optionnels pour la requête
        """
        adapted_sql = self.adapt_sql(sql)
        
        # Adapter les placeholders : SQLite utilise ?, PostgreSQL utilise %s
        if self.db_type == 'postgresql':
            # Remplacer tous les ? par %s, mais pas ceux dans les chaînes littérales
            # Approche simple : remplacer tous les ? par %s
            adapted_sql = adapted_sql.replace('?', '%s')
        
        # Debug : vérifier si INSERT OR REPLACE est encore présent après adaptation
        if self.db_type == 'postgresql' and 'INSERT OR REPLACE' in adapted_sql.upper():
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'ERREUR CRITIQUE: INSERT OR REPLACE non converti! Requête originale: {sql[:200]}')
            logger.error(f'Requête adaptée: {adapted_sql[:200]}')
            # Forcer la conversion en dernier recours
            import re
            adapted_sql = re.sub(r'INSERT\s+OR\s+REPLACE', 'INSERT', adapted_sql, flags=re.IGNORECASE | re.DOTALL)
            # Ajouter ON CONFLICT basique si pas déjà présent
            if 'ON CONFLICT' not in adapted_sql.upper():
                # Extraire le nom de la table
                table_match = re.search(r'INSERT\s+INTO\s+(\w+)', adapted_sql, re.IGNORECASE)
                if table_match:
                    table_name = table_match.group(1)
                    # Pour analysis_pentest_security_headers, utiliser (analysis_id, header_name)
                    if 'security_headers' in table_name:
                        adapted_sql = re.sub(r'(\s*VALUES\s*\([^)]+\))', r'\1 ON CONFLICT (analysis_id, header_name) DO UPDATE SET status = EXCLUDED.status', adapted_sql, flags=re.IGNORECASE)
                    else:
                        # Fallback générique
                        adapted_sql = re.sub(r'(\s*VALUES\s*\([^)]+\))', r'\1 ON CONFLICT DO UPDATE SET status = EXCLUDED.status', adapted_sql, flags=re.IGNORECASE)
        
        if params:
            cursor.execute(adapted_sql, params)
        else:
            cursor.execute(adapted_sql)
    
    def execute(self, cursor, sql: str, params=None):
        """
        Alias pour execute_sql pour compatibilité
        Permet d'utiliser self.execute() au lieu de self.execute_sql()
        """
        return self.execute_sql(cursor, sql, params)
    
    def insert_or_ignore_sql(self, table: str, columns: list, conflict_columns: list = None):
        """
        Génère une requête INSERT OR IGNORE compatible SQLite et PostgreSQL
        
        Args:
            table: Nom de la table
            columns: Liste des colonnes à insérer
            conflict_columns: Colonnes pour la contrainte ON CONFLICT (PostgreSQL)
                            Si None, utilise toutes les colonnes sauf la première (généralement l'ID)
        
        Returns:
            str: Requête SQL adaptée
        """
        cols_str = ', '.join(columns)
        placeholders = ', '.join(['?' if self.db_type == 'sqlite' else '%s'] * len(columns))
        
        if self.db_type == 'postgresql':
            # Pour PostgreSQL, utiliser ON CONFLICT DO NOTHING
            if conflict_columns is None:
                # Par défaut, utiliser toutes les colonnes sauf la première (généralement l'ID auto-incrémenté)
                conflict_columns = columns[1:] if len(columns) > 1 else columns
            conflict_str = ', '.join(conflict_columns)
            return f'INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT ({conflict_str}) DO NOTHING'
        else:
            # Pour SQLite, utiliser INSERT OR IGNORE
            return f'INSERT OR IGNORE INTO {table} ({cols_str}) VALUES ({placeholders})'
    
    def safe_execute_sql(self, cursor, sql: str, params=None):
        """
        Exécute une requête SQL en gérant les erreurs "déjà existant"
        Utile pour les migrations (ALTER TABLE ADD COLUMN, etc.)
        
        Args:
            cursor: Curseur de base de données
            sql: Requête SQL (écrite pour SQLite)
            params: Paramètres optionnels pour la requête
        """
        try:
            self.execute_sql(cursor, sql, params)
            # Pour PostgreSQL, commit après chaque migration réussie pour éviter les transactions bloquées
            if self.db_type == 'postgresql':
                cursor.connection.commit()
        except Exception as e:
            # Pour PostgreSQL, si une transaction a échoué, il faut faire un rollback
            if self.db_type == 'postgresql':
                try:
                    cursor.connection.rollback()
                except:
                    pass
            
            # Ignorer les erreurs "déjà existant"
            if not self.handle_operational_error(e):
                raise

