# Guide de l'API Publique

## Vue d'ensemble

L'API publique de ProspectLab permet d'accéder aux données d'entreprises et d'emails depuis des applications externes (facturation, devis, comptabilité, etc.). L'authentification se fait via des tokens API sécurisés.

## Authentification

### Génération d'un token API

Les tokens API sont générés par un administrateur via l'interface d'administration :

1. Se connecter en tant qu'administrateur
2. Accéder à l'endpoint `/api/tokens` (POST)
3. Fournir un nom pour le token
4. Sauvegarder immédiatement le token retourné (il ne sera plus affiché)

### Utilisation du token

Le token peut être fourni de deux manières :

#### 1. Header Authorization (recommandé)
```
Authorization: Bearer <votre_token>
```

#### 2. Paramètre de requête
```
?api_token=<votre_token>
```

## Endpoints disponibles

### Base URL
```
http://votre-domaine.com/api/public
```

### 1. Liste des entreprises

**GET** `/api/public/entreprises`

**Paramètres de requête** :
- `limit` (int, optionnel) : Nombre maximum de résultats (défaut: 100, max: 1000)
- `offset` (int, optionnel) : Offset pour la pagination (défaut: 0)
- `secteur` (string, optionnel) : Filtrer par secteur
- `statut` (string, optionnel) : Filtrer par statut commercial (`Nouveau`, `À qualifier`, `Relance`, `Gagné`, `Perdu`)
- `search` (string, optionnel) : Recherche textuelle (nom, website)

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/entreprises?limit=50&secteur=Informatique"
```

**Réponse** :
```json
{
  "success": true,
  "count": 50,
  "limit": 50,
  "offset": 0,
  "data": [
    {
      "id": 1,
      "nom": "Entreprise Example",
      "website": "https://example.com",
      "secteur": "Informatique",
      "statut": "Nouveau",
      "email_principal": "contact@example.com",
      "telephone": "+33123456789",
      "address_1": "123 Rue Example",
      "address_2": "75001 Paris",
      "longitude": 2.3522,
      "latitude": 48.8566,
      "note_google": 4.5,
      "nb_avis_google": 120,
      "tags": ["client", "important"],
      "og_data": {...}
    }
  ]
}
```

### 2. Détails d'une entreprise

**GET** `/api/public/entreprises/<entreprise_id>`

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/entreprises/1"
```

**Réponse** :
```json
{
  "success": true,
  "data": {
    "id": 1,
    "nom": "Entreprise Example",
    "website": "https://example.com",
    "secteur": "Informatique",
    "statut": "Nouveau",
    "email_principal": "contact@example.com",
    "telephone": "+33123456789",
    "address_1": "123 Rue Example",
    "address_2": "75001 Paris",
    "longitude": 2.3522,
    "latitude": 48.8566,
    "note_google": 4.5,
    "nb_avis_google": 120,
    "tags": ["client", "important"],
    "og_data": {...}
  }
}
```

### 3. Emails d'une entreprise

**GET** `/api/public/entreprises/<entreprise_id>/emails`

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/entreprises/1/emails"
```

**Réponse** :
```json
{
  "success": true,
  "entreprise_id": 1,
  "count": 3,
  "data": [
    {
      "email": "contact@example.com",
      "nom": "John Doe",
      "page_url": "https://example.com/contact",
      "date_scraping": "2026-01-22 10:30:00"
    },
    {
      "email": "info@example.com",
      "nom": null,
      "page_url": "https://example.com",
      "date_scraping": "2026-01-22 10:30:00"
    }
  ]
}
```

### 4. Liste de tous les emails

**GET** `/api/public/emails`

**Paramètres de requête** :
- `limit` (int, optionnel) : Nombre maximum de résultats (défaut: 100, max: 1000)
- `offset` (int, optionnel) : Offset pour la pagination (défaut: 0)
- `entreprise_id` (int, optionnel) : Filtrer par entreprise

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/emails?limit=100&entreprise_id=1"
```

