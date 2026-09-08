"""
Sync Brevo + classification IMAP node12 (journal inbox_events append-only).
"""

from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from email.message import Message
from typing import Any, Dict, List, Optional, Tuple

from utils.inbox_classification import classify_imap_reply, map_brevo_event_to_category
from utils.tracking_suspect import is_cloud_scanner_ip

logger = logging.getLogger(__name__)

BOUNCE_HINTS = (
    'undelivery',
    'undelivered',
    'delivery status',
    'mail delivery failed',
    'returned mail',
    'failure notice',
    'delivery failure',
    'mailer-daemon',
    'postmaster',
)


def _env_get_profile(key: str, profile: Optional[str]) -> Optional[str]:
    """Lit une variable d'env avec suffixe profil (ex. IMAP_HOST_NODE12)."""
    if not profile or str(profile).strip().lower() in {'default', 'main'}:
        return os.getenv(key)
    suffix = str(profile).strip().upper()
    return os.getenv(f'{key}_{suffix}') or os.getenv(key)


def _decode_header(raw: Optional[str]) -> str:
    """Decode un header email MIME."""
    if not raw:
        return ''
    parts = email.header.decode_header(raw)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or 'utf-8', errors='replace'))
        else:
            out.append(str(chunk))
    return ' '.join(out).strip()


def _body_preview(msg: Message, limit: int = 400) -> str:
    """Extrait un apercu texte du message."""
    text = ''
    if msg.is_multipart():
        for part in msg.walk():
            if (part.get_content_type() or '').lower() == 'text/plain':
                payload = part.get_payload(decode=True) or b''
                charset = part.get_content_charset() or 'utf-8'
                text = payload.decode(charset, errors='replace')
                break
    else:
        payload = msg.get_payload(decode=True) or b''
        charset = msg.get_content_charset() or 'utf-8'
        text = payload.decode(charset, errors='replace')
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text[:limit]


def _looks_like_bounce(subject: str, from_addr: str, preview: str) -> bool:
    """Detecte un NDR / bounce (laisse au scan bounce dedie)."""
    blob = f'{subject}\n{from_addr}\n{preview}'.lower()
    return any(h in blob for h in BOUNCE_HINTS)


def _campaign_subject_hints(campagne_manager) -> List[str]:
    """Recupere quelques sujets de campagnes recentes pour matcher les replies."""
    hints: List[str] = []
    try:
        conn = campagne_manager.get_connection()
        cur = conn.cursor()
        campagne_manager.execute_sql(
            cur,
            '''
            SELECT DISTINCT sujet FROM emails_envoyes
            WHERE sujet IS NOT NULL AND trim(sujet) <> ''
            ORDER BY id DESC
            LIMIT 80
            ''',
        )
        for row in cur.fetchall() or []:
            s = row.get('sujet') if isinstance(row, dict) else row[0]
            if s:
                hints.append(str(s).lower()[:80])
        conn.close()
    except Exception:
        pass
    return hints


def sync_brevo_events(*, limit: int = 50) -> Dict[str, Any]:
    """
    Synchronise les evenements Brevo recents vers inbox_events + bounces BDD.

    @param limit: Nombre max d'events Brevo a tirer
    @returns: Resume {inserted, bounced, skipped, errors}
    """
    from services.brevo_client import BrevoClient
    from services.database.campagnes import CampagneManager

    cm = CampagneManager()
    client = BrevoClient()
    summary = {'inserted': 0, 'bounced': 0, 'skipped': 0, 'errors': 0, 'events': 0}

    # Blocked contacts
    try:
        blocked = client.get_blocked_contacts(limit=min(limit, 50))
        contacts = ((blocked.get('data') or {}).get('contacts') if isinstance(blocked, dict) else None) or []
        for c in contacts:
            email_addr = (c.get('email') or '').strip()
            if not email_addr:
                continue
            reason = ((c.get('reason') or {}) if isinstance(c.get('reason'), dict) else {})
            code = reason.get('code') or 'blocked'
            msg = reason.get('message') or 'blocked by brevo'
            ext = f"blocked:{email_addr}:{c.get('blockedAt') or ''}"
            inserted = cm.insert_inbox_event_if_new(
                source='brevo',
                external_id=ext,
                category='blocked' if code != 'hardBounce' else 'bounce_hard',
                email=email_addr,
                subject=None,
                preview=str(msg)[:400],
                raw_meta=c,
                date_event=c.get('blockedAt'),
            )
            if inserted:
                summary['inserted'] += 1
                eid = cm.mark_latest_email_bounced_for_recipient(
                    email_addr, reason=f'brevo:{code}:{msg}'
                )
                if eid:
                    summary['bounced'] += 1
            else:
                summary['skipped'] += 1
    except Exception as e:
        logger.warning('Brevo blocked contacts sync failed: %s', e)
        summary['errors'] += 1

    # SMTP events
    try:
        raw = client.get_recent_smtp_events(limit=max(1, min(int(limit or 50), 50)))
        events = []
        if isinstance(raw, dict):
            data = raw.get('data') or {}
            events = data.get('events') or []
        summary['events'] = len(events)
        for ev in events:
            if not isinstance(ev, dict):
                continue
            event_name = ev.get('event') or ''
            category = map_brevo_event_to_category(event_name)
            email_addr = (ev.get('email') or '').strip()
            message_id = (ev.get('messageId') or ev.get('message_id') or '').strip()
            date_event = ev.get('date')
            ip = ev.get('ip')

            # Clicks bots cloud
            if event_name in {'clicks', 'click'} and is_cloud_scanner_ip(ip):
                category = 'bot_click'
            if not category:
                summary['skipped'] += 1
                continue

            ext = f"{event_name}:{message_id or email_addr}:{date_event or ''}"
            inserted = cm.insert_inbox_event_if_new(
                source='brevo',
                external_id=ext,
                category=category,
                email=email_addr or None,
                subject=ev.get('subject'),
                preview=(ev.get('reason') or '')[:400] or None,
                raw_meta=ev,
                date_event=date_event,
            )
            if not inserted:
                summary['skipped'] += 1
                continue
            summary['inserted'] += 1

            if category in {'bounce_hard', 'blocked'}:
                eid = cm.mark_latest_email_bounced_for_recipient(
                    email_addr,
                    reason=f"brevo:{event_name}:{ev.get('reason') or ''}",
                )
                if eid:
                    summary['bounced'] += 1
    except Exception as e:
        logger.warning('Brevo events sync failed: %s', e)
        summary['errors'] += 1

    return summary


