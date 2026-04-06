import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Optional


def _load_translate_fn():
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
    repo_root = here.parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


def _needs_translation(raw: str) -> bool:
    t = (raw or "").strip()
    if not t:
        return False
    if "_" in t:
        return True
    low = t.lower()
    if low != t:
        return False
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


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("Aucun secteur trouvé avec ces filtres.")
        return

    max_count_w = max(len(str(r["count"])) for r in rows)
    max_sector_w = min(70, max(len(r["secteur"]) for r in rows))
    has_preview = any("preview_fr" in r for r in rows)

    header = f"{'#':>4}  {'count':>{max_count_w}}  {'secteur'.ljust(max_sector_w)}"
    if has_preview:
        header += "  preview_fr"
    print(header)
    print("-" * len(header))

    for i, r in enumerate(rows, start=1):
        secteur = r["secteur"]
        if len(secteur) > max_sector_w:
            secteur = secteur[: max_sector_w - 1] + "…"
        line = f"{i:>4}  {str(r['count']).rjust(max_count_w)}  {secteur.ljust(max_sector_w)}"
        if has_preview:
            line += f"  {r.get('preview_fr', '')}"
        print(line)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Liste les valeurs distinctes de entreprises.secteur (avec occurrences) pour préparer la traduction."
    )
    p.add_argument("--database-url", help="Optionnel: override DATABASE_URL (postgresql://...).")
    p.add_argument("--db-path", help="Optionnel: override DATABASE_PATH (SQLite).")
    p.add_argument("--top", type=int, default=0, help="Afficher seulement les N premiers résultats (0 = tous).")
    p.add_argument("--contains", help="Filtrer les secteurs contenant ce texte (insensible à la casse).")
    p.add_argument(
        "--only-needs-translation",
        action="store_true",
        help="Garder uniquement les secteurs qui semblent encore à traduire.",
    )
    p.add_argument(
        "--preview-translation",
        action="store_true",
        help="Ajoute un aperçu FR via le mapping builtin (sans écrire en base).",
    )
    p.add_argument("--csv-out", help="Chemin CSV de sortie (colonnes: secteur,count[,preview_fr]).")
    args = p.parse_args(argv)

    _ensure_repo_root_on_syspath()
    from services.database.base import DatabaseBase  # type: ignore

    translate_fn = _load_translate_fn() if args.preview_translation else None

    db = DatabaseBase(db_path=args.db_path, database_url=args.database_url)
    conn = db.get_connection()
    cur = conn.cursor()
    db.execute_sql(
        cur,
        "SELECT secteur FROM entreprises WHERE secteur IS NOT NULL AND TRIM(secteur) <> ''",
    )
    rows = cur.fetchall() or []

    values: list[str] = []
    for row in rows:
        try:
            raw = row["secteur"] if isinstance(row, dict) else row[0]
        except Exception:
            continue
        s = str(raw).strip() if raw is not None else ""
        if s:
            values.append(s)

    counts = Counter(values)
    out: list[dict] = []
    contains = (args.contains or "").strip().lower()

    for secteur, count in counts.items():
        if contains and contains not in secteur.lower():
            continue
        if args.only_needs_translation and not _needs_translation(secteur):
            continue
        item = {"secteur": secteur, "count": count}
        if translate_fn is not None:
            try:
                item["preview_fr"] = str(translate_fn(secteur, mode="builtin") or "")
            except Exception:
                item["preview_fr"] = ""
        out.append(item)

    out.sort(key=lambda x: (-int(x["count"]), x["secteur"].lower()))
    if args.top and args.top > 0:
        out = out[: args.top]

    total_rows = len(values)
    unique_count = len(counts)
    print(f"DB: {db.db_type} | lignes avec secteur: {total_rows} | secteurs distincts: {unique_count}")
    _print_table(out)

    if args.csv_out:
        csv_path = Path(args.csv_out)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        fields = ["secteur", "count"] + (["preview_fr"] if translate_fn is not None else [])
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in out:
                w.writerow({k: r.get(k, "") for k in fields})
        print(f"\nCSV écrit: {csv_path}")

    try:
        conn.close()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

