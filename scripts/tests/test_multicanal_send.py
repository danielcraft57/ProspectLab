import argparse
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_project_root))

# Charger .env depuis la racine du projet
try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

from services.multicanal import (
    ChannelName,
    MessagePayload,
    MetaMessengerProvider,
    MultiCanalService,
    XDirectMessageProvider,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test multicanal (X ou Meta) via services.multicanal."
    )
    parser.add_argument(
        "--channel",
        required=True,
        choices=["x", "meta"],
        help="Canal de test: x ou meta.",
    )
    parser.add_argument(
        "--recipient-id",
        required=True,
        help="ID destinataire (X user_id ou Meta PSID).",
    )
    parser.add_argument(
        "--body",
        required=True,
        help="Texte du message prive a envoyer.",
    )
    parser.add_argument(
        "--entreprise-id",
        type=int,
        default=0,
        help="ID entreprise associe (defaut: 0).",
    )
    return parser


def resolve_channel(value: str) -> ChannelName:
    if value == "x":
        return ChannelName.X
    return ChannelName.FACEBOOK


def register_provider(service: MultiCanalService, channel: ChannelName) -> None:
    if channel == ChannelName.X:
        service.register_provider(XDirectMessageProvider())
        return
    if channel == ChannelName.FACEBOOK:
        service.register_provider(MetaMessengerProvider())
        return
    raise ValueError(f"Canal non supporte: {channel}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    channel = resolve_channel(args.channel)
    service = MultiCanalService()
    register_provider(service, channel)

    payload = MessagePayload(
        channel=channel,
        entreprise_id=args.entreprise_id,
        recipient=str(args.recipient_id),
        body=args.body,
        metadata={"source": "scripts/tests/test_multicanal_send.py"},
    )
    result = service.send_one(payload)

    print(f"success: {result.success}")
    print(f"channel: {result.channel.value}")
    print(f"recipient: {result.recipient}")
    print(f"message_id: {result.message_id}")
    print(f"error: {result.error}")
    print(f"raw: {result.raw}")

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())

