#!/usr/bin/env python3
"""
Récupère des bounces directement depuis une boite mail IMAP et tagge ProspectLab.

Idée:
- Se connecter en IMAP à la boite qui reçoit les NDR (mailer-daemon / postmaster)
- Chercher des messages récents qui ressemblent à un bounce
- Extraire les destinataires (Final-Recipient, Original-Recipient, "for <...>", ou regex)
- Marquer le dernier email_envoye correspondant en statut "bounced"
- Passer l'entreprise en statut "Bounce" et ajouter le tag "bounce"

Par défaut, tourne en dry-run. Utiliser --apply pour écrire en base.

Variables d'env (à mettre dans .env ou .env.prod):
- IMAP_HOST (ex: imap.gmail.com, mail.domaine.fr)
- IMAP_PORT (défaut 993 si SSL, sinon 143)
- IMAP_USERNAME
- IMAP_PASSWORD
- IMAP_SSL (true/false, défaut true)
- IMAP_MAILBOX (défaut INBOX)
Optionnel:
- IMAP_SINCE_DAYS (défaut 14)
"""

from __future__ import annotations

import argparse
import email
import imaplib
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import Database  # noqa: E402
from services.database.campagnes import CampagneManager  # noqa: E402


BOUNCE_HINTS = (
    "Undelivery mail returned to sender",
    "Undelivered Mail Returned to Sender",
    "Delivery Status Notification",
    "Mail delivery failed",
    "Returned mail",
    "failure notice",
    "Delivery failure",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch IMAP bounces et tagge la BDD ProspectLab.")
    p.add_argument("--campagne-id", type=int, default=None, help="Optionnel: restreindre à une campagne.")
    p.add_argument("--days", type=int, default=None, help="Fenêtre en jours (défaut IMAP_SINCE_DAYS ou 14).")
    p.add_argument("--apply", action="store_true", help="Applique les changements (sinon dry-run).")
    p.add_argument(
        "--profiles",
        type=str,
        default=None,
        help=(
            "Liste de profils IMAP à scanner (séparés par virgule). "
            "Si absent: utilise IMAP_PROFILES ou 'default'."
        ),
    )
    p.add_argument(
        "--delete-processed",
        action="store_true",
        help="Après tagging (apply), supprime/déplace en corbeille les bounces traités (évite de les retraiter).",
    )
    p.add_argument(
        "--trash-mailbox",
        type=str,
        default=None,
        help="Boite IMAP de corbeille (ex Gmail: [Gmail]/Trash). Si absent, tentative auto.",
    )
    p.add_argument("--db-path", type=str, default=None, help="Chemin SQLite optionnel (ignoré si DATABASE_URL défini).")
    p.add_argument("--limit", type=int, default=0, help="Limite de messages IMAP à scanner (0 = sans limite).")
    p.add_argument("--reason", type=str, default="bounce imap", help="Texte stocké dans emails_envoyes.erreur.")
    p.add_argument(
        "--debug",
        action="store_true",
        help="Affiche quelques adresses extraites pour diagnostiquer les matchs.",
    )
    return p.parse_args()


def _load_env_if_present() -> None:
    root = Path(__file__).parent.parent
    env_path = root / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=str(env_path), override=False)
        return
    except Exception:
        pass
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_bool(key: str, default: bool) -> bool:
    v = (os.getenv(key) or "").strip().lower()
    if not v:
        return default
    return v in {"1", "true", "yes", "on"}

def _env_get_profile(key: str, profile: str | None) -> str | None:
    """
    Lecture d'env avec support des profils:
    - profile=None ou 'default' -> KEY
    - profile='gmail' -> KEY_GMAIL
    """
    if not profile or str(profile).strip().lower() in {"default", "main"}:
        return os.getenv(key)
    suffix = str(profile).strip().upper()
    return os.getenv(f"{key}_{suffix}") or os.getenv(key)

def _env_bool_profile(key: str, profile: str | None, default: bool) -> bool:
    v = (_env_get_profile(key, profile) or "").strip().lower()
    if not v:
        return default
    return v in {"1", "true", "yes", "on"}

def _env_int_profile(key: str, profile: str | None, default: int) -> int:
    raw = (_env_get_profile(key, profile) or "").strip()
    try:
        return int(raw)
    except Exception:
        return int(default)

