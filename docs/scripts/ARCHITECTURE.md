# Architecture des Scripts

Ce document décrit l'architecture et l'organisation des scripts utilitaires de ProspectLab.

## Structure des dossiers

```
scripts/
├── windows/              # Scripts PowerShell pour Windows
│   ├── start-redis.ps1
│   ├── stop-redis.ps1
│   ├── start-redis-wsl.ps1
│   ├── stop-redis-wsl.ps1
│   └── test-wsl-tools.ps1
├── linux/                # Scripts Bash pour Linux/WSL
│   ├── install_osint_tools.sh
│   └── install_pentest_tools.sh
└── README.md             # Documentation principale
```

## Organisation par plateforme

### Windows (PowerShell)

Les scripts PowerShell sont organisés par fonctionnalité :

**Redis :**
- `start-redis.ps1` : Démarre Redis avec Docker
- `stop-redis.ps1` : Arrête Redis (Docker)
- `start-redis-wsl.ps1` : Démarre Redis dans WSL
- `stop-redis-wsl.ps1` : Arrête Redis (WSL)

**Tests :**
- `test-wsl-tools.ps1` : Teste la disponibilité des outils WSL

### Linux/WSL (Bash)

Les scripts Bash sont organisés par type d'outils :

**Installation :**
- `install_osint_tools.sh` : Installe les outils OSINT
- `install_pentest_tools.sh` : Installe les outils de Pentest

## Principes de conception

### Scripts PowerShell

1. **Gestion d'erreurs** : Utilisation de try/catch pour gérer les erreurs
2. **Messages utilisateur** : Messages colorés et informatifs
3. **Vérifications** : Vérification des prérequis avant exécution
4. **Configuration** : Utilisation des variables depuis `config.py`

### Scripts Bash

1. **Vérification d'environnement** : Vérifie que l'environnement est correct (Kali Linux)
2. **Gestion des erreurs** : Arrêt propre en cas d'erreur
3. **Messages clairs** : Affichage de la progression et des erreurs
4. **Installation atomique** : Installation complète ou échec propre

## Flux d'exécution

### Démarrage de Redis (Docker)

```
start-redis.ps1
  ├─> Vérifie Docker Desktop
  ├─> Vérifie le conteneur existant
  ├─> Crée/démarre le conteneur
  ├─> Attend que Redis soit prêt
  └─> Teste la connexion (PING)
```

### Démarrage de Redis (WSL)

```
start-redis-wsl.ps1
  ├─> Vérifie WSL
  ├─> Vérifie l'installation de Redis
  ├─> Installe Redis si nécessaire
  ├─> Démarre le service Redis
  └─> Teste la connexion (PING)
```

### Installation des outils OSINT

```
install_osint_tools.sh
  ├─> Vérifie l'environnement (Kali Linux)
  ├─> Met à jour le système
  ├─> Installe les dépendances
  ├─> Installe chaque outil
  └─> Vérifie l'installation
```

## Intégration avec l'application

Les scripts sont utilisés par :

1. **Configuration initiale** : Installation des dépendances
2. **Démarrage de l'application** : Démarrage de Redis avant Celery
3. **Tests** : Vérification de la disponibilité des outils
4. **Maintenance** : Installation/mise à jour des outils

## Configuration

Les scripts utilisent la configuration depuis `config.py` :

- `WSL_DISTRO` : Distribution WSL (défaut: `kali-linux`)
- `WSL_USER` : Utilisateur WSL (défaut: `loupix`)

Ces valeurs peuvent être surchargées dans `.env`.

## Extensibilité

Pour ajouter un nouveau script :

1. **Place-le dans le bon dossier** : `windows/` ou `linux/`
2. **Suis les conventions** :
   - Noms en minuscules avec tirets
   - Gestion d'erreurs appropriée
   - Messages utilisateur clairs
3. **Documente-le** : Ajoute la documentation dans `README.md`
4. **Teste-le** : Vérifie sur un environnement propre

## Maintenance

### Mise à jour

Les scripts sont versionnés avec le projet. Pour mettre à jour :
1. Récupère la dernière version
2. Vérifie les changements dans `README.md`
3. Relance les scripts d'installation si nécessaire

### Tests

Pour tester les scripts :
- **PowerShell** : Exécute-les dans un terminal PowerShell
- **Bash** : Exécute-les dans WSL ou Linux

### Logs

Les scripts affichent leurs messages directement dans la console. Pour les logs Docker :
```powershell
docker logs prospectlab-redis
```

Pour les logs WSL :
```bash
wsl -d Ubuntu -e bash -c "sudo journalctl -u redis-server"
```

