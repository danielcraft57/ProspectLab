# OCR

## Objectif

Transformer une photo (carte de visite, ecran, facture, site) en texte exploitable.

Contraintes
- la qualite varie beaucoup (flou, reflets, rotation, faible contraste)
- l'OCR fait souvent des erreurs sur:
  - `@` remplace par `(a)` ou espace
  - `0` / `O`, `1` / `I`, `5` / `S`
  - `.` manque dans les domaines

## Strategie MVP

On fait un OCR local dans l'app pour:
- reponse immediate
- pas d'upload obligatoire d'image (meilleur pour la vie privee)

Note importante (Expo)
- l'OCR "on-device" s'appuie generalement sur des modules natifs (ML Kit / Vision).
- donc, pour un vrai OCR sur iOS/Android, on part sur un build Dev Client (ou un build natif), pas uniquement Expo Go.

Ensuite on fait une extraction tolerant aux erreurs:
- emails: regex + normalisation (ex: remplacer `(at)` par `@`)
- telephone: conserver les chiffres, normaliser formats FR (+33 / 0...)
- website: detecter domaines et URLs, normaliser `https://` si besoin

## Moteur OCR (choix)

On vise une interface `OcrEngine` avec 2 implementations:
- `MlKitOcrEngine` (Android/iOS): OCR on-device via ML Kit (recommande)
- `ManualOcrEngine` (fallback): l'utilisateur colle le texte (utile en dev, ou si OCR indispo)

## Qualite et UX

Toujours afficher:
- texte OCR brut (copiable)
- champs extraits (editables)
- un score simple (ex: "confiance: faible/moyen/bon") base sur heuristiques (presence de `@`, longueur, etc.)

## Confidentialite

Par defaut, les images ne quittent pas l'app.
Si plus tard on ajoute un OCR serveur, il faudra:
- opt-in explicite
- supprimer l'image cote serveur apres traitement

