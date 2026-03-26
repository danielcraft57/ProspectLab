from __future__ import annotations

import argparse
import html as _html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from template_studio.html_sources_provider import FileHtmlContentProvider
from template_studio.html_templates_generator import HtmlTemplatesGenerator
from template_studio.include_expander import expand_includes
from template_studio.template_repo import JsonTemplatesRepository


def _build_generator(repo_root: Path) -> HtmlTemplatesGenerator:
    # Source de vérité JSON côté Template Studio
    templates_file = repo_root / "template_studio" / "templates_data.json"
    default_file = repo_root / "template_studio" / "templates_data.default.json"

    repo = JsonTemplatesRepository(templates_file=templates_file, default_file=default_file)

    templates = repo.load_templates()

    sources_dir = repo_root / "template_studio" / "html_sources"
    file_provider = FileHtmlContentProvider(sources_dir=sources_dir)
    fragments_dir = repo_root / "template_studio" / "fragments"

    def _infer_title(html_text: str) -> str:
        # On tente de récupérer le <title> pour proposer un subject réutilisable.
        # Si rien n'est trouvé, on renvoie vide.
        m = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
        raw_title = (m.group(1) if m else "").strip()
        # Normaliser les espaces sans toucher aux {placeholders}
        title = re.sub(r"\s+", " ", raw_title).strip()
        return title

    def _humanize_name_from_title_or_id(title: str, tpl_id: str) -> str:
        """
        Produit un nom lisible pour l'UI (différent de l'ID technique).
        - base: <title>
        - sans placeholders {entreprise}, {nom}, etc.
        - sans décorations type "— {entreprise}"
        """
        t = _html.unescape(title or "").strip()
        # Retirer les placeholders
        t = re.sub(r"\{[a-zA-Z0-9_\-]+\}", "", t).strip()
        # Nettoyer les séparateurs et espaces
        t = re.sub(r"\s*[-—–]\s*", " — ", t)
        t = re.sub(r"\s+", " ", t).strip(" —-–")
        if t:
            return t

        # Fallback: à partir de l'ID
        base = (tpl_id or "").strip()
        base = re.sub(r"^html_", "", base)
        base = base.replace("_", " ").strip()
        return base[:1].upper() + base[1:] if base else tpl_id

    def _infer_specs_from_html_sources() -> list[dict]:
        specs: list[dict] = []
        if not sources_dir.exists():
            return specs
        for file_path in sorted(sources_dir.glob("*.html")):
            tpl_id = file_path.stem
            try:
                html_text = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            title = _infer_title(html_text)
            subject = title
            name = _humanize_name_from_title_or_id(title, tpl_id)
            specs.append(
                {
                    "id": tpl_id,
                    "name": name,
                    "subject": subject or "",
                }
            )
        return specs

    # Specs = 100% dérivées des sources HTML (source de vérité),
    # pour garder des `name` lisibles et cohérents même si templates_data.json
    # contenait des noms techniques auparavant.
    html_specs: list[dict] = _infer_specs_from_html_sources()

    return HtmlTemplatesGenerator(
        repo=repo,
        html_specs=html_specs,
        # On inline les fragments dans templates_data*.json pour que l'UI
        # (page “modèles d'email”) affiche du HTML complet sans directives {#include:...}.
        get_html_content_by_id=lambda template_id: expand_includes(file_provider(template_id), fragments_dir),
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(description="Template Studio - génération templates email HTML")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Racine du repo (par défaut: dossier parent du package template_studio).",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write-default", "-w", action="store_true", help="Génère templates_data.default.json (HTML).")
    group.add_argument("--restore", "-r", action="store_true", help="Recopie templates_data.default.json -> templates_data.json.")
    group.add_argument("--sync", "-s", action="store_true", help="Write-default puis restore (sync complète).")

    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    gen = _build_generator(repo_root)

    if args.sync:
        n = gen.write_default_html_only()
        m = gen.restore_from_default()
        print(f"Sync OK: sources -> default({n}) -> templates({m})")
        return 0

    if args.write_default:
        n = gen.write_default_html_only()
        print(f"OK: {repo_root / 'templates_data.default.json'} ecrit avec {n} modeles HTML.")
        return 0

    if args.restore:
        m = gen.restore_from_default()
        print(f"Restauration OK: templates_data.json recree avec {m} modeles HTML.")
        return 0

    added = gen.upsert_missing_templates()
    print(f"Ajout HTML (uniquement manquants) : {added} modeles dans {repo_root / 'templates_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

