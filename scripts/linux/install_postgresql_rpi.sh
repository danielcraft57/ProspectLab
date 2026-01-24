#!/usr/bin/env bash

# Installation et configuration PostgreSQL optimisée pour Raspberry Pi 5
# Spécifique pour: RPi 5, 4GB RAM, 32GB stockage, Debian Trixie
# Exécution: bash scripts/linux/install_postgresql_rpi.sh

set -e

echo "[*] Installation PostgreSQL pour Raspberry Pi 5..."

# Mise à jour du système
echo "[*] Mise à jour APT..."
sudo apt-get update

# Installation PostgreSQL
echo "[*] Installation PostgreSQL..."
sudo apt-get install -y postgresql postgresql-contrib

# Démarrer PostgreSQL
echo "[*] Démarrage PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Obtenir la version PostgreSQL (chercher dans /etc/postgresql/)
PG_VERSION=$(ls -1 /etc/postgresql/ 2>/dev/null | head -1)
if [ -z "$PG_VERSION" ] || [ "$PG_VERSION" = "" ]; then
    # Fallback: version par défaut pour Trixie
    PG_VERSION="17"
fi
echo "[✓] PostgreSQL version $PG_VERSION détectée"

# Configuration mémoire optimisée pour RPi 5 (4GB RAM)
echo "[*] Configuration mémoire optimisée pour RPi 5 (4GB RAM)..."

# Calculer les valeurs optimales
# shared_buffers: 25% de la RAM = 1GB (mais on reste conservateur avec 512MB pour RPi)
# effective_cache_size: 50-75% de la RAM = 2-3GB (on prend 2GB)
# maintenance_work_mem: 512MB max (on prend 256MB)
# work_mem: 4-16MB par connexion (on prend 8MB)
# checkpoint_completion_target: 0.9 pour lisser les I/O
# wal_buffers: 16MB (suffisant)
# default_statistics_target: 100 (standard)

PG_CONFIG="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"

# Backup de la config
sudo cp "$PG_CONFIG" "${PG_CONFIG}.backup"

# Modifications pour RPi 5 optimisé
echo "[*] Application des optimisations..."

# Mémoire
sudo sed -i "s/#shared_buffers = 128MB/shared_buffers = 512MB/" "$PG_CONFIG"
sudo sed -i "s/#effective_cache_size = 4GB/effective_cache_size = 2GB/" "$PG_CONFIG"
sudo sed -i "s/#maintenance_work_mem = 64MB/maintenance_work_mem = 256MB/" "$PG_CONFIG"
sudo sed -i "s/#work_mem = 4MB/work_mem = 8MB/" "$PG_CONFIG"

# WAL (Write-Ahead Logging) - optimisé pour stockage limité
sudo sed -i "s/#wal_buffers = -1/wal_buffers = 16MB/" "$PG_CONFIG"
sudo sed -i "s/#checkpoint_completion_target = 0.9/checkpoint_completion_target = 0.9/" "$PG_CONFIG"
sudo sed -i "s/#min_wal_size = 80MB/min_wal_size = 256MB/" "$PG_CONFIG"
sudo sed -i "s/#max_wal_size = 1GB/max_wal_size = 1GB/" "$PG_CONFIG"

# Connexions (limitées pour RPi)
sudo sed -i "s/#max_connections = 100/max_connections = 50/" "$PG_CONFIG"

# Statistiques
sudo sed -i "s/#default_statistics_target = 100/default_statistics_target = 100/" "$PG_CONFIG"

# Logging (modéré pour économiser l'espace disque)
sudo sed -i "s/#logging_collector = off/logging_collector = on/" "$PG_CONFIG"
sudo sed -i "s/#log_directory = 'log'/log_directory = 'log'/" "$PG_CONFIG"
sudo sed -i "s/#log_rotation_age = 1d/log_rotation_age = 1d/" "$PG_CONFIG"
sudo sed -i "s/#log_rotation_size = 10MB/log_rotation_size = 10MB/" "$PG_CONFIG"
sudo sed -i "s/#log_min_duration_statement = -1/log_min_duration_statement = 1000/" "$PG_CONFIG"

# Autovacuum (important pour maintenir les performances)
sudo sed -i "s/#autovacuum = on/autovacuum = on/" "$PG_CONFIG"
sudo sed -i "s/#autovacuum_max_workers = 3/autovacuum_max_workers = 2/" "$PG_CONFIG"

# Timeouts
sudo sed -i "s/#statement_timeout = 0/statement_timeout = 30000/" "$PG_CONFIG"

echo "[✓] Configuration optimisée appliquée"

# Créer la base de données et l'utilisateur pour ProspectLab
echo "[*] Création de la base de données ProspectLab..."

# Demander les informations (ou utiliser des valeurs par défaut)
DB_NAME="${POSTGRES_DB:-prospectlab}"
DB_USER="${POSTGRES_USER:-prospectlab}"
DB_PASSWORD="${POSTGRES_PASSWORD:-}"

if [ -z "$DB_PASSWORD" ]; then
    echo "[!] Mot de passe PostgreSQL non défini dans POSTGRES_PASSWORD"
    echo "[*] Génération d'un mot de passe aléatoire..."
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    echo "[*] Mot de passe généré: $DB_PASSWORD"
    echo "[!] IMPORTANT: Notez ce mot de passe pour votre fichier .env"
fi

# Créer l'utilisateur
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || echo "[!] Utilisateur $DB_USER existe déjà"

# Créer la base de données
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || echo "[!] Base de données $DB_NAME existe déjà"

# Donner tous les droits
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# Extension pour UUID si besoin
sudo -u postgres psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>/dev/null || true

echo "[✓] Base de données $DB_NAME créée avec l'utilisateur $DB_USER"

# Redémarrer PostgreSQL pour appliquer les changements
echo "[*] Redémarrage PostgreSQL..."
sudo systemctl restart postgresql

# Vérifier que PostgreSQL fonctionne
if sudo systemctl is-active --quiet postgresql; then
    echo "[✓] PostgreSQL est actif et fonctionne"
else
    echo "[!] Erreur: PostgreSQL n'est pas actif"
    exit 1
fi

# Afficher les informations de connexion
echo ""
echo "=========================================="
echo "PostgreSQL installé et configuré !"
echo "=========================================="
echo "Version: $PG_VERSION"
echo "Base de données: $DB_NAME"
echo "Utilisateur: $DB_USER"
echo "Mot de passe: $DB_PASSWORD"
echo ""
echo "URL de connexion:"
echo "DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
echo ""
echo "Pour tester la connexion:"
echo "  psql -h localhost -U $DB_USER -d $DB_NAME"
echo ""
echo "Configuration optimisée pour:"
echo "  - Raspberry Pi 5"
echo "  - 4GB RAM"
echo "  - 32GB stockage"
echo "=========================================="

