#!/usr/bin/env bash
# Installe le navigateur Chromium Playwright pour les captures screenshots.
# Usage (sur le worker app, ex. node15) :
#   bash scripts/linux/install_playwright_chromium.sh
#   bash scripts/linux/install_playwright_chromium.sh /opt/prospectlab

set -euo pipefail

PROJECT_DIR="${1:-/opt/prospectlab}"
PYTHON_BIN="${PROJECT_DIR}/env/bin/python"

echo "[*] Playwright Chromium — projet: ${PROJECT_DIR}"

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "[!] Python introuvable: ${PYTHON_BIN}"
  echo "    Cree d'abord l'env Conda / venv du projet."
  exit 1
fi

echo "[*] Version Playwright Python..."
"${PYTHON_BIN}" -c "import playwright; print(playwright.__version__)" || {
  echo "[!] Module playwright manquant — pip install -r requirements.txt d'abord"
  exit 1
}

echo "[*] Telechargement Chromium (headless shell)..."
"${PYTHON_BIN}" -m playwright install chromium

echo "[*] Verification binaire..."
"${PYTHON_BIN}" - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    browser.close()
print("[OK] Chromium Playwright demarre correctement")
PY

echo "[✓] Playwright Chromium pret"
