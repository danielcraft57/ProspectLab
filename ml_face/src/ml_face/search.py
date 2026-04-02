from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .embedding_store import l2_normalize


@dataclass(frozen=True)
class SearchHit:
    index: int
    score: float


def topk_cosine(query: np.ndarray, embeddings: np.ndarray, k: int = 10) -> list[SearchHit]:
    """
    embeddings: shape (N, D), deja L2-normalise idealement
    query: shape (D,) ou (1, D)
    """
    if query.ndim == 2:
        query = query[0]
    q = query.astype(np.float32, copy=False).reshape(1, -1)
    q = l2_normalize(q)

    # cosine similarity == dot product apres normalisation
    scores = (embeddings @ q.T).reshape(-1)
    if k <= 0:
        k = 10
    k = min(int(k), int(scores.shape[0]))
    idx = np.argpartition(-scores, kth=k - 1)[:k]
    idx = idx[np.argsort(-scores[idx])]
    return [SearchHit(index=int(i), score=float(scores[int(i)])) for i in idx]