def _get_profiles(args: argparse.Namespace) -> list[str]:
    if args.profiles:
        return [p.strip() for p in str(args.profiles).split(",") if p.strip()]
    env_profiles = (os.getenv("IMAP_PROFILES") or "").strip()
    if env_profiles:
        return [p.strip() for p in env_profiles.split(",") if p.strip()]
    return ["default"]


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    try:
        parts = decode_header(value)
        out = ""
        for chunk, enc in parts:
            if isinstance(chunk, bytes):
                out += chunk.decode(enc or "utf-8", errors="ignore")
            else:
                out += str(chunk)
        return out
    except Exception:
        return str(value)


def _get_text_payload(msg: email.message.Message) -> str:
    if msg.is_multipart():
        texts: list[str] = []
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            if ctype in {"text/plain", "message/delivery-status"}:
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    texts.append(payload.decode(charset, errors="ignore"))
                except Exception:
                    continue
        return "\n".join(texts)
    try:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="ignore")
    except Exception:
        return ""


def _looks_like_bounce(subject: str, from_addr: str, body: str) -> bool:
    blob = f"{subject}\n{from_addr}\n{body}".lower()
    if any(h.lower() in blob for h in BOUNCE_HINTS):
        return True
    if "mailer-daemon" in blob or "postmaster" in blob:
        return True
    if "delivery-status" in blob or "status:" in blob and "diagnostic-code" in blob:
        return True
    return False


def _extract_recipients(subject: str, body: str) -> list[str]:
    s = f"{subject}\n{body}"

    # DSN fields: Final-Recipient / Original-Recipient
    dsn = re.findall(r"(?im)^(final-recipient|original-recipient)\s*:\s*[^;]*;\s*([^\s<>\"']+)", s)
    out: list[str] = []
    for _, addr in dsn or []:
        out.append(addr.strip())

    # for <recipient@...>
    for_addr = re.findall(r"(?im)\bfor\s*<([^>]+@[^>]+)>", s)
    out.extend(a.strip() for a in for_addr if a and "@" in a)

    # fallback regex
    if not out:
        out = re.findall(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", s) or []

    # nettoyage
    cleaned: list[str] = []
    seen = set()
    bad_domain_suffixes = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".css",
        ".js",
        ".ico",
        ".pdf",
        ".mp4",
        ".webm",
    }
    for e in out:
        es = (e or "").strip().lower()
        if not es or "@" not in es:
            continue
        # Éviter les faux positifs du type "logo@2x.png" ou "...@site.jpg"
        try:
            local, domain = es.split("@", 1)
        except Exception:
            continue
        if not local or not domain or "." not in domain:
            continue
        if any(domain.endswith(suf) for suf in bad_domain_suffixes):
            continue
        if "/" in es or "\\" in es:
            continue
        if es in seen:
            continue
        seen.add(es)
        cleaned.append(es)
    return cleaned


def _filter_to_known_sent_emails(db: Database, emails: list[str], campagne_id: int | None) -> list[str]:
    if not emails:
        return []

    conn = db.get_connection()
    cursor = conn.cursor()
    keep: set[str] = set()

    chunk_size = 300
    for i in range(0, len(emails), chunk_size):
        chunk = emails[i : i + chunk_size]
        placeholders = ",".join(["?"] * len(chunk))
        if campagne_id:
            db.execute_sql(
                cursor,
                f"SELECT DISTINCT LOWER(email) as email FROM emails_envoyes WHERE campagne_id = ? AND LOWER(email) IN ({placeholders})",
                (int(campagne_id), *chunk),
            )
        else:
            db.execute_sql(
                cursor,
                f"SELECT DISTINCT LOWER(email) as email FROM emails_envoyes WHERE LOWER(email) IN ({placeholders})",
                tuple(chunk),
            )
        for row in cursor.fetchall() or []:
            v = row.get("email") if isinstance(row, dict) else row[0]
            if v:
                keep.add(str(v).strip().lower())

    conn.close()
    return [e for e in emails if e in keep]


def _imap_date_since(days: int) -> str:
    # IMAP uses e.g. 30-Mar-2026
    dt = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    return dt.strftime("%d-%b-%Y")

def _imap_list_mailboxes(imap: imaplib.IMAP4) -> list[str]:
    try:
        typ, data = imap.list()
        if typ != "OK" or not data:
            return []
        out: list[str] = []
        for raw in data:
            if not raw:
                continue
            s = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
            # format IMAP: (... ) "/" "Mailbox Name"
            m = re.search(r'\"([^\"]+)\"\s*$', s)
            if m:
                out.append(m.group(1))
            else:
                parts = s.split(' "/" ')
                if len(parts) >= 2:
                    out.append(parts[-1].strip().strip('"'))
        return out
    except Exception:
        return []

