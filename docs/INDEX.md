# Documentation ProspectLab

Bienvenue dans la documentation de ProspectLab. Cette documentation est organisée par thème pour faciliter la navigation.

## Démarrage rapide

- [README principal](../README.md) - Vue d'ensemble et installation rapide
- [Guide Celery](CELERY.md) - Configuration et utilisation de Celery pour les taches asynchrones
- [Guide Scraping](SCRAPING.md) - Documentation complete du systeme de scraping unifie
- [Architecture JavaScript modulaire](../static/js/modules/README.md) - Documentation de l'architecture modulaire JS

## Installation

- [Installation générale](installation/INSTALLATION.md) - Guide d'installation et configuration de base
- [Installation des outils](installation/INSTALLATION_TOOLS.md) - Installation des outils OSINT et Pentest
- [Scripts utilitaires](scripts/SCRIPTS.md) - Documentation des scripts PowerShell et Bash
- [Architecture des scripts](scripts/ARCHITECTURE.md) - Organisation et structure des scripts

## Configuration

- [Configuration](configuration/CONFIGURATION.md) - Guide complet de configuration de l'application
- [Environnements et déploiement](configuration/ENVIRONNEMENTS_ET_DEPLOIEMENT.md) - Organisation dev/prod et architecture de déploiement
- [Déploiement en production](configuration/DEPLOIEMENT_PRODUCTION.md) - Guide complet du déploiement en production avec HTTPS

## Guides d'utilisation

- [Interface utilisateur](guides/INTERFACE_UTILISATEUR.md) - Guide complet de l'interface utilisateur
- [**Graph entreprises (liens externes)**](guides/GRAPH_ENTREPRISES.md) - Vue graphe fiches ↔ domaines tiers, API, mini-scrape, BDD
- [Authentification](guides/AUTHENTIFICATION.md) - Guide du système d'authentification et de sécurité
- [Campagnes Email](guides/CAMPAGNES_EMAIL.md) - Guide complet du système de campagnes email avec tracking
- [Profil de pondération (priorité commerciale)](guides/PROFIL_PONDERATION_PRIORITE_COMMERCIALE.md) - À quoi sert le profil de pondération et la vue Top commercial
- [Évolution des métriques (snapshots)](guides/EVOLUTION_METRIQUES_SNAPSHOTS.md) - Historique technique/SEO, comparaison et alertes (API)
- [Critères de recherche Google Maps](guides/CRITERES_RECHERCHE_GOOGLE_MAPS.md) - Guide pour les recherches Google Maps
- [Recommandations AJAX](guides/RECOMMANDATIONS_AJAX.md) - Bonnes pratiques pour l'utilisation d'AJAX

### API publique (`/api/public`)

- [**Guide API publique (référence serveur)**](guides/API_PUBLIQUE.md) - Sommaire, permissions, cache, tableau de tous les endpoints, exemples cURL
- [**Intégration API mobile**](mobile/API_INTEGRATION.md) - Client Expo, résumé des routes, cache applicatif, variables d'environnement  
  → Menu complet mobile : [mobile/INDEX.md](mobile/INDEX.md)

## Mobile

- [Documentation mobile](mobile/INDEX.md) - Architecture, OCR, integration API, securite et workflow
- [Navigation & headers (mobile)](mobile/NAVIGATION_ET_HEADERS.md) - Retour, titres, tab bar, ergonomie iOS / Material

## Documentation technique

- [Architecture](architecture/ARCHITECTURE.md) - Documentation de l'architecture modulaire backend
- [Architecture JavaScript modulaire](../static/js/modules/README.md) - Documentation de l'architecture modulaire frontend JS
- [Architecture distribuée (cluster / Raspberry Pi)](developpement/ARCHITECTURE_DISTRIBUEE_RASPBERRY.md) - Workers Celery, broker, NFS
- [Migration](architecture/MIGRATION.md) - Guide de migration vers la nouvelle architecture
- [WebSocket](techniques/WEBSOCKET.md) - Documentation sur la communication WebSocket
- [Outils OSINT](techniques/OSINT_TOOLS.md) - Guide des outils OSINT disponibles
- [Outils Pentest](techniques/PENTEST_TOOLS.md) - Guide des outils de test de pénétration

## Développement

- [Améliorations](developpement/AMELIORATIONS.md) - Liste des améliorations possibles
- [Améliorations Temps Réel](developpement/AMELIORATIONS_TEMPS_REEL.md) - Améliorations du système de scraping et d'analyse technique en temps réel
- [Séparation des Scripts](developpement/SEPARATION_SCRIPTS.md) - Refactorisation des scripts JavaScript inline vers des fichiers externes
- [Analyse des emails pendant le scraping](developpement/ANALYSE_EMAILS_SCRAPING.md) - Implémentation de l'analyse automatique des emails et corrections associées

## Modifications récentes

- [Changelog technique récent](CHANGELOG_RECENT.md) - Résumé des corrections PostgreSQL, modale, templates et déploiement

## Fichiers obsolètes

- [Fichiers obsolètes](FICHIERS_OBSOLETES.md) - Liste des fichiers obsolètes conservés pour référence

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
- **email_templates** : Modeles d'emails (templates HTML / texte stockés en base)
- **campagnes_email** : Campagnes email avec metadonnees
- **emails_envoyes** : Details des emails envoyes avec tracking_token
- **email_tracking_events** : Evenements de tracking (ouvertures, clics)
- **users** : Utilisateurs avec authentification (username, email, password_hash, is_admin)
- **api_tokens** : Tokens API pour l'acces a l'API publique (token, name, user_id, is_active)
- **external_domains** : Metadonnees par domaine externe (titre, vignette, groupe graphe, mini-scrape)
- **entreprise_external_links** : Liens sortants par entreprise / run de scraper vers un domaine externe
- **external_link_pages** : Pages mini-scrapees liees a un lien ; details en tables filles (OG, images, lieu, telephones)
- **entreprise_touchpoints** : Journal d’interactions prospection (API `/api/entreprise/<id>/touchpoints`) ; création assurée au démarrage via `ensure_entreprise_touchpoints_table()` si la table manquait

Toutes les relations utilisent `ON DELETE CASCADE` pour maintenir l'integrite referentielle.

