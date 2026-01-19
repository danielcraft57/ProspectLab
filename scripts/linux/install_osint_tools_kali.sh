#!/bin/bash
# Script d'installation des outils OSINT pour Kali Linux
# À exécuter dans WSL Kali Linux

set -e

echo "=========================================="
echo "Installation des outils OSINT pour Kali Linux"
echo "=========================================="

# Mettre à jour le système
echo "[1/10] Mise à jour du système..."
sudo apt update
sudo apt upgrade -y

# Installer les dépendances Python et autres outils
echo "[2/10] Installation des dépendances Python et outils..."
sudo apt install -y python3 python3-pip python3-venv git curl wget unzip

# Installer les outils OSINT de base
echo "[3/10] Installation des outils OSINT de base..."

# TheHarvester
echo "  - Installation de TheHarvester..."
if ! command -v theHarvester &> /dev/null; then
    sudo apt install -y theharvester
else
    echo "    TheHarvester déjà installé"
fi

# Sublist3r
echo "  - Installation de Sublist3r..."
if ! command -v sublist3r &> /dev/null; then
    sudo apt install -y sublist3r
else
    echo "    Sublist3r déjà installé"
fi

# Amass
echo "  - Installation de Amass..."
if ! command -v amass &> /dev/null; then
    sudo apt install -y amass
else
    echo "    Amass déjà installé"
fi

# DNSrecon
echo "  - Installation de DNSrecon..."
if ! command -v dnsrecon &> /dev/null; then
    sudo apt install -y dnsrecon
else
    echo "    DNSrecon déjà installé"
fi

# WhatWeb
echo "  - Installation de WhatWeb..."
if ! command -v whatweb &> /dev/null; then
    sudo apt install -y whatweb
else
    echo "    WhatWeb déjà installé"
fi

# SSLScan
echo "  - Installation de SSLScan..."
if ! command -v sslscan &> /dev/null; then
    sudo apt install -y sslscan
else
    echo "    SSLScan déjà installé"
fi

# Installer pipx si nécessaire (recommandé pour Kali Linux moderne)
echo "[4/10] Installation de pipx et des outils Python..."
if ! command -v pipx &> /dev/null; then
    echo "  - Installation de pipx..."
    sudo apt install -y pipx
fi

# Toujours s'assurer que pipx est dans le PATH
pipx ensurepath 2>/dev/null || true
# Recharger le PATH pour cette session
export PATH="$HOME/.local/bin:$PATH"
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    export PATH="$HOME/.local/bin:$PATH"
fi

# Sherlock
echo "  - Installation de Sherlock..."
if ! command -v sherlock &> /dev/null; then
    pipx install sherlock-project
else
    echo "    Sherlock déjà installé"
fi

# Maigret
echo "  - Installation de Maigret..."
if ! command -v maigret &> /dev/null; then
    pipx install maigret
else
    echo "    Maigret déjà installé"
fi

# Holehe
echo "  - Installation de Holehe..."
if ! command -v holehe &> /dev/null; then
    pipx install holehe
else
    echo "    Holehe déjà installé"
fi

# PhoneInfoga
echo "[5/10] Installation de PhoneInfoga..."
if ! command -v phoneinfoga &> /dev/null; then
    # Utiliser le script d'installation officiel de PhoneInfoga
    echo "    Installation via le script officiel PhoneInfoga..."
    
    # Créer un répertoire temporaire pour l'installation
    INSTALL_DIR=$(mktemp -d)
    cd "$INSTALL_DIR"
    
    # Le script officiel gère automatiquement l'architecture et l'installation
    curl -sSL https://raw.githubusercontent.com/sundowndev/phoneinfoga/master/support/scripts/install | bash
    
    # Le script installe dans le répertoire courant, déplacer vers /usr/local/bin
    if [ -f "./phoneinfoga" ]; then
        sudo mv ./phoneinfoga /usr/local/bin/phoneinfoga
        sudo chmod +x /usr/local/bin/phoneinfoga
        echo "    ✓ PhoneInfoga installé avec succès"
    elif command -v phoneinfoga &> /dev/null; then
        echo "    ✓ PhoneInfoga déjà dans le PATH"
    else
        echo "    ⚠ Installation échouée, tentative manuelle..."
        # Fallback: téléchargement manuel
        ARCH=$(uname -m)
        if [ "$ARCH" = "x86_64" ]; then
            ARCH="x86_64"
        elif [ "$ARCH" = "aarch64" ]; then
            ARCH="arm64"
        else
            ARCH="x86_64"
        fi
        
        rm -f phoneinfoga.tar.gz phoneinfoga 2>/dev/null
        wget -q "https://github.com/sundowndev/phoneinfoga/releases/download/v2.11.0/phoneinfoga_Linux_${ARCH}.tar.gz" -O phoneinfoga.tar.gz && {
            tar -xzf phoneinfoga.tar.gz
            if [ -f phoneinfoga ]; then
                sudo mv phoneinfoga /usr/local/bin/phoneinfoga
                sudo chmod +x /usr/local/bin/phoneinfoga
                echo "    ✓ PhoneInfoga installé manuellement"
            fi
            rm -f phoneinfoga.tar.gz
        } || echo "    ⚠ Échec du téléchargement manuel"
    fi
    
    cd ~
    rm -rf "$INSTALL_DIR"
    
    # Vérifier l'installation finale
    if command -v phoneinfoga &> /dev/null; then
        echo "    ✓ PhoneInfoga disponible dans le PATH"
    fi
