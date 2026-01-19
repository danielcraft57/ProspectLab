#!/usr/bin/env bash
# Stoppe redis-server lancé en mode --daemonize (WSL fallback)
set -e
echo "[*] Arret de redis-server (WSL fallback)..."
redis-cli shutdown || true

