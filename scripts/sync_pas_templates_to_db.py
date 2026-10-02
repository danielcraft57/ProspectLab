#!/usr/bin/env python3
"""
Purge email_templates puis upsert les 6 modeles PAS depuis html_sources.

Usage (prod node15):
  cd /opt/prospectlab
  PYTHONPATH=/opt/prospectlab /opt/prospectlab/env/bin/python scripts/sync_pas_templates_to_db.py --purge
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

PAS_SPECS = (
    {
        "id": "html_dc_pas_echantillon",
        "name": "J0 - Un modele deja fait (PAS)",
        "category": "echantillons",
        "subject": "Un modele {secteur_label} pour {entreprise} ?",
    },
    {
        "id": "html_dc_pas_style_custom",
        "name": "J1 - Style + echantillons custom (PAS)",
        "category": "echantillons",
        "subject": "Des echantillons specifiques pour {entreprise} ?",
    },
    {
        "id": "html_dc_pas_constat_site",
        "name": "J2 - Constat site / rapport (PAS)",
        "category": "audit",
        "subject": "{entreprise} - ce que j'ai vu sur votre site",
    },
    {
        "id": "html_dc_pas_projection",
        "name": "J3 - Projection enseigne (PAS)",
        "category": "echantillons",
        "subject": "Imaginez le site de {entreprise} dans ce style",
    },
    {
        "id": "html_dc_pas_midi",
        "name": "J4 - Autour de midi (PAS)",
        "category": "offres",
        "subject": "15 minutes pour {entreprise} - autour de midi ?",
    },
    {
        "id": "html_dc_pas_breakup",
        "name": "J5 - Breakup dossier (PAS)",
        "category": "audit",
        "subject": "Je ferme le dossier {entreprise}",
    },
)


def _subject_from_html(html: str, fallback: str) -> str:
    """
    Extrait le sujet depuis le commentaire SUBJECT ou la balise title.

    @param html: Contenu HTML
    @param fallback: Sujet par defaut
    @returns: Sujet
    """
    m = re.search(r"<!--\s*SUBJECT:\s*(.+?)\s*-->", html, flags=re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"<title>\s*Objet:\s*(.+?)\s*</title>", html, flags=re.I | re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return fallback


def main() -> int:
    """
    Point d'entree CLI.

    @returns: Code retour shell
    """
    parser = argparse.ArgumentParser(description="Sync modeles PAS vers email_templates")
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Supprime tous les modeles existants avant upsert",
    )
    parser.add_argument(
        "--sources-dir",
        default=str(ROOT / "template_studio" / "html_sources"),
        help="Dossier des sources HTML",
    )
    args = parser.parse_args()

    sources_dir = Path(args.sources_dir)
    from services.database import Database

    db = Database()
    print(f"db_type={getattr(db, 'db_type', '?')}")

    before = db.list_email_templates(active_only=False)
    print(f"avant={len(before)}")

    if args.purge:
        deleted = 0
        for row in before:
            tid = (row.get("id") or "").strip()
            if tid and db.delete_email_template(tid):
                deleted += 1
        print(f"supprimes={deleted}")

    upserted = 0
    # Upsert du dernier jour vers le premier pour que updated_desc
    # affiche J0 (echantillon) en haut de liste dans l'UI.
    for spec in reversed(PAS_SPECS):
        path = sources_dir / f"{spec['id']}.html"
        if not path.is_file():
            print(f"MANQUANT: {path}", file=sys.stderr)
            return 1
        content = path.read_text(encoding="utf-8")
        subject = _subject_from_html(content, spec["subject"])
        db.upsert_email_template(
            template_id=spec["id"],
            name=spec["name"],
            category=spec["category"],
            subject=subject,
            content=content,
            is_html=True,
            is_active=True,
        )
        upserted += 1
        print(f"ok {spec['id']} ({spec['category']})")

    after = db.list_email_templates(active_only=False)
    print(f"apres={len(after)} upserted={upserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
