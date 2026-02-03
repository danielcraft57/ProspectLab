# Déploiement en production - ProspectLab

Ce document décrit le déploiement complet de ProspectLab en production sur `node15.lan` avec reverse proxy HTTPS sur `node12.lan`.

## Architecture de production

```
Internet (HTTPS)
    ↓
node12.lan (Nginx + SSL Let's Encrypt)
    ↓ (proxy HTTP interne)
node15.lan:5000 (ProspectLab + Gunicorn)
    ↓
PostgreSQL + Redis + Celery
```

### Composants

- **node12.lan** : Reverse proxy Nginx avec certificats SSL Let's Encrypt
- **node15.lan** : Application ProspectLab (Flask + Gunicorn + Celery)
- **PostgreSQL** : Base de données de production
- **Redis** : Broker de messages pour Celery
- **Services systemd** : Gestion automatique des services

## Étape 1 : Préparation de node15.lan

### 1.1. Installation des dépendances système

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential libpq-dev libssl-dev libffi-dev pkg-config \
    redis-server postgresql
```

### 1.2. Configuration PostgreSQL

Créer l'utilisateur et la base de données :

```bash
sudo -u postgres psql << EOF
CREATE USER prospectlab WITH PASSWORD 'ton-mot-de-passe-securise';
CREATE DATABASE prospectlab OWNER prospectlab;
EOF
```

Configurer l'authentification PostgreSQL :

```bash
sudo sed -i '1i host    prospectlab    prospectlab    127.0.0.1/32    md5' /etc/postgresql/17/main/pg_hba.conf
sudo systemctl restart postgresql
```

### 1.3. Configuration Redis

Vérifier que Redis est actif :

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping  # Doit répondre PONG
```

### 1.4. Déploiement de l'application

Cloner ou copier le projet :

```bash
sudo mkdir -p /opt/prospectlab
sudo chown pi:pi /opt/prospectlab
cd /opt/prospectlab
# Copier les fichiers du projet ici (via git clone ou scp)
```

Créer l'environnement virtuel :

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 1.5. Configuration de l'environnement

Créer le fichier `.env` de production :

```bash
cp env.example .env
nano .env
```

Variables essentielles à configurer :

```bash
SECRET_KEY=ta-cle-ultra-secrete-generee-aleatoirement
DATABASE_URL=postgresql://prospectlab:ton-mot-de-passe@localhost:5432/prospectlab
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_WORKERS=6
BASE_URL=https://prospectlab.danielcraft.fr
RESTRICT_TO_LOCAL_NETWORK=true
```

Générer une SECRET_KEY :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 1.6. Initialisation de la base de données

```bash
cd /opt/prospectlab
source venv/bin/activate
python -c "from services.database import Database; db = Database(); db.init_database(); print('Base initialisée')"
```

## Étape 2 : Configuration des services systemd

### 2.1. Service ProspectLab (Gunicorn)

Créer `/etc/systemd/system/prospectlab.service` :

```ini
[Unit]
Description=ProspectLab Flask Application
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment=PATH=/opt/prospectlab/venv/bin
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/venv/bin/gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 \
    --timeout 120 \
    --access-logfile /opt/prospectlab/logs/gunicorn_access.log \
    --error-logfile /opt/prospectlab/logs/gunicorn_error.log \
    app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2.2. Service Celery Worker

Créer le script `/opt/prospectlab/scripts/linux/start_celery_worker.sh` :

```bash
#!/bin/bash
cd /opt/prospectlab
source venv/bin/activate
exec celery -A celery_app worker \
    --loglevel=info \
    --logfile=/opt/prospectlab/logs/celery_worker.log \
    --pidfile=/opt/prospectlab/celery_worker.pid \
    --pool=threads \
    --concurrency=${CELERY_WORKERS:-6}
```

Rendre exécutable :

```bash
chmod +x /opt/prospectlab/scripts/linux/start_celery_worker.sh
```

Créer `/etc/systemd/system/prospectlab-celery.service` :

```ini
[Unit]
Description=ProspectLab Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment=PATH=/opt/prospectlab/venv/bin
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/scripts/linux/start_celery_worker.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2.3. Service Celery Beat

