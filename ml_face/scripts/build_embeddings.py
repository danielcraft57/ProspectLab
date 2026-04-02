from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

try:
    from ml_face.embedding_store import EmbeddingRow, l2_normalize, save_embeddings
    from ml_face.face_models import build_facenet_pytorch_models, pick_device
    from ml_face.image_io import load_image
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    from ml_face.embedding_store import EmbeddingRow, l2_normalize, save_embeddings
    from ml_face.face_models import build_facenet_pytorch_models, pick_device
    from ml_face.image_io import load_image


LOGGER = logging.getLogger("ml_face.build_embeddings")


@dataclass(frozen=True)
class ManifestRow:
    source_path: str
    face_index: int
    crop_path: str
    box: list[float] | None
    probability: float | None
    image_width: int | None
    image_height: int | None
    source_url: str | None
    image_id: int | None
    entreprise_id: int | None


def read_manifest(manifest_path: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    with manifest_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            rows.append(
                ManifestRow(
                    source_path=str(p.get("source_path", "")),
                    face_index=int(p.get("face_index", 0)),
                    crop_path=str(p.get("crop_path", "")),
                    box=p.get("box"),
                    probability=p.get("probability"),
                    image_width=p.get("image_width"),
                    image_height=p.get("image_height"),
                    source_url=p.get("source_url"),
                    image_id=p.get("image_id"),
                    entreprise_id=p.get("entreprise_id"),
                )
            )
    return rows


def _to_tensor(img: Image.Image, device: torch.device) -> torch.Tensor:
    # facenet-pytorch attend un tensor float [3, 160, 160] normalise [-1,1]
    from torchvision import transforms

    tfm = transforms.Compose(
        [
            transforms.Resize((160, 160)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ]
    )
    t = tfm(img).unsqueeze(0).to(device)
    return t


def main() -> int:
    parser = argparse.ArgumentParser(description="Calcule les embeddings a partir des crops.")
    parser.add_argument(
        "--manifest",
        default="ml_face/artifacts/faces_crops/manifest.jsonl",
        help="Manifest JSONL genere par extract_faces.py",
    )
    parser.add_argument("--out-dir", default="ml_face/artifacts/embeddings", help="Dossier de sortie")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto", help="Device torch")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size embeddings")
    parser.add_argument("--limit", type=int, default=0, help="Limiter (debug)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")

    manifest_path = Path(args.manifest)
    out_dir = Path(args.out_dir)

    if args.device == "auto":
        device = pick_device(prefer_cuda=True)
    else:
        device = torch.device(args.device)

    models = build_facenet_pytorch_models(device=device)
    rows = read_manifest(manifest_path)
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    embeddings_list: list[np.ndarray] = []
    meta_rows: list[EmbeddingRow] = []

    batch_tensors: list[torch.Tensor] = []
    batch_meta: list[ManifestRow] = []

    def flush_batch() -> None:
        nonlocal batch_tensors, batch_meta
        if not batch_tensors:
            return
        x = torch.cat(batch_tensors, dim=0)
        with torch.no_grad():
            y = models.embedder(x).detach().cpu().numpy()
        embeddings_list.append(y)
        for m in batch_meta:
            meta_rows.append(
                EmbeddingRow(
                    source_path=m.source_path,
                    face_index=m.face_index,
                    crop_path=m.crop_path,
                    probability=m.probability,
                    box=m.box,
                    image_width=m.image_width,
                    image_height=m.image_height,
                    source_url=m.source_url,
                    image_id=m.image_id,
                    entreprise_id=m.entreprise_id,
                )
            )
        batch_tensors = []
        batch_meta = []

    for r in tqdm(rows, desc="Embeddings"):
        crop_path = Path(r.crop_path)
        try:
            img = load_image(crop_path)
        except Exception as e:
            LOGGER.warning("Crop illisible %s (%s)", crop_path, e)
            continue
        t = _to_tensor(img, device=device)
        batch_tensors.append(t)
        batch_meta.append(r)
        if len(batch_tensors) >= args.batch_size:
            flush_batch()

    flush_batch()

    if not embeddings_list:
        raise SystemExit("Aucun embedding produit. Verifie le manifest.")

    embeddings = np.concatenate(embeddings_list, axis=0).astype(np.float32)
    embeddings = l2_normalize(embeddings)
    save_embeddings(out_dir=out_dir, embeddings=embeddings, rows=meta_rows)

    print(f"OK - embeddings: {embeddings.shape} -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

