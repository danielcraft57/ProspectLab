# Maquettes emails - Audit / secu / clicks

Galerie : ouvrir `index.html`.

Reference : [docs/guides/DANIELCRAFT_EMAIL_VOICE.md](../../../docs/guides/DANIELCRAFT_EMAIL_VOICE.md)

## Variantes (objets = sujets d'email)

| # | Fichier | Objet (sujet) |
|---|---------|----------------|
| 01 | `01-audit-rapport.html` | Claire, ton rapport est pret - jette un oeil |
| 02 | `02-pentest-priorites.html` | Ta porte web est un peu ouverte (atelier-nord.fr) |
| 03 | `03-scores-360.html` | 3 notes sur ton site - une est pas terrible |
| 04 | `04-relance-analyse.html` | Hop, je remets le lien - au cas ou ca a file |
| 05 | `05-tech-franchement.html` | On en parle franchement ? (autour de midi si tu veux) |
| 06 | `06-secu-clanche.html` | Secu: ton site laisse la porte ouverte |
| 07 | `07-anciennete-rincee.html` | Ton site a pris un coup de vieux |
| 08 | `08-voisin-google.html` | Le commerce d'a cote est plus facile a trouver |
| 09 | `09-bassote-demandes.html` | Les gens arrivent - puis ca coince |
| 10 | `10-curiosite-30s.html` | 30 secondes - jette un oeil a ce que j'ai vu |

## Vocabulaire (francais simple)

Plus d'argot lorrain. Equivalents utilises :

| Avant (lorrain) | Maintenant |
|-----------------|------------|
| regarde voir / dis voir | jette un oeil / dis-moi |
| entre midi | autour de midi |
| nareux / nareuse | tatillon / pas terrible |
| clanche / clancher | porte / fermer |
| rincee du temps | coup de vieux |
| bassoter | coincer / peiner |

## Assets

`assets/` : heroes JPG + charts PNG. Regenerer charts :

```powershell
python design/mockups/emails-audit/generate_charts.py
```

## CTA

```
https://danielcraft.fr/analyse?website=...&full=1&email=...&name=...
```
