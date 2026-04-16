"""
Tests de connexion SMTP (sans envoi de message).
"""

from __future__ import annotations

import smtplib
from typing import Any, Dict, Optional


def probe_smtp(
    host: str,
    port: int,
    use_tls: bool,
    use_ssl: bool,
    username: Optional[str],
    password: Optional[str],
    timeout: float = 25.0,
) -> Dict[str, Any]:
    """
    Ouvre une session SMTP, optionnellement STARTTLS ou SSL implicite, tente login si username.

    Returns:
        dict avec success (bool), message (str), detail (str optionnel)
    """
    server = None
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, int(port), timeout=timeout)
        else:
            server = smtplib.SMTP(host, int(port), timeout=timeout)
        server.ehlo()
        if not use_ssl and use_tls:
            server.starttls()
            server.ehlo()
        if username:
            try:
                server.login(username, password or "")
            except smtplib.SMTPNotSupportedError:
                pass
        try:
            server.noop()
        except Exception:
            pass
        return {"success": True, "message": "Connexion SMTP et authentification OK."}
    except smtplib.SMTPAuthenticationError as e:
        return {
            "success": False,
            "message": "Échec d'authentification SMTP.",
            "detail": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Impossible de joindre ou de négocier la session SMTP.",
            "detail": str(e),
        }
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass
