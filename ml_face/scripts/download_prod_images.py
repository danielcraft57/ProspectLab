from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    from services.database.base import DatabaseBase
except ModuleNotFoundError:
    import sys

    # lancer depuis la racine du repo ou fallback ici
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from services.database.base import DatabaseBase


def _safe_filename(url: str, image_id: int | None = None) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    prefix = f"img_{int(image_id)}" if image_id is not None else "img"
    if name and len(name) <= 120:
        return f"{prefix}_{h}_{name}"
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{h}.jpg"


def _download(url: str, out_path: Path, timeout: float = 25.0) -> bool:
    try:
        r = requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": "ProspectLab-MLFace/1.0"})
        if r.status_code != 200:
            return False
        ctype = (r.headers.get("content-type") or "").lower()
        if "image" not in ctype:
            return False
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Telecharge un lot d'images (URLs distantes) depuis la BDD prod."
    )
    parser.add_argument(
        "--env-file",
        default=".env.prod",
        help="Fichier env a charger (contient DATABASE_URL). Defaut: .env.prod",
    )
    parser.add_argument("--out-dir", default="ml_face/data_raw/prod_sample", help="Dossier de sortie")
    parser.add_argument("--limit", type=int, default=50, help="Nombre d'images a telecharger")
    parser.add_argument("--min-bytes", type=int, default=20_000, help="Taille mini d'une image")
    args = parser.parse_args()

    # Charger l'env prod sans afficher les secrets
    env_file = Path(args.env_file)
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=str(env_file), override=True)
        except Exception:
            pass

    if not (os.environ.get("DATABASE_URL") or "").startswith("postgresql://"):
        raise SystemExit("DATABASE_URL manquant ou non PostgreSQL. Charge la config prod.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    db = DatabaseBase()
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        # On prend des URLs recentes, en limitant le volume.
        db.execute_sql(
            cursor,
            """
            SELECT id, entreprise_id, url
            FROM images
            WHERE url IS NOT NULL AND url != ''
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(args.limit) * 6,),
        )
        rows = cursor.fetchall() or []
    finally:
        conn.close()

    rows_payload: list[dict] = []
    for r in rows:
        if isinstance(r, dict):
            image_id = r.get("id")
            entreprise_id = r.get("entreprise_id")
            url = r.get("url")
        else:
            image_id = r[0]
            entreprise_id = r[1]
            url = r[2]
        if not url:
            continue
        url = str(url).strip()
        if url.startswith("http://") or url.startswith("https://"):
            rows_payload.append(
                {
                    "image_id": image_id,
                    "entreprise_id": entreprise_id,
                    "source_url": url,
                }
            )

    ok = 0
    tried = 0
    downloaded_rows: list[dict] = []
    for item in rows_payload:
        if ok >= int(args.limit):
            break
        tried += 1
        url = str(item["source_url"])
        img_id_raw = item.get("image_id")
        img_id = None if img_id_raw is None else int(img_id_raw)
        name = _safe_filename(url, image_id=img_id)
        out_path = out_dir / name
        if out_path.exists() and out_path.stat().st_size >= int(args.min_bytes):
            downloaded_rows.append(
                {
                    "local_path": str(out_path.resolve()),
                    "source_url": url,
                    "image_id": item["image_id"],
                    "entreprise_id": item["entreprise_id"],
                }
            )
            ok += 1
            continue
        success = _download(url, out_path)
        if not success:
            try:
                if out_path.exists():
                    out_path.unlink()
            except Exception:
                pass
            continue
        if out_path.stat().st_size < int(args.min_bytes):
            try:
                out_path.unlink()
            except Exception:
                pass
            continue
        downloaded_rows.append(
            {
                "local_path": str(out_path.resolve()),
                "source_url": url,
                "image_id": item["image_id"],
                "entreprise_id": item["entreprise_id"],
            }
        )
        ok += 1

    manifest_path = out_dir / "download_manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as f:
        for row in downloaded_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"OK - images telechargees: {ok} (tries={tried}) -> {out_dir}")
    print(f"Manifest -> {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

