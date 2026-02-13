#!/usr/bin/env bash

# Installation d'outils SEO sur Debian Trixie / RPi (arm64)
# Exécution : bash scripts/linux/trixie/install_seo_tools_trixie.sh

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
install_pkg wget
install_pkg git
install_pkg python3-pip
install_pkg python3-venv
install_pkg nodejs
install_pkg npm

# Mettre à jour npm si ancienne version
if command -v npm >/dev/null 2>&1; then
  echo "[*] Mise à jour npm..."
  sudo npm install -g npm@latest || true
fi

echo "[*] Outils réseau de base (déjà installés normalement)..."
install_pkg curl
install_pkg wget

echo "[*] Bibliothèques Python pour SEO..."
# Détecter si on est dans un venv
if [ -n "$VIRTUAL_ENV" ]; then
  echo "[*] Environnement virtuel détecté, installation dans le venv..."
  pip3 install --upgrade beautifulsoup4 lxml requests html5lib || true
  pip3 install --upgrade urllib3 certifi || true
else
  echo "[*] Installation globale (--user)..."
  pip3 install --user --upgrade beautifulsoup4 lxml requests html5lib || true
  pip3 install --user --upgrade urllib3 certifi || true
fi

echo "[*] Lighthouse (audit SEO/perfs via npm)..."
if command -v npm >/dev/null 2>&1; then
  sudo npm install -g lighthouse || npm install -g lighthouse || true
  echo "[✓] Lighthouse installé (ou tentative effectuée)"
else
  echo "[!] npm non disponible, Lighthouse ne sera pas installé"
fi

echo "[*] Vérifications rapides..."
for tool in curl wget python3 node npm; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "[✓] $tool : $(command -v $tool)"
  else
    echo "[✗] $tool : non trouvé"
  fi
done

# Vérifier Lighthouse
if command -v lighthouse >/dev/null 2>&1; then
  echo "[✓] lighthouse : $(command -v lighthouse)"
  lighthouse --version || true
else
  echo "[!] lighthouse : non trouvé (peut être installé via: npm install -g lighthouse)"
fi

# Vérifier Python libs
echo "[*] Vérification bibliothèques Python..."
python3 -c "import bs4; print('[✓] beautifulsoup4 OK')" 2>/dev/null || echo "[✗] beautifulsoup4 manquant"
python3 -c "import requests; print('[✓] requests OK')" 2>/dev/null || echo "[✗] requests manquant"
python3 -c "import lxml; print('[✓] lxml OK')" 2>/dev/null || echo "[✗] lxml manquant (optionnel)"

echo ""
echo "[*] Installation terminée !"
echo "[*] Outils disponibles :"
echo "  - curl, wget : requêtes HTTP"
echo "  - Python + beautifulsoup4, requests : parsing HTML, meta tags"
echo "  - Lighthouse (si npm OK) : audit SEO/perfs"
echo ""
echo "[*] Pour tester Lighthouse :"
echo "  lighthouse https://example.com --output=json --output-path=/tmp/lighthouse.json"
