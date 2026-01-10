# Architecture ProspectLab

## Vue d'ensemble

ProspectLab utilise une architecture modulaire avec Flask, Celery et WebSockets pour offrir une expérience utilisateur réactive et performante.

## Structure du projet

```
prospectlab/
├── app.py                 # Application Flask principale (ancienne version)
├── app_new.py             # Application Flask refactorisée (nouvelle version)
├── app_old.py             # Sauvegarde de l'ancienne version
├── celery_app.py          # Configuration Celery
├── config.py              # Configuration de l'application
├── routes/                # Blueprints Flask
│   ├── __init__.py
│   ├── main.py            # Routes principales (pages HTML)
│   ├── api.py             # Routes API REST
│   ├── upload.py          # Routes d'upload de fichiers
│   └── websocket_handlers.py  # Handlers WebSocket
├── tasks/                 # Tâches Celery
│   ├── __init__.py
│   ├── analysis_tasks.py  # Tâches d'analyse d'entreprises
│   ├── scraping_tasks.py  # Tâches de scraping
│   └── technical_analysis_tasks.py  # Tâches d'analyses techniques
├── services/              # Services métier
│   ├── database.py
│   ├── entreprise_analyzer.py
│   ├── unified_scraper.py
│   └── ...
├── utils/                 # Utilitaires
│   ├── __init__.py
│   └── helpers.py         # Fonctions utilitaires
└── templates/             # Templates HTML
```

## Composants principaux

### 1. Application Flask (app_new.py)

Point d'entrée principal de l'application. Initialise Flask, Celery et SocketIO, et enregistre les blueprints.

**Fonctionnalités :**
- Configuration de l'application Flask
- Initialisation de Celery pour les tâches asynchrones
- Configuration de SocketIO pour les WebSockets
- Enregistrement des blueprints

### 2. Blueprints Flask (routes/)

Les blueprints organisent les routes par domaine fonctionnel :

#### routes/main.py
Routes principales qui affichent les pages HTML :
- `/` - Redirection vers le dashboard
- `/dashboard` - Dashboard avec statistiques
- `/entreprises` - Liste des entreprises
- `/entreprise/<id>` - Détail d'une entreprise
- `/analyses-techniques` - Liste des analyses techniques
- `/analyses-osint` - Liste des analyses OSINT
- `/analyses-pentest` - Liste des analyses Pentest
- `/carte-entreprises` - Carte géographique des entreprises

#### routes/api.py
Routes API REST pour les données :
- `/api/statistics` - Statistiques globales
- `/api/analyses` - Liste des analyses
- `/api/entreprises` - Liste des entreprises avec filtres
- `/api/entreprise/<id>` - Détails d'une entreprise
- `/api/entreprise/<id>/tags` - Gestion des tags
- `/api/entreprise/<id>/notes` - Gestion des notes
- `/api/entreprise/<id>/favori` - Basculer le statut favori
- `/api/secteurs` - Liste des secteurs

#### routes/upload.py
Routes pour l'upload et la prévisualisation de fichiers :
- `/upload` - Formulaire d'upload
- `/preview/<filename>` - Prévisualisation du fichier
- `/api/upload` - API d'upload (JSON)
- `/analyze/<filename>` - Démarrage de l'analyse

#### routes/websocket_handlers.py
Handlers WebSocket pour les mises à jour en temps réel :
- `start_analysis` - Démarre une analyse d'entreprises
- `stop_analysis` - Arrête une analyse en cours
- `start_scraping` - Démarre un scraping d'emails
- `stop_scraping` - Arrête un scraping en cours

### 3. Tâches Celery (tasks/)

Les tâches Celery exécutent les opérations longues de manière asynchrone :

#### tasks/analysis_tasks.py
- `analyze_entreprise_task` - Analyse un fichier Excel d'entreprises

#### tasks/scraping_tasks.py
- `scrape_emails_task` - Scrape les emails d'un site web

#### tasks/technical_analysis_tasks.py
- `technical_analysis_task` - Analyse technique d'un site
- `osint_analysis_task` - Analyse OSINT d'un site
- `pentest_analysis_task` - Analyse Pentest d'un site

### 4. Utilitaires (utils/)

Fonctions utilitaires réutilisables :
- `helpers.py` - Fonctions d'aide (validation de fichiers, émission WebSocket sécurisée, etc.)

## Flux de données

### Analyse d'entreprises

1. **Upload du fichier** : L'utilisateur upload un fichier Excel via `/upload`
2. **Prévisualisation** : Le fichier est validé et prévisualisé
3. **Démarrage de l'analyse** : Le client WebSocket émet `start_analysis`
4. **Tâche Celery** : Une tâche Celery est lancée pour analyser les entreprises
5. **Mises à jour en temps réel** : La progression est envoyée via WebSocket
6. **Résultat** : Le fichier analysé est disponible dans `/exports`

### Scraping d'emails

1. **Démarrage** : Le client WebSocket émet `start_scraping` avec l'URL
2. **Tâche Celery** : Une tâche Celery scrape le site web
3. **Mises à jour** : Les emails trouvés sont envoyés en temps réel
4. **Résultat** : Les résultats sont sauvegardés en base de données

## Avantages de cette architecture

### 1. Modularité
- Code organisé par domaine fonctionnel
- Facilite la maintenance et les tests
- Permet le développement en parallèle

### 2. Performance
- Tâches longues exécutées en arrière-plan (Celery)
- Application Flask reste réactive
- Scalabilité horizontale possible

### 3. Expérience utilisateur
- Mises à jour en temps réel via WebSockets
- Pas de blocage de l'interface
- Feedback immédiat sur la progression

### 4. Maintenabilité
- Code bien documenté avec docstrings
- Séparation des responsabilités
- Facilite l'ajout de nouvelles fonctionnalités

## Déploiement

### Développement local

1. **Démarrer Redis** (nécessaire pour Celery) :
```bash
redis-server
```

2. **Démarrer Celery** (dans un terminal séparé) :
```bash
celery -A celery_app worker --loglevel=info
```

3. **Démarrer l'application Flask** :
```bash
python app_new.py
```

### Production

Pour la production, utilisez un serveur WSGI comme Gunicorn avec SocketIO :

```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app_new:app
```

Et démarrez Celery comme service système.

## Migration depuis l'ancienne version

L'ancienne version (`app.py`) est toujours disponible pour compatibilité. Pour migrer :

1. Testez `app_new.py` en développement
2. Migrez progressivement les routes restantes vers les blueprints
3. Une fois tout migré, renommez `app_new.py` en `app.py`

## Prochaines étapes

- [ ] Migrer toutes les routes restantes vers les blueprints
- [ ] Ajouter des tests unitaires pour les blueprints
- [ ] Ajouter des tests d'intégration pour les tâches Celery
- [ ] Documenter les endpoints API avec Swagger/OpenAPI
- [ ] Ajouter la gestion d'erreurs centralisée
- [ ] Implémenter la mise en cache avec Redis

