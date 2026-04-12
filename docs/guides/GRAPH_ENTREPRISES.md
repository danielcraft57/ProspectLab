# Graph entreprises (liens externes)

Vue interactive **entreprises ↔ domaines tiers** découverts lors du scraping (liens sortants, crédits éventuels). Elle complète la fiche entreprise sans la remplacer.

## Accès

- **URL :** `/graph-entreprises`
- **Menu :** entrée dédiée dans la navigation (à côté des autres pages métier).

## Fonctionnalités côté interface

- Graphe **vis-network** : zoom, cadrage, physique on/off, export **PNG**, historique de vues (précédent / suivant).
- **Filtres locaux** : types de nœuds (fiche, agence, autres domaines), types d’arêtes (crédit, lien, réf. site, fiche en base), libellés compacts, recherche sur le graphe chargé.
- **Périmètre serveur** : recherche texte, filtre par domaine, plafonds lignes / entreprises, IDs entreprises, option « crédits seuls » ; rechargement via **Actualiser**.
- **Thème** : bouton **Auto → Sombre → Clair** (préférence stockée dans `localStorage` ; les infobulles synchronisent des variables CSS sur `:root` car le conteneur `vis-tooltip` est hors de la page).
- **Infobulles (survol)** : contenu riche en **HTML injecté comme nœud DOM** (exigence vis-network ≥ 9 : les chaînes HTML dans `title` ne sont plus interprétées). Cartes avec icônes Material, stats **libellé + valeur sur une même ligne**, blocs schémas / JSON-LD, liens cliquables vers le site fiche.
- **Carte détail** (clic nœud) : panneau latéral avec sections icônées, puces catégories / JSON-LD différenciées, lien vers la fiche entreprise si applicable.

## API

- **`GET /api/entreprises/graph`**  
  Paramètres de requête typiques : `search`, `domain`, `only_credit`, `max_link_rows`, `max_enterprises`, `entreprise_ids` (liste d’IDs séparés par des virgules).  
  Réponse JSON : `nodes`, `edges`, `stats`, `graph_scope` (filtres et métadonnées d’échantillonnage).

Les nœuds **entreprise** peuvent inclure `thumb_url` / `thumbnail_url` à partir du champ **`entreprises.favicon`** (scraper unifié). Les nœuds **domaine** utilisent **`external_domains.thumb_url`** alimenté par le mini-scrape (favicon / aperçu OG), sans URL de services tiers type Google favicon.

## Données et pipeline

1. Lors d’un scraping, les **liens externes** pertinents sont extraits et, après mini-scrape optionnel, stockés dans le schéma relationnel (voir ci-dessous).
2. **`services/external_mini_scraper.py`** : GET homepage (+ pages internes de premier niveau), extraction titre, meta, OG, images, téléphones, lieu (réutilisation de `location_harvest`), favicon depuis balises `link` ou `/favicon.ico` logique, classification grossière (`external_site_classifier`).
3. **`services/database/external_links.py`** : création / migration des tables, fusion `external_domains`, construction du graphe pour l’API (`ExternalLinksManager`).

### Tables principales (graphe externe)

| Table | Rôle |
|--------|------|
| `external_domains` | Un enregistrement par hôte normalisé : titre, description, URL résolue, `thumb_url`, `graph_group`, erreur mini-scrape, date. |
| `entreprise_external_links` | Lien sortant pour un couple (entreprise, scraper) vers un `domain_id`. |
| `external_link_pages` | Pages mini-scrapées par lien (profondeur, statut HTTP, titre, etc.). |
| `external_link_page_*` | Détails normalisés : propriétés OG, images, lieu structuré, téléphones (plus de gros champs JSON sur la page). |

Les anciennes colonnes JSON sur `external_link_pages` sont **retirées par migration** si elles existent encore (données portées par les tables filles).

## Scripts utiles

- **`python scripts/clear_external_graph.py`** : vide les tables du graphe externe (domaines, liens, pages, taxonomies associées) sans supprimer les tables.  
  Voir aussi [Scripts](../scripts/SCRIPTS.md).

## Tests

- `scripts/tests/test_entreprises_graph.py` : tests ciblés sur le graphe / API (selon évolutions du dépôt).

## Variables d’environnement (mini-scrape)

Préfixe **`EXTERNAL_MINI_SCRAPE_`** (certaines clés ont un repli `AGENCY_MINI_SCRAPE_*` pour compatibilité) : timeouts, nombre max de domaines, délai entre requêtes, activation du niveau 1, etc. Consulter le code de `external_mini_scraper.py` et `.env` / `env.example` pour la liste à jour.

## Fichiers front principaux

- `templates/pages/graph_entreprises.html`
- `static/js/graph_entreprises.js`
- `static/css/graph_entreprises.css`
