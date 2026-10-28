#!/usr/bin/env bash
# Smoke install ProspectLab Facebook messenger sur serv2 (apres deploy_to_serv2.ps1).

set -euo pipefail

FB_DIR="${SOCIALDESK_REPO_ROOT:-/home/pi/Documents/socialdesk}/facebook-playwright"
SCRIPTS="${SOCIALDESK_REPO_ROOT:-/home/pi/Documents/socialdesk}/deploy/scripts"

echo "== ProspectLab Facebook messenger (serv2) =="
command -v node >/dev/null || { echo "node manquant"; exit 1; }
command -v python3 >/dev/null || { echo "python3 manquant"; exit 1; }

test -f "$FB_DIR/src/prospectlab-facebook-job.mjs" || { echo "job mjs absent — lance deploy_to_serv2.ps1"; exit 1; }
test -f "$SCRIPTS/prospectlab_facebook_remote.py" || { echo "wrapper absent"; exit 1; }

cd "$FB_DIR"
node src/check-session.mjs --account=danielcraft --quick || {
  echo "Session FB KO — connecte-toi en RDP sur serv2 (Chrome pi), puis :"
  echo "  node src/sync-chrome-session.mjs --account=danielcraft --headless"
  exit 2
}

echo "OK session + fichiers ProspectLab messenger."
