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
UPLOAD_FOLDER = Path(os.environ.get('UPLOAD_FOLDER', str(APP_DIR / 'uploads')))
EXPORT_FOLDER = Path(os.environ.get('EXPORT_FOLDER', str(APP_DIR / 'exports')))
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Restriction optionnelle à un réseau local (similaire à MailPilot)
# Si RESTRICT_TO_LOCAL_NETWORK=true dans l'environnement, l'app ne sera
# accessible qu'au réseau local, sauf pour certaines routes publiques
# (tracking / API publique).
RESTRICT_TO_LOCAL_NETWORK = os.environ.get('RESTRICT_TO_LOCAL_NETWORK', 'false').lower() == 'true'

# Créer les dossiers si nécessaire
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
EXPORT_FOLDER.mkdir(parents=True, exist_ok=True)

# Configuration email (à configurer selon ton serveur)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'Loic Daniel <loic@example.com>')

# Destinataire par défaut pour les rapports internes (campagnes, diagnostics, etc.)
MAIL_DEFAULT_RECIPIENT = os.environ.get('MAIL_DEFAULT_RECIPIENT', 'contact@danielcraft.fr')

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
# Abstract (https://www.abstractapi.com/) — validation email / téléphone en option
ABSTRACT_EMAIL_API_KEY = os.environ.get('ABSTRACT_EMAIL_API_KEY', '')
ABSTRACT_PHONE_API_KEY = os.environ.get('ABSTRACT_PHONE_API_KEY', '')
# Numverify (APILayer) — ligne type / pays / opérateur pour un E.164
NUMVERIFY_API_KEY = os.environ.get('NUMVERIFY_API_KEY', '')
BUILTWITH_API_KEY = os.environ.get('BUILTWITH_API_KEY', '')
HIBP_API_KEY = os.environ.get('HIBP_API_KEY', '')

# Configuration WSL (pour les outils OSINT/Pentest)
WSL_DISTRO = os.environ.get('WSL_DISTRO', 'kali-linux')
WSL_USER = os.environ.get('WSL_USER', 'loupix')

# Configuration timeout pour les outils externes
OSINT_TOOL_TIMEOUT = int(os.environ.get('OSINT_TOOL_TIMEOUT', '60'))  # secondes

# Parse des numéros (lib phonenumbers) et cap analyse OSINT téléphone
PHONE_DEFAULT_REGION = os.environ.get('PHONE_DEFAULT_REGION', 'FR')
PHONE_OSINT_MAX_NUMBERS = int(os.environ.get('PHONE_OSINT_MAX_NUMBERS', '8'))
# PhoneInfoga v2 : scanners optionnels via variables documentées upstream (ex. NUMVERIFY_API_KEY).
PENTEST_TOOL_TIMEOUT = int(os.environ.get('PENTEST_TOOL_TIMEOUT', '120'))  # secondes

