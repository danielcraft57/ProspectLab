from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.email_subject import humanize_template_name, infer_subject_from_html

from template_studio.html_sources_provider import brand_provider
from template_studio.html_templates_generator import HtmlTemplatesGenerator
from template_studio.include_expander import expand_includes
from template_studio.template_repo import JsonTemplatesRepository


def _normalize_brand_slug(brand: str | None) -> str | None:
    if brand is None:
        return None
    b = str(brand).strip().lower()
    if not b:
        return None
    b = re.sub(r"[^a-z0-9_-]+", "_", b)
    b = re.sub(r"_+", "_", b).strip("_")
    return b or None


def _build_generator(repo_root: Path, brand: str | None = None) -> HtmlTemplatesGenerator:
    brand_slug = _normalize_brand_slug(brand)
    # Source de vérité JSON côté Template Studio
    if brand_slug:
        brand_root = repo_root / "template_studio" / "brands" / brand_slug
        brand_root.mkdir(parents=True, exist_ok=True)
        templates_file = brand_root / "templates_data.json"
        default_file = brand_root / "templates_data.default.json"
    else:
        templates_file = repo_root / "template_studio" / "templates_data.json"
        default_file = repo_root / "template_studio" / "templates_data.default.json"

    repo = JsonTemplatesRepository(templates_file=templates_file, default_file=default_file)

    templates = repo.load_templates()

    common_sources_dir = repo_root / "template_studio" / "html_sources"
    brand_sources_dir = (
        repo_root / "template_studio" / "brands" / brand_slug / "html_sources"
        if brand_slug
        else None
    )
    get_html_from_sources = brand_provider(
        common_sources_dir=common_sources_dir,
        brand_sources_dir=brand_sources_dir,
    )

    common_fragments_dir = repo_root / "template_studio" / "fragments"
    brand_fragments_dir = (
        repo_root / "template_studio" / "brands" / brand_slug / "fragments"
        if brand_slug
        else None
    )
    fragments_dirs = [d for d in [brand_fragments_dir, common_fragments_dir] if d is not None]

    def _infer_title(html_text: str) -> str:
        """Déduit le sujet depuis le HTML (commentaire SUBJECT ou balise title)."""
        return infer_subject_from_html(html_text)

    def _humanize_name_from_title_or_id(title: str, tpl_id: str) -> str:
        """Produit un nom lisible pour l'UI (sans Objet:, placeholders ni ())."""
        return humanize_template_name(title, tpl_id)

    def _category_for_id(tpl_id: str) -> str:
        """Categorie UI : audit, offres, echantillons, bouquins."""
        tid = (tpl_id or "").strip()
        if "_offres_" in tid or tid.startswith("html_dc_offres"):
            return "offres"
        if "_echantillons_" in tid or tid.startswith("html_dc_echantillons"):
            return "echantillons"
        if "_bouquins_" in tid or tid.startswith("html_dc_bouquins"):
            return "bouquins"
        if tid.startswith("html_dc_"):
            return "audit"
        return "html_email"

    def _infer_specs_from_html_sources() -> list[dict]:
        specs: list[dict] = []
        scan_dirs = [d for d in [brand_sources_dir, common_sources_dir] if d is not None]
        known: set[str] = set()
        if not scan_dirs:
            return specs
        for src_dir in scan_dirs:
            if not src_dir.exists():
                continue
            for file_path in sorted(src_dir.glob("*.html")):
                tpl_id = file_path.stem
                if tpl_id in known:
                    continue
                known.add(tpl_id)
                try:
                    html_text = get_html_from_sources(tpl_id)
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
                        "category": _category_for_id(tpl_id),
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
        get_html_content_by_id=lambda template_id: expand_includes(
            get_html_from_sources(template_id),
            fragments_dirs,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(description="Template Studio - génération templates email HTML")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Racine du repo (par défaut: dossier parent du package template_studio).",
    )
    parser.add_argument(
        "--brand",
        default=None,
        help="Slug de marque/domaine (ex: danielcraft, jammy). "
             "Si défini, lit/écrit dans template_studio/brands/<slug>/.",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write-default", "-w", action="store_true", help="Génère templates_data.default.json (HTML).")
    group.add_argument("--restore", "-r", action="store_true", help="Recopie templates_data.default.json -> templates_data.json.")
    group.add_argument("--sync", "-s", action="store_true", help="Write-default puis restore (sync complète).")

    parser.add_argument(
        "--only-ids",
        default=None,
        metavar="ID1,ID2",
        help="Régénère et fusionne uniquement ces template_id (sources HTML), sans resynchroniser tout le bundle.",
    )

    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    gen = _build_generator(repo_root, brand=args.brand)

    if args.only_ids:
        ids = [x.strip() for x in str(args.only_ids).split(",") if x.strip()]
        n = gen.upsert_templates_by_ids(ids)
        print(f"OK: {n} modele(s) mis a jour (merge) -> {gen.repo.templates_file}")
        return 0

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

