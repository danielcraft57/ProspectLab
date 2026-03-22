#!/usr/bin/env bash
# Affiche CELERY_BROKER_URL / CELERY_RESULT_BACKEND tels que les voit Python (après .env).
# À comparer avec la bannière du worker : « transport: redis://... » doit être identique.
# Usage : cd /opt/prospectlab && bash scripts/linux/print_celery_broker.sh

set -e
cd "$(dirname "$0")/../.." 2>/dev/null || cd /opt/prospectlab
if [ ! -x "env/bin/python" ]; then
  echo "[!] env/bin/python introuvable (lance depuis la racine du projet)" >&2
  exit 1
fi
exec env/bin/python -c "
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
print('CELERY_BROKER_URL     =', CELERY_BROKER_URL)
print('CELERY_RESULT_BACKEND =', CELERY_RESULT_BACKEND)
"
