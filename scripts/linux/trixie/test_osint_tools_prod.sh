#!/usr/bin/env bash

# Script de vérification des outils OSINT en production (Linux natif, sans WSL)
# Usage:
#   bash scripts/linux/test_osint_tools_prod.sh

set -e

# PATH complet (certains outils sont en /usr/sbin ou /sbin)
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

is_debian_trixie() {
  [ -f /etc/debian_version ] && grep -q '^13' /etc/debian_version 2>/dev/null
}

echo "[*] Vérification des outils OSINT (prod Linux, natif)..."
echo

check_tool() {
  local tool_name="$1"
  local optional="${2:-0}"
  echo " - Vérification de: $tool_name"
  if command -v "$tool_name" >/dev/null 2>&1; then
    echo "   [OK] $tool_name trouvé: $(command -v "$tool_name")"
  else
    if [ "$optional" = "1" ]; then
      echo "   [OPT] $tool_name non trouvé (optionnel)"
    else
      echo "   [KO] $tool_name non trouvé dans le PATH"
    fi
  fi
  echo
}

echo "[*] Outils de reconnaissance / réseau"
check_tool "theharvester"
check_tool "dnsrecon"
check_tool "whatweb"
check_tool "sslscan"
check_tool "nmap"
check_tool "masscan"

echo "[*] Outils de sous-domaines / domaine"
check_tool "sublist3r"
check_tool "amass"
check_tool "subfinder"
if is_debian_trixie; then
  # Findomain: binaire parfois introuvable selon releases/arch; non bloquant.
  check_tool "findomain" "1"
else
  check_tool "findomain"
fi
check_tool "dnsenum"
check_tool "fierce"

echo "[*] Outils OSINT CLI (via pipx ou équivalent)"
check_tool "sherlock"
check_tool "maigret"
check_tool "holehe"
check_tool "shodan"
check_tool "censys"

echo "[*] Outils de métadonnées (optionnels)"
# Metagoofil est souvent obsolète/non packagé sur Debian récente.
check_tool "metagoofil" "1"
check_tool "exiftool"
check_tool "recon-ng" "1"

echo "[*] Bibliothèques Python optionnelles (whois, dns, etc.)"
python3 - << 'EOF' || true
import importlib

modules = ["whois", "dns.resolver"]
for name in modules:
    try:
        importlib.import_module(name)
        print(f"[OK] Module Python {name} importable")
    except Exception as e:
        print(f"[KO] Module Python {name} non importable: {e}")
EOF

echo
echo "[*] Vérification OSINT terminée."

