from __future__ import annotations

import re
from pathlib import Path


INCLUDE_PATTERNS: list[re.Pattern[str]] = [
    # {#include:footer_standard}
    re.compile(r"\{#include:([a-zA-Z0-9_\-]+)\}"),
    # {#include_footer_standard}
    re.compile(r"\{#include_([a-zA-Z0-9_\-]+)\}"),
]


def expand_includes(content: str, fragments_dir: Path, *, max_depth: int = 8) -> str:
    """
    Remplace les directives d'include par le contenu des fragments.
    Supporte les fragments imbriqués (récursif) avec une profondeur max.

    Fragments:
      template_studio/fragments/<name>.html
    """
    if not isinstance(content, str) or "{#include" not in content:
        return content

    if not fragments_dir.exists():
        return content

    def load_fragment(fragment_name: str) -> str:
        fragment_file = fragments_dir / f"{fragment_name}.html"
        if not fragment_file.exists():
            return ""
        return fragment_file.read_text(encoding="utf-8")

    out = content
    for _ in range(max_depth):
        if "{#include" not in out:
            break

        before = out
        for pat in INCLUDE_PATTERNS:
            out = pat.sub(lambda m: load_fragment(m.group(1)), out)

        if out == before:
            break

    return out

