# Outils utilisés dans ProspectLab

Ce document répertorie tous les outils CLI et bibliothèques utilisés par le projet, organisés par catégorie d'analyse.

## 📋 Vue d'ensemble

| Catégorie | Nombre d'outils | Statut |
|-----------|----------------|--------|
| OSINT | 27 | ✅ Complet |
| Pentest | 10 | ✅ Complet |
| SEO | 3 | ✅ Complet |
| Social OSINT | 3 | ✅ Complet |
| Technique | 2 | ✅ Complet |

---

## 🔍 OSINT (Open Source Intelligence)

### Reconnaissance de domaines
- **dnsrecon** - Énumération DNS et découverte de sous-domaines
- **theharvester** / **theHarvester** - Collecte d'emails, sous-domaines, personnes
- **sublist3r** - Découverte de sous-domaines via moteurs de recherche
- **amass** - Découverte de sous-domaines passive/active
- **subfinder** - Découverte de sous-domaines rapide
- **findomain** - Découverte de sous-domaines via certificats TLS
- **dnsenum** - Énumération DNS complète
- **fierce** - Scanner DNS récursif

### Analyse web
- **whatweb** - Détection de technologies web
- **sslscan** - Analyse SSL/TLS
- **testssl.sh** - Analyse SSL/TLS complète et détaillée
- **wafw00f** - Détection de WAF (Web Application Firewall)
- **nikto** - Scanner de vulnérabilités web
- **gobuster** - Énumération de répertoires et fichiers

### Recherche de personnes
- **sherlock** - Recherche de profils sur réseaux sociaux
- **maigret** - Recherche de profils sur réseaux sociaux (1000+ sites)
- **phoneinfoga** - Analyse OSINT de numéros de téléphone
- **holehe** - Vérification de comptes email sur différents sites

### Métadonnées
- **metagoofil** - Extraction de métadonnées de documents (PDF, DOC, etc.)
- **exiftool** - Extraction de métadonnées d'images et fichiers

### Frameworks OSINT
- **recon-ng** - Framework OSINT modulaire

### APIs CLI
- **shodan** - Recherche d'infrastructures et services exposés (nécessite clé API)
- **censys** - Recherche d'infrastructures et certificats (nécessite clé API)

### Modules Python
- **social-analyzer** - Module Python pour recherche de profils sociaux (1000+ sites)
- **whois** - Module Python pour requêtes WHOIS
- **dns.resolver** (dnspython) - Module Python pour requêtes DNS

### Fichiers sources
- `services/osint_analyzer.py` - Service principal OSINT

---

## 🔒 Pentest (Penetration Testing)

### Scanners de vulnérabilités web
- **sqlmap** - Détection et exploitation d'injections SQL
- **wpscan** - Scanner de vulnérabilités WordPress
- **nikto** - Scanner de vulnérabilités web généraliste
- **wapiti** - Scanner de vulnérabilités web automatisé

### Scanners réseau
- **nmap** - Scanner de ports et services réseau
- **masscan** - Scanner de ports ultra-rapide

### Fuzzing / Découverte de chemins
- **ffuf** - Fuzzer web rapide
- **gobuster** - Énumération de répertoires et fichiers
- **dirsearch** - Scanner de répertoires et fichiers

### Analyse SSL/TLS
- **sslscan** - Analyse SSL/TLS

### Fichiers sources
- `services/pentest_analyzer.py` - Service principal Pentest

---

## 📊 SEO (Search Engine Optimization)

### Outils CLI
- **lighthouse** - Audit SEO, performance et accessibilité (via npm)
- **curl** - Requêtes HTTP en ligne de commande
- **wget** - Téléchargement de fichiers HTTP/HTTPS

### Modules Python
- **beautifulsoup4** - Parsing HTML
- **requests** - Requêtes HTTP
- **lxml** - Parser XML/HTML rapide

### Fichiers sources
- `services/seo_analyzer.py` - Service principal SEO
- `services/technical_analyzer.py` - Utilise aussi Lighthouse via npx

---

## 👥 Social OSINT

### Outils CLI
- **sherlock** - Recherche de profils sur réseaux sociaux
- **maigret** - Recherche de profils sur réseaux sociaux (1000+ sites)

### Modules Python
- **social-analyzer** - Module Python pour recherche de profils sociaux

### Fichiers sources
- `services/osint_analyzer.py` - Utilise ces outils pour la recherche sociale
- `scripts/linux/bookworm/install_social_tools_bookworm.sh` - Script d'installation

---

## 🔧 Technique

### Outils CLI
- **nmap** - Scanner de ports et services réseau (utilisé aussi en Pentest)
- **lighthouse** - Audit technique via npx (utilisé aussi en SEO)

### Modules Python
- **whois** - Requêtes WHOIS
- **dns.resolver** (dnspython) - Requêtes DNS
- **requests** - Requêtes HTTP
- **beautifulsoup4** - Parsing HTML
### Fichiers sources
- `services/technical_analyzer.py` - Service principal technique

