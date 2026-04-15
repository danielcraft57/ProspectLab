"""
Application Flask ProspectLab - Version refactorisée
Plateforme de prospection et analyse d'entreprises

Architecture modulaire avec :
- Blueprints Flask pour organiser les routes
- Celery pour les tâches asynchrones
- WebSockets pour les mises à jour en temps réel
"""

import os
import sys
from pathlib import Path

# Avant tout import réseau : si Socket.IO utilise Redis (message_queue) avec
# async_mode=eventlet, python-socketio exige des sockets monkey-patchés
# (socketio.redis_manager.RuntimeError sinon). Gunicorn -k eventlet le fait
# souvent avant le chargement de l'app ; en dev Flask / Windows, il faut patcher ici.
sys.path.insert(0, str(Path(__file__).parent))


def _apply_async_monkey_patch_for_socketio_redis():
    if os.environ.get('SOCKETIO_DISABLE_MESSAGE_QUEUE', '').strip().lower() in (
        '1',
        'true',
        'yes',
        'on',
    ):
        return
    am = (os.environ.get('SOCKETIO_ASYNC_MODE') or '').strip().lower()
    if am == 'threading':
        return
    if 'gevent' in am:
        try:
            from gevent import monkey

            monkey.patch_all()
        except ImportError:
            pass
        return
    try:
        import eventlet
        from eventlet.patcher import is_monkey_patched

        if not is_monkey_patched('socket'):
            eventlet.monkey_patch()
    except ImportError:
        pass


_apply_async_monkey_patch_for_socketio_redis()

from flask import Flask, request, render_template
from flask.json.provider import DefaultJSONProvider
from flask_socketio import SocketIO
import ipaddress
import logging
from logging.handlers import RotatingFileHandler
import math
import json

from config import (
    UPLOAD_FOLDER,
    EXPORT_FOLDER,
    MAX_CONTENT_LENGTH,
    SECRET_KEY,
    RESTRICT_TO_LOCAL_NETWORK,
    FLASK_DEBUG,
    SOCKETIO_MESSAGE_QUEUE,
)
from celery_app import make_celery

# Configuration des logs via le module centralisé
from services.logging_config import setup_root_logger
import logging

# JSON encoder personnalisé pour gérer les NaN et Infinity
class SafeJSONProvider(DefaultJSONProvider):
    """JSON provider qui convertit automatiquement NaN et Infinity en null"""
    def dumps(self, obj, **kwargs):
        """Nettoie les NaN avant la sérialisation JSON"""
        from utils.helpers import clean_json_dict
        cleaned_obj = clean_json_dict(obj)
        return super().dumps(cleaned_obj, **kwargs)
    
    def default(self, obj):
        """Gère les objets non sérialisables"""
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
        return super().default(obj)

# Créer l'application Flask
app = Flask(__name__)
app.json = SafeJSONProvider(app)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['EXPORT_FOLDER'] = str(EXPORT_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = SECRET_KEY
app.config['DEBUG'] = FLASK_DEBUG
app.config['TESTING'] = False

# Configurer les logs de l'application Flask (après création de l'app)
setup_root_logger(app)

# Initialiser Celery
celery = make_celery(app)

# Initialiser SocketIO
# IMPORTANT (prod) : avec Gunicorn « -k eventlet », ne pas forcer async_mode='threading'.
# La doc Flask-SocketIO indique que le mode threading n'est pas supporté quand eventlet/gevent
# monkey-patchent la stdlib — les événements Socket.IO (ex. start_seo_analysis) peuvent alors
# ne jamais exécuter le handler côté serveur (aucune tâche Celery enfilée, aucun log).
# - Par défaut : None → détection auto (eventlet si déjà patché par Gunicorn, sinon threading en dev).
# - Forcer si besoin : SOCKETIO_ASYNC_MODE=threading | eventlet | gevent
_socketio_async_mode = os.environ.get('SOCKETIO_ASYNC_MODE') or None
if _socketio_async_mode is not None:
    _socketio_async_mode = _socketio_async_mode.strip() or None

_socketio_message_queue = None
if os.environ.get('SOCKETIO_DISABLE_MESSAGE_QUEUE', '').strip().lower() not in (
    '1',
    'true',
    'yes',
    'on',
):
    _socketio_message_queue = SOCKETIO_MESSAGE_QUEUE

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode=_socketio_async_mode,
    logger=False,
    engineio_logger=False,
    # Robustesse : éviter les déconnexions intempestives quand le serveur est occupé
    # (bulk d'events + eventlet) ou derrière un proxy qui coupe vite les websockets.
    ping_timeout=60,
    ping_interval=25,
    allow_unsafe_werkzeug=True,
    # Permet aux workers Celery d'émettre (emit) vers les clients connectés.
    message_queue=_socketio_message_queue,
)

