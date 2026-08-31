"""Métadonnées de ciblage persistées dans campaign_params_json."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def normalize_groupe_ids(raw: Any) -> List[int]:
    """Normalise une liste d'IDs de groupes."""
    if raw is None:
        return []
    if isinstance(raw, (int, str)):
        try:
            return [int(raw)]
        except (TypeError, ValueError):
            return []
    if isinstance(raw, list):
        out = []
        for item in raw:
            try:
                if item is not None:
                    out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out
    return []


def extract_groupe_ids_from_payload(data: Optional[Dict[str, Any]]) -> List[int]:
    """
    Extrait groupe_ids depuis le payload API (racine ou snapshot ciblage).

    @param data: Body JSON de création campagne
    @returns: Liste d'IDs groupes
    """
    if not data:
        return []
    ids = normalize_groupe_ids(data.get('groupe_ids'))
    if ids:
        return ids
    ciblage = data.get('ciblage') or {}
    if not isinstance(ciblage, dict):
        return []
    ids = normalize_groupe_ids(ciblage.get('groupe_ids'))
    if ids:
        return ids
    criteres = ciblage.get('criteres') or {}
    if isinstance(criteres, dict):
        return normalize_groupe_ids(criteres.get('groupe_ids'))
    return []


def build_campaign_params(
    *,
    recipients: List[Dict[str, Any]],
    template_id: Optional[str],
    subject: str,
    delay: int = 2,
    mail_account_id=None,
    custom_message: Optional[str] = None,
    groupe_ids: Optional[List[int]] = None,
    ciblage: Optional[Dict[str, Any]] = None,
    plan_hebdo_id: Optional[int] = None,
    slot_index: Optional[int] = None,
    rotation_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Construit le dict campaign_params_json standard."""
    params: Dict[str, Any] = {
        'recipients': recipients,
        'template_id': template_id,
        'subject': subject,
        'delay': delay,
        'mail_account_id': mail_account_id,
    }
    if custom_message:
        params['custom_message'] = custom_message
    if groupe_ids:
        params['groupe_ids'] = groupe_ids
    if ciblage:
        params['ciblage'] = ciblage
    if plan_hebdo_id is not None:
        params['plan_hebdo_id'] = plan_hebdo_id
    if slot_index is not None:
        params['slot_index'] = slot_index
    if rotation_mode:
        params['rotation_mode'] = rotation_mode
    return params


def enrich_campagne_from_params(campagne: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrichit une campagne API avec groupe_ids, plan, ciblage depuis campaign_params_json.

    @param campagne: Dict campagne BDD
    @returns: Même dict enrichi
    """
    import json

    if not campagne:
        return campagne

    params = {}
    raw = campagne.get('campaign_params_json')
    if raw:
        try:
            params = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            params = {}

    groupe_ids = normalize_groupe_ids(params.get('groupe_ids'))
    if not groupe_ids and params.get('groupe_id') is not None:
        groupe_ids = normalize_groupe_ids([params.get('groupe_id')])

    campagne['groupe_ids'] = groupe_ids
    campagne['plan_hebdo_id'] = campagne.get('plan_hebdo_id') or params.get('plan_hebdo_id')
    campagne['rotation_mode'] = params.get('rotation_mode')
    campagne['slot_index'] = params.get('slot_index')
    campagne['ciblage'] = params.get('ciblage')
    return campagne
