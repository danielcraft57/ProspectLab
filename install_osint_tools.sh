#!/bin/bash
# Script d'installation des outils OSINT pour ProspectLab
# À exécuter dans Kali Linux (WSL)

echo "=========================================="
echo "Installation des outils OSINT"
echo "=========================================="
echo ""

# Vérifier qu'on est bien dans Kali Linux
if [ ! -f /etc/os-release ] || ! grep -q "Kali" /etc/os-release; then
    echo "⚠️  Attention: Ce script est conçu pour Kali Linux"
    read -p "Continuer quand même ? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Mise à jour du système
echo "📦 Mise à jour du système..."
sudo apt update && sudo apt upgrade -y

# Installation des outils de scanning
echo ""
echo "🔍 Installation des outils de scanning..."
sudo apt install -y \
    nmap \
    masscan \
    zmap \
    unicornscan

# Installation des outils DNS
echo ""
echo "🌐 Installation des outils DNS..."
sudo apt install -y \
    dnsrecon \
    dnsenum \
    fierce \
    sublist3r \
    amass \
    findomain

# Installation des outils WHOIS
echo ""
echo "📋 Installation des outils WHOIS..."
sudo apt install -y whois

# Installation des outils web
echo ""
echo "🌍 Installation des outils d'analyse web..."
sudo apt install -y \
    wafw00f \
    whatweb \
    nikto \
    dirb \
    dirbuster \
    gobuster

# Installation des outils OSINT
echo ""
echo "🕵️ Installation des outils OSINT..."
sudo apt install -y \
    theharvester \
    recon-ng \
    sherlock

# Installation des outils SSL/TLS
echo ""
echo "🔒 Installation des outils SSL/TLS..."
sudo apt install -y \
    sslscan \
    sslyze

# Installation des outils de métadonnées
echo ""
echo "📄 Installation des outils de métadonnées..."
sudo apt install -y \
    libimage-exiftool-perl \
    metagoofil

# Installation des outils de réseaux sociaux
echo ""
echo "👥 Installation des outils de réseaux sociaux..."
sudo apt install -y set

# Installation de testssl.sh
echo ""
echo "🔐 Installation de testssl.sh..."
cd ~
if [ -d "testssl.sh" ]; then
    echo "testssl.sh existe déjà, mise à jour..."
    cd testssl.sh
    git pull
else
    git clone --depth 1 https://github.com/drwetter/testssl.sh.git
    cd testssl.sh
fi
chmod +x testssl.sh
cd ~

# Installation des outils Python
echo ""
echo "🐍 Installation des outils Python..."
pip3 install --upgrade pip
pip3 install \
    requests \
    beautifulsoup4 \
    lxml \
    python-whois \
    dnspython \
    shodan \
    censys \
    waybackpy \
    socialscan \
    holehe

# Installation de SpiderFoot (optionnel)
echo ""
read -p "Installer SpiderFoot ? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🕷️  Installation de SpiderFoot..."
    cd ~
    if [ -d "spiderfoot" ]; then
        echo "SpiderFoot existe déjà, mise à jour..."
        cd spiderfoot
        git pull
    else
        git clone https://github.com/smicallef/spiderfoot.git
        cd spiderfoot
    fi
    pip3 install -r requirements.txt
    cd ~
fi

# Vérification de l'installation
echo ""
echo "=========================================="
echo "Vérification de l'installation..."
echo "=========================================="
echo ""

tools=("nmap" "dnsrecon" "theharvester" "whatweb" "sslscan" "whois")
for tool in "${tools[@]}"; do
    if command -v $tool &> /dev/null; then
        echo "✅ $tool: installé"
    else
        echo "❌ $tool: non trouvé"
    fi
done

echo ""
echo "=========================================="
echo "Installation terminée !"
echo "=========================================="
echo ""
echo "📚 Consultez OSINT_TOOLS.md pour plus d'informations"
echo ""

