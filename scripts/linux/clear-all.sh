 #!/usr/bin/env bash
# Nettoie logs, base et Redis (Debian/Bookworm). À lancer depuis la racine du projet ou depuis scripts/linux.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "[*] Nettoyage complet..."

echo "[1/3] Logs"
rm -f logs/*.log 2>/dev/null || true

echo "[2/3] Base de données (SQLite ou PostgreSQL)"
# Utiliser l'environnement Conda (env) ou venv, puis le script Python
if [ -x "env/bin/python3" ]; then
    env/bin/python3 scripts/clear_db.py --clear --no-confirm 2>/dev/null || true
elif [ -x "venv/bin/python3" ]; then
    venv/bin/python3 scripts/clear_db.py --clear --no-confirm 2>/dev/null || true
else
    python3 scripts/clear_db.py --clear --no-confirm 2>/dev/null || true
fi

echo "[3/3] Redis"
redis-cli FLUSHALL || true

echo "[*] Nettoyage terminé."

