#!/usr/bin/env bash
# Nettoie les logs de l'application (Debian/Bookworm)
set -e
LOG_DIR="logs"
echo "[*] Nettoyage des logs dans ${LOG_DIR}..."
rm -f ${LOG_DIR}/*.log || true
echo "[*] Logs nettoyés."

