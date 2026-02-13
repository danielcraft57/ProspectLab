#!/usr/bin/env bash

# Script de test complet de tous les outils en production (Linux natif) - Debian Trixie
# Exécute tous les scripts de test un par un
# Usage:
#   bash scripts/linux/trixie/test_all_tools_trixie.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Test complet des outils ProspectLab"
echo "  (Production Linux - natif, Debian Trixie)"
echo "=========================================="
echo

# Fonction pour exécuter un script de test
run_test() {
    local test_name="$1"
    local test_script="$2"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Test: $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    
    if [ -f "$test_script" ]; then
        bash "$test_script"
        local exit_code=$?
        if [ $exit_code -eq 0 ]; then
            echo "[✓] $test_name terminé avec succès"
        else
            echo "[✗] $test_name a échoué (code: $exit_code)"
        fi
    else
        echo "[✗] Script de test introuvable: $test_script"
    fi
    
    echo
    echo
}

# Exécuter tous les tests un par un
run_test "Outils OSINT" "$SCRIPT_DIR/test_osint_tools_prod.sh"
run_test "Outils Pentest" "$SCRIPT_DIR/test_pentest_tools_prod.sh"
run_test "Outils SEO" "$SCRIPT_DIR/test_seo_tools_prod.sh"
run_test "Outils OSINT Réseaux Sociaux" "$SCRIPT_DIR/test_social_tools_prod.sh"

echo "=========================================="
echo "  Tous les tests terminés"
echo "=========================================="
