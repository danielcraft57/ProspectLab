#!/bin/bash
# Script pour corriger les permissions des scripts shell
# Usage: ./scripts/fix_permissions.sh [chemin_projet]

set -e

PROJECT_DIR="${1:-/opt/prospectlab}"

echo "=========================================="
echo "Correction des permissions des scripts"
echo "=========================================="
echo ""

if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Répertoire introuvable: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

echo "[*] Ajout des permissions d'exécution aux scripts shell..."
find scripts -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true
find scripts/linux -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true

echo "✅ Permissions corrigées"
echo ""
echo "Scripts disponibles:"
find scripts/linux -name '*.sh' -type f | while read -r script; do
    if [ -x "$script" ]; then
        echo "  ✅ $script"
    else
        echo "  ❌ $script (permissions manquantes)"
    fi
done
