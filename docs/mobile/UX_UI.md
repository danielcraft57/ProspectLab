# UX UI (mobile)

## Objectif

Faire une app rapide, lisible, et agreable a utiliser, meme en conditions reelles (debout, lumiere moyenne, une main).

## Principes

- Lisibilite d'abord
  - gros titres, contrastes corrects, textes courts
- Une action principale par ecran
  - un bouton clair, le reste en secondaire
- Feedback immediat
  - chargement, erreurs lisibles, etat vide
- Degradation elegante
  - si OCR ou API indispo: on garde le texte et on laisse l'utilisateur continuer

## Animations

- micro animations uniquement (fade/slide a l'apparition)
- pas d'animation qui bloque ou qui ralentit

## Graphiques

MVP
- cartes KPI (totaux)
- mini bar chart simple pour donner une impression de "dashboard"

Ensuite (quand on veut aller plus loin)
- courbes par periode (jour/semaine) si l'API expose des series temporelles
- taux d'ouverture / clics pour les campagnes

## Mode sombre

Active par defaut via `userInterfaceStyle: automatic`.

## Navigation (detail)

Pour les ecrans **liste → detail** (entreprise, campagne) : header natif, titre contextuel, tab bar masquee sur les routes `*/details`, deep links. Voir le guide complet **[NAVIGATION_ET_HEADERS.md](NAVIGATION_ET_HEADERS.md)**.

