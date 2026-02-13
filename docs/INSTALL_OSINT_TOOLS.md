# Installation des outils OSINT pour ProspectLab

Ce guide explique comment installer les outils OSINT selon l'environnement :

- **En production (serveur Linux)** : pas de WSL. Les outils sont exécutés **directement** sur le système (apt, pip, etc. sur le serveur).
- **En développement (Windows)** : on utilise **WSL** (ex. Kali) et on installe les outils **dans** la distro WSL.

## Versions Debian / Kali supportées

Les scripts sont organisés par environnement :

- **Debian 13 (Trixie)** : `scripts/linux/trixie/*`
- **Debian 12 (Bookworm)** : `scripts/linux/bookworm/*`
- **Kali Linux (WSL / desktop)** : `scripts/linux/kali/*`

Les scripts dispatcher (`install_all_tools.sh`, `test_all_tools.sh`) détectent automatiquement votre version (Debian ou Kali) et utilisent les bons scripts.

## Prérequis

**Production (Linux)** : accès root ou sudo sur le serveur.

**Développement (Windows)** : WSL installé, distro Kali (ou autre), accès root/sudo dans la distro.

## Installation automatique

### Scripts dispatcher (recommandé)

Les scripts `install_all_tools.sh` et `test_all_tools.sh` détectent automatiquement votre version Debian et utilisent les bons scripts :

```bash
# En production (Linux) : détection automatique de la version
cd /opt/prospectlab
bash scripts/linux/install_all_tools.sh
bash scripts/linux/test_all_tools.sh
```

Ces scripts lisent `/etc/os-release` et utilisent :
- **Debian 13 (Trixie)** → `scripts/linux/trixie/*`
- **Debian 12 (Bookworm)** → `scripts/linux/bookworm/*`

### Installation par environnement spécifique

Si vous préférez installer manuellement pour un environnement précis :

**Debian 13 (Trixie)** :
```bash
cd /opt/prospectlab
bash scripts/linux/trixie/install_all_tools_trixie.sh
bash scripts/linux/trixie/test_all_tools_trixie.sh
```

**Debian 12 (Bookworm) / RPi** :
```bash
cd /opt/prospectlab
bash scripts/linux/bookworm/install_all_tools_bookworm.sh
bash scripts/linux/bookworm/test_all_tools_bookworm.sh
```

**Kali Linux (WSL / desktop)** :
```bash
# Dans la session Kali (WSL ou machine Kali directe)
cd /chemin/vers/ProspectLab
bash scripts/linux/kali/install_all_tools_kali.sh
bash scripts/linux/kali/test_all_tools_kali.sh
```

## Installation manuelle

Si vous préférez installer les outils manuellement :

### 1. Outils de base (via apt)

```bash
sudo apt update
sudo apt install -y \
    theharvester \
    sublist3r \
    amass \
    dnsrecon \
    whatweb \
    sslscan
```

### 2. Installation de pipx (recommandé pour Kali Linux moderne)

Kali Linux utilise maintenant un environnement Python géré de manière externe (PEP 668). Il faut utiliser `pipx` pour installer les applications Python :

```bash
sudo apt install -y pipx
pipx ensurepath
export PATH="$HOME/.local/bin:$PATH"  # Pour cette session
```

### 3. Outils Python (via pipx)

```bash
pipx install sherlock-project
pipx install maigret
pipx install holehe
pipx install socialscan
pipx install hibpcli
```

### 4. PhoneInfoga (avec environnement virtuel)

```bash
cd /tmp
git clone https://github.com/sundowndev/phoneinfoga.git
cd phoneinfoga
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
# Créer un wrapper script
sudo tee /usr/local/bin/phoneinfoga > /dev/null << 'EOF'
#!/bin/bash
cd /tmp/phoneinfoga
source venv/bin/activate
python3 phoneinfoga.py "$@"
deactivate
EOF
sudo chmod +x /usr/local/bin/phoneinfoga
cd ~
```

### 5. Infoga (recherche d'emails)

```bash
cd ~
git clone https://github.com/m4ll0k/Infoga.git
cd Infoga
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
# Pour utiliser Infoga : cd ~/Infoga && source venv/bin/activate && python infoga.py
```

## Vérification de l'installation

Vérifiez que tous les outils sont installés :

