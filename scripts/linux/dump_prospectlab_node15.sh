#!/usr/bin/env bash
set -euo pipefail
OUT_DIR="${OUT_DIR:-/tmp/prospectlab_backups}"
OUT_FILE="${OUT_DIR}/prospectlab_backup_$(date +%Y%m%d_%H%M%S).sql.gz"
ERR_LOG="/tmp/pg_dump_err.log"
mkdir -p "${OUT_DIR}"
echo "[*] Dump prospectlab via postgres..."
if sudo -u postgres pg_dump -d prospectlab --no-owner --no-acl 2>"${ERR_LOG}" | gzip > "${OUT_FILE}"; then
  SIZE="$(stat -c%s "${OUT_FILE}")"
  echo "DUMP_OK ${OUT_FILE} SIZE=${SIZE}"
  ls -lh "${OUT_FILE}"
else
  echo "DUMP_FAIL"
  tail -n 80 "${ERR_LOG}" || true
  exit 1
fi
