#!/usr/bin/env python3
"""Rebuild overlay sans tables incompatibles avec le schema avril."""
from __future__ import annotations

import gzip
import os
import re

SRC = r"c:\Users\loicDaniel\Projects\ProspectLab\backups\prospectlab_resilient_20260912_062430.sql.gz"
OUT = r"c:\Users\loicDaniel\Projects\ProspectLab\backups\overlay_safe_20260912.sql"

# Eviter campagnes_email (schema plus recent) et tables qui cascade-wipe emails
WANT = {
    "users",
    "personnes",
    "personnes_data_breaches",
    "personnes_family",
    "personnes_hobbies",
    "personnes_locations",
    "personnes_osint_details",
    "personnes_photos",
    "personnes_professional_history",
    "mail_accounts",
    "api_tokens",
    "application_clients",
    "segments_ciblage",
    "plans_campagne_hebdo",
    "inbox_events",
    "entreprise_touchpoints",
    "mobile_expo_push_registrations",
}


def main() -> None:
    text = gzip.open(SRC, "rt", encoding="utf-8", errors="replace").read()
    parts: list[tuple[str, str]] = []
    for match in re.finditer(r"^COPY public\.(\w+) .*?FROM stdin;\n", text, re.M):
        name = match.group(1)
        if name not in WANT:
            continue
        start = match.start()
        end = text.find("\n\\.\n", start)
        if end < 0:
            print(f"SKIP incomplete {name}")
            continue
        end = end + 4
        parts.append((name, text[start:end]))
        print(f"KEEP {name} bytes={end - start}")

    header = (
        "SET client_encoding = 'UTF8';\n"
        "SET standard_conforming_strings = on;\n"
        "SET check_function_bodies = false;\n\n"
    )
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(header)
        for name, block in parts:
            # Pour users/personnes: TRUNCATE ok. Pas de CASCADE large.
            if name == "users":
                handle.write("TRUNCATE TABLE public.users CASCADE;\n")
            elif name.startswith("personnes"):
                handle.write(f"TRUNCATE TABLE public.{name};\n")
            elif name == "personnes":
                handle.write("TRUNCATE TABLE public.personnes CASCADE;\n")
            else:
                handle.write(f"TRUNCATE TABLE public.{name} CASCADE;\n")
            handle.write(block)
            handle.write("\n")

    print(f"OUT {OUT} SIZE={os.path.getsize(OUT)}")


if __name__ == "__main__":
    main()
