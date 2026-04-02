"""
Module de base de données ProspectLab - Architecture modulaire

Ce module expose la classe Database qui combine toutes les fonctionnalités
de gestion de la base de données via des mixins.

Architecture :
- base.py : Connexion et initialisation
- schema.py : Création des tables
- entreprises.py : Gestion des entreprises
- analyses.py : Gestion des analyses générales
- scrapers.py : Gestion des scrapers
- personnes.py : Gestion des personnes
- campagnes.py : Gestion des campagnes email
- osint.py : Gestion des analyses OSINT
- technical.py : Gestion des analyses techniques
- pentest.py : Gestion des analyses pentest
"""

from .base import DatabaseBase
from .schema import DatabaseSchema
from .entreprises import EntrepriseManager
from .groupes import GroupeEntrepriseManager
from .analyses import DatabaseAnalyses
from .scrapers import ScraperManager
from .personnes import PersonneManager
from .campagnes import CampagneManager
from .osint import OSINTManager
from .technical import TechnicalManager
from .pentest import PentestManager
from .seo import SEOManager
from .email_templates import EmailTemplateManager
import os
import threading
import logging


class Database(
    DatabaseSchema,
    EntrepriseManager,
    GroupeEntrepriseManager,
    DatabaseAnalyses,
    ScraperManager,
    PersonneManager,
    CampagneManager,
    EmailTemplateManager,
    OSINTManager,
    TechnicalManager,
    PentestManager,
    SEOManager,
    DatabaseBase  # DatabaseBase en dernier pour résoudre le MRO
):
    """
    Classe principale de gestion de la base de données
    
    Combine toutes les fonctionnalités via l'héritage multiple (mixins).
    Cette architecture permet de séparer les responsabilités tout en
    gardant une interface unifiée.
    
    Usage:
        from services.database import Database
        
        db = Database()
        entreprises = db.get_entreprises()
    """
    
    # Initialisation schéma "once" par process Python (web/worker).
    # Évite que chaque tâche Celery relance init_database() et ses ALTER TABLE,
    # source de locks/timeouts sous charge.
    _schema_init_lock = threading.Lock()
    _schema_initialized = False

    def __init__(self, db_path=None):
        """
        Initialise la base de données
        
        Args:
            db_path: Chemin vers le fichier de base de données (optionnel)
        """
        # Initialiser toutes les classes parentes via super()
        # Cela résout automatiquement le MRO
        super().__init__(db_path)

        try:
            self.ensure_commercial_priority_profiles_table()
        except Exception:
            logging.getLogger(__name__).warning(
                'Migration commercial_priority_profiles non appliquée', exc_info=True
            )

        try:
            self.ensure_entreprise_metric_snapshots_table()
        except Exception:
            logging.getLogger(__name__).warning(
                'Migration entreprise_metric_snapshots non appliquée', exc_info=True
            )

        # Initialiser la base de données (créer les tables) une seule fois par process.
        # Permet un contournement explicite via env pour debug/migration forcée.
        force_each_instance = str(os.environ.get('DB_INIT_EACH_INSTANCE', '')).strip().lower() in (
            '1', 'true', 'yes', 'on'
        )
        if force_each_instance:
            self.init_database()
            return

        if not Database._schema_initialized:
            with Database._schema_init_lock:
                if not Database._schema_initialized:
                    self.init_database()
                    Database._schema_initialized = True
                    logging.getLogger(__name__).info(
                        'Schéma DB initialisé (once par process).'
                    )


# Exposer Database pour compatibilité avec l'import existant
__all__ = ['Database']

