#!/usr/bin/env python3
"""
Regénère template_studio/templates_data.json depuis les sources HTML
et upsert tous les modèles dans la table email_templates (prod PostgreSQL).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    only_ids = [a for a in sys.argv[1:] if a.strip()]
    cmd = [sys.executable, "-m", "template_studio.generate_cli"]
    if only_ids:
        cmd.extend(["--only-ids", ",".join(only_ids)])
    else:
        cmd.append("--sync")

    subprocess.run(cmd, cwd=str(ROOT), check=True)

    json_path = ROOT / "template_studio" / "templates_data.json"
    if not json_path.is_file():
        print("ERREUR: templates_data.json introuvable après génération.", file=sys.stderr)
        return 1

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    templates = payload.get("templates") or []
    if only_ids:
        wanted = set(only_ids)
        templates = [t for t in templates if t.get("id") in wanted]

    from services.database import Database

    db = Database()
    if not hasattr(db, "upsert_email_template"):
        print("ERREUR: upsert_email_template indisponible.", file=sys.stderr)
        return 1

    count = 0
    for tpl in templates:
        tid = (tpl.get("id") or "").strip()
        if not tid:
            continue
        category = tpl.get("category") or "html_email"
        is_html = bool(tpl.get("is_html")) or category == "html_email"
        db.upsert_email_template(
            template_id=tid,
            name=tpl.get("name") or tid,
            category=category,
            subject=tpl.get("subject") or "",
            content=tpl.get("content") or "",
            is_html=is_html,
            is_active=True,
        )
        count += 1

    print(f"OK: {count} modèle(s) synchronisé(s) en BDD.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
