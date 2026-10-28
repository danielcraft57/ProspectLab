"""
Normalisation du resultat prospect_flow (ok / partial / failed).
"""

from __future__ import annotations

from typing import Any

FOLLOW_OK_STATUSES = frozenset({'already', 'dry-run', 'followed', 'clicked'})


def normalize_prospect_flow_result(parsed: dict[str, Any]) -> dict[str, Any]:
    """
    Ajuste ok et prospect_status apres retour serv1.

    - completed : page + follow + message (envoi ou dry-run compose OK)
    - partial : page + follow OK, message KO (lien et follow quand meme utiles)
    - failed : page introuvable ou follow impossible

    @param parsed: JSON brut Playwright
    @returns: Meme dict enrichi (steps, prospect_status, ok)
    """
    out = dict(parsed)
    selected = out.get('selected') or {}
    follow = out.get('follow') or {}
    message = out.get('message') or {}

    page_ok = bool(str(selected.get('url') or '').strip())
    follow_ok = str(follow.get('status') or '') in FOLLOW_OK_STATUSES
    message_ok = bool(message.get('ok'))

    out['steps'] = {
        'page': page_ok,
        'follow': follow_ok,
        'message': message_ok,
    }
    out['prospect_complete'] = page_ok and follow_ok and message_ok

    if page_ok and follow_ok and message_ok:
        out['prospect_status'] = 'completed'
        out['ok'] = True
    elif page_ok and follow_ok:
        out['prospect_status'] = 'partial'
        out['ok'] = True
    else:
        out['prospect_status'] = 'failed'
        if not out.get('error'):
            if not page_ok:
                out['error'] = 'Page Facebook introuvable ou score insuffisant'
            elif not follow_ok:
                out['error'] = 'Action Suivre impossible sur la page'
        out['ok'] = False

    return out


def prospect_flow_job_status(parsed: dict[str, Any]) -> tuple[str, str | None]:
    """
    Statut BDD du job facebook_prospection_jobs.

    @returns: (status, error_message optionnel)
    """
    ps = str(parsed.get('prospect_status') or 'failed')
    if ps == 'completed':
        return 'completed', None
    if ps == 'partial':
        msg = parsed.get('message') or {}
        step = msg.get('step') or msg.get('typed', {}).get('status') or 'echec'
        return 'partial', f'Messenger non finalise ({step})'[:500]
    err = str(parsed.get('error') or 'echec prospect_flow')[:500]
    return 'failed', err
