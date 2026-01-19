#!/usr/bin/env bash
# Vide Redis (Debian/Bookworm)
set -e
echo "[*] Flush Redis..."
redis-cli FLUSHALL
echo "[*] Redis vidé."