else
    echo "    PhoneInfoga déjà installé"
fi

# Installer des outils supplémentaires pour la recherche de personnes
echo "[6/10] Installation d'outils supplémentaires pour la recherche de personnes..."

# SocialScan (recherche d'emails sur les réseaux sociaux)
echo "  - Installation de SocialScan..."
if ! command -v socialscan &> /dev/null; then
    pipx install socialscan
else
    echo "    SocialScan déjà installé"
fi

# Infoga (recherche d'emails) - OPTIONNEL
# Désactiver set -e pour cette section car Infoga est optionnel
set +e
echo "  - Installation d'Infoga (optionnel)..."
if [ ! -d ~/Infoga ]; then
    cd ~
    # Télécharger directement l'archive ZIP depuis GitHub (pas besoin d'authentification)
    echo "    Tentative de téléchargement d'Infoga depuis GitHub (timeout 15s)..."
    
    # Essayer plusieurs méthodes de téléchargement avec timeout
    DOWNLOAD_SUCCESS=0
    
    # Méthode 1: wget avec timeout court (15 secondes max)
    if command -v timeout &> /dev/null; then
        timeout 15 wget -q --timeout=10 "https://codeload.github.com/m4ll0k/Infoga/zip/refs/heads/master" -O Infoga.zip 2>/dev/null
    else
        wget -q --timeout=10 "https://codeload.github.com/m4ll0k/Infoga/zip/refs/heads/master" -O Infoga.zip 2>/dev/null &
        WGET_PID=$!
        sleep 15
        kill $WGET_PID 2>/dev/null || true
        wait $WGET_PID 2>/dev/null || true
    fi
    
    if [ -f Infoga.zip ] && [ -s Infoga.zip ]; then
        DOWNLOAD_SUCCESS=1
    fi
    
    # Méthode 2: curl si wget a échoué
    if [ "$DOWNLOAD_SUCCESS" -eq 0 ]; then
        echo "    Tentative avec curl..."
        if command -v timeout &> /dev/null; then
            timeout 15 curl -sL --max-time 10 "https://codeload.github.com/m4ll0k/Infoga/zip/refs/heads/master" -o Infoga.zip 2>/dev/null
        else
            curl -sL --max-time 10 "https://codeload.github.com/m4ll0k/Infoga/zip/refs/heads/master" -o Infoga.zip 2>/dev/null &
            CURL_PID=$!
            sleep 15
            kill $CURL_PID 2>/dev/null || true
            wait $CURL_PID 2>/dev/null || true
        fi
        
        if [ -f Infoga.zip ] && [ -s Infoga.zip ]; then
            DOWNLOAD_SUCCESS=1
        fi
    fi
    
    if [ "$DOWNLOAD_SUCCESS" -eq 1 ] && [ -f Infoga.zip ] && [ -s Infoga.zip ]; then
        unzip -q Infoga.zip 2>/dev/null
        if [ -d Infoga-master ]; then
            mv Infoga-master Infoga
            rm -f Infoga.zip
            cd Infoga
            # Créer un environnement virtuel pour Infoga
            python3 -m venv venv
            source venv/bin/activate
            # Installer les dépendances
            if [ -f requirements.txt ]; then
                pip install -r requirements.txt 2>/dev/null || {
                    echo "    Installation des dépendances de base..."
                    pip install requests colorama urllib3
                }
            else
                echo "    Installation des dépendances de base..."
                pip install requests colorama urllib3
            fi
            deactivate
            cd ~
            echo "    ✓ Infoga installé (utiliser: cd ~/Infoga && source venv/bin/activate && python infoga.py)"
        else
            echo "    ⚠ Erreur lors de l'extraction d'Infoga"
            rm -f Infoga.zip
        fi
    else
        echo "    ⚠ Impossible de télécharger Infoga (timeout ou repo inaccessible)"
        echo "    Infoga est optionnel, le script continue sans cet outil"
        echo "    Pour l'installer manuellement: https://github.com/m4ll0k/Infoga"
        rm -f Infoga.zip
    fi
    cd ~
else
    echo "    Infoga déjà installé"
fi

