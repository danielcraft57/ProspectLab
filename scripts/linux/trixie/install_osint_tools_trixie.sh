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

apt_has_pkg() {
  local pkg="$1"
  local candidate
  candidate="$(apt-cache policy "$pkg" 2>/dev/null | awk '/Candidate:/ {print $2}')"
  [ -n "$candidate" ] && [ "$candidate" != "(none)" ]
}

install_pkg_if_available() {
  local pkg="$1"
  if apt_has_pkg "$pkg"; then
    install_pkg "$pkg"
  else
    echo "[!] $pkg absent des dépôts APT (skip)"
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
install_pkg_if_available theharvester || true
if ! command -v theharvester >/dev/null 2>&1; then
  echo "  - theharvester absent des dépôts APT, tentative via pipx (git)..."
  pipx install "git+https://github.com/laramies/theHarvester.git" || true
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
  ARCH_RAW="$(uname -m)"
  case "$ARCH_RAW" in
    x86_64) ARCH="x86_64" ;;
    aarch64) ARCH="aarch64" ;;
    *) ARCH="x86_64" ;;
  esac

  _tmp="/tmp/findomain"
  rm -f "$_tmp" 2>/dev/null || true

  # 1) Tentative via API GitHub (plus robuste que /latest/download selon assets)
  tag="$(curl -fsSL https://api.github.com/repos/Findomain/Findomain/releases/latest 2>/dev/null | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)"
  if [ -n "$tag" ]; then
    # Quelques noms d'assets possibles selon release
    for asset in \
      "findomain-linux-${ARCH}" \
      "findomain-linux-${ARCH_RAW}" \
      "findomain-linux" \
      "findomain"; do
      url="https://github.com/Findomain/Findomain/releases/download/${tag}/${asset}"
      if curl -fsSL "$url" -o "$_tmp" 2>/dev/null; then
        break
      fi
    done
  fi

  # 2) Fallback direct latest/download (si API rate limit)
  if [ ! -s "$_tmp" ]; then
    curl -fsSL "https://github.com/Findomain/Findomain/releases/latest/download/findomain-linux-${ARCH}" -o "$_tmp" 2>/dev/null || true
  fi

  if [ -s "$_tmp" ]; then
    sudo mv "$_tmp" /usr/local/bin/findomain
    sudo chmod +x /usr/local/bin/findomain
    echo "    ✓ findomain installé"
  else
    echo "    ⚠ findomain non installé (asset introuvable)."
    echo "    ⚠ Fallback: compilation locale via Rust (cargo) si disponible..."
    if ! command -v cargo >/dev/null 2>&1; then
      echo "    - Installation de cargo (APT)..."
      install_pkg_if_available cargo || true
    fi
    if command -v cargo >/dev/null 2>&1; then
      cargo install findomain --locked 2>/dev/null || cargo install findomain 2>/dev/null || true
      if [ -f "$HOME/.cargo/bin/findomain" ]; then
        sudo ln -sf "$HOME/.cargo/bin/findomain" /usr/local/bin/findomain
        echo "    ✓ findomain installé (cargo)"
      fi
    else
      echo "    ⚠ cargo absent: installation impossible (APT). Alternative: rustup puis relancer."
    fi
  fi
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
  install_pkg_if_available nikto || true
fi

# Gobuster (énumération de répertoires)
if ! command -v gobuster >/dev/null 2>&1; then
  install_pkg gobuster || echo "    ⚠ gobuster non disponible via apt"
fi

