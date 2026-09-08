"""
Helpers pour la gestion des templates avec support de la nouvelle architecture
"""

import os
import time
from flask import render_template


def _static_asset_version():
    """Version cache-buster basée sur la date de modif des assets critiques."""
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(root, 'static', 'js', 'campagnes.js'),
            os.path.join(root, 'static', 'css', 'modules', 'pages', 'campagnes.css'),
        ]
        mtimes = [os.path.getmtime(p) for p in candidates if os.path.isfile(p)]
        if mtimes:
            return str(int(max(mtimes)))
    except OSError:
        pass
    return str(int(time.time()))


_DEFAULT_ASSET_VERSION = _static_asset_version()


def render_page(template_name, **kwargs):
    """
    Rend un template avec fallback automatique vers pages/
    
    Args:
        template_name: Nom du template (sans extension .html)
        **kwargs: Arguments à passer au template
    
    Returns:
        Rendered template
    
    Exemples:
        render_page('dashboard') -> cherche pages/dashboard.html puis dashboard.html
        render_page('pages/dashboard') -> cherche pages/dashboard.html directement
    """
    # Cache-buster pour les assets (JS/CSS) afin d'éviter que le navigateur garde une ancienne version.
    # Surcharge possible via .env: APP_BUILD_ID=20260330-1 (par ex).
    kwargs.setdefault('asset_version', (os.getenv('APP_BUILD_ID') or '').strip() or _DEFAULT_ASSET_VERSION)

    # Si le nom contient déjà 'pages/', utiliser tel quel
    if template_name.startswith('pages/'):
        try:
            return render_template(template_name, **kwargs)
        except:
            # Fallback sur la racine si pages/ n'existe pas
            fallback_name = template_name.replace('pages/', '')
            return render_template(fallback_name, **kwargs)
    
    # Sinon, essayer pages/ d'abord, puis fallback sur racine
    try:
        return render_template(f'pages/{template_name}', **kwargs)
    except:
        return render_template(template_name, **kwargs)

