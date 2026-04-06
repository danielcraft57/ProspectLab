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

ARCH="$(uname -m)"
CONDA_INSTALL_URL=""
CONDA_INSTALL_CANDIDATES=""
FORCE_NO_CONDA=0
case "$ARCH" in
    x86_64|amd64)
        CONDA_INSTALL_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
        CONDA_INSTALL_CANDIDATES="$CONDA_INSTALL_URL"
        ;;
    aarch64|arm64)
        CONDA_INSTALL_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
        CONDA_INSTALL_CANDIDATES="$CONDA_INSTALL_URL"
        ;;
    armv7l|armv7|armhf)
        # armv7l (32-bit ARM): Conda/Miniforge n'est plus fiable/maintenu partout.
        # On force le mode "venv python3.11" via apt (beaucoup plus robuste).
        FORCE_NO_CONDA=1
        ;;
    *)
        echo "[!] Architecture non gérée pour installation auto de Conda: $ARCH"
        echo "    Installe Conda/Miniforge manuellement sur ce noeud."
        ;;
esac

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
    python3-full \
    python3-venv \
    python3-pip \
    python3-dev \
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
RECREATE_ENV=0
CONDA_EXE=""
REINSTALL_MINICONDA=0

if [ -x "$ENV_DIR/bin/python" ]; then
    CURRENT_ENV_PY_MM="$("$ENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo unknown)"
    if [ "$CURRENT_ENV_PY_MM" != "3.11" ]; then
        echo "   [!] Environnement existant en Python $CURRENT_ENV_PY_MM (attendu: 3.11) -> recréation"
        RECREATE_ENV=1
        rm -rf "$ENV_DIR"
    fi
fi

if [ -x "$HOME/miniconda3/bin/conda" ]; then
    # Miniconda détecté (utilisation directe du binaire conda, plus robuste que source conda.sh)
    USE_CONDA=1
    CONDA_EXE="$HOME/miniconda3/bin/conda"
elif [ -x "$HOME/anaconda3/bin/conda" ]; then
    USE_CONDA=1
    CONDA_EXE="$HOME/anaconda3/bin/conda"
elif command -v conda >/dev/null 2>&1; then
    USE_CONDA=1
    CONDA_EXE="$(command -v conda)"
fi

# armv7l: ignorer Conda même si présent (souvent trop vieux / casse SSL)
if [ "$FORCE_NO_CONDA" -eq 1 ]; then
    USE_CONDA=0
    CONDA_EXE=""
fi

# Un conda "exécutable" peut quand même être au mauvais format (ex: x86_64 sur ARM)
# => Exec format error. Dans ce cas, on force une réinstallation Miniconda aarch64.
if [ "$USE_CONDA" -eq 1 ]; then
    if ! "$CONDA_EXE" --version >/dev/null 2>&1; then
        echo "   [!] Conda détecté mais inutilisable (format binaire incompatible ?): $CONDA_EXE"
        USE_CONDA=0
        CONDA_EXE=""
        REINSTALL_MINICONDA=1
    fi
fi

if [ "$USE_CONDA" -eq 1 ]; then
    echo "   - Utilisation de Conda (env prefix=$ENV_DIR)"
    if [ ! -d "$ENV_DIR" ] || [ "$RECREATE_ENV" -eq 1 ]; then
        "$CONDA_EXE" create --prefix "$ENV_DIR" python=3.11 -y --override-channels -c conda-forge
        echo "   [✓] Environnement Conda créé"
    else
        echo "   [✓] Environnement Conda déjà présent"
    fi
    PYTHON_BIN="$ENV_DIR/bin/python"
    PIP_BIN="$ENV_DIR/bin/pip"
