"""
Blueprint pour l'API publique
Expose les données d'entreprises et emails pour intégration avec d'autres logiciels
Authentification par token API
"""

from flask import Blueprint, request, jsonify
from services.database import Database
from services.api_auth import api_token_required
import json

api_public_bp = Blueprint('api_public', __name__, url_prefix='/api/public')

# Initialiser la base de données
database = Database()


@api_public_bp.route('/entreprises', methods=['GET'])
@api_token_required
def get_entreprises():
    """
    API publique : Liste des entreprises
    
    Query params:
        limit (int): Nombre maximum de résultats (défaut: 100, max: 1000)
        offset (int): Offset pour la pagination (défaut: 0)
        secteur (str): Filtrer par secteur
        statut (str): Filtrer par statut
        search (str): Recherche textuelle (nom, website)
        
    Returns:
        JSON: Liste des entreprises avec leurs informations
    """
    try:
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        
        filters = {}
        if request.args.get('secteur'):
            filters['secteur'] = request.args.get('secteur')
        if request.args.get('statut'):
            filters['statut'] = request.args.get('statut')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        entreprises = database.get_entreprises(filters=filters if filters else None, limit=limit, offset=offset)
        
        # Nettoyer les valeurs NaN pour la sérialisation JSON
        from utils.helpers import clean_json_dict
        entreprises = clean_json_dict(entreprises)
        
        return jsonify({
            'success': True,
            'count': len(entreprises),
            'limit': limit,
            'offset': offset,
            'data': entreprises
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/entreprises/<int:entreprise_id>', methods=['GET'])
@api_token_required
def get_entreprise(entreprise_id):
    """
    API publique : Détails d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Détails complets de l'entreprise
    """
    try:
        entreprise = database.get_entreprise(entreprise_id)
        
        if not entreprise:
            return jsonify({
                'success': False,
                'error': 'Entreprise introuvable'
            }), 404
        
        # Nettoyer les valeurs NaN pour la sérialisation JSON
        from utils.helpers import clean_json_dict
        entreprise = clean_json_dict(entreprise)
        
        return jsonify({
            'success': True,
            'data': entreprise
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/entreprises/<int:entreprise_id>/emails', methods=['GET'])
@api_token_required
def get_entreprise_emails(entreprise_id):
    """
    API publique : Emails d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Liste des emails associés à l'entreprise
    """
    try:
        # Vérifier que l'entreprise existe
        entreprise = database.get_entreprise(entreprise_id)
        if not entreprise:
            return jsonify({
                'success': False,
                'error': 'Entreprise introuvable'
            }), 404
        
        # Récupérer les emails depuis les scrapers
        scrapers = database.get_scrapers_by_entreprise(entreprise_id)
        emails = []
        
        for scraper in scrapers:
            scraper_emails = database.get_scraper_emails(scraper['id'])
            for email_data in scraper_emails:
                # Éviter les doublons
                if not any(e['email'] == email_data.get('email') for e in emails):
                    emails.append({
                        'email': email_data.get('email'),
                        'nom': email_data.get('name_info'),
                        'page_url': email_data.get('page_url'),
                        'date_scraping': email_data.get('date_scraping')
                    })
        
        return jsonify({
            'success': True,
            'entreprise_id': entreprise_id,
            'count': len(emails),
            'data': emails
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/emails', methods=['GET'])
@api_token_required
def get_all_emails():
    """
    API publique : Liste de tous les emails
    
    Query params:
        limit (int): Nombre maximum de résultats (défaut: 100, max: 1000)
        offset (int): Offset pour la pagination (défaut: 0)
        entreprise_id (int): Filtrer par entreprise
        
    Returns:
        JSON: Liste de tous les emails avec leurs entreprises associées
    """
    try:
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        entreprise_id = request.args.get('entreprise_id', type=int)
        
        conn = database.get_connection()
        conn.row_factory = lambda cursor, row: {
            'email': row[0],
            'nom': row[1],
            'entreprise_id': row[2],
            'entreprise_nom': row[3],
            'page_url': row[4],
            'date_scraping': row[5]
        }
        cursor = conn.cursor()
        
        if entreprise_id:
            cursor.execute('''
                SELECT DISTINCT
                    se.email,
                    se.name_info as nom,
                    e.id as entreprise_id,
                    e.nom as entreprise_nom,
                    se.page_url,
                    se.date_found as date_scraping
                FROM scraper_emails se
                JOIN scrapers s ON se.scraper_id = s.id
                JOIN entreprises e ON s.entreprise_id = e.id
                WHERE e.id = ? AND se.email IS NOT NULL AND se.email != ''
                ORDER BY se.date_found DESC
                LIMIT ? OFFSET ?
            ''', (entreprise_id, limit, offset))
        else:
            cursor.execute('''
                SELECT DISTINCT
                    se.email,
                    se.name_info as nom,
                    e.id as entreprise_id,
                    e.nom as entreprise_nom,
                    se.page_url,
                    se.date_found as date_scraping
                FROM scraper_emails se
                JOIN scrapers s ON se.scraper_id = s.id
                JOIN entreprises e ON s.entreprise_id = e.id
                WHERE se.email IS NOT NULL AND se.email != ''
                ORDER BY se.date_found DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        
        emails = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(emails),
            'limit': limit,
            'offset': offset,
            'data': emails
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/statistics', methods=['GET'])
@api_token_required
def get_statistics():
    """
    API publique : Statistiques globales
    
    Returns:
        JSON: Statistiques de l'application
    """
    try:
        stats = database.get_statistics()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/campagnes', methods=['GET'])
@api_token_required
def get_campagnes():
    """
    API publique : Liste des campagnes email
    
    Query params:
        limit (int): Nombre maximum de résultats (défaut: 100, max: 1000)
        offset (int): Offset pour la pagination (défaut: 0)
        statut (str): Filtrer par statut (draft, running, completed, failed)
        
    Returns:
        JSON: Liste des campagnes avec leurs informations
    """
    try:
        from services.database.campagnes import CampagneManager
        
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        statut = request.args.get('statut')
        
        campagne_manager = CampagneManager()
        campagnes = campagne_manager.list_campagnes(statut=statut, limit=limit, offset=offset)
        
        return jsonify({
            'success': True,
            'count': len(campagnes),
            'limit': limit,
            'offset': offset,
            'data': campagnes
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/campagnes/<int:campagne_id>', methods=['GET'])
@api_token_required
def get_campagne(campagne_id):
    """
    API publique : Détails d'une campagne email
    
    Args:
        campagne_id (int): ID de la campagne
        
    Returns:
        JSON: Détails complets de la campagne
    """
    try:
        from services.database.campagnes import CampagneManager
        
        campagne_manager = CampagneManager()
        campagne = campagne_manager.get_campagne(campagne_id)
        
        if not campagne:
            return jsonify({
                'success': False,
                'error': 'Campagne introuvable'
            }), 404
        
        return jsonify({
            'success': True,
            'data': campagne
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/campagnes/<int:campagne_id>/emails', methods=['GET'])
@api_token_required
def get_campagne_emails(campagne_id):
    """
    API publique : Emails envoyés d'une campagne
    
    Args:
        campagne_id (int): ID de la campagne
        
    Query params:
        limit (int): Nombre maximum de résultats (défaut: 100, max: 1000)
        offset (int): Offset pour la pagination (défaut: 0)
        statut (str): Filtrer par statut (sent, failed)
        
    Returns:
        JSON: Liste des emails envoyés pour cette campagne
    """
    try:
        from services.database.campagnes import CampagneManager
        
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        statut = request.args.get('statut')
        
        campagne_manager = CampagneManager()
        
        # Vérifier que la campagne existe
        campagne = campagne_manager.get_campagne(campagne_id)
        if not campagne:
            return jsonify({
                'success': False,
                'error': 'Campagne introuvable'
            }), 404
        
        # Récupérer les emails
        emails = campagne_manager.get_emails_campagne(campagne_id)
        
        # Filtrer par statut si demandé
        if statut:
            emails = [e for e in emails if e.get('statut') == statut]
        
        # Pagination
        total = len(emails)
        emails = emails[offset:offset+limit]
        
        return jsonify({
            'success': True,
            'campagne_id': campagne_id,
            'count': len(emails),
            'total': total,
            'limit': limit,
            'offset': offset,
            'data': emails
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/campagnes/<int:campagne_id>/statistics', methods=['GET'])
@api_token_required
def get_campagne_statistics(campagne_id):
    """
    API publique : Statistiques de tracking d'une campagne
    
    Args:
        campagne_id (int): ID de la campagne
        
    Returns:
        JSON: Statistiques de tracking (ouvertures, clics)
    """
    try:
        from services.database.campagnes import CampagneManager
        
        campagne_manager = CampagneManager()
        
        # Vérifier que la campagne existe
        campagne = campagne_manager.get_campagne(campagne_id)
        if not campagne:
            return jsonify({
                'success': False,
                'error': 'Campagne introuvable'
            }), 404
        
        # Récupérer les statistiques
        stats = campagne_manager.get_campagne_tracking_stats(campagne_id)
        
        return jsonify({
            'success': True,
            'campagne_id': campagne_id,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

