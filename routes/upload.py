"""
Blueprint pour les routes d'upload et prévisualisation de fichiers
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import pandas as pd
from services.entreprise_analyzer import EntrepriseAnalyzer
from services.database import Database
from utils.helpers import allowed_file, get_file_path
from config import CELERY_WORKERS
from utils.template_helpers import render_page
from services.auth import login_required
from utils.celery_health import online_workers_count

upload_bp = Blueprint('upload', __name__)


def _row_to_duplicate_keys(row, columns=None):
    """Extrait nom, website, address_1, address_2 depuis une ligne (même logique que la tâche d'analyse)."""
    # Colonnes possibles (nom exact ou variantes) - insensible à la casse via _find_col
    def _find_col(cols, *candidates):
        if not cols:
            return None
        lower_map = {c.lower(): c for c in cols}
        for cand in candidates:
            if cand.lower() in lower_map:
                return lower_map[cand.lower()]
        return None

    cols = list(columns) if columns else (list(row.index) if hasattr(row, 'index') else [])
    name_col = _find_col(cols, 'name', 'nom', 'Name', 'Nom')
    web_col = _find_col(cols, 'website', 'site', 'Site web', 'url', 'Website')
    addr1_col = _find_col(cols, 'address_1', 'address_full', 'adresse')
    addr2_col = _find_col(cols, 'address_2')

    def _val(col):
        if col and col in (row.index if hasattr(row, 'index') else []):
            v = row[col] if hasattr(row, '__getitem__') else row.get(col)
            return str(v).strip() if v is not None and str(v).strip() and str(v).strip().lower() not in ('nan', 'none', 'null', '') else None
        return None

    name = (_val(name_col) or '').strip() or None
    website = _val(web_col) or ''
    address_1 = (str(_val(addr1_col) or '')).strip() or None
    address_2 = (str(_val(addr2_col) or '')).strip() or None
    return name or '', website, address_1, address_2


def _preview_stats_from_df(df, database=None):
    """
    Calcule les statistiques du fichier pour le bloc récapitulatif.
    - Si database est fourni : compte les vraies "nouvelles" entreprises (sans doublon en BDD).
    - Sinon : total = nombre de lignes (comportement de secours).
    
    Args:
        df: DataFrame pandas du fichier Excel
        database: instance Database optionnelle pour détecter les doublons en BDD
        
    Returns:
        dict: file_total, total (nouvelles), with_website, with_phone, with_address, with_category, existing, duplicates_in_file
    """
    if df is None or df.empty:
        return {
            'file_total': 0,
            'total': 0,
            'with_website': 0,
            'with_phone': 0,
            'with_address': 0,
            'with_category': 0,
            'existing': 0,
            'duplicates_in_file': 0,
        }

    total = len(df)

    def filled(series):
        return series.notna() & (series.astype(str).str.strip() != '')

    # Statistiques brutes sur le fichier (toutes les lignes)
    with_website_all = int(filled(df['website']).sum()) if 'website' in df.columns else 0
    with_phone_all = int(filled(df['phone_number']).sum()) if 'phone_number' in df.columns else 0
    with_category_all = int(filled(df['category']).sum()) if 'category' in df.columns else 0
    addr_cols = [c for c in ('address_1', 'address_2', 'address_full') if c in df.columns]
    if addr_cols:
        has_addr = (df[addr_cols].fillna('').astype(str).apply(lambda s: s.str.strip() != '')).any(axis=1)
        with_address = int(has_addr.sum())
    else:
        with_address = 0

    # Statistiques finales (par défaut: basées sur tout le fichier)
    new_count = total
    existing_count = 0
    duplicates_in_file = 0
    with_phone_new = with_phone_all
    with_address_new = with_address
    with_category_new = with_category_all

    if database is not None:
        seen_signatures = set()
        new_count = 0
        # Quand la BDD est disponible, on recalcule aussi les compteurs
        # téléphone / adresse / catégorie uniquement sur les lignes qui
        # seront vraiment analysées (non doublons fichier + BDD).
        with_phone_new = 0
        with_address_new = 0
        with_category_new = 0
        columns = list(df.columns)
        try:
            for idx, row in df.iterrows():
                name, website, address_1, address_2 = _row_to_duplicate_keys(row, columns)
                # Signature pour doublons dans le fichier (alignée avec analysis_tasks)
                from utils.url_utils import normalize_website_domain
                website_norm = normalize_website_domain(website) if website else ''
                if website_norm:
                    sig = ('domain', website_norm)
                else:
                    sig = (name.lower() if name else '', (address_1 or '').lower(), (address_2 or '').lower())
                if sig in seen_signatures and any(sig):
                    duplicates_in_file += 1
                    continue
                seen_signatures.add(sig)

                # Présence de téléphone / adresse / catégorie sur cette ligne
                has_phone = False
                if 'phone_number' in row.index:
                    val = row['phone_number']
                    has_phone = (val is not None) and (str(val).strip() != '') and str(val).strip().lower() not in ('nan', 'none', 'null')

                has_address = False
                if any(c in row.index for c in ('address_1', 'address_2', 'address_full')):
                    addr_vals = []
                    for c in ('address_1', 'address_2', 'address_full'):
                        if c in row.index:
                            addr_vals.append(str(row[c]) if row[c] is not None else '')
                    has_address = any(v.strip() and v.strip().lower() not in ('nan', 'none', 'null') for v in addr_vals)

                has_category = False
                if 'category' in row.index:
                    cat = row['category']
                    has_category = (cat is not None) and (str(cat).strip() != '') and str(cat).strip().lower() not in ('nan', 'none', 'null')

                duplicate_id = database.find_duplicate_entreprise(name, website, address_1, address_2)
                if duplicate_id:
                    existing_count += 1
                else:
                    new_count += 1
                    if has_phone:
                        with_phone_new += 1
                    if has_address:
                        with_address_new += 1
                    if has_category:
                        with_category_new += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Prévisualisation doublons BDD: {e}, fallback total={total}')
            new_count = total
            existing_count = 0
            duplicates_in_file = 0
            # En cas de fallback, revenir aux compteurs basés sur tout le fichier
            with_phone_new = with_phone_all
            with_address_new = with_address
            with_category_new = with_category_all

    return {
        'file_total': int(total),
        'total': int(new_count),
        'with_website': with_website_all,
        # On affiche ici les compteurs pour les lignes réellement analysées (nouvelles)
        'with_phone': int(with_phone_new),
        'with_address': int(with_address_new),
        'with_category': int(with_category_new),
        'existing': existing_count,
        'duplicates_in_file': duplicates_in_file,
    }


@upload_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """
    Upload et prévisualisation d'un fichier Excel (route classique pour compatibilité)
    
    Methods:
        GET: Affiche le formulaire d'upload
        POST: Traite le fichier uploadé et affiche la prévisualisation
        
    Returns:
        str: Template HTML du formulaire ou de la prévisualisation
    """
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Aucun fichier sélectionné', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('Aucun fichier sélectionné', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            upload_dir = current_app.config.get('UPLOAD_FOLDER')
            filepath = os.path.join(upload_dir, filename)
            tmp_path = filepath + '.uploading'
            file.save(tmp_path)
            os.replace(tmp_path, filepath)
            
            # Lire le fichier Excel pour prévisualisation
            try:
                analyzer = EntrepriseAnalyzer(excel_file=filepath)
                df = analyzer.load_excel()
                
                # Valider les lignes pour afficher les erreurs
                validation_warnings = []
                for idx, row in df.head(20).iterrows():
                    is_valid, errors = analyzer.validate_row(row, idx)
                    if not is_valid:
                        validation_warnings.extend(errors[:3])
                
                preview = df.head(10).to_dict('records')
                columns = list(df.columns)
                try:
                    db = Database()
                    preview_stats = _preview_stats_from_df(df, database=db)
                except Exception as e:
                    logger = __import__('logging').getLogger(__name__)
                    logger.warning(f'Preview stats avec BDD: {e}')
                    preview_stats = _preview_stats_from_df(df)

                # Debug: logger la valeur de CELERY_WORKERS
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f'Rendu preview.html avec celery_workers={CELERY_WORKERS}')

                celery_workers_ui = CELERY_WORKERS if int(CELERY_WORKERS or 0) > 0 else 4
                return render_page('preview.html',
                                     filename=filename,
                                     preview=preview,
                                     columns=columns,
                                     total_rows=len(df),
                                     preview_stats=preview_stats,
                                     validation_warnings=validation_warnings[:10],
                                     celery_workers=celery_workers_ui,
                                     celery_nodes_online=online_workers_count())
            except Exception as e:
                flash(f'Erreur lors de la lecture du fichier: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_page('upload.html')


@upload_bp.route('/preview/<filename>')
@login_required
def preview_file(filename):
    """
    Page de prévisualisation du fichier Excel avant analyse
    
    Args:
        filename (str): Nom du fichier à prévisualiser
        
    Returns:
        str: Template HTML de la prévisualisation ou page d'erreur
    """
    try:
        upload_dir = current_app.config.get('UPLOAD_FOLDER')
        filepath = os.path.join(upload_dir, filename)
        
        if not os.path.exists(filepath):
            # Fichier upload introuvable
            return render_template('error.html',
                                 error_title='Fichier introuvable',
                                 error_message=f'Le fichier "{filename}" n\'a pas été trouvé.',
                                 error_details='Le fichier uploadé a peut-être été supprimé automatiquement après 6 heures pour libérer de l\'espace. Veuillez réimporter votre fichier Excel.',
                                 back_url=url_for('upload.upload_file'))
        
        analyzer = EntrepriseAnalyzer(excel_file=filepath)
        df = analyzer.load_excel()
        
        if df is None or df.empty:
            return render_template('error.html',
                                 error_title='Erreur de lecture',
                                 error_message='Impossible de lire le fichier Excel.',
                                 error_details='Le fichier est peut-être corrompu ou dans un format non supporté. Vérifiez que c\'est un fichier Excel valide (.xlsx ou .xls).',
                                 back_url=url_for('upload.upload_file'))
        
        # Valider les lignes
        validation_warnings = []
        for idx, row in df.head(20).iterrows():
            is_valid, errors = analyzer.validate_row(row, idx)
            if not is_valid:
                validation_warnings.extend(errors[:3])
        
        preview = df.head(10).to_dict('records')
        columns = list(df.columns)
        try:
            db = Database()
            preview_stats = _preview_stats_from_df(df, database=db)
        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.warning(f'Preview (GET) stats avec BDD: {e}')
            preview_stats = _preview_stats_from_df(df)

        # Debug: logger la valeur de CELERY_WORKERS
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'Rendu preview.html avec celery_workers={CELERY_WORKERS}')

        celery_workers_ui = CELERY_WORKERS if int(CELERY_WORKERS or 0) > 0 else 4
        return render_page('preview.html',
                             filename=filename,
                             preview=preview,
                             columns=columns,
                             total_rows=len(df),
                             preview_stats=preview_stats,
                             celery_workers=celery_workers_ui,
                             celery_nodes_online=online_workers_count(),
                             validation_warnings=validation_warnings[:10])
    except pd.errors.EmptyDataError:
        return render_template('error.html',
                             error_title='Fichier vide',
                             error_message='Le fichier Excel est vide.',
                             error_details='Le fichier ne contient aucune donnée. Vérifiez que votre fichier Excel contient bien des données.',
                             back_url=url_for('upload.upload_file'))
    except Exception as e:
        return render_template('error.html',
                             error_title='Erreur lors de la lecture',
                             error_message=f'Une erreur est survenue lors de la lecture du fichier: {str(e)}',
                             error_details='Vérifiez que le fichier n\'est pas corrompu et qu\'il est au bon format.',
                             back_url=url_for('upload.upload_file'))


