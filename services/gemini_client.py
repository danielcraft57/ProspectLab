"""
Client Gemini (Google AI Studio) avec rotation multi-cles.

Pattern inspire de SocialDesk (gemini-client.mjs) :
- 429 → cle suivante
- 401/403 → cle ignoree jusqu'au redemarrage process
- toutes en quota → pause GEMINI_QUOTA_RETRY_MS puis nouvel essai
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence

import requests

logger = logging.getLogger(__name__)

BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
DEFAULT_TIMEOUT_MS = 60_000

# Cles revoquees (403/401) pour la duree du process
_revoked_keys: set[str] = set()
_preferred_key_index: int = 0


class GeminiClientError(Exception):
    """Erreur d'appel Gemini apres epuisement des cles / retries."""


def get_gemini_api_keys() -> List[str]:
    """
    Collecte les cles Gemini depuis l'environnement.

    Ordre : GEMINI_API_KEYS (CSV) puis GEMINI_API_KEY + GEMINI_API_KEY_2 … _9.

    @returns: Liste de cles uniques non vides
    @raises GeminiClientError: Aucune cle configuree
    """
    keys: List[str] = []

    def _push(value: Optional[str]) -> None:
        key = (value or '').strip()
        if key and key not in keys:
            keys.append(key)

    csv_list = (os.environ.get('GEMINI_API_KEYS') or '').strip()
    if csv_list:
        for part in csv_list.replace(';', ',').replace('\n', ',').split(','):
            _push(part)

    _push(os.environ.get('GEMINI_API_KEY'))
    for i in range(2, 10):
        _push(os.environ.get(f'GEMINI_API_KEY_{i}'))

    if not keys:
        raise GeminiClientError(
            'Cle Gemini manquante — GEMINI_API_KEY ou GEMINI_API_KEYS dans .env'
        )
    return keys


def gemini_config() -> Dict[str, Any]:
    """
    Lit la configuration Gemini depuis l'environnement.

    @returns: Dict model / quota_retry_ms / quota_retry_rounds
    """
    return {
        'model': (
            os.environ.get('GEMINI_DESIGN_MODEL')
            or os.environ.get('GEMINI_MODEL')
            or 'gemini-3.8-flash'
        ),
        'quota_retry_ms': int(os.environ.get('GEMINI_QUOTA_RETRY_MS') or 65_000),
        'quota_retry_rounds': int(os.environ.get('GEMINI_QUOTA_RETRY_ROUNDS') or 1),
    }


def _key_tag(api_key: str, num: int, total: int) -> str:
    """Label court pour les logs (jamais la cle entiere)."""
    tail = api_key[-4:] if len(api_key) >= 4 else '????'
    return f'cle {num}/{total} (…{tail})'