# Réactiver la gestion d'erreurs pour le reste du script
set -e

# Installer des outils pour la recherche d'images
echo "[7/10] Installation d'outils pour la recherche d'images..."

# Note: yandex-images n'est pas disponible via pip, on utilise des alternatives
# Les recherches d'images se feront via les APIs web directement dans le code Python
echo "    Les recherches d'images seront effectuées via les APIs web (Google Images, DuckDuckGo)"
echo "    Aucune installation supplémentaire nécessaire"

# Installer des outils pour la géolocalisation
echo "[8/10] Installation d'outils pour la géolocalisation..."

# Geocoder (bibliothèque Python, pas une app CLI)
if ! python3 -c "import geocoder" 2>/dev/null; then
    python3 -m venv /tmp/geocoder_venv
    source /tmp/geocoder_venv/bin/activate
    pip install geocoder
    deactivate
    echo "    Geocoder installé dans venv temporaire"
else
    echo "    Geocoder déjà disponible"
fi

# Installer des outils pour la recherche de fuites de données
echo "[9/10] Installation d'outils pour la recherche de fuites de données..."

# HIBP (Have I Been Pwned) CLI
if ! command -v hibp &> /dev/null; then
    pipx install hibpcli
else
    echo "    HIBP CLI déjà installé"
fi

# Installer des outils OSINT supplémentaires très utiles
echo "[10/15] Installation d'outils OSINT supplémentaires..."

# Recon-ng (framework de reconnaissance web)
echo "  - Installation de Recon-ng..."
if ! command -v recon-ng &> /dev/null; then
    sudo apt install -y recon-ng || echo "    ⚠ Recon-ng non disponible via apt"
else
    echo "    Recon-ng déjà installé"
fi

# Subfinder (découverte de sous-domaines rapide - Go)
echo "  - Installation de Subfinder..."
if ! command -v subfinder &> /dev/null; then
    if command -v go &> /dev/null; then
        export PATH=$PATH:/usr/local/go/bin
        export GOPATH=$HOME/go
        export PATH=$PATH:$GOPATH/bin
        mkdir -p $GOPATH/bin
        go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
        if [ -f "$GOPATH/bin/subfinder" ]; then
            sudo cp $GOPATH/bin/subfinder /usr/local/bin/subfinder
            sudo chmod +x /usr/local/bin/subfinder
            echo "    ✓ Subfinder installé"
        fi
    else
        echo "    ⚠ Go non disponible, Subfinder non installé"
    fi
else
    echo "    Subfinder déjà installé"
fi

# Findomain (découverte de domaines)
echo "  - Installation de Findomain..."
if ! command -v findomain &> /dev/null; then
    sudo apt install -y findomain || {
        # Fallback: téléchargement depuis GitHub
        cd /tmp
        ARCH=$(uname -m)
        if [ "$ARCH" = "x86_64" ]; then
            ARCH="x86_64"
        elif [ "$ARCH" = "aarch64" ]; then
            ARCH="aarch64"
        else
            ARCH="x86_64"
        fi
        wget -q "https://github.com/Findomain/Findomain/releases/latest/download/findomain-linux" -O findomain
        sudo mv findomain /usr/local/bin/findomain
        sudo chmod +x /usr/local/bin/findomain
        cd ~
        echo "    ✓ Findomain installé depuis GitHub"
    }
else
    echo "    Findomain déjà installé"
fi

# DNSenum (énumération DNS avancée)
echo "  - Installation de DNSenum..."
if ! command -v dnsenum &> /dev/null; then
    sudo apt install -y dnsenum || echo "    ⚠ DNSenum non disponible via apt"
else
    echo "    DNSenum déjà installé"
fi

# Fierce (scanner de domaine)
echo "  - Installation de Fierce..."
if ! command -v fierce &> /dev/null; then
    sudo apt install -y fierce || echo "    ⚠ Fierce non disponible via apt"
else
    echo "    Fierce déjà installé"
fi

# Metagoofil (extraction de métadonnées de documents)
echo "  - Installation de Metagoofil..."
if ! command -v metagoofil &> /dev/null; then
    sudo apt install -y metagoofil || echo "    ⚠ Metagoofil non disponible via apt"
else
    echo "    Metagoofil déjà installé"
fi

# ExifTool (extraction de métadonnées d'images)
echo "  - Installation d'ExifTool..."
if ! command -v exiftool &> /dev/null; then
    sudo apt install -y libimage-exiftool-perl || echo "    ⚠ ExifTool non disponible via apt"
else
    echo "    ExifTool déjà installé"
fi

