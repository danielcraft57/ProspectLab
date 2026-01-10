"""
Tâches Celery pour ProspectLab

Ce module importe toutes les tâches pour qu'elles soient enregistrées avec Celery.
"""

# Importer toutes les tâches pour qu'elles soient enregistrées
from . import analysis_tasks
from . import scraping_tasks
from . import technical_analysis_tasks
from . import technical_advanced_tasks
from . import email_tasks

__all__ = [
    'analysis_tasks',
    'scraping_tasks',
    'technical_analysis_tasks',
    'technical_advanced_tasks',
    'email_tasks',
]
