# Intégration interne des applications (Facturio, MailPilot, VocalGuard)

Ce document décrit l'API interne exposée par ProspectLab pour les applications
clientes internes (Facturio, MailPilot, VocalGuard, etc.).

L’objectif est d’avoir :
- **un modèle d’« application cliente »** avec une clé API dédiée,
- **un middleware `x-api-key`** homogène,
- **des endpoints normalisés autour de la notion de `company`**.

---

## 1. Modèle d’application cliente & clés API

### 1.1. Modèle `application_clients`

Table interne créée dans la base ProspectLab :

- **id**: identifiant interne
- **name**: nom de l’application (`Facturio`, `MailPilot`, `VocalGuard`, …)
- **api_key**: clé API unique (token généré)
- **active**: 1/0 – permet d’activer/désactiver une app
- **description**: texte libre
- **created_at**: date de création
- **last_used**: dernière utilisation
- **last_ip**: dernière IP vue
- **last_endpoint**: dernier endpoint appelé
- **last_status**: dernier code HTTP renvoyé (optionnel / futur)

Pour l’instant, la création/mise à jour se fait côté admin (ou script) en base
de données. À terme, on pourra rajouter une petite interface.

### 1.2. Authentification via `x-api-key`

Un middleware Flask (`client_api_key_required`) protège les routes d’intégration.

- Le client doit envoyer **une clé API** valide :
  - dans le header: `x-api-key: <CLE_API>`
  - ou en paramètre: `?api_key=<CLE_API>` (fallback)
- Si la clé est invalide/inactive → **401 Unauthorized**
- À chaque appel validé, ProspectLab met à jour:
  - `last_used`
  - `last_ip`
  - `last_endpoint`

Dans le code, l’application cliente est disponible via `request.client_app`.

---

## 2. Endpoints exposés

Base URL (interne) :

```text
http://<host>:5000/api
```

Tous les endpoints ci-dessous exigent un header `x-api-key` valide.

### 2.1. GET `/api/companies/<id>`

**But**: récupérer toutes les infos d’une entreprise depuis son identifiant ProspectLab.

**Exemple de requête**:

```bash
curl -H "x-api-key: VOTRE_CLE_API" \
  "http://localhost:5000/api/companies/123"
```

### 2.2. GET `/api/companies/by-email?email=...`

**But** (MailPilot) : retrouver l’entreprise à partir de l’email d’un contact.

- Recherche d’abord dans `scraper_emails.email`
- Fallback sur `entreprises.email_principal`

**Exemple**:

```bash
curl -H "x-api-key: VOTRE_CLE_API" \
  "http://localhost:5000/api/companies/by-email?email=contact@exemple.com"
```

### 2.3. GET `/api/companies/by-phone?phone=...`

**But** (VocalGuard) : retrouver l’entreprise à partir d’un numéro de téléphone.

- Recherche d’abord dans `scraper_phones.phone`
- Fallback sur `entreprises.telephone`

**Exemple**:

```bash
curl -H "x-api-key: VOTRE_CLE_API" \
  "http://localhost:5000/api/companies/by-phone?phone=+33123456789"
```

### 2.4. (Optionnel) GET `/api/companies/by-domain?domain=...`

**But**: retrouver l’entreprise à partir d’un domaine (utile pour de futurs usages).

- Normalisation légère du domaine (suppression schéma / chemin)
- Recherche sur `entreprises.website` (LIKE `%domain%`)
- Fallback via `scraper_emails.domain`

**Exemple**:

```bash
curl -H "x-api-key: VOTRE_CLE_API" \
  "http://localhost:5000/api/companies/by-domain?domain=exemple.com"
```

---

## 3. Format JSON de la réponse

Tous les endpoints renvoient la même structure JSON de haut niveau :

```json
{
  "success": true,
  "data": {
    "id": 123,
    "name": "Entreprise Exemple",
    "siret": null,
    "vat_number": null,
    "address": "10 rue Exemple",
    "city": null,
    "zip": null,
    "country": "France",
    "email": "contact@exemple.com",
    "phone": "+33123456789",
    "website": "https://www.exemple.com",
    "status": "prospect",
    "tags": ["client", "important"],
    "score": 85
  }
}
```

- **id**: identifiant interne ProspectLab (clé de référence unique)
- **name**: nom de l’entreprise (`entreprises.nom`)
- **siret**: SIRET (si/ quand disponible en base)
- **vat_number**: numéro de TVA (si/ quand disponible en base)
- **address**: adresse principale (`entreprises.address_1`)
- **city** / **zip**: à compléter plus tard si ajoutés au modèle
- **country**: pays (`entreprises.pays`)
- **email**: email principal (`entreprises.email_principal`)
- **phone**: téléphone principal (`entreprises.telephone`)
- **website**: site web (`entreprises.website`)
- **status**: statut commercial (`entreprises.statut`, ex. prospect/client)
- **tags**: tags (liste JSON venant de `entreprises.tags`)
- **score**: score (actuellement `score_securite`, ajustable si besoin)

En cas d’erreur:

```json
{
  "success": false,
  "error": "Message d'erreur"
}
```

---

## 4. Exemples d’intégration

### 4.1. cURL

```bash
API_KEY="VOTRE_CLE_API"
BASE_URL="http://localhost:5000/api"

curl -H "x-api-key: $API_KEY" \
  "$BASE_URL/companies/by-email?email=contact@exemple.com"
```

### 4.2. Python (requests)

```python
import requests

API_KEY = "VOTRE_CLE_API"
BASE_URL = "http://localhost:5000/api"

headers = {
    "x-api-key": API_KEY,
}

def get_company_by_email(email: str):
    resp = requests.get(
        f"{BASE_URL}/companies/by-email",
        headers=headers,
        params={"email": email},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        return None
    return data["data"]
```

### 4.3. Node.js (axios)

```javascript
const axios = require('axios');

const API_KEY = 'VOTRE_CLE_API';
const BASE_URL = 'http://localhost:5000/api';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'x-api-key': API_KEY,
  },
});

async function getCompanyByPhone(phone) {
  const response = await api.get('/companies/by-phone', {
    params: { phone },
  });

  if (!response.data.success) {
    return null;
  }
  return response.data.data;
}
```

---

## 5. Notes et évolutions possibles

- Ajouter des champs enrichis (SIRET, TVA, ville, CP) dans la table `entreprises`
  puis les exposer dans le payload.
- Ajouter un petit écran d’admin pour gérer les `application_clients` (génération
  de clés, activation/désactivation).
- Mettre en place du rate limiting par `api_key` si nécessaire.

