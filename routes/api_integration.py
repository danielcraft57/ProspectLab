"""
Blueprint pour les routes d'intégration internes (applications clientes)

Expose une API normalisée autour de la notion de "company" pour :
- Facturio
- MailPilot
- VocalGuard
"""

from flask import Blueprint, request, jsonify

from services.database import Database
from services.api_auth import client_api_key_required

api_integration_bp = Blueprint("api_integration", __name__, url_prefix="/api")

database = Database()


def _format_company_payload(entreprise: dict) -> dict:
    """
    Transforme une entreprise ProspectLab en payload JSON standard.
    """
    tags = entreprise.get("tags") or []
    if isinstance(tags, str):
        try:
            import json as _json

            tags = _json.loads(tags)
        except Exception:
            tags = []

    return {
        "id": entreprise.get("id"),
        "name": entreprise.get("nom"),
        "siret": entreprise.get("siret") if "siret" in entreprise else None,
        "vat_number": entreprise.get("vat_number") if "vat_number" in entreprise else None,
        "address": entreprise.get("address_1"),
        "city": entreprise.get("city") if "city" in entreprise else None,
        "zip": entreprise.get("zip") if "zip" in entreprise else None,
        "country": entreprise.get("pays"),
        "email": entreprise.get("email_principal"),
        "phone": entreprise.get("telephone"),
        "website": entreprise.get("website"),
        "status": entreprise.get("statut"),
        "tags": tags,
        "score": entreprise.get("score_securite"),
    }


