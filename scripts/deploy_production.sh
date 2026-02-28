#!/bin/bash
# Script de déploiement ProspectLab en production
# Usage: ./scripts/deploy_production.sh [serveur] [utilisateur] [chemin]

set -e

# Configuration par défaut (exemples — personnalisez en paramètres ou variables d'environnement)
# Usage: ./deploy_production.sh [serveur_app] [utilisateur] [chemin] [serveur_proxy_nginx] [utilisateur_proxy]
# Exemple: ./deploy_production.sh serveur-app.lan deploy /opt/prospectlab serveur-proxy.lan deploy
SERVER="${1:-serveur-app.lan}"
USER="${2:-deploy}"
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

# Vérifier Conda sur le serveur
echo "[3/8] Vérification de Conda..."
CONDA_CMD=$(ssh "$USER@$SERVER" "which conda 2>/dev/null || (source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null && which conda) || (source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null && which conda) || true" || echo "")
if [ -z "$CONDA_CMD" ]; then
    echo "❌ Conda n'est pas installé sur le serveur (miniconda3 ou anaconda3)"
    echo "   Installez Miniconda puis relancez le déploiement."
    exit 1
fi
echo "✅ Conda détecté"
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

# Créer ou mettre à jour l'environnement Conda sur le serveur (prefix = env)
echo "[6/8] Configuration de l'environnement Conda..."
ssh "$USER@$SERVER" "set -e; source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh; cd $REMOTE_PATH; if [ ! -d env ]; then conda create --prefix $REMOTE_PATH/env python=3.11 -y --override-channels -c conda-forge; fi; $REMOTE_PATH/env/bin/pip install --upgrade pip setuptools wheel; $REMOTE_PATH/env/bin/pip install -r requirements.txt"
if [ $? -ne 0 ]; then
    echo "❌ Erreur lors de l'installation des dépendances Conda/pip"
    exit 1
fi
echo "✅ Environnement Conda configuré (prefix=$REMOTE_PATH/env)"
echo ""

# Créer les répertoires nécessaires
echo "[7/8] Création des répertoires nécessaires..."
ssh "$USER@$SERVER" "cd $REMOTE_PATH && mkdir -p logs logs_server"
echo "✅ Répertoires créés"
echo ""

# Ajouter les permissions d'exécution aux scripts shell
echo "[7.5/9] Configuration des permissions des scripts..."
ssh "$USER@$SERVER" "cd $REMOTE_PATH && find scripts/linux -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true"
ssh "$USER@$SERVER" "cd $REMOTE_PATH && find scripts -name '*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true"
echo "✅ Permissions des scripts configurées"
echo ""

# Mettre à jour les services systemd pour Conda (env) si le script existe
echo "[7.6/9] Mise à jour des services systemd (Conda)..."
if ssh "$USER@$SERVER" "test -x $REMOTE_PATH/scripts/linux/update_services_to_conda.sh" 2>/dev/null; then
    ssh "$USER@$SERVER" "cd $REMOTE_PATH && sudo bash scripts/linux/update_services_to_conda.sh" 2>/dev/null && echo "✅ Services systemd mis à jour" || echo "⚠️  Mise à jour des services ignorée (vérifiez sudo)"
else
    echo "   (script update_services_to_conda.sh non trouvé, ignoré)"
fi
echo ""

# Nettoyage du cache et redémarrage des services
echo "[8/9] Nettoyage du cache et redémarrage des services..."
ssh "$USER@$SERVER" "cd $REMOTE_PATH; if [ -x scripts/linux/clear-logs.sh ]; then ./scripts/linux/clear-logs.sh; fi"
ssh "$USER@$SERVER" "sudo systemctl restart prospectlab prospectlab-celery prospectlab-celerybeat"
echo "✅ Cache vidé et services redémarrés"
echo ""

# Vérification que l'application répond sur le serveur app (évite 502 côté Nginx)
echo "[8.5/9] Vérification de l'application sur $SERVER..."
sleep 3
HTTP_CODE=$(ssh "$USER@$SERVER" "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 http://127.0.0.1:5000/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "301" ]; then
    echo "✅ Application répond sur $SERVER:5000 (HTTP $HTTP_CODE)"
else
    echo "⚠️  L'application ne répond pas correctement sur $SERVER:5000 (HTTP $HTTP_CODE)"
    echo "   Sur le serveur app, vérifiez: sudo systemctl status prospectlab && curl -I http://127.0.0.1:5000/"
    echo "   Si Nginx affiche 502, vérifiez sur le serveur proxy que <SERVEUR_APP> est résolu et que le port 5000 est joignable."
    echo "   Voir: docs/configuration/DEPLOIEMENT_PRODUCTION.md (section Dépannage 502)"
fi
echo ""

# Rechargement Nginx optionnel sur le serveur proxy pour prise en compte immédiate
PROXY_SERVER="${4:-}"
PROXY_USER="${5:-deploy}"
if [ -n "$PROXY_SERVER" ]; then
    echo "[8.6/9] Rechargement Nginx sur le serveur proxy $PROXY_SERVER..."
    if ssh -o ConnectTimeout=5 "$PROXY_USER@$PROXY_SERVER" "sudo nginx -t && sudo systemctl reload nginx" 2>/dev/null; then
        echo "✅ Nginx rechargé sur $PROXY_SERVER"
    else
        echo "⚠️  Impossible de recharger Nginx sur $PROXY_SERVER (vérifiez SSH et sudo)"
    fi
    echo ""
fi

# Instructions finales
echo "[9/9] Déploiement terminé !"
echo ""
echo "Prochaines étapes:"
echo "1. Connectez-vous au serveur de production"
echo "2. Allez dans le répertoire de déploiement"
echo "3. Configurez le fichier .env avec vos paramètres de production"
echo "4. Environnement Conda: $REMOTE_PATH/env (activer avec: source \$CONDA_PREFIX/etc/profile.d/conda.sh && conda activate $REMOTE_PATH/env)"
echo "5. Initialisez la base de données si nécessaire"
echo "6. Démarrez l'application avec Gunicorn ou vérifiez les services systemd"
echo ""
echo "Pour plus d'informations, consultez:"
echo "  docs/configuration/DEPLOIEMENT_PRODUCTION.md"
echo ""

# Nettoyer le répertoire de déploiement local
rm -rf "$DEPLOY_DIR"
echo "✅ Répertoire de déploiement local nettoyé"
