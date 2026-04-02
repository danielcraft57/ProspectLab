from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


def load_image(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")

