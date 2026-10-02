# Audit Gemini (Vision + rapport complet)

ProspectLab utilise l'API Google Gemini pour deux usages principaux :

1. **Rapport d'audit complet** (fiche entreprise / API publique) : synthèse tech, SEO, OSINT, pentest + analyse visuelle des screenshots.
2. **Analyse design / mockups** à partir de captures d'écran.

Les clés et le modèle se configurent uniquement via `.env` / `.env.prod` (jamais dans Git).

## Clés API (rotation multi-comptes)

Plusieurs clés free-tier peuvent tourner en parallèle logique :

```env
GEMINI_API_KEY=...
GEMINI_API_KEY_2=...
GEMINI_API_KEY_3=...
# jusqu'à GEMINI_API_KEY_9
# ou liste CSV :
# GEMINI_API_KEYS=key1,key2,key3
```

Comportement du client (`services/gemini_client.py`) :

| Code / cas | Comportement |
|---|---|
| **429 RPM** (retry court) | Passe à la clé suivante immédiatement |
| **429 RPD** (quota jour réel) | Clé ignorée jusqu'au reset (~minuit Pacific) |
| **503 / high demand** | Passe à la clé suivante (pas d'attente 60s) |
| **401 / 403 invalide** | Clé révoquée jusqu'au redémarrage du process |
| Toutes en pause | Attend `GEMINI_QUOTA_RETRY_MS` puis nouvel essai |

Tester une clé avant de la déployer (sinon elle sera ignorée et le compteur "X clés" sera faux) :

```powershell
python -c "from services.gemini_client import get_gemini_api_keys, gemini_generate_content; print(len(get_gemini_api_keys())); print(gemini_generate_content('Réponds OK', model='gemini-3.8-flash')[:80])"
```

## File d'attente et concurrence

Deux mécanismes distincts :

1. **File Redis de démarrage** (`services/gemini_queue.py`) : espace les lancements entre entreprises (`GEMINI_JOB_SPACING_SEC`, défaut **90 s**). Évite de poster 20 jobs Vision d'un coup.
2. **Slots concurrents Vision** (`GEMINI_FULL_REPORT_MAX_CONCURRENT`, défaut **1**) : combien de rapports Gemini tournent vraiment en même temps sur le worker.

Avec 4–5 clés valides, un `GEMINI_FULL_REPORT_MAX_CONCURRENT=1` reste volontairement prudent : chaque rapport Vision est lourd. Monter à **2** accélère un peu, mais les **503 high demand** Google restent possibles même avec des clés saines.

Variables utiles :

```env
GEMINI_DESIGN_MODEL=gemini-3.8-flash
GEMINI_MODEL=gemini-3.8-flash
GEMINI_QUOTA_RETRY_MS=35000
GEMINI_QUOTA_RETRY_ROUNDS=3
GEMINI_TRANSIENT_RETRY_MS=90000
GEMINI_FULL_REPORT_MAX_CONCURRENT=1
GEMINI_JOB_SPACING_SEC=90
GEMINI_QUEUE_PENDING_TTL_SEC=7200
GEMINI_SLOT_WAIT_SEC=900
```

## 503 vs clés mortes

- **503 / UNAVAILABLE / high demand** : surcharge côté Google sur le modèle, pas une clé HS. La rotation saute de compte en compte ; si tous répondent 503, le job échoue ou attend selon les retries.
- **401 / API_KEY_INVALID** : clé mauvaise ou révoquée → ne pas la mettre en prod.
- **429 avec retry ~60s** : limite minute (RPM), la rotation multi-clés absorbe souvent le pic.

Logs utiles : `logs/gemini_full_report_tasks.log` et toasts / journal sur la fiche entreprise.

## Lien avec OSINT / analyses classiques

Gemini ne remplace pas les outils OSINT CLI (theHarvester, dnsrecon, etc.). Il **agrège** les résultats déjà en base (technique, SEO, OSINT, pentest) et commente les screenshots. Pour installer / lister les outils CLI, voir [OSINT_TOOLS.md](../techniques/OSINT_TOOLS.md) et [OUTILS_UTILISES.md](../OUTILS_UTILISES.md).

## API publique

- `GET /api/public/entreprises/<id>/gemini-report`
- `POST /api/public/entreprises/<id>/gemini-report` (lance la tâche Celery, 202 + `task_id`)

Détail : [API_PUBLIQUE.md](API_PUBLIQUE.md).
