#!/usr/bin/env python3
"""
Telecharge et prepare les heroes email-pub a partir des assets danielcraft.fr.

Inclut les screenshots echantillons (sitemap) recadres au format email (nombre d'or).

Usage:
    python scripts/prepare_emails_pub_assets.py
    python scripts/prepare_emails_pub_assets.py --echantillons-only
"""
from __future__ import annotations

import argparse
import urllib.request
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design" / "mockups" / "emails-pub" / "assets"
OUT_ECHANTILLONS = OUT / "echantillons"
STATIC_PUB = ROOT / "static" / "email" / "danielcraft" / "pub"
STATIC_ECHANTILLONS = STATIC_PUB / "echantillons"

SITEMAP_URL = "https://danielcraft.fr/sitemap-echantillons.xml"
SCREENSHOT_TMPL = "https://danielcraft.fr/echantillons/{slug}/screenshots/tablet_1024x2500.webp"

# Fallback si sitemap indisponible
DEFAULT_ECHANTILLON_SLUGS = (
    "restauration",
    "beaute",
    "odontologie",
    "automobile",
    "commerce",
    "comptable",
    "industrie",
    "immobilier",
    "juridique",
    "architecture",
    "fitness",
    "photographie",
    "association",
    "education",
    "services",
    "etablissement",
    "technologie",
    "boulangerie",
    "artisan",
    "fleuriste",
    "caviste",
    "osteo",
    "saas-landing",
    "saas-dashboard",
    "saas-empty",
    "saas-notifications",
    "saas-onboarding",
)

# Alias historiques (anciennes maquettes)
LEGACY_ECHANTILLON_ALIASES = {
    "hero-echantillons.jpg": "beaute",
    "hero-echantillons-enseigne.jpg": "commerce",
    "hero-echantillons-restauration.jpg": "restauration",
    "hero-echantillons-automobile.jpg": "automobile",
    "hero-echantillons-sante.jpg": "odontologie",
    "hero-echantillons-immo.jpg": "immobilier",
    "hero-echantillons-juridique.jpg": "juridique",
}

DIRECT = {
    "hero-offres-reputation.jpg": "https://danielcraft.fr/assets/images/prestations/cards/pack-reputation-locale.jpg",
    "hero-offres-vitrine.jpg": "https://danielcraft.fr/assets/images/prestations/cards/site-vitrine-essentiel.jpg",
    "hero-offres-whatsapp.jpg": "https://danielcraft.fr/assets/images/prestations/cards/pack-whatsapp-commerce.jpg",
    "hero-offres-ia.jpg": "https://danielcraft.fr/assets/images/prestations/cards/repondeur-intelligent.jpg",
}

COVERS_BOUQUINS = [
    "https://danielcraft.fr/assets/images/livres/covers/html-css-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/python-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/ia-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/git-les-bases.jpg",
]

COVERS_COMMERCE = [
    "https://danielcraft.fr/assets/images/livres/covers/commerce-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/vente-avancee.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/ecommerce-trouver-clients.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/ecommerce-clients.jpg",
]

COVERS_IA = [
    "https://danielcraft.fr/assets/images/livres/covers/ia-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/ia-machine-learning.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/ia-deep-learning.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/python-les-bases.jpg",
]

COVERS_SECU = [
    "https://danielcraft.fr/assets/images/livres/covers/securite-web-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/securite-web-intermediaire.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/securite-web-expert.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/git-les-bases.jpg",
]

COVERS_CODE = [
    "https://danielcraft.fr/assets/images/livres/covers/html-css-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/javascript-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/python-les-bases.jpg",
    "https://danielcraft.fr/assets/images/livres/covers/git-les-bases.jpg",
]

PHI = 1.6180339887
# Hero email : largeur L, hauteur l = L / φ (nombre d'or paysage)
HERO_W = 1200
HERO_H = int(round(HERO_W / PHI))  # ~742


