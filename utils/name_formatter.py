"""
Utilitaire pour formater les noms depuis différents formats (JSON, string, etc.)
et filtrer les faux prénoms dérivés d'emails génériques (contact@, info@…).
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


# Local-parts / libellés qui ne sont pas un vrai interlocuteur.
GENERIC_DISPLAY_NAME_TOKENS = frozenset({
    'info',
    'infos',
    'contact',
    'contacts',
    'hello',
    'bonjour',
    'hi',
    'support',
    'sav',
    'admin',
    'administration',
    'commercial',
    'sales',
    'service',
    'services',
    'secretariat',
    'secrétariat',
    'accueil',
    'office',
    'team',
    'equipe',
    'équipe',
    'webmaster',
    'postmaster',
    'noreply',
    'no-reply',
    'donotreply',
    'do-not-reply',
    'newsletter',
    'notification',
    'notifications',
    'mail',
    'email',
    'direction',
    'gerente',
    'principal',
})

_GENERIC_PLACEHOLDERS = frozenset({
    '',
    'n/a',
    'na',
    'monsieur/madame',
    'monsieur',
    'madame',
    'cher prospect',
    'bonjour',
    'hello',
})


def _normalize_token(value: str) -> str:
    """Normalise un token pour comparaison (minuscules, sans accents utiles)."""
    text = (value or '').strip().lower()
    text = text.replace('é', 'e').replace('è', 'e').replace('ê', 'e').replace('à', 'a')
    text = re.sub(r'[^a-z0-9@._+\- ]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def email_localpart_for_name(value: Optional[str]) -> str:
    """
    Extrait la partie locale d'un email ou d'un libellé type contact@.

    @param value: Email ou chaîne quelconque
    @returns: Local-part normalisé, ou chaîne vide
    """
    text = _normalize_token(str(value or ''))
    if not text:
        return ''
    if '@' in text:
        text = text.split('@', 1)[0].strip()
    return text


def is_generic_name_token(token: Optional[str]) -> bool:
    """
    Indique si un token unique est un libellé générique (contact, info…).

    @param token: Mot isolé (local-part ou prénom dérivé)
    @returns: True si générique
    """
    raw = email_localpart_for_name(token)
    if not raw:
        return True
    compact = re.sub(r'[^a-z0-9]+', '', raw)
    if raw in GENERIC_DISPLAY_NAME_TOKENS or compact in {
        re.sub(r'[^a-z0-9]+', '', t) for t in GENERIC_DISPLAY_NAME_TOKENS
    }:
        return True
    # Prefixe role courant : contact-, info., support_
    for prefix in ('contact', 'info', 'infos', 'noreply', 'no-reply', 'support', 'admin'):
        if raw == prefix or raw.startswith(prefix + '.') or raw.startswith(prefix + '-') or raw.startswith(prefix + '_'):
            return True
    return False


def is_generic_display_name(name: Optional[str]) -> bool:
    """
    Indique si un nom affiché / CTA ne doit pas être utilisé comme prénom.

    Couvre : Contact, info@domaine, Monsieur/Madame, local-part générique.

    @param name: Nom candidat
    @returns: True si à ignorer
    @example:
        >>> is_generic_display_name('Contact')
        True
        >>> is_generic_display_name('Jean Dupont')
        False
    """
    if name is None:
        return True
    normalized = _normalize_token(str(name))
    if normalized in _GENERIC_PLACEHOLDERS:
        return True
    compact_spaces = re.sub(r'[\s/]+', '', normalized)
    if compact_spaces in {'monsieurmadame', 'mrsmadame', 'cherprospect'}:
        return True
    local = email_localpart_for_name(normalized)
    if is_generic_name_token(local):
        return True
    # Multi-mots : si le premier token est générique (ex. "Contact commercial")
    parts = [p for p in re.split(r'[\s._+\-]+', local) if p]
    if parts and is_generic_name_token(parts[0]):
        return True
    return False


def is_generic_email_for_name(email: Optional[str]) -> bool:
    """
    True si l'email ne doit jamais produire un prénom (contact@, info@…).

    @param email: Adresse email
    @returns: True si local-part générique
    """
    return is_generic_name_token(email_localpart_for_name(email))


def format_name(name_data: Any) -> str:
    """
    Formate un nom depuis différents formats possibles.

    Args:
        name_data: Peut être :
            - Une chaîne JSON (ex: '{"first_name": "John", "last_name": "Doe"}')
            - Un dictionnaire Python
            - Une chaîne simple (ex: "John Doe")
            - None

    Returns:
        str: Nom formaté (ex: "John Doe") ou "N/A" si aucun nom valide
    """
    if not name_data:
        return 'N/A'

    # Si c'est déjà une chaîne simple, la retourner telle quelle
    if isinstance(name_data, str):
        # Essayer de parser si c'est du JSON
        if name_data.strip().startswith('{') or name_data.strip().startswith('['):
            try:
                parsed = json.loads(name_data)
                if isinstance(parsed, dict):
                    return _format_from_dict(parsed)
                # Si c'est une liste, prendre le premier élément
                if isinstance(parsed, list) and len(parsed) > 0:
                    if isinstance(parsed[0], dict):
                        return _format_from_dict(parsed[0])
                    return str(parsed[0])
            except (json.JSONDecodeError, ValueError):
                # Si le parsing échoue, c'est probablement une chaîne simple
                pass

        cleaned = name_data.strip() if name_data.strip() else 'N/A'
        if cleaned != 'N/A' and is_generic_display_name(cleaned):
            return 'N/A'
        return cleaned

    # Si c'est un dictionnaire
    if isinstance(name_data, dict):
        return _format_from_dict(name_data)

    # Sinon, convertir en chaîne
    text = str(name_data) if name_data else 'N/A'
    if text != 'N/A' and is_generic_display_name(text):
        return 'N/A'
    return text


def _format_from_dict(name_dict: dict) -> str:
    """
    Formate un nom depuis un dictionnaire.

    Args:
        name_dict: Dictionnaire avec first_name, last_name, full_name, etc.

    Returns:
        str: Nom formaté
    """
    if not name_dict:
        return 'N/A'

    # Essayer full_name d'abord
    full_name = name_dict.get('full_name') or name_dict.get('fullname')
    if full_name:
        text = str(full_name).strip()
        return 'N/A' if is_generic_display_name(text) else text

    # Sinon, construire depuis first_name et last_name
    first_name = name_dict.get('first_name') or name_dict.get('firstname') or ''
    last_name = name_dict.get('last_name') or name_dict.get('lastname') or ''

    # Nettoyer les valeurs
    first_name = str(first_name).strip() if first_name else ''
    last_name = str(last_name).strip() if last_name else ''

    if first_name and is_generic_display_name(first_name):
        first_name = ''
    if last_name and is_generic_display_name(last_name) and not first_name:
        last_name = ''

    # Construire le nom complet
    if first_name and last_name:
        return f'{first_name} {last_name}'
    elif first_name:
        return first_name
    elif last_name:
        return last_name if not is_generic_display_name(last_name) else 'N/A'

    # Si rien n'est disponible, essayer 'name' comme fallback
    name = name_dict.get('name')
    if name:
        text = str(name).strip()
        return 'N/A' if is_generic_display_name(text) else text

    return 'N/A'
