#!/usr/bin/env python3
"""
Upsert les 6 modeles de la suite audit semaine (html_dc_as_*).

Usage (prod node15):
  cd /opt/prospectlab
  PYTHONPATH=/opt/prospectlab /opt/prospectlab/env/bin/python scripts/sync_audit_suite_to_db.py
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

AS_SPECS = (
    {
        "id": "html_dc_as_rapport",
        "name": "AS J0 - Rapport pret (audit semaine)",
        "category": "audit",
        "subject": "{entreprise} - votre rapport est prêt",
    },
    {
        "id": "html_dc_as_notes",
        "name": "AS J1 - 3 notes (audit semaine)",
        "category": "audit",
        "subject": "3 notes sur le site de {entreprise}",
    },
    {
        "id": "html_dc_as_porte",
        "name": "AS J2 - Porte / protection (audit semaine)",
        "category": "audit",
        "subject": "{entreprise} - la porte web un peu ouverte ?",
    },
    {
        "id": "html_dc_as_friction",
        "name": "AS J3 - Friction demandes (audit semaine)",
        "category": "audit",
        "subject": "Les gens arrivent sur {entreprise} - puis ça coince ?",
    },
    {
        "id": "html_dc_as_midi",
        "name": "AS J4 - Autour de midi (audit semaine)",
        "category": "audit",
        "subject": "15 minutes pour {entreprise} - autour de midi ?",
    },
    {
        "id": "html_dc_as_breakup",
        "name": "AS J5 - Breakup dossier (audit semaine)",
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
    parser = argparse.ArgumentParser(description="Sync suite audit semaine vers email_templates")
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

    upserted = 0
    for spec in reversed(AS_SPECS):
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

    print(f"upserted={upserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
