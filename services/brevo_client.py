"""
Client Brevo (Sendinblue) pour statut compte, quota et stats d'envoi.

Utilise la clé API ``BREVO_API_KEY`` (pas la clé SMTP).
L'envoi applicatif reste en SMTP via ``MAIL_*`` ; ce module sert au monitoring.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from config import (
    BREVO_API_KEY,
    BREVO_DAILY_EMAIL_LIMIT,
    MAIL_DEFAULT_SENDER,
    MAIL_PASSWORD,
    MAIL_SERVER,
    MAIL_USERNAME,
)

logger = logging.getLogger(__name__)

BREVO_API_BASE = 'https://api.brevo.com/v3'

# Mapping événements Brevo -> event_type stocké dans email_tracking_events
BREVO_EVENT_TYPE_MAP = {
    'requests': 'brevo_request',
    'request': 'brevo_request',
    'delivered': 'brevo_delivered',
    'opened': 'brevo_open',
    'open': 'brevo_open',
    'clicks': 'brevo_click',
    'click': 'brevo_click',
    'hardBounce': 'brevo_hard_bounce',
    'hardbounces': 'brevo_hard_bounce',
    'softBounce': 'brevo_soft_bounce',
    'softbounces': 'brevo_soft_bounce',
    'spam': 'brevo_spam',
    'blocked': 'brevo_blocked',
    'invalid': 'brevo_invalid',
    'error': 'brevo_error',
    'deferred': 'brevo_deferred',
    'unsubscribed': 'brevo_unsubscribed',
}


def extract_sender_email(sender_value: Optional[str] = None) -> str:
    """
    Extrait l'email depuis ``Nom <email>`` ou renvoie la chaîne telle quelle.

    @param sender_value: Valeur MAIL_DEFAULT_SENDER
    @returns: Email en minuscules, ou chaîne vide
    """
    raw = (sender_value if sender_value is not None else MAIL_DEFAULT_SENDER) or ''
    raw = str(raw).strip()
    if '<' in raw and '>' in raw:
        try:
            return raw.split('<', 1)[1].split('>', 1)[0].strip().lower()
        except Exception:
            return raw.lower()
    return raw.lower()


class BrevoClient:
    """
    Client HTTP léger vers l'API Brevo.

    Responsabilités :
    - lire le compte / crédits restants
    - récupérer les stats d'envoi et derniers événements
    - signaler les incohérences de config SMTP (.env vs compte Brevo)
    """

    def __init__(self, api_key: Optional[str] = None, timeout: int = 20):
        """
        @param api_key: Clé API Brevo (défaut : ``BREVO_API_KEY``)
        @param timeout: Timeout HTTP en secondes
        """
        self.api_key = (api_key if api_key is not None else BREVO_API_KEY or '').strip()
        self.timeout = max(5, int(timeout or 20))

    @property
    def is_configured(self) -> bool:
        """
        @returns: True si une clé API est présente
        """
        return bool(self.api_key)

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Exécute une requête JSON vers l'API Brevo.

        @param method: Méthode HTTP (GET, POST, ...)
        @param path: Chemin relatif (ex. ``/account``)
        @param params: Query string optionnelle
        @returns: Dict ``{ok, status, data, error}``
        @raises: Ne lève pas ; les erreurs sont encapsulées dans le dict
        """
        if not self.is_configured:
            return {
                'ok': False,
                'status': 0,
                'data': None,
                'error': 'BREVO_API_KEY manquante dans .env',
            }

        query = ''
        if params:
            query = '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f'{BREVO_API_BASE}{path}{query}'
        req = urllib.request.Request(
            url,
            method=(method or 'GET').upper(),
            headers={
                'api-key': self.api_key,
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
                data = json.loads(raw) if raw else {}
                return {'ok': True, 'status': int(resp.status), 'data': data, 'error': None}
        except urllib.error.HTTPError as exc:
            body = ''
            try:
                body = exc.read().decode('utf-8', errors='replace')
            except Exception:
                body = str(exc)
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {'raw': body}
            msg = None
            if isinstance(parsed, dict):
                if isinstance(parsed.get('message'), str):
                    msg = parsed.get('message')
                err_obj = parsed.get('error')
                if not msg and isinstance(err_obj, dict) and isinstance(err_obj.get('message'), str):
                    msg = err_obj.get('message')
            return {
                'ok': False,
                'status': int(exc.code or 0),
                'data': parsed,
                'error': msg or f'HTTP {exc.code}',
            }
        except Exception as exc:
            logger.warning('Brevo API %s %s: %s', method, path, exc)
            return {'ok': False, 'status': 0, 'data': None, 'error': str(exc)}

    def get_account(self) -> Dict[str, Any]:
        """
        Récupère le compte Brevo (plan, crédits, relay SMTP).

        @returns: Réponse brute encapsulée ``{ok, status, data, error}``
        """
        return self._request('GET', '/account')

    def get_smtp_aggregated_report(self) -> Dict[str, Any]:
        """
        Stats agrégées d'envoi transactionnel (période glissante côté Brevo).

        @returns: Réponse API encapsulée
        """
        return self._request('GET', '/smtp/statistics/aggregatedReport')

    def get_recent_smtp_events(self, limit: int = 10) -> Dict[str, Any]:
        """
        Derniers événements SMTP (delivered, opened, hardBounce, etc.).

        @param limit: Nombre max d'événements (1-50)
        @returns: Réponse API encapsulée
        """
        lim = max(1, min(int(limit or 10), 50))
        return self._request('GET', '/smtp/statistics/events', {'limit': lim})

    def get_blocked_contacts(self, limit: int = 10) -> Dict[str, Any]:
        """
        Contacts bloqués côté Brevo (hard bounce, spam, etc.).

        @param limit: Nombre max de contacts
        @returns: Réponse API encapsulée
        """
        lim = max(1, min(int(limit or 10), 50))
        return self._request('GET', '/smtp/blockedContacts', {'limit': lim})

    def build_status(self) -> Dict[str, Any]:
        """
        Construit un résumé prêt pour l'UI (quota, warnings, erreurs, stats).

        @returns: Dict sérialisable JSON pour ``GET /api/brevo/status``
        @example:
            >>> status = BrevoClient().build_status()
            >>> status['plan']['credits_remaining']
            294
        """
        warnings: List[str] = []
        errors: List[str] = []

        if not self.is_configured:
            return {
                'ok': False,
                'configured': False,
                'provider': 'brevo',
                'sender': MAIL_DEFAULT_SENDER,
                'smtp': {
                    'host': MAIL_SERVER,
                    'login': MAIL_USERNAME,
                    'password_configured': bool(MAIL_PASSWORD),
                },
                'plan': {
                    'type': None,
                    'credits_remaining': None,
                    'credits_type': None,
                    'daily_limit_config': BREVO_DAILY_EMAIL_LIMIT,
                },
                'stats': {},
                'recent_events': [],
                'blocked_contacts': [],
                'warnings': [],
                'errors': ['Clé API Brevo absente (BREVO_API_KEY).'],
            }

        account_res = self.get_account()
        stats_res = self.get_smtp_aggregated_report()
        events_res = self.get_recent_smtp_events(8)
        blocked_res = self.get_blocked_contacts(8)

        account = account_res.get('data') if account_res.get('ok') else {}
        if not account_res.get('ok'):
            errors.append(f"Compte Brevo: {account_res.get('error') or 'erreur API'}")

        plan_rows = (account or {}).get('plan') or []
        plan0 = plan_rows[0] if isinstance(plan_rows, list) and plan_rows else {}
        credits = plan0.get('credits')
        try:
            credits_i = int(credits) if credits is not None else None
        except (TypeError, ValueError):
            credits_i = None

        relay = ((account or {}).get('relay') or {}).get('data') or {}
        relay_login = (relay.get('userName') or '').strip()
        # Lecture live os.environ (prioritaire) pour éviter un process Flask avec vieux MAIL_*
        import os
        env_login = (os.environ.get('MAIL_USERNAME') or MAIL_USERNAME or '').strip()
        mail_server = (os.environ.get('MAIL_SERVER') or MAIL_SERVER or '').strip()
        mail_password = (os.environ.get('MAIL_PASSWORD') or MAIL_PASSWORD or '').strip()
        mail_sender = (os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_DEFAULT_SENDER or '').strip()
        login_matches = bool(relay_login) and relay_login.lower() == env_login.lower()
        using_brevo_smtp = any(
            x in mail_server.lower()
            for x in ('brevo', 'sendinblue', 'mailin.fr')
        )
        sender_email = extract_sender_email(mail_sender)

        if not using_brevo_smtp:
            warnings.append(
                f"SMTP actuel = {mail_server or '(vide)'} (pas Brevo). "
                "Redémarre Flask/Celery pour recharger le .env local."
            )
        if not mail_password:
            warnings.append('MAIL_PASSWORD (clé SMTP) vide : les envois SMTP échoueront.')
        if using_brevo_smtp and relay_login and env_login and not login_matches:
            warnings.append(
                f'Login SMTP .env ({env_login}) différent du compte Brevo ({relay_login}).'
            )
        if credits_i is not None and credits_i <= 0:
            errors.append('Quota Brevo épuisé (0 crédit restant).')
        elif credits_i is not None and credits_i <= 20:
            warnings.append(f'Quota Brevo bas : {credits_i} crédit(s) restant(s).')

        stats_raw = stats_res.get('data') if stats_res.get('ok') else {}
        if not stats_res.get('ok') and stats_res.get('error'):
            warnings.append(f"Stats Brevo indisponibles: {stats_res.get('error')}")

        events_raw = (events_res.get('data') or {}).get('events') if events_res.get('ok') else []
        recent_events = []
        for ev in (events_raw or [])[:8]:
            if not isinstance(ev, dict):
                continue
            recent_events.append({
                'email': ev.get('email'),
                'event': ev.get('event'),
                'date': ev.get('date'),
                'subject': ev.get('subject'),
                'message_id': ev.get('messageId'),
            })

        blocked_raw = (blocked_res.get('data') or {}).get('contacts') if blocked_res.get('ok') else []
        blocked_contacts = []
        for c in (blocked_raw or [])[:8]:
            if not isinstance(c, dict):
                continue
            reason = c.get('reason') or {}
            blocked_contacts.append({
                'email': c.get('email'),
                'reason': reason.get('message') if isinstance(reason, dict) else str(reason or ''),
                'code': reason.get('code') if isinstance(reason, dict) else None,
                'blocked_at': c.get('blockedAt'),
            })

        ok = account_res.get('ok') is True and not errors
        return {
            'ok': ok,
            'configured': True,
            'provider': 'brevo',
            'account_email': (account or {}).get('email'),
            'display_email': sender_email or extract_sender_email(mail_sender),
            'company': (account or {}).get('companyName') or 'Daniel Craft',
            'sender': mail_sender or MAIL_DEFAULT_SENDER,
            'smtp': {
                'host': mail_server or relay.get('relay') or 'smtp-relay.brevo.com',
                'port': int(relay.get('port') or 587),
                'login': env_login,
                'login_expected': relay_login or None,
                'login_matches_env': login_matches if relay_login else None,
                'password_configured': bool(mail_password),
                'relay_enabled': bool(((account or {}).get('relay') or {}).get('enabled')),
                'using_brevo_smtp': using_brevo_smtp,
            },
            'plan': {
                'type': plan0.get('type'),
                'credits_remaining': credits_i,
                'credits_type': plan0.get('creditsType'),
                'daily_limit_config': BREVO_DAILY_EMAIL_LIMIT,
            },
            'stats': {
                'range': (stats_raw or {}).get('range'),
                'requests': (stats_raw or {}).get('requests'),
                'delivered': (stats_raw or {}).get('delivered'),
                'hard_bounces': (stats_raw or {}).get('hardBounces'),
                'soft_bounces': (stats_raw or {}).get('softBounces'),
                'spam_reports': (stats_raw or {}).get('spamReports'),
                'blocked': (stats_raw or {}).get('blocked'),
                'invalid': (stats_raw or {}).get('invalid'),
                'errors': (stats_raw or {}).get('error'),
                'opens': (stats_raw or {}).get('uniqueOpens'),
                'clicks': (stats_raw or {}).get('uniqueClicks'),
                'unsubscribed': (stats_raw or {}).get('unsubscribed'),
            },
            'recent_events': recent_events,
            'blocked_contacts': blocked_contacts,
            'warnings': warnings,
            'errors': errors,
        }

    def sync_events_to_campagnes(self, campagne_id: Optional[int] = None, limit: int = 100) -> Dict[str, Any]:
        """
        Récupère les événements Brevo et les enregistre dans ``email_tracking_events``.

        Appariement : ``brevo_message_id`` puis email+sujet (+campagne).
        Les types sont préfixés ``brevo_*`` pour ne pas écraser les trackers ProspectLab.

        @param campagne_id: Limiter l'appariement à une campagne
        @param limit: Nombre d'événements Brevo à tirer
        @returns: Résumé {ok, fetched, matched, inserted, bounced_updated, unmatched, errors}
        """
        from services.database.campagnes import CampagneManager

        if not self.is_configured:
            return {
                'ok': False,
                'fetched': 0,
                'matched': 0,
                'inserted': 0,
                'bounced_updated': 0,
                'unmatched': 0,
                'errors': ['BREVO_API_KEY manquante'],
            }

        events_res = self.get_recent_smtp_events(limit=max(1, min(int(limit or 100), 100)))
        if not events_res.get('ok'):
            return {
                'ok': False,
                'fetched': 0,
                'matched': 0,
                'inserted': 0,
                'bounced_updated': 0,
                'unmatched': 0,
                'errors': [events_res.get('error') or 'Impossible de lire les events Brevo'],
            }

        events = ((events_res.get('data') or {}).get('events') or [])
        db = CampagneManager()
        matched = 0
        inserted = 0
        bounced_updated = 0
        unmatched = 0
        errors: List[str] = []

        for ev in events:
            if not isinstance(ev, dict):
                continue
            raw_type = str(ev.get('event') or '').strip()
            event_type = BREVO_EVENT_TYPE_MAP.get(raw_type) or BREVO_EVENT_TYPE_MAP.get(raw_type.lower())
            if not event_type:
                # garder une trace générique
                event_type = f"brevo_{raw_type or 'unknown'}"

            mid = (ev.get('messageId') or ev.get('message-id') or '').strip()
            email_addr = (ev.get('email') or '').strip()
            subject = (ev.get('subject') or '').strip()
            row = db.find_email_envoye_for_brevo_event(
                email=email_addr,
                subject=subject,
                message_id=mid or None,
                campagne_id=campagne_id,
            )
            if not row:
                unmatched += 1
                continue

            matched += 1
            email_id = row.get('id')
            token = row.get('tracking_token') or f'brevo-{email_id}'

            if mid and not row.get('brevo_message_id'):
                try:
                    db.update_email_brevo_message_id(email_id, mid)
                except Exception as exc:
                    errors.append(f'brevo_message_id email {email_id}: {exc}')

            # Dédupliquer sur message_id + type
            if self._tracking_event_exists(db, email_id, event_type, mid):
                continue

            event_data = {
                'source': 'brevo',
                'brevo_event': raw_type,
                'message_id': mid,
                'date': ev.get('date'),
                'subject': subject,
                'from': ev.get('from'),
            }
            try:
                new_id = db.record_tracking_event(
                    tracking_token=token,
                    event_type=event_type,
                    event_data=event_data,
                    ip_address=None,
                    user_agent='brevo-api-sync',
                )
                if new_id:
                    inserted += 1
            except Exception as exc:
                errors.append(f'insert event email {email_id}: {exc}')
                continue

            if event_type == 'brevo_hard_bounce' and row.get('statut') != 'bounced':
                try:
                    if self._mark_email_bounced(db, email_id):
                        bounced_updated += 1
                except Exception as exc:
                    errors.append(f'bounce email {email_id}: {exc}')

        return {
            'ok': True,
            'fetched': len(events),
            'matched': matched,
            'inserted': inserted,
            'bounced_updated': bounced_updated,
            'unmatched': unmatched,
            'errors': errors,
            'campagne_id': campagne_id,
        }

    @staticmethod
    def _tracking_event_exists(db, email_id, event_type, message_id) -> bool:
        """
        Vérifie si un événement Brevo est déjà enregistré.

        @param db: CampagneManager
        @param email_id: ID email
        @param event_type: Type stocké
        @param message_id: Message-ID Brevo
        @returns: True si déjà présent
        """
        conn = db.get_connection()
        cursor = conn.cursor()
        mid = (message_id or '').strip()
        if mid:
            like = f'%{mid}%'
            db.execute_sql(
                cursor,
                '''
                SELECT id FROM email_tracking_events
                WHERE email_id = ? AND event_type = ? AND event_data LIKE ?
                LIMIT 1
                ''',
                (int(email_id), event_type, like),
            )
        else:
            db.execute_sql(
                cursor,
                '''
                SELECT id FROM email_tracking_events
                WHERE email_id = ? AND event_type = ? AND user_agent = 'brevo-api-sync'
                LIMIT 1
                ''',
                (int(email_id), event_type),
            )
        row = cursor.fetchone()
        conn.close()
        return bool(row)

    @staticmethod
    def _mark_email_bounced(db, email_id) -> bool:
        """
        Passe un email en statut bounced.

        @param db: CampagneManager
        @param email_id: ID email
        @returns: True si mis à jour
        """
        conn = db.get_connection()
        cursor = conn.cursor()
        db.execute_sql(
            cursor,
            "UPDATE emails_envoyes SET statut = 'bounced', erreur = COALESCE(erreur, 'Brevo hardBounce') WHERE id = ?",
            (int(email_id),),
        )
        conn.commit()
        ok = cursor.rowcount > 0
        conn.close()
        return ok


def get_brevo_status() -> Dict[str, Any]:
    """
    Raccourci pour l'API Flask : statut Brevo prêt à sérialiser.

    @returns: Dict de statut (voir ``BrevoClient.build_status``)
    """
    return BrevoClient().build_status()


def sync_brevo_events(campagne_id: Optional[int] = None, limit: int = 100) -> Dict[str, Any]:
    """
    Raccourci : synchronise les événements Brevo vers la base locale.

    @param campagne_id: Campagne cible optionnelle
    @param limit: Nombre d'événements à tirer
    @returns: Résumé de sync
    """
    return BrevoClient().sync_events_to_campagnes(campagne_id=campagne_id, limit=limit)