# Nikto (scanner de vulnérabilités web) — absent sur certaines variantes Trixie.
# Fallback: install via git clone + symlink.
if ! command -v nikto >/dev/null 2>&1; then
  echo "  - Installation de nikto (fallback git)..."
  install_pkg_if_available nikto || true
  if ! command -v nikto >/dev/null 2>&1; then
    install_pkg_if_available perl || true
    install_pkg_if_available libwww-perl || true
    install_pkg_if_available libnet-ssleay-perl || true
    install_pkg_if_available openssl || true
    if [ ! -d "$HOME/nikto" ]; then
      git clone --depth 1 https://github.com/sullo/nikto.git "$HOME/nikto" 2>/dev/null || true
    fi
    if [ -f "$HOME/nikto/program/nikto.pl" ]; then
      sudo ln -sf "$HOME/nikto/program/nikto.pl" /usr/local/bin/nikto
      sudo chmod +x "$HOME/nikto/program/nikto.pl" 2>/dev/null || true
      echo "    ✓ nikto installé (/usr/local/bin/nikto)"
    else
      echo "    ⚠ nikto non installé (clone/chemin invalide)"
    fi
  fi
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
# PhoneInfoga v2 (binaire Go — le paquet PyPI « phoneinfoga » 0.1 est obsolète)
if ! command -v phoneinfoga >/dev/null 2>&1; then
  echo "  - Installation de PhoneInfoga (release GitHub)..."
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64) PI_ARCH=x86_64 ;;
    aarch64) PI_ARCH=arm64 ;;
    armv7l) PI_ARCH=armv7 ;;
    armv6l) PI_ARCH=armv6 ;;
    *) PI_ARCH=x86_64 ;;
  esac
  PI_TAG=$(curl -fsSL https://api.github.com/repos/sundowndev/phoneinfoga/releases/latest | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
  PI_TAG=${PI_TAG:-v2.11.0}
  TMPD=$(mktemp -d)
  if curl -fsSL "https://github.com/sundowndev/phoneinfoga/releases/download/${PI_TAG}/phoneinfoga_Linux_${PI_ARCH}.tar.gz" -o "$TMPD/pi.tgz" && tar -xzf "$TMPD/pi.tgz" -C "$TMPD"; then
    if [ -f "$TMPD/phoneinfoga" ]; then
      sudo mv "$TMPD/phoneinfoga" /usr/local/bin/phoneinfoga
      sudo chmod +x /usr/local/bin/phoneinfoga
      echo "    ✓ PhoneInfoga $PI_TAG → /usr/local/bin/phoneinfoga"
    fi
  else
    echo "    ⚠ Binaire GitHub indisponible, repli pipx (ancien client)..."
    pipx install phoneinfoga || true
  fi
  rm -rf "$TMPD"
else
  echo "  - PhoneInfoga déjà présent"
fi

echo "[*] Outils de métadonnées..."
# Metagoofil (extraction de métadonnées de documents)
if ! command -v metagoofil >/dev/null 2>&1; then
  echo "  - Installation de metagoofil..."
  install_pkg_if_available metagoofil || true
  if ! command -v metagoofil >/dev/null 2>&1; then
    echo "    ⚠ metagoofil non disponible via apt, tentative via pipx..."
    pipx install metagoofil 2>/dev/null || true
    if ! command -v metagoofil >/dev/null 2>&1; then
      # Fallback git (si PyPI indisponible)
      pipx install "git+https://github.com/opsdisk/metagoofil.git" 2>/dev/null || true
    fi
    if ! command -v metagoofil >/dev/null 2>&1; then
      echo "    ⚠ metagoofil non installé (pipx/git). Fallback: script wrapper (git clone)."
      if [ ! -d "$HOME/metagoofil" ]; then
        git clone --depth 1 https://github.com/opsdisk/metagoofil.git "$HOME/metagoofil" 2>/dev/null || true
      fi
      if [ -f "$HOME/metagoofil/metagoofil.py" ]; then
        sudo tee /usr/local/bin/metagoofil >/dev/null << 'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/metagoofil/metagoofil.py" "$@"
EOF
        sudo chmod +x /usr/local/bin/metagoofil
        echo "    ✓ metagoofil installé (wrapper /usr/local/bin/metagoofil)"
      fi
    fi
  fi
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
  # Sur Trixie, le paquet APT peut manquer et recon-ng n'est pas toujours sur PyPI.
  # Fallback: pipx depuis GitHub.
  pipx install "git+https://github.com/lanmaster53/recon-ng.git" 2>/dev/null || true
  command -v recon-ng >/dev/null 2>&1 || echo "    ⚠ recon-ng non installé (pipx git)."
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
install_pkg_if_available python3-whois 2>/dev/null || true
echo "[i] Note: le venv /opt/prospectlab/env est géré par requirements.txt (on évite de le modifier ici)."

echo "[*] Vérifications rapides..."
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
echo ""
echo "Outils installés :"
echo "=================="

tools=("theharvester" "dnsrecon" "whatweb" "sslscan" "nmap" "masscan" "sublist3r" "amass" "sherlock" "maigret" "holehe" "socialscan" "hibp" "subfinder" "findomain" "dnsenum" "fierce" "testssl.sh" "wafw00f" "nikto" "gobuster" "phoneinfoga" "metagoofil" "exiftool" "recon-ng" "shodan" "censys")

for tool in "${tools[@]}"; do
  if [ "$tool" = "theharvester" ]; then
    if command -v theharvester >/dev/null 2>&1 || command -v theHarvester >/dev/null 2>&1; then
      echo "[OK] theharvester détecté"
    else
      echo "[KO] theharvester manquant"
    fi
  elif [ "$tool" = "hibp" ]; then
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
PY_CHECK_BIN="python3"
if [ -x "/opt/prospectlab/env/bin/python" ]; then
  PY_CHECK_BIN="/opt/prospectlab/env/bin/python"
fi
"$PY_CHECK_BIN" - << 'EOF' || true
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
