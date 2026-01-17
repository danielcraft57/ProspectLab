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
from tasks.technical_analysis_tasks import osint_analysis_task, pentest_analysis_task, technical_analysis_task
import os
import threading
import logging
from services.database import Database

# Logger pour ce module
logger = logging.getLogger(__name__)

# Initialiser les services
database = Database()

# Dictionnaires pour stocker les tâches actives
active_tasks = {}
tasks_lock = threading.Lock()


def register_websocket_handlers(socketio, app):
    """
    Enregistre tous les handlers WebSocket
    
    Args:
        socketio: Instance de SocketIO
        app: Instance de l'application Flask
    """
    
    @socketio.on('start_analysis')
    def handle_start_analysis(data):
        """
        Démarre une analyse d'entreprises via Celery
        
        Args:
            data (dict): Paramètres de l'analyse (filename, max_workers, delay, enable_osint)
        """
        try:
            filename = data.get('filename')
            max_workers = int(data.get('max_workers', 3))
            delay = float(data.get('delay', 2.0))
            enable_osint = data.get('enable_osint', False)
            session_id = request.sid
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if not os.path.exists(filepath):
                safe_emit(socketio, 'analysis_error', {'error': 'Fichier introuvable'}, room=session_id)
                return
            
            # Créer le fichier de sortie
            output_filename = f"analyzed_{filename}"
            output_path = os.path.join(app.config['EXPORT_FOLDER'], output_filename)
            
            # Vérifier que Celery/Redis est disponible
            try:
                # Test de connexion Redis
                from celery_app import celery
                celery.control.inspect().active()
            except Exception as e:
                error_msg = 'Celery worker non disponible. '
                error_msg += 'Démarre Celery avec: .\\scripts\\windows\\start-celery.ps1'
                error_msg += ' (ou: celery -A celery_app worker --loglevel=info)'
                safe_emit(socketio, 'analysis_error', {
                    'error': error_msg
                }, room=session_id)
                return
            
            # Lancer la tâche Celery
            try:
                task = analyze_entreprise_task.delay(
                    filepath=filepath,
                    output_path=output_path,
                    max_workers=max_workers,
                    delay=delay,
                    enable_osint=enable_osint
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
                                meta = task_result.info
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
                                
                                result = task_result.result
                                total_processed = result.get('total_processed', 0) if result else 0
                                analysis_id = result.get('analysis_id') if result else None
                                safe_emit(
                                    socketio,
                                    'analysis_complete',
                                    {
                                    'success': True,
                                    'output_file': result.get('output_file') if result else None,
                                    'total_processed': total_processed,
                                    'total': total_processed,  # Pour compatibilité avec l'ancien code
                                    'message': f'Analyse terminée avec succès ! {total_processed} entreprises analysées.'
                                    },
                                    room=session_id
                                )

                                # Lancer automatiquement le scraping de toutes les entreprises de cette analyse
                                # Vérifier qu'une tâche de scraping n'est pas déjà en cours pour cette analyse
                                if analysis_id:
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
                                            break
                                        
                                        scraping_task = scrape_analysis_task.delay(analysis_id=analysis_id)
                                        with tasks_lock:
                                            active_tasks[session_id] = {
                                                'task_id': scraping_task.id,
                                                'type': 'analysis_scraping',
                                                'analysis_id': analysis_id
                                            }

                                        safe_emit(
                                            socketio,
                                            'scraping_started',
                                            {
                                                'message': 'Scraping des entreprises en cours...',
                                                'task_id': scraping_task.id,
                                                'analysis_id': analysis_id
                                            },
                                            room=session_id
                                        )

                                        # L'analyse technique est maintenant lancée en parallèle dans la tâche de scraping
                                        # On va suivre les tâches techniques via le monitoring du scraping
                                        logger.info(f'[WebSocket] L\'analyse technique sera lancée en parallèle du scraping pour chaque entreprise')
                                        
                                        # Émettre l'événement de démarrage de l'analyse technique immédiatement
                                        # On utilisera le même nombre que les entreprises scrapées
                                        db = Database()
                                        conn = db.get_connection()
                                        cursor = conn.cursor()
                                        cursor.execute(
                                            '''
                                            SELECT COUNT(*) FROM entreprises
                                            WHERE analyse_id = ?
                                              AND website IS NOT NULL
                                              AND TRIM(website) <> ''
                                            ''',
                                            (analysis_id,)
                                        )
                                        total_entreprises_avec_site = cursor.fetchone()[0]
                                        conn.close()
                                        
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
                                            logger.info(f'[WebSocket] Événement technical_analysis_started émis pour {total_entreprises_avec_site} entreprises')
                                        
                                        tech_tasks_to_monitor = []  # Sera rempli dès qu'on reçoit les IDs dans le meta
                                        tech_tasks_monitoring_started = False  # Flag pour démarrer le monitoring une seule fois
                                        
                                        # Surveiller la tâche de scraping
                                        def monitor_scraping():
                                            nonlocal tech_tasks_to_monitor, tech_tasks_monitoring_started
                                            try:
                                                last_meta_scraping = None
                                                while True:
                                                    try:
                                                        scraping_result = celery.AsyncResult(scraping_task.id)
                                                        if scraping_result.state == 'PROGRESS':
                                                            meta_scraping = scraping_result.info or {}
                                                            if meta_scraping != last_meta_scraping:
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
                                                                    logger.info(f'[WebSocket] Démarrant le monitoring de {len(tech_tasks_to_monitor)} analyses techniques en temps réel')
                                                                    
                                                                    # Démarrer le monitoring des analyses techniques en temps réel
                                                                    def monitor_tech_tasks_realtime():
                                                                        tech_completed = 0
                                                                        total_tech = len(tech_tasks_to_monitor)
                                                                        tech_tasks_status = {t['task_id']: {'completed': False, 'last_progress': None, 'current_progress': 0} for t in tech_tasks_to_monitor}
                                                                        
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
                                                                                        meta_tech = tech_result.info or {}
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
                                                                            
                                                                            threading.Event().wait(0.5)
                                                                        
                                                                        # Toutes les analyses techniques sont terminées
                                                                        safe_emit(
                                                                            socketio,
                                                                            'technical_analysis_complete',
                                                                            {
                                                                                'message': f'Analyses techniques terminées pour {tech_completed}/{total_tech} entreprises.',
                                                                                'analysis_id': analysis_id,
                                                                                'current': tech_completed,
                                                                                'total': total_tech
                                                                            },
                                                                            room=session_id
                                                                        )
                                                                    
                                                                    threading.Thread(target=monitor_tech_tasks_realtime, daemon=True).start()
                                                                
                                                                last_meta_scraping = meta_scraping
                                                        elif scraping_result.state == 'SUCCESS':
                                                            res = scraping_result.result or {}
                                                            stats = res.get('stats', {})
                                                            scraped_count = res.get('scraped_count', 0)
                                                            total_entreprises = res.get('total_entreprises', 0)
                                                            
                                                            # Le monitoring des analyses techniques se fait déjà en temps réel
                                                            # Pas besoin de le relancer ici
                                                            
                                                            safe_emit(
                                                                socketio,
                                                                'scraping_complete',
                                                                {
                                                                    'success': True,
                                                                    'analysis_id': res.get('analysis_id'),
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
                                                                if session_id in active_tasks:
                                                                    del active_tasks[session_id]
                                                            break
                                                        elif scraping_result.state == 'FAILURE':
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
                                                    threading.Event().wait(1)
                                            except Exception as e_scraping:
                                                safe_emit(
                                                    socketio,
                                                    'scraping_error',
                                                    {
                                                        'error': f'Erreur générale dans le suivi du scraping: {str(e_scraping)}'
                                                    },
                                                    room=session_id
                                                )

                                        scraping_thread = threading.Thread(target=monitor_scraping)
                                        scraping_thread.daemon = True
                                        scraping_thread.start()
                                        
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
                        threading.Event().wait(0.5)  # Vérifier plus souvent (toutes les 0.5 secondes)
                except Exception as e:
                    # Erreur générale dans le thread de monitoring
                    safe_emit(socketio, 'analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}'
                    }, room=session_id)
            
            thread = threading.Thread(target=monitor_task)
            thread.daemon = True
            thread.start()
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
            session_id = request.sid
            
            if not url:
                safe_emit(socketio, 'scraping_error', {'error': 'URL requise'}, room=session_id)
                return
            
            # Vérifier que Celery/Redis est disponible
            try:
                from celery_app import celery
                celery.control.inspect().active()
            except Exception as e:
                error_msg = 'Celery worker non disponible. '
                error_msg += 'Démarre Celery avec: .\\scripts\\windows\\start-celery.ps1'
                error_msg += ' (ou: celery -A celery_app worker --loglevel=info)'
                safe_emit(socketio, 'scraping_error', {
                    'error': error_msg
                }, room=session_id)
                return
            
            # Lancer la tâche Celery
            try:
                task = scrape_emails_task.delay(
                    url=url,
                    max_depth=max_depth,
                    max_workers=max_workers,
                    max_time=max_time
                )
            except Exception as e:
                safe_emit(socketio, 'scraping_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return
        
            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'scraping'}
            
            safe_emit(socketio, 'scraping_started', {'message': 'Scraping démarré...', 'task_id': task.id}, room=session_id)
            
            # Surveiller la progression (similaire à l'analyse)
            def monitor_task():
                try:
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            if task_result.state == 'PROGRESS':
                                meta = task_result.info
                                safe_emit(socketio, 'scraping_progress', {
                                    'message': meta.get('message', '')
                                }, room=session_id)
                            elif task_result.state == 'SUCCESS':
                                result = task_result.result
                                safe_emit(socketio, 'scraping_complete', {
                                    'success': True,
                                    'results': result.get('results', {})
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif task_result.state == 'FAILURE':
                                safe_emit(socketio, 'scraping_error', {
                                    'error': str(task_result.info)
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'scraping_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}'
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        threading.Event().wait(1)
                except Exception as e:
                    safe_emit(socketio, 'scraping_error', {
                        'error': f'Erreur dans le suivi: {str(e)}'
                    }, room=session_id)
            
            thread = threading.Thread(target=monitor_task)
            thread.daemon = True
            thread.start()
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
            
            if not url:
                safe_emit(socketio, 'osint_analysis_error', {'error': 'URL requise'}, room=session_id)
                return
            
            # Vérifier que Celery/Redis est disponible
            try:
                from celery_app import celery
                celery.control.inspect().active()
            except Exception as e:
                error_msg = 'Celery worker non disponible. '
                error_msg += 'Démarre Celery avec: .\\scripts\\windows\\start-celery.ps1'
                safe_emit(socketio, 'osint_analysis_error', {
                    'error': error_msg
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
            
            # Lancer la tâche Celery
            try:
                task = osint_analysis_task.delay(
                    url=url,
                    entreprise_id=entreprise_id,
                    people_from_scrapers=people_from_scrapers
                )
            except Exception as e:
                safe_emit(socketio, 'osint_analysis_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return
            
            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'osint', 'url': url}
            
            safe_emit(socketio, 'osint_analysis_started', {'message': 'Analyse OSINT démarrée...', 'task_id': task.id}, room=session_id)
            
            # Surveiller la progression
            def monitor_task():
                try:
                    last_meta = None
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            current_state = task_result.state
                            
                            if current_state == 'PROGRESS':
                                meta = task_result.info
                                if meta != last_meta:
                                    safe_emit(socketio, 'osint_analysis_progress', {
                                        'progress': meta.get('progress', 0),
                                        'message': meta.get('message', '')
                                    }, room=session_id)
                                    last_meta = meta
                            elif current_state == 'SUCCESS':
                                result = task_result.result
                                safe_emit(socketio, 'osint_analysis_complete', {
                                    'success': True,
                                    'analysis_id': result.get('analysis_id'),
                                    'url': url,
                                    'summary': result.get('summary', {}),
                                    'updated': result.get('updated', False)
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif current_state == 'FAILURE':
                                safe_emit(socketio, 'osint_analysis_error', {
                                    'error': str(task_result.info)
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'osint_analysis_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}'
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        threading.Event().wait(0.5)
                except Exception as e:
                    safe_emit(socketio, 'osint_analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}'
                    }, room=session_id)
            
            thread = threading.Thread(target=monitor_task)
            thread.daemon = True
            thread.start()
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
            
            if not url:
                safe_emit(socketio, 'pentest_analysis_error', {'error': 'URL requise'}, room=session_id)
                return
            
            # Vérifier que Celery/Redis est disponible
            try:
                from celery_app import celery
                celery.control.inspect().active()
            except Exception as e:
                error_msg = 'Celery worker non disponible. '
                error_msg += 'Démarre Celery avec: .\\scripts\\windows\\start-celery.ps1'
                safe_emit(socketio, 'pentest_analysis_error', {
                    'error': error_msg
                }, room=session_id)
                return
            
            # Lancer la tâche Celery
            try:
                task = pentest_analysis_task.delay(
                    url=url,
                    entreprise_id=entreprise_id,
                    options=options
                )
            except Exception as e:
                safe_emit(socketio, 'pentest_analysis_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return
            
            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'pentest', 'url': url}
            
            safe_emit(socketio, 'pentest_analysis_started', {'message': 'Analyse de sécurité démarrée...', 'task_id': task.id}, room=session_id)
            
            # Surveiller la progression
            def monitor_task():
                try:
                    last_meta = None
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            current_state = task_result.state
                            
                            if current_state == 'PROGRESS':
                                meta = task_result.info
                                if meta != last_meta:
                                    safe_emit(socketio, 'pentest_analysis_progress', {
                                        'progress': meta.get('progress', 0),
                                        'message': meta.get('message', '')
                                    }, room=session_id)
                                    last_meta = meta
                            elif current_state == 'SUCCESS':
                                result = task_result.result
                                safe_emit(socketio, 'pentest_analysis_complete', {
                                    'success': True,
                                    'analysis_id': result.get('analysis_id'),
                                    'url': url,
                                    'summary': result.get('summary', {}),
                                    'risk_score': result.get('risk_score', 0),
                                    'updated': result.get('updated', False)
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif current_state == 'FAILURE':
                                safe_emit(socketio, 'pentest_analysis_error', {
                                    'error': str(task_result.info)
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'pentest_analysis_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}'
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        threading.Event().wait(0.5)
                except Exception as e:
                    safe_emit(socketio, 'pentest_analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}'
                    }, room=session_id)
            
            thread = threading.Thread(target=monitor_task)
            thread.daemon = True
            thread.start()
        except Exception as e:
            try:
                safe_emit(socketio, 'pentest_analysis_error', {
                    'error': f'Erreur lors du démarrage de l\'analyse Pentest: {str(e)}'
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
            session_id = request.sid

            if not url:
                safe_emit(socketio, 'technical_analysis_error', {'error': 'URL requise'}, room=session_id)
                return

            # Vérifier que Celery/Redis est disponible
            try:
                from celery_app import celery
                celery.control.inspect().active()
            except Exception:
                error_msg = 'Celery worker non disponible. Démarre Celery avec: .\\scripts\\windows\\start-celery.ps1'
                safe_emit(socketio, 'technical_analysis_error', {'error': error_msg}, room=session_id)
                return

            # Lancer la tâche Celery
            try:
                task = technical_analysis_task.delay(url=url, entreprise_id=entreprise_id)
            except Exception as e:
                safe_emit(socketio, 'technical_analysis_error', {
                    'error': f'Erreur lors du démarrage de la tâche: {str(e)}'
                }, room=session_id)
                return

            # Stocker la tâche
            with tasks_lock:
                active_tasks[session_id] = {'task_id': task.id, 'type': 'technical', 'url': url}

            safe_emit(socketio, 'technical_analysis_started', {
                'message': 'Analyse technique démarrée...',
                'task_id': task.id
            }, room=session_id)

            # Surveiller la progression
            def monitor_task():
                try:
                    last_meta = None
                    while True:
                        try:
                            task_result = celery.AsyncResult(task.id)
                            current_state = task_result.state

                            if current_state == 'PROGRESS':
                                meta = task_result.info or {}
                                if meta != last_meta:
                                    safe_emit(socketio, 'technical_analysis_progress', {
                                        'progress': meta.get('progress', 0),
                                        'message': meta.get('message', '')
                                    }, room=session_id)
                                    last_meta = meta
                            elif current_state == 'SUCCESS':
                                result = task_result.result or {}
                                safe_emit(socketio, 'technical_analysis_complete', {
                                    'success': True,
                                    'analysis_id': result.get('analysis_id'),
                                    'url': url,
                                    'results': result.get('results', {})
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                            elif current_state == 'FAILURE':
                                safe_emit(socketio, 'technical_analysis_error', {
                                    'error': str(task_result.info)
                                }, room=session_id)
                                with tasks_lock:
                                    if session_id in active_tasks:
                                        del active_tasks[session_id]
                                break
                        except Exception as e:
                            safe_emit(socketio, 'technical_analysis_error', {
                                'error': f'Erreur lors du suivi de la tâche: {str(e)}'
                            }, room=session_id)
                            with tasks_lock:
                                if session_id in active_tasks:
                                    del active_tasks[session_id]
                            break
                        threading.Event().wait(0.5)
                except Exception as e:
                    safe_emit(socketio, 'technical_analysis_error', {
                        'error': f'Erreur dans le suivi: {str(e)}'
                    }, room=session_id)

            thread = threading.Thread(target=monitor_task)
            thread.daemon = True
            thread.start()
        except Exception as e:
            try:
                safe_emit(socketio, 'technical_analysis_error', {
                    'error': f'Erreur lors du démarrage de l\'analyse technique: {str(e)}'
                }, room=request.sid)
            except:
                pass

