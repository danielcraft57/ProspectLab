#!/usr/bin/env bash
# Vérifie que les fichiers static essentiels sont présents sur le serveur.
# Usage: bash scripts/linux/verify_static_deploy.sh
#   PROSPECTLAB_PATH=/opt/prospectlab bash scripts/linux/verify_static_deploy.sh

set -euo pipefail

PROSPECTLAB_PATH="${PROSPECTLAB_PATH:-/opt/prospectlab}"

REQUIRED=(
  static/css/style.css
  static/js/main.js
  static/js/dashboard.js
  static/js/websocket.js
  static/js/modules/utils/notifications.js
  static/favicon/manifest.json
  static/favicon/favicon-32x32.png
)

missing=0
echo "Vérification static dans: $PROSPECTLAB_PATH"
for rel in "${REQUIRED[@]}"; do
  full="$PROSPECTLAB_PATH/$rel"
  if [ -f "$full" ]; then
    echo "  OK  $rel"
  else
    echo "  MANQUANT  $rel"
    missing=$((missing + 1))
  fi
done

if [ "$missing" -eq 0 ]; then
  echo "Tous les fichiers static requis sont présents."
  exit 0
fi

echo ""
echo "$missing fichier(s) manquant(s). Corrigez avec:"
echo "  - git pull (repo propre) ou scripts/deploy_production.sh"
echo "  - ou depuis Windows: .\\scripts\\sync_templates_static.ps1 <serveur> <user>"
exit 1
