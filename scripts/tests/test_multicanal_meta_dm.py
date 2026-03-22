import argparse
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

from services.multicanal import ChannelName, MessagePayload, MetaMessengerProvider, MultiCanalService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test d'envoi DM Meta Messenger via services.multicanal."
    )
    parser.add_argument(
        "--recipient-id",
        required=True,
        help="PSID Meta du destinataire.",
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    service = MultiCanalService()
    service.register_provider(MetaMessengerProvider())

    payload = MessagePayload(
        channel=ChannelName.FACEBOOK,
        entreprise_id=args.entreprise_id,
        recipient=str(args.recipient_id),
        body=args.body,
        metadata={"source": "scripts/tests/test_multicanal_meta_dm.py"},
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

