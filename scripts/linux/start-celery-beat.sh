#!/usr/bin/env bash
# Démarre uniquement Celery beat (Debian/Bookworm)
set -e
echo "[*] Demarrage de Celery beat..."
source venv/bin/activate 2>/dev/null || true
celery -A celery_app beat --loglevel=info

