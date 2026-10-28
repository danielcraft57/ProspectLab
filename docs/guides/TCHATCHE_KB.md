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
3. **Variables CRM** : `{{entreprise}}`, `{{ville}}`, `{{website}}`, etc. — choix d'une fiche dans le tchatche ou `entreprise_id` sur un fil Messenger.

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

API (authentifie) :

- `GET /api/facebook-prospection/tchatche/status`
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
