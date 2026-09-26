"""
Analyse design UX/UI d'un screenshot (Gemini Vision + fallback heuristique).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DESIGN_SYSTEM_PROMPT = (
    "Tu es un expert UX/UI B2B. Analyse le screenshot d'un site vitrine. "
    "Reponds uniquement en JSON valide avec les cles: "
    "score (0-100, plus bas = design plus faible/obsolète), "
    "positives (liste de 2 a 5 points forts courts en francais), "
    "negatives (liste de 2 a 5 points faibles courts en francais), "
    "refonte_priority (faible|moyenne|elevee), "
    "pitch (1 phrase commerciale courte en francais pour motiver une refonte)."
)


def _mime_for_path(path: Path) -> str:
    """Retourne le MIME estime selon l'extension."""
    ext = path.suffix.lower()
    if ext in ('.jpg', '.jpeg'):
        return 'image/jpeg'
    if ext == '.png':
        return 'image/png'
    return 'image/webp'


def heuristic_design_review(
    *,
    site_age_score: Optional[int] = None,
    http_last_modified: Optional[str] = None,
    tags: Optional[List[str]] = None,
    page_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fallback local si Gemini est indisponible.

    @param site_age_score: Score d'age du site (0+)
    @param http_last_modified: Header Last-Modified
    @param tags: Tags entreprise
    @param page_url: URL de la page capturee
    @returns: Dict design_review normalise
    """
    score = 62
    positives: List[str] = []
    negatives: List[str] = ['Analyse Vision Gemini indisponible — revue visuelle incomplete']
    refonte = 'moyenne'

    age = None
    try:
        age = int(site_age_score) if site_age_score is not None else None
    except (TypeError, ValueError):
        age = None

    if age is not None:
        if age >= 4:
            score = 28
            negatives.append('Signaux d\'age forts (copyright / stack ancienne)')
            refonte = 'elevee'
        elif age >= 2:
            score = 42
            negatives.append('Site potentiellement date')
            refonte = 'elevee'
        elif age >= 1:
            score = 55
            negatives.append('Quelques indices de modernisation a predire')
        else:
            positives.append('Peu de signaux d\'obsolescence detectes')
            score = 72
            refonte = 'faible'

    if http_last_modified:
        year = None
        for token in str(http_last_modified).replace('-', ' ').split():
            if token.isdigit() and len(token) == 4:
                year = int(token)
                break
        if year and year <= 2018:
            score = min(score, 35)
            negatives.append(f'Last-Modified ancien ({year})')
            refonte = 'elevee'

    tag_list = tags or []
    if any('fort_potentiel_refonte' == str(t) for t in tag_list):
        score = min(score, 38)
        negatives.append('Tag fort potentiel refonte deja present')
        refonte = 'elevee'

    if page_url and str(page_url).startswith('http://'):
        score = min(score, 45)
        negatives.append('Site servi en HTTP sans HTTPS')

    if not negatives:
        negatives.append('Analyse visuelle Gemini indisponible — estimation heuristique')

    pitch = (
        'Une modernisation UX/UI renforcerait credibilite et conversion.'
        if refonte in ('moyenne', 'elevee')
        else 'Le design semble correct ; une revue fine reste possible.'
    )
    return {
        'score': max(0, min(100, int(score))),
        'positives': positives[:5],
        'negatives': negatives[:5],
        'refonte_priority': refonte,
        'pitch': pitch,
        'source': 'heuristic',
    }


def _normalize_review(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Normalise un dict design_review (Gemini ou heuristique)."""
    score = raw.get('score', raw.get('design_score', 50))
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 50
    score = max(0, min(100, score))

    def _as_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()][:8]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    refonte = str(raw.get('refonte_priority') or raw.get('priority') or 'moyenne').lower()
    if refonte not in ('faible', 'moyenne', 'elevee'):
        if score < 40:
            refonte = 'elevee'
        elif score < 60:
            refonte = 'moyenne'
        else:
            refonte = 'faible'

    return {
        'score': score,
        'positives': _as_list(raw.get('positives') or raw.get('points_forts')),
        'negatives': _as_list(raw.get('negatives') or raw.get('points_faibles')),
        'refonte_priority': refonte,
        'pitch': str(raw.get('pitch') or raw.get('summary') or '').strip()[:500],
        'source': source,
    }


def analyze_screenshot_design(
    *,
    image_path: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
    page_url: Optional[str] = None,
    site_age_score: Optional[int] = None,
    site_indicators: Optional[str] = None,
    http_last_modified: Optional[str] = None,
    tags: Optional[List[str]] = None,
    force_heuristic: bool = False,
) -> Dict[str, Any]:
    """
    Analyse le design d'un screenshot (Gemini Vision, sinon heuristiques).

    @param image_path: Chemin fichier image
    @param image_bytes: Contenu binaire alternatif
    @param mime_type: MIME de l'image
    @param page_url: URL de la page
    @param site_age_score: Score d'age
    @param site_indicators: Indicateurs texte
    @param http_last_modified: Last-Modified
    @param tags: Tags entreprise
    @param force_heuristic: Force le fallback
    @returns: Dict avec design_review, design_score, design_source, design_analyzed_at
    """
    analyzed_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    context_bits = []
    if page_url:
        context_bits.append(f'URL: {page_url}')
    if site_age_score is not None:
        context_bits.append(f'site_age_score={site_age_score}')
    if site_indicators:
        context_bits.append(f'indicateurs: {site_indicators}')
    if http_last_modified:
        context_bits.append(f'Last-Modified: {http_last_modified}')

    data: Optional[bytes] = image_bytes
    resolved_mime = mime_type or 'image/webp'
    if data is None and image_path:
        path = Path(image_path)
        if path.is_file():
            data = path.read_bytes()
            resolved_mime = _mime_for_path(path)

    use_gemini = (
        not force_heuristic
        and data
        and (
            os.environ.get('GEMINI_API_KEY')
            or os.environ.get('GEMINI_API_KEYS')
            or os.environ.get('GEMINI_API_KEY_2')
        )
    )

    if use_gemini:
        try:
            from services.gemini_client import gemini_vision_json

            prompt = (
                "Analyse ce screenshot de site web (desktop). "
                + (' Contexte: ' + ' | '.join(context_bits) if context_bits else '')
            )
            raw = gemini_vision_json(
                prompt=prompt,
                image_bytes=data,
                mime_type=resolved_mime,
                system_instruction=DESIGN_SYSTEM_PROMPT,
            )
            review = _normalize_review(raw if isinstance(raw, dict) else {}, 'gemini')
            return {
                'design_review': review,
                'design_score': review['score'],
                'design_source': 'gemini',
                'design_analyzed_at': analyzed_at,
            }
        except Exception as exc:
            logger.warning('Gemini Vision design review echec, fallback heuristique: %s', exc)

    review = heuristic_design_review(
        site_age_score=site_age_score,
        http_last_modified=http_last_modified,
        tags=tags,
        page_url=page_url,
    )
    review = _normalize_review(review, 'heuristic')
    return {
        'design_review': review,
        'design_score': review['score'],
        'design_source': 'heuristic',
        'design_analyzed_at': analyzed_at,
    }


def serialize_design_review(review: Any) -> Optional[str]:
    """Serialise design_review en JSON texte pour la BDD."""
    if review is None:
        return None
    if isinstance(review, str):
        return review
    try:
        return json.dumps(review, ensure_ascii=False)
    except Exception:
        return None


def parse_design_review(raw: Any) -> Optional[Dict[str, Any]]:
    """Parse design_review_json depuis la BDD."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None
