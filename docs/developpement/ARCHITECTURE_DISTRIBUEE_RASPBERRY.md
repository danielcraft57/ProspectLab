## Architecture distribuée avec Raspberry Pi - Notes de travail

Ces notes servent de base pour la mise en place future d'une architecture distribuée de ProspectLab en utilisant un cluster de Raspberry Pi comme workers Celery. Rien n'est figé ici, c'est un espace de réflexion et de préparation.

### Objectifs

- Utiliser plusieurs Raspberry Pi comme **workers Celery** pour exécuter les tâches longues (scraping, analyses, OSINT, etc.).
 - Garder l'**API Flask** et l'interface utilisateur sur une **machine centrale** (PC, serveur ou VPS / serveur dédié).
 - Centraliser les éléments critiques sur une machine suffisamment puissante (CPU/RAM/stockage) :
   - **Base de données PostgreSQL** (par exemple sur un serveur type `node15.lan` ou une VM dédiée)
   - **Redis** (broker de messages, idéalement sur la même machine que la base)
   - **Fichiers d'exports et logs** (disque SSD avec assez d'espace)
 - Utiliser les Raspberry Pi du **cluster local (ex: node10.lan à node15.lan)** principalement comme **workers Celery** connectés au broker/DB distants, et non comme nœuds principaux de production.

### Vue d'ensemble (rappel simplifié)

- **Machine centrale** :
  - Héberge l'application Flask (par exemple `app.py` / `app_new.py` + Gunicorn)
  - Héberge Redis (ou utilise un Redis managé externe)
  - Héberge PostgreSQL (ou utilise un service managé type RDS)
- **Raspberry Pi** :
  - Hébergent des workers Celery
  - Consomment les tâches depuis Redis
  - N'exposent pas d'API publique

Schéma logique simplifié (architecture cible) :

```
Utilisateur (navigateur) -> Nginx (ex: node12.lan, avec HTTPS) -> Serveur central (Flask/Gunicorn + Redis + PostgreSQL)
                                                              ↘
                                                                Workers Celery (Raspberry Pi : node10.lan à node15.lan)
```

### Plan de travail (à faire plus tard)

- [ ] Définir quels Raspberry Pi seront utilisés (modèles, nombre, IP locales)
- [ ] Choisir un schéma de répartition des tâches (par type de tâche ou charge équilibrée)
- [ ] Définir la configuration standard d'un worker Celery sur Raspberry Pi
- [ ] Décider si l'on utilise Docker sur les Raspberry Pi ou une installation Python "classique"
- [ ] Documenter un playbook de déploiement simple (sans orchestration complexe au début)
 - [ ] Garder à l'esprit que certains nœuds du cluster (par exemple `node15.lan`) peuvent être dédiés à d'autres usages (assistant vocal, etc.) et ne pas servir de nœud principal pour ProspectLab.

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
- Pour un environnement de **production**, privilégier un serveur dédié (physique ou VM) avec au moins 2–4 Go de RAM et un stockage SSD pour héberger la base de données, Redis et l'application Flask/Celery, en laissant les Raspberry Pi jouer le rôle de workers supplémentaires.

Ces notes pourront être complétées et détaillées au moment où l'architecture distribuée sera réellement mise en place.


