# Modeles d'ingenierie (mobile)

## Pourquoi

On veut une app qui grossit sans se transformer en spaghetti:
- OCR, parsing, reseau, stockage, UI
- plusieurs sources de donnees (ProspectLab + APIs publiques)
- offline + synchronisation plus tard

Donc on adopte des modeles simples et connus.

## Modele d'architecture (Clean / Hexagonal light)

On se base sur une separation en 4 zones:

- UI
  - ecrans, composants, navigation
  - pas de logique reseau directe

- Use cases (application)
  - orchestration (ex: "scanner puis rechercher")
  - pas de dependance a React

- Domain (modeles + regles)
  - entites (Entreprise, Campagne, ScanResult)
  - valeurs (Email, Phone, Website)
  - normalisation et regles de validation

- Infra
  - clients HTTP
  - stockage securise
  - OCR engine

Regle: UI -> Use cases -> Domain/Infra
L'infra ne depend de personne (sauf libs).

## Modeles de domaine (MVP)

Entreprise (vue mobile)
- id: number
- nom: string
- website: string | null
- secteur: string | null
- statut: string | null
- email_principal: string | null
- telephone: string | null

Campagne (vue mobile)
- id: number
- nom: string
- statut: string
- total_destinataires: number | null
- total_envoyes: number | null
- total_reussis: number | null
- date_creation: string | null

ScanResult
- rawText: string
- emails: string[]
- phones: string[]
- websites: string[]
- createdAt: string
- imageUri: string | null

## Patterns utilises

- Repository
  - `ProspectLabRepository` encapsule les appels `api/public`
- Adapter
  - adapter de reponse API -> modeles UI
- Service
  - `OcrService`, `ParsingService`, `SecureTokenStore`
- Error model
  - erreurs normalisees (reseau, auth, parsing)

## Diagramme (simple)

UI
-> UseCases
-> Repositories
-> HTTP Client
-> API ProspectLab

UI
-> OCR Service
-> Parsing Service
-> Repositories (lookup)

