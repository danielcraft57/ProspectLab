#!/usr/bin/env bash
# Supprime le compteur d'étalement global WebSocket (Redis).
# À utiliser si les analyses semblent « gelées » : l'ancienne version pouvait accumuler
# un countdown de plusieurs heures (clé prospectlab:heavy:stagger:seq).
#
# La base Redis (/0, /1, …) doit être celle de CELERY_BROKER_URL. Ce script utilise
# la même URL que l'app (config + .env).
#
# Usage : cd /opt/prospectlab && bash scripts/linux/reset_prospectlab_stagger_counter.sh

set -e
cd "$(dirname "$0")/../.." 2>/dev/null || cd /opt/prospectlab
env/bin/python << 'PY'
from config import CELERY_BROKER_URL
import redis
r = redis.Redis.from_url(CELERY_BROKER_URL, decode_responses=True)
n = r.delete("prospectlab:heavy:stagger:seq")
print("DEL prospectlab:heavy:stagger:seq ->", n, "(1=clé supprimée, 0=absente)")
PY
