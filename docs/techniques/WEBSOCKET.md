# Communication WebSocket - ProspectLab

## Architecture

L'application utilise **Flask-SocketIO** pour la communication en temps réel entre le frontend et le backend via WebSockets.

### Avantages des WebSockets

- **Mises à jour en temps réel** : Progression de l'analyse affichée en direct
- **Pas de polling** : Pas besoin de requêter régulièrement le serveur
- **Bidirectionnel** : Le serveur peut envoyer des données au client à tout moment
- **Performance** : Moins de charge réseau que les requêtes HTTP répétées

## Structure

### Backend (Flask-SocketIO)

```python
# app.py
from flask_socketio import SocketIO, emit

socketio = SocketIO(app, async_mode='threading')

@socketio.on('start_analysis')
def handle_analysis(data):
    # Traitement dans un thread séparé
    # Émission d'événements via socketio.emit()
```

### Frontend (JavaScript vanilla)

```javascript
// websocket.js
class ProspectLabWebSocket {
    connect() {
        this.socket = io(); // Connexion automatique
    }
    
    startAnalysis(filename, options) {
        this.socket.emit('start_analysis', {...});
    }
}
```

## Événements

### Analyse globale d'entreprises

**Client → Serveur :**
- `start_analysis` : Démarre l'analyse

**Serveur → Client :**
- `analysis_started` : Analyse démarrée
- `analysis_progress` : Progression (current, total, percentage, message)
- `analysis_complete` : Analyse terminée
- `analysis_error` : Erreur globale
- `analysis_error_item` : Erreur pour une entreprise spécifique

### Analyses techniques / SEO / OSINT / Pentest par entreprise

Ces flux sont utilisés principalement par la page **Liste des entreprises** et la **fiche entreprise détaillée**.

#### 1. Analyse technique

**Client → Serveur :**

- `start_technical_analysis`
  - `url` (string) : URL du site à analyser
  - `entreprise_id` (int) : ID de l'entreprise
  - `enable_nmap` (bool, optionnel) : Active le scan réseau

**Serveur → Client :**

- `technical_analysis_started`
  - `message` (string)
  - `task_id` (string)
- `technical_analysis_progress`
  - `progress` (0‑100)
  - `message` (string)
- `technical_analysis_complete`
  - `success` (bool)
  - `analysis_id` (int)
  - `url` (string)
  - `entreprise_id` (int)
  - `results` (dict) : Résultat technique normalisé
- `technical_analysis_error`
  - `error` (string)
  - `entreprise_id` (int)

#### 2. Analyse SEO

**Client → Serveur :**

- `start_seo_analysis`
  - `url` (string)
  - `entreprise_id` (int)
  - `use_lighthouse` (bool) : Active l'audit Lighthouse

**Serveur → Client :**

- `seo_analysis_started`
  - `message` (string)
  - `task_id` (string)
- `seo_analysis_progress`
  - `progress` (0‑100)
  - `message` (string)
- `seo_analysis_complete`
  - `success` (bool)
  - `analysis_id` (int)
  - `url` (string)
  - `entreprise_id` (int)
  - `summary` (dict)
  - `score` (int) : Score SEO global 0‑100
  - `updated` (bool) : Indique si l'analyse a été persistée
- `seo_analysis_error`
  - `error` (string)
  - `entreprise_id` (int)

#### 3. Analyse OSINT

**Client → Serveur :**

- `start_osint_analysis`
  - `url` (string)
  - `entreprise_id` (int)

**Serveur → Client :**

- `osint_analysis_started`
  - `message` (string)
  - `task_id` (string)
- `osint_analysis_progress`
  - `progress` (0‑100)
  - `message` (string)
  - `entreprise_id` (int)
- `osint_analysis_complete`
  - `success` (bool)
  - `analysis_id` (int)
  - `url` (string)
  - `entreprise_id` (int)
  - `summary` (dict)
  - `updated` (bool)
- `osint_analysis_error`
  - `error` (string)
  - `entreprise_id` (int)

#### 4. Analyse Pentest

**Client → Serveur :**

- `start_pentest_analysis`
  - `url` (string)
  - `entreprise_id` (int)
  - `options` (dict) : Options avancées du test

**Serveur → Client :**

- `pentest_analysis_started`
  - `message` (string)
  - `task_id` (string)
- `pentest_analysis_progress`
  - `progress` (0‑100)
  - `message` (string)
  - `entreprise` (string) : Nom de l'entreprise
  - `cumulative_totals` (dict) : Statistiques agrégées
- `pentest_analysis_complete`
  - `success` (bool)
  - `analysis_id` (int)
  - `url` (string)
  - `entreprise_id` (int)
  - `summary` (dict)
  - `risk_score` (int) : Score de risque 0‑100
  - `updated` (bool)
- `pentest_analysis_error`
  - `error` (string)
  - `entreprise_id` (int)

### Scraping d'emails

**Client → Serveur :**
- `start_scraping` : Démarre le scraping

**Serveur → Client :**
- `scraping_started` : Scraping démarré
- `scraping_progress` : Progression (visited, emails, elapsed_time)
- `scraping_complete` : Scraping terminé
- `scraping_error` : Erreur

## Utilisation dans les templates

Les templates utilisent des **Custom Events** pour découpler le code :

```javascript
// Le gestionnaire WebSocket émet des Custom Events
document.addEventListener('analysis:progress', function(e) {
    const data = e.detail;
    // Mettre à jour l'UI
});
```

## Installation

Les dépendances sont dans `requirements.txt` :
- `Flask-SocketIO==5.3.6`
- `eventlet==0.33.3` (ou `threading` mode)

## Mode async

L'application utilise `async_mode='threading'` pour la compatibilité avec tous les systèmes. Pour de meilleures performances, on peut utiliser `eventlet` ou `gevent`.

## Indicateur de connexion

Un indicateur en bas à droite de l'écran affiche le statut de la connexion WebSocket :
- Vert : Connecté
- Rouge : Déconnecté

