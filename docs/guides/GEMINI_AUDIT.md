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
| **503 / high demand** | Fallback modèle sur la **même** clé (`GEMINI_FALLBACK_MODELS`), puis clé suivante. Après N clés 503 d'affilée (`GEMINI_503_MAX_CONSECUTIVE_KEYS`, défaut **2**) : stop précoce + pause courte |
| **401 / 403 invalide** | Clé révoquée jusqu'au redémarrage du process |
| Toutes en pause | Attend `GEMINI_QUOTA_RETRY_MS` puis nouvel essai |

Tester une clé avant de la déployer (sinon elle sera ignorée et le compteur "X clés" sera faux) :

```powershell
python -c "from services.gemini_client import get_gemini_api_keys, gemini_generate_content; print(len(get_gemini_api_keys())); print(gemini_generate_content(parts=[{'text':'Réponds OK'}])[:80])"
```

## File d'attente et concurrence

Deux mécanismes distincts :

1. **File Redis de démarrage** (`services/gemini_queue.py`) : espace les lancements entre entreprises (`GEMINI_JOB_SPACING_SEC`, défaut **90 s**). Évite de poster 20 jobs Vision d'un coup.
2. **Slots concurrents Vision** (`GEMINI_FULL_REPORT_MAX_CONCURRENT`, défaut **2**) : combien de rapports Gemini tournent vraiment en même temps sur le worker.

Avec 4–5 clés valides, **2** slots est un bon compromis. Monter plus haut augmente les 429 RPM / 503.

## Vision plus léger

Par défaut le rapport complet envoie **1** screenshot (desktop), redimensionné (~1280px) et recompressé JPEG. Moins de 503 qu'avec 2–3 images brutes.

```env
GEMINI_VISION_MAX_IMAGES=1
GEMINI_VISION_MAX_WIDTH=1280
GEMINI_VISION_JPEG_QUALITY=72
GEMINI_VISION_COMPRESS=1
```

## Variables utiles

```env
GEMINI_DESIGN_MODEL=gemini-3.8-flash
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODELS=gemini-flash-latest,gemini-3.5-flash
GEMINI_QUOTA_RETRY_MS=35000
GEMINI_QUOTA_RETRY_ROUNDS=3
GEMINI_TRANSIENT_RETRY_MS=25000
GEMINI_503_MAX_CONSECUTIVE_KEYS=2
GEMINI_FULL_REPORT_MAX_CONCURRENT=2
GEMINI_JOB_SPACING_SEC=90
GEMINI_QUEUE_PENDING_TTL_SEC=7200
GEMINI_SLOT_WAIT_SEC=900
```

## 503 vs clés mortes

- **503 / UNAVAILABLE / high demand** : surcharge côté Google sur le modèle, pas une clé HS. Le client bascule d'abord de modèle, puis de compte, puis pause courte.
- **401 / API_KEY_INVALID** : clé mauvaise ou révoquée → ne pas la mettre en prod.
- **429 avec retry ~60s** : limite minute (RPM), la rotation multi-clés absorbe souvent le pic.

Logs utiles : `logs/gemini_full_report_tasks.log` et toasts / journal sur la fiche entreprise.

## Lien avec OSINT / analyses classiques

Gemini ne remplace pas les outils OSINT CLI (theHarvester, dnsrecon, etc.). Il **agrège** les résultats déjà en base (technique, SEO, OSINT, pentest) et commente les screenshots. Pour installer / lister les outils CLI, voir [OSINT_TOOLS.md](../techniques/OSINT_TOOLS.md) et [OUTILS_UTILISES.md](../OUTILS_UTILISES.md).

## API publique

Même contenu que l'onglet **Rapport Gemini** de la fiche entreprise.

- `POST /api/public/entreprises/<id>/gemini-report` — lance la tâche Celery (202 + `task_id` + `poll_url`) ; body optionnel `{ "ensure_screenshots": true }`
- `GET /api/public/entreprises/<id>/gemini-report` — lit le dernier rapport structuré :
  - score global, recommandation de refonte, source, résumé, pitch
  - **indicateurs** modules (`design`, `technical`, `seo`, `osint`, `pentest`) avec score + notes
  - **bons / mauvais points** (`what_works`, `whats_wrong`)
  - actions prioritaires + améliorations
  - `design_analysis` (UX/UI, à garder / à refaire)
  - query optionnelles : `?task_id=` (suivi), `?include_document=true` (Markdown détaillé), `?include_raw=true`

Détail et exemples JSON : [API_PUBLIQUE.md](API_PUBLIQUE.md).
