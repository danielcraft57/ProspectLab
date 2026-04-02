"""
Blueprint pour l'API publique
Expose les données d'entreprises et emails pour intégration avec d'autres logiciels
Authentification par token API
"""

from flask import Blueprint, request, jsonify
from config import SEO_USE_LIGHTHOUSE_DEFAULT
from services.database import Database
from services.api_auth import api_token_required, require_api_permission
import json
import re
from urllib.parse import urlparse

from utils.url_utils import canonical_website_https_url
from services.public_api_response_cache import public_response_cache

api_public_bp = Blueprint('api_public', __name__, url_prefix='/api/public')

# Initialiser la base de données
database = Database()

def _normalize_email(raw: str) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s or '@' not in s:
        return None
    return s


def _digits_only_phone(raw: str) -> str:
    return re.sub(r'\D', '', raw or '')


def _phone_digit_equivalence_keys(d: str) -> set[str]:
    """Clés numériques pour comparer FR (+33 / 0…) et formats internationaux."""
    if not d:
        return set()
    keys = {d}
    # France métropolitaine : 0X XX XX XX XX ↔ 33X…
    if len(d) == 10 and d.startswith('0'):
        keys.add('33' + d[1:])
    if len(d) == 11 and d.startswith('33') and d[2] in '123456789':
        keys.add('0' + d[2:])
    # Appel international depuis l'étranger : 00… → même suite qu'avec +
    if d.startswith('00') and len(d) >= 12:
        keys.add(d[2:])
    return keys


def _phone_lookup_variants(raw: str) -> list[str]:
    """
    Variantes de chaînes susceptibles d'être stockées telles quelles en base
    (scrapers, saisie utilisateur, formats +33, 06…, 00…).
    """
    s = (raw or '').strip()
    if not s:
        return []
    variants: set[str] = set()
    d = _digits_only_phone(s)
    if not d:
        return []

    def add(v: str | None):
        if v and v.strip():
            variants.add(v.strip())

    add(s)
    add(d)
    # Éviter "+0612…" (invalide) : le cas FR est couvert plus bas (+33…).
    if not (len(d) == 10 and d.startswith('0')):
        add('+' + d)
    if s.startswith('+'):
        add(s[1:])
    if d.startswith('00') and len(d) >= 10:
        add('+' + d[2:])
        add(d[2:])
    # France
    if len(d) == 10 and d.startswith('0'):
        intl = '33' + d[1:]
        add(intl)
        add('+' + intl)
        add('00' + intl)
    if len(d) == 11 and d.startswith('33'):
        add(d)
        add('+' + d)
        add('0' + d[2:])
        add('00' + d)
    # International (hors cas FR ci-dessus)
    if len(d) >= 10 and not (len(d) == 10 and d.startswith('0')):
        add(d)
        add('+' + d)
        if not d.startswith('00'):
            add('00' + d)

    return list(variants)


def _sql_phone_digits_expr(alias: str = 'phone') -> str:
    """Expression SQL (SQLite / PG) : ne garde que les chiffres pour comparaison."""
    # PostgreSQL et SQLite acceptent || pour concaténer des REPLACE imbriqués.
    e = f"COALESCE({alias}, '')" if alias else "COALESCE(phone, '')"
    for ch in (' ', '-', '.', '(', ')', '+'):
        e = f"REPLACE({e}, '{ch}', '')"
    return e


