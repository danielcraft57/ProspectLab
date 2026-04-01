# Securite

## Token API ProspectLab

Le token donne acces a des donnees. Sur mobile, on fait simple:
- stockage dans un coffre securise (Secure Storage)
- jamais de token dans git
- possibilite de "deconnecter" (efface le token)

## Transport

- HTTPS obligatoire en prod
- en dev local, HTTP accepte uniquement sur emulateur/appareil dev

## Logs

- ne jamais logger le token
- limiter les logs reseau aux codes HTTP + endpoint (sans query sensible)

## Permissions

ProspectLab supporte des permissions fines par token (entreprises, emails, statistics, campagnes).
Pour le mobile MVP, on vise:
- `entreprises`: oui
- `emails`: oui (si besoin lookup par email)
- `statistics`: optionnel
- `campagnes`: optionnel

