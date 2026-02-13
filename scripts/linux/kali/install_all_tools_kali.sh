#!/usr/bin/env bash

# Installation complète des outils OSINT, Pentest, SEO et Social sur Kali Linux (WSL)
# Exécution : wsl -d kali-linux bash scripts/linux/kali/install_all_tools_kali.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Installation complète des outils"
echo "  (Kali Linux / WSL)"
echo "=========================================="
echo

run_install() {
  local name="$1"
  local script_path="$2"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Installation: $name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo
  if [ -f "$script_path" ]; then
    bash "$script_path"
    echo
  else
    echo "[!] Script introuvable: $script_path"
    echo
  fi
}

run_install "OSINT" "$SCRIPT_DIR/install_osint_tools_kali.sh"
run_install "Pentest" "$SCRIPT_DIR/install_pentest_tools_kali.sh"
run_install "SEO" "$SCRIPT_DIR/install_seo_tools_kali.sh"
run_install "Social / Réseaux sociaux" "$SCRIPT_DIR/install_social_tools_kali.sh"

echo "=========================================="
echo "  Installation complète terminée"
echo "=========================================="

