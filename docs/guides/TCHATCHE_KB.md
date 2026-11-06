# Tchatche KB et Qdrant (Messenger)

Simulateur client sans Facebook : page **`/tchatche-kb`**. Meme moteur que les suggestions de la messagerie (Qdrant + catalogue intents + variables CRM).

## Qdrant sur node15

| Parametre | Valeur validee (oct. 2026) |
|-----------|---------------------------|
| URL | `http://node15.lan:6333` |
| Collection par defaut | `intents_outbound_commercial` |
| Vecteurs | 384 dimensions, distance Cosine |
| Points (prod) | ~429 (evolue apres sync) |

Collections presentes sur le noeud : `intents_outbound_commercial`, `intents_inbound`, plus d'autres jeux non utilises par ProspectLab.

### Tester avant de modifier le `.env`

Depuis Windows (PowerShell) :

```powershell
Invoke-RestMethod -Uri "http://node15.lan:6333/collections/intents_outbound_commercial" -Method Get
```

Attendu : `status: ok`, `points_count` > 0, `config.params.vectors.size` = 384.

Depuis la racine ProspectLab :

```powershell
$env:QDRANT_URL = 'http://node15.lan:6333'
python scripts/facebook_prospection/seed_qdrant_collection.py
```

Sortie attendue : `"ok": true`, `"collection": "intents_outbound_commercial"`.

Ensuite seulement, dans ton **`.env`** local ou `.env.prod` :

```env
QDRANT_URL=http://node15.lan:6333
FACEBOOK_PROSPECTION_QDRANT_COLLECTION=intents_outbound_commercial
FACEBOOK_PROSPECTION_QDRANT_DIMS=384
```

(Voir aussi `env.example`.)

## Moteur Q/R

1. **Qdrant** : recherche d'intent (patterns / reponses indexees) sur la collection ci-dessus.
2. **API tchatche interne** (optionnel) : si l'URL API catalogue est definie (`VOCALGUARD_URL` dans `.env`, voir `env.example`), ProspectLab appelle `/api/v1/internal/kb/chat` pour les phrases et la persona. Sinon, reponses via catalogue + Qdrant uniquement.
3. **Variables CRM** : memes placeholders que les **emails prospect** (`{{entreprise}}`, `{{performance_score}}`, `{{gemini_pitch}}`, `{{analysis_url}}`, blocs `{{#if_ville}}`, `{#if_performance}`, etc.).
4. **Fil naturel (mode Qdrant seul)** : module `dialogue.py` — embed enrichi (dernier bot + client), penalite si le meme intent revient, pivot `out_qualify_website` -> `out_objection_has_site` sur reponse negative, rotation des variantes `INTENT_TEMPLATES`. Pour une vraie persona, brancher `VOCALGUARD_URL` (API kb/chat).

Sync des nouveaux intents vers Qdrant (depuis le catalogue API) :

```powershell
$env:QDRANT_URL = 'http://node15.lan:6333'
python scripts/facebook_prospection/sync_vocalguard_qdrant.py
```

## UI

| Page | Route | Role |
|------|-------|------|
| Tchatche | `/tchatche-kb` | Sandbox client, debug intent / scores / variables |
| Messagerie | menu Messagerie | Fils sync serv2, bouton **Proposer (KB)** |

Lien direct avec fiche CRM : `/tchatche-kb?entreprise_id=40`

### Parcours tchatche

1. Rechercher une entreprise dans **Contexte CRM** (autocomplete).
2. L'API `GET .../tchatche/entreprise/<id>` charge la fiche, les variables `{{...}}` et 1 a 3 **ouvertures** (`out_presentation` personnalisees).
3. Cliquer **Demarrer avec ce message** : la bulle DanielCraft s'affiche en premier ; tu reponds ensuite **comme le client** dans le composer.
4. Onglet **Variables** : valeurs injectees (memes cles que les emails prospect).

**Ordre obligatoire** : lier une fiche CRM **avant** tout message (UI + API `entreprise_id` requis).

API (authentifie) :

- `GET /api/facebook-prospection/tchatche/status`
- `GET /api/facebook-prospection/tchatche/coverage`
- `GET /api/facebook-prospection/tchatche/entreprise/<id>`
- `POST /api/facebook-prospection/tchatche`
- `GET /api/facebook-prospection/tchatche/entreprises?q=...`

## Depannage

| Symptome | Piste |
|----------|--------|
| Statut Qdrant KO | VPN / LAN, `QDRANT_URL`, pare-feu port 6333 |
| Intent sans phrase | Lancer la sync Qdrant ; verifier le tag dans la collection |
| Variables vides | Lier une fiche entreprise dans le tchatche |
| API tchatche hors ligne | Optionnel : URL API catalogue + jeton interne (`env.example`) |

Doc prospection Facebook : `docs/guides/FACEBOOK_PROSPECTION.md`.

## Revoir les Q/R (questions / reponses)

**Architecture alignee VocalGuard :**

| Composant | Role |
|-----------|------|
| Postgres **`vocalguard`** | Source de verite : `intents`, `intent_patterns`, `intent_responses`, `intent_embeddings` |
| **Qdrant node15** | Collection `intents_outbound_commercial` (point id = `intent_embeddings.id`) |
| **ProspectLab** | Lecture catalogue SQL, tchatche, **CRUD** + re-sync Qdrant au PATCH |

Ce n'est pas la base `prospectlab` (CRM). C'est la **meme BDD que l'app VocalGuard**.

### `.env`

```env
QDRANT_URL=http://node15.lan:6333
VOCALGUARD_DATABASE_URL=postgresql://vocalguard:...@<hote>:5432/vocalguard
VOCALGUARD_KB_PROFILE=outbound_commercial
```

`VOCALGUARD_URL` reste optionnel (persona). Les **phrases** viennent du Postgres des que `VOCALGUARD_DATABASE_URL` est configure.

### CRUD ProspectLab

| Methode | Route |
|---------|-------|
| GET | `/api/facebook-prospection/kb/intents` |
| GET | `/api/facebook-prospection/kb/intents/<tag>` |
| PATCH | `/api/facebook-prospection/kb/intents/<tag>` body `{ "responses": [...], "patterns": [...] }` |

PATCH ecrit Postgres + met a jour Qdrant node15 (meme logique que VocalGuard).

Audit : `python scripts/facebook_prospection/list_kb_coverage.py` ou `GET .../tchatche/coverage`.

`INTENT_TEMPLATES` dans `reply_vars.py` = secours si Postgres injoignable.
