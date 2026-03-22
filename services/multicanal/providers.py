from __future__ import annotations

import os
import requests

from .dispatcher import ChannelProviderProtocol
from .types import ChannelName, MessagePayload, SendResult


class DummyProvider(ChannelProviderProtocol):
    """
    Provider de test pour valider le flux multicanal sans appeler d'API externe.
    """

    def __init__(self, channel_name: ChannelName) -> None:
        self.channel_name = channel_name

    def send(self, payload: MessagePayload) -> SendResult:
        return SendResult(
            success=True,
            channel=self.channel_name,
            recipient=payload.recipient,
            message_id=f"dummy-{self.channel_name.value}-{payload.entreprise_id}",
            raw={"note": "Envoi simulé (dummy provider)."},
        )


class XDirectMessageProvider(ChannelProviderProtocol):
    """
    Provider X (Twitter) pour l'envoi de messages privés.

    Ce provider utilise Tweepy + OAuth1.

    Variables d'environnement attendues:
    - X_API_KEY
    - X_API_SECRET
    - X_ACCESS_TOKEN
    - X_ACCESS_TOKEN_SECRET
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
    ) -> None:
        self.channel_name = ChannelName.X
        self.api_key = api_key or os.getenv("X_API_KEY")
        self.api_secret = api_secret or os.getenv("X_API_SECRET")
        self.access_token = access_token or os.getenv("X_ACCESS_TOKEN")
        self.access_token_secret = access_token_secret or os.getenv("X_ACCESS_TOKEN_SECRET")

    def _build_api_client(self):
        try:
            import tweepy
        except Exception as exc:  # pragma: no cover - dépendance externe
            raise RuntimeError("Le package `tweepy` est requis pour XDirectMessageProvider.") from exc

        missing = [
            name
            for name, value in (
                ("X_API_KEY", self.api_key),
                ("X_API_SECRET", self.api_secret),
                ("X_ACCESS_TOKEN", self.access_token),
                ("X_ACCESS_TOKEN_SECRET", self.access_token_secret),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Variables X manquantes: {', '.join(missing)}")

        auth = tweepy.OAuth1UserHandler(
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_token_secret,
        )
        return tweepy.API(auth)

    def send(self, payload: MessagePayload) -> SendResult:
        """
        Envoie un message privé X à un user_id.

        Notes:
        - `payload.recipient` doit être l'ID utilisateur X (numérique).
        - Le compte expéditeur doit être autorisé à DM ce destinataire.
        """
        try:
            api = self._build_api_client()
            if not payload.recipient or not str(payload.recipient).strip().isdigit():
                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    recipient=payload.recipient,
                    error="Le recipient X doit être un user_id numérique.",
                )

            text = (payload.body or "").strip()
            if not text:
                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    recipient=payload.recipient,
                    error="Le corps du message est vide.",
                )

            response = api.send_direct_message(recipient_id=str(payload.recipient), text=text)
            message_id = getattr(response, "id", None)
            return SendResult(
                success=True,
                channel=self.channel_name,
                recipient=str(payload.recipient),
                message_id=str(message_id) if message_id is not None else None,
                raw={"provider": "x", "response_type": str(type(response).__name__)},
            )
        except Exception as exc:
            return SendResult(
                success=False,
                channel=self.channel_name,
                recipient=str(payload.recipient),
                error=str(exc),
            )


class MetaMessengerProvider(ChannelProviderProtocol):
    """
    Provider Meta Messenger (Facebook/Instagram via Graph API).

    Variables d'environnement attendues:
    - META_PAGE_ID
    - META_PAGE_ACCESS_TOKEN
    - META_GRAPH_API_VERSION (optionnel, défaut: v20.0)

    Notes:
    - `payload.recipient` doit être le PSID (Page Scoped ID).
    - Le compte/page doit être autorisé à contacter ce destinataire.
    """

    def __init__(
        self,
        page_id: str | None = None,
        page_access_token: str | None = None,
        graph_api_version: str | None = None,
    ) -> None:
        self.channel_name = ChannelName.FACEBOOK
        self.page_id = page_id or os.getenv("META_PAGE_ID")
        self.page_access_token = page_access_token or os.getenv("META_PAGE_ACCESS_TOKEN")
        self.graph_api_version = graph_api_version or os.getenv("META_GRAPH_API_VERSION", "v20.0")

    def send(self, payload: MessagePayload) -> SendResult:
        try:
            missing = [
                name
                for name, value in (
                    ("META_PAGE_ID", self.page_id),
                    ("META_PAGE_ACCESS_TOKEN", self.page_access_token),
                )
                if not value
            ]
            if missing:
                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    recipient=payload.recipient,
                    error=f"Variables Meta manquantes: {', '.join(missing)}",
                )

            recipient = (payload.recipient or "").strip()
            text = (payload.body or "").strip()
            if not recipient:
                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    recipient=payload.recipient,
                    error="Le recipient Meta (PSID) est requis.",
                )
            if not text:
                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    recipient=payload.recipient,
                    error="Le corps du message est vide.",
                )

            url = f"https://graph.facebook.com/{self.graph_api_version}/{self.page_id}/messages"
            body = {
                "recipient": {"id": recipient},
                "messaging_type": "MESSAGE_TAG",
                "tag": "ACCOUNT_UPDATE",
                "message": {"text": text},
            }
            params = {"access_token": self.page_access_token}
            response = requests.post(url, params=params, json=body, timeout=20)

            try:
                data = response.json()
            except Exception:
                data = {"raw_text": response.text}

            if response.status_code >= 400:
                error = data.get("error", {}) if isinstance(data, dict) else {}
                message = error.get("message") or f"Erreur HTTP {response.status_code}"
                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    recipient=recipient,
                    error=str(message),
                    raw=data if isinstance(data, dict) else {"response": data},
                )

            message_id = data.get("message_id") if isinstance(data, dict) else None
            return SendResult(
                success=True,
                channel=self.channel_name,
                recipient=recipient,
                message_id=str(message_id) if message_id else None,
                raw=data if isinstance(data, dict) else {"response": data},
            )
        except Exception as exc:
            return SendResult(
                success=False,
                channel=self.channel_name,
                recipient=str(payload.recipient),
                error=str(exc),
            )

