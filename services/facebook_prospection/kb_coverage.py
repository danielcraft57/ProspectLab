"""
Audit couverture Q/R : Qdrant vs catalogue API vs templates ProspectLab.
"""

from __future__ import annotations

from typing import Any

from config import VOCALGUARD_KB_PROFILE
from services.facebook_prospection.qdrant import FacebookProspectionQdrant
from services.facebook_prospection.reply_vars import INTENT_TEMPLATES, templates_for_tag
from services.facebook_prospection.vocalguard_client import list_intents, vocalguard_configured
from services.facebook_prospection.vocalguard_kb_db import list_intents_from_db, vocalguard_db_configured


def _catalog_index(profile: str | None = None) -> dict[str, dict[str, Any]]:
    """Index tag -> intent (Postgres VocalGuard prioritaire)."""
    out: dict[str, dict[str, Any]] = {}
    prof = profile or VOCALGUARD_KB_PROFILE
    items: list[dict[str, Any]] = []
    if vocalguard_db_configured():
        items = list_intents_from_db(profile=prof, enabled_only=False)
    if not items:
        items = list_intents(profile=prof)
    for item in items:
        tag = str(item.get('tag') or '').strip()
        if tag:
            out[tag] = item
    return out


def _intent_has_catalog_reply(intent: dict[str, Any] | None) -> bool:
    if not intent:
        return False
    for row in intent.get('responses') or []:
        if isinstance(row, str) and row.strip():
            return True
        if isinstance(row, dict) and str(row.get('text') or '').strip():
            return True
    return False


def kb_coverage_report(*, profile: str | None = None) -> dict[str, Any]:
    """
    Rapport lisible pour revoir les Q/R manquantes.

    @param profile: Profil KB
    @returns: tags, gaps, stats
    """
    prof = profile or VOCALGUARD_KB_PROFILE or 'outbound_commercial'
    store = FacebookProspectionQdrant(profile=prof)
    qdrant_tags = sorted(store.list_intent_tags())
    catalog = _catalog_index(prof)
    local_tags = sorted(INTENT_TEMPLATES.keys())

    all_tags = sorted(set(qdrant_tags) | set(catalog.keys()) | set(local_tags))
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for tag in all_tags:
        in_qdrant = tag in qdrant_tags
        has_catalog = _intent_has_catalog_reply(catalog.get(tag))
        has_template = bool(templates_for_tag(tag))
        ok = has_catalog or has_template
        row = {
            'tag': tag,
            'in_qdrant': in_qdrant,
            'has_catalog_reply': has_catalog,
            'has_local_template': has_template,
            'template_variants': len(templates_for_tag(tag)),
            'ok_for_sandbox': ok,
        }
        rows.append(row)
        if in_qdrant and not ok:
            gaps.append(row)

    return {
        'profile': prof,
        'catalog_configured': vocalguard_db_configured() or vocalguard_configured(),
        'catalog_intent_count': len(catalog),
        'qdrant_ok': bool(store.enabled() and (store.collection_info() or {}).get('ok')),
        'qdrant_tag_count': len(qdrant_tags),
        'local_template_tags': local_tags,
        'gap_count': len(gaps),
        'gaps': gaps[:80],
        'tags': rows,
    }
