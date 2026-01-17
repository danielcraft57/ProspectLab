# Améliorations Temps Réel - Scraping et Analyse Technique

Ce document décrit les améliorations apportées au système de scraping et d'analyse technique pour offrir un suivi en temps réel et une meilleure expérience utilisateur.

## Vue d'ensemble

Les améliorations portent sur :
- L'exécution concurrente des analyses techniques pendant le scraping
- L'affichage en temps réel de la progression via WebSocket
- Le scroll automatique vers les sections actives
- La redirection automatique après la fin des processus
- Le nettoyage des logs frontend pour un environnement de production propre

## Exécution Concurrente des Analyses Techniques

### Problème initial

Les analyses techniques étaient lancées séquentiellement après la fin du scraping, ce qui rallongeait considérablement le temps total d'analyse.

### Solution

Les analyses techniques sont maintenant lancées en parallèle dès le début du scraping, permettant une exécution simultanée des deux processus.

**Fichier modifié :** `tasks/scraping_tasks.py`

```python
# Dans scrape_analysis_task
# Lancement de toutes les analyses techniques en parallèle au début
tech_tasks_launched_ids = []
for entreprise in entreprises_avec_site:
    tech_task = technical_analysis_task.delay(analysis_id, entreprise['id'], entreprise['url'])
    tech_tasks_launched_ids.append({
        'task_id': tech_task.id,
        'entreprise_id': entreprise['id'],
        'url': entreprise['url'],
        'nom': entreprise.get('nom', 'N/A')
    })
```

### Configuration Celery

Pour permettre la concurrence sur Windows, le pool Celery a été changé de `solo` à `threads` :

**Fichiers modifiés :**
- `run_celery.py`
- `scripts/windows/start-celery.ps1`
- `services/database/base.py`

```python
# Avant
celery worker --pool=solo

# Après
celery worker --pool=threads
```

## Affichage en Temps Réel

### Monitoring des Tâches Techniques

Un système de monitoring en temps réel a été implémenté pour suivre la progression de chaque analyse technique individuellement.

**Fichier :** `routes/websocket_handlers.py`

Le monitoring calcule la progression globale en faisant la moyenne des progressions individuelles de toutes les tâches techniques :

```python
def monitor_tech_tasks_realtime():
    tech_completed = 0
    total_tech = len(tech_tasks_to_monitor)
    tech_tasks_status = {t['task_id']: {'completed': False, 'last_progress': None, 'current_task_progress': 0} for t in tech_tasks_to_monitor}
    total_progress_sum = 0  # Somme des pourcentages de toutes les tâches
    
    while tech_completed < total_tech:
        for tech_info in tech_tasks_to_monitor:
            # ... monitoring de chaque tâche ...
            if current_state == 'PROGRESS':
                progress_tech = meta_tech.get('progress', 0)
                # Mise à jour de la progression globale
                total_progress_sum -= tech_tasks_status[task_id]['current_task_progress']
                total_progress_sum += progress_tech
                global_progress = int(total_progress_sum / total_tech) if total_tech > 0 else 0
```

### Événements WebSocket

Les événements suivants sont émis pour le frontend :

- `technical_analysis_started` : Démarrage des analyses techniques
- `technical_analysis_progress` : Mise à jour de la progression (avec pourcentage global)
- `technical_analysis_complete` : Fin de toutes les analyses techniques

### Frontend - Affichage de la Progression

**Fichier :** `templates/preview.html`

La barre de progression affiche le pourcentage au centre de la barre de remplissage, et se met à jour en temps réel :

```javascript
window.wsManager.socket.on('technical_analysis_progress', function(data) {
    const percent = typeof data.progress === 'number' ? Math.min(100, Math.max(0, data.progress)) : null;
    if (percent !== null) {
        technicalProgressFill.style.width = percent + '%';
        technicalProgressLabel.textContent = `${percent}%`;
    }
});
```

## Scroll Automatique

Pour améliorer l'expérience utilisateur, un scroll automatique a été ajouté lorsque les processus démarrent.

**Fichier :** `templates/preview.html`

