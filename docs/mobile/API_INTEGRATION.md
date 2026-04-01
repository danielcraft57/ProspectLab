# Intégration API (application mobile)

Ce document décrit comment **l’app mobile** appelle ProspectLab. La **référence complète** des routes, permissions, cache serveur et exemples cURL est le [**Guide de l’API publique**](../guides/API_PUBLIQUE.md).

---

## Base URL et authentification

Base URL

- developpement local : `http://localhost:5000` (prefixe `/api/public`)
- production : `https://prospectlab.danielcraft.fr` (prefixe `/api/public`)

Prefix configurable cote app : `EXPO_PUBLIC_PROSPECTLAB_API_PUBLIC_PREFIX` (defaut `/api/public`).

Auth

- **Recommande** : header `Authorization: Bearer <token>`
- **Evite sur mobile** : `?api_token=<token>` (fuite possible via logs / historique)

Permissions du token (champs en base) : lecture entreprises, emails, statistiques, campagnes. Une route peut exiger une ou plusieurs permissions ; une route peut aussi n'exiger qu'un token valide (ex. metadonnees du token).

## Cache

- **Serveur** : les reponses `GET` de plusieurs routes sont mises en cache en memoire (TTL par route, cle par token + chemin + query). Desactiver : `PUBLIC_API_RESPONSE_CACHE=false`. Voir commentaires dans `config.py`.
- **Application mobile** : cache memoire TTL sur les appels `ProspectLabApi.*` ; `skipCache: true` sur pull-to-refresh / actions explicites ; vidage a la suppression du token.

## Endpoints API publique (resume)

Toutes les URLs ci-dessous sont relatives au prefixe `/api/public`.

### Metadonnees et diagnostics

| Methode | Chemin | Permission | Description |
|--------|--------|------------|-------------|
| GET | `/token/info` | Token valide uniquement | Nom du token, apercu masque, permissions booleennes, `user_id`, `last_used`, `date_creation`. |

### Statistiques

| Methode | Chemin | Permission | Description |
|--------|--------|------------|-------------|
| GET | `/statistics` | `statistics` | Statistiques globales detaillees (dashboard web / export). |
| GET | `/statistics/overview?days=7` | `statistics` | **Vue mobile** : totaux (`total_entreprises`, `total_analyses`, `total_campagnes`, `total_emails`, `emails_envoyes`) et serie `trend_entreprises` (`date`, `count`) sur `days` jours (max 90). |

### Reference / filtres (UI)

| Methode | Chemin | Permission | Description |
|--------|--------|------------|-------------|
| GET | `/entreprises/statuses` | `entreprises` | Statuts entreprise supportes (workflow, webhooks, etc.). |
| GET | `/reference/ciblage` | `entreprises` | Listes distinctes : `secteurs`, `opportunites`, `statuts` (champ entreprise), `tags`. |
| GET | `/reference/ciblage/counts` | `entreprises` | Memes dimensions avec effectifs `{ value, count }` pour facettes / pickers. |
| GET | `/campagnes/statuses` | `campagnes` | Valeurs de statut campagne : `draft`, `scheduled`, `running`, `completed`, `failed`. |

### Entreprises

| Methode | Chemin | Permission | Description |
|--------|--------|------------|-------------|
| GET | `/entreprises` | `entreprises` | Liste paginee (`limit`, `offset`, `search`, `secteur`, `statut`). |
| GET | `/entreprises/<id>` | `entreprises` | Detail d'une entreprise. |
| GET | `/entreprises/by-website?website=...` | `entreprises` | Recherche par site. |
| GET | `/entreprises/by-email?email=...&include_emails=` | `entreprises` + `emails` | Recherche par email. |
| GET | `/entreprises/by-phone?phone=...&include_phones=` | `entreprises` | Recherche par telephone. |
| GET | `/entreprises/<id>/emails` | `entreprises` + `emails` | Emails simplifies. |
| GET | `/entreprises/<id>/emails/all?include_primary=` | `entreprises` + `emails` | Tous les emails enrichis. |
| GET | `/entreprises/<id>/phones?include_primary=` | `entreprises` | **Nouveau** : telephones scrapes + principal. |
| GET | `/entreprises/<id>/campagnes` | `campagnes` | Campagnes liees a l'entreprise. |
| PATCH/POST | `/entreprises/<id>/statut` | `entreprises` | Mise a jour statut (voir doc serveur). |
| POST | `/entreprises/<id>/unsubscribe` | `entreprises` | Evenements de cycle de vie (bounce, reply, etc.) — voir routes dediees dans `api_public.py`. |

### Emails (global)

| Methode | Chemin | Permission | Description |
|--------|--------|------------|-------------|
| GET | `/emails` | `emails` | Liste paginee (`limit`, `offset`, `entreprise_id` optionnel). |

### Analyse site

| Methode | Chemin | Permission | Description |
|--------|--------|------------|-------------|
| GET | `/website-analysis?website=...&full=` | `entreprises` | Rapport SEO / technique / pentest / OSINT (agrege). |
| POST | `/website-analysis` | `entreprises` | Lance les taches d'analyse ; reponse typique `202` avec ids de taches. |

### Campagnes

| Methode | Chemin | Permission | Description |
|--------|--------|------------|-------------|
| GET | `/campagnes` | `campagnes` | Liste (`limit`, `offset`, `statut`, `entreprise_id`). |
| GET | `/campagnes/<id>` | `campagnes` | Detail campagne. |
| GET | `/campagnes/<id>/emails` | `campagnes` | Emails envoys (avec pagination interne / filtres). |
| GET | `/campagnes/<id>/statistics` | `campagnes` | Statistiques de tracking. |

## Client mobile (`ProspectLabApi`)

Fichier : `mobile/src/features/prospectlab/prospectLabApi.ts`.

Methodes principales alignees sur les endpoints : `getTokenInfo`, `getStatistics`, `getStatisticsOverview`, `getReferenceCiblage`, `getReferenceCiblageCounts`, `getCampagneStatuses`, `listEntreprises`, `getEntreprise`, lookups by website/email/phone, `listEntrepriseEmailsAll`, `listEntreprisePhones`, `listCampagnes`, `listCampagnesByEntreprise`, `getWebsiteAnalysis`, `launchWebsiteAnalysis`, etc. Le dernier argument optionnel `{ skipCache?: boolean }` controle le cache client.

## Erreurs habituelles

- `401` : token manquant ou invalide.
- `403` : token valide mais permission manquante pour la route.
- `404` : ressource absente (entreprise, rapport d'analyse, etc.).
- CORS : uniquement pertinent pour **Expo Web** ; l'app native ne depend pas des en-tetes CORS.

## Voir aussi

- [**Guide de l’API publique (serveur)**](../guides/API_PUBLIQUE.md) — tableau unique des endpoints, détail des permissions, cache `PUBLIC_API_RESPONSE_CACHE`, admin tokens  
- [**Index mobile**](INDEX.md) — navigation dans toute la doc mobile  
- [**Index documentation**](../INDEX.md) — menu général du dépôt

## APIs externes (optionnel)

Objectif : enrichir la fiche quand l'OCR est partiel (ex. nom + ville).

Regles : pas de cles en dur dans l'app ; feature flags et timeouts courts.

Exemples envisageables plus tard : annuaires d'entreprises, DNS/WHOIS publics, etc.