def fetch(url: str) -> bytes:
    """
    Telecharge une URL et renvoie les octets.

    @param url: URL absolue
    @returns: Contenu binaire
    @raises: urllib.error.URLError / HTTPError
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ProspectLab-email-assets/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def list_echantillon_slugs_from_sitemap() -> list[str]:
    """
    Lit le sitemap echantillons et extrait les slugs.

    @returns: Liste de slugs uniques (hors pages demo)
    """
    try:
        raw = fetch(SITEMAP_URL)
        root = ET.fromstring(raw)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [el.text or "" for el in root.findall("sm:url/sm:loc", ns)]
        if not locs:
            locs = [el.text or "" for el in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        slugs: list[str] = []
        for loc in locs:
            # https://danielcraft.fr/echantillons/<slug>/
            parts = loc.rstrip("/").split("/")
            if len(parts) < 2:
                continue
            if "echantillons" not in parts:
                continue
            idx = parts.index("echantillons")
            if idx + 1 >= len(parts):
                continue
            slug = parts[idx + 1].strip()
            if not slug or slug in ("demo",) or "demo" in parts[idx + 1 :]:
                continue
            if slug not in slugs:
                slugs.append(slug)
        return slugs or list(DEFAULT_ECHANTILLON_SLUGS)
    except Exception as exc:
        print(f"WARN sitemap: {exc} -> fallback liste locale")
        return list(DEFAULT_ECHANTILLON_SLUGS)


def to_hero_cover(im: Image.Image, size: tuple[int, int] | None = None) -> Image.Image:
    """Recadre une image en cover centre vers le format hero email (nombre d'or)."""
    target_w, target_h = size or (HERO_W, HERO_H)
    w, h = im.size
    scale = max(target_w / w, target_h / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - target_w) // 2
    top = (nh - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def crop_top_half_golden(im: Image.Image, size: tuple[int, int] | None = None) -> Image.Image:
    """
    Recadre la moitie haute d'un screenshot, puis force le ratio d'or L x l.

    @param im: Screenshot tablet (tres haut)
    @param size: (L, l) avec L/l ≈ φ ; defaut 1200x742
    @returns: Image RGB hero email
    """
    target_w, target_h = size or (HERO_W, HERO_H)
    w, h = im.size
    top_half = im.crop((0, 0, w, max(1, h // 2)))
    tw, th = top_half.size
    crop_h = min(int(tw / PHI), th)
    window = top_half.crop((0, 0, tw, crop_h))
    return window.resize((target_w, target_h), Image.Resampling.LANCZOS)


def collage(urls: list[str], size: tuple[int, int] | None = None) -> Image.Image:
    """Assemble 4 covers sur fond turquoise DanielCraft (canvas ratio d'or)."""
    target_w, target_h = size or (HERO_W, HERO_H)
    imgs = [Image.open(BytesIO(fetch(u))).convert("RGB") for u in urls]
    height = int(target_h * 0.88)
    resized = []
    for im in imgs:
        ratio = height / im.height
        resized.append(im.resize((max(1, int(im.width * ratio)), height), Image.Resampling.LANCZOS))
    gap = 24
    total_w = sum(i.width for i in resized) + gap * (len(resized) + 1)
    canvas = Image.new("RGB", (max(total_w, target_w), target_h), (223, 248, 248))
    x = gap
    y = (target_h - height) // 2
    for im in resized:
        canvas.paste(im, (x, y))
        x += im.width + gap
    return canvas.resize((target_w, target_h), Image.Resampling.LANCZOS)


def save_jpg(im: Image.Image, path: Path) -> None:
    """
    Enregistre un JPG email-friendly (et miroir static si sous assets/).

    @param im: Image RGB
    @param path: Destination sous design/mockups/emails-pub/assets
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(path, "JPEG", quality=82, optimize=True)
    # Miroir dans static pour envoi email ({base_url}/static/...)
    try:
        rel = path.relative_to(OUT)
        static_path = STATIC_PUB / rel
        static_path.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").save(static_path, "JPEG", quality=82, optimize=True)
    except ValueError:
        pass
    print("ok", path.relative_to(OUT).as_posix(), im.size)


def prepare_echantillon_heroes(slugs: list[str] | None = None) -> int:
    """
    Telecharge + croppe les screenshots echantillons pour l'email.

    @param slugs: Liste de slugs (defaut = sitemap)
    @returns: Nombre de heroes generes
    """
    OUT_ECHANTILLONS.mkdir(parents=True, exist_ok=True)
    STATIC_ECHANTILLONS.mkdir(parents=True, exist_ok=True)
    targets = slugs or list_echantillon_slugs_from_sitemap()
    ok = 0
    for slug in targets:
        url = SCREENSHOT_TMPL.format(slug=slug)
        try:
            im = Image.open(BytesIO(fetch(url))).convert("RGB")
            hero = crop_top_half_golden(im)
            save_jpg(hero, OUT_ECHANTILLONS / f"{slug}.jpg")
            ok += 1
        except Exception as exc:
            print(f"SKIP {slug}: {exc}")
    # Alias historiques pour maquettes / galerie
    for alias, slug in LEGACY_ECHANTILLON_ALIASES.items():
        src = OUT_ECHANTILLONS / f"{slug}.jpg"
        if not src.is_file():
            continue
        im = Image.open(src).convert("RGB")
        save_jpg(im, OUT / alias)
    return ok


def main() -> None:
    """Prepare tous les heroes locaux a partir des assets DanielCraft."""
    parser = argparse.ArgumentParser(description="Prepare heroes email-pub")
    parser.add_argument(
        "--echantillons-only",
        action="store_true",
        help="Ne regenerer que les screenshots echantillons",
    )
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    STATIC_PUB.mkdir(parents=True, exist_ok=True)

    n_ech = prepare_echantillon_heroes()
    print(f"echantillons heroes={n_ech}")

    if args.echantillons_only:
        print("done (echantillons-only)", f"hero={HERO_W}x{HERO_H} (phi)")
        return

    for name, url in DIRECT.items():
        im = Image.open(BytesIO(fetch(url))).convert("RGB")
        save_jpg(to_hero_cover(im), OUT / name)

    save_jpg(collage(COVERS_BOUQUINS), OUT / "hero-bouquins.jpg")
    save_jpg(collage(COVERS_COMMERCE), OUT / "hero-bouquins-commerce.jpg")
    save_jpg(collage(COVERS_IA), OUT / "hero-bouquins-ia.jpg")
    save_jpg(collage(COVERS_SECU), OUT / "hero-bouquins-secu.jpg")
    save_jpg(collage(COVERS_CODE), OUT / "hero-bouquins-code.jpg")
    print("done", f"hero={HERO_W}x{HERO_H} (phi)")


if __name__ == "__main__":
    main()
