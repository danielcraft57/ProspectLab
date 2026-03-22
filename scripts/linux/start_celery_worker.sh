#!/bin/bash
# Script wrapper pour le worker Celery sous systemd (production).
# OBLIGATOIRE : consommer les files « celery » ET « heavy » (SEO, technique, pentest, OSINT, scraping lourd).
# Sans « -Q celery,heavy », seules les tâches sur la file par défaut « celery » sont exécutées — les analyses lourdes restent en file d'attente indéfiniment.
#
# Variables (via EnvironmentFile=.env dans l'unité systemd) :
#   CELERY_WORKERS          défaut 6
#   CELERY_WORKER_QUEUES    défaut celery,heavy (voir config.CELERY_WORKER_QUEUES)

cd /opt/prospectlab || exit 1

CELERY_WORKERS="${CELERY_WORKERS:-6}"
CELERY_WORKER_QUEUES="${CELERY_WORKER_QUEUES:-celery,heavy}"
# Option -Q : pas d'espaces (si .env = uniquement des espaces, tr donne "" → Celery démarre avec « -Q » vide et ne consomme rien correctement)
CELERY_Q=$(echo "${CELERY_WORKER_QUEUES}" | tr -d ' ')
if [ -z "$CELERY_Q" ]; then
    CELERY_Q="celery,heavy"
fi

exec /opt/prospectlab/env/bin/celery -A celery_app worker \
    --loglevel=info \
    --logfile=/opt/prospectlab/logs/celery_worker.log \
    --pidfile=/opt/prospectlab/celery_worker.pid \
    --pool=threads \
    --concurrency="${CELERY_WORKERS}" \
    -Q "${CELERY_Q}"
