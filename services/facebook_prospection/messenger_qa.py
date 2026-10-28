"""
Question / reponse Messenger : KB VocalGuard (API tchatche + Qdrant intents_inbound).
"""

from __future__ import annotations

import logging
from typing import Any

from services.facebook_prospection.qdrant import FacebookProspectionQdrant
from config import VOCALGUARD_KB_PROFILE
from services.facebook_prospection.reply_vars import (
    INTENT_TEMPLATES,
    apply_vars_to_suggestions,
    load_entreprise_reply_vars,
    merge_template_suggestions,
    public_var_catalog,
    render_reply_template,
)
from services.facebook_prospection.vocalguard_client import chat_turn, list_intents, vocalguard_configured
from services.facebook_prospection.vocalguard_embed import EMBED_DIM, embed_text

logger = logging.getLogger(__name__)

_INTENTS_CACHE: dict[str, Any] = {'items': [], 'ts': 0.0}
_INTENTS_TTL_SEC = 120.0


def _catalog(profile: str | None = None) -> dict[str, dict[str, Any]]:
    """
    Index tag -> intent (reponses VocalGuard), cache court.

    @param profile: Profil KB
    @returns: Dict tag -> intent
    """
    import time

    now = time.time()
    if now - float(_INTENTS_CACHE.get('ts') or 0) < _INTENTS_TTL_SEC and _INTENTS_CACHE.get('items'):
        items = _INTENTS_CACHE['items']
    else:
        items = list_intents(profile=profile or VOCALGUARD_KB_PROFILE)
        _INTENTS_CACHE['items'] = items
        _INTENTS_CACHE['ts'] = now
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        tag = str(item.get('tag') or '').strip()
        if tag:
            out[tag] = item
    return out


def _reply_from_intent(intent: dict[str, Any] | None) -> str:
    """Premiere reponse catalogue d'un intent."""
    if not intent:
        return ''
    responses = intent.get('responses') or []
    texts: list[str] = []
    for row in responses:
        if isinstance(row, str):
            texts.append(row.strip())
        elif isinstance(row, dict):
            texts.append(str(row.get('text') or '').strip())
    for text in texts:
        if text:
            return text
    return ''


