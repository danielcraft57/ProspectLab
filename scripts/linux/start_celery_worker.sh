#!/bin/bash
# Script wrapper pour le worker Celery sous systemd (production).
# OBLIGATOIRE : consommer toutes les files lourdes (technical, scraping, seo, osint, pentest, …).
# Sinon les tâches routées vers ces files restent PENDING (« Tâche en file… »), y compris le pack « analyse site complet » (file technical par défaut, ou website_full si isolé).
#
# Variables (via EnvironmentFile=.env dans l'unité systemd) :
#   CELERY_WORKERS          défaut 6
#   CELERY_WORKER_QUEUES    défaut celery,heavy (voir config.CELERY_WORKER_QUEUES)

cd /opt/prospectlab || exit 1

CELERY_WORKERS="${CELERY_WORKERS:-6}"
# Par défaut, écouter toutes les queues de ProspectLab (tâches lourdes spécialisées).
# `heavy` est conservée en compat (si des tâches historiques y sont encore routées).
CELERY_WORKER_QUEUES="${CELERY_WORKER_QUEUES:-celery,scraping,technical,seo,osint,pentest,heavy,website_full}"
# Option -Q : pas d'espaces (si .env = uniquement des espaces, tr donne "" → Celery démarre avec « -Q » vide et ne consomme rien correctement)
CELERY_Q=$(echo "${CELERY_WORKER_QUEUES}" | tr -d ' ')
if [ -z "$CELERY_Q" ]; then
    CELERY_Q="celery,scraping,technical,seo,osint,pentest,heavy"
fi

exec /opt/prospectlab/env/bin/celery -A celery_app worker \
    --loglevel=info \
    --logfile=/opt/prospectlab/logs/celery_worker.log \
    --pidfile=/opt/prospectlab/celery_worker.pid \
    --pool=threads \
    --concurrency="${CELERY_WORKERS}" \
    -Q "${CELERY_Q}"
