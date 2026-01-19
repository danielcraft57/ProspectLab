#!/usr/bin/env bash
# Démarre Celery worker + beat (Debian/Bookworm)
# Utilise run_celery.py pour démarrer worker et beat ensemble.
set -e
echo "[*] Demarrage de Celery (worker + beat)..."
source venv/bin/activate 2>/dev/null || true
python run_celery.py

