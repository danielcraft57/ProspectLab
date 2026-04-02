from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from ml_face.db_client import MLFaceDB
except ModuleNotFoundError:
    import sys

    # Ajoute la racine du repo pour que `services.*` soit importable.
    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ml_face.db_client import MLFaceDB


def main() -> int:
    parser = argparse.ArgumentParser(description="Push identities vers la BDD (prod via DATABASE_URL).")
    parser.add_argument(
        "--env-file",
        default=".env.cluster",
        help="Fichier env a charger (pour definir DATABASE_URL). Defaut: .env.cluster",
    )
    parser.add_argument("--identities", default="ml_face/artifacts/identities/identities.json", help="Fichier identities.json")
    parser.add_argument("--run-id", type=int, required=True, help="run_id cible (celui cree par push_embeddings_to_db.py)")
    args = parser.parse_args()

    env_file = Path(args.env_file)
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=str(env_file), override=True)
        except Exception:
            pass

    identities_path = Path(args.identities)
    payload = json.loads(identities_path.read_text(encoding="utf-8"))

    db = MLFaceDB()
    db.ensure_schema()

    # On mappe les members (indices embeddings) -> embedding_id BDD via (source_path, face_index)
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        db.execute_sql(cursor, "SELECT id, source_path, face_index FROM ml_face_embeddings WHERE run_id=?", (int(args.run_id),))
        rows = cursor.fetchall()
    finally:
        conn.close()

    index_map: dict[tuple[str, int], int] = {}
    for r in rows:
        if isinstance(r, dict):
            index_map[(str(r["source_path"]), int(r["face_index"]))] = int(r["id"])
        else:
            index_map[(str(r[1]), int(r[2]))] = int(r[0])

    # Pour pouvoir resoudre l'index embeddings -> (source_path, face_index),
    # on lit aussi le metadata.jsonl du dossier embeddings.
    emb_meta = Path("ml_face/artifacts/embeddings/metadata.jsonl")
    if not emb_meta.exists():
        raise SystemExit("metadata.jsonl introuvable. Lance d'abord build_embeddings.py (ou copie le fichier).")

    meta_keys: list[tuple[str, int]] = []
    with emb_meta.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            meta_keys.append((str(p.get("source_path", "")), int(p.get("face_index", 0))))

    for ident in payload:
        identity_index = int(ident["id"])
        members = [int(x) for x in ident.get("members", [])]
        size = int(ident.get("size", len(members)))
        identity_id = db.create_identity(run_id=int(args.run_id), identity_index=identity_index, threshold=None, size=size)

        reps = [int(x) for x in ident.get("representatives", [])]
        rep_set = set(reps)

        for m in members:
            if m < 0 or m >= len(meta_keys):
                continue
            key = meta_keys[m]
            emb_id = index_map.get(key)
            if emb_id is None:
                continue
            rank = None
            if m in rep_set:
                rank = reps.index(m) + 1
            db.add_identity_member(identity_id=identity_id, embedding_id=emb_id, rank=rank)

    print("OK - identities pushed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

