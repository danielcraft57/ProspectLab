# Installation des outils OSINT pour ProspectLab

Ce guide explique comment installer les outils OSINT nécessaires dans votre environnement WSL Kali Linux.

## Prérequis

- WSL (Windows Subsystem for Linux) installé
- Distribution Kali Linux configurée dans WSL
- Accès root ou sudo

## Installation automatique

Le script d'installation automatique installe tous les outils nécessaires :

```bash
# Depuis Windows PowerShell ou CMD
wsl -d kali-linux bash scripts/linux/install_osint_tools_kali.sh

# Ou depuis WSL Kali Linux directement
cd /mnt/c/Users/loicDaniel/Documents/DanielCraft/prospectlab
bash scripts/linux/install_osint_tools_kali.sh
```

## Debian Bookworm / RPi

```bash
bash scripts/linux/install_osint_tools_bookworm.sh
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

