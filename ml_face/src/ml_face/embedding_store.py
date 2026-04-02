from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class EmbeddingRow:
    source_path: str
    face_index: int
    crop_path: str | None
    probability: float | None
    box: list[float] | None
    image_width: int | None
    image_height: int | None
    source_url: str | None
    image_id: int | None
    entreprise_id: int | None


def save_embeddings(out_dir: Path, embeddings: np.ndarray, rows: list[EmbeddingRow]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "embeddings.npy", embeddings.astype(np.float32))
    with (out_dir / "metadata.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r.__dict__, ensure_ascii=False) + "\n")


def load_embeddings(dir_path: Path) -> tuple[np.ndarray, list[EmbeddingRow]]:
    emb = np.load(dir_path / "embeddings.npy")
    rows: list[EmbeddingRow] = []
    with (dir_path / "metadata.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            rows.append(
                EmbeddingRow(
                    source_path=str(payload.get("source_path", "")),
                    face_index=int(payload.get("face_index", 0)),
                    crop_path=payload.get("crop_path"),
                    probability=payload.get("probability"),
                    box=payload.get("box"),
                    image_width=payload.get("image_width"),
                    image_height=payload.get("image_height"),
                    source_url=payload.get("source_url"),
                    image_id=payload.get("image_id"),
                    entreprise_id=payload.get("entreprise_id"),
                )
            )
    return emb, rows


def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / (norms + eps)