def _find_entreprise_row_by_phone(db: Database, phone_raw: str) -> tuple[int | None, dict | None]:
    """
    Cherche une entreprise par numéro : scraper_phones puis entreprises.telephone.
    Retourne (entreprise_id, match_info) ou (None, None).
    """
    variants = _phone_lookup_variants(phone_raw)
    d = _digits_only_phone(phone_raw)
    digit_keys = _phone_digit_equivalence_keys(d)
    if not d:
        return None, None

    conn = db.get_connection()
    cursor = conn.cursor()
    row = None
    row2 = None
    match: dict | None = None

    vlist = [v for v in variants if v][:64]
    if vlist:
        ph = ','.join(['?'] * len(vlist))
        db.execute_sql(cursor, f'''
            SELECT entreprise_id, phone, page_url, date_found, phone_e164, osint_json
            FROM scraper_phones
            WHERE phone IN ({ph}) OR phone_e164 IN ({ph})
            ORDER BY date_found DESC
            LIMIT 1
        ''', tuple(vlist) + tuple(vlist))
        row = cursor.fetchone()

    if not row and digit_keys:
        klist = list(digit_keys)[:16]
        if klist:
            expr = _sql_phone_digits_expr('phone')
            expr164 = _sql_phone_digits_expr('phone_e164')
            ph2 = ','.join(['?'] * len(klist))
            db.execute_sql(cursor, f'''
                SELECT entreprise_id, phone, page_url, date_found, phone_e164, osint_json
                FROM scraper_phones
                WHERE {expr} IN ({ph2}) OR (phone_e164 IS NOT NULL AND phone_e164 != '' AND {expr164} IN ({ph2}))
                ORDER BY date_found DESC
                LIMIT 1
            ''', tuple(klist) + tuple(klist))
            row = cursor.fetchone()

    if row:
        r = dict(row) if not isinstance(row, dict) else row
        eid = r.get('entreprise_id')
        match = {
            'source': 'scraper',
            'phone': r.get('phone'),
            'page_url': r.get('page_url'),
            'date_found': r.get('date_found'),
            'phone_e164': r.get('phone_e164'),
        }
        raw_oj = r.get('osint_json')
        if raw_oj:
            try:
                match['osint'] = json.loads(raw_oj)
            except (json.JSONDecodeError, TypeError):
                pass
        conn.close()
        return int(eid), match

    if vlist:
        ph = ','.join(['?'] * len(vlist))
        db.execute_sql(cursor, f'''
            SELECT id
            FROM entreprises
            WHERE telephone IN ({ph})
            LIMIT 1
        ''', tuple(vlist))
        row2 = cursor.fetchone()

    if not row2 and digit_keys:
        klist = list(digit_keys)[:16]
        expr = _sql_phone_digits_expr('telephone')
        ph2 = ','.join(['?'] * len(klist))
        db.execute_sql(cursor, f'''
            SELECT id
            FROM entreprises
            WHERE {expr} IN ({ph2})
            LIMIT 1
        ''', tuple(klist))
        row2 = cursor.fetchone()

    conn.close()

    if row2:
        eid = row2.get('id') if isinstance(row2, dict) else row2[0]
        return int(eid), {
            'source': 'principal',
            'phone': d,
            'page_url': None,
            'date_found': None,
        }

    return None, None


def _get_entreprise_phones_list(entreprise_id: int, include_primary: bool = True) -> list[dict]:
    """Téléphones scrapés + optionnellement telephone de l'entreprise."""
    out: list[dict] = []
    conn = database.get_connection()
    cursor = conn.cursor()
    database.execute_sql(cursor, '''
        SELECT phone, page_url, date_found, phone_e164, carrier, location, line_type, phone_valid,
               osint_json, analyzed_at
        FROM scraper_phones
        WHERE entreprise_id = ?
        ORDER BY date_found DESC
    ''', (entreprise_id,))
    for row in cursor.fetchall() or []:
        r = dict(row) if not isinstance(row, dict) else row
        pv = r.get('phone_valid')
        item = {
            'source': 'scraper',
            'phone': r.get('phone'),
            'page_url': r.get('page_url'),
            'date_found': r.get('date_found'),
            'phone_e164': r.get('phone_e164'),
            'carrier': r.get('carrier'),
            'location': r.get('location'),
            'line_type': r.get('line_type'),
            'valid': bool(pv) if pv is not None else None,
            'analyzed_at': r.get('analyzed_at'),
        }
        raw_oj = r.get('osint_json')
        if raw_oj:
            try:
                item['osint'] = json.loads(raw_oj)
            except (json.JSONDecodeError, TypeError):
                pass
        out.append(item)
    conn.close()

    if include_primary:
        ent = database.get_entreprise(entreprise_id)
        if ent and (ent.get('telephone') or '').strip():
            tel = (ent.get('telephone') or '').strip()
            if not any((x.get('phone') or '').strip() == tel for x in out):
                out.insert(0, {
                    'source': 'principal',
                    'phone': tel,
                    'page_url': None,
                    'date_found': None,
                })
    return out


def _extract_person_from_name_info(name_info) -> dict | None:
    """
    name_info provient de l'analyse email (JSON) et peut contenir des infos personne.
    On normalise au format:
        { full_name, first_name, last_name }
    """
    if not name_info:
        return None
    try:
        if isinstance(name_info, str):
            name_info = json.loads(name_info)
    except Exception:
        return None

    if isinstance(name_info, dict):
        full_name = (name_info.get('full_name') or name_info.get('name') or '').strip() or None
        first_name = (name_info.get('first_name') or name_info.get('prenom') or '').strip() or None
        last_name = (name_info.get('last_name') or name_info.get('nom') or '').strip() or None
        if not full_name and (first_name or last_name):
            full_name = (' '.join([x for x in [first_name, last_name] if x]) or '').strip() or None
        if full_name and (not first_name and not last_name):
            parts = [p for p in full_name.split(' ') if p]
            if len(parts) >= 2:
                first_name = parts[0]
                last_name = ' '.join(parts[1:])
        if full_name or first_name or last_name:
            return {'full_name': full_name, 'first_name': first_name, 'last_name': last_name}
        return None

    # Fallback simple si name_info est une liste ou autre
    try:
        s = str(name_info).strip()
        if not s:
            return None
        parts = [p for p in s.split(' ') if p]
        if len(parts) >= 2:
            return {'full_name': s, 'first_name': parts[0], 'last_name': ' '.join(parts[1:])}
        return {'full_name': s, 'first_name': None, 'last_name': None}
    except Exception:
        return None


