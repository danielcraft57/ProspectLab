#!/usr/bin/env python3
"""
Scan de la table entreprises et proposition de revisions de secteur.

Usage:
    python scripts/scan_secteur_revisions.py --out backups/secteur_revisions_<ts>.csv --limit 200

Le script :
 - charge la DB via services.database.Database
 - pour chaque entreprise récupère le champ `secteur`
 - calcule le `secteur_new` via utils.secteurs.enrich_secteur_template_vars
 - si secteur_new != secteur_old, ajoute une ligne CSV (id, nom, website, secteur_old, secteur_new, reason)
"""
from __future__ import annotations

import csv
import argparse
from datetime import datetime
from pathlib import Path
from services.database import Database
from utils.secteurs import enrich_secteur_template_vars


def scan(limit: int | None, out_path: Path) -> int:
    db = Database()
    # pagination to avoid loading everything in memory
    offset = 0
    page = 500
    found = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "nom", "website", "secteur_old", "secteur_new", "echantillon_slug", "reason"])

        while True:
            rows = db.get_entreprises(limit=page, offset=offset, filters=None)
            if not rows:
                break
            for r in rows:
                eid = r.get("id")
                nom = r.get("nom") or ""
                website = r.get("website") or ""
                secteur_old = (r.get("secteur") or "").strip()
                # compute new values
                vars_new = enrich_secteur_template_vars(r.get("secteur") or r.get("categorie") or "")
                secteur_new = (vars_new.get("secteur_label") or "").strip()
                slug = vars_new.get("echantillon_slug") or ""
                reason = ""
                if secteur_new != secteur_old:
                    reason = "mismatch"
                    writer.writerow([eid, nom, website, secteur_old, secteur_new, slug, reason])
                    found += 1
                    if limit and found >= limit:
                        return found
            offset += len(rows)
    return found


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=None, help="Chemin CSV de sortie")
    p.add_argument("--limit", type=int, default=200, help="Nombre max de propositions")
    args = p.parse_args()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else Path("backups") / f"secteur_revisions_{ts}.csv"
    n = scan(limit=args.limit, out_path=out)
    print(f"Wrote {n} candidates -> {out}")


if __name__ == '__main__':
    main()