```javascript
// Scroll automatique quand scraping démarre
window.wsManager.socket.on('scraping_started', function(data) {
    // ... affichage du conteneur ...
    setTimeout(() => {
        scrapingProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
});

// Scroll automatique quand analyse technique démarre
window.wsManager.socket.on('technical_analysis_started', function(data) {
    // ... affichage du conteneur ...
    setTimeout(() => {
        technicalProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
});
```

## Redirection Automatique

Une fois le scraping et l'analyse technique terminés, l'utilisateur est automatiquement redirigé vers la page des entreprises.

**Fichier :** `templates/preview.html`

```javascript
let scrapingDone = false;
let technicalDone = false;
let lastScrapingResult = null;

function maybeRedirectAfterAllDone() {
    if (!scrapingDone || !technicalDone) {
        return;
    }
    const analysisId = lastScrapingResult && lastScrapingResult.analysis_id;
    if (analysisId) {
        window.location.href = `/entreprises?analyse_id=${analysisId}`;
    } else {
        window.location.href = '/entreprises';
    }
}
```

Les événements `scraping_complete` et `technical_analysis_complete` mettent à jour les flags et déclenchent la redirection si les deux processus sont terminés.

## Nettoyage des Logs Frontend

Tous les `console.log`, `console.warn` et autres logs de débogage ont été supprimés du frontend pour un environnement de production propre.

**Fichiers nettoyés :**
- `templates/preview.html` : Suppression de tous les `console.log` et `console.warn` liés au monitoring

Les `console.error` sont conservés dans les autres fichiers JS pour le débogage des erreurs en production.

## Résolution de Bugs

### Bug : Working outside of request context

**Problème :** Erreur `RuntimeError: Working outside of request context` lors de l'émission d'événements WebSocket depuis un thread séparé.

**Solution :** Capture de `session_id = request.sid` avant le lancement du thread de monitoring :

```python
# Dans routes/websocket_handlers.py
session_id = request.sid  # Capturé avant le thread

def monitor_campagne_task():
    # Utilisation de session_id au lieu de request.sid
    safe_emit(socketio, 'campagne_progress', data, room=session_id)
```

### Bug : SyntaxError avec nonlocal

**Problème :** `SyntaxError: name 'tech_tasks_monitoring_started' is used prior to nonlocal declaration`

**Solution :** Déplacement de la déclaration `nonlocal` au début de la fonction :

```python
def monitor_scraping():
    nonlocal tech_tasks_to_monitor, tech_tasks_monitoring_started  # Au début
    # ... reste du code ...
```

## Impact sur les Performances

- **Temps d'exécution réduit** : Les analyses techniques s'exécutent en parallèle du scraping au lieu d'attendre sa fin
- **Meilleure réactivité** : L'utilisateur voit la progression en temps réel au lieu d'attendre la fin complète
- **Expérience utilisateur améliorée** : Scroll automatique et redirection pour un flux de travail plus fluide

## Fichiers Modifiés

### Backend
- `tasks/scraping_tasks.py` : Lancement parallèle des analyses techniques
- `routes/websocket_handlers.py` : Monitoring en temps réel et gestion des événements
- `run_celery.py` : Configuration du pool threads
- `scripts/windows/start-celery.ps1` : Configuration du pool threads
- `services/database/base.py` : Configuration du pool threads

### Frontend
- `templates/preview.html` : Scroll automatique, redirection, nettoyage des logs, affichage de la progression

## Tests Recommandés

1. **Test de concurrence** : Vérifier que les analyses techniques se lancent bien en parallèle
2. **Test de progression** : Vérifier que la barre de progression se met à jour en temps réel
3. **Test de scroll** : Vérifier que le scroll automatique fonctionne lors du démarrage
4. **Test de redirection** : Vérifier que la redirection se fait bien après la fin des deux processus
5. **Test sur Windows** : Vérifier que le pool threads fonctionne correctement sur Windows

## Notes Techniques

- Le pool `threads` de Celery permet la concurrence sur Windows, contrairement au pool `solo` qui est séquentiel
- Le calcul de la progression globale prend en compte la progression individuelle de chaque tâche technique
- Le scroll automatique utilise `scrollIntoView` avec un délai de 100ms pour laisser le temps au DOM de se mettre à jour
- La redirection utilise l'`analysis_id` du scraping pour cibler la liste des entreprises de l'analyse en cours