# testssl.sh (analyse SSL/TLS complète)
echo "  - Installation de testssl.sh..."
if [ ! -d ~/testssl.sh ]; then
    cd ~
    git clone --depth 1 https://github.com/drwetter/testssl.sh.git 2>/dev/null && {
        chmod +x testssl.sh/testssl.sh
        sudo ln -sf ~/testssl.sh/testssl.sh /usr/local/bin/testssl.sh
        echo "    ✓ testssl.sh installé"
    } || echo "    ⚠ Échec du clonage de testssl.sh"
    cd ~
else
    echo "    testssl.sh déjà installé"
fi

# Wafw00f (détection de WAF)
echo "  - Installation de Wafw00f..."
if ! command -v wafw00f &> /dev/null; then
    sudo apt install -y wafw00f || pipx install wafw00f || echo "    ⚠ Wafw00f non disponible"
else
    echo "    Wafw00f déjà installé"
fi

# Nikto (scanner de vulnérabilités web)
echo "  - Installation de Nikto..."
if ! command -v nikto &> /dev/null; then
    sudo apt install -y nikto || echo "    ⚠ Nikto non disponible via apt"
else
    echo "    Nikto déjà installé"
fi

# Gobuster (énumération de répertoires rapide)
echo "  - Installation de Gobuster..."
if ! command -v gobuster &> /dev/null; then
    sudo apt install -y gobuster || echo "    ⚠ Gobuster non disponible via apt"
else
    echo "    Gobuster déjà installé"
fi

# Shodan CLI (si clé API disponible)
echo "  - Installation de Shodan CLI..."
if ! command -v shodan &> /dev/null; then
    pipx install shodan || echo "    ⚠ Shodan CLI non installé (nécessite pipx)"
else
    echo "    Shodan CLI déjà installé"
fi

# Censys CLI
echo "  - Installation de Censys CLI..."
if ! command -v censys &> /dev/null; then
    pipx install censys || echo "    ⚠ Censys CLI non installé (nécessite pipx)"
else
    echo "    Censys CLI déjà installé"
fi

# SpiderFoot (plateforme d'intelligence automatisée)
echo "[11/15] Installation de SpiderFoot (optionnel, peut prendre du temps)..."
set +e
if [ ! -d ~/spiderfoot ]; then
    cd ~
    git clone https://github.com/smicallef/spiderfoot.git 2>/dev/null && {
        cd spiderfoot
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt 2>/dev/null || {
            echo "    Installation des dépendances de base..."
            pip install requests beautifulsoup4 lxml
        }
        deactivate
        echo "    ✓ SpiderFoot installé (utiliser: cd ~/spiderfoot && source venv/bin/activate && python3 sf.py)"
    } || echo "    ⚠ Échec du clonage de SpiderFoot"
    cd ~
else
    echo "    SpiderFoot déjà installé"
fi
set -e

# Réactiver la gestion d'erreurs
set -e

# Vérifier les installations
echo ""
echo "[12/15] Vérification des installations..."
echo ""
echo "Outils installés :"
echo "=================="

tools=("theHarvester" "sublist3r" "amass" "dnsrecon" "whatweb" "sslscan" "sherlock" "maigret" "holehe" "phoneinfoga" "socialscan" "recon-ng" "subfinder" "findomain" "dnsenum" "fierce" "metagoofil" "exiftool" "wafw00f" "nikto" "gobuster" "shodan" "censys")

for tool in "${tools[@]}"; do
    if command -v $tool &> /dev/null; then
        echo "✓ $tool : installé"
    else
        echo "✗ $tool : non trouvé"
    fi
done

echo ""
echo "=========================================="
echo "Installation terminée !"
echo "=========================================="
echo ""
echo "📋 Outils installés par catégorie :"
echo ""
echo "🔍 Reconnaissance de domaines :"
echo "   - TheHarvester, Sublist3r, Amass, Subfinder, Findomain"
echo "   - DNSrecon, DNSenum, Fierce"
echo ""
echo "👥 Recherche de personnes :"
echo "   - Sherlock, Maigret, Holehe, SocialScan"
echo "   - PhoneInfoga"
echo ""
echo "🌐 Analyse web :"
echo "   - WhatWeb, Wafw00f, Nikto, Gobuster"
echo "   - SSLScan, testssl.sh"
echo ""
echo "📄 Métadonnées :"
echo "   - Metagoofil, ExifTool"
echo ""
echo "🕵️ Frameworks OSINT :"
echo "   - Recon-ng, SpiderFoot"
echo ""
echo "☁️ APIs et services :"
echo "   - Shodan CLI, Censys CLI"
echo ""
echo "⚠️  Notes importantes :"
echo "   - Certains outils nécessitent des clés API (Shodan, Censys)"
echo "   - SpiderFoot nécessite un environnement virtuel Python"
echo "   - Configurez vos clés API dans config.py pour utiliser Shodan/Censys"
echo ""
echo "📚 Documentation :"
echo "   - Consultez docs/INSTALL_OSINT_TOOLS.md pour plus d'informations"
echo ""

