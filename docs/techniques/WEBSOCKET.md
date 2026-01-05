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

### Analyse d'entreprises

**Client → Serveur :**
- `start_analysis` : Démarre l'analyse

**Serveur → Client :**
- `analysis_started` : Analyse démarrée
- `analysis_progress` : Progression (current, total, percentage, message)
- `analysis_complete` : Analyse terminée
- `analysis_error` : Erreur globale
- `analysis_error_item` : Erreur pour une entreprise spécifique

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

