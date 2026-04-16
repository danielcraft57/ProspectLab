"""
API : comptes SMTP / domaines d'envoi (multi-marques).
"""

from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from services.auth import login_required
from services.database import Database
from services.email_sender import EmailSender
from services.mail_dns_check import check_domain_mail_dns
from services.smtp_probe import probe_smtp

mail_accounts_bp = Blueprint("mail_accounts", __name__, url_prefix="/api/mail-accounts")


def _parse_bool(v, default=False):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off", ""):
        return False
    return default


@mail_accounts_bp.route("", methods=["GET"])
@login_required
def list_accounts():
    db = Database()
    rows = db.list_mail_accounts(active_only=False)
    return jsonify({"success": True, "accounts": rows})


@mail_accounts_bp.route("/<int:account_id>", methods=["GET"])
@login_required
def get_account(account_id):
    db = Database()
    row = db.get_mail_account(account_id)
    if not row:
        return jsonify({"error": "Compte introuvable"}), 404
    return jsonify({"success": True, "account": row})


@mail_accounts_bp.route("", methods=["POST"])
@login_required
def create_account():
    data = request.get_json() or {}
    if not (data.get("smtp_host") or "").strip():
        return jsonify({"error": "smtp_host requis"}), 400
    if not (data.get("default_sender") or "").strip():
        return jsonify({"error": "default_sender requis (en-tête From)"}), 400
    if not (data.get("slug") or "").strip():
        return jsonify({"error": "slug requis (identifiant unique, ex. danielcraft)"}), 400

    db = Database()
    try:
        aid = db.create_mail_account(
            slug=data.get("slug") or "",
            label=(data.get("label") or "").strip() or (data.get("slug") or "Compte"),
            smtp_host=(data.get("smtp_host") or "").strip(),
            default_sender=(data.get("default_sender") or "").strip(),
            smtp_port=int(data.get("smtp_port") or 587),
            smtp_use_tls=_parse_bool(data.get("smtp_use_tls"), True),
            smtp_use_ssl=_parse_bool(data.get("smtp_use_ssl"), False),
            smtp_username=(data.get("smtp_username") or "").strip() or None,
            smtp_password=data.get("smtp_password"),
            domain_name=(data.get("domain_name") or "").strip() or None,
            reply_to=(data.get("reply_to") or "").strip() or None,
            is_active=_parse_bool(data.get("is_active"), True),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        err = str(e).lower()
        if "unique" in err or "duplicate" in err:
            return jsonify({"error": "Ce slug est déjà utilisé."}), 409
        raise
    row = db.get_mail_account(aid)
    return jsonify({"success": True, "account": row, "id": aid}), 201


@mail_accounts_bp.route("/<int:account_id>", methods=["PATCH"])
@login_required
def patch_account(account_id):
    data = request.get_json() or {}
    db = Database()
    existing = db.get_mail_account(account_id)
    if not existing:
        return jsonify({"error": "Compte introuvable"}), 404

    kw = {}
    for k in (
        "slug",
        "label",
        "domain_name",
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "default_sender",
        "reply_to",
    ):
        if k in data:
            kw[k] = data.get(k)

    if "smtp_use_tls" in data:
        kw["smtp_use_tls"] = _parse_bool(data.get("smtp_use_tls"), True)
    if "smtp_use_ssl" in data:
        kw["smtp_use_ssl"] = _parse_bool(data.get("smtp_use_ssl"), False)
    if "is_active" in data:
        kw["is_active"] = _parse_bool(data.get("is_active"), True)
    if "smtp_password" in data:
        pwd = data.get("smtp_password")
        if pwd is None or str(pwd).strip() == "":
            kw["clear_password"] = True
        else:
            kw["smtp_password"] = pwd

    if not kw:
        return jsonify({"error": "Aucune modification"}), 400

    try:
        ok = db.update_mail_account(account_id, **kw)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        err = str(e).lower()
        if "unique" in err or "duplicate" in err:
            return jsonify({"error": "Ce slug est déjà utilisé."}), 409
        raise
    if not ok:
        return jsonify({"error": "Mise à jour impossible"}), 400
    row = db.get_mail_account(account_id)
    return jsonify({"success": True, "account": row})


@mail_accounts_bp.route("/<int:account_id>", methods=["DELETE"])
@login_required
def delete_account(account_id):
    db = Database()
    if not db.get_mail_account(account_id):
        return jsonify({"error": "Compte introuvable"}), 404
    db.delete_mail_account(account_id)
    return jsonify({"success": True})


@mail_accounts_bp.route("/probe-raw", methods=["POST"])
@login_required
def probe_raw():
    """
    Test SMTP sans enregistrement (saisie formulaire).
    """
    data = request.get_json() or {}
    host = (data.get("smtp_host") or "").strip()
    if not host:
        return jsonify({"error": "smtp_host requis"}), 400
    port = int(data.get("smtp_port") or 587)
    use_tls = _parse_bool(data.get("smtp_use_tls"), True)
    use_ssl = _parse_bool(data.get("smtp_use_ssl"), False)
    user = (data.get("smtp_username") or "").strip() or None
    password = data.get("smtp_password") or ""

    res = probe_smtp(host, port, use_tls, use_ssl, user, password)
    return jsonify({"success": res.get("success"), **res})


@mail_accounts_bp.route("/<int:account_id>/probe", methods=["POST"])
@login_required
def probe_saved(account_id):
    db = Database()
    acc = db.get_mail_account_decrypted(account_id)
    if not acc:
        return jsonify({"error": "Compte introuvable ou inactif"}), 404
    res = probe_smtp(
        acc["smtp_host"],
        int(acc.get("smtp_port") or 587),
        bool(int(acc.get("smtp_use_tls", 1))),
        bool(int(acc.get("smtp_use_ssl", 0))),
        (acc.get("smtp_username") or "").strip() or None,
        acc.get("smtp_password") or "",
    )
    db.record_smtp_test(account_id, bool(res.get("success")), res.get("message", "") + (res.get("detail") or ""))
    return jsonify({"success": res.get("success"), **res})


@mail_accounts_bp.route("/<int:account_id>/send-test", methods=["POST"])
@login_required
def send_test(account_id):
    data = request.get_json() or {}
    to_addr = (data.get("to") or "").strip()
    if not to_addr:
        return jsonify({"error": "Champ \"to\" (destinataire) requis"}), 400

    db = Database()
    acc = db.get_mail_account_decrypted(account_id)
    if not acc:
        return jsonify({"error": "Compte introuvable ou inactif"}), 404

    sender = EmailSender.from_mail_account(acc)
    subj = data.get("subject") or "[ProspectLab] Test compte SMTP"
    body = data.get("body") or (
        f"Message de test pour le compte « {acc.get('label') or acc.get('slug')} ».\n"
        f"Expéditeur : {acc.get('default_sender')}\n"
    )
    result = sender.send_email(to=to_addr, subject=subj, body=body, html_body=data.get("html_body"))
    db.record_smtp_test(account_id, bool(result.get("success")), result.get("message", ""))
    status = 200 if result.get("success") else 502
    return jsonify({"success": result.get("success"), "message": result.get("message")}), status


@mail_accounts_bp.route("/<int:account_id>/check-dns", methods=["POST"])
@login_required
def check_dns(account_id):
    db = Database()
    acc = db.get_mail_account(account_id)
    if not acc:
        return jsonify({"error": "Compte introuvable"}), 404
    domain = (acc.get("domain_name") or "").strip()
    if not domain:
        return jsonify({"error": "domain_name non renseigné pour ce compte"}), 400

    report = check_domain_mail_dns(domain)
    db.record_dns_check(account_id, json.dumps(report, ensure_ascii=False))
    return jsonify({"success": True, "report": report})


@mail_accounts_bp.route("/check-dns-raw", methods=["POST"])
@login_required
def check_dns_raw():
    data = request.get_json() or {}
    domain = (data.get("domain") or "").strip()
    if not domain:
        return jsonify({"error": "domain requis"}), 400
    report = check_domain_mail_dns(domain)
    return jsonify({"success": True, "report": report})
