# Documentation ProspectLab

Bienvenue dans la documentation de ProspectLab. Cette documentation est organisée par thème pour faciliter la navigation.

## Démarrage rapide

- [README principal](../README.md) - Vue d'ensemble et installation rapide
- [Guide Celery](CELERY.md) - Configuration et utilisation de Celery pour les taches asynchrones
- [Guide Scraping](SCRAPING.md) - Documentation complete du systeme de scraping unifie

## Installation

- [Installation générale](installation/INSTALLATION.md) - Guide d'installation et configuration de base
- [Installation des outils](installation/INSTALLATION_TOOLS.md) - Installation des outils OSINT et Pentest
- [Scripts utilitaires](scripts/SCRIPTS.md) - Documentation des scripts PowerShell et Bash
- [Architecture des scripts](scripts/ARCHITECTURE.md) - Organisation et structure des scripts

## Configuration

- [Configuration](configuration/CONFIGURATION.md) - Guide complet de configuration de l'application

## Guides d'utilisation

- [Interface utilisateur](guides/INTERFACE_UTILISATEUR.md) - Guide complet de l'interface utilisateur
- [Critères de recherche Google Maps](guides/CRITERES_RECHERCHE_GOOGLE_MAPS.md) - Guide pour les recherches Google Maps
- [Recommandations AJAX](guides/RECOMMANDATIONS_AJAX.md) - Bonnes pratiques pour l'utilisation d'AJAX

## Documentation technique

- [Architecture](architecture/ARCHITECTURE.md) - Documentation de l'architecture modulaire
- [Architecture distribuée (Raspberry Pi)](developpement/ARCHITECTURE_DISTRIBUEE_RASPBERRY.md) - Utilisation d'un cluster de Raspberry Pi comme workers Celery
- [Migration](architecture/MIGRATION.md) - Guide de migration vers la nouvelle architecture
- [WebSocket](techniques/WEBSOCKET.md) - Documentation sur la communication WebSocket
- [Outils OSINT](techniques/OSINT_TOOLS.md) - Guide des outils OSINT disponibles
- [Outils Pentest](techniques/PENTEST_TOOLS.md) - Guide des outils de test de pénétration

## Développement

- [Améliorations](developpement/AMELIORATIONS.md) - Liste des améliorations possibles
- [Améliorations Temps Réel](developpement/AMELIORATIONS_TEMPS_REEL.md) - Améliorations du système de scraping et d'analyse technique en temps réel
- [Séparation des Scripts](developpement/SEPARATION_SCRIPTS.md) - Refactorisation des scripts JavaScript inline vers des fichiers externes
- [Architecture distribuée Raspberry Pi](developpement/ARCHITECTURE_DISTRIBUEE_RASPBERRY.md) - Notes de travail sur l'utilisation des Raspberry Pi comme workers Celery
- [Analyse des emails pendant le scraping](developpement/ANALYSE_EMAILS_SCRAPING.md) - Implémentation de l'analyse automatique des emails et corrections associées

## Structure de la base de donnees

### Tables principales

- **analyses** : Historique des analyses Excel
- **entreprises** : Informations sur les entreprises
- **scrapers** : Resultats de scraping (totaux et metadonnees)
- **scraper_emails** : Emails extraits avec contexte
- **scraper_people** : Personnes identifiees avec coordonnees
- **scraper_phones** : Telephones extraits avec page source
- **scraper_social** : Profils de reseaux sociaux
- **scraper_technologies** : Technologies detectees
- **scraper_images** : Images du site avec dimensions
- **entreprise_og_data** : Donnees OpenGraph normalisees
- **entreprise_og_images** : Images OpenGraph
- **entreprise_og_videos** : Videos OpenGraph
- **entreprise_og_audios** : Audios OpenGraph
- **entreprise_og_locales** : Locales supportees
- **technical_analyses** : Analyses techniques (frameworks, serveurs)
- **osint_analyses** : Analyses OSINT (recherche responsables)
- **pentest_analyses** : Analyses Pentest (securite)
- **templates** : Modeles d'emails

Toutes les relations utilisent `ON DELETE CASCADE` pour maintenir l'integrite referentielle.

