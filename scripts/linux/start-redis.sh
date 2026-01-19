#!/usr/bin/env bash
# Démarre Redis en local (Debian/Bookworm)
set -e
echo "[*] Demarrage de Redis..."
sudo systemctl start redis-server
sudo systemctl status redis-server --no-pager

