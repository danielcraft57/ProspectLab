# ProspectLab Mobile

App mobile (Expo + TypeScript) pour consulter le dashboard, les entreprises, les campagnes, et scanner du texte (OCR).

## Ecrans (MVP)

- Dashboard: stats globales via `GET /api/public/statistics`
- Entreprises: liste + recherche simple via `GET /api/public/entreprises`
- Campagnes: liste via `GET /api/public/campagnes`
- Scan: extraction (email/tel/website) + lookup via `api/public` (MVP: OCR manuel)
- Reglages: stockage securise du token

## Demarrer

Dans `mobile/`:
- `npm install`
- `npm run start`

Si Expo affiche des warnings de versions, fais une reinstall propre:
- supprimer `mobile/node_modules`
- supprimer `mobile/package-lock.json`
- relancer `npm install`

## Variables d'environnement (optionnel)

Expo expose les variables `EXPO_PUBLIC_*`.

Exemples
- `EXPO_PUBLIC_PROSPECTLAB_BASE_URL=http://localhost:5000`
- `EXPO_PUBLIC_PROSPECTLAB_API_PUBLIC_PREFIX=/api/public`

## Token API

L'app attend un token `Bearer` pour appeler l'API publique.
Tu peux le coller dans l'onglet `Reglages`.

## OCR (etat)

Le flux `Scan` est pret et l'extraction est en place.
L'OCR natif on-device (ML Kit / Vision) sera branche via un moteur `OcrEngine` (voir `docs/mobile/OCR.md`).

