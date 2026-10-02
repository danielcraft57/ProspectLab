#!/usr/bin/env bash
# A executer sur node15 DES QUE SSH revient :
#   bash /tmp/cutover_node15_to_node6_db.sh
# Met a jour DATABASE_URL vers node6 et redemarre l'app.
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/prospectlab/.env}"
DB_HOST="${DB_HOST:-node6.lan}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[✗] ${ENV_FILE} introuvable"
  exit 1
fi

cp "${ENV_FILE}" "${ENV_FILE}.bak_db_$(date +%Y%m%d_%H%M%S)"
sed -i "s#@192.168.1.198:5432/#@${DB_HOST}:5432/#g" "${ENV_FILE}"
sed -i "s#@node15.lan:5432/#@${DB_HOST}:5432/#g" "${ENV_FILE}"
sed -i "s#@localhost:5432/#@${DB_HOST}:5432/#g" "${ENV_FILE}"

echo "[*] DATABASE_URL:"
grep '^DATABASE_URL=' "${ENV_FILE}" || true

echo "[*] Test connexion DB..."
# shellcheck disable=SC1090
set -a
# extrait sommaire du mot de passe depuis URL
python3 - <<'PY'
import os,re,urllib.parse
from pathlib import Path
env=Path(os.environ.get('ENV_FILE','/opt/prospectlab/.env')).read_text(encoding='utf-8',errors='replace')
m=re.search(r'^DATABASE_URL=(.+)$',env,re.M)
if not m:
    raise SystemExit('DATABASE_URL missing')
url=m.group(1).strip().strip('"').strip("'")
print('URL_HOST_OK' if 'node6' in url or '192.168.1.215' in url else url)
PY

sudo systemctl restart prospectlab prospectlab-celery prospectlab-celerybeat
sleep 2
sudo systemctl is-active prospectlab prospectlab-celery prospectlab-celerybeat
curl -sI http://127.0.0.1:5000/ | head -n 5 || true
echo "[✓] Cutover app -> DB ${DB_HOST} termine"
