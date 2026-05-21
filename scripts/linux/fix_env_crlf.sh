#!/usr/bin/env bash
# Convertit .env (CRLF Windows → LF Unix). À lancer sur le serveur après copie depuis Windows.
set -euo pipefail

ENV_FILE="${1:-/opt/prospectlab/.env}"
if [ ! -f "$ENV_FILE" ]; then
  echo "Fichier introuvable: $ENV_FILE"
  exit 1
fi
if grep -q $'\r' "$ENV_FILE" 2>/dev/null; then
  sed -i 's/\r$//' "$ENV_FILE"
  echo "CRLF corrigés dans $ENV_FILE"
else
  echo "Déjà au format Unix: $ENV_FILE"
fi