@upload_bp.route('/api/upload', methods=['POST'])
@login_required
def api_upload_file():
    """
    API: Upload de fichier Excel avec retour JSON
    
    Returns:
        JSON: Informations sur le fichier uploadé ou erreur
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            upload_dir = current_app.config.get('UPLOAD_FOLDER')
            filepath = os.path.join(upload_dir, filename)
            tmp_path = filepath + '.uploading'
            file.save(tmp_path)
            os.replace(tmp_path, filepath)
            
            # Lire le fichier Excel pour validation (avec gestion de progression)
            analyzer = EntrepriseAnalyzer(excel_file=filepath)
            df = analyzer.load_excel()
            
            if df is None or df.empty:
                return jsonify({'error': 'Le fichier Excel est vide ou ne peut pas être lu'}), 400
            
            # Compter les lignes valides (optimisé pour les gros fichiers)
            valid_rows = 0
            total_rows = len(df)
            validation_warnings = []
            
            # Valider par batch pour éviter de bloquer trop longtemps
            batch_size = min(100, total_rows)
            for batch_start in range(0, total_rows, batch_size):
                batch_end = min(batch_start + batch_size, total_rows)
                for idx in range(batch_start, batch_end):
                    row = df.iloc[idx]
                    is_valid, errors = analyzer.validate_row(row, idx)
                    if is_valid:
                        valid_rows += 1
                    elif len(validation_warnings) < 10:  # Limiter les warnings
                        validation_warnings.extend(errors[:2])
            
            # Préparer la prévisualisation directement ici pour éviter le double traitement
            preview = df.head(10).to_dict('records')
            columns = list(df.columns)
            
            # S'assurer que preview est sérialisable (convertir les NaN en None)
            preview_serializable = []
            for row in preview:
                clean_row = {}
                for key, value in row.items():
                    if pd.isna(value):
                        clean_row[key] = None
                    else:
                        clean_row[key] = value
                preview_serializable.append(clean_row)
            
            response_data = {
                'success': True,
                'filename': filename,
                'total_rows': int(total_rows),
                'valid_rows': int(valid_rows),
                'columns': columns,
                'preview': preview_serializable,
                'validation_warnings': validation_warnings[:10]
            }
            
            return jsonify(response_data)
        except Exception as e:
            return jsonify({'error': f'Erreur lors de la lecture du fichier: {str(e)}'}), 400
    
    return jsonify({'error': 'Format de fichier non autorisé'}), 400


@upload_bp.route('/analyze/<filename>', methods=['POST'])
@login_required
def analyze_entreprises(filename):
    """
    API: Démarre l'analyse d'un fichier (retourne immédiatement, utilise WebSocket pour les mises à jour)
    
    Args:
        filename (str): Nom du fichier à analyser
        
    Returns:
        JSON: Confirmation que l'analyse a démarré
    """
    return jsonify({
        'success': True,
        'message': 'Analyse démarrée. Utilisez WebSocket pour suivre la progression.',
        'use_websocket': True
    }), 200

