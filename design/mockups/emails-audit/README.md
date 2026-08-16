# Maquettes emails - Audit / secu / clicks

Galerie : ouvrir `index.html`.

Reference : [docs/guides/DANIELCRAFT_EMAIL_VOICE.md](../../../docs/guides/DANIELCRAFT_EMAIL_VOICE.md)

## Variantes (objets = sujets d'email)

| # | Fichier | Objet (sujet) |
|---|---------|----------------|
| 01 | `01-audit-rapport.html` | Claire, ton rapport est pret - regarde voir |
| 02 | `02-pentest-priorites.html` | Ta clanche web est un peu ouverte (atelier-nord.fr) |
| 03 | `03-scores-360.html` | 3 notes sur ton site - une est un peu nareuse |
| 04 | `04-relance-analyse.html` | Hop, je remets le lien - au cas ou ca a file |
| 05 | `05-tech-franchement.html` | On en parle franchement ? (entre midi si tu veux) |
| 06 | `06-secu-clanche.html` | Secu: ton site laisse la clanche ouverte |
| 07 | `07-anciennete-rincee.html` | Ton site a pris une rincee du temps |
| 08 | `08-voisin-google.html` | Le commerce d'a cote est plus facile a trouver |
| 09 | `09-bassote-demandes.html` | Ton site bassote un peu cote demandes |
| 10 | `10-curiosite-30s.html` | 30 secondes - regarde voir ce que j'ai vu |

## Levain lorrain utilise

clanche, rincee, chawée, nareux/nareuse, bassote/bassoter, trisse/trissent, couarail, entre midi, regarde voir / dis voir, beugner/beugne.

## Assets

`assets/` : heroes JPG + charts PNG. Regenerer charts :

```powershell
python design/mockups/emails-audit/generate_charts.py
```

## CTA

```
https://danielcraft.fr/analyse?website=...&full=1&email=...&name=...
```
