#!/usr/bin/env bash

# Installation complète de ProspectLab en production sur Raspberry Pi 5
# Exécution: bash scripts/linux/install_production_complete.sh

set -e

echo "=========================================="
echo "Installation complète ProspectLab en PROD"
echo "=========================================="
echo ""

# Variables
PROJECT_DIR="/opt/prospectlab"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_USER="pi"

echo "[*] Étape 1/7: Installation Redis avec plugins..."

# Installation Redis
if ! command -v redis-server &> /dev/null; then
    echo "[*] Installation Redis..."
    sudo apt-get update
    sudo apt-get install -y redis-server redis-tools
else
    echo "[✓] Redis déjà installé"
fi

# Configuration Redis optimisée pour RPi 5
REDIS_CONF="/etc/redis/redis.conf"
if [ -f "$REDIS_CONF" ]; then
    echo "[*] Configuration Redis optimisée pour RPi 5..."
    
    # Backup
    sudo cp "$REDIS_CONF" "${REDIS_CONF}.backup"
    
    # Optimisations mémoire (4GB RAM)
    sudo sed -i 's/^# maxmemory <bytes>/maxmemory 512mb/' "$REDIS_CONF"
    sudo sed -i 's/^# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' "$REDIS_CONF"
    
    # Persistance optimisée
    sudo sed -i 's/^save 900 1/save 300 10/' "$REDIS_CONF"
    sudo sed -i 's/^save 300 10/save 60 1000/' "$REDIS_CONF"
    
    # Compression
    sudo sed -i 's/^# list-compress-depth 0/list-compress-depth 1/' "$REDIS_CONF"
    
    # Timeout pour éviter les connexions zombies
    sudo sed -i 's/^# timeout 0/timeout 300/' "$REDIS_CONF"
    
    echo "[✓] Configuration Redis appliquée"
fi

# Démarrer et activer Redis
sudo systemctl restart redis-server
sudo systemctl enable redis-server

if sudo systemctl is-active --quiet redis-server; then
    echo "[✓] Redis est actif"
else
    echo "[!] Erreur: Redis n'est pas actif"
    exit 1
fi

# Vérifier la connexion Redis
if redis-cli ping | grep -q PONG; then
    echo "[✓] Redis répond correctement"
else
    echo "[!] Erreur: Redis ne répond pas"
    exit 1
fi

echo ""
echo "[*] Étape 2/7: Installation des dépendances système..."

# Installation des dépendances système nécessaires
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    pkg-config

echo "[✓] Dépendances système installées"

echo ""
echo "[*] Étape 3/7: Création de l'environnement virtuel Python..."

cd "$PROJECT_DIR"

# Créer le venv s'il n'existe pas
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "[✓] Environnement virtuel créé"
else
    echo "[✓] Environnement virtuel existe déjà"
fi

# Activer le venv
source "$VENV_DIR/bin/activate"

# Mettre à jour pip
pip install --upgrade pip setuptools wheel

echo "[✓] Environnement virtuel configuré"

echo ""
echo "[*] Étape 4/7: Installation des dépendances Python..."

# Installer les dépendances
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip install -r "$PROJECT_DIR/requirements.txt"
    echo "[✓] Dépendances Python installées"
else
    echo "[!] Erreur: requirements.txt introuvable"
    exit 1
fi

echo ""
echo "[*] Étape 5/7: Vérification de la connexion PostgreSQL..."

# Vérifier que le .env existe
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "[!] Erreur: fichier .env introuvable"
    exit 1
fi

# Charger les variables d'environnement (méthode plus sûre)
set -a
source "$PROJECT_DIR/.env" 2>/dev/null || true
set +a

# Tester la connexion PostgreSQL
python3 << EOF
import os
import sys
from dotenv import load_dotenv

load_dotenv('$PROJECT_DIR/.env')

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    print("[!] Erreur: DATABASE_URL non défini dans .env")
    sys.exit(1)

if database_url.startswith('postgresql://'):
    try:
        import psycopg2
        from urllib.parse import urlparse
        
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:] if parsed.path.startswith('/') else parsed.path
        )
        cursor = conn.cursor()
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        print(f"[✓] Connexion PostgreSQL réussie: {version[:50]}...")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[!] Erreur de connexion PostgreSQL: {e}")
        sys.exit(1)
