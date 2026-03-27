"""
Handlers WebSocket pour ProspectLab

Gère toutes les communications WebSocket en temps réel pour les analyses,
scraping et autres opérations longues.
"""

from flask import request
from flask_socketio import emit
from utils.helpers import safe_emit
from celery_app import celery
from tasks.analysis_tasks import analyze_entreprise_task
from tasks.scraping_tasks import scrape_emails_task, scrape_analysis_task
from tasks.technical_analysis_tasks import technical_analysis_task
from tasks.pentest_tasks import pentest_analysis_task
from tasks.osint_tasks import osint_analysis_task
from tasks.seo_tasks import seo_analysis_task
from tasks.heavy_schedule import next_websocket_stagger_countdown
from utils.celery_health import broker_ping_ok
from utils.cluster_files import cluster_copy_upload_to_workers, is_windows_path
import os
import threading
import logging
import time
from services.database import Database

# Logger pour ce module
logger = logging.getLogger(__name__)

# Intervalle entre deux polls AsyncResult côté WebSocket (réduit la charge Redis ; défaut 1s)
_WS_MONITOR_POLL_SEC = max(0.3, float(os.environ.get('CELERY_WS_MONITOR_POLL_SEC', '1.0')))

_CELERY_BROKER_UNREACHABLE_MSG = (
    'Redis / broker Celery injoignable. Vérifie que Redis tourne, puis le worker avec la file « heavy » : '
    'celery -A celery_app worker -Q celery,heavy --loglevel=info '
    '(Windows : .\\scripts\\windows\\start-celery.ps1).'
)

# Initialiser les services
database = Database()

# Dictionnaires pour stocker les tâches actives
active_tasks = {}
tasks_lock = threading.Lock()


def _celery_progress_meta_as_dict(info):
    """
    Normalise task_result.info pour l'état PROGRESS.
    Selon le backend Celery / timing, `info` peut être le dict `meta` ou une Exception.
    """
    if isinstance(info, dict):
        return info
    if info is None:
        return {}
    return {'progress': 0, 'message': str(info)}


def _celery_success_result_as_dict(result):
    """Retourne le résultat SUCCESS si c'est un dict, sinon None (exception ou type inattendu)."""
    if isinstance(result, dict):
        return result
    return None


def _sleep_before_monitor_poll(countdown_sec: int) -> None:
    """Évite de poller AsyncResult en boucle pendant le countdown Celery (charge Redis / CPU)."""
    if countdown_sec and countdown_sec > 0:
        time.sleep(min(float(countdown_sec), 120.0))


def _start_monitor_background(socketio, target):
    """
    Lance le suivi Celery (poll + emit) sans threading.Thread.

    Sous Gunicorn -k eventlet, un thread OS séparé ne peut pas émettre vers le client Socket.IO
    de façon fiable : pas de seo_analysis_progress / *_complete. start_background_task utilise
    le même modèle async que le serveur (eventlet.spawn, etc.).
    """
    if socketio is None or target is None:
        return
    try:
        sb = getattr(socketio, 'start_background_task', None)
        if callable(sb):
            sb(target)
            return
    except Exception:
        logger.debug('start_background_task indisponible, fallback thread', exc_info=True)
    t = threading.Thread(target=target, daemon=True)
    t.start()


