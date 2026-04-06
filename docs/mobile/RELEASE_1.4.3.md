# Release mobile 1.4.3

Date: 2026-04-06

## Nouveautés principales

- Nouvelle page `Carte` (onglet) basée sur OpenStreetMap.
- Natif iOS/Android via MapLibre (tuiles OSM), web via Leaflet.
- Recherche de ville (Grand Est), rafraîchissement auto et conservation du viewport (position + zoom).
- Palette de couleurs enrichie pour les points (secteur, statut, opportunité, score).
- Clic sur marqueur: fiche entreprise enrichie avec niveaux, jauges et détails.

## Détails API / backend

- Ajout de `GET /api/public/reference/carte-villes` pour alimenter la recherche de villes avec comptage.
- Ajout de `GET /api/public/entreprises/<id>/gallery` pour exposer les visuels agrégés d'une fiche.
- Ajout de `count_nearby_entreprises()` côté DB pour les agrégations carte.

## Fiche entreprise (carte)

- Enrichissement de la fiche avec:
  - données de détail entreprise (email, téléphone, adresse, stack, résumé),
  - galerie d'images,
  - scores technique, SEO et pentest.
- Fermeture via croix et tap sur le fond.
- Icône secteur affichée à gauche du titre.

## Correctifs importants

- Rétablissement du header global sur l'onglet Carte.
- Android: retour au rendu marqueurs `ShapeSource + CircleLayer` (fiable), suite à des régressions d'affichage avec `PointAnnotation`.
- Tolérance aux erreurs de route galerie (ex: HTTP 405): la fiche continue de s'afficher.

## Maintenance / ménage

- Séparation des implémentations native/web pour certains modules cache/offline.
- Ignorance Git de `scripts/google_maps_tools/.google_maps_api_key`.
- Alignement de version appli mobile:
  - `mobile/package.json`: `1.4.3`
  - `mobile/app.json` (Expo): `1.4.3`
