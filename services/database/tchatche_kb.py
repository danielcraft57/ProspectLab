"""
Persistance des sessions sandbox Tchatche KB (contexte + archive).
"""

from __future__ import annotations

import json
from typing import Any

from .base import DatabaseBase


class TchatcheKbManager(DatabaseBase):
    """CRUD tables tchatche_sessions / tchatche_messages."""

    def create_tchatche_session(
        self,
        entreprise_id: int,
        *,
        created_by: int | None = None,
        title: str | None = None,
        context_summary: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> int:
        """
        Cree une session sandbox liee a une fiche CRM.

        @param entreprise_id: ID entreprise ProspectLab
        @param created_by: Utilisateur Flask (optionnel)
        @param title: Libelle affiche dans l'archive
        @param context_summary: Resume long terme (optionnel)
        @param meta: JSON libre (profil KB, etc.)
        @returns: id session
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            params = (
                int(entreprise_id),
                int(created_by) if created_by else None,
                (title or '')[:500] or None,
                (context_summary or '')[:8000] or None,
                json.dumps(meta or {}, ensure_ascii=False),
            )
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO tchatche_sessions
                        (entreprise_id, created_by, title, context_summary, meta_json)
                    VALUES (?, ?, ?, ?, ?)
                    RETURNING id
                    ''',
                    params,
                )
                row = cursor.fetchone()
                session_id = row.get('id') if isinstance(row, dict) else row[0]
            else:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO tchatche_sessions
                        (entreprise_id, created_by, title, context_summary, meta_json)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    params,
                )
                session_id = cursor.lastrowid
            conn.commit()
            return int(session_id)
        finally:
            conn.close()

    def touch_tchatche_session(
        self,
        session_id: int,
        *,
        title: str | None = None,
        context_summary: str | None = None,
    ) -> None:
        """
        Met a jour horodatage et champs optionnels.

        @param session_id: ID session
        @param title: Nouveau titre
        @param context_summary: Resume contexte
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            sets = ['updated_at = CURRENT_TIMESTAMP']
            params: list[Any] = []
            if title is not None:
                sets.append('title = ?')
                params.append((title or '')[:500] or None)
            if context_summary is not None:
                sets.append('context_summary = ?')
                params.append((context_summary or '')[:8000] or None)
            params.append(int(session_id))
            self.execute_sql(
                cursor,
                f'UPDATE tchatche_sessions SET {", ".join(sets)} WHERE id = ?',
                tuple(params),
            )
            conn.commit()
        finally:
            conn.close()

    def get_tchatche_session(
        self,
        session_id: int,
        *,
        entreprise_id: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Charge une session si elle existe (filtre entreprise optionnel).

        @param session_id: ID session
        @param entreprise_id: Verifie la fiche CRM
        @returns: Ligne session ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if entreprise_id is not None:
                self.execute_sql(
                    cursor,
                    'SELECT * FROM tchatche_sessions WHERE id = ? AND entreprise_id = ?',
                    (int(session_id), int(entreprise_id)),
                )
            else:
                self.execute_sql(cursor, 'SELECT * FROM tchatche_sessions WHERE id = ?', (int(session_id),))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row) if not isinstance(row, dict) else row
        finally:
            conn.close()

    def list_tchatche_sessions(
        self,
        entreprise_id: int,
        *,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Archive des tests sandbox pour une entreprise.

        @param entreprise_id: Fiche CRM
        @param limit: Nombre max de sessions
        @returns: Sessions triees par activite recente
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT s.*,
                    (SELECT COUNT(*) FROM tchatche_messages m WHERE m.session_id = s.id) AS message_count
                FROM tchatche_sessions s
                WHERE s.entreprise_id = ?
                ORDER BY s.updated_at DESC, s.id DESC
                LIMIT ?
                ''',
                (int(entreprise_id), int(limit)),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def add_tchatche_message(
        self,
        session_id: int,
        role: str,
        body_text: str | None,
        *,
        intent_tag: str | None = None,
        engine: str | None = None,
        score: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> int:
        """
        Ajoute un tour user/bot/system a la session.

        @param session_id: ID session
        @param role: user | bot | system
        @param body_text: Contenu
        @param intent_tag: Tag KB detecte
        @param engine: qdrant | kb_api | ...
        @param score: Confiance intent
        @param meta: JSON (predictions tronquees, etc.)
        @returns: id message
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            params = (
                int(session_id),
                str(role)[:20],
                (body_text or '')[:8000] or None,
                (intent_tag or '')[:200] or None,
                (engine or '')[:80] or None,
                float(score) if score is not None else None,
                json.dumps(meta or {}, ensure_ascii=False),
            )
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO tchatche_messages
                        (session_id, role, body_text, intent_tag, engine, score, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    ''',
                    params,
                )
                row = cursor.fetchone()
                msg_id = row.get('id') if isinstance(row, dict) else row[0]
            else:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO tchatche_messages
                        (session_id, role, body_text, intent_tag, engine, score, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    params,
                )
                msg_id = cursor.lastrowid
            self.execute_sql(
                cursor,
                'UPDATE tchatche_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (int(session_id),),
            )
            conn.commit()
            return int(msg_id)
        finally:
            conn.close()

    def list_tchatche_messages(
        self,
        session_id: int,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Messages d'une session sandbox (ordre chronologique).

        @param session_id: ID session
        @param limit: Nombre max
        @returns: Liste de messages
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM tchatche_messages
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?
                ''',
                (int(session_id), int(limit)),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def build_tchatche_context_window(
        messages: list[dict[str, Any]],
        *,
        limit: int = 6,
    ) -> dict[str, list[str]]:
        """
        Construit la fenetre envoyee au moteur KB (6 derniers tours).

        @param messages: Messages session (roles user/bot)
        @param limit: Taille fenetre par liste
        @returns: recent_replies, recent_tags, recent_user_texts
        """
        recent_replies: list[str] = []
        recent_tags: list[str] = []
        recent_user_texts: list[str] = []
        for row in messages:
            role = str(row.get('role') or '').strip().lower()
            body = str(row.get('body_text') or row.get('text') or '').strip()
            if role == 'user' and body:
                recent_user_texts.append(body)
            elif role == 'bot':
                if body:
                    recent_replies.append(body)
                tag = str(row.get('intent_tag') or '').strip()
                if tag:
                    recent_tags.append(tag)
        cap = max(1, int(limit))
        return {
            'recent_replies': recent_replies[-cap:],
            'recent_tags': recent_tags[-cap:],
            'recent_user_texts': recent_user_texts[-cap:],
        }