def _get_entreprise_emails_full(entreprise_id: int, include_primary: bool = True) -> list[dict]:
    """
    Retourne tous les emails connus pour une entreprise, avec info personne si disponible.
    Source:
      - email_principal (entreprises)
      - scraper_emails (scraping) + analyse (provider/type/risk_score/name_info/is_person)
    """
    emails: list[dict] = []

    entreprise = database.get_entreprise(entreprise_id)
    if include_primary and entreprise and isinstance(entreprise, dict):
        primary = (entreprise.get('email_principal') or '').strip()
        if primary:
            emails.append({
                'email': primary,
                'source': 'principal',
                'page_url': None,
                'date_found': None,
                'analysis': None,
                'is_person': None,
                'person': None,
            })

    conn = database.get_connection()
    cursor = conn.cursor()
    # Chercher dans scraper_emails (normalisée)
    database.execute_sql(cursor, '''
        SELECT
            email,
            page_url,
            provider,
            type,
            format_valid,
            mx_valid,
            risk_score,
            domain,
            name_info,
            is_person,
            analyzed_at,
            date_found
        FROM scraper_emails
        WHERE entreprise_id = ?
          AND email IS NOT NULL
          AND TRIM(email) <> ''
        ORDER BY date_found DESC
    ''', (entreprise_id,))
    rows = cursor.fetchall() or []
    conn.close()

    seen = {e['email'].lower() for e in emails if isinstance(e.get('email'), str)}
    for row in rows:
        d = dict(row) if not isinstance(row, dict) else row
        email_val = (d.get('email') or '').strip()
        if not email_val:
            continue
        key = email_val.lower()
        if key in seen:
            continue
        seen.add(key)

        name_info = None
        try:
            name_info = json.loads(d.get('name_info')) if d.get('name_info') else None
        except Exception:
            name_info = None

        analysis = None
        if d.get('provider') is not None or d.get('type') is not None:
            analysis = {
                'provider': d.get('provider'),
                'type': d.get('type'),
                'format_valid': bool(d.get('format_valid')) if d.get('format_valid') is not None else None,
                'mx_valid': bool(d.get('mx_valid')) if d.get('mx_valid') is not None else None,
                'risk_score': d.get('risk_score'),
                'domain': d.get('domain'),
                'name_info': name_info,
                'analyzed_at': d.get('analyzed_at'),
            }

        emails.append({
            'email': email_val,
            'source': 'scraper',
            'page_url': d.get('page_url'),
            'date_found': d.get('date_found'),
            'analysis': analysis,
            'is_person': bool(d.get('is_person')) if d.get('is_person') is not None else None,
            'person': _extract_person_from_name_info(name_info),
        })

    return emails

def _expand_statut_level(statut: str) -> list[str]:
    """
    Permet de "coupler" plusieurs statuts événementiels sous un niveau marketing.

    Choix de mapping (option simple, sans migration DB) :
    - Gagné   => Gagné + Réponse positive
    - Perdu   => Perdu + Réponse négative + Bounce + Désabonné + Ne pas contacter + Plainte spam
    - Relance => Relance + Nouveau + À qualifier + À rappeler
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
    """
    Si l'UI envoie un niveau (Gagné/Perdu/Relance), on l'étend en liste de statuts événementiels.
    Sinon, on laisse en valeur stricte.
    """
    if not statut_param:
        return None
    s = str(statut_param).strip()
    if s in ('Gagné', 'Perdu', 'Relance'):
        return _expand_statut_level(s)
    return s

def _get_allowed_entreprise_statuses() -> list[str]:
    """
    Retourne la liste canonique des statuts autorisés côté DB.
    Fallback robuste si le symbole n'est pas importable.
    """
    try:
        from services.database.entreprises import ENTERPRISE_STATUSES
        return sorted(list(ENTERPRISE_STATUSES), key=lambda s: s.lower())
    except Exception:
        # Fallback minimal (ne pas casser l'API si import échoue)
        return [
            'Nouveau', 'À qualifier', 'Relance', 'Gagné', 'Perdu',
            'Désabonné', 'Réponse négative', 'Réponse positive', 'Bounce',
            'Plainte spam', 'Ne pas contacter', 'À rappeler',
        ]

def _normalize_url_for_analysis(raw: str) -> str | None:
    """URL HTTPS canonique (sans www.) — alignée sur la dédup domaine en base."""
    if raw is None:
        return None
    return canonical_website_https_url(str(raw).strip() or None)


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
@public_response_cache(25)
def get_entreprises():
    """
    API publique : Liste des entreprises
    
    Query params:
        limit (int): Nombre maximum de résultats (défaut: 100, max: 1000)
        offset (int): Offset pour la pagination (défaut: 0)
        secteur (str): Filtrer par secteur
        statut (str): Filtrer par statut
        opportunite (str): Filtrer par opportunite / score d'opportunite affiche
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
            filters['statut'] = _maybe_expand_statut_filter(request.args.get('statut'))
        if request.args.get('opportunite'):
            filters['opportunite'] = request.args.get('opportunite')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        entreprises = database.get_entreprises(filters=filters if filters else None, limit=limit, offset=offset)

        # Total correspondant aux mêmes filtres (liste + recherche) : une seule requête COUNT
        # sur la première page pour limiter le coût lors du « load more ».
        total = None
        if offset == 0:
            total = database.count_entreprises(filters=filters if filters else None)

        # Nettoyer les valeurs NaN pour la sérialisation JSON
        from utils.helpers import clean_json_dict
        entreprises = clean_json_dict(entreprises)

        payload = {
            'success': True,
            'count': len(entreprises),
            'limit': limit,
            'offset': offset,
            'data': entreprises,
        }
        if total is not None:
            payload['total'] = int(total)
        return jsonify(payload)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/entreprises/statuses', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@public_response_cache(300)
