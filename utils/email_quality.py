"""
Helpers pour filtrer les emails de mauvaise qualité (campagnes + scraper).

Exemples exclus :
- adresses fictives de templates (IONOS, etc.)
- faux positifs d'images / assets (`logo@2x.png`, `plan@150x.webp`)
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

# Dernier label de domaine qui ressemble a une extension de fichier (pas un TLD mail).
FILE_LIKE_DOMAIN_LABELS = frozenset({
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp', 'tif', 'tiff', 'avif', 'heic',
    'css', 'js', 'mjs', 'cjs', 'map', 'json', 'xml', 'html', 'htm', 'php', 'asp', 'aspx', 'jsp',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'txt', 'rtf', 'odt',
    'zip', 'rar', '7z', 'gz', 'tar', 'tgz', 'bz2',
    'mp3', 'mp4', 'avi', 'mov', 'webm', 'mkv', 'wav', 'ogg',
    'woff', 'woff2', 'ttf', 'eot', 'otf',
    'scss', 'less', 'sass', 'vue', 'jsx', 'ts', 'tsx',
    'py', 'rb', 'java', 'class', 'jar', 'dll', 'exe', 'bin', 'dat',
    'sql', 'bak', 'log', 'md', 'yml', 'yaml', 'toml', 'ini', 'cfg', 'conf',
})


def email_domain(email: Optional[str]) -> str:
    """
    Extrait le domaine d'une adresse email (partie apres @).

    @param email: Adresse email eventuelle
    @returns: Domaine en minuscules, ou chaine vide
    """
    if not email or '@' not in str(email):
        return ''
    return str(email).rsplit('@', 1)[-1].strip().lower()


def is_file_like_email(email: Optional[str]) -> bool:
    """
    Indique si l'adresse ressemble a un faux positif d'asset (image, js, css...).

    Exemples : ``logo@2x.png``, ``plan@150x.webp``, ``script@app.js``.

    @param email: Adresse a evaluer
    @returns: True si le domaine n'est pas un vrai domaine mail
    @example:
        >>> is_file_like_email('cropped-favicon@2x-32x32.png')
        True
        >>> is_file_like_email('contact@danielcraft.fr')
        False
    """
    domain = email_domain(email)
    if not domain:
        return True
    # Un vrai domaine mail a au moins un point (exemple.fr)
    if '.' not in domain:
        return True
    last_label = domain.rsplit('.', 1)[-1].strip().lower()
    if not last_label:
        return True
    # TLD purement numerique (ex. @2x-300x160) deja couvert si last = 'jpg'
    if last_label in FILE_LIKE_DOMAIN_LABELS:
        return True
    # Domaine entierement "extension" apres suppression des tailles (@2x.png deja gere)
    if last_label.isdigit():
        return True
    return False


def is_placeholder_email(email: Optional[str], source: Optional[str] = None) -> bool:
    """
    Indique si l'email (ou sa source) ressemble a un faux contact.

    Couvre : domaines fictifs, pages templates, et faux positifs fichiers.

    @param email: Adresse email a evaluer
    @param source: URL ou libelle de provenance (ex. page_url scraper)
    @returns: True si l'adresse doit etre ecartee des campagnes / scrapes
    @example:
        >>> is_placeholder_email('info@exemple.fr')
        True
        >>> is_placeholder_email('logo@2x.png')
        True
    """
    if is_file_like_email(email):
        return True

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
