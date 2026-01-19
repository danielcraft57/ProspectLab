# Scripts ProspectLab

Ce dossier contient tous les scripts utilitaires pour ProspectLab, organisés par plateforme.

## Structure

```
scripts/
├── windows/          # Scripts PowerShell pour Windows
├── linux/            # Scripts Bash pour Linux/WSL
└── README.md         # Ce fichier
```

## Scripts Windows (PowerShell)

### Redis

#### `start-redis.ps1` - Démarre Redis avec Docker
Démarre Redis dans un conteneur Docker.

**Prérequis :**
- Docker Desktop installé et démarré

**Utilisation :**
```powershell
.\scripts\windows\start-redis.ps1
```

#### `stop-redis.ps1` - Arrête Redis (Docker)
Arrête le conteneur Redis Docker.

**Utilisation :**
```powershell
.\scripts\windows\stop-redis.ps1
```

#### `start-redis-wsl.ps1` - Démarre Redis dans WSL
Installe et démarre Redis dans WSL Ubuntu.

**Prérequis :**
- WSL installé avec Ubuntu

**Utilisation :**
```powershell
.\scripts\windows\start-redis-wsl.ps1
```

#### `stop-redis-wsl.ps1` - Arrête Redis (WSL)
Arrête Redis dans WSL Ubuntu.

**Utilisation :**
```powershell
.\scripts\windows\stop-redis-wsl.ps1
```

### Celery

#### `start-celery.ps1` - Démarre Celery (worker + beat)
Démarre le worker Celery ET le scheduler Celery Beat dans un seul processus pour exécuter les tâches asynchrones et les tâches périodiques (comme le nettoyage automatique).

**Prérequis :**
- Redis démarré
- Environnement conda prospectlab activé

**Utilisation :**
```powershell
.\scripts\windows\start-celery.ps1
```

**Note :** Ce script lance à la fois le worker Celery et Celery Beat pour gérer les tâches périodiques (nettoyage automatique toutes les heures).

#### `stop-celery.ps1` - Arrête Celery
Arrête tous les processus Celery (worker et beat).

**Utilisation :**
```powershell
.\scripts\windows\stop-celery.ps1
```

#### `check-celery.ps1` - Vérifie l'état de Celery
Affiche l'état des processus Celery (worker et beat) et les tâches en cours.

**Utilisation :**
```powershell
.\scripts\windows\check-celery.ps1
```

### Tests

#### `test-wsl-tools.ps1` - Teste les outils OSINT et Pentest
Vérifie la disponibilité des outils OSINT et Pentest dans WSL kali-linux.

**Prérequis :**
- WSL installé avec kali-linux

**Utilisation :**
```powershell
.\scripts\windows\test-wsl-tools.ps1
```

**Résultat :**
Affiche la liste des outils disponibles et non disponibles.

#### `test_celery_tasks.py` - Teste l'enregistrement des tâches Celery
Vérifie que toutes les tâches Celery sont correctement enregistrées.

**Prérequis :**
- Environnement conda prospectlab activé

**Utilisation :**
```bash
python scripts/test_celery_tasks.py
```

**Résultat :**
Affiche la liste de toutes les tâches enregistrées et vérifie les tâches principales.

#### `test_redis_connection.py` - Teste la connexion Redis et Celery
Vérifie que Redis est accessible et que Celery peut s'y connecter.

**Prérequis :**
- Redis démarré
- Environnement conda prospectlab activé

**Utilisation :**
```bash
python scripts/test_redis_connection.py
```

**Résultat :**
Affiche les informations de configuration Redis, teste la connexion et vérifie les workers Celery actifs.

### Nettoyage

#### `clear_db.py` - Nettoie la base de données
Vide toutes les tables de la base de données ou uniquement certaines tables spécifiques.

**Emplacement :** `scripts/clear_db.py`

