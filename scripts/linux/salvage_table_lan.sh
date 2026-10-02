#!/usr/bin/env bash
# Tente de sauver les lignes lisibles d'une table corrompue via zero_damaged_pages.
set -euo pipefail
SRC_HOST="${SRC_HOST:-192.168.1.198}"
DB_USER="${DB_USER:-prospectlab}"
DB_NAME="${DB_NAME:-prospectlab}"
DB_PASSWORD="${DB_PASSWORD:?required}"
TABLE="${TABLE:?required}"
OUT="${OUT:?required}"

export PGPASSWORD="${DB_PASSWORD}"
export PGOPTIONS="-c zero_damaged_pages=on"

echo "[*] Salvage ${TABLE} -> ${OUT}"
# COPY peut encore échouer; on tente aussi un SELECT COUNT
psql -h "${SRC_HOST}" -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=0 -c "SET zero_damaged_pages=on; SELECT COUNT(*) AS cnt FROM ${TABLE};" || true

if psql -h "${SRC_HOST}" -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 \
  -c "SET zero_damaged_pages=on; COPY ${TABLE} TO STDOUT" > "${OUT}.raw" 2>"${OUT}.err"; then
  {
    echo "COPY public.${TABLE} FROM stdin;"
    cat "${OUT}.raw"
    echo "\\."
  } > "${OUT}"
  echo "SALVAGE_OK rows_bytes=$(wc -c < "${OUT}.raw")"
else
  echo "SALVAGE_FAIL"
  cat "${OUT}.err" || true
  exit 1
fi
