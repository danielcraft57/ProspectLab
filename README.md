# ProspectLab

Application Flask professionnelle pour la prospection et l'analyse approfondie d'entreprises.

## Fonctionnalités principales

- **Import et analyse d'entreprises** : Importez un fichier Excel et analysez automatiquement les sites web des entreprises
- **Scraping complet et unifié** : Extraction automatique d'emails, personnes, téléphones, réseaux sociaux, technologies et images
- **Données OpenGraph multi-pages** : Collecte des métadonnées OG de toutes les pages visitées, affichées dans l'onglet "Pages"
- **Analyse technique avancée** : Détection de frameworks, serveurs, hébergeurs, versions et vulnérabilités
- **Analyse OSINT** : Recherche approfondie sur les responsables (LinkedIn, réseaux sociaux, actualités)
- **Analyse Pentest** : Scan de sécurité et détection de vulnérabilités (nécessite outils externes)
- **Envoi d'emails de prospection** : Campagnes personnalisées avec modèles réutilisables
- **Suivi en temps réel** : WebSocket pour suivre la progression des analyses et scraping
- **Base de données normalisée** : Stockage structuré avec OpenGraph, images, et métadonnées

## Installation

1. Installer les dépendances :
```bash
pip install -r requirements.txt
```

2. Configurer les variables d'environnement :
   
   Copiez le fichier `env.example` en `.env` et configurez les variables :
   ```bash
   cp env.example .env
   ```
   
   Variables principales :
   - **SECRET_KEY** : Clé secrète Flask (générer avec: `python -c "import secrets; print(secrets.token_hex(32))"`)
   - **MAIL_*** : Configuration SMTP pour l'envoi d'emails
   - **SIRENE_API_KEY** : (Optionnel) Clé API pour l'API Sirene (data.gouv.fr)
   - **WSL_DISTRO** : Distribution WSL pour les outils OSINT/Pentest (défaut: kali-linux)
   - **WSL_USER** : Utilisateur WSL (défaut: loupix)
   - **DATABASE_PATH** : (Optionnel) Chemin personnalisé pour la base de données
   
   Voir `env.example` pour la liste complète des variables.

3. Installer et démarrer Redis (nécessaire pour Celery) :
   
   **Option 1 - Avec Docker (recommandé) :**
   ```powershell
   .\scripts\windows\start-redis.ps1
   ```
   
   **Option 2 - Avec WSL :**
   ```powershell
   .\scripts\windows\start-redis-wsl.ps1
   ```
   
   Voir [la documentation des scripts](docs/scripts/SCRIPTS.md) pour plus de détails.

4. Démarrer Celery (dans un terminal séparé) :
   
   **Windows (PowerShell) :**
   ```powershell
   .\scripts\windows\start-celery.ps1
   ```
   
   **Ou manuellement :**
   ```bash
   python run_celery.py
   ```
   
   **Linux/Mac :**
   ```bash
   celery -A celery_app worker --loglevel=info
   ```

5. Lancer l'application :
```bash
python app_new.py
```

L'application sera accessible sur http://localhost:5000

**Note** : L'application utilise Celery pour les tâches asynchrones (analyses, scraping) et WebSocket pour les mises à jour en temps réel. Redis doit être démarré avant de lancer l'application.

## Utilisation

### Import et analyse Excel

1. Allez sur "Importer Excel"
2. Uploadez un fichier Excel avec au minimum les colonnes :
   - `name` : Nom de l'entreprise
   - `website` : URL du site web
   - `category` : Catégorie (optionnel)
   - `address` : Adresse (optionnel)
   - `phone` : Téléphone (optionnel)

