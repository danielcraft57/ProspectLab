#!/usr/bin/env bash
# Prépare PostgreSQL sur node6 pour héberger prospectlab (LAN + tuning RAM léger).
# Usage: sudo bash scripts/linux/prep_node6_postgres_prospectlab.sh
# Ne touche pas à la base streamnews.

set -euo pipefail

DB_NAME="${DB_NAME:-prospectlab}"
DB_USER="${DB_USER:-prospectlab}"
DB_PASSWORD="${DB_PASSWORD:?Définir DB_PASSWORD}"
LAN_CIDR="${LAN_CIDR:-192.168.1.0/24}"

PG_VERSION="$(ls -1 /etc/postgresql/ 2>/dev/null | head -1)"
if [[ -z "${PG_VERSION}" ]]; then
  echo "[✗] Aucune version PostgreSQL trouvée dans /etc/postgresql/"
  exit 1
fi

PG_CONF_DIR="/etc/postgresql/${PG_VERSION}/main"
PG_CONF="${PG_CONF_DIR}/postgresql.conf"
PG_HBA="${PG_CONF_DIR}/pg_hba.conf"
TS="$(date +%Y%m%d_%H%M%S)"

echo "[*] PostgreSQL ${PG_VERSION} — backup configs..."
cp "${PG_CONF}" "${PG_CONF}.backup_prospectlab_${TS}"
cp "${PG_HBA}" "${PG_HBA}.backup_prospectlab_${TS}"

set_conf() {
  local key="$1"
  local value="$2"
  if grep -qE "^[[:space:]]*#?[[:space:]]*${key}[[:space:]]*=" "${PG_CONF}"; then
    sed -i -E "s|^[[:space:]]*#?[[:space:]]*${key}[[:space:]]*=.*|${key} = ${value}|" "${PG_CONF}"
  else
    echo "${key} = ${value}" >> "${PG_CONF}"
  fi
}

echo "[*] Tuning RAM léger (cohabitation streamnews)..."
set_conf listen_addresses "'*'"
set_conf shared_buffers "128MB"
set_conf effective_cache_size "384MB"
set_conf work_mem "4MB"
set_conf maintenance_work_mem "64MB"
set_conf max_connections "50"

echo "[*] Règle pg_hba LAN pour ${DB_NAME}/${DB_USER}..."
if ! grep -qE "host[[:space:]]+${DB_NAME}[[:space:]]+${DB_USER}[[:space:]]+${LAN_CIDR}" "${PG_HBA}"; then
  {
    echo ""
    echo "# prospectlab-lan"
    echo "host    ${DB_NAME}    ${DB_USER}    ${LAN_CIDR}    scram-sha-256"
  } >> "${PG_HBA}"
  echo "[✓] Règle hba ajoutée"
else
  echo "[i] Règle hba déjà présente"
fi

echo "[*] Création rôle + base..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec

GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

# Droits schéma public (PG15+)
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "${DB_NAME}" <<SQL
GRANT ALL ON SCHEMA public TO ${DB_USER};
ALTER SCHEMA public OWNER TO ${DB_USER};
SQL

echo "[*] Redémarrage PostgreSQL..."
systemctl restart postgresql
systemctl is-active postgresql

echo "[✓] Préparation node6 terminée"
grep -E "^(listen_addresses|shared_buffers|effective_cache_size|work_mem|maintenance_work_mem|max_connections)" "${PG_CONF}" || true
grep -E "prospectlab" "${PG_HBA}" || true
ss -tln | grep 5432 || true
