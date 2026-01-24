#!/usr/bin/env bash

# Installation d'un set d'outils OSINT sur Raspbian Trixie / RPi (arm64)
# Exécution : bash scripts/linux/install_osint_tools_trixie.sh

set -e

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
install_pkg curl
install_pkg git
install_pkg python3-pip
install_pkg python3-venv
install_pkg pipx || true
pipx ensurepath || true

echo "[*] Outils APT (réseau / DNS / recon)..."
install_pkg theharvester
install_pkg dnsrecon
install_pkg whatweb
install_pkg sslscan
install_pkg nmap
install_pkg masscan

echo "[*] Outils OSINT via pipx (CLI)..."
pipx install sublist3r || true
pipx install amass || true
pipx install sherlock-project || true
pipx install maigret || true
pipx install holehe || true
pipx install socialscan || true
pipx install hibpcli || true

echo "[*] Outils supplémentaires (git clone manuel si besoin)..."
echo "  - spiderfoot, recon-ng, phoneinfoga peuvent être installés manuellement selon l'usage."

echo "[*] Vérifications rapides..."
for tool in theharvester dnsrecon whatweb sslscan nmap masscan; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "[OK] $tool détecté"
  else
    echo "[KO] $tool manquant"
  fi
done
for tool in sublist3r amass sherlock maigret holehe socialscan hibp; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "[OK] $tool détecté"
  else
    echo "[KO] $tool manquant"
  fi
done

echo "[*] Installation OSINT (Trixie) terminée."

