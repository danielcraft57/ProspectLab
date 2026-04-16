"""
Chiffrement réversible des secrets SMTP (dérivé de SECRET_KEY).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet_key_from_secret(secret: str) -> bytes:
    digest = hashlib.sha256((secret or "").encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_smtp_secret(plain: str, secret_key: str) -> str:
    if plain is None:
        return ""
    f = Fernet(_fernet_key_from_secret(secret_key))
    return f.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_smtp_secret(token: str, secret_key: str) -> str:
    if not token:
        return ""
    f = Fernet(_fernet_key_from_secret(secret_key))
    return f.decrypt(token.encode("ascii")).decode("utf-8")
