"""
Helpers pour comparer domaine site / domaine email (cross-links scraper).
"""

from __future__ import annotations

from typing import Optional, Set

FREE_MAIL_DOMAINS = frozenset({
    'gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.fr', 'hotmail.com', 'hotmail.fr',
    'outlook.com', 'outlook.fr', 'live.com', 'live.fr', 'msn.com', 'icloud.com', 'me.com',
    'orange.fr', 'wanadoo.fr', 'free.fr', 'sfr.fr', 'laposte.net', 'protonmail.com',
    'proton.me', 'gmx.fr', 'gmx.com', 'aol.com', 'mail.com', 'yandex.ru',
})


def _labels(domain: str) -> Set[str]:
    """Decoupe un domaine en labels utiles (points + tirets, ignore tld courts)."""
    parts = []
    for chunk in (domain or '').split('.'):
        if not chunk:
            continue
        parts.extend(chunk.split('-'))
    # ignorer tld-like courts et tokens trop generiques
    skip = {'www', 'mail', 'email', 'contact', 'info', 'com', 'fr', 'net', 'org', 'lu', 'eu'}
    return {p for p in parts if len(p) >= 3 and p not in skip}


def domains_compatible(website_domain: Optional[str], mail_domain: Optional[str]) -> bool:
    """
    Indique si le domaine mail est coherent avec le site de l'entreprise.

    @param website_domain: Domaine site normalise
    @param mail_domain: Domaine email
    @returns: True si coherent (a conserver)
    @example:
        >>> domains_compatible('fdc55.com', 'contact.fdc55.fr')
        True
        >>> domains_compatible('fdc55.com', 'meuse.gouv.fr')
        False
    """
    site = (website_domain or '').strip().lower()
    mail = (mail_domain or '').strip().lower()
    if not site or not mail:
        return True
    if mail in FREE_MAIL_DOMAINS:
        return True
    if mail == site or mail.endswith('.' + site) or site.endswith('.' + mail):
        return True
    site_labels = _labels(site)
    mail_labels = _labels(mail)
    if site_labels and mail_labels and (site_labels & mail_labels):
        return True
    return False
