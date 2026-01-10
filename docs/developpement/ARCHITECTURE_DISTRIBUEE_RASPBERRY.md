## Architecture distribuée avec Raspberry Pi - Notes de travail

Ces notes servent de base pour la mise en place future d'une architecture distribuée de ProspectLab en utilisant un cluster de Raspberry Pi comme workers Celery. Rien n'est figé ici, c'est un espace de réflexion et de préparation.

### Objectifs

- Utiliser plusieurs Raspberry Pi comme **workers Celery** pour exécuter les tâches longues (scraping, analyses, OSINT, etc.).
- Garder l'**API Flask** et l'interface utilisateur sur une **machine centrale** (PC, serveur ou VPS).
- Centraliser les éléments critiques :
  - Redis (broker de messages)
  - Base de données
  - Fichiers d'exports

### Vue d'ensemble (rappel simplifié)

- **Machine centrale** :
  - Héberge `app_new.py` (Flask + WebSocket)
  - Héberge Redis
  - Accède à la base de données
- **Raspberry Pi** :
  - Hébergent des workers Celery
  - Consomment les tâches depuis Redis
  - N'exposent pas d'API publique

Schéma logique simplifié :

```
Utilisateur -> Flask (app_new.py) -> Redis (broker) -> Workers Celery (Raspberry Pi) -> Base de données
```

### Plan de travail (à faire plus tard)

- [ ] Définir quels Raspberry Pi seront utilisés (modèles, nombre, IP locales)
- [ ] Choisir un schéma de répartition des tâches (par type de tâche ou charge équilibrée)
- [ ] Définir la configuration standard d'un worker Celery sur Raspberry Pi
- [ ] Décider si l'on utilise Docker sur les Raspberry Pi ou une installation Python "classique"
- [ ] Documenter un playbook de déploiement simple (sans orchestration complexe au début)

### Idées pour la répartition des tâches (brouillon)

- Option 1 : Tous les Raspberry Pi peuvent traiter tous les types de tâches (`analysis_tasks`, `scraping_tasks`, `technical_analysis_tasks`).
- Option 2 : Spécialiser certains Raspberry Pi :
  - Raspberry A/B : scraping et analyses simples
  - Raspberry C/D : analyses techniques plus lourdes

La décision sera prise plus tard en fonction des performances observées et des modèles exacts de Raspberry disponibles.

### Points de vigilance à garder en tête

- Ressources limitées (CPU, RAM, stockage) sur les Raspberry Pi.
- Fiabilité du réseau local (coupures possibles, redémarrages).
- Nécessité d'écrire des tâches Celery **idempotentes** pour supporter les relances.
- Éviter de stocker des données critiques sur les cartes SD des Raspberry Pi.

Ces notes pourront être complétées et détaillées au moment où l'architecture distribuée sera réellement mise en place.


