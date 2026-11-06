"""
Acces Postgres VocalGuard (catalogue intents) + sync Qdrant node15.

Meme schema que l'app VocalGuard : intents, intent_patterns, intent_responses,
intent_embeddings. Les points Qdrant utilisent intent_embeddings.id comme point id.
"""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from typing import Any, Generator
from urllib.parse import urlparse

from config import VOCALGUARD_DATABASE_URL, VOCALGUARD_KB_PROFILE
from services.facebook_prospection.qdrant import FacebookProspectionQdrant
from services.facebook_prospection.vocalguard_embed import EMBED_DIM, embed_text

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r'^[a-z][a-z0-9_]{1,79}$')


def vocalguard_db_configured() -> bool:
    """True si VOCALGUARD_DATABASE_URL est renseigne."""
    return bool((VOCALGUARD_DATABASE_URL or '').strip())


def _normalize_db_url(url: str) -> str:
    """Retire le prefixe SQLAlchemy pour psycopg2."""
    u = (url or '').strip()
    if u.startswith('postgresql+psycopg2://'):
        return 'postgresql://' + u.split('://', 1)[1]
    return u


@contextmanager
def _conn() -> Generator[Any, None, None]:
    """
    Connexion psycopg2 courte.

    @yields: connection
    @raises: RuntimeError si URL absente ou driver manquant
    """
    if not vocalguard_db_configured():
        raise RuntimeError('VOCALGUARD_DATABASE_URL manquant')
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError('psycopg2 requis pour VOCALGUARD_DATABASE_URL') from exc
    raw = _normalize_db_url(VOCALGUARD_DATABASE_URL)
    parsed = urlparse(raw)
    if parsed.scheme not in ('postgresql', 'postgres'):
        raise RuntimeError('VOCALGUARD_DATABASE_URL doit etre postgresql://')
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=(parsed.path or '/').lstrip('/') or 'vocalguard',
        user=parsed.username,
        password=parsed.password,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _intent_row_to_dict(row: tuple, patterns: list[str], responses: list[str]) -> dict[str, Any]:
    """Format API compatible VocalGuard list_intents."""
    return {
        'id': row[0],
        'tag': row[1],
        'profile': row[2],
        'enabled': bool(row[3]),
        'priority': int(row[4] or 0),
        'action': row[5],
        'patterns': patterns,
        'responses': responses,
    }