# Enregistrer les blueprints
from routes.main import main_bp
from routes.api import api_bp
from routes.api_extended import api_extended_bp
from routes.api_public import api_public_bp
from routes.api_tokens import api_tokens_bp
from routes.api_integration import api_integration_bp
from routes.upload import upload_bp
from routes.other import other_bp
from routes.auth import auth_bp

app.register_blueprint(auth_bp)  # Auth en premier pour gérer la redirection /
app.register_blueprint(main_bp)
app.register_blueprint(api_bp)
app.register_blueprint(api_extended_bp)
app.register_blueprint(api_public_bp)  # API publique
app.register_blueprint(api_tokens_bp)  # Gestion des tokens API
app.register_blueprint(api_integration_bp)  # API d'intégration interne (applications clientes)
app.register_blueprint(upload_bp)
app.register_blueprint(other_bp)

# Enregistrer les handlers WebSocket
from routes.websocket_handlers import register_websocket_handlers
register_websocket_handlers(socketio, app)

# Trace unique au boot worker : confirme async_mode (diagnostic Gunicorn + Socket.IO)
try:
    _am = getattr(socketio, 'async_mode', None) or 'inconnu'
except Exception:
    _am = 'erreur'
app.logger.info(
    'ProspectLab Socket.IO prêt (async_mode=%s, message_queue=%s)',
    _am,
    'oui' if _socketio_message_queue else 'non',
)

# CORS : autoriser les clients web locaux (Vite, Expo Web, etc.) à appeler l'API.
# Surchargable via CORS_ALLOWED_ORIGINS="https://foo,https://bar"
_cors_origins_env = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if _cors_origins_env.strip():
    ALLOWED_CORS_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()]
else:
    ALLOWED_CORS_ORIGINS = [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:8081',
        'http://127.0.0.1:8081',
        'http://localhost:19006',
        'http://127.0.0.1:19006',
    ]

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin')
    if origin and origin in ALLOWED_CORS_ORIGINS and request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, x-api-key'
        response.headers['Access-Control-Max-Age'] = '86400'
    return response

@app.route('/api/<path:path>', methods=['OPTIONS'])
def api_options(path):
    """Répond aux prérequêtes CORS OPTIONS pour les routes /api/*"""
    origin = request.headers.get('Origin')
    if origin and origin in ALLOWED_CORS_ORIGINS:
        from flask import make_response
        r = make_response('', 204)
        r.headers['Access-Control-Allow-Origin'] = origin
        r.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, x-api-key'
        r.headers['Access-Control-Max-Age'] = '86400'
        return r
    return '', 204


def _get_client_ip() -> str:
    """
    Détermine l'adresse IP "réelle" du client en tenant compte
    des proxys (X-Forwarded-For / X-Real-IP).

    Returns:
        str: Adresse IP du client (ou chaîne vide si inconnue)
    """
    raw = (
        request.headers.get('X-Forwarded-For')
        or request.headers.get('X-Real-IP')
        or (request.remote_addr if request.remote_addr else '')
    )
    if not raw:
        return ''
    return raw.split(',')[0].strip()


def _client_ip_allowed() -> bool:
    """
    Retourne True si la restriction réseau est désactivée
    ou si l'IP client appartient au réseau local (LAN / localhost).
    """
    try:
        if not RESTRICT_TO_LOCAL_NETWORK:
            return True

        ip_str = _get_client_ip()
        if not ip_str:
            return False

        ip = ipaddress.ip_address(ip_str)

        # Réseaux privés classiques + localhost
        allowed_networks = [
            ipaddress.ip_network('192.168.0.0/16'),
            ipaddress.ip_network('10.0.0.0/8'),
            ipaddress.ip_network('172.16.0.0/12'),
            ipaddress.ip_network('127.0.0.0/8'),
        ]

        return any(ip in net for net in allowed_networks)
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"Restriction IP: erreur de vérification ({e}), accès autorisé par sécurité"
        )
        # Fail-open pour ne pas bloquer l'app en cas de bug
        return True


