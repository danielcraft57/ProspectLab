"""
Embeddings hashing VocalGuard (384d) pour chercher dans intents_inbound.

Meme algo que VocalGuard/backend/voice/intent_embed.py : sans Gemini, les
vecteurs collent a la collection deja indexee.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable, Sequence

EMBED_DIM = 384

_TOKEN_RE = re.compile(r"[a-z0-9àâäéèêëïîôùûüç]+", re.IGNORECASE)


def normalize_intent_text(text: str) -> str:
    """
    Normalise un texte FR pour matching / embedding.

    @param text: Phrase brute
    @returns: Texte minuscule, espaces reduits
    """
    raw = (text or '').strip().lower()
    raw = raw.replace("'", "'").replace("'", "'")
    return re.sub(r'\s+', ' ', raw)


def _tokens(text: str) -> list[str]:
    """Decoupe en tokens alphanumeriques."""
    return _TOKEN_RE.findall(normalize_intent_text(text))


def _ngrams(tokens: Sequence[str], n: int) -> Iterable[str]:
    """Genere des n-grams de tokens."""
    if n <= 1:
        for token in tokens:
            yield token
        return
    for i in range(0, max(0, len(tokens) - n + 1)):
        yield ' '.join(tokens[i : i + n])


def _bucket(feature: str, dim: int) -> int:
    """
    Hash d'une feature vers un index de vecteur.

    @param feature: Chaine a hasher
    @param dim: Dimension cible
    @returns: Index 0..dim-1
    """
    digest = hashlib.sha256(feature.encode('utf-8')).digest()
    return int.from_bytes(digest[:4], 'little') % dim


def embed_text(text: str, *, dim: int = EMBED_DIM) -> list[float]:
    """
    Embedding L2-normalise (unigrammes + bigrammes + 3-grams caracteres).

    @param text: Phrase a encoder
    @param dim: Dimension du vecteur
    @returns: Liste de floats de longueur dim
    """
    vec = [0.0] * dim
    tokens = _tokens(text)
    if not tokens:
        return vec
    features: list[str] = []
    features.extend(_ngrams(tokens, 1))
    features.extend(_ngrams(tokens, 2))
    compact = ''.join(tokens)
    for i in range(0, max(0, len(compact) - 2)):
        features.append(f'c:{compact[i : i + 3]}')
    for feat in features:
        idx = _bucket(feat, dim)
        sign = 1.0 if (hashlib.md5(feat.encode('utf-8')).digest()[0] & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 1e-12:
        return vec
    return [v / norm for v in vec]
