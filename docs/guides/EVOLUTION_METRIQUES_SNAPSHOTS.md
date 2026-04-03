# Snapshots de métriques (avant / après)

Objectif : **Sprint 3 — suivi dans le temps** (base pour re-scans et alertes).

## Principe

À chaque **sauvegarde ou mise à jour** d’une analyse **technique** ou **SEO**, l’application enregistre une ligne dans `entreprise_metric_snapshots` :

- `source` : `technical` ou `seo`
- `analysis_id` : id de l’analyse concernée
- `metrics_json` : extrait des indicateurs (scores, SSL, CMS, etc.)

Les **deux derniers** snapshots d’une même source permettent de calculer des **deltas** et des **alertes** simples (baisse forte de score, SSL invalide, expiration proche, changement de CMS).

## API (authentification requise)

| Méthode | Route | Description |
|--------|--------|-------------|
| GET | `/api/entreprise/<id>/metric-snapshots` | Liste (`?limit=`, `?source=technical\|seo`) |
| GET | `/api/entreprise/<id>/metric-snapshots/compare` | Compare les 2 derniers (`?source=` défaut `technical`) |
| POST | `/api/entreprise/<id>/metric-snapshots/rescan` | Enfile re-scan technique + SEO (JSON optionnel : `run_technical`, `run_seo`, `enable_nmap`, `use_lighthouse`) → **202** + ids Celery |

Réponse `compare` : `current`, `previous`, `deltas`, `alerts` (codes : `ssl_invalid`, `ssl_expired`, `ssl_expiring_soon`, `security_score_drop`, `performance_score_drop`, `seo_score_drop`, `cms_changed`).

## Migration

La table est créée par `init_database` et par `ensure_entreprise_metric_snapshots_table()` au démarrage (`Database()`).

## Suite possible

- UI sur la fiche entreprise (timeline + badge alertes)
- Notifications / file d’alertes globale
- Re-scan planifié : tâche Celery `tasks.metric_rescan_tasks.metric_rescan_entreprise_task` (enqueue technique + SEO, mêmes hooks snapshots)

### Celery (re-scan)

- **Tâche** : `metric_rescan_entreprise_task(entreprise_id, run_technical=True, run_seo=True, enable_nmap=False, use_lighthouse=None)`
- **File** : `celery` (orchestrateur) ; les sous-tâches partent sur `technical` et `seo`.
