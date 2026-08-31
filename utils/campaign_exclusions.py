"""Exclusions campagne : désabonnés, bounces, entreprises non joignables."""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

# Statuts entreprise : exclusion de toute l'entreprise
EXCLUDED_ENTREPRISE_STATUTS: Tuple[str, ...] = (
    'Désabonné',
    'Bounce',
    'Plainte spam',
    'Ne pas contacter',
)

# Tags entreprise impliquant exclusion (bounce / désabonnement enregistré)
EXCLUDED_ENTREPRISE_TAGS: Tuple[str, ...] = (
    'bounce',
    'email_invalide',
    'desabonne',
)


def entreprise_statut_excluded(statut: Optional[str]) -> bool:
    """True si le statut CRM exclut l'entreprise des campagnes."""
    if not statut:
        return False
    return str(statut).strip() in EXCLUDED_ENTREPRISE_STATUTS


def entreprise_tags_excluded(tags_raw: Any) -> bool:
    """True si les tags JSON contiennent bounce / email_invalide."""
    if not tags_raw:
        return False
    import json

    tags: List[str] = []
    if isinstance(tags_raw, list):
        tags = [str(t).lower() for t in tags_raw]
    elif isinstance(tags_raw, str):
        raw = tags_raw.strip()
        if raw.startswith('['):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    tags = [str(t).lower() for t in parsed]
            except (json.JSONDecodeError, TypeError):
                tags = [raw.lower()]
        else:
            tags = [raw.lower()]
    for tag in tags:
        if tag in EXCLUDED_ENTREPRISE_TAGS:
            return True
    return False


def load_campaign_exclusion_data(
    entreprise_ids: Optional[Iterable[Any]] = None,
    emails: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Charge en lot les données d'exclusion depuis la BDD.

    @returns: dict avec excluded_entreprise_ids, bounced_emails
    """
    from services.database.base import DatabaseBase

    db = DatabaseBase()
    conn = db.get_connection()
    cursor = conn.cursor()

    excluded_entreprise_ids: Set[int] = set()
    bounced_emails: Set[str] = set()

    ent_ids = sorted({int(x) for x in (entreprise_ids or []) if x is not None})
    if ent_ids:
        chunk_size = 400
        for i in range(0, len(ent_ids), chunk_size):
            chunk = ent_ids[i:i + chunk_size]
            placeholders = ','.join(['?' for _ in chunk])
            db.execute_sql(
                cursor,
                f'''
                SELECT id, statut, tags
                FROM entreprises
                WHERE id IN ({placeholders})
                ''',
                tuple(chunk),
            )
            for row in cursor.fetchall():
                r = dict(row)
                eid = r.get('id')
                if eid is None:
                    continue
                if entreprise_statut_excluded(r.get('statut')) or entreprise_tags_excluded(r.get('tags')):
                    excluded_entreprise_ids.add(int(eid))

        for i in range(0, len(ent_ids), chunk_size):
            chunk = ent_ids[i:i + chunk_size]
            placeholders = ','.join(['?' for _ in chunk])
            db.execute_sql(
                cursor,
                f'''
                SELECT DISTINCT entreprise_id
                FROM emails_envoyes
                WHERE entreprise_id IN ({placeholders})
                  AND statut = 'bounced'
                ''',
                tuple(chunk),
            )
            for row in cursor.fetchall():
                r = dict(row)
                if r.get('entreprise_id') is not None:
                    excluded_entreprise_ids.add(int(r['entreprise_id']))

    email_list = sorted({(e or '').strip().lower() for e in (emails or []) if e and '@' in str(e)})
    if email_list:
        chunk_size = 400
        for i in range(0, len(email_list), chunk_size):
            chunk = email_list[i:i + chunk_size]
            placeholders = ','.join(['?' for _ in chunk])
            db.execute_sql(
                cursor,
                f'''
                SELECT DISTINCT LOWER(TRIM(email)) AS email
                FROM emails_envoyes
                WHERE LOWER(TRIM(email)) IN ({placeholders})
                  AND statut = 'bounced'
                ''',
                tuple(chunk),
            )
            for row in cursor.fetchall():
                r = dict(row)
                if r.get('email'):
                    bounced_emails.add(str(r['email']).lower())

    conn.close()
    return {
        'excluded_entreprise_ids': excluded_entreprise_ids,
        'bounced_emails': bounced_emails,
    }


def is_recipient_excluded(
    recipient: Dict[str, Any],
    *,
    excluded_entreprise_ids: Optional[Set[int]] = None,
    bounced_emails: Optional[Set[str]] = None,
) -> Tuple[bool, str]:
    """
    Vérifie si un destinataire doit être exclu.

    @returns: (excluded, reason) — reason parmi unsub, bounce_entreprise, bounce_email
    """
    ent_id = recipient.get('entreprise_id')
    if ent_id is not None and excluded_entreprise_ids and int(ent_id) in excluded_entreprise_ids:
        return True, 'unsub_or_bounce_entreprise'

    email = (recipient.get('email') or '').strip().lower()
    if email and bounced_emails and email in bounced_emails:
        return True, 'bounce_email'

    return False, ''


def append_unreachable_entreprise_sql(base_sql: str, params: list) -> str:
    """
    Ajoute les clauses SQL d'exclusion entreprises non joignables (alias ``e``).

    Exclut : statuts perdus, tag bounce, au moins un email bounced historique.
    """
    statut_ph = ','.join(['?' for _ in EXCLUDED_ENTREPRISE_STATUTS])
    base_sql += f" AND COALESCE(e.statut, '') NOT IN ({statut_ph})"
    params.extend(EXCLUDED_ENTREPRISE_STATUTS)

    for tag in EXCLUDED_ENTREPRISE_TAGS:
        base_sql += ' AND (e.tags IS NULL OR (e.tags NOT LIKE ? AND e.tags NOT LIKE ?))'
        params.append(f'%"{tag}"%')
        params.append(f'%{tag}%')

    base_sql += '''
        AND NOT EXISTS (
            SELECT 1
            FROM emails_envoyes ee_b
            WHERE ee_b.entreprise_id = e.id
              AND ee_b.statut = 'bounced'
        )
    '''
    return base_sql


def split_recipients_for_rotation(
    recipients: List[Dict[str, Any]],
    slot_count: int,
) -> List[List[Dict[str, Any]]]:
    """
    Répartit les destinataires en N lots égaux (rotation A/B/C/D).

    @param recipients: Liste de destinataires
    @param slot_count: Nombre de créneaux actifs
    @returns: Liste de listes (une par slot)
    """
    if slot_count <= 0:
        return []
    if slot_count == 1:
        return [list(recipients)]

    chunks: List[List[Dict[str, Any]]] = [[] for _ in range(slot_count)]
    for idx, rec in enumerate(recipients):
        chunks[idx % slot_count].append(rec)
    return chunks