**Réponse** :
```json
{
  "success": true,
  "count": 100,
  "limit": 100,
  "offset": 0,
  "data": [
    {
      "email": "contact@example.com",
      "nom": "John Doe",
      "entreprise_id": 1,
      "entreprise_nom": "Entreprise Example",
      "page_url": "https://example.com/contact",
      "date_scraping": "2026-01-22 10:30:00"
    }
  ]
}
```

### 5. Liste des campagnes email

**GET** `/api/public/campagnes`

**Paramètres de requête** :
- `limit` (int, optionnel) : Nombre maximum de résultats (défaut: 100, max: 1000)
- `offset` (int, optionnel) : Offset pour la pagination (défaut: 0)
- `statut` (string, optionnel) : Filtrer par statut (draft, running, completed, failed)

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/campagnes?limit=50&statut=completed"
```

**Réponse** :
```json
{
  "success": true,
  "count": 50,
  "limit": 50,
  "offset": 0,
  "data": [
    {
      "id": 1,
      "nom": "Campagne Janvier 2026",
      "template_id": "modernisation_technique",
      "sujet": "Modernisation de votre infrastructure",
      "total_destinataires": 100,
      "total_envoyes": 98,
      "total_reussis": 95,
      "statut": "completed",
      "date_creation": "2026-01-22 10:00:00"
    }
  ]
}
```

### 6. Détails d'une campagne

**GET** `/api/public/campagnes/<campagne_id>`

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/campagnes/1"
```

**Réponse** :
```json
{
  "success": true,
  "data": {
    "id": 1,
    "nom": "Campagne Janvier 2026",
    "template_id": "modernisation_technique",
    "sujet": "Modernisation de votre infrastructure",
    "total_destinataires": 100,
    "total_envoyes": 98,
    "total_reussis": 95,
    "statut": "completed",
    "date_creation": "2026-01-22 10:00:00"
  }
}
```

### 7. Emails d'une campagne

**GET** `/api/public/campagnes/<campagne_id>/emails`

**Paramètres de requête** :
- `limit` (int, optionnel) : Nombre maximum de résultats (défaut: 100, max: 1000)
- `offset` (int, optionnel) : Offset pour la pagination (défaut: 0)
- `statut` (string, optionnel) : Filtrer par statut (sent, failed)

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/campagnes/1/emails?limit=100"
```

**Réponse** :
```json
{
  "success": true,
  "campagne_id": 1,
  "count": 100,
  "total": 98,
  "limit": 100,
  "offset": 0,
  "data": [
    {
      "id": 1,
      "campagne_id": 1,
      "entreprise_id": 5,
      "email": "contact@example.com",
      "nom_destinataire": "John Doe",
      "entreprise": "Example Corp",
      "sujet": "Modernisation de votre infrastructure",
      "date_envoi": "2026-01-22 10:05:00",
      "statut": "sent",
      "erreur": null,
      "tracking_token": "abc123..."
    }
  ]
}
```

### 8. Statistiques d'une campagne

**GET** `/api/public/campagnes/<campagne_id>/statistics`

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/campagnes/1/statistics"
```

**Réponse** :
```json
{
  "success": true,
  "campagne_id": 1,
  "data": {
    "total_emails": 98,
    "total_opens": 45,
    "total_clicks": 12,
    "open_rate": 45.9,
    "click_rate": 12.2,
    "events_by_type": {
      "open": 45,
      "click": 12
    }
  }
}
```

### 9. Statistiques

**GET** `/api/public/statistics`

Retourne un résumé global des données accessibles via l’API publique.

**Exemple de requête** :
```bash
curl -H "Authorization: Bearer votre_token" \
  "http://localhost:5000/api/public/statistics"
```