```bash
tools=("theHarvester" "sublist3r" "amass" "dnsrecon" "whatweb" "sslscan" "sherlock" "maigret" "holehe" "phoneinfoga")

for tool in "${tools[@]}"; do
    if command -v $tool &> /dev/null; then
        echo "✓ $tool : installé"
    else
        echo "✗ $tool : non trouvé"
    fi
done
```

## Configuration

### Variables d'environnement WSL

Assurez-vous que votre fichier `config.py` contient les bonnes valeurs :

```python
WSL_DISTRO = 'kali-linux'
WSL_USER = 'votre_utilisateur'  # Remplacez par votre utilisateur WSL
```

### Permissions

Certains outils peuvent nécessiter des permissions supplémentaires. Si vous rencontrez des erreurs :

```bash
# Ajouter votre utilisateur au groupe sudo si nécessaire
sudo usermod -aG sudo $USER

# Vérifier les permissions pour les outils Python
chmod +x ~/.local/bin/*
```

## Outils installés et leurs usages

### TheHarvester
- **Usage** : Recherche d'emails, sous-domaines, personnes
- **Commande** : `theHarvester -d example.com -b google`

### Sublist3r
- **Usage** : Découverte de sous-domaines
- **Commande** : `sublist3r -d example.com`

### Amass
- **Usage** : Découverte de sous-domaines avancée
- **Commande** : `amass enum -d example.com`

### DNSrecon
- **Usage** : Reconnaissance DNS
- **Commande** : `dnsrecon -d example.com`

### WhatWeb
- **Usage** : Détection de technologies web
- **Commande** : `whatweb example.com`

### SSLScan
- **Usage** : Analyse SSL/TLS
- **Commande** : `sslscan example.com`

### Sherlock
- **Usage** : Recherche de profils sociaux par username
- **Commande** : `sherlock username`

### Maigret
- **Usage** : Recherche de profils sociaux avancée
- **Commande** : `maigret username`

### Holehe
- **Usage** : Vérification d'emails sur différents sites
- **Commande** : `holehe email@example.com`

### PhoneInfoga
- **Usage** : Analyse de numéros de téléphone
- **Commande** : `phoneinfoga scan --number +33123456789`

## Pourquoi OSINT / Pentest ne fonctionnent pas

**En production (Linux)** : il n’y a pas de WSL. Les outils sont exécutés **en natif** : le serveur cherche chaque outil dans le `PATH` (`which whatweb`, etc.). Si les outils ne sont pas installés sur le serveur (apt, pip, scripts d’install), les étapes correspondantes restent vides. Installer les outils directement sur le serveur (voir scripts `install_osint_tools_*.sh` adaptés à la distro, ou installation manuelle).

**En développement (Windows)** : le code utilise WSL si disponible, sinon il tente le `PATH` Windows (souvent vide pour ces outils). Si rien ne se passe :

1. **WSL installé et démarré**  
   Depuis PowerShell : `wsl -l -v`. La distro doit être « Running ».

2. **Nom de distro et utilisateur**  
   Dans `.env` ou `config.py` :  
   - `WSL_DISTRO` = le nom exact (ex. `kali-linux`).  
   - `WSL_USER` = l’utilisateur (ex. `loupix`).  
   Test : `wsl -d kali-linux -u loupix whoami`.

3. **Outils installés dans WSL**  
   Les outils sont cherchés **dans** la distro. Depuis WSL :  
   `wsl -d kali-linux -u loupix bash -c "which whatweb; which sherlock"`.  
   Si « not found », installer dans WSL (scripts `install_osint_tools_*.sh`).

4. **Timeouts**  
   `OSINT_TOOL_TIMEOUT=90`, `PENTEST_TOOL_TIMEOUT=180` dans `.env` si besoin.

5. **Logs**  
   `logs/osint_tasks.log`, `logs/pentest_tasks.log`, `logs/celery.log`.

**Diagnostic** : `GET /api/osint/diagnostic` et `GET /api/pentest/diagnostic` renvoient `execution_mode` (`native` en prod, `wsl` en dev Windows avec WSL), plus la liste des outils détectés (disponibles / manquants).

## Nouveaux outils (ranking, SEO, réseaux sociaux)

### Ranking / SEO (Linux, open source)