---

## 👤 Données personnes / validation des noms

Ces outils et bibliothèques sont utilisés pour extraire et **valider de vrais noms/prénoms** (éviter de stocker des intitulés de boutons, titres de pages, etc. comme "Prenez RDV", "Choisir", "React", …).

### Bibliothèques Python
- **probablepeople** - Détection Person vs Corporation à partir d’une chaîne de caractères
- **nameparser** - Parsing d’un nom complet en composants (prénom, nom, titre…)
- **gender-guesser** - Vérifie que le premier mot est un **prénom connu** (base multi-pays, dont FR)

### Fichiers sources
- `services/name_validator.py` - Règles de validation des noms/prénoms (mots-clés exclus, probablepeople, nameparser, gender-guesser)
- `services/email_analyzer.py` - Extraction de noms depuis les emails avec validation
- `services/unified_scraper.py` - Extraction de personnes depuis les pages web, en s’appuyant sur `name_validator`

---

## 📦 Installation

### Scripts d'installation disponibles

#### Debian Bookworm / RPi (arm64)
- `scripts/linux/bookworm/install_osint_tools_bookworm.sh` - Installation OSINT
- `scripts/linux/bookworm/install_pentest_tools_bookworm.sh` - Installation Pentest
- `scripts/linux/bookworm/install_seo_tools_bookworm.sh` - Installation SEO
- `scripts/linux/bookworm/install_social_tools_bookworm.sh` - Installation Social OSINT

#### Kali Linux (via WSL ou natif)
- `scripts/linux/kali/install_osint_tools_kali.sh` - Wrapper vers Bookworm
- `scripts/linux/kali/install_pentest_tools_kali.sh` - Wrapper vers Bookworm
- `scripts/linux/kali/install_seo_tools_kali.sh` - Wrapper vers Bookworm
- `scripts/linux/kali/install_social_tools_kali.sh` - Wrapper vers Bookworm

#### Installation complète
- `scripts/linux/install_all_tools.sh` - Installation de tous les outils
- `scripts/linux/bookworm/install_all_tools_bookworm.sh` - Installation complète Bookworm
- `scripts/linux/kali/install_all_tools_kali.sh` - Installation complète Kali

### Vérification

Scripts de test disponibles :
- `scripts/linux/test_osint_tools_prod.sh` - Test OSINT
- `scripts/linux/test_pentest_tools_prod.sh` - Test Pentest
- `scripts/linux/test_seo_tools_prod.sh` - Test SEO
- `scripts/linux/test_social_tools_prod.sh` - Test Social OSINT

---

## ✅ Statut de couverture

### OSINT
- ✅ Tous les outils utilisés dans `osint_analyzer.py` sont couverts par les scripts d'installation
- ✅ Scripts mis à jour pour inclure : subfinder, findomain, dnsenum, fierce, testssl.sh, wafw00f, nikto, gobuster, phoneinfoga, metagoofil, exiftool, recon-ng, shodan, censys

### Pentest
- ✅ Tous les outils utilisés dans `pentest_analyzer.py` sont couverts par les scripts d'installation
- ✅ Aucun outil manquant

### SEO
- ✅ Tous les outils utilisés dans `seo_analyzer.py` sont couverts par les scripts d'installation
- ✅ Lighthouse installé via npm

### Social OSINT
- ✅ Tous les outils utilisés sont couverts par les scripts d'installation

### Technique
- ✅ Tous les outils utilisés dans `technical_analyzer.py` sont couverts
- ✅ nmap et lighthouse déjà installés via OSINT/Pentest/SEO

---

## 📝 Notes importantes

1. **Clés API requises** :
   - Shodan CLI nécessite une clé API (gratuite avec limitations)
   - Censys CLI nécessite une clé API (gratuite avec limitations)

2. **Privilèges** :
   - Certains outils nécessitent `sudo` pour l'installation
   - masscan nécessite des privilèges root pour scanner les ports

3. **WSL** :
   - Sur Windows, les outils peuvent être exécutés via WSL (Kali Linux recommandé)
   - Les scripts Kali sont des wrappers vers les scripts Bookworm

4. **Architecture** :
   - Les scripts supportent x86_64 et arm64 (Raspberry Pi)
   - Certains outils (subfinder, findomain) téléchargent les binaires appropriés

5. **Dépendances Python** :
   - Les modules Python (whois, dnspython, social-analyzer) sont installés via pip/pipx
   - Un environnement virtuel est recommandé pour l'isolation

---

## 🔄 Mise à jour

Pour mettre à jour ce document après ajout d'un nouvel outil :

1. Ajouter l'outil dans la section appropriée ci-dessus
2. Vérifier qu'il est installé dans le script d'installation correspondant
3. Mettre à jour la table "Vue d'ensemble" si nécessaire
4. Vérifier le statut de couverture

---

*Dernière mise à jour : 2026-02-24*
