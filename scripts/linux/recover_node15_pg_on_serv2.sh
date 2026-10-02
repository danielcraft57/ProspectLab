#!/usr/bin/env bash
# Recuperation PostgreSQL depuis SD node15 montee sur serv2.
set -euo pipefail

SD_PG=/mnt/node15-sd/var/lib/postgresql/17/main
BINDFS=/mnt/node15-pgdata
BASE=/home/pi/pg_recover
MERGED="${BASE}/merged"
LOG=/home/pi/pg_recover/recover.log

sudo mkdir -p "${BINDFS}" "${BASE}/upper" "${BASE}/work" "${MERGED}" "${BASE}/wal/archive_status" "${BASE}/wal/summaries"
sudo chown -R pi:pi "${BASE}"
sudo chown -R postgres:postgres "${BASE}/upper" "${BASE}/work" "${BASE}/wal" 2>/dev/null || true

sudo umount -l "${MERGED}/pg_wal" 2>/dev/null || true
sudo umount -l "${MERGED}" 2>/dev/null || true
sudo umount -l "${BINDFS}" 2>/dev/null || true

sudo bindfs --map=103/112:@105/@116 "${SD_PG}" "${BINDFS}"
sudo mount -t overlay overlay -o "lowerdir=${BINDFS},upperdir=${BASE}/upper,workdir=${BASE}/work" "${MERGED}"
sudo chown -R postgres:postgres "${BASE}/upper" "${BASE}/work"
sudo chmod 700 "${MERGED}"
sudo chown postgres:postgres "${MERGED}"
sudo rm -f "${MERGED}/postmaster.pid"

sudo mount --bind "${BASE}/wal" "${MERGED}/pg_wal"
sudo chown -R postgres:postgres "${BASE}/wal"

sudo tee "${MERGED}/postgresql.conf" >/dev/null <<EOF
data_directory = '${MERGED}'
hba_file = '${MERGED}/pg_hba.conf'
ident_file = '${MERGED}/pg_ident.conf'
port = 5433
listen_addresses = '127.0.0.1'
max_connections = 20
shared_buffers = 128MB
logging_collector = off
log_destination = 'stderr'
zero_damaged_pages = on
unix_socket_directories = '/tmp'
fsync = off
full_page_writes = off
synchronous_commit = off
EOF
sudo tee "${MERGED}/pg_hba.conf" >/dev/null <<EOF
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
EOF
sudo tee "${MERGED}/postgresql.auto.conf" >/dev/null <<EOF
EOF
sudo touch "${MERGED}/pg_ident.conf"
sudo chown postgres:postgres "${MERGED}/postgresql.conf" "${MERGED}/pg_hba.conf" "${MERGED}/postgresql.auto.conf" "${MERGED}/pg_ident.conf"

echo "[*] pg_resetwal..."
sudo -u postgres /usr/lib/postgresql/17/bin/pg_resetwal -f "${MERGED}"
echo "[*] start..."
sudo -u postgres /usr/lib/postgresql/17/bin/pg_ctl -D "${MERGED}" -l "${LOG}" start
sleep 5
ss -tln | grep 5433 || true
sudo tail -n 40 "${LOG}" || true
echo DONE
