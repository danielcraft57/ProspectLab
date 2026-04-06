# Guide de l’API publique ProspectLab

Documentation de référence pour le préfixe **`/api/public`**. Pour l’app mobile (client Expo, cache client, variables d’env), voir aussi [**Intégration API mobile**](../mobile/API_INTEGRATION.md).

---

## Liens connexes

| Document | Contenu |
|----------|---------|
| [Intégration API mobile](../mobile/API_INTEGRATION.md) | Base URL, permissions, tableau des routes côté client, cache applicatif |
| [Index de la documentation](../INDEX.md) | Menu général |
| [Architecture mobile](../mobile/ARCHITECTURE_MOBILE.md) | Couches UI → `ProspectLabApi` |

---

## Vue d’ensemble

L’API publique permet d’accéder aux données d’entreprises, emails, campagnes et statistiques depuis des applications externes, et d’**enregistrer des jetons de notification push** pour les clients mobiles. L’authentification se fait par **token API** (généré côté admin).

---

## Sommaire

1. [Authentification](#authentification)  
2. [Permissions](#permissions)  
3. [Cache des réponses GET](#cache-des-réponses-get)  
4. [Base URL](#base-url)  
5. [Table de référence des endpoints](#table-de-référence-des-endpoints)  
6. [Détail et exemples](#détail-par-domaine)  
7. [Gestion des tokens API (admin)](#gestion-des-tokens-api-admin)  
8. [Codes HTTP et format des réponses](#codes-de-réponse-http)  
9. [Exemples d’intégration](#exemples-dintégration)  
10. [Sécurité et limitations](#sécurité)

---

## Authentification

### Génération d’un token API

Les tokens sont créés par un administrateur (interface dédiée ou API admin).

1. Se connecter en tant qu’administrateur  
2. Utiliser l’interface **Tokens API** ou l’API admin documentée plus bas  
3. **Conserver** le token affiché : il ne sera en général plus montré en clair  

### Utilisation du token

**1. Header `Authorization` (recommandé)**

```http
Authorization: Bearer <votre_token>
```

**2. Paramètre de requête (à éviter sur mobile)**

```text
?api_token=<votre_token>
```

---

## Permissions

Chaque token possède des flags en base (`api_tokens`) :

| Permission API | Champ | Rôle |
|----------------|-------|------|
| Entreprises | `can_read_entreprises` | Listes, détails, recherche, analyse site, téléphones, références ciblage |
| Suppression entreprises | `can_delete_entreprises` | Permet la suppression PERMANENTE d’entreprises (côté API publique) |
| Emails | `can_read_emails` | Emails (y compris routes combinées avec entreprises) |
| Statistiques | `can_read_statistics` | `/statistics`, `/statistics/overview` |
| Campagnes | `can_read_campagnes` | Campagnes, emails / stats de campagne, statuts campagne |

Certaines routes exigent **plusieurs** permissions (ex. `by-email` avec `include_emails`). La route **`GET /token/info`** exige seulement un **token valide** et permet de vérifier les permissions sans appeler les données métier.

En cas de permission manquante, la réponse est **`403 Forbidden`** avec un message explicite.

---

## Cache des réponses GET

Les réponses **GET** de nombreuses routes sont mises en **cache mémoire** côté serveur (clé : identifiant du token + chemin + query string ; TTL par route).

- **Désactiver** : variable d’environnement `PUBLIC_API_RESPONSE_CACHE=false`  
- **Paramètres** : voir commentaires en fin de `config.py` (`PUBLIC_API_CACHE_TTL_DEFAULT`, `PUBLIC_API_CACHE_MAX_ENTRIES`)

Les clients doivent accepter un léger délai de cohérence ou prévoir un **rafraîchissement forcé** côté UI si besoin. L’app mobile gère un cache client distinct (voir [API_INTEGRATION.md](../mobile/API_INTEGRATION.md)).

---

## Base URL

```text
https://<votre-domaine>/api/public
```

Exemples (adapter le domaine) :

- Développement local : `http://localhost:5000/api/public`  
- Production : `https://<votre-domaine>/api/public`  

Tous les chemins ci‑dessous sont **relatifs** à `/api/public`.

---

## Table de référence des endpoints

| Méthode | Chemin | Permission(s) | Description |
|---------|--------|---------------|-------------|
| **GET** | `/token/info` | Token valide | Métadonnées du token (nom, aperçu masqué, permissions, dates) |
| **GET** | `/statistics` | Statistiques | Statistiques globales détaillées |
| **GET** | `/statistics/overview` | Statistiques | Vue compacte + série journalière (`?days=`, max 90) |
| **GET** | `/reference/ciblage` | Entreprises | Listes secteurs, opportunités, statuts entreprise, tags |
| **GET** | `/reference/ciblage/counts` | Entreprises | Idem avec effectifs `{ value, count }` |
| **GET** | `/entreprises/statuses` | Entreprises | Statuts entreprise supportés (pipeline, délivrabilité) |
| **GET** | `/campagnes/statuses` | Campagnes | `draft`, `scheduled`, `running`, `completed`, `failed` |
| **GET** | `/entreprises` | Entreprises | Liste paginée (`limit`, `offset`, `secteur`, `statut`, `search`) |
| **GET** | `/entreprises/<id>` | Entreprises | Détail entreprise |
| **DELETE** | `/entreprises/<id>` | Entreprises + `entreprises_delete` | Suppression PERMANENTE (cascades de données liées incluses) |
| **GET** | `/entreprises/by-website` | Entreprises | Recherche par site (`website`) |
| **GET** | `/entreprises/by-email` | Entreprises + emails | Recherche par email (`include_emails`) |
| **GET** | `/entreprises/by-phone` | Entreprises | Recherche par téléphone (`include_phones`) |
| **PATCH**/**POST** | `/entreprises/<id>/statut` | Entreprises | Mise à jour du statut (+ `note` optionnelle) |
| **POST** | `/entreprises/<id>/unsubscribe` | Entreprises | Raccourcis événements (voir section dédiée) |
| **POST** | `/entreprises/<id>/negative-reply` | Entreprises | |
| **POST** | `/entreprises/<id>/bounce` | Entreprises | |
| **POST** | `/entreprises/<id>/positive-reply` | Entreprises | |
| **POST** | `/entreprises/<id>/spam-complaint` | Entreprises | |
| **POST** | `/entreprises/<id>/do-not-contact` | Entreprises | |
| **POST** | `/entreprises/<id>/callback` | Entreprises | |
| **GET** | `/entreprises/<id>/emails` | Entreprises + emails | Emails format court |
| **GET** | `/entreprises/<id>/emails/all` | Entreprises + emails | Emails enrichis (`include_primary`) |
| **GET** | `/entreprises/<id>/phones` | Entreprises | Téléphones scrapés + principal (`include_primary`) |
| **GET** | `/entreprises/<id>/campagnes` | Campagnes | Campagnes liées à l’entreprise |
| **GET** | `/emails` | Emails | Liste globale (`limit`, `offset`, `entreprise_id`) |
| **GET** | `/campagnes` | Campagnes | Liste (`limit`, `offset`, `statut`, `entreprise_id`) |
| **GET** | `/campagnes/<id>` | Campagnes | Détail campagne |
| **GET** | `/campagnes/<id>/emails` | Campagnes | Emails envoyés |
| **GET** | `/campagnes/<id>/statistics` | Campagnes | Tracking (ouvertures, clics) |
| **GET** | `/website-analysis` | Entreprises | Rapport agrégé (`website`, `full`) |
| **POST** | `/website-analysis` | Entreprises | Lance les analyses asynchrones (réponse typique **202**) |
| **POST** | `/push/register` | Token valide | Enregistre un jeton Expo Push (corps JSON, voir ci‑dessous) |
| **DELETE** | `/push/register` | Token valide | Retire un jeton Expo Push enregistré |

---

## Détail par domaine

### Métadonnées du token

**GET** `/token/info`

Réponse type :

```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Token mobile",
    "token_preview": "AbCdEf1234…",
    "app_url": null,
    "user_id": null,
    "permissions": {
      "entreprises": true,
      "entreprises_delete": true,
      "emails": true,
      "statistics": true,
      "campagnes": true
    },
    "last_used": "2026-04-01 12:00:00",
    "date_creation": "2026-01-15 10:00:00"
  }
}
```

La **valeur complète** du secret n’est **pas** renvoyée.

---

### Statistiques

**GET** `/statistics` — jeu complet (répartition par statut, secteur, campagnes récentes, etc.).

**GET** `/statistics/overview?days=7` — optimisé pour tableaux de bord et apps mobiles :

- `total_entreprises`, `total_analyses`, `total_campagnes`, `total_emails` (lignes `scraper_emails` non vides), `emails_envoyes`  
- `trend_entreprises` : `[{ "date": "YYYY-MM-DD", "count": n }, ...]` sur `days` jours (max **90**)

---

### Référence et filtres UI

- **`GET /entreprises/statuses`** — liste des statuts entreprise (pipeline + délivrabilité).  
- **`GET /reference/ciblage`** — `secteurs`, `opportunites`, `statuts`, `tags` (valeurs distinctes).  
- **`GET /reference/ciblage/counts`** — mêmes dimensions avec comptages pour facettes.  
- **`GET /campagnes/statuses`** — valeurs de `statut` pour les campagnes email.

---

### Entreprises : liste et recherche

**GET** `/entreprises`

Paramètres : `limit` (défaut 100, max 1000), `offset`, `secteur`, `statut`, `search`.  
Pour `statut` : si la valeur est `Gagné`, `Perdu` ou `Relance`, le filtre inclut les statuts événementiels associés ; sinon filtre exact.

**GET** `/entreprises/by-website?website=`** — URL ou domaine normalisé.

**GET** `/entreprises/by-email?email=&include_emails=`** — nécessite la permission **emails** si vous chargez les emails associés.

**GET** `/entreprises/by-phone?phone=&include_phones=`** — variantes de numéro acceptées (FR + international).

---

### Emails et téléphones d’une entreprise

- **`GET /entreprises/<id>/emails`** — liste simplifiée.  
- **`GET /entreprises/<id>/emails/all?include_primary=`** — détail enrichi (analyse, personne, etc.).  
- **`GET /entreprises/<id>/phones?include_primary=`** — téléphones scrapés + téléphone principal.

---

### Campagnes

- **`GET /campagnes`** — `limit`, `offset`, `statut`, **`entreprise_id`** (campagnes liées à une entreprise).  
- **`GET /entreprises/<id>/campagnes`** — même logique de filtrage, scoping par ID.  
- **`GET /campagnes/<id>`**, **`.../emails`**, **`.../statistics`** — détail, envois, métriques de tracking.

---

### Analyse de site

**GET** `/website-analysis?website=&full=`** — rapport SEO / technique / OSINT / pentest (agrégation existante en base). Réponse **404** si aucune entreprise associée au site.

**POST** `/website-analysis` — corps JSON : `website`, `force`, `full`, options de profondeur / workers / Lighthouse / Nmap, etc. Déclenche des tâches Celery ; réponse typique **202** avec identifiants de tâches. Puis interroger le **GET** pour récupérer le rapport.

---

### Notifications push (clients Expo / React Native)

Réservé aux applications qui utilisent **Expo Notifications**. N’exige pas les permissions « entreprises / emails / … » au‑delà d’un **token API valide**.

**POST** `/push/register` — `Content-Type: application/json` :

- `expo_push_token` (string, requis) — valeur du type `ExponentPushToken[...]`
- `platform` (string, défaut `android`) — `android` ou `ios`
- `installation_id` (string, optionnel) — identifiant stable d’installation côté app

**DELETE** `/push/register` — corps JSON : `{ "expo_push_token": "..." }`

**Déploiement** : le reverse proxy (nginx, etc.) doit **transmettre les requêtes POST** vers l’application pour ce chemin ; une erreur **405 Method Not Allowed** indique souvent un blocage ou une règle statique devant Flask.

---

### Événements délivrabilité et statut entreprise

Mapping recommandé (raccourcis **POST**) :

| Cas | Endpoint | Effet statut typique |
|-----|----------|----------------------|
| Bounce / non livré | `/entreprises/<id>/bounce` | `Bounce` |
| Auto-réponse | `/entreprises/<id>/callback` | `À rappeler` |
| Réponse négative | `/entreprises/<id>/negative-reply` | `Réponse négative` |
| Réponse positive | `/entreprises/<id>/positive-reply` | `Réponse positive` |
| Désabonnement | `/entreprises/<id>/unsubscribe` | `Désabonné` |
| Ne plus contacter | `/entreprises/<id>/do-not-contact` | `Ne pas contacter` |
| Plainte spam | `/entreprises/<id>/spam-complaint` | `Plainte spam` |

**PATCH** ou **POST** `/entreprises/<id>/statut` — corps : `{ "statut": "...", "note": "..." }` avec une valeur parmi **`GET /entreprises/statuses`**.

Body optionnel sur les POST : `{ "note": "..." }`.

---

### Exemples cURL (extraits)

Liste des entreprises :

```bash
curl -H "Authorization: Bearer VOTRE_TOKEN" \
  "https://votre-domaine/api/public/entreprises?limit=50&search=example"
```

Vue overview (mobile / dashboard léger) :

```bash
curl -H "Authorization: Bearer VOTRE_TOKEN" \
  "https://votre-domaine/api/public/statistics/overview?days=14"
```

Infos token :

```bash
curl -H "Authorization: Bearer VOTRE_TOKEN" \
  "https://votre-domaine/api/public/token/info"
```

---

## Gestion des tokens API (admin)

Hors préfixe `/api/public` : routes réservées à la session admin (voir interface **Tokens API**).

### Créer un token

**POST** `/api/tokens`  

**Headers** :
- `Authorization: Bearer <token_admin>` (session admin)

Authentification admin par session/cookie ou header Bearer selon votre déploiement.

**Body (JSON)** :

```json
{
  "name": "Token pour logiciel de facturation",
  "user_id": 1
}
```

Réponse : objet avec `token` en clair **une seule fois** — à sauvegarder immédiatement.

### Lister les tokens

**GET** `/api/tokens`  
Query : `user_id` (optionnel).

### Révoquer / supprimer

- **DELETE** `/api/tokens/<token_id>` — désactive le token.  
- **DELETE** `/api/tokens/<token_id>/delete` — suppression définitive.

---

## Codes de réponse HTTP

| Code | Signification |
|------|----------------|
| **200** | OK |
| **201** | Ressource créée |
| **202** | Accepté (ex. analyse lancée) |
| **400** | Paramètres invalides |
| **401** | Token manquant ou invalide |
| **403** | Token valide mais **permission insuffisante** |
| **404** | Ressource introuvable |
| **500** | Erreur serveur |

---

## Format des réponses

**Succès** (schéma fréquent) :

```json
{
  "success": true,
  "data": { },
  "count": 10,
  "limit": 100,
  "offset": 0
}
```

**Erreur** :

```json
{
  "success": false,
  "error": "Message d'erreur",
  "message": "Détails supplémentaires"
}
```

---

## Exemples d’intégration

### Python

```python
import requests

API_BASE_URL = "https://votre-domaine/api/public"
API_TOKEN = "votre_token"

headers = {"Authorization": f"Bearer {API_TOKEN}"}

entreprises = requests.get(f"{API_BASE_URL}/entreprises", headers=headers).json()["data"]
overview = requests.get(f"{API_BASE_URL}/statistics/overview?days=7", headers=headers).json()["data"]
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

const api = axios.create({
  baseURL: 'https://votre-domaine/api/public',
  headers: { Authorization: 'Bearer VOTRE_TOKEN' },
});

const { data } = await api.get('/statistics/overview', { params: { days: 7 } });
console.log(data.data);
```

### PHP

```php
<?php
$ch = curl_init('https://votre-domaine/api/public/token/info');
curl_setopt_array($ch, [
    CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $apiToken],
    CURLOPT_RETURNTRANSFER => true,
]);
$info = json_decode(curl_exec($ch), true);
curl_close($ch);
?>
```

---

## Sécurité

1. **Ne jamais** committer les tokens ; préférer variables d’environnement ou coffres secrets.  
2. **HTTPS** obligatoire en production.  
3. **Rotation** : révoquer les tokens obsolètes ou compromis.  
4. **Principe du moindre privilège** : désactiver `can_read_emails` / `can_read_statistics` / `can_read_campagnes` sur le token si l’intégration n’en a pas besoin.  
5. Éviter `?api_token=` dans des URLs loguées ou partagées.

---

## Limitations

- **Pagination** : `limit` maximal typiquement **1000** par requête.  
- **Rate limiting** : à renforcer au besoin en production (reverse proxy, WAF).  
- **Cache GET** : données légèrement différées par rapport à la base (voir section cache).

---

## Support

Pour l’architecture des routes côté code : blueprint `routes/api_public.py`. Pour toute évolution documentaire, croiser avec [API_INTEGRATION.md](../mobile/API_INTEGRATION.md) (mobile) et [INDEX.md](../INDEX.md).
