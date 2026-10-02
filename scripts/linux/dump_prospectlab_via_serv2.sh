#!/usr/bin/env bash
# Dump ProspectLab depuis node15 (PG17) via LAN, avec pg_dump 17.
# Exclut les DATA de analyses_seo (toast corrompu).
set -euo pipefail

SRC_HOST="${SRC_HOST:-192.168.1.198}"
SRC_PORT="${SRC_PORT:-5432}"
DB_NAME="${DB_NAME:-prospectlab}"
DB_USER="${DB_USER:-prospectlab}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD requis}"
OUT_DIR="${OUT_DIR:-/tmp/prospectlab_backups}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${OUT_DIR}/${DB_NAME}_from_node15_${TS}.sql.gz"
ERR_LOG="/tmp/pg_dump_lan_err.log"

export PGPASSWORD="${DB_PASSWORD}"
mkdir -p "${OUT_DIR}"

echo "[*] Test connexion..."
psql -h "${SRC_HOST}" -p "${SRC_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "SELECT version();"

echo "[*] Dump exclude-table-data=analyses_seo -> ${OUT_FILE}"
if pg_dump -h "${SRC_HOST}" -p "${SRC_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
  --no-owner --no-acl \
  --exclude-table-data=public.analyses_seo \
  2>"${ERR_LOG}" | gzip > "${OUT_FILE}"; then
  SIZE="$(stat -c%s "${OUT_FILE}")"
  echo "DUMP_OK ${OUT_FILE} SIZE=${SIZE}"
  ls -lh "${OUT_FILE}"
else
  echo "DUMP_FAIL"
  tail -n 100 "${ERR_LOG}" || true
  rm -f "${OUT_FILE}"
  exit 1
fi
