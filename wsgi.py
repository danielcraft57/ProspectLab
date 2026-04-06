"""
Point d'entrée WSGI pour un serveur de production (Gunicorn, etc.).

    set FLASK_DEBUG=0
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app

Avec Flask-SocketIO, utiliser un worker compatible (souvent eventlet, 1 worker) ;
voir docs/configuration/DEPLOIEMENT_PRODUCTION.md et commentaires dans app.py.
"""
import os

os.environ.setdefault('FLASK_DEBUG', '0')

from app import app  # noqa: E402

__all__ = ['app']
