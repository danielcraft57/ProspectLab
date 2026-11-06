"""
Heuristiques de fil conversationnel (sandbox Qdrant sans API persona).

Evite les boucles du meme intent / la meme phrase quand le client repond court.
"""

from __future__ import annotations

import re
from typing import Any

_NEG_RE = re.compile(
    r'\b('
    r'non|nan|nop|pas|aucun|aucune|aucunes|aucuns|jamais|personne|'
    r'vitrine|inutile|dort|dormir|marche\s*pas|'
    r'pas\s*vraiment|pas\s*du\s*tout|'
    r'zero|0|rien'
    r')\b',
    re.IGNORECASE,
)

_CONTINUE_RE = re.compile(
    r'\b(continuez|continue|vas\s*y|allez\s*y|ok|daccord|d\'accord|oui)\b',
    re.IGNORECASE,
)

_ACK_AFTER_OBJECTION_RE = re.compile(
    r'\b(compris|entendu|je\s*vois|daccord|ok)\b',
    re.IGNORECASE,
)

# Apres ce tag bot, si le client repond negativement -> intent de pivot.
_AFTER_QUALIFY_NEGATIVE: dict[str, str] = {
    'out_qualify_website': 'out_objection_has_site',
}

# Apres ouverture, le client accepte de continuer.
_AFTER_PRESENTATION_CONTINUE: dict[str, str] = {
    'out_presentation': 'out_go_ahead',
    'opening': 'out_go_ahead',
}

# Tag deja vu deux fois de suite : forcer un voisin si possible.
_REPEAT_TAG_PENALTY = 0.35


def _norm(text: str) -> str:
    """Normalise pour comparer deux reponses bot."""
    t = (text or '').strip().lower()
    t = re.sub(r'\s+', ' ', t)
    return t


def user_sentiment_hint(text: str) -> str:
    """
    Indice grossier sur le dernier message client.

    @param text: Message user
    @returns: negative | continue | neutral
    """
    q = (text or '').strip()
    if not q:
        return 'neutral'
    if _NEG_RE.search(q) and not _CONTINUE_RE.search(q):
        return 'negative'
    if _CONTINUE_RE.search(q) and len(q) < 40:
        return 'continue'
    return 'neutral'


def dialogue_override_tag(
    user_text: str,
    recent_tags: list[str] | None,
) -> str | None:
    """
    Choisit un intent metier avant Qdrant si le contexte est clair.

    @param user_text: Message courant
    @param recent_tags: Tags bot precedents
    @returns: Tag force ou None
    """
    tags = [str(t).strip() for t in (recent_tags or []) if str(t).strip()]
    if not tags:
        return None
    last = tags[-1]
    hint = user_sentiment_hint(user_text)
    if hint == 'negative':
        pivot = _AFTER_QUALIFY_NEGATIVE.get(last)
        if pivot:
            return pivot
    if hint == 'continue' or (
        hint == 'neutral' and _CONTINUE_RE.search(user_text or '') and len((user_text or '').strip()) < 50
    ):
        pivot = _AFTER_PRESENTATION_CONTINUE.get(last)
        if pivot:
            return pivot
    return None


def penalize_repeated_intents(
    preds: list[dict[str, Any]],
    recent_tags: list[str] | None,
) -> list[dict[str, Any]]:
    """
    Reduit le score des intents deja joues recemment.

    @param preds: Top predictions brutes
    @param recent_tags: Historique tags
    @returns: Predictions reordonnees
    """
    tags = [str(t).strip() for t in (recent_tags or []) if str(t).strip()]
    if not tags or not preds:
        return preds
    recent_set = set(tags[-3:])
    last = tags[-1]
    adjusted: list[dict[str, Any]] = []
    for row in preds:
        item = dict(row)
        tag = str(item.get('tag') or '')
        raw = float(item.get('raw_score') or item.get('score') or 0)
        if tag == last:
            raw *= _REPEAT_TAG_PENALTY
        elif tag in recent_set:
            raw *= 0.55
        item['raw_score'] = raw
        item['score'] = raw
        adjusted.append(item)
    adjusted.sort(key=lambda r: float(r.get('raw_score') or 0), reverse=True)
    total = sum(float(r.get('raw_score') or 0) for r in adjusted) or 1.0
    for row in adjusted:
        row['score'] = round(float(row.get('raw_score') or 0) / total, 4)
    return adjusted


