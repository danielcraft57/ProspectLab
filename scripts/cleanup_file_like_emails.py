#!/usr/bin/env python3
"""
Purge les faux emails type assets (logo@2x.png, plan@150x.webp) dans scraper_emails
et nettoie email_principal si besoin.

Usage:
  python scripts/cleanup_file_like_emails.py           # dry-run
  python scripts/cleanup_file_like_emails.py --apply   # delete reel
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.email_quality import is_file_like_email


def main() -> int:
    """
    Parcourt scraper_emails et supprime les adresses fichier-like.

    @returns: Code de sortie (0 = OK)
    """
    parser = argparse.ArgumentParser(description="Purge faux emails (extensions fichiers)")
    parser.add_argument("--apply", action="store_true", help="Applique les DELETE (sinon dry-run)")
    args = parser.parse_args()

    from services.database import Database

    db = Database()
    conn = db.get_connection()
    cur = conn.cursor()

    db.execute_sql(cur, "SELECT id, email FROM scraper_emails WHERE email LIKE '%@%'")
    rows = cur.fetchall() or []

    ids_to_delete = []
    emails_sample = []
    for r in rows:
        d = dict(r) if hasattr(r, "keys") else {"id": r[0], "email": r[1]}
        email = d.get("email") or ""
        if is_file_like_email(email):
            ids_to_delete.append(int(d["id"]))
            if len(emails_sample) < 20:
                emails_sample.append(email)

    print(f"total_scraper_emails={len(rows)}")
    print(f"a_supprimer={len(ids_to_delete)}")
    print("samples=", emails_sample)

    db.execute_sql(
        cur,
        "SELECT id, email_principal FROM entreprises WHERE email_principal IS NOT NULL AND email_principal LIKE '%@%'",
    )
    principal_rows = cur.fetchall() or []
    principal_bad = []
    for r in principal_rows:
        d = dict(r) if hasattr(r, "keys") else {"id": r[0], "email_principal": r[1]}
        if is_file_like_email(d.get("email_principal")):
            principal_bad.append(int(d["id"]))
    print(f"email_principal_a_vider={len(principal_bad)}")

    if not args.apply:
        print("dry-run: aucun DELETE (relancer avec --apply)")
        conn.close()
        return 0

    batch = 500
    deleted = 0
    for i in range(0, len(ids_to_delete), batch):
        chunk = ids_to_delete[i : i + batch]
        placeholders = ",".join(["?"] * len(chunk))
        db.execute_sql(cur, f"DELETE FROM scraper_emails WHERE id IN ({placeholders})", chunk)
        deleted += len(chunk)
        conn.commit()
        if deleted % 5000 == 0 or deleted == len(ids_to_delete):
            print(f"deleted_scraper_emails={deleted}/{len(ids_to_delete)}")

    cleared = 0
    for i in range(0, len(principal_bad), batch):
        chunk = principal_bad[i : i + batch]
        placeholders = ",".join(["?"] * len(chunk))
        db.execute_sql(
            cur,
            f"UPDATE entreprises SET email_principal = NULL WHERE id IN ({placeholders})",
            chunk,
        )
        cleared += len(chunk)
        conn.commit()
        print(f"cleared_principal={cleared}/{len(principal_bad)}")

    conn.close()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
