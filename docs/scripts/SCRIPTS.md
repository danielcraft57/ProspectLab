# Documentation des Scripts

Cette documentation détaille l'utilisation et la maintenance des scripts utilitaires de ProspectLab.

## Vue d'ensemble

Les scripts sont organisés par plateforme dans le dossier `scripts/` :
- **Windows** : Scripts PowerShell (.ps1) pour la gestion de Redis/Celery et les tests
- **Linux** : Scripts Bash (.sh) pour l'installation (OSINT/Pentest) et la gestion Redis/Celery/maintenance

## Scripts Windows

### Gestion de Redis

Redis est nécessaire pour le fonctionnement de Celery, qui gère les tâches asynchrones de ProspectLab.

#### Méthode 1 : Docker (recommandé)

**Avantages :**
- Installation simple
- Isolation des dépendances
- Facile à démarrer/arrêter

**Scripts :**
- `scripts/windows/start-redis.ps1` : Démarre Redis dans Docker
- `scripts/windows/stop-redis.ps1` : Arrête Redis

**Prérequis :**
- Docker Desktop installé et démarré

**Utilisation :**
```powershell
# Démarrer Redis
.\scripts\windows\start-redis.ps1

# Arrêter Redis
.\scripts\windows\stop-redis.ps1
```

#### Méthode 2 : WSL

**Avantages :**
- Fonctionne sans Docker
- Utilise les ressources système directement

**Scripts :**
- `scripts/windows/start-redis-wsl.ps1` : Installe et démarre Redis dans WSL Ubuntu
- `scripts/windows/stop-redis-wsl.ps1` : Arrête Redis dans WSL

**Prérequis :**
- WSL installé avec Ubuntu

**Utilisation :**
```powershell
# Démarrer Redis (installe automatiquement si nécessaire)
.\scripts\windows\start-redis-wsl.ps1

# Arrêter Redis
.\scripts\windows\stop-redis-wsl.ps1
```

### Tests des outils WSL

Le script `test-wsl-tools.ps1` vérifie la disponibilité des outils OSINT et Pentest dans WSL kali-linux.

**Utilisation :**
```powershell
.\scripts\windows\test-wsl-tools.ps1
```

**Résultat :**
Affiche un rapport détaillé des outils disponibles et non disponibles, organisé par catégorie (OSINT / Pentest).

## Scripts Linux/WSL

### Installation des outils OSINT

- `scripts/linux/install_osint_tools_kali.sh` : installation OSINT sous Kali (WSL ou natif)
- `scripts/linux/install_osint_tools_bookworm.sh` : installation OSINT sous Debian Bookworm / RPi

**Outils installés :**
- **dnsrecon** : Reconnaissance DNS
- **theHarvester** : Collecte d'informations publiques
- **sublist3r** : Découverte de sous-domaines
- **amass** : Cartographie de surface d'attaque
- **whatweb** : Identification de technologies web
- **sslscan** : Analyse SSL/TLS
- **sherlock** : Recherche de comptes sociaux
- **maigret** : Recherche OSINT avancée

**Utilisation (Kali WSL) :**
```bash
wsl -d kali-linux
sudo bash scripts/linux/install_osint_tools_kali.sh
```

**Utilisation (Debian/RPi) :**
```bash
bash scripts/linux/install_osint_tools_bookworm.sh
```

### Installation des outils de Pentest

- `scripts/linux/install_pentest_tools_kali.sh` : installation Pentest sous Kali (WSL ou natif)
- `scripts/linux/install_pentest_tools_bookworm.sh` : installation Pentest sous Debian Bookworm / RPi

**Outils installés :**
- **sqlmap** : Détection d'injections SQL
- **wpscan** : Scan de sécurité WordPress
- **nikto** : Scanner de vulnérabilités web
- **wapiti** : Scanner de sécurité web
- **nmap** : Scanner de ports et services
- **sslscan** : Analyse SSL/TLS

