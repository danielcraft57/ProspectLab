#!/usr/bin/env bash
# Lance Redis sur WSL (fallback si service systemd non dispo)
set -e
echo "[*] Demarrage de redis-server (WSL fallback)..."
redis-server --daemonize yes
redis-cli ping

