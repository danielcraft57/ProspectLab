# Utiliser le cluster en local (Windows)

Depuis ta machine Windows, tu peux lancer l’application Flask **en local** tout en envoyant les tâches Celery au **cluster** (Redis sur node15, workers sur node15 / node13 / node14). Aucun worker Celery ne tourne sur ta machine : le cluster exécute les tâches.

## Prérequis

1. **Réseau** : ta machine et le cluster sont sur le même LAN (ex. 192.168.1.x).
2. **Redis sur node15** : accessible depuis le LAN (port 6379), par ex. après avoir exécuté `configure_master_cluster_access.sh` sur node15 (`bind 0.0.0.0`).
3. **PostgreSQL** (optionnel) : si tu veux utiliser la BDD du cluster, Postgres sur node15 doit écouter sur le LAN (port 5432) et `pg_hba.conf` doit autoriser ton réseau (idem via le script de config master).

## Configuration

### Option A : Fichier `.env.cluster` + script (recommandé)

1. Copie le fichier d’exemple :
   ```powershell
   Copy-Item env.cluster.example .env.cluster
   ```
2. Édite `.env.cluster` :
   - `CELERY_BROKER_URL=redis://node15.lan:6379/1`
   - `CELERY_RESULT_BACKEND=redis://node15.lan:6379/1`
   - Si tu utilises la BDD du cluster : décommente et remplis `DATABASE_URL=postgresql://...@node15.lan:5432/prospectlab`
3. Lance l’app avec le script (il charge `.env.cluster` sans modifier ton `.env` habituel) :
   ```powershell
   .\scripts\run_local_use_cluster.ps1
   ```

### Option B : Modifier ton `.env` à la main

Dans ton `.env` :

- `CELERY_BROKER_URL=redis://node15.lan:6379/1`
- `CELERY_RESULT_BACKEND=redis://node15.lan:6379/1`
- Optionnel : `DATABASE_URL=postgresql://...@node15.lan:5432/prospectlab`

Puis lance l’app comme d’habitude (ex. `python app.py`). Pense à remettre `redis://localhost:6379/0` quand tu reviens en mode 100 % local.

## Comportement

- **Flask** tourne sur ta machine (localhost:5000 ou autre).
- Les **tâches Celery** sont envoyées à Redis sur node15 ; les workers du cluster (node15, node13, node14) les exécutent.
- Tu **ne dois pas** lancer de worker Celery en local (`celery -A celery_app worker`), sinon tu aurais des workers en double sur le même broker.
- Pour l'analyse Excel: l'app **copie l'upload vers les noeuds du cluster** (sinon un worker Linux ne peut pas lire un chemin Windows `C:\...`). Configure `CLUSTER_WORKER_NODES` dans `.env.cluster`.

## Vérification rapide

1. Depuis ta machine, test de connexion Redis :
   ```powershell
   python -c "import redis; r=redis.from_url('redis://node15.lan:6379/1'); print(r.ping())"
   ```
   Tu dois voir `True`.

2. Test d’une tâche (depuis le répertoire du projet, avec le même `.env` ou `.env.cluster` que l’app) :
   ```powershell
   python -c "from celery_app import celery_app; r=celery_app.send_task('debug.ping', args=(2,3)); print(r.get(timeout=10))"
   ```
   Tu dois voir `5` (résultat de 2+3). Si ça timeout ou échoue, vérifie que les workers du cluster sont bien démarrés (`celery -A celery_app status` sur un nœud du cluster).

## Voir aussi

- [ARCHITECTURE_DISTRIBUEE_RASPBERRY.md](../developpement/ARCHITECTURE_DISTRIBUEE_RASPBERRY.md) pour l’architecture cluster.
- `scripts/test_cluster_worker.ps1` pour tester les workers sur un nœud du cluster.