**Avertissement légal :**
Ces outils sont destinés uniquement à des tests autorisés. Utilisez-les uniquement sur des systèmes pour lesquels vous avez une autorisation écrite explicite.

**Utilisation (Kali WSL) :**
```bash
wsl -d kali-linux
sudo bash scripts/linux/install_pentest_tools_kali.sh
```

**Utilisation (Debian/RPi) :**
```bash
bash scripts/linux/install_pentest_tools_bookworm.sh
```

**Durée indicative :** 10-20 minutes selon la connexion et la machine.

### Gestion Redis/Celery (Linux)

- `scripts/linux/start-redis.sh` / `stop-redis.sh` : via systemd
- `scripts/linux/start-redis-wsl.sh` / `stop-redis-wsl.sh` : fallback daemonize (si pas de systemd)
- `scripts/linux/start-celery.sh` : worker + beat via `run_celery.py`
- `scripts/linux/start-celery-beat.sh` : beat seul
- `scripts/linux/stop-celery.sh` : stoppe worker/beat (pkill)
- `scripts/linux/check-celery.sh` : `celery -A celery_app status`

### Nettoyage (Linux)

- `scripts/linux/clear-logs.sh` : supprime `logs/*.log`
- `scripts/linux/clear-db.sh` : supprime `prospectlab.db`
- `scripts/linux/clear-redis.sh` : `redis-cli FLUSHALL`
- `scripts/linux/clear-all.sh` : enchaîne logs + DB + Redis

### Scripts de nettoyage

#### `clear_db.py` - Nettoyage de la base de données

Script Python pour vider la base de données SQLite, soit complètement, soit certaines tables spécifiques.

**Emplacement :** `scripts/clear_db.py`

**Utilisation :**
```bash
# Afficher les statistiques de la base de données
python scripts/clear_db.py

# Vider toutes les tables (avec confirmation)
python scripts/clear_db.py --clear

# Vider toutes les tables (sans confirmation)
python scripts/clear_db.py --clear --no-confirm

# Vider uniquement certaines tables
python scripts/clear_db.py --clear --tables entreprises analyses
```

**Avec PowerShell (wrapper) :**
```powershell
.\scripts\windows\clear-db.ps1 -Clear
.\scripts\windows\clear-db.ps1 -Clear -NoConfirm
```

**Note :** Le script PowerShell active automatiquement l'environnement conda `prospectlab` et exécute le script Python directement.

#### `clear_redis.py` - Nettoyage de Redis

Script Python pour vider toutes les données Celery dans Redis (broker et backend).

**Emplacement :** `scripts/clear_redis.py`

**Prérequis :**
- Redis démarré
- Environnement conda prospectlab activé

**Utilisation :**
```bash
python scripts/clear_redis.py
```

**Avec PowerShell (wrapper) :**
```powershell
.\scripts\windows\clear-redis.ps1
```

**Avertissement :** Cette opération supprime toutes les tâches en attente et les résultats en cache dans Redis.

### Scripts de test

#### `test_celery_tasks.py` - Test des tâches Celery

Vérifie que toutes les tâches Celery sont correctement enregistrées.

**Emplacement :** `scripts/test_celery_tasks.py`

**Utilisation :**
```bash
python scripts/test_celery_tasks.py
```

**Résultat :** Affiche la liste de toutes les tâches enregistrées et vérifie les tâches principales (analysis, scraping, technical_analysis, email, cleanup).

#### `test_redis_connection.py` - Test de la connexion Redis

Vérifie que Redis est accessible et que Celery peut s'y connecter.

**Emplacement :** `scripts/test_redis_connection.py`

**Prérequis :**
- Redis démarré
- Environnement conda prospectlab activé

**Utilisation :**
```bash
python scripts/test_redis_connection.py
```

**Résultat :** Affiche les informations de configuration Redis, teste la connexion et vérifie les workers Celery actifs.

### Déploiement en production

