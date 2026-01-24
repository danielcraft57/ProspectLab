"""
Blueprint pour les routes API principales

Contient toutes les routes API REST pour les entreprises, analyses, etc.
"""

from flask import Blueprint, request, jsonify
from services.database import Database
from services.auth import login_required
import json

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialiser la base de données
database = Database()


@api_bp.route('/statistics')
@login_required
def statistics():
    """
    API: Statistiques globales
    
    Returns:
        JSON: Statistiques de l'application
    """
    try:
        stats = database.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analyses')
@login_required
def analyses():
    """
    API: Liste des analyses
    
    Query params:
        limit (int): Nombre maximum d'analyses à retourner (défaut: 50)
        
    Returns:
        JSON: Liste des analyses
    """
    try:
        limit = int(request.args.get('limit', 50))
        analyses_list = database.get_analyses(limit=limit)
        return jsonify(analyses_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprises')
@login_required
def entreprises():
    """
    API: Liste des entreprises avec filtres
    
    Query params:
        analyse_id (int): Filtrer par ID d'analyse
        secteur (str): Filtrer par secteur
        statut (str): Filtrer par statut
        opportunite (str): Filtrer par opportunité
        favori (bool): Filtrer les favoris
        search (str): Recherche textuelle
        
    Returns:
        JSON: Liste des entreprises
    """
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
        
        entreprises_list = database.get_entreprises(
            analyse_id=analyse_id, 
            filters=filters if filters else None
        )
        return jsonify(entreprises_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>', methods=['GET', 'DELETE'])
@login_required
def entreprise_detail(entreprise_id):
    """
    API: Détails d'une entreprise ou suppression
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Methods:
        GET: Retourne les détails de l'entreprise
        DELETE: Supprime l'entreprise
        
    Returns:
        JSON: Détails de l'entreprise ou confirmation de suppression
    """
    if request.method == 'DELETE':
        try:
            conn = database.get_connection()
            cursor = conn.cursor()
            
            # Récupérer le nom de l'entreprise avant suppression
            database.execute_sql(cursor, 'SELECT nom FROM entreprises WHERE id = ?', (entreprise_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return jsonify({'error': 'Entreprise introuvable'}), 404
            
            # Supprimer l'entreprise
            database.execute_sql(cursor, 'DELETE FROM entreprises WHERE id = ?', (entreprise_id,))
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
        
        database.execute_sql(cursor, 'SELECT * FROM entreprises WHERE id = ?', (entreprise_id,))
        row = cursor.fetchone()
        
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
            
            # Charger les données OpenGraph depuis les tables normalisées
            try:
                entreprise['og_data'] = database.get_og_data(entreprise_id)
            except Exception as og_error:
                # Si erreur lors du chargement des données OG, continuer sans
                import logging
                logging.getLogger(__name__).warning(f'Erreur lors du chargement des données OG pour entreprise {entreprise_id}: {og_error}')
                entreprise['og_data'] = None
            
            conn.close()
            return jsonify(entreprise)
        else:
            conn.close()
            return jsonify({'error': 'Entreprise introuvable'}), 404
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).error(f'Erreur dans entreprise_detail pour entreprise {entreprise_id}: {e}\n{traceback.format_exc()}')
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/tags', methods=['POST', 'PUT', 'DELETE'])
@login_required
def entreprise_tags(entreprise_id):
    """
    API: Gestion des tags d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Methods:
        POST/PUT: Met à jour les tags
        DELETE: Supprime tous les tags
        
    Returns:
        JSON: Tags mis à jour
    """
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


@api_bp.route('/entreprise/<int:entreprise_id>/notes', methods=['POST', 'PUT'])
@login_required
def entreprise_notes(entreprise_id):
    """
    API: Gestion des notes d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Notes mises à jour
    """
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        database.update_entreprise_notes(entreprise_id, notes)
        return jsonify({'success': True, 'notes': notes})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/favori', methods=['POST'])
@login_required
def entreprise_favori(entreprise_id):
    """
    API: Basculer le statut favori d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Nouveau statut favori
    """
    try:
        is_favori = database.toggle_favori(entreprise_id)
        return jsonify({'success': True, 'favori': is_favori})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/secteurs')
@login_required
def secteurs():
    """
    API: Liste des secteurs disponibles
    
    Returns:
        JSON: Liste des secteurs
    """
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        
        database.execute_sql(cursor, '''
            SELECT DISTINCT secteur
            FROM entreprises
            WHERE secteur IS NOT NULL AND secteur != ''
            ORDER BY secteur
        ''')
        
        rows = cursor.fetchall()
        # Gérer les dictionnaires PostgreSQL et les tuples SQLite
        secteurs_list = []
        for row in rows:
            if isinstance(row, dict):
                secteur = row.get('secteur')
            else:
                secteur = row[0] if row else None
            if secteur:
                secteurs_list.append(secteur)
        
        conn.close()
        
        return jsonify(secteurs_list)
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).error(f'Erreur dans secteurs: {e}\n{traceback.format_exc()}')
        return jsonify({'error': str(e)}), 500


