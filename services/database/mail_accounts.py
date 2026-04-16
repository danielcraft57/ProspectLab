"""
Comptes SMTP / identités d'envoi multi-domaines (stockage en base).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import SECRET_KEY

from .base import DatabaseBase
from services.mail_crypto import decrypt_smtp_secret, encrypt_smtp_secret

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class MailAccountManager(DatabaseBase):
    """CRUD des comptes mail + lecture avec mot de passe déchiffré (usage serveur uniquement)."""

    def _encrypt_pw(self, plain: Optional[str]) -> str:
        if not plain:
            return ""
        return encrypt_smtp_secret(plain, SECRET_KEY)

    def _public_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(row)
        enc = d.pop("smtp_password_encrypted", None)
        d["has_password"] = bool(enc)
        d.pop("smtp_password", None)
        return d

    def validate_slug(self, slug: str) -> bool:
        s = (slug or "").strip().lower()
        return bool(_SLUG_RE.match(s))

    def list_mail_accounts(self, active_only: bool = False) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            sql = (
                "SELECT id, slug, label, domain_name, smtp_host, smtp_port, smtp_use_tls, smtp_use_ssl, "
                "smtp_username, smtp_password_encrypted, default_sender, reply_to, is_active, "
                "last_test_at, last_test_ok, last_test_message, last_dns_check_at, last_dns_check_json, "
                "created_at, updated_at FROM mail_accounts"
            )
            params: List[Any] = []
            if active_only:
                sql += " WHERE is_active = 1"
            sql += " ORDER BY label ASC"
            self.execute_sql(cursor, sql, tuple(params) if params else None)
            rows = cursor.fetchall() or []
            return [self._public_row(dict(r)) for r in rows]
        finally:
            conn.close()

    def get_mail_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            self.execute_sql(
                cursor,
                "SELECT id, slug, label, domain_name, smtp_host, smtp_port, smtp_use_tls, smtp_use_ssl, "
                "smtp_username, smtp_password_encrypted, default_sender, reply_to, is_active, "
                "last_test_at, last_test_ok, last_test_message, last_dns_check_at, last_dns_check_json, "
                "created_at, updated_at FROM mail_accounts WHERE id = ?",
                (int(account_id),),
            )
            row = cursor.fetchone()
            return self._public_row(dict(row)) if row else None
        finally:
            conn.close()

    def get_mail_account_decrypted(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Usage interne (Celery / envoi) : inclut smtp_password en clair."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            self.execute_sql(
                cursor,
                "SELECT * FROM mail_accounts WHERE id = ?",
                (int(account_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            enc = d.get("smtp_password_encrypted") or ""
            d["smtp_password"] = decrypt_smtp_secret(enc, SECRET_KEY) if enc else ""
            d.pop("smtp_password_encrypted", None)
            return d
        finally:
            conn.close()

    def get_mail_account_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            self.execute_sql(
                cursor,
                "SELECT id, slug, label, domain_name, smtp_host, smtp_port, smtp_use_tls, smtp_use_ssl, "
                "smtp_username, smtp_password_encrypted, default_sender, reply_to, is_active, "
                "last_test_at, last_test_ok, last_test_message, last_dns_check_at, last_dns_check_json, "
                "created_at, updated_at FROM mail_accounts WHERE slug = ?",
                (slug.strip().lower(),),
            )
            row = cursor.fetchone()
            return self._public_row(dict(row)) if row else None
        finally:
            conn.close()

    def create_mail_account(
        self,
        slug: str,
        label: str,
        smtp_host: str,
        default_sender: str,
        smtp_port: int = 587,
        smtp_use_tls: bool = True,
        smtp_use_ssl: bool = False,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        domain_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        is_active: bool = True,
    ) -> int:
        if not self.validate_slug(slug):
            raise ValueError("Slug invalide (a-z, 0-9, tirets/underscores, 1–63 caractères).")
        now = datetime.now().isoformat()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            pw = self._encrypt_pw(smtp_password)
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    """
                    INSERT INTO mail_accounts (
                        slug, label, domain_name, smtp_host, smtp_port, smtp_use_tls, smtp_use_ssl,
                        smtp_username, smtp_password_encrypted, default_sender, reply_to, is_active,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (
                        slug.strip().lower(),
                        label,
                        (domain_name or "").strip() or None,
                        smtp_host,
                        int(smtp_port),
                        1 if smtp_use_tls else 0,
                        1 if smtp_use_ssl else 0,
                        (smtp_username or "").strip() or None,
                        pw or None,
                        default_sender,
                        (reply_to or "").strip() or None,
                        1 if is_active else 0,
                        now,
                        now,
                    ),
                )
                row = cursor.fetchone()
                new_id = row.get("id") if isinstance(row, dict) else (row[0] if row else None)
            else:
                self.execute_sql(
                    cursor,
                    """
                    INSERT INTO mail_accounts (
                        slug, label, domain_name, smtp_host, smtp_port, smtp_use_tls, smtp_use_ssl,
                        smtp_username, smtp_password_encrypted, default_sender, reply_to, is_active,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        slug.strip().lower(),
                        label,
                        (domain_name or "").strip() or None,
                        smtp_host,
                        int(smtp_port),
                        1 if smtp_use_tls else 0,
                        1 if smtp_use_ssl else 0,
                        (smtp_username or "").strip() or None,
                        pw or None,
                        default_sender,
                        (reply_to or "").strip() or None,
                        1 if is_active else 0,
                        now,
                        now,
                    ),
                )
                new_id = cursor.lastrowid
            conn.commit()
            return int(new_id)
        finally:
            conn.close()

    def update_mail_account(
        self,
        account_id: int,
        slug: Optional[str] = None,
        label: Optional[str] = None,
        domain_name: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_use_tls: Optional[bool] = None,
        smtp_use_ssl: Optional[bool] = None,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        default_sender: Optional[str] = None,
        reply_to: Optional[str] = None,
        is_active: Optional[bool] = None,
        clear_password: bool = False,
    ) -> bool:
        now = datetime.now().isoformat()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            updates = []
            values: List[Any] = []

            if slug is not None:
                normalized_slug = (slug or "").strip().lower()
                if not self.validate_slug(normalized_slug):
                    raise ValueError("Slug invalide (a-z, 0-9, tirets/underscores, 1–63 caractères).")
                updates.append("slug = ?")
                values.append(normalized_slug)
            if label is not None:
                updates.append("label = ?")
                values.append(label)
            if domain_name is not None:
                updates.append("domain_name = ?")
                values.append(domain_name.strip() or None)
            if smtp_host is not None:
                updates.append("smtp_host = ?")
                values.append(smtp_host)
            if smtp_port is not None:
                updates.append("smtp_port = ?")
                values.append(int(smtp_port))
            if smtp_use_tls is not None:
                updates.append("smtp_use_tls = ?")
                values.append(1 if smtp_use_tls else 0)
            if smtp_use_ssl is not None:
                updates.append("smtp_use_ssl = ?")
                values.append(1 if smtp_use_ssl else 0)
            if smtp_username is not None:
                updates.append("smtp_username = ?")
                values.append(smtp_username.strip() or None)
            if smtp_password is not None:
                updates.append("smtp_password_encrypted = ?")
                values.append(self._encrypt_pw(smtp_password) or None)
            elif clear_password:
                updates.append("smtp_password_encrypted = ?")
                values.append(None)
            if default_sender is not None:
                updates.append("default_sender = ?")
                values.append(default_sender)
            if reply_to is not None:
                updates.append("reply_to = ?")
                values.append(reply_to.strip() or None)
            if is_active is not None:
                updates.append("is_active = ?")
                values.append(1 if is_active else 0)

            updates.append("updated_at = ?")
            values.append(now)

            if len(updates) <= 1:
                conn.close()
                return False

            values.append(int(account_id))
            sql = f"UPDATE mail_accounts SET {', '.join(updates)} WHERE id = ?"
            self.execute_sql(cursor, sql, tuple(values))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_mail_account(self, account_id: int) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            self.execute_sql(cursor, "DELETE FROM mail_accounts WHERE id = ?", (int(account_id),))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def record_smtp_test(self, account_id: int, ok: bool, message: str) -> None:
        now = datetime.now().isoformat()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            self.execute_sql(
                cursor,
                "UPDATE mail_accounts SET last_test_at = ?, last_test_ok = ?, last_test_message = ?, updated_at = ? WHERE id = ?",
                (now, 1 if ok else 0, (message or "")[:2000], now, int(account_id)),
            )
            conn.commit()
        finally:
            conn.close()

    def record_dns_check(self, account_id: int, json_payload: str) -> None:
        now = datetime.now().isoformat()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            self.execute_sql(
                cursor,
                "UPDATE mail_accounts SET last_dns_check_at = ?, last_dns_check_json = ?, updated_at = ? WHERE id = ?",
                (now, json_payload, now, int(account_id)),
            )
            conn.commit()
        finally:
            conn.close()
