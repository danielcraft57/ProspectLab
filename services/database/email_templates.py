"""
Gestion des modèles d'emails stockés en base (email_templates).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import DatabaseBase


class EmailTemplateManager(DatabaseBase):
    """
    Manager CRUD des modèles d'emails stockés en BDD.
    """

    def list_email_templates(self, category: Optional[str] = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Liste les modèles.

        Args:
            category: Filtrer par catégorie (optionnel).
            active_only: Si True, ne renvoie que les modèles actifs.

        Returns:
            Liste de modèles.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            where = []
            params: list[Any] = []

            if category:
                where.append("category = ?")
                params.append(category)

            if active_only:
                where.append("is_active = 1")

            sql = "SELECT id, name, category, subject, content, is_html, is_active, created_at, updated_at FROM email_templates"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY updated_at DESC"

            # Utiliser execute_sql pour gérer SQLite/PostgreSQL (placeholders, adaptations).
            self.execute_sql(cursor, sql, params or None)
            rows = cursor.fetchall() or []
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_email_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un modèle par id.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            sql = (
                "SELECT id, name, category, subject, content, is_html, is_active, created_at, updated_at "
                "FROM email_templates WHERE id = ?"
            )
            self.execute_sql(cursor, sql, (template_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def upsert_email_template(
        self,
        template_id: str,
        name: str,
        category: str,
        subject: str,
        content: str,
        is_html: bool,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Crée ou met à jour un modèle.
        """
        now = datetime.now().isoformat()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            existing = self.get_email_template(template_id)
            if existing:
                sql = (
                    "UPDATE email_templates SET name = ?, category = ?, subject = ?, content = ?, "
                    "is_html = ?, is_active = ?, updated_at = ? WHERE id = ?"
                )
                self.execute_sql(
                    cursor,
                    sql,
                    (name, category, subject, content, 1 if is_html else 0, 1 if is_active else 0, now, template_id),
                )
            else:
                sql = (
                    "INSERT INTO email_templates (id, name, category, subject, content, is_html, is_active, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                )
                self.execute_sql(
                    cursor,
                    sql,
                    (template_id, name, category, subject, content, 1 if is_html else 0, 1 if is_active else 0, now, now),
                )

            # Toujours valider la transaction, SQLite ou PostgreSQL.
            conn.commit()

            tpl = self.get_email_template(template_id)
            return tpl or {
                "id": template_id,
                "name": name,
                "category": category,
                "subject": subject,
                "content": content,
                "is_html": 1 if is_html else 0,
                "is_active": 1 if is_active else 0,
                "created_at": now,
                "updated_at": now,
            }
        finally:
            conn.close()

    def delete_email_template(self, template_id: str) -> bool:
        """
        Supprime un modèle.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            sql = "DELETE FROM email_templates WHERE id = ?"
            self.execute_sql(cursor, sql, (template_id,))
            # Valider la suppression dans tous les cas.
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def count_email_templates(self) -> int:
        """
        Compte les modèles.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            sql = "SELECT COUNT(*) as n FROM email_templates"
            self.execute_sql(cursor, sql)
            row = cursor.fetchone()
            if not row:
                return 0
            data = dict(row)
            return int(data.get("n") or data.get("count") or 0)
        finally:
            conn.close()

