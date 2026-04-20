"""
Tâches Celery pour ProspectLab

Ce module importe toutes les tâches pour qu'elles soient enregistrées avec Celery.
"""

# Importer toutes les tâches pour qu'elles soient enregistrées
from . import analysis_tasks
from . import scraping_tasks
from . import technical_analysis_tasks
from . import osint_tasks
from . import pentest_tasks
from . import seo_tasks
from . import screenshot_tasks
from . import email_tasks
from . import phone_tasks
from . import debug_tasks
from . import metric_rescan_tasks

__all__ = [
    'analysis_tasks',
    'scraping_tasks',
    'technical_analysis_tasks',
    'osint_tasks',
    'pentest_tasks',
    'seo_tasks',
    'screenshot_tasks',
    'email_tasks',
    'phone_tasks',
    'debug_tasks',
    'metric_rescan_tasks',
]
