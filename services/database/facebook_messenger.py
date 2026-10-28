"""
Tables et CRUD Messenger synchronise (inbox Facebook).
"""

from __future__ import annotations

import json
from typing import Any

from .base import DatabaseBase
from services.facebook_prospection.messenger_store import (
    message_fingerprint,
    normalize_sync_direction,
)


class FacebookMessengerManager(DatabaseBase):
    """Fil Messenger global + messages dedoublonnes."""

    def ensure_facebook_messenger_tables(self) -> None:
        """Cree les tables messenger_* si absentes."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                CREATE TABLE IF NOT EXISTS facebook_messenger_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL DEFAULT 'danielcraft',
                    thread_key TEXT NOT NULL,
                    contact_name TEXT,
                    entreprise_id INTEGER,
                    thread_url TEXT,
                    preview TEXT,
                    unread_count INTEGER NOT NULL DEFAULT 0,
                    last_message_at TIMESTAMP,
                    read_at TIMESTAMP,
                    meta_json TEXT,
                    last_sync_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(account_id, thread_key),
                    FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE SET NULL
                )
                ''',
            )
            self.execute_sql(
                cursor,
                '''
                CREATE TABLE IF NOT EXISTS facebook_messenger_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    body_text TEXT,
                    msg_fingerprint TEXT NOT NULL,
                    sent_at TIMESTAMP,
                    raw_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (thread_id) REFERENCES facebook_messenger_threads(id) ON DELETE CASCADE,
                    UNIQUE(thread_id, msg_fingerprint)
                )
                ''',
            )
            self.execute_sql(
                cursor,
                '''
                CREATE TABLE IF NOT EXISTS facebook_messenger_sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    stats_json TEXT
                )
                ''',
            )
            self.execute_sql(
                cursor,
                'CREATE INDEX IF NOT EXISTS idx_fb_messenger_threads_ent ON facebook_messenger_threads(entreprise_id, last_sync_at DESC)',
            )
            self.execute_sql(
                cursor,
                'CREATE INDEX IF NOT EXISTS idx_fb_messenger_threads_unread ON facebook_messenger_threads(unread_count)',
            )
            conn.commit()
        finally:
            conn.close()

    def match_entreprise_for_messenger_contact(self, contact_name: str) -> int | None:
        """
        Tente de lier un fil Messenger a une fiche entreprise (nom ou page FB).

        @param contact_name: Nom affiche dans l'inbox
        @returns: entreprise_id ou None
        """
        needle = str(contact_name or '').strip()
        if len(needle) < 2:
            return None
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            like = f'%{needle[:80]}%'
            self.execute_sql(
                cursor,
                '''
                SELECT e.id FROM entreprises e
                LEFT JOIN facebook_prospection_pages p ON p.entreprise_id = e.id AND p.selected = 1
                WHERE e.nom LIKE ? OR p.page_name LIKE ?
                ORDER BY e.id DESC
                LIMIT 1
                ''',
                (like, like),
            )
            row = cursor.fetchone()
            if not row:
                return None
            eid = row.get('id') if isinstance(row, dict) else row[0]
            return int(eid) if eid else None
        finally:
            conn.close()

    def upsert_facebook_messenger_thread(
        self,
        account_id: str,
        thread_key: str,
        *,
        contact_name: str | None = None,
        entreprise_id: int | None = None,
        thread_url: str | None = None,
        preview: str | None = None,
        fb_unread: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> tuple[int, bool]:
        """
        Cree ou met a jour un fil inbox.

        @returns: (thread_id, created_new)
        """
        from datetime import datetime, timezone

        acc = str(account_id or 'danielcraft')[:80]
        key = str(thread_key or '')[:500]
        conn = self.get_connection()
        cursor = conn.cursor()
        created = False
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT id, unread_count, entreprise_id FROM facebook_messenger_threads
                WHERE account_id = ? AND thread_key = ?
                LIMIT 1
                ''',
                (acc, key),
            )
            row = cursor.fetchone()
            meta_json = json.dumps(meta or {}, ensure_ascii=False)
            now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            unread = 1 if fb_unread else 0

            if row:
                tid = row.get('id') if isinstance(row, dict) else row[0]
                old_unread = row.get('unread_count') if isinstance(row, dict) else row[1]
                old_ent = row.get('entreprise_id') if isinstance(row, dict) else row[2]
                ent_val = entreprise_id if entreprise_id else old_ent
                new_unread = max(int(old_unread or 0), unread)
                self.execute_sql(
                    cursor,
                    '''
                    UPDATE facebook_messenger_threads
                    SET contact_name = COALESCE(?, contact_name),
                        entreprise_id = ?,
                        thread_url = COALESCE(?, thread_url),
                        preview = COALESCE(?, preview),
                        unread_count = ?,
                        meta_json = ?,
                        last_message_at = ?,
                        last_sync_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''',
                    (
                        contact_name,
                        ent_val,
                        thread_url,
                        preview,
                        new_unread,
                        meta_json,
                        now,
                        int(tid),
                    ),
                )
                conn.commit()
                return int(tid), False

            params = (
                acc,
                key,
                contact_name,
                entreprise_id,
                thread_url,
                preview,
                unread,
                now,
                meta_json,
            )
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_messenger_threads
                        (account_id, thread_key, contact_name, entreprise_id, thread_url,
                         preview, unread_count, last_message_at, meta_json, last_sync_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    RETURNING id
                    ''',
                    params,
                )
                ins = cursor.fetchone()
                tid = ins.get('id') if isinstance(ins, dict) else ins[0]
            else:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_messenger_threads
                        (account_id, thread_key, contact_name, entreprise_id, thread_url,
                         preview, unread_count, last_message_at, meta_json, last_sync_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''',
                    params,
                )
                tid = cursor.lastrowid
            created = True
            conn.commit()
            return int(tid), created
        finally:
            conn.close()

    def add_facebook_messenger_message_if_new(
        self,
        thread_id: int,
        direction: str,
        body_text: str,
        *,
        msg_fingerprint: str,
        sent_at: str | None = None,
        raw_json: dict[str, Any] | None = None,
    ) -> bool:
        """
        Insere un message si le fingerprint n'existe pas encore.

        @returns: True si nouvelle ligne
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            params = (
                int(thread_id),
                str(direction)[:20],
                (body_text or '')[:8000],
                str(msg_fingerprint)[:80],
                sent_at,
                json.dumps(raw_json or {}, ensure_ascii=False),
            )
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_messenger_messages
                        (thread_id, direction, body_text, msg_fingerprint, sent_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (thread_id, msg_fingerprint) DO NOTHING
                    RETURNING id
                    ''',
                    params,
                )
                row = cursor.fetchone()
                inserted = row is not None
            else:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT OR IGNORE INTO facebook_messenger_messages
                        (thread_id, direction, body_text, msg_fingerprint, sent_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    params,
                )
                inserted = cursor.rowcount > 0
            if inserted:
                self.execute_sql(
                    cursor,
                    '''
                    UPDATE facebook_messenger_threads
                    SET preview = ?, last_message_at = COALESCE(?, CURRENT_TIMESTAMP),
                        last_sync_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''',
                    ((body_text or '')[:500], sent_at, int(thread_id)),
                )
            conn.commit()
            return bool(inserted)
        finally:
            conn.close()

    def bump_facebook_messenger_thread_unread(self, thread_id: int, delta: int = 1) -> None:
        """Incremente le compteur non lu d'un fil."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                UPDATE facebook_messenger_threads
                SET unread_count = unread_count + ?
                WHERE id = ?
                ''',
                (max(1, int(delta)), int(thread_id)),
            )
            conn.commit()
        finally:
            conn.close()

    def get_facebook_messenger_thread_unread(self, thread_id: int) -> int:
        """Lit unread_count."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'SELECT unread_count FROM facebook_messenger_threads WHERE id = ?',
                (int(thread_id),),
            )
            row = cursor.fetchone()
            if not row:
                return 0
            val = row.get('unread_count') if isinstance(row, dict) else row[0]
            return int(val or 0)
        finally:
            conn.close()

    def get_facebook_messenger_thread(self, thread_id: int) -> dict[str, Any] | None:
        """Retourne un fil Messenger par id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'SELECT * FROM facebook_messenger_threads WHERE id = ?',
                (int(thread_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row) if not isinstance(row, dict) else row
        finally:
            conn.close()

    def get_last_inbound_facebook_messenger_message(
        self,
        thread_id: int,
    ) -> dict[str, Any] | None:
        """Dernier message entrant enregistre sur un fil."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_messenger_messages
                WHERE thread_id = ? AND direction = 'inbound'
                ORDER BY id DESC
                LIMIT 1
                ''',
                (int(thread_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row) if not isinstance(row, dict) else row
        finally:
            conn.close()

    def list_facebook_messenger_threads(
        self,
        *,
        entreprise_id: int | None = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Liste les fils synchronises."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            clauses = ['1=1']
            params: list[Any] = []
            if entreprise_id is not None:
                clauses.append('entreprise_id = ?')
                params.append(int(entreprise_id))
            if unread_only:
                clauses.append('unread_count > 0')
            params.append(int(limit))
            self.execute_sql(
                cursor,
                f'''
                SELECT * FROM facebook_messenger_threads
                WHERE {' AND '.join(clauses)}
                ORDER BY COALESCE(last_message_at, last_sync_at) DESC, id DESC
                LIMIT ?
                ''',
                tuple(params),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_facebook_messenger_messages(
        self,
        thread_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Messages d'un fil Messenger."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_messenger_messages
                WHERE thread_id = ?
                ORDER BY id ASC
                LIMIT ?
                ''',
                (int(thread_id), int(limit)),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_facebook_messenger_summary(self) -> dict[str, Any]:
        """Compteurs inbox pour l'UI (pastilles + notifications)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT
                    COUNT(*) AS thread_count,
                    SUM(CASE WHEN unread_count > 0 THEN 1 ELSE 0 END) AS unread_threads,
                    COALESCE(SUM(unread_count), 0) AS unread_messages
                FROM facebook_messenger_threads
                ''',
            )
            row = cursor.fetchone()
            if not row:
                return {'thread_count': 0, 'unread_threads': 0, 'unread_messages': 0}
            if isinstance(row, dict):
                return {
                    'thread_count': int(row.get('thread_count') or 0),
                    'unread_threads': int(row.get('unread_threads') or 0),
                    'unread_messages': int(row.get('unread_messages') or 0),
                }
            return {
                'thread_count': int(row[0] or 0),
                'unread_threads': int(row[1] or 0),
                'unread_messages': int(row[2] or 0),
            }
        finally:
            conn.close()

    def mark_facebook_messenger_thread_read(self, thread_id: int) -> bool:
        """Marque un fil comme lu dans ProspectLab."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                UPDATE facebook_messenger_threads
                SET unread_count = 0, read_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (int(thread_id),),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def record_facebook_messenger_sync_event(self, stats: dict[str, Any]) -> None:
        """Journalise une sync reussie."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'INSERT INTO facebook_messenger_sync_log (stats_json) VALUES (?)',
                (json.dumps(stats, ensure_ascii=False),),
            )
            conn.commit()
        finally:
            conn.close()

    def mirror_messenger_thread_to_prospection_conversation(
        self,
        entreprise_id: int,
        messenger_thread_id: int,
        contact_name: str,
        thread_key: str,
        messages: list[Any],
    ) -> None:
        """
        Copie les messages vers facebook_prospection_* pour l'onglet entreprise.

        @param messenger_thread_id: ID fil messenger global
        """
        page_row = self.get_facebook_prospection_selected_page(int(entreprise_id))
        page_id = int(page_row.get('id') or 0) if page_row else None
        conv_id = self.upsert_facebook_prospection_conversation(
            int(entreprise_id),
            page_id=page_id,
            thread_key=f'msg:{thread_key}',
            fb_page_url=(page_row or {}).get('page_url'),
            status='synced',
            meta={
                'messenger_thread_id': messenger_thread_id,
                'contact_name': contact_name,
            },
        )
        for mi, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            body = str(msg.get('text') or '').strip()
            if not body:
                continue
            direction = normalize_sync_direction(msg.get('direction'))
            fp = message_fingerprint(direction, body, mi)
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                self.execute_sql(
                    cursor,
                    '''
                    SELECT id FROM facebook_prospection_messages
                    WHERE conversation_id = ? AND raw_json LIKE ?
                    LIMIT 1
                    ''',
                    (int(conv_id), f'%{fp[:20]}%'),
                )
                if cursor.fetchone():
                    continue
            finally:
                conn.close()
            self.add_facebook_prospection_message(
                conv_id,
                'outbound' if direction == 'outbound' else 'inbound',
                body,
                raw_json={'fp': fp, 'source': 'messenger_sync'},
            )
