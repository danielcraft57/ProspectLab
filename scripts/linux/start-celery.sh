#!/usr/bin/env bash
# Démarre Celery worker + beat (Debian/Bookworm). Utilise l'env Conda (env) ou venv.
# Utilise run_celery.py pour démarrer worker et beat ensemble.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "[*] Demarrage de Celery (worker + beat)..."
if [ -x "env/bin/python" ]; then
    exec env/bin/python run_celery.py
elif [ -x "venv/bin/python" ]; then
    exec venv/bin/python run_celery.py
else
    exec python run_celery.py
fi

