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


@api_bp.route('/osint/diagnostic')
@login_required
def osint_diagnostic():
    """
    API: Diagnostic de l'environnement OSINT (WSL + outils).
    Permet de comprendre pourquoi les analyses OSINT peuvent être vides ou partielles.
    
    Returns:
        JSON: wsl_available, wsl_distro, wsl_user, tools_available, tools_missing, message
    """
    try:
        from services.osint_analyzer import OSINTAnalyzer
        analyzer = OSINTAnalyzer()
        return jsonify(analyzer.get_diagnostic())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/pentest/diagnostic')
@login_required
def pentest_diagnostic():
    """
    API: Diagnostic de l'environnement Pentest (WSL + outils).
    Permet de comprendre pourquoi les analyses Pentest peuvent être vides ou partielles.
    
    Returns:
        JSON: wsl_available, wsl_distro, wsl_user, tools_available, tools_missing, message
    """
    try:
        from services.pentest_analyzer import PentestAnalyzer
        analyzer = PentestAnalyzer()
        return jsonify(analyzer.get_diagnostic())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/seo/diagnostic')
@login_required
def seo_diagnostic():
    """
    API: Diagnostic de l'environnement SEO (outils disponibles).
    Permet de comprendre pourquoi les analyses SEO peuvent être limitées.
    
    Returns:
        JSON: execution_mode, tools_available, tools_missing, message
    """
    try:
        from services.seo_analyzer import SEOAnalyzer
        analyzer = SEOAnalyzer()
        return jsonify(analyzer.get_diagnostic())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        security_min (int): Score sécurité minimal (0-100)
        security_max (int): Score sécurité maximal (0-100)
        pentest_min (int): Score pentest (risk_score) minimal (0-100)
        pentest_max (int): Score pentest (risk_score) maximal (0-100)

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
            'search': request.args.get('search'),
            'security_min': request.args.get('security_min', type=int),
            'security_max': request.args.get('security_max', type=int),
            'pentest_min': request.args.get('pentest_min', type=int),
            'pentest_max': request.args.get('pentest_max', type=int),
        }
        # Ne pas retirer les entiers 0 (valides pour min/max)
        def keep_filter(k, v):
            if v is None: return False
            if k in ('security_min', 'security_max', 'pentest_min', 'pentest_max'):
                return 0 <= v <= 100
            return v != ''
        filters = {k: v for k, v in filters.items() if keep_filter(k, v)}
        
        entreprises_list = database.get_entreprises(
            analyse_id=analyse_id, 
            filters=filters if filters else None
        )
        
        # Nettoyer les valeurs NaN pour la sérialisation JSON (double sécurité)
        from utils.helpers import clean_json_dict
        entreprises_list = clean_json_dict(entreprises_list)
        return jsonify(entreprises_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/groupes-entreprises', methods=['GET', 'POST'])
@login_required
def groupes_entreprises():
    """
    API: Gestion de base des groupes d'entreprises.

    GET:
        Query params:
            entreprise_id (int, optionnel): si fourni, ajoute is_member pour cette entreprise.
        Retourne la liste des groupes.

    POST:
        Crée un groupe.
        Corps JSON:
            - nom (str, requis)
            - description (str, optionnel)
            - couleur (str, optionnel)
    """
    try:
        if request.method == 'GET':
            entreprise_id = request.args.get('entreprise_id', type=int)
            groupes = database.get_groupes_entreprises(entreprise_id=entreprise_id)
            return jsonify(groupes)

        data = request.get_json() or {}
        nom = (data.get('nom') or '').strip()
        description = (data.get('description') or '').strip() or None
        couleur = (data.get('couleur') or '').strip() or None

        if not nom:
            return jsonify({'error': 'Le nom du groupe est requis.'}), 400

        groupe = database.create_groupe_entreprise(nom=nom, description=description, couleur=couleur)
        return jsonify(groupe), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/groupes-entreprises/<int:groupe_id>', methods=['DELETE'])
@login_required
def delete_groupe_entreprise(groupe_id):
    """
    API: Supprime un groupe d'entreprises.

    Args:
        groupe_id (int): ID du groupe.
    """
    try:
        database.delete_groupe_entreprise(groupe_id)
        return jsonify({'success': True})
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
            # Utiliser clean_row_dict pour nettoyer les NaN dès la conversion
            entreprise = database.clean_row_dict(dict(row))
            
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
            
            # Nettoyer les valeurs NaN pour la sérialisation JSON (double sécurité)
            from utils.helpers import clean_json_dict
            entreprise = clean_json_dict(entreprise)
            
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


@api_bp.route('/entreprise/<int:entreprise_id>/groupes', methods=['POST'])
@login_required
def add_entreprise_to_groupe(entreprise_id):
    """
    API: Ajoute une entreprise à un groupe.

    Corps JSON:
        - groupe_id (int): ID du groupe cible.
    """
    try:
        data = request.get_json() or {}
        groupe_id = data.get('groupe_id')
        if not groupe_id:
            return jsonify({'error': 'groupe_id est requis'}), 400

        added = database.add_entreprise_to_groupe(entreprise_id, int(groupe_id))
        return jsonify({'success': True, 'added': added})
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).error(f'Erreur dans add_entreprise_to_groupe pour entreprise {entreprise_id}: {e}\n{traceback.format_exc()}')
        return jsonify({'error': 'Erreur lors de l\'ajout au groupe'}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/groupes/<int:groupe_id>', methods=['DELETE'])
@login_required
def remove_entreprise_from_groupe(entreprise_id, groupe_id):
    """
    API: Retire une entreprise d'un groupe.
    """
    try:
        database.remove_entreprise_from_groupe(entreprise_id, groupe_id)
        return jsonify({'success': True})
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).error(f'Erreur dans remove_entreprise_from_groupe pour entreprise {entreprise_id}: {e}\n{traceback.format_exc()}')
        return jsonify({'error': 'Erreur lors du retrait du groupe'}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/recalculate-opportunity', methods=['POST'])
@login_required
def recalculate_opportunity(entreprise_id):
    """
    API: Recalcule le score d'opportunité d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        JSON: Résultat du calcul avec breakdown détaillé
    """
    try:
        result = database.update_opportunity_score(entreprise_id)
        if result:
            return jsonify({
                'success': True,
                'opportunity': result['opportunity'],
                'score': result['score'],
                'breakdown': result['breakdown'],
                'indicators': result['indicators']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Impossible de calculer l\'opportunité'
            }), 500
    except Exception as e:
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


