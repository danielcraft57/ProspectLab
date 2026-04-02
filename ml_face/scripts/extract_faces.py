from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from tqdm import tqdm
from PIL import Image

try:
    from ml_face.face_models import build_facenet_pytorch_models, pick_device
    from ml_face.image_io import load_image
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    from ml_face.face_models import build_facenet_pytorch_models, pick_device
    from ml_face.image_io import load_image


LOGGER = logging.getLogger("ml_face.extract_faces")


@dataclass(frozen=True)
class FaceCrop:
    source_path: str
    face_index: int
    crop_path: str
    box: list[float]
    probability: float | None
    image_width: int
    image_height: int
    source_url: str | None
    image_id: int | None
    entreprise_id: int | None


def iter_images_from_index(index_path: Path) -> list[dict]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    files = payload.get("files", [])
    out: list[dict] = []
    for it in files:
        if isinstance(it, str):
            out.append({"path": str(Path(it))})
            continue
        if isinstance(it, dict):
            out.append(
                {
                    "path": str(it.get("path", "")),
                    "source_url": it.get("source_url"),
                    "image_id": it.get("image_id"),
                    "entreprise_id": it.get("entreprise_id"),
                }
            )
    return out


def _tensor_to_pil(crop: torch.Tensor) -> Image.Image:
    """
    Convertit une crop tensor (CHW) en image PIL (RGB).
    MTCNN renvoie generalement des tensors float en valeurs [0,1] ou parfois [-1,1].
    """
    t = crop.detach().cpu()
    if t.ndim != 3 or t.shape[0] not in (1, 3):
        raise ValueError(f"Format crop inattendu (shape={tuple(t.shape)})")

    # Si jamais c'est en [-1, 1], on ramene vers [0, 1]
    t_min = float(t.min().item())
    t_max = float(t.max().item())
    if t_min < 0.0 and t_max <= 1.0:
        t = (t + 1.0) / 2.0

    t = t.clamp(0.0, 1.0)
    # CHW -> HWC
    arr = (t.permute(1, 2, 0).numpy() * 255.0).round().astype("uint8")
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    return Image.fromarray(arr, mode="RGB")


def main() -> int:
    parser = argparse.ArgumentParser(description="Detecte les visages et sauvegarde des crops.")
    parser.add_argument("--index", default="ml_face/data/photos_index.json", help="Index JSON des photos")
    parser.add_argument("--out-dir", default="ml_face/artifacts/faces_crops", help="Dossier de sortie des crops")
    parser.add_argument("--min-prob", type=float, default=0.90, help="Seuil de confiance detection")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto", help="Device torch")
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre d'images (debug)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")

    index_path = Path(args.index)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.device == "auto":
        device = pick_device(prefer_cuda=True)
    else:
        device = torch.device(args.device)

    models = build_facenet_pytorch_models(device=device)
    image_items = iter_images_from_index(index_path)
    if args.limit and args.limit > 0:
        image_items = image_items[: args.limit]

    manifest_path = out_dir / "manifest.jsonl"
    count_faces = 0

    with manifest_path.open("w", encoding="utf-8") as f:
        for image_item in tqdm(image_items, desc="Extraction visages"):
            img_path = Path(str(image_item.get("path", "")))
            try:
                img = load_image(img_path)
            except Exception as e:
                LOGGER.warning("Image illisible %s (%s)", img_path, e)
                continue

            boxes, probs = models.detector.detect(img)
            if boxes is None or len(boxes) == 0:
                continue

            crops = models.detector.extract(img, boxes, save_path=None)
            if crops is None:
                continue

            for i, crop in enumerate(crops):
                prob = None if probs is None else float(probs[i])
                if prob is not None and prob < args.min_prob:
                    continue

                crop_name = f"{img_path.stem}__face{i}.jpg"
                crop_path = out_dir / crop_name
                if isinstance(crop, torch.Tensor):
                    crop_img = _tensor_to_pil(crop)
                else:
                    crop_img = crop
                crop_img.save(crop_path, format="JPEG", quality=95)

                item = FaceCrop(
                    source_path=str(img_path),
                    face_index=i,
                    crop_path=str(crop_path),
                    box=[float(x) for x in boxes[i].tolist()],
                    probability=prob,
                    image_width=int(img.width),
                    image_height=int(img.height),
                    source_url=image_item.get("source_url"),
                    image_id=image_item.get("image_id"),
                    entreprise_id=image_item.get("entreprise_id"),
                )
                f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
                count_faces += 1

    print(f"OK - {count_faces} visages extraits -> {out_dir}")
    print(f"Manifest -> {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