3. Prévisualisez les données et vérifiez les avertissements de validation
4. Lancez l'analyse avec les paramètres souhaités :
   - **Nombre de threads** : Traitement parallèle (recommandé : 3-5)
   - **Délai entre requêtes** : Évite les blocages (recommandé : 2 secondes)
   - **Analyse OSINT** : Recherche approfondie sur les responsables (optionnel, ralentit l'analyse)

5. Suivez la progression en temps réel :
   - Barre de progression globale (X / Y entreprises)
   - Statistiques de l'entreprise actuelle
   - Statistiques cumulées globales
   - Analyse des entreprises (extraction des informations de base)
   - Scraping complet (emails, personnes, téléphones, réseaux sociaux, technologies, images, métadonnées OG)
   
6. Redirection automatique vers la liste des entreprises une fois terminé

### Scraping complet d'un site

1. Allez sur "Scraper Emails" ou "Analyse & Scraping"
2. Entrez l'URL du site web à scraper
3. Configurez les paramètres :
   - **Profondeur max** : Nombre de niveaux de navigation (recommandé : 3)
   - **Nombre de threads** : Traitement parallèle (recommandé : 5)
   - **Temps max** : Limite de temps par site en secondes (recommandé : 300)
   - **Pages max** : Limite de pages à scraper (recommandé : 50)

4. Lancez le scraping et suivez la progression en temps réel
5. Consultez les résultats détaillés par catégorie :
   - Emails trouvés
   - Personnes identifiées (noms, titres)
   - Téléphones extraits
   - Réseaux sociaux détectés
   - Technologies utilisées
   - Images du site
   - Métadonnées OpenGraph de toutes les pages visitées (onglet "Pages")

### Envoi d'emails

1. Allez sur "Envoyer Emails"
2. Sélectionnez un modèle (optionnel) ou créez un message personnalisé
3. Entrez les destinataires au format JSON
4. Envoyez les emails

### Gestion de modèles

1. Allez sur "Modèles"
2. Créez, modifiez ou supprimez vos modèles de messages
3. Utilisez les variables {nom}, {entreprise}, {email} pour personnaliser

## Structure du projet

```
prospectlab/
├── app_new.py             # Application Flask principale (architecture moderne)
├── celery_app.py          # Configuration Celery pour les tâches asynchrones
├── run_celery.py          # Wrapper pour lancer Celery avec gestion Ctrl+C
├── config.py              # Configuration centralisée
├── requirements.txt       # Dépendances Python
├── prospectlab.db         # Base de données SQLite (générée automatiquement)
├── docs/                  # Documentation complète
│   ├── INDEX.md           # Index de la documentation
│   ├── architecture/      # Documentation de l'architecture
│   ├── installation/      # Guides d'installation
│   ├── configuration/     # Guides de configuration
│   ├── guides/            # Guides d'utilisation
│   ├── techniques/        # Documentation technique (OSINT, Pentest, WebSocket)
│   └── developpement/     # Notes de développement
├── routes/                # Blueprints Flask (architecture modulaire)
│   ├── main.py            # Routes principales (pages HTML)
│   ├── api.py             # Routes API REST (entreprises, analyses)
│   ├── api_extended.py    # Routes API étendues (scrapers, OSINT, Pentest)
│   ├── upload.py          # Routes d'upload de fichiers
│   ├── other.py           # Routes diverses (download, templates)
│   └── websocket_handlers.py  # Handlers WebSocket (progression temps réel)
├── tasks/                 # Tâches Celery (opérations asynchrones)
│   ├── analysis_tasks.py  # Analyse d'entreprises depuis Excel
│   ├── scraping_tasks.py  # Scraping complet (emails, personnes, phones, etc.)
│   ├── email_tasks.py     # Envoi d'emails en masse
│   └── technical_analysis_tasks.py  # Analyses techniques (standard + avancée)
├── services/              # Services métier (logique métier)
│   ├── database.py        # Gestion base de données (ORM simplifié)
│   ├── entreprise_analyzer.py  # Analyse d'entreprises
│   ├── unified_scraper.py # Scraper unifié (emails, personnes, phones, social, tech, images)
│   ├── email_sender.py    # Envoi d'emails SMTP
│   ├── template_manager.py # Gestion des modèles d'emails
│   ├── technical_analyzer.py  # Analyse technique de sites (standard + avancée)
│   ├── osint_analyzer.py  # Analyse OSINT (recherche responsables)
│   ├── pentest_analyzer.py  # Analyse Pentest (sécurité)
│   └── logging_config.py  # Configuration centralisée des logs
├── utils/                 # Utilitaires
│   └── helpers.py         # Fonctions utilitaires
├── scripts/               # Scripts utilitaires
│   ├── windows/           # Scripts PowerShell (Windows)
│   │   ├── start-redis.ps1      # Démarrer Redis (Docker)
│   │   ├── start-celery.ps1     # Démarrer Celery
│   │   ├── stop-redis.ps1       # Arrêter Redis
│   │   └── stop-celery.ps1      # Arrêter Celery
│   └── linux/             # Scripts Bash (Linux)
│       ├── install_osint_tools.sh   # Installer outils OSINT
│       └── install_pentest_tools.sh # Installer outils Pentest
├── templates/             # Templates HTML (Jinja2)
├── static/                # Ressources statiques
│   ├── css/               # Feuilles de style
│   ├── js/                # Scripts JavaScript
│   └── favicon/           # Favicons
├── logs/                  # Logs de l'application (rotation automatique)
│   ├── prospectlab.log    # Logs Flask
│   ├── celery.log         # Logs Celery
│   ├── analysis_tasks.log # Logs des tâches d'analyse
│   └── scraping_tasks.log # Logs des tâches de scraping
├── uploads/               # Fichiers uploadés (Excel)
└── exports/               # Fichiers exportés (résultats)
```

## Architecture

L'application utilise une architecture moderne et modulaire :

### Backend
- **Flask** : Framework web Python avec architecture Blueprints
- **Celery** : Exécution asynchrone des tâches longues (scraping, analyses)
- **Redis** : Broker de messages pour Celery
- **SQLite** : Base de données normalisée avec tables relationnelles
- **Flask-SocketIO** : Communication bidirectionnelle en temps réel

### Frontend
- **HTML5/CSS3** : Interface responsive et moderne
- **JavaScript vanilla** : Pas de framework lourd, code optimisé
- **Socket.IO client** : Mises à jour en temps réel de la progression
- **Fetch API** : Appels API REST asynchrones

### Flux de traitement
1. **Upload Excel** : Validation et prévisualisation
2. **Analyse entreprises** : Extraction informations de base (tâche Celery)
3. **Scraping complet** : Extraction détaillée (tâche Celery séparée)
4. **Mise à jour temps réel** : WebSocket pour suivre la progression
5. **Stockage BDD** : Sauvegarde normalisée avec relations
6. **Affichage résultats** : Interface interactive avec modals

### Logs centralisés
Tous les logs sont centralisés dans le dossier `logs/` avec rotation automatique :
- Logs Flask : `prospectlab.log`
- Logs Celery : `celery.log`
- Logs par tâche : `analysis_tasks.log`, `scraping_tasks.log`, etc.

Pour plus de détails, voir [la documentation de l'architecture](docs/architecture/ARCHITECTURE.md).

## Analyse technique approfondie

L'application extrait également des informations techniques détaillées :

- **Framework et version** : WordPress, Drupal, Joomla, React, Vue.js, Angular
- **Serveur web** : Apache, Nginx, IIS avec versions
- **Versions PHP/ASP.NET** : Depuis les headers HTTP
- **Hébergeur** : Détection automatique (OVH, AWS, Azure, etc.)
- **Dates domaine** : Création et modification via WHOIS
- **IP et DNS** : Adresse IP, name servers
- **Scan nmap** : Optionnel, nécessite nmap installé (voir INSTALLATION.md)

## Analyse OSINT des responsables

L'application peut effectuer une recherche OSINT (Open Source Intelligence) sur les responsables trouvés :

- **LinkedIn** : Recherche de profils LinkedIn publics
- **Réseaux sociaux** : Twitter/X, GitHub (pour profils tech)
- **Contact** : Emails et téléphones trouvés publiquement
- **Actualités** : Mentions dans la presse et articles
- **Registres** : SIREN/SIRET si dirigeant d'entreprise (France)
- **Score de présence** : Évaluation de la présence en ligne

⚠️ **Important** : L'analyse OSINT utilise uniquement des données publiques et respecte la vie privée. Elle peut ralentir l'analyse globale.

## Documentation

La documentation complète est disponible dans le dossier `docs/`. Consultez [docs/INDEX.md](docs/INDEX.md) pour une vue d'ensemble.

### Documentation rapide

- **Installation** : [docs/installation/INSTALLATION.md](docs/installation/INSTALLATION.md)
- **Configuration** : [docs/configuration/CONFIGURATION.md](docs/configuration/CONFIGURATION.md)
- **Interface utilisateur** : [docs/guides/INTERFACE_UTILISATEUR.md](docs/guides/INTERFACE_UTILISATEUR.md) - Guide complet de l'interface
- **Scraping** : [docs/SCRAPING.md](docs/SCRAPING.md) - Documentation du système de scraping unifié
- **Celery** : [docs/CELERY.md](docs/CELERY.md) - Configuration et utilisation de Celery
- **Outils OSINT/Pentest** : [docs/installation/INSTALLATION_TOOLS.md](docs/installation/INSTALLATION_TOOLS.md)
- **Scripts utilitaires** : [docs/scripts/SCRIPTS.md](docs/scripts/SCRIPTS.md) - Scripts PowerShell et Bash

## Notes

- Les analyses peuvent prendre du temps selon le nombre d'entreprises
- Respectez les délais entre requêtes pour éviter les blocages
- Configurez correctement vos paramètres SMTP pour l'envoi d'emails
- Pour l'analyse technique complète, installez les dépendances supplémentaires (voir [docs/installation/INSTALLATION.md](docs/installation/INSTALLATION.md))