Créer `/etc/systemd/system/prospectlab-celerybeat.service` :

```ini
[Unit]
Description=ProspectLab Celery Beat Scheduler
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment=PATH=/opt/prospectlab/venv/bin
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/venv/bin/celery -A celery_app beat \
    --loglevel=info \
    --logfile=/opt/prospectlab/logs/celery_beat.log \
    --pidfile=/opt/prospectlab/celery_beat.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2.4. Activation des services

```bash
sudo systemctl daemon-reload
sudo systemctl enable prospectlab prospectlab-celery prospectlab-celerybeat
sudo systemctl start prospectlab prospectlab-celery prospectlab-celerybeat
```

Vérifier le statut :

```bash
sudo systemctl status prospectlab prospectlab-celery prospectlab-celerybeat
```

## Étape 3 : Configuration du reverse proxy sur node12.lan

### 3.1. Installation de Nginx

```bash
sudo apt update
sudo apt install -y nginx
```

### 3.2. Configuration Nginx

Créer `/etc/nginx/sites-available/prospectlab.danielcraft.fr` :

```nginx
server {
    listen 80;
    server_name prospectlab.danielcraft.fr;

    location / {
        proxy_pass http://node15.lan:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts pour les longues requêtes (scraping, analyses)
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    access_log /var/log/nginx/prospectlab_access.log;
    error_log /var/log/nginx/prospectlab_error.log;
}

server {
    listen 80;
    server_name campaigns.danielcraft.fr;

    location / {
        proxy_pass http://node15.lan:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    access_log /var/log/nginx/campaigns_access.log;
    error_log /var/log/nginx/campaigns_error.log;
}
```

Augmenter la taille du hash bucket pour les noms de serveurs :

```bash
sudo sed -i '/^http {/a\    server_names_hash_bucket_size 128;' /etc/nginx/nginx.conf
```

Activer le site :

```bash
sudo ln -sf /etc/nginx/sites-available/prospectlab.danielcraft.fr /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3.3. Configuration SSL avec Let's Encrypt

Installer Certbot :

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Obtenir les certificats SSL :

```bash
sudo certbot --nginx \
    -d prospectlab.danielcraft.fr \
    -d campaigns.danielcraft.fr \
    --non-interactive \
    --agree-tos \
    --email ton-email@example.com \
    --redirect
```

Certbot configure automatiquement :
- Les certificats SSL
- La redirection HTTP → HTTPS
- Le renouvellement automatique

Vérifier le renouvellement automatique :

```bash
sudo certbot renew --dry-run
sudo systemctl status certbot.timer
```

## Étape 4 : Vérifications et tests

### 4.1. Vérification des services

Sur node15.lan :

```bash
# Vérifier les services
sudo systemctl status prospectlab prospectlab-celery prospectlab-celerybeat

# Vérifier les processus
ps aux | grep -E '(gunicorn|celery)'

# Tester l'application localement
curl http://localhost:5000
```

### 4.2. Vérification du reverse proxy

Sur node12.lan :

```bash
# Tester Nginx
sudo nginx -t
sudo systemctl status nginx

# Tester la connexion vers node15.lan (depuis le LAN / VPN)
curl http://node15.lan:5000

# Tester HTTPS
curl -I https://prospectlab.danielcraft.fr
```

### 4.3. Vérification des logs

```bash
# Logs ProspectLab
tail -f /opt/prospectlab/logs/gunicorn_error.log
tail -f /opt/prospectlab/logs/prospectlab.log

# Logs Celery
tail -f /opt/prospectlab/logs/celery_worker.log
tail -f /opt/prospectlab/logs/celery_beat.log

# Logs Nginx
tail -f /var/log/nginx/prospectlab_access.log
tail -f /var/log/nginx/prospectlab_error.log

# Logs systemd
sudo journalctl -u prospectlab -f
sudo journalctl -u prospectlab-celery -f
```

## Étape 5 : Maintenance et monitoring

### 5.1. Commandes utiles

Redémarrer les services :

```bash
sudo systemctl restart prospectlab
sudo systemctl restart prospectlab-celery
sudo systemctl restart prospectlab-celerybeat
```

Voir les logs en temps réel :

```bash
sudo journalctl -u prospectlab -f
sudo journalctl -u prospectlab-celery -f
```

Vérifier l'espace disque :

```bash
df -h
du -sh /opt/prospectlab/logs/*
```

### 5.2. Sauvegarde de la base de données

Sauvegarde PostgreSQL :

```bash
sudo -u postgres pg_dump prospectlab > /opt/prospectlab/backup_$(date +%Y%m%d_%H%M%S).sql
```

Restauration :

```bash
sudo -u postgres psql prospectlab < /opt/prospectlab/backup_YYYYMMDD_HHMMSS.sql
```

### 5.3. Mise à jour de l'application

```bash
cd /opt/prospectlab
git pull  # Si utilisation de git
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart prospectlab prospectlab-celery
```

### 5.4. Renouvellement des certificats SSL

Les certificats sont renouvelés automatiquement par Certbot. Vérifier manuellement :

```bash
sudo certbot renew
```

## Dépannage

### Problème : Service ne démarre pas

```bash
# Vérifier les logs
sudo journalctl -u prospectlab -n 50

# Vérifier les permissions
ls -la /opt/prospectlab
sudo chown -R pi:pi /opt/prospectlab

# Vérifier le fichier .env
cat /opt/prospectlab/.env
```

### Problème : Erreur de connexion PostgreSQL

```bash
# Vérifier que PostgreSQL est actif
sudo systemctl status postgresql

# Tester la connexion
sudo -u postgres psql -c "SELECT version();"

# Vérifier pg_hba.conf
sudo cat /etc/postgresql/17/main/pg_hba.conf | grep prospectlab
```

### Problème : Port 5000 déjà utilisé

```bash
# Trouver le processus
sudo lsof -i :5000

# Tuer le processus
sudo pkill -f gunicorn

# Redémarrer le service
sudo systemctl restart prospectlab
```

### Problème : Erreurs Nginx

```bash
# Tester la configuration
sudo nginx -t

# Vérifier les logs
sudo tail -f /var/log/nginx/error.log

# Vérifier la résolution DNS
ping node15.lan
```

## Résumé de l'architecture finale

- **URLs publiques** :
  - `https://prospectlab.danielcraft.fr`
  - `https://campaigns.danielcraft.fr`

- **Services actifs** :
  - ProspectLab (Gunicorn + Flask) sur node15.lan:5000
  - Celery Worker (6 workers) sur node15.lan
  - Celery Beat (planificateur) sur node15.lan
  - PostgreSQL sur node15.lan:5432
  - Redis sur node15.lan:6379
  - Nginx (reverse proxy) sur node12.lan

- **Sécurité** :
  - Certificats SSL Let's Encrypt
  - Redirection HTTP → HTTPS automatique
  - Renouvellement automatique des certificats
  - Authentification PostgreSQL avec mot de passe

- **Monitoring** :
  - Logs centralisés dans `/opt/prospectlab/logs/`
  - Logs Nginx dans `/var/log/nginx/`
  - Logs systemd via `journalctl`

## Notes importantes

1. **BASE_URL** : Doit être configurée en HTTPS dans `.env` pour le tracking des emails
2. **Timeouts** : Nginx est configuré avec des timeouts de 300s pour les longues opérations
3. **Workers Celery** : Ajuster `CELERY_WORKERS` selon les ressources disponibles
4. **Sauvegardes** : Mettre en place des sauvegardes régulières de PostgreSQL
5. **Monitoring** : Surveiller les logs et l'espace disque régulièrement
6. **Restriction réseau** : Avec `RESTRICT_TO_LOCAL_NETWORK=true`, l'interface complète de ProspectLab (pages HTML, routes API internes) n'est accessible que depuis le LAN/VPN.  
   Seules les routes `/track/...` et `/api/public/...` restent exposées à Internet (pour le tracking d'emails et les intégrations externes via token).

