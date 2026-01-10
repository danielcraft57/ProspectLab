"""
Application Flask ProspectLab
Plateforme de prospection et analyse d'entreprises
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

# Ajouter le répertoire au path
sys.path.insert(0, str(Path(__file__).parent))

from config import UPLOAD_FOLDER, EXPORT_FOLDER, ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH
from services.entreprise_analyzer import EntrepriseAnalyzer
from services.unified_scraper import UnifiedScraper

# Configuration des logs via le module centralisé
from services.logging_config import setup_root_logger
import logging

from services.email_analyzer import EmailAnalyzer
from services.email_sender import EmailSender
from services.template_manager import TemplateManager
from services.database import Database
from services.export_manager import ExportManager
from services.osint_analyzer import OSINTAnalyzer
from services.pentest_analyzer import PentestAnalyzer

app = Flask(__name__)

# Configurer les logs de l'application Flask (après création de l'app)
setup_root_logger(app)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['EXPORT_FOLDER'] = str(EXPORT_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialiser SocketIO
# Utiliser threading pour éviter les conflits avec les threads Python standards
# Eventlet ne peut pas basculer entre différents threads, donc on utilise threading
# Ajouter allow_unsafe_werkzeug=True pour éviter les problèmes de socket sur Windows
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False, allow_unsafe_werkzeug=True)

# Dictionnaire pour stocker les scrapers actifs (clé: session_id, valeur: scraper)
active_scrapers = {}
scrapers_lock = threading.Lock()

# Dictionnaire pour stocker les analyses actives (clé: session_id, valeur: dict avec 'stop_flag' et 'thread')
active_analyses = {}
analyses_lock = threading.Lock()

# Dictionnaire pour stocker les analyses OSINT/Pentest actives (clé: url, valeur: dict avec 'stop_flag' et 'thread')
active_osint_analyses = {}
active_pentest_analyses = {}
osint_analyses_lock = threading.Lock()
pentest_analyses_lock = threading.Lock()

# Initialiser les services
template_manager = TemplateManager()
database = Database()
export_manager = ExportManager()


def allowed_file(filename):
    """Vérifie si le fichier a une extension autorisée"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Redirection vers le dashboard (nouvelle page d'accueil)"""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    """Dashboard avec statistiques"""
    return render_template('dashboard.html')


@app.route('/entreprises')
def liste_entreprises():
    """Page de liste des entreprises avec filtres"""
    return render_template('entreprises.html')


@app.route('/entreprise/<int:entreprise_id>')
def entreprise_detail(entreprise_id):
    """Page de détail d'une entreprise"""
    return render_template('entreprise_detail.html', entreprise_id=entreprise_id)


@app.route('/analyses-techniques')
def liste_analyses_techniques():
    """Page de liste des analyses techniques"""
    return render_template('analyses_techniques.html')


@app.route('/analyses-osint')
def liste_analyses_osint():
    """Page de liste des analyses OSINT"""
    return render_template('analyses_osint.html')


@app.route('/analyses-pentest')
def liste_analyses_pentest():
    """Page de liste des analyses Pentest"""
    return render_template('analyses_pentest.html')


@app.route('/carte-entreprises')
def carte_entreprises():
    """Page de visualisation cartographique des entreprises"""
    return render_template('carte_entreprises.html')


