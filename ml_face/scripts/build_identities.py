from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from ml_face.embedding_store import load_embeddings
    from ml_face.identities import cluster_by_threshold, pick_representatives
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    from ml_face.embedding_store import load_embeddings
    from ml_face.identities import cluster_by_threshold, pick_representatives


@dataclass(frozen=True)
class IdentityOut:
    id: int
    size: int
    members: list[int]
    representatives: list[int]


def main() -> int:
    parser = argparse.ArgumentParser(description="Regroupe les visages en identites (clustering cosine).")
    parser.add_argument("--emb-dir", default="ml_face/artifacts/embeddings", help="Dossier embeddings")
    parser.add_argument("--out-dir", default="ml_face/artifacts/identities", help="Dossier de sortie")
    parser.add_argument("--threshold", type=float, default=0.75, help="Seuil cosine (plus haut = plus strict)")
    parser.add_argument("--min-size", type=int, default=2, help="Taille min d'une identite")
    parser.add_argument("--rep-k", type=int, default=12, help="Nb de visages representatifs par identite")
    parser.add_argument("--copy-crops", action="store_true", help="Copie quelques crops dans la galerie")
    args = parser.parse_args()

    emb_dir = Path(args.emb_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    embeddings, rows = load_embeddings(emb_dir)
    clusters = cluster_by_threshold(embeddings, threshold=args.threshold, min_cluster_size=args.min_size)

    out: list[IdentityOut] = []
    for c in clusters:
        reps = pick_representatives(embeddings, c.members, k=args.rep_k)
        out.append(IdentityOut(id=c.id, size=len(c.members), members=c.members, representatives=reps))

    out_path = out_dir / "identities.json"
    out_path.write_text(json.dumps([asdict(x) for x in out], ensure_ascii=False, indent=2), encoding="utf-8")

    if args.copy_crops:
        gallery_dir = out_dir / "gallery"
        if gallery_dir.exists():
            shutil.rmtree(gallery_dir)
        gallery_dir.mkdir(parents=True, exist_ok=True)

        for ident in out:
            ident_dir = gallery_dir / f"id_{ident.id:04d}__n{ident.size}"
            ident_dir.mkdir(parents=True, exist_ok=True)
            for rank, idx in enumerate(ident.representatives, start=1):
                crop_path = rows[idx].crop_path
                if not crop_path:
                    continue
                src = Path(crop_path)
                if not src.exists():
                    continue
                dst = ident_dir / f"rep_{rank:02d}__idx{idx}.jpg"
                shutil.copyfile(src, dst)

    print(f"OK - identites: {len(out)} -> {out_path}")
    if args.copy_crops:
        print(f"Galerie -> {out_dir / 'gallery'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

