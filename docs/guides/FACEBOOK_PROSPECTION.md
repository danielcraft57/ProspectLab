# Prospection Facebook (Playwright + Qdrant)

Branche experimentale : retrouver une page Facebook d'un etablissement, scraper des infos utiles, puis echanger en Messenger avec un arbre Q&R vectoriel.

## Topologie

| Role | Machine | Usage ProspectLab |
|------|---------|-------------------|
| Playwright Facebook (recherche, scrape, prospect, Messenger) | **serv1** Windows + SocialDesk | Tous les jobs Playwright via SSH, pour l'instant |
| Celery workers | **serv2** Debian | Workers applicatifs ; **messagerie Facebook dediee prevue plus tard** (pas serv1 en parallele long terme) |

Compte Facebook : **danielcraft** (page DanielCraft + profil perso pour bascule Messenger).

**Recherche / scrape** : execution sur **serv1** via SSH + `prospectlab-facebook-job.mjs` (SocialDesk). Defaut `FACEBOOK_PROSPECTION_RUNNER=remote` et `FACEBOOK_PROSPECTION_REMOTE_HEADLESS=false` pour voir Chrome sur serv1 (RDP).

**Option locale** : `FACEBOOK_PROSPECTION_RUNNER=local` + services Python `services/facebook_prospection/` (dev uniquement).

Orchestration **node15** : Celery ou API declenchent le SSH depuis le Pi (meme cle que audit PDF).

## Cookies (tous les matins)

Le rafraichissement reel des sessions Chrome est deja planifie dans SocialDesk :

- Job `cookies-refresh-danielcraft` — cron `0 5 * * *`
- Etapes `sync-chrome-session.mjs` pour LinkedIn, Facebook et X sur `danielcraft`

ProspectLab ne duplique pas cette logique : une tache Celery Beat **verifie** la session FB sur **serv1** apres 6h30 (Paris) et loggue une alerte si `check-session` echoue. Pas de check Playwright sur serv2 (Debian).

Apres un echec : lancer manuellement sur la machine concernee :

```powershell
cd C:\Users\loicDaniel\Documents\SocialDesk\facebook-playwright
node src/sync-chrome-session.mjs --account=danielcraft
```

Chrome doit etre **ferme** (`requiresChromeClosed: true` sur le job cookies).

## Qdrant (node15)

- URL : `QDRANT_URL=http://node15.lan:6333` (voir aussi `SocialDesk/docs/architecture-qdrant.md`)
- Collection dediee ProspectLab (ne pas melanger avec `socialdesk_messaging`) :
  - `QDRANT_COLLECTION_FACEBOOK_PROSPECTION=prospectlab_facebook_messaging`
  - Vecteurs **768d** (Gemini `text-embedding-004`, aligne SocialDesk)

Types de points (`payload.kind`) :

| kind | Role |
|------|------|
| `intent_def` | Definition d'intent (ex. `pricing_question`) |
| `intent_example` | Exemple de message entrant |
| `intent_reply` | Reponse type a envoyer |
| `faq_snippet` | Info etablissement / offre DanielCraft |

Indexer :

```powershell
python scripts/facebook_prospection/seed_qdrant_collection.py
python scripts/facebook_prospection/seed_qdrant_collection.py --apply

(FAQ source : `scripts/facebook_prospection/qdrant_seed_faq.json`)
```

## Code SocialDesk a reutiliser

Repertoire local : `Documents/SocialDesk/facebook-playwright`

| Module | Fichier | Usage |
|--------|---------|-------|
| Recherche pages | `src/facebook-search.mjs` | `openSearch(page, 'pages', query)` |
| Profil page | `src/engage-page.mjs`, `src/probe-facebook-profile.mjs` | Infos publiques |
| Messenger | `src/messenger-inbox.mjs`, `src/facebook-messenger.mjs` | Inbox + compose |
| Qdrant intents | `socialdesk-core/src/qdrant/store.mjs` | `searchMessagingIntents` (modele a copier cote PL) |

CLI SocialDesk : `facebook-playwright/src/prospectlab-facebook-job.mjs` (JSON stdin/stdout), appele par `scripts/facebook_prospection/run_socialdesk_facebook_remote.py` sur **serv1**.

## Variables d'environnement (ProspectLab)

Voir `env.example` section Facebook prospection.

## UI

Page **Entreprises** : onglet **Facebook** dans la modale fiche (ID visible dans l'onglet Info).

### prospect_flow (serv1)

1. Recherche pages FB avec score nom + **address_hint** (adresse fiche entreprise).
2. Ouvre la meilleure page, **Suivre** (ou dry-run).
3. Ouvre Messenger, tape le message ; envoi seulement si `send: true`.

API : `POST /api/facebook-prospection/entreprise/<id>/prospect` body `{ "send": false, "message_text": "..." }`.

### Tests serv1 (RDP)

```powershell
cd C:\Users\loicDaniel\Documents\SocialDesk\deploy\scripts
.\test_on_serv1.ps1 prospect -Query "Hotel des Ventes de Metz" -AddressHint "43 Rue Dupont des Loges, 57000 Metz"
```

### Tests SSH depuis le PC

```powershell
python scripts/facebook_prospection/test_remote.py prospect --entreprise-id 40
python scripts/facebook_prospection/test_remote.py search "boulangerie metz"
```

Deploy : `scripts/facebook_prospection/deploy_to_serv1.ps1` — index : `scripts/facebook_prospection/README.md`.

## Tables PostgreSQL / SQLite

- `facebook_prospection_jobs` — file de travail
- `facebook_prospection_page_candidates` — resultats recherche
- `facebook_prospection_pages` — fiche FB retenue + JSON scrape
- Colonne **`entreprises.facebook_page_url`** — lien affiche sur la fiche CRM (sync auto apres search / prospect_flow si score >= 0.35)
- **`facebook_prospection_conversations`** + **`facebook_prospection_messages`** — fil Messenger et texte sortant
- Statuts job **`prospect_flow`** : `completed`, **`partial`**, `failed`

API debug : `POST /api/facebook-prospection/search-sync` avec `{ "query": "...", "entreprise_id": 40 }`.
