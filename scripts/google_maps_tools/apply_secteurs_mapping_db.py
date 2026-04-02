import argparse
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Optional


TARGET_SECTEURS = {
    "Technologie",
    "Services",
    "Restauration",
    "Commerce",
    "Éducation",
    "Automobile",
    "Beauté",
    "Immobilier",
    "BTP",
    "Communication",
    "Santé",
    "Industrie",
    "Finance",
    "Hôtellerie",
    "Juridique",
    "Transport",
    "Artisanat",
}


RAW_TO_TARGET = {
    "etablissement": "Services",
    "alimentation": "Commerce",
    "lodging": "Hôtellerie",
    "real estate agency": "Immobilier",
    "sante": "Santé",
    "entreprise de travaux": "BTP",
    "magasin": "Commerce",
    "demenageur": "Transport",
    "location de voiture": "Automobile",
    "association / organization": "Services",
    "bank": "Finance",
    "coiffeur": "Beauté",
    "computer consultant": "Technologie",
    "electrician": "BTP",
    "florist": "Artisanat",
    "garage": "Automobile",
    "magasin vetements": "Commerce",
    "rugby club": "Services",
    "training center": "Éducation",
    "advertising agency": "Communication",
    "agence de voyage": "Services",
    "architecture": "BTP",
    "church": "Services",
    "computer store": "Commerce",
    "ecole": "Éducation",
    "laundry": "Services",
    "magasin maison": "Commerce",
    "veterinaire": "Santé",
    "accounting": "Finance",
    "adult education school": "Éducation",
    "agence immobiliere": "Immobilier",
    "apartment rental agency": "Hôtellerie",
    "art gallery": "Artisanat",
    "assurance": "Finance",
    "bakery": "Commerce",
    "bicycle club": "Services",
    "board game club": "Services",
    "cafe": "Commerce",
    "chartered accountant": "Finance",
    "dentist": "Santé",
    "design agency": "Communication",
    "embassy": "Services",
    "equipment rental agency": "Services",
    "family counselor": "Santé",
    "gas station": "Automobile",
    "graphic designer": "Communication",
    "handball club": "Services",
    "handicraft": "Artisanat",
    "holiday apartment rental": "Hôtellerie",
    "home goods store": "Commerce",
    "lieu de culte": "Services",
    "liquor store": "Commerce",
    "local government office": "Services",
    "magasin electronique": "Commerce",
    "mosque": "Services",
    "music instructor": "Éducation",
    "orthopedic shoe store": "Commerce",
    "painter": "BTP",
    "parc d'attractions": "Services",
    "pet trainer": "Artisanat",
    "pilates studio": "Santé",
    "plasterer": "BTP",
    "roofing contractor": "BTP",
    "shoe repair shop": "Commerce",
    "store": "Commerce",
    "temp agency": "Services",
    "tennis club": "Services",
    "vacation rental": "Hôtellerie",
    "wedding planner": "Communication",
    "wholesaler": "Commerce",
}


def _ensure_repo_root_on_syspath() -> Path:
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


def _norm_text(v: str) -> str:
    s = (v or "").strip().lower()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    s = " ".join(s.split())
    return s


def _build_mapping() -> dict[str, str]:
    m: dict[str, str] = {}
    for raw, target in RAW_TO_TARGET.items():
        if target not in TARGET_SECTEURS:
            raise ValueError(f"Secteur cible inconnu dans mapping: {target}")
        m[_norm_text(raw)] = target
    return m


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Applique un mapping contrôlé de secteurs vers les secteurs FR existants."
    )
    p.add_argument("--database-url", help="Optionnel: override DATABASE_URL (postgresql://...).")
    p.add_argument("--db-path", help="Optionnel: override DATABASE_PATH (SQLite).")
    p.add_argument(
        "--backup-column",
        default="secteur_raw",
        help="Colonne backup pour l'ancienne valeur (défaut: secteur_raw).",
    )
    p.add_argument("--dry-run", action="store_true", help="N'écrit rien en base.")
    p.add_argument("--limit", type=int, help="Limiter le nombre de lignes (debug).")
    args = p.parse_args(argv)

    _ensure_repo_root_on_syspath()
    from services.database.base import DatabaseBase  # type: ignore

    db = DatabaseBase(db_path=args.db_path, database_url=args.database_url)
    conn = db.get_connection()
    cur = conn.cursor()

    mapping = _build_mapping()
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

    for row in rows:
        seen += 1
        rid = row["id"] if isinstance(row, dict) else row[0]
        raw = row["secteur"] if isinstance(row, dict) else row[1]
        src = str(raw).strip()
        if not src:
            continue
        key = _norm_text(src)
        target = mapping.get(key)
        if not target:
            not_mapped[src] += 1
            continue
        if src == target:
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

    print(f"DB: {db.db_type} | lignes lues: {seen} | lignes modifiées: {updated} | dry_run={bool(args.dry_run)}")
    if by_target:
        print("\nRépartition des mises à jour par secteur cible:")
        for k, c in sorted(by_target.items(), key=lambda x: (-x[1], x[0])):
            print(f"- {k}: {c}")

    if not_mapped:
        print("\nValeurs non mappées (top 30):")
        for s, c in sorted(not_mapped.items(), key=lambda x: (-x[1], x[0]))[:30]:
            print(f"- {s}: {c}")

    try:
        conn.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

