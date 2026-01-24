#!/usr/bin/env bash
# Nettoie la base de données (SQLite ou PostgreSQL)
# Utilise le script Python clear_db.py qui gère automatiquement le type de base
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR" || exit 1

# Activer le venv si présent
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "[*] Nettoyage de la base de données..."
echo "[*] Le script détectera automatiquement SQLite ou PostgreSQL"

# Utiliser le script Python qui gère les deux types de bases
if [ -x "venv/bin/python3" ]; then
    venv/bin/python3 scripts/clear_db.py --clear --no-confirm
else
    python3 scripts/clear_db.py --clear --no-confirm
fi

echo "[*] Nettoyage terminé!"
