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


class Database(
    DatabaseSchema,
    EntrepriseManager,
    GroupeEntrepriseManager,
    DatabaseAnalyses,
    ScraperManager,
    PersonneManager,
    CampagneManager,
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
    
    def __init__(self, db_path=None):
        """
        Initialise la base de données
        
        Args:
            db_path: Chemin vers le fichier de base de données (optionnel)
        """
        # Initialiser toutes les classes parentes via super()
        # Cela résout automatiquement le MRO
        super().__init__(db_path)
        
        # Initialiser la base de données (créer les tables)
        self.init_database()


# Exposer Database pour compatibilité avec l'import existant
__all__ = ['Database']

