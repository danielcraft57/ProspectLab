from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent

# Permet les imports `template_studio.*` quand le script est lancé directement.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def export_html_sources(out_dir: Path, overwrite: bool = False) -> List[str]:
    """
    Exporte les templates HTML depuis `templates_data.json`
    vers `template_studio/html_sources/<template_id>.html`.
    """

    # On exporte depuis templates_data.json (source de vérité actuel local).
    # Le dossier scripts n'est pas un package, donc on ne dépend pas des fonctions historiques.
    from template_studio.template_repo import JsonTemplatesRepository

    repo = JsonTemplatesRepository(
        templates_file=ROOT / "template_studio" / "templates_data.json",
        default_file=ROOT / "template_studio" / "templates_data.default.json",
    )
    templates = repo.load_templates()

    out_dir.mkdir(parents=True, exist_ok=True)

    exported: List[str] = []
    for tpl in templates:
        template_id = (tpl.get("id") or "").strip()
        if not template_id:
            continue

        is_html = bool(tpl.get("is_html")) or tpl.get("category") == "html_email" or template_id.startswith("html_")
        if not is_html:
            continue

        content = tpl.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        target = out_dir / f"{template_id}.html"
        if target.exists() and not overwrite:
            continue
        target.write_text(content, encoding="utf-8")
        exported.append(template_id)

    return exported


def main() -> int:
    parser = argparse.ArgumentParser(description="Export templates HTML vers html_sources/")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Ré-écrit les fichiers existants.",
    )
    args = parser.parse_args()

    sources_dir = ROOT / "template_studio" / "html_sources"
    exported = export_html_sources(sources_dir, overwrite=args.overwrite)
    print(f"Export: {len(exported)} fichiers -> {sources_dir}")
    if exported:
        for t in exported:
            print(f"- {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

