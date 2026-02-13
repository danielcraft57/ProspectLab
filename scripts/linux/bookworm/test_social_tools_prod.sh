#!/usr/bin/env bash

# Script de vérification des outils OSINT "réseaux sociaux" en production (Linux natif)
# Usage:
#   bash scripts/linux/test_social_tools_prod.sh

set -e

echo "[*] Vérification des outils OSINT sur les réseaux sociaux (prod Linux, natif)..."
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

echo "[*] Outils CLI principaux"
check_tool "sherlock"
check_tool "maigret"
check_tool "tinfoleak"

echo "[*] Social Analyzer (module Python ou CLI)"

python3 - << 'EOF' || true
import importlib
import subprocess
import sys

print("[*] Test import module Python social-analyzer...")
module_names = ["social_analyzer", "socialanalyzer", "socialanalyzer.socialanalyzer"]
found_import = False
for name in module_names:
    try:
        importlib.import_module(name)
        print("[OK] Module Python {} importable".format(name))
        found_import = True
        break
    except ImportError:
        continue
    except Exception as e:
        print("[!] Erreur lors de l'import de {}: {}".format(name, e))

if not found_import:
    print("[!] Import direct non disponible, test via CLI...")

print("[*] Test exécution python3 -m social_analyzer --help...")
try:
    result = subprocess.run(
        [sys.executable, "-m", "social_analyzer", "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        print("[OK] Commande python -m social_analyzer fonctionnelle")
    else:
        # Essayer avec socialanalyzer (sans underscore)
        result2 = subprocess.run(
            [sys.executable, "-m", "socialanalyzer", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if result2.returncode == 0:
            print("[OK] Commande python -m socialanalyzer fonctionnelle")
        else:
            print("[KO] Commande python -m social_analyzer a retourné {}".format(result.returncode))
            if result.stderr:
                print(result.stderr.strip()[:200])
except Exception as e:
    print("[KO] Erreur lors de l'exécution de social_analyzer: {}".format(e))
EOF

echo
echo "[*] Vérification des outils social OSINT terminée."

