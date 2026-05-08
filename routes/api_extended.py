"""
Blueprint pour les routes API étendues

Contient les routes API supplémentaires pour les analyses, scrapers, exports, etc.
"""

from flask import Blueprint, request, jsonify, session
from services.database import Database
from services.export_manager import ExportManager
from services.auth import login_required
from config import CELERY_BROKER_URL, CELERY_FULL_ANALYSIS_QUEUE, SEO_USE_LIGHTHOUSE_DEFAULT, LANDING_VARIANTS_ENABLED
import json
import pandas as pd
import socket
import requests
from urllib.parse import urlparse

from utils.url_utils import canonical_website_https_url, normalize_website_domain

api_extended_bp = Blueprint('api_extended', __name__, url_prefix='/api')

# Initialiser les services
database = Database()
export_manager = ExportManager()

def _normalize_url_for_analysis(raw: str) -> str | None:
    """URL HTTPS canonique (sans www.) — alignée sur la dédup domaine en base."""
    if raw is None:
        return None
    return canonical_website_https_url(str(raw).strip() or None)


def _get_entreprise_id_for_website(database: Database, website: str) -> int | None:
    # Réutilise la logique de déduplication basée sur le domaine
    try:
        return database.find_duplicate_entreprise(nom='', website=website)
    except Exception:
        return None


