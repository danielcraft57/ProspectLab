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
import math
from pathlib import Path
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tasks.phone_tasks import analyze_phones_dict_for_storage
from tasks.scraping_tasks import schedule_enrich_external_links_mini_scrape
from services.unified_scraper import merge_scraper_metadata_for_storage
from config import EXPORT_FOLDER, UPLOAD_FOLDER

# Configurer le logger pour cette tâche
logger = setup_logger(__name__, 'analysis_tasks.log', level=logging.DEBUG)


def _resolve_upload_path_for_worker(filepath: str) -> str:
    """
    L'app peut enfiler un chemin serveur (/srv/nfs/...) alors que le worker voit le même
    fichier sous UPLOAD_FOLDER (montage NFS différent par nœud).
    """
    if not filepath:
        return filepath
    p = Path(filepath)
    try:
        if p.is_file() and p.stat().st_size > 0:
            return str(p.resolve())
    except OSError:
        pass
    candidate = UPLOAD_FOLDER / p.name
    logger.info(
        'Résolution chemin upload (worker): reçu=%s UPLOAD_FOLDER=%s candidate=%s',
        filepath,
        str(UPLOAD_FOLDER),
        str(candidate),
    )
    try:
        if candidate.exists():
            # On accepte même si st_size == 0 pour éviter de rater un fichier en cours d'écriture.
            if candidate.is_file():
                logger.info('Chemin upload résolu pour le worker: %s -> %s', filepath, str(candidate))
                return str(candidate.resolve())
    except OSError as exc:
        logger.warning('Stat candidate échouée (%s): %s', str(candidate), exc)
    return filepath


def _resolve_output_path_for_worker(output_path: str) -> str:
    """Même logique pour l'export : écrire sous EXPORT_FOLDER du worker si le chemin absolu distant n'existe pas."""
    if not output_path:
        return output_path
    p = Path(output_path)
    parent = p.parent
    try:
        if parent.exists() and os.access(str(parent), os.W_OK):
            return str(p)
    except OSError:
        pass
    out = EXPORT_FOLDER / p.name
    logger.info(f'Chemin export résolu pour le worker: {output_path} -> {out}')
    return str(out)


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


