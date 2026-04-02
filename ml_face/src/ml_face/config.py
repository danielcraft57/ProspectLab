from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class FaceConfig:
    detector: str
    embedder: str


@dataclass(frozen=True)
class IndexingConfig:
    allowed_extensions: tuple[str, ...]


@dataclass(frozen=True)
class PathsConfig:
    data_raw: Path
    data: Path
    artifacts: Path
    runs: Path


@dataclass(frozen=True)
class AppConfig:
    project_name: str
    paths: PathsConfig
    indexing: IndexingConfig
    faces: FaceConfig


def _as_path(p: str) -> Path:
    return Path(p)


def load_config(path: Path) -> AppConfig:
    payload: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))

    project_name = str(payload.get("project", {}).get("name", "ml_face"))

    paths_raw = payload.get("paths", {}) or {}
    paths = PathsConfig(
        data_raw=_as_path(str(paths_raw.get("data_raw", "ml_face/data_raw"))),
        data=_as_path(str(paths_raw.get("data", "ml_face/data"))),
        artifacts=_as_path(str(paths_raw.get("artifacts", "ml_face/artifacts"))),
        runs=_as_path(str(paths_raw.get("runs", "ml_face/runs"))),
    )

    indexing_raw = payload.get("indexing", {}) or {}
    allowed = indexing_raw.get("allowed_extensions", [".jpg", ".jpeg", ".png", ".webp"])
    indexing = IndexingConfig(allowed_extensions=tuple(str(x).lower() for x in allowed))

    faces_raw = payload.get("faces", {}) or {}
    faces = FaceConfig(
        detector=str(faces_raw.get("detector", "facenet_pytorch_mtcnn")),
        embedder=str(faces_raw.get("embedder", "facenet_pytorch_inception_resnet_v1")),
    )

    return AppConfig(project_name=project_name, paths=paths, indexing=indexing, faces=faces)

