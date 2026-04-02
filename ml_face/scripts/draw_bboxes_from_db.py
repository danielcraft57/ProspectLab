from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from ml_face.db_client import MLFaceDB
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    from ml_face.db_client import MLFaceDB


def main() -> int:
    parser = argparse.ArgumentParser(description="Dessine les bboxes de visages depuis la BDD sur les images locales.")
    parser.add_argument("--env-file", default=".env.cluster", help="Fichier env (pour DATABASE_URL)")
    parser.add_argument("--run-id", type=int, required=True, help="run_id dans ml_face_runs")
    parser.add_argument("--out-dir", default="ml_face/artifacts/debug_bbox", help="Dossier de sortie")
    parser.add_argument("--limit", type=int, default=100, help="Nombre max de bboxes a dessiner")
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

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        db.execute_sql(
            cursor,
            """
            SELECT source_path, face_index, box_json, probability
            FROM ml_face_embeddings
            WHERE run_id = ?
            LIMIT ?
            """,
            (int(args.run_id), int(args.limit)),
        )
        rows = cursor.fetchall() or []
    finally:
        conn.close()

    per_image: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if isinstance(r, dict):
            source_path = str(r.get("source_path") or "")
            box_json = r.get("box_json")
            face_index = int(r.get("face_index") or 0)
            probability = r.get("probability")
        else:
            source_path = str(r[0] or "")
            box_json = r[2]
            face_index = int(r[1] or 0)
            probability = r[3]

        if not source_path or not box_json:
            continue
        box = json.loads(box_json)
        per_image[source_path].append({"face_index": face_index, "box": box, "probability": probability})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    drawn = 0
    for source_path, items in per_image.items():
        img_path = Path(source_path)
        if not img_path.exists():
            continue
        img = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        for it in items:
            x1, y1, x2, y2 = it["box"]
            # Couleur et epaisseur simples pour debug
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1 + 2, y1 + 2), str(it["face_index"]), fill="red")
            drawn += 1

        out_path = out_dir / f"bbox__{img_path.name}"
        img.save(out_path, format="JPEG", quality=95)

    print(f"OK - bboxes dessinees: {drawn} -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

