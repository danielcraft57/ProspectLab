#!/usr/bin/env bash
# Nettoie la base SQLite (supprime le fichier prospectlab.db)
set -e
echo "[*] Suppression de la base prospectlab.db..."
rm -f prospectlab.db
echo "[*] Base supprimée."

