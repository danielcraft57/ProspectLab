#!/usr/bin/env python3
"""Genere des graphiques PNG email-safe (palette DanielCraft) pour les maquettes."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'assets'

PRIMARY = (77, 169, 214)       # #4da9d6
PRIMARY_DARK = (15, 53, 80)    # #0f3550
METAL_4 = (24, 76, 112)        # #184c70
SECONDARY = (223, 248, 248)    # #dff8f8
ACCENT = (201, 244, 242)       # #c9f4f2
AMBER = (217, 119, 6)          # #d97706
AMBER_SOFT = (254, 243, 199)   # #fef3c7
GREEN = (47, 158, 106)         # #2f9e6a
GREEN_SOFT = (238, 248, 241)   # #eef8f1
GRAY_500 = (107, 114, 128)
GRAY_700 = (55, 65, 81)
WHITE = (255, 255, 255)


def _font(size: int) -> ImageFont.ImageFont:
    for name in (
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibri.ttf',
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def chart_bars_360() -> None:
    """Barres Technique 62 / Protection 28 / Vitesse 71."""
    w, h = 1120, 420
    img = Image.new('RGB', (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=24, fill=SECONDARY)

    title = _font(28)
    label = _font(20)
    value = _font(32)
    draw.text((48, 28), 'Synthèse atelier-nord.fr', fill=PRIMARY_DARK, font=title)
    draw.text((48, 68), 'Technique · Protection · Vitesse', fill=GRAY_500, font=label)

    bars = [
        ('Technique', 62, PRIMARY, ACCENT),
        ('Protection', 28, AMBER, AMBER_SOFT),
        ('Vitesse', 71, GREEN, GREEN_SOFT),
    ]
    base_y = 340
    max_bar = 200
    gap = 40
    bar_w = 280
    x0 = 80
    for i, (name, score, color, soft) in enumerate(bars):
        x = x0 + i * (bar_w + gap)
        bar_h = int(max_bar * (score / 100))
        # track
        draw.rounded_rectangle((x, base_y - max_bar, x + bar_w, base_y), radius=16, fill=WHITE)
        # fill
        draw.rounded_rectangle((x, base_y - bar_h, x + bar_w, base_y), radius=16, fill=color)
        # soft chip behind label
        draw.rounded_rectangle((x, base_y + 16, x + bar_w, base_y + 58), radius=12, fill=soft)
        draw.text((x + 18, base_y + 24), name, fill=PRIMARY_DARK, font=label)
        draw.text((x + 18, base_y - bar_h - 42), f'{score}', fill=color, font=value)

    img.save(OUT / 'chart-scores-360.png', optimize=True)


def chart_protection_gauge() -> None:
    """Jauge horizontale score protection 28/100."""
    w, h = 1120, 280
    img = Image.new('RGB', (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=24, fill=AMBER_SOFT)

    title = _font(26)
    body = _font(20)
    big = _font(48)
    draw.text((48, 32), 'Niveau de protection', fill=PRIMARY_DARK, font=title)
    draw.text((48, 72), 'Corrigeable vite - sans tout refaire', fill=GRAY_700, font=body)
    draw.text((48, 120), '28 / 100', fill=AMBER, font=big)

    track = (48, 200, w - 48, 236)
    draw.rounded_rectangle(track, radius=18, fill=WHITE)
    fill_w = int((w - 96) * 0.28)
    draw.rounded_rectangle((48, 200, 48 + fill_w, 236), radius=18, fill=AMBER)

    img.save(OUT / 'chart-protection-gauge.png', optimize=True)


def chart_priority_sparks() -> None:
    """Mini spark / priorites 1-2-3 pour mail relance ou franchement."""
    w, h = 1120, 320
    img = Image.new('RGB', (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=24, fill=SECONDARY)

    title = _font(26)
    body = _font(18)
    draw.text((48, 28), 'Ce qui freine le plus', fill=PRIMARY_DARK, font=title)

    items = [
        ('Téléphone', 45, PRIMARY),
        ('Protection', 28, AMBER),
        ('Vitesse', 71, GREEN),
    ]
    y = 90
    for name, score, color in items:
        draw.text((48, y), name, fill=GRAY_700, font=body)
        draw.rounded_rectangle((280, y + 4, w - 48, y + 28), radius=12, fill=WHITE)
        fill = int((w - 328) * (score / 100))
        draw.rounded_rectangle((280, y + 4, 280 + fill, y + 28), radius=12, fill=color)
        draw.text((w - 110, y), f'{score}', fill=color, font=body)
        y += 60

    img.save(OUT / 'chart-priorites.png', optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    chart_bars_360()
    chart_protection_gauge()
    chart_priority_sparks()
    print('ok', OUT)


if __name__ == '__main__':
    main()
