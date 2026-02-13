#!/usr/bin/env bash

# Script dispatcher pour test complet des outils
# Détecte automatiquement la version Debian (Bookworm ou Trixie) et appelle le bon script
# Usage: bash scripts/linux/test_all_tools.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Détecter la version (Debian / Kali)
if [ -f /etc/os-release ]; then
    . /etc/os-release
    VERSION_CODENAME="${VERSION_CODENAME:-}"
    VERSION_ID="${VERSION_ID:-}"
    ID="${ID:-}"
    NAME="${NAME:-}"
    
    echo "=========================================="
    echo "  Détection de la distribution"
    echo "=========================================="
    echo "  ID: $ID"
    echo "  Version: $VERSION_ID"
    echo "  Nom de code: $VERSION_CODENAME"
    echo "  Nom complet: $NAME"
    echo
else
    echo "[!] Impossible de détecter la distribution (/etc/os-release introuvable)"
    echo "[*] Utilisation de Bookworm par défaut"
    VERSION_CODENAME="bookworm"
    ID="debian"
fi

# Déterminer le dossier et le script à utiliser
TEST_DIR=""
TEST_SCRIPT=""
VERSION_NAME=""

if [ "$ID" = "kali" ] || echo "$NAME" | grep -qi "kali"; then
    TEST_DIR="$SCRIPT_DIR/kali"
    VERSION_NAME="Kali Linux"
    TEST_SCRIPT="$TEST_DIR/test_all_tools_kali.sh"
elif [ "$VERSION_CODENAME" = "trixie" ]; then
    TEST_DIR="$SCRIPT_DIR/trixie"
    VERSION_NAME="Debian Trixie"
    TEST_SCRIPT="$TEST_DIR/test_all_tools_trixie.sh"
elif [ "$VERSION_CODENAME" = "bookworm" ]; then
    TEST_DIR="$SCRIPT_DIR/bookworm"
    VERSION_NAME="Debian Bookworm"
    TEST_SCRIPT="$TEST_DIR/test_all_tools_bookworm.sh"
else
    echo "[!] Version non reconnue: $VERSION_CODENAME (ID=$ID)"
    echo "[*] Tentative avec Bookworm..."
    TEST_DIR="$SCRIPT_DIR/bookworm"
    VERSION_NAME="Debian Bookworm (fallback)"
    TEST_SCRIPT="$TEST_DIR/test_all_tools_bookworm.sh"
fi

echo "=========================================="
echo "  Test complet des outils ProspectLab"
echo "  ($VERSION_NAME)"
echo "=========================================="
echo

if [ ! -d "$TEST_DIR" ]; then
    echo "[✗] Dossier introuvable: $TEST_DIR"
    echo "[*] Vérifiez que les scripts sont bien présents"
    exit 1
fi

if [ -f "$TEST_SCRIPT" ]; then
    echo "[*] Exécution de: $TEST_SCRIPT"
    echo
    bash "$TEST_SCRIPT"
else
    echo "[✗] Script de test introuvable: $TEST_SCRIPT"
    echo "[*] Scripts disponibles dans: $TEST_DIR"
    exit 1
fi
