from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChannelName(str, Enum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    X = "x"


@dataclass
class MessagePayload:
    """
    Charge utile standard pour un envoi multicanal.
    """

    channel: ChannelName
    entreprise_id: int
    recipient: str
    subject: str | None = None
    body: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SendResult:
    """
    Résultat normalisé d'un envoi sur un canal.
    """

    success: bool
    channel: ChannelName
    recipient: str
    message_id: str | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None