@app.route('/analyse-technique/<int:analysis_id>')
def analyse_technique_detail(analysis_id):
    """Page de détail d'une analyse technique"""
    return render_template('analyse_technique_detail.html', analysis_id=analysis_id)


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Upload et prévisualisation d'un fichier Excel (route classique pour compatibilité)"""
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
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Lire le fichier Excel pour prévisualisation
            try:
                # Utiliser la même méthode de nettoyage que pour l'analyse
                analyzer = EntrepriseAnalyzer(excel_file=filepath)
                df = analyzer.load_excel()
                
                # Valider les lignes pour afficher les erreurs
                validation_warnings = []
                for idx, row in df.head(20).iterrows():  # Valider les 20 premières lignes pour la prévisualisation
                    is_valid, errors = analyzer.validate_row(row, idx)
                    if not is_valid:
                        validation_warnings.extend(errors[:3])  # Limiter à 3 erreurs par ligne
                
                preview = df.head(10).to_dict('records')
                columns = list(df.columns)
                
                return render_template('preview.html', 
                                     filename=filename,
                                     preview=preview,
                                     columns=columns,
                                     total_rows=len(df),
                                     validation_warnings=validation_warnings[:10])  # Limiter à 10 avertissements
            except Exception as e:
                flash(f'Erreur lors de la lecture du fichier: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_template('upload.html')


@app.route('/preview/<filename>')
def preview_file(filename):
    """Page de prévisualisation du fichier Excel avant analyse"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            flash('Fichier introuvable', 'error')
            return redirect(url_for('upload_file'))
        
        # Lire le fichier Excel pour prévisualisation
        analyzer = EntrepriseAnalyzer(excel_file=filepath)
        df = analyzer.load_excel()
        
        if df is None or df.empty:
            flash('Erreur lors de la lecture du fichier Excel', 'error')
            return redirect(url_for('upload_file'))
        
        # Valider les lignes pour afficher les erreurs
        validation_warnings = []
        for idx, row in df.head(20).iterrows():  # Valider les 20 premières lignes
            is_valid, errors = analyzer.validate_row(row, idx)
            if not is_valid:
                validation_warnings.extend(errors[:3])  # Limiter à 3 erreurs par ligne
        
        preview = df.head(10).to_dict('records')
        columns = list(df.columns)
        
        return render_template('preview.html', 
                             filename=filename,
                             preview=preview,
                             columns=columns,
                             total_rows=len(df),
                             validation_warnings=validation_warnings[:10])  # Limiter à 10 avertissements
    except Exception as e:
        flash(f'Erreur lors de la lecture du fichier: {str(e)}', 'error')
        return redirect(url_for('upload_file'))


@app.route('/api/upload', methods=['POST'])
def api_upload_file():
    """API: Upload de fichier Excel avec retour JSON"""
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Format de fichier non autorisé. Utilisez .xlsx ou .xls'}), 400
    
    try:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Valider et lire le fichier Excel
        analyzer = EntrepriseAnalyzer(excel_file=filepath)
        df = analyzer.load_excel()
        
        # Valider les lignes pour détecter les erreurs
        validation_warnings = []
        valid_count = 0
        for idx, row in df.head(20).iterrows():  # Valider les 20 premières lignes
            is_valid, errors = analyzer.validate_row(row, idx)
            if is_valid:
                valid_count += 1
            else:
                validation_warnings.extend(errors[:3])
        
        return jsonify({
            'success': True,
            'filename': filename,
            'total_rows': len(df),
            'valid_rows_preview': valid_count,
            'columns': list(df.columns),
            'validation_warnings': validation_warnings[:10]  # Limiter à 10 avertissements
        })
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la lecture du fichier: {str(e)}'}), 400


@socketio.on('start_analysis')
def handle_analysis(data):
    """Gère le démarrage de l'analyse via WebSocket"""
    filename = data.get('filename')
    max_workers = int(data.get('max_workers', 3))
    delay = float(data.get('delay', 2.0))
    enable_osint = data.get('enable_osint', False)
    session_id = request.sid
    
    # Créer un flag d'arrêt pour cette session
    with analyses_lock:
        active_analyses[session_id] = {'stop_flag': threading.Event(), 'thread': None}
    
    def analyze_in_background():
        try:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            if not os.path.exists(filepath):
                safe_emit('analysis_error', {'error': 'Fichier introuvable'}, room=session_id)
                return
            
            safe_emit('analysis_started', {'message': 'Analyse démarrée...'}, room=session_id)
            
            # Créer le fichier de sortie
            output_filename = f"analyzed_{filename}"
            output_path = os.path.join(app.config['EXPORT_FOLDER'], output_filename)
            
            # Récupérer le flag d'arrêt
            stop_flag = None
            with analyses_lock:
                if session_id in active_analyses:
                    stop_flag = active_analyses[session_id]['stop_flag']
            
            # Créer un analyzer avec callback pour les mises à jour
            class ProgressAnalyzer(EntrepriseAnalyzer):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.current_index = 0
                    self.total = 0
                    self.stop_flag = stop_flag
                    self.valid_rows = []  # Stocker les lignes valides
                    self.session_id = session_id  # Stocker le session_id pour safe_emit
                
                def process_all(self):
                    try:
                        df = self.load_excel()
                        if df is None or df.empty:
                            safe_emit('analysis_error', {'error': 'Le fichier Excel est vide ou ne peut pas être lu'}, room=self.session_id)
                            return None
                        
                        # Valider et filtrer les lignes valides
                        validation_errors = []
                        self.valid_rows = []
                        
                        for idx, row in df.iterrows():
                            is_valid, errors = self.validate_row(row, idx)
                            if is_valid:
                                self.valid_rows.append((idx, row))
                            else:
                                validation_errors.extend(errors)
                        
                        # Avertir l'utilisateur des erreurs de validation
                        if validation_errors:
                            error_summary = f"{len(validation_errors)} erreur(s) détectée(s) dans le fichier. Les lignes invalides seront ignorées."
                            safe_emit('analysis_error_item', {
                                'entreprise': 'Validation',
                                'error': error_summary,
                                'details': validation_errors[:10]  # Limiter à 10 erreurs pour éviter la surcharge
                            }, room=self.session_id)
                        
                        if not self.valid_rows:
                            safe_emit('analysis_error', {'error': 'Aucune ligne valide trouvée dans le fichier Excel'}, room=self.session_id)
                            return None
                        
                        self.total = len(self.valid_rows)
                        safe_emit('analysis_progress', {
                            'current': 0,
                            'total': self.total,
                            'percentage': 0,
                            'message': f'Début de l\'analyse de {self.total} entreprises valides (sur {len(df)} lignes totales)...'
                        }, room=self.session_id)
                        
                        results = []
                        # Cache pour stocker les résultats du scraper par URL (accessible depuis scrape_with_callback)
                        scraper_results_cache = {}
                        self.scraper_results_cache = scraper_results_cache  # Rendre accessible depuis les méthodes
                        
                        # Créer l'analyse dans la BDD dès le début pour avoir l'analysis_id
                        import time
                        start_time = time.time()
                        output_filename = Path(self.output_file).name
                        analysis_id = database.save_analysis(
                            filename=Path(self.excel_file).name,
                            output_filename=output_filename,
                            total=self.total,
                            parametres={'max_workers': max_workers, 'delay': delay, 'enable_osint': enable_osint},
                            duree=0  # Sera mis à jour à la fin
                        )
                        
                        # Stocker les IDs existants avant l'import pour détecter les doublons
                        conn_before = database.get_connection()
                        cursor_before = conn_before.cursor()
                        cursor_before.execute('SELECT id FROM entreprises')
                        existing_ids_before = {row['id'] for row in cursor_before.fetchall()}
                        conn_before.close()
                        
                        # Stats thread-safe
                        import threading
                        stats_lock = threading.Lock()
                        stats = {
                            'total': self.total,
                            'inserted': 0,
                            'duplicates': 0,
                            'errors': 0
                        }
                        self.analysis_id = analysis_id
                        self.existing_ids_before = existing_ids_before
                        self.stats = stats
                        self.stats_lock = stats_lock
                        
                        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                            futures = {executor.submit(self.analyze_entreprise_with_progress, row, idx): idx 
                                      for idx, row in self.valid_rows}
                            
                            for future in as_completed(futures):
                                # Vérifier le flag d'arrêt avant chaque traitement
                                if self.stop_flag and self.stop_flag.is_set():
                                    safe_emit('analysis_stopped', {
                                        'message': 'Analyse arrêtée par l\'utilisateur',
                                        'current': self.current_index,
                                        'total': self.total,
                                        'results_count': len(results)
                                    }, room=self.session_id)
                                    # Annuler les futures restantes
                                    for f in futures:
                                        f.cancel()
                                    break
                                
                                idx = futures[future]
                                try:
                                    result = future.result()
                                    results.append(result)
                                    self.current_index += 1
                                    
                                    percentage = int((self.current_index / self.total) * 100)
                                    safe_emit('analysis_progress', {
                                        'current': self.current_index,
                                        'total': self.total,
                                        'percentage': percentage,
                                        'message': f'Analyse de {result.get("name", "entreprise")}... ({self.current_index}/{self.total})',
                                        'current_entreprise': result.get('name', '')
                                    }, room=self.session_id)
                                except Exception as e:
                                    self.current_index += 1
                                    row_name = row.get('name', 'Erreur') if hasattr(row, 'get') else 'Erreur'
                                    results.append({'name': row_name, 'error': str(e)})
                                    safe_emit('analysis_error_item', {
                                        'entreprise': row_name,
                                        'error': str(e)
                                    }, room=self.session_id)
                        
                        # Vérifier si l'analyse a été arrêtée avant de sauvegarder
                        if self.stop_flag and self.stop_flag.is_set():
                            # Sauvegarder les résultats partiels
                            if results:
                                results_df = pd.DataFrame(results)
                                # Reconstruire le DataFrame avec les lignes valides analysées
                                valid_indices = [idx for idx, _ in self.valid_rows[:len(results)]]
                                df_partial = df.loc[valid_indices]
                                final_df = df_partial.merge(results_df, on='name', how='left', suffixes=('', '_new'))
                                
                                original_cols = list(df.columns)
                                new_cols = [col for col in results_df.columns if col not in original_cols]
                                final_df = final_df[original_cols + new_cols]
                                
                                # Sauvegarder le fichier partiel
                                partial_filename = f"analyzed_partial_{output_filename}"
                                partial_path = os.path.join(app.config['EXPORT_FOLDER'], partial_filename)
                                final_df.to_excel(partial_path, index=False)
                                
                                safe_emit('analysis_stopped', {
                                    'message': f'Analyse arrêtée: {len(results)} entreprises analysées sur {self.total}',
                                    'output_file': partial_filename,
                                    'current': self.current_index,
                                    'total': self.total,
                                    'results_count': len(results)
                                }, room=self.session_id)
                            return None
                        
                        # Mettre à jour la durée de l'analyse
                        duration = time.time() - start_time
                        conn_update = database.get_connection()
                        cursor_update = conn_update.cursor()
                        cursor_update.execute('UPDATE analyses SET duree_secondes = ? WHERE id = ?', (duration, analysis_id))
                        conn_update.commit()
                        conn_update.close()
                        
                        # Récupérer les stats finales
                        with stats_lock:
                            final_stats = stats.copy()
                        
                        results_df = pd.DataFrame(results)
                        # Reconstruire le DataFrame avec les lignes valides
                        valid_indices = [idx for idx, _ in self.valid_rows]
                        df_valid = df.loc[valid_indices]
                        final_df = df_valid.merge(results_df, on='name', how='left', suffixes=('', '_new'))
                        
                        original_cols = list(df.columns)
                        new_cols = [col for col in results_df.columns if col not in original_cols]
                        final_df = final_df[original_cols + new_cols]
                        
                        safe_emit('analysis_complete', {
                            'success': True,
                            'message': f'Analyse terminée: {final_stats["inserted"]} nouvelles entreprises, {final_stats["duplicates"]} doublons évités',
                            'output_file': output_filename,
                            'total': len(final_df),
                            'stats': final_stats
                        }, room=self.session_id)
                        return final_df
                    except Exception as e:
                        safe_emit('analysis_error', {'error': f'Erreur lors de la sauvegarde: {str(e)}'}, room=self.session_id)
                        return None
                
                def analyze_entreprise_with_progress(self, row, idx):
                    """Analyse une entreprise avec gestion d'erreurs améliorée"""
                    try:
                        # Stocker le nom de l'entreprise en cours pour les callbacks
                        self.current_entreprise_name = row.get('name', 'Inconnu') if hasattr(row, 'get') else 'Inconnu'
                        self.current_entreprise_url = row.get('website', '') if hasattr(row, 'get') else ''
                        
                        # Modifier scrape_website pour utiliser un callback et stocker les résultats
                        original_scrape = self.scrape_website
                        self.scraper_results_for_save = None  # Variable pour stocker les résultats complets
                        
                        def scrape_with_callback(url, max_pages=3, use_global_scraper=True):
                            if use_global_scraper:
                                try:
                                    from services.unified_scraper import UnifiedScraper
                                    
                                    # Callback pour émettre les événements WebSocket
                                    def scraping_progress(message):
                                        try:
                                            safe_emit('scraping_progress', {
                                                'message': message,
                                                'entreprise': self.current_entreprise_name,
                                                'url': url
                                            }, room=getattr(self, 'session_id', None))
                                        except:
                                            pass
                                    
                                    unified_scraper = UnifiedScraper(
                                        base_url=url,
                                        max_workers=min(5, max_pages),
                                        max_depth=2,
                                        max_time=300,
                                        max_pages=50,  # Limite à 50 pages pour éviter les sites trop volumineux
                                        progress_callback=scraping_progress
                                    )
                                    scraper_results = unified_scraper.scrape()
                                    
                                    # Stocker les résultats complets pour la sauvegarde
                                    self.scraper_results_for_save = scraper_results
                                    if hasattr(self, 'scraper_results_cache'):
                                        self.scraper_results_cache[url] = scraper_results
                                    
                                    # Construire le résultat au format attendu
                                    result = {
                                        'url': url,
                                        'emails': [e.get('email', e) if isinstance(e, dict) else e for e in scraper_results.get('emails', [])],
                                        'people': scraper_results.get('people', []),
                                        'phones': [p.get('phone', p) if isinstance(p, dict) else p for p in scraper_results.get('phones', [])],
                                        'social_media': scraper_results.get('social_links', {}),
                                        'technologies': scraper_results.get('technologies', {}),
                                        'metadata': scraper_results.get('metadata', {})
                                    }
                                    
                                    # Extraire les informations de base du site
                                    response = requests.get(url, headers=self.headers, timeout=10, allow_redirects=True)
                                    response.raise_for_status()
                                    soup = BeautifulSoup(response.text, 'html.parser')
                                    text = soup.get_text()
                                    
                                    result.update({
                                        'description': self.extract_description(soup),
                                        'founded_year': self.extract_founded_year(soup, text),
                                        'sector': self.extract_sector(None, text, soup),
                                        'company_size': self.estimate_company_size(soup, text, None),
                                        'website_age': self.analyze_website_age(soup, text)
                                    })
                                    
                                    return result
                                except Exception:
                                    # En cas d'erreur, continuer avec le scraping classique
                                    pass
                            
                            # Scraping classique (fallback)
                            return original_scrape(url, max_pages, use_global_scraper)
                        
                        # Modifier l'analyse technique pour utiliser un callback
                        original_technical_analyzer = self.technical_analyzer
                        if self.technical_analyzer:
                            # Créer un wrapper pour l'analyse technique avec callback
                            class TechnicalAnalyzerWrapper:
                                def __init__(self, original_analyzer, current_entreprise_name):
                                    self.original = original_analyzer
                                    self.current_entreprise_name = current_entreprise_name
                                
                                def analyze_technical_details(self, url, enable_nmap=False):
                                    # Émettre le début de l'analyse technique
                                    try:
                                        safe_emit('technical_analysis_progress', {
                                            'progress': 10,
                                            'message': 'Initialisation de l\'analyse technique...',
                                            'entreprise': self.current_entreprise_name,
                                            'url': url
                                        })
                                    except:
                                        pass
                                    
                                    # Appeler l'analyse technique originale
                                    try:
                                        result = self.original.analyze_technical_details(url, enable_nmap=enable_nmap)
                                        
                                        # Émettre la fin de l'analyse technique
                                        try:
                                            safe_emit('technical_analysis_progress', {
                                                'progress': 100,
                                                'message': 'Analyse technique terminée',
                                                'entreprise': self.current_entreprise_name,
                                                'url': url
                                            })
                                        except:
                                            pass
                                        
                                        return result
                                    except Exception as e:
                                        # En cas d'erreur, émettre un message d'erreur
                                        try:
                                            safe_emit('technical_analysis_progress', {
                                                'progress': 0,
                                                'message': f'Erreur lors de l\'analyse technique: {str(e)}',
                                                'entreprise': self.current_entreprise_name,
                                                'url': url
                                            })
                                        except:
                                            pass
                                        raise
                            
                            # Remplacer temporairement l'analyseur technique
                            self.technical_analyzer = TechnicalAnalyzerWrapper(self.technical_analyzer, self.current_entreprise_name)
                        
                        # Remplacer temporairement la méthode
                        self.scrape_website = scrape_with_callback
                        
                        result = self.analyze_entreprise(row)
                        
                        # Restaurer les méthodes originales
                        self.scrape_website = original_scrape
                        if original_technical_analyzer:
                            self.technical_analyzer = original_technical_analyzer
                        
                        # Sauvegarder l'entreprise immédiatement après l'analyse
                        if result and not result.get('error'):
                            try:
                                # Préparer les données pour la sauvegarde
                                row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                                # Fusionner avec les résultats de l'analyse
                                row_dict.update(result)
                                
                                # Sauvegarder l'entreprise avec skip_duplicates pour éviter les doublons
                                entreprise_id = database.save_entreprise(
                                    getattr(self, 'analysis_id', None),
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
                                                stats['duplicates'] += 1
                                            else:
                                                stats['inserted'] += 1
                                                existing_ids_before.add(entreprise_id)
                                    else:
                                        if entreprise_id in existing_ids_before:
                                            stats['duplicates'] = stats.get('duplicates', 0) + 1
                                        else:
                                            stats['inserted'] = stats.get('inserted', 0) + 1
                                            existing_ids_before.add(entreprise_id)
                                    
                                    # Sauvegarder les résultats du scraper avec l'ID de l'entreprise
                                    url = row_dict.get('website') or result.get('url')
                                    if url:
                                        # Utiliser scraper_results_for_save qui contient les résultats complets du scraper
                                        scraper_results = getattr(self, 'scraper_results_for_save', None)
                                        
                                        # Si pas disponible, essayer le cache
                                        if not scraper_results:
                                            scraper_results_cache = getattr(self, 'scraper_results_cache', {})
                                            scraper_results = scraper_results_cache.get(url)
                                        
                                        if scraper_results:
                                            try:
                                                db = Database()
                                                db.save_scraper(
                                                    entreprise_id=entreprise_id,
                                                    url=url,
                                                    scraper_type='unified',
                                                    emails=scraper_results.get('emails', []),
                                                    people=scraper_results.get('people', []),
                                                    phones=scraper_results.get('phones', []),
                                                    social_profiles=scraper_results.get('social_links', {}),
                                                    technologies=scraper_results.get('technologies', {}),
                                                    metadata=scraper_results.get('metadata', {}),
                                                    images=scraper_results.get('images', []),
                                                    visited_urls=len(scraper_results.get('visited_urls', [])),
                                                    total_emails=scraper_results.get('total_emails', 0),
                                                    total_people=scraper_results.get('total_people', 0),
                                                    total_phones=scraper_results.get('total_phones', 0),
                                                    total_social_profiles=scraper_results.get('total_social_platforms', 0),
                                                    total_technologies=scraper_results.get('total_technologies', 0),
                                                    total_metadata=len(scraper_results.get('metadata', {}).get('meta_tags', {})),
                                                    total_images=scraper_results.get('total_images', 0),
                                                    duration=scraper_results.get('duration', 0)
                                                )
                                                
                                                # Mettre à jour la fiche entreprise avec le résumé et les images principales
                                                metadata = scraper_results.get('metadata') or {}
                                                if isinstance(metadata, str):
                                                    try:
                                                        metadata = json.loads(metadata)
                                                    except Exception:
                                                        metadata = {}
                                                
                                                icons = metadata.get('icons', {}) if isinstance(metadata, dict) else {}
                                                og_tags = metadata.get('open_graph', {}) if isinstance(metadata, dict) else {}
                                                
                                                resume = scraper_results.get('resume') or None
                                                if isinstance(resume, str) and resume.strip() == '':
                                                    resume = None
                                                
                                                og_image = icons.get('og_image') or icons.get('main_image')
                                                favicon = icons.get('favicon')
                                                logo = icons.get('logo')
                                                
                                                og_data_json = None
                                                if og_tags:
                                                    try:
                                                        og_data_json = json.dumps(og_tags, ensure_ascii=False)
                                                    except Exception:
                                                        og_data_json = None
                                                
                                                conn_update = database.get_connection()
                                                cursor_update = conn_update.cursor()
                                                cursor_update.execute('''
                                                    UPDATE entreprises
                                                    SET
                                                        resume = COALESCE(?, resume),
                                                        og_image = COALESCE(?, og_image),
                                                        favicon = COALESCE(?, favicon),
                                                        logo = COALESCE(?, logo),
                                                        og_data = COALESCE(?, og_data)
                                                    WHERE id = ?
                                                ''', (resume, og_image, favicon, logo, og_data_json, entreprise_id))
                                                conn_update.commit()
                                                conn_update.close()
                                            except Exception as e:
                                                # Log silencieux
                                                pass
                            except Exception as e:
                                # Log silencieux pour éviter les erreurs
                                pass
                        
                        return result
                    except Exception as e:
                        # Retourner un résultat d'erreur plutôt que de faire planter l'analyse
                        return {
                            'name': row.get('name', 'Inconnu') if hasattr(row, 'get') else 'Inconnu',
                            'error': f'Erreur lors de l\'analyse: {str(e)}'
                        }
            
            analyzer = ProgressAnalyzer(
                excel_file=filepath,
                output_file=output_path,
                max_workers=max_workers,
                delay=delay
            )
            
            # Désactiver OSINT si demandé
            if not enable_osint:
                analyzer.osint_analyzer = None
            
            analyzer.process_all()
            
        except Exception as e:
            safe_emit('analysis_error', {'error': str(e)}, room=session_id)
        finally:
            # Nettoyer active_analyses
            with analyses_lock:
                if session_id in active_analyses:
                    del active_analyses[session_id]
    
    # Lancer l'analyse dans un thread séparé
    thread = threading.Thread(target=analyze_in_background)
    thread.daemon = True
    
    # Stocker le thread dans active_analyses
    with analyses_lock:
        if session_id in active_analyses:
            active_analyses[session_id]['thread'] = thread
    
    thread.start()


@socketio.on('stop_analysis')
def handle_stop_analysis():
    """Gère l'arrêt de l'analyse via WebSocket"""
    session_id = request.sid
    
    with analyses_lock:
        if session_id in active_analyses:
            active_analyses[session_id]['stop_flag'].set()
            safe_emit('analysis_stopping', {'message': 'Arrêt de l\'analyse en cours...'})
        else:
            safe_emit('analysis_error', {'error': 'Aucune analyse en cours'})


@socketio.on('stop_analysis')
def handle_stop_analysis():
    """Gère l'arrêt de l'analyse via WebSocket"""
    session_id = request.sid
    
    with analyses_lock:
        if session_id in active_analyses:
            active_analyses[session_id]['stop_flag'].set()
            safe_emit('analysis_stopping', {'message': 'Arrêt de l\'analyse en cours...'})
        else:
            safe_emit('analysis_error', {'error': 'Aucune analyse en cours'})


@app.route('/analyze/<filename>', methods=['POST'])
def analyze_entreprises(filename):
    """Analyse les entreprises du fichier Excel (route HTTP pour compatibilité)"""
    # Rediriger vers WebSocket si possible
    return jsonify({
        'message': 'Utilisez WebSocket pour les mises à jour en temps réel',
        'use_websocket': True
    }), 200


@socketio.on('start_scraping')
def handle_scraping(data):
    """
    Gère le démarrage du scraping d'emails via WebSocket.
    
    Cette fonction est appelée lorsqu'un client WebSocket émet l'événement
    'start_scraping'. Elle lance le scraping en arrière-plan dans un thread
    séparé pour ne pas bloquer le serveur Flask.
    
    Le scraping inclut l'analyse automatique de chaque email trouvé pour
    enrichir les données avec des informations techniques et personnelles.
    
    Args:
        data (dict): Données reçues du client contenant :
            - url (str): URL de départ pour le scraping
            - max_depth (int, optional): Profondeur maximale (défaut: 3)
            - max_workers (int, optional): Nombre de threads (défaut: 5)
            - max_time (int, optional): Temps max en secondes (défaut: 300)
            
    Events émis:
        - scraping_started: Quand le scraping démarre
        - scraping_email_found: Pour chaque email trouvé (avec analyse)
        - scraping_progress: Mises à jour périodiques de progression
        - scraping_complete: Quand le scraping se termine avec succès
        - scraping_stopped: Si le scraping est arrêté manuellement
        - scraping_error: En cas d'erreur
    """
    from flask import request as flask_request
    
    # Récupérer l'ID de session WebSocket pour pouvoir arrêter le scraping
    session_id = flask_request.sid
    
    # Extraire les paramètres du scraping
    url = data.get('url')
    max_depth = int(data.get('max_depth', 3))  # Profondeur de navigation
    max_workers = int(data.get('max_workers', 5))  # Nombre de threads parallèles
    max_time = int(data.get('max_time', 300))  # Durée max en secondes
    
    # Vérifier que l'URL est fournie
    if not url:
        socketio.emit('scraping_error', {'error': 'URL requise'})
        return
    
    def scrape_in_background():
        """
        Fonction exécutée dans un thread séparé pour le scraping.
        
        Cette fonction gère tout le processus de scraping :
        1. Initialise le scraper et l'analyseur d'emails
        2. Définit un callback pour analyser chaque email trouvé
        3. Lance le scraping dans un thread
        4. Envoie des mises à jour de progression
        5. Gère l'arrêt manuel si demandé
        6. Sauvegarde les résultats et émet les événements finaux
        """
        try:
            # Notifier le client que le scraping a démarré
            socketio.emit('scraping_started', {'message': f'Début du scraping de {url}...'})
            
            # Variable pour stocker le scraper (sera définie après)
            scraper = None
            
            # Initialiser l'analyseur d'emails pour enrichir les données
            # Cet analyseur va extraire des infos techniques et personnelles
            email_analyzer = EmailAnalyzer()
            
            # Callback appelé à chaque nouvel email trouvé par le scraper
            def on_email_found(email, source_url):
                """
                Callback exécuté à chaque découverte d'un nouvel email.
                
                Cette fonction est appelée par le scraper dès qu'un email est trouvé.
                Elle analyse immédiatement l'email et envoie les résultats au client
                via WebSocket pour un affichage en temps réel.
                
                Args:
                    email (str): L'adresse email trouvée
                    source_url (str): URL de la page où l'email a été trouvé
                """
                nonlocal scraper
                try:
                    # Compter le nombre total d'emails trouvés jusqu'à présent
                    total = len(scraper.emails) if scraper else 0
                    
                    # Analyser l'email pour extraire des informations enrichies
                    # (format, fournisseur, type, nom, MX, score de risque)
                    analysis = email_analyzer.analyze_email(email, source_url)
                    
                    # Envoyer l'email et son analyse au client via WebSocket
                    safe_emit('scraping_email_found', {
                        'email': email,
                        'source_url': source_url,
                        'total_emails': total,
                        'analysis': analysis  # Analyse complète avec toutes les infos
                    })
                except Exception as e:
                    # En cas d'erreur d'analyse, envoyer quand même l'email sans analyse
                    # pour ne pas perdre l'information
                    try:
                        total = len(scraper.emails) if scraper else 0
                        safe_emit('scraping_email_found', {
                            'email': email,
                            'source_url': source_url,
                            'total_emails': total,
                            'analysis': None  # Pas d'analyse disponible
                        })
                    except:
                        # Si même l'envoi échoue, ignorer silencieusement
                        pass
            
            def on_person_found(person, source_url):
                """Callback appelé à chaque nouvelle personne trouvée"""
                nonlocal scraper
                try:
                    safe_emit('scraping_person_found', {
                        'person': person,
                        'source_url': source_url,
                        'total_people': len(scraper.people) if scraper else 0
                    })
                except Exception:
                    pass
            
            def on_phone_found(phone, source_url):
                """Callback appelé à chaque nouveau téléphone trouvé"""
                nonlocal scraper
                try:
                    safe_emit('scraping_phone_found', {
                        'phone': phone,
                        'source_url': source_url,
                        'total_phones': len(scraper.phones) if scraper else 0
                    })
                except Exception:
                    pass
            
            def on_social_found(platform, url, source_url):
                """Callback appelé à chaque nouveau réseau social trouvé"""
                nonlocal scraper
                try:
                    safe_emit('scraping_social_found', {
                        'platform': platform,
                        'url': url,
                        'source_url': source_url,
                        'total_platforms': len(scraper.social_links) if scraper else 0
                    })
                except Exception:
                    pass
            
            def progress_callback(message):
                """Callback pour les mises à jour de progression"""
                # Envoyer seulement un message de progression simple (sans détails)
                # Les données sont déjà envoyées en temps réel via les callbacks
                try:
                    with scraper.lock:
                        visited = len(scraper.visited_urls)
                        total_emails = len(scraper.emails)
                        total_people = len(scraper.people)
                        total_phones = len(scraper.phones)
                    
                    # Envoyer seulement toutes les 5 pages pour éviter le spam
                    if visited % 5 == 0 or visited == 1:
                        safe_emit('scraping_progress', {
                            'message': f'{visited} page(s) analysée(s)',
                            'visited': visited,
                            'emails': total_emails,
                            'people': total_people,
                            'phones': total_phones
                        })
                except Exception:
                    pass
            
            scraper = UnifiedScraper(
                base_url=url,
                max_workers=max_workers,
                max_depth=max_depth,
                max_time=max_time,
                max_pages=50,  # Limite à 50 pages pour éviter les sites trop volumineux
                progress_callback=progress_callback,
                on_email_found=on_email_found,
                on_person_found=on_person_found,
                on_phone_found=on_phone_found,
                on_social_found=on_social_found
            )
            
            # Enregistrer le scraper comme actif
            with scrapers_lock:
                active_scrapers[session_id] = scraper
            
            # Envoyer des mises à jour périodiques pendant le scraping
            import time
            start_time = time.time()
            
            # Lancer le scraping dans un thread avec monitoring
            scraping_done = threading.Event()
            manual_stop = False
            
            scrape_results = None
            
            def run_scrape():
                nonlocal scraper, scrape_results
                import logging
                logger = logging.getLogger(__name__)
                try:
                    logger.info(f'[APP] Démarrage du scraping pour {url}')
                    scrape_results = scraper.scrape()
                    logger.info('[APP] Scraping terminé avec succès')
                except Exception as e:
                    logger.error(f'[APP] Erreur lors du scraping: {e}', exc_info=True)
                    import traceback
                    traceback.print_exc()
                finally:
                    scraping_done.set()
            
            scrape_thread = threading.Thread(target=run_scrape)
            scrape_thread.daemon = True
            scrape_thread.start()
            
            # Envoyer des mises à jour toutes les 2 secondes
            iteration = 0
            while not scraping_done.is_set():
                iteration += 1
                # Vérifier si le scraping a été arrêté
                with scrapers_lock:
                    if session_id not in active_scrapers:
                        # Le scraping a été arrêté manuellement
                        scraper.should_stop = True
                        manual_stop = True
                        break
                
                if iteration % 5 == 0:  # Log toutes les 10 secondes
                    pass
                
                time.sleep(2)
            
            scrape_thread.join(timeout=30)
            if scrape_thread.is_alive():
                pass
            else:
                pass
            
            # Retirer le scraper de la liste des actifs
            with scrapers_lock:
                active_scrapers.pop(session_id, None)
            
            # Vérifier si c'était un arrêt manuel
            if manual_stop or (scraper.should_stop and not scraping_done.is_set()):
                with scraper.lock:
                    safe_emit('scraping_stopped', {
                        'message': 'Scraping arrêté par l\'utilisateur',
                        'emails': list(scraper.emails),
                            'people': scraper.people,
                            'phones': [{'phone': p, 'page_url': None} for p in scraper.phones],
                        'total_emails': len(scraper.emails),
                            'total_people': len(scraper.people),
                            'total_phones': len(scraper.phones),
                        'visited_urls': len(scraper.visited_urls)
                    })
                return
            
            # Utiliser les résultats du scraping
            if scrape_results:
                results = scrape_results
            else:
                # Fallback si les résultats ne sont pas disponibles
                with scraper.lock:
                    results = {
                        'emails': list(scraper.emails),
                                'people': scraper.people,
                                'phones': [{'phone': p, 'page_url': None} for p in scraper.phones],
                                'social_links': scraper.social_links,
                                'technologies': scraper.technologies,
                                'metadata': scraper.metadata,
                        'visited_urls': list(scraper.visited_urls),
                                'duration': time.time() - start_time,
                                'total_emails': len(scraper.emails),
                                'total_people': len(scraper.people),
                                'total_phones': len(scraper.phones),
                                'total_social_platforms': len(scraper.social_links),
                        'total_technologies': sum(len(v) if isinstance(v, list) else 1 for v in scraper.technologies.values()),
                        # Générer un résumé même dans le fallback
                        'resume': scraper.generate_company_summary() if hasattr(scraper, 'generate_company_summary') else ''
                    }
            
            # Sauvegarder le scraper et mettre à jour l'entreprise si entreprise_id est fourni
            entreprise_id = data.get('entreprise_id')
            if entreprise_id:
                try:
                    db = Database()
                    scraper_id = db.save_scraper(
                        entreprise_id=entreprise_id,
                        url=url,
                        scraper_type='unified',
                        emails=results.get('emails', []),
                        people=results.get('people', []),
                        phones=results.get('phones', []),
                        social_profiles=results.get('social_links', {}),
                        technologies=results.get('technologies', {}),
                        metadata=results.get('metadata', {}),
                        images=results.get('images', []),  # Images extraites depuis les balises <img>
                        visited_urls=len(results.get('visited_urls', [])),
                        total_emails=results.get('total_emails', 0),
                        total_people=results.get('total_people', 0),
                        total_phones=results.get('total_phones', 0),
                        total_social_profiles=results.get('total_social_platforms', 0),
                        total_technologies=results.get('total_technologies', 0),
                        total_metadata=len(results.get('metadata', {}).get('meta_tags', {})),
                        total_images=results.get('total_images', 0),
                        duration=results.get('duration', 0)
                    )
                    
                    # Mettre à jour la fiche entreprise avec le résumé et les images principales
                    metadata = results.get('metadata') or {}
                    # Désérialiser si besoin
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except Exception:
                            metadata = {}
                    
                    icons = metadata.get('icons', {}) if isinstance(metadata, dict) else {}
                    og_tags = metadata.get('open_graph', {}) if isinstance(metadata, dict) else {}
                    
                    resume = results.get('resume') or None
                    if isinstance(resume, str) and resume.strip() == '':
                        resume = None
                    
                    og_image = icons.get('og_image') or icons.get('main_image')
                    favicon = icons.get('favicon')
                    logo = icons.get('logo')
                    
                    og_data_json = None
                    if og_tags:
                        try:
                            og_data_json = json.dumps(og_tags, ensure_ascii=False)
                        except Exception:
                            og_data_json = None
                    
                    conn_update = db.get_connection()
                    cursor_update = conn_update.cursor()
                    cursor_update.execute('''
                        UPDATE entreprises
                        SET 
                            resume = COALESCE(?, resume),
                            og_image = COALESCE(?, og_image),
                            favicon = COALESCE(?, favicon),
                            logo = COALESCE(?, logo),
                            og_data = COALESCE(?, og_data)
                        WHERE id = ?
                    ''', (resume, og_image, favicon, logo, og_data_json, entreprise_id))
                    conn_update.commit()
                    conn_update.close()
                except Exception as e:
                    import traceback
                    traceback.print_exc()
            
            safe_emit('scraping_complete', {
                'success': True,
                'emails': results.get('emails', []),
                'people': results.get('people', []),
                'phones': results.get('phones', []),
                'social_links': results.get('social_links', {}),
                'technologies': results.get('technologies', {}),
                'metadata': results.get('metadata', {}),
                'images': results.get('images', []),  # Images extraites depuis les balises <img>
                'total_emails': results.get('total_emails', 0),
                'total_people': results.get('total_people', 0),
                'total_phones': results.get('total_phones', 0),
                'total_social_platforms': results.get('total_social_platforms', 0),
                'total_technologies': results.get('total_technologies', 0),
                'total_images': results.get('total_images', 0),
                'visited_urls': len(results.get('visited_urls', []))
            })
        except Exception as e:
            with scrapers_lock:
                active_scrapers.pop(session_id, None)
            safe_emit('scraping_error', {'error': str(e)})
    
    thread = threading.Thread(target=scrape_in_background)
    thread.daemon = True
    thread.start()


@socketio.on('start_people_scraping')
def handle_start_people_scraping(data):
    """Redirige vers le scraper unifié"""
    handle_scraping(data)

@socketio.on('stop_people_scraping')
def handle_stop_people_scraping():
    """Arrête le scraping en cours"""
    handle_stop_scraping()

@socketio.on('start_phone_scraping')
def handle_start_phone_scraping(data):
    """Redirige vers le scraper unifié"""
    handle_scraping(data)

@socketio.on('start_social_scraping')
def handle_start_social_scraping(data):
    """Redirige vers le scraper unifié"""
    handle_scraping(data)

@socketio.on('start_technology_scraping')
def handle_start_technology_scraping(data):
    """Redirige vers le scraper unifié"""
    handle_scraping(data)

@socketio.on('start_metadata_scraping')
def handle_start_metadata_scraping(data):
    """Redirige vers le scraper unifié"""
    handle_scraping(data)

@socketio.on('stop_scraping')
def handle_stop_scraping():
    """Arrête le scraping en cours pour cette session"""
    from flask import request as flask_request
    session_id = flask_request.sid
    
    with scrapers_lock:
        if session_id in active_scrapers:
            scraper = active_scrapers[session_id]
            scraper.should_stop = True
            # Retirer immédiatement pour éviter les conflits
            del active_scrapers[session_id]
            safe_emit('scraping_stopping', {'message': 'Arrêt du scraping en cours...'})
        else:
            safe_emit('scraping_error', {'error': 'Aucun scraping en cours'})


def safe_emit(event, data, room=None):
    """Émet un événement SocketIO de manière sécurisée"""
    try:
        if room:
            socketio.emit(event, data, room=room)
        else:
            socketio.emit(event, data)
    except Exception as e:
        # Ignorer les erreurs si le client est déconnecté
        pass

@socketio.on('start_technical_analysis')
def handle_technical_analysis(data):
    """Gère le démarrage d'une analyse technique via WebSocket"""
    url = data.get('url')
    enable_nmap = data.get('enable_nmap', False)
    force = data.get('force', False)  # Force la relance même si une analyse existe
    entreprise_id = data.get('entreprise_id')  # ID de l'entreprise si lancé depuis la modale
    
    if not url:
        safe_emit('technical_analysis_error', {'error': 'URL requise'})
        return
    
    def analyze_in_background():
        try:
            from services.technical_analyzer import TechnicalAnalyzer
            
            # Vérifier si une analyse existe déjà
            existing = None
            if not force:
                existing = database.get_technical_analysis_by_url(url)
                if existing:
                    # Si une analyse existe et qu'on a un entreprise_id, mettre à jour le lien
                    if entreprise_id and existing.get('entreprise_id') != entreprise_id:
                        conn = database.get_connection()
                        cursor = conn.cursor()
                        cursor.execute('UPDATE analyses_techniques SET entreprise_id = ? WHERE id = ?', (entreprise_id, existing['id']))
                        conn.commit()
                        conn.close()
                    
                    safe_emit('technical_analysis_exists', {
                        'exists': True,
                        'analysis_id': existing['id'],
                        'url': url,
                        'entreprise_id': entreprise_id,
                        'message': 'Une analyse existe déjà pour cette URL'
                    })
                    # Rediriger quand même vers la page de détail
                    safe_emit('technical_analysis_complete', {
                        'success': True,
                        'message': 'Analyse existante trouvée',
                        'analysis_id': existing['id'],
                        'url': url,
                        'entreprise_id': entreprise_id,
                        'updated': False
                    })
                    return
            
            safe_emit('technical_analysis_progress', {
                'progress': 5,
                'message': 'Initialisation de l\'analyse technique...'
            })
            
            analyzer = TechnicalAnalyzer()
            
            safe_emit('technical_analysis_progress', {
                'progress': 10,
                'message': 'Récupération des informations du serveur...'
            })
            
            # Lancer l'analyse technique
            tech_data = analyzer.analyze_technical_details(url, enable_nmap=enable_nmap)
            
            if tech_data.get('error'):
                safe_emit('technical_analysis_error', {'error': tech_data['error']})
                return
            
            safe_emit('technical_analysis_progress', {
                'progress': 80,
                'message': 'Sauvegarde des résultats...'
            })
            
            # Si une analyse existe déjà, la mettre à jour au lieu d'en créer une nouvelle
            if existing:
                database.update_technical_analysis(existing['id'], tech_data)
                analysis_id = existing['id']
            else:
                # Créer une nouvelle analyse
                conn = database.get_connection()
                cursor = conn.cursor()
                
                # Extraire le domaine
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc or parsed.path.split('/')[0]
                domain_clean = domain.replace('www.', '') if domain else ''
                
                # Préparer les données pour l'insertion
                cursor.execute('''
                    INSERT INTO analyses_techniques (
                        entreprise_id, url, domain, ip_address, server_software,
                        framework, framework_version, cms, cms_version, cms_plugins, hosting_provider,
                        domain_creation_date, domain_updated_date, domain_registrar,
                        ssl_valid, ssl_expiry_date, security_headers, waf, cdn,
                        analytics, seo_meta, performance_metrics, nmap_scan, technical_details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entreprise_id,  # Associer à l'entreprise si fourni
                    url,
                    domain_clean,
                    tech_data.get('ip_address'),
                    tech_data.get('server_software'),
                    tech_data.get('framework'),
                    tech_data.get('framework_version'),
                    tech_data.get('cms'),
                    tech_data.get('cms_version'),
                    json.dumps(tech_data.get('cms_plugins', [])) if tech_data.get('cms_plugins') else None,
                    tech_data.get('hosting_provider'),
                    tech_data.get('domain_creation_date'),
                    tech_data.get('domain_updated_date'),
                    tech_data.get('domain_registrar'),
                    tech_data.get('ssl_valid'),
                    tech_data.get('ssl_expiry_date'),
                    json.dumps(tech_data.get('security_headers', {})) if tech_data.get('security_headers') else None,
                    tech_data.get('waf'),
                    tech_data.get('cdn'),
                    json.dumps(tech_data.get('analytics', [])) if tech_data.get('analytics') else None,
                    json.dumps(tech_data.get('seo_meta', {})) if tech_data.get('seo_meta') else None,
                    json.dumps(tech_data.get('performance_metrics', {})) if tech_data.get('performance_metrics') else None,
                    json.dumps(tech_data.get('nmap_scan', {})) if tech_data.get('nmap_scan') else None,
                    json.dumps(tech_data) if tech_data else None
                ))
                
                analysis_id = cursor.lastrowid
                conn.commit()
                conn.close()
            
            safe_emit('technical_analysis_progress', {
                'progress': 100,
                'message': 'Analyse terminée avec succès !'
            })
            
            safe_emit('technical_analysis_complete', {
                'success': True,
                'message': 'Analyse technique terminée',
                'analysis_id': analysis_id,
                'url': url,
                'entreprise_id': entreprise_id,
                'updated': existing is not None
            })
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            # Utiliser print au lieu de socketio.emit pour les erreurs critiques
            # car le client peut être déconnecté
            try:
                safe_emit('technical_analysis_error', {'error': error_msg})
            except:
                pass
    
    # Stocker l'analyse active pour pouvoir l'arrêter
    analysis_key = f"{entreprise_id}_{url}" if entreprise_id else url
    with analyses_lock:
        stop_flag = threading.Event()
        thread = threading.Thread(target=analyze_in_background)
        thread.daemon = True
        active_analyses[analysis_key] = {'stop_flag': stop_flag, 'thread': thread}
        thread.start()


@socketio.on('stop_technical_analysis')
def handle_stop_technical_analysis(data):
    """Arrête une analyse technique en cours"""
    url = data.get('url')
    entreprise_id = data.get('entreprise_id')
    analysis_key = f"{entreprise_id}_{url}" if entreprise_id else url
    
    if analysis_key and analysis_key in active_analyses:
        with analyses_lock:
            analysis_info = active_analyses.get(analysis_key)
            if analysis_info:
                analysis_info['stop_flag'].set()
                del active_analyses[analysis_key]
                safe_emit('technical_analysis_stopped', {'message': 'Analyse technique arrêtée'})
    else:
        safe_emit('technical_analysis_error', {'error': 'Aucune analyse technique en cours'})


@socketio.on('start_osint_analysis')
def handle_osint_analysis(data):
    """Gère le démarrage d'une analyse OSINT via WebSocket"""
    url = data.get('url')
    entreprise_id = data.get('entreprise_id')
    
    if not url:
        safe_emit('osint_analysis_error', {'error': 'URL requise'})
        return
    
    def analyze_in_background():
        try:
            # Vérifier si une analyse existe déjà
            existing = database.get_osint_analysis_by_url(url)
            if existing:
                # Si une analyse existe et qu'on a un entreprise_id, mettre à jour le lien
                if entreprise_id and existing.get('entreprise_id') != entreprise_id:
                    conn = database.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE analyses_osint SET entreprise_id = ? WHERE id = ?', (entreprise_id, existing['id']))
                    conn.commit()
                    conn.close()
                
                safe_emit('osint_analysis_exists', {
                    'exists': True,
                    'analysis_id': existing['id'],
                    'url': url,
                    'entreprise_id': entreprise_id,
                    'message': 'Une analyse existe déjà pour cette URL'
                })
                # Mettre à jour l'analyse existante
                safe_emit('osint_analysis_progress', {
                    'progress': 5,
                    'message': 'Mise à jour de l\'analyse OSINT existante...'
                })
            else:
                safe_emit('osint_analysis_progress', {
                    'progress': 5,
                    'message': 'Initialisation de l\'analyse OSINT...'
                })
            
            analyzer = OSINTAnalyzer()
            
            # Callback pour mettre à jour la progression
            def progress_update(message):
                safe_emit('osint_analysis_progress', {
                    'progress': 20,
                    'message': message
                })
            
            safe_emit('osint_analysis_progress', {
                'progress': 20,
                'message': 'Découverte de sous-domaines...'
            })
            
            # Récupérer les personnes trouvées par les scrapers
            people_from_scrapers = []
            if entreprise_id:
                try:
                    scrapers = database.get_scrapers_by_entreprise(entreprise_id)
                    for scraper in scrapers:
                        if scraper.get('people'):
                            people_list = scraper['people'] if isinstance(scraper['people'], list) else json.loads(scraper['people'])
                            people_from_scrapers.extend(people_list)
                except Exception as e:
                    pass
            
            # Lancer l'analyse OSINT avec callback de progression et personnes des scrapers
            osint_data = analyzer.analyze_osint(url, progress_callback=progress_update, people_from_scrapers=people_from_scrapers)
            
            # Sauvegarder les personnes enrichies dans la table personnes
            if entreprise_id and osint_data.get('people'):
                try:
                    people_data = osint_data['people']
                    if isinstance(people_data, dict) and 'from_scrapers' in people_data:
                        enriched_people = people_data['from_scrapers']
                    elif isinstance(people_data, dict) and 'people' in people_data:
                        enriched_people = people_data['people']
                    else:
                        enriched_people = []
                    
                    for person in enriched_people:
                        # Extraire prénom et nom
                        full_name = person.get('name', '')
                        name_parts = full_name.split(' ', 1)
                        prenom = name_parts[0] if len(name_parts) > 0 else None
                        nom = name_parts[1] if len(name_parts) > 1 else full_name
                        
                        database.save_personne(
                            entreprise_id=entreprise_id,
                            nom=nom,
                            prenom=prenom,
                            titre=person.get('title'),
                            role=person.get('role'),
                            email=person.get('email'),
                            telephone=person.get('phone'),
                            linkedin_url=person.get('linkedin_url'),
                            linkedin_profile_data=person.get('linkedin_profile_data'),
                            social_profiles=person.get('social_profiles'),
                            osint_data=person,
                            niveau_hierarchique=person.get('niveau_hierarchique'),
                            manager_id=None,  # À déterminer plus tard
                            source='osint_enriched'
                        )
                except Exception as e:
                    pass
            
            if osint_data.get('error'):
                safe_emit('osint_analysis_error', {'error': osint_data['error']})
                return
            
            safe_emit('osint_analysis_progress', {
                'progress': 50,
                'message': 'Récupération des enregistrements DNS...'
            })
            
            safe_emit('osint_analysis_progress', {
                'progress': 70,
                'message': 'Collecte d\'emails et informations WHOIS...'
            })
            
            safe_emit('osint_analysis_progress', {
                'progress': 90,
                'message': 'Sauvegarde des résultats...'
            })
            
            # Sauvegarder ou mettre à jour dans la base de données
            if existing:
                analysis_id = database.update_osint_analysis(existing['id'], osint_data)
            else:
                analysis_id = database.save_osint_analysis(entreprise_id, url, osint_data)
            
            safe_emit('osint_analysis_progress', {
                'progress': 100,
                'message': 'Analyse OSINT terminée !'
            })
            
            safe_emit('osint_analysis_complete', {
                'success': True,
                'analysis_id': analysis_id,
                'url': url,
                'summary': osint_data.get('summary', {}),
                'updated': existing is not None
            })
        
        except Exception as e:
            error_msg = f'Erreur lors de l\'analyse OSINT: {str(e)}'
            safe_emit('osint_analysis_error', {'error': error_msg})
            # Retirer de la liste des analyses actives en cas d'erreur
            with osint_analyses_lock:
                active_osint_analyses.pop(url, None)
    
    # Stocker l'analyse active pour pouvoir l'arrêter
    with osint_analyses_lock:
        stop_flag = threading.Event()
        thread = threading.Thread(target=analyze_in_background)
        thread.daemon = True
        active_osint_analyses[url] = {'stop_flag': stop_flag, 'thread': thread}
        thread.start()
    
    thread.start()


@socketio.on('stop_osint_analysis')
def handle_stop_osint_analysis(data):
    """Arrête une analyse OSINT en cours"""
    url = data.get('url')
    if url and url in active_osint_analyses:
        with osint_analyses_lock:
            analysis_info = active_osint_analyses.get(url)
            if analysis_info:
                analysis_info['stop_flag'].set()
                del active_osint_analyses[url]
                safe_emit('osint_analysis_stopped', {'message': 'Analyse OSINT arrêtée'})
    else:
        safe_emit('osint_analysis_error', {'error': 'Aucune analyse OSINT en cours pour cette URL'})


@socketio.on('start_pentest_analysis')
def handle_pentest_analysis(data):
    """Gère le démarrage d'une analyse Pentest via WebSocket"""
    url = data.get('url')
    options = data.get('options', {})
    entreprise_id = data.get('entreprise_id')
    
    if not url:
        safe_emit('pentest_analysis_error', {'error': 'URL requise'})
        return
    
    def analyze_in_background():
        try:
            # Vérifier si une analyse existe déjà
            existing = database.get_pentest_analysis_by_url(url)
            if existing:
                # Si une analyse existe et qu'on a un entreprise_id, mettre à jour le lien
                if entreprise_id and existing.get('entreprise_id') != entreprise_id:
                    conn = database.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE analyses_pentest SET entreprise_id = ? WHERE id = ?', (entreprise_id, existing['id']))
                    conn.commit()
                    conn.close()
                
                safe_emit('pentest_analysis_exists', {
                    'exists': True,
                    'analysis_id': existing['id'],
                    'url': url,
                    'entreprise_id': entreprise_id,
                    'message': 'Une analyse existe déjà pour cette URL'
                })
                # Mettre à jour l'analyse existante
                safe_emit('pentest_analysis_progress', {
                    'progress': 5,
                    'message': 'Mise à jour de l\'analyse de sécurité existante...'
                })
            else:
                safe_emit('pentest_analysis_progress', {
                    'progress': 5,
                    'message': 'Initialisation de l\'analyse de sécurité...'
                })
            
            analyzer = PentestAnalyzer()
            
            safe_emit('pentest_analysis_progress', {
                'progress': 20,
                'message': 'Scan de vulnérabilités en cours...'
            })
            
            # Lancer l'analyse Pentest
            pentest_data = analyzer.analyze_pentest(url, options)
            
            if pentest_data.get('error'):
                safe_emit('pentest_analysis_error', {'error': pentest_data['error']})
                return
            
            safe_emit('pentest_analysis_progress', {
                'progress': 90,
                'message': 'Sauvegarde des résultats...'
            })
            
            # Sauvegarder ou mettre à jour dans la base de données
            if existing:
                analysis_id = database.update_pentest_analysis(existing['id'], pentest_data)
            else:
                analysis_id = database.save_pentest_analysis(entreprise_id, url, pentest_data)
            
            safe_emit('pentest_analysis_progress', {
                'progress': 100,
                'message': 'Analyse de sécurité terminée !'
            })
            
            safe_emit('pentest_analysis_complete', {
                'success': True,
                'analysis_id': analysis_id,
                'url': url,
                'summary': pentest_data.get('summary', {}),
                'risk_score': pentest_data.get('risk_score', 0),
                'updated': existing is not None
            })
        
        except Exception as e:
            error_msg = f'Erreur lors de l\'analyse Pentest: {str(e)}'
            safe_emit('pentest_analysis_error', {'error': error_msg})
            # Retirer de la liste des analyses actives en cas d'erreur
            with pentest_analyses_lock:
                active_pentest_analyses.pop(url, None)
    
    # Stocker l'analyse active pour pouvoir l'arrêter
    with pentest_analyses_lock:
        stop_flag = threading.Event()
        thread = threading.Thread(target=analyze_in_background)
        thread.daemon = True
        active_pentest_analyses[url] = {'stop_flag': stop_flag, 'thread': thread}
        thread.start()


@socketio.on('stop_pentest_analysis')
def handle_stop_pentest_analysis(data):
    """Arrête une analyse Pentest en cours"""
    url = data.get('url')
    if url and url in active_pentest_analyses:
        with pentest_analyses_lock:
            analysis_info = active_pentest_analyses.get(url)
            if analysis_info:
                analysis_info['stop_flag'].set()
                del active_pentest_analyses[url]
                safe_emit('pentest_analysis_stopped', {'message': 'Analyse Pentest arrêtée'})
    else:
        safe_emit('pentest_analysis_error', {'error': 'Aucune analyse Pentest en cours pour cette URL'})


@app.route('/analyse/scraping')
def analyse_scraping_page():
    """Page d'analyse/scraping unifiée"""
    return render_template('analyse_scraping.html')

@app.route('/scrape-emails', methods=['GET', 'POST'])
def scrape_emails():
    """Scrape les emails d'un site web (route HTTP pour compatibilité)"""
    if request.method == 'POST':
        return jsonify({
            'message': 'Utilisez WebSocket pour les mises à jour en temps réel',
            'use_websocket': True
        }), 200
    
    return render_template('scrape_emails.html')


@app.route('/send-emails', methods=['GET', 'POST'])
def send_emails():
    """Envoi d'emails de prospection"""
    if request.method == 'POST':
        data = request.get_json()
        
        # Récupérer les données
        recipients = data.get('recipients', [])  # Liste de {email, nom, entreprise}
        template_id = data.get('template_id')
        subject = data.get('subject')
        custom_message = data.get('custom_message')
        
        if not recipients:
            return jsonify({'error': 'Aucun destinataire'}), 400
        
        try:
            email_sender = EmailSender()
            
            # Charger le template si fourni
            if template_id:
                template = template_manager.get_template(template_id)
                if not template:
                    return jsonify({'error': 'Template introuvable'}), 404
            
            results = []
            for recipient in recipients:
                # Personnaliser le message
                if template_id and template:
                    message = template_manager.render_template(
                        template_id,
                        recipient.get('nom', ''),
                        recipient.get('entreprise', ''),
                        recipient.get('email', '')
                    )
                elif custom_message:
                    message = custom_message
                else:
                    return jsonify({'error': 'Template ou message requis'}), 400
                
                # Envoyer l'email
                result = email_sender.send_email(
                    to=recipient['email'],
                    subject=subject or template.get('subject', 'Prospection'),
                    body=message,
                    recipient_name=recipient.get('nom', '')
                )
                
                results.append({
                    'email': recipient['email'],
                    'success': result['success'],
                    'message': result.get('message', '')
                })
            
            return jsonify({
                'success': True,
                'results': results,
                'total_sent': sum(1 for r in results if r['success']),
                'total_failed': sum(1 for r in results if not r['success'])
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET: Afficher le formulaire
    templates = template_manager.list_templates()
    return render_template('send_emails.html', templates=templates)


@app.route('/templates', methods=['GET', 'POST'])
def manage_templates():
    """Gestion des modèles de messages"""
    if request.method == 'POST':
        data = request.get_json()
        action = data.get('action')
        
        if action == 'create':
            template = template_manager.create_template(
                name=data.get('name'),
                subject=data.get('subject'),
                content=data.get('content'),
                category=data.get('category', 'cold_email')
            )
            return jsonify({'success': True, 'template': template})
        
        elif action == 'update':
            template = template_manager.update_template(
                template_id=data.get('template_id'),
                name=data.get('name'),
                subject=data.get('subject'),
                content=data.get('content')
            )
            return jsonify({'success': True, 'template': template})
        
        elif action == 'delete':
            template_manager.delete_template(data.get('template_id'))
            return jsonify({'success': True})
    
    # GET: Liste des templates
    templates = template_manager.list_templates()
    return render_template('templates.html', templates=templates)


@app.route('/download/<filename>')
def download_file(filename):
    """Télécharger un fichier exporté"""
    filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        flash('Fichier introuvable', 'error')
        return redirect(url_for('index'))


@app.route('/api/templates')
def api_templates():
    """API: Liste des templates"""
    templates = template_manager.list_templates()
    return jsonify(templates)


@app.route('/api/templates/<template_id>')
def api_template_detail(template_id):
    """API: Détails d'un template"""
    template = template_manager.get_template(template_id)
    if template:
        return jsonify(template)
    return jsonify({'error': 'Template introuvable'}), 404


@app.route('/api/statistics')
def api_statistics():
    """API: Statistiques globales"""
    try:
        stats = database.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyses')
def api_analyses():
    """API: Liste des analyses"""
    try:
        limit = int(request.args.get('limit', 50))
        analyses = database.get_analyses(limit=limit)
        return jsonify(analyses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprises')
def api_entreprises():
    """API: Liste des entreprises avec filtres"""
    try:
        analyse_id = request.args.get('analyse_id', type=int)
        filters = {
            'secteur': request.args.get('secteur'),
            'statut': request.args.get('statut'),
            'opportunite': request.args.get('opportunite'),
            'favori': request.args.get('favori') == 'true',
            'search': request.args.get('search')
        }
        filters = {k: v for k, v in filters.items() if v}
        
        entreprises = database.get_entreprises(analyse_id=analyse_id, filters=filters if filters else None)
        return jsonify(entreprises)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprise/<int:entreprise_id>', methods=['GET', 'DELETE'])
def api_entreprise_detail(entreprise_id):
    """API: Détails d'une entreprise ou suppression"""
    if request.method == 'DELETE':
        try:
            conn = database.get_connection()
            cursor = conn.cursor()
            
            # Récupérer le nom de l'entreprise avant suppression
            cursor.execute('SELECT nom FROM entreprises WHERE id = ?', (entreprise_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return jsonify({'error': 'Entreprise introuvable'}), 404
            
            # Supprimer l'entreprise (les analyses techniques associées seront supprimées en cascade si configuré)
            cursor.execute('DELETE FROM entreprises WHERE id = ?', (entreprise_id,))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Entreprise "{row["nom"]}" supprimée avec succès'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET: Détails de l'entreprise
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM entreprises WHERE id = ?', (entreprise_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            entreprise = dict(row)
            # Parser les tags si c'est une string JSON
            if entreprise.get('tags'):
                try:
                    entreprise['tags'] = json.loads(entreprise['tags']) if isinstance(entreprise['tags'], str) else entreprise['tags']
                except:
                    entreprise['tags'] = []
            else:
                entreprise['tags'] = []
            
            # Parser les données OpenGraph si présentes
            if entreprise.get('og_data'):
                try:
                    entreprise['og_data'] = json.loads(entreprise['og_data']) if isinstance(entreprise['og_data'], str) else entreprise['og_data']
                except:
                    entreprise['og_data'] = None
            
            return jsonify(entreprise)
        else:
            return jsonify({'error': 'Entreprise introuvable'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprise/<int:entreprise_id>/tags', methods=['POST', 'PUT', 'DELETE'])
def api_entreprise_tags(entreprise_id):
    """API: Gestion des tags d'une entreprise"""
    try:
        if request.method == 'POST' or request.method == 'PUT':
            data = request.get_json()
            tags = data.get('tags', [])
            database.update_entreprise_tags(entreprise_id, tags)
            return jsonify({'success': True, 'tags': tags})
        elif request.method == 'DELETE':
            database.update_entreprise_tags(entreprise_id, [])
            return jsonify({'success': True, 'tags': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprise/<int:entreprise_id>/notes', methods=['POST', 'PUT'])
def api_entreprise_notes(entreprise_id):
    """API: Gestion des notes d'une entreprise"""
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        database.update_entreprise_notes(entreprise_id, notes)
        return jsonify({'success': True, 'notes': notes})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprise/<int:entreprise_id>/favori', methods=['POST'])
def api_entreprise_favori(entreprise_id):
    """API: Basculer le statut favori"""
    try:
        is_favori = database.toggle_favori(entreprise_id)
        return jsonify({'success': True, 'favori': is_favori})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/secteurs')
def api_secteurs():
    """API: Liste des secteurs disponibles"""
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT secteur
            FROM entreprises
            WHERE secteur IS NOT NULL AND secteur != ''
            ORDER BY secteur
        ''')
        
        secteurs = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(secteurs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyses-techniques')
def api_analyses_techniques():
    """API: Liste des analyses techniques"""
    try:
        limit = int(request.args.get('limit', 100))
        analyses = database.get_all_technical_analyses(limit=limit)
        return jsonify(analyses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyse-technique/<int:analysis_id>')
def api_analyse_technique_detail(analysis_id):
    """API: Détails d'une analyse technique"""
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT at.*, e.nom as entreprise_nom, e.id as entreprise_id
            FROM analyses_techniques at
            LEFT JOIN entreprises e ON at.entreprise_id = e.id
            WHERE at.id = ?
        ''', (analysis_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            analysis = dict(row)
            # Parser les champs JSON
            for field in ['cms_plugins', 'security_headers', 'analytics', 'seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details']:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            return jsonify(analysis)
        else:
            return jsonify({'error': 'Analyse introuvable'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprise/<int:entreprise_id>/scrapers')
def api_get_scrapers(entreprise_id):
    """Récupère tous les scrapers d'une entreprise"""
    try:
        db = Database()
        scrapers = db.get_scrapers_by_entreprise(entreprise_id)
        # S'assurer que toutes les valeurs sont sérialisables en JSON
        for scraper in scrapers:
            for key, value in list(scraper.items()):
                if value is None:
                    continue
                # Convertir les types non sérialisables
                if isinstance(value, (bytes, bytearray)):
                    scraper[key] = value.decode('utf-8', errors='ignore')
        return jsonify(scrapers)
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        app.logger.error(f"Erreur dans api_get_scrapers: {error_msg}\n{traceback.format_exc()}")
        return jsonify({'error': error_msg}), 500

@app.route('/api/entreprise/<int:entreprise_id>/images')
def api_get_images(entreprise_id):
    """Récupère toutes les images d'une entreprise"""
    try:
        db = Database()
        images = db.get_images_by_entreprise(entreprise_id)
        return jsonify(images)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scraper/<int:scraper_id>/images')
def api_get_scraper_images(scraper_id):
    """Récupère toutes les images d'un scraper"""
    try:
        db = Database()
        images = db.get_images_by_scraper(scraper_id)
        return jsonify(images)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/entreprise/<int:entreprise_id>/personnes')
def api_entreprise_personnes(entreprise_id):
    """API: Liste des personnes d'une entreprise"""
    try:
        personnes = database.get_personnes_by_entreprise(entreprise_id)
        return jsonify(personnes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/entreprise/<int:entreprise_id>/organigramme')
def api_entreprise_organigramme(entreprise_id):
    """API: Organigramme d'une entreprise"""
    try:
        organigramme = database.get_organigramme(entreprise_id)
        return jsonify(organigramme)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scraper', methods=['POST'])
def api_save_scraper():
    """Sauvegarde un scraper"""
    try:
        data = request.get_json()
        entreprise_id = data.get('entreprise_id')
        url = data.get('url')
        scraper_type = data.get('scraper_type')
        emails = data.get('emails', [])
        people = data.get('people', [])
        visited_urls = data.get('visited_urls', 0)
        total_emails = data.get('total_emails', 0)
        total_people = data.get('total_people', 0)
        duration = data.get('duration', 0)
        
        if not url or not scraper_type:
            return jsonify({'error': 'URL et type de scraper requis'}), 400
        
        db = Database()
        scraper_id = db.save_scraper(
            entreprise_id=entreprise_id,
            url=url,
            scraper_type=scraper_type,
            emails=emails,
            people=people,
            visited_urls=visited_urls,
            total_emails=total_emails,
            total_people=total_people,
            duration=duration
        )
        
        return jsonify({'success': True, 'scraper_id': scraper_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/entreprise/<int:entreprise_id>/analyse-technique')
def api_entreprise_technical_analysis(entreprise_id):
    """API: Analyse technique d'une entreprise"""
    try:
        db = Database()
        analysis = db.get_technical_analysis(entreprise_id)
        if analysis:
            return jsonify(analysis)
        else:
            return jsonify({'error': 'Aucune analyse technique trouvée'}), 404
    except Exception as e:
        import traceback
        app.logger.error(f"Erreur dans api_entreprise_technical_analysis: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprise/<int:entreprise_id>/analyse-osint')
def api_entreprise_osint_analysis(entreprise_id):
    """API: Analyse OSINT d'une entreprise"""
    try:
        db = Database()
        analysis = db.get_osint_analysis_by_entreprise(entreprise_id)
        if analysis:
            return jsonify(analysis)
        else:
            return jsonify({'error': 'Aucune analyse OSINT trouvée'}), 404
    except Exception as e:
        import traceback
        app.logger.error(f"Erreur dans api_entreprise_osint_analysis: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprise/<int:entreprise_id>/analyse-pentest')
def api_entreprise_pentest_analysis(entreprise_id):
    """API: Analyse Pentest d'une entreprise"""
    try:
        db = Database()
        analysis = db.get_pentest_analysis_by_entreprise(entreprise_id)
        if analysis:
            return jsonify(analysis)
        else:
            return jsonify({'error': 'Aucune analyse Pentest trouvée'}), 404
    except Exception as e:
        import traceback
        app.logger.error(f"Erreur dans api_entreprise_pentest_analysis: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyse-technique/<int:analysis_id>', methods=['DELETE'])
def api_delete_technical_analysis(analysis_id):
    """API: Supprime une analyse technique"""
    try:
        deleted = database.delete_technical_analysis(analysis_id)
        if deleted:
            return jsonify({'success': True, 'message': 'Analyse technique supprimée avec succès'})
        else:
            return jsonify({'error': 'Analyse technique introuvable'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyses-osint')
def api_osint_analyses():
    """API: Liste toutes les analyses OSINT"""
    try:
        analyses = database.get_all_osint_analyses()
        return jsonify(analyses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyse-osint/<int:analysis_id>', methods=['GET', 'DELETE'])
def api_osint_analysis_detail(analysis_id):
    """API: Détails ou suppression d'une analyse OSINT"""
    if request.method == 'DELETE':
        try:
            deleted = database.delete_osint_analysis(analysis_id)
            if deleted:
                return jsonify({'success': True, 'message': 'Analyse OSINT supprimée avec succès'})
            else:
                return jsonify({'error': 'Analyse OSINT introuvable'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        try:
            analysis = database.get_osint_analysis(analysis_id)
            if analysis:
                return jsonify(analysis)
            else:
                return jsonify({'error': 'Analyse OSINT introuvable'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/analyses-pentest')
def api_pentest_analyses():
    """API: Liste toutes les analyses Pentest"""
    try:
        analyses = database.get_all_pentest_analyses()
        return jsonify(analyses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyse-pentest/<int:analysis_id>', methods=['GET', 'DELETE'])
def api_pentest_analysis_detail(analysis_id):
    """API: Détails ou suppression d'une analyse Pentest"""
    if request.method == 'DELETE':
        try:
            deleted = database.delete_pentest_analysis(analysis_id)
            if deleted:
                return jsonify({'success': True, 'message': 'Analyse Pentest supprimée avec succès'})
            else:
                return jsonify({'error': 'Analyse Pentest introuvable'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        try:
            analysis = database.get_pentest_analysis(analysis_id)
            if analysis:
                return jsonify(analysis)
            else:
                return jsonify({'error': 'Analyse Pentest introuvable'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/entreprises/nearby')
def api_nearby_entreprises():
    """API: Trouve les entreprises proches d'un point géographique"""
    try:
        latitude = float(request.args.get('latitude', 0))
        longitude = float(request.args.get('longitude', 0))
        radius_km = float(request.args.get('radius_km', 10))
        secteur = request.args.get('secteur')
        limit = int(request.args.get('limit', 50))
        
        if not latitude or not longitude:
            return jsonify({'error': 'Latitude et longitude requises'}), 400
        
        entreprises = database.get_nearby_entreprises(
            latitude, longitude, radius_km, secteur, limit
        )
        
        return jsonify({
            'success': True,
            'count': len(entreprises),
            'entreprises': entreprises
        })
    except ValueError as e:
        return jsonify({'error': 'Coordonnées invalides'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/entreprise/<int:entreprise_id>/competition')
def api_competition_analysis(entreprise_id):
    """API: Analyse de la concurrence locale pour une entreprise"""
    try:
        radius_km = float(request.args.get('radius_km', 10))
        
        analysis = database.get_competition_analysis(entreprise_id, radius_km)
        
        if 'error' in analysis:
            return jsonify(analysis), 404
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/clear', methods=['POST'])
def api_clear_database():
    """API: Vide toute la base de données"""
    try:
        database.clear_all_data()
        return jsonify({'success': True, 'message': 'Base de données vidée avec succès'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/export/<format>')
def export_data(format):
    """Export des données dans différents formats (route classique pour compatibilité)"""
    try:
        # Récupérer les filtres
        filters = {
            'secteur': request.args.get('secteur'),
            'statut': request.args.get('statut'),
            'opportunite': request.args.get('opportunite'),
            'search': request.args.get('search')
        }
        filters = {k: v for k, v in filters.items() if v}
        
        # Récupérer les entreprises depuis la base
        entreprises = database.get_entreprises(filters=filters if filters else None)
        
        if not entreprises:
            return jsonify({'error': 'Aucune donnée à exporter'}), 404
        
        # Convertir en DataFrame
        df = pd.DataFrame(entreprises)
        
        # Export selon le format
        if format == 'csv':
            filepath = export_manager.export_to_csv(df)
        elif format == 'json':
            filepath = export_manager.export_to_json(df)
        elif format == 'pdf':
            filepath = export_manager.export_to_pdf_report(df)
        else:
            return jsonify({'error': 'Format non supporté'}), 400
        
        if filepath:
            return send_file(str(filepath), as_attachment=True)
        else:
            return jsonify({'error': 'Erreur lors de l\'export'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/<format>')
def api_export_data(format):
    """API: Export des données avec retour de fichier via AJAX"""
    try:
        # Récupérer les filtres
        filters = {
            'secteur': request.args.get('secteur'),
            'statut': request.args.get('statut'),
            'opportunite': request.args.get('opportunite'),
            'search': request.args.get('search')
        }
        filters = {k: v for k, v in filters.items() if v}
        
        # Récupérer les entreprises depuis la base
        entreprises = database.get_entreprises(filters=filters if filters else None)
        
        if not entreprises:
            return jsonify({'error': 'Aucune donnée à exporter'}), 404
        
        # Convertir en DataFrame
        df = pd.DataFrame(entreprises)
        
        # Export selon le format
        if format == 'csv':
            filepath = export_manager.export_to_csv(df)
            mimetype = 'text/csv'
        elif format == 'json':
            filepath = export_manager.export_to_json(df)
            mimetype = 'application/json'
        elif format == 'pdf':
            filepath = export_manager.export_to_pdf_report(df)
            mimetype = 'application/pdf'
        else:
            return jsonify({'error': 'Format non supporté'}), 400
        
        if filepath:
            return send_file(str(filepath), as_attachment=True, mimetype=mimetype)
        else:
            return jsonify({'error': 'Erreur lors de l\'export'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Désactiver le reloader pour éviter les problèmes de socket sur Windows
    import signal
    import sys
    
    def signal_handler(sig, frame):
        """Gère Ctrl+C proprement"""
        print('\nArrêt de l\'application...')
        sys.exit(0)
    
    # Enregistrer le gestionnaire de signal pour Windows
    if sys.platform == 'win32':
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    try:
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print('\nArrêt de l\'application...')
        sys.exit(0)

