"""
Regles deterministes de classification des reponses IMAP (hors bounce NDR).
"""

from __future__ import annotations

from typing import Optional

OOO_MARKERS = (
    'out of office',
    'out-of-office',
    'automatic reply',
    'auto-reply',
    'autoreply',
    'réponse automatique',
    'reponse automatique',
    'absence du bureau',
    'absente du bureau',
    'absent du bureau',
    'je suis absent',
    'je suis absente',
    'i am away',
    'i am currently out',
    'annual leave',
    'congé',
    'conges',
    'congés',
)

TICKET_MARKERS = (
    'ticket',
    'helpdesk',
    'votre demande a bien été',
    'votre demande a bien ete',
    'demande d\'assistance',
    'demande d assistance',
    'epagine',
    'dossier a été ouvert',
    'dossier a ete ouvert',
    'we have received your request',
    'votre demande a été reçue',
    'votre demande a ete recue',
)

NOISE_MARKERS = (
    'notifications@github.com',
    'github.com',
    'no-reply@',
    'noreply@',
    'mailer-daemon',
    'postmaster@',
    'workflow run',
    'cd node15',
    'ci - main',
    'test email',
    'test passage brevo',
)


def classify_imap_reply(
    *,
    subject: Optional[str] = None,
    preview: Optional[str] = None,
    from_addr: Optional[str] = None,
    looks_like_campaign_reply: bool = False,
) -> str:
    """
    Classe un message IMAP non-bounce dans une categorie inbox.

    @param subject: Sujet du message
    @param preview: Apercu corps texte
    @param from_addr: Expediteur
    @param looks_like_campaign_reply: True si In-Reply-To / sujet croise une campagne PL
    @returns: Categorie ``auto_ooo`` | ``ticket_auto`` | ``noise`` | ``human_reply``
    @example:
        >>> classify_imap_reply(subject='Automatic reply: Hello', preview='I am away')
        'auto_ooo'
    """
    subj = (subject or '').lower()
    body = (preview or '').lower()
    frm = (from_addr or '').lower()
    blob = f'{subj}\n{body}\n{frm}'

    if any(m in blob for m in OOO_MARKERS):
        return 'auto_ooo'
    if any(m in blob for m in TICKET_MARKERS):
        return 'ticket_auto'
    if any(m in blob for m in NOISE_MARKERS):
        return 'noise'
    if looks_like_campaign_reply:
        return 'human_reply'
    # Par defaut : humain si ca ne matche rien d'automatique
    return 'human_reply'


def map_brevo_event_to_category(event_name: Optional[str]) -> Optional[str]:
    """
    Mappe un nom d'evenement Brevo vers une categorie ``inbox_events``.

    @param event_name: Nom brut Brevo (hardBounces, loadedByProxy, …)
    @returns: Categorie ou None si non pertinent
    """
    name = (event_name or '').strip()
    mapping = {
        'hardBounces': 'bounce_hard',
        'softBounces': 'bounce_soft',
        'blocked': 'blocked',
        'loadedByProxy': 'open_proxy',
        'spam': 'noise',
        'invalid': 'bounce_hard',
        'error': 'noise',
    }
    return mapping.get(name)
