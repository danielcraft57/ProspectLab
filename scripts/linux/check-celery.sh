#!/usr/bin/env bash
# Vérifie l'état des workers Celery (Debian/Bookworm)
set -e
echo "[*] Statut des workers Celery..."
celery -A celery_app status || { echo "[!] Celery ne répond pas"; exit 1; }

