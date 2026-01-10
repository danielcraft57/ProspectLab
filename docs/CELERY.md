# Guide Celery

## Vue d'ensemble

ProspectLab utilise Celery pour executer les taches longues de maniere asynchrone, permettant a l'application Flask de rester reactive.

## Architecture

### Composants

1. **Flask** : Application web principale
2. **Celery Worker** : Execute les taches en arriere-plan
3. **Redis** : Broker de messages entre Flask et Celery
4. **WebSocket** : Communication temps reel pour la progression

### Flux de traitement

```
User -> Flask -> Celery Task (via Redis) -> Celery Worker
                    |                            |
                    v                            v
                WebSocket <- Progress Updates <- Task
```

## Configuration

### Redis

Redis doit etre demarre avant Celery et Flask :

**Windows (Docker) :**
```powershell
.\scripts\windows\start-redis.ps1
```

**Windows (WSL) :**
```powershell
.\scripts\windows\start-redis-wsl.ps1
```

**Linux/Mac :**
```bash
redis-server
```

### Celery Worker

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

### Configuration Celery

Fichier `celery_app.py` :

```python
from celery import Celery
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery = Celery(
    'prospectlab',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Paris',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 heure max par tache
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50
)
```

## Taches disponibles

### analysis_tasks.py

#### analyze_entreprise_task
Analyse un fichier Excel d'entreprises.

**Parametres :**
- `filepath` : Chemin du fichier Excel
- `output_path` : Chemin de sortie (optionnel)
- `max_workers` : Nombre de threads (defaut: 3)
- `delay` : Delai entre requetes (defaut: 2.0)
- `enable_osint` : Activer OSINT (defaut: False)

**Retour :**
```python
{
    'success': True,
    'output_file': None,
    'total_processed': 42,
    'stats': {'inserted': 40, 'duplicates': 2},
    'analysis_id': 123
}
```

### scraping_tasks.py

#### scrape_analysis_task
Scrape toutes les entreprises d'une analyse.

**Parametres :**
- `analysis_id` : ID de l'analyse
- `max_depth` : Profondeur max (defaut: 3)
- `max_workers` : Nombre de threads (defaut: 5)
- `max_time` : Temps max par site (defaut: 300)
- `max_pages` : Pages max par site (defaut: 50)

**Retour :**
```python
{
    'success': True,
    'analysis_id': 123,
    'scraped_count': 40,
    'total_entreprises': 42,
    'stats': {
        'total_emails': 156,
        'total_people': 42,
        'total_phones': 89,
        'total_social_platforms': 67,
        'total_technologies': 234,
        'total_images': 1234
    }
}
```

#### scrape_emails_task
Scrape un site web unique.

**Parametres :**
- `url` : URL du site
- `max_depth` : Profondeur max (defaut: 3)
- `max_workers` : Nombre de threads (defaut: 5)
- `max_time` : Temps max (defaut: 300)
- `max_pages` : Pages max (defaut: 50)
- `entreprise_id` : ID entreprise (optionnel)

### email_tasks.py

#### send_emails_task
Envoie des emails en masse.

**Parametres :**
- `recipients` : Liste des destinataires
- `subject` : Sujet de l'email
- `body` : Corps de l'email
- `template_id` : ID du modele (optionnel)

### technical_analysis_tasks.py

#### technical_analysis_task
Analyse technique d'un site web.

**Parametres :**
- `url` : URL du site
- `entreprise_id` : ID entreprise (optionnel)

### technical_advanced_tasks.py

#### osint_analysis_task
Analyse OSINT d'une personne.

**Parametres :**
- `url` : URL du site
- `entreprise_id` : ID entreprise (optionnel)
- `people_from_scrapers` : Liste de personnes (optionnel)

#### pentest_analysis_task
Analyse Pentest d'un site web.

**Parametres :**
- `url` : URL du site
- `entreprise_id` : ID entreprise (optionnel)

## Suivi de progression

### Depuis Flask

```python
from celery_app import celery
from tasks.analysis_tasks import analyze_entreprise_task

# Lancer la tache
task = analyze_entreprise_task.delay(filepath, output_path)

# Recuperer l'etat
result = celery.AsyncResult(task.id)
state = result.state  # PENDING, PROGRESS, SUCCESS, FAILURE
info = result.info    # Metadonnees (progression, message, etc.)
```

### Depuis WebSocket

```javascript
// Ecouter les mises a jour
socket.on('analysis_progress', function(data) {
    console.log(data.current, '/', data.total);
    console.log(data.percentage, '%');
    console.log(data.message);
});

socket.on('analysis_complete', function(data) {
    console.log('Termine !', data.total_processed, 'entreprises');
});

socket.on('scraping_progress', function(data) {
    console.log('Emails:', data.total_emails);
    console.log('Personnes:', data.total_people);
    console.log('Telephones:', data.total_phones);
});
```

## Gestion des erreurs

### Retry automatique

```python
@celery.task(bind=True, max_retries=3)
def my_task(self, arg):
    try:
        # Code de la tache
        pass
    except Exception as exc:
        # Retry dans 60 secondes
        raise self.retry(exc=exc, countdown=60)
```

### Logs

Tous les logs Celery sont centralises dans `logs/celery.log` avec rotation automatique.

Les logs par tache sont dans :
- `logs/analysis_tasks.log`
- `logs/scraping_tasks.log`
- `logs/email_tasks.log`
- `logs/technical_analysis_tasks.log`
- `logs/technical_advanced_tasks.log`

## Monitoring

### Flower (optionnel)

Flower est une interface web pour monitorer Celery :

```bash
pip install flower
celery -A celery_app flower
```

Accessible sur http://localhost:5555

### Commandes utiles

**Verifier l'etat de Celery :**
```bash
celery -A celery_app inspect active
```

**Voir les taches en attente :**
```bash
celery -A celery_app inspect reserved
```

**Voir les workers actifs :**
```bash
celery -A celery_app inspect stats
```

**Purger toutes les taches :**
```bash
celery -A celery_app purge
```

## Bonnes pratiques

1. **Toujours verifier Redis** avant de lancer Celery
2. **Utiliser des timeouts** pour eviter les taches infinies
3. **Logger abondamment** pour faciliter le debug
4. **Gerer les erreurs** avec retry et fallback
5. **Limiter la memoire** avec `worker_max_tasks_per_child`
6. **Monitorer les performances** avec Flower
7. **Nettoyer les resultats** periodiquement (Redis peut grossir)

## Arret propre

**Windows :**
```powershell
.\scripts\windows\stop-celery.ps1
```

**Ou Ctrl+C** dans le terminal (gestion propre implementee)

**Linux/Mac :**
```bash
# Ctrl+C ou
pkill -f "celery worker"
```

## Troubleshooting

### Celery ne demarre pas
- Verifier que Redis est demarre
- Verifier la connexion Redis dans `config.py`
- Verifier les logs dans `logs/celery.log`

### Taches bloquees
- Verifier les timeouts dans `celery_app.py`
- Purger les taches avec `celery -A celery_app purge`
- Redemarrer Celery

### Performances lentes
- Augmenter `worker_prefetch_multiplier`
- Augmenter le nombre de workers
- Optimiser les taches (moins de requetes HTTP, etc.)

## Voir aussi

- [Architecture](architecture/ARCHITECTURE.md)
- [WebSocket](techniques/WEBSOCKET.md)
- [Scraping](SCRAPING.md)