@api_integration_bp.route("/companies/<int:company_id>")
@client_api_key_required
def get_company_by_id(company_id: int):
    """
    GET /api/companies/<id>
    Récupère toutes les infos d'une entreprise à partir de son identifiant ProspectLab.
    """
    try:
        entreprise = database.get_entreprise(company_id)
        if not entreprise:
            return jsonify({"success": False, "error": "Company not found"}), 404

        return jsonify({"success": True, "data": _format_company_payload(entreprise)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_integration_bp.route("/companies/by-email")
@client_api_key_required
def get_company_by_email():
    """
    GET /api/companies/by-email?email=...
    Pour MailPilot : retrouver l'entreprise depuis l'email d'un contact.
    """
    email = request.args.get("email")
    if not email:
        return jsonify({"success": False, "error": "Missing email parameter"}), 400

    try:
        conn = database.get_connection()
        cursor = conn.cursor()

        # Chercher dans les emails scrappés en priorité
        database.execute_sql(
            cursor,
            """
            SELECT entreprise_id
            FROM scraper_emails
            WHERE LOWER(email) = LOWER(?)
            ORDER BY date_found DESC
            LIMIT 1
            """,
            (email,),
        )
        row = cursor.fetchone()

        entreprise_id = None
        if row:
            entreprise_id = row["entreprise_id"] if isinstance(row, dict) else row[0]
        else:
            # Fallback éventuel sur email_principal de l'entreprise
            database.execute_sql(
                cursor,
                """
                SELECT id
                FROM entreprises
                WHERE LOWER(email_principal) = LOWER(?)
                LIMIT 1
                """,
                (email,),
            )
            row = cursor.fetchone()
            if row:
                entreprise_id = row["id"] if isinstance(row, dict) else row[0]

        conn.close()

        if not entreprise_id:
            return jsonify({"success": False, "error": "Company not found"}), 404

        entreprise = database.get_entreprise(entreprise_id)
        if not entreprise:
            return jsonify({"success": False, "error": "Company not found"}), 404

        return jsonify({"success": True, "data": _format_company_payload(entreprise)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_integration_bp.route("/companies/by-phone")
@client_api_key_required
def get_company_by_phone():
    """
    GET /api/companies/by-phone?phone=...
    Pour VocalGuard : retrouver l'entreprise depuis un numéro d'appel.
    """
    phone = request.args.get("phone")
    if not phone:
        return jsonify({"success": False, "error": "Missing phone parameter"}), 400

    try:
        conn = database.get_connection()
        cursor = conn.cursor()

        # Chercher dans les téléphones scrappés
        database.execute_sql(
            cursor,
            """
            SELECT entreprise_id
            FROM scraper_phones
            WHERE phone = ?
            ORDER BY date_found DESC
            LIMIT 1
            """,
            (phone,),
        )
        row = cursor.fetchone()

        entreprise_id = None
        if row:
            entreprise_id = row["entreprise_id"] if isinstance(row, dict) else row[0]
        else:
            # Fallback sur le téléphone principal de l'entreprise
            database.execute_sql(
                cursor,
                """
                SELECT id
                FROM entreprises
                WHERE telephone = ?
                LIMIT 1
                """,
                (phone,),
            )
            row = cursor.fetchone()
            if row:
                entreprise_id = row["id"] if isinstance(row, dict) else row[0]

        conn.close()

        if not entreprise_id:
            return jsonify({"success": False, "error": "Company not found"}), 404

        entreprise = database.get_entreprise(entreprise_id)
        if not entreprise:
            return jsonify({"success": False, "error": "Company not found"}), 404

        return jsonify({"success": True, "data": _format_company_payload(entreprise)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_integration_bp.route("/companies/by-domain")
@client_api_key_required
def get_company_by_domain():
    """
    GET /api/companies/by-domain?domain=...
    Optionnel : retrouver l'entreprise depuis un nom de domaine.
    """
    domain = request.args.get("domain")
    if not domain:
        return jsonify({"success": False, "error": "Missing domain parameter"}), 400

    # Normaliser un peu le domaine (retirer schéma/chemin éventuels)
    domain = domain.strip().lower()
    if domain.startswith("http://") or domain.startswith("https://"):
        # Garder seulement le host approximatif
        without_scheme = domain.split("://", 1)[1]
        domain = without_scheme.split("/", 1)[0]

    try:
        conn = database.get_connection()
        cursor = conn.cursor()

        # Chercher d'abord via le website de l'entreprise
        pattern = f"%{domain}%"
        database.execute_sql(
            cursor,
            """
            SELECT id
            FROM entreprises
            WHERE LOWER(website) LIKE LOWER(?)
            ORDER BY date_analyse DESC
            LIMIT 1
            """,
            (pattern,),
        )
        row = cursor.fetchone()

        entreprise_id = None
        if row:
            entreprise_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            # Fallback via les domaines d'emails scrappés
            database.execute_sql(
                cursor,
                """
                SELECT entreprise_id
                FROM scraper_emails
                WHERE LOWER(domain) = LOWER(?)
                ORDER BY date_found DESC
                LIMIT 1
                """,
                (domain,),
            )
            row = cursor.fetchone()
            if row:
                entreprise_id = row["entreprise_id"] if isinstance(row, dict) else row[0]

        conn.close()

        if not entreprise_id:
            return jsonify({"success": False, "error": "Company not found"}), 404

        entreprise = database.get_entreprise(entreprise_id)
        if not entreprise:
            return jsonify({"success": False, "error": "Company not found"}), 404

        return jsonify({"success": True, "data": _format_company_payload(entreprise)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_integration_bp.route("/companies/from-website", methods=["POST"])
@client_api_key_required
def create_or_update_company_from_website():
    """
    POST /api/companies/from-website

    Point d'entrée d'intégration pour CompetiScope (ou autres apps internes).

    Corps JSON attendu :
        - website (str, requis) : URL ou domaine du site (ex: "https://exemple.com")
        - name (str, optionnel) : nom lisible de l'entreprise
        - status (str, optionnel) : "prospect" ou "concurrent" (stocké dans le champ statut)
        - tags (list[str], optionnel) : tags additionnels (["CompetiScope", "SEO", ...])

    Comportement :
        - Normalise l'URL du site.
        - Cherche un duplicat existant (nom + website ou website seul).
        - Crée l'entreprise si nécessaire, avec le bon statut.
        - Met à jour les tags si fournis.

    Retourne :
        {
          "success": true,
          "created": bool,
          "entreprise_id": int,
          "data": { ... payload formaté ... }
        }
    """
    import urllib.parse
    import json as _json

    payload = request.get_json() or {}
    raw_website = (payload.get("website") or "").strip()
    name = (payload.get("name") or "").strip() or None
    status = (payload.get("status") or "").strip().lower() or None
    tags = payload.get("tags") or []

    if not raw_website:
        return jsonify({"success": False, "error": "Field 'website' is required"}), 400

    # Normaliser l'URL
    website = raw_website
    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    parsed = urllib.parse.urlparse(website)
    domain = parsed.netloc or website

    # Nom de base si non fourni
    if not name:
        name = domain

    # Statut normalisé (nouvelle échelle : Nouveau, À qualifier, Relance, Gagné, Perdu)
    # À la création, on force toujours "Nouveau". Les anciennes valeurs API (prospect/concurrent) ne sont plus utilisées.
    if status in ("prospect", "prospects"):
        statut_value = "Prospect"
    elif status in ("concurrent", "concurrents", "competition"):
        statut_value = "Concurrent"
    else:
        statut_value = None

    try:
        # Vérifier si l'entreprise existe déjà
        existing_id = database.find_duplicate_entreprise(name, website, None, None)

        created = False
        if existing_id:
            entreprise_id = existing_id
        else:
            # Nouvelle entreprise : forcer statut = "Nouveau" (aucun email envoyé)
            entreprise_data = {
                "name": name,
                "website": website,
                "statut": "Nouveau",
            }
            entreprise_id = database.save_entreprise(
                analyse_id=None,
                entreprise_data=entreprise_data,
                skip_duplicates=False,
            )
            created = True

        # Mettre à jour le statut uniquement pour une entreprise existante (si le payload envoie une valeur reconnue)
        if not created and statut_value:
            conn = database.get_connection()
            cursor = conn.cursor()
            database.execute_sql(
                cursor,
                "UPDATE entreprises SET statut = ? WHERE id = ?",
                (statut_value, entreprise_id),
            )
            conn.commit()
            conn.close()

        if tags:
            # Charger les tags existants et fusionner
            conn = database.get_connection()
            cursor = conn.cursor()
            database.execute_sql(
                cursor, "SELECT tags FROM entreprises WHERE id = ?", (entreprise_id,)
            )
            row = cursor.fetchone()
            existing_tags = []
            if row and row[0]:
                try:
                    existing_tags = _json.loads(row[0]) if isinstance(row[0], str) else row[0]
                except Exception:
                    existing_tags = []

            merged = list({t.strip() for t in (existing_tags or []) + tags if isinstance(t, str) and t.strip()})
            database.execute_sql(
                cursor,
                "UPDATE entreprises SET tags = ? WHERE id = ?",
                (_json.dumps(merged), entreprise_id),
            )
            conn.commit()
            conn.close()

        entreprise = database.get_entreprise(entreprise_id)
        return jsonify(
            {
                "success": True,
                "created": created,
                "entreprise_id": entreprise_id,
                "data": _format_company_payload(entreprise),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

