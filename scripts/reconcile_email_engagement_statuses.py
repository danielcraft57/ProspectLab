#!/usr/bin/env python3
"""
Rattrapage des statuts CRM selon l'engagement email historique.

Regles:
- click  -> Relance (prospect chaud)
- open   -> A qualifier (si pas de click)

Par defaut, le script tourne en dry-run (aucune ecriture).
Utiliser --apply pour appliquer les changements.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import Database  # noqa: E402


PROTECTED_STATUSES = {
    "Gagné",
    "Réponse positive",
    "Désabonné",
    "Plainte spam",
    "Ne pas contacter",
}

# click -> Relance
CLICK_ALLOWED_CURRENT = {
    "Nouveau",
    "À qualifier",
    "Perdu",
    "À rappeler",
    "Relance",
}

# open only -> À qualifier (sans degrader un statut deja chaud)
OPEN_ALLOWED_CURRENT = {
    "Nouveau",
    "À qualifier",
    "Perdu",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rattrape les statuts CRM depuis les events email (open/click)."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Fenetre glissante en jours (defaut: 90).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Applique les modifications (sinon dry-run).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Chemin SQLite optionnel (ignore si DATABASE_URL est defini).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=15,
        help="Nombre d'IDs exemples a afficher (defaut: 15).",
    )
    return parser.parse_args()


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


def fetch_id_set(rows: Iterable, key: str = "entreprise_id") -> set[int]:
    values: set[int] = set()
    for row in rows:
        v = row[key] if isinstance(row, dict) else row[0]
        if v is None:
            continue
        try:
            values.add(int(v))
        except Exception:
            continue
    return values


def fetch_current_status_map(db: Database, cursor, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    placeholders = ",".join(["?"] * len(ids))
    db.execute_sql(
        cursor,
        f"SELECT id, statut FROM entreprises WHERE id IN ({placeholders})",
        ids,
    )
    mapping: dict[int, str] = {}
    for row in cursor.fetchall() or []:
        if isinstance(row, dict):
            mapping[int(row["id"])] = str(row.get("statut") or "").strip()
        else:
            mapping[int(row[0])] = str(row[1] or "").strip()
    return mapping


def batch_update_status(
    db: Database,
    cursor,
    ids: list[int],
    target_status: str,
    allowed_current: set[str],
) -> int:
    if not ids:
        return 0
    placeholders = ",".join(["?"] * len(ids))
    allowed_placeholders = ",".join(["?"] * len(allowed_current))
    params = [target_status] + ids + list(allowed_current)
    db.execute_sql(
        cursor,
        f"""
        UPDATE entreprises
        SET statut = ?
        WHERE id IN ({placeholders})
          AND statut IN ({allowed_placeholders})
        """,
        params,
    )
    return int(getattr(cursor, "rowcount", 0) or 0)


def main() -> int:
    args = parse_args()
    _load_env_if_present()

    if args.days <= 0:
        print("[ERREUR] --days doit etre > 0")
        return 2

    since = (datetime.utcnow() - timedelta(days=args.days)).isoformat(sep=" ", timespec="seconds")
    db = Database(db_path=args.db_path)
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # Entreprises avec au moins un click
        db.execute_sql(
            cursor,
            """
            SELECT DISTINCT e.entreprise_id
            FROM email_tracking_events et
            JOIN emails_envoyes e ON e.id = et.email_id
            WHERE et.event_type = 'click'
              AND e.entreprise_id IS NOT NULL
              AND et.date_event >= ?
            """,
            (since,),
        )
        click_ids = fetch_id_set(cursor.fetchall())

        # Entreprises avec au moins un open
        db.execute_sql(
            cursor,
            """
            SELECT DISTINCT e.entreprise_id
            FROM email_tracking_events et
            JOIN emails_envoyes e ON e.id = et.email_id
            WHERE et.event_type = 'open'
              AND e.entreprise_id IS NOT NULL
              AND et.date_event >= ?
            """,
            (since,),
        )
        open_ids = fetch_id_set(cursor.fetchall())

        # open_only = opens sans click
        open_only_ids = open_ids - click_ids

        involved_ids = sorted(click_ids | open_only_ids)
        status_map = fetch_current_status_map(db, cursor, involved_ids)

        # Exclure les statuts proteges
        click_candidates = sorted(
            i for i in click_ids
            if status_map.get(i, "") not in PROTECTED_STATUSES
        )
        open_candidates = sorted(
            i for i in open_only_ids
            if status_map.get(i, "") not in PROTECTED_STATUSES
        )

        print("=== Rattrapage statuts engagement email ===")
        print(f"Fenetre: {args.days} jours (depuis {since})")
        print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        print("")
        print(f"Candidats click  -> Relance    : {len(click_candidates)}")
        print(f"Candidats open   -> À qualifier: {len(open_candidates)}")
        if args.sample > 0:
            print(f"Exemples click IDs: {click_candidates[:args.sample]}")
            print(f"Exemples open IDs : {open_candidates[:args.sample]}")

        if not args.apply:
            print("")
            print("Aucune modification appliquee (dry-run).")
            print("Relancer avec --apply pour ecrire en base.")
            return 0

        updated_click = batch_update_status(
            db=db,
            cursor=cursor,
            ids=click_candidates,
            target_status="Relance",
            allowed_current=CLICK_ALLOWED_CURRENT,
        )
        updated_open = batch_update_status(
            db=db,
            cursor=cursor,
            ids=open_candidates,
            target_status="À qualifier",
            allowed_current=OPEN_ALLOWED_CURRENT,
        )
        conn.commit()

        print("")
        print("=== Résultat APPLY ===")
        print(f"Mis a jour vers Relance    : {updated_click}")
        print(f"Mis a jour vers À qualifier: {updated_open}")
        return 0
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[ERREUR] {exc}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

