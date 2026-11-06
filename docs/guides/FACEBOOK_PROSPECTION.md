# Prospection Facebook (Playwright + Qdrant)

Branche experimentale : retrouver une page Facebook d'un etablissement, scraper des infos utiles, puis echanger en Messenger avec un arbre Q&R vectoriel.

## Topologie

| Role | Machine | Usage ProspectLab |
|------|---------|-------------------|
| Recherche, scrape, prospect (page + 1er message compose) | **serv1** Windows | SSH PowerShell + Chrome |
| Inbox Messenger (sync, reponses UI, Qdrant) | **serv2** Debian | SSH bash + Playwright headless (meme repo SocialDesk que `messenger-inbox.mjs`) |
| Celery workers ProspectLab | **serv2** (ou node15) | File jobs, pas Chrome CM lourd |

Compte Facebook : **danielcraft** (page DanielCraft + profil perso pour bascule Messenger).

**Recherche / scrape** : execution sur **serv1** via SSH + `prospectlab-facebook-job.mjs` (SocialDesk). Defaut `FACEBOOK_PROSPECTION_RUNNER=remote` et `FACEBOOK_PROSPECTION_REMOTE_HEADLESS=false` pour voir Chrome sur serv1 (RDP).

**Option locale** : `FACEBOOK_PROSPECTION_RUNNER=local` + services Python `services/facebook_prospection/` (dev uniquement).

Orchestration **node15** : Celery ou API declenchent le SSH depuis le Pi (meme cle que audit PDF).

## Cookies (tous les matins)

Meme flux **`sync-chrome-session.mjs`** sur **serv1** (worker SocialDesk 5h) et **serv2** (job `cookies-refresh-danielcraft-serv2` 5h05 + Celery ProspectLab 5h10).

- serv1 : job SocialDesk `cookies-refresh-danielcraft` — Chrome **ferme** avant le cron
- serv2 : profil Chrome local `~/.config/google-chrome` (RDP pi, pas les cookies serv1)
- ProspectLab : tache `facebook_prospection.refresh_cookies` (SSH sync sur serv1 + serv2)
- Verification : `facebook_prospection.check_sessions` a 6h30

ProspectLab ne duplique pas le job LI/X : uniquement Facebook via le wrapper `cookies_refresh`.

Apres un echec **serv1** :

```powershell
cd C:\Users\loicDaniel\Documents\SocialDesk\facebook-playwright
node src/sync-chrome-session.mjs --account=danielcraft
```

Apres un echec **serv2** (cookies propres a serv2, pas serv1) :

```bash
cd ~/Documents/socialdesk/facebook-playwright
node src/sync-chrome-session.mjs --account=danielcraft
```

Chrome doit etre **ferme** (`requiresChromeClosed: true` sur le job cookies).

## Qdrant / KB Messenger (node15)

Index vectoriel partage pour le tchatche et la messagerie :

- URL : `QDRANT_URL=http://node15.lan:6333` (valider avec `seed_qdrant_collection.py` avant prod)
- Collection : `intents_outbound_commercial` par defaut (384d, cosine)
- Reponses : catalogue intents + recherche Qdrant ; API tchatche interne optionnelle (voir `env.example`)

Guide detaille : **`docs/guides/TCHATCHE_KB.md`**.

Tchatche de test (sans Facebook) : page `/tchatche-kb`.

Variables dans les reponses : `{{entreprise}}`, `{{nom}}`, `{{prenom}}`, `{{ville}}`, `{{website}}`, `{{telephone}}`, `{{secteur}}`, `{{metier}}`, plus blocs `{{#if_ville}}...{{/if_ville}}`.

Phrases deja branchees (tchatche / Messenger) : `out_presentation`, `out_qualify_website`, `out_objection_has_site`, `out_who_are_you`, `out_audit_offer`. Le tchatche choisit une fiche CRM ; Messenger reprend `entreprise_id` du fil.

Verifier la collection :

```powershell
python scripts/facebook_prospection/seed_qdrant_collection.py
```

Reindexer apres ajout d'intents :

```powershell
python scripts/facebook_prospection/sync_vocalguard_qdrant.py
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
- **`facebook_prospection_conversations`** + **`facebook_prospection_messages`** — fil Messenger lie a une entreprise (prospect)
- **`facebook_messenger_threads`** + **`facebook_messenger_messages`** — inbox synchronisee (sync serv1) + compteur non lu

Sync : job `messenger_sync` sur **serv2** via SSH. Deploy : `scripts/facebook_prospection/deploy_to_serv2.ps1`.

### Page Messagerie

- Menu **Messagerie** : sync / reponses / Qdrant — jobs Playwright sur **serv2** (pas serv1).
- API : `POST .../conversations/<id>/suggestions`, `POST .../conversations/<id>/reply` body `{ message_text, send }`.
- Qdrant : collection `intents_outbound_commercial` (+ API tchatche optionnelle). Tchatche : `/tchatche-kb`. Voir `docs/guides/TCHATCHE_KB.md`.
- Statuts job **`prospect_flow`** : `completed`, **`partial`**, `failed`

API debug : `POST /api/facebook-prospection/search-sync` avec `{ "query": "...", "entreprise_id": 40 }`.
