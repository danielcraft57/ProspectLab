"""
Propositions de reponses Messenger via la KB VocalGuard (Qdrant + tchatche).
"""

from __future__ import annotations

from typing import Any

from services.facebook_prospection.messenger_qa import answer_user_turn


def build_reply_suggestions(
    inbound_text: str,
    *,
    contact_name: str | None = None,
    entreprise_id: int | None = None,
    limit: int = 5,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Cherche des reponses types proches du dernier message entrant.

    @param inbound_text: Message du contact
    @param contact_name: Nom affiche
    @param entreprise_id: Fiche CRM pour personnaliser {{ville}} etc.
    @param limit: Nombre max de propositions
    @param min_score: Ignore (seuil gere cote VocalGuard / Qdrant)
    @returns: Liste { text, score, kind, intent_id?, label? }
    """
    del min_score
    turn = answer_user_turn(
        inbound_text,
        contact_name=contact_name,
        entreprise_id=entreprise_id,
        top_k=max(limit, 5),
    )
    suggestions = list(turn.get('suggestions') or [])
    return suggestions[:limit]
