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

### Comment faire, concrètement (version simple et fiable)

L'idée la plus safe, c'est:

- une machine "centrale" (PC/serveur) qui héberge Redis + PostgreSQL + l'app Flask
- les Raspberry Pi ne font que tourner des workers Celery

Comme ça, tes RPi3 ne stockent rien d'important et si un Pi plante tu ne perds pas tes données.

#### 1) Pré-requis côté machine centrale

- Redis doit être accessible depuis le LAN (port 6379).
- PostgreSQL doit être accessible depuis le LAN (port 5432) si tes tâches l'utilisent directement.
- L'app Flask peut rester sur la machine centrale.

Dans le `.env` de prod (machine centrale), les URLs Celery doivent pointer sur Redis central. Exemple:

```bash
CELERY_BROKER_URL=redis://node12.lan:6379/1
CELERY_RESULT_BACKEND=redis://node12.lan:6379/1
```

Note: `Celery Beat` (les tâches planifiées) doit tourner sur une seule machine. Le plus simple: uniquement sur la machine centrale, pas sur les Raspberry.

**Utiliser le cluster depuis ta machine Windows (app en local, workers sur le cluster)** : voir [UTILISER_CLUSTER_EN_LOCAL.md](../configuration/UTILISER_CLUSTER_EN_LOCAL.md) et le script `scripts/run_local_use_cluster.ps1`.

#### 2) Déployer un worker sur un Raspberry (sans orchestration)

Sur chaque Raspberry Pi (Debian/Raspberry Pi OS), tu fais une install "classique" et tu lances un service systemd.

Variables importantes dans `/opt/prospectlab/.env` sur le Raspberry:

```bash
CELERY_BROKER_URL=redis://node12.lan:6379/1
CELERY_RESULT_BACKEND=redis://node12.lan:6379/1

# Ajuste selon ton Pi3 (souvent 1 ou 2, rarement plus)
CELERY_WORKERS=2
```

Ensuite tu actives un service `systemd` qui démarre un worker.

Option A (simple): un seul worker par Raspberry

- tu installes ProspectLab sur le Pi dans `/opt/prospectlab` (même structure que le serveur central)
- tu réutilises le service `prospectlab-celery.service` décrit dans `docs/configuration/DEPLOIEMENT_PRODUCTION.md`
- tu démarres le service

Option B (plus flexible): plusieurs instances Celery sur le même Raspberry (ex: 2 workers séparés)

Tu peux créer une unité systemd "template" (une seule fois), par exemple:

`/etc/systemd/system/prospectlab-celery@.service`

```ini
[Unit]
Description=ProspectLab Celery Worker (%i)
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment=PATH=/opt/prospectlab/env/bin
EnvironmentFile=/opt/prospectlab/.env

# Nom unique par instance (important)
ExecStart=/opt/prospectlab/env/bin/celery -A celery_app worker --loglevel=info --pool=threads --concurrency=${CELERY_WORKERS} --hostname=worker-%i@%h

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Et ensuite tu démarres des instances, par exemple:

```bash
sudo systemctl daemon-reload
sudo systemctl enable prospectlab-celery@1
sudo systemctl start prospectlab-celery@1
sudo systemctl enable prospectlab-celery@2
sudo systemctl start prospectlab-celery@2
```

Ça te permet d'augmenter/réduire le nombre d'instances sans recopier 15 fichiers.

#### 3) Répartir les tâches (optionnel, quand tu voudras aller plus loin)

Par défaut, si tous les workers écoutent la queue par défaut, Celery répartit la charge tout seul. C'est souvent suffisant pour démarrer.

Si tu veux spécialiser des Raspberry par type de tâches, l'approche la plus propre c'est les queues:

- un worker "scraping" n'écoute que `scraping`
- un worker "osint" n'écoute que `osint`
- etc.

Exemples de démarrage:

```bash
celery -A celery_app worker --loglevel=info --pool=threads --concurrency=2 --hostname=scraping@%h -Q scraping
```

```bash
celery -A celery_app worker --loglevel=info --pool=threads --concurrency=1 --hostname=osint@%h -Q osint
```

Et côté code, tu routes tes tâches vers la bonne queue (par ex. via `task_routes` dans `celery_app.py`). On peut le faire au moment où tu décides vraiment ta stratégie de répartition.

#### 4) Deux points qui évitent 80% des galères

- Un seul `celery beat` au total (sinon tes tâches planifiées partent en double).
- Des noms de workers uniques (`--hostname=...`) pour éviter les collisions quand tu as plusieurs machines.


