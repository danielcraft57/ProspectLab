# Déploiement en production - ProspectLab

Ce document décrit le déploiement complet de ProspectLab en production. **Remplacez les noms de serveurs, domaines et utilisateurs (SERVEUR_APP, SERVEUR_PROXY, UTILISATEUR, etc.) par vos propres valeurs.**

## Architecture de production

```
Internet (HTTPS)
    ↓
<SERVEUR_PROXY> (Nginx + SSL Let's Encrypt)
    ↓ (proxy HTTP interne)
<SERVEUR_APP>:5000 (ProspectLab + Gunicorn)
    ↓
PostgreSQL + Redis + Celery
```

### Composants

- **Serveur proxy** : Nginx avec certificats SSL Let's Encrypt
- **Serveur application** : ProspectLab (Flask + Gunicorn + Celery)
- **PostgreSQL** : Base de données de production
- **Redis** : Broker de messages pour Celery
- **Services systemd** : Gestion automatique des services

## Étape 1 : Préparation du serveur application

### 1.1. Installation des dépendances système et Conda

Conda (Miniconda ou Anaconda) est utilisé pour l'environnement Python en production.

```bash
sudo apt update
sudo apt install -y build-essential libpq-dev libssl-dev libffi-dev pkg-config \
    redis-server postgresql
# Installer Miniconda pour l'utilisateur pi si besoin : https://docs.conda.io/en/latest/miniconda.html
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
sudo chown <UTILISATEUR>:<UTILISATEUR> /opt/prospectlab
cd /opt/prospectlab
# Copier les fichiers du projet ici (via git clone, scp ou le script scripts/deploy_production.ps1 / .sh)
```

Créer l'environnement Conda (préfixe fixe pour systemd) :

```bash
cd /opt/prospectlab
source ~/miniconda3/etc/profile.d/conda.sh   # ou anaconda3
conda create --prefix /opt/prospectlab/env python=3.11 -y
/opt/prospectlab/env/bin/pip install --upgrade pip setuptools wheel
/opt/prospectlab/env/bin/pip install -r requirements.txt
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
BASE_URL=https://<VOTRE_DOMAINE>
RESTRICT_TO_LOCAL_NETWORK=true
```

Générer une SECRET_KEY :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 1.6. Initialisation de la base de données

