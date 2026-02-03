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
            # Valeurs optimisées pour Celery avec --pool=threads --concurrency dynamique
            # Celery gère déjà la concurrence, pas besoin de délai artificiel élevé
            from config import CELERY_WORKERS
            max_workers = int(data.get('max_workers', CELERY_WORKERS))  # Utilise la valeur depuis la config
            delay = float(data.get('delay', 0.1))         # Délai minimal, Celery gère la concurrence
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
                                
                                logger.info(f'Analyse terminée: total_processed={total_processed}, analysis_id={analysis_id}')
                                logger.info(f'Résultat complet de la tâche: {result}')
                                
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
                                logger.info(f'Vérification du lancement du scraping: analysis_id={analysis_id}, scraping_launched={scraping_launched}')
                                if not analysis_id:
                                    logger.warning(f'analysis_id est None ou vide, impossible de lancer le scraping automatiquement')
                                elif analysis_id:
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
                                                scraping_task = scrape_analysis_task.delay(analysis_id=analysis_id)
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
                                        logger.debug(f'Analyse technique lancée en parallèle du scraping')
                                        
                                        # Émettre l'événement de démarrage de l'analyse technique immédiatement
                                        # On utilisera le même nombre que les entreprises scrapées
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
                                                            meta_scraping = scraping_result.info or {}
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
                                                                                'analysis_id': analysis_id_for_tech,
                                                                                'current': tech_completed,
                                                                                'total': total_tech
                                                                            },
                                                                            room=session_id
                                                                        )
                                                                    
                                                                    threading.Thread(target=monitor_tech_tasks_realtime, daemon=True).start()
                                                                
                                                                # Récupérer les IDs des tâches OSINT depuis le meta
                                                                osint_tasks_ids = meta_scraping.get('osint_tasks_launched_ids', [])
                                                                if osint_tasks_ids:
                                                                    # Initialiser la liste si elle n'existe pas
                                                                    if not hasattr(monitor_scraping, 'osint_tasks_to_monitor'):
                                                                        monitor_scraping.osint_tasks_to_monitor = []
                                                                        monitor_scraping.osint_monitoring_started = False
                                                                    
                                                                    # Ajouter les nouvelles tâches OSINT qui ne sont pas déjà dans la liste
                                                                    existing_task_ids = {t['task_id'] for t in monitor_scraping.osint_tasks_to_monitor}
                                                                    new_tasks = [t for t in osint_tasks_ids if t['task_id'] not in existing_task_ids]
                                                                    
                                                                    if new_tasks:
                                                                        monitor_scraping.osint_tasks_to_monitor.extend(new_tasks)
                                                                        logger.debug(f'{len(new_tasks)} nouvelle(s) tâche(s) OSINT détectée(s), total: {len(monitor_scraping.osint_tasks_to_monitor)}')
                                                                    
                                                                    # Démarrer le monitoring si ce n'est pas déjà fait
                                                                    if not monitor_scraping.osint_monitoring_started and len(monitor_scraping.osint_tasks_to_monitor) > 0:
                                                                        osint_tasks_to_monitor = monitor_scraping.osint_tasks_to_monitor
                                                                        monitor_scraping.osint_monitoring_started = True
                                                                        logger.debug(f'Monitoring de {len(osint_tasks_to_monitor)} analyses OSINT démarré')
                                                                    
                                                                    # Émettre l'événement de démarrage OSINT
                                                                    safe_emit(
                                                                        socketio,
                                                                        'osint_analysis_started',
                                                                        {
                                                                            'message': f'Analyse OSINT démarrée pour {len(osint_tasks_to_monitor)} entreprises...',
                                                                            'total': len(osint_tasks_to_monitor),
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
                                                                                    break
                                                                            
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
                                                                                        meta_osint = osint_result.info or {}
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
                                                                            
                                                                            threading.Event().wait(0.5)
                                                                        
                                                                            # Ne plus envoyer de message périodique, les jauges sont mises à jour directement
                                                                            
                                                                            threading.Event().wait(0.5)
                                                                        
                                                                        # Toutes les analyses OSINT sont terminées
                                                                        final_total = len(monitor_scraping.osint_tasks_to_monitor)
                                                                        safe_emit(
                                                                            socketio,
                                                                            'osint_analysis_complete',
                                                                            {
                                                                                'message': f'Analyses OSINT terminées pour {osint_completed}/{final_total} entreprises.',
                                                                                'current': osint_completed,
                                                                                'total': final_total
                                                                            },
                                                                            room=session_id
                                                                        )
                                                                    
                                                                    threading.Thread(target=monitor_osint_tasks_realtime, daemon=True).start()
                                                                
                                                                # Récupérer les IDs des tâches Pentest depuis le meta
                                                                pentest_tasks_ids = meta_scraping.get('pentest_tasks_launched_ids', [])
                                                                if pentest_tasks_ids:
                                                                    if not hasattr(monitor_scraping, 'pentest_tasks_to_monitor'):
                                                                        monitor_scraping.pentest_tasks_to_monitor = []
                                                                        monitor_scraping.pentest_monitoring_started = False
                                                                    
                                                                    existing_pentest_ids = {t['task_id'] for t in monitor_scraping.pentest_tasks_to_monitor}
                                                                    new_pentest_tasks = [t for t in pentest_tasks_ids if t['task_id'] not in existing_pentest_ids]
                                                                    if new_pentest_tasks:
                                                                        monitor_scraping.pentest_tasks_to_monitor.extend(new_pentest_tasks)
                                                                        logger.info(f'[WebSocket] {len(new_pentest_tasks)} nouvelle(s) tâche(s) Pentest détectée(s), total: {len(monitor_scraping.pentest_tasks_to_monitor)}')
                                                                    
                                                                    if not monitor_scraping.pentest_monitoring_started and len(monitor_scraping.pentest_tasks_to_monitor) > 0:
                                                                        monitor_scraping.pentest_monitoring_started = True
                                                                        pentest_tasks_to_monitor = monitor_scraping.pentest_tasks_to_monitor
                                                                        
                                                                        safe_emit(
                                                                            socketio,
                                                                            'pentest_analysis_started',
                                                                            {
                                                                                'message': f'Analyse Pentest démarrée pour {len(pentest_tasks_to_monitor)} entreprises...',
                                                                                'total': len(pentest_tasks_to_monitor),
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
                                                                                            meta_pentest = pentest_result.info or {}
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
                                                                                        safe_emit(
                                                                                            socketio,
                                                                                            'pentest_analysis_progress',
                                                                                            {
                                                                                                'current': pentest_completed,
                                                                                                'total': total_pentest,
                                                                                                'progress': global_progress,
                                                                                                'message': 'Analyse Pentest en cours...',
                                                                                                'task_progress': global_progress
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
                                                                                    threading.Event().wait(0.5)
                                                                                    continue
                                                                                
                                                                                threading.Event().wait(0.5)
                                                                            
                                                                            final_total = len(monitor_scraping.pentest_tasks_to_monitor)
                                                                            safe_emit(
                                                                                socketio,
                                                                                'pentest_analysis_complete',
                                                                                {
                                                                                    'message': f'Analyses Pentest terminées pour {pentest_completed}/{final_total} entreprises.',
                                                                                    'current': pentest_completed,
                                                                                    'total': final_total
                                                                                },
                                                                                room=session_id
                                                                            )
                                                                        
                                                                        threading.Thread(target=monitor_pentest_tasks_realtime, daemon=True).start()
                                                                
                                                                last_meta_scraping = meta_scraping
                                                        elif scraping_result.state == 'SUCCESS':
                                                            # Le scraping est terminé: on peut autoriser les autres monitorings à finaliser proprement
                                                            monitor_scraping.scraping_done = True
                                                            res = scraping_result.result or {}
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
                                        'message': meta.get('message', ''),
                                        'task_progress': meta.get('progress', 0),  # Progression de cette tâche
                                        'url': url,
                                        'entreprise_id': entreprise_id
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
            enable_nmap = data.get('enable_nmap', False)
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
                task = technical_analysis_task.delay(url=url, entreprise_id=entreprise_id, enable_nmap=enable_nmap)
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

                            threading.Event().wait(1.0)
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

            thread = threading.Thread(target=monitor_task)
            thread.daemon = True
            thread.start()
        except Exception as e:
            try:
                safe_emit(socketio, 'campagne_error', {
                    'campagne_id': data.get('campagne_id'),
                    'error': f'Erreur lors du démarrage du monitoring: {str(e)}'
                }, room=request.sid)
            except:
                pass

