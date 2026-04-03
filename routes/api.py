"""
Blueprint pour les routes API principales

Contient toutes les routes API REST pour les entreprises, analyses, etc.
"""

from flask import Blueprint, request, jsonify, session
from services.database import Database
from services.database.entreprises import ENTERPRISE_STATUSES, CRM_PIPELINE_ETAPES, EntrepriseManager
from services.auth import login_required
from utils.helpers import clean_json_dict
import json

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialiser la base de données
database = Database()

def _expand_statut_level(statut: str) -> list[str]:
    """
    Couplage simple (sans migration DB) :
    étendre un niveau Gagné/Perdu/Relance vers une liste de statuts événementiels.
    """
    if not statut:
        return []

    s = str(statut).strip()
    mapping: dict[str, list[str]] = {
        'Gagné': ['Gagné', 'Réponse positive'],
        'Perdu': ['Perdu', 'Réponse négative', 'Bounce', 'Désabonné', 'Ne pas contacter', 'Plainte spam'],
        'Relance': ['Relance', 'Nouveau', 'À qualifier', 'À rappeler'],
    }
    return mapping.get(s, [s])


def _maybe_expand_statut_filter(statut_param):
    if not statut_param:
        return None
    s = str(statut_param).strip()
    if s in ('Gagné', 'Perdu', 'Relance'):
        return _expand_statut_level(s)
    return s


