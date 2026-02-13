#!/usr/bin/env bash

# Script pour mettre à jour le venv Python vers une version plus récente
# Usage: bash scripts/linux/upgrade_python_venv.sh [3.11|3.12]
# Par défaut, essaie d'installer Python 3.11 (disponible sur Bookworm)

set -e

PROJECT_DIR="${PROJECT_DIR:-/opt/prospectlab}"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/venv}"
PYTHON_VERSION="${1:-3.11}"

echo "=========================================="
echo "  Mise à jour du venv Python"
echo "  Version cible: Python $PYTHON_VERSION"
echo "=========================================="
echo

# Vérifier si on est dans le bon répertoire
if [ ! -d "$PROJECT_DIR" ]; then
    echo "[!] Répertoire projet non trouvé: $PROJECT_DIR"
    echo "[*] Utilisez: PROJECT_DIR=/chemin/vers/prospectlab bash $0"
    exit 1
fi

cd "$PROJECT_DIR"

# Vérifier les versions Python disponibles
echo "[*] Vérification des versions Python disponibles sur le système..."

# Chercher toutes les versions Python disponibles
FOUND_PYTHON=""
FOUND_VERSION=""

# Vérifier python3.13, 3.12, 3.11, 3.10, 3.9 dans l'ordre décroissant
for v in 3.13 3.12 3.11 3.10 3.9; do
    if command -v python${v} >/dev/null 2>&1; then
        FOUND_PYTHON="python${v}"
        FOUND_VERSION="$v"
        echo "[OK] Python $v trouvé: $(command -v $FOUND_PYTHON)"
        break
    fi
done

# Si aucune version spécifique trouvée, utiliser python3
if [ -z "$FOUND_PYTHON" ]; then
    if command -v python3 >/dev/null 2>&1; then
        FOUND_PYTHON="python3"
        FOUND_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        echo "[OK] python3 trouvé: $(command -v $FOUND_PYTHON) (version $FOUND_VERSION)"
    else
        echo "[✗] Aucune version Python trouvée sur le système"
        exit 1
    fi
fi

# Si une version spécifique est demandée et différente de celle trouvée
if [ -n "$1" ] && [ "$1" != "$FOUND_VERSION" ]; then
    echo "[*] Version demandée: Python $1"
    echo "[*] Version disponible: Python $FOUND_VERSION"
    
    # Essayer d'installer depuis les backports ou deadsnakes
    if [ "$1" = "3.11" ] || [ "$1" = "3.12" ]; then
        echo "[*] Tentative d'installation de Python $1..."
        echo "[*] Option 1: Backports Debian..."
        sudo apt-get update
        sudo apt-get install -y -t bookworm-backports python${1} python${1}-venv python${1}-dev || {
            echo "[!] Backports non disponibles"
            echo "[*] Option 2: Utilisation de la version disponible ($FOUND_VERSION)..."
            PYTHON_CMD="$FOUND_PYTHON"
            PYTHON_VERSION="$FOUND_VERSION"
        }
    else
        echo "[!] Version $1 non disponible, utilisation de Python $FOUND_VERSION"
        PYTHON_CMD="$FOUND_PYTHON"
        PYTHON_VERSION="$FOUND_VERSION"
    fi
else
    PYTHON_CMD="$FOUND_PYTHON"
    PYTHON_VERSION="$FOUND_VERSION"
fi

# Vérifier que la commande Python fonctionne
if ! $PYTHON_CMD --version >/dev/null 2>&1; then
    echo "[✗] La commande $PYTHON_CMD ne fonctionne pas"
    exit 1
fi

echo
echo "[*] Version Python qui sera utilisée: $PYTHON_VERSION ($PYTHON_CMD)"
$PYTHON_CMD --version

# Sauvegarder les dépendances actuelles si le venv existe
if [ -d "$VENV_DIR" ]; then
    echo
    echo "[*] Sauvegarde des dépendances actuelles..."
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate" || true
        pip freeze > /tmp/prospectlab_requirements_backup.txt 2>/dev/null || true
        deactivate || true
        echo "[OK] Dépendances sauvegardées dans /tmp/prospectlab_requirements_backup.txt"
    fi
    
    echo "[*] Suppression de l'ancien venv..."
    rm -rf "$VENV_DIR"
    echo "[OK] Ancien venv supprimé"
fi

# Créer le nouveau venv
echo
echo "[*] Création du nouveau venv avec Python $PYTHON_VERSION..."
$PYTHON_CMD -m venv "$VENV_DIR"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "[✗] Échec de la création du venv"
    exit 1
fi

echo "[OK] Nouveau venv créé"

# Activer le venv et mettre à jour pip
echo
echo "[*] Activation du venv et mise à jour de pip..."
source "$VENV_DIR/bin/activate"
python --version
pip install --upgrade pip setuptools wheel

# Réinstaller les dépendances si sauvegardées
if [ -f /tmp/prospectlab_requirements_backup.txt ]; then
    echo
    echo "[*] Réinstallation des dépendances..."
    pip install -r /tmp/prospectlab_requirements_backup.txt || {
        echo "[!] Certaines dépendances ont échoué, mais le venv est créé"
        echo "[*] Tu peux réinstaller manuellement avec: pip install -r requirements.txt"
    }
else
    echo
    echo "[*] Aucune sauvegarde de dépendances trouvée"
    echo "[*] Réinstalle les dépendances avec: pip install -r requirements.txt"
fi

echo
echo "=========================================="
echo "  Venv mis à jour avec succès !"
echo "  Python: $PYTHON_VERSION"
echo "  Chemin: $VENV_DIR"
echo "=========================================="
echo
echo "[*] Pour activer le venv:"
echo "    source $VENV_DIR/bin/activate"
echo
echo "[*] Pour vérifier la version:"
echo "    python --version"
