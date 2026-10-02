#!/usr/bin/env bash
# Dump resilient : schema complet + data table par table, ignore les tables corrompues.
set -euo pipefail

SRC_HOST="${SRC_HOST:-192.168.1.198}"
DB_NAME="${DB_NAME:-prospectlab}"
DB_USER="${DB_USER:-prospectlab}"
DB_PASSWORD="${DB_PASSWORD:?required}"
OUT_DIR="${OUT_DIR:-/tmp/prospectlab_backups}"
TS="$(date +%Y%m%d_%H%M%S)"
WORK="${OUT_DIR}/work_${TS}"
OUT_FILE="${OUT_DIR}/${DB_NAME}_resilient_${TS}.sql.gz"
SKIP_LOG="${OUT_DIR}/skipped_tables_${TS}.txt"

export PGPASSWORD="${DB_PASSWORD}"
mkdir -p "${WORK}"
: > "${SKIP_LOG}"

echo "[1/3] Schema-only dump..."
pg_dump -h "${SRC_HOST}" -U "${DB_USER}" -d "${DB_NAME}" --schema-only --no-owner --no-acl \
  > "${WORK}/00_schema.sql"

echo "[2/3] Liste des tables..."
mapfile -t TABLES < <(psql -h "${SRC_HOST}" -U "${DB_USER}" -d "${DB_NAME}" -Atc \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")

echo "  ${#TABLES[@]} tables"
ok=0
fail=0
for t in "${TABLES[@]}"; do
  echo -n "  data ${t}... "
  if pg_dump -h "${SRC_HOST}" -U "${DB_USER}" -d "${DB_NAME}" \
    --data-only --no-owner --no-acl \
    --table="public.${t}" \
    > "${WORK}/data_${t}.sql" 2>"${WORK}/err_${t}.log"; then
    echo OK
    ok=$((ok+1))
  else
    echo SKIP
    echo "${t}" >> "${SKIP_LOG}"
    cat "${WORK}/err_${t}.log" >> "${SKIP_LOG}"
    echo "-----" >> "${SKIP_LOG}"
    rm -f "${WORK}/data_${t}.sql"
    fail=$((fail+1))
  fi
done

echo "[3/3] Assemblage gzip..."
{
  cat "${WORK}/00_schema.sql"
  echo ""
  echo "-- DATA START"
  for f in "${WORK}"/data_*.sql; do
    [[ -f "$f" ]] || continue
    cat "$f"
  done
} | gzip > "${OUT_FILE}"

SIZE="$(stat -c%s "${OUT_FILE}")"
echo "DUMP_OK ${OUT_FILE} SIZE=${SIZE} OK_TABLES=${ok} SKIPPED=${fail}"
ls -lh "${OUT_FILE}"
echo "Skipped list: ${SKIP_LOG}"
cat "${SKIP_LOG}" || true
