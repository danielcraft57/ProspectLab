from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from tqdm import tqdm

try:
    from ml_face.db_client import MLFaceDB
    from ml_face.embedding_store import load_embeddings
except ModuleNotFoundError:
    import sys

    # Ajoute la racine du repo pour que `services.*` soit importable.
    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml_face.db_client import MLFaceDB
    from ml_face.embedding_store import load_embeddings


@dataclass(frozen=True)
class IdentityKey:
    source_path: str
    face_index: int


def main() -> int:
    parser = argparse.ArgumentParser(description="Push embeddings vers la BDD (prod via DATABASE_URL).")
    parser.add_argument(
        "--env-file",
        default=".env.cluster",
        help="Fichier env a charger (pour definir DATABASE_URL). Defaut: .env.cluster",
    )
    parser.add_argument("--emb-dir", default="ml_face/artifacts/embeddings", help="Dossier embeddings")
    parser.add_argument("--run-name", default="default", help="Nom du run (creera une ligne ml_face_runs)")
    parser.add_argument("--limit", type=int, default=0, help="Limiter (debug)")
    args = parser.parse_args()

    env_file = Path(args.env_file)
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=str(env_file), override=True)
        except Exception:
            pass

    emb_dir = Path(args.emb_dir)
    embeddings, rows = load_embeddings(emb_dir)
    if args.limit and args.limit > 0:
        embeddings = embeddings[: args.limit]
        rows = rows[: args.limit]

    db = MLFaceDB()
    db.ensure_schema()
    run = db.create_run(args.run_name)

    for i in tqdm(range(len(rows)), desc="DB embeddings"):
        r = rows[i]
        emb = embeddings[i]
        box = None
        if r.box is not None:
            box = [float(x) for x in r.box]
        db.upsert_embedding(
            run_id=run.id,
            image_id=None if r.image_id is None else int(r.image_id),
            entreprise_id=None if r.entreprise_id is None else int(r.entreprise_id),
            source_path=r.source_path,
            source_url=r.source_url,
            face_index=int(r.face_index),
            crop_path=r.crop_path,
            probability=None if r.probability is None else float(r.probability),
            box=box,
            image_width=None if r.image_width is None else int(r.image_width),
            image_height=None if r.image_height is None else int(r.image_height),
            embedding=emb,
        )

    print(f"OK - embeddings pushed. run_id={run.id} name={run.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

