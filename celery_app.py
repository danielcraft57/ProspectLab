"""
Configuration Celery pour ProspectLab

Celery est utilisé pour exécuter les tâches longues (scraping, analyses) 
de manière asynchrone, évitant ainsi de bloquer l'application Flask.
"""

from celery import Celery
from celery.signals import setup_logging
from celery.schedules import crontab
from kombu import Queue
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_SERIALIZER, \
    CELERY_RESULT_SERIALIZER, CELERY_ACCEPT_CONTENT, CELERY_TIMEZONE, CELERY_ENABLE_UTC, \
    CELERY_TASK_TRACK_STARTED, CELERY_TASK_TIME_LIMIT, CELERY_TASK_SOFT_TIME_LIMIT, \
    CELERY_WORKER_PREFETCH_MULTIPLIER, CELERY_TASK_ACKS_LATE

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
    # Répartition : tâches légères (emails, cron) vs lourdes (analyses, scraping)
    task_default_queue='celery',
    task_queues=(
        Queue('celery', routing_key='celery'),
        Queue('scraping', routing_key='scraping'),
        # Relances UI / API unitaires : ne pas se faire bloquer derrière un bulk multi-sites
        Queue('scraping_interactive', routing_key='scraping_interactive'),
        Queue('technical', routing_key='technical'),
        Queue('seo', routing_key='seo'),
        Queue('osint', routing_key='osint'),
        Queue('pentest', routing_key='pentest'),
        # Queue legacy conservée (compat). A terme, tout doit être routé ailleurs.
        Queue('heavy', routing_key='heavy'),
        # Pack « analyse site complet » : file dédiée pour éviter qu’un vieux worker (file celery
        # seule) vole le job et renvoie NotRegistered alors qu’un autre nœud a le code à jour.
        Queue('website_full', routing_key='website_full'),
    ),
    # Dict pattern -> route (Celery 5 / kombu : une *liste* de tuples casse MapRoute qui itère
    # chaque entrée en « k, v » — le 1er élément est une str → too many values to unpack).
    task_routes={
        # scrape_emails sans queue explicite → relances UI ; le bulk API garde apply_async(..., queue='scraping')
        'tasks.scraping_tasks.scrape_emails_task': {'queue': 'scraping_interactive'},
        # Bulk "analyse site" : isoler sur la queue heavy (utile pour donner plus de temps au node rapide).
        'tasks.scraping_tasks.scrape_analysis_orchestrator_task': {'queue': 'heavy'},
        'tasks.scraping_tasks.scrape_analysis_task': {'queue': 'heavy'},
        # Pentest dédié sur heavy (évite qu’un worker plus lent prenne trop de tâches).
        'tasks.pentest_tasks.pentest_analysis_task': {'queue': 'heavy'},
        'tasks.scraping_tasks.*': {'queue': 'scraping'},
        'tasks.technical_analysis_tasks.*': {'queue': 'technical'},
        'tasks.seo_tasks.*': {'queue': 'seo'},
        'tasks.osint_tasks.*': {'queue': 'osint'},
        'tasks.phone_tasks.*': {'queue': 'osint'},
        'tasks.pentest_tasks.*': {'queue': 'pentest'},
        # Analyse Excel "pack" : plutôt côté technique (inclut notamment génération des sous-tâches).
        'tasks.analysis_tasks.*': {'queue': 'technical'},
        # Pack site unique : même file que les analyses techniques par défaut (voir CELERY_FULL_ANALYSIS_QUEUE).
        # La queue « website_full » reste disponible pour un worker dédié (isolation / charge).
        'tasks.full_website_analysis.*': {'queue': 'technical'},
    },
    task_create_missing_queues=True,
    worker_prefetch_multiplier=CELERY_WORKER_PREFETCH_MULTIPLIER,
    task_acks_late=CELERY_TASK_ACKS_LATE,
    # Importer automatiquement les tâches
    # Important : inclure explicitement toutes les tâches spécialisées
    imports=(
        'tasks.debug_tasks',
        'tasks.analysis_tasks',
        'tasks.scraping_tasks',
        'tasks.technical_analysis_tasks',
        'tasks.osint_tasks',
        'tasks.phone_tasks',
        'tasks.pentest_tasks',
        'tasks.seo_tasks',
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
        'start-scheduled-campagnes': {
            'task': 'tasks.email_tasks.start_scheduled_campagnes',
            'schedule': 60.0,  # Toutes les minutes : lance les campagnes dont l'heure programmée est atteinte (UTC)
        },
        # Rapports de campagnes (matin / soir) vers contact@danielcraft.fr
        'campagnes-report-evening': {
            'task': 'tasks.email_tasks.send_campagnes_report_task',
            'schedule': crontab(hour=18, minute=0),  # Tous les jours à 18h (heure de Paris via CELERY_TIMEZONE)
            'args': ('evening',),
        },
        'campagnes-report-morning': {
            'task': 'tasks.email_tasks.send_campagnes_report_task',
            'schedule': crontab(hour=8, minute=0),  # Tous les jours à 8h
            'args': ('morning',),
        },
        # Vérification périodique des changements significatifs des performances de campagnes
        'campagnes-significant-changes': {
            'task': 'tasks.email_tasks.check_campaigns_significant_changes_task',
            'schedule': 1800.0,  # Toutes les 30 minutes
        },
        # Scan IMAP des bounces: 2 fois par jour (sans limite de messages par défaut)
        'bounce-scan-morning': {
            'task': 'tasks.email_tasks.run_bounce_scan_task',
            'schedule': crontab(hour=8, minute=10),
        },
        'bounce-scan-evening': {
            'task': 'tasks.email_tasks.run_bounce_scan_task',
            'schedule': crontab(hour=20, minute=10),
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