def _backfill_external_links_target(database: Database, entreprise_id: int, website: str) -> int:
    """
    Rattache les anciens liens externes à une fiche entreprise devenue connue.
    Cas typique : le lien existait déjà dans le graphe, puis on analyse ce domaine plus tard.
    """
    host = normalize_website_domain(website)
    if not host or not entreprise_id:
        return 0
    conn = database.get_connection()
    cursor = conn.cursor()
    try:
        database.execute_sql(
            cursor,
            '''
            UPDATE entreprise_external_links
               SET target_entreprise_id = ?
             WHERE (target_entreprise_id IS NULL OR target_entreprise_id = 0)
               AND entreprise_id != ?
               AND domain_id IN (
                    SELECT id FROM external_domains WHERE domain_host = ?
               )
            ''',
            (int(entreprise_id), int(entreprise_id), host),
        )
        n = int(getattr(cursor, 'rowcount', 0) or 0)
        conn.commit()
        return n
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def _resolve_target_entreprise_from_external_domain(database: Database, website: str) -> int | None:
    """
    Si ce domaine externe est déjà relié à une fiche cible connue, retourne cette fiche.
    Évite de créer une nouvelle entreprise "indépendante" pour un domaine déjà mappé.
    """
    host = normalize_website_domain(website)
    if not host:
        return None
    conn = database.get_connection()
    cursor = conn.cursor()
    try:
        database.execute_sql(
            cursor,
            '''
            SELECT l.target_entreprise_id AS eid, COUNT(*) AS c
              FROM entreprise_external_links l
              JOIN external_domains d ON d.id = l.domain_id
             WHERE d.domain_host = ?
               AND l.target_entreprise_id IS NOT NULL
             GROUP BY l.target_entreprise_id
             ORDER BY c DESC
             LIMIT 1
            ''',
            (host,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = database.clean_row_dict(dict(row))
        eid = d.get('eid')
        return int(eid) if eid is not None else None
    except Exception:
        return None
    finally:
        conn.close()


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

    screenshots_latest = {}
    try:
        screenshots_latest = database.get_latest_entreprise_screenshots(entreprise_id) or {}
    except Exception:
        screenshots_latest = {}

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
        'screenshots': {
            'status': 'done' if screenshots_latest else 'never',
            'latest': screenshots_latest,
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
        # Attention: peut être volumineux (emails/people/images). À utiliser côté intégration.
        report['scraping']['items'] = scrapers
        report['scraping']['count'] = len(scrapers)
    return report


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


@api_extended_bp.route('/google-maps/import', methods=['POST'])
@login_required
def google_maps_import():
    """
    API: Importe une liste de lieux Google Maps comme entreprises ProspectLab.

    Corps JSON:
        {
            "places": [
                {
                    "place_id": "...",
                    "name": "...",
                    "website": "...",
                    "phone_number": "...",
                    "country": "...",
                    "address_1": "...",
                    "address_2": "...",
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "rating": 4.5,
                    "reviews_count": 123,
                    "category": "boulangerie"
                },
                ...
            ]
        }

    Returns:
        JSON: {
            "results": [
                {
                    "place_id": "...",
                    "entreprise_id": 123,
                    "created": true
                },
                ...
            ]
        }
    """
    payload = request.get_json(silent=True) or {}
    places = payload.get('places') or []

    if not isinstance(places, list) or not places:
        return jsonify({'error': 'Le champ "places" (liste) est requis.'}), 400

    results = []

    for place in places:
        if not isinstance(place, dict):
            continue

        name = (place.get('name') or '').strip()
        website = (place.get('website') or '').strip() or None
        phone = (place.get('phone_number') or place.get('phone') or '').strip() or None
        country = (place.get('country') or '').strip() or None
        address_1 = (place.get('address_1') or place.get('address') or '').strip() or None
        address_2 = (place.get('address_2') or '').strip() or None
        latitude = place.get('latitude', place.get('lat'))
        longitude = place.get('longitude', place.get('lng'))
        rating = place.get('rating')
        reviews_count = place.get('reviews_count')
        category = (place.get('category') or '').strip() or None

        try:
            # Vérifier si une entreprise similaire existe déjà
            existing_id = None
            if name or website:
                existing_id = database.find_duplicate_entreprise(
                    nom=name,
                    website=website,
                    address_1=address_1,
                    address_2=address_2,
                )

            created = False
            if existing_id:
                entreprise_id = existing_id
            else:
                entreprise_data = {
                    'name': name or website or 'Entreprise Google Maps',
                    'website': website,
                    'telephone': phone,
                    'pays': country,
                    'address_1': address_1,
                    'address_2': address_2,
                    'latitude': latitude,
                    'longitude': longitude,
                    'rating': rating,
                    'reviews_count': reviews_count,
                    'category': category,
                    'category_translate': category,
                    'statut': 'Nouveau',
                }

                entreprise_id = database.save_entreprise(
                    analyse_id=None,
                    entreprise_data=entreprise_data,
                    skip_duplicates=False,
                )
                created = True

            results.append({
                'place_id': place.get('place_id'),
                'entreprise_id': entreprise_id,
                'created': created,
            })
        except Exception as e:  # pragma: no cover - robust face aux erreurs ponctuelles
            results.append({
                'place_id': place.get('place_id'),
                'error': str(e),
            })

    return jsonify({'results': results})


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


@api_extended_bp.route('/entreprise/<int:entreprise_id>/audit-pipeline')
@login_required
def entreprise_audit_pipeline(entreprise_id):
    """
    API: Résumé du pipeline d'audit d'une entreprise
    
    Retourne, pour chaque brique (Scraping, Technique, SEO, OSINT, Pentest),
    le dernier état connu et quelques métriques clés.
    """
    try:
        pipeline = {}

        # Scraping (données issues du scraper le plus récent)
        try:
            scrapers = database.get_scrapers_by_entreprise(entreprise_id)
        except Exception:
            scrapers = []
        if scrapers:
            latest_scraper = scrapers[0]
            emails = latest_scraper.get('emails') or []
            people = latest_scraper.get('people') or []
            phones = latest_scraper.get('phones') or []
            pipeline['scraping'] = {
                'status': 'done',
                'last_date': latest_scraper.get('date_modification') or latest_scraper.get('date_creation'),
                'url': latest_scraper.get('url'),
                'emails_count': len(emails),
                'people_count': len(people),
                'phones_count': len(phones),
            }
        else:
            pipeline['scraping'] = {'status': 'never'}

        # Analyse technique
        try:
            technical = database.get_technical_analysis(entreprise_id)
        except Exception:
            technical = None
        if technical:
            pipeline['technical'] = {
                'status': 'done',
                'last_date': technical.get('date_analyse'),
                'url': technical.get('url'),
                'security_score': technical.get('security_score'),
                'performance_score': technical.get('performance_score'),
            }
        else:
            pipeline['technical'] = {'status': 'never'}

        # Analyse SEO
        seo_summary = {'status': 'never'}
        try:
            seo_list = database.get_seo_analyses_by_entreprise(entreprise_id, limit=1)
            if seo_list:
                seo = seo_list[0]
                seo_summary = {
                    'status': 'done',
                    'last_date': seo.get('date_analyse'),
                    'url': seo.get('url'),
                    'score': seo.get('score'),
                }
        except Exception:
            pass
        pipeline['seo'] = seo_summary

        screenshots_latest = {}
        try:
            screenshots_latest = database.get_latest_entreprise_screenshots(entreprise_id) or {}
        except Exception:
            screenshots_latest = {}
        if screenshots_latest:
            pipeline['screenshots'] = {
                'status': 'done',
                'devices': ['desktop', 'tablet', 'mobile'],
                'latest': screenshots_latest,
            }
        else:
            pipeline['screenshots'] = {'status': 'never'}

        # Analyse OSINT
        try:
            osint = database.get_osint_analysis_by_entreprise(entreprise_id)
        except Exception:
            osint = None
        if osint:
            emails = osint.get('emails') or []
            social_media = osint.get('social_media') or {}
            people_data = osint.get('people') or {}
            enriched_people = []
            if isinstance(people_data, dict):
                # Plusieurs formats possibles, on normalise grossièrement
                enriched_people = people_data.get('enriched') or people_data.get('people') or []
            elif isinstance(people_data, list):
                enriched_people = people_data
            pipeline['osint'] = {
                'status': 'done',
                'last_date': osint.get('date_analyse'),
                'url': osint.get('url'),
                'emails_count': len(emails),
                'people_count': len(enriched_people),
                'social_platforms_count': len(social_media.keys()) if isinstance(social_media, dict) else 0,
            }
        else:
            pipeline['osint'] = {'status': 'never'}

        # Analyse Pentest
        try:
            pentest = database.get_pentest_analysis_by_entreprise(entreprise_id)
        except Exception:
            pentest = None
        if pentest:
            vulnerabilities = pentest.get('vulnerabilities') or []
            critical_count = len([v for v in vulnerabilities if v.get('severity') == 'Critical'])
            high_count = len([v for v in vulnerabilities if v.get('severity') == 'High'])
            pipeline['pentest'] = {
                'status': 'done',
                'last_date': pentest.get('date_analyse'),
                'url': pentest.get('url'),
                'risk_score': pentest.get('risk_score'),
                'vulnerabilities_count': len(vulnerabilities),
                'critical_count': critical_count,
                'high_count': high_count,
            }
        else:
            pipeline['pentest'] = {'status': 'never'}

        return jsonify({
            'entreprise_id': entreprise_id,
            'pipeline': pipeline
        })
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
        limit = max(1, min(limit, 500))
        
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


@api_extended_bp.route('/website-analysis', methods=['GET', 'POST'])
@login_required
def website_analysis():
    """
    API: Analyse d'un site web (par URL).

    GET:
        Query params:
            website (str, requis): URL ou domaine du site.
        Retourne le rapport agrégé si disponible.

    POST:
        Corps JSON:
            - website (str, requis): URL ou domaine du site.
            - force (bool, optionnel): si true, relance les analyses même si un rapport existe.
            - max_depth (int, optionnel): profondeur max de scraping (défaut 2).
            - max_workers (int, optionnel): workers scraping (défaut 5).
            - max_time (int, optionnel): temps max en secondes (défaut 180).
            - max_pages (int, optionnel): pages max (défaut 30).
            - enable_nmap (bool, optionnel): active Nmap dans l'analyse technique (défaut false).
            - use_lighthouse (bool, optionnel): Lighthouse pour SEO (défaut false, désactivé).

        Comportement:
            - si force=false et un rapport existe => retourne le rapport
            - sinon => crée/associe une entreprise et lance les tâches (scraping/tech/seo/osint/pentest)
    """
    database = Database()

    # IMPORTANT : cet endpoint /api/* est réservé à l'interface interne.
    # L'accès public doit passer par /api/public/* (token).
    # Comme l'auth utilisateur est partiellement désactivée dans ce projet,
    # on verrouille ici en exigeant une session utilisateur active.
    if not session.get('user_id'):
        return jsonify({
            'error': 'Authentification requise',
            'message': 'Connectez-vous à ProspectLab (session) ou utilisez /api/public/website-analysis avec un token.'
        }), 401

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

    # POST
    payload = request.get_json(silent=True) or {}
    website_raw = (payload.get('website') or '').strip()
    website = _normalize_url_for_analysis(website_raw)
    if not website:
        return jsonify({'error': 'Le champ "website" est requis (URL ou domaine).'}), 400

    force = bool(payload.get('force', False))
    full = bool(payload.get('full', False))
    entreprise_id = _get_entreprise_id_for_website(database, website)

    # Si on a déjà une entreprise, retourner le rapport si demandé
    if entreprise_id and not force:
        report = _build_website_analysis_report(database, entreprise_id, full=full)
        report['website'] = website
        return jsonify(report)

    # Créer une entreprise minimale si nécessaire
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

    # Lancer les tâches d'analyse
    max_depth = int(payload.get('max_depth', 2) or 2)
    max_workers = int(payload.get('max_workers', 5) or 5)
    max_time = int(payload.get('max_time', 180) or 180)
    max_pages = int(payload.get('max_pages', 30) or 30)
    enable_nmap = bool(payload.get('enable_nmap', False))
    use_lighthouse = bool(payload.get('use_lighthouse', SEO_USE_LIGHTHOUSE_DEFAULT))

    from tasks.scraping_tasks import scrape_emails_task
    from tasks.technical_analysis_tasks import technical_analysis_task
    from tasks.seo_tasks import seo_analysis_task
    from tasks.screenshot_tasks import website_screenshot_task
    from tasks.osint_tasks import osint_analysis_task
    from tasks.pentest_tasks import pentest_analysis_task
    from tasks.heavy_schedule import BulkSubtaskStagger

    # Étaler les 5 sous-tâches (même principe que le scraping multi-entreprises)
    _st = BulkSubtaskStagger()
    tasks_launched = {}
    try:
        scraping_task = scrape_emails_task.apply_async(
            kwargs=dict(
                url=website,
                max_depth=max_depth,
                max_workers=max_workers,
                max_time=max_time,
                max_pages=max_pages,
                entreprise_id=entreprise_id,
            ),
            countdown=_st.next_countdown(),
            queue='scraping',
        )
        tasks_launched['scraping_task_id'] = scraping_task.id
    except Exception as e:
        tasks_launched['scraping_error'] = str(e)

    try:
        tech_task = technical_analysis_task.apply_async(
            kwargs=dict(url=website, entreprise_id=entreprise_id, enable_nmap=enable_nmap),
            countdown=_st.next_countdown(),
            queue='technical',
        )
        tasks_launched['technical_task_id'] = tech_task.id
    except Exception as e:
        tasks_launched['technical_error'] = str(e)

    try:
        seo_task = seo_analysis_task.apply_async(
            kwargs=dict(url=website, entreprise_id=entreprise_id, use_lighthouse=use_lighthouse),
            countdown=_st.next_countdown(),
            queue='seo',
        )
        tasks_launched['seo_task_id'] = seo_task.id
    except Exception as e:
        tasks_launched['seo_error'] = str(e)

    try:
        screenshot_task = website_screenshot_task.apply_async(
            kwargs=dict(url=website, entreprise_id=entreprise_id, analysis_id=None, full_page=False),
            countdown=_st.next_countdown(),
            queue='screenshot',
        )
        tasks_launched['screenshot_task_id'] = screenshot_task.id
    except Exception as e:
        tasks_launched['screenshot_error'] = str(e)

    # OSINT/Pentest peuvent fonctionner sans attendre le scraping (ils récupèrent aussi les données en BDD si dispo)
    try:
        osint_task = osint_analysis_task.apply_async(
            kwargs=dict(url=website, entreprise_id=entreprise_id),
            countdown=_st.next_countdown(),
            queue='osint',
        )
        tasks_launched['osint_task_id'] = osint_task.id
    except Exception as e:
        tasks_launched['osint_error'] = str(e)

    try:
        pentest_task = pentest_analysis_task.apply_async(
            kwargs=dict(url=website, entreprise_id=entreprise_id, options={}),
            countdown=_st.next_countdown(),
            queue='heavy',
        )
        tasks_launched['pentest_task_id'] = pentest_task.id
    except Exception as e:
        tasks_launched['pentest_error'] = str(e)

    return jsonify({
        'success': True,
        'website': website,
        'entreprise_id': entreprise_id,
        'launched': True,
        'tasks': tasks_launched,
        'message': 'Analyses lancées. Utilisez GET /api/website-analysis?website=... pour récupérer le rapport.',
    }), 202


@api_extended_bp.route('/website-analysis/ensure-entreprise', methods=['POST'])
@login_required
def website_analysis_ensure_entreprise():
    """Crée (ou retrouve) la fiche entreprise pour une URL sans lancer d'analyses."""
    if not session.get('user_id'):
        return jsonify({'error': 'Authentification requise'}), 401
    database = Database()
    payload = request.get_json(silent=True) or {}
    website = _normalize_url_for_analysis((payload.get('website') or '').strip())
    if not website:
        return jsonify({'error': 'Le champ "website" est requis (URL ou domaine).'}), 400

    entreprise_id = _get_entreprise_id_for_website(database, website)
    if not entreprise_id:
        entreprise_id = _resolve_target_entreprise_from_external_domain(database, website)
    created = False
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
        created = True
    if not entreprise_id:
        return jsonify({'error': "Impossible de créer/retrouver l'entreprise."}), 500
    backfilled = _backfill_external_links_target(database, int(entreprise_id), website)
    entreprise_name = ''
    try:
        ent_row = database.get_entreprise(int(entreprise_id)) or {}
        entreprise_name = (ent_row.get('nom') or ent_row.get('name') or '').strip()
    except Exception:
        entreprise_name = ''
    if not entreprise_name:
        try:
            entreprise_name = (urlparse(website).netloc or website or '').strip()
        except Exception:
            entreprise_name = ''
    return jsonify(
        {
            'success': True,
            'website': website,
            'entreprise_id': int(entreprise_id),
            'entreprise_name': entreprise_name,
            'created': created,
            'links_backfilled': backfilled,
        }
    )


def _json_safe_celery_result(value):
    """Rend un résultat Celery sérialisable (dates, Exception)."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _json_safe_celery_result(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_celery_result(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)[:8000]


def _to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _validate_website_resolvable(website: str) -> tuple[bool, str | None]:
    """
    Vérifie rapidement qu'un domaine est résolvable avant de lancer des jobs lourds.
    Évite de démarrer des tâches landing variants sur un site inexistant.
    """
    parsed = urlparse(str(website or '').strip())
    host = (parsed.hostname or '').strip()
    if not host:
        return False, "URL invalide (hôte introuvable)."

    # 1) Validation DNS primaire (rapide)
    dns_error: Exception | None = None
    try:
        socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        return True, None
    except Exception as e:
        dns_error = e

    # 2) Fallback HTTP(S): certains environnements DNS/stack réseau sont capricieux.
    # Si la requête répond, on considère le site atteignable.
    try:
        resp = requests.get(str(website), timeout=6, allow_redirects=True)
        if resp is not None and resp.status_code:
            return True, None
    except Exception:
        pass

    if isinstance(dns_error, socket.gaierror):
        return False, "Domaine introuvable (DNS). Vérifiez l'URL du site."
    if dns_error is not None:
        return False, f"Impossible de valider le domaine ({type(dns_error).__name__}). Vérifiez l'URL du site."
    return False, "Impossible de valider le domaine. Vérifiez l'URL du site."


def _format_celery_failure_message(async_res):
    """
    Message d'échec Celery lisible (info / traceback).
    Les workers non à jour renvoient souvent NotRegistered('tasks.xxx.task_name').
    """
    info = getattr(async_res, 'info', None)
    parts = []

    if info is not None:
        if isinstance(info, (list, tuple)):
            if len(info) >= 2 and info[1] is not None:
                parts.append(f'{info[0]}: {info[1]}')
            elif len(info) >= 1:
                parts.append(str(info[0]))
        elif isinstance(info, BaseException):
            parts.append(f'{type(info).__name__}: {info}')
        else:
            parts.append(str(info))

    tb = getattr(async_res, 'traceback', None)
    if isinstance(tb, str) and tb.strip():
        lines = [ln.strip() for ln in tb.strip().split('\n') if ln.strip()]
        if lines:
            parts.append('— '.join(lines[-3:]))

    msg = ' '.join(parts) if parts else 'Erreur inconnue (tâche Celery).'

    low = msg.lower()
    if 'notregistered' in low or ("'tasks." in msg and 'full_website' in low):
        msg += (
            ' — Vérifiez que les workers écoutent la file configurée (CELERY_FULL_ANALYSIS_QUEUE, '
            'souvent « technical ») et que CELERY_WORKER_QUEUES sur le serveur l’inclut. '
            'Redémarrez les workers après déploiement.'
        )
    return msg[:12000]


@api_extended_bp.route('/website-full-analysis/start', methods=['POST'])
@login_required
def website_full_analysis_start():
    """
    Démarre le pack complet (scraping → technique → SEO → OSINT → pentest) pour une URL.
    Crée une ligne ``analyses`` (statut En cours) et rattache l'``entreprise`` à cette analyse.
    """
    database = Database()
    if not session.get('user_id'):
        return jsonify({
            'error': 'Authentification requise',
            'message': 'Connectez-vous à ProspectLab pour lancer cette analyse.',
        }), 401

    payload = request.get_json(silent=True) or {}
    website = _normalize_url_for_analysis((payload.get('website') or '').strip())
    if not website:
        return jsonify({'error': 'Le champ "website" est requis (URL ou domaine).'}), 400

    netloc = urlparse(website).netloc or website
    filename = f'full-scan:{netloc}'
    enable_technical = bool(payload.get('enable_technical', True))
    enable_seo = bool(payload.get('enable_seo', True))
    enable_screenshot = bool(payload.get('enable_screenshot', True))
    enable_osint = bool(payload.get('enable_osint', True))
    enable_pentest = bool(payload.get('enable_pentest', True))
    parametres = {
        'source': 'website_full',
        'url': website,
        'modules': {
            'technical': enable_technical,
            'seo': enable_seo,
            'screenshot': enable_screenshot,
            'osint': enable_osint,
            'pentest': enable_pentest,
        },
    }

    analyse_id = database.create_pending_analysis(filename, parametres, total_entreprises=1)
    if not analyse_id:
        return jsonify({'error': 'Impossible de créer l\'enregistrement d\'analyse.'}), 500

    entreprise_id = database.save_entreprise(
        analyse_id,
        {
            'name': netloc,
            'website': website,
            'statut': 'Nouveau',
        },
        skip_duplicates=True,
    )
    if not entreprise_id:
        try:
            database.finalize_analysis(analyse_id, statut='Erreur')
        except Exception:
            pass
        return jsonify({'error': 'Impossible de créer ou retrouver l\'entreprise.'}), 500
    _backfill_external_links_target(database, int(entreprise_id), website)

    max_depth = int(payload.get('max_depth', 2) or 2)
    max_workers = int(payload.get('max_workers', 5) or 5)
    max_time = int(payload.get('max_time', 240) or 240)
    max_pages = int(payload.get('max_pages', 40) or 40)
    enable_nmap = bool(payload.get('enable_nmap', False))
    use_lighthouse = bool(payload.get('use_lighthouse', SEO_USE_LIGHTHOUSE_DEFAULT))

    try:
        from tasks.analysis_tasks import full_website_analysis_task
        async_res = full_website_analysis_task.apply_async(
            kwargs=dict(
                url=website,
                entreprise_id=entreprise_id,
                analyse_id=analyse_id,
                max_depth=max_depth,
                max_workers=max_workers,
                max_time=max_time,
                max_pages=max_pages,
                enable_nmap=enable_nmap,
                use_lighthouse=use_lighthouse,
                enable_technical=enable_technical,
                enable_seo=enable_seo,
                enable_screenshot=enable_screenshot,
                enable_osint=enable_osint,
                enable_pentest=enable_pentest,
            ),
            queue=CELERY_FULL_ANALYSIS_QUEUE,
        )
    except Exception as e:
        try:
            database.finalize_analysis(analyse_id, statut='Erreur')
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500

    entreprise_name = ''
    try:
        ent = database.get_entreprise(int(entreprise_id)) or {}
        entreprise_name = (ent.get('nom') or ent.get('name') or netloc or website).strip()
    except Exception:
        entreprise_name = (netloc or website or '').strip()

    return jsonify({
        'success': True,
        'task_id': async_res.id,
        'entreprise_id': entreprise_id,
        'entreprise_name': entreprise_name,
        'analyse_id': analyse_id,
        'website': website,
        'message': 'Analyse complète démarrée. Interroger /api/celery-task/<task_id> jusqu\'à state=SUCCESS.',
    }), 202


@api_extended_bp.route('/landing-variants/start', methods=['POST'])
@login_required
def landing_variants_start():
    """
    Démarre une génération de landing variants via tâche Celery dédiée.

    Corps JSON:
      - url (str, requis)
      - variants (int, optionnel, défaut 4)
      - free_mode (bool, optionnel, défaut true)
      - output_dir (str, optionnel)
      - extra_instructions (str, optionnel)
      - screenshot_desktop_only (bool, optionnel)
      - skip_screenshots (bool, optionnel)
    """
    if not session.get('user_id'):
        return jsonify({'error': 'Authentification requise'}), 401
    if not LANDING_VARIANTS_ENABLED:
        return jsonify({'success': False, 'error': 'Feature landing variants désactivée côté serveur'}), 503

    payload = request.get_json(silent=True) or {}
    entreprise_id = payload.get('entreprise_id', None)
    if entreprise_id is not None:
        try:
            entreprise_id = int(entreprise_id)
        except Exception:
            return jsonify({'success': False, 'error': 'entreprise_id invalide'}), 400
    website = _normalize_url_for_analysis((payload.get('url') or payload.get('website') or '').strip())
    if not website and entreprise_id:
        ent = database.get_entreprise(int(entreprise_id))
        website = _normalize_url_for_analysis((ent or {}).get('website'))
    if not website:
        return jsonify({'success': False, 'error': 'Le champ "url" est requis (URL ou domaine).'}), 400
    ok_site, site_err = _validate_website_resolvable(website)
    if not ok_site:
        return jsonify({'success': False, 'error': 'unreachable_site', 'message': site_err}), 400

    variants = int(payload.get('variants', 4) or 4)
    variants = max(1, min(variants, 4))

    free_mode = _to_bool(payload.get('free_mode'), True)
    screenshot_desktop_only = _to_bool(payload.get('screenshot_desktop_only'), False)
    skip_screenshots = _to_bool(payload.get('skip_screenshots'), False)
    output_dir = (payload.get('output_dir') or '').strip() or None
    extra_instructions = (payload.get('extra_instructions') or '').strip() or None

    try:
        # Bloquer une nouvelle tâche si un run est déjà en cours (évite de boucher serv1).
        lock_key = None
        if entreprise_id:
            lock_key = f"prospectlab:landing:variants:lock:{int(entreprise_id)}"
        else:
            lock_key = "prospectlab:landing:variants:lock:global"
        try:
            import redis

            r = redis.Redis.from_url(
                CELERY_BROKER_URL,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            # TTL large: si worker plante, le lock se libère tout seul.
            ttl_sec = 60 * 60 * 2
            ok = r.set(lock_key, "1", nx=True, ex=ttl_sec)
            if not ok:
                return jsonify(
                    {
                        "success": False,
                        "error": "already_running",
                        "message": "Une génération landing variants est déjà en cours. Attendez la fin avant de relancer.",
                    }
                ), 409
        except Exception:
            # Si Redis indisponible, on n'empêche pas le lancement (fallback).
            lock_key = None

        from tasks.landing_variant_tasks import generate_landing_variants_remote_task

        async_res = generate_landing_variants_remote_task.apply_async(
            kwargs=dict(
                url=website,
                entreprise_id=entreprise_id,
                variants=variants,
                free_mode=free_mode,
                output_dir=output_dir,
                extra_instructions=extra_instructions,
                screenshot_desktop_only=screenshot_desktop_only,
                skip_screenshots=skip_screenshots,
                launch_lock_key=lock_key,
            ),
            queue='landing',
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify(
        {
            'success': True,
            'task_id': async_res.id,
            'url': website,
            'variants': variants,
            'free_mode': free_mode,
            'entreprise_id': entreprise_id,
            'message': 'Génération des variants lancée. Suivre via /api/celery-task/<task_id>.',
        }
    ), 202


@api_extended_bp.route('/entreprise/<int:entreprise_id>/landing-variants', methods=['GET'])
@login_required
def entreprise_landing_variants(entreprise_id):
    """
    API: Dernier run de landing variants + assets normalisés (UI entreprise).
    """
    try:
        entreprise = database.get_entreprise(int(entreprise_id))
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404
        latest = database.get_latest_landing_variant_bundle(int(entreprise_id)) or {}
        runs = database.list_landing_variant_runs(int(entreprise_id), limit=10)
        return jsonify(
            {
                'success': True,
                'entreprise_id': int(entreprise_id),
                'latest': latest,
                'runs': runs,
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/landing-variants/start', methods=['POST'])
@login_required
def entreprise_landing_variants_start(entreprise_id):
    """
    API: Wrapper UI entreprise pour démarrer génération variants.
    """
    try:
        if not LANDING_VARIANTS_ENABLED:
            return jsonify({'success': False, 'error': 'Feature landing variants désactivée côté serveur'}), 503
        entreprise = database.get_entreprise(int(entreprise_id))
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404
        website = _normalize_url_for_analysis((entreprise or {}).get('website'))
        if not website:
            return jsonify({'success': False, 'error': 'Aucun website valide sur cette entreprise'}), 400
        ok_site, site_err = _validate_website_resolvable(website)
        if not ok_site:
            return jsonify({'success': False, 'error': 'unreachable_site', 'message': site_err}), 400
        payload = request.get_json(silent=True) or {}
        variants = int(payload.get('variants', 4) or 4)
        variants = max(1, min(variants, 4))
        free_mode = _to_bool(payload.get('free_mode'), True)
        screenshot_desktop_only = _to_bool(payload.get('screenshot_desktop_only'), False)
        skip_screenshots = _to_bool(payload.get('skip_screenshots'), False)
        output_dir = (payload.get('output_dir') or '').strip() or None
        extra_instructions = (payload.get('extra_instructions') or '').strip() or None
        from tasks.landing_variant_tasks import generate_landing_variants_remote_task

        # Lock Redis par entreprise pour empêcher une relance avant la fin.
        lock_key = f"prospectlab:landing:variants:lock:{int(entreprise_id)}"
        try:
            import redis

            r = redis.Redis.from_url(
                CELERY_BROKER_URL,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            ttl_sec = 60 * 60 * 2
            ok = r.set(lock_key, "1", nx=True, ex=ttl_sec)
            if not ok:
                return jsonify(
                    {
                        "success": False,
                        "error": "already_running",
                        "message": "Une génération landing variants est déjà en cours. Attendez la fin avant de relancer.",
                    }
                ), 409
        except Exception:
            lock_key = None

        async_res = generate_landing_variants_remote_task.apply_async(
            kwargs=dict(
                url=website,
                entreprise_id=int(entreprise_id),
                variants=variants,
                free_mode=free_mode,
                output_dir=output_dir,
                extra_instructions=extra_instructions,
                screenshot_desktop_only=screenshot_desktop_only,
                skip_screenshots=skip_screenshots,
                launch_lock_key=lock_key,
            ),
            queue='landing',
        )
        return jsonify(
            {
                'success': True,
                'task_id': async_res.id,
                'url': website,
                'entreprise_id': int(entreprise_id),
                'variants': variants,
                'free_mode': free_mode,
                'message': 'Génération des variants lancée. Suivre via /api/celery-task/<task_id>.',
            }
        ), 202
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/screenshots')
@login_required
def entreprise_screenshots(entreprise_id):
    """
    API: Récupère les captures d'écran d'une entreprise (historique + dernière par device).
    """
    try:
        limit = int(request.args.get('limit', 30) or 30)
        rows = database.list_entreprise_screenshots(
            entreprise_id=int(entreprise_id),
            limit=limit,
        )
        latest = database.get_latest_entreprise_screenshots(int(entreprise_id))
        return jsonify(
            {
                'success': True,
                'entreprise_id': int(entreprise_id),
                'latest': latest,
                'items': rows,
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended_bp.route('/entreprise/<int:entreprise_id>/screenshots/capture', methods=['POST'])
@login_required
def entreprise_screenshots_capture(entreprise_id):
    """
    API: Lance une tâche Celery de capture screenshots (desktop/tablet/mobile) pour une entreprise.
    """
    try:
        entreprise = database.get_entreprise(int(entreprise_id))
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404

        website = _normalize_url_for_analysis(entreprise.get('website'))
        if not website:
            return jsonify({'success': False, 'error': 'Aucun website valide sur cette entreprise'}), 400

        payload = request.get_json(silent=True) or {}
        analysis_id = payload.get('analysis_id')
        if analysis_id is not None:
            try:
                analysis_id = int(analysis_id)
            except Exception:
                analysis_id = None

        from tasks.screenshot_tasks import website_screenshot_task

        task = website_screenshot_task.apply_async(
            kwargs=dict(
                url=website,
                entreprise_id=int(entreprise_id),
                analysis_id=analysis_id,
            ),
            queue='screenshot',
        )
        return jsonify(
            {
                'success': True,
                'entreprise_id': int(entreprise_id),
                'website': website,
                'task_id': task.id,
            }
        ), 202
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended_bp.route('/celery-task/<task_id>', methods=['GET'])
@login_required
def celery_task_status(task_id):
    """État d'une tâche Celery (progression ou résultat)."""
    if not session.get('user_id'):
        return jsonify({'error': 'Authentification requise'}), 401

    from celery_app import celery as celery_app

    async_res = celery_app.AsyncResult(task_id)
    out = {'state': async_res.state, 'task_id': task_id}
    if async_res.state == 'PENDING':
        out['pending'] = True
    elif async_res.state == 'PROGRESS':
        out['meta'] = async_res.info
    elif async_res.state == 'SUCCESS':
        out['result'] = _json_safe_celery_result(async_res.result)
    elif async_res.state == 'FAILURE':
        out['error'] = _format_celery_failure_message(async_res)
    elif async_res.state in ('REJECTED', 'REVOKED'):
        out['error'] = f"Tâche {async_res.state.lower()} (annulée ou refusée)."
    return jsonify(out)


def _parse_graph_entreprise_ids(raw) -> set[int] | None:
    """Liste d’IDs depuis une query string (virgules). ``None`` = pas de filtre ; ensemble vide = aucun résultat."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return set()
    out: set[int] = set()
    for part in s.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            continue
        if len(out) >= 500:
            break
    return out


@api_extended_bp.route('/entreprises/graph', methods=['GET'])
@api_extended_bp.route('/agencies/graph', methods=['GET'])
@login_required
def api_entreprises_graph():
    """
    Graphe interactif : fiches entreprises ↔ domaines externes (crédits, liens, portfolio).

    Query (optionnel) : ``search``, ``domain`` / ``agency_domain``, ``only_credit`` (1/true),
    ``entreprise_ids`` (virgules), ``max_link_rows``, ``max_enterprises``, ``meta`` (1/true) pour métadonnées seules.

    URL historique ``/api/agencies/graph`` conservée (redondante avec ``/api/entreprises/graph``).
    """
    if not session.get('user_id'):
        return jsonify({'error': 'Authentification requise'}), 401
    try:
        search = (request.args.get('search') or request.args.get('q') or '').strip() or None
        domain_contains = (
            request.args.get('domain') or request.args.get('agency_domain') or ''
        ).strip() or None
        only_credit = str(request.args.get('only_credit', '')).strip().lower() in (
            '1',
            'true',
            'yes',
            'on',
        )
        meta_only = str(request.args.get('meta', '')).strip().lower() in ('1', 'true', 'yes', 'on')
        max_link_rows = request.args.get('max_link_rows', type=int)
        max_enterprises = request.args.get('max_enterprises', type=int)
        entreprise_ids = _parse_graph_entreprise_ids(request.args.get('entreprise_ids'))

        data = database.get_entreprises_link_graph(
            search=search,
            entreprise_ids=entreprise_ids,
            domain_contains=domain_contains,
            only_credit=only_credit,
            max_link_rows=max_link_rows,
            max_enterprises=max_enterprises,
            meta_only=meta_only,
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_extended_bp.route('/entreprises/graph/entreprise-autocomplete', methods=['GET'])
@api_extended_bp.route('/entreprises/graph/entreprise-suggest', methods=['GET'])
@api_extended_bp.route('/agencies/graph/entreprise-autocomplete', methods=['GET'])
@api_extended_bp.route('/agencies/graph/entreprise-suggest', methods=['GET'])
@login_required
def api_entreprises_graph_entreprise_autocomplete():
    """Autocomplétion : entreprises ayant des liens ``entreprise_external_links``."""
    if not session.get('user_id'):
        return jsonify({'error': 'Authentification requise'}), 401
    q = (request.args.get('q') or '').strip()
    limit = request.args.get('limit', default=15, type=int) or 15
    try:
        items = database.suggest_entreprises_for_link_graph(q, limit)
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

