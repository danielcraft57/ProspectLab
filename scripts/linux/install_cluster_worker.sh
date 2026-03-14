#!/usr/bin/env bash

# Installation d'un noeud worker Celery complet (OSINT / SEO / technique / scraping)
# sur un Raspberry Pi (aarch64, Debian / Raspberry Pi OS Bookworm ou Trixie).
#
# Usage (sur le RPi, connecté en pi@node13.lan ou pi@node14.lan) :
#   sudo mkdir -p /opt/prospectlab
#   sudo chown -R pi:pi /opt/prospectlab
#   # Copier ou cloner le projet dans /opt/prospectlab
#   cd /opt/prospectlab
#   bash scripts/linux/install_cluster_worker.sh
#
# Prérequis :
#   - Le dépôt ProspectLab est déjà présent dans /opt/prospectlab
#   - Un fichier .env sera créé ou copié après l'installation
#   - Un serveur "master" (node15.lan par exemple) fournit :
#       * Redis (CELERY_BROKER_URL)
#       * PostgreSQL (DATABASE_URL)
#       * L'application Flask

set -e

echo "=========================================="
echo "Installation d'un worker Celery ProspectLab"
echo "=========================================="
echo

PROJECT_DIR="/opt/prospectlab"
ENV_DIR="$PROJECT_DIR/env"
SERVICE_USER="pi"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "[!] Erreur : le dossier $PROJECT_DIR n'existe pas."
    echo "    Copiez ou clonez d'abord le dépôt ProspectLab dans $PROJECT_DIR."
    exit 1
fi

cd "$PROJECT_DIR"

echo "[1/6] Installation des dépendances système de base..."
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    pkg-config \
    git \
    curl
echo "[✓] Dépendances système installées"
echo

echo "[2/6] Environnement Python (Conda recommandé, sinon venv classique)..."

USE_CONDA=0
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    # Miniconda aarch64 installé
    USE_CONDA=1
    # shellcheck source=/dev/null
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    USE_CONDA=1
    # shellcheck source=/dev/null
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
fi

if [ "$USE_CONDA" -eq 1 ]; then
    echo "   - Utilisation de Conda (env prefix=$ENV_DIR)"
    if [ ! -d "$ENV_DIR" ]; then
        conda create --prefix "$ENV_DIR" python=3.11 -y --override-channels -c conda-forge
        echo "   [✓] Environnement Conda créé"
    else
        echo "   [✓] Environnement Conda déjà présent"
    fi
    PYTHON_BIN="$ENV_DIR/bin/python"
    PIP_BIN="$ENV_DIR/bin/pip"
else
    echo "   - Conda non détecté, fallback sur venv intégré"
    if [ ! -d "$ENV_DIR" ]; then
        python3 -m venv "$ENV_DIR"
        echo "   [✓] Environnement venv créé"
    else
        echo "   [✓] Environnement venv déjà présent"
    fi
    PYTHON_BIN="$ENV_DIR/bin/python"
    PIP_BIN="$ENV_DIR/bin/pip"
fi

"$PIP_BIN" install --upgrade pip setuptools wheel
echo "[✓] Environnement Python prêt"
echo

echo "[3/6] Installation des dépendances Python de ProspectLab..."
if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "[!] Erreur : requirements.txt introuvable dans $PROJECT_DIR"
    exit 1
fi

"$PIP_BIN" install -r "$PROJECT_DIR/requirements.txt"
echo "[✓] Dépendances Python installées"
echo

echo "[4/6] Installation des outils OSINT / Pentest / SEO (noeud worker complet)..."
if [ -x "$PROJECT_DIR/scripts/linux/install_all_tools.sh" ]; then
    bash "$PROJECT_DIR/scripts/linux/install_all_tools.sh"
    echo "[✓] Outils externes installés (selon la distribution détectée)"
else
    echo "[!] Script scripts/linux/install_all_tools.sh introuvable ou non exécutable."
    echo "    Tu pourras l'exécuter plus tard manuellement si besoin."
fi
echo

echo "[5/6] Préparation des répertoires et permissions..."
mkdir -p "$PROJECT_DIR/logs"
chmod +x "$PROJECT_DIR"/scripts/linux/*.sh 2>/dev/null || true

echo "[✓] Répertoires et scripts prêts"
echo

echo "[6/6] Création du service systemd pour le worker Celery..."

sudo tee /etc/systemd/system/prospectlab-celery.service > /dev/null << SERVICE_EOF
[Unit]
Description=ProspectLab Celery Worker (noeud cluster)
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$ENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/scripts/linux/start_celery_worker.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo systemctl daemon-reload

echo "[i] Le fichier .env doit exister dans $PROJECT_DIR avant de démarrer le service."
echo "    Copie recommandée depuis le master (node15.lan), puis adaptation des variables suivantes :"
echo
echo "    - CELERY_BROKER_URL=redis://node15.lan:6379/1"
echo "    - CELERY_RESULT_BACKEND=redis://node15.lan:6379/1"
echo "    - DATABASE_URL=postgresql://prospectlab:motdepasse@node15.lan:5432/prospectlab"
echo
echo "Quand le .env est prêt, active et démarre le worker avec :"
echo "    sudo systemctl enable prospectlab-celery"
echo "    sudo systemctl start prospectlab-celery"
echo
echo "Pour voir l'état du worker :"
echo "    sudo systemctl status prospectlab-celery"
echo
echo "Installation du worker Celery terminée."

