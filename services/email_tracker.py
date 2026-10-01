"""
Service de tracking des emails

Gère le tracking des ouvertures, clics et temps de lecture des emails
"""

import secrets
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from html.parser import HTMLParser
from typing import Dict, List, Optional


def _normalize_tracker_base_url(base_url: str) -> str:
    """
    Normalise l'URL de base du tracker (slash final + réparation .f → .fr).

    @param base_url: URL publique de l'app (tracking)
    @returns: URL sans slash final, hôtes danielcraft réparés si besoin
    """
    try:
        from config import normalize_public_base_url

        return normalize_public_base_url(base_url or '', source='EmailTracker')
    except Exception:
        url = (base_url or '').strip().replace('\r', '').replace('\n', '')
        while url.endswith('/'):
            url = url[:-1]
        # Filet de sécurité si config indisponible
        url = re.sub(
            r'\.f(?!r)(?=/|$|\?|#|"|\'|\s)',
            '.fr',
            url,
            flags=re.IGNORECASE,
        )
        return url or 'http://localhost:5000'


class EmailTracker:
    """
    Service pour tracker les emails envoyés
    """

    def __init__(self, base_url='http://localhost:5000'):
        """
        Initialise le tracker

        Args:
            base_url: URL de base de l'application (pour les liens de tracking)
        """
        self.base_url = _normalize_tracker_base_url(base_url)

    def generate_tracking_token(self) -> str:
        """
        Génère un token de tracking unique

        Returns:
            str: Token unique
        """
        return secrets.token_urlsafe(32)

    def inject_tracking_pixel(self, html_content: str, tracking_token: str) -> str:
        """
        Injecte un pixel de tracking invisible dans le HTML.

        Combine une balise img (Gmail) et un background CSS (clients qui
        rendent les styles). Les hits trop tot ou automatiques sont filtres
        cote serveur, pas ici.

        @param html_content: Contenu HTML de l'email
        @param tracking_token: Token de tracking unique
        @returns: HTML avec le pixel de tracking
        """
        tracking_url = f'{self.base_url}/track/pixel/{tracking_token}'
        img_url = f'{tracking_url}?ch=img'
        css_url = f'{tracking_url}?ch=css'

        # Img pour Gmail (le proxy ne charge souvent pas les backgrounds CSS).
        # CSS en plus: certains scanners ne fetchent que les <img src>.
        tracking_pixel = (
            f'<div class="pl-o" style="line-height:1px;font-size:1px;max-height:1px;'
            f'overflow:hidden;width:1px;height:1px;">'
            f'<img src="{img_url}" width="1" height="1" alt="" loading="lazy" '
            f'style="display:none;border:0;outline:none;width:1px;height:1px;" />'
            f'</div>'
            f'<style>@media screen{{.pl-o{{background-image:url(\'{css_url}\')!important;}}}}</style>'
        )

        # Si le HTML contient un </body>, insérer avant
        if '</body>' in html_content.lower():
            html_content = re.sub(
                r'</body>',
                f'{tracking_pixel}</body>',
                html_content,
                flags=re.IGNORECASE
            )
        # Sinon, ajouter à la fin
        else:
            html_content += tracking_pixel

        return html_content

    def track_links(self, html_content: str, tracking_token: str) -> str:
        """
        Modifie tous les liens dans le HTML pour ajouter le tracking
        
        Args:
            html_content: Contenu HTML de l'email
            tracking_token: Token de tracking unique

        Returns:
            str: HTML modifié avec les liens trackés
        """
        def replace_link(match):
            """
            Remplace un lien par sa version trackée
            """
            full_tag = match.group(0)
            href = match.group(1)

            # Ignorer les liens mailto:, tel:, javascript:, etc.
            if any(href.lower().startswith(prefix) for prefix in ['mailto:', 'tel:', 'javascript:', '#']):
                return full_tag

            # Construire l'URL de tracking
            tracking_url = f'{self.base_url}/track/click/{tracking_token}'

            # Encoder l'URL de destination
            from urllib.parse import quote
            encoded_url = quote(href, safe='')

            # Nouveau href avec redirection
            new_href = f'{tracking_url}?url={encoded_url}'

            # Remplacer le href dans le tag
            return full_tag.replace(f'href="{href}"', f'href="{new_href}"')

        # Pattern pour trouver tous les liens <a href="...">
        link_pattern = r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>'

        # Remplacer tous les liens
        html_content = re.sub(link_pattern, replace_link, html_content, flags=re.IGNORECASE)

        return html_content

    def process_email_content(self, html_content: str, tracking_token: str) -> str:
        """
        Traite le contenu HTML d'un email pour ajouter le tracking complet.

        Répare aussi d'éventuels hôtes ``danielcraft.f`` tronqués avant injection.

        @param html_content: Contenu HTML de l'email
        @param tracking_token: Token de tracking unique
        @returns: HTML modifié avec tracking
        """
        try:
            from config import repair_truncated_danielcraft_urls

            html_content = repair_truncated_danielcraft_urls(html_content or '')
        except Exception:
            html_content = re.sub(
                r'\.f(?!r)(?=/|$|\?|#|"|\'|\s)',
                '.fr',
                html_content or '',
                flags=re.IGNORECASE,
            )

        # D'abord tracker les liens
        html_content = self.track_links(html_content, tracking_token)

        # Ensuite injecter le pixel
        html_content = self.inject_tracking_pixel(html_content, tracking_token)

        return html_content

    def convert_text_to_html(self, text_content: str) -> str:
        """
        Convertit un texte brut en HTML (pour le tracking)

        Args:
            text_content: Contenu texte brut

        Returns:
            str: Contenu HTML
        """
        # Échapper les caractères HTML
        from html import escape
        html = escape(text_content)

        # Convertir les retours à la ligne en <br>
        html = html.replace('\n', '<br>\n')

        # Convertir les URLs en liens
        url_pattern = r'(https?://[^\s<>"]+)'
        html = re.sub(url_pattern, r'<a href="\1">\1</a>', html)

        return f'<html><body>{html}</body></html>'

