"""
Client Qdrant pour la KB Messenger (collections intents_*).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import requests

from config import (
    FACEBOOK_PROSPECTION_QDRANT_COLLECTION,
    FACEBOOK_PROSPECTION_QDRANT_DIMS,
    FACEBOOK_PROSPECTION_QDRANT_URL,
    VOCALGUARD_KB_PROFILE,
)

_PROFILE_COLLECTIONS = {
    'inbound': 'intents_inbound',
    'outbound_commercial': 'intents_outbound_commercial',
}

logger = logging.getLogger(__name__)


def _qdrant_base() -> str:
    url = (FACEBOOK_PROSPECTION_QDRANT_URL or '').strip().rstrip('/')
    if not url:
        raise RuntimeError('QDRANT_URL / FACEBOOK_PROSPECTION_QDRANT_URL manquant')
    return url


class FacebookProspectionQdrant:
    """
    Recherche vectorielle sur la KB VocalGuard (pas d'indexation ProspectLab).
    """

    def __init__(
        self,
        collection: str | None = None,
        dims: int | None = None,
        profile: str | None = None,
    ) -> None:
        self.profile = (profile or VOCALGUARD_KB_PROFILE or 'outbound_commercial').strip().lower()
        self.collection = (
            collection
            or _PROFILE_COLLECTIONS.get(self.profile)
            or FACEBOOK_PROSPECTION_QDRANT_COLLECTION
        )
        self.dims = dims or FACEBOOK_PROSPECTION_QDRANT_DIMS

    def enabled(self) -> bool:
        """True si Qdrant est configure."""
        return bool((FACEBOOK_PROSPECTION_QDRANT_URL or '').strip())

    def upsert_intent_text(
        self,
        intent_tag: str,
        ref_type: str,
        text: str,
        vector: list[float],
    ) -> None:
        """
        Indexe un pattern ou une reponse (point id hashe, sans ecraser les IDs VocalGuard).

        @param intent_tag: Tag KB
        @param ref_type: pattern | response
        @param text: Texte embedde
        @param vector: Vecteur 384d
        """
        tag = (intent_tag or '').strip()
        body_txt = (text or '').strip()
        if not tag or not body_txt:
            return
        if len(vector) != self.dims:
            raise ValueError(f'vecteur {len(vector)} != {self.dims}')
        digest = hashlib.sha256(
            f'pl|{self.profile}|{tag}|{ref_type}|{body_txt}'.encode('utf-8')
        ).digest()
        point_id = int.from_bytes(digest[:8], 'big', signed=False) % (2**63)
        payload = {
            'intent_tag': tag,
            'ref_type': ref_type,
            'ref_id': 0,
            'profile': self.profile,
            'source': 'prospectlab_sync',
        }
        resp = requests.put(
            f'{_qdrant_base()}/collections/{self.collection}/points?wait=true',
            json={
                'points': [
                    {
                        'id': point_id,
                        'vector': [float(x) for x in vector],
                        'payload': payload,
                    }
                ]
            },
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f'Qdrant upsert HTTP {resp.status_code}: {resp.text[:200]}')

    def upsert_vocalguard_point(
        self,
        *,
        point_id: int,
        vector: list[float],
        intent_tag: str,
        ref_type: str,
        ref_id: int,
        profile: str | None = None,
    ) -> None:
        """
        Upsert aligne VocalGuard (point id = intent_embeddings.id).

        @param point_id: ID embedding / point Qdrant
        @param vector: Vecteur 384d
        @param intent_tag: Tag
        @param ref_type: pattern | response
        @param ref_id: ID pattern ou response
        @param profile: Profil KB
        """
        if len(vector) != self.dims:
            raise ValueError(f'vecteur {len(vector)} != {self.dims}')
        prof = (profile or self.profile or 'outbound_commercial').strip().lower()
        payload = {
            'intent_tag': (intent_tag or '').strip(),
            'ref_type': str(ref_type)[:20],
            'ref_id': int(ref_id),
            'profile': prof,
        }
        resp = requests.put(
            f'{_qdrant_base()}/collections/{self.collection}/points?wait=true',
            json={
                'points': [
                    {
                        'id': int(point_id),
                        'vector': [float(x) for x in vector],
                        'payload': payload,
                    }
                ]
            },
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f'Qdrant upsert HTTP {resp.status_code}: {resp.text[:200]}')

    def delete_points_by_ids(self, point_ids: list[int]) -> None:
        """
        Supprime des points Qdrant (IDs intent_embeddings).

        @param point_ids: Liste d'IDs
        """
        if not point_ids or not self.enabled():
            return
        resp = requests.post(
            f'{_qdrant_base()}/collections/{self.collection}/points/delete?wait=true',
            json={'points': [int(x) for x in point_ids]},
            timeout=30,
        )
        if resp.status_code not in (200, 202):
            logger.warning('Qdrant delete HTTP %s', resp.status_code)

    def collection_info(self) -> dict[str, Any]:
        """
        Snapshot collection (points, dim).

        @returns: Dict ok / points_count / detail
        """
        if not self.enabled():
            return {'ok': False, 'configured': False, 'points_count': 0, 'detail': 'QDRANT_URL manquant'}
        try:
            resp = requests.get(f'{_qdrant_base()}/collections/{self.collection}', timeout=8)
        except requests.RequestException as exc:
            return {
                'ok': False,
                'configured': True,
                'collection': self.collection,
                'points_count': 0,
                'detail': str(exc)[:160],
            }
        if resp.status_code != 200:
            return {
                'ok': False,
                'configured': True,
                'collection': self.collection,
                'points_count': 0,
                'detail': f'HTTP {resp.status_code}',
            }
        result = (resp.json() or {}).get('result') or {}
        params = result.get('config', {}).get('params', {}).get('vectors') or {}
        return {
            'ok': True,
            'configured': True,
            'collection': self.collection,
            'points_count': int(result.get('points_count') or 0),
            'vector_size': params.get('size'),
            'distance': params.get('distance'),
            'detail': None,
        }

    def search(
        self,
        vector: list[float],
        *,
        limit: int = 24,
        min_score: float = 0.0,
        profile: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Recherche cosine, payload VocalGuard (intent_tag, ref_type, profile).

        @param vector: Embedding 384d
        @param limit: Nombre max de hits
        @param min_score: Seuil cosine
        @param profile: inbound | outbound_commercial
        @returns: Liste {score, payload}
        """
        want_profile = (profile or self.profile or 'inbound').strip().lower()
        must: list[dict[str, Any]] = []
        if want_profile:
            must.append({'key': 'profile', 'match': {'value': want_profile}})
        body: dict[str, Any] = {
            'vector': vector,
            'limit': limit,
            'score_threshold': min_score,
            'with_payload': True,
        }
        if must:
            body['filter'] = {'must': must}
        try:
            resp = requests.post(
                f'{_qdrant_base()}/collections/{self.collection}/points/search',
                json=body,
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning('Qdrant KB injoignable: %s', exc)
            return []
        if resp.status_code != 200:
            # Anciens points sans payload.profile : retry sans filtre.
            if must and resp.status_code in (400, 422):
                return self._search_unfiltered(vector, limit=limit, min_score=min_score, want_profile=want_profile)
            logger.warning('Qdrant search HTTP %s', resp.status_code)
            return []
        hits = self._parse_hits(resp.json(), want_profile=want_profile)
        if not hits and must:
            hits = self._search_unfiltered(vector, limit=limit, min_score=min_score, want_profile=want_profile)
        return hits

    def list_intent_tags(self, *, limit: int = 2000) -> set[str]:
        """
        Liste les intent_tag presents dans la collection (scroll Qdrant).

        @param limit: Points max par page scroll
        @returns: Ensemble de tags
        """
        if not self.enabled():
            return set()
        tags: set[str] = set()
        offset = None
        pages = 0
        while pages < 50:
            body: dict[str, Any] = {
                'limit': min(limit, 256),
                'with_payload': True,
            }
            if offset is not None:
                body['offset'] = offset
            try:
                resp = requests.post(
                    f'{_qdrant_base()}/collections/{self.collection}/points/scroll',
                    json=body,
                    timeout=20,
                )
            except requests.RequestException as exc:
                logger.warning('Qdrant scroll: %s', exc)
                break
            if resp.status_code != 200:
                break
            data = resp.json() or {}
            result = data.get('result') or {}
            points = result.get('points') or []
            for pt in points:
                payload = pt.get('payload') or {}
                tag = str(payload.get('intent_tag') or '').strip()
                if tag:
                    tags.add(tag)
            offset = result.get('next_page_offset')
            pages += 1
            if offset is None:
                break
        return tags

    def _search_unfiltered(
        self,
        vector: list[float],
        *,
        limit: int,
        min_score: float,
        want_profile: str,
    ) -> list[dict[str, Any]]:
        """Recherche sans filtre payload (collection mixte / legacy)."""
        try:
            resp = requests.post(
                f'{_qdrant_base()}/collections/{self.collection}/points/search',
                json={
                    'vector': vector,
                    'limit': limit,
                    'score_threshold': min_score,
                    'with_payload': True,
                },
                timeout=15,
            )
        except requests.RequestException:
            return []
        if resp.status_code != 200:
            return []
        return self._parse_hits(resp.json(), want_profile=want_profile)

    def _parse_hits(self, data: dict[str, Any], *, want_profile: str) -> list[dict[str, Any]]:
        """
        Normalise les hits Qdrant VocalGuard.

        @param data: JSON Qdrant
        @param want_profile: Profil attendu
        @returns: Hits filtres
        """
        result = data.get('result') or []
        hits: list[dict[str, Any]] = []
        for item in result:
            payload = item.get('payload') or {}
            point_profile = str(payload.get('profile') or want_profile).strip().lower()
            if payload.get('profile') and point_profile != want_profile:
                continue
            hits.append({'score': item.get('score'), 'payload': payload})
        return hits