def _guess_trash_mailbox(imap: imaplib.IMAP4, host: str, user: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    # heuristique Gmail
    h = (host or "").lower()
    u = (user or "").lower()
    if "gmail" in h or u.endswith("@gmail.com") or u.endswith("@googlemail.com"):
        return "[Gmail]/Trash"
    # fallback: scanner la liste
    boxes = _imap_list_mailboxes(imap)
    for candidate in ("Trash", "INBOX.Trash", "Corbeille", "Deleted Items", "Deleted Messages", "Deleted"):
        if candidate in boxes:
            return candidate
    for b in boxes:
        bl = b.lower()
        if "trash" in bl or "corbeille" in bl or "deleted" in bl:
            return b
    return None

def _is_gmail_imap(imap: imaplib.IMAP4, host: str | None = None, user: str | None = None) -> bool:
    try:
        caps = getattr(imap, "capabilities", None)
        if caps and any(str(c).upper() == "X-GM-EXT-1" for c in caps):
            return True
    except Exception:
        pass
    h = (host or "").lower()
    u = (user or "").lower()
    return ("gmail" in h) or u.endswith("@gmail.com") or u.endswith("@googlemail.com")


def _gmail_trash(imap: imaplib.IMAP4, uid: str, debug: bool = False) -> bool:
    """
    Gmail IMAP: suppression fiable via labels.
    - ajoute \\Trash
    - enlève \\Inbox (sinon reste visible)
    """
    try:
        typ1, data1 = imap.uid("STORE", uid, "+X-GM-LABELS", "\\Trash")
        typ2, data2 = imap.uid("STORE", uid, "-X-GM-LABELS", "\\Inbox")
        if debug:
            print(f"[Gmail] uid={uid} STORE +Trash typ={typ1} resp={data1[:1] if isinstance(data1, list) else data1}")
            print(f"[Gmail] uid={uid} STORE -Inbox typ={typ2} resp={data2[:1] if isinstance(data2, list) else data2}")
        return typ1 == "OK" or typ2 == "OK"
    except Exception:
        return False


def _move_to_trash_or_delete(
    imap: imaplib.IMAP4,
    msg_id: bytes,
    uid: str | None,
    trash_mailbox: str | None,
    host: str | None = None,
    user: str | None = None,
    debug: bool = False,
) -> bool:
    """
    Essaie d'abord de copier vers la corbeille (si dispo), puis marque en \\Deleted et expunge.
    """
    # Gmail: préférer le mécanisme labels (plus fiable que \\Deleted/EXPUNGE)
    if _is_gmail_imap(imap, host=host, user=user):
        if not uid:
            if debug:
                print("[Gmail] UID manquant - impossible de déplacer en corbeille.")
            return False
        return _gmail_trash(imap, uid, debug=debug)

    ok_copy = False
    if trash_mailbox:
        try:
            typ, _ = imap.copy(msg_id, trash_mailbox)
            ok_copy = (typ == "OK")
        except Exception:
            ok_copy = False
    try:
        imap.store(msg_id, "+FLAGS", "\\Deleted")
        imap.expunge()
        return True if ok_copy or True else False
    except Exception:
        return ok_copy


def main() -> int:
    args = parse_args()
    _load_env_if_present()

    db = Database(db_path=args.db_path)
    cm = CampagneManager()

    profiles = _get_profiles(args)
    any_ok = False

    for profile in profiles:
        host = (_env_get_profile("IMAP_HOST", profile) or "").strip()
        user = (_env_get_profile("IMAP_USERNAME", profile) or "").strip()
        password = (_env_get_profile("IMAP_PASSWORD", profile) or "").strip()
        mailbox = (_env_get_profile("IMAP_MAILBOX", profile) or "INBOX").strip() or "INBOX"
        ssl_enabled = _env_bool_profile("IMAP_SSL", profile, True)
        port = _env_int_profile("IMAP_PORT", profile, 993 if ssl_enabled else 143)

        days = args.days
        if days is None:
            d_env = (_env_get_profile("IMAP_SINCE_DAYS", profile) or "").strip()
            days = int(d_env) if d_env.isdigit() else 14
        if days <= 0:
            days = 14

        print("")
        print("=== Fetch bounces IMAP ===")
        print(f"Profil: {profile}")
        print(f"Host: {host or '(manquant)'}")
        print(f"Mailbox: {mailbox}")
        print(f"Since: {_imap_date_since(days)} ({days} jours)")
        print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        print(f"Campagne: {args.campagne_id if args.campagne_id else '(toutes)'}")
        if args.delete_processed and not args.apply:
            print("[INFO] --delete-processed ignoré en dry-run (ajoute --apply pour supprimer).")

        if not host or not user or not password:
            print("[WARN] IMAP_HOST / IMAP_USERNAME / IMAP_PASSWORD manquants pour ce profil, je saute.")
            continue

        since = _imap_date_since(days)
        imap = imaplib.IMAP4_SSL(host, port) if ssl_enabled else imaplib.IMAP4(host, port)

        try:
            imap.login(user, password)
            imap.select(mailbox)

            typ, data = imap.search(None, "SINCE", since)
            if typ != "OK":
                print("[ERREUR] IMAP search a échoué.")
                continue

            ids = (data[0] or b"").split()
            if not ids:
                print("[INFO] Aucun message sur la fenêtre demandée.")
                any_ok = True
                continue

            if int(args.limit or 0) > 0:
                ids = ids[-int(args.limit) :]
            ids = list(reversed(ids))

            total_scanned = 0
            total_bounce_like = 0
            total_recipients_found = 0
            total_recipients_known = 0
            total_tagged = 0
            total_deleted = 0
            debug_extracted: list[str] = []
            debug_known: list[str] = []
            trash_box = _guess_trash_mailbox(imap, host=host, user=user, explicit=args.trash_mailbox) if args.delete_processed else None

            for mid in ids:
                total_scanned += 1
                typ, msg_data = imap.fetch(mid, "(RFC822 UID)")
                if typ != "OK" or not msg_data:
                    continue

                uid = None
                try:
                    meta = msg_data[0][0]
                    meta_s = meta.decode("utf-8", errors="ignore") if isinstance(meta, (bytes, bytearray)) else str(meta)
                    m = re.search(r"\bUID\s+(\d+)\b", meta_s)
                    if m:
                        uid = m.group(1)
                except Exception:
                    uid = None

                raw = msg_data[0][1]
                if not raw:
                    continue

                try:
                    msg = email.message_from_bytes(raw)
                except Exception:
                    continue

                subject = _decode_header_value(msg.get("Subject"))
                from_addr = _decode_header_value(msg.get("From"))
                body = _get_text_payload(msg)

                if not _looks_like_bounce(subject, from_addr, body):
                    continue

                total_bounce_like += 1
                recipients = _extract_recipients(subject, body)
                if not recipients:
                    continue

                total_recipients_found += len(recipients)
                if args.debug and len(debug_extracted) < 30:
                    for r in recipients:
                        if len(debug_extracted) >= 30:
                            break
                        debug_extracted.append(r)

                known = _filter_to_known_sent_emails(db, recipients, args.campagne_id)
                if not known:
                    continue

                total_recipients_known += len(known)
                if args.debug and len(debug_known) < 30:
                    for r in known:
                        if len(debug_known) >= 30:
                            break
                        debug_known.append(r)

                tagged_any = False
                for rcpt in known:
                    if not args.apply:
                        total_tagged += 1
                        tagged_any = True
                        continue
                    email_id = cm.mark_latest_email_bounced_for_recipient(
                        recipient_email=rcpt,
                        campagne_id=args.campagne_id,
                        reason=args.reason,
                    )
                    if email_id:
                        total_tagged += 1
                        tagged_any = True

                if args.apply and args.delete_processed and tagged_any:
                    if _move_to_trash_or_delete(
                        imap,
                        mid,
                        uid,
                        trash_box,
                        host=host,
                        user=user,
                        debug=bool(args.debug),
                    ):
                        total_deleted += 1

            print("")
            print("=== Résultat ===")
            print(f"Messages scannés: {total_scanned}")
            print(f"Messages type bounce: {total_bounce_like}")
            print(f"Destinataires trouvés (brut): {total_recipients_found}")
            print(f"Destinataires reconnus en base: {total_recipients_known}")
            print(f"Taggés bounced: {total_tagged}")
            if args.apply and args.delete_processed:
                print(f"Bounces supprimés/déplacés: {total_deleted}")
            if not args.apply:
                print("Aucune écriture effectuée (dry-run). Relance avec --apply pour écrire en base.")
            if args.debug:
                print("")
                print("=== Debug (exemples) ===")
                print(f"Extraits (max 30): {debug_extracted}")
                print(f"Reconnus (max 30): {debug_known}")

            any_ok = True
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    return 0 if any_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

