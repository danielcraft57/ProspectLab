## Contexte

- Pourquoi on le fait
- Ce que ca remplace ou complete

## Objectifs

- Objectif principal
- Objectifs secondaires

## Non-objectifs

- Ce qu'on ne fera pas dans ce lot

## Donnees

- Source des photos
- Volume estime (nb photos, taille)
- Contraintes (droit a l'image, stockage, retention)

## Approche

- Indexation (comment on scanne, comment on stocke l'index)
- Detection visage (choix modele, perfs)
- Embeddings (choix modele, dimension)
- Matching (cosine, seuils, top-k)

## Perf et cout

- Temps cible (ex: 10k photos/min sur machine X)
- GPU ou CPU
- Budget disque (artifacts + caches)

## Risques et mitigations

- Faux positifs / faux negatifs
- Photos floues, angles, eclairage
- Multivisages

## Plan de test

- Petit dataset de validation
- Metriques (precision@k, taux de FP)
- Tests de non-regression

## Definition of Done

- Ce qui doit etre vrai pour dire "c'est fini"