def classify_imap_replies(
    *,
    profiles: Optional[str] = None,
    days: int = 3,
    limit: int = 80,
) -> Dict[str, Any]:
    """
    Scanne les boites IMAP (node12…) et classe les messages non-bounce.

    @param profiles: Liste CSV de profils (defaut IMAP_PROFILES / node12)
    @param days: Fenetre SINCE
    @param limit: Max messages par profil
    @returns: Resume {inserted, skipped, bounce_like, errors, by_category}
    """
    from services.database.campagnes import CampagneManager

    cm = CampagneManager()
    hints = _campaign_subject_hints(cm)
    summary: Dict[str, Any] = {
        'inserted': 0,
        'skipped': 0,
        'bounce_like': 0,
        'errors': 0,
        'by_category': {},
        'profiles': [],
    }

    raw_profiles = (profiles or os.getenv('BOUNCE_SCAN_PROFILES') or os.getenv('IMAP_PROFILES') or 'node12').strip()
    profile_list = [p.strip() for p in raw_profiles.split(',') if p.strip()] or ['node12']
    summary['profiles'] = profile_list

    since_dt = datetime.now(timezone.utc) - timedelta(days=max(1, int(days or 3)))
    since_imap = since_dt.strftime('%d-%b-%Y')

    for profile in profile_list:
        host = _env_get_profile('IMAP_HOST', profile) or 'node12.lan'
        user = _env_get_profile('IMAP_USERNAME', profile) or ''
        password = _env_get_profile('IMAP_PASSWORD', profile) or ''
        mailbox = _env_get_profile('IMAP_MAILBOX', profile) or 'INBOX'
        try:
            port = int(_env_get_profile('IMAP_PORT', profile) or '993')
        except Exception:
            port = 993
        if not user or not password:
            logger.warning('IMAP profile %s: credentials manquants', profile)
            summary['errors'] += 1
            continue

        try:
            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(user, password)
            mail.select(mailbox)
            typ, data = mail.search(None, f'(SINCE {since_imap})')
            if typ != 'OK' or not data or not data[0]:
                mail.logout()
                continue
            ids = data[0].split()
            if limit:
                ids = ids[-max(1, int(limit)) :]

            for msg_id in ids:
                typ, msg_data = mail.fetch(msg_id, '(RFC822)')
                if typ != 'OK' or not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject = _decode_header(msg.get('Subject'))
                from_addr = _decode_header(msg.get('From'))
                preview = _body_preview(msg)
                message_id = (msg.get('Message-ID') or msg.get('Message-Id') or '').strip()
                if not message_id:
                    message_id = f'{profile}:{msg_id.decode() if isinstance(msg_id, bytes) else msg_id}:{subject[:40]}'

                if _looks_like_bounce(subject, from_addr, preview):
                    summary['bounce_like'] += 1
                    continue

                looks_campaign = False
                subj_low = subject.lower()
                if any(h and h in subj_low for h in hints):
                    looks_campaign = True
                if subject.lower().startswith('re:') or 'réponse' in subject.lower() or 'reponse' in subject.lower():
                    looks_campaign = True

                category = classify_imap_reply(
                    subject=subject,
                    preview=preview,
                    from_addr=from_addr,
                    looks_like_campaign_reply=looks_campaign,
                )
                # Extraire email expediteur
                _, addr = email.utils.parseaddr(from_addr)
                date_tuple = email.utils.parsedate_to_datetime(msg.get('Date')) if msg.get('Date') else None
                date_event = date_tuple.isoformat() if date_tuple else None

                inserted = cm.insert_inbox_event_if_new(
                    source='imap',
                    external_id=message_id,
                    category=category,
                    email=(addr or '').strip() or None,
                    subject=subject,
                    preview=preview,
                    raw_meta={'profile': profile, 'from': from_addr},
                    date_event=date_event,
                    confidence=0.8 if looks_campaign else 0.5,
                )
                if inserted:
                    summary['inserted'] += 1
                    summary['by_category'][category] = summary['by_category'].get(category, 0) + 1
                else:
                    summary['skipped'] += 1

            mail.logout()
        except Exception as e:
            logger.warning('IMAP classify profile %s failed: %s', profile, e)
            summary['errors'] += 1

    return summary