| Outil | Rôle | Installation |
|-------|------|--------------|
| **Serposcope** | Suivi de positionnement Google (mots-clés, positions, concurrence). CRON, proxys, captchas. | Java requis. Téléchargement sur serphacker.com. Tourne en local ou VPS. |
| **Lighthouse** | Audit SEO (perfs, accessibilité, bonnes pratiques). Score + recommandations. | `npm i -g lighthouse` ou `npx lighthouse https://... --output=json` |
| **Screaming Frog** | Crawler SEO (URLs, titres, meta). Version gratuite limitée (500 URLs). | App desktop (Linux possible), pas pur CLI. |

En pratique : Serposcope pour le suivi de positions, Lighthouse pour l’audit technique SEO.

### Présence sur les réseaux sociaux (Linux / CLI)

| Outil | Rôle | Installation |
|-------|------|--------------|
| **Social Analyzer** | OSINT : vérifier si un pseudo existe sur des centaines de réseaux, score de confiance, métadonnées. | `pip3 install social-analyzer` ou interface web (port 9005). |
| **Sherlock** | Recherche d’un username sur de nombreux sites (déjà utilisé dans ProspectLab). | `pipx install sherlock-project` ou `sudo apt install sherlock` (Kali). |
| **Maigret** | Même idée : un pseudo → profils trouvés sur plein de plateformes. | `pipx install maigret`. |
| **Tinfoleak** | Spécialisé X/Twitter : tweets, abonnés, hashtags, géo (OSINT/SOCMINT). | Souvent inclus dans Kali ; sinon installation manuelle. |

Sherlock et Maigret sont déjà dans la liste des outils OSINT du projet. Social Analyzer et Lighthouse sont inclus dans les scripts d'installation (`install_social_tools_*.sh`, `install_seo_tools_*.sh`).

## Structure des scripts

Les scripts sont organisés dans `scripts/linux/` :

```
scripts/linux/
├── install_all_tools.sh          # Dispatcher (détection auto)
├── test_all_tools.sh             # Dispatcher (détection auto)
├── upgrade_python_venv.sh       # Mise à jour venv Python
├── bookworm/                     # Scripts pour Debian 12
│   ├── install_osint_tools_bookworm.sh
│   ├── install_pentest_tools_bookworm.sh
│   ├── install_seo_tools_bookworm.sh
│   ├── install_social_tools_bookworm.sh
│   ├── install_all_tools_bookworm.sh
│   └── test_*_tools_prod.sh
└── trixie/                       # Scripts pour Debian 13
    ├── install_osint_tools_trixie.sh
    ├── install_pentest_tools_trixie.sh
    ├── install_seo_tools_trixie.sh
    ├── install_social_tools_trixie.sh
    ├── install_all_tools_trixie.sh
    └── test_*_tools_prod.sh
```

**Utilisation recommandée** : utilisez les dispatchers `install_all_tools.sh` et `test_all_tools.sh` qui détectent automatiquement votre version Debian.

## Dépannage

### Problème : Outil non trouvé après installation

```bash
# Vérifier que ~/.local/bin est dans le PATH
echo $PATH | grep -q ".local/bin" || export PATH="$HOME/.local/bin:$PATH"

# Ajouter au .bashrc pour rendre permanent
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Problème : Permission denied

```bash
# Donner les permissions d'exécution
chmod +x ~/.local/bin/*
```

### Problème : Module Python non trouvé

```bash
# Pour les applications CLI, utiliser pipx
pipx install nom_du_module

# Pour les bibliothèques Python, créer un venv
python3 -m venv venv
source venv/bin/activate
pip install nom_du_module
deactivate
```

### Problème : "externally-managed-environment"

Kali Linux utilise maintenant PEP 668. Solutions :

1. **Utiliser pipx** (recommandé pour les applications CLI) :
```bash
pipx install nom_du_module
```

2. **Créer un environnement virtuel** (pour les bibliothèques) :
```bash
python3 -m venv venv
source venv/bin/activate
pip install nom_du_module
```

3. **Installer via apt** si disponible :
```bash
sudo apt install python3-nom-du-module
```

## Support

Pour plus d'informations sur chaque outil, consultez leur documentation officielle :
- TheHarvester : https://github.com/laramies/theHarvester
- PhoneInfoga : https://github.com/sundowndev/phoneinfoga
- Holehe : https://github.com/megadose/holehe
- Maigret : https://github.com/soxoj/maigret

