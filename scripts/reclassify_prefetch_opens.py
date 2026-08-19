#!/usr/bin/env python3
"""
Reclasse les faux opens de tracking (prefetch, scanners, Apple MPP, burst IP).

Par defaut: dry-run. Passer --apply pour ecrire en base.

Usage:
    python scripts/reclassify_prefetch_opens.py
    python scripts/reclassify_prefetch_opens.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_args() -> argparse.Namespace:
    """
    Parse les arguments CLI.

    @returns: Arguments
    """
    parser = argparse.ArgumentParser(
        description="Reclasse les ouvertures automatiques du pixel de tracking.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ecrit en base (sinon dry-run).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre max d'events open a examiner.",
    )
    return parser.parse_args()


def _load_env_if_present() -> None:
    """
    Charge le fichier .env local s'il existe.
    """
    root = Path(__file__).parent.parent
    env_path = root / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=str(env_path), override=False)
        return
    except Exception:
        pass
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    """
    Point d'entree du reclassement.

    @returns: Code retour (0 = ok)
    """
    args = parse_args()
    _load_env_if_present()

    from services.database import Database

    db = Database()
    result = db.reclassify_prefetch_opens(limit=args.limit, dry_run=not args.apply)
    print("=== Reclassement prefetch / faux opens ===")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if not args.apply:
        print("Dry-run: rien n'a ete ecrit. Relancer avec --apply pour appliquer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
