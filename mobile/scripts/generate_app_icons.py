"""
Genere l'icone ProspectLab (prospection / loupe / tendance) pour Expo et Android natif.
Execute depuis mobile/: python scripts/generate_app_icons.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
RES = ROOT / "android" / "app" / "src" / "main" / "res"

# Tailles Android (Expo prebuild habituel)
FOREGROUND_SIZES = {
    "mipmap-mdpi": 108,
    "mipmap-hdpi": 162,
    "mipmap-xhdpi": 216,
    "mipmap-xxhdpi": 324,
    "mipmap-xxxhdpi": 432,
}
LEGACY_SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def draw_vertical_gradient(img: Image.Image, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    px = img.load()
    w, h = img.size
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(lerp(top[0], bottom[0], t))
        g = int(lerp(top[1], bottom[1], t))
        b = int(lerp(top[2], bottom[2], t))
        for x in range(w):
            px[x, y] = (r, g, b, 255)


def draw_icon_rgba(size: int) -> Image.Image:
    """Loupe + mini graphique montant sur fond degrade (theme prospection)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    r_outer = int(size * 0.42)

    # Disque principal (fond icone)
    bbox = (cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    # degrade vertical dans le cercle
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse(bbox, fill=255)
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    top = (15, 23, 42)  # #0f172a
    bottom = (30, 58, 138)  # #1e3a8a
    draw_vertical_gradient(grad, top, bottom)
    grad.putalpha(mask)
    img.alpha_composite(grad)

    # Anneau loupe (clair)
    ring_w = max(2, size // 42)
    r_lens = int(size * 0.22)
    draw.arc(
        (cx - r_lens, cy - r_lens - int(size * 0.02), cx + r_lens, cy + r_lens - int(size * 0.02)),
        start=200,
        end=520,
        fill=(226, 232, 240, 255),
        width=ring_w,
    )

    # Manche loupe
    ang = math.radians(45)
    x0 = cx + int(r_lens * 0.55 * math.cos(ang))
    y0 = cy + int(r_lens * 0.55 * math.sin(ang)) - int(size * 0.02)
    x1 = cx + int(r_outer * 0.95 * math.cos(ang))
    y1 = cy + int(r_outer * 0.95 * math.sin(ang)) - int(size * 0.02)
    draw.line((x0, y0, x1, y1), fill=(147, 197, 253, 255), width=max(3, size // 28))

    # Petit graphique / "prospectus" (3 barres)
    bw = max(2, size // 38)
    gap = max(3, size // 55)
    bx0 = cx - int(size * 0.12)
    base = cy + int(size * 0.08)
    heights = [0.06, 0.1, 0.14]
    for i, h in enumerate(heights):
        x = bx0 + i * (bw + gap)
        hh = int(size * h)
        draw.rounded_rectangle(
            (x, base - hh, x + bw, base),
            radius=max(1, bw // 3),
            fill=(52, 211, 153, 255),
        )

    # Point cible (prospect)
    pr = max(2, size // 55)
    draw.ellipse((cx - pr, cy - int(size * 0.12) - pr, cx + pr, cy - int(size * 0.12) + pr), fill=(251, 191, 36, 255))

    return img


def composite_on_background(foreground_rgba: Image.Image, bg: tuple[int, int, int]) -> Image.Image:
    base = Image.new("RGBA", foreground_rgba.size, (*bg, 255))
    base.alpha_composite(foreground_rgba)
    return base


def save_webp(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = img.convert("RGBA")
    rgb.save(path, "WEBP", quality=92, method=6)


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def main() -> None:
    master = 1024
    fg_master = draw_icon_rgba(master)

    # Expo: icone store + adaptive foreground + splash + favicon
    save_png(fg_master, ASSETS / "icon.png")
    save_png(fg_master, ASSETS / "adaptive-icon.png")
    save_png(fg_master, ASSETS / "splash-icon.png")
    small = fg_master.resize((48, 48), Image.Resampling.LANCZOS)
    save_png(small, ASSETS / "favicon.png")

    bg = (11, 16, 33)  # #0b1021 — aligne values/colors iconBackground

    for folder, px in FOREGROUND_SIZES.items():
        im = fg_master.resize((px, px), Image.Resampling.LANCZOS)
        save_webp(im, RES / folder / "ic_launcher_foreground.webp")

    for folder, px in LEGACY_SIZES.items():
        fg = fg_master.resize((px, px), Image.Resampling.LANCZOS)
        legacy = composite_on_background(fg, bg)
        save_webp(legacy, RES / folder / "ic_launcher.webp")
        save_webp(legacy, RES / folder / "ic_launcher_round.webp")

    colors_xml = ROOT / "android" / "app" / "src" / "main" / "res" / "values" / "colors.xml"
    if colors_xml.exists():
        txt = colors_xml.read_text(encoding="utf-8")
        txt = txt.replace(
            '<color name="iconBackground">#ffffff</color>',
            '<color name="iconBackground">#0B1021</color>',
        )
        txt = txt.replace(
            '<color name="splashscreen_background">#ffffff</color>',
            '<color name="splashscreen_background">#0B1021</color>',
        )
        colors_xml.write_text(txt, encoding="utf-8")

    import json

    app_json = ROOT / "app.json"
    if app_json.exists():
        data = json.loads(app_json.read_text(encoding="utf-8"))
        ex = data.setdefault("expo", {})
        ex.setdefault("splash", {})["backgroundColor"] = "#0B1021"
        ex.setdefault("android", {}).setdefault("adaptiveIcon", {})["backgroundColor"] = "#0B1021"
        app_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("OK: assets + mipmap-* webp + colors + app.json")


if __name__ == "__main__":
    main()
