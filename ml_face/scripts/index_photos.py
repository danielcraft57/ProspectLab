from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_photos(root: Path, exts: set[str]) -> list[Path]:
    paths: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in exts:
            paths.append(p)
    return paths


def _load_download_manifest(input_dir: Path) -> dict[str, dict]:
    manifest_path = input_dir / "download_manifest.jsonl"
    if not manifest_path.exists():
        return {}
    out: dict[str, dict] = {}
    with manifest_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            local_path = str(Path(str(p.get("local_path", ""))).resolve())
            if not local_path:
                continue
            out[local_path] = {
                "source_url": p.get("source_url"),
                "image_id": p.get("image_id"),
                "entreprise_id": p.get("entreprise_id"),
            }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Indexe les photos (chemins) en JSON.")
    parser.add_argument("--input", required=True, help="Dossier racine des photos")
    parser.add_argument("--output", default="ml_face/data/photos_index.json", help="Chemin de sortie JSON")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    photos = iter_photos(input_dir, DEFAULT_EXTS)
    meta_by_path = _load_download_manifest(input_dir)
    files_payload: list[dict] = []
    for p in photos:
        key = str(p.resolve())
        item = {"path": str(p)}
        if key in meta_by_path:
            item.update(meta_by_path[key])
        files_payload.append(item)
    payload = {
        "input_root": str(input_dir),
        "count": len(photos),
        "files": files_payload,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK - {len(photos)} fichiers indexés -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

