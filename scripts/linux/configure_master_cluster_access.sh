#!/usr/bin/env bash

# Configure le "master" (node15.lan typiquement) pour accepter les workers du cluster :
# - Redis écoute sur le réseau local
# - PostgreSQL écoute sur le réseau local et autorise les IP du LAN
#
# À exécuter directement sur node15.lan :
#   bash scripts/linux/configure_master_cluster_access.sh

set -e

echo "=========================================="
echo "Configuration du serveur master pour le cluster ProspectLab"
echo "  - Ouverture Redis sur le LAN"
echo "  - Ouverture PostgreSQL sur le LAN"
echo "=========================================="
echo

echo "[1/4] Configuration Redis..."

if ! command -v redis-server >/dev/null 2>&1; then
  echo "[!] redis-server n'est pas installé, installation..."
  sudo apt-get update
  sudo apt-get install -y redis-server
fi

REDIS_CONF="/etc/redis/redis.conf"

if [ ! -f "$REDIS_CONF" ]; then
  echo "[✗] Fichier $REDIS_CONF introuvable"
else
  sudo cp "$REDIS_CONF" "${REDIS_CONF}.backup_cluster_$(date +%Y%m%d_%H%M%S)"

  # Autoriser l'écoute sur toutes les interfaces (le firewall doit protéger l'accès)
  if grep -qE '^\s*bind\s' "$REDIS_CONF"; then
    sudo sed -i "s/^\s*bind .*/bind 0.0.0.0/" "$REDIS_CONF"
  else
    echo "bind 0.0.0.0" | sudo tee -a "$REDIS_CONF" >/dev/null
  fi

  # Laisser protected-mode activé (par défaut) pour limiter certains abus
  # mais Redis sera joignable depuis le LAN.

  echo "[✓] redis.conf mis à jour (bind 0.0.0.0)"
fi

echo "[*] Redémarrage de redis-server..."
sudo systemctl restart redis-server

if sudo systemctl is-active --quiet redis-server; then
  echo "[✓] Redis est actif"
else
  echo "[✗] Redis ne démarre pas, vérifie les logs: sudo journalctl -u redis-server -n 50"
  exit 1
fi

echo
echo "[2/4] Détection de la version PostgreSQL..."

if ! command -v psql >/dev/null 2>&1; then
  echo "[!] PostgreSQL n'est pas installé, installation..."
  sudo apt-get update
  sudo apt-get install -y postgresql postgresql-contrib
fi

PG_VERSION=$(ls -1 /etc/postgresql/ 2>/dev/null | head -1)
if [ -z "$PG_VERSION" ]; then
  PG_VERSION="17"
fi

PG_CONF_DIR="/etc/postgresql/${PG_VERSION}/main"
PG_CONF="${PG_CONF_DIR}/postgresql.conf"
PG_HBA="${PG_CONF_DIR}/pg_hba.conf"

echo "  - Version PostgreSQL détectée : $PG_VERSION"
echo "  - Dossier de config : $PG_CONF_DIR"
echo

if [ ! -f "$PG_CONF" ] || [ ! -f "$PG_HBA" ]; then
  echo "[✗] Fichiers de configuration PostgreSQL introuvables dans $PG_CONF_DIR"
  exit 1
fi

echo "[3/4] Configuration PostgreSQL (écoute réseau + pg_hba)..."

sudo cp "$PG_CONF" "${PG_CONF}.backup_cluster_$(date +%Y%m%d_%H%M%S)"
sudo cp "$PG_HBA" "${PG_HBA}.backup_cluster_$(date +%Y%m%d_%H%M%S)"

# 3.1 écouter sur toutes les interfaces
if grep -qE "^\s*listen_addresses" "$PG_CONF"; then
  sudo sed -i "s/^\s*listen_addresses.*/listen_addresses = '*'/" "$PG_CONF"
else
  echo "listen_addresses = '*'" | sudo tee -a "$PG_CONF" >/dev/null
fi

# 3.2 autoriser les IP du réseau local dans pg_hba.conf
# Pour ton réseau: 192.168.1.0/16
LAN_CIDR_DEFAULT="192.168.1.0/16"

if ! grep -q "$LAN_CIDR_DEFAULT" "$PG_HBA"; then
  {
    echo ""
    echo "# Ajout pour cluster ProspectLab (workers Raspberry Pi)"
    echo "host    all             all             ${LAN_CIDR_DEFAULT}          md5"
  } | sudo tee -a "$PG_HBA" >/dev/null
  echo "[✓] Règle pg_hba ajoutée pour ${LAN_CIDR_DEFAULT}"
else
  echo "[i] Règle pg_hba pour ${LAN_CIDR_DEFAULT} déjà présente"
fi

echo "[*] Redémarrage de PostgreSQL..."
sudo systemctl restart postgresql

if sudo systemctl is-active --quiet postgresql; then
  echo "[✓] PostgreSQL est actif"
else
  echo "[✗] PostgreSQL ne démarre pas, vérifie les logs: sudo journalctl -u postgresql -n 50"
  exit 1
fi

echo
echo "[4/4] Vérifications rapides (écoute sur les ports)..."

echo "  - Redis (6379) :"
if command -v ss >/dev/null 2>&1; then
  sudo ss -tlnp | grep 6379 || echo "    (aucune écoute détectée sur 6379)"
else
  sudo netstat -tlnp | grep 6379 || echo "    (aucune écoute détectée sur 6379)"
fi

echo
echo "  - PostgreSQL (5432) :"
if command -v ss >/dev/null 2>&1; then
  sudo ss -tlnp | grep 5432 || echo "    (aucune écoute détectée sur 5432)"
else
  sudo netstat -tlnp | grep 5432 || echo "    (aucune écoute détectée sur 5432)"
fi

echo
echo "=========================================="
echo "Configuration master terminée."
echo "Les workers (node10-14) doivent pouvoir atteindre :"
echo "  - redis://<IP_NODE15>:6379/1"
echo "  - postgresql://prospectlab:...@<IP_NODE15>:5432/prospectlab"
echo "Pense à vérifier ton firewall (ufw/iptables) si nécessaire."
echo "=========================================="

