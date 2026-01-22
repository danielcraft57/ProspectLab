"""
Application Flask ProspectLab - Version refactorisée
Plateforme de prospection et analyse d'entreprises

Architecture modulaire avec :
- Blueprints Flask pour organiser les routes
- Celery pour les tâches asynchrones
- WebSockets pour les mises à jour en temps réel
"""

from flask import Flask
from flask_socketio import SocketIO
import os
import sys
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

# Ajouter le répertoire au path
sys.path.insert(0, str(Path(__file__).parent))

from config import UPLOAD_FOLDER, EXPORT_FOLDER, MAX_CONTENT_LENGTH, SECRET_KEY
from celery_app import make_celery

# Configuration des logs via le module centralisé
from services.logging_config import setup_root_logger
import logging

# Créer l'application Flask
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['EXPORT_FOLDER'] = str(EXPORT_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = SECRET_KEY

# Configurer les logs de l'application Flask (après création de l'app)
setup_root_logger(app)

# Initialiser Celery
celery = make_celery(app)

# Initialiser SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False,
    allow_unsafe_werkzeug=True
)

# Enregistrer les blueprints
from routes.main import main_bp
from routes.api import api_bp
from routes.api_extended import api_extended_bp
from routes.upload import upload_bp
from routes.other import other_bp
from routes.auth import auth_bp

app.register_blueprint(auth_bp)  # Auth en premier pour gérer la redirection /
app.register_blueprint(main_bp)
app.register_blueprint(api_bp)
app.register_blueprint(api_extended_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(other_bp)

# Enregistrer les handlers WebSocket
from routes.websocket_handlers import register_websocket_handlers
register_websocket_handlers(socketio, app)

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
    
    Pour démarrer l'application :
        python app_new.py
        
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
                debug=True, 
                host='0.0.0.0', 
                port=5000, 
                use_reloader=False, 
                allow_unsafe_werkzeug=True
            )
        except Exception as e:
            print(f'Erreur SocketIO: {e}')
    
    # Enregistrer le gestionnaire de signal AVANT de lancer SocketIO
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform == 'win32':
        signal.signal(signal.SIGTERM, signal_handler)
    
    print('Démarrage de l\'application Flask sur http://0.0.0.0:5000')
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

