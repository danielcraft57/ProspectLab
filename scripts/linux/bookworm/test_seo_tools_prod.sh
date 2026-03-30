#!/usr/bin/env bash

# Script de vérification des outils SEO en production (Linux natif, sans WSL)
# Usage:
#   bash scripts/linux/test_seo_tools_prod.sh

set -e

echo "[*] Vérification des outils SEO (prod Linux, natif)..."
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

echo "[*] Outils de base"
check_tool "curl"
check_tool "wget"
check_tool "python3"
check_tool "node"
check_tool "npm"

echo "[*] Lighthouse (audit SEO / performances)"
check_tool "lighthouse"

echo "[*] Chromium (moteur navigateur pour Lighthouse)"
if command -v chromium >/dev/null 2>&1; then
  echo "[OK] chromium trouvé: $(command -v chromium)"
elif command -v chromium-browser >/dev/null 2>&1; then
  echo "[OK] chromium-browser trouvé: $(command -v chromium-browser)"
else
  echo "[KO] Chromium non trouvé dans le PATH"
fi
echo

echo "[*] Vérification CHROME_PATH (si défini)"
if [ -n "${CHROME_PATH:-}" ]; then
  if [ -x "$CHROME_PATH" ]; then
    echo "[OK] CHROME_PATH valide: $CHROME_PATH"
  else
    echo "[KO] CHROME_PATH défini mais binaire introuvable/inexécutable: $CHROME_PATH"
  fi
else
  echo "[i] CHROME_PATH non défini (fallback auto via chemins standards)"
fi
echo

echo "[*] Bibliothèques Python pour parsing HTML / SEO"
python3 - << 'EOF' || true
import importlib

modules = ["bs4", "requests", "lxml", "html5lib"]
for name in modules:
    try:
        importlib.import_module(name)
        print(f"[OK] Module Python {name} importable")
    except Exception as e:
        print(f"[KO] Module Python {name} non importable: {e}")
EOF

echo
echo "[*] Vérification SEO terminée."

