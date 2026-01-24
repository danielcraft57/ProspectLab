"""
Configuration Celery pour ProspectLab

Celery est utilisé pour exécuter les tâches longues (scraping, analyses) 
de manière asynchrone, évitant ainsi de bloquer l'application Flask.
"""

from celery import Celery
from celery.signals import setup_logging
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_SERIALIZER, \
    CELERY_RESULT_SERIALIZER, CELERY_ACCEPT_CONTENT, CELERY_TIMEZONE, CELERY_ENABLE_UTC, \
    CELERY_TASK_TRACK_STARTED, CELERY_TASK_TIME_LIMIT, CELERY_TASK_SOFT_TIME_LIMIT

# Configuration des logs Celery via le module centralisé
from services.logging_config import setup_celery_logger

# Configurer les logs Celery
celery_logger = setup_celery_logger()

# Signal pour configurer les logs Celery au démarrage du worker
@setup_logging.connect
def config_celery_logging(*args, **kwargs):
    """Configure les logs Celery au démarrage du worker"""
    # Les logs sont configurés via setup_celery_logger
    pass

# Créer l'instance Celery
celery = Celery(
    'prospectlab',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# Configuration Celery
import sys

celery.conf.update(
    task_serializer=CELERY_TASK_SERIALIZER,
    result_serializer=CELERY_RESULT_SERIALIZER,
    accept_content=CELERY_ACCEPT_CONTENT,
    timezone=CELERY_TIMEZONE,
    enable_utc=CELERY_ENABLE_UTC,
    task_track_started=CELERY_TASK_TRACK_STARTED,
    task_time_limit=CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
    # Importer automatiquement les tâches
    imports=(
        'tasks.analysis_tasks',
        'tasks.scraping_tasks',
        'tasks.technical_analysis_tasks',
        'tasks.osint_tasks',
        'tasks.email_tasks',
        'tasks.cleanup_tasks',
    ),
    # Configuration pour Windows : utiliser solo au lieu de prefork
    # Le mode prefork n'est pas supporté sur Windows
    # En production Linux, on utilise threads pour une meilleure efficacité mémoire
    # Le paramètre --pool=threads dans la ligne de commande surcharge cette valeur
    worker_pool='solo' if sys.platform == 'win32' else 'threads',
    broker_connection_retry_on_startup=True,
    # Configuration des logs
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    worker_hijack_root_logger=False,  # Ne pas prendre le contrôle du root logger
    # Configuration du beat scheduler pour les tâches périodiques
    beat_schedule={
        'cleanup-old-files': {
            'task': 'cleanup.cleanup_old_files',
            'schedule': 3600.0,  # Toutes les heures
            'args': (6,)  # Supprimer les fichiers de plus de 6 heures
        },
    },
)


def make_celery(app):
    """
    Configure Celery pour utiliser le contexte Flask
    
    Args:
        app: Instance de l'application Flask
        
    Returns:
        Celery: Instance Celery configurée
        
    Example:
        >>> celery = make_celery(app)
    """
    class ContextTask(celery.Task):
        """Permet à Celery d'accéder au contexte Flask"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery


# Importer les tâches pour qu'elles soient enregistrées avec Celery
# Cela doit être fait après la création de l'instance celery
try:
    # Importer le module tasks qui importe toutes les tâches
    import tasks
except ImportError as e:
    # Les tâches peuvent ne pas être disponibles au moment de l'import
    # C'est normal si on importe celery_app avant que les tâches soient définies
    import logging
    logging.warning(f"Impossible d'importer les tâches Celery: {e}")