@app.before_request
def restrict_to_local_network():
    """
    Bloque l'accès HTTP si l'IP n'est pas dans le réseau local
    quand RESTRICT_TO_LOCAL_NETWORK est activé.

    Routes qui restent publiques :
    - /track/... : tracking emails (appelé par les destinataires externes)
    - /api/public/... : API publique protégée par token
    """
    path = request.path or ''
    # Pour les endpoints API non-publics, on privilégie un comportement "fail-closed"
    # (si la logique de restriction rencontre une erreur, on bloque au lieu d'autoriser).
    is_private_api = path.startswith('/api/') and not path.startswith('/api/public')

    try:
        # Tracking et API publique restent accessibles depuis l'extérieur
        if path.startswith('/track/'):
            return None
        if path.startswith('/api/public'):
            return None
        # Socket.IO doit rester accessible, sinon handshake WS/polling échoue
        # et le navigateur affiche "WebSocket is closed before the connection is established."
        if path.startswith('/socket.io'):
            return None

        if _client_ip_allowed():
            return None

        # Page de restriction simple
        try:
            client_ip = _get_client_ip()
            return render_template('restricted.html', client_ip=client_ip), 403
        except Exception:
            # Si le template n'existe pas encore, renvoyer un message texte
            return "Accès restreint au réseau local", 403
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Restriction IP: erreur dans before_request ({e}), accès autorisé par sécurité"
        )
        # Fail-closed pour l'API privée (ex: /api/website-analysis)
        if is_private_api:
            try:
                client_ip = _get_client_ip()
                return render_template('restricted.html', client_ip=client_ip), 403
            except Exception:
                return "Accès restreint au réseau local", 403
        # Fail-open pour le reste de l'app (évite un lock total)
        return None

# Note: Certaines routes ne sont pas encore migrées vers les blueprints.
# Pour utiliser toutes les fonctionnalités, utilisez app.py qui contient toutes les routes.
# Routes non migrées (à migrer progressivement) :
# - /send-emails, /templates, /scrape-emails, /scrapers, /analyse/scraping
# - /download/<filename>
# - Routes API restantes (analyses-techniques, analyses-osint, analyses-pentest, etc.)

# Importer les tâches Celery pour qu'elles soient enregistrées
from tasks import analysis_tasks, scraping_tasks, technical_analysis_tasks

if __name__ == '__main__':
    """
    Point d'entrée principal de l'application
    
    Pour démarrer l'application (Socket.IO inclus — recommandé en dev) :
        python app.py
    
    Éviter ``flask run`` pour le temps réel : sans ``socketio.run``, les WebSockets
    / reconnexions Socket.IO peuvent échouer.
        
    Pour démarrer Celery (dans un terminal séparé) :
        celery -A celery_app worker --loglevel=info --pool=threads --concurrency=4
    """
    import signal
    import sys
    import os
    import threading
    
    # Variable globale pour contrôler l'arrêt
    shutdown_event = threading.Event()
    
    def signal_handler(sig, frame):
        """Gère Ctrl+C proprement"""
        print('\n\n[!] Arrêt de l\'application...')
        shutdown_event.set()
        # Arrêt forcé immédiat sur Windows
        os._exit(0)
    
    def run_socketio():
        """Lance SocketIO dans un thread séparé"""
        try:
            socketio.run(
                app,
                debug=bool(app.config.get('DEBUG')),
                host=os.environ.get('FLASK_RUN_HOST', '0.0.0.0'),
                port=int(os.environ.get('FLASK_RUN_PORT', '5000')),
                # Reloader désactivé (stable sous Windows + thread SocketIO) ; activer via FLASK_USE_RELOADER=1 si besoin.
                use_reloader=bool(app.config.get('DEBUG'))
                and os.environ.get('FLASK_USE_RELOADER', '0').lower() in ('1', 'true', 'yes', 'on'),
                allow_unsafe_werkzeug=True,
            )
        except Exception as e:
            print(f'Erreur SocketIO: {e}')
    
    # Enregistrer le gestionnaire de signal AVANT de lancer SocketIO
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform == 'win32':
        signal.signal(signal.SIGTERM, signal_handler)
    
    _port = int(os.environ.get('FLASK_RUN_PORT', '5000'))
    _host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    _mode = 'DEBUG' if app.config.get('DEBUG') else 'production (pas de débogueur)'
    print(f"Démarrage Flask mode {_mode} sur http://{_host}:{_port}")
    print('Appuyez sur Ctrl+C pour arrêter l\'application\n')
    
    # Lancer SocketIO dans un thread séparé (non-daemon pour qu'il reste actif)
    socketio_thread = threading.Thread(target=run_socketio, daemon=False)
    socketio_thread.start()
    
    # Attendre que le thread démarre
    import time
    time.sleep(0.5)
    
    # Surveiller l'arrêt dans le thread principal
    try:
        # Sur Windows, surveiller l'entrée standard dans le thread principal
        if sys.platform == 'win32':
            try:
                import msvcrt
                while socketio_thread.is_alive() and not shutdown_event.is_set():
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\x03':  # Ctrl+C
                            print('\n\n[!] Ctrl+C détecté - Arrêt de l\'application...')
                            os._exit(0)
                    time.sleep(0.1)
            except ImportError:
                # msvcrt non disponible, attendre simplement
                socketio_thread.join()
        else:
            # Sur Linux/Mac, attendre normalement
            socketio_thread.join()
    except KeyboardInterrupt:
        print('\n\n[!] Arrêt de l\'application...')
        os._exit(0)