def list_intents_from_db(
    *,
    profile: str | None = None,
    enabled_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Catalogue intents depuis Postgres VocalGuard.

    @param profile: inbound | outbound_commercial
    @param enabled_only: Filtre enabled=true
    @returns: Liste d'intents (patterns + responses)
    """
    if not vocalguard_db_configured():
        return []
    prof = (profile or VOCALGUARD_KB_PROFILE or 'outbound_commercial').strip().lower()
    sql = '''
        SELECT id, tag, profile, enabled, priority, action
        FROM intents
        WHERE profile = %s
    '''
    params: list[Any] = [prof]
    if enabled_only:
        sql += ' AND enabled = true'
    sql += ' ORDER BY priority DESC, tag ASC'
    out: list[dict[str, Any]] = []
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            for row in rows:
                iid = row[0]
                cur.execute(
                    'SELECT pattern FROM intent_patterns WHERE intent_id = %s ORDER BY id',
                    (iid,),
                )
                patterns = [str(r[0]) for r in cur.fetchall() if r and r[0]]
                cur.execute(
                    'SELECT text FROM intent_responses WHERE intent_id = %s ORDER BY position, id',
                    (iid,),
                )
                responses = [str(r[0]) for r in cur.fetchall() if r and r[0]]
                out.append(_intent_row_to_dict(row, patterns, responses))
    except Exception as exc:
        logger.warning('Catalogue VocalGuard DB illisible: %s', exc)
        return []
    return out


def get_intent_by_tag_from_db(tag: str) -> dict[str, Any] | None:
    """
    Charge un intent par tag.

    @param tag: Tag KB
    @returns: Intent dict ou None
    """
    key = (tag or '').strip()
    if not key or not vocalguard_db_configured():
        return None
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT id, tag, profile, enabled, priority, action FROM intents WHERE tag = %s',
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return None
            iid = row[0]
            cur.execute(
                'SELECT pattern FROM intent_patterns WHERE intent_id = %s ORDER BY id',
                (iid,),
            )
            patterns = [str(r[0]) for r in cur.fetchall() if r and r[0]]
            cur.execute(
                'SELECT text FROM intent_responses WHERE intent_id = %s ORDER BY position, id',
                (iid,),
            )
            responses = [str(r[0]) for r in cur.fetchall() if r and r[0]]
            return _intent_row_to_dict(row, patterns, responses)
    except Exception as exc:
        logger.warning('Intent %s illisible en DB: %s', key, exc)
        return None


def _collect_embedding_point_ids(cur: Any, ref_type: str, ref_ids: list[int]) -> list[int]:
    if not ref_ids:
        return []
    cur.execute(
        '''
        SELECT id FROM intent_embeddings
        WHERE ref_type = %s AND ref_id = ANY(%s)
        ''',
        (ref_type, ref_ids),
    )
    return [int(r[0]) for r in cur.fetchall()]


def _upsert_embedding_row(
    cur: Any,
    store: FacebookProspectionQdrant,
    *,
    intent_id: int,
    intent_tag: str,
    profile: str,
    ref_type: str,
    ref_id: int,
    text: str,
) -> None:
    """
    Met a jour intent_embeddings + point Qdrant (meme id que VocalGuard).

    @param cur: Curseur Postgres
    @param store: Client Qdrant ProspectLab
    @param intent_id: FK intent
    @param intent_tag: Tag
    @param profile: Profil KB
    @param ref_type: pattern | response
    @param ref_id: ID pattern/response
    @param text: Texte embedde
    """
    vector = embed_text(text, dim=store.dims or EMBED_DIM)
    payload_json = json.dumps([float(x) for x in vector])
    cur.execute(
        '''
        INSERT INTO intent_embeddings (intent_id, ref_type, ref_id, embedding_json, dim)
        VALUES (%s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (ref_type, ref_id) DO UPDATE SET
            intent_id = EXCLUDED.intent_id,
            embedding_json = EXCLUDED.embedding_json,
            dim = EXCLUDED.dim
        RETURNING id
        ''',
        (intent_id, ref_type, ref_id, payload_json, len(vector)),
    )
    emb_id = int(cur.fetchone()[0])
    store.upsert_vocalguard_point(
        point_id=emb_id,
        vector=vector,
        intent_tag=intent_tag,
        ref_type=ref_type,
        ref_id=ref_id,
        profile=profile,
    )


def update_intent_in_db(
    tag: str,
    *,
    patterns: list[str] | None = None,
    responses: list[str] | None = None,
    enabled: bool | None = None,
    priority: int | None = None,
) -> dict[str, Any] | None:
    """
    CRUD metier : met a jour patterns/reponses + re-indexe Qdrant node15.

    @param tag: Tag intent
    @param patterns: Nouveaux patterns (remplace tout)
    @param responses: Nouvelles reponses (remplace tout)
    @param enabled: Flag actif
    @param priority: Priorite
    @returns: Intent mis a jour ou None
    """
    key = (tag or '').strip()
    if not key or not vocalguard_db_configured():
        return None
    store = FacebookProspectionQdrant()
    if not store.enabled():
        raise RuntimeError('QDRANT_URL manquant pour sync embeddings')
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT id, tag, profile, enabled, priority, action FROM intents WHERE tag = %s',
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return None
            intent_id, intent_tag, profile = int(row[0]), str(row[1]), str(row[2])
            if enabled is not None:
                cur.execute('UPDATE intents SET enabled = %s WHERE id = %s', (bool(enabled), intent_id))
            if priority is not None:
                cur.execute('UPDATE intents SET priority = %s WHERE id = %s', (int(priority), intent_id))

            if patterns is not None:
                cur.execute('SELECT id FROM intent_patterns WHERE intent_id = %s', (intent_id,))
                old_pids = [int(r[0]) for r in cur.fetchall()]
                old_points = _collect_embedding_point_ids(cur, 'pattern', old_pids)
                if old_points:
                    store.delete_points_by_ids(old_points)
                cur.execute('DELETE FROM intent_patterns WHERE intent_id = %s', (intent_id,))
                for ptxt in patterns:
                    p = str(ptxt or '').strip()
                    if not p:
                        continue
                    cur.execute(
                        'INSERT INTO intent_patterns (intent_id, pattern, weight) VALUES (%s, %s, 1.0) RETURNING id',
                        (intent_id, p),
                    )
                    pid = int(cur.fetchone()[0])
                    _upsert_embedding_row(
                        cur,
                        store,
                        intent_id=intent_id,
                        intent_tag=intent_tag,
                        profile=profile,
                        ref_type='pattern',
                        ref_id=pid,
                        text=p,
                    )

            if responses is not None:
                cur.execute('SELECT id FROM intent_responses WHERE intent_id = %s', (intent_id,))
                old_rids = [int(r[0]) for r in cur.fetchall()]
                old_points = _collect_embedding_point_ids(cur, 'response', old_rids)
                if old_points:
                    store.delete_points_by_ids(old_points)
                cur.execute('DELETE FROM intent_responses WHERE intent_id = %s', (intent_id,))
                pos = 0
                for rtxt in responses:
                    r = str(rtxt or '').strip()
                    if not r:
                        continue
                    cur.execute(
                        '''
                        INSERT INTO intent_responses (intent_id, position, text)
                        VALUES (%s, %s, %s) RETURNING id
                        ''',
                        (intent_id, pos, r),
                    )
                    rid = int(cur.fetchone()[0])
                    pos += 1
                    _upsert_embedding_row(
                        cur,
                        store,
                        intent_id=intent_id,
                        intent_tag=intent_tag,
                        profile=profile,
                        ref_type='response',
                        ref_id=rid,
                        text=r,
                    )
    except Exception as exc:
        logger.warning('Update intent %s echoue: %s', key, exc)
        raise
    return get_intent_by_tag_from_db(key)
