"""
Blueprint pour les routes d'upload et prévisualisation de fichiers
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from services.entreprise_analyzer import EntrepriseAnalyzer
from utils.helpers import allowed_file, get_file_path
from config import UPLOAD_FOLDER

upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/upload', methods=['GET', 'POST'])
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
                
                return render_template('preview.html', 
                                     filename=filename,
                                     preview=preview,
                                     columns=columns,
                                     total_rows=len(df),
                                     validation_warnings=validation_warnings[:10])
            except Exception as e:
                flash(f'Erreur lors de la lecture du fichier: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_template('upload.html')


@upload_bp.route('/preview/<filename>')
def preview_file(filename):
    """
    Page de prévisualisation du fichier Excel avant analyse
    
    Args:
        filename (str): Nom du fichier à prévisualiser
        
    Returns:
        str: Template HTML de la prévisualisation
    """
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            flash('Fichier introuvable', 'error')
            return redirect(url_for('upload.upload_file'))
        
        analyzer = EntrepriseAnalyzer(excel_file=filepath)
        df = analyzer.load_excel()
        
        if df is None or df.empty:
            flash('Erreur lors de la lecture du fichier Excel', 'error')
            return redirect(url_for('upload.upload_file'))
        
        # Valider les lignes
        validation_warnings = []
        for idx, row in df.head(20).iterrows():
            is_valid, errors = analyzer.validate_row(row, idx)
            if not is_valid:
                validation_warnings.extend(errors[:3])
        
        preview = df.head(10).to_dict('records')
        columns = list(df.columns)
        
        return render_template('preview.html', 
                             filename=filename,
                             preview=preview,
                             columns=columns,
                             total_rows=len(df),
                             validation_warnings=validation_warnings[:10])
    except Exception as e:
        flash(f'Erreur lors de la lecture du fichier: {str(e)}', 'error')
        return redirect(url_for('upload.upload_file'))


@upload_bp.route('/api/upload', methods=['POST'])
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
            
            # Lire le fichier Excel pour validation
            analyzer = EntrepriseAnalyzer(excel_file=filepath)
            df = analyzer.load_excel()
            
            if df is None or df.empty:
                return jsonify({'error': 'Le fichier Excel est vide ou ne peut pas être lu'}), 400
            
            # Compter les lignes valides
            valid_rows = 0
            for idx, row in df.iterrows():
                is_valid, _ = analyzer.validate_row(row, idx)
                if is_valid:
                    valid_rows += 1
            
            return jsonify({
                'success': True,
                'filename': filename,
                'total_rows': len(df),
                'valid_rows': valid_rows,
                'columns': list(df.columns)
            })
        except Exception as e:
            return jsonify({'error': f'Erreur lors de la lecture du fichier: {str(e)}'}), 400
    
    return jsonify({'error': 'Format de fichier non autorisé'}), 400


@upload_bp.route('/analyze/<filename>', methods=['POST'])
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

