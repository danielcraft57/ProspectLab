#!/usr/bin/env bash

# Installation d'un set d'outils OSINT sur Debian Trixie / RPi (arm64)
# Exécution : bash scripts/linux/trixie/install_osint_tools_trixie.sh

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
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

echo "[*] Outils APT (réseau / DNS / recon)..."
install_pkg theharvester || true
if ! command -v theharvester >/dev/null 2>&1; then
  echo "  - theharvester absent des dépôts, tentative via pipx..."
  pipx install theHarvester || true
fi
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

echo "[*] Outils de sous-domaines supplémentaires..."
# Subfinder (via Go ou binaire)
if ! command -v subfinder >/dev/null 2>&1; then
  echo "  - Installation de subfinder..."
  if command -v go >/dev/null 2>&1; then
    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest || true
  else
    # Télécharger le binaire depuis GitHub
    SUBFINDER_VERSION=$(curl -s https://api.github.com/repos/projectdiscovery/subfinder/releases/latest | grep tag_name | cut -d '"' -f 4)
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
      ARCH="amd64"
    elif [ "$ARCH" = "aarch64" ]; then
      ARCH="arm64"
    fi
    wget -q "https://github.com/projectdiscovery/subfinder/releases/download/${SUBFINDER_VERSION}/subfinder_${SUBFINDER_VERSION#v}_linux_${ARCH}.zip" -O /tmp/subfinder.zip 2>/dev/null && {
      unzip -q -o /tmp/subfinder.zip -d /tmp/ 2>/dev/null
      sudo mv /tmp/subfinder /usr/local/bin/subfinder 2>/dev/null || true
      sudo chmod +x /usr/local/bin/subfinder 2>/dev/null || true
      rm -f /tmp/subfinder.zip
      echo "    ✓ subfinder installé"
    } || echo "    ⚠ subfinder non installé (nécessite Go ou téléchargement manuel)"
  fi
fi

# Findomain (binaire)
if ! command -v findomain >/dev/null 2>&1; then
  echo "  - Installation de findomain..."
  ARCH=$(uname -m)
  if [ "$ARCH" = "x86_64" ]; then
    ARCH="x86_64"
  elif [ "$ARCH" = "aarch64" ]; then
    ARCH="aarch64"
  else
    ARCH="x86_64"
  fi
  wget -q "https://github.com/Findomain/Findomain/releases/latest/download/findomain-linux-${ARCH}" -O /tmp/findomain 2>/dev/null && {
    sudo mv /tmp/findomain /usr/local/bin/findomain
    sudo chmod +x /usr/local/bin/findomain
    echo "    ✓ findomain installé"
  } || echo "    ⚠ findomain non installé (téléchargement manuel requis)"
fi

# DNSenum
if ! command -v dnsenum >/dev/null 2>&1; then
  echo "  - Installation de dnsenum..."
  install_pkg dnsenum || echo "    ⚠ dnsenum non disponible via apt"
fi

# Fierce
if ! command -v fierce >/dev/null 2>&1; then
  echo "  - Installation de fierce..."
  install_pkg fierce || pipx install fierce || echo "    ⚠ fierce non disponible"
fi

echo "[*] Outils d'analyse web supplémentaires..."
# Nikto (scanner de vulnérabilités web)
if ! command -v nikto >/dev/null 2>&1; then
  install_pkg nikto || echo "    ⚠ nikto non disponible via apt"
fi

# Gobuster (énumération de répertoires)
if ! command -v gobuster >/dev/null 2>&1; then
  install_pkg gobuster || echo "    ⚠ gobuster non disponible via apt"
fi

# testssl.sh (analyse SSL/TLS complète)
if ! command -v testssl.sh >/dev/null 2>&1; then
  echo "  - Installation de testssl.sh..."
  if [ ! -d ~/testssl.sh ]; then
    cd ~
    git clone --depth 1 https://github.com/drwetter/testssl.sh.git 2>/dev/null && {
      chmod +x testssl.sh/testssl.sh
      sudo ln -sf ~/testssl.sh/testssl.sh /usr/local/bin/testssl.sh
      echo "    ✓ testssl.sh installé"
    } || echo "    ⚠ Échec du clonage de testssl.sh"
    cd - >/dev/null
  else
    echo "    testssl.sh déjà installé"
  fi