def get_entreprise_statuses():
    """
    API publique : Liste des statuts d'entreprise supportés.
    Utile côté intégration pour valider/mapper les événements (désabonnement, bounce, etc.).
    """
    return jsonify({
        'success': True,
        'data': _get_allowed_entreprise_statuses(),
    })


@api_public_bp.route('/entreprises/<int:entreprise_id>/statut', methods=['PATCH', 'POST'])
@api_token_required
@require_api_permission('entreprises')
def update_entreprise_statut_public(entreprise_id: int):
    """
    API publique : Met à jour le statut d'une entreprise.

    Body JSON:
        - statut (str, requis): nouveau statut (voir GET /api/public/entreprises/statuses)
        - note (str, optionnel): texte libre ajouté aux notes (audit) si fourni
    """
    payload = request.get_json(silent=True) or {}
    statut = (payload.get('statut') or '').strip()
    note = payload.get('note')
    return _update_entreprise_status(entreprise_id, statut=statut, note=note)


def _update_entreprise_status(entreprise_id: int, statut: str, note=None):
    try:
        entreprise = database.get_entreprise(entreprise_id)
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404

        if not statut:
            return jsonify({'success': False, 'error': 'Le champ "statut" est requis.'}), 400

        allowed = set(_get_allowed_entreprise_statuses())
        if statut not in allowed:
            return jsonify({
                'success': False,
                'error': 'Statut non supporté',
                'allowed': sorted(list(allowed), key=lambda s: s.lower()),
            }), 400

        updated = database.update_entreprise_statut(entreprise_id, statut)
        if updated is False:
            return jsonify({
                'success': False,
                'error': 'Statut non supporté',
                'allowed': sorted(list(allowed), key=lambda s: s.lower()),
            }), 400

        if isinstance(note, str) and note.strip():
            existing_notes = (entreprise.get('notes') or '').strip() if isinstance(entreprise, dict) else ''
            new_notes = (existing_notes + '\n' if existing_notes else '') + note.strip()
            try:
                database.update_entreprise_notes(entreprise_id, new_notes)
            except Exception:
                pass

        entreprise_updated = database.get_entreprise(entreprise_id)
        from utils.helpers import clean_json_dict
        entreprise_updated = clean_json_dict(entreprise_updated)

        return jsonify({'success': True, 'data': entreprise_updated})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/entreprises/<int:entreprise_id>/unsubscribe', methods=['POST'])
@api_token_required
@require_api_permission('entreprises')
def entreprise_unsubscribe_public(entreprise_id: int):
    """API publique : Marque une entreprise comme Désabonné."""
    payload = request.get_json(silent=True) or {}
    return _update_entreprise_status(entreprise_id, statut='Désabonné', note=payload.get('note'))


@api_public_bp.route('/entreprises/<int:entreprise_id>/negative-reply', methods=['POST'])
@api_token_required
@require_api_permission('entreprises')
def entreprise_negative_reply_public(entreprise_id: int):
    """API publique : Marque une entreprise comme Réponse négative."""
    payload = request.get_json(silent=True) or {}
    return _update_entreprise_status(entreprise_id, statut='Réponse négative', note=payload.get('note'))


@api_public_bp.route('/entreprises/<int:entreprise_id>/bounce', methods=['POST'])
@api_token_required
@require_api_permission('entreprises')
def entreprise_bounce_public(entreprise_id: int):
    """API publique : Marque une entreprise comme Bounce."""
    payload = request.get_json(silent=True) or {}
    return _update_entreprise_status(entreprise_id, statut='Bounce', note=payload.get('note'))


@api_public_bp.route('/entreprises/<int:entreprise_id>/positive-reply', methods=['POST'])
@api_token_required
@require_api_permission('entreprises')
def entreprise_positive_reply_public(entreprise_id: int):
    """API publique : Marque une entreprise comme Réponse positive."""
    payload = request.get_json(silent=True) or {}
    return _update_entreprise_status(entreprise_id, statut='Réponse positive', note=payload.get('note'))


