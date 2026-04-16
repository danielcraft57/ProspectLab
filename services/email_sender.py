"""
Service d'envoi d'emails de prospection
"""

import smtplib
from contextlib import contextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ajouter le répertoire parent au path pour importer config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS,
    MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
)


class EmailSender:
    def __init__(
        self,
        mail_server: Optional[str] = None,
        mail_port: Optional[int] = None,
        mail_use_tls: Optional[bool] = None,
        mail_use_ssl: bool = False,
        mail_username: Optional[str] = None,
        mail_password: Optional[str] = None,
        default_sender: Optional[str] = None,
        reply_to: Optional[str] = None,
    ):
        self.mail_server = mail_server if mail_server is not None else MAIL_SERVER
        self.mail_port = int(mail_port if mail_port is not None else MAIL_PORT)
        self.mail_use_tls = MAIL_USE_TLS if mail_use_tls is None else bool(mail_use_tls)
        self.mail_use_ssl = bool(mail_use_ssl)
        self.mail_username = mail_username if mail_username is not None else MAIL_USERNAME
        self.mail_password = mail_password if mail_password is not None else MAIL_PASSWORD
        self.default_sender = default_sender if default_sender is not None else MAIL_DEFAULT_SENDER
        self.reply_to = (reply_to or "").strip() or None

    @classmethod
    def from_mail_account(cls, row: Dict[str, Any]) -> "EmailSender":
        """Construit un expéditeur à partir d'une ligne mail_accounts (mot de passe en clair)."""
        return cls(
            mail_server=row.get("smtp_host"),
            mail_port=int(row.get("smtp_port") or 587),
            mail_use_tls=bool(int(row.get("smtp_use_tls", 1))),
            mail_use_ssl=bool(int(row.get("smtp_use_ssl", 0))),
            mail_username=row.get("smtp_username") or "",
            mail_password=row.get("smtp_password") or "",
            default_sender=row.get("default_sender"),
            reply_to=row.get("reply_to"),
        )

    @contextmanager
    def _smtp_session(self):
        if self.mail_use_ssl:
            server = smtplib.SMTP_SSL(self.mail_server, self.mail_port, timeout=30)
        else:
            server = smtplib.SMTP(self.mail_server, self.mail_port, timeout=30)
        try:
            server.ehlo()
            if not self.mail_use_ssl and self.mail_use_tls:
                server.starttls()
                server.ehlo()
            if self.mail_username:
                try:
                    server.login(self.mail_username, self.mail_password or "")
                except smtplib.SMTPNotSupportedError:
                    pass
            yield server
        finally:
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass

    def send_email(
        self,
        to,
        subject,
        body,
        recipient_name=None,
        html_body=None,
        tracking_token=None,
        reply_to=None,
    ):
        """
        Envoie un email

        Args:
            to: Adresse email du destinataire
            subject: Sujet de l'email
            body: Corps de l'email (texte)
            recipient_name: Nom du destinataire (optionnel)
            html_body: Corps HTML (optionnel)
            tracking_token: Token de tracking (optionnel, déjà injecté dans html_body)
            reply_to: Reply-To pour ce message (optionnel, sinon self.reply_to)

        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.default_sender
            msg["To"] = to
            msg["Subject"] = subject
            rt = (reply_to or "").strip() or self.reply_to
            if rt:
                msg["Reply-To"] = rt

            text_part = MIMEText(body, "plain", "utf-8")
            msg.attach(text_part)

            if html_body:
                html_part = MIMEText(html_body, "html", "utf-8")
                msg.attach(html_part)

            with self._smtp_session() as server:
                server.send_message(msg)

            return {
                "success": True,
                "message": f"Email envoyé avec succès à {to}",
            }

        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "message": "Erreur d'authentification. Vérifiez vos identifiants email.",
            }
        except smtplib.SMTPRecipientsRefused:
            return {
                "success": False,
                "message": f"Adresse email invalide: {to}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors de l'envoi: {str(e)}",
            }

    def send_bulk_emails(self, recipients, subject_template, body_template, delay=2):
        """
        Envoie plusieurs emails avec un délai entre chaque envoi

        Args:
            recipients: Liste de dicts {'email': str, 'nom': str, 'entreprise': str}
            subject_template: Template du sujet (peut contenir {nom}, {entreprise})
            body_template: Template du corps (peut contenir {nom}, {entreprise})
            delay: Délai en secondes entre chaque envoi

        Returns:
            list: Liste de résultats pour chaque destinataire
        """
        results = []

        for recipient in recipients:
            subject = subject_template.format(
                nom=recipient.get("nom", ""),
                entreprise=recipient.get("entreprise", ""),
            )
            body = body_template.format(
                nom=recipient.get("nom", ""),
                entreprise=recipient.get("entreprise", ""),
            )

            result = self.send_email(
                to=recipient["email"],
                subject=subject,
                body=body,
                recipient_name=recipient.get("nom"),
            )

            results.append(
                {
                    "email": recipient["email"],
                    "success": result["success"],
                    "message": result["message"],
                }
            )

            if delay > 0:
                import time

                time.sleep(delay)

        return results
