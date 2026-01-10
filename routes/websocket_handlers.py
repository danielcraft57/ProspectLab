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
from services.database import Database

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
            def monitor_task():
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
                                if analysis_id:
                                    try:
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

                                        # Surveiller la tâche de scraping
                                        def monitor_scraping():
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
                                                                last_meta_scraping = meta_scraping
                                                        elif scraping_result.state == 'SUCCESS':
                                                            res = scraping_result.result or {}
                                                            stats = res.get('stats', {})
                                                            safe_emit(
                                                                socketio,
                                                                'scraping_complete',
                                                                {
                                                                    'success': True,
                                                                    'analysis_id': res.get('analysis_id'),
                                                                    'scraped_count': res.get('scraped_count', 0),
                                                                    'total_entreprises': res.get('total_entreprises', 0),
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

