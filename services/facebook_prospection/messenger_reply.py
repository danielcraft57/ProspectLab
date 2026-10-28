"""
Envoi de reponses Messenger via Playwright serv1.
"""

from __future__ import annotations

from typing import Any

from services.facebook_prospection.job_runner import FacebookProspectionJobRunner
from services.facebook_prospection.messenger_store import message_fingerprint


def execute_messenger_reply(
    db: Any,
    thread_id: int,
    message_text: str,
    *,
    send: bool = False,
) -> dict[str, Any]:
    """
    Ouvre le fil sur serv1, compose et envoie (ou dry-run).

    @param db: Database
    @param thread_id: ID facebook_messenger_threads
    @param message_text: Texte a envoyer
    @param send: True = clic Envoyer
    @returns: JSON Playwright + persist local
    """
    thread = db.get_facebook_messenger_thread(int(thread_id))
    if not thread:
        return {'ok': False, 'error': 'fil introuvable'}

    body = (message_text or '').strip()
    if not body:
        return {'ok': False, 'error': 'message_text vide'}

    payload = {
        'contact_name': thread.get('contact_name') or '',
        'thread_url': thread.get('thread_url') or '',
        'message_text': body,
        'send': bool(send),
        'headless': False,
    }
    parsed = FacebookProspectionJobRunner().run(
        'messenger_reply',
        payload,
        force_remote=True,
    )
    if not isinstance(parsed, dict):
        return {'ok': False, 'error': 'reponse Playwright invalide'}

    if parsed.get('ok'):
        fp = message_fingerprint('outbound', body, 0)
        db.add_facebook_messenger_message_if_new(
            int(thread_id),
            'outbound',
            body,
            msg_fingerprint=fp,
            raw_json={'source': 'messenger_reply', 'send': send},
        )
        db.mark_facebook_messenger_thread_read(int(thread_id))

    return parsed
