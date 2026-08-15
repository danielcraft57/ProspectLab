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
        env_login = (MAIL_USERNAME or '').strip()
        login_matches = bool(relay_login) and relay_login.lower() == env_login.lower()

        if not MAIL_PASSWORD:
            warnings.append('MAIL_PASSWORD (clé SMTP) vide : les envois SMTP échoueront.')
        if relay_login and env_login and not login_matches:
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
            'company': (account or {}).get('companyName'),
            'sender': MAIL_DEFAULT_SENDER,
            'smtp': {
                'host': MAIL_SERVER or relay.get('relay') or 'smtp-relay.brevo.com',
                'port': int(relay.get('port') or 587),
                'login': env_login,
                'login_expected': relay_login or None,
                'login_matches_env': login_matches if relay_login else None,
                'password_configured': bool(MAIL_PASSWORD),
                'relay_enabled': bool(((account or {}).get('relay') or {}).get('enabled')),
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


def get_brevo_status() -> Dict[str, Any]:
    """
    Raccourci pour l'API Flask : statut Brevo prêt à sérialiser.

    @returns: Dict de statut (voir ``BrevoClient.build_status``)
    """
    return BrevoClient().build_status()
