"""Construction des destinataires pour un plan hebdomadaire à partir d'un groupe."""
from __future__ import annotations

from typing import Any, Dict, List


def build_recipients_from_groupe(groupe_id: int) -> List[Dict[str, Any]]:
    """
    Charge tous les emails principaux des entreprises d'un groupe.

    @param groupe_id: ID du groupe
    @returns: Liste de dicts destinataires (email, nom, entreprise, entreprise_id)
    """
    from services.database.entreprises import EntrepriseManager

    em = EntrepriseManager()
    filters = {
        'groupe_ids': [int(groupe_id)],
        'principal_only': True,
        'exclude_risky': True,
        'exclude_placeholders': True,
    }
    recipients: List[Dict[str, Any]] = []
    offset = 0
    limit = 200

    while True:
        payload = em.get_entreprises_for_campagne(filters, limit=limit, offset=offset)
        items = payload.get('items') or []
        if not items:
            break
        for ent in items:
            for email_obj in ent.get('emails') or []:
                addr = (email_obj.get('email') or '').strip()
                if not addr or '@' not in addr:
                    continue
                recipients.append({
                    'email': addr,
                    'nom': (
                        email_obj.get('nom')
                        or email_obj.get('name_info')
                        or email_obj.get('email_nom')
                        or ''
                    ),
                    'entreprise': ent.get('nom') or '',
                    'entreprise_id': ent.get('id'),
                    'is_principal': bool(email_obj.get('is_principal')),
                    'is_person': bool(email_obj.get('is_person')),
                })
        total = int(payload.get('total') or 0)
        offset += len(items)
        if offset >= total:
            break

    return recipients
