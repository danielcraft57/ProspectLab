"""
Tâches Celery pour les analyses d'entreprises

Ces tâches permettent d'exécuter les analyses de manière asynchrone,
évitant ainsi de bloquer l'application Flask principale.
"""

from celery_app import celery
from services.entreprise_analyzer import EntrepriseAnalyzer
from services.database import Database
from services.logging_config import setup_logger
import os
import logging
import threading
import time
from pathlib import Path

# Configurer le logger pour cette tâche
logger = setup_logger(__name__, 'analysis_tasks.log', level=logging.DEBUG)


def _safe_update_state(task, task_id, **kwargs):
    """
    Met à jour l'état de la tâche uniquement si un task_id est disponible.
    
    Args:
        task: Instance de la tâche Celery
        task_id: ID de la tâche (fallback si task.request.id est absent)
        **kwargs: Arguments passés à update_state
    """
    try:
        effective_id = getattr(task.request, 'id', None) or task_id
        if not effective_id:
            return
        task.update_state(task_id=effective_id, **kwargs)
    except Exception as exc:
        logger.warning(f'update_state impossible: {exc}')


@celery.task(bind=True)
def analyze_entreprise_task(self, filepath, output_path, max_workers=4, delay=0.1, 
                             enable_osint=False):
    """
    Tâche Celery pour analyser un fichier Excel d'entreprises
    
    Cette tâche exécute l'analyse complète des entreprises en arrière-plan,
    permettant à l'application Flask de rester réactive.
    
    Optimisée pour Celery avec --pool=threads --concurrency=4.
    Celery gère déjà la concurrence, donc délai minimal nécessaire.
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        filepath (str): Chemin vers le fichier Excel à analyser
        output_path (str): Chemin de sortie pour le fichier analysé
        max_workers (int): Nombre de threads parallèles (défaut: 4, optimisé pour Celery concurrency=4)
        delay (float): Délai entre requêtes en secondes (défaut: 0.1, minimal car Celery gère la concurrence)
        enable_osint (bool): Activer l'analyse OSINT (défaut: False)
        
    Returns:
        dict: Résultats de l'analyse avec le chemin du fichier de sortie
        
    Example:
        >>> result = analyze_entreprise_task.delay('file.xlsx', 'output.xlsx')
        >>> result.get()  # Attendre le résultat
    """
    try:
        logger.info(f'Début analyze_entreprise_task filepath={filepath} output={output_path} '
                    f'max_workers={max_workers} delay={delay} enable_osint={enable_osint}')
        task_id = getattr(self.request, 'id', None)
        if not task_id:
            logger.warning('task_id introuvable au démarrage - progression websocket risque de manquer')
        if not os.path.exists(filepath):
            logger.error(f'Fichier introuvable (abandon): {filepath}')
            raise FileNotFoundError(f'Fichier introuvable: {filepath}')
        
        # Mettre à jour l'état initial
        _safe_update_state(
            self,
            task_id,
            state='PROGRESS',
            meta={'current': 0, 'total': 0, 'percentage': 0, 'message': 'Chargement du fichier Excel...'}
        )
        
        # Créer un analyzer avec callback de progression
        task_instance = self
        
        class ProgressAnalyzer(EntrepriseAnalyzer):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.current_index = 0
                self.total = 0
                self.task = task_instance
                self.task_id = task_id
                self.progress_lock = threading.Lock()  # Verrou pour synchroniser les mises à jour
                self.current_entreprise_name = None
                self.current_entreprise_url = None

                # Callback de progression pour le scraper unifié (UnifiedScraper)
                def scraper_progress(message):
                    """
                    Callback appelé par le scraper pendant l'analyse d'un site.
                    Utilisé pour remonter l'avancement du scraping en temps réel.
                    """
                    try:
                        current = self.current_index
                        total = self.total or 0
                        percentage = int((current / total * 100)) if total > 0 else 0
                        # Message principal reste centré sur l'analyse d'entreprise
                        analyse_message = f'Analyse de {self.current_entreprise_name or "entreprise"} ({current}/{total})'
                        _safe_update_state(
                            self.task,
                            self.task_id,
                            state='PROGRESS',
                            meta={
                                'current': current,
                                'total': total,
                                'percentage': percentage,
                                'message': analyse_message,
                                'scraping_message': message,
                                'scraping_url': self.current_entreprise_url,
                                'scraping_entreprise': self.current_entreprise_name,
                            }
                        )
                    except Exception as exc:
                        logger.warning(f'Erreur scraper_progress: {exc}')

                # Exposer le callback pour EntrepriseAnalyzer.scrape_website
                self.progress_callback = scraper_progress
        
            def process_all(self):
                logger.info('Chargement du fichier Excel...')
                try:
                    df = self.load_excel()
                except Exception as exc:
                    logger.error(f'Erreur load_excel: {exc}', exc_info=True)
                    raise
                if df is None or df.empty:
                    _safe_update_state(
                        self.task,
                        self.task_id,
                        state='PROGRESS',
                        meta={'current': 0, 'total': 0, 'percentage': 0, 'message': 'Fichier Excel vide ou invalide'}
                    )
                    logger.warning('Fichier Excel vide ou invalide - arrêt')
                    return None
                
                self.total = len(df)
                logger.info(f'{self.total} lignes trouvées dans Excel')
                _safe_update_state(
                    self.task,
                    self.task_id,
                    state='PROGRESS',
                    meta={'current': 0, 'total': self.total, 'percentage': 0, 'message': 'Démarrage de l\'analyse...'}
                )
                
                return super().process_all()
            
            def analyze_entreprise_with_progress(self, row, idx):
                with self.progress_lock:
                    self.current_index = idx + 1
                    # Mémoriser l'entreprise courante pour les callbacks de scraping
                    try:
                        self.current_entreprise_name = row.get('name', 'inconnu')
                        self.current_entreprise_url = row.get('website', '')
                    except Exception:
                        self.current_entreprise_name = 'inconnu'
                        self.current_entreprise_url = ''
                    percentage = int((self.current_index / self.total * 100)) if self.total > 0 else 0
                    try:
                        _safe_update_state(
                            self.task,
                            self.task_id,
                            state='PROGRESS',
                            meta={
                                'current': self.current_index,
                                'total': self.total,
                                'percentage': percentage,
                                'message': f'Analyse de {row.get("name", "entreprise")}'
                            }
                        )
                    except Exception as e:
                        logger.warning(f'Erreur lors de la mise à jour de progression: {e}')
                
                # Analyser l'entreprise
                try:
                    result = super().analyze_entreprise(row)
                except Exception as exc:
                    logger.error(
                        f'Erreur analyse ligne {idx} ({row.get("name", "inconnu")}): {exc}',
                        exc_info=True
                    )
                    result = {'name': row.get('name'), 'error': str(exc)}
                
                # Sauvegarder l'entreprise dans la BDD (comme l'ancien système)
                if result and not result.get('error'):
                    try:
                        database = getattr(self, 'database', None)
                        if database:
                            # Préparer les données pour la sauvegarde
                            row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                            # Fusionner avec les résultats de l'analyse
                            row_dict.update(result)
                            
                            # Sauvegarder l'entreprise avec skip_duplicates pour éviter les doublons
                            analysis_id_to_use = getattr(self, 'analysis_id', None)
                            # Vérifier que analysis_id est valide (pas 0 ou None)
                            if not analysis_id_to_use or analysis_id_to_use == 0:
                                logger.error(f'ERREUR: analysis_id invalide ({analysis_id_to_use}) pour entreprise {row.get("name", "inconnu")}')
                                analysis_id_to_use = None
                            
                            entreprise_id = database.save_entreprise(
                                analysis_id_to_use,
                                row_dict,
                                skip_duplicates=True
                            )
                            
                            if entreprise_id:
                                # Vérifier si c'est un doublon
                                existing_ids_before = getattr(self, 'existing_ids_before', set())
                                stats = getattr(self, 'stats', {})
                                stats_lock = getattr(self, 'stats_lock', None)
                                
                                if stats_lock:
                                    with stats_lock:
                                        if entreprise_id in existing_ids_before:
                                            stats['duplicates'] = stats.get('duplicates', 0) + 1
                                        else:
                                            stats['inserted'] = stats.get('inserted', 0) + 1
                                            existing_ids_before.add(entreprise_id)
                                
                                # Sauvegarder aussi les données du scraper global (emails, people, etc.)
                                scraper_data = result.get('scraper_data')
                                if scraper_data:
                                    try:
                                        social_profiles = scraper_data.get('social_media') or scraper_data.get('social_links')
                                        visited_urls = scraper_data.get('visited_urls', 0)
                                        if isinstance(visited_urls, list):
                                            visited_urls_count = len(visited_urls)
                                        else:
                                            visited_urls_count = visited_urls or 0
                                        
                                        metadata_value = scraper_data.get('metadata', {})
                                        metadata_total = len(metadata_value) if isinstance(metadata_value, dict) else 0
                                        
                                        database.save_scraper(
                                            entreprise_id=entreprise_id,
                                            url=row_dict.get('website') or scraper_data.get('url'),
                                            scraper_type='unified_scraper',
                                            emails=scraper_data.get('emails'),
                                            people=scraper_data.get('people'),
                                            phones=scraper_data.get('phones'),
                                            social_profiles=social_profiles,
                                            technologies=scraper_data.get('technologies'),
                                            metadata=metadata_value,
                                            images=scraper_data.get('images'),
                                            visited_urls=visited_urls_count,
                                            total_emails=scraper_data.get('total_emails', 0),
                                            total_people=scraper_data.get('total_people', 0),
                                            total_phones=scraper_data.get('total_phones', 0),
                                            total_social_profiles=scraper_data.get('total_social_platforms', 0),
                                            total_technologies=scraper_data.get('total_technologies', 0),
                                            total_metadata=metadata_total,
                                            total_images=scraper_data.get('total_images', 0),
                                            duration=scraper_data.get('duration', 0)
                                        )
                                    except Exception as e:
                                        logger.warning(f'Erreur lors de la sauvegarde du scraper pour {row.get("name", "inconnu")}: {e}')
                    except Exception as e:
                        logger.warning(f'Erreur lors de la sauvegarde de l\'entreprise {row.get("name", "inconnu")}: {e}')
                else:
                    logger.warning(f'Analyse échouée pour {row.get("name", "inconnu")} : {result}')
                
                return result
        
        analyzer = ProgressAnalyzer(
            excel_file=filepath,
            output_file=output_path,
            max_workers=max_workers,
            delay=delay
        )
        
        # Désactiver OSINT si demandé
        if not enable_osint:
            analyzer.osint_analyzer = None
            logger.info('OSINT désactivé pour cette analyse')
        
        # Initialiser la base de données
        database = Database()
        logger.info(f'Base de données initialisée: {database.db_path}')
        
        # Créer l'enregistrement d'analyse
        start_time = time.time()
        output_filename = None  # Pas d'export Excel
        analysis_id = database.save_analysis(
            filename=Path(filepath).name,
            output_filename=output_filename,
            total=0,  # Sera mis à jour après
            parametres={'max_workers': max_workers, 'delay': delay, 'enable_osint': enable_osint},
            duree=0  # Sera mis à jour à la fin
        )
        logger.info(f'Analyse créée en BDD id={analysis_id}')
        
        # Stocker l'analysis_id et la database dans l'analyzer pour la sauvegarde
        analyzer.analysis_id = analysis_id
        analyzer.database = database
        analyzer.stats = {'inserted': 0, 'duplicates': 0}
        analyzer.stats_lock = threading.Lock()
        
        # Récupérer les IDs existants pour détecter les doublons
        conn = database.get_connection()
        cursor = conn.cursor()
        database.execute_sql(cursor, 'SELECT id FROM entreprises')
        rows = cursor.fetchall()
        # Gérer les dictionnaires PostgreSQL et les tuples SQLite
        analyzer.existing_ids_before = {row['id'] if isinstance(row, dict) else row[0] for row in rows}
        conn.close()
        logger.info(f'{len(analyzer.existing_ids_before)} entreprises déjà présentes avant analyse')
        
        # Exécuter l'analyse
        logger.info('Démarrage de process_all()')
        result = analyzer.process_all()
        
        if result is None:
            logger.error('L\'analyse n\'a produit aucun résultat')
            raise ValueError('L\'analyse n\'a produit aucun résultat')
        
        # Mettre à jour la durée de l'analyse
        duration = time.time() - start_time
        conn_update = database.get_connection()
        cursor_update = conn_update.cursor()
        # Mettre à jour la durée et le total (colonne: total_entreprises)
        database.execute_sql(cursor_update,
            'UPDATE analyses SET duree_secondes = ?, total_entreprises = ? WHERE id = ?',
            (duration, len(result), analysis_id)
        )
        conn_update.commit()
        conn_update.close()
        logger.info(f'Durée de l\'analyse mise à jour ({duration:.1f}s)')
        
        # Récupérer les stats finales
        total_processed = analyzer.total if hasattr(analyzer, 'total') else len(result)
        stats = analyzer.stats if hasattr(analyzer, 'stats') else {'inserted': 0, 'duplicates': 0}
        
        logger.info(f'Analyse terminée avec succès ({total_processed} entreprises traitées, {stats["inserted"]} nouvelles, {stats["duplicates"]} doublons)')
        
        # Mettre à jour l'état final
        self.update_state(
            state='PROGRESS',
            meta={
                'current': total_processed,
                'total': total_processed,
                'percentage': 100,
                'message': f'Analyse terminée! {stats["inserted"]} nouvelles entreprises, {stats["duplicates"]} doublons évités'
            }
        )
        
        return {
            'success': True,
            'output_file': None,  # Pas de fichier Excel exporté
            'total_processed': total_processed,
            'stats': stats,
            'analysis_id': analysis_id
        }
        
    except Exception as e:
        logger.error(f'Erreur lors de l\'analyse: {e}', exc_info=True)
        raise

