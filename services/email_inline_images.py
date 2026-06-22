"""
Inlining des images locales static/email/ pour preview navigateur et envoi SMTP (CID).
"""

from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

STATIC_EMAIL_MARKER = '/static/email/'


def _static_email_root() -> Path:
    """Racine des assets email versionnés dans le dépôt."""
    return (Path(__file__).resolve().parent.parent / 'static' / 'email').resolve()


def extract_static_email_relative(url: str) -> Optional[str]:
    """
    Extrait le chemin relatif sous static/email/ depuis une URL ou un src HTML.

    @param url - Valeur de l'attribut src (absolue ou relative)
    @returns Chemin relatif (ex. facturio/hero.png) ou None
    """
    if not isinstance(url, str) or not url.strip():
        return None
    raw = url.strip().strip('"').strip("'")
    lower = raw.lower()
    marker = STATIC_EMAIL_MARKER
    idx = lower.find(marker)
    if idx < 0:
        if lower.startswith('static/email/'):
            return raw.split('?', 1)[0].split('#', 1)[0].replace('static/email/', '', 1).lstrip('/')
        return None
    rel = raw[idx + len(marker):]
    rel = rel.split('?', 1)[0].split('#', 1)[0].lstrip('/')
    return rel or None


def resolve_static_email_file(url: str) -> Optional[Path]:
    """
    Résout un src HTML vers un fichier local sous static/email/.

    @param url - src de la balise img
    @returns Path du fichier ou None
    """
    rel = extract_static_email_relative(url)
    if not rel:
        return None
    root = _static_email_root()
    candidate = (root / rel).resolve()
    if not str(candidate).startswith(str(root)):
        return None
    return candidate if candidate.is_file() else None


def _image_mime_subtype(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in ('.jpg', '.jpeg'):
        return 'jpeg'
    if ext == '.gif':
        return 'gif'
    if ext == '.webp':
        return 'webp'
    return 'png'


def inline_images_for_browser_preview(html: str) -> str:
    """
    Remplace les src static/email/ par des data URI pour l'aperçu dans l'UI (iframe).

    @param html - HTML du modèle (base_url déjà substitué si besoin)
    @returns HTML avec images embarquées en base64
    """
    if not isinstance(html, str) or '<img' not in html:
        return html

    pattern = re.compile(r'(src\s*=\s*["\'])([^"\']+)(["\'])', flags=re.IGNORECASE)

    def repl(match: re.Match) -> str:
        prefix, src, suffix = match.group(1), match.group(2), match.group(3)
        file_path = resolve_static_email_file(src)
        if not file_path:
            return match.group(0)
        mime = _image_mime_subtype(file_path)
        encoded = base64.b64encode(file_path.read_bytes()).decode('ascii')
        return f'{prefix}data:image/{mime};base64,{encoded}{suffix}'

    return pattern.sub(repl, html)


def embed_images_as_cid(html: str) -> Tuple[str, List]:
    """
    Transforme les images static/email/ en références cid: pour envoi SMTP.

    @param html - HTML rendu prêt à l'envoi
    @returns Tuple (html modifié, parties MIMEImage à attacher)
    """
    if not isinstance(html, str) or '<img' not in html:
        return html, []

    from email.mime.image import MIMEImage

    images: List[MIMEImage] = []
    pattern = re.compile(r'(src\s*=\s*["\'])([^"\']+)(["\'])', flags=re.IGNORECASE)

    def repl(match: re.Match) -> str:
        prefix, src, suffix = match.group(1), match.group(2), match.group(3)
        file_path = resolve_static_email_file(src)
        if not file_path:
            return match.group(0)
        cid = f'img_{uuid.uuid4().hex[:12]}@prospectlab'
        subtype = _image_mime_subtype(file_path)
        part = MIMEImage(file_path.read_bytes(), _subtype=subtype)
        part.add_header('Content-ID', f'<{cid}>')
        part.add_header('Content-Disposition', 'inline', filename=file_path.name)
        images.append(part)
        return f'{prefix}cid:{cid}{suffix}'

    return pattern.sub(repl, html), images
