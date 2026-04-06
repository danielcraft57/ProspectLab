#!/usr/bin/env python3
"""
Import simple de bounces (NDR) dans ProspectLab.

But:
- Extraire des adresses email de retours type "Undelivery mail returned to sender"
  (copier-coller du mail, export .eml/.mbox, ou un fichier .txt)
- Marquer le dernier email envoyé correspondant en "bounced"
- Passer l'entreprise en statut "Bounce" et ajouter le tag "bounce"

Par défaut, le script tourne en dry-run. Utiliser --apply pour écrire en base.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import Database  # noqa: E402
from services.database.campagnes import CampagneManager  # noqa: E402


BOUNCE_HINT_PATTERNS = (
    "Undelivery mail returned to sender",
    "Undelivered Mail Returned to Sender",
    "Delivery Status Notification",
    "Mail delivery failed",
    "Returned mail",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Importe des bounces et tagge la BDD.")
    p.add_argument("--input", type=str, required=True, help="Chemin du fichier à analyser (txt/eml/mbox).")
    p.add_argument("--campagne-id", type=int, default=None, help="Optionnel: restreindre à une campagne.")
    p.add_argument("--reason", type=str, default="bounce import", help="Texte stocké dans emails_envoyes.erreur.")
    p.add_argument("--apply", action="store_true", help="Applique les changements (sinon dry-run).")
    p.add_argument("--db-path", type=str, default=None, help="Chemin SQLite optionnel (ignoré si DATABASE_URL défini).")
    p.add_argument("--max", type=int, default=5000, help="Nombre max d'emails à traiter (défaut: 5000).")
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


def _extract_candidate_recipients(text: str) -> list[str]:
    """
    Essaie d'extraire les destinataires depuis des champs DSN usuels,
    sinon retombe sur une extraction d'emails par regex.
    """
    s = text or ""

    # DSN fields: Final-Recipient / Original-Recipient
    dsn = re.findall(r"(?im)^(final-recipient|original-recipient)\s*:\s*[^;]*;\s*([^\s<>\"']+)", s)
    out: list[str] = []
    for _, addr in dsn or []:
        out.append(addr.strip())

    # Some MTAs provide "To:" or "for <recipient@...>"
    for_addr = re.findall(r"(?im)\bfor\s*<([^>]+@[^>]+)>", s)
    out.extend(a.strip() for a in for_addr if a and "@" in a)

    if out:
        return out

    # Fallback: regex email addresses
    candidates = re.findall(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", s)
    return [c.strip() for c in candidates]


def _filter_to_known_sent_emails(db: Database, emails: list[str], campagne_id: int | None) -> list[str]:
    """
    On ne garde que les adresses réellement présentes dans emails_envoyes,
    comme ça on évite de tagger l'expéditeur, postmaster, etc.
    """
    cleaned: list[str] = []
    seen = set()
    for e in emails:
        es = (e or "").strip().lower()
        if not es or "@" not in es:
            continue
        if es in seen:
            continue
        seen.add(es)
        cleaned.append(es)

    if not cleaned:
        return []

    # limiter pour éviter des requêtes énormes
    cleaned = cleaned[:20000]

    conn = db.get_connection()
    cursor = conn.cursor()
    keep: set[str] = set()

    chunk_size = 400
    for i in range(0, len(cleaned), chunk_size):
        chunk = cleaned[i : i + chunk_size]
        placeholders = ",".join(["?"] * len(chunk))
        if campagne_id:
            db.execute_sql(
                cursor,
                f"SELECT DISTINCT email FROM emails_envoyes WHERE campagne_id = ? AND email IN ({placeholders})",
                (int(campagne_id), *chunk),
            )
        else:
            db.execute_sql(
                cursor,
                f"SELECT DISTINCT email FROM emails_envoyes WHERE email IN ({placeholders})",
                tuple(chunk),
            )
        for row in cursor.fetchall() or []:
            v = row.get("email") if isinstance(row, dict) else row[0]
            if v:
                keep.add(str(v).strip().lower())

    conn.close()
    return [e for e in cleaned if e in keep]


def main() -> int:
    args = parse_args()
    _load_env_if_present()

    path = Path(args.input)
    if not path.exists() or not path.is_file():
        print(f"[ERREUR] Fichier introuvable: {path}")
        return 2

    raw = path.read_text(encoding="utf-8", errors="ignore")
    has_hint = any(h.lower() in raw.lower() for h in BOUNCE_HINT_PATTERNS)
    if not has_hint:
        print("[INFO] Je ne vois pas de phrase 'bounce' évidente dans le fichier.")
        print("[INFO] Je tente quand même d'extraire des destinataires via les entêtes DSN/regex.")

    candidates = _extract_candidate_recipients(raw)
    if not candidates:
        print("[ERREUR] Aucune adresse email détectée dans le fichier.")
        return 3

    db = Database(db_path=args.db_path)
    known = _filter_to_known_sent_emails(db, candidates, args.campagne_id)
    if not known:
        print("[ERREUR] Aucune des adresses détectées ne correspond à des emails envoyés en base.")
        print("[INFO] Vérifie que tu importes bien un bounce lié à une campagne ProspectLab, ou passe --campagne-id.")
        return 4

    known = known[: max(1, int(args.max))]
    cm = CampagneManager()

    print("=== Import bounces ProspectLab ===")
    print(f"Fichier: {path}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Campagne: {args.campagne_id if args.campagne_id else '(toutes)'}")
    print(f"Emails candidats détectés: {len(candidates)}")
    print(f"Emails reconnus en base: {len(known)}")

    marked = 0
    not_found = 0

    for email in known:
        if not args.apply:
            # en dry-run, on simule juste
            marked += 1
            continue
        email_id = cm.mark_latest_email_bounced_for_recipient(
            recipient_email=email,
            campagne_id=args.campagne_id,
            reason=args.reason,
        )
        if email_id:
            marked += 1
        else:
            not_found += 1

    print("")
    print("=== Résultat ===")
    print(f"Taggés bounced: {marked}")
    if args.apply:
        print(f"Non taggés (match manquant): {not_found}")
    else:
        print("Aucune écriture effectuée (dry-run). Relance avec --apply pour écrire en base.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

