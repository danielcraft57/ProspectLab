#!/usr/bin/env python3
"""
Recalcule les opportunités pour les entreprises.

- Dry-run par défaut (aucune écriture)
- Utilise Database.update_opportunity_score / OpportunityCalculator
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import Database  # noqa: E402


PROTECTED_STATUSES = {
    "Ne pas contacter",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recalcule les scores d'opportunite pour les entreprises."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Applique les mises a jour (sinon dry-run).",
    )
    parser.add_argument(
        "--only-with-email",
        action="store_true",
        help="Limiter aux entreprises avec au moins un email.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Taille des batchs de recalcul (defaut: 500).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Chemin SQLite optionnel (ignore si DATABASE_URL est defini).",
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


def fetch_all_entreprise_ids(db: Database, cursor, only_with_email: bool) -> list[int]:
    sql = "SELECT id, statut FROM entreprises"
    params: list = []
    if only_with_email:
        sql = """
            SELECT e.id, e.statut
            FROM entreprises e
            WHERE
                (e.email_principal IS NOT NULL AND TRIM(e.email_principal) != '')
                OR EXISTS (
                    SELECT 1 FROM scraper_emails se
                    WHERE se.entreprise_id = e.id
                      AND se.email IS NOT NULL
                      AND TRIM(se.email) != ''
                )
                OR EXISTS (
                    SELECT 1 FROM personnes p
                    WHERE p.entreprise_id = e.id
                      AND p.email IS NOT NULL
                      AND TRIM(p.email) != ''
                )
                OR EXISTS (
                    SELECT 1 FROM scraper_people sp
                    WHERE sp.entreprise_id = e.id
                      AND sp.email IS NOT NULL
                      AND TRIM(sp.email) != ''
                )
                OR EXISTS (
                    SELECT 1
                    FROM analyses_osint ao
                    JOIN analysis_osint_emails aoe ON aoe.analysis_id = ao.id
                    WHERE ao.entreprise_id = e.id
                      AND aoe.email IS NOT NULL
                      AND TRIM(aoe.email) != ''
                )
        """
    db.execute_sql(cursor, sql, params)
    ids: list[int] = []
    for row in cursor.fetchall() or []:
        if isinstance(row, dict):
            ent_id = int(row["id"])
            statut = str(row.get("statut") or "").strip()
        else:
            ent_id = int(row[0])
            statut = str(row[1] or "").strip()
        if statut in PROTECTED_STATUSES:
            continue
        ids.append(ent_id)
    return ids


def batched(iterable: Iterable[int], n: int) -> Iterable[list[int]]:
    batch: list[int] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch


def main() -> int:
    args = parse_args()
    _load_env_if_present()

    db = Database(db_path=args.db_path)
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        from services.opportunity_calculator import OpportunityCalculator  # type: ignore
    except Exception:
        OpportunityCalculator = None  # type: ignore

    try:
        print("=== Recalcul des opportunites ===")
        print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        print(f"Filtre: {'seulement entreprises avec email' if args.only_with_email else 'toutes entreprises'}")
        print("")

        ids = fetch_all_entreprise_ids(db, cursor, args.only_with_email)
        total = len(ids)
        print(f"Entreprises a traiter: {total}")
        if total == 0:
            return 0

        updated = 0
        failed = 0

        if not args.apply:
            print("Dry-run: aucun recalcul ecrit. Relancer avec --apply pour appliquer.")
            return 0

        # Recalcul batch par batch
        for batch in batched(ids, max(1, args.batch_size)):
            for ent_id in batch:
                try:
                    # API interne existante
                    res = db.update_opportunity_score(ent_id)
                    if res:
                        updated += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            conn.commit()

        print("")
        print("=== Résultat APPLY ===")
        print(f"Recalculs reussis : {updated}")
        print(f"Echecs/erreurs    : {failed}")
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

