#!/usr/bin/env bash
# Stoppe Celery worker + beat (Debian/Bookworm)
# Envoie un SIGTERM aux process celery et run_celery.py
set -e
echo "[*] Arret de Celery..."
pkill -f "celery" || true
pkill -f "run_celery.py" || true
echo "[*] Celery stoppé (si des processus étaient en cours)."

