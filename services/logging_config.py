"""
Configuration centralisée des logs pour ProspectLab

Tous les logs sont enregistrés dans le dossier logs/ avec rotation automatique.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Créer le dossier logs s'il n'existe pas
LOGS_DIR = Path(__file__).parent.parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Configuration des niveaux de log
LOG_LEVEL = logging.INFO  # INFO pour voir les logs importants, DEBUG pour plus de détails

# Format des logs
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Taille max des fichiers de log (10MB)
MAX_LOG_SIZE = 10 * 1024 * 1024
# Nombre de fichiers de backup à garder
BACKUP_COUNT = 1


def setup_logger(name, log_file, level=LOG_LEVEL, console=True):
    """
    Configure un logger avec fichier et console.
    
    Args:
        name: Nom du logger (généralement __name__)
        log_file: Nom du fichier de log (sera dans logs/)
        level: Niveau de log (par défaut LOG_LEVEL)
        console: Si True, affiche aussi dans la console
        
    Returns:
        logging.Logger: Logger configuré
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Éviter les handlers dupliqués
    if logger.handlers:
        return logger
    
    # Chemin complet du fichier de log
    log_path = LOGS_DIR / log_file
    
    # Handler pour le fichier avec rotation
    file_handler = RotatingFileHandler(
        log_path,
        encoding='utf-8',
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Handler pour la console
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


def setup_root_logger(app=None):
    """
    Configure le logger racine pour l'application Flask.
    
    Args:
        app: Instance Flask (optionnel, pour configurer app.logger)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    
    # Supprimer les handlers existants pour éviter les doublons
    root_logger.handlers.clear()
    
    # Handler pour le fichier Flask
    flask_log_path = LOGS_DIR / 'prospectlab.log'
    flask_handler = RotatingFileHandler(
        flask_log_path,
        encoding='utf-8',
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    flask_handler.setLevel(LOG_LEVEL)
    flask_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    flask_handler.setFormatter(flask_formatter)
    root_logger.addHandler(flask_handler)
    
    # Handler pour la console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Configurer aussi le logger Flask si une instance est fournie
    if app:
        app.logger.setLevel(LOG_LEVEL)
        app.logger.handlers.clear()
        app.logger.addHandler(flask_handler)
        app.logger.addHandler(console_handler)
    
    # Configurer aussi les loggers werkzeug et flask
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(LOG_LEVEL)
    werkzeug_logger.handlers.clear()
    werkzeug_logger.addHandler(flask_handler)
    werkzeug_logger.addHandler(console_handler)
    
    flask_app_logger = logging.getLogger('flask.app')
    flask_app_logger.setLevel(LOG_LEVEL)
    flask_app_logger.handlers.clear()
    flask_app_logger.addHandler(flask_handler)
    flask_app_logger.addHandler(console_handler)
    
    return root_logger


def setup_celery_logger():
    """
    Configure le logger Celery.
    
    Returns:
        logging.Logger: Logger Celery configuré
    """
    celery_logger = logging.getLogger('celery')
    celery_logger.setLevel(LOG_LEVEL)
    
    # Éviter les handlers dupliqués
    if celery_logger.handlers:
        return celery_logger
    
    # Handler pour le fichier Celery
    celery_log_path = LOGS_DIR / 'celery.log'
    celery_file_handler = RotatingFileHandler(
        celery_log_path,
        encoding='utf-8',
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    celery_file_handler.setLevel(LOG_LEVEL)
    celery_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    celery_file_handler.setFormatter(celery_formatter)
    celery_logger.addHandler(celery_file_handler)
    
    # Handler pour la console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    celery_logger.addHandler(console_handler)
    
    # Configurer aussi les loggers des tasks
    task_logger = logging.getLogger('celery.task')
    task_logger.setLevel(LOG_LEVEL)
    if not task_logger.handlers:
        task_logger.addHandler(celery_file_handler)
        task_logger.addHandler(console_handler)
    
    return celery_logger

