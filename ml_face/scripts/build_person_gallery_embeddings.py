from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from tqdm import tqdm

try:
    from ml_face.db_client import MLFaceDB
    from ml_face.face_models import build_facenet_pytorch_models, pick_device
    from ml_face.image_io import load_image
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
    from ml_face.db_client import MLFaceDB
    from ml_face.face_models import build_facenet_pytorch_models, pick_device
    from ml_face.image_io import load_image


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


def _parse_photos_urls_field(raw: str | None) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        out: list[str] = []
        for x in data:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                out.append(s)
        return out
    if isinstance(data, str) and data.strip():
        return [data.strip()]
    return []


def _collect_gallery_rows(db: MLFaceDB, entreprise_id: int) -> tuple[list[tuple[int, int | None, str]], int, int]:
    """
    Photos candidates: personnes_photos + URLs JSON dans personnes_osint_details.photos_urls.
    Retourne (lignes uniques (personne_id, entreprise_id, url), nb_lignes_pp, nb_lignes_osint).
    """
    seen: set[tuple[int, str]] = set()
    rows: list[tuple[int, int | None, str]] = []

    conn = db.get_connection()
    cursor = conn.cursor()
    n_pp = 0
    n_osint = 0
    try:
        if entreprise_id and entreprise_id > 0:
            db.execute_sql(
                cursor,
                """
                SELECT pp.personne_id, p.entreprise_id, pp.photo_url
                FROM personnes_photos pp
                JOIN personnes p ON p.id = pp.personne_id
                WHERE p.entreprise_id = ?
                """,
                (int(entreprise_id),),
            )
        else:
            db.execute_sql(
                cursor,
                """
                SELECT pp.personne_id, p.entreprise_id, pp.photo_url
                FROM personnes_photos pp
                JOIN personnes p ON p.id = pp.personne_id
                """,
            )
        for row in cursor.fetchall() or []:
            if isinstance(row, dict):
                personne_id = int(row.get("personne_id"))
                eid = row.get("entreprise_id")
                photo_url = str(row.get("photo_url") or "")
            else:
                personne_id = int(row[0])
                eid = row[1]
                photo_url = str(row[2] or "")
            n_pp += 1
            if not photo_url:
                continue
            key = (personne_id, photo_url)
            if key not in seen:
                seen.add(key)
                rows.append((personne_id, None if eid is None else int(eid), photo_url))

        if entreprise_id and entreprise_id > 0:
            db.execute_sql(
                cursor,
                """
                SELECT p.id, p.entreprise_id, pod.photos_urls
                FROM personnes_osint_details pod
                JOIN personnes p ON p.id = pod.personne_id
                WHERE p.entreprise_id = ?
                AND pod.photos_urls IS NOT NULL AND TRIM(pod.photos_urls) <> ''
                """,
                (int(entreprise_id),),
            )
        else:
            db.execute_sql(
                cursor,
                """
                SELECT p.id, p.entreprise_id, pod.photos_urls
                FROM personnes_osint_details pod
                JOIN personnes p ON p.id = pod.personne_id
                WHERE pod.photos_urls IS NOT NULL AND TRIM(pod.photos_urls) <> ''
                """,
            )
        for row in cursor.fetchall() or []:
            if isinstance(row, dict):
                personne_id = int(row.get("id"))
                eid = row.get("entreprise_id")
                raw_urls = row.get("photos_urls")
            else:
                personne_id = int(row[0])
                eid = row[1]
                raw_urls = row[2]
            n_osint += 1
            for photo_url in _parse_photos_urls_field(raw_urls if isinstance(raw_urls, str) else None):
                key = (personne_id, photo_url)
                if key not in seen:
                    seen.add(key)
                    rows.append((personne_id, None if eid is None else int(eid), photo_url))
    finally:
        conn.close()

    return rows, n_pp, n_osint


def main() -> int:
    parser = argparse.ArgumentParser(description="Construit une galerie embeddings des personnes (photos OSINT).")
    parser.add_argument("--env-file", default=".env.cluster", help="Fichier env (DATABASE_URL)")
    parser.add_argument("--entreprise-id", type=int, default=0, help="Filtre entreprise (0=toutes)")
    parser.add_argument("--limit", type=int, default=0, help="Limiter les photos traitees")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto")
    args = parser.parse_args()

    env_file = Path(args.env_file)
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=str(env_file), override=True)
        except Exception:
            pass

    if args.device == "auto":
        device = pick_device(prefer_cuda=True)
    else:
        device = torch.device(args.device)

    db = MLFaceDB()
    db.ensure_schema()
    models = build_facenet_pytorch_models(device=device)

    rows, n_pp, n_osint = _collect_gallery_rows(db, int(args.entreprise_id))
    print(
        f"Sources BDD: personnes_photos={n_pp} lignes, "
        f"personnes_osint_details (avec photos_urls)={n_osint} lignes, "
        f"URLs uniques a traiter={len(rows)}"
    )
    if not rows:
        print(
            "Aucune photo de reference: enrichir OSINT (photos dans personnes_photos ou "
            "tableau JSON photos_urls dans personnes_osint_details), puis relancer ce script."
        )
        return 0

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    ok = 0
    for row in tqdm(rows, desc="Person gallery"):
        personne_id, entreprise_id, photo_url = row[0], row[1], row[2]
        photo_url = str(photo_url or "")

        if not photo_url:
            continue
        try:
            import requests

            r = requests.get(photo_url, timeout=20, headers={"User-Agent": "ProspectLab-MLFace/1.0"})
            if r.status_code != 200:
                continue
            tmp_path = Path("ml_face/artifacts/person_gallery_tmp.jpg")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(r.content)
            img = load_image(tmp_path)
            boxes, probs = models.detector.detect(img)
            if boxes is None or len(boxes) == 0:
                continue
            crops = models.detector.extract(img, boxes, save_path=None)
            if not crops:
                continue
            x = _to_tensor(crops[0], device=device)
            with torch.no_grad():
                emb = models.embedder(x).detach().cpu().numpy().reshape(-1)
            db.upsert_person_gallery_embedding(
                personne_id=personne_id,
                entreprise_id=None if entreprise_id is None else int(entreprise_id),
                source_url=photo_url,
                source_path=None,
                embedding=emb,
            )
            ok += 1
        except Exception:
            continue

    print(f"OK - person gallery embeddings: {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