def _parse_gemini_content(raw: str) -> str:
    """
    Extrait le texte de reponse generateContent.

    @param raw: Corps JSON brut
    @returns: Texte concatene des parts
    @raises GeminiClientError: JSON invalide ou contenu vide
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeminiClientError(f'Gemini — reponse JSON invalide: {raw[:200]}') from exc

    parts = (
        (data.get('candidates') or [{}])[0]
        .get('content', {})
        .get('parts')
        or []
    )
    content = ''.join((p.get('text') or '') for p in parts).strip()
    if not content:
        reason = (
            (data.get('candidates') or [{}])[0].get('finishReason')
            or (data.get('promptFeedback') or {}).get('blockReason')
            or 'inconnu'
        )
        raise GeminiClientError(f'Gemini — contenu vide ({reason})')
    return content


def _request_gemini(
    *,
    api_key: str,
    model: str,
    body: Dict[str, Any],
    timeout_ms: int,
) -> tuple[int, str]:
    """
    Execute un appel HTTP generateContent.

    @returns: (status_code, body_text)
    """
    url = f'{BASE_URL}/models/{model}:generateContent'
    resp = requests.post(
        url,
        params={'key': api_key},
        headers={'Content-Type': 'application/json'},
        json=body,
        timeout=max(5, timeout_ms / 1000.0),
    )
    return resp.status_code, resp.text or ''


def _try_all_keys(
    *,
    api_keys: Sequence[str],
    model: str,
    body: Dict[str, Any],
    timeout_ms: int,
) -> Dict[str, Any]:
    """
    Essaie chaque cle active (round-robin) jusqu'a succes ou epuisement.

    @returns: Dict avec content ou error / saw_429 / all_keys_exhausted
    """
    global _preferred_key_index

    active = [k for k in api_keys if k not in _revoked_keys]
    n = len(active)
    if not n:
        return {
            'error': GeminiClientError('Gemini — aucune cle active (toutes revoquees 403 ?)'),
            'saw_429': False,
            'all_keys_exhausted': True,
        }

    last_error: Optional[Exception] = None
    saw_429 = False
    keys_attempted = 0

    for offset in range(n):
        idx = (_preferred_key_index + offset) % n
        api_key = active[idx]
        tag = _key_tag(api_key, offset + 1, len(api_keys))
        keys_attempted += 1

        for attempt in range(3):
            try:
                status, raw = _request_gemini(
                    api_key=api_key,
                    model=model,
                    body=body,
                    timeout_ms=timeout_ms,
                )
            except requests.RequestException as exc:
                last_error = GeminiClientError(f'Gemini reseau: {exc}')
                logger.warning('[Gemini] %s — erreur reseau, cle suivante…', tag)
                break

            if status == 200:
                try:
                    content = _parse_gemini_content(raw)
                except GeminiClientError as exc:
                    last_error = exc
                    break
                _preferred_key_index = idx
                if offset > 0:
                    logger.warning('[Gemini] OK avec %s', tag)
                return {'content': content}

            last_error = GeminiClientError(f'Gemini {status}: {raw[:400]}')

            if status == 429:
                saw_429 = True
                logger.warning('[Gemini] %s — quota (429), cle suivante…', tag)
                break

            if status == 401:
                _revoked_keys.add(api_key)
                logger.warning('[Gemini] %s — 401, cle ignoree…', tag)
                break

            if status == 403:
                # Cle invalide → blacklist. PERMISSION_DENIED projet / feature →
                # on passe a la cle suivante SANS blacklist permanente (souvent intermittent).
                lowered = (raw or '').lower()
                hard_revoke = (
                    'api key not valid' in lowered
                    or 'api_key_invalid' in lowered
                    or 'invalid api key' in lowered
                )
                if hard_revoke:
                    _revoked_keys.add(api_key)
                    logger.warning('[Gemini] %s — 403 cle invalide, ignoree…', tag)
                else:
                    logger.warning('[Gemini] %s — 403 (pas de blacklist): %s', tag, raw[:180])
                break

            if status >= 500 and attempt < 2:
                time.sleep(4 * (attempt + 1))
                continue

            logger.warning('[Gemini] %s — erreur %s, cle suivante…', tag, status)
            break

    return {
        'error': last_error or GeminiClientError('Gemini — echec inconnu'),
        'saw_429': saw_429,
        'all_keys_exhausted': keys_attempted >= n,
    }


def gemini_generate_content(
    *,
    parts: List[Dict[str, Any]],
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    json_mode: bool = False,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    quota_retry_rounds: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Appel Gemini generateContent avec rotation de cles.

    @param parts: Parts utilisateur (text et/ou inline_data)
    @param system_instruction: Instruction systeme optionnelle
    @param model: Modele (defaut GEMINI_DESIGN_MODEL / GEMINI_MODEL)
    @param max_tokens: Limite de tokens de sortie
    @param temperature: Temperature de generation
    @param json_mode: Force responseMimeType application/json
    @param timeout_ms: Timeout HTTP en ms
    @param quota_retry_rounds: Tours de pause apres epuisement 429
    @param tools: Outils Gemini optionnels (ex: [{"url_context": {}}])
    @returns: Texte de reponse
    @raises GeminiClientError: Echec apres retries
    """
    cfg = gemini_config()
    resolved_model = model or cfg['model']
    rounds = (
        quota_retry_rounds
        if quota_retry_rounds is not None
        else cfg['quota_retry_rounds']
    )
    api_keys = get_gemini_api_keys()

    # thinkingLevel low : gemini-3.x flash peut sinon "réfléchir" 30-60s pour un JSON simple
    body: Dict[str, Any] = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {
            'temperature': temperature,
            'maxOutputTokens': max_tokens,
            'thinkingConfig': {'thinkingLevel': 'low'},
        },
    }
    if system_instruction:
        body['systemInstruction'] = {'parts': [{'text': system_instruction}]}
    if json_mode:
        body['generationConfig']['responseMimeType'] = 'application/json'
    if tools:
        body['tools'] = tools

    last_error: Optional[Exception] = None
    for round_idx in range(rounds + 1):
        result = _try_all_keys(
            api_keys=api_keys,
            model=resolved_model,
            body=body,
            timeout_ms=timeout_ms,
        )
        if result.get('content'):
            return result['content']

        last_error = result.get('error')
        can_wait = (
            result.get('saw_429')
            and result.get('all_keys_exhausted')
            and round_idx < rounds
            and cfg['quota_retry_ms'] > 0
        )
        if not can_wait:
            break
        secs = round(cfg['quota_retry_ms'] / 1000)
        logger.warning(
            '[Gemini] pause %ss puis nouvel essai sur les %s cles…',
            secs,
            len(api_keys),
        )
        time.sleep(cfg['quota_retry_ms'] / 1000.0)

    hint = (
        f' ({len(api_keys)} cles configurees)'
        if len(api_keys) > 1
        else ''
    )
    raise GeminiClientError(f'{last_error}{hint}' if last_error else f'Gemini echec{hint}')


