#!/bin/bash
# Script wrapper pour démarrer Celery Worker avec la concurrency depuis .env
# Systemd charge déjà le .env via EnvironmentFile, donc CELERY_WORKERS est disponible

cd /opt/prospectlab || exit 1

# Utiliser CELERY_WORKERS depuis l'environnement (chargé par systemd), défaut à 6
CELERY_WORKERS=${CELERY_WORKERS:-6}

# Lancer Celery Worker avec la concurrency configurée
# Pour systemd forking, on doit démarrer en arrière-plan et retourner immédiatement
exec /opt/prospectlab/venv/bin/celery -A celery_app worker \
    --loglevel=info \
    --logfile=/opt/prospectlab/logs/celery_worker.log \
    --pidfile=/opt/prospectlab/celery_worker.pid \
    --pool=threads \
    --concurrency=${CELERY_WORKERS}

