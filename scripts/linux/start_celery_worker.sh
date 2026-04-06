#!/bin/bash
# Script wrapper pour le worker Celery sous systemd (production).
# OBLIGATOIRE : consommer toutes les files lourdes (technical, scraping, seo, osint, pentest, …).
# Sinon les tâches routées vers ces files restent PENDING (« Tâche en file… »), y compris le pack « analyse site complet » (file technical par défaut, ou website_full si isolé).
#
# Variables (via EnvironmentFile=.env dans l'unité systemd) :
#   CELERY_WORKERS                  défaut 6
#   CELERY_WORKER_QUEUES            surcharge la liste ci-dessous si défini dans .env
#   CELERY_WORKER_QUEUE_PRESET    optionnel : full (implicite) | scraping_only | non_scraping
#                                   définit la liste par défaut si CELERY_WORKER_QUEUES est absent

cd /opt/prospectlab || exit 1

CELERY_WORKERS="${CELERY_WORKERS:-6}"
# Liste par défaut selon preset (surchargée par CELERY_WORKER_QUEUES dans .env).
# scraping_interactive : scrape unitaire Socket.IO (ne pas rester derrière scrape_analysis bulk sur scraping).
_DEFAULT_Q="celery,scraping,scraping_interactive,technical,seo,osint,pentest,heavy,website_full"
case "${CELERY_WORKER_QUEUE_PRESET:-}" in
    scraping_only)
        _DEFAULT_Q="scraping,scraping_interactive"
        ;;
    non_scraping)
        _DEFAULT_Q="celery,technical,seo,osint,pentest,heavy,website_full"
        ;;
esac
CELERY_WORKER_QUEUES="${CELERY_WORKER_QUEUES:-$_DEFAULT_Q}"
# Option -Q : pas d'espaces (si .env = uniquement des espaces, tr donne "" → Celery démarre avec « -Q » vide et ne consomme rien correctement)
CELERY_Q=$(echo "${CELERY_WORKER_QUEUES}" | tr -d ' ')
if [ -z "$CELERY_Q" ]; then
    CELERY_Q="celery,scraping,scraping_interactive,technical,seo,osint,pentest,heavy,website_full"
fi

# Aide au diagnostic cluster : si « scraping » n’est pas dans -Q, les bulk (scrape_analysis_*)
# ne seront jamais pris sur ce nœud (seul un worker qui écoute « scraping » les exécute).
case ",${CELERY_Q}," in
    *,scraping,*) ;;
    *)
        echo "prospectlab-celery: ATTENTION: la file « scraping » est absente de -Q (${CELERY_Q})." >&2
        echo "prospectlab-celery: Les tâches bulk de scraping ne seront pas exécutées sur ce nœud." >&2
        echo "prospectlab-celery: Ajoute « scraping » à CELERY_WORKER_QUEUES ou enlève CELERY_WORKER_QUEUE_PRESET=non_scraping." >&2
        ;;
esac
echo "prospectlab-celery: démarrage avec -Q ${CELERY_Q}" >&2

exec /opt/prospectlab/env/bin/celery -A celery_app worker \
    --loglevel=info \
    --logfile=/opt/prospectlab/logs/celery_worker.log \
    --pidfile=/opt/prospectlab/celery_worker.pid \
    --pool=threads \
    --concurrency="${CELERY_WORKERS}" \
    -Q "${CELERY_Q}"
