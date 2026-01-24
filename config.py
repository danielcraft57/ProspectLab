"""
Configuration de l'application ProspectLab
"""

import os
from pathlib import Path

# Charger les variables d'environnement depuis .env si disponible
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv n'est pas installé, on continue sans
    pass

# Chemins de base
BASE_DIR = Path(__file__).parent.parent
APP_DIR = Path(__file__).parent

# Configuration Flask
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
UPLOAD_FOLDER = APP_DIR / 'uploads'
EXPORT_FOLDER = APP_DIR / 'exports'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Créer les dossiers si nécessaire
UPLOAD_FOLDER.mkdir(exist_ok=True)
EXPORT_FOLDER.mkdir(exist_ok=True)

# Configuration email (à configurer selon ton serveur)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'Loic Daniel <loic@example.com>')

# Configuration scraping
SCRAPING_DELAY = 2.0  # Délai entre requêtes (secondes)
SCRAPING_MAX_WORKERS = 3  # Nombre de threads parallèles
SCRAPING_MAX_DEPTH = 3  # Profondeur maximale de scraping

# Allowed extensions
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# Configuration base de données
DATABASE_PATH = os.environ.get('DATABASE_PATH', None)  # None = chemin par défaut

# Configuration API Sirene (data.gouv.fr)
# L'API publique ne nécessite pas de clé, mais une clé permet plus de requêtes
SIRENE_API_KEY = os.environ.get('SIRENE_API_KEY', '')
SIRENE_API_URL = os.environ.get('SIRENE_API_URL', 'https://recherche-entreprises.api.gouv.fr/search')

# Configuration APIs OSINT (optionnelles mais recommandées)
SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', '')
CENSYS_API_ID = os.environ.get('CENSYS_API_ID', '')
CENSYS_API_SECRET = os.environ.get('CENSYS_API_SECRET', '')
HUNTER_API_KEY = os.environ.get('HUNTER_API_KEY', '')
BUILTWITH_API_KEY = os.environ.get('BUILTWITH_API_KEY', '')
HIBP_API_KEY = os.environ.get('HIBP_API_KEY', '')

# Configuration WSL (pour les outils OSINT/Pentest)
WSL_DISTRO = os.environ.get('WSL_DISTRO', 'kali-linux')
WSL_USER = os.environ.get('WSL_USER', 'loupix')

# Configuration timeout pour les outils externes
OSINT_TOOL_TIMEOUT = int(os.environ.get('OSINT_TOOL_TIMEOUT', '60'))  # secondes
PENTEST_TOOL_TIMEOUT = int(os.environ.get('PENTEST_TOOL_TIMEOUT', '120'))  # secondes

# Configuration des limites de requêtes API
SIRENE_API_RATE_LIMIT = int(os.environ.get('SIRENE_API_RATE_LIMIT', '10'))  # requêtes par minute

# Configuration Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'Europe/Paris'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max par tâche
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes avant arrêt doux
# Nombre de workers Celery (4 en dev, 6 en prod par défaut)
CELERY_WORKERS = int(os.environ.get('CELERY_WORKERS', '4'))

# URL de base pour le tracking des emails (doit être accessible publiquement)
# Exemple: https://votre-domaine.com ou http://votre-ip:5000
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
