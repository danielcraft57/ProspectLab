#!/usr/bin/env bash
# Nettoie logs, base et Redis (Debian/Bookworm)
set -e

echo "[*] Nettoyage complet..."

echo "[1/3] Logs"
rm -f logs/*.log || true

echo "[2/3] Base SQLite"
rm -f prospectlab.db || true

echo "[3/3] Redis"
redis-cli FLUSHALL || true

echo "[*] Nettoyage terminé."

