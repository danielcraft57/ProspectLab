"""
Helpers pour filtrer les emails de mauvaise qualité en campagne.

Exemples exclus : adresses fictives de templates (IONOS, etc.).
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

# Domaines typiques des demos / templates (pas de vrais contacts).
PLACEHOLDER_EMAIL_DOMAINS = frozenset({
    'exemple.fr',
    'exemple.com',
    'example.com',
    'example.fr',
    'example.org',
    'votre-domaine.fr',
    'votre-domaine.com',
    'votredomaine.fr',
    'votreentreprise.fr',
    'votreentreprise.com',
    'monentreprise.fr',
    'mondomaine.fr',
    'domain.com',
    'domaine.fr',
    'email.com',
    'test.com',
    'test.fr',
    'mailinator.com',
    'yopmail.com',
})

# Sources scrapees qui pointent souvent vers des pages demo / builder.
PLACEHOLDER_SOURCE_MARKERS = (
    'ionos.fr/site-internet',
    'ionos.fr/tools/',
    'ionos.com/website',
    'wix.com/website-template',
    'wordpress.com/themes',
    'jimdo.com',
    'webflow.io/templates',
)


def email_domain(email: Optional[str]) -> str:
    """
    Extrait le domaine d'une adresse email (partie apres @).

    @param email: Adresse email eventuelle
    @returns: Domaine en minuscules, ou chaine vide
    """
    if not email or '@' not in str(email):
        return ''
    return str(email).rsplit('@', 1)[-1].strip().lower()


def is_placeholder_email(email: Optional[str], source: Optional[str] = None) -> bool:
    """
    Indique si l'email (ou sa source) ressemble a un faux contact de template.

    @param email: Adresse email a evaluer
    @param source: URL ou libelle de provenance (ex. page_url scraper)
    @returns: True si l'adresse doit etre ecartee des campagnes
    @example:
        >>> is_placeholder_email('info@exemple.fr')
        True
        >>> is_placeholder_email(
        ...     'contact@acme.fr',
        ...     'https://www.ionos.fr/site-internet/creer-un-site-internet',
        ... )
        True
    """
    domain = email_domain(email)
    if domain and domain in PLACEHOLDER_EMAIL_DOMAINS:
        return True
    if domain and any(domain.endswith('.' + d) for d in PLACEHOLDER_EMAIL_DOMAINS):
        return True

    src = (source or '').strip().lower()
    if not src:
        return False

    # Normaliser une URL complete pour matcher les marqueurs
    try:
        parsed = urlparse(src if '://' in src else 'https://' + src)
        haystack = (parsed.netloc + parsed.path).lower()
    except Exception:
        haystack = src

    return any(marker in haystack or marker in src for marker in PLACEHOLDER_SOURCE_MARKERS)
