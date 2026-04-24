#!/usr/bin/env python3
"""
Rattrapage des statuts Bounce selon la regle "tous les emails bounced".

Regle appliquee:
- une entreprise passe en statut "Bounce" uniquement si toutes les adresses
  connues dans emails_envoyes pour cette entreprise ont au moins un bounce.

Par defaut, le script tourne en dry-run (aucune ecriture).
Utiliser --apply pour ecrire en base.

Note prod:
- le script est compatible SQLite et PostgreSQL via Database.execute_sql.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import Database  # noqa: E402
from services.database.entreprises import EntrepriseManager  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recalcule les statuts Bounce selon les emails bounced."
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
        "--reset-non-qualifying",
        action="store_true",
        help=(
            "Repasse les entreprises actuellement Bounce mais non-qualifiees "
            "vers 'À qualifier'."
        ),
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=20,
        help="Nombre d'IDs exemple a afficher (defaut: 20).",
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


def _is_row_bounced(row) -> bool:
    try:
        total_cnt = row.get("total_cnt") if isinstance(row, dict) else row[2]
        bounced_cnt = row.get("bounced_cnt") if isinstance(row, dict) else row[3]
        return int(total_cnt or 0) > 0 and int(bounced_cnt or 0) > 0
    except Exception:
        return False


def main() -> int:
    args = parse_args()
    _load_env_if_present()

    db = Database(db_path=args.db_path)
    em = EntrepriseManager(db_path=args.db_path)
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # Par entreprise + email normalise:
        # total_cnt = nb lignes emails_envoyes pour cet email
        # bounced_cnt = nb lignes bounced pour cet email
        db.execute_sql(
            cursor,
            """
            SELECT
                entreprise_id,
                LOWER(TRIM(email)) AS email_norm,
                COUNT(*) AS total_cnt,
                SUM(CASE WHEN statut = 'bounced' THEN 1 ELSE 0 END) AS bounced_cnt
            FROM emails_envoyes
            WHERE entreprise_id IS NOT NULL
              AND email IS NOT NULL
              AND TRIM(email) <> ''
            GROUP BY entreprise_id, LOWER(TRIM(email))
            ORDER BY entreprise_id
            """,
        )
        rows = cursor.fetchall() or []
        if not rows:
            print("[INFO] Aucune ligne exploitable dans emails_envoyes.")
            return 0

        by_ent: dict[int, list] = {}
        for row in rows:
            ent_id = row.get("entreprise_id") if isinstance(row, dict) else row[0]
            if ent_id is None:
                continue
            eid = int(ent_id)
            if eid not in by_ent:
                by_ent[eid] = []
            by_ent[eid].append(row)

        qualifying_bounce_ids: list[int] = []
        non_qualifying_ids: list[int] = []

        for eid, ent_rows in by_ent.items():
            all_bounced = all(_is_row_bounced(r) for r in ent_rows)
            if all_bounced:
                qualifying_bounce_ids.append(eid)
            else:
                non_qualifying_ids.append(eid)

        # Entreprises actuellement en statut Bounce
        db.execute_sql(cursor, "SELECT id FROM entreprises WHERE statut = ?", ("Bounce",))
        current_bounce_ids = set()
        for row in cursor.fetchall() or []:
            current_bounce_ids.add(int(row.get("id") if isinstance(row, dict) else row[0]))

        qualifying_set = set(qualifying_bounce_ids)
        to_set_bounce = sorted(qualifying_set - current_bounce_ids)
        bounce_but_not_qualified = sorted(current_bounce_ids - qualifying_set)

        print("=== Recalcul statuts Bounce ===")
        print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        print(f"Entreprises avec historique emails: {len(by_ent)}")
        print(f"Qualifiees Bounce (regle stricte): {len(qualifying_bounce_ids)}")
        print(f"A passer en Bounce: {len(to_set_bounce)}")
        print(f"Actuellement Bounce mais non-qualifiees: {len(bounce_but_not_qualified)}")
        if args.sample > 0:
            print(f"Exemples a passer Bounce: {to_set_bounce[:args.sample]}")
            print(
                "Exemples Bounce non qualifies: "
                f"{bounce_but_not_qualified[:args.sample]}"
            )

        if not args.apply:
            print("")
            print("Aucune modification appliquee (dry-run).")
            print("Relance avec --apply pour ecrire en base.")
            if bounce_but_not_qualified and not args.reset_non_qualifying:
                print(
                    "Option utile: --reset-non-qualifying pour repasser ces fiches "
                    "en 'À qualifier'."
                )
            return 0

        updated_to_bounce = 0
        for eid in to_set_bounce:
            try:
                if em.update_entreprise_statut(int(eid), "Bounce"):
                    updated_to_bounce += 1
            except Exception:
                continue

        reset_count = 0
        if args.reset_non_qualifying:
            for eid in bounce_but_not_qualified:
                try:
                    if em.update_entreprise_statut(int(eid), "À qualifier"):
                        reset_count += 1
                except Exception:
                    continue

        print("")
        print("=== Resultat APPLY ===")
        print(f"Mis a jour vers Bounce: {updated_to_bounce}")
        if args.reset_non_qualifying:
            print(f"Reset vers À qualifier: {reset_count}")
        else:
            print("Reset non qualifie: ignore (utiliser --reset-non-qualifying)")
        return 0
    except Exception as exc:
        print(f"[ERREUR] {exc}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

