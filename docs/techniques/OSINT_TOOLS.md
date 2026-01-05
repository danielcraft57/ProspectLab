# Guide d'installation des outils OSINT pour ProspectLab

## Installation dans Kali Linux (WSL)

### Commandes de base

```bash
# Se connecter à Kali Linux
wsl -d kali-linux -u loupix

# Mettre à jour le système
sudo apt update && sudo apt upgrade -y
```

## Outils OSINT essentiels

### 1. Reconnaissance et scanning

```bash
# Nmap (déjà installé normalement)
sudo apt install nmap

# Masscan (scan rapide de ports)
sudo apt install masscan

# Zmap (scanner réseau ultra-rapide)
sudo apt install zmap

# Unicornscan (scanner réseau avancé)
sudo apt install unicornscan
```

### 2. Analyse DNS et domaine

```bash
# DNSRecon (reconnaissance DNS avancée)
sudo apt install dnsrecon

# DNSenum (énumération DNS)
sudo apt install dnsenum

# Fierce (scanner de domaine)
sudo apt install fierce

# Sublist3r (énumération de sous-domaines)
sudo apt install sublist3r

# Amass (reconnaissance réseau et énumération)
sudo apt install amass

# Subfinder (découverte de sous-domaines)
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Findomain (découverte de domaines)
sudo apt install findomain
```

### 3. WHOIS et informations domaine

```bash
# Whois (déjà installé normalement)
sudo apt install whois

# Dnsrecon (déjà mentionné mais important)
# Maltego (outil de visualisation - installation manuelle)
```

### 4. Analyse web et technologies

```bash
# Wafw00f (détection de WAF)
sudo apt install wafw00f

# Whatweb (identification de technologies web)
sudo apt install whatweb

# Wappalyzer (via npm, pour analyse de technologies)
# Nécessite Node.js installé dans WSL

# Nikto (scanner de vulnérabilités web)
sudo apt install nikto

# Dirb / Dirbuster (énumération de répertoires)
sudo apt install dirb dirbuster

# Gobuster (énumération de répertoires rapide)
sudo apt install gobuster
```

### 5. OSINT et recherche d'informations

```bash
# TheHarvester (collecte d'emails, sous-domaines, etc.)
sudo apt install theharvester

# Recon-ng (framework de reconnaissance)
sudo apt install recon-ng

# OSINT-SPY (outil d'investigation)
git clone https://github.com/Sharad-Kumar/osint-spy.git

# Sherlock (recherche de comptes sur réseaux sociaux)
sudo apt install sherlock

# SocialScan (vérification d'emails sur réseaux sociaux)
pip3 install socialscan

# Holehe (vérification d'emails sur différents services)
pip3 install holehe
```

### 6. Analyse SSL/TLS

```bash
# SSLscan (analyse SSL/TLS)
sudo apt install sslscan

# SSLyze (analyse SSL/TLS avancée)
sudo apt install sslyze

# TestSSL (test SSL complet)
git clone --depth 1 https://github.com/drwetter/testssl.sh.git
```

### 7. Analyse de métadonnées

```bash
# ExifTool (extraction de métadonnées)
sudo apt install libimage-exiftool-perl

# Metagoofil (extraction de métadonnées Google)
sudo apt install metagoofil
```

### 8. Analyse de réseaux sociaux

```bash
# Social-Engineer Toolkit (SET)
sudo apt install set

# SocialFish (phishing framework)
# Installation manuelle depuis GitHub
```

### 9. Outils Python pour OSINT

```bash
# Installation de bibliothèques Python utiles
pip3 install --upgrade pip
pip3 install requests beautifulsoup4 lxml
pip3 install python-whois dnspython
pip3 install shodan
pip3 install censys
pip3 install fullcontact
pip3 install clearbit
```

### 10. Outils de recherche avancée

```bash
# Shodan CLI (nécessite une clé API)
pip3 install shodan

# Censys CLI (nécessite une clé API)
pip3 install censys

# Wayback Machine (archive web)
pip3 install waybackpy
```

## Installation groupée (copier-coller)

```bash
# Se connecter à Kali
wsl -d kali-linux -u loupix

# Mise à jour
sudo apt update && sudo apt upgrade -y

# Installation des outils essentiels
sudo apt install -y \
    nmap masscan zmap \
    dnsrecon dnsenum fierce sublist3r amass findomain \
    whois \
    wafw00f whatweb nikto dirb dirbuster gobuster \
    theharvester recon-ng sherlock \
    sslscan sslyze \
    libimage-exiftool-perl metagoofil \
    set

# Installation des outils Python
pip3 install --upgrade pip
pip3 install requests beautifulsoup4 lxml python-whois dnspython
pip3 install shodan censys waybackpy socialscan holehe

# Installation de testssl.sh
cd ~
git clone --depth 1 https://github.com/drwetter/testssl.sh.git
cd testssl.sh
chmod +x testssl.sh
```

## Outils à installer manuellement (optionnels mais puissants)

### 1. Maltego
- Site: https://www.maltego.com/
- Outil de visualisation de données OSINT
- Nécessite une installation graphique

### 2. Shodan / Censys
- Nécessitent des clés API (gratuites avec limitations)
- Très puissants pour la recherche d'infrastructures

### 3. SpiderFoot
```bash
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot
pip3 install -r requirements.txt
```

### 4. OSINT Framework
- Site web: https://osintframework.com/
- Collection d'outils organisés par catégorie

## Intégration avec ProspectLab

Ces outils peuvent être intégrés dans ProspectLab pour enrichir les analyses :

1. **DNSRecon / Amass** : Pour découvrir plus de sous-domaines
2. **TheHarvester** : Pour trouver plus d'emails
3. **Whatweb / Wappalyzer** : Pour détecter plus de technologies
4. **SSLscan / SSLyze** : Pour une analyse SSL plus approfondie
5. **Shodan / Censys** : Pour des informations sur l'infrastructure

## Notes importantes

- Certains outils nécessitent des privilèges root (sudo)
- Les outils avec API (Shodan, Censys) nécessitent des clés API
- Certains outils peuvent être détectés par les systèmes de sécurité
- Toujours respecter les conditions d'utilisation des services

## Vérification de l'installation

```bash
# Tester quelques outils
nmap --version
dnsrecon -h
theharvester -h
whatweb --version
sslscan --version
```

