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

## Scripts Linux/WSL (Bash)

### Installation d'outils

#### `install_osint_tools.sh` - Installe les outils OSINT
Installe tous les outils OSINT nécessaires pour ProspectLab dans Kali Linux.

**Prérequis :**
- Kali Linux (WSL ou natif)
- Droits sudo

**Utilisation :**
```bash
# Dans WSL kali-linux
wsl -d kali-linux
sudo bash scripts/linux/install_osint_tools.sh
```

**Outils installés :**
- dnsrecon
- theHarvester
- sublist3r
- amass
- whatweb
- sslscan
- sherlock
- maigret

#### `install_pentest_tools.sh` - Installe les outils de Pentest
Installe tous les outils de Pentest nécessaires pour ProspectLab dans Kali Linux.

**Prérequis :**
- Kali Linux (WSL ou natif)
- Droits sudo
- **Autorisation écrite** pour les tests de sécurité

**Utilisation :**
```bash
# Dans WSL kali-linux
wsl -d kali-linux
sudo bash scripts/linux/install_pentest_tools.sh
```

**Outils installés :**
- sqlmap
- wpscan
- nikto
- wapiti
- nmap
- sslscan

**Avertissement :**
Ces outils sont destinés uniquement à des tests autorisés. Utilisez-les uniquement sur des systèmes pour lesquels vous avez une autorisation écrite.

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

