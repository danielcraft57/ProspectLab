# Installation et Configuration - Analyse Technique

## Dépendances supplémentaires

Pour utiliser l'analyse technique complète (nmap, whois, DNS), installez les dépendances suivantes :

### Python packages

```bash
pip install -r requirements.txt
```

Cela installera :
- `python-whois` : Pour les informations WHOIS
- `dnspython` : Pour les requêtes DNS
- `python-nmap` : Pour les scans nmap

### Outils système requis

#### Nmap (pour les scans serveur)

**Windows :**
1. Téléchargez nmap depuis https://nmap.org/download.html
2. Installez-le et ajoutez-le au PATH système
3. Ou utilisez le package via Chocolatey : `choco install nmap`

**Linux :**
```bash
sudo apt-get install nmap  # Debian/Ubuntu
sudo yum install nmap      # CentOS/RHEL
```

**macOS :**
```bash
brew install nmap
```

### Vérification de l'installation

Testez que nmap est installé :
```bash
nmap --version
```

## Utilisation

L'analyse technique est activée par défaut mais **sans le scan nmap** pour des raisons de performance.

### Activer le scan nmap

Pour activer le scan nmap (peut ralentir l'analyse), modifiez dans `services/entreprise_analyzer.py` :

```python
tech_details = self.technical_analyzer.analyze_technical_details(url, enable_nmap=True)
```

**Note :** Le scan nmap peut prendre 30-60 secondes par site et nécessite des privilèges administrateur sur certains systèmes.

## Informations extraites

L'analyse technique extrait :

- **Framework et version** : WordPress, Drupal, Joomla, React, Vue.js, Angular, etc.
- **Serveur web** : Apache, Nginx, IIS avec versions
- **PHP/ASP.NET versions** : Depuis les headers HTTP
- **Hébergeur** : Détection via reverse DNS et name servers
- **Dates** : Création et modification du domaine (WHOIS)
- **IP et DNS** : Adresse IP, name servers
- **Headers HTTP** : Last-Modified, Server, X-Powered-By, etc.
- **Scan nmap** (optionnel) : Ports ouverts, services détectés

## Limitations

- **WHOIS** : Peut être limité par certains registrars
- **Nmap** : Nécessite nmap installé et peut être bloqué par les pare-feu
- **Hébergeur** : Détection basée sur des patterns, peut ne pas détecter tous les hébergeurs

