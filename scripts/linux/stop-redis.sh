#!/usr/bin/env bash
# Stoppe Redis en local (Debian/Bookworm)
set -e
echo "[*] Arret de Redis..."
sudo systemctl stop redis-server
sudo systemctl status redis-server --no-pager || true