else
    echo "   - Conda non détecté, fallback sur venv intégré"
    # pandas==2.1.3 ne supporte pas correctement Python 3.13 (erreurs C-API).
    # On préfère 3.11/3.12 pour l'env venv, sinon on stoppe avec un message clair.
    VENV_PYTHON_BIN=""
    if command -v python3.11 >/dev/null 2>&1; then
        VENV_PYTHON_BIN="python3.11"
    elif command -v python3.12 >/dev/null 2>&1; then
        VENV_PYTHON_BIN="python3.12"
    else
        PY_MM="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        if [ "$PY_MM" = "3.13" ]; then
            if [ "$FORCE_NO_CONDA" -eq 1 ]; then
                echo "[!] Python système = 3.13 sur armv7l: installation de python3.11 + venv via apt..."
                sudo apt-get update
                sudo apt-get install -y python3.11 python3.11-venv python3.11-dev || {
                    echo "[!] Impossible d'installer python3.11 sur ce noeud (ARCH=$ARCH)."
                    echo "    Soit tu n'utilises pas ce noeud comme worker (recommandé pour armv7l),"
                    echo "    soit tu restes sur Debian 12 (Python 3.11) sur ce noeud."
                    exit 1
                }
                VENV_PYTHON_BIN="python3.11"
            else
                echo "[!] Python système = 3.13 détecté, tentative d'installation automatique de Miniconda..."
            CONDA_INSTALL_SH="/tmp/conda-installer.sh"
            if [ "$REINSTALL_MINICONDA" -eq 1 ] && [ -d "$HOME/miniconda3" ]; then
                echo "   [i] Suppression de l'installation Miniconda existante (incompatible) ..."
                rm -rf "$HOME/miniconda3"
            fi
            if [ ! -x "$HOME/miniconda3/bin/conda" ]; then
                if [ -n "$CONDA_INSTALL_CANDIDATES" ]; then
                    for candidate in $CONDA_INSTALL_CANDIDATES; do
                        if curl -fsI "$candidate" >/dev/null 2>&1; then
                            CONDA_INSTALL_URL="$candidate"
                            break
                        fi
                    done
                fi
                if [ -z "$CONDA_INSTALL_URL" ]; then
                    echo "[!] Impossible d'installer Conda automatiquement: URL inconnue pour ARCH=$ARCH"
                    if [ -n "$CONDA_INSTALL_CANDIDATES" ]; then
                        echo "    Candidats testés:"
                        for candidate in $CONDA_INSTALL_CANDIDATES; do
                            echo "    - $candidate"
                        done
                    fi
                    exit 1
                fi
                echo "   [i] Téléchargement Conda pour ARCH=$ARCH"
                curl -fsSL "$CONDA_INSTALL_URL" -o "$CONDA_INSTALL_SH"
                # Les options varient selon Miniconda/Miniforge. Pour éviter les erreurs (ex: -u),
                # on fait une réinstallation propre si le dossier existe.
                if [ -d "$HOME/miniconda3" ]; then
                    rm -rf "$HOME/miniconda3"
                fi
                bash "$CONDA_INSTALL_SH" -b -p "$HOME/miniconda3"
                rm -f "$CONDA_INSTALL_SH"
            fi
            if [ ! -x "$HOME/miniconda3/bin/conda" ]; then
                echo "[!] Miniconda installé mais binaire conda introuvable: $HOME/miniconda3/bin/conda"
                exit 1
            fi
            CONDA_EXE="$HOME/miniconda3/bin/conda"
            if ! "$CONDA_EXE" --version >/dev/null 2>&1; then
                echo "[!] Conda installé mais non exécutable correctement (possible problème d'architecture)."
                exit 1
            fi
            echo "   [✓] Miniconda installé/détecté, bascule en mode Conda"
            if [ ! -d "$ENV_DIR" ]; then
                "$CONDA_EXE" create --prefix "$ENV_DIR" python=3.11 -y --override-channels -c conda-forge
                echo "   [✓] Environnement Conda créé"
            else
                echo "   [✓] Environnement Conda déjà présent"
            fi
            PYTHON_BIN="$ENV_DIR/bin/python"
            PIP_BIN="$ENV_DIR/bin/pip"
            VENV_PYTHON_BIN=""
            USE_CONDA=1
            fi
        else
            VENV_PYTHON_BIN="python3"
        fi
    fi

    if [ "${USE_CONDA:-0}" -eq 0 ]; then
        if [ ! -d "$ENV_DIR" ] || [ "$RECREATE_ENV" -eq 1 ]; then
            "$VENV_PYTHON_BIN" -m venv "$ENV_DIR"
            echo "   [✓] Environnement venv créé"
        else
            echo "   [✓] Environnement venv déjà présent"
        fi
        PYTHON_BIN="$ENV_DIR/bin/python"
        PIP_BIN="$ENV_DIR/bin/pip"
    fi
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

