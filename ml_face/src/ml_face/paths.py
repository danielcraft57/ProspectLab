from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def data_raw(self) -> Path:
        return self.root / "data_raw"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def runs(self) -> Path:
        return self.root / "runs"


def get_project_paths(repo_root: Path) -> ProjectPaths:
    return ProjectPaths(root=repo_root / "ml_face")

