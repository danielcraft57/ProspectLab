#!/usr/bin/env python3
"""
Importe les maquettes emails-pub vers template_studio + assets static.

Usage:
    python scripts/import_emails_pub_to_studio.py
    python scripts/import_emails_pub_to_studio.py --sync-db
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOCKUPS = ROOT / "design" / "mockups" / "emails-pub"
OUT_HTML = ROOT / "template_studio" / "html_sources"
OUT_ASSETS = ROOT / "static" / "email" / "danielcraft" / "pub"
IMG_BASE = "{base_url}/static/email/danielcraft/pub"

# fichier mockup -> (id studio, categorie BDD)
PUB_TEMPLATES: list[tuple[str, str, str]] = [
    ("01-offres-reputation.html", "html_dc_offres_reputation", "offres"),
    ("02-offres-vitrine-390.html", "html_dc_offres_vitrine", "offres"),
    ("03-offres-whatsapp.html", "html_dc_offres_whatsapp", "offres"),
    ("04-offres-assistant-ia.html", "html_dc_offres_ia", "offres"),
    ("05-echantillons-metier.html", "html_dc_echantillons_metier", "echantillons"),
    ("06-echantillons-enseigne.html", "html_dc_echantillons_enseigne", "echantillons"),
    ("09-echantillons-restauration.html", "html_dc_echantillons_restauration", "echantillons"),
    ("10-echantillons-auto.html", "html_dc_echantillons_auto", "echantillons"),
    ("11-echantillons-sante.html", "html_dc_echantillons_sante", "echantillons"),
    ("15-echantillons-30s.html", "html_dc_echantillons_30s", "echantillons"),
    ("16-echantillons-mobile.html", "html_dc_echantillons_mobile", "echantillons"),
    ("17-echantillons-demo-live.html", "html_dc_echantillons_demo_live", "echantillons"),
    ("18-echantillons-avant-devis.html", "html_dc_echantillons_avant_devis", "echantillons"),
    ("19-echantillons-catalogue.html", "html_dc_echantillons_catalogue", "echantillons"),
    ("20-echantillons-projection.html", "html_dc_echantillons_projection", "echantillons"),
    ("21-echantillons-secteur-semaine.html", "html_dc_echantillons_secteur_semaine", "echantillons"),
    ("07-bouquins-050.html", "html_dc_bouquins_050", "bouquins"),
    ("08-bouquins-commerce.html", "html_dc_bouquins_commerce", "bouquins"),
    ("12-bouquins-ia.html", "html_dc_bouquins_ia", "bouquins"),
    ("13-bouquins-secu.html", "html_dc_bouquins_secu", "bouquins"),
    ("14-bouquins-code.html", "html_dc_bouquins_code", "bouquins"),
]

AUDIT_IDS = {
    "html_dc_30_sec",
    "html_dc_anciennete_rincee",
    "html_dc_audit_rapport",
    "html_dc_ca_coince",
    "html_dc_clanche",
    "html_dc_franchement",
    "html_dc_relance",
    "html_dc_scores_nareuse",
    "html_dc_secu_clanche",
    "html_dc_voisin_google",
}


def infer_category(template_id: str) -> str:
    """
    Deduit la categorie ProspectLab depuis l'ID technique.

    @param template_id: ID du template (ex: html_dc_offres_reputation)
    @returns: audit | offres | echantillons | bouquins | html_email
    """
    tid = (template_id or "").strip()
    if "_offres_" in tid or tid.startswith("html_dc_offres"):
        return "offres"
    if "_echantillons_" in tid or tid.startswith("html_dc_echantillons"):
        return "echantillons"
    if "_bouquins_" in tid or tid.startswith("html_dc_bouquins"):
        return "bouquins"
    if tid.startswith("html_dc_"):
        return "audit"
    return "html_email"


def prepare_html(raw: str) -> str:
    """
    Adapte le HTML maquette pour l'envoi email (assets, placeholders).

    @param raw: HTML source maquette
    @returns: HTML pret pour template_studio
    """
    out = raw
    out = out.replace('Salut <strong>Claire</strong>', "Salut <strong>{nom}</strong>")
    out = re.sub(
        r'(src|href)=([\'"])assets/([^\'"]+)\2',
        rf"\1=\2{IMG_BASE}/\3\2",
        out,
    )
    return out


def copy_assets() -> int:
    """Copie les heroes JPG (racine + echantillons/) vers static/email/danielcraft/pub/."""
    src_dir = MOCKUPS / "assets"
    if not src_dir.is_dir():
        print("WARN: pas de dossier assets mockups")
        return 0
    OUT_ASSETS.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in src_dir.rglob("*.jpg"):
        rel = path.relative_to(src_dir)
        dest = OUT_ASSETS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        n += 1
        print("asset", rel.as_posix())
    return n


def import_html_sources() -> int:
    """Ecrit les html_sources a partir des maquettes pub."""
    OUT_HTML.mkdir(parents=True, exist_ok=True)
    n = 0
    for filename, tpl_id, _cat in PUB_TEMPLATES:
        src = MOCKUPS / filename
        if not src.is_file():
            print("SKIP missing", filename)
            continue
        html = prepare_html(src.read_text(encoding="utf-8"))
        dest = OUT_HTML / f"{tpl_id}.html"
        dest.write_text(html, encoding="utf-8", newline="\n")
        print("html", tpl_id)
        n += 1
    return n


def patch_templates_data_categories() -> None:
    """Reclasse audit/offres/echantillons/bouquins dans templates_data*.json."""
    import json

    for name in ("templates_data.json", "templates_data.default.json"):
        path = ROOT / "template_studio" / name
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = 0
        for tpl in data.get("templates") or []:
            tid = tpl.get("id") or ""
            cat = infer_category(tid)
            if tpl.get("category") != cat:
                tpl["category"] = cat
                changed += 1
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"categories {name}: {changed} mis a jour")


def sync_studio_and_db() -> None:
    """Regenere JSON studio et upsert BDD."""
    subprocess.run(
        [sys.executable, "-m", "template_studio.generate_cli", "--sync"],
        cwd=str(ROOT),
        check=True,
    )
    patch_templates_data_categories()
    subprocess.run(
        [sys.executable, "scripts/linux/sync_template_studio_to_db.py"],
        cwd=str(ROOT),
        check=True,
    )


def main() -> None:
    """Point d'entree CLI."""
    p = argparse.ArgumentParser()
    p.add_argument("--sync-db", action="store_true", help="Sync templates_data + BDD apres import")
    args = p.parse_args()

    n_assets = copy_assets()
    n_html = import_html_sources()
    print(f"done assets={n_assets} html={n_html}")

    if args.sync_db:
        sync_studio_and_db()
        print("sync BDD OK")


if __name__ == "__main__":
    main()
