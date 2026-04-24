# Graph entreprises (liens externes)

Vue interactive **entreprises ↔ domaines tiers** découverts lors du scraping (liens sortants, crédits éventuels). Elle complète la fiche entreprise sans la remplacer.

## Accès

- **URL :** `/graph-entreprises`
- **Menu :** entrée dédiée dans la navigation (à côté des autres pages métier).

## Fonctionnalités côté interface

- Graphe **vis-network** : zoom, cadrage (manuel), export **PNG**, historique de vues (précédent / suivant), thème clair/sombre/auto.
- **Layout initial** : positions calculées (entreprises en cercle + “molécules” autour des voisins) pour éviter l’affichage “en ligne”.
- **Pas de physique ni recadrage auto** : la vue reste stable (pas de `fit()` automatique). Un bouton **Ajuster** reste disponible si besoin.
- **Rail du haut** : puces de synthèse (agences, entreprises, domaines, nœuds, liens, etc.) centrées sous la barre du cadre graphe.
- **Dock d’actions** (colonne à droite sur la zone graphe) : plein écran, vue/zoom, rechargement périmètre, ajuster, export, thème. Le dock est ancré en **haut et bas** de la zone canvas (`top` / `bottom`) pour que la hauteur suive celle du conteneur et que le défilement interne (`overflow-y: auto`) reste fiable (évite les coupures dues à un `max-height: 100%` mal résolu). Variable CSS **`--graph-entreprises-dock-slot`** : marge réservée pour la carte détail et le positionnement du panneau.
- **Plein écran** : le bloc `#graph-entreprises-wrap` passe en plein navigateur ou pseudo-plein écran ; languette **Filtres & périmètre** et panneau associé ; les filtres hors plein écran restent dans la page au-dessus du cadre.
- **Conteneur graphe** : canvas vis-network dans `#graph-entreprises-canvas` (pile `#graph-entreprises-canvas-stack`).
- **Filtres locaux** : types de nœuds (fiche, agence, autres domaines), types d’arêtes (crédit, lien, réf. site, fiche en base), libellés compacts, recherche sur le graphe chargé, option **Zones** (teinte des fiches par localisation).
- **Périmètre serveur** : recherche texte, filtre par domaine, plafonds lignes / entreprises, IDs entreprises, option « crédits seuls » ; rechargement via **Actualiser**.
- **Chargement initial allégé (anti-freeze)** : au premier affichage, si les champs périmètre sont vides, la page applique automatiquement `max_link_rows=1200` et `max_enterprises=160` avant le premier appel API.
- **Comportement inchangé en manuel** : dès qu'un utilisateur saisit un périmètre (recherche, domaine, IDs, plafonds, crédits seuls), ces valeurs prennent la priorité.
- **Thème** : bouton **Auto → Sombre → Clair** (préférence stockée dans `localStorage` ; les infobulles synchronisent des variables CSS sur `:root` car le conteneur `vis-tooltip` est hors de la page).
- **Infobulles (survol)** : contenu riche en **HTML injecté comme nœud DOM** (exigence vis-network ≥ 9 : les chaînes HTML dans `title` ne sont plus interprétées). Cartes avec icônes Material, stats **libellé + valeur sur une même ligne**, blocs schémas / JSON-LD, liens cliquables vers le site fiche.
- **Carte détail** (clic nœud) : panneau latéral avec sections icônées, puces catégories / JSON-LD différenciées, lien vers la fiche entreprise si applicable.

### Ancienne URL

- La route **`/agences-reseau`** (ancien libellé « Réseau agences ») redirige en **301** vers **`/graph-entreprises`** (favoris et liens profonds).

## API

- **`GET /api/entreprises/graph`**  
  Paramètres de requête typiques : `search`, `domain`, `only_credit`, `max_link_rows`, `max_enterprises`, `entreprise_ids` (liste d’IDs séparés par des virgules).  
  Réponse JSON : `nodes`, `edges`, `stats`, `graph_scope` (filtres et métadonnées d’échantillonnage).

### Notes de performance recommandées

- Garder des plafonds modestes pour l'ouverture (ex. `1200 / 160`) puis élargir progressivement.
- Utiliser `entreprise_ids` quand un sous-ensemble est connu (mode investigation ciblée).
- En cas de bannière « Aperçu tronqué », affiner d'abord `search` / `domain` avant d'augmenter les plafonds.

Les nœuds **entreprise** peuvent inclure `thumb_url` / `thumbnail_url` à partir du champ **`entreprises.favicon`** (scraper unifié). Les nœuds **domaine** utilisent **`external_domains.thumb_url`** alimenté par le mini-scrape (favicon / aperçu OG), sans URL de services tiers type Google favicon.

## Données et pipeline

1. Lors d’un scraping, les **liens externes** pertinents sont extraits et, après mini-scrape optionnel, stockés dans le schéma relationnel (voir ci-dessous).
2. **`services/external_mini_scraper.py`** : GET homepage (+ pages internes de premier niveau), extraction titre, meta, OG, images, téléphones, lieu (réutilisation de `location_harvest`), favicon depuis balises `link` ou `/favicon.ico` logique, classification grossière (`external_site_classifier`).
3. **`services/database/external_links.py`** : création / migration des tables, fusion `external_domains`, construction du graphe pour l’API (`ExternalLinksManager`).

### Temps réel (mini-scrape “un par un”)

- Le mini-scrape asynchrone émet **un événement par domaine** dès qu’il est mini-scrapé et persisté.
- Le graphe crée alors immédiatement le **nœud** (domaine) et l’**arête** depuis la fiche entreprise, sans attendre la fin du lot.

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

- `templates/pages/graph_entreprises.html` — gabarit, `window.GRAPH_ENTREPRISES_PAGE` (ex. URL fiche entreprise).
- `static/js/graph_entreprises.js` — chargement API, vis-network, physique, plein écran, dock, infobulles DOM, carte détail.
- `static/css/graph_entreprises.css` — thème M3, rail, dock, plein écran, légende, carte détail.

### Backend

- Route page : `routes/main.py` (`graph_entreprises`) ; redirection depuis `agences_reseau_redirect` (`/agences-reseau`).