@api_public_bp.route('/entreprises/<int:entreprise_id>/spam-complaint', methods=['POST'])
@api_token_required
@require_api_permission('entreprises')
def entreprise_spam_complaint_public(entreprise_id: int):
    """API publique : Marque une entreprise comme Plainte spam."""
    payload = request.get_json(silent=True) or {}
    return _update_entreprise_status(entreprise_id, statut='Plainte spam', note=payload.get('note'))


@api_public_bp.route('/entreprises/<int:entreprise_id>/do-not-contact', methods=['POST'])
@api_token_required
@require_api_permission('entreprises')
def entreprise_do_not_contact_public(entreprise_id: int):
    """API publique : Marque une entreprise comme Ne pas contacter."""
    payload = request.get_json(silent=True) or {}
    return _update_entreprise_status(entreprise_id, statut='Ne pas contacter', note=payload.get('note'))


@api_public_bp.route('/entreprises/<int:entreprise_id>/callback', methods=['POST'])
@api_token_required
@require_api_permission('entreprises')
def entreprise_callback_public(entreprise_id: int):
    """API publique : Marque une entreprise comme À rappeler."""
    payload = request.get_json(silent=True) or {}
    return _update_entreprise_status(entreprise_id, statut='À rappeler', note=payload.get('note'))