**Réponse** (exemple) :
```json
{
  "success": true,
  "data": {
    "total_analyses": 10,
    "total_entreprises": 250,
    "favoris": 15,
    "par_statut": {
      "Nouveau": 120,
      "À qualifier": 60,
      "Relance": 40,
      "Gagné": 20,
      "Perdu": 10
    },
    "par_secteur": {
      "Technologie": 100,
      "Commerce": 50
    },
    "par_opportunite": {
      "Élevée": 20,
      "Moyenne": 30
    }
  }
}
```

## Gestion des tokens API (Admin)

### Créer un token

**POST** `/api/tokens`

**Headers** :
- `Authorization: Bearer <token_admin>` (session admin)

**Body (JSON)** :
```json
{
  "name": "Token pour logiciel de facturation",
  "user_id": 1
}
```

**Réponse** :
```json
{
  "success": true,
  "message": "Token créé avec succès. Sauvegardez-le immédiatement, il ne sera plus affiché.",
  "data": {
    "id": 1,
    "token": "votre_token_complet_ici",
    "name": "Token pour logiciel de facturation",
    "user_id": 1,
    "is_active": true
  }
}
```

### Lister les tokens

**GET** `/api/tokens`

**Query params** :
- `user_id` (int, optionnel) : Filtrer par utilisateur

### Révoquer un token

**DELETE** `/api/tokens/<token_id>`

Désactive le token (ne le supprime pas).

### Supprimer un token

**DELETE** `/api/tokens/<token_id>/delete`

Supprime définitivement le token.

## Codes de réponse HTTP

- **200 OK** : Requête réussie
- **201 Created** : Ressource créée avec succès
- **400 Bad Request** : Paramètres invalides
- **401 Unauthorized** : Token manquant ou invalide
- **404 Not Found** : Ressource introuvable
- **500 Internal Server Error** : Erreur serveur

## Format des réponses

Toutes les réponses suivent ce format :

**Succès** :
```json
{
  "success": true,
  "data": {...},
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

## Exemples d'intégration

### Python

```python
import requests

API_BASE_URL = "http://localhost:5000/api/public"
API_TOKEN = "votre_token"

headers = {
    "Authorization": f"Bearer {API_TOKEN}"
}

# Récupérer les entreprises
response = requests.get(f"{API_BASE_URL}/entreprises", headers=headers)
entreprises = response.json()["data"]

# Récupérer les emails d'une entreprise
entreprise_id = 1
response = requests.get(
    f"{API_BASE_URL}/entreprises/{entreprise_id}/emails",
    headers=headers
)
emails = response.json()["data"]
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

const API_BASE_URL = 'http://localhost:5000/api/public';
const API_TOKEN = 'votre_token';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Authorization': `Bearer ${API_TOKEN}`
  }
});

// Récupérer les entreprises
const entreprises = await api.get('/entreprises');
console.log(entreprises.data.data);

// Récupérer les emails
const emails = await api.get('/entreprises/1/emails');
console.log(emails.data.data);
```

### PHP

```php
<?php
$apiBaseUrl = 'http://localhost:5000/api/public';
$apiToken = 'votre_token';

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $apiBaseUrl . '/entreprises');
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Authorization: Bearer ' . $apiToken
]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

$response = curl_exec($ch);
$entreprises = json_decode($response, true);

curl_close($ch);
?>
```

## Sécurité

### Bonnes pratiques

1. **Stockage des tokens** :
   - Ne jamais commiter les tokens dans le code source
   - Utiliser des variables d'environnement
   - Chiffrer les tokens en base de données si nécessaire

2. **HTTPS** :
   - Utiliser HTTPS en production pour protéger les tokens en transit

3. **Rotation des tokens** :
   - Révoquer et recréer les tokens régulièrement
   - Révoquer immédiatement les tokens compromis

4. **Limitation des accès** :
   - Créer des tokens spécifiques par application
   - Révoquer les tokens inutilisés

## Limitations

- **Rate limiting** : À implémenter en production
- **Pagination** : Maximum 1000 résultats par requête
- **Filtres** : Les filtres complexes ne sont pas encore supportés

## Support

Pour toute question ou problème, consultez la documentation complète ou contactez l'administrateur.

