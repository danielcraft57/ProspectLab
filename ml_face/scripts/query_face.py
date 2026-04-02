from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import torch
from tqdm import tqdm

try:
    from ml_face.embedding_store import load_embeddings
    from ml_face.face_models import build_facenet_pytorch_models, pick_device
    from ml_face.image_io import load_image
    from ml_face.search import topk_cosine
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    from ml_face.embedding_store import load_embeddings
    from ml_face.face_models import build_facenet_pytorch_models, pick_device
    from ml_face.image_io import load_image
    from ml_face.search import topk_cosine


LOGGER = logging.getLogger("ml_face.query_face")


def _to_tensor(img, device: torch.device) -> torch.Tensor:
    from torchvision import transforms

    tfm = transforms.Compose(
        [
            transforms.Resize((160, 160)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ]
    )
    return tfm(img).unsqueeze(0).to(device)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recherche de visages similaires (cosine similarity).")
    parser.add_argument("--image", required=True, help="Image requete (photo avec visage)")
    parser.add_argument("--emb-dir", default="ml_face/artifacts/embeddings", help="Dossier embeddings")
    parser.add_argument("--topk", type=int, default=10, help="Top K resultats")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto", help="Device torch")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")

    if args.device == "auto":
        device = pick_device(prefer_cuda=True)
    else:
        device = torch.device(args.device)

    emb_dir = Path(args.emb_dir)
    embeddings, rows = load_embeddings(emb_dir)

    models = build_facenet_pytorch_models(device=device)

    img_path = Path(args.image)
    img = load_image(img_path)

    # On detecte d'abord les visages sur l'image requete, puis on fait une requete par visage
    boxes, probs = models.detector.detect(img)
    if boxes is None or len(boxes) == 0:
        raise SystemExit("Aucun visage detecte sur l'image requete.")

    crops = models.detector.extract(img, boxes, save_path=None)
    if crops is None or len(crops) == 0:
        raise SystemExit("Impossible d'extraire les crops du visage.")

    for face_i, crop in enumerate(tqdm(crops, desc="Query faces")):
        x = _to_tensor(crop, device=device)
        with torch.no_grad():
            q = models.embedder(x).detach().cpu().numpy().astype(np.float32)
        hits = topk_cosine(query=q, embeddings=embeddings, k=args.topk)

        print("")
        print(f"Face {face_i} - top {len(hits)}")
        for rank, h in enumerate(hits, start=1):
            r = rows[h.index]
            print(f"{rank}. score={h.score:.4f} source={r.source_path} face_index={r.face_index} crop={r.crop_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