def _delete_entreprise_public(entreprise_id: int):
    """
    Supprime l'entreprise et les lignes liées (CASCADE côté schéma SQLite / FK PostgreSQL).
    """
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        database.execute_sql(cursor, 'SELECT id, nom FROM entreprises WHERE id = ?', (entreprise_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404

        try:
            nom = row['nom']
        except (TypeError, KeyError, IndexError):
            nom = row[1] if len(row) > 1 else None
        database.execute_sql(cursor, 'DELETE FROM entreprises WHERE id = ?', (entreprise_id,))
        conn.commit()
        conn.close()

        label = (nom or '').strip() or f'#{entreprise_id}'
        return jsonify({
            'success': True,
            'deleted_id': entreprise_id,
            'message': f'Entreprise « {label} » supprimée',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/entreprises/<int:entreprise_id>', methods=['DELETE'])
@api_token_required
@require_api_permission('entreprises')
@require_api_permission('entreprises_delete')
def delete_entreprise_public(entreprise_id: int):
    """
    API publique : suppression définitive d'une fiche entreprise.
    Nécessite la permission token « suppression entreprises » (can_delete_entreprises), en plus de la lecture entreprises.
    """
    return _delete_entreprise_public(entreprise_id)


@api_public_bp.route('/entreprises/<int:entreprise_id>', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@public_response_cache(35)
def get_entreprise(entreprise_id):
    """
    API publique : Détails d'une entreprise.
    """
    try:
        entreprise = database.get_entreprise(entreprise_id)

        if not entreprise:
            return jsonify({
                'success': False,
                'error': 'Entreprise introuvable'
            }), 404

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


@api_public_bp.route('/entreprises/by-email', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@require_api_permission('emails')
@public_response_cache(35)
def get_entreprise_by_email():
    """
    API publique : retrouver une entreprise à partir d'un email.

    Query params:
        email (str, requis)
        include_emails (bool, optionnel): si true, renvoie aussi tous les emails connus de l'entreprise
    """
    try:
        email_raw = request.args.get('email', '')
        email = _normalize_email(email_raw)
        if not email:
            return jsonify({'success': False, 'error': 'Paramètre "email" requis.'}), 400

        include_emails = str(request.args.get('include_emails', '')).lower() in ('1', 'true', 'yes')

        conn = database.get_connection()
        cursor = conn.cursor()

        # 1) priorité : emails scrappés (scraper_emails)
        database.execute_sql(cursor, '''
            SELECT entreprise_id, email, name_info, is_person, page_url, date_found
            FROM scraper_emails
            WHERE LOWER(email) = LOWER(?)
            ORDER BY date_found DESC
            LIMIT 1
        ''', (email,))
        row = cursor.fetchone()

        entreprise_id = None
        match = None
        if row:
            r = dict(row) if not isinstance(row, dict) else row
            entreprise_id = r.get('entreprise_id')
            name_info = None
            try:
                name_info = json.loads(r.get('name_info')) if r.get('name_info') else None
            except Exception:
                name_info = None
            match = {
                'source': 'scraper',
                'email': r.get('email'),
                'page_url': r.get('page_url'),
                'date_found': r.get('date_found'),
                'is_person': bool(r.get('is_person')) if r.get('is_person') is not None else None,
                'person': _extract_person_from_name_info(name_info),
            }
        else:
            # 2) fallback : email principal entreprise
            database.execute_sql(cursor, '''
                SELECT id
                FROM entreprises
                WHERE LOWER(email_principal) = LOWER(?)
                LIMIT 1
            ''', (email,))
            row2 = cursor.fetchone()
            if row2:
                entreprise_id = row2.get('id') if isinstance(row2, dict) else row2[0]
                match = {
                    'source': 'principal',
                    'email': email,
                    'page_url': None,
                    'date_found': None,
                    'is_person': None,
                    'person': None,
                }

        conn.close()

        if not entreprise_id:
            return jsonify({'success': False, 'error': 'Entreprise introuvable pour cet email.'}), 404

        entreprise = database.get_entreprise(int(entreprise_id))
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable.'}), 404

        from utils.helpers import clean_json_dict
        entreprise = clean_json_dict(entreprise)

        payload = {'success': True, 'data': {'entreprise': entreprise, 'match': match}}
        if include_emails:
            payload['data']['emails'] = _get_entreprise_emails_full(int(entreprise_id), include_primary=True)
            payload['data']['emails_count'] = len(payload['data']['emails'])

        return jsonify(payload)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/entreprises/by-website', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@public_response_cache(35)
def get_entreprise_by_website():
    """
    API publique : retrouver l'entreprise via son URL/domaine.

    Query params:
        website (str, requis): URL ou domaine.

    Returns:
        JSON: { success: True, data: <entreprise> }
    """
    try:
        website_raw = request.args.get('website', '')
        website = _normalize_url_for_analysis(website_raw)
        if not website:
            return jsonify({'success': False, 'error': 'Paramètre "website" requis (URL ou domaine).'}), 400

        entreprise_id = _get_entreprise_id_for_website(database, website)
        if not entreprise_id:
            return jsonify({'success': False, 'error': 'Entreprise introuvable pour ce website.'}), 404

        entreprise = database.get_entreprise(entreprise_id)
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable.'}), 404

        from utils.helpers import clean_json_dict
        entreprise = clean_json_dict(entreprise)

        return jsonify({
            'success': True,
            'data': entreprise,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/entreprises/by-phone', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@public_response_cache(35)
def get_entreprise_by_phone():
    """
    API publique : retrouver une entreprise à partir d'un numéro de téléphone.

    Query params:
        phone (str, requis) : numéro tel quel (ex. +33 6 12 34 56 78, 06 12 34 56 78, 0033…, numéros étrangers).
        include_phones (bool, optionnel) : si true, liste les téléphones connus (scraping + téléphone principal).
    """
    try:
        phone_raw = request.args.get('phone', '')
        if not (phone_raw or '').strip():
            return jsonify({'success': False, 'error': 'Paramètre "phone" requis.'}), 400

        include_phones = str(request.args.get('include_phones', '')).lower() in ('1', 'true', 'yes')

        entreprise_id, match = _find_entreprise_row_by_phone(database, phone_raw)
        if not entreprise_id:
            return jsonify({'success': False, 'error': 'Entreprise introuvable pour ce numéro.'}), 404

        entreprise = database.get_entreprise(int(entreprise_id))
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable.'}), 404

        from utils.helpers import clean_json_dict
        entreprise = clean_json_dict(entreprise)

        payload = {
            'success': True,
            'data': {
                'entreprise': entreprise,
                'match': match,
            },
        }
        if include_phones:
            payload['data']['phones'] = _get_entreprise_phones_list(int(entreprise_id), include_primary=True)
            payload['data']['phones_count'] = len(payload['data']['phones'])

        return jsonify(payload)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/entreprises/<int:entreprise_id>/emails', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@require_api_permission('emails')
@public_response_cache(20)
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

        # Utiliser la logique complète mais renvoyer un format simple (compatibilité)
        full_items = _get_entreprise_emails_full(entreprise_id, include_primary=False)

        emails = []
        for item in full_items:
            email = item.get('email')
            if not email:
                continue
            # Dériver un "nom" simple à partir de person ou name_info si dispo
            person = item.get('person') or {}
            full_name = person.get('full_name')
            if not full_name and person.get('first_name'):
                full_name = (person.get('first_name') + ' ' + (person.get('last_name') or '')).strip()

            if not full_name:
                analysis = item.get('analysis') or {}
                ni = analysis.get('name_info')
                if isinstance(ni, dict):
                    full_name = ni.get('full_name') or ni.get('name')
                elif isinstance(ni, str):
                    full_name = ni

            emails.append({
                'email': email,
                'nom': full_name,
                'page_url': item.get('page_url'),
                'date_scraping': item.get('date_found'),
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


@api_public_bp.route('/entreprises/<int:entreprise_id>/emails/all', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@require_api_permission('emails')
@public_response_cache(20)
def get_entreprise_emails_all(entreprise_id: int):
    """
    API publique : Tous les emails d'une entreprise (email_principal + emails scrapés),
    avec informations d'analyse (provider/type/risk_score/name_info/is_person) si disponibles.

    Query params:
        include_primary (bool, optionnel): inclure email_principal (défaut: true)
    """
    try:
        entreprise = database.get_entreprise(entreprise_id)
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404

        include_primary = str(request.args.get('include_primary', '1')).lower() in ('1', 'true', 'yes')
        items = _get_entreprise_emails_full(entreprise_id, include_primary=include_primary)
        return jsonify({
            'success': True,
            'entreprise_id': entreprise_id,
            'count': len(items),
            'data': items,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/entreprises/<int:entreprise_id>/phones', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@public_response_cache(20)
def get_entreprise_phones_public(entreprise_id: int):
    """
    API publique : telephones connus pour une entreprise (scraping + telephone principal).

    Query params:
        include_primary (bool, optionnel): inclure telephone principal (defaut: true)
    """
    try:
        entreprise = database.get_entreprise(entreprise_id)
        if not entreprise:
            return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404
        include_primary = str(request.args.get('include_primary', '1')).lower() in ('1', 'true', 'yes')
        items = _get_entreprise_phones_list(entreprise_id, include_primary=include_primary)
        from utils.helpers import clean_json_dict
        items = clean_json_dict(items)
        return jsonify({
            'success': True,
            'entreprise_id': entreprise_id,
            'count': len(items),
            'data': items,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/emails', methods=['GET'])
@api_token_required
@require_api_permission('emails')
@public_response_cache(20)
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


@api_public_bp.route('/token/info', methods=['GET'])
@api_token_required
@public_response_cache(15)
def public_api_token_info():
    """
    API publique : metadonnees du token courant (sans exposer la valeur complete).

    Permet au client mobile de verifier la validite du token et les permissions.
    """
    td = getattr(request, 'api_token', None) or {}
    raw = (td.get('token') or '') or ''
    preview = (raw[:10] + '…') if len(raw) > 10 else ('***' if raw else None)
    return jsonify({
        'success': True,
        'data': {
            'id': td.get('id'),
            'name': td.get('name'),
            'token_preview': preview,
            'app_url': td.get('app_url'),
            'user_id': td.get('user_id'),
            'permissions': {
                'entreprises': bool(td.get('can_read_entreprises')),
                'entreprises_delete': bool(td.get('can_read_entreprises')) and bool(td.get('can_delete_entreprises')),
                'emails': bool(td.get('can_read_emails')),
                'statistics': bool(td.get('can_read_statistics')),
                'campagnes': bool(td.get('can_read_campagnes')),
            },
            'last_used': str(td.get('last_used')) if td.get('last_used') is not None else None,
            'date_creation': str(td.get('date_creation')) if td.get('date_creation') is not None else None,
        },
    })


@api_public_bp.route('/statistics', methods=['GET'])
@api_token_required
@require_api_permission('statistics')
@public_response_cache(45)
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


@api_public_bp.route('/statistics/overview', methods=['GET'])
@api_token_required
@require_api_permission('statistics')
@public_response_cache(45)
def get_statistics_overview():
    """
    API publique : vue compacte pour mobile (KPI + tendance journaliere des entreprises).

    Query params:
        days (int, optionnel): fenetere pour la serie (defaut: 7, max: 90).
    """
    try:
        raw_days = request.args.get('days', '')
        try:
            days = int(raw_days) if raw_days not in (None, '') else 7
        except Exception:
            days = 7
        days = max(1, min(days, 90))
        data = database.get_mobile_dashboard_overview(trend_days=days)
        from utils.helpers import clean_json_dict
        return jsonify({'success': True, 'data': clean_json_dict(data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/reference/ciblage', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@public_response_cache(120)
def public_reference_ciblage():
    """
    API publique : listes de valeurs distinctes pour filtres (secteur, opportunite, statut entreprise, tags).
    """
    try:
        data = database.get_ciblage_suggestions()
        from utils.helpers import clean_json_dict
        return jsonify({'success': True, 'data': clean_json_dict(data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/reference/ciblage/counts', methods=['GET'])
@api_token_required
@require_api_permission('entreprises')
@public_response_cache(120)
def public_reference_ciblage_counts():
    """
    API publique : meme chose que /reference/ciblage avec effectifs par valeur (pour pickers / facettes).
    """
    try:
        data = database.get_ciblage_suggestions_with_counts()
        from utils.helpers import clean_json_dict
        return jsonify({'success': True, 'data': clean_json_dict(data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/website-analysis', methods=['GET', 'POST'])
@api_token_required
@require_api_permission('entreprises')
def public_website_analysis():
    """
    API publique (token) : Analyse d'un site web (par URL).

    Pas de cache GET (public_response_cache) : le rapport évolue pendant le traitement Celery ;
    une entrée 200 figée 90 s bloquerait le polling mobile (l’UI web utilise /api/website-analysis).

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
    use_lighthouse = bool(payload.get('use_lighthouse', SEO_USE_LIGHTHOUSE_DEFAULT))

    from tasks.scraping_tasks import scrape_emails_task
    from tasks.technical_analysis_tasks import technical_analysis_task
    from tasks.seo_tasks import seo_analysis_task
    from tasks.osint_tasks import osint_analysis_task
    from tasks.pentest_tasks import pentest_analysis_task
    from tasks.heavy_schedule import BulkSubtaskStagger

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
        )
        tasks_launched['seo_task_id'] = seo_task.id
    except Exception as e:
        tasks_launched['seo_error'] = str(e)

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
        'message': 'Analyses lancées. Utilisez GET /api/public/website-analysis?website=... pour récupérer le rapport.',
    }), 202


@api_public_bp.route('/campagnes/statuses', methods=['GET'])
@api_token_required
@require_api_permission('campagnes')
@public_response_cache(600)
def public_campagne_statuses():
    """
    API publique : statuts possibles pour une campagne email (filtrage / UI).
    """
    return jsonify({
        'success': True,
        'data': ['draft', 'scheduled', 'running', 'completed', 'failed'],
    })


@api_public_bp.route('/campagnes', methods=['GET'])
@api_token_required
@require_api_permission('campagnes')
@public_response_cache(25)
def get_campagnes():
    """
    API publique : Liste des campagnes email
    
    Query params:
        limit (int): Nombre maximum de résultats (défaut: 100, max: 1000)
        offset (int): Offset pour la pagination (défaut: 0)
        statut (str): Filtrer par statut (draft, running, completed, failed)
        entreprise_id (int, optionnel): Ne retourner que les campagnes associées à cette entreprise
            (envois enregistrés et campagnes programmées dont les destinataires incluent l'entreprise).
        
    Returns:
        JSON: Liste des campagnes avec leurs informations
    """
    try:
        from services.database.campagnes import CampagneManager
        
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        statut = request.args.get('statut')
        entreprise_id = request.args.get('entreprise_id', type=int)
        
        campagne_manager = CampagneManager()
        campagnes = campagne_manager.list_campagnes(
            statut=statut,
            limit=limit,
            offset=offset,
            entreprise_id=entreprise_id,
        )
        
        return jsonify({
            'success': True,
            'count': len(campagnes),
            'limit': limit,
            'offset': offset,
            'entreprise_id': entreprise_id,
            'data': campagnes
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_public_bp.route('/entreprises/<int:entreprise_id>/campagnes', methods=['GET'])
@api_token_required
@require_api_permission('campagnes')
@public_response_cache(25)
def get_campagnes_by_entreprise(entreprise_id: int):
    """
    API publique : campagnes liées à une entreprise (même filtre que GET /campagnes?entreprise_id=).
    """
    try:
        from services.database.campagnes import CampagneManager

        ent = database.get_entreprise(entreprise_id)
        if not ent:
            return jsonify({'success': False, 'error': 'Entreprise introuvable'}), 404

        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        statut = request.args.get('statut')

        campagne_manager = CampagneManager()
        campagnes = campagne_manager.list_campagnes(
            statut=statut,
            limit=limit,
            offset=offset,
            entreprise_id=entreprise_id,
        )
        return jsonify({
            'success': True,
            'count': len(campagnes),
            'limit': limit,
            'offset': offset,
            'entreprise_id': entreprise_id,
            'data': campagnes,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_public_bp.route('/campagnes/<int:campagne_id>', methods=['GET'])
@api_token_required
@require_api_permission('campagnes')
@public_response_cache(25)
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
@public_response_cache(25)
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
@public_response_cache(25)
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


@api_public_bp.route('/push/register', methods=['POST', 'DELETE'])
@api_token_required
def expo_push_register():
    """
    POST: enregistre un jeton Expo Push pour ce token API.
    DELETE: retire un jeton Expo Push pour ce token API.

    Body JSON:
        expo_push_token (str): ExponentPushToken[...]
        platform (str, POST seulement): android | ios (défaut android)
        installation_id (str, optionnel): identifiant stable d'installation.
    """
    try:
        from services.mobile_expo_push import register_device, unregister_device

        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type application/json requis'}), 400

        token_row = getattr(request, 'api_token', None) or {}
        api_token_id = token_row.get('id')
        if not api_token_id:
            return jsonify({'success': False, 'error': 'Token API invalide'}), 401

        body = request.get_json(silent=True) or {}
        expo_push_token = (body.get('expo_push_token') or '').strip()

        if request.method == 'DELETE':
            ok = unregister_device(int(api_token_id), expo_push_token)
            return jsonify({'success': True, 'removed': ok})

        platform = (body.get('platform') or 'android').strip()
        installation_id = body.get('installation_id')
        if installation_id is not None:
            installation_id = str(installation_id).strip() or None

        register_device(
            int(api_token_id),
            expo_push_token,
            platform=platform,
            installation_id=installation_id,
        )

        return jsonify({'success': True})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

