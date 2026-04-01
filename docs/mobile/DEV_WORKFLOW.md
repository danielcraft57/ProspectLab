# Workflow dev (mobile)

## Pre-requis

- Node.js LTS
- npm (ou pnpm)
- Expo Go sur telephone (optionnel) ou emulateur Android

## Installation

Aller dans `mobile/` puis installer:
- `npm install`

## Variables d'environnement

On utilise des variables Expo (prefixe `EXPO_PUBLIC_`).

Exemples
- `EXPO_PUBLIC_PROSPECTLAB_BASE_URL=http://localhost:5000`
- `EXPO_PUBLIC_PROSPECTLAB_API_PUBLIC_PREFIX=/api/public`

Le token n'est pas une variable d'env. Il est saisi dans l'app puis stocke en securise.

## Lancer

- `npm run start`

## Build (plus tard)

On ajoutera EAS (build cloud) quand le MVP est stable.

