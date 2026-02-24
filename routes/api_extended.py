"""
Blueprint pour les routes API étendues

Contient les routes API supplémentaires pour les analyses, scrapers, exports, etc.
"""

from flask import Blueprint, request, jsonify
from services.database import Database
from services.export_manager import ExportManager
from services.auth import login_required
import json
import pandas as pd

api_extended_bp = Blueprint('api_extended', __name__, url_prefix='/api')

# Initialiser les services
database = Database()
export_manager = ExportManager()


@api_extended_bp.route('/analyses-techniques')
@login_required
def analyses_techniques():
    """
    API: Liste des analyses techniques
    
    Query params:
        limit (int): Nombre maximum d'analyses (défaut: 100)
        
    Returns:
        JSON: Liste des analyses techniques
    """
    try:
        limit = int(request.args.get('limit', 100))
        analyses = database.get_all_technical_analyses(limit=limit)
        return jsonify(analyses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/analyse-technique/<int:analysis_id>')
@login_required
def analyse_technique_detail(analysis_id):
    """
    API: Détails d'une analyse technique
    
    Args:
        analysis_id (int): ID de l'analyse technique
        
    Returns:
        JSON: Détails de l'analyse technique
    """
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


@api_extended_bp.route('/analyse-technique/<int:analysis_id>', methods=['DELETE'])
@login_required
def delete_technical_analysis(analysis_id):
    """
    API: Supprime une analyse technique
    
    Args:
        analysis_id (int): ID de l'analyse technique
        
    Returns:
        JSON: Confirmation de suppression
    """
    try:
        deleted = database.delete_technical_analysis(analysis_id)
        if deleted:
            return jsonify({'success': True, 'message': 'Analyse technique supprimée avec succès'})
        else:
            return jsonify({'error': 'Analyse technique introuvable'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/analyses-osint')
@login_required
def analyses_osint():
    """
    API: Liste toutes les analyses OSINT
    
    Returns:
        JSON: Liste des analyses OSINT
    """
    try:
        analyses = database.get_all_osint_analyses()
        return jsonify(analyses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/analyse-osint/<int:analysis_id>', methods=['GET', 'DELETE'])
@login_required
def analyse_osint_detail(analysis_id):
    """
    API: Détails ou suppression d'une analyse OSINT
    
    Args:
        analysis_id (int): ID de l'analyse OSINT
        
    Methods:
        GET: Retourne les détails
        DELETE: Supprime l'analyse
        
    Returns:
        JSON: Détails ou confirmation de suppression
    """
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


@api_extended_bp.route('/analyses-pentest')
@login_required
def analyses_pentest():
    """
    API: Liste toutes les analyses Pentest
    
    Returns:
        JSON: Liste des analyses Pentest
    """
    try:
        analyses = database.get_all_pentest_analyses()
        return jsonify(analyses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/analyse-pentest/<int:analysis_id>', methods=['GET', 'DELETE'])
@login_required
def analyse_pentest_detail(analysis_id):
    """
    API: Détails ou suppression d'une analyse Pentest
    
    Args:
        analysis_id (int): ID de l'analyse Pentest
        
    Methods:
        GET: Retourne les détails
        DELETE: Supprime l'analyse
        
    Returns:
        JSON: Détails ou confirmation de suppression
    """
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


@api_extended_bp.route('/analyses-seo')
@login_required
def analyses_seo():
    """
    API: Liste toutes les analyses SEO
    
    Returns:
        JSON: Liste des analyses SEO
    """
    try:
        analyses = database.get_all_seo_analyses()
        return jsonify(analyses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/analyse-seo/<int:analysis_id>', methods=['GET', 'DELETE'])
@login_required
def analyse_seo_detail(analysis_id):
    """
    API: Détails ou suppression d'une analyse SEO
    
    Args:
        analysis_id (int): ID de l'analyse SEO
        
    Methods:
        GET: Retourne les détails
        DELETE: Supprime l'analyse
        
    Returns:
        JSON: Détails ou confirmation de suppression
    """
    if request.method == 'DELETE':
        try:
            # Supprimer l'analyse (les tables normalisées seront supprimées via CASCADE)
            conn = database.get_connection()
            cursor = conn.cursor()
            database.execute_sql(cursor, 'DELETE FROM analyses_seo WHERE id = ?', (analysis_id,))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Analyse SEO supprimée avec succès'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        try:
            analysis = database.get_seo_analysis_by_id(analysis_id)
            if analysis:
                return jsonify(analysis)
            else:
                return jsonify({'error': 'Analyse SEO introuvable'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            analysis = database.get_pentest_analysis(analysis_id)
            if analysis:
                return jsonify(analysis)
            else:
                return jsonify({'error': 'Analyse Pentest introuvable'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/analyse-technique')
@login_required
def entreprise_technical_analysis(entreprise_id):
    """
    API: Analyse technique d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Analyse technique de l'entreprise
    """
    try:
        analysis = database.get_technical_analysis(entreprise_id)
        if analysis:
            return jsonify(analysis)
        else:
            return jsonify({'error': 'Aucune analyse technique trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/analyse-osint')
@login_required
def entreprise_osint_analysis(entreprise_id):
    """
    API: Analyse OSINT d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Analyse OSINT de l'entreprise
    """
    try:
        analysis = database.get_osint_analysis_by_entreprise(entreprise_id)
        if analysis:
            return jsonify(analysis)
        else:
            return jsonify({'error': 'Aucune analyse OSINT trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/analyse-pentest')
@login_required
def entreprise_pentest_analysis(entreprise_id):
    """
    API: Analyse Pentest d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Analyse Pentest de l'entreprise
    """
    try:
        analysis = database.get_pentest_analysis_by_entreprise(entreprise_id)
        if analysis:
            return jsonify(analysis)
        else:
            return jsonify({'error': 'Aucune analyse Pentest trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/analyse-seo')
@login_required
def entreprise_seo_analysis(entreprise_id):
    """
    API: Analyse SEO d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Analyse SEO la plus récente de l'entreprise
    """
    try:
        analyses = database.get_seo_analyses_by_entreprise(entreprise_id, limit=1)
        if analyses:
            # Retourner l'analyse la plus récente
            return jsonify(analyses[0])
        else:
            return jsonify({'error': 'Aucune analyse SEO trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/scrapers')
@login_required
def get_scrapers(entreprise_id):
    """
    API: Récupère tous les scrapers d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Liste des scrapers
    """
    try:
        scrapers = database.get_scrapers_by_entreprise(entreprise_id)
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
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/images')
@login_required
def get_images(entreprise_id):
    """
    API: Récupère toutes les images d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Liste des images
    """
    try:
        images = database.get_images_by_entreprise(entreprise_id)
        return jsonify(images)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/scraper/<int:scraper_id>/images')
@login_required
def get_scraper_images(scraper_id):
    """
    API: Récupère toutes les images d'un scraper
    
    Args:
        scraper_id (int): ID du scraper
        
    Returns:
        JSON: Liste des images
    """
    try:
        images = database.get_images_by_scraper(scraper_id)
        return jsonify(images)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/scraper', methods=['POST'])
@login_required
def save_scraper():
    """
    API: Sauvegarde un scraper
    
    Returns:
        JSON: ID du scraper créé
    """
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
        
        scraper_id = database.save_scraper(
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


@api_extended_bp.route('/entreprise/<int:entreprise_id>/personnes')
@login_required
def entreprise_personnes(entreprise_id):
    """
    API: Liste des personnes d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Liste des personnes
    """
    try:
        personnes = database.get_personnes_by_entreprise(entreprise_id)
        return jsonify(personnes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/organigramme')
@login_required
def entreprise_organigramme(entreprise_id):
    """
    API: Organigramme d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Organigramme de l'entreprise
    """
    try:
        organigramme = database.get_organigramme(entreprise_id)
        return jsonify(organigramme)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_extended_bp.route('/entreprises/nearby')
@login_required
def nearby_entreprises():
    """
    API: Trouve les entreprises proches d'un point géographique
    
    Query params:
        latitude (float): Latitude
        longitude (float): Longitude
        radius_km (float): Rayon en km (défaut: 10)
        secteur (str): Filtrer par secteur (optionnel)
        limit (int): Nombre maximum de résultats (défaut: 50)
        
    Returns:
        JSON: Liste des entreprises proches
    """
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


@api_extended_bp.route('/entreprise/<int:entreprise_id>/competition')
@login_required
def competition_analysis(entreprise_id):
    """
    API: Analyse de la concurrence locale pour une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Query params:
        radius_km (float): Rayon en km (défaut: 10)
        
    Returns:
        JSON: Analyse de la concurrence
    """
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


@api_extended_bp.route('/export/<format>')
@login_required
def export_data(format):
    """
    API: Export des données dans différents formats
    
    Args:
        format (str): Format d'export (csv, json, pdf)
        
    Query params:
        secteur (str): Filtrer par secteur
        statut (str): Filtrer par statut
        opportunite (str): Filtrer par opportunité
        search (str): Recherche textuelle
        
    Returns:
        Response: Fichier exporté ou erreur
    """
    try:
        from flask import send_file
        
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

