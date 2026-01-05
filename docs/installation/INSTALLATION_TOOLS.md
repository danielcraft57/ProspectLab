# Guide d'installation des outils pour ProspectLab

Ce guide regroupe tous les outils nécessaires pour maximiser les capacités de ProspectLab.

## 📋 Guides disponibles

1. **[OSINT_TOOLS.md](OSINT_TOOLS.md)** - Outils de renseignement en sources ouvertes
2. **[PENTEST_TOOLS.md](PENTEST_TOOLS.md)** - Outils de test de pénétration

## 🚀 Installation rapide

### Option 1 : Installation automatique (recommandé)

```bash
# Se connecter à Kali Linux
wsl -d kali-linux -u loupix

# Aller dans le dossier du projet
cd /mnt/c/Users/loicDaniel/Documents/DanielCraft/prospectlab

# Installation des outils OSINT
chmod +x install_osint_tools.sh
./install_osint_tools.sh

# Installation des outils de pentest
chmod +x install_pentest_tools.sh
./install_pentest_tools.sh
```

### Option 2 : Installation manuelle groupée

```bash
wsl -d kali-linux -u loupix
sudo apt update && sudo apt upgrade -y

# Outils OSINT essentiels
sudo apt install -y \
    nmap masscan dnsrecon dnsenum fierce sublist3r amass findomain \
    whois wafw00f whatweb nikto dirb gobuster \
    theharvester recon-ng sherlock sslscan sslyze \
    libimage-exiftool-perl metagoofil set

# Outils de pentest essentiels
sudo apt install -y \
    metasploit-framework exploitdb beef-xss set routersploit \
    john hashcat hydra medusa crunch cewl wordlists \
    sqlmap wpscan joomscan droopescan wapiti arachni \
    wireshark tcpdump ettercap-text-only bettercap responder \
    zaproxy xsser commix ffuf wfuzz dirsearch feroxbuster \
    radare2 gdb binwalk bloodhound crackmapexec \
    netcat socat proxychains4 sshuttle steghide outguess

# Outils Python
pip3 install --upgrade pip
pip3 install \
    requests beautifulsoup4 lxml python-whois dnspython \
    shodan censys waybackpy socialscan holehe \
    python-nmap

# Initialisation Metasploit
sudo msfdb init
```

## 📦 Outils par catégorie

### OSINT (Renseignement)
- **Reconnaissance** : nmap, masscan, dnsrecon, amass
- **DNS** : dnsenum, fierce, sublist3r, findomain
- **Web** : whatweb, wafw00f, nikto
- **Emails** : theharvester, holehe, socialscan
- **SSL/TLS** : sslscan, sslyze, testssl.sh

### Pentest (Test de pénétration)
- **Frameworks** : Metasploit, Empire, BeEF
- **Web** : SQLMap, WPScan, Burp Suite, OWASP ZAP
- **Force brute** : John, Hashcat, Hydra
- **Réseau** : Wireshark, Ettercap, Bettercap
- **Post-exploitation** : BloodHound, CrackMapExec

## ⚙️ Configuration WSL

Le code de ProspectLab est configuré pour utiliser :
- **WSL** : `wsl -d kali-linux -u loupix`
- **Nmap** : Détecté automatiquement (natif ou via WSL)

## ⚠️ Avertissements légaux

### OSINT
- Les outils OSINT sont généralement légaux pour la recherche d'informations publiques
- Respecter les conditions d'utilisation des services
- Ne pas abuser des APIs (Shodan, Censys)

### Pentest
- ⚠️ **CRITIQUE** : Utiliser uniquement avec autorisation écrite
- Ne jamais tester sans permission
- Respecter les lois locales et internationales
- Documenter toutes les activités

## 🔧 Vérification de l'installation

```bash
# Tester les outils OSINT
nmap --version
dnsrecon -h
theharvester -h
whatweb --version

# Tester les outils de pentest
msfconsole --version
sqlmap --version
wpscan --version
john --version
hashcat --version
```

## 📚 Ressources

- **Kali Linux Documentation** : https://www.kali.org/docs/
- **OWASP** : https://owasp.org/
- **Metasploit Unleashed** : https://www.offensive-security.com/metasploit-unleashed/
- **OSINT Framework** : https://osintframework.com/

## 🎯 Prochaines étapes

1. Installer les outils OSINT pour enrichir les analyses
2. Installer les outils de pentest pour les tests de sécurité
3. Configurer les clés API (Shodan, Censys) si nécessaire
4. Lire les guides détaillés pour chaque catégorie d'outils

## 💡 Intégration avec ProspectLab

Les outils peuvent être intégrés dans ProspectLab pour :
- **Analyses techniques** : Détection automatique de technologies
- **Scans de vulnérabilités** : Intégration des résultats
- **Recherche d'informations** : Enrichissement des données
- **Reporting** : Génération de rapports complets

