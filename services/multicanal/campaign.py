from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from .dispatcher import MultiCanalService
from .types import ChannelName, MessagePayload, SendResult


@dataclass
class CampaignAttempt:
    """
    Résultat d'une tentative d'envoi pour une ligne de campagne.
    """

    entreprise_id: int
    attempted_channels: list[ChannelName]
    final_result: SendResult


@dataclass
class CampaignReport:
    """
    Rapport synthétique d'exécution d'une campagne multicanal.
    """

    total_rows: int
    sent_ok: int
    sent_failed: int
    by_channel_success: dict[str, int]
    by_channel_failed: dict[str, int]
    attempts: list[CampaignAttempt]


class SocialCampaignRunner:
    """
    Exécute des envois multicanaux avec fallback ordonné.
    """

    def __init__(self, service: MultiCanalService) -> None:
        self.service = service

    def send_with_fallback(
        self,
        payloads_by_channel: dict[ChannelName, MessagePayload],
        preferred_order: list[ChannelName],
        dry_run: bool = False,
    ) -> CampaignAttempt:
        attempted: list[ChannelName] = []
        last_failure: SendResult | None = None
        entreprise_id = 0

        for channel in preferred_order:
            payload = payloads_by_channel.get(channel)
            if not payload:
                continue
            entreprise_id = payload.entreprise_id
            attempted.append(channel)

            if dry_run:
                return CampaignAttempt(
                    entreprise_id=payload.entreprise_id,
                    attempted_channels=attempted,
                    final_result=SendResult(
                        success=True,
                        channel=channel,
                        recipient=payload.recipient,
                        message_id="dry-run",
                        raw={"dry_run": True},
                    ),
                )

            result = self.service.send_one(payload)
            if result.success:
                return CampaignAttempt(
                    entreprise_id=payload.entreprise_id,
                    attempted_channels=attempted,
                    final_result=result,
                )
            last_failure = result

        if last_failure:
            return CampaignAttempt(
                entreprise_id=entreprise_id,
                attempted_channels=attempted,
                final_result=last_failure,
            )

        # Aucun canal utilisable pour cette ligne
        return CampaignAttempt(
            entreprise_id=entreprise_id,
            attempted_channels=attempted,
            final_result=SendResult(
                success=False,
                channel=preferred_order[0] if preferred_order else ChannelName.X,
                recipient="",
                error="Aucun payload valide pour les canaux demandés.",
            ),
        )

    def run(
        self,
        rows: Iterable[tuple[dict[ChannelName, MessagePayload], list[ChannelName]]],
        dry_run: bool = False,
        max_messages: int | None = None,
        sleep_seconds: float = 0.0,
    ) -> CampaignReport:
        attempts: list[CampaignAttempt] = []
        by_success: dict[str, int] = {}
        by_failed: dict[str, int] = {}

        total_rows = 0
        for payloads_by_channel, preferred_order in rows:
            total_rows += 1
            if max_messages is not None and len(attempts) >= max_messages:
                break

            attempt = self.send_with_fallback(
                payloads_by_channel=payloads_by_channel,
                preferred_order=preferred_order,
                dry_run=dry_run,
            )
            attempts.append(attempt)

            key = attempt.final_result.channel.value
            if attempt.final_result.success:
                by_success[key] = by_success.get(key, 0) + 1
            else:
                by_failed[key] = by_failed.get(key, 0) + 1

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        sent_ok = sum(by_success.values())
        sent_failed = sum(by_failed.values())
        return CampaignReport(
            total_rows=total_rows,
            sent_ok=sent_ok,
            sent_failed=sent_failed,
            by_channel_success=by_success,
            by_channel_failed=by_failed,
            attempts=attempts,
        )