```bash
cd /opt/prospectlab
/opt/prospectlab/env/bin/python -c "from services.database import Database; db = Database(); db.init_database(); print('Base initialisée')"
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
Environment=PATH=/opt/prospectlab/env/bin
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/env/bin/gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 \
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

Le script `scripts/linux/start_celery_worker.sh` utilise déjà `/opt/prospectlab/env/bin/celery`. Aucune activation manuelle nécessaire.

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
Environment=PATH=/opt/prospectlab/env/bin
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
Environment=PATH=/opt/prospectlab/env/bin
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/env/bin/celery -A celery_app beat \
    --loglevel=info \
    --logfile=/opt/prospectlab/logs/celery_beat.log \
    --pidfile=/opt/prospectlab/celery_beat.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2.4. Mise à jour des services (passage venv → Conda)

Si les services pointaient encore vers `venv`, exécuter une fois sur le serveur :

```bash
cd /opt/prospectlab
sudo bash scripts/linux/update_services_to_conda.sh --restart
```

Ce script réécrit les unités systemd avec les chemins `/opt/prospectlab/env` et recharge systemd. Le déploiement (`deploy_production.sh` / `.ps1`) l’appelle automatiquement à chaque déploiement.

### 2.5. Activation des services

```bash
sudo systemctl daemon-reload
sudo systemctl enable prospectlab prospectlab-celery prospectlab-celerybeat
sudo systemctl start prospectlab prospectlab-celery prospectlab-celerybeat
```

Vérifier le statut :

```bash
sudo systemctl status prospectlab prospectlab-celery prospectlab-celerybeat
```

## Étape 3 : Configuration du reverse proxy sur <SERVEUR_PROXY>

### 3.1. Installation de Nginx

```bash
sudo apt update
sudo apt install -y nginx
```

### 3.2. Configuration Nginx

Créer `/etc/nginx/sites-available/<VOTRE_DOMAINE>` :

```nginx
server {
    listen 80;
    server_name <VOTRE_DOMAINE>;

    location / {
        proxy_pass http://<SERVEUR_APP>:5000;
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
    server_name <AUTRE_DOMAINE_OPTIONNEL>;

    location / {
        proxy_pass http://<SERVEUR_APP>:5000;
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
sudo ln -sf /etc/nginx/sites-available/<VOTRE_DOMAINE> /etc/nginx/sites-enabled/
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
    -d <VOTRE_DOMAINE> \
    -d <AUTRE_DOMAINE_OPTIONNEL> \
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

Sur <SERVEUR_APP> :

```bash
# Vérifier les services
sudo systemctl status prospectlab prospectlab-celery prospectlab-celerybeat

# Vérifier les processus
ps aux | grep -E '(gunicorn|celery)'

# Tester l'application localement
curl http://localhost:5000
```

### 4.2. Vérification du reverse proxy

Sur <SERVEUR_PROXY> :

```bash
# Tester Nginx
sudo nginx -t
sudo systemctl status nginx

# Tester la connexion vers <SERVEUR_APP> (depuis le LAN / VPN)
curl http://<SERVEUR_APP>:5000

# Tester HTTPS
curl -I https://<VOTRE_DOMAINE>
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
/opt/prospectlab/env/bin/pip install -r requirements.txt
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
ping <SERVEUR_APP>
```

### Problème : Erreur 502 Bad Gateway (Nginx sur SERVEUR_PROXY, app sur SERVEUR_APP)

Une 502 signifie que Nginx ne peut pas joindre l’application. Vérifications dans l’ordre :

**1. Sur le serveur application (SERVEUR_APP) : l’app écoute bien sur toutes les interfaces**

```bash
# Vérifier que Gunicorn écoute sur 0.0.0.0:5000 (pas seulement 127.0.0.1)
ss -tlnp | grep 5000
# Attendu : 0.0.0.0:5000

# Vérifier le service et les logs
sudo systemctl status prospectlab
sudo journalctl -u prospectlab -n 30
```

Le service systemd doit lancer Gunicorn avec `-b 0.0.0.0:5000`. Si vous voyez `127.0.0.1:5000`, corrigez le fichier `/etc/systemd/system/prospectlab.service` (voir section 2.1 de ce document) puis `sudo systemctl daemon-reload && sudo systemctl restart prospectlab`.

**2. Depuis le serveur proxy (SERVEUR_PROXY) : résolution et connectivité vers SERVEUR_APP**

```bash
# Sur le serveur proxy : résolution du nom du serveur app
ping -c 1 SERVEUR_APP
getent hosts SERVEUR_APP

# Si le nom ne se résout pas, ajoutez dans /etc/hosts (sur le serveur proxy) :
# IP_SERVEUR_APP  SERVEUR_APP

# Test direct vers l'app (depuis le serveur proxy)
curl -I http://SERVEUR_APP:5000/
```

**3. Pare-feu sur SERVEUR_APP**

Le port 5000 doit être accepté depuis le serveur proxy (ou depuis tout le LAN). Exemple avec ufw :

```bash
# Sur le serveur application
sudo ufw allow from IP_SERVEUR_PROXY to any port 5000
# ou pour tout le réseau local
sudo ufw allow from 192.168.0.0/16 to any port 5000
sudo ufw reload
```

**4. Configuration Nginx sur SERVEUR_PROXY**

`proxy_pass` doit pointer vers l’hôte et le port de l’app (ex. `http://SERVEUR_APP:5000`). Timeouts suffisants pour les longues requêtes :

```nginx
location / {
    proxy_pass http://SERVEUR_APP:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}
```

Après toute modification sur le serveur proxy : `sudo nginx -t && sudo systemctl reload nginx`.

**5. Déploiement avec vérification et rechargement Nginx**

Pour vérifier l’app après déploiement et recharger Nginx sur le proxy en une commande (remplacez SERVEUR_APP, UTILISATEUR, SERVEUR_PROXY, UTILISATEUR_PROXY par vos valeurs) :

```bash
# Bash (Linux / WSL)
./scripts/deploy_production.sh SERVEUR_APP UTILISATEUR /opt/prospectlab SERVEUR_PROXY UTILISATEUR_PROXY

# PowerShell (Windows)
.\scripts\deploy_production.ps1 -Server SERVEUR_APP -User UTILISATEUR -RemotePath /opt/prospectlab -ProxyServer SERVEUR_PROXY -ProxyUser UTILISATEUR_PROXY
```

## Résumé de l'architecture finale

- **URLs publiques** :
  - `https://<VOTRE_DOMAINE>`
  - `https://<AUTRE_DOMAINE_OPTIONNEL>`

- **Services actifs** :
  - ProspectLab (Gunicorn + Flask) sur <SERVEUR_APP>:5000
  - Celery Worker (6 workers) sur <SERVEUR_APP>
  - Celery Beat (planificateur) sur <SERVEUR_APP>
  - PostgreSQL sur <SERVEUR_APP>:5432
  - Redis sur <SERVEUR_APP>:6379
  - Nginx (reverse proxy) sur <SERVEUR_PROXY>

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

