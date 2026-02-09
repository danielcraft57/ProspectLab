#!/bin/bash
# Script de déploiement ProspectLab en production
# Usage: ./scripts/deploy_production.sh [serveur] [utilisateur] [chemin]

set -e

# Configuration par défaut (modifiable via paramètres)
SERVER="${1:-node15.lan}"
USER="${2:-pi}"
REMOTE_PATH="${3:-/opt/prospectlab}"

# Obtenir le répertoire du projet ProspectLab (parent du dossier scripts)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo "Déploiement ProspectLab en production"
echo "=========================================="
echo ""

# Vérifier la connexion SSH
echo "[1/8] Vérification de la connexion SSH..."
if ! ssh -o ConnectTimeout=5 "$USER@$SERVER" "echo 'Connexion OK'" > /dev/null 2>&1; then
    echo "❌ Impossible de se connecter au serveur"
    echo "   Vérifiez que:"
    echo "   - Le serveur est allumé"
    echo "   - SSH est activé"
    echo "   - La clé SSH est configurée"
    exit 1
fi
echo "✅ Connexion SSH OK"
echo ""

# Créer le répertoire de déploiement local
echo "[2/8] Préparation des fichiers locaux..."
DEPLOY_DIR="$PROJECT_DIR/deploy"
if [ -d "$DEPLOY_DIR" ]; then
    rm -rf "$DEPLOY_DIR"
fi
mkdir -p "$DEPLOY_DIR"

# Copier les fichiers nécessaires
FILES_TO_COPY=(
    'routes'
    'services'
    'tasks'
    'templates'
    'static'
    'utils'
    'scripts'
    'app.py'
    'celery_app.py'
    'config.py'
    'requirements.txt'
    'README.md'
    'run_celery.py'
)

# Vérifier que templates/pages existe et sera copié avec templates
echo "   Vérification des templates/pages..."
if [ -d "$PROJECT_DIR/templates/pages" ]; then
    echo "  [+] templates/pages détecté"
fi

echo "   Copie des fichiers..."
for item in "${FILES_TO_COPY[@]}"; do
    if [ -e "$PROJECT_DIR/$item" ]; then
        cp -r "$PROJECT_DIR/$item" "$DEPLOY_DIR/"
        echo "  [+] $item"
        
        # Vérifications supplémentaires pour les dossiers importants
        if [ "$item" = "templates" ]; then
            if [ -d "$DEPLOY_DIR/templates/pages" ]; then
                PAGE_COUNT=$(find "$DEPLOY_DIR/templates/pages" -name "*.html" -type f 2>/dev/null | wc -l)
                echo "     └─ templates/pages/ : $PAGE_COUNT fichiers HTML"
            fi
        fi
        if [ "$item" = "static" ]; then
            JS_COUNT=0
            CSS_COUNT=0
            if [ -d "$DEPLOY_DIR/static/js" ]; then
                JS_COUNT=$(find "$DEPLOY_DIR/static/js" -name "*.js" -type f 2>/dev/null | wc -l)
            fi
            if [ -d "$DEPLOY_DIR/static/css" ]; then
                CSS_COUNT=$(find "$DEPLOY_DIR/static/css" -name "*.css" -type f 2>/dev/null | wc -l)
            fi
            echo "     └─ static/ : $JS_COUNT fichiers JS, $CSS_COUNT fichiers CSS"
        fi
    fi
done

# Exclure les fichiers inutiles
echo "   Nettoyage des fichiers inutiles..."
find "$DEPLOY_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOY_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$DEPLOY_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$DEPLOY_DIR" -type d -name ".git" -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOY_DIR" -type d -name "venv" -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOY_DIR" -type d -name "env" -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOY_DIR" -type f -name ".env" -delete 2>/dev/null || true
find "$DEPLOY_DIR" -type f -name "*.db" -delete 2>/dev/null || true
find "$DEPLOY_DIR" -type f -name "*.log" -delete 2>/dev/null || true
find "$DEPLOY_DIR" -type d -name "logs" -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOY_DIR" -type d -name "logs_server" -exec rm -rf {} + 2>/dev/null || true

