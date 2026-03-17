"""
Blueprint pour l'API publique
Expose les données d'entreprises et emails pour intégration avec d'autres logiciels
Authentification par token API
"""

from flask import Blueprint, request, jsonify
from services.database import Database
from services.api_auth import api_token_required, require_api_permission
import json
from urllib.parse import urlparse

api_public_bp = Blueprint('api_public', __name__, url_prefix='/api/public')

# Initialiser la base de données
database = Database()

def _normalize_url_for_analysis(raw: str) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if not s.startswith(('http://', 'https://')):
        s = f'https://{s}'
    try:
        parsed = urlparse(s)
        if not parsed.scheme or not parsed.netloc:
            return None
    except Exception:
        return None
    return s


def _get_entreprise_id_for_website(database: Database, website: str) -> int | None:
    try:
        return database.find_duplicate_entreprise(nom='', website=website)
    except Exception:
        return None


def _build_website_analysis_report(database: Database, entreprise_id: int, full: bool = False) -> dict:
    entreprise = database.get_entreprise(entreprise_id)

    scrapers = []
    try:
        scrapers = database.get_scrapers_by_entreprise(entreprise_id) or []
    except Exception:
        scrapers = []

    technical = None
    try:
        technical = database.get_technical_analysis(entreprise_id)
    except Exception:
        technical = None

    seo = None
    try:
        seo_list = database.get_seo_analyses_by_entreprise(entreprise_id, limit=1) or []
        seo = seo_list[0] if seo_list else None
    except Exception:
        seo = None

    osint = None
    try:
        osint = database.get_osint_analysis_by_entreprise(entreprise_id)
    except Exception:
        osint = None

    pentest = None
    try:
        pentest = database.get_pentest_analysis_by_entreprise(entreprise_id)
    except Exception:
        pentest = None

    report = {
        'success': True,
        'entreprise_id': entreprise_id,
        'entreprise': entreprise,
        'scraping': {
            'status': 'done' if scrapers else 'never',
            'latest': scrapers[0] if scrapers else None,
        },
        'technical': {
            'status': 'done' if technical else 'never',
            'latest': technical,
        },
        'seo': {
            'status': 'done' if seo else 'never',
            'latest': seo,
        },
        'osint': {
            'status': 'done' if osint else 'never',
            'latest': osint,
        },
        'pentest': {
            'status': 'done' if pentest else 'never',
            'latest': pentest,
        },
    }

    if full:
        report['scraping']['items'] = scrapers
        report['scraping']['count'] = len(scrapers)
    return report


@api_public_bp.route('/entreprises', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
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
@require_api_permission('entreprises')
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
@require_api_permission('entreprises')
@require_api_permission('emails')
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
@require_api_permission('emails')
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
@require_api_permission('statistics')
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


@api_public_bp.route('/website-analysis', methods=['GET', 'POST'])
@api_token_required
@require_api_permission('entreprises')
def public_website_analysis():
    """
    API publique (token) : Analyse d'un site web (par URL).

    GET:
        Query params:
            website (str, requis): URL ou domaine.
            full (bool, optionnel): si true, inclut l'historique des scrapers (volumineux).

    POST:
        Corps JSON:
            - website (str, requis)
            - force (bool, optionnel)
            - full (bool, optionnel)
            - max_depth/max_workers/max_time/max_pages/enable_nmap/use_lighthouse (optionnels)
    """
    if request.method == 'GET':
        website_raw = request.args.get('website', '')
        website = _normalize_url_for_analysis(website_raw)
        if not website:
            return jsonify({'error': 'Paramètre "website" requis (URL ou domaine).'}), 400
        full = str(request.args.get('full', '')).lower() in ('1', 'true', 'yes')

        entreprise_id = _get_entreprise_id_for_website(database, website)
        if not entreprise_id:
            return jsonify({'error': 'Aucun rapport trouvé pour ce site.'}), 404

        report = _build_website_analysis_report(database, entreprise_id, full=full)
        report['website'] = website
        return jsonify(report)

    payload = request.get_json(silent=True) or {}
    website_raw = (payload.get('website') or '').strip()
    website = _normalize_url_for_analysis(website_raw)
    if not website:
        return jsonify({'error': 'Le champ "website" est requis (URL ou domaine).'}), 400

    force = bool(payload.get('force', False))
    full = bool(payload.get('full', False))
    entreprise_id = _get_entreprise_id_for_website(database, website)

    if entreprise_id and not force:
        report = _build_website_analysis_report(database, entreprise_id, full=full)
        report['website'] = website
        return jsonify(report)

    if not entreprise_id:
        entreprise_id = database.save_entreprise(
            analyse_id=None,
            entreprise_data={
                'name': urlparse(website).netloc or website,
                'website': website,
                'statut': 'Nouveau',
            },
            skip_duplicates=True,
        )

    max_depth = int(payload.get('max_depth', 2) or 2)
    max_workers = int(payload.get('max_workers', 5) or 5)
    max_time = int(payload.get('max_time', 180) or 180)
    max_pages = int(payload.get('max_pages', 30) or 30)
    enable_nmap = bool(payload.get('enable_nmap', False))
    use_lighthouse = bool(payload.get('use_lighthouse', True))

    from tasks.scraping_tasks import scrape_emails_task
    from tasks.technical_analysis_tasks import technical_analysis_task
    from tasks.seo_tasks import seo_analysis_task
    from tasks.osint_tasks import osint_analysis_task
    from tasks.pentest_tasks import pentest_analysis_task

    tasks_launched = {}
    try:
        scraping_task = scrape_emails_task.delay(
            url=website,
            max_depth=max_depth,
            max_workers=max_workers,
            max_time=max_time,
            max_pages=max_pages,
            entreprise_id=entreprise_id,
        )
        tasks_launched['scraping_task_id'] = scraping_task.id
    except Exception as e:
        tasks_launched['scraping_error'] = str(e)

    try:
        tech_task = technical_analysis_task.delay(url=website, entreprise_id=entreprise_id, enable_nmap=enable_nmap)
        tasks_launched['technical_task_id'] = tech_task.id
    except Exception as e:
        tasks_launched['technical_error'] = str(e)

    try:
        seo_task = seo_analysis_task.delay(url=website, entreprise_id=entreprise_id, use_lighthouse=use_lighthouse)
        tasks_launched['seo_task_id'] = seo_task.id
    except Exception as e:
        tasks_launched['seo_error'] = str(e)

    try:
        osint_task = osint_analysis_task.delay(url=website, entreprise_id=entreprise_id)
        tasks_launched['osint_task_id'] = osint_task.id
    except Exception as e:
        tasks_launched['osint_error'] = str(e)

    try:
        pentest_task = pentest_analysis_task.delay(url=website, entreprise_id=entreprise_id, options={})
        tasks_launched['pentest_task_id'] = pentest_task.id
    except Exception as e:
        tasks_launched['pentest_error'] = str(e)

    return jsonify({
        'success': True,
        'website': website,
        'entreprise_id': entreprise_id,
        'launched': True,
        'tasks': tasks_launched,
        'message': 'Analyses lancées. Utilisez GET /api/public/website-analysis?website=... pour récupérer le rapport.',
    }), 202


@api_public_bp.route('/campagnes', methods=['GET'])
@api_token_required
@require_api_permission('campagnes')
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
@require_api_permission('campagnes')
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
@require_api_permission('campagnes')
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
@require_api_permission('campagnes')
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

