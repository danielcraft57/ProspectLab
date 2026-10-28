"""
Client Qdrant minimal pour la collection prospectlab_facebook_messaging.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import requests

from config import (
    FACEBOOK_PROSPECTION_QDRANT_BRAND_ID,
    FACEBOOK_PROSPECTION_QDRANT_COLLECTION,
    FACEBOOK_PROSPECTION_QDRANT_DIMS,
    FACEBOOK_PROSPECTION_QDRANT_URL,
)

logger = logging.getLogger(__name__)


def _qdrant_base() -> str:
    url = (FACEBOOK_PROSPECTION_QDRANT_URL or '').strip().rstrip('/')
    if not url:
        raise RuntimeError('QDRANT_URL / FACEBOOK_PROSPECTION_QDRANT_URL manquant')
    return url


def qdrant_point_id(brand_id: str, kind: str, ref_key: str) -> int:
    """
    ID entier stable pour upsert idempotent (aligne SocialDesk).

    @param brand_id: Marque (ex. danielcraft)
    @param kind: Type de point Qdrant
    @param ref_key: Cle logique unique
    @returns: Entier 32 bits pour Qdrant
    """
    digest = hashlib.sha256(f'{brand_id}|{kind}|{ref_key}'.encode('utf-8')).digest()
    return int.from_bytes(digest[:4], 'big', signed=False)


class FacebookProspectionQdrant:
    """
    Operations Qdrant pour les intents Messenger ProspectLab.
    """

    def __init__(
        self,
        collection: str | None = None,
        brand_id: str | None = None,
        dims: int | None = None,
    ) -> None:
        self.collection = collection or FACEBOOK_PROSPECTION_QDRANT_COLLECTION
        self.brand_id = brand_id or FACEBOOK_PROSPECTION_QDRANT_BRAND_ID
        self.dims = dims or FACEBOOK_PROSPECTION_QDRANT_DIMS

    def enabled(self) -> bool:
        """True si Qdrant est configure."""
        return bool((FACEBOOK_PROSPECTION_QDRANT_URL or '').strip())

    def ensure_collection(self) -> None:
        """Cree la collection cosine 768d si absente."""
        base = _qdrant_base()
        url = f'{base}/collections/{self.collection}'
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return
        create = requests.put(
            url,
            json={'vectors': {'size': self.dims, 'distance': 'Cosine'}},
            timeout=30,
        )
        if create.status_code not in (200, 201):
            raise RuntimeError(f'Qdrant create collection: {create.status_code} {create.text[:300]}')

    def upsert_point(
        self,
        kind: str,
        ref_key: str,
        text: str,
        vector: list[float],
        extra_payload: dict[str, Any] | None = None,
    ) -> None:
        """
        Indexe ou met a jour un point.

        @param kind: intent_def | intent_example | intent_reply | faq_snippet
        @param ref_key: Cle stable
        @param text: Texte embedde (preview stocke aussi)
        @param vector: Embedding dimension self.dims
        @param extra_payload: Champs additionnels (intent_id, label, etc.)
        """
        if len(vector) != self.dims:
            raise ValueError(f'vecteur {len(vector)} != {self.dims}')
        payload: dict[str, Any] = {
            'brand_id': self.brand_id,
            'kind': kind,
            'ref_key': ref_key[:200],
            'text_preview': (text or '')[:500],
        }
        if extra_payload:
            for key, value in extra_payload.items():
                if value is not None:
                    payload[key] = value
        point_id = qdrant_point_id(self.brand_id, kind, ref_key)
        base = _qdrant_base()
        url = f'{base}/collections/{self.collection}/points?wait=true'
        body = {
            'points': [
                {
                    'id': point_id,
                    'vector': vector,
                    'payload': payload,
                }
            ]
        }
        resp = requests.put(url, json=body, timeout=60)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f'Qdrant upsert: {resp.status_code} {resp.text[:300]}')

    def search(
        self,
        vector: list[float],
        kinds: list[str] | None = None,
        limit: int = 8,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Recherche vectorielle filtree par brand_id (+ kinds optionnels).

        @param vector: Embedding requete
        @param kinds: Filtre kinds Qdrant
        @param limit: Nombre max de hits
        @param min_score: Seuil score cosine
        @returns: Liste de hits {score, payload, ...}
        """
        must: list[dict[str, Any]] = [{'key': 'brand_id', 'match': {'value': self.brand_id}}]
        if kinds:
            if len(kinds) == 1:
                must.append({'key': 'kind', 'match': {'value': kinds[0]}})
            else:
                must.append({'key': 'kind', 'match': {'any': kinds}})
        base = _qdrant_base()
        url = f'{base}/collections/{self.collection}/points/search'
        resp = requests.post(
            url,
            json={
                'vector': vector,
                'limit': limit,
                'score_threshold': min_score,
                'with_payload': True,
                'filter': {'must': must},
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning('Qdrant search HTTP %s', resp.status_code)
            return []
        data = resp.json()
        result = data.get('result') or []
        hits: list[dict[str, Any]] = []
        for item in result:
            hits.append(
                {
                    'score': item.get('score'),
                    'payload': item.get('payload') or {},
                }
            )
        return hits
