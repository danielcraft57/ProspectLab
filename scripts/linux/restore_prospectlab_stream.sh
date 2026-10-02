#!/usr/bin/env bash
# Restore streamé d'un dump .sql.gz vers PostgreSQL 15 (filtre directives PG17).
# Usage: bash restore_prospectlab_stream.sh /path/dump.sql.gz
set -euo pipefail

DUMP_FILE="${1:?dump.sql.gz requis}"
DB_NAME="${DB_NAME:-prospectlab}"
DB_USER="${DB_USER:-prospectlab}"

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "[✗] Introuvable: ${DUMP_FILE}"
  exit 1
fi

echo "[*] Drop/recreate ${DB_NAME}..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${DB_NAME};
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

echo "[*] Restore stream (filtre PG17)..."
set +e
gunzip -c "${DUMP_FILE}" \
  | grep -v -E '^\\restrict ' \
  | grep -v -E '^SET transaction_timeout' \
  | grep -v -E '^SET idle_session_timeout' \
  | sudo -u postgres psql -d "${DB_NAME}" -v ON_ERROR_STOP=0 \
  > /tmp/prospectlab_restore.log 2>&1
RC=$?
set -e
echo "[i] psql pipeline rc=${RC}"
tail -n 30 /tmp/prospectlab_restore.log || true

echo "[*] Droits ${DB_USER}..."
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "${DB_NAME}" <<SQL
GRANT ALL ON SCHEMA public TO ${DB_USER};
ALTER SCHEMA public OWNER TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
SQL

echo "[*] Checks..."
sudo -u postgres psql -d "${DB_NAME}" -c "SELECT pg_size_pretty(pg_database_size('${DB_NAME}'));"
sudo -u postgres psql -d "${DB_NAME}" -c "SELECT COUNT(*) AS entreprises FROM entreprises;" || true
sudo -u postgres psql -d "${DB_NAME}" -c "SELECT COUNT(*) AS users FROM users;" || true
echo "[✓] Done"