else:
    print("[!] DATABASE_URL ne pointe pas vers PostgreSQL")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "[!] Erreur lors de la vérification PostgreSQL"
    exit 1
fi

echo ""
echo "[*] Étape 6/7: Initialisation du schéma de base de données..."

# Initialiser le schéma
python3 << EOF
import os
import sys
from dotenv import load_dotenv

# Ajouter le projet au path
sys.path.insert(0, '$PROJECT_DIR')

load_dotenv('$PROJECT_DIR/.env')

try:
    from services.database import Database
    
    print("[*] Création des tables...")
    db = Database()
    print("[✓] Schéma de base de données initialisé avec succès")
    
    # Vérifier quelques tables
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Détecter le type de base de données
    try:
        if hasattr(db, 'is_postgresql') and db.is_postgresql():
            cursor.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                ORDER BY tablename
            """)
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    except:
        # Fallback: essayer PostgreSQL d'abord
        try:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        except:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    
    tables = [row[0] for row in cursor.fetchall()]
    print(f"[✓] {len(tables)} tables créées")
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"[!] Erreur lors de l'initialisation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "[!] Erreur lors de l'initialisation du schéma"
    exit 1
fi

echo ""
echo "[*] Étape 7/7: Création des services systemd..."

# Créer le service Flask/Gunicorn
sudo tee /etc/systemd/system/prospectlab.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=ProspectLab Flask Application
After=network.target postgresql.service redis-server.service

[Service]
Type=notify
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment="PATH=/opt/prospectlab/venv/bin"
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/venv/bin/gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 --timeout 120 --access-logfile /opt/prospectlab/logs/gunicorn_access.log --error-logfile /opt/prospectlab/logs/gunicorn_error.log app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Créer le service Celery Worker
sudo tee /etc/systemd/system/prospectlab-celery.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=ProspectLab Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=forking
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment="PATH=/opt/prospectlab/venv/bin"
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/scripts/linux/start_celery_worker.sh
ExecStop=/bin/kill -s TERM `cat /opt/prospectlab/celery_worker.pid 2>/dev/null` || true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Créer le service Celery Beat
sudo tee /etc/systemd/system/prospectlab-celerybeat.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=ProspectLab Celery Beat Scheduler
After=network.target postgresql.service redis-server.service

[Service]
Type=forking
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment="PATH=/opt/prospectlab/venv/bin"
ExecStart=/opt/prospectlab/venv/bin/celery -A celery_app beat --loglevel=info --logfile=/opt/prospectlab/logs/celery_beat.log --pidfile=/opt/prospectlab/celery_beat.pid --detach
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Créer le dossier logs s'il n'existe pas
mkdir -p "$PROJECT_DIR/logs"

# Rendre le script wrapper exécutable
chmod +x "$PROJECT_DIR/scripts/linux/start_celery_worker.sh"

# Recharger systemd
sudo systemctl daemon-reload

echo "[✓] Services systemd créés"

echo ""
echo "=========================================="
echo "Installation terminée avec succès !"
echo "=========================================="
echo ""
echo "Services créés:"
echo "  - prospectlab.service (Flask/Gunicorn)"
echo "  - prospectlab-celery.service (Celery Worker)"
echo "  - prospectlab-celerybeat.service (Celery Beat)"
echo ""
echo "Pour démarrer les services:"
echo "  sudo systemctl start prospectlab"
echo "  sudo systemctl start prospectlab-celery"
echo "  sudo systemctl start prospectlab-celerybeat"
echo ""
echo "Pour activer au démarrage:"
echo "  sudo systemctl enable prospectlab"
echo "  sudo systemctl enable prospectlab-celery"
echo "  sudo systemctl enable prospectlab-celerybeat"
echo ""
echo "Pour voir les logs:"
echo "  sudo journalctl -u prospectlab -f"
echo "  sudo journalctl -u prospectlab-celery -f"
echo "  sudo journalctl -u prospectlab-celerybeat -f"
echo ""
echo "L'application sera accessible sur: http://node15.lan:5000"
echo "=========================================="

