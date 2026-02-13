#!/usr/bin/env bash

# Script de vérification des outils OSINT en production (Linux natif, sans WSL)
# Usage:
#   bash scripts/linux/test_osint_tools_prod.sh

set -e

echo "[*] Vérification des outils OSINT (prod Linux, natif)..."
echo

check_tool() {
  local tool_name="$1"
  echo " - Vérification de: $tool_name"
  if command -v "$tool_name" >/dev/null 2>&1; then
    echo "   [OK] $tool_name trouvé: $(command -v "$tool_name")"
  else
    echo "   [KO] $tool_name non trouvé dans le PATH"
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
check_tool "findomain"
check_tool "dnsenum"
check_tool "fierce"

echo "[*] Outils OSINT CLI (via pipx ou équivalent)"
check_tool "sherlock"
check_tool "maigret"
check_tool "holehe"
check_tool "shodan"
check_tool "censys"

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

