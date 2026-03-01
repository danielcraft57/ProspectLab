#!/usr/bin/env bash
# Démarre uniquement Celery beat (Debian/Bookworm). Utilise l'env Conda (env) ou venv.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "[*] Demarrage de Celery beat..."
if [ -x "env/bin/celery" ]; then
    exec env/bin/celery -A celery_app beat --loglevel=info
elif [ -x "venv/bin/celery" ]; then
    exec venv/bin/celery -A celery_app beat --loglevel=info
else
    exec celery -A celery_app beat --loglevel=info
fi

