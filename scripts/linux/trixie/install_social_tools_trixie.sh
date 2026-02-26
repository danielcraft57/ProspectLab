#!/usr/bin/env bash

# Installation d'outils OSINT orientés réseaux sociaux sur Debian Trixie / RPi
# Exécution : bash scripts/linux/trixie/install_social_tools_trixie.sh

set -e

export PATH="$HOME/.local/bin:$PATH"

echo "[*] Mise à jour APT..."
sudo apt-get update

install_pkg() {
  local pkg="$1"
  if sudo apt-get install -y "$pkg"; then
    echo "[✓] $pkg installé"
  else
    echo "[!] $pkg indisponible sur cette distro, à installer manuellement si besoin"
  fi
}

echo "[*] Pré-requis..."
install_pkg python3-pip
install_pkg python3-venv
install_pkg python3-dev
install_pkg git

echo "[*] Installation de pipx (recommandé)..."
install_pkg pipx || true
pipx ensurepath || true
export PATH="$HOME/.local/bin:$PATH"

echo "[*] Outils CLI principaux (via pipx)..."
pipx install sherlock-project || true
pipx install maigret || true

echo "[*] Social Analyzer (via pipx, évite PEP 668)..."
pipx install social-analyzer || true

echo "[*] Tinfoleak n'est généralement pas dans les dépôts Debian. Installation manuelle recommandée si besoin (git clone + venv)."

echo "[*] Vérifications rapides..."
export PATH="$HOME/.local/bin:$PATH"
for tool in sherlock maigret social-analyzer; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "[OK] $tool détecté"
  elif [ "$tool" = "social-analyzer" ] && pipx list 2>/dev/null | grep -q social-analyzer; then
    echo "[OK] social-analyzer installé (utiliser: pipx run social-analyzer ...)"
  else
    echo "[KO] $tool manquant"
  fi
done

echo "[*] Installation outils social OSINT (Trixie) terminée."