# Analyse SEO : timeouts séparés connexion / lecture (plusieurs URL candidates)
SEO_FETCH_CONNECT_TIMEOUT = float(os.environ.get('SEO_FETCH_CONNECT_TIMEOUT', '12'))
SEO_FETCH_READ_TIMEOUT = float(os.environ.get('SEO_FETCH_READ_TIMEOUT', '25'))
SEO_TOOL_TIMEOUT = int(os.environ.get('SEO_TOOL_TIMEOUT', '120'))
# Active Lighthouse par défaut via l'environnement (prod recommandé).
SEO_USE_LIGHTHOUSE_DEFAULT = os.environ.get('SEO_USE_LIGHTHOUSE_DEFAULT', 'false').lower() in ('1', 'true', 'yes', 'on')
# HTTP 429 / 503 : nouveaux essais avec attente (Retry-After ou backoff exponentiel)
SEO_FETCH_RATE_LIMIT_MAX_RETRIES = max(
    0, int(os.environ.get('SEO_FETCH_RATE_LIMIT_MAX_RETRIES', '5'))
)
SEO_FETCH_RATE_LIMIT_BASE_DELAY_SEC = float(
    os.environ.get('SEO_FETCH_RATE_LIMIT_BASE_DELAY_SEC', '4')
)
# Pack « analyse site complète » : pause après le scraping avant technique/SEO (réduit le rafale sur l’hôte)
FULL_ANALYSIS_INTER_STEP_PAUSE_SEC = float(
    os.environ.get('FULL_ANALYSIS_INTER_STEP_PAUSE_SEC', '3')
)
# Lighthouse (Node chrome-launcher) : sur Linux embarqué / Raspberry Pi, Chrome n’est pas dans le PATH standard
CHROME_PATH = (os.environ.get('CHROME_PATH') or os.environ.get('LIGHTHOUSE_CHROME_PATH') or '').strip() or None

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
# Étalement des sous-tâches lancées en masse (scraping multi-sites, etc.) : countdown = index * valeur
CELERY_BULK_STAGGER_SEC = float(os.environ.get('CELERY_BULK_STAGGER_SEC', '0.75'))
# Index Redis global (WebSocket) pris modulo cette valeur pour éviter un countdown énorme
# si la clé prospectlab:heavy:stagger:seq a été incrémentée des milliers de fois (sinon les
# tâches restent « planifiées » pendant des heures et le worker semble ne rien faire).
CELERY_BULK_STAGGER_SLOT_MODULO = max(1, int(os.environ.get('CELERY_BULK_STAGGER_SLOT_MODULO', '400')))
# 1 = le worker ne précharge qu'une tâche à la fois (meilleure répartition sous charge)
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.environ.get('CELERY_WORKER_PREFETCH_MULTIPLIER', '1'))
CELERY_TASK_ACKS_LATE = os.environ.get('CELERY_TASK_ACKS_LATE', 'true').lower() in ('1', 'true', 'yes')
# Files Celery à consommer.
# En dev, si CELERY_WORKER_QUEUES n'est pas fourni, on doit écouter aussi les queues dédiées
# (scraping/technical/seo/osint/pentest), sinon les tâches routées ne sont jamais exécutées.
CELERY_WORKER_QUEUES = os.environ.get(
    'CELERY_WORKER_QUEUES',
    'celery,scraping,scraping_interactive,technical,seo,osint,pentest,heavy,website_full',
)

# File d’enqueue pour le pack « analyse site complet ».
# Défaut « technical » : les workers existants écoutent déjà cette file (voir CELERY_WORKER_QUEUES).
# Pour isoler le pack sur un worker dédié : CELERY_FULL_ANALYSIS_QUEUE=website_full et ajoutez
# « website_full » à CELERY_WORKER_QUEUES sur ce nœud (sinon la tâche reste PENDING à l’infini).
CELERY_FULL_ANALYSIS_QUEUE = (
    (os.environ.get('CELERY_FULL_ANALYSIS_QUEUE') or 'technical').strip() or 'technical'
)

# Mise à l’échelle (cluster) : plusieurs workers → même CELERY_BROKER_URL vers Redis (ex. node15.lan).
# Pas de variable « nombre de workers » côté app : chaque nœud définit CELERY_WORKERS localement.
# Surveiller Redis (mémoire) et PostgreSQL max_connections — voir docs/configuration/DEPLOIEMENT_PRODUCTION.md.

# URL de base pour le tracking des emails (doit être accessible publiquement)
# Exemple: https://votre-domaine.com ou http://votre-ip:5000
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

# Scan automatique des bounces (IMAP -> tags/statuts)
BOUNCE_SCAN_ENABLED = os.environ.get('BOUNCE_SCAN_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on')
# Profils IMAP à scanner (doit correspondre à IMAP_PROFILES et variables IMAP_*_PROFIL)
BOUNCE_SCAN_PROFILES = (os.environ.get('BOUNCE_SCAN_PROFILES') or os.environ.get('IMAP_PROFILES') or 'default').strip()
# Fenêtre de scan périodique en jours (cron 2x/jour)
BOUNCE_SCAN_DAYS = max(1, int(os.environ.get('BOUNCE_SCAN_DAYS', '14')))
# Fenêtre de scan pour le run déclenché peu après lancement d'une campagne
BOUNCE_SCAN_AFTER_CAMPAIGN_DAYS = max(1, int(os.environ.get('BOUNCE_SCAN_AFTER_CAMPAIGN_DAYS', '2')))
# 0 = sans limite de messages IMAP, >0 = limite
BOUNCE_SCAN_LIMIT = int(os.environ.get('BOUNCE_SCAN_LIMIT', '0'))
# true = déplacer/supprimer les bounces traités côté IMAP (Gmail/node12)
BOUNCE_SCAN_DELETE_PROCESSED = os.environ.get('BOUNCE_SCAN_DELETE_PROCESSED', 'true').lower() in ('1', 'true', 'yes', 'on')
# Délai (secondes) après lancement campagne avant 1er scan auto
BOUNCE_SCAN_POST_CAMPAIGN_DELAY_SEC = max(30, int(os.environ.get('BOUNCE_SCAN_POST_CAMPAIGN_DELAY_SEC', '1800')))
