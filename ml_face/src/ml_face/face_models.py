from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch


@dataclass(frozen=True)
class FaceModels:
    detector: Any
    embedder: torch.nn.Module
    device: torch.device


def build_facenet_pytorch_models(device: torch.device) -> FaceModels:
    """
    Construit un detecteur MTCNN et un embedder InceptionResnetV1.
    On garde ca dans un module a part pour pouvoir changer plus tard (insightface, etc.).
    """
    from facenet_pytorch import InceptionResnetV1, MTCNN

    detector = MTCNN(keep_all=True, device=device)
    embedder = InceptionResnetV1(pretrained="vggface2").eval().to(device)
    return FaceModels(detector=detector, embedder=embedder, device=device)


def pick_device(prefer_cuda: bool = True) -> torch.device:
    if prefer_cuda and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")