def _parse_entreprise_list_query_filters():
    """
    Lit les query params comme la route GET /entreprises (filtres + analyse_id).
    Retourne (analyse_id, filters) avec filters déjà nettoyé par keep_filter.
    """
    analyse_id = request.args.get('analyse_id', type=int)
    filters = {
        'secteur': request.args.get('secteur'),
        'statut': _maybe_expand_statut_filter(request.args.get('statut')),
        'opportunite': request.args.get('opportunite'),
        'favori': request.args.get('favori') == 'true',
        'search': request.args.get('search'),
        'security_min': request.args.get('security_min', type=int),
        'security_max': request.args.get('security_max', type=int),
        'pentest_min': request.args.get('pentest_min', type=int),
        'pentest_max': request.args.get('pentest_max', type=int),
        'seo_min': request.args.get('seo_min', type=int),
        'seo_max': request.args.get('seo_max', type=int),
        'security_null': request.args.get('security_null'),
        'pentest_null': request.args.get('pentest_null'),
        'seo_null': request.args.get('seo_null'),
        'groupe_id': request.args.get('groupe_id', type=int),
        'no_group': request.args.get('no_group'),
        'has_email': request.args.get('has_email'),
        'cms': request.args.get('cms'),
        'framework': request.args.get('framework'),
        'has_blog': request.args.get('has_blog'),
        'has_form': request.args.get('has_form'),
        'has_tunnel': request.args.get('has_tunnel'),
        'performance_min': request.args.get('performance_min', type=int),
        'performance_max': request.args.get('performance_max', type=int),
        'tags_contains': request.args.get('tags_contains'),
        'tags_any': request.args.get('tags_any'),
        'tags_all': request.args.get('tags_all'),
        'etape_prospection': request.args.get('etape_prospection'),
    }

    def keep_filter(k, v):
        if v is None:
            return False
        if k in ('security_min', 'security_max', 'pentest_min', 'pentest_max', 'seo_min', 'seo_max',
                 'performance_min', 'performance_max'):
            return 0 <= v <= 100
        if k in ('has_email', 'no_group', 'has_blog', 'has_form', 'has_tunnel',
                 'security_null', 'pentest_null', 'seo_null'):
            return str(v).lower() in ('1', 'true', 'yes')
        if k == 'etape_prospection':
            return bool(v and str(v).strip())
        return v != ''

    filters = {k: v for k, v in filters.items() if keep_filter(k, v)}
    return analyse_id, filters


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
    
    Query params:
        days (int, optionnel): nombre de jours à considérer pour les stats temporelles
            (emails, campagnes, prospects gagnés). Exemple: 7, 30, 90.
        offset_days (int, optionnel): décalage de fenêtre pour comparer à la période
            précédente. Exemple avec days=30, offset_days=30 => fenêtre [-60,-30] jours.
    
    Returns:
        JSON: Statistiques de l'application
    """
    try:
        days_param = request.args.get('days')
        offset_days_param = request.args.get('offset_days')
        days = None
        offset_days = 0
        if days_param:
            try:
                days_val = int(days_param)
                if days_val > 0:
                    days = days_val
            except ValueError:
                days = None
        if offset_days_param:
            try:
                offset_val = int(offset_days_param)
                if offset_val > 0:
                    offset_days = offset_val
            except ValueError:
                offset_days = 0

        stats = database.get_statistics(days=days, offset_days=offset_days)
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
        seo_min (int): Score SEO minimal (0-100)
        seo_max (int): Score SEO maximal (0-100)
    
    Returns:
        - Mode legacy (sans pagination): liste simple d'entreprises (compatibilité ascendante)
        - Mode paginé (avec query param page/page_size): objet JSON
          {
              "items": [...],
              "total": <int>,
              "page": <int>,
              "page_size": <int>
          }
    """
    try:
        analyse_id, filters = _parse_entreprise_list_query_filters()

        page = request.args.get('page', type=int)
        page_size = request.args.get('page_size', type=int)
        # include_og=1 pour forcer le chargement des données OG,
        # sinon, en mode paginé, on les désactive par défaut pour accélérer la liste.
        include_og_flag = request.args.get('include_og')
        include_og = True
        if include_og_flag is not None:
            include_og = include_og_flag in ('1', 'true', 'True')
        elif page or page_size:
            include_og = False

        # Mode paginé: on renvoie un objet { items, total, page, page_size }
        if page or page_size:
            page = page or 1
            page_size = page_size or 20
            page = max(page, 1)
            page_size = max(1, min(page_size, 200))
            offset = (page - 1) * page_size

            entreprises_list = database.get_entreprises(
                analyse_id=analyse_id,
                filters=filters if filters else None,
                limit=page_size,
                offset=offset,
                include_og=include_og,
            )

            total = database.count_entreprises(
                analyse_id=analyse_id,
                filters=filters if filters else None,
            )

            from utils.helpers import clean_json_dict
            entreprises_list = clean_json_dict(entreprises_list)

            return jsonify({
                'items': entreprises_list,
                'total': total,
                'page': page,
                'page_size': page_size,
            })

        # Mode legacy: on renvoie la liste brute (avec OG) pour compatibilité
        entreprises_list = database.get_entreprises(
            analyse_id=analyse_id,
            filters=filters if filters else None,
            include_og=True,
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


@api_bp.route('/groupes-entreprises/<int:groupe_id>', methods=['DELETE', 'PUT', 'PATCH'])
@login_required
def delete_groupe_entreprise(groupe_id):
    """
    API: Supprime ou met à jour un groupe d'entreprises.

    Methods:
        DELETE: Supprime le groupe.
        PUT/PATCH: Met à jour le groupe (nom / description / couleur).

    Args:
        groupe_id (int): ID du groupe.
    """
    try:
        if request.method in ('PUT', 'PATCH'):
            data = request.get_json() or {}
            nom = data.get('nom')
            description = data.get('description')
            couleur = data.get('couleur')

            if nom is not None:
                nom = nom.strip()
                if not nom:
                    return jsonify({'error': 'Le nom du groupe ne peut pas être vide.'}), 400

            updated = database.update_groupe_entreprise(
                groupe_id,
                nom=nom,
                description=description,
                couleur=couleur,
            )
            if not updated:
                return jsonify({'error': 'Groupe introuvable'}), 404
            return jsonify(updated)

        # DELETE
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
                'indicators': result['indicators'],
                'score_band': result.get('score_band')
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Impossible de calculer l\'opportunité'
            }), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprises/recalculate-opportunities', methods=['POST'])
@login_required
def recalculate_opportunities_bulk():
    """
    API: Recalcule l'opportunité pour plusieurs entreprises en une seule requête.

    Body:
        { "ids": [1,2,3] }

    Returns:
        JSON: { success, total, ok, failed, results? }
    """
    try:
        data = request.get_json() or {}
        ids = data.get('ids') or []
        if not isinstance(ids, list) or not ids:
            return jsonify({'error': 'ids est requis (liste non vide)'}), 400

        ok = 0
        failed = 0
        results = []
        # On limite le payload de retour (utile UI sans exploser la réponse)
        max_results = 30

        for raw in ids:
            try:
                entreprise_id = int(raw)
            except Exception:
                failed += 1
                continue
            try:
                res = database.update_opportunity_score(entreprise_id)
                if res:
                    ok += 1
                    if len(results) < max_results:
                        results.append({
                            'id': entreprise_id,
                            'opportunity': res.get('opportunity'),
                            'score': res.get('score'),
                            'score_band': res.get('score_band'),
                        })
                else:
                    failed += 1
            except Exception:
                failed += 1

        return jsonify({
            'success': True,
            'total': len(ids),
            'ok': ok,
            'failed': failed,
            'results': results
        })
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


