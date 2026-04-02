from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

try:
    from ml_face.db_client import MLFaceDB
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    from ml_face.db_client import MLFaceDB


def _l2(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v) + 1e-12
    return v / n


def main() -> int:
    parser = argparse.ArgumentParser(description="Associe des visages detectes a des personnes (mode propose).")
    parser.add_argument("--env-file", default=".env.cluster", help="Fichier env (DATABASE_URL)")
    parser.add_argument("--run-id", type=int, required=True, help="run_id a matcher")
    parser.add_argument("--topk", type=int, default=3, help="Nombre de propositions par visage")
    parser.add_argument("--min-score", type=float, default=0.55, help="Seuil min cosine")
    args = parser.parse_args()

    env_file = Path(args.env_file)
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=str(env_file), override=True)
        except Exception:
            pass

    db = MLFaceDB()
    db.ensure_schema()

    emb_rows = db.list_run_embeddings(args.run_id)
    if not emb_rows:
        raise SystemExit("Aucun embedding pour ce run.")

    # index galerie par entreprise
    gallery_rows = db.list_person_gallery()
    gallery_by_ent: dict[int | None, list[dict]] = {}
    for g in gallery_rows:
        ent = g.get("entreprise_id")
        gallery_by_ent.setdefault(ent, []).append(g)

    proposals = 0
    for e in emb_rows:
        evec = db.decode_embedding_row(e["embedding_b64"], e["embedding_dim"])
        evec = _l2(evec.astype(np.float32))
        ent = e.get("entreprise_id")
        candidates = gallery_by_ent.get(ent) or []
        if not candidates:
            continue

        scored: list[tuple[float, int]] = []
        for c in candidates:
            cvec = db.decode_embedding_row(c["embedding_b64"], c["embedding_dim"])
            cvec = _l2(cvec.astype(np.float32))
            score = float(np.dot(evec, cvec))
            if score >= float(args.min_score):
                scored.append((score, int(c["personne_id"])))
        if not scored:
            continue

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: max(1, int(args.topk))]
        for score, personne_id in top:
            confidence = "low"
            if score >= 0.82:
                confidence = "high"
            elif score >= 0.68:
                confidence = "medium"
            db.upsert_person_match(
                run_id=int(args.run_id),
                embedding_id=int(e["id"]),
                personne_id=personne_id,
                score=score,
                confidence=confidence,
            )
            proposals += 1

    print(f"OK - propositions enregistrees: {proposals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

