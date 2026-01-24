#!/usr/bin/env bash
# Nettoie logs, base et Redis (Debian/Bookworm)
set -e

echo "[*] Nettoyage complet..."

echo "[1/3] Logs"
rm -f logs/*.log || true

echo "[2/3] Base de données (SQLite ou PostgreSQL)"
# Utiliser le script Python qui gère les deux types de bases
if [ -d "venv" ]; then
    source venv/bin/activate
fi
if [ -x "venv/bin/python3" ]; then
    venv/bin/python3 scripts/clear_db.py --clear --no-confirm 2>/dev/null || true
else
    python3 scripts/clear_db.py --clear --no-confirm 2>/dev/null || true
fi

echo "[3/3] Redis"
redis-cli FLUSHALL || true

echo "[*] Nettoyage terminé."

