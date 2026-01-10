# Documentation des Scripts

Cette documentation détaille l'utilisation et la maintenance des scripts utilitaires de ProspectLab.

## Vue d'ensemble

Les scripts sont organisés par plateforme dans le dossier `scripts/` :
- **Windows** : Scripts PowerShell (.ps1) pour la gestion de Redis et les tests
- **Linux** : Scripts Bash (.sh) pour l'installation des outils OSINT et Pentest

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

Le script `install_osint_tools.sh` installe tous les outils OSINT nécessaires pour ProspectLab.

**Outils installés :**
- **dnsrecon** : Reconnaissance DNS
- **theHarvester** : Collecte d'informations publiques
- **sublist3r** : Découverte de sous-domaines
- **amass** : Cartographie de surface d'attaque
- **whatweb** : Identification de technologies web
- **sslscan** : Analyse SSL/TLS
- **sherlock** : Recherche de comptes sociaux
- **maigret** : Recherche OSINT avancée

**Utilisation :**
```bash
# Dans WSL kali-linux
wsl -d kali-linux
sudo bash scripts/linux/install_osint_tools.sh
```

**Durée :** Environ 10-15 minutes selon la connexion internet.

### Installation des outils de Pentest

Le script `install_pentest_tools.sh` installe tous les outils de Pentest nécessaires.

**Outils installés :**
- **sqlmap** : Détection d'injections SQL
- **wpscan** : Scan de sécurité WordPress
- **nikto** : Scanner de vulnérabilités web
- **wapiti** : Scanner de sécurité web
- **nmap** : Scanner de ports et services
- **sslscan** : Analyse SSL/TLS

**Avertissement légal :**
Ces outils sont destinés uniquement à des tests autorisés. Utilisez-les uniquement sur des systèmes pour lesquels vous avez une autorisation écrite explicite.

**Utilisation :**
```bash
# Dans WSL kali-linux
wsl -d kali-linux
sudo bash scripts/linux/install_pentest_tools.sh
```

**Durée :** Environ 15-20 minutes selon la connexion internet.

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

