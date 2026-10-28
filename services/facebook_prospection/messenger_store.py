"""
Persistance des fils Messenger synchronises depuis SocialDesk (messenger_sync).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def message_fingerprint(direction: str, text: str, index: int = 0) -> str:
    """
    Cle stable pour dedoublonner un message en base.

    @param direction: incoming | outgoing | inbound | outbound
    @param text: Corps du message
    @param index: Position dans le fil (secours si texte vide)
    @returns: Hash hex court
    """
    raw = f"{direction}|{(text or '').strip()}|{index}"
    return hashlib.sha256(raw.encode('utf-8', errors='replace')).hexdigest()[:40]


def normalize_sync_direction(direction: str) -> str:
    """Mappe les directions SocialDesk vers inbound / outbound."""
    d = str(direction or '').strip().lower()
    if d in ('outgoing', 'outbound', 'sent'):
        return 'outbound'
    return 'inbound'


def persist_messenger_sync_result(db: Any, parsed: dict[str, Any]) -> dict[str, Any]:
    """
    Enregistre le JSON renvoye par messenger_sync (threads + messages).

    @param db: Instance Database
    @param parsed: Reponse Playwright { threads: [...], account?: str }
    @returns: Statistiques { threads, messages_new, inbound_new, unread_threads }
    """
    if not parsed.get('ok'):
        return {'ok': False, 'error': parsed.get('error') or 'sync echoue'}

    account_id = str(parsed.get('account') or 'danielcraft').strip() or 'danielcraft'
    threads = list(parsed.get('threads') or [])
    stats = {
        'ok': True,
        'account': account_id,
        'threads': 0,
        'messages_new': 0,
        'inbound_new': 0,
        'unread_threads': 0,
        'synced_at': _utc_now_iso(),
    }

    for idx, thread in enumerate(threads):
        if not isinstance(thread, dict):
            continue
        contact_name = str(thread.get('contact_name') or '').strip()
        thread_key = str(thread.get('thread_key') or '').strip()
        if not thread_key:
            thread_key = message_fingerprint('thread', contact_name, idx)

        entreprise_id = db.match_entreprise_for_messenger_contact(contact_name)
        unread_flag = bool(thread.get('unread'))
        preview = str(thread.get('preview') or '')[:500]
        messages = list(thread.get('messages') or [])

        last_inbound_preview = ''
        for m in reversed(messages):
            if not isinstance(m, dict):
                continue
            if normalize_sync_direction(m.get('direction')) == 'inbound':
                last_inbound_preview = str(m.get('text') or '')[:500]
                break
        if not preview and messages:
            last = messages[-1]
            if isinstance(last, dict):
                preview = str(last.get('text') or '')[:500]

        thread_id, created_thread = db.upsert_facebook_messenger_thread(
            account_id,
            thread_key,
            contact_name=contact_name or None,
            entreprise_id=entreprise_id,
            thread_url=str(thread.get('thread_url') or '')[:1000] or None,
            preview=preview or None,
            fb_unread=unread_flag,
            meta={'open_status': thread.get('open_status'), 'sync': stats['synced_at']},
        )
        stats['threads'] += 1

        inbound_new_for_thread = 0
        for mi, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            body = str(msg.get('text') or '').strip()
            if not body:
                continue
            direction = normalize_sync_direction(msg.get('direction'))
            fp = message_fingerprint(direction, body, mi)
            inserted = db.add_facebook_messenger_message_if_new(
                thread_id,
                direction,
                body,
                msg_fingerprint=fp,
                raw_json={
                    'sender': msg.get('sender'),
                    'source': 'messenger_sync',
                },
            )
            if inserted:
                stats['messages_new'] += 1
                if direction == 'inbound':
                    stats['inbound_new'] += 1
                    inbound_new_for_thread += 1

        if inbound_new_for_thread and not created_thread:
            db.bump_facebook_messenger_thread_unread(thread_id, inbound_new_for_thread)

        if unread_flag or db.get_facebook_messenger_thread_unread(thread_id) > 0:
            stats['unread_threads'] += 1

        if entreprise_id and messages:
            db.mirror_messenger_thread_to_prospection_conversation(
                int(entreprise_id),
                thread_id,
                contact_name,
                thread_key,
                messages,
            )

    db.record_facebook_messenger_sync_event(stats)
    return stats


def persist_messenger_inbox_report(db: Any, parsed: dict[str, Any]) -> dict[str, Any]:
    """
    Enregistre les fils lus par messenger_inbox (mode auto-reply) dans la meme store.

    @param db: Database
    @param parsed: JSON job avec cle report.contacts
    @returns: Stats legeres
    """
    report = parsed.get('report') if isinstance(parsed.get('report'), dict) else {}
    contacts = list(report.get('contacts') or [])
    if not contacts:
        return {'ok': True, 'threads': 0, 'messages_new': 0}

    pseudo = {
        'ok': True,
        'account': parsed.get('account') or 'danielcraft',
        'threads': [],
    }
    for entry in contacts:
        if not isinstance(entry, dict):
            continue
        contact = entry.get('contact') if isinstance(entry.get('contact'), dict) else {}
        name = str(contact.get('displayName') or contact.get('searchName') or '').strip()
        msgs = list(entry.get('messages') or [])
        pseudo['threads'].append(
            {
                'contact_name': name,
                'preview': msgs[-1].get('text') if msgs and isinstance(msgs[-1], dict) else '',
                'unread': entry.get('status') not in ('skipped', 'sent'),
                'thread_key': f"contact:{entry.get('contactId') or name}",
                'messages': msgs,
            }
        )
    return persist_messenger_sync_result(db, pseudo)