@api_bp.route('/entreprise/<int:entreprise_id>/statut', methods=['POST', 'PUT', 'PATCH'])
@login_required
def entreprise_statut(entreprise_id):
    """
    API: Met à jour le statut d'une entreprise (Gagné, Perdu, etc.)
    Body: { "statut": "Gagné" } (Nouveau, À qualifier, Relance, Gagné, Perdu)
    """
    try:
        data = request.get_json() or {}
        statut = (data.get('statut') or '').strip()
        if not statut:
            return jsonify({'error': 'statut requis'}), 400
        ok = database.update_entreprise_statut(entreprise_id, statut)
        if not ok:
            return jsonify({'error': 'statut invalide'}), 400
        return jsonify({'success': True, 'statut': statut})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/statuts', methods=['GET'])
@login_required
def entreprise_statuts():
    """
    API: Liste des statuts pipeline supportés côté entreprise.
    """
    return jsonify(sorted(ENTERPRISE_STATUSES))


@api_bp.route('/entreprise/pipeline/kanban', methods=['GET'])
@login_required
def entreprise_pipeline_kanban():
    """
    API: Effectifs par statut pour une vue Kanban (optionnellement filtré par analyse).

    Query params:
      - analyse_id (int, optionnel): limite aux entreprises liées à cette analyse.
      - Même filtres optionnels que GET /api/entreprises (secteur, statut, search, scores,
        groupe, tags, segmentation, etc.). Si au moins un filtre est actif, l’agrégation
        utilise la même sous-requête que count_entreprises (y compris filtres sur scores).
    """
    try:
        analyse_id, filters = _parse_entreprise_list_query_filters()
        data = database.get_pipeline_kanban_snapshot(
            analyse_id=analyse_id,
            filters=filters if filters else None,
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/pipeline/kanban-crm', methods=['GET'])
@login_required
def entreprise_pipeline_kanban_crm():
    """
    API: Effectifs par étape de prospection CRM (Kanban dédié, champ etape_prospection).

    Mêmes query params que /entreprise/pipeline/kanban (analyse_id + filtres liste entreprises).
    """
    try:
        analyse_id, filters = _parse_entreprise_list_query_filters()
        data = database.get_crm_kanban_snapshot(
            analyse_id=analyse_id,
            filters=filters if filters else None,
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/crm/etapes', methods=['GET'])
@login_required
def entreprise_crm_etapes():
    """API: Ordre des étapes du pipeline CRM prospection (Kanban)."""
    return jsonify(list(CRM_PIPELINE_ETAPES))


@api_bp.route('/entreprise/<int:entreprise_id>/etape-prospection', methods=['PATCH', 'PUT'])
@login_required
def entreprise_etape_prospection(entreprise_id):
    """
    API: Met à jour l'étape CRM (À prospecter, Contacté, RDV, Proposition, Gagné, Perdu).
    Body: { "etape": "Contacté" }
    """
    try:
        data = request.get_json() or {}
        etape = (data.get('etape') or '').strip()
        if not etape:
            return jsonify({'error': 'etape requis'}), 400
        if etape not in CRM_PIPELINE_ETAPES:
            return jsonify({'error': 'etape invalide'}), 400
        row = database.update_entreprise_etape_prospection(entreprise_id, etape)
        if not row:
            return jsonify({'error': 'entreprise introuvable'}), 404
        return jsonify({'success': True, 'entreprise': row})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/commercial/priority-profiles', methods=['GET'])
@login_required
def commercial_priority_profiles():
    """API: Profils de pondération (SEO / sécu / perf / opportunité) pour la priorité commerciale."""
    try:
        items = database.list_commercial_priority_profiles()
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprises/commercial/top', methods=['GET'])
@login_required
def entreprises_commercial_top():
    """
    API: Top entreprises par score pondéré + ancienneté du dernier touchpoint.

    Mêmes filtres que GET /api/entreprises (y compris etape_prospection).

    Query params:
        profile_id (int, optionnel): charge les poids depuis la table commercial_priority_profiles.
        w_seo, w_secu, w_perf, w_opp (float, optionnels): poids manuels si pas de profile_id.
        priority_min (float, optionnel): seuil minimal sur priority_score.
        limit (int, défaut 50, max 200).
    """
    try:
        analyse_id, filters = _parse_entreprise_list_query_filters()
        profile_id = request.args.get('profile_id', type=int)
        weights = None
        if profile_id:
            prof = database.get_commercial_priority_profile(profile_id)
            if not prof:
                return jsonify({'error': 'Profil introuvable'}), 404
            weights = prof.get('poids')
        else:
            weights = {
                'w_seo': request.args.get('w_seo', type=float),
                'w_secu': request.args.get('w_secu', type=float),
                'w_perf': request.args.get('w_perf', type=float),
                'w_opp': request.args.get('w_opp', type=float),
            }
        priority_min = request.args.get('priority_min', type=float)
        limit = request.args.get('limit', default=50, type=int)
        items = database.get_entreprises_commercial_top(
            analyse_id=analyse_id,
            filters=filters if filters else None,
            weights=weights,
            priority_min=priority_min,
            limit=limit if limit else 50,
        )
        nw = EntrepriseManager._normalize_commercial_weights(weights)
        from utils.helpers import clean_json_dict
        return jsonify(clean_json_dict({
            'success': True,
            'items': items,
            'weights': nw,
            'profile_id': profile_id,
            'limit': max(1, min(int(limit or 50), 200)),
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/touchpoints', methods=['GET', 'POST'])
@login_required
def entreprise_touchpoints(entreprise_id):
    """
    API: Journal des interactions d'une entreprise (touchpoints).

    GET:
      - Query params: limit (defaut 50), offset (defaut 0)
    POST:
      - Body JSON: { canal, sujet, note?, happened_at? }
    """
    try:
        if request.method == 'GET':
            limit = request.args.get('limit', default=50, type=int)
            offset = request.args.get('offset', default=0, type=int)
            items = database.list_entreprise_touchpoints(entreprise_id, limit=limit, offset=offset)
            return jsonify({'success': True, 'items': items, 'count': len(items)})

        data = request.get_json() or {}
        canal = (data.get('canal') or '').strip()
        sujet = (data.get('sujet') or '').strip()
        note = data.get('note')
        happened_at = data.get('happened_at')

        if not canal:
            return jsonify({'error': 'canal requis'}), 400
        if not sujet:
            return jsonify({'error': 'sujet requis'}), 400

        created_by = session.get('user_id')
        item = database.create_entreprise_touchpoint(
            entreprise_id=entreprise_id,
            canal=canal,
            sujet=sujet,
            note=note,
            happened_at=happened_at,
            created_by=created_by,
        )
        return jsonify({'success': True, 'item': item}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/touchpoints/<int:touchpoint_id>', methods=['DELETE'])
@login_required
def entreprise_touchpoint_delete(entreprise_id, touchpoint_id):
    """
    API: Supprime un touchpoint d'entreprise.
    """
    try:
        deleted = database.delete_entreprise_touchpoint(entreprise_id, touchpoint_id)
        if not deleted:
            return jsonify({'error': 'Touchpoint introuvable'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/touchpoints/<int:touchpoint_id>', methods=['PATCH'])
@login_required
def entreprise_touchpoint_patch(entreprise_id, touchpoint_id):
    """
    API: Met à jour un touchpoint d'entreprise.

    Body JSON (PATCH partiel) :
      - canal?: str
      - sujet?: str
      - note?: str | null
      - happened_at?: str (ou format accepté par la DB)
    """
    try:
        data = request.get_json() or {}

        # On distingue "champ absent" (=> pas de modif) de "champ présent et null" (=> pour note, ex: vider).
        kwargs: dict[str, object] = {}
        if 'canal' in data:
            kwargs['canal'] = data.get('canal')
        if 'sujet' in data:
            kwargs['sujet'] = data.get('sujet')
        if 'note' in data:
            kwargs['note'] = data.get('note')
        if 'happened_at' in data:
            kwargs['happened_at'] = data.get('happened_at')

        item = database.update_entreprise_touchpoint(
            entreprise_id=entreprise_id,
            touchpoint_id=touchpoint_id,
            **kwargs,
        )
        if not item:
            return jsonify({'error': 'Touchpoint introuvable'}), 404

        return jsonify({'success': True, 'item': item})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/metric-snapshots', methods=['GET'])
@login_required
def entreprise_metric_snapshots(entreprise_id):
    """
    Historique des snapshots de métriques (après analyse technique ou SEO).

    Query: limit (défaut 30, max 100), source (optionnel : technical | seo).
    """
    try:
        limit = request.args.get('limit', default=30, type=int)
        source = request.args.get('source', type=str)
        items = database.list_entreprise_metric_snapshots(
            entreprise_id,
            limit=limit,
            source=source.strip() if source else None,
        )
        return jsonify(clean_json_dict({'success': True, 'items': items}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/metric-snapshots/compare', methods=['GET'])
@login_required
def entreprise_metric_snapshots_compare(entreprise_id):
    """
    Compare les deux derniers snapshots d’une même source : deltas + alertes (v1).

    Query: source (défaut technical ; ex. seo).
    """
    try:
        source = (request.args.get('source') or 'technical').strip() or 'technical'
        data = database.compare_entreprise_metric_snapshots(entreprise_id, source=source)
        return jsonify(clean_json_dict(data))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/entreprise/<int:entreprise_id>/metric-snapshots/rescan', methods=['POST'])
@login_required
def entreprise_metric_snapshots_rescan(entreprise_id):
    """
    Enfile un re-scan technique et/ou SEO pour alimenter de nouveaux snapshots.

    JSON optionnel : run_technical (défaut true), run_seo (défaut true),
    enable_nmap (défaut false), use_lighthouse (défaut config SEO).
    """
    try:
        from tasks.metric_rescan_tasks import enqueue_metric_rescan_for_entreprise

        data = request.get_json(silent=True) or {}

        def _bool(val, default):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return bool(val)
            s = str(val).strip().lower()
            if s in ('0', 'false', 'no', 'off'):
                return False
            if s in ('1', 'true', 'yes', 'on'):
                return True
            return default

        run_technical = _bool(data.get('run_technical'), True)
        run_seo = _bool(data.get('run_seo'), True)
        enable_nmap = _bool(data.get('enable_nmap'), False)
        use_lighthouse = data.get('use_lighthouse')
        if use_lighthouse is not None:
            use_lighthouse = _bool(use_lighthouse, True)

        if not run_technical and not run_seo:
            return jsonify({'success': False, 'error': 'run_technical_and_run_seo_false'}), 400

        result = enqueue_metric_rescan_for_entreprise(
            entreprise_id,
            run_technical=run_technical,
            run_seo=run_seo,
            enable_nmap=enable_nmap,
            use_lighthouse=use_lighthouse,
        )
        if not result.get('success'):
            err = result.get('error') or 'unknown'
            if err == 'entreprise_not_found':
                return jsonify(clean_json_dict(result)), 404
            if err == 'no_website':
                return jsonify(clean_json_dict(result)), 400
            return jsonify(clean_json_dict(result)), 500

        return jsonify(clean_json_dict(result)), 202
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


@api_bp.route('/opportunites')
@login_required
def opportunites():
    """
    API: Liste des opportunites disponibles

    Returns:
        JSON: Liste des opportunites distinctes presentes en base
    """
    try:
        conn = database.get_connection()
        cursor = conn.cursor()

        database.execute_sql(cursor, '''
            SELECT DISTINCT opportunite
            FROM entreprises
            WHERE opportunite IS NOT NULL AND opportunite != ''
            ORDER BY opportunite
        ''')

        rows = cursor.fetchall()
        opportunites_list = []
        for row in rows:
            if isinstance(row, dict):
                opportunite = row.get('opportunite')
            else:
                opportunite = row[0] if row else None
            if opportunite:
                opportunites_list.append(opportunite)

        conn.close()
        return jsonify(opportunites_list)
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).error(f'Erreur dans opportunites: {e}\n{traceback.format_exc()}')
        return jsonify({'error': str(e)}), 500


