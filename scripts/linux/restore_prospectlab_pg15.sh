#!/usr/bin/env bash
# Restaure un dump ProspectLab (souvent PG17) vers PostgreSQL 15 local.
# Usage:
#   sudo -u postgres bash restore_prospectlab_pg15.sh /path/to/dump.sql.gz
set -euo pipefail

DUMP_FILE="${1:?Fichier dump.sql.gz requis}"
DB_NAME="${DB_NAME:-prospectlab}"
DB_USER="${DB_USER:-prospectlab}"

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "[✗] Fichier introuvable: ${DUMP_FILE}"
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

TMP_SQL="$(mktemp /tmp/prospectlab_restore_XXXX.sql)"
cleanup() { rm -f "${TMP_SQL}"; }
trap cleanup EXIT

echo "[*] Gunzip + filtre compat PG15 (retire directives PG17)..."
# Retire: \restrict, SET transaction_timeout, SET idle_session_timeout (si besoin)
gunzip -c "${DUMP_FILE}" \
  | grep -v -E '^\\restrict ' \
  | grep -v -E '^SET transaction_timeout' \
  | grep -v -E '^SET idle_session_timeout' \
  > "${TMP_SQL}"

echo "[*] Restore dans ${DB_NAME} (peut prendre longtemps)..."
if sudo -u postgres psql -v ON_ERROR_STOP=0 -d "${DB_NAME}" -f "${TMP_SQL}" > /tmp/prospectlab_restore.log 2>&1; then
  echo "[i] psql exit 0"
else
  echo "[!] psql a renvoyé une erreur — voir /tmp/prospectlab_restore.log (fin) :"
  tail -n 50 /tmp/prospectlab_restore.log || true
fi

echo "[*] Droits schéma public -> ${DB_USER}"
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
sudo -u postgres psql -d "${DB_NAME}" -c "SELECT COUNT(*) AS entreprises FROM entreprises;" || echo "[!] count entreprises failed"
sudo -u postgres psql -d "${DB_NAME}" -c "SELECT COUNT(*) AS users FROM users;" || echo "[!] count users failed"

echo "[✓] Restore terminé"