def _reply_from_catalog_intent(intent: dict[str, Any] | None) -> str:
    """Premiere reponse non vide d'un intent catalogue."""
    if not intent:
        return ''
    responses = intent.get('responses') or []
    for row in responses:
        if isinstance(row, str):
            text = row.strip()
        elif isinstance(row, dict):
            text = str(row.get('text') or '').strip()
        else:
            text = ''
        if text:
            return text
    return ''


def pick_intent_from_predictions(
    preds: list[dict[str, Any]],
    *,
    forced_tag: str | None,
    recent_replies: list[str] | None,
    catalog: dict[str, dict[str, Any]],
) -> tuple[str | None, float, list[dict[str, Any]]]:
    """
    Retient un tag en evitant une reponse identique au dernier bot.

    @param preds: Predictions (deja penalisees)
    @param forced_tag: Override dialogue
    @param recent_replies: Dernieres reponses bot
    @param catalog: Intents VocalGuard
    @returns: tag, score, preds eventuellement reordonnes
    """
    if forced_tag:
        for row in preds:
            if str(row.get('tag') or '') == forced_tag:
                return forced_tag, float(row.get('score') or 0.5), preds
        if forced_tag in catalog:
            return forced_tag, 0.5, preds

    last_reply = _norm((recent_replies or [])[-1] if recent_replies else '')
    ordered = list(preds or [])
    for row in ordered:
        tag = str(row.get('tag') or '').strip()
        if not tag:
            continue
        intent = catalog.get(tag)
        if not intent:
            continue
        candidate = _reply_from_catalog_intent(intent)
        if last_reply and _norm(candidate) == last_reply:
            continue
        return tag, float(row.get('score') or 0), ordered
    if ordered:
        tag = str(ordered[0].get('tag') or '') or None
        return tag, float(ordered[0].get('score') or 0), ordered
    return None, 0.0, ordered


def template_pick_index(
    tag: str | None,
    recent_tags: list[str] | None,
    user_text: str,
) -> int:
    """
    Choisit quelle variante INTENT_TEMPLATES utiliser (pas toujours la #1).

    @param tag: Intent retenu
    @param recent_tags: Historique
    @param user_text: Message client
    @returns: Index 0..n
    """
    key = str(tag or '').strip()
    if not key:
        return 0
    same = sum(1 for t in (recent_tags or []) if str(t).strip() == key)
    hint = user_sentiment_hint(user_text)
    if hint == 'continue':
        return min(max(same, 1), 2)
    if hint == 'negative':
        return min(same + 1, 2)
    return min(same, 2)


def build_qdrant_query_text(
    user_text: str,
    *,
    recent_user_texts: list[str] | None = None,
    recent_replies: list[str] | None = None,
    recent_tags: list[str] | None = None,
) -> str:
    """
    Texte embedde : message + mini contexte (pas seulement le dernier tag).

    @param user_text: Tour courant
    @param recent_user_texts: Historique client
    @param recent_replies: Historique bot
    @param recent_tags: Tags precedents
    @returns: Chaine pour embedding
    """
    parts = [(user_text or '').strip()]
    users = [str(t).strip() for t in (recent_user_texts or []) if str(t).strip()]
    if len(users) >= 2:
        parts.append(f'client avant: {users[-2]}')
    bots = [str(t).strip() for t in (recent_replies or []) if str(t).strip()]
    if bots:
        snippet = bots[-1][:160]
        parts.append(f'bot avant: {snippet}')
    tags = [str(t).strip() for t in (recent_tags or []) if str(t).strip()]
    if tags:
        parts.append(f'intent: {tags[-1]}')
    return '\n'.join(p for p in parts if p)
