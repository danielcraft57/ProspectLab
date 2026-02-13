#!/usr/bin/env bash

# Wrapper d'installation des outils OSINT pour Kali Linux (WSL)
# Exécution : bash scripts/linux/kali/install_osint_tools_kali.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Wrapper Kali: installation des outils OSINT..."

if [ -f "$SCRIPT_DIR/../install_osint_tools_kali.sh" ]; then
  bash "$SCRIPT_DIR/../install_osint_tools_kali.sh"
else
  echo "[✗] Script source introuvable: $SCRIPT_DIR/../install_osint_tools_kali.sh"
  exit 1
fi

