# Guide de migration vers la nouvelle architecture

## Vue d'ensemble

La nouvelle architecture de ProspectLab utilise des blueprints Flask et Celery pour améliorer la modularité et les performances. Ce guide explique comment migrer depuis l'ancienne version.

## Changements principaux

### 1. Structure modulaire

Les routes sont maintenant organisées en blueprints :
- `routes/main.py` - Routes principales
- `routes/api.py` - Routes API REST
- `routes/upload.py` - Routes d'upload
- `routes/websocket_handlers.py` - Handlers WebSocket

### 2. Tâches asynchrones avec Celery

Les opérations longues (scraping, analyses) sont maintenant exécutées via Celery :
- `tasks/analysis_tasks.py` - Analyse d'entreprises
- `tasks/scraping_tasks.py` - Scraping d'emails
- `tasks/technical_analysis_tasks.py` - Analyses techniques

### 3. Configuration

Nouvelles variables d'environnement pour Celery :
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Migration étape par étape

### Étape 1 : Installation des dépendances

```bash
pip install -r requirements.txt
```

Les nouvelles dépendances incluent :
- `celery==5.3.4`
- `redis==5.0.1`

### Étape 2 : Configuration Redis

Redis doit être installé et démarré. Voir la section installation dans le README.

### Étape 3 : Test de la nouvelle architecture

1. Démarrer Redis
2. Démarrer Celery dans un terminal séparé :
   ```bash
   celery -A celery_app worker --loglevel=info
   ```
3. Démarrer l'application avec la nouvelle architecture :
   ```bash
   python app_new.py
   ```

### Étape 4 : Migration progressive

L'ancienne version (`app.py`) reste disponible pour compatibilité. Vous pouvez :
1. Tester `app_new.py` en parallèle
2. Migrer progressivement les routes restantes
3. Une fois tout testé, remplacer `app.py` par `app_new.py`

## Routes migrées

### Routes principales (routes/main.py)
- ✅ `/` - Redirection dashboard
- ✅ `/dashboard` - Dashboard
- ✅ `/entreprises` - Liste entreprises
- ✅ `/entreprise/<id>` - Détail entreprise
- ✅ `/analyses-techniques` - Liste analyses techniques
- ✅ `/analyses-osint` - Liste analyses OSINT
- ✅ `/analyses-pentest` - Liste analyses Pentest
- ✅ `/carte-entreprises` - Carte entreprises
- ✅ `/analyse-technique/<id>` - Détail analyse technique

### Routes API (routes/api.py)
- ✅ `/api/statistics` - Statistiques
- ✅ `/api/analyses` - Liste analyses
- ✅ `/api/entreprises` - Liste entreprises
- ✅ `/api/entreprise/<id>` - Détail entreprise
- ✅ `/api/entreprise/<id>/tags` - Gestion tags
- ✅ `/api/entreprise/<id>/notes` - Gestion notes
- ✅ `/api/entreprise/<id>/favori` - Favori
- ✅ `/api/secteurs` - Liste secteurs

### Routes upload (routes/upload.py)
- ✅ `/upload` - Upload fichier
- ✅ `/preview/<filename>` - Prévisualisation
- ✅ `/api/upload` - API upload
- ✅ `/analyze/<filename>` - Démarrage analyse

### Handlers WebSocket (routes/websocket_handlers.py)
- ✅ `start_analysis` - Démarrage analyse
- ✅ `stop_analysis` - Arrêt analyse
- ✅ `start_scraping` - Démarrage scraping
- ✅ `stop_scraping` - Arrêt scraping

## Routes à migrer

Les routes suivantes sont encore dans `app.py` et doivent être migrées :
- Routes d'export (`/export/<format>`, `/api/export/<format>`)
- Routes de templates (`/templates`, `/api/templates`)
- Routes d'envoi d'emails (`/send-emails`)
- Routes de scraping (`/scrape-emails`, `/scrapers`, etc.)
- Routes d'analyses techniques (`/api/analyses-techniques`, etc.)
- Routes OSINT/Pentest (`/api/analyses-osint`, `/api/analyses-pentest`, etc.)

## Avantages de la migration

### Performance
- Tâches longues exécutées en arrière-plan
- Application Flask reste réactive
- Pas de blocage lors des analyses

### Maintenabilité
- Code mieux organisé
- Facilite les tests
- Ajout de nouvelles fonctionnalités plus simple

### Scalabilité
- Possibilité de scaler Celery indépendamment
- Distribution des tâches sur plusieurs workers
- Meilleure gestion de la charge

## Dépannage

### Erreur "Connection refused" pour Redis
- Vérifiez que Redis est démarré : `redis-cli ping` doit retourner `PONG`
- Vérifiez l'URL dans `config.py` : `CELERY_BROKER_URL`

### Tâches Celery ne se lancent pas
- Vérifiez que le worker Celery est démarré
- Vérifiez les logs du worker pour les erreurs
- Vérifiez que Redis est accessible

### WebSockets ne fonctionnent pas
- Vérifiez que SocketIO est correctement configuré
- Vérifiez les logs du serveur pour les erreurs de connexion

## Support

Pour toute question ou problème lors de la migration, consultez :
- [Documentation de l'architecture](ARCHITECTURE.md)
- [Documentation technique](../techniques/)
- Issues sur le dépôt Git

