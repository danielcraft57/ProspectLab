# Prospection Facebook (Playwright + Qdrant)

Branche experimentale : retrouver une page Facebook d'un etablissement, scraper des infos utiles, puis echanger en Messenger avec un arbre Q&R vectoriel.

## Topologie

| Role | Machine | SocialDesk `schedule.json` | Usage ProspectLab |
|------|---------|---------------------------|-------------------|
| Recherche / scrape page | **serv1** (`role: worker`) | CM, keywords, scan groupes | Jobs `search`, `scrape_page` |
| Messenger / tchat | **serv2** (`role: messenger`) | `facebook-messenger-danielcraft`, inbox | Jobs `messenger_inbox`, `send_message` |

Compte Facebook : **danielcraft** (page DanielCraft + profil perso pour bascule Messenger).

Orchestration depuis **node15** (Flask + Celery) via **SSH** (meme cle que audit PDF / landing variants).

## Cookies (tous les matins)

Le rafraichissement reel des sessions Chrome est deja planifie dans SocialDesk :

- Job `cookies-refresh-danielcraft` — cron `0 5 * * *`
- Etapes `sync-chrome-session.mjs` pour LinkedIn, Facebook et X sur `danielcraft`

ProspectLab ne duplique pas cette logique : une tache Celery Beat **verifie** la session FB sur serv1 et serv2 apres 6h30 (Paris) et loggue une alerte si `check-session` echoue.

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
```

## Code SocialDesk a reutiliser

Repertoire local : `Documents/SocialDesk/facebook-playwright`

| Module | Fichier | Usage |
|--------|---------|-------|
| Recherche pages | `src/facebook-search.mjs` | `openSearch(page, 'pages', query)` |
| Profil page | `src/engage-page.mjs`, `src/probe-facebook-profile.mjs` | Infos publiques |
| Messenger | `src/messenger-inbox.mjs`, `src/facebook-messenger.mjs` | Inbox + compose |
| Qdrant intents | `socialdesk-core/src/qdrant/store.mjs` | `searchMessagingIntents` (modele a copier cote PL) |

CLI SocialDesk : `facebook-playwright/src/prospectlab-facebook-job.mjs` (JSON stdin/stdout), appele par `scripts/facebook_prospection/run_socialdesk_facebook_remote.py` sur serv1/serv2.

## Variables d'environnement (ProspectLab)

Voir `env.example` section Facebook prospection.

## UI

Page `/facebook-prospection` : lancer recherche, voir candidats, declencher scrape et dry-run Messenger pour une entreprise.

## Tables PostgreSQL / SQLite

- `facebook_prospection_jobs` — file de travail
- `facebook_prospection_page_candidates` — resultats recherche
- `facebook_prospection_pages` — fiche FB retenue + JSON scrape
- `facebook_prospection_conversations` — thread Messenger
- `facebook_prospection_messages` — historique sync
