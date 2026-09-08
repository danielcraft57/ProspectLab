#!/usr/bin/env python3
"""Regenere design/mockups/emails/templates-bundle.js depuis emails-audit + emails-pub."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    """Ecrit le bundle JS des maquettes email."""
    root = Path(__file__).resolve().parents[1] / "design" / "mockups"
    pairs = []
    for folder in ("emails-audit", "emails-pub"):
        for path in sorted((root / folder).glob("*.html")):
            if path.name.lower() == "index.html":
                continue
            pairs.append((f"{folder}/{path.name}", path.read_text(encoding="utf-8")))

    out = root / "emails" / "templates-bundle.js"
    lines = [
        "// Auto-generated par scripts/build_emails_mockups_bundle.py",
        "window.EMAIL_TEMPLATES_BUNDLE = {",
    ]
    for key, html in pairs:
        lines.append(f"  {json.dumps(key)}: {json.dumps(html, ensure_ascii=False)},")
    lines.append("};")
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"OK: {len(pairs)} templates -> {out}")


if __name__ == "__main__":
    main()
