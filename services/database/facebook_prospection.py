"""
Persistance des jobs et conversations Facebook ProspectLab.
"""

from __future__ import annotations

import json
from typing import Any

from .base import DatabaseBase


class FacebookProspectionManager(DatabaseBase):
    """CRUD tables facebook_prospection_*."""

    def create_facebook_prospection_job(
        self,
        entreprise_id: int,
        job_type: str,
        query: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> int:
        """
        Cree un job en statut pending.

        @param entreprise_id: Fiche entreprise ProspectLab
        @param job_type: search | scrape_page | messenger_inbox
        @param query: Requete de recherche FB optionnelle
        @param meta: JSON libre (role serv1/serv2, etc.)
        @returns: id du job
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            params = (
                int(entreprise_id),
                job_type,
                query,
                json.dumps(meta or {}, ensure_ascii=False),
            )
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_jobs
                        (entreprise_id, job_type, status, search_query, meta_json)
                    VALUES (?, ?, 'pending', ?, ?)
                    RETURNING id
                    ''',
                    params,
                )
                row = cursor.fetchone()
                job_id = row.get('id') if isinstance(row, dict) else row[0]
            else:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_jobs
                        (entreprise_id, job_type, status, search_query, meta_json)
                    VALUES (?, ?, 'pending', ?, ?)
                    ''',
                    params,
                )
                job_id = cursor.lastrowid
            conn.commit()
            return int(job_id)
        finally:
            conn.close()

    def update_facebook_prospection_job_status(
        self,
        job_id: int,
        status: str,
        error_message: str | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> None:
        """Met a jour le statut et le resultat d'un job."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                UPDATE facebook_prospection_jobs
                SET status = ?, error_message = ?, result_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    status,
                    error_message,
                    json.dumps(result_json or {}, ensure_ascii=False) if result_json else None,
                    int(job_id),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_facebook_prospection_job(self, job_id: int) -> dict[str, Any] | None:
        """Retourne un job par id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'SELECT * FROM facebook_prospection_jobs WHERE id = ?',
                (int(job_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row) if not isinstance(row, dict) else row
        finally:
            conn.close()

    def list_facebook_prospection_jobs(
        self,
        entreprise_id: int,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Liste les jobs recents pour une entreprise."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_prospection_jobs
                WHERE entreprise_id = ?
                ORDER BY id DESC
                LIMIT ?
                ''',
                (int(entreprise_id), int(limit)),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def save_facebook_page_candidates(
        self,
        job_id: int,
        entreprise_id: int,
        candidates: list[dict[str, Any]],
    ) -> None:
        """
        Enregistre les candidats pages FB pour un job de recherche.

        @param job_id: Job source
        @param entreprise_id: Entreprise liee
        @param candidates: Liste {name, url, score, raw}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for item in candidates:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_page_candidates
                        (job_id, entreprise_id, page_name, page_url, match_score, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        int(job_id),
                        int(entreprise_id),
                        str(item.get('name') or '')[:500],
                        str(item.get('url') or '')[:1000],
                        float(item.get('score') or 0),
                        json.dumps(item, ensure_ascii=False),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def list_facebook_page_candidates(self, job_id: int) -> list[dict[str, Any]]:
        """Candidats pages pour un job."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_prospection_page_candidates
                WHERE job_id = ?
                ORDER BY match_score DESC, id ASC
                ''',
                (int(job_id),),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()
