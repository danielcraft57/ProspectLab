import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Tuple


def _load_translator():
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    try:
        import places_search as ps  # type: ignore

        return ps._translate_category  # noqa: SLF001
    finally:
        try:
            sys.path.remove(str(here))
        except Exception:
            pass


def _ensure_repo_root_on_syspath() -> Path:
    here = Path(__file__).resolve()
    # .../scripts/google_maps_tools/patch_translate_db.py -> repo root is 2 parents up from scripts/
    repo_root = here.parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


def _fmt_s(seconds: float) -> str:
    s = max(0, int(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


def _needs_translation(raw: str) -> bool:
    t = (raw or "").strip()
    if not t:
        return False
    # Typiquement les types Places ont des underscores ou sont déjà en minuscule anglais.
    if "_" in t:
        return True
    low = t.lower()
    if low != t:
        # Déjà FR souvent avec majuscules, on ne force pas.
        return False
    # Heuristique simple: tokens anglais communs
    english_markers = {
        "restaurant",
        "store",
        "shop",
        "clinic",
        "hospital",
        "school",
        "station",
        "office",
        "finance",
        "health",
        "food",
        "establishment",
        "point_of_interest",
    }
    return low in english_markers


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Patch BDD: traduit entreprises.secteur (types Google Places) en FR via mapping builtin."
    )
    p.add_argument(
        "--database-url",
        help="Optionnel: override DATABASE_URL (postgresql://...). Sinon env DATABASE_URL/SQLite par défaut.",
    )
    p.add_argument("--db-path", help="Optionnel: override DATABASE_PATH (SQLite).")
    p.add_argument(
        "--backup-column",
        default="secteur_raw",
        help="Nom de colonne de backup pour l'ancien secteur (defaut: secteur_raw). Vide => pas de backup.",
    )
    p.add_argument("--dry-run", action="store_true", help="Ne fait pas les UPDATE, affiche juste un résumé.")
    p.add_argument("--limit", type=int, help="Limite de lignes à traiter (debug).")
    p.add_argument("--commit-every", type=int, default=500, help="Commit toutes les N mises à jour (defaut: 500)")
    p.add_argument("--progress-every", type=int, default=2000, help="Avancement toutes les N lignes lues (defaut: 2000)")
    args = p.parse_args(argv)

    translate_fn = _load_translator()

    # Import lazy (assure que le repo root est dans sys.path)
    _ensure_repo_root_on_syspath()
    from services.database.base import DatabaseBase  # type: ignore

    db = DatabaseBase(db_path=args.db_path, database_url=args.database_url)
    conn = db.get_connection()
    cursor = conn.cursor()

    # Ajouter la colonne backup si demandée
    backup_col = (args.backup_column or "").strip()
    if backup_col and not args.dry_run:
        try:
            db.safe_execute_sql(cursor, f"ALTER TABLE entreprises ADD COLUMN {backup_col} TEXT")
            if not db.is_postgresql():
                conn.commit()
        except Exception:
            # safe_execute_sql gère déjà "exists", ici on ignore toute erreur non critique
            pass

    # Charger les lignes à traiter
    sql = "SELECT id, secteur FROM entreprises WHERE secteur IS NOT NULL AND TRIM(secteur) <> ''"
    if args.limit and int(args.limit) > 0:
        sql += " LIMIT ?"
        db.execute_sql(cursor, sql, (int(args.limit),))
    else:
        db.execute_sql(cursor, sql)
    rows = cursor.fetchall() or []

    total = len(rows)
    if total == 0:
        print("Aucune entreprise avec secteur non vide.")
        try:
            conn.close()
        except Exception:
            pass
        return 0

    t0 = time.time()
    changed = 0
    updated = 0
    scanned = 0
    commit_every = max(1, int(args.commit_every))
    progress_every = max(1, int(args.progress_every))

    print(f"DB: {db.db_type} | lignes candidates: {total} | dry_run={bool(args.dry_run)} | backup={backup_col or 'non'}")

    for row in rows:
        scanned += 1
        try:
            rid = row["id"] if isinstance(row, dict) else row[0]
            secteur = row.get("secteur") if isinstance(row, dict) else row[1]
        except Exception:
            continue
        secteur_s = str(secteur).strip() if secteur is not None else ""
        if not secteur_s:
            continue
        if not _needs_translation(secteur_s):
            continue

        new_fr = translate_fn(secteur_s, mode="builtin")
        if not new_fr:
            continue
        new_fr_s = str(new_fr).strip()
        if not new_fr_s:
            continue

        # Ne pas toucher si c'est déjà identique à une normalisation près
        if new_fr_s.lower() == secteur_s.lower():
            continue

        changed += 1
        if args.dry_run:
            continue

        if backup_col:
            # On remplit secteur_raw seulement si vide, pour garder la 1ère valeur originale
            db.execute_sql(
                cursor,
                f"UPDATE entreprises SET {backup_col} = COALESCE(NULLIF({backup_col}, ''), ?), secteur = ? WHERE id = ?",
                (secteur_s, new_fr_s, rid),
            )
        else:
            db.execute_sql(cursor, "UPDATE entreprises SET secteur = ? WHERE id = ?", (new_fr_s, rid))

        updated += 1
        if updated % commit_every == 0:
            conn.commit()

        if scanned % progress_every == 0:
            elapsed = time.time() - t0
            pct = (scanned * 100.0 / total) if total else 100.0
            rate = scanned / elapsed if elapsed > 0 else 0.0
            eta = (total - scanned) / rate if rate > 0 else 0.0
            print(
                f"[{scanned}/{total}] {pct:.1f}% | candidats: {changed} | updates: {updated} | "
                f"elapsed: {_fmt_s(elapsed)} | eta: {_fmt_s(eta)}"
            )

    if not args.dry_run:
        conn.commit()

    elapsed = time.time() - t0
    print(
        f"Terminé. Scannés: {scanned} | candidats traduits: {changed} | updates: {updated} | temps: {_fmt_s(elapsed)}"
    )

    try:
        conn.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

