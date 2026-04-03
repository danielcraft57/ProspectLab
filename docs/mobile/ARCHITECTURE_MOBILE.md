# Architecture mobile

## Vue d'ensemble

L'app mobile est un client leger qui fait 3 choses:
- capture une image (camera ou galerie)
- fait un OCR local pour extraire du texte
- transforme ce texte en signaux (email, telephone, domaine, URL) puis appelle:
  - l'API publique ProspectLab (`/api/public/...`) pour retrouver/enrichir/synchroniser
  - des APIs publiques externes (optionnel) pour enrichissement

Principe important: l'app reste utilisable meme si l'OCR est imparfait. On affiche toujours le texte OCR brut + une extraction "proposee" editable.
Pour les modeles d'ingenierie (couches, patterns, modeles de domaine), voir `MODELES_INGENIERIE.md`.

## Dossiers (cible)

On ajoute un dossier `mobile/` a la racine du repo.

Dans `mobile/`, structure type:
- `app/`: navigation et ecrans (Expo Router)
- `src/`
  - `core/`: config, erreurs, types, helpers
  - `features/`
    - `scan/`: capture, OCR, extraction, correction manuelle
    - `prospectlab/`: appels à l'API publique — référence serveur [Guide API publique](../guides/API_PUBLIQUE.md), côté client [API_INTEGRATION.md](API_INTEGRATION.md)
    - `enrichment/`: appels APIs externes (optionnel)
  - `lib/`
    - `http/`: client HTTP, interceptors, timeouts
    - `storage/`: stockage securise des secrets (token)
    - `ocr/`: moteur OCR (implementations)
    - `parsing/`: regex + normalisation email/phone/url

## Architecture logique

UI (React Native)
-> use case (ex: ScanAndLookupUseCase)
-> services (OCRService, ParsingService, ProspectLabApi)
-> storage (SecureStore)

Regles
- pas de token en dur dans le code
- on supporte un mode "demo" sans token (uniquement OCR + extraction locale)
- toute requete reseau passe par un seul client HTTP (timeouts, logs minimal)

## Flux principal (MVP)

1) Photo
- l'utilisateur prend une photo d'une carte de visite ou d'un ecran

2) OCR
- OCR local -> texte brut

3) Extraction
- extraire:
  - emails (peut etre plusieurs)
  - telephones (formats FR + international)
  - website (domaine ou URL)

4) Lookup ProspectLab
- si on a un website:
  - `GET /api/public/entreprises/by-website?website=...`
  - si pas trouve: `POST /api/public/website-analysis` pour lancer l'analyse
- si on a un email:
  - `GET /api/public/entreprises/by-email?email=...&include_emails=true`
- si on a un telephone:
  - `GET /api/public/entreprises/by-phone?phone=...&include_phones=true`

5) Affichage
- afficher la fiche entreprise si trouvee
- sinon afficher une fiche "a creer" (MVP: seulement sauvegarde locale)

## Dashboard (comme le projet)

L'app mobile a une navigation en onglets:
- Dashboard: statistiques globales (API publique) + acces rapides
- Entreprises: liste + recherche basique + detail light
- Campagnes: liste + detail + stats de tracking (si permission)
- Scan: capture + OCR + lookup
- Reglages: base URL, token, debug

## Offline et resilience

Offline
- l'app reste fonctionnelle sans réseau : OCR / extraction / sélection des URLs.
- les analyses de sites (onglet **Sites**) peuvent être **enregistrées** hors ligne, puis envoyées automatiquement dès que la connexion revient.
- persistance : file locale `website_analysis_queue` via SQLite (voir `mobile/src/lib/offline/websiteAnalysisQueue.ts`).
  - migration automatique au premier démarrage depuis l'ancien fichier JSON `website_analysis_queue_v1.json` (si présent).

Réseau
- un module réseau (`mobile/src/lib/net/`) expose le transport (Wi‑Fi / données mobiles / etc.) et un indicateur `usableForApi`.
- un hook `useOnBecameOnline` permet de déclencher des actions à la reconnexion (flush de file, refresh des écrans).

UI
- le bouton principal du scan caméra passe de **Analyser** (en ligne) à **Enregistrer** (hors ligne), pour éviter de bloquer l'utilisateur sur des tests de joignabilité impossibles.
- le dashboard / listes **entreprises** / **campagnes** se rafraîchissent automatiquement dès que l'app repasse en ligne.

Resilience
- si une API externe tombe, on degrade sans casser le flux principal

