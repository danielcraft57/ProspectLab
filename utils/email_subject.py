"""
Helpers pour nettoyer les sujets d'emails de campagne.
"""

from __future__ import annotations

import re
from typing import Optional

_EMPTY_PARENS_RE = re.compile(r'\(\s*\)')
_MULTI_SPACE_RE = re.compile(r'[ \t]{2,}')
_ORPHAN_SEP_RE = re.compile(r'[\s]*[-–—|:]\s*$')
_ORPHAN_SEP_START_RE = re.compile(r'^[\s]*[-–—|:]\s*')
_TITLE_PREFIX_RE = re.compile(r'^(?:objet|subject|sujet)\s*:\s*', re.IGNORECASE)
_DISPLAY_TAG_PREFIX_RE = re.compile(r'^(?:sécu|secu)\s*:\s*', re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r'\{[a-zA-Z0-9_\-]+\}')
_SUBJECT_COMMENT_RE = re.compile(r'<!--\s*SUBJECT:\s*(.*?)\s*-->', re.IGNORECASE | re.DOTALL)
_HTML_TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)
_POUR_ORPHAN_RE = re.compile(r'\s+pour\s+[-–—]\s+', re.IGNORECASE)
_PREP_ORPHAN_RE = re.compile(r'\s+(?:sur|pour|de|à)\s+[-–—]\s+', re.IGNORECASE)
_LEADING_ORPHAN_RE = re.compile(r'^[,;:\-–—|]+\s*')


def normalize_template_value(value: Optional[str], fallback: str = '') -> str:
    """
    Normalise une valeur de template (nom / entreprise).

    Traite ``None``, chaines vides et marqueurs type ``N/A``.

    @param value: Valeur brute
    @param fallback: Valeur de remplacement si vide
    @returns: Chaine nettoyees ou fallback
    """
    text = (value or '').strip()
    if not text:
        return fallback
    if text.lower() in {'n/a', 'na', 'none', 'null', 'undefined', 'votre entreprise', 'monsieur/madame'}:
        return fallback
    return text


def clean_email_subject(subject: Optional[str]) -> str:
    """
    Nettoie un sujet apres formatage (parentheses vides, espaces, separateurs orphelins).

    @param subject: Sujet brut
    @returns: Sujet nettoye
    @example:
        >>> clean_email_subject('Sécu : clanche ouverte () Services')
        'Sécu : clanche ouverte Services'
        >>> clean_email_subject('Un mot pour  - ')
        'Un mot pour'
    """
    text = (subject or '').strip()
    if not text:
        return ''
    # Plusieurs passes pour () imbriques apres collapse
    for _ in range(3):
        cleaned = _EMPTY_PARENS_RE.sub('', text)
        if cleaned == text:
            break
        text = cleaned
    text = _MULTI_SPACE_RE.sub(' ', text).strip()
    text = _ORPHAN_SEP_RE.sub('', text).strip()
    text = _ORPHAN_SEP_START_RE.sub('', text).strip()
    text = _MULTI_SPACE_RE.sub(' ', text).strip()
    return text


def strip_template_title_prefix(text: Optional[str]) -> str:
    """
    Retire les préfixes techniques type « Objet: », « Subject: ».

    @param text: Titre ou sujet brut
    @returns: Texte sans préfixe editorial
    """
    value = (text or '').strip()
    if not value:
        return ''
    value = _TITLE_PREFIX_RE.sub('', value).strip()
    return value


def strip_template_display_tag_prefix(text: Optional[str]) -> str:
    """
    Retire les étiquettes d'affichage (ex. « Sécu: ») pour le nom UI d'un modèle.

    @param text: Nom brut
    @returns: Nom sans étiquette de catégorie
    """
    value = (text or '').strip()
    if not value:
        return ''
    return _DISPLAY_TAG_PREFIX_RE.sub('', value).strip()


def normalize_template_subject(raw: Optional[str]) -> str:
    """
    Normalise le sujet stocké en BDD (garde les placeholders, retire « Objet: »).

    @param raw: Sujet ou titre HTML brut
    @returns: Sujet prêt pour l'envoi
    """
    text = strip_template_title_prefix(raw)
    text = _MULTI_SPACE_RE.sub(' ', text).strip()
    return text


def infer_subject_from_html(html_text: str) -> str:
    """
    Déduit le sujet depuis les sources HTML (commentaire SUBJECT ou balise title).

    @param html_text: Contenu HTML du modèle
    @returns: Sujet normalisé avec placeholders
    """
    raw = ''
    match = _SUBJECT_COMMENT_RE.search(html_text or '')
    if match:
        raw = match.group(1).strip()
    else:
        title_match = _HTML_TITLE_RE.search(html_text or '')
        raw = (title_match.group(1) if title_match else '').strip()
    raw = re.sub(r'\s+', ' ', raw).strip()
    return normalize_template_subject(raw)


def humanize_template_name(subject_or_title: Optional[str], template_id: str = '') -> str:
    """
    Produit un nom lisible pour l'UI à partir du sujet HTML.

    Retire les préfixes « Objet: » / « Sécu: », les placeholders et les « () » vides.

    @param subject_or_title: Sujet ou titre source
    @param template_id: Identifiant technique (fallback)
    @returns: Nom affiché dans les listes
    @example:
        >>> humanize_template_name('Objet: Garage pret ({secteur_label})', 'html_dc_x')
        'Garage pret'
    """
    text = strip_template_title_prefix(subject_or_title)
    text = _PLACEHOLDER_RE.sub('', text).strip()
    text = _POUR_ORPHAN_RE.sub(' — ', text)
    text = _PREP_ORPHAN_RE.sub(' - ', text)
    text = clean_email_subject(text)
    text = strip_template_display_tag_prefix(text)
    text = _LEADING_ORPHAN_RE.sub('', text).strip()
    text = _MULTI_SPACE_RE.sub(' ', text).strip(' —-–')
    if text:
        return text[0].upper() + text[1:] if len(text) > 1 else text.upper()

    base = (template_id or '').strip()
    base = re.sub(r'^html_', '', base)
    base = base.replace('_', ' ').strip()
    return base[:1].upper() + base[1:] if base else template_id
