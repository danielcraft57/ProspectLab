# ProspectLab Mobile

App mobile (Expo + TypeScript) pour consulter le dashboard, les entreprises, les campagnes, et scanner du texte (OCR).

## Ecrans (MVP)

- Dashboard : stats globales via `GET /api/public/statistics`
- Entreprises : liste + recherche simple via `GET /api/public/entreprises`
- Campagnes : liste via `GET /api/public/campagnes`
- Sites : saisie URL, test de joignabilite, capture / OCR en dessous (token API uniquement dans Reglages)
- Reglages : stockage securise du token API, synchronisation optionnelle des notifications push (Expo)

## Demarrer

Dans `mobile/`:
- `npm install`
- `npm run start`

Si Expo affiche des warnings de versions, fais une reinstall propre:
- supprimer `mobile/node_modules`
- supprimer `mobile/package-lock.json`
- relancer `npm install`

## Variables d'environnement (optionnel)

Expo expose les variables `EXPO_PUBLIC_*`. Ne pas y mettre de token utilisateur ni de secrets Firebase.

Exemples (adapter l’URL a ton environnement) :

- `EXPO_PUBLIC_PROSPECTLAB_BASE_URL=http://localhost:5000` ou `https://<ton-domaine>`
- `EXPO_PUBLIC_PROSPECTLAB_API_PUBLIC_PREFIX=/api/public`
- `EXPO_PUBLIC_EAS_PROJECT_ID=<uuid-projet-expo>` — requis pour `getExpoPushTokenAsync` (voir `eas project:info` / expo.dev)

Pour Android, le fichier **client** `google-services.json` (console Firebase, appli avec le bon `applicationId`) doit etre present localement ; il n’est en general **pas** versionne (voir `mobile/.gitignore`).

## Token API

L'app attend un token `Bearer` pour appeler l'API publique.
Tu peux le coller dans l'onglet `Reglages`.

## Build Android (interne / prod)

### Interne (sans Store)

Genere un **APK** installable via un lien EAS :

- `npm run build:android:internal`

### Production (Play Store)

Genere un **AAB** (non installable directement, a soumettre sur Google Play) :

- `npm run build:android:prod`

### Local (release + installation)

Build Gradle en release + installation sur un appareil Android via ADB (USB recommande) :

- `npm run android:local-release`

## OCR (etat)

Le flux `Scan` est pret et l'extraction est en place.
L'OCR natif on-device (ML Kit / Vision) sera branche via un moteur `OcrEngine` (voir `docs/mobile/OCR.md`).

