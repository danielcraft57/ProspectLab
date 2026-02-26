#!/usr/bin/env bash

# Wrapper d'installation des outils OSINT pour Kali Linux (WSL)
# Réutilise le script Bookworm (mêmes paquets apt/pip)
# Exécution : bash scripts/linux/kali/install_osint_tools_kali.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Wrapper Kali: installation des outils OSINT..."

if [ -f "$SCRIPT_DIR/../bookworm/install_osint_tools_bookworm.sh" ]; then
  bash "$SCRIPT_DIR/../bookworm/install_osint_tools_bookworm.sh"
else
  echo "[✗] Script source introuvable: $SCRIPT_DIR/../bookworm/install_osint_tools_bookworm.sh"
  exit 1
fi

echo "[*] Installation OSINT terminée pour Kali."

