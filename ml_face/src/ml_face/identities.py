from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class IdentityCluster:
    id: int
    members: list[int]  # indices dans embeddings/metadata


def cluster_by_threshold(
    embeddings: np.ndarray,
    threshold: float = 0.75,
    min_cluster_size: int = 2,
) -> list[IdentityCluster]:
    """
    Clustering simple et robuste pour demarrer:
    - on part d'un point non assigne
    - on cree un cluster en ajoutant tout ce qui a une similarite >= threshold avec le centroid courant
    - on met a jour le centroid (moyenne puis normalisation)

    embeddings doit etre L2-normalise (cosine = dot).
    """
    if embeddings.ndim != 2:
        raise ValueError("embeddings doit etre un tableau 2D (N, D)")
    n = int(embeddings.shape[0])
    if n == 0:
        return []

    assigned = np.zeros(n, dtype=bool)
    clusters: list[IdentityCluster] = []
    cluster_id = 0

    def _norm(v: np.ndarray) -> np.ndarray:
        denom = np.linalg.norm(v) + 1e-12
        return v / denom

    for i in range(n):
        if assigned[i]:
            continue

        members: list[int] = [i]
        assigned[i] = True
        centroid = embeddings[i].copy()

        changed = True
        while changed:
            changed = False
            # scores: cosine similarity vers le centroid
            scores = embeddings @ centroid.reshape(-1, 1)
            scores = scores.reshape(-1)
            candidates = np.where((scores >= threshold) & (~assigned))[0]
            if candidates.size == 0:
                continue
            for j in candidates.tolist():
                assigned[j] = True
                members.append(int(j))
                changed = True
            centroid = _norm(np.mean(embeddings[members], axis=0))

        if len(members) >= int(min_cluster_size):
            clusters.append(IdentityCluster(id=cluster_id, members=sorted(members)))
            cluster_id += 1

    # Option: trier par taille decroissante
    clusters.sort(key=lambda c: len(c.members), reverse=True)
    # Reindex pour avoir des ids propres apres tri
    return [IdentityCluster(id=k, members=c.members) for k, c in enumerate(clusters)]


def pick_representatives(
    embeddings: np.ndarray,
    members: list[int],
    k: int = 12,
) -> list[int]:
    """
    Choisit des representants: les plus proches du centroid (donc plus "centraux").
    """
    if not members:
        return []
    m = np.array(members, dtype=int)
    centroid = np.mean(embeddings[m], axis=0)
    centroid = centroid / (np.linalg.norm(centroid) + 1e-12)
    scores = (embeddings[m] @ centroid.reshape(-1, 1)).reshape(-1)
    order = np.argsort(-scores)
    k = min(int(k), int(order.shape[0]))
    return [int(m[int(order[t])]) for t in range(k)]