Les scripts de déploiement copient le code (routes, services, tasks, templates, static, utils, scripts) vers un serveur distant et synchronisent explicitement chaque dossier pour éviter les soucis d'archives (tar sous Windows).

- **`deploy_production.ps1`** (Windows) : déploiement complet. Usage : `.\scripts\deploy_production.ps1 [serveur] [utilisateur]` (défaut : voir les paramètres en tête du script). Après le transfert principal, envoi explicite de routes, services, tasks, templates, static, utils, scripts via `scp -r` pour garantir leur présence sur le serveur.
- **`deploy_production.sh`** (Linux/macOS) : même logique. Usage : `./scripts/deploy_production.sh [serveur] [utilisateur] [chemin_distant]`.
- **`sync_templates_static.ps1`** (Windows) : envoie uniquement `templates/` et `static/` sans refaire tout le déploiement. Utile pour une mise à jour rapide du front. Usage : `.\scripts\sync_templates_static.ps1 [serveur] [utilisateur]`.

Le dossier `scripts/` est inclus dans le déploiement ; les permissions d'exécution des `.sh` sont appliquées côté serveur après transfert.

## Configuration

Les scripts utilisent les variables de configuration depuis `config.py` :

- `WSL_DISTRO` : Distribution WSL à utiliser (défaut: `kali-linux`)
- `WSL_USER` : Utilisateur WSL (défaut: `loupix`)

Ces variables peuvent être surchargées dans le fichier `.env`.

## Dépannage

### Redis ne démarre pas

**Problème :** Erreur "Docker Desktop n'est pas démarré"

**Solution :**
1. Démarre Docker Desktop depuis le menu Démarrer
2. Attends que Docker soit complètement démarré (icône stable dans la barre des tâches)
3. Relance le script

**Problème :** Erreur "WSL non disponible"

**Solution :**
1. Installe WSL : `wsl --install`
2. Installe Ubuntu : `wsl --install -d Ubuntu`
3. Relance le script

### Les outils WSL ne sont pas détectés

**Problème :** Les outils OSINT/Pentest ne sont pas trouvés

**Solutions :**
1. Vérifie que kali-linux est installé : `wsl --list`
2. Installe les outils manquants avec les scripts d'installation
3. Vérifie la configuration WSL dans `config.py`

**Problème :** Erreur "Défaillance irrémédiable" avec WSL

**Solutions :**
1. Redémarre WSL : `wsl --shutdown`
2. Vérifie que la distribution est correctement installée
3. Les scripts essaient automatiquement sans utilisateur si ça échoue avec l'utilisateur configuré

### Erreurs de permissions

**PowerShell :**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Bash :**
```bash
chmod +x scripts/linux/*.sh
```

## Maintenance

### Mise à jour des scripts

Les scripts sont versionnés avec le projet. Pour mettre à jour :
1. Récupère la dernière version depuis le dépôt
2. Relance les scripts d'installation si nécessaire

### Vérification de l'état

Pour vérifier l'état de Redis :
```powershell
# Docker
docker ps --filter "name=prospectlab-redis"

# WSL
wsl -d Ubuntu -e bash -c "sudo service redis-server status"
```

Pour tester les outils :
```powershell
.\scripts\windows\test-wsl-tools.ps1
```

## Architecture technique

### Scripts PowerShell

Les scripts PowerShell utilisent :
- `docker-compose` pour la gestion Docker
- `wsl` pour l'interaction avec WSL
- Gestion d'erreurs avec try/catch
- Messages colorés pour une meilleure UX

### Scripts Bash

Les scripts Bash :
- Vérifient l'environnement (Kali Linux)
- Installent les dépendances via `apt-get`
- Gèrent les erreurs et affichent des messages clairs
- Supportent l'interruption (Ctrl+C)

## Contribution

Pour ajouter un nouveau script :

1. Place-le dans le bon dossier (`windows/` ou `linux/`)
2. Ajoute la documentation dans ce fichier
3. Teste-le sur un environnement propre
4. Mets à jour le README principal dans `scripts/README.md`

