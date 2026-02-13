#!/usr/bin/env bash

# Installation complète des outils OSINT, Pentest, SEO et Social sur Debian Trixie / RPi
# Exécution : bash scripts/linux/trixie/install_all_tools_trixie.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Installation complète des outils"
echo "  (Debian Trixie / Raspberry Pi)"
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

run_install "OSINT" "$SCRIPT_DIR/install_osint_tools_trixie.sh"
run_install "Pentest" "$SCRIPT_DIR/install_pentest_tools_trixie.sh"
run_install "SEO" "$SCRIPT_DIR/install_seo_tools_trixie.sh"
run_install "Social / Réseaux sociaux" "$SCRIPT_DIR/install_social_tools_trixie.sh"

echo "=========================================="
echo "  Installation complète terminée"
echo "=========================================="
