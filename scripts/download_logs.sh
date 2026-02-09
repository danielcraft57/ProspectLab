#!/bin/bash
# Script pour télécharger et analyser les logs depuis le serveur de production
# Usage: ./scripts/download_logs.sh [serveur] [utilisateur] [chemin]

set -e

# Configuration par défaut
SERVER="${1:-node15.lan}"
USER="${2:-pi}"
REMOTE_PATH="${3:-/opt/prospectlab}"

# Obtenir le répertoire du projet ProspectLab
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$PROJECT_DIR/logs_analysis"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOGS_ARCHIVE="$LOGS_DIR/logs_$TIMESTAMP"

# Créer le répertoire d'analyse
mkdir -p "$LOGS_DIR"
mkdir -p "$LOGS_ARCHIVE"

echo "=========================================="
echo "Téléchargement et analyse des logs"
echo "=========================================="
echo ""

# Vérifier la connexion SSH
echo "[1/4] Vérification de la connexion SSH..."
if ! ssh -o ConnectTimeout=5 "$USER@$SERVER" "echo 'Connexion OK'" > /dev/null 2>&1; then
    echo "❌ Impossible de se connecter au serveur"
    exit 1
fi
echo "✅ Connexion SSH OK"
echo ""

# Vérifier quels fichiers de logs existent
echo "[2/4] Recherche des fichiers de logs..."
LOG_FILES=$(ssh "$USER@$SERVER" "cd $REMOTE_PATH && find logs logs_server -type f -name '*.log' 2>/dev/null | head -20" || echo "")
if [ -n "$LOG_FILES" ]; then
    echo "   Fichiers trouvés:"
    echo "$LOG_FILES" | while read -r file; do
        echo "     - $file"
    done
else
    echo "   Aucun fichier .log trouvé, recherche de tous les fichiers..."
    ssh "$USER@$SERVER" "cd $REMOTE_PATH && ls -la logs/ logs_server/ 2>/dev/null || echo 'Aucun répertoire de logs trouvé'"
fi
echo ""

# Créer une archive des logs sur le serveur
echo "[3/4] Création d'une archive des logs sur le serveur..."
REMOTE_ARCHIVE="/tmp/prospectlab_logs_$TIMESTAMP.tar.gz"
ssh "$USER@$SERVER" "cd $REMOTE_PATH && (tar -czf $REMOTE_ARCHIVE logs/ logs_server/ 2>/dev/null || tar -czf $REMOTE_ARCHIVE logs/ 2>/dev/null || echo 'Aucun log trouvé')" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    # Télécharger l'archive
    echo "   Téléchargement de l'archive..."
    scp "$USER@$SERVER:$REMOTE_ARCHIVE" "$LOGS_ARCHIVE.tar.gz" > /dev/null 2>&1
    
    if [ -f "$LOGS_ARCHIVE.tar.gz" ]; then
        # Extraire l'archive
        echo "   Extraction de l'archive..."
        tar -xzf "$LOGS_ARCHIVE.tar.gz" -C "$LOGS_ARCHIVE" 2>/dev/null || true
        
        # Nettoyer l'archive locale
        rm -f "$LOGS_ARCHIVE.tar.gz"
        
        # Nettoyer l'archive sur le serveur
        ssh "$USER@$SERVER" "rm -f $REMOTE_ARCHIVE" > /dev/null 2>&1
        
        echo "✅ Logs téléchargés dans: $LOGS_ARCHIVE"
    else
        echo "⚠️ Aucun log téléchargé (fichiers vides ou inexistants)"
    fi
else
    echo "⚠️ Impossible de créer l'archive des logs"
fi
echo ""

# Analyser les logs
echo "[4/4] Analyse des logs..."
ANALYSIS_FILE="$LOGS_ARCHIVE/analysis_$TIMESTAMP.txt"

cat > "$ANALYSIS_FILE" << EOF
========================================
ANALYSE DES LOGS - $(date "+%Y-%m-%d %H:%M:%S")
========================================

EOF

# Trouver tous les fichiers de logs
LOG_FILES_LOCAL=$(find "$LOGS_ARCHIVE" -type f 2>/dev/null || echo "")

if [ -z "$LOG_FILES_LOCAL" ]; then
    echo "Aucun fichier de log trouvé dans l'archive." >> "$ANALYSIS_FILE"
    echo "" >> "$ANALYSIS_FILE"
