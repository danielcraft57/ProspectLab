import argparse
import csv
import json
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
    SocialCampaignRunner,
    XDirectMessageProvider,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test envoi multicanal en lot depuis CSV (X/Meta + fallback)."
    )
    parser.add_argument("--csv", required=True, help="Chemin du fichier CSV d'entree.")
    parser.add_argument(
        "--default-order",
        default="x,meta",
        help="Ordre fallback par defaut (ex: x,meta ou meta,x).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simule les envois sans appeler les APIs.")
    parser.add_argument("--max-messages", type=int, default=None, help="Limite max de lignes traitees.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Pause entre messages (secondes).")
    parser.add_argument(
        "--output-json",
        default="",
        help="Chemin optionnel pour sauver le rapport detaille JSON.",
    )
    return parser.parse_args()


def parse_order(raw: str) -> list[ChannelName]:
    items = [x.strip().lower() for x in (raw or "").split(",") if x.strip()]
    order: list[ChannelName] = []
    for item in items:
        if item == "x":
            order.append(ChannelName.X)
        elif item in ("meta", "facebook"):
            order.append(ChannelName.FACEBOOK)
    return order or [ChannelName.X, ChannelName.FACEBOOK]


def build_rows(
    csv_path: str,
    default_order: list[ChannelName],
):
    """
    Colonnes attendues:
    - entreprise_id
    - body
    - x_recipient_id (optionnel)
    - meta_recipient_id (optionnel)
    - channel_order (optionnel: x,meta | meta,x)
    """
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entreprise_id = int((row.get("entreprise_id") or "0").strip() or "0")
            body = (row.get("body") or "").strip()
            if not body:
                continue

            payloads: dict[ChannelName, MessagePayload] = {}
            x_recipient = (row.get("x_recipient_id") or "").strip()
            meta_recipient = (row.get("meta_recipient_id") or "").strip()

            if x_recipient:
                payloads[ChannelName.X] = MessagePayload(
                    channel=ChannelName.X,
                    entreprise_id=entreprise_id,
                    recipient=x_recipient,
                    body=body,
                    metadata={"source": "scripts/tests/test_multicanal_batch.py"},
                )
            if meta_recipient:
                payloads[ChannelName.FACEBOOK] = MessagePayload(
                    channel=ChannelName.FACEBOOK,
                    entreprise_id=entreprise_id,
                    recipient=meta_recipient,
                    body=body,
                    metadata={"source": "scripts/tests/test_multicanal_batch.py"},
                )

            row_order = parse_order((row.get("channel_order") or "").strip()) or default_order
            yield (payloads, row_order)


def main() -> int:
    args = parse_args()

    service = MultiCanalService()
    service.register_provider(XDirectMessageProvider())
    service.register_provider(MetaMessengerProvider())

    runner = SocialCampaignRunner(service)
    report = runner.run(
        rows=build_rows(args.csv, parse_order(args.default_order)),
        dry_run=args.dry_run,
        max_messages=args.max_messages,
        sleep_seconds=args.sleep,
    )

    print("=== Rapport campagne multicanal ===")
    print(f"total_rows: {report.total_rows}")
    print(f"sent_ok: {report.sent_ok}")
    print(f"sent_failed: {report.sent_failed}")
    print(f"by_channel_success: {report.by_channel_success}")
    print(f"by_channel_failed: {report.by_channel_failed}")

    if args.output_json:
        data = {
            "total_rows": report.total_rows,
            "sent_ok": report.sent_ok,
            "sent_failed": report.sent_failed,
            "by_channel_success": report.by_channel_success,
            "by_channel_failed": report.by_channel_failed,
            "attempts": [
                {
                    "entreprise_id": a.entreprise_id,
                    "attempted_channels": [c.value for c in a.attempted_channels],
                    "result": {
                        "success": a.final_result.success,
                        "channel": a.final_result.channel.value,
                        "recipient": a.final_result.recipient,
                        "message_id": a.final_result.message_id,
                        "error": a.final_result.error,
                        "raw": a.final_result.raw,
                    },
                }
                for a in report.attempts
            ],
        }
        with open(args.output_json, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        print(f"Rapport detaille ecrit: {args.output_json}")

    return 0 if report.sent_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

