#!/usr/bin/env python3
"""Filtrage serveur des destinataires de campagne avant envoi."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from utils.email_quality import is_campaign_risky_email
from utils.campaign_exclusions import (
    is_recipient_excluded,
    load_campaign_exclusion_data,
)


def filter_campagne_recipients(
    recipients: Optional[List[Dict[str, Any]]],
    *,
    exclude_risky: bool = True,
    max_emails_per_entreprise: int = 2,
    exclude_unreachable: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Filtre une liste de destinataires avant creation / relance de campagne.

    Applique :
    - exclusion désabonnés / bounces (entreprise entière + email bounce)
    - exclusion des emails a risque (gouv / SaaS / support / placeholder)
    - plafond d'emails par entreprise (priorite : deja principal si marque, sinon ordre d'arrivee)

    @param recipients: Liste de dicts ``{email, nom, entreprise, entreprise_id, ...}``
    @param exclude_risky: Activer le filtre ``is_campaign_risky_email``
    @param max_emails_per_entreprise: Max d'adresses par entreprise (0 = illimite)
    @param exclude_unreachable: Exclure désabonnés, bounces entreprise/email
    @returns: Tuple (destinataires filtrés, stats)
    """
    stats = {
        'input': 0,
        'dropped_risky': 0,
        'dropped_cap': 0,
        'dropped_dup': 0,
        'dropped_unreachable': 0,
        'output': 0,
    }
    if not recipients:
        return [], stats

    exclusion_data: Dict[str, Any] = {}
    excluded_entreprise_ids: Set[int] = set()
    bounced_emails: Set[str] = set()
    if exclude_unreachable:
        ent_ids = [r.get('entreprise_id') for r in recipients if isinstance(r, dict)]
        emails = [(r.get('email') or '') for r in recipients if isinstance(r, dict)]
        exclusion_data = load_campaign_exclusion_data(ent_ids, emails)
        excluded_entreprise_ids = exclusion_data.get('excluded_entreprise_ids') or set()
        bounced_emails = exclusion_data.get('bounced_emails') or set()

    cleaned: List[Dict[str, Any]] = []
    seen_emails = set()
    for raw in recipients:
        if not isinstance(raw, dict):
            continue
        stats['input'] += 1
        email = (raw.get('email') or '').strip()
        if not email or '@' not in email:
            stats['dropped_risky'] += 1
            continue
        key = email.lower()
        if key in seen_emails:
            stats['dropped_dup'] += 1
            continue

        if exclude_unreachable:
            excluded, _reason = is_recipient_excluded(
                raw,
                excluded_entreprise_ids=excluded_entreprise_ids,
                bounced_emails=bounced_emails,
            )
            if excluded:
                stats['dropped_unreachable'] += 1
                continue

        if exclude_risky and is_campaign_risky_email(email):
            stats['dropped_risky'] += 1
            continue
        seen_emails.add(key)
        cleaned.append(dict(raw))

    if max_emails_per_entreprise and max_emails_per_entreprise > 0:
        by_ent: Dict[Any, List[Dict[str, Any]]] = {}
        order: List[Any] = []
        for rec in cleaned:
            ent_key = rec.get('entreprise_id')
            if ent_key is None:
                ent_key = (rec.get('entreprise') or '').strip().lower() or f"email:{rec.get('email')}"
            if ent_key not in by_ent:
                by_ent[ent_key] = []
                order.append(ent_key)
            by_ent[ent_key].append(rec)

        capped: List[Dict[str, Any]] = []
        for ent_key in order:
            group = by_ent[ent_key]
            ranked = sorted(
                group,
                key=lambda r: (
                    0 if r.get('is_principal') else 1,
                    0 if r.get('is_person') else 1,
                    (r.get('email') or '').lower(),
                ),
            )
            keep = ranked[: max_emails_per_entreprise]
            stats['dropped_cap'] += max(0, len(ranked) - len(keep))
            capped.extend(keep)
        cleaned = capped

    stats['output'] = len(cleaned)
    return cleaned, stats
