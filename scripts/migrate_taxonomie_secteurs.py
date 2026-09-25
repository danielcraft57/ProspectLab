#!/usr/bin/env python3
"""
Migration taxonomie hierarchique : secteur (groupe) + categorie (metier).

Parcourt entreprises, applique resolve_hierarchie, backup secteur_raw,
remplit categorie. Supporte --dry-run et commits par lots.

Usage (PowerShell) :
    python scripts/migrate_taxonomie_secteurs.py --dry-run
    python scripts/migrate_taxonomie_secteurs.py
    python scripts/migrate_taxonomie_secteurs.py --database-url "postgresql://..."
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Optional


def _ensure_repo_root_on_syspath() -> Path:
    """Ajoute la racine du repo au sys.path."""
    here = Path(__file__).resolve()
    repo_root = here.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


def _ensure_columns(db, conn, cur) -> None:
    """
    Ajoute categorie / secteur_raw si absentes.

    @param db: Instance DatabaseBase
    @param conn: Connexion
    @param cur: Curseur
    """
    for col in ("categorie", "secteur_raw"):
        try:
            db.safe_execute_sql(cur, f"ALTER TABLE entreprises ADD COLUMN {col} TEXT")
            if not db.is_postgresql():
                conn.commit()
        except Exception:
            pass
    try:
        db.execute_sql(
            cur,
            "CREATE INDEX IF NOT EXISTS idx_entreprises_categorie ON entreprises(categorie)",
        )
        if not db.is_postgresql():
            conn.commit()
    except Exception:
        pass


def main(argv: Optional[list[str]] = None) -> int:
    """
    Applique la taxonomie hierarchique sur la table entreprises.

    @param argv: Arguments CLI optionnels
    @returns: Code retour process
    """
    p = argparse.ArgumentParser(
        description="Migration hierarchique secteurs -> secteur (groupe) + categorie."
    )
    p.add_argument("--database-url", help="Override DATABASE_URL (postgresql://...).")
    p.add_argument("--db-path", help="Override DATABASE_PATH (SQLite).")
    p.add_argument("--dry-run", action="store_true", help="N'ecrit rien en base.")
    p.add_argument("--limit", type=int, help="Limiter le nombre de lignes (debug).")
    p.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Taille des lots de commit (defaut: 500).",
    )
    p.add_argument(
        "--no-reclass",
        action="store_true",
        help="Ne pas reclasser les macros via le nom.",
    )
    args = p.parse_args(argv)

    _ensure_repo_root_on_syspath()
    from services.database.base import DatabaseBase
    from utils.taxonomie_secteurs import resolve_hierarchie

    db = DatabaseBase(db_path=args.db_path, database_url=args.database_url)
    conn = db.get_connection()
    cur = conn.cursor()

    # Colonnes necessaires meme en dry-run (ADD COLUMN nullable, sans toucher aux lignes)
    _ensure_columns(db, conn, cur)
    try:
        conn.commit()
    except Exception:
        pass

    sql = (
        "SELECT id, nom, secteur, "
        "COALESCE(categorie, '') AS categorie, "
        "COALESCE(secteur_raw, '') AS secteur_raw "
        "FROM entreprises"
    )
    params: tuple = ()
    if args.limit and args.limit > 0:
        if db.is_postgresql():
            sql += " LIMIT %s"
        else:
            sql += " LIMIT ?"
        params = (int(args.limit),)

    try:
        db.execute_sql(cur, sql, params if params else None)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        sql = "SELECT id, nom, secteur, '' AS categorie, '' AS secteur_raw FROM entreprises"
        if args.limit and args.limit > 0:
            if db.is_postgresql():
                sql += " LIMIT %s"
            else:
                sql += " LIMIT ?"
        db.execute_sql(cur, sql, params if params else None)

    rows = cur.fetchall() or []

    updated = 0
    unchanged = 0
    seen = 0
    by_groupe: Counter[str] = Counter()
    by_categorie: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()
    reclass: Counter[str] = Counter()
    still_establishment = 0
    batch = 0
    batch_size = max(1, int(args.batch_size or 500))
    reclasser = not bool(args.no_reclass)

    for row in rows:
        seen += 1
        if isinstance(row, dict):
            rid = row["id"]
            nom = row.get("nom") or ""
            secteur = (row.get("secteur") or "").strip()
            categorie = (row.get("categorie") or "").strip()
            secteur_raw = (row.get("secteur_raw") or "").strip()
        else:
            rid = row[0]
            nom = row[1] or ""
            secteur = (row[2] or "").strip()
            categorie = (row[3] or "").strip()
            secteur_raw = (row[4] or "").strip()

        resolved = resolve_hierarchie(
            secteur,
            nom=nom,
            categorie_actuelle=categorie or None,
            secteur_raw=secteur_raw or None,
            reclasser_macro=reclasser,
        )
        new_secteur = str(resolved.get("secteur") or "").strip()
        new_categorie = str(resolved.get("categorie") or "").strip()
        reason = str(resolved.get("reason") or "")
        source_raw = str(resolved.get("source_raw") or secteur).strip()

        by_reason[reason] += 1
        if new_secteur:
            by_groupe[new_secteur] += 1
        if new_categorie:
            by_categorie[new_categorie] += 1
        if new_secteur.lower() == "establishment" or (not new_categorie and secteur.lower() == "establishment"):
            still_establishment += 1

        needs_update = (new_secteur != secteur) or (new_categorie != categorie)
        # Toujours poser secteur_raw si vide et source differente
        need_raw = (not secteur_raw) and source_raw and source_raw != new_secteur

        if new_secteur != secteur:
            reclass[f"{secteur or '(vide)'} -> {new_secteur}"] += 1

        if not needs_update and not need_raw:
            unchanged += 1
            continue

        updated += 1
        if args.dry_run:
            continue

        backup = secteur_raw or (secteur if secteur != new_secteur else source_raw)
        if not backup:
            backup = source_raw or secteur

        db.execute_sql(
            cur,
            "UPDATE entreprises SET "
            "secteur = ?, categorie = ?, "
            "secteur_raw = COALESCE(NULLIF(secteur_raw, ''), ?) "
            "WHERE id = ?",
            (new_secteur or None, new_categorie or None, backup or None, rid),
        )
        batch += 1
        if batch >= batch_size:
            conn.commit()
            batch = 0

    if not args.dry_run and batch > 0:
        conn.commit()

    print(
        f"DB: {db.db_type} | lues: {seen} | a maj: {updated} | "
        f"inchanges: {unchanged} | dry_run={bool(args.dry_run)}"
    )
    print(f"still_establishment_like: {still_establishment}")

    print("\nRaisons:")
    for k, c in sorted(by_reason.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {c:>6}  {k}")

    print("\nGroupes cibles:")
    for k, c in sorted(by_groupe.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {c:>6}  {k}")

    print("\nTop categories:")
    for k, c in sorted(by_categorie.items(), key=lambda x: (-x[1], x[0]))[:40]:
        print(f"  {c:>6}  {k}")

    if reclass:
        print("\nTop reclassements secteur:")
        for k, c in sorted(reclass.items(), key=lambda x: (-x[1], x[0]))[:40]:
            print(f"  {c:>6}  {k}")

    try:
        conn.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
