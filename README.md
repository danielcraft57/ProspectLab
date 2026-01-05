# ProspectLab

Application Flask pour la prospection et l'analyse d'entreprises.

## Fonctionnalités

- **Import et analyse d'entreprises** : Importez un fichier Excel et analysez automatiquement les sites web des entreprises
- **Scraping d'emails** : Extrayez automatiquement les adresses email depuis les sites web
- **Envoi d'emails de prospection** : Envoyez des campagnes personnalisées à vos prospects
- **Gestion de modèles** : Créez et gérez vos modèles de messages réutilisables

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

3. Lancer l'application :
```bash
python app.py
```

L'application sera accessible sur http://localhost:5000

## Utilisation

### Import Excel

1. Allez sur "Importer Excel"
2. Uploadez un fichier Excel avec au minimum les colonnes :
   - `name` : Nom de l'entreprise
   - `website` : URL du site web
   - `category` : Catégorie (optionnel)
   - `address_1` : Adresse (optionnel)
   - `phone_number` : Téléphone (optionnel)

3. Prévisualisez les données
4. Lancez l'analyse avec les paramètres souhaités

### Scraping d'emails

1. Allez sur "Scraper Emails"
2. Entrez l'URL du site web à scraper
3. Configurez les paramètres (profondeur, nombre de threads, temps max)
4. Lancez le scraping

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
├── app.py                 # Application Flask principale
├── config.py              # Configuration
├── requirements.txt        # Dépendances Python
├── docs/                   # Documentation
│   ├── installation/       # Guides d'installation
│   ├── configuration/      # Guides de configuration
│   ├── guides/             # Guides d'utilisation
│   ├── techniques/         # Documentation technique
│   └── developpement/      # Notes de développement
├── services/              # Services adaptés des scripts
│   ├── entreprise_analyzer.py
│   ├── email_scraper.py
│   ├── email_sender.py
│   └── template_manager.py
├── templates/             # Templates HTML
├── static/                # CSS et JS
├── uploads/               # Fichiers uploadés
└── exports/               # Fichiers exportés
```

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
- **Outils OSINT/Pentest** : [docs/installation/INSTALLATION_TOOLS.md](docs/installation/INSTALLATION_TOOLS.md)

## Notes

- Les analyses peuvent prendre du temps selon le nombre d'entreprises
- Respectez les délais entre requêtes pour éviter les blocages
- Configurez correctement vos paramètres SMTP pour l'envoi d'emails
- Pour l'analyse technique complète, installez les dépendances supplémentaires (voir [docs/installation/INSTALLATION.md](docs/installation/INSTALLATION.md))