**Utilisation :**
```bash
# Afficher les statistiques
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

#### `clear_redis.py` - Nettoie Redis
Vide toutes les données Celery dans Redis (broker et backend).

**Emplacement :** `scripts/clear_redis.py`

**Prérequis :**
- Redis démarré

**Utilisation :**
```bash
python scripts/clear_redis.py
```

**Avec PowerShell (wrapper) :**
```powershell
.\scripts\windows\clear-redis.ps1
```

## Scripts Linux/WSL (Bash)

### Installation d'outils (Linux)

- `scripts/linux/install_osint_tools_kali.sh` : OSINT pour Kali (WSL ou natif)
- `scripts/linux/install_osint_tools_bookworm.sh` : OSINT pour Debian Bookworm / RPi
- `scripts/linux/install_pentest_tools_kali.sh` : Pentest pour Kali (WSL ou natif)
- `scripts/linux/install_pentest_tools_bookworm.sh` : Pentest pour Debian Bookworm / RPi

**Exemple (Kali WSL) :**
```bash
wsl -d kali-linux
sudo bash scripts/linux/install_osint_tools_kali.sh
sudo bash scripts/linux/install_pentest_tools_kali.sh
```

**Exemple (Debian/RPi) :**
```bash
bash scripts/linux/install_osint_tools_bookworm.sh
bash scripts/linux/install_pentest_tools_bookworm.sh
```

**Avertissement :**
Les outils Pentest sont à utiliser uniquement sur des cibles autorisées (autorisation écrite).

### Services (Linux)

- `scripts/linux/start-redis.sh` / `stop-redis.sh` (systemd)
- `scripts/linux/start-redis-wsl.sh` / `stop-redis-wsl.sh` (fallback daemonize si pas de systemd)
- `scripts/linux/start-celery.sh` (worker + beat via `run_celery.py`)
- `scripts/linux/start-celery-beat.sh` (beat seul)
- `scripts/linux/stop-celery.sh` (pkill des process celery/run_celery.py)
- `scripts/linux/check-celery.sh` (statut des workers)

### Nettoyage (Linux)

- `scripts/linux/clear-logs.sh` : supprime `logs/*.log`
- `scripts/linux/clear-db.sh` : supprime `prospectlab.db`
- `scripts/linux/clear-redis.sh` : `redis-cli FLUSHALL`
- `scripts/linux/clear-all.sh` : enchaîne logs + DB + Redis

## Notes importantes

### Redis

ProspectLab nécessite Redis pour fonctionner avec Celery. Tu peux utiliser soit :
- **Docker** : Plus simple si Docker Desktop est installé
- **WSL** : Alternative si Docker n'est pas disponible

### WSL

Les scripts WSL utilisent les variables de configuration depuis `config.py` :
- `WSL_DISTRO` : Distribution WSL à utiliser (défaut: kali-linux)
- `WSL_USER` : Utilisateur WSL (défaut: loupix)

### Permissions

Pour exécuter les scripts PowerShell, tu peux avoir besoin d'autoriser l'exécution :
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Pour les scripts bash, assure-toi qu'ils sont exécutables :
```bash
chmod +x scripts/linux/*.sh
```

## Dépannage

### Redis ne démarre pas

1. **Docker** : Vérifie que Docker Desktop est démarré
2. **WSL** : Vérifie que WSL est installé et que Ubuntu est disponible
3. Vérifie les logs avec `docker logs prospectlab-redis` ou `wsl -d Ubuntu -e bash -c "sudo service redis-server status"`

### Les outils WSL ne sont pas détectés

1. Vérifie que kali-linux est installé : `wsl --list`
2. Teste manuellement : `wsl -d kali-linux nmap --version`
3. Lance le script de test : `.\scripts\windows\test-wsl-tools.ps1`

### Erreurs de permissions

- **PowerShell** : Exécute en tant qu'administrateur ou ajuste la politique d'exécution
- **Bash** : Utilise `sudo` pour les scripts d'installation