def gemini_vision_json(
    *,
    prompt: str,
    image_bytes: bytes,
    mime_type: str = 'image/webp',
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyse une image via Gemini Vision et parse la reponse JSON.

    @param prompt: Consigne utilisateur
    @param image_bytes: Contenu binaire de l'image
    @param mime_type: MIME (image/webp, image/jpeg, …)
    @param system_instruction: Instruction systeme
    @param model: Modele optionnel
    @returns: Dict JSON parse
    @raises GeminiClientError: Echec API ou JSON invalide
    """
    return gemini_vision_multi_json(
        prompt=prompt,
        images=[{'bytes': image_bytes, 'mime_type': mime_type}],
        system_instruction=system_instruction,
        model=model,
        max_tokens=2048,
    )


def gemini_vision_multi_json(
    *,
    prompt: str,
    images: List[Dict[str, Any]],
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Analyse multimodale (plusieurs images + texte) via Gemini, reponse JSON.

    @param prompt: Consigne utilisateur
    @param images: Liste de dicts {bytes|image_bytes, mime_type?}
    @param system_instruction: Instruction systeme
    @param model: Modele optionnel
    @param max_tokens: Limite de sortie
    @param timeout_ms: Timeout HTTP en ms
    @param tools: Outils Gemini optionnels (ex. url_context)
    @returns: Dict JSON parse
    @raises GeminiClientError: Echec API ou JSON invalide
    """
    parts: List[Dict[str, Any]] = [{'text': prompt}]
    for img in images or []:
        raw = img.get('bytes') or img.get('image_bytes')
        if not raw:
            continue
        mime = (img.get('mime_type') or img.get('mime') or 'image/webp').strip()
        b64 = base64.b64encode(raw).decode('ascii')
        parts.append({
            'inline_data': {
                'mime_type': mime,
                'data': b64,
            }
        })
    raw = gemini_generate_content(
        parts=parts,
        system_instruction=system_instruction,
        model=model,
        json_mode=True,
        temperature=0.25,
        max_tokens=max_tokens,
        timeout_ms=timeout_ms,
        tools=tools,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find('{')
        end = raw.rfind('}')
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise GeminiClientError(f'Gemini Vision multi — JSON invalide: {raw[:300]}')
