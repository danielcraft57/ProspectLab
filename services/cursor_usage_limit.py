"""
Détection des erreurs « usage limit » de l'agent Cursor (serv1).
"""

from __future__ import annotations

CURSOR_USAGE_LIMIT_MARKERS = (
    'usage limit',
    'hit your usage limit',
    'get cursor pro',
    'free plan',
    'quota',
)


class CursorUsageLimitError(RuntimeError):
    """Le compte Cursor distant a atteint sa limite — reprise manuelle après recharge."""

    def __init__(self, message: str = 'Cursor usage limit', *, detail: str = ''):
        super().__init__(message)
        self.detail = detail or message


def contains_cursor_usage_limit(text: str) -> bool:
    low = (text or '').lower()
    return any(marker in low for marker in CURSOR_USAGE_LIMIT_MARKERS)