def register_websocket_handlers(socketio, app):
    """
    Enregistre tous les handlers WebSocket
    
    Args:
        socketio: Instance de SocketIO
        app: Instance de l'application Flask
    """

    @socketio.on('connect')
    def handle_socket_connect():
        """Voir prospectlab.log (niveau DEBUG) ou activer logging DEBUG pour tracer les connexions."""
        try:
            app.logger.debug('[Socket.IO] connect sid=%s', request.sid)
        except Exception:
            pass

    @socketio.on('disconnect')
    def handle_socket_disconnect():
        try:
            app.logger.debug('[Socket.IO] disconnect sid=%s', request.sid)
        except Exception:
            pass
    
    @socketio.on('start_analysis')
    def handle_start_analysis(data):
        """
        Démarre une analyse d'entreprises via Celery
        
        Args:
            data (dict): Paramètres de l'analyse (filename, max_workers, delay, enable_osint)
        """
        try:
            filename = data.get('filename')
            # Valeurs optimisées pour Celery avec --pool=threads --concurrency dynamique
            # Celery gère déjà la concurrence, pas besoin de délai artificiel élevé
            from config import CELERY_WORKERS
            max_workers = int(data.get('max_workers', CELERY_WORKERS))  # Utilise la valeur depuis la config
            delay = float(data.get('delay', 0.1))         # Délai minimal, Celery gère la concurrence
            enable_osint = data.get('enable_osint', False)
            session_id = request.sid
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            # Sur certains déploiements (volume réseau / IO lente / multi-instances),
            # le fichier peut ne pas être visible immédiatement. Attente courte + retry.
            timeout_s = float(os.environ.get('UPLOAD_VISIBILITY_TIMEOUT_S', '3.0'))
            interval_s = float(os.environ.get('UPLOAD_VISIBILITY_INTERVAL_S', '0.2'))
            deadline = time.time() + max(0.0, timeout_s)
            while time.time() < deadline:
                try:
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        break
                except OSError:
                    pass
                time.sleep(interval_s)
            if not os.path.exists(filepath):
                safe_emit(
                    socketio,
                    'analysis_error',
                    {'error': f'Fichier introuvable: {filepath}'},
                    room=session_id
                )
                return

            # Mode cluster (app Windows -> workers Linux): copier le fichier sur les noeuds avant d'enfiler la tâche
            # Sinon les workers reçoivent un chemin C:\... et échouent "fichier introuvable".
            try:
                if is_windows_path(filepath) and (os.environ.get('CLUSTER_WORKER_NODES') or '').strip():
                    safe_emit(socketio, 'analysis_progress', {
                        'current': 0,
                        'total': 0,
                        'percentage': 0,
                        'message': 'Copie du fichier vers le cluster...'
                    }, room=session_id)
                    filepath = cluster_copy_upload_to_workers(filepath, remote_filename=filename)
            except Exception as e:
                safe_emit(socketio, 'analysis_error', {
                    'error': f'Erreur copie fichier vers cluster: {str(e)}'
                }, room=session_id)
                return
            
            # Créer le fichier de sortie
            output_filename = f"analyzed_{filename}"
            output_path = os.path.join(app.config['EXPORT_FOLDER'], output_filename)
            
            # Vérifier que Celery/Redis est disponible (test léger, sans bloquer si un worker répond lentement)
            try:
                from celery_app import celery
                inspector = celery.control.inspect()
                # ping() retourne un dict ou None. Si None, on loggue seulement.
                ping_result = inspector.ping()
                if not ping_result:
                    logger.warning('Inspecteur Celery ne retourne aucun worker (ping vide), mais on tente quand même de lancer la tâche.')
            except Exception as e:
                # Si on ne peut même pas contacter le broker, là on bloque vraiment.
                error_msg = 'Celery/Redis indisponible. '
                error_msg += 'Vérifiez que le broker et le worker Celery sont démarrés '
                error_msg += '(ex: .\\scripts\\windows\\start-celery.ps1 ou celery -A celery_app worker --loglevel=info).'
                safe_emit(socketio, 'analysis_error', {
                    'error': error_msg
                }, room=session_id)
                logger.warning(f'Start_analysis refusé (erreur connexion broker): {e}')
                return
            
            # Lancer la tâche Celery
            try:
                task = analyze_entreprise_task.apply_async(
                    kwargs=dict(
                        filepath=filepath,
                        output_path=output_path,
                        max_workers=max_workers,
                        delay=delay,
                        enable_osint=enable_osint,
                    ),
                    queue='technical',
                )
            except Exception as e:
                safe_emit(socketio, 'analysis_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return
        
            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'analysis'}
            
            safe_emit(socketio, 'analysis_started', {'message': 'Analyse démarrée...', 'task_id': task.id}, room=session_id)
        
            # Surveiller la progression de la tâche dans un thread séparé
            scraping_launched = False  # Marqueur pour éviter de relancer le scraping plusieurs fois
            
            def monitor_task():
                nonlocal scraping_launched
                try:
                    last_state = None
                    last_meta = None
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            current_state = task_result.state
                            
                            # Vérifier si l'état a changé ou si c'est PROGRESS avec nouvelles infos
                            if current_state == 'PROGRESS':
                                meta = _celery_progress_meta_as_dict(task_result.info)
                                # Émettre seulement si les métadonnées ont changé
                                if meta != last_meta:
                                    progress_data = {
                                        'current': meta.get('current', 0),
                                        'total': meta.get('total', 0),
                                        'percentage': meta.get('percentage', 0),
                                        'message': meta.get('message', '')
                                    }
                                    safe_emit(socketio, 'analysis_progress', progress_data, room=session_id)

                                    # Si le Celery meta contient des infos de scraping, les propager aussi
                                    scraping_message = meta.get('scraping_message')
                                    if scraping_message:
                                        safe_emit(socketio, 'scraping_progress', {
                                            'message': scraping_message,
                                            'url': meta.get('scraping_url'),
                                            'entreprise': meta.get('scraping_entreprise')
                                        }, room=session_id)

                                    last_meta = meta
                            elif current_state == 'PENDING' and last_state != 'PENDING':
                                # Tâche en attente - envoyer un message initial
                                safe_emit(socketio, 'analysis_progress', {
                                    'current': 0,
                                    'total': 0,
                                    'percentage': 0,
                                    'message': 'Tâche en attente...'
                                }, room=session_id)
                            elif current_state == 'SUCCESS':
                                # Ne traiter SUCCESS qu'une seule fois
                                if scraping_launched:
                                    # Le scraping a déjà été lancé, arrêter le monitoring
                                    break
                                
                                result = _celery_success_result_as_dict(task_result.result)
                                total_processed = result.get('total_processed', 0) if result else 0
                                stats = result.get('stats', {}) if result else {}
                                inserted = stats.get('inserted')
                                effective_total = inserted if isinstance(inserted, int) else total_processed
                                analysis_id = result.get('analysis_id') if result else None
                                
                                logger.info(f'Analyse terminée: total_processed={total_processed}, inserted={inserted}, analysis_id={analysis_id}')
                                logger.info(f'Résultat complet de la tâche: {result}')
                                
                                safe_emit(
                                    socketio,
                                    'analysis_complete',
                                    {
                                    'success': True,
                                    'output_file': result.get('output_file') if result else None,
                                    'total_processed': effective_total,
                                    'total': effective_total,  # Pour compatibilité avec l'ancien code
                                    'stats': stats,
                                    'message': f'Analyse terminée avec succès ! {effective_total} nouvelles entreprises analysées.'
                                    },
                                    room=session_id
                                )

                                # Lancer automatiquement le scraping de toutes les entreprises de cette analyse
                                # Vérifier qu'une tâche de scraping n'est pas déjà en cours pour cette analyse
                                logger.info(f'Vérification du lancement du scraping: analysis_id={analysis_id}, scraping_launched={scraping_launched}')
                                if not analysis_id:
                                    logger.warning(f'analysis_id est None ou vide, impossible de lancer le scraping automatiquement')
                                elif analysis_id and effective_total > 0:
                                    logger.info(f'Lancement automatique du scraping pour analysis_id={analysis_id}')
                                    try:
                                        # Vérifier si une tâche de scraping est déjà en cours pour cette analyse
                                        scraping_already_started = False
                                        with tasks_lock:
                                            for sid, task_info in list(active_tasks.items()):
                                                if (task_info.get('type') == 'analysis_scraping' and 
                                                    task_info.get('analysis_id') == analysis_id):
                                                    scraping_already_started = True
                                                    break
                                        
                                        if scraping_already_started:
                                            logger.info(f'Scraping déjà en cours pour l\'analyse {analysis_id}, ignoré')
                                            scraping_launched = True
                                        else:
                                            logger.info(f'Lancement de la tâche de scraping pour analysis_id={analysis_id}')
                                            try:
                                                scraping_task = scrape_analysis_task.apply_async(
                                                    kwargs=dict(analysis_id=analysis_id),
                                                    queue='scraping',
                                                )
                                                logger.info(f'Tâche de scraping lancée avec task_id={scraping_task.id}')
                                                scraping_launched = True
                                            except Exception as scrape_error:
                                                logger.error(
                                                    f'Erreur lors du lancement du scraping: {scrape_error}',
                                                    exc_info=True
                                                )
                                                raise
                                        
                                            with tasks_lock:
                                                active_tasks[session_id] = {
                                                    'task_id': scraping_task.id,
                                                    'type': 'analysis_scraping',
                                                    'analysis_id': analysis_id
                                                }
    
                                            # Récupérer le total d'entreprises (avec site) pour l'UI OSINT/Pentest
                                            db = Database()
                                            conn = db.get_connection()
                                            cursor = conn.cursor()
                                            db.execute_sql(cursor,
                                                '''
                                                SELECT COUNT(*) as count FROM entreprises
                                                WHERE analyse_id = ?
                                                  AND website IS NOT NULL
                                                  AND TRIM(website) <> ''
                                                ''',
                                                (analysis_id,)
                                            )
                                            result = cursor.fetchone()
                                            total_entreprises_avec_site = result['count'] if isinstance(result, dict) else result[0] if result else 0
                                            conn.close()
    
                                            safe_emit(
                                                socketio,
                                                'scraping_started',
                                                {
                                                    'message': 'Scraping des entreprises en cours...',
                                                    'task_id': scraping_task.id,
                                                    'analysis_id': analysis_id,
                                                    'total': total_entreprises_avec_site
                                                },
                                                room=session_id
                                            )
    
                                            # L'analyse technique est maintenant lancée en parallèle dans la tâche de scraping
                                            logger.debug(f'Analyse technique lancée en parallèle du scraping')
                                            
                                            if total_entreprises_avec_site > 0:
                                                safe_emit(
                                                    socketio,
                                                    'technical_analysis_started',
                                                    {
                                                        'message': f'Analyse technique démarrée pour {total_entreprises_avec_site} entreprises...',
                                                        'total': total_entreprises_avec_site,
                                                        'current': 0,
                                                        'immediate_100': False
                                                    },
                                                    room=session_id
                                                )
                                                logger.debug(f'Événement technical_analysis_started émis pour {total_entreprises_avec_site} entreprises')
                                            
                                            tech_tasks_to_monitor = []  # Sera rempli dès qu'on reçoit les IDs dans le meta
                                            tech_tasks_monitoring_started = False  # Flag pour démarrer le monitoring une seule fois
                                            
                                            # Capturer analysis_id dans une variable locale pour la fonction monitor_scraping
                                            analysis_id_for_monitoring = analysis_id
    
                                            # Surveiller la tâche de scraping
                                            def monitor_scraping():
                                                nonlocal tech_tasks_to_monitor, tech_tasks_monitoring_started
                                                analysis_id_local = analysis_id_for_monitoring  # Utiliser la variable capturée
                                                try:
                                                    # Flag partagé: sert à éviter que certains monitorings (OSINT/Pentest)
                                                    # s'arrêtent trop tôt alors que le scraping continue encore et
                                                    # peut ajouter de nouvelles tâches à surveiller.
                                                    monitor_scraping.scraping_done = False
                                                    last_meta_scraping = None
                                                    while True:
                                                        try:
                                                            scraping_result = celery.AsyncResult(scraping_task.id)
                                                            if scraping_result.state == 'PROGRESS':
                                                                meta_scraping = _celery_progress_meta_as_dict(scraping_result.info)
                                                                if meta_scraping != last_meta_scraping:
                                                                    # Mettre à jour analysis_id depuis le meta si disponible
                                                                    if 'analysis_id' in meta_scraping:
                                                                        analysis_id_local = meta_scraping['analysis_id']
                                                                    safe_emit(
                                                                        socketio,
                                                                        'scraping_progress',
                                                                        {
                                                                            'message': meta_scraping.get('message', ''),
                                                                            'entreprise': meta_scraping.get('entreprise'),
                                                                            'url': meta_scraping.get('url'),
                                                                            'current': meta_scraping.get('current', 0),
                                                                            'total': meta_scraping.get('total', 0),
                                                                            'total_emails': meta_scraping.get('total_emails', 0),
                                                                            'total_people': meta_scraping.get('total_people', 0),
                                                                            'total_phones': meta_scraping.get('total_phones', 0),
                                                                            'total_social_platforms': meta_scraping.get('total_social_platforms', 0),
                                                                            'total_technologies': meta_scraping.get('total_technologies', 0),
                                                                            'total_images': meta_scraping.get('total_images', 0),
                                                                        },
                                                                        room=session_id
                                                                    )
    
                                                                    # Récupérer les IDs des tâches techniques depuis le meta
                                                                    tech_tasks_ids = meta_scraping.get('tech_tasks_launched_ids', [])
                                                                    if tech_tasks_ids and not tech_tasks_monitoring_started:
                                                                        tech_tasks_to_monitor = tech_tasks_ids
                                                                        tech_tasks_monitoring_started = True
                                                                        logger.debug(f'Monitoring de {len(tech_tasks_to_monitor)} analyses techniques démarré')
                                                                    
                                                                        # Démarrer le monitoring des analyses techniques en temps réel
                                                                        def monitor_tech_tasks_realtime():
                                                                            tech_completed = 0
                                                                            total_tech = len(tech_tasks_to_monitor)
                                                                            tech_tasks_status = {t['task_id']: {'completed': False, 'last_progress': None, 'current_progress': 0} for t in tech_tasks_to_monitor}
                                                                            analysis_id_for_tech = analysis_id_local  # Utiliser la variable capturée
                                                                            
                                                                            while tech_completed < total_tech:
                                                                                total_progress_sum = 0
                                                                                for tech_info in tech_tasks_to_monitor:
                                                                                    task_id = tech_info['task_id']
                                                                                    if tech_tasks_status[task_id]['completed']:
                                                                                        total_progress_sum += 100  # Tâche terminée = 100%
                                                                                        continue
                                                                                    
                                                                                    try:
                                                                                        tech_result = celery.AsyncResult(task_id)
                                                                                        current_state = tech_result.state
                                                                                        
                                                                                        if current_state == 'PROGRESS':
                                                                                            # Mettre à jour la progression en temps réel
                                                                                            meta_tech = _celery_progress_meta_as_dict(tech_result.info)
                                                                                            progress_tech = meta_tech.get('progress', 0)
                                                                                            message_tech = meta_tech.get('message', '')
                                                                                            
                                                                                            # Mettre à jour la progression de cette tâche
                                                                                            tech_tasks_status[task_id]['current_progress'] = progress_tech
                                                                                            total_progress_sum += progress_tech
                                                                                            
                                                                                            # Émettre seulement si la progression a changé
                                                                                            if tech_tasks_status[task_id]['last_progress'] != progress_tech:
                                                                                                # Calculer la progression globale moyenne
                                                                                                global_progress = int((total_progress_sum / total_tech) if total_tech > 0 else 0)
                                                                                                
                                                                                                safe_emit(
                                                                                                    socketio,
                                                                                                    'technical_analysis_progress',
                                                                                                    {
                                                                                                        'current': tech_completed,
                                                                                                        'total': total_tech,
                                                                                                        'progress': global_progress,
                                                                                                        'message': f'{message_tech} - {tech_info.get("nom", "N/A")}',
                                                                                                        'url': tech_info.get('url', ''),
                                                                                                        'entreprise': tech_info.get('nom', 'N/A'),
                                                                                                        'task_progress': progress_tech
                                                                                                    },
                                                                                                    room=session_id
                                                                                                )
                                                                                                tech_tasks_status[task_id]['last_progress'] = progress_tech
                                                                                        elif current_state == 'PENDING':
                                                                                            # Tâche en attente, progression à 0
                                                                                            total_progress_sum += 0
                                                                                        
                                                                                        elif current_state == 'SUCCESS':
                                                                                            if not tech_tasks_status[task_id]['completed']:
                                                                                                tech_tasks_status[task_id]['completed'] = True
                                                                                                tech_completed += 1
                                                                                                total_progress_sum += 100
                                                                                                
                                                                                                # Calculer la progression globale moyenne
                                                                                                global_progress = int((total_progress_sum / total_tech) if total_tech > 0 else 0)
                                                                                                
                                                                                                safe_emit(
                                                                                                    socketio,
                                                                                                    'technical_analysis_progress',
                                                                                                    {
                                                                                                        'current': tech_completed,
                                                                                                        'total': total_tech,
                                                                                                        'progress': global_progress,
                                                                                                        'message': f'Analyse technique terminée pour {tech_info.get("nom", "N/A")}',
                                                                                                        'url': tech_info.get('url', ''),
                                                                                                        'entreprise': tech_info.get('nom', 'N/A')
                                                                                                    },
                                                                                                    room=session_id
                                                                                                )
                                                                                            else:
                                                                                                total_progress_sum += 100
                                                                                        
                                                                                        elif current_state == 'FAILURE':
                                                                                            if not tech_tasks_status[task_id]['completed']:
                                                                                                tech_tasks_status[task_id]['completed'] = True
                                                                                                tech_completed += 1
                                                                                                total_progress_sum += 100
                                                                                                
                                                                                                # Calculer la progression globale moyenne
                                                                                                global_progress = int((total_progress_sum / total_tech) if total_tech > 0 else 0)
                                                                                                
                                                                                                safe_emit(
                                                                                                    socketio,
                                                                                                    'technical_analysis_progress',
                                                                                                    {
                                                                                                        'current': tech_completed,
                                                                                                        'total': total_tech,
                                                                                                        'progress': global_progress,
                                                                                                        'message': f'Erreur lors de l\'analyse technique pour {tech_info.get("nom", "N/A")}',
                                                                                                        'url': tech_info.get('url', ''),
                                                                                                        'entreprise': tech_info.get('nom', 'N/A')
                                                                                                    },
                                                                                                    room=session_id
                                                                                                )
                                                                                            else:
                                                                                                total_progress_sum += 100
                                                                                    
                                                                                    except Exception as e:
                                                                                        logger.warning(f'Erreur monitoring tâche technique {task_id}: {e}')
                                                                                
                                                                                time.sleep(0.5)
                                                                            
                                                                            # Toutes les analyses techniques sont terminées
                                                                            safe_emit(
                                                                                socketio,
                                                                                'technical_analysis_complete',
                                                                                {
                                                                                    'message': f'Analyses techniques terminées pour {tech_completed}/{total_tech} entreprises.',
                                                                                    'analysis_id': analysis_id_for_tech,
                                                                                    'current': tech_completed,
                                                                                    'total': total_tech
                                                                                },
                                                                                room=session_id
                                                                            )
                                                                        
                                                                        _start_monitor_background(socketio, monitor_tech_tasks_realtime)
                                                                    
                                                                    # Récupérer les IDs des tâches OSINT depuis le meta
                                                                    # (une tâche OSINT par site scrapé ; la liste grossit à chaque update_progress)
                                                                    osint_tasks_ids = meta_scraping.get('osint_tasks_launched_ids', [])
                                                                    if osint_tasks_ids:
                                                                        # Nombre d'entreprises attendu (pour redirection à 100 %)
                                                                        expected_total_osint = meta_scraping.get('total') or len(monitor_scraping.osint_tasks_to_monitor)
                                                                        if not hasattr(monitor_scraping, 'osint_tasks_to_monitor'):
                                                                            monitor_scraping.osint_tasks_to_monitor = []
                                                                            monitor_scraping.osint_monitoring_started = False
                                                                        
                                                                        # Ajouter les nouvelles tâches OSINT qui ne sont pas déjà dans la liste
                                                                        existing_task_ids = {t['task_id'] for t in monitor_scraping.osint_tasks_to_monitor}
                                                                        new_tasks = [t for t in osint_tasks_ids if t['task_id'] not in existing_task_ids]
                                                                        
                                                                        if new_tasks:
                                                                            monitor_scraping.osint_tasks_to_monitor.extend(new_tasks)
                                                                            logger.debug(f'{len(new_tasks)} nouvelle(s) tâche(s) OSINT détectée(s), total: {len(monitor_scraping.osint_tasks_to_monitor)}')
                                                                            
                                                                            # Si le monitoring OSINT est déjà démarré, mettre à jour le compteur X/Y
                                                                            if getattr(monitor_scraping, 'osint_monitoring_started', False):
                                                                                safe_emit(
                                                                                    socketio,
                                                                                    'osint_analysis_started',
                                                                                    {
                                                                                        'message': f'Analyse OSINT démarrée pour {len(monitor_scraping.osint_tasks_to_monitor)} entreprises...',
                                                                                        'total': len(monitor_scraping.osint_tasks_to_monitor),
                                                                                        'expected_total': expected_total_osint,
                                                                                        'current': 0
                                                                                    },
                                                                                    room=session_id
                                                                                )
                                                                        
                                                                        # Démarrer le monitoring si ce n'est pas déjà fait
                                                                        if not monitor_scraping.osint_monitoring_started and len(monitor_scraping.osint_tasks_to_monitor) > 0:
                                                                            osint_tasks_to_monitor = monitor_scraping.osint_tasks_to_monitor
                                                                            monitor_scraping.osint_monitoring_started = True
                                                                            logger.debug(f'Monitoring de {len(osint_tasks_to_monitor)} analyses OSINT démarré')
                                                                            
                                                                            # Émettre l'événement de démarrage OSINT initial
                                                                            safe_emit(
                                                                                socketio,
                                                                                'osint_analysis_started',
                                                                                {
                                                                                    'message': f'Analyse OSINT démarrée pour {len(osint_tasks_to_monitor)} entreprises...',
                                                                                    'total': len(osint_tasks_to_monitor),
                                                                                    'expected_total': expected_total_osint,
                                                                                    'current': 0
                                                                                },
                                                                                room=session_id
                                                                            )
                                                                        
                                                                        # Démarrer le monitoring des analyses OSINT en temps réel
                                                                        def monitor_osint_tasks_realtime():
                                                                            osint_completed = 0
                                                                            osint_tasks_status = {}  # Dictionnaire dynamique pour suivre les tâches
                                                                            osint_cumulative_totals = {  # Totaux cumulés OSINT
                                                                                'subdomains': 0,
                                                                                'emails': 0,
                                                                                'people': 0,
                                                                                'dns_records': 0,
                                                                                'ssl_analyses': 0,
                                                                                'waf_detections': 0,
                                                                                'directories': 0,
                                                                                'open_ports': 0,
                                                                                'services': 0
                                                                            }
                                                                            
                                                                            while True:
                                                                                # Utiliser la liste dynamique qui se met à jour
                                                                                current_osint_tasks = monitor_scraping.osint_tasks_to_monitor
                                                                                total_osint = len(current_osint_tasks)
                                                                                
                                                                                # Initialiser les nouvelles tâches dans le statut
                                                                                for osint_info in current_osint_tasks:
                                                                                    task_id = osint_info['task_id']
                                                                                    if task_id not in osint_tasks_status:
                                                                                        osint_tasks_status[task_id] = {'completed': False, 'last_progress': None, 'current_progress': 0, 'info': osint_info}
                                                                                
                                                                                # Si toutes les tâches sont terminées et qu'il n'y a plus de nouvelles tâches, sortir
                                                                                if osint_completed >= total_osint and total_osint > 0:
                                                                                    # Vérifier s'il y a de nouvelles tâches en attente
                                                                                    pending_tasks = [t for t in current_osint_tasks if not osint_tasks_status.get(t['task_id'], {}).get('completed', False)]
                                                                                    if len(pending_tasks) == 0:
                                                                                        # Ne sortir définitivement que lorsque le scraping est terminé,
                                                                                        # sinon on risque de manquer des tâches OSINT ajoutées plus tard
                                                                                        if getattr(monitor_scraping, 'scraping_done', False):
                                                                                            break
                                                                                        # Scraping toujours en cours : attendre et continuer à surveiller
                                                                                        time.sleep(0.5)
                                                                                        continue
                                                                                
                                                                                # Parcourir toutes les tâches pour mettre à jour leur état
                                                                                for osint_info in current_osint_tasks:
                                                                                    task_id = osint_info['task_id']
                                                                                    # Vérifier que la tâche est initialisée dans le statut
                                                                                    if task_id not in osint_tasks_status:
                                                                                        osint_tasks_status[task_id] = {'completed': False, 'last_progress': None, 'current_progress': 0, 'info': osint_info}
                                                                                    
                                                                                    if osint_tasks_status[task_id]['completed']:
                                                                                        continue
                                                                                    
                                                                                    try:
                                                                                        osint_result = celery.AsyncResult(task_id)
                                                                                        current_state = osint_result.state
                                                                                        
                                                                                        if current_state == 'PROGRESS':
                                                                                            meta_osint = _celery_progress_meta_as_dict(osint_result.info)
                                                                                            progress_osint = meta_osint.get('progress', 0)
                                                                                            message_osint = meta_osint.get('message', '')
                                                                                            
                                                                                            # Mettre à jour la progression de cette tâche
                                                                                            old_progress = osint_tasks_status[task_id].get('current_progress', 0)
                                                                                            osint_tasks_status[task_id]['current_progress'] = progress_osint
                                                                                            
                                                                                            # Ne mettre à jour que si la progression a vraiment changé
                                                                                            if old_progress != progress_osint:
                                                                                                # Recalculer la progression globale après mise à jour
                                                                                                total_progress_sum = 0
                                                                                                for tid, status in osint_tasks_status.items():
                                                                                                    if status.get('completed', False):
                                                                                                        total_progress_sum += 100
                                                                                                    else:
                                                                                                        total_progress_sum += status.get('current_progress', 0)
                                                                                                
                                                                                                global_progress = int((total_progress_sum / total_osint) if total_osint > 0 else 0)
                                                                                                
                                                                                                safe_emit(
                                                                                                    socketio,
                                                                                                    'osint_analysis_progress',
                                                                                                    {
                                                                                                        'current': osint_completed,
                                                                                                        'total': total_osint,
                                                                                                        'expected_total': expected_total_osint,
                                                                                                        'progress': global_progress,
                                                                                                        'message': f'{message_osint} - {osint_info.get("nom", "N/A")}',
                                                                                                        'url': osint_info.get('url', ''),
                                                                                                        'entreprise': osint_info.get('nom', 'N/A'),
                                                                                                        'task_progress': progress_osint,
                                                                                                        'cumulative_totals': osint_cumulative_totals.copy()
                                                                                                    },
                                                                                                    room=session_id
                                                                                                )
                                                                                        elif current_state == 'SUCCESS':
                                                                                            if not osint_tasks_status[task_id]['completed']:
                                                                                                osint_tasks_status[task_id]['completed'] = True
                                                                                                osint_tasks_status[task_id]['current_progress'] = 100
                                                                                                osint_completed += 1
                                                                                                
                                                                                                # Calculer les totaux cumulés depuis le résultat OSINT
                                                                                                result_osint = osint_result.result or {}
                                                                                                summary = result_osint.get('summary', {})
                                                                                                
                                                                                                # Ajouter les données de cette entreprise aux totaux cumulés
                                                                                                if summary:
                                                                                                    osint_cumulative_totals['subdomains'] += summary.get('subdomains_count', 0)
                                                                                                    osint_cumulative_totals['emails'] += summary.get('emails_count', 0)
                                                                                                    osint_cumulative_totals['people'] += summary.get('people_count', 0)
                                                                                                    osint_cumulative_totals['dns_records'] += summary.get('dns_records_count', 0)
                                                                                                
                                                                                                # Compter aussi depuis les données brutes si disponibles
                                                                                                if result_osint.get('subdomains'):
                                                                                                    osint_cumulative_totals['subdomains'] += len(result_osint.get('subdomains', []))
                                                                                                if result_osint.get('emails'):
                                                                                                    osint_cumulative_totals['emails'] += len(result_osint.get('emails', []))
                                                                                                if result_osint.get('ssl_info'):
                                                                                                    osint_cumulative_totals['ssl_analyses'] += 1
                                                                                                if result_osint.get('waf_detection'):
                                                                                                    osint_cumulative_totals['waf_detections'] += 1
                                                                                                if result_osint.get('directories'):
                                                                                                    osint_cumulative_totals['directories'] += len(result_osint.get('directories', []))
                                                                                                if result_osint.get('open_ports'):
                                                                                                    osint_cumulative_totals['open_ports'] += len(result_osint.get('open_ports', []))
                                                                                                if result_osint.get('services'):
                                                                                                    osint_cumulative_totals['services'] += len(result_osint.get('services', []))
                                                                                                
                                                                                                # Recalculer la progression globale après mise à jour
                                                                                                total_progress_sum = 0
                                                                                                for tid, status in osint_tasks_status.items():
                                                                                                    if status.get('completed', False):
                                                                                                        total_progress_sum += 100
                                                                                                    else:
                                                                                                        total_progress_sum += status.get('current_progress', 0)
                                                                                                
                                                                                                global_progress = int((total_progress_sum / total_osint) if total_osint > 0 else 0)
                                                                                                
                                                                                                safe_emit(
                                                                                                    socketio,
                                                                                                    'osint_analysis_progress',
                                                                                                    {
                                                                                                        'current': osint_completed,
                                                                                                        'total': total_osint,
                                                                                                        'expected_total': expected_total_osint,
                                                                                                        'progress': global_progress,
                                                                                                        'message': f'Analyse OSINT terminée pour {osint_info.get("nom", "N/A")}',
                                                                                                        'url': osint_info.get('url', ''),
                                                                                                        'entreprise': osint_info.get('nom', 'N/A'),
                                                                                                        'task_progress': 100,  # Entreprise terminée = 100%
                                                                                                        'summary': summary,
                                                                                                        'cumulative_totals': osint_cumulative_totals.copy()
                                                                                                    },
                                                                                                    room=session_id
                                                                                                )
                                                                                        elif current_state == 'FAILURE':
                                                                                            if not osint_tasks_status[task_id]['completed']:
                                                                                                osint_tasks_status[task_id]['completed'] = True
                                                                                                osint_tasks_status[task_id]['current_progress'] = 100
                                                                                                osint_completed += 1
                                                                                                
                                                                                                # Recalculer la progression globale après mise à jour
                                                                                                total_progress_sum = 0
                                                                                                for tid, status in osint_tasks_status.items():
                                                                                                    if status.get('completed', False):
                                                                                                        total_progress_sum += 100
                                                                                                    else:
                                                                                                        total_progress_sum += status.get('current_progress', 0)
                                                                                                
                                                                                                global_progress = int((total_progress_sum / total_osint) if total_osint > 0 else 0)
                                                                                                
                                                                                                safe_emit(
                                                                                                    socketio,
                                                                                                    'osint_analysis_error',
                                                                                                    {
                                                                                                        'error': f'Erreur lors de l\'analyse OSINT pour {osint_info.get("nom", "N/A")}',
                                                                                                        'url': osint_info.get('url', ''),
                                                                                                        'entreprise': osint_info.get('nom', 'N/A')
                                                                                                    },
                                                                                                    room=session_id
                                                                                                )
                                                                                            else:
                                                                                                total_progress_sum += 100
                                                                                    
                                                                                    except Exception as e:
                                                                                        logger.warning(f'Erreur monitoring tâche OSINT {task_id}: {e}')
                                                                                
                                                                                time.sleep(0.5)
                                                                            
                                                                                # Ne plus envoyer de message périodique, les jauges sont mises à jour directement
                                                                                
                                                                                time.sleep(0.5)
                                                                            
                                                                            # Toutes les analyses OSINT sont terminées
                                                                            final_total = len(monitor_scraping.osint_tasks_to_monitor)
                                                                            safe_emit(
                                                                                socketio,
                                                                                'osint_analysis_complete',
                                                                                {
                                                                                    'message': f'Analyses OSINT terminées pour {osint_completed}/{final_total} entreprises.',
                                                                                    'current': osint_completed,
                                                                                    'total': final_total,
                                                                                    'expected_total': expected_total_osint
                                                                                },
                                                                                room=session_id
                                                                            )
                                                                        
                                                                        _start_monitor_background(socketio, monitor_osint_tasks_realtime)
                                                                    
                                                                    # Récupérer les IDs des tâches Pentest depuis le meta
                                                                    # (une tâche Pentest par site scrapé ; la liste grossit à chaque update_progress)
                                                                    pentest_tasks_ids = meta_scraping.get('pentest_tasks_launched_ids', [])
                                                                    if pentest_tasks_ids:
                                                                        # Nombre d'entreprises de l'analyse (pour afficher X/2 au lieu de X/1)
                                                                        expected_total_entreprises = meta_scraping.get('total') or len(monitor_scraping.pentest_tasks_to_monitor)
                                                                        if not hasattr(monitor_scraping, 'pentest_tasks_to_monitor'):
                                                                            monitor_scraping.pentest_tasks_to_monitor = []
                                                                            monitor_scraping.pentest_monitoring_started = False
                                                                        
                                                                        existing_pentest_ids = {t['task_id'] for t in monitor_scraping.pentest_tasks_to_monitor}
                                                                        new_pentest_tasks = [t for t in pentest_tasks_ids if t['task_id'] not in existing_pentest_ids]
                                                                        if new_pentest_tasks:
                                                                            monitor_scraping.pentest_tasks_to_monitor.extend(new_pentest_tasks)
                                                                            logger.info(f'[WebSocket] {len(new_pentest_tasks)} nouvelle(s) tâche(s) Pentest détectée(s), total: {len(monitor_scraping.pentest_tasks_to_monitor)}')
                                                                            
                                                                            # Si le monitoring Pentest est déjà démarré, mettre à jour le compteur X/Y
                                                                            if getattr(monitor_scraping, 'pentest_monitoring_started', False):
                                                                                safe_emit(
                                                                                    socketio,
                                                                                    'pentest_analysis_started',
                                                                                    {
                                                                                        'message': f'Analyse Pentest démarrée pour {len(monitor_scraping.pentest_tasks_to_monitor)} entreprises...',
                                                                                        'total': len(monitor_scraping.pentest_tasks_to_monitor),
                                                                                        'expected_total': expected_total_entreprises,
                                                                                        'current': 0
                                                                                    },
                                                                                    room=session_id
                                                                                )
                                                                        
                                                                        if not monitor_scraping.pentest_monitoring_started and len(monitor_scraping.pentest_tasks_to_monitor) > 0:
                                                                            monitor_scraping.pentest_monitoring_started = True
                                                                            pentest_tasks_to_monitor = monitor_scraping.pentest_tasks_to_monitor
                                                                            
                                                                            safe_emit(
                                                                                socketio,
                                                                                'pentest_analysis_started',
                                                                                {
                                                                                    'message': f'Analyse Pentest démarrée pour {len(pentest_tasks_to_monitor)} entreprises...',
                                                                                    'total': len(pentest_tasks_to_monitor),
                                                                                    'expected_total': expected_total_entreprises,
                                                                                    'current': 0
                                                                                },
                                                                                room=session_id
                                                                            )
                                                                            
                                                                            def monitor_pentest_tasks_realtime():
                                                                                pentest_completed = 0
                                                                                pentest_status = {}
                                                                                last_global_progress = None
                                                                                pentest_cumulative_totals = {
                                                                                    'vulnerabilities': 0,
                                                                                    'forms_tested': 0,
                                                                                    'sql_injections': 0,
                                                                                    'xss_vulnerabilities': 0,
                                                                                    'risk_score': 0
                                                                                }
                                                                                
                                                                                while True:
                                                                                    current_tasks = monitor_scraping.pentest_tasks_to_monitor
                                                                                    total_pentest = len(current_tasks)
                                                                                    if total_pentest == 0:
                                                                                        break
                                                                                    
                                                                                    # Recalculer le nombre de tâches complétées à chaque itération
                                                                                    pentest_completed = sum(1 for status in pentest_status.values() if status.get('completed', False))
                                                                                    
                                                                                    total_progress_sum = 0
                                                                                    
                                                                                    for pentest_info in current_tasks:
                                                                                        task_id = pentest_info['task_id']
                                                                                        if task_id not in pentest_status:
                                                                                            pentest_status[task_id] = {'completed': False, 'last_progress': None, 'current_progress': 0}
                                                                                        
                                                                                        if pentest_status[task_id]['completed']:
                                                                                            total_progress_sum += 100
                                                                                            continue
                                                                                        
                                                                                        try:
                                                                                            pentest_result = celery.AsyncResult(task_id)
                                                                                            current_state = pentest_result.state
                                                                                            
                                                                                            if current_state == 'PROGRESS':
                                                                                                meta_pentest = _celery_progress_meta_as_dict(pentest_result.info)
                                                                                                progress_pentest = meta_pentest.get('progress', 0)
                                                                                                message_pentest = meta_pentest.get('message', '')
                                                                                                
                                                                                                pentest_status[task_id]['current_progress'] = progress_pentest
                                                                                                total_progress_sum += progress_pentest
                                                                                                
                                                                                                if pentest_status[task_id]['last_progress'] != progress_pentest:
                                                                                                    # Recalculer le nombre de tâches complétées avant l'émission
                                                                                                    pentest_completed = sum(1 for tid, status in pentest_status.items() if status.get('completed', False))
                                                                                                    global_progress = int((total_progress_sum / total_pentest) if total_pentest > 0 else 0)
                                                                                                    safe_emit(
                                                                                                        socketio,
                                                                                                        'pentest_analysis_progress',
                                                                                                        {
                                                                                                            'current': pentest_completed,
                                                                                                            'total': total_pentest,
                                                                                                            'expected_total': expected_total_entreprises,
                                                                                                            'progress': global_progress,
                                                                                                            'message': f'{message_pentest} - {pentest_info.get("nom", "N/A")}',
                                                                                                            'url': pentest_info.get('url', ''),
                                                                                                            'entreprise': pentest_info.get('nom', 'N/A'),
                                                                                                            'task_progress': progress_pentest,
                                                                                                            'cumulative_totals': pentest_cumulative_totals.copy()
                                                                                                        },
                                                                                                        room=session_id
                                                                                                    )
                                                                                                    pentest_status[task_id]['last_progress'] = progress_pentest
                                                                                            elif current_state == 'SUCCESS':
                                                                                                if not pentest_status[task_id]['completed']:
                                                                                                    pentest_status[task_id]['completed'] = True
                                                                                                    pentest_completed += 1
                                                                                                    total_progress_sum += 100
                                                                                                    
                                                                                                    result_pentest = pentest_result.result or {}
                                                                                                    summary = result_pentest.get('summary', {})
                                                                                                    
                                                                                                    # Calculer les totaux cumulés depuis le résultat Pentest
                                                                                                    if result_pentest.get('forms_checks'):
                                                                                                        pentest_cumulative_totals['forms_tested'] += len(result_pentest.get('forms_checks', []))
                                                                                                    
                                                                                                    vulnerabilities = result_pentest.get('vulnerabilities', [])
                                                                                                    if vulnerabilities:
                                                                                                        pentest_cumulative_totals['vulnerabilities'] += len(vulnerabilities)
                                                                                                        # Compter les types spécifiques
                                                                                                        for vuln in vulnerabilities:
                                                                                                            vuln_type = vuln.get('type', '').lower()
                                                                                                            if 'sql' in vuln_type or 'injection' in vuln_type:
                                                                                                                pentest_cumulative_totals['sql_injections'] += 1
                                                                                                            if 'xss' in vuln_type or 'cross-site' in vuln_type:
                                                                                                                pentest_cumulative_totals['xss_vulnerabilities'] += 1
                                                                                                    
                                                                                                    # Ajouter le score de risque (moyenne)
                                                                                                    risk_score = result_pentest.get('risk_score', 0)
                                                                                                    if risk_score > 0:
                                                                                                        # Calculer la moyenne des scores de risque
                                                                                                        pentest_cumulative_totals['risk_score'] = int((pentest_cumulative_totals['risk_score'] * (pentest_completed - 1) + risk_score) / pentest_completed)
                                                                                                    
                                                                                                    global_progress = int((total_progress_sum / total_pentest) if total_pentest > 0 else 0)
                                                                                                    safe_emit(
                                                                                                        socketio,
                                                                                                        'pentest_analysis_progress',
                                                                                                        {
                                                                                                            'current': pentest_completed,
                                                                                                            'total': total_pentest,
                                                                                                            'expected_total': expected_total_entreprises,
                                                                                                            'progress': global_progress,
                                                                                                            'message': f'Analyse Pentest terminée pour {pentest_info.get("nom", "N/A")}',
                                                                                                            'url': pentest_info.get('url', ''),
                                                                                                            'entreprise': pentest_info.get('nom', 'N/A'),
                                                                                                            'task_progress': 100,
                                                                                                            'summary': summary,
                                                                                                            'risk_score': risk_score,
                                                                                                            'cumulative_totals': pentest_cumulative_totals.copy()
                                                                                                        },
                                                                                                        room=session_id
                                                                                                    )
                                                                                            elif current_state == 'FAILURE':
                                                                                                if not pentest_status[task_id]['completed']:
                                                                                                    pentest_status[task_id]['completed'] = True
                                                                                                    pentest_completed += 1
                                                                                                    total_progress_sum += 100
                                                                                                    
                                                                                                    global_progress = int((total_progress_sum / total_pentest) if total_pentest > 0 else 0)
                                                                                                    safe_emit(
                                                                                                        socketio,
                                                                                                        'pentest_analysis_error',
                                                                                                        {
                                                                                                            'error': f'Erreur lors de l analyse Pentest pour {pentest_info.get("nom", "N/A")}',
                                                                                                            'url': pentest_info.get('url', ''),
                                                                                                            'entreprise': pentest_info.get('nom', 'N/A'),
                                                                                                            'progress': global_progress
                                                                                                        },
                                                                                                        room=session_id
                                                                                                    )
                                                                                        except Exception as e:
                                                                                            logger.warning(f'Erreur monitoring tâche Pentest {task_id}: {e}')
                                                                                    
                                                                                    # Recalculer la progression globale et notifier si elle évolue
                                                                                    if total_pentest > 0:
                                                                                        global_progress = int((total_progress_sum / total_pentest))
                                                                                        if last_global_progress != global_progress:
                                                                                            # Événement \"heartbeat\" global : NE PAS envoyer task_progress ni entreprise/url
                                                                                            # pour ne pas écraser l'affichage de l'entreprise en cours côté frontend.
                                                                                            safe_emit(
                                                                                                socketio,
                                                                                                'pentest_analysis_progress',
                                                                                                {
                                                                                                    'current': pentest_completed,
                                                                                                    'total': total_pentest,
                                                                                                    'expected_total': expected_total_entreprises,
                                                                                                    'progress': global_progress,
                                                                                                    'message': 'Analyse Pentest en cours...'
                                                                                                },
                                                                                                room=session_id
                                                                                            )
                                                                                            last_global_progress = global_progress
                                                                                    
                                                                                    # Important: ne pas s'arrêter tant que le scraping n'est pas terminé.
                                                                                    # Sinon, si la 1ere tâche Pentest finit vite, on sort avec un total=1,
                                                                                    # et les autres tâches (ajoutées après) ne seront jamais monitorées.
                                                                                    if pentest_completed >= total_pentest:
                                                                                        if getattr(monitor_scraping, 'scraping_done', False):
                                                                                            break
                                                                                        # Scraping toujours en cours: attendre, de nouvelles tâches peuvent arriver
                                                                                        time.sleep(0.5)
                                                                                        continue
                                                                                    
                                                                                    time.sleep(0.5)
                                                                                
                                                                                final_total = len(monitor_scraping.pentest_tasks_to_monitor)
                                                                                safe_emit(
                                                                                    socketio,
                                                                                    'pentest_analysis_complete',
                                                                                    {
                                                                                        'message': f'Analyses Pentest terminées pour {pentest_completed}/{final_total} entreprises.',
                                                                                        'current': pentest_completed,
                                                                                        'total': final_total,
                                                                                        'expected_total': expected_total_entreprises
                                                                                    },
                                                                                    room=session_id
                                                                                )
                                                                            
                                                                            _start_monitor_background(socketio, monitor_pentest_tasks_realtime)
                                                                    
                                                                    last_meta_scraping = meta_scraping
                                                            elif scraping_result.state == 'SUCCESS':
                                                                res = scraping_result.result or {}
                                                                # IMPORTANT: synchroniser les listes OSINT/Pentest depuis le résultat AVANT de marquer scraping_done.
                                                                # Sinon, si on a passé directement de PROGRESS (1 tâche) à SUCCESS sans voir le dernier meta,
                                                                # les monitors n'auraient qu'une tâche et sortiraient prématurément avec 1/2.
                                                                for osint_info in res.get('osint_tasks', []):
                                                                    tid = osint_info.get('task_id')
                                                                    if tid and (not hasattr(monitor_scraping, 'osint_tasks_to_monitor') or not any(t.get('task_id') == tid for t in monitor_scraping.osint_tasks_to_monitor)):
                                                                        if not hasattr(monitor_scraping, 'osint_tasks_to_monitor'):
                                                                            monitor_scraping.osint_tasks_to_monitor = []
                                                                        monitor_scraping.osint_tasks_to_monitor.append(osint_info)
                                                                        logger.debug(f'[WebSocket] Tâche OSINT {tid} ajoutée depuis SUCCESS (sync)')
                                                                for pentest_info in res.get('pentest_tasks', []):
                                                                    tid = pentest_info.get('task_id')
                                                                    if tid and (not hasattr(monitor_scraping, 'pentest_tasks_to_monitor') or not any(t.get('task_id') == tid for t in monitor_scraping.pentest_tasks_to_monitor)):
                                                                        if not hasattr(monitor_scraping, 'pentest_tasks_to_monitor'):
                                                                            monitor_scraping.pentest_tasks_to_monitor = []
                                                                        monitor_scraping.pentest_tasks_to_monitor.append(pentest_info)
                                                                        logger.debug(f'[WebSocket] Tâche Pentest {tid} ajoutée depuis SUCCESS (sync)')
                                                                monitor_scraping.scraping_done = True
                                                                stats = res.get('stats', {})
                                                                scraped_count = res.get('scraped_count', 0)
                                                                total_entreprises = res.get('total_entreprises', 0)
                                                                analysis_id = res.get('analysis_id')
                                                                
                                                                # Le monitoring des analyses techniques se fait déjà en temps réel
                                                                # Pas besoin de le relancer ici
                                                                
                                                                safe_emit(
                                                                    socketio,
                                                                    'scraping_complete',
                                                                    {
                                                                        'success': True,
                                                                        'analysis_id': analysis_id,
                                                                        'scraped_count': scraped_count,
                                                                        'total_entreprises': total_entreprises,
                                                                        'total_emails': stats.get('total_emails', 0),
                                                                        'total_people': stats.get('total_people', 0),
                                                                        'total_phones': stats.get('total_phones', 0),
                                                                        'total_social_platforms': stats.get('total_social_platforms', 0),
                                                                        'total_technologies': stats.get('total_technologies', 0),
                                                                        'total_images': stats.get('total_images', 0)
                                                                    },
                                                                    room=session_id
                                                                )
                                                                
                                                                
                                                                with tasks_lock:
                                                                    if session_id in active_tasks and active_tasks[session_id].get('type') == 'analysis_scraping':
                                                                        del active_tasks[session_id]
                                                                break
                                                            elif scraping_result.state == 'FAILURE':
                                                                # Même en échec, on marque le scraping comme terminé
                                                                monitor_scraping.scraping_done = True
                                                                safe_emit(
                                                                    socketio,
                                                                    'scraping_error',
                                                                    {
                                                                        'error': str(scraping_result.info)
                                                                    },
                                                                    room=session_id
                                                                )
                                                                with tasks_lock:
                                                                    if session_id in active_tasks:
                                                                        del active_tasks[session_id]
                                                                break
                                                        except Exception as e_scraping:
                                                            safe_emit(
                                                                socketio,
                                                                'scraping_error',
                                                                {
                                                                    'error': f'Erreur lors du suivi du scraping: {str(e_scraping)}'
                                                                },
                                                                room=session_id
                                                            )
                                                            with tasks_lock:
                                                                if session_id in active_tasks:
                                                                    del active_tasks[session_id]
                                                            break
                                                        time.sleep(1)
                                                except Exception as e_scraping:
                                                    safe_emit(
                                                        socketio,
                                                        'scraping_error',
                                                        {
                                                            'error': f'Erreur générale dans le suivi du scraping: {str(e_scraping)}'
                                                        },
                                                        room=session_id
                                                    )
    
                                            _start_monitor_background(socketio, monitor_scraping)
                                            
                                            # Marquer que le scraping a été lancé pour éviter de le relancer
                                            scraping_launched = True
                                            
                                            # Arrêter le monitoring de l'analyse principale après avoir lancé le scraping
                                            # Le monitoring du scraping se fera dans le thread séparé
                                            break
                                    except Exception as e_scraping_start:
                                        safe_emit(
                                            socketio,
                                            'scraping_error',
                                            {
                                                'error': f'Impossible de démarrer le scraping automatique: {str(e_scraping_start)}'
                                            },
                                            room=session_id
                                        )

                                else:
                                    with tasks_lock:
                                        if session_id in active_tasks:
                                            del active_tasks[session_id]
                                    break
                            elif current_state == 'FAILURE':
                                safe_emit(socketio, 'analysis_error', {
                                    'error': str(task_result.info)
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            
                            last_state = current_state
                        except Exception as e:
                            # Erreur lors de la vérification de l'état de la tâche
                            safe_emit(socketio, 'analysis_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}'
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        time.sleep(0.5)  # Vérifier plus souvent (toutes les 0.5 secondes)
                except Exception as e:
                    # Erreur générale dans le thread de monitoring
                    safe_emit(socketio, 'analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}'
                    }, room=session_id)
            
            _start_monitor_background(socketio, monitor_task)
        except Exception as e:
            # Erreur générale dans le handler
            try:
                safe_emit(socketio, 'analysis_error', {
                    'error': f'Erreur lors du démarrage de l\'analyse: {str(e)}'
                }, room=request.sid)
            except:
                pass  # Si même l'émission échoue, on ignore
    
    @socketio.on('stop_analysis')
    def handle_stop_analysis():
        """
        Arrête une analyse en cours
        """
        session_id = request.sid
        with tasks_lock:
            if session_id in active_tasks and active_tasks[session_id]['type'] == 'analysis':
                task_id = active_tasks[session_id]['task_id']
                # Révoquer la tâche Celery
                celery.AsyncResult(task_id).revoke(terminate=True)
                del active_tasks[session_id]
                safe_emit(socketio, 'analysis_stopped', {'message': 'Analyse arrêtée'}, room=session_id)
    
    @socketio.on('start_scraping')
    def handle_start_scraping(data):
        """
        Démarre un scraping d'emails via Celery
        
        Args:
            data (dict): Paramètres du scraping (url, max_depth, max_workers, max_time)
        """
        try:
            url = data.get('url')
            max_depth = int(data.get('max_depth', 3))
            max_workers = int(data.get('max_workers', 5))
            max_time = int(data.get('max_time', 300))
            max_pages = int(data.get('max_pages', 50))
            entreprise_id = data.get('entreprise_id')
            try:
                entreprise_id = int(entreprise_id) if entreprise_id is not None else None
            except Exception:
                entreprise_id = None
            session_id = request.sid

            try:
                logger.info(
                    '[Socket.IO] start_scraping sid=%s entreprise_id=%s url=%s depth=%s workers=%s time=%s pages=%s',
                    session_id,
                    entreprise_id,
                    (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
                    max_depth,
                    max_workers,
                    max_time,
                    max_pages,
                )
            except Exception:
                pass

            if not url and entreprise_id:
                try:
                    entreprise = database.get_entreprise(entreprise_id)
                    if entreprise:
                        url = entreprise.get('website') or entreprise.get('url')
                        if url:
                            logger.info(
                                '[Socket.IO] scraping url récupérée via entreprise_id=%s -> %s',
                                entreprise_id,
                                (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
                            )
                except Exception as e:
                    logger.warning(
                        '[Socket.IO] scraping fallback url échoué via entreprise_id=%s: %s',
                        entreprise_id,
                        str(e),
                        exc_info=True,
                    )
            
            if not url:
                safe_emit(socketio, 'scraping_error', {'error': 'URL requise', 'entreprise_id': entreprise_id}, room=session_id)
                return
            
            if not broker_ping_ok():
                logger.warning(
                    '[Socket.IO] start_scraping: broker Redis injoignable sid=%s entreprise_id=%s',
                    session_id,
                    entreprise_id,
                )
                safe_emit(socketio, 'scraping_error', {
                    'error': _CELERY_BROKER_UNREACHABLE_MSG
                }, room=session_id)
                return
            
            # Lancer la tâche Celery
            try:
                cd = next_websocket_stagger_countdown(session_id)
                task = scrape_emails_task.apply_async(
                    kwargs=dict(
                        url=url,
                        max_depth=max_depth,
                        max_workers=max_workers,
                        max_time=max_time,
                        max_pages=max_pages,
                        entreprise_id=entreprise_id,
                    ),
                    countdown=cd,
                    queue='scraping',
                )
            except Exception as e:
                logger.exception(
                    '[Socket.IO] apply_async scraping échoué sid=%s entreprise_id=%s',
                    session_id,
                    entreprise_id,
                )
                safe_emit(socketio, 'scraping_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}',
                    'entreprise_id': entreprise_id
                }, room=session_id)
                return
        
            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'scraping'}

            logger.info(
                '[Socket.IO] scraping enfilée task_id=%s entreprise_id=%s countdown=%.2fs queue=scraping url=%s',
                task.id,
                entreprise_id,
                cd,
                (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
            )
            
            safe_emit(socketio, 'scraping_started', {'message': 'Scraping démarré...', 'task_id': task.id, 'entreprise_id': entreprise_id}, room=session_id)
            
            # Surveiller la progression (similaire à l'analyse)
            def monitor_task():
                try:
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            if task_result.state == 'PROGRESS':
                                meta = _celery_progress_meta_as_dict(task_result.info)
                                safe_emit(socketio, 'scraping_progress', {
                                    'message': meta.get('message', ''),
                                    'entreprise_id': entreprise_id
                                }, room=session_id)
                            elif task_result.state == 'SUCCESS':
                                result = _celery_success_result_as_dict(task_result.result)
                                safe_emit(socketio, 'scraping_complete', {
                                    'success': True,
                                    'results': result.get('results', {}) if result else {},
                                    'entreprise_id': entreprise_id
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif task_result.state == 'FAILURE':
                                safe_emit(socketio, 'scraping_error', {
                                    'error': str(task_result.info),
                                    'entreprise_id': entreprise_id
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'scraping_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}',
                                'entreprise_id': entreprise_id
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        time.sleep(1)
                except Exception as e:
                    safe_emit(socketio, 'scraping_error', {
                        'error': f'Erreur dans le suivi: {str(e)}'
                    }, room=session_id)
            
            _start_monitor_background(socketio, monitor_task)
        except Exception as e:
            try:
                safe_emit(socketio, 'scraping_error', {
                    'error': f'Erreur lors du démarrage du scraping: {str(e)}'
                }, room=request.sid)
            except:
                pass
    
    @socketio.on('start_osint_analysis')
    def handle_start_osint_analysis(data):
        """
        Démarre une analyse OSINT via Celery
        
        Args:
            data (dict): Paramètres de l'analyse (url, entreprise_id)
        """
        try:
            url = data.get('url')
            entreprise_id = data.get('entreprise_id')
            session_id = request.sid

            try:
                logger.info(
                    '[Socket.IO] start_osint_analysis sid=%s entreprise_id=%s url=%s',
                    session_id,
                    entreprise_id,
                    (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
                )
            except Exception:
                pass

            if not url and entreprise_id:
                try:
                    entreprise = database.get_entreprise(entreprise_id)
                    if entreprise:
                        url = entreprise.get('website') or entreprise.get('url')
                        if url:
                            logger.info(
                                '[Socket.IO] osint url récupérée via entreprise_id=%s -> %s',
                                entreprise_id,
                                (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
                            )
                except Exception as e:
                    logger.warning(
                        '[Socket.IO] osint fallback url échoué via entreprise_id=%s: %s',
                        entreprise_id,
                        str(e),
                        exc_info=True,
                    )
            
            if not url:
                safe_emit(socketio, 'osint_analysis_error', {'error': 'URL requise'}, room=session_id)
                return
            
            if not broker_ping_ok():
                logger.warning(
                    '[Socket.IO] start_osint_analysis: broker Redis injoignable sid=%s entreprise_id=%s',
                    session_id,
                    entreprise_id,
                )
                safe_emit(socketio, 'osint_analysis_error', {
                    'error': _CELERY_BROKER_UNREACHABLE_MSG
                }, room=session_id)
                return
            
            # Récupérer les personnes des scrapers si nécessaire
            people_from_scrapers = None
            if entreprise_id:
                try:
                    scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                    people_from_scrapers = []
                    for scraper in scrapers:
                        if scraper.get('people'):
                            import json
                            people_list = scraper['people'] if isinstance(scraper['people'], list) else json.loads(scraper['people'])
                            people_from_scrapers.extend(people_list)
                except Exception as e:
                    pass
            
            # Lancer la tâche Celery (étalement par session : technique/SEO/pentest démarrent dans la seconde)
            cd = next_websocket_stagger_countdown(session_id)
            try:
                task = osint_analysis_task.apply_async(
                    kwargs=dict(
                        url=url,
                        entreprise_id=entreprise_id,
                        people_from_scrapers=people_from_scrapers,
                    ),
                    countdown=cd,
                    queue='osint',
                )
            except Exception as e:
                logger.exception(
                    '[Socket.IO] apply_async osint échoué sid=%s entreprise_id=%s',
                    session_id,
                    entreprise_id,
                )
                safe_emit(socketio, 'osint_analysis_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return
            
            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'osint', 'url': url}

            logger.info(
                '[Socket.IO] osint enfilée task_id=%s entreprise_id=%s countdown=%.2fs queue=osint url=%s',
                task.id,
                entreprise_id,
                cd,
                (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
            )
            
            safe_emit(socketio, 'osint_analysis_started', {'message': 'Analyse OSINT démarrée...', 'task_id': task.id}, room=session_id)
            
            # Surveiller la progression
            def monitor_task():
                try:
                    _sleep_before_monitor_poll(cd)
                    last_meta = None
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            current_state = task_result.state
                            
                            if current_state == 'PROGRESS':
                                meta = _celery_progress_meta_as_dict(task_result.info)
                                if meta != last_meta:
                                    safe_emit(socketio, 'osint_analysis_progress', {
                                        'progress': meta.get('progress', 0),
                                        'message': meta.get('message', ''),
                                        'task_progress': meta.get('progress', 0),  # Progression de cette tâche
                                        'url': url,
                                        'entreprise_id': entreprise_id
                                    }, room=session_id)
                                    last_meta = meta
                            elif current_state == 'SUCCESS':
                                result = _celery_success_result_as_dict(task_result.result)
                                safe_emit(socketio, 'osint_analysis_complete', {
                                    'success': True,
                                    'analysis_id': result.get('analysis_id') if result else None,
                                    'url': url,
                                    'entreprise_id': entreprise_id,
                                    'summary': result.get('summary', {}) if result else {},
                                    'updated': result.get('updated', False) if result else False
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif current_state == 'FAILURE':
                                safe_emit(socketio, 'osint_analysis_error', {
                                    'error': str(task_result.info),
                                    'entreprise_id': entreprise_id
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'osint_analysis_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}',
                                'entreprise_id': entreprise_id
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        time.sleep(_WS_MONITOR_POLL_SEC)
                except Exception as e:
                    safe_emit(socketio, 'osint_analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}',
                        'entreprise_id': entreprise_id
                    }, room=session_id)
            
            _start_monitor_background(socketio, monitor_task)
        except Exception as e:
            try:
                safe_emit(socketio, 'osint_analysis_error', {
                    'error': f'Erreur lors du démarrage de l\'analyse OSINT: {str(e)}'
                }, room=request.sid)
            except:
                pass
    
    @socketio.on('start_pentest_analysis')
    def handle_start_pentest_analysis(data):
        """
        Démarre une analyse Pentest via Celery
        
        Args:
            data (dict): Paramètres de l'analyse (url, entreprise_id, options)
        """
        try:
            url = data.get('url')
            entreprise_id = data.get('entreprise_id')
            options = data.get('options', {})
            session_id = request.sid

            # Log côté serveur (utile quand le front n'a "aucun retour / aucun log").
            try:
                logger.info(
                    '[Socket.IO] start_pentest_analysis sid=%s entreprise_id=%s url=%s',
                    session_id,
                    entreprise_id,
                    (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
                )
            except Exception:
                pass
            
            # Robustesse : si le front envoie un entreprise_id mais pas (ou vide) de url,
            # on récupère le "website" depuis la base.
            if not url and entreprise_id:
                try:
                    entreprise = database.get_entreprise(entreprise_id)
                    if entreprise:
                        url = entreprise.get('website') or entreprise.get('url')
                        if url:
                            logger.info(
                                '[Socket.IO] pentest url récupérée via entreprise_id=%s -> %s',
                                entreprise_id,
                                (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
                            )
                except Exception as e:
                    logger.warning(
                        '[Socket.IO] pentest fallback url échoué via entreprise_id=%s: %s',
                        entreprise_id,
                        str(e),
                        exc_info=True,
                    )

            if not url:
                safe_emit(socketio, 'pentest_analysis_error', {'error': 'URL requise'}, room=session_id)
                return
            
            if not broker_ping_ok():
                logger.warning(
                    '[Socket.IO] start_pentest_analysis: broker Redis injoignable sid=%s entreprise_id=%s',
                    session_id,
                    entreprise_id,
                )
                safe_emit(socketio, 'pentest_analysis_error', {
                    'error': _CELERY_BROKER_UNREACHABLE_MSG
                }, room=session_id)
                return

            # Récupérer les formulaires depuis les scrapers si disponibles (pour tester les formulaires côté Pentest)
            forms_from_scrapers = None
            if entreprise_id:
                try:
                    scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                    all_forms = []
                    for scraper in scrapers:
                        scraper_id = scraper.get('id') if isinstance(scraper, dict) else None
                        if scraper_id:
                            try:
                                forms = database.get_scraper_forms(scraper_id)
                                if forms:
                                    all_forms.extend(forms)
                            except Exception:
                                continue
                    if all_forms:
                        forms_from_scrapers = all_forms
                except Exception:
                    forms_from_scrapers = None
            
            cd = next_websocket_stagger_countdown(session_id)
            # Lancer la tâche Celery
            try:
                task = pentest_analysis_task.apply_async(
                    kwargs=dict(
                        url=url,
                        entreprise_id=entreprise_id,
                        options=options,
                        forms_from_scrapers=forms_from_scrapers,
                    ),
                    countdown=cd,
                    queue='pentest',
                )
            except Exception as e:
                logger.exception(
                    '[Socket.IO] apply_async pentest échoué sid=%s entreprise_id=%s',
                    session_id,
                    entreprise_id,
                )
                safe_emit(socketio, 'pentest_analysis_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return
            
            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'pentest', 'url': url}

            logger.info(
                '[Socket.IO] pentest enfilée task_id=%s entreprise_id=%s countdown=%.2fs queue=pentest url=%s',
                task.id,
                entreprise_id,
                cd,
                (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
            )
            
            safe_emit(socketio, 'pentest_analysis_started', {'message': 'Analyse de sécurité démarrée...', 'task_id': task.id}, room=session_id)
            
            # Surveiller la progression
            def monitor_task():
                try:
                    _sleep_before_monitor_poll(cd)
                    last_meta = None
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            current_state = task_result.state
                            
                            if current_state == 'PROGRESS':
                                meta = _celery_progress_meta_as_dict(task_result.info)
                                if meta != last_meta:
                                    safe_emit(socketio, 'pentest_analysis_progress', {
                                        'progress': meta.get('progress', 0),
                                        'message': meta.get('message', '')
                                    }, room=session_id)
                                    last_meta = meta
                            elif current_state == 'SUCCESS':
                                result = _celery_success_result_as_dict(task_result.result)
                                safe_emit(socketio, 'pentest_analysis_complete', {
                                    'success': True,
                                    'analysis_id': result.get('analysis_id') if result else None,
                                    'url': url,
                                    'entreprise_id': entreprise_id,
                                    'summary': result.get('summary', {}) if result else {},
                                    'risk_score': result.get('risk_score', 0) if result else 0,
                                    'updated': result.get('updated', False) if result else False
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif current_state == 'FAILURE':
                                safe_emit(socketio, 'pentest_analysis_error', {
                                    'error': str(task_result.info),
                                    'entreprise_id': entreprise_id
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'pentest_analysis_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}',
                                'entreprise_id': entreprise_id
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        time.sleep(_WS_MONITOR_POLL_SEC)
                except Exception as e:
                    safe_emit(socketio, 'pentest_analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}',
                        'entreprise_id': entreprise_id
                    }, room=session_id)
            
            _start_monitor_background(socketio, monitor_task)
        except Exception as e:
            try:
                safe_emit(socketio, 'pentest_analysis_error', {
                    'error': f'Erreur lors du démarrage de l\'analyse Pentest: {str(e)}'
                }, room=request.sid)
            except:
                pass
    
    @socketio.on('start_seo_analysis')
    def handle_start_seo_analysis(data):
        """
        Démarre une analyse SEO via Celery
        
        Args:
            data (dict): Paramètres de l'analyse (url, entreprise_id, use_lighthouse)
        """
        try:
            url = data.get('url')
            entreprise_id = data.get('entreprise_id')
            use_lighthouse = data.get('use_lighthouse', False)
            session_id = request.sid

            # app.logger : même cible que setup_root_logger (prospectlab.log sous Gunicorn)
            try:
                app.logger.info(
                    '[Socket.IO] start_seo_analysis sid=%s entreprise_id=%s url=%s',
                    session_id,
                    entreprise_id,
                    (url[:100] + '…') if isinstance(url, str) and len(url) > 100 else url,
                )
            except Exception:
                pass

            if not url and entreprise_id:
                try:
                    entreprise = database.get_entreprise(entreprise_id)
                    if entreprise:
                        url = entreprise.get('website') or entreprise.get('url')
                        if url:
                            app.logger.info(
                                '[Socket.IO] seo url récupérée via entreprise_id=%s -> %s',
                                entreprise_id,
                                (url[:100] + '…') if isinstance(url, str) and len(url) > 100 else url,
                            )
                except Exception as e:
                    try:
                        app.logger.warning(
                            '[Socket.IO] seo fallback url échoué via entreprise_id=%s: %s',
                            entreprise_id,
                            str(e),
                        )
                    except Exception:
                        pass
            
            if not url:
                safe_emit(socketio, 'seo_analysis_error', {'error': 'URL requise'}, room=session_id)
                return
            
            if not broker_ping_ok():
                app.logger.warning('[Socket.IO] start_seo_analysis: broker Redis injoignable sid=%s', session_id)
                safe_emit(socketio, 'seo_analysis_error', {
                    'error': _CELERY_BROKER_UNREACHABLE_MSG
                }, room=session_id)
                return
            
            cd = next_websocket_stagger_countdown(session_id)
            # Lancer la tâche Celery
            try:
                task = seo_analysis_task.apply_async(
                    kwargs=dict(
                        url=url,
                        entreprise_id=entreprise_id,
                        use_lighthouse=use_lighthouse,
                    ),
                    countdown=cd,
                    queue='seo',
                )
            except Exception as e:
                app.logger.exception('[Socket.IO] apply_async SEO échoué sid=%s: %s', session_id, e)
                safe_emit(socketio, 'seo_analysis_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return
            
            app.logger.info(
                '[Socket.IO] SEO enfilée task_id=%s entreprise_id=%s countdown=%.2fs queue=seo url=%s',
                task.id, entreprise_id, cd, url,
            )
            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'seo', 'url': url}
            
            safe_emit(socketio, 'seo_analysis_started', {'message': 'Analyse SEO démarrée...', 'task_id': task.id}, room=session_id)
            
            # Surveiller la progression
            def monitor_task():
                try:
                    _sleep_before_monitor_poll(cd)
                    last_meta = None
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            current_state = task_result.state
                            
                            if current_state == 'PROGRESS':
                                meta = _celery_progress_meta_as_dict(task_result.info)
                                if meta != last_meta:
                                    safe_emit(socketio, 'seo_analysis_progress', {
                                        'progress': meta.get('progress', 0),
                                        'message': meta.get('message', '')
                                    }, room=session_id)
                                    last_meta = meta
                            elif current_state == 'SUCCESS':
                                result = _celery_success_result_as_dict(task_result.result)
                                safe_emit(socketio, 'seo_analysis_complete', {
                                    'success': True,
                                    'analysis_id': result.get('analysis_id') if result else None,
                                    'url': url,
                                    'entreprise_id': entreprise_id,
                                    'summary': result.get('summary', {}) if result else {},
                                    'score': result.get('score', 0) if result else 0,
                                    'updated': result.get('updated', False) if result else False
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif current_state == 'FAILURE':
                                safe_emit(socketio, 'seo_analysis_error', {
                                    'error': str(task_result.info),
                                    'entreprise_id': entreprise_id
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'seo_analysis_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}',
                                'entreprise_id': entreprise_id
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        time.sleep(_WS_MONITOR_POLL_SEC)
                except Exception as e:
                    safe_emit(socketio, 'seo_analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}',
                        'entreprise_id': entreprise_id
                    }, room=session_id)
            
            _start_monitor_background(socketio, monitor_task)
        except Exception as e:
            try:
                safe_emit(socketio, 'seo_analysis_error', {
                    'error': f'Erreur lors du démarrage de l\'analyse SEO: {str(e)}'
                }, room=request.sid)
            except:
                pass

    @socketio.on('start_technical_analysis')
    def handle_start_technical_analysis(data):
        """
        Démarre une analyse technique (standalone) via Celery pour une entreprise.
        
        Args:
            data (dict): Paramètres de l'analyse (url, entreprise_id)
        """
        try:
            url = data.get('url')
            entreprise_id = data.get('entreprise_id')
            enable_nmap = data.get('enable_nmap', False)
            session_id = request.sid

            try:
                logger.info(
                    '[Socket.IO] start_technical_analysis sid=%s entreprise_id=%s url=%s enable_nmap=%s',
                    session_id,
                    entreprise_id,
                    (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
                    enable_nmap,
                )
            except Exception:
                pass

            if not url and entreprise_id:
                try:
                    entreprise = database.get_entreprise(entreprise_id)
                    if entreprise:
                        url = entreprise.get('website') or entreprise.get('url')
                        if url:
                            logger.info(
                                '[Socket.IO] technical url récupérée via entreprise_id=%s -> %s',
                                entreprise_id,
                                (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
                            )
                except Exception as e:
                    logger.warning(
                        '[Socket.IO] technical fallback url échoué via entreprise_id=%s: %s',
                        entreprise_id,
                        str(e),
                        exc_info=True,
                    )

            if not url:
                safe_emit(socketio, 'technical_analysis_error', {'error': 'URL requise'}, room=session_id)
                return

            if not broker_ping_ok():
                logger.warning(
                    '[Socket.IO] start_technical_analysis: broker Redis injoignable sid=%s entreprise_id=%s',
                    session_id,
                    entreprise_id,
                )
                safe_emit(socketio, 'technical_analysis_error', {'error': _CELERY_BROKER_UNREACHABLE_MSG}, room=session_id)
                return

            cd = next_websocket_stagger_countdown(session_id)
            # Lancer la tâche Celery
            try:
                task = technical_analysis_task.apply_async(
                    kwargs=dict(url=url, entreprise_id=entreprise_id, enable_nmap=enable_nmap),
                    countdown=cd,
                    queue='technical',
                )
            except Exception as e:
                logger.exception(
                    '[Socket.IO] apply_async technical échoué sid=%s entreprise_id=%s',
                    session_id,
                    entreprise_id,
                )
                safe_emit(socketio, 'technical_analysis_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return

            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'technical', 'url': url}

            logger.info(
                '[Socket.IO] technical enfilée task_id=%s entreprise_id=%s countdown=%.2fs queue=technical url=%s',
                task.id,
                entreprise_id,
                cd,
                (url[:100] + '...') if isinstance(url, str) and len(url) > 100 else url,
            )

            safe_emit(socketio, 'technical_analysis_started', {
                'message': 'Analyse technique démarrée...',
                'task_id': task.id
            }, room=session_id)

            # Surveiller la progression
            def monitor_task():
                try:
                    _sleep_before_monitor_poll(cd)
                    last_meta = None
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            current_state = task_result.state

                            if current_state == 'PROGRESS':
                                meta = _celery_progress_meta_as_dict(task_result.info)
                                if meta != last_meta:
                                    safe_emit(socketio, 'technical_analysis_progress', {
                                        'progress': meta.get('progress', 0),
                                        'message': meta.get('message', '')
                                    }, room=session_id)
                                    last_meta = meta
                            elif current_state == 'SUCCESS':
                                result = _celery_success_result_as_dict(task_result.result)
                                safe_emit(socketio, 'technical_analysis_complete', {
                                    'success': True,
                                    'analysis_id': result.get('analysis_id') if result else None,
                                    'url': url,
                                    'entreprise_id': entreprise_id,
                                    'results': result.get('results', {}) if result else {}
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif current_state == 'FAILURE':
                                safe_emit(socketio, 'technical_analysis_error', {
                                    'error': str(task_result.info),
                                    'entreprise_id': entreprise_id
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'technical_analysis_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}',
                                'entreprise_id': entreprise_id
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        time.sleep(_WS_MONITOR_POLL_SEC)
                except Exception as e:
                    safe_emit(socketio, 'technical_analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}',
                        'entreprise_id': entreprise_id
                    }, room=session_id)

            _start_monitor_background(socketio, monitor_task)
        except Exception as e:
            try:
                safe_emit(socketio, 'technical_analysis_error', {
                    'error': f'Erreur lors du démarrage de l\'analyse technique: {str(e)}'
                }, room=request.sid)
            except:
                pass

    @socketio.on('monitor_campagne')
    def handle_monitor_campagne(data):
        """
        Démarre le monitoring d'une campagne email en temps réel.

        Args:
            data (dict): {task_id, campagne_id}
        """
        try:
            task_id = data.get('task_id')
            campagne_id = data.get('campagne_id')
            session_id = request.sid

            if not task_id:
                safe_emit(socketio, 'campagne_error', {
                    'campagne_id': campagne_id,
                    'error': 'Task ID manquant'
                }, room=session_id)
                return

            def monitor_task():
                try:
                    task = celery.AsyncResult(task_id)
                    while True:
                        try:
                            current_state = task.state
                            task_result = task.info

                            if current_state == 'PROGRESS':
                                meta = task_result if isinstance(task_result, dict) else {}
                                safe_emit(socketio, 'campagne_progress', {
                                    'campagne_id': campagne_id,
                                    'progress': meta.get('progress', 0),
                                    'current': meta.get('current', 0),
                                    'total': meta.get('total', 0),
                                    'sent': meta.get('sent', 0),
                                    'failed': meta.get('failed', 0),
                                    'message': meta.get('message', 'Envoi en cours...')
                                }, room=session_id)
                            elif current_state == 'SUCCESS':
                                result = task_result if isinstance(task_result, dict) else {}
                                safe_emit(socketio, 'campagne_complete', {
                                    'campagne_id': campagne_id,
                                    'result': result
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif current_state == 'FAILURE':
                                error_msg = str(task_result) if task_result else 'Erreur inconnue'
                                safe_emit(socketio, 'campagne_error', {
                                    'campagne_id': campagne_id,
                                    'error': error_msg
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break

                            time.sleep(1.0)
                        except Exception as e:
                            safe_emit(socketio, 'campagne_error', {
                                'campagne_id': campagne_id,
                                'error': f'Erreur lors du suivi: {str(e)}'
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                except Exception as e:
                    safe_emit(socketio, 'campagne_error', {
                        'campagne_id': campagne_id,
                        'error': f'Erreur dans le monitoring: {str(e)}'
                    }, room=session_id)

            with tasks_lock:
                active_tasks[session_id] = {'type': 'campagne', 'task_id': task_id}

            _start_monitor_background(socketio, monitor_task)
        except Exception as e:
            try:
                safe_emit(socketio, 'campagne_error', {
                    'campagne_id': data.get('campagne_id'),
                    'error': f'Erreur lors du démarrage du monitoring: {str(e)}'
                }, room=request.sid)
            except:
                pass

