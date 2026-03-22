from __future__ import annotations

from typing import Iterable

from .types import ChannelName, MessagePayload, SendResult


class ChannelProviderProtocol:
    """
    Contrat minimal d'un provider de canal.

    Un provider concret (ex: LinkedIn, Meta, X) doit exposer:
    - channel_name
    - send(payload) -> SendResult
    """

    channel_name: ChannelName

    def send(self, payload: MessagePayload) -> SendResult:  # pragma: no cover - interface
        raise NotImplementedError


class MultiCanalService:
    """
    Orchestrateur simple des envois multicanaux.
    """

    def __init__(self) -> None:
        self._providers: dict[ChannelName, ChannelProviderProtocol] = {}

    def register_provider(self, provider: ChannelProviderProtocol) -> None:
        self._providers[provider.channel_name] = provider

    def can_send(self, channel: ChannelName) -> bool:
        return channel in self._providers

    def send_one(self, payload: MessagePayload) -> SendResult:
        provider = self._providers.get(payload.channel)
        if not provider:
            return SendResult(
                success=False,
                channel=payload.channel,
                recipient=payload.recipient,
                error=f"Canal non configuré: {payload.channel.value}",
            )
        return provider.send(payload)

    def send_batch(self, payloads: Iterable[MessagePayload]) -> list[SendResult]:
        return [self.send_one(payload) for payload in payloads]

