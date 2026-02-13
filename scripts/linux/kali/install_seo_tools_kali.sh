#!/usr/bin/env bash

# Wrapper d'installation des outils SEO pour Kali Linux (WSL)
# Réutilise le script Bookworm (mêmes paquets apt/pip)
# Exécution : bash scripts/linux/kali/install_seo_tools_kali.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Wrapper Kali: installation des outils SEO..."

if [ -f "$SCRIPT_DIR/../install_seo_tools_bookworm.sh" ]; then
  bash "$SCRIPT_DIR/../install_seo_tools_bookworm.sh"
else
  echo "[✗] Script source introuvable: $SCRIPT_DIR/../install_seo_tools_bookworm.sh"
  exit 1
fi

