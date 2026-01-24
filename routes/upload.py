"""
Blueprint pour les routes d'upload et prévisualisation de fichiers
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import pandas as pd
from services.entreprise_analyzer import EntrepriseAnalyzer
from utils.helpers import allowed_file, get_file_path
from config import UPLOAD_FOLDER, CELERY_WORKERS
from utils.template_helpers import render_page
from services.auth import login_required

upload_bp = Blueprint('upload', __name__)


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
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
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
                
                # Debug: logger la valeur de CELERY_WORKERS
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f'Rendu preview.html avec celery_workers={CELERY_WORKERS}')
                
                return render_page('preview.html', 
                                     filename=filename,
                                     preview=preview,
                                     columns=columns,
                                     total_rows=len(df),
                                     validation_warnings=validation_warnings[:10],
                                     celery_workers=CELERY_WORKERS)
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
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
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
        
        # Debug: logger la valeur de CELERY_WORKERS
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'Rendu preview.html avec celery_workers={CELERY_WORKERS}')
        
        return render_page('preview.html', 
                             filename=filename,
                             preview=preview,
                             columns=columns,
                             total_rows=len(df),
                             celery_workers=CELERY_WORKERS,
                             validation_warnings=validation_warnings[:10])
    except pd.errors.EmptyDataError:
        return render_template('error.html',
                             error_title='Fichier vide',
                             error_message='Le fichier Excel est vide.',
                             error_details='Le fichier ne contient aucune donnée. Vérifiez que votre fichier Excel contient bien des données.',
                             back_url=url_for('upload.upload_file'))
    except pd.errors.ExcelFileError as e:
        return render_template('error.html',
                             error_title='Format de fichier invalide',
                             error_message='Le fichier n\'est pas un fichier Excel valide.',
                             error_details=f'Erreur technique: {str(e)}. Assurez-vous que le fichier est bien au format .xlsx ou .xls.',
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
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
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

