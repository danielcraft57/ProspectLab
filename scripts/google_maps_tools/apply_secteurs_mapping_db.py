#!/usr/bin/env python3
"""Applique le mapping secteurs bruts -> secteurs FR canoniques."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Optional


def _ensure_repo_root_on_syspath() -> Path:
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


_ensure_repo_root_on_syspath()
from utils.secteurs import TARGET_SECTEURS, normalize_key, normalize_secteur  # noqa: E402


def main(argv: Optional[list[str]] = None) -> int:
    """
    Parcourt entreprises.secteur et normalise vers TARGET_SECTEURS.

    @param argv: Arguments CLI optionnels
    @returns: Code retour process
    """
    p = argparse.ArgumentParser(
        description="Applique un mapping controle de secteurs vers les secteurs FR existants."
    )
    p.add_argument("--database-url", help="Optionnel: override DATABASE_URL (postgresql://...).")
    p.add_argument("--db-path", help="Optionnel: override DATABASE_PATH (SQLite).")
    p.add_argument(
        "--backup-column",
        default="secteur_raw",
        help="Colonne backup pour l'ancienne valeur (defaut: secteur_raw).",
    )
    p.add_argument("--dry-run", action="store_true", help="N'ecrit rien en base.")
    p.add_argument("--limit", type=int, help="Limiter le nombre de lignes (debug).")
    args = p.parse_args(argv)

    from services.database.base import DatabaseBase  # type: ignore

    db = DatabaseBase(db_path=args.db_path, database_url=args.database_url)
    conn = db.get_connection()
    cur = conn.cursor()

    backup_col = (args.backup_column or "").strip()

    if backup_col and not args.dry_run:
        try:
            db.safe_execute_sql(cur, f"ALTER TABLE entreprises ADD COLUMN {backup_col} TEXT")
            if not db.is_postgresql():
                conn.commit()
        except Exception:
            pass

    sql = "SELECT id, secteur FROM entreprises WHERE secteur IS NOT NULL AND TRIM(secteur) <> ''"
    params: tuple = ()
    if args.limit and args.limit > 0:
        if db.is_postgresql():
            sql += " LIMIT %s"
        else:
            sql += " LIMIT ?"
        params = (int(args.limit),)
    db.execute_sql(cur, sql, params if params else None)
    rows = cur.fetchall() or []

    updated = 0
    seen = 0
    by_target: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    not_mapped: Counter[str] = Counter()
    already_ok = 0

    for row in rows:
        seen += 1
        rid = row["id"] if isinstance(row, dict) else row[0]
        raw = row["secteur"] if isinstance(row, dict) else row[1]
        src = str(raw).strip()
        if not src:
            continue
        target = normalize_secteur(src)
        if not target or target not in TARGET_SECTEURS:
            not_mapped[src] += 1
            continue
        if src == target:
            already_ok += 1
            continue

        by_target[target] += 1
        by_source[src] += 1

        if args.dry_run:
            updated += 1
            continue

        if backup_col:
            db.execute_sql(
                cur,
                f"UPDATE entreprises SET {backup_col} = COALESCE(NULLIF({backup_col}, ''), ?), secteur = ? WHERE id = ?",
                (src, target, rid),
            )
        else:
            db.execute_sql(cur, "UPDATE entreprises SET secteur = ? WHERE id = ?", (target, rid))
        updated += 1

    if not args.dry_run:
        conn.commit()

    print(
        f"DB: {db.db_type} | lignes lues: {seen} | a corriger: {updated} | "
        f"deja OK: {already_ok} | dry_run={bool(args.dry_run)}"
    )
    if by_target:
        print("\nRepartition des mises a jour par secteur cible:")
        for k, c in sorted(by_target.items(), key=lambda x: (-x[1], x[0])):
            print(f"- {k}: {c}")

    if by_source:
        print("\nSources les plus frequentes (top 25):")
        for s, c in sorted(by_source.items(), key=lambda x: (-x[1], x[0]))[:25]:
            print(f"- {s} -> {normalize_secteur(s)}: {c}")

    if not_mapped:
        print("\nValeurs non mappees (top 30):")
        for s, c in sorted(not_mapped.items(), key=lambda x: (-x[1], x[0]))[:30]:
            print(f"- {s}: {c} (key={normalize_key(s)!r})")

    try:
        conn.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