def search_intents_qdrant(
    text: str,
    *,
    top_k: int = 8,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """
    Predict local : hashing VocalGuard + collection Qdrant.

    @param text: Message user
    @param top_k: Nombre d'intents
    @param profile: inbound | outbound_commercial
    @returns: Liste {tag, score, ref_type}
    """
    query = (text or '').strip()
    if not query:
        return []
    prof = profile or VOCALGUARD_KB_PROFILE
    store = FacebookProspectionQdrant(profile=prof)
    if not store.enabled():
        return []
    vector = embed_text(query, dim=store.dims or EMBED_DIM)
    hits = store.search(vector, limit=max(top_k * 4, 16), min_score=0.05, profile=prof)
    scored: dict[str, float] = {}
    meta: dict[str, str] = {}
    for hit in hits:
        payload = hit.get('payload') or {}
        tag = str(payload.get('intent_tag') or '').strip()
        if not tag:
            continue
        ref_type = str(payload.get('ref_type') or '')
        weight = 1.0 if ref_type == 'pattern' else 0.35
        val = float(hit.get('score') or 0.0) * weight
        if val >= scored.get(tag, 0.0):
            scored[tag] = val
            meta[tag] = ref_type
    items = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(s for _, s in items) or 1.0
    out: list[dict[str, Any]] = []
    for tag, score in items[: max(1, top_k)]:
        out.append(
            {
                'tag': tag,
                'score': round(float(score / total), 4),
                'raw_score': round(float(score), 4),
                'ref_type': meta.get(tag),
            }
        )
    return out


def answer_user_turn(
    text: str,
    *,
    contact_name: str | None = None,
    recent_replies: list[str] | None = None,
    recent_tags: list[str] | None = None,
    recent_user_texts: list[str] | None = None,
    top_k: int = 8,
    profile: str | None = None,
    entreprise_id: int | None = None,
) -> dict[str, Any]:
    """
    Un tour Q/R : VocalGuard tchatche si possible, sinon Qdrant local.

    @param text: Message utilisateur
    @param contact_name: Nom affiche (contexte)
    @param recent_replies: Historique bot
    @param recent_tags: Historique tags
    @param recent_user_texts: Historique user
    @param top_k: Voisins
    @param profile: Profil KB
    @param entreprise_id: Fiche CRM pour {{ville}} / {{entreprise}} etc.
    @returns: reply, tag, score, source, suggestions, top_predictions
    """
    vars_map, fiche = load_entreprise_reply_vars(
        entreprise_id,
        contact_name=contact_name,
    )
    prof = profile or VOCALGUARD_KB_PROFILE or 'outbound_commercial'
    query = (text or '').strip()
    empty = {
        'reply': '',
        'tag': None,
        'score': 0.0,
        'source': 'empty',
        'engine': 'empty',
        'suggestions': [],
        'top_predictions': [],
        'persona_reason': None,
        'mood': None,
    }
    if not query:
        return empty

    vg = None
    if vocalguard_configured():
        vg = chat_turn(
            query,
            top_k=top_k,
            recent_replies=recent_replies,
            recent_tags=recent_tags,
            recent_user_texts=recent_user_texts,
            profile=prof,
        )

    vg_ok = bool(vg and vg.get('tag') and float(vg.get('score') or 0) > 0)
    if vg_ok:
        reply = str(vg.get('reply') or '').strip()
        tag = vg.get('tag')
        score = float(vg.get('score') or 0.0)
        preds = vg.get('top_predictions') or vg.get('raw_predictions') or []
        suggestions = _suggestions_from_reply(reply, tag, score, preds, profile=prof)
        return _personalize_turn(
            {
                'reply': reply,
                'tag': tag,
                'score': round(score, 4),
                'source': 'kb_api',
                'engine': vg.get('source') or 'kb_api',
                'path': vg.get('_path'),
                'suggestions': suggestions,
                'top_predictions': preds,
                'persona_reason': vg.get('persona_reason'),
                'mood': vg.get('mood'),
                'action': vg.get('action'),
            },
            vars_map,
            fiche,
        )

    preds = search_intents_qdrant(query, top_k=top_k, profile=prof)
    catalog = _catalog(prof)
    tag = preds[0]['tag'] if preds else None
    score = float(preds[0]['score']) if preds else 0.0
    intent = catalog.get(str(tag)) if tag else None
    reply = _reply_from_intent(intent)
    if not reply and tag:
        reply = (
            f"Intent detecte : {tag} "
            f"(score {score:.2f}). Active l'API tchatche interne dans le .env pour les phrases du catalogue."
        )
    if not reply:
        reply = (
            "Aucun intent proche dans la collection Qdrant. "
            "Verifie QDRANT_URL, la collection intents_outbound_commercial et la sync catalogue."
        )
    suggestions = _suggestions_from_reply(reply, tag, score, preds, profile=prof, catalog=catalog)
    return _personalize_turn(
        {
            'reply': reply,
            'tag': tag,
            'score': round(score, 4),
            'source': 'qdrant',
            'engine': 'qdrant',
            'suggestions': suggestions,
            'top_predictions': preds,
            'persona_reason': None,
            'mood': None,
            'action': (intent or {}).get('action') if intent else None,
        },
        vars_map,
        fiche,
    )


def _personalize_turn(
    turn: dict[str, Any],
    vars_map: dict[str, str],
    fiche: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Injecte les variables entreprise dans reply + suggestions.

    @param turn: Tour Q/R brut
    @param vars_map: Placeholders
    @param fiche: Fiche CRM ou None
    @returns: Tour enrichi
    """
    turn['reply'] = render_reply_template(str(turn.get('reply') or ''), vars_map)
    turn['suggestions'] = apply_vars_to_suggestions(list(turn.get('suggestions') or []), vars_map)
    reply, chips = merge_template_suggestions(
        turn.get('tag'),
        vars_map,
        list(turn.get('suggestions') or []),
        score=float(turn.get('score') or 0),
    )
    if reply:
        turn['reply'] = reply
        turn['suggestions'] = chips
    turn['vars'] = vars_map
    turn['templates'] = list(INTENT_TEMPLATES.get(str(turn.get('tag') or ''), []))
    turn['entreprise_id'] = int(fiche['id']) if fiche and fiche.get('id') is not None else None
    turn['entreprise_nom'] = (fiche or {}).get('nom') if fiche else None
    return turn


def _suggestions_from_reply(
    reply: str,
    tag: Any,
    score: float,
    preds: list[dict[str, Any]],
    *,
    profile: str,
    catalog: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Transforme un tour Q/R en chips Messenger.

    @param reply: Phrase principale
    @param tag: Intent retenu
    @param score: Score
    @param preds: Top predictions
    @param profile: Profil KB
    @param catalog: Intents VocalGuard
    @returns: Liste suggestions
    """
    cat = catalog if catalog is not None else _catalog(profile)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def _push(text: str, kind: str, intent_id: Any, label: Any, sc: float) -> None:
        clean = (text or '').strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        out.append(
            {
                'text': clean[:2000],
                'score': round(float(sc), 4),
                'kind': kind,
                'intent_id': intent_id,
                'label': label or intent_id,
            }
        )

    _push(reply, 'kb_reply', tag, tag, score)
    for pred in preds[:5]:
        ptag = pred.get('tag')
        if not ptag or ptag == tag:
            continue
        intent = cat.get(str(ptag))
        alt = _reply_from_intent(intent)
        if alt:
            _push(alt, 'kb_alt', ptag, ptag, float(pred.get('score') or 0))
    return out


def kb_status() -> dict[str, Any]:
    """
    Etat Qdrant + API tchatche optionnelle.

    @returns: Snapshot pour l'UI tchatche
    """
    store = FacebookProspectionQdrant()
    info = store.collection_info()
    chat_api = vocalguard_configured()
    return {
        'qdrant': info,
        'kb_chat_configured': chat_api,
        'embed': 'hashing_384',
        'dims': store.dims,
        'collection': store.collection,
        'profile': store.profile,
        'reply_vars': public_var_catalog(),
        'template_tags': list(INTENT_TEMPLATES.keys()),
    }