fi

# Wafw00f (détection de WAF)
if ! command -v wafw00f >/dev/null 2>&1; then
  echo "  - Installation de wafw00f..."
  install_pkg wafw00f || pipx install wafw00f || echo "    ⚠ wafw00f non disponible"
fi

echo "[*] Outils de recherche de personnes supplémentaires..."
# PhoneInfoga
if ! command -v phoneinfoga >/dev/null 2>&1; then
  echo "  - Installation de phoneinfoga..."
  pipx install phoneinfoga || echo "    ⚠ phoneinfoga non disponible via pipx"
fi

echo "[*] Outils de métadonnées..."
# Metagoofil (extraction de métadonnées de documents)
if ! command -v metagoofil >/dev/null 2>&1; then
  echo "  - Installation de metagoofil..."
  install_pkg metagoofil || echo "    ⚠ metagoofil non disponible via apt"
fi

# ExifTool (extraction de métadonnées d'images)
if ! command -v exiftool >/dev/null 2>&1; then
  echo "  - Installation d'exiftool..."
  install_pkg libimage-exiftool-perl || echo "    ⚠ exiftool non disponible via apt"
fi

echo "[*] Frameworks OSINT..."
# Recon-ng
if ! command -v recon-ng >/dev/null 2>&1; then
  echo "  - Installation de recon-ng..."
  pipx install recon-ng || echo "    ⚠ recon-ng non disponible via pipx"
fi

echo "[*] APIs CLI (nécessitent des clés API)..."
# Shodan CLI
if ! command -v shodan >/dev/null 2>&1; then
  echo "  - Installation de shodan CLI..."
  pipx install shodan || echo "    ⚠ shodan CLI non installé (nécessite pipx)"
fi

# Censys CLI
if ! command -v censys >/dev/null 2>&1; then
  echo "  - Installation de censys CLI..."
  pipx install censys || echo "    ⚠ censys CLI non installé (nécessite pipx)"
fi

echo "[*] Outils supplémentaires (git clone manuel si besoin)..."
echo "  - spiderfoot peut être installé manuellement selon l'usage."

# Module Python whois (optionnel)
install_pkg python3-whois 2>/dev/null || true

echo "[*] Vérifications rapides..."
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
echo ""
echo "Outils installés :"
echo "=================="

tools=("theharvester" "dnsrecon" "whatweb" "sslscan" "nmap" "masscan" "sublist3r" "amass" "sherlock" "maigret" "holehe" "socialscan" "hibp" "subfinder" "findomain" "dnsenum" "fierce" "testssl.sh" "wafw00f" "nikto" "gobuster" "phoneinfoga" "metagoofil" "exiftool" "recon-ng" "shodan" "censys")

for tool in "${tools[@]}"; do
  if [ "$tool" = "hibp" ]; then
    if command -v hibp >/dev/null 2>&1 || command -v hibpcli >/dev/null 2>&1; then
      echo "[OK] hibp détecté"
    else
      echo "[KO] hibp manquant"
    fi
  elif command -v "$tool" >/dev/null 2>&1; then
    echo "[OK] $tool détecté"
  else
    echo "[KO] $tool manquant"
  fi
done

echo ""
echo "Modules Python (vérification optionnelle)..."
python3 - << 'EOF' || true
import importlib
modules = ["whois", "dns.resolver"]
for name in modules:
    try:
        importlib.import_module(name)
        print(f"[OK] Module Python {name} importable")
    except Exception:
        print(f"[KO] Module Python {name} non importable (optionnel)")
EOF

echo "[*] Installation OSINT (Trixie) terminée."