else
    FILE_COUNT=$(echo "$LOG_FILES_LOCAL" | wc -l)
    echo "Fichiers de logs trouvés: $FILE_COUNT" >> "$ANALYSIS_FILE"
    echo "$LOG_FILES_LOCAL" | while read -r file; do
        REL_PATH="${file#$LOGS_ARCHIVE/}"
        echo "  - $REL_PATH" >> "$ANALYSIS_FILE"
    done
    echo "" >> "$ANALYSIS_FILE"
    
    # Analyser chaque fichier
    echo "$LOG_FILES_LOCAL" | while read -r file; do
        echo "" >> "$ANALYSIS_FILE"
        echo "========================================" >> "$ANALYSIS_FILE"
        echo "FICHIER: $(basename "$file")" >> "$ANALYSIS_FILE"
        echo "========================================" >> "$ANALYSIS_FILE"
        echo "" >> "$ANALYSIS_FILE"
        
        # Statistiques générales
        LINE_COUNT=$(wc -l < "$file" 2>/dev/null || echo "0")
        FILE_SIZE=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
        FILE_SIZE_KB=$((FILE_SIZE / 1024))
        
        echo "Taille: ${FILE_SIZE_KB} KB" >> "$ANALYSIS_FILE"
        echo "Lignes: $LINE_COUNT" >> "$ANALYSIS_FILE"
        echo "" >> "$ANALYSIS_FILE"
        
        if [ "$LINE_COUNT" -gt 0 ]; then
            # Dernières lignes
            echo "--- DERNIÈRES 20 LIGNES ---" >> "$ANALYSIS_FILE"
            tail -n 20 "$file" >> "$ANALYSIS_FILE"
            echo "" >> "$ANALYSIS_FILE"
            
            # Recherche d'erreurs
            ERROR_COUNT=$(grep -i "ERROR\|Exception\|Traceback\|CRITICAL\|Fatal" "$file" 2>/dev/null | wc -l || echo "0")
            if [ "$ERROR_COUNT" -gt 0 ]; then
                echo "--- ERREURS TROUVÉES ($ERROR_COUNT) ---" >> "$ANALYSIS_FILE"
                grep -i "ERROR\|Exception\|Traceback\|CRITICAL\|Fatal" "$file" | head -50 >> "$ANALYSIS_FILE"
                echo "" >> "$ANALYSIS_FILE"
            fi
            
            # Recherche d'avertissements
            WARN_COUNT=$(grep -i "WARNING\|WARN" "$file" 2>/dev/null | wc -l || echo "0")
            if [ "$WARN_COUNT" -gt 0 ]; then
                echo "--- AVERTISSEMENTS TROUVÉS ($WARN_COUNT) ---" >> "$ANALYSIS_FILE"
                grep -i "WARNING\|WARN" "$file" | head -30 >> "$ANALYSIS_FILE"
                echo "" >> "$ANALYSIS_FILE"
            fi
            
            # Recherche de problèmes NaN
            NAN_COUNT=$(grep -i "NaN\|nan\|Not a Number" "$file" 2>/dev/null | wc -l || echo "0")
            if [ "$NAN_COUNT" -gt 0 ]; then
                echo "--- PROBLÈMES NaN TROUVÉS ($NAN_COUNT) ---" >> "$ANALYSIS_FILE"
                grep -i "NaN\|nan\|Not a Number" "$file" >> "$ANALYSIS_FILE"
                echo "" >> "$ANALYSIS_FILE"
            fi
            
            # Recherche de problèmes JSON
            JSON_COUNT=$(grep -i "JSON\|json\|SyntaxError\|ParseError" "$file" 2>/dev/null | wc -l || echo "0")
            if [ "$JSON_COUNT" -gt 0 ]; then
                echo "--- PROBLÈMES JSON TROUVÉS ($JSON_COUNT) ---" >> "$ANALYSIS_FILE"
                grep -i "JSON\|json\|SyntaxError\|ParseError" "$file" >> "$ANALYSIS_FILE"
                echo "" >> "$ANALYSIS_FILE"
            fi
            
            # Statistiques
            INFO_COUNT=$(grep -i "INFO" "$file" 2>/dev/null | wc -l || echo "0")
            DEBUG_COUNT=$(grep -i "DEBUG" "$file" 2>/dev/null | wc -l || echo "0")
            
            echo "--- STATISTIQUES ---" >> "$ANALYSIS_FILE"
            echo "Erreurs: $ERROR_COUNT" >> "$ANALYSIS_FILE"
            echo "Avertissements: $WARN_COUNT" >> "$ANALYSIS_FILE"
            echo "Infos: $INFO_COUNT" >> "$ANALYSIS_FILE"
            echo "Debug: $DEBUG_COUNT" >> "$ANALYSIS_FILE"
            echo "" >> "$ANALYSIS_FILE"
        fi
    done
fi

echo "✅ Analyse terminée"
echo ""
echo "Résultats:"
echo "  Logs: $LOGS_ARCHIVE"
echo "  Analyse: $ANALYSIS_FILE"
echo ""

# Afficher un résumé
echo "--- RÉSUMÉ DE L'ANALYSE ---"
head -50 "$ANALYSIS_FILE"

echo ""
echo "Pour voir l'analyse complète:"
echo "  cat \"$ANALYSIS_FILE\""