echo "✅ Fichiers préparés"
echo ""

# Vérifier Python sur le serveur
echo "[3/8] Vérification de Python..."
PYTHON_VERSION=$(ssh "$USER@$SERVER" "python3 --version 2>&1 | head -1" || echo "")
if [ -z "$PYTHON_VERSION" ]; then
    echo "❌ Python3 n'est pas installé sur le serveur"
    exit 1
fi
echo "✅ $PYTHON_VERSION détecté"
echo ""

# Créer le répertoire sur le serveur
echo "[4/8] Préparation du répertoire sur le serveur..."
ssh "$USER@$SERVER" "sudo mkdir -p $REMOTE_PATH && sudo chown -R $USER:$USER $REMOTE_PATH"
echo "✅ Répertoire créé sur le serveur"
echo ""

# Copier les fichiers vers le serveur
echo "[5/8] Transfert des fichiers vers le serveur..."
echo "   Cela peut prendre quelques instants..."
scp -r "$DEPLOY_DIR"/* "$USER@$SERVER:$REMOTE_PATH/" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Erreur lors du transfert des fichiers"
    echo "   Vérifiez les permissions et la connexion SSH"
    exit 1
fi
echo "✅ Fichiers transférés"
echo "   Envoi explicite des dossiers (routes, services, tasks, templates, static, utils, scripts)..."
for dir in routes services tasks templates static utils scripts; do
    if [ -d "$DEPLOY_DIR/$dir" ]; then
        scp -r "$DEPLOY_DIR/$dir" "$USER@$SERVER:$REMOTE_PATH/"
        if [ $? -ne 0 ]; then
            echo "❌ Erreur lors de l'envoi de $dir"
            exit 1
        fi
    fi
done
echo "✅ Dossiers synchronisés"
echo ""

# Créer l'environnement virtuel sur le serveur
echo "[6/8] Configuration de l'environnement virtuel..."
ssh "$USER@$SERVER" "cd $REMOTE_PATH && if [ ! -d venv ]; then python3 -m venv venv; fi"
ssh "$USER@$SERVER" "cd $REMOTE_PATH && source venv/bin/activate && pip install --upgrade pip setuptools wheel && pip install -r requirements.txt"
if [ $? -ne 0 ]; then
    echo "❌ Erreur lors de l'installation des dépendances"
    exit 1
fi
echo "✅ Environnement virtuel configuré"
echo ""

# Créer les répertoires nécessaires
echo "[7/8] Création des répertoires nécessaires..."
ssh "$USER@$SERVER" "cd $REMOTE_PATH && mkdir -p logs logs_server"
echo "✅ Répertoires créés"
echo ""

# Ajouter les permissions d'exécution aux scripts shell
echo "[7.5/8] Configuration des permissions des scripts..."
ssh "$USER@$SERVER" "cd $REMOTE_PATH && find scripts/linux -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true"
ssh "$USER@$SERVER" "cd $REMOTE_PATH && find scripts -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true"
echo "✅ Permissions des scripts configurées"
echo ""

# Instructions finales
echo "[8/8] Déploiement terminé !"
echo ""
echo "Prochaines étapes:"
echo "1. Connectez-vous au serveur de production"
echo "2. Allez dans le répertoire de déploiement"
echo "3. Configurez le fichier .env avec vos paramètres de production"
echo "4. Activez l'environnement virtuel: source venv/bin/activate"
echo "5. Initialisez la base de données si nécessaire"
echo "6. Démarrez l'application avec Gunicorn ou configurez un service systemd"
echo ""
echo "Pour plus d'informations, consultez:"
echo "  docs/configuration/DEPLOIEMENT_PRODUCTION.md"
echo ""

# Nettoyer le répertoire de déploiement local
rm -rf "$DEPLOY_DIR"
echo "✅ Répertoire de déploiement local nettoyé"
