# Production — PostgreSQL et audits site

Checklist rapide pour `campaigns.danielcraft.fr` (ou équivalent).

## Base de données

```env
APP_ENV=production
DATABASE_URL=postgresql://prospectlab:***@localhost:5432/prospectlab
# Pas de DATABASE_PATH
DATABASE_POOL_MIN=2
DATABASE_POOL_MAX=20
DATABASE_POOL_WAIT_SEC=20
DATABASE_CONNECT_TIMEOUT_SEC=10
DATABASE_STATEMENT_TIMEOUT_MS=600000
```

- Pool activé automatiquement si `APP_ENV=production`.
- Index `idx_entreprises_website_btrim_lower` appliqué au démarrage (`postgresql_tune.py`).
- Recherche entreprise par site : requête ciblée (plus de scan complet de `entreprises`).

## Celery

```env
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_WORKERS=4
CELERY_WORKER_QUEUES=celery,scraping,scraping_interactive,mini_scrape,technical,seo,screenshot,osint,pentest,heavy,website_full,landing
```

Audits API :

| Mode | Files minimales |
|------|-----------------|
| Simple | `technical` |
| Complet | `technical`, `scraping`, `screenshot`, `osint`, `pentest` |

Option : worker dédié `CELERY_WORKER_QUEUE_PRESET=non_scraping` sur un nœud qui écoute surtout `technical`.

## PostgreSQL serveur

Voir `DEPLOIEMENT_PRODUCTION.md` : `max_connections`, `pg_hba.conf` pour workers LAN.

Formule indicative : `(gunicorn × 2) + (nœuds_celery × CELERY_WORKERS × 2) + 10` ≤ `max_connections`.

## SSH vers serv1 (rapport expert)

Prérequis sur le Pi : `openssh-client`, `.env` au format Unix (pas de CRLF), clé `LANDING_VARIANTS_SSH_KEY_PATH` (ex. `/home/pi/.ssh/id_rsa`). Guide : [SSH_SERV1_ET_AUDIT.md](SSH_SERV1_ET_AUDIT.md).

## Audit — fichiers (pas de tables SQL)

- PDF pause / reprise : `exports/audit_reports/<domaine>/pending_*.json`
- Livrables : `exports/audit_reports/<domaine>/audit_complet_*.pdf`
- Rapport expert distant : `C:\Temp\cursor_generated_audit_reports\audit_<domaine>\` sur serv1

## URL publique

Un seul `BASE_URL=https://votre-domaine.fr` dans `.env`, ou `WEBSITE_AUDIT_PUBLIC_BASE_URL` explicite.
