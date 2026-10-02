#!/usr/bin/env python3
"""Extrait campagnes/emails depuis le dump avril pour repair apres wipe."""
from __future__ import annotations

import gzip
import os
import re

SRC = r"c:\Users\loicDaniel\Projects\ProspectLab\backups\prospectlab_backup_20260428_185627.sql.gz"
OUT = r"c:\Users\loicDaniel\Projects\ProspectLab\backups\repair_emails_from_avril.sql"

WANT = {
    "campagnes_email",
    "emails_envoyes",
    "email_tracking_events",
    "email_templates",
}


def main() -> None:
    print("Scanning april dump (large)...")
    parts: list[tuple[str, str]] = []
    # Stream to avoid loading 5GB in RAM if possible - but need full blocks.
    # For these tables sizes are moderate; scan line by line.
    current = None
    buf: list[str] = []
    with gzip.open(SRC, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if current is None:
                match = re.match(r"^COPY public\.(\w+) .*FROM stdin;\n$", line)
                if match and match.group(1) in WANT:
                    current = match.group(1)
                    buf = [line]
                continue
            buf.append(line)
            if line == "\\.\n":
                parts.append((current, "".join(buf)))
                print(f"FOUND {current} lines={len(buf)}")
                current = None
                buf = []
                if {n for n, _ in parts} >= WANT:
                    break

    header = (
        "SET client_encoding = 'UTF8';\n"
        "SET standard_conforming_strings = on;\n\n"
    )
    with open(OUT, "w", encoding="utf-8", newline="\n") as out:
        out.write(header)
        # order: templates -> campagnes -> emails -> tracking
        order = ["email_templates", "campagnes_email", "emails_envoyes", "email_tracking_events"]
        by_name = dict(parts)
        for name in order:
            if name not in by_name:
                print(f"MISSING {name}")
                continue
            out.write(f"TRUNCATE TABLE public.{name} CASCADE;\n")
            out.write(by_name[name])
            out.write("\n")
    print(f"OUT {OUT} SIZE={os.path.getsize(OUT)}")


if __name__ == "__main__":
    main()