def _to_jsonable_value(value):
    """
    Convertit une valeur potentiellement pandas/numpy en valeur JSON-serializable.

    Celery est configuré en serializer 'json', donc on évite de passer des types
    comme numpy.int64, pandas.Timestamp, ou pandas NA.
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        # Si pd.isna ne marche pas sur le type, on continue.
        pass

    # Scalars numpy (ex: numpy.int64, numpy.float64, numpy.bool_)
    try:
        if hasattr(value, "item"):
            return value.item()
    except Exception:
        pass

    # float NaN/Inf
    try:
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
    except Exception:
        pass

    if isinstance(value, (str, int, float, bool)):
        return value

    # datetime / timestamp
    try:
        iso = getattr(value, "isoformat", None)
        if callable(iso):
            return iso()
    except Exception:
        pass

    # List / dict récursifs
    if isinstance(value, (list, tuple)):
        return [_to_jsonable_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable_value(v) for k, v in value.items()}

    return str(value)


def _records_to_jsonable(records):
    """
    Transforme une liste de dict (records) en liste JSON-serializable.
    """
    out = []
    for r in records or []:
        if not isinstance(r, dict):
            out.append(_to_jsonable_value(r))
            continue
        out.append({str(k): _to_jsonable_value(v) for k, v in r.items()})
    return out


def _deduplicate_df_global_option_b(df, database, existing_ids_before):
    """
    Déduplication globale type B :
    - doublons dans le fichier via une signature (domaine normalisé si possible, sinon nom + adresses)
    - doublons déjà existants dans la BDD via find_duplicate_entreprise + existing_ids_before

    Args:
        df (pandas.DataFrame): DataFrame chargé depuis Excel
        database (Database): instance Database
        existing_ids_before (set[int]): IDs entreprises présents avant analyse

    Returns:
        pandas.DataFrame: DataFrame filtré, reset_index(drop=True)
    """
    from utils.url_utils import normalize_website_domain

    seen_signatures = set()
    rows_to_keep = []

    def normalize_website_for_signature(raw):
        domain = normalize_website_domain(raw)
        return domain or ''

    original_total = len(df)

    for idx, row in df.iterrows():
        try:
            name = (str(row.get('name') or row.get('nom') or '')).strip()
            website_raw = row.get('website') or ''
            website_norm = normalize_website_for_signature(website_raw)
            address_1 = (str(row.get('address_1') or row.get('address_full') or '')).strip().lower()
            address_2 = (str(row.get('address_2') or '')).strip().lower()
        except Exception:
            name = str(row.get('name', '')).strip()
            website_raw = row.get('website')
            website_norm = normalize_website_for_signature(website_raw)
            address_1 = str(row.get('address_1', '')).strip().lower()
            address_2 = str(row.get('address_2', '')).strip().lower()

        if website_norm:
            signature = ('domain', website_norm)
        else:
            signature = (name.lower(), address_1, address_2)

        # Doublon dans le même fichier
        if signature in seen_signatures and any(signature):
            continue

        duplicate_existing_id = None
        if database and (name or website_raw):
            try:
                duplicate_existing_id = database.find_duplicate_entreprise(
                    name, website_raw, address_1, address_2
                )
            except Exception as e:
                logger.warning(f'Erreur find_duplicate_entreprise pour "{name}": {e}')

        # Doublon déjà présent en BDD avant analyse
        if duplicate_existing_id and duplicate_existing_id in existing_ids_before:
            continue

        seen_signatures.add(signature)
        rows_to_keep.append(idx)

    if rows_to_keep:
        df_filtered = df.loc[rows_to_keep].reset_index(drop=True)
    else:
        df_filtered = df.iloc[0:0].copy()

    logger.info(
        'Déduplication globale option B: original=%s filtré=%s (ignorés=%s)',
        original_total,
        len(df_filtered),
        original_total - len(df_filtered),
    )
    return df_filtered


@celery.task(bind=True)
def analyze_entreprise_batch_task(
    self,
    filepath,
    batch_rows,
    analysis_id,
    max_workers=4,
    delay=0.1,
    enable_osint=False,
    output_path=None,
):
    """
    Tâche Celery "batch" : analyse d'un sous-ensemble de lignes (20 lignes par défaut côté orchestrateur).

    Args:
        filepath (str): chemin du fichier (peut être un chemin 'app' ou 'worker', on le résout par nom)
        batch_rows (list[dict]): liste de lignes JSON-serialisables
        analysis_id (int): ID d'analyse en BDD (créée par l'orchestrateur)
        max_workers (int): concurrence interne (threads) dans le batch
        delay (float): délai entre requêtes scraping/analyse
        enable_osint (bool): activer/désactiver OSINT
        output_path (str|None): chemin export (non utilisé dans cette version)

    Returns:
        dict: total_processed
    """
    try:
        filepath = _resolve_upload_path_for_worker(filepath)

        database = Database()

        analyzer = EntrepriseAnalyzer(
            excel_file=filepath,
            output_file=output_path,
            max_workers=max_workers,
            delay=delay,
        )
        if not enable_osint:
            analyzer.osint_analyzer = None

        batch_rows = _records_to_jsonable(batch_rows)
        total_processed = len(batch_rows or [])
        batch_task_id = getattr(self.request, 'id', None)
        processed_counter = 0
        progress_lock = threading.Lock()
        logger.info('Batch démarre analysis_id=%s batch_len=%s filepath=%s', analysis_id, total_processed, filepath)

        _safe_update_state(
            self,
            batch_task_id,
            state='PROGRESS',
            meta={
                'analysis_id': analysis_id,
                'current': 0,
                'total': total_processed,
                'percentage': 0,
                'message': f'Batch en cours (0/{total_processed})',
            },
        )

        def _process_one(row_dict):
            """
            Traite une entreprise et sauvegarde dans la BDD.
            """
            result = None
            try:
                # analyze_entreprise gère row.get et pd.isna pour dicts aussi
                result = analyzer.analyze_entreprise(row_dict)
            except Exception as exc:
                result = {'error': str(exc)}

            if result and not result.get('error'):
                try:
                    row_dict_merged = dict(row_dict) if isinstance(row_dict, dict) else dict(row_dict)
                    row_dict_merged.update(result)

                    entreprise_id = database.save_entreprise(
                        analysis_id,
                        row_dict_merged,
                        skip_duplicates=True,
                    )

                    if entreprise_id:
                        scraper_data = result.get('scraper_data')
                        if scraper_data:
                            try:
                                social_profiles = scraper_data.get('social_media') or scraper_data.get('social_links')
                                visited_urls = scraper_data.get('visited_urls', 0)
                                if isinstance(visited_urls, list):
                                    visited_urls_count = len(visited_urls)
                                else:
                                    visited_urls_count = visited_urls or 0

                                metadata_value = merge_scraper_metadata_for_storage(
                                    scraper_data.get('metadata'),
                                    scraper_data.get('external_links'),
                                    scraper_data.get('scraped_location'),
                                )
                                metadata_total = len(metadata_value) if isinstance(metadata_value, dict) else 0

                                phone_analyses = {}
                                phones_s = scraper_data.get('phones') or []
                                if phones_s:
                                    try:
                                        phone_analyses = analyze_phones_dict_for_storage(
                                            phones_s,
                                            source_url=row_dict_merged.get('website') or scraper_data.get('url'),
                                        )
                                    except Exception as pe:
                                        logger.warning('Analyse téléphones pour scraper BDD: %s', pe)

                                sid = database.save_scraper(
                                    entreprise_id=entreprise_id,
                                    url=row_dict_merged.get('website') or scraper_data.get('url'),
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
                                    duration=scraper_data.get('duration', 0),
                                    phone_analyses=phone_analyses if phone_analyses else None,
                                )
                                try:
                                    cw_url = row_dict_merged.get('website') or scraper_data.get('url')
                                    database.replace_web_external_links_for_scraper(
                                        entreprise_id=entreprise_id,
                                        scraper_id=sid,
                                        client_site_url=cw_url,
                                        external_links=scraper_data.get('external_links'),
                                    )
                                except Exception as cle:
                                    logger.warning('web_external_links (batch): %s', cle)
                                schedule_enrich_external_links_mini_scrape(entreprise_id, sid)
                                try:
                                    database.patch_entreprise_location_from_scrape(
                                        entreprise_id, scraper_data.get('scraped_location')
                                    )
                                except Exception as le:
                                    logger.warning('patch_entreprise_location (batch): %s', le)
                            except Exception as se:
                                logger.warning('Erreur sauvegarde scraper: %s', se)
                except Exception as se:
                    logger.warning('Erreur sauvegarde entreprise: %s', se)

            nonlocal processed_counter
            with progress_lock:
                processed_counter += 1
                percentage = int((processed_counter / total_processed) * 100) if total_processed > 0 else 100
                _safe_update_state(
                    self,
                    batch_task_id,
                    state='PROGRESS',
                    meta={
                        'analysis_id': analysis_id,
                        'current': processed_counter,
                        'total': total_processed,
                        'percentage': percentage,
                        'message': f'Batch en cours ({processed_counter}/{total_processed})',
                    },
                )
            return 1

        # Exécuter en parallèle à l'intérieur du batch
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_process_one, row) for row in (batch_rows or [])]
            # Drain futures (les exceptions sont gérées dans _process_one)
            for _ in as_completed(futures):
                pass

        return {
            'success': True,
            'total_processed': total_processed,
        }

    except Exception as e:
        logger.error('Erreur analyse batch: %s', e, exc_info=True)
        raise


@celery.task(bind=True)
def analyze_entreprise_orchestrator_task(
    self,
    filepath,
    output_path,
    max_workers=4,
    delay=0.1,
    enable_osint=False,
    batch_size=20,
):
    """
    Orchestrateur multi-batches (option B : déduplication globale) pour accélérer un fichier Excel.
    """
    try:
        filepath = _resolve_upload_path_for_worker(filepath)
        output_path = _resolve_output_path_for_worker(output_path)

        logger.info(
            'Début orchestrateur analyse_entreprise_orchestrator_task filepath=%s output=%s max_workers=%s delay=%s enable_osint=%s batch_size=%s',
            filepath,
            output_path,
            max_workers,
            delay,
            enable_osint,
            batch_size,
        )

        task_id = getattr(self.request, 'id', None)
        if not task_id:
            logger.warning('task_id introuvable au démarrage - progression websocket risque de manquer')

        # Attendre un court délai que le fichier soit visible sur le worker
        timeout_s = float(os.environ.get('UPLOAD_VISIBILITY_TIMEOUT_S', '5.0'))
        interval_s = float(os.environ.get('UPLOAD_VISIBILITY_INTERVAL_S', '0.25'))
        deadline = time.time() + max(0.0, timeout_s)
        while time.time() < deadline:
            try:
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    break
            except OSError:
                pass
            time.sleep(interval_s)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'Fichier introuvable: {filepath}')

        _safe_update_state(
            self,
            task_id,
            state='PROGRESS',
            meta={'current': 0, 'total': 0, 'percentage': 0, 'message': 'Chargement du fichier...'}
        )

        start_time = time.time()

        database = Database()
        filename_only = Path(filepath).name

        # Charger Excel 1 fois pour dédup globale
        analyzer = EntrepriseAnalyzer(
            excel_file=filepath,
            output_file=output_path,
            max_workers=max_workers,
            delay=delay,
        )
        if not enable_osint:
            analyzer.osint_analyzer = None

        df = analyzer.load_excel()
        if df is None or df.empty:
            _safe_update_state(
                self,
                task_id,
                state='PROGRESS',
                meta={'current': 0, 'total': 0, 'percentage': 0, 'message': 'Fichier Excel vide ou invalide'}
            )
            raise ValueError('Fichier Excel vide ou invalide')

        # existing_ids_before (comme dans la tâche monolithe)
        conn = database.get_connection()
        cursor = conn.cursor()
        database.execute_sql(cursor, 'SELECT id FROM entreprises')
        rows = cursor.fetchall()

        existing_ids_before = set()
        for row in rows:
            try:
                if isinstance(row, dict):
                    rid = row.get('id')
                else:
                    rid = row[0]
                if rid is not None:
                    existing_ids_before.add(int(rid))
            except Exception:
                continue
        conn.close()

        # Déduplication globale option B
        df_filtered = _deduplicate_df_global_option_b(df, database, existing_ids_before)
        total_rows = len(df_filtered)

        # Créer l'enregistrement d'analyse (pour que le scraping auto puisse se lancer)
        analysis_id = database.save_analysis(
            filename=filename_only,
            output_filename=None,
            total=0,
            parametres={'max_workers': max_workers, 'delay': delay, 'enable_osint': enable_osint, 'batch_size': batch_size},
            duree=0,
        )

        if total_rows == 0:
            duration = time.time() - start_time
            conn_update = database.get_connection()
            cursor_update = conn_update.cursor()
            database.execute_sql(
                cursor_update,
                'UPDATE analyses SET duree_secondes = ?, total_entreprises = ? WHERE id = ?',
                (duration, 0, analysis_id),
            )
            conn_update.commit()
            conn_update.close()

            self.update_state(
                state='PROGRESS',
                meta={'current': 0, 'total': 0, 'percentage': 0, 'message': 'Aucune entreprise à analyser'}
            )
            return {
                'success': True,
                'output_file': None,
                'total_processed': 0,
                'stats': {'inserted': 0, 'duplicates': 0},
                'analysis_id': analysis_id,
            }

        # Préparer les batches
        batches = []
        for i in range(0, total_rows, int(batch_size or 20)):
            df_batch = df_filtered.iloc[i:i + int(batch_size or 20)]
            records = df_batch.to_dict('records')
            records = _records_to_jsonable(records)
            batches.append(records)

        total_batches = len(batches)
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': total_rows, 'percentage': 0, 'message': 'Démarrage de l\'analyse...'}
        )

        # Lancer les batch tasks en parallèle (multi-noeuds)
        batch_task_ids = []
        batch_started_at = {}
        for batch_index, records in enumerate(batches):
            res = analyze_entreprise_batch_task.apply_async(
                kwargs=dict(
                    filepath=filepath,
                    batch_rows=records,
                    analysis_id=analysis_id,
                    max_workers=max_workers,
                    delay=delay,
                    enable_osint=enable_osint,
                    output_path=output_path,
                ),
                queue='technical',
            )
            batch_task_ids.append((res.id, len(records)))
            batch_started_at[res.id] = time.time()

        completed_rows = 0
        processed_done_ids = set()
        per_batch_progress = {tid: 0 for tid, _ in batch_task_ids}
        last_reported_completed_rows = -1
        batch_watchdog_timeout_s = float(os.environ.get('ANALYSIS_BATCH_WATCHDOG_TIMEOUT_S', '300'))
        timed_out_batches = set()

        while len(processed_done_ids) < len(batch_task_ids):
            progress_changed = False
            for tid, batch_len in batch_task_ids:
                if tid in processed_done_ids:
                    continue
                r = celery.AsyncResult(tid)
                if r.state == 'PROGRESS':
                    meta = r.info if isinstance(r.info, dict) else {}
                    current_batch = int(meta.get('current', 0) or 0)
                    current_batch = max(0, min(current_batch, batch_len))
                    if current_batch != per_batch_progress.get(tid, 0):
                        per_batch_progress[tid] = current_batch
                        progress_changed = True
                elif r.state == 'SUCCESS':
                    processed_done_ids.add(tid)
                    per_batch_progress[tid] = batch_len
                    progress_changed = True
                elif r.state in ('FAILURE', 'REVOKED'):
                    if tid in timed_out_batches:
                        processed_done_ids.add(tid)
                        progress_changed = True
                        continue
                    raise RuntimeError(f'Batch {tid} en échec: state={r.state}')

                if tid not in processed_done_ids and batch_watchdog_timeout_s > 0:
                    started = batch_started_at.get(tid, time.time())
                    elapsed = time.time() - started
                    if elapsed >= batch_watchdog_timeout_s:
                        logger.error(
                            'Batch timeout analysis_id=%s task_id=%s elapsed=%.1fs current=%s/%s',
                            analysis_id,
                            tid,
                            elapsed,
                            per_batch_progress.get(tid, 0),
                            batch_len,
                        )
                        try:
                            celery.AsyncResult(tid).revoke(terminate=True)
                        except Exception as revoke_exc:
                            logger.warning('Batch revoke échoué task_id=%s: %s', tid, revoke_exc)
                        timed_out_batches.add(tid)
                        processed_done_ids.add(tid)
                        progress_changed = True

            completed_rows = sum(per_batch_progress.values())
            if progress_changed and completed_rows != last_reported_completed_rows:
                last_reported_completed_rows = completed_rows
                percentage = int((completed_rows / total_rows) * 100) if total_rows > 0 else 0
                _safe_update_state(
                    self,
                    task_id,
                    state='PROGRESS',
                    meta={
                        'current': completed_rows,
                        'total': total_rows,
                        'percentage': percentage,
                        'message': f'Analyse en cours ({completed_rows}/{total_rows})'
                    }
                )
            time.sleep(1.0)

        duration = time.time() - start_time

        # Mettre à jour analyses (total_entreprises et durée)
        conn_update = database.get_connection()
        cursor_update = conn_update.cursor()
        database.execute_sql(
            cursor_update,
            'UPDATE analyses SET duree_secondes = ?, total_entreprises = ? WHERE id = ?',
            (duration, completed_rows, analysis_id),
        )
        conn_update.commit()
        conn_update.close()

        return {
            'success': True,
            'output_file': None,
            'total_processed': completed_rows,
            'stats': {
                'inserted': completed_rows,
                'duplicates': 0,
                'timed_out_batches': len(timed_out_batches),
            },
            'analysis_id': analysis_id,
        }

    except Exception as e:
        logger.error('Erreur orchestrateur analyse: %s', e, exc_info=True)
        raise


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
        filepath = _resolve_upload_path_for_worker(filepath)
        output_path = _resolve_output_path_for_worker(output_path)
        logger.info(f'Début analyze_entreprise_task filepath={filepath} output={output_path} '
                    f'max_workers={max_workers} delay={delay} enable_osint={enable_osint}')
        task_id = getattr(self.request, 'id', None)
        if not task_id:
            logger.warning('task_id introuvable au démarrage - progression websocket risque de manquer')
        # En prod, le fichier peut apparaître avec un léger délai (volume réseau, rename atomique, etc.).
        # On fait un retry court avant d'abandonner.
        timeout_s = float(os.environ.get('UPLOAD_VISIBILITY_TIMEOUT_S', '5.0'))
        interval_s = float(os.environ.get('UPLOAD_VISIBILITY_INTERVAL_S', '0.25'))
        deadline = time.time() + max(0.0, timeout_s)
        while time.time() < deadline:
            try:
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    break
            except OSError:
                pass
            time.sleep(interval_s)
        if not os.path.exists(filepath):
            logger.error(f'Fichier introuvable (abandon): {filepath}')
            # Diagnostic : le worker voit-il le fichier sous UPLOAD_FOLDER ?
            try:
                fallback = (UPLOAD_FOLDER / Path(filepath).name).resolve()
                logger.error('Diagnostic fichier candidat: %s existe=%s', str(fallback), fallback.exists())
            except Exception:
                pass
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
                
                original_total = len(df)
                logger.info(f'{original_total} lignes trouvées dans Excel (avant déduplication)')

                # Dédupliquer en amont pour éviter les doublons (dans le fichier et en BDD)
                try:
                    database = getattr(self, 'database', None)
                    existing_ids_before = getattr(self, 'existing_ids_before', set())
                    stats = getattr(self, 'stats', {})
                    stats_lock = getattr(self, 'stats_lock', None)

                    from utils.url_utils import normalize_website_domain

                    seen_signatures = set()
                    rows_to_keep = []

                    def normalize_website_for_signature(raw):
                        """
                        Utilise la même normalisation de domaine que le backend (normalize_website_domain)
                        pour garantir qu'un domaine correspond à une seule entreprise.
                        """
                        domain = normalize_website_domain(raw)
                        return domain or ''

                    for idx, row in df.iterrows():
                        try:
                            name = (str(row.get('name') or row.get('nom') or '')).strip()
                            website_raw = row.get('website') or ''
                            website_norm = normalize_website_for_signature(website_raw)
                            address_1 = (str(row.get('address_1') or row.get('address_full') or '')).strip().lower()
                            address_2 = (str(row.get('address_2') or '')).strip().lower()
                        except Exception:
                            name = str(row.get('name', '')).strip()
                            website_raw = row.get('website')
                            website_norm = normalize_website_for_signature(website_raw)
                            address_1 = str(row.get('address_1', '')).strip().lower()
                            address_2 = str(row.get('address_2', '')).strip().lower()

                        # Signature pour détecter les doublons dans le fichier :
                        # - si domaine connu : unicité sur le domaine
                        # - sinon : fallback nom + adresses
                        if website_norm:
                            signature = ('domain', website_norm)
                        else:
                            signature = (name.lower(), address_1, address_2)

                        # Doublon dans le même fichier
                        if signature in seen_signatures and any(signature):
                            if stats_lock:
                                with stats_lock:
                                    stats['duplicates'] = stats.get('duplicates', 0) + 1
                            continue

                        duplicate_existing_id = None
                        # Doublon déjà présent en base AVANT cette analyse
                        if database and (name or website_raw):
                            try:
                                duplicate_existing_id = database.find_duplicate_entreprise(
                                    name, website_raw, address_1, address_2
                                )
                            except Exception as e:
                                logger.warning(f'Erreur find_duplicate_entreprise pour "{name}": {e}')

                        if duplicate_existing_id and duplicate_existing_id in existing_ids_before:
                            # On considère cette ligne comme doublon global -> on ne relance pas d\'analyse dessus
                            if stats_lock:
                                with stats_lock:
                                    stats['duplicates'] = stats.get('duplicates', 0) + 1
                            continue

                        seen_signatures.add(signature)
                        rows_to_keep.append(idx)

                    if rows_to_keep:
                        df_filtered = df.loc[rows_to_keep].reset_index(drop=True)
                    else:
                        df_filtered = df.iloc[0:0].copy()

                    self._df_override = df_filtered
                    self.total = len(df_filtered)
                    logger.info(
                        f'{self.total} lignes à analyser après déduplication '
                        f'({original_total - self.total} doublon(s) ignoré(s))'
                    )
                except Exception as e:
                    # En cas de problème, on retombe sur le comportement existant
                    logger.warning(f'Erreur lors de la déduplication en amont: {e}')
                    self.total = original_total

                _safe_update_state(
                    self.task,
                    self.task_id,
                    state='PROGRESS',
                    meta={
                        'current': 0,
                        'total': self.total,
                        'percentage': 0,
                        'message': 'Démarrage de l\'analyse...'
                    }
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
                                        
                                        metadata_value = merge_scraper_metadata_for_storage(
                                            scraper_data.get('metadata'),
                                            scraper_data.get('external_links'),
                                            scraper_data.get('scraped_location'),
                                        )
                                        metadata_total = len(metadata_value) if isinstance(metadata_value, dict) else 0
                                        
                                        phone_analyses = {}
                                        phones_s = scraper_data.get('phones') or []
                                        if phones_s:
                                            try:
                                                phone_analyses = analyze_phones_dict_for_storage(
                                                    phones_s,
                                                    source_url=row_dict.get('website') or scraper_data.get('url'),
                                                )
                                            except Exception as pe:
                                                logger.warning(
                                                    'Analyse téléphones pour scraper BDD: %s', pe
                                                )
                                        
                                        sid = database.save_scraper(
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
                                            duration=scraper_data.get('duration', 0),
                                            phone_analyses=phone_analyses if phone_analyses else None,
                                        )
                                        try:
                                            cw_url = row_dict.get('website') or scraper_data.get('url')
                                            database.replace_web_external_links_for_scraper(
                                                entreprise_id=entreprise_id,
                                                scraper_id=sid,
                                                client_site_url=cw_url,
                                                external_links=scraper_data.get('external_links'),
                                            )
                                        except Exception as cle:
                                            logger.warning('web_external_links (analyse): %s', cle)
                                        schedule_enrich_external_links_mini_scrape(entreprise_id, sid)
                                        try:
                                            database.patch_entreprise_location_from_scrape(
                                                entreprise_id, scraper_data.get('scraped_location')
                                            )
                                        except Exception as le:
                                            logger.warning('patch_entreprise_location (analyse): %s', le)
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
        analyzer.existing_ids_before = set()

        # SQLite utilise sqlite3.Row (indexable), Postgres peut renvoyer dict/tuple
        for row in rows:
            try:
                if isinstance(row, dict):
                    rid = row.get('id')
                else:
                    # sqlite3.Row et tuple: premier champ = id
                    rid = row[0]
                if rid is not None:
                    analyzer.existing_ids_before.add(int(rid))
            except Exception as e:
                logger.warning(f'Erreur extraction existing_ids_before: {e} (row_type={type(row)})')
                continue
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


@celery.task(
    bind=True,
    time_limit=3600,
    soft_time_limit=3500,
    # Nom stable : les workers chargent toujours analysis_tasks ; évite NotRegistered
    # si le module tasks.full_website_analysis n’était pas importé au démarrage du worker.
    name='tasks.full_website_analysis.full_website_analysis_task',
)
def full_website_analysis_task(
    self,
    url,
    entreprise_id,
    analyse_id=None,
    max_depth=2,
    max_workers=5,
    max_time=240,
    max_pages=40,
    enable_nmap=False,
    use_lighthouse=False,
    enable_technical=True,
    enable_seo=True,
    enable_osint=True,
    enable_pentest=True,
):
    from tasks.full_website_analysis import run_full_website_analysis_impl

    return run_full_website_analysis_impl(
        self,
        url,
        entreprise_id,
        analyse_id=analyse_id,
        max_depth=max_depth,
        max_workers=max_workers,
        max_time=max_time,
        max_pages=max_pages,
        enable_nmap=enable_nmap,
        use_lighthouse=use_lighthouse,
        enable_technical=enable_technical,
        enable_seo=enable_seo,
        enable_osint=enable_osint,
        enable_pentest=enable_pentest,
    )

