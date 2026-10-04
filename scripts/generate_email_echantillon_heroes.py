#!/usr/bin/env python3
"""
Genere les JPG hero email (crop haut, plus haut que le nombre d'or).

Source prioritaire : desktop_*.webp puis tablet_*.webp sous
static/danielcraft/echantillons/<slug>/.

Sortie : static/email/danielcraft/pub/echantillons/<slug>.jpg
Format cible : 1200x1000 (ratio 6:5, plus de hauteur que 1200x742).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "static" / "danielcraft" / "echantillons"
OUT_DIR = ROOT / "static" / "email" / "danielcraft" / "pub" / "echantillons"

# Un peu plus haut que le crop nombre d'or 1200x742
OUT_W = 1200
OUT_H = 1000
JPEG_QUALITY = 86


def _pick_source(slug_dir: Path) -> Path | None:
    """
    Choisit la meilleure source screenshot pour un echantillon.

    @param slug_dir: Dossier static/danielcraft/echantillons/<slug>
    @returns: Chemin image ou None
    """
    candidates = (
        sorted(slug_dir.glob("desktop_*.webp"))
        + sorted(slug_dir.glob("tablet_*.webp"))
        + sorted(slug_dir.glob("catalog_*.webp"))
        + sorted(slug_dir.glob("*.webp"))
        + sorted(slug_dir.glob("*.png"))
        + sorted(slug_dir.glob("*.jpg"))
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def _crop_top(img: Image.Image, width: int, height: int) -> Image.Image:
    """
    Recadre le haut de la page au ratio cible (cover from top).

    @param img: Image source
    @param width: Largeur sortie
    @param height: Hauteur sortie
    @returns: Image RGB recadree
    """
    src = img.convert("RGB")
    sw, sh = src.size
    target_ratio = width / float(height)
    src_ratio = sw / float(sh) if sh else target_ratio

    if src_ratio > target_ratio:
        # Source trop large : crop horizontal centre, garde le haut
        new_w = int(sh * target_ratio)
        left = max(0, (sw - new_w) // 2)
        box = (left, 0, left + new_w, sh)
    else:
        # Source trop haute : garde le haut, crop bas
        new_h = int(sw / target_ratio)
        box = (0, 0, sw, min(sh, new_h))

    cropped = src.crop(box)
    return cropped.resize((width, height), Image.Resampling.LANCZOS)


def generate_all(*, force: bool = True) -> int:
    """
    Genere les JPG hero pour tous les dossiers echantillons.

    @param force: Regenerer meme si le JPG existe
    @returns: Nombre de fichiers ecrits
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for slug_dir in sorted(p for p in SRC_ROOT.iterdir() if p.is_dir()):
        slug = slug_dir.name
        out = OUT_DIR / f"{slug}.jpg"
        if out.is_file() and not force:
            continue
        src = _pick_source(slug_dir)
        if not src:
            print(f"skip {slug}: pas de screenshot")
            continue
        try:
            with Image.open(src) as im:
                hero = _crop_top(im, OUT_W, OUT_H)
            hero.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            written += 1
            print(f"ok {slug} <- {src.name} ({OUT_W}x{OUT_H})")
        except Exception as exc:
            print(f"ERR {slug}: {exc}", file=sys.stderr)
    return written


if __name__ == "__main__":
    n = generate_all(force=True)
    print(f"done written={n}")
