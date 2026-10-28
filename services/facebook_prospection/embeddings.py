"""
Embeddings Messenger : hashing VocalGuard (384d), compatible intents_inbound.
"""

from __future__ import annotations

from services.facebook_prospection.vocalguard_embed import EMBED_DIM, embed_text as vocalguard_embed_text


def embed_text(text: str, dims: int | None = None) -> list[float]:
    """
    Vectorise un texte comme VocalGuard (pas Gemini).

    @param text: Texte entrant ou requete
    @param dims: Dimension (defaut 384)
    @returns: Vecteur float
    """
    size = int(dims or EMBED_DIM)
    return vocalguard_embed_text(text, dim=size)
