## Segmentation avancée des prospects – Spécification v1

### 1. Objectif produit

Permettre de cibler finement les prospects en combinant :

- Données **business** (secteur, taille, zone, statut, opportunité, favoris).
- Données **techniques** (CMS, framework front/back, scores sécurité/perf, présence HTTPS, etc.).
- Données **contenu / UX** (présence blog, formulaire, tunnel e‑commerce).
- Données **scraping / OSINT / SEO** (tags intelligents, signaux d’intention…).

Cette segmentation doit être :

- **Requêtée** côté API pour alimenter :
  - la **liste des entreprises** (page `entreprises`),
  - le **ciblage des campagnes email** (page `campagnes`, étape 1),
  - l’**API publique** (cas Notion/CRM/Make).
- **Enregistrable** sous forme de **segments nommés**, réutilisés dans les campagnes.
- **Compréhensible visuellement** (résumé texte lisible des critères).

---

### 2. Backend – Modèle de données & services

#### 2.1. Colonnes côté `entreprises`

Ajouter (via `DatabaseSchema.safe_execute_sql`) les colonnes suivantes dans la table `entreprises` :

- `cms TEXT`
- `framework TEXT`
- `has_blog INTEGER` (0/1)
- `has_contact_form INTEGER` (0/1)
- `has_checkout INTEGER` (0/1)
- `performance_score INTEGER` (optionnel, si exposé en résumé)

Ces colonnes seront alimentées à partir des dernières analyses techniques/SEO/scraping.

#### 2.2. Alimentation depuis les analyses

Points d’accroche (à consolider dans une itération ultérieure) :

- À la fin d’une **analyse technique** :
  - Détecter CMS, framework, flags (blog/form/tunnel) dans `TechnicalAnalyzer`.
  - Mettre à jour `entreprises.cms`, `entreprises.framework`, `has_blog`, `has_contact_form`, `has_checkout`, `performance_score` pour l’entreprise concernée.
- À la fin d’une **analyse SEO / scraping** :
  - Optionnel : enrichir certains flags (présence blog, pages de type /blog/, etc.).

> v1 : on prépare le schéma + support de filtres côté `EntrepriseManager`; l’alimentation détaillée pourra être branchée plus tard.

#### 2.3. Filtres dans `EntrepriseManager`

Dans `services/database/entreprises.py` :

- Étendre `get_entreprises(...)` et `count_entreprises(...)` pour supporter de nouveaux filtres dans `filters` :

  - `cms` : string ou liste de CMS.
  - `framework` : string ou liste.
  - `has_blog` : bool (filtre `e.has_blog = 1`).
  - `has_form` : bool (`e.has_contact_form = 1`).
  - `has_tunnel` : bool (`e.has_checkout = 1`).
  - `performance_min` / `performance_max` : seuils sur `performance_score` (ou à défaut sur un score dérivé des analyses techniques).

- Logique SQL typique (pseudo) :

  - `cms` / `framework` :
    - si liste : `e.cms IN (?, ?, ...)`
    - sinon : `e.cms = ?`
  - `has_*` : test sur colonnes entières (`1`).
  - `performance_*` : contraintes `>=` / `<=` sur la valeur (en prenant en compte `NULL`).

#### 2.4. API `/api/entreprises`

Dans `routes/api.py`, route `@api_bp.route('/entreprises')` :

- Ajouter des query params supportés :

  - `cms`
  - `framework`
  - `has_blog` (`1/true`)
  - `has_form` (`1/true`)
  - `has_tunnel` (`1/true`)
  - `performance_min`, `performance_max` (0–100).

- Adapter le `filters = {...}` et la fonction `keep_filter` pour laisser passer ces valeurs.
- Transmettre `filters` telles quelles à `database.get_entreprises(...)` et `database.count_entreprises(...)`.

#### 2.5. Ciblage campagnes & segments

Dans `services/database/entreprises.py` :

- Étendre `get_entreprises_for_campagne(filters=None)` pour reconnaître les mêmes filtres métier :
  - `secteur`, `secteur_contains`, `opportunite`, `statut`, `tags_contains`, `favori`, `search`, `score_securite_max`, `exclude_already_contacted`, `groupe_ids` (déjà en place),
  - **+** `cms`, `framework`, `has_blog`, `has_form`, `has_tunnel`, `performance_max` (pour limiter aux sites faibles).
  - **+ (Sprint 2)** `etape_prospection` ; tri / filtre priorité : `sort_commercial`, `priority_min`, `commercial_profile_id` (ID table `commercial_priority_profiles`), `commercial_limit`. Les segments peuvent inclure ces clés dans `criteres_json` ; `loadEntreprisesWithFilters` les transmet à `/api/ciblage/entreprises`.

Dans `services/database/campagnes.py` :

- Les segments de ciblage (`segments_ciblage`) stockent leurs critères dans `criteres_json` :
  - Structurer `criteres_json` pour refléter exactement les filtres supportés (`cms`, `has_blog`, etc.).

Dans `routes/other.py` :

- **(v1)** : conserver les endpoints existants :
  - `/api/ciblage/entreprises` (ciblage direct sur critères),
  - `/api/ciblage/segments` (CRUD segments).
- **(v2)** : ajouter un endpoint de *prévisualisation* :
  - `GET /api/ciblage/segments/<id>/preview` :
    - charge le segment via `CampagneManager.get_segment(id)`,
    - applique `criteres` sur `EntrepriseManager.get_entreprises_for_campagne`,
    - renvoie `{ "total": <int>, "items": [ ... ] }` avec un `limit` raisonnable (ex. 50).

---

### 3. Front – page `entreprises`

#### 3.1. Panneau de filtres avancés

Dans `templates/pages/entreprises.html` :

- Conserver la structure actuelle, mais ajouter des groupes de filtres :
  - **Technos & CMS**
    - `select#filter-cms`
    - `select#filter-framework`
  - **Comportements / contenu**
    - `checkbox#filter-has-blog` (“Avec blog”)
    - `checkbox#filter-has-form` (“Avec formulaire de contact”)
    - `checkbox#filter-has-tunnel` (“Avec tunnel e‑commerce”)

Dans `static/js/entreprises.refactored.js` :

- Dans `getCurrentFilters()` :
  - lire `filter-cms`, `filter-framework`, `filter-has-blog`, `filter-has-form`, `filter-has-tunnel`,
  - ajouter les clés `cms`, `framework`, `has_blog`, `has_form`, `has_tunnel` dans l’objet `filters` (avec les mêmes conventions que l’API).

#### 3.2. Micro‑interactions & animation (v1.5)

- Panneau “Filtres avancés” :
  - Animation d’ouverture/fermeture (classe `.is-open` + transition `max-height`, `opacity`, `transform`).
  - Badge `#active-filters-count` mis à jour à partir de `getCurrentFilters()` (hors pagination), avec une petite animation de scale/fade à chaque changement.
- Skeletons de chargement :
  - Remplacer le texte “Chargement des entreprises...” par 3–6 cartes skeleton (`div.entreprise-card.skeleton`) quand la requête API est en cours.
  - Animation shimmer en CSS uniquement.

---

### 4. Front – page `campagnes` (builder de segments)

Dans `templates/pages/campagnes.html` (étape 1) :

- Sous le select `#ciblage-segment` :
  - `p#ciblage-segment-summary` pour afficher un résumé lisible des critères,
  - un bouton lien `#ciblage-segment-preview-btn` (“Voir les entreprises de ce segment”).

Dans `static/js/campagnes.js` :

- Dans `loadSegmentsCiblage()` :
  - conserver `seg.criteres` dans `opt.dataset.criteres` (JSON stringify),
  - au `change` sur `#ciblage-segment` :
    - parser `dataset.criteres`,
    - transformer l’objet en texte métier (“Secteur contient BTP · CMS = WordPress · SEO ≤ 50 · Sans HTTPS”),
    - l’afficher dans `#ciblage-segment-summary`.

- Panneau slide‑over de prévisualisation :
  - Ajouter un panneau latéral droit masqué (`#segment-preview-panel`),
  - au clic sur `#ciblage-segment-preview-btn` :
    - appeler `/api/ciblage/segments/<id>/preview`,
    - afficher un échantillon de cartes entreprises à l’intérieur,
    - ouvrir le panneau avec une transition `transform: translateX(100%) -> 0`.

---

### 5. Roadmap de mise en œuvre

1. **Step 1 – Backend minimal**
   - Ajouter les colonnes de résumé sur `entreprises` (cms/framework/flags/perf).
   - Étendre `get_entreprises` / `count_entreprises` et `/api/entreprises` pour `cms` + `framework`.
   - Étendre `get_entreprises_for_campagne` pour accepter `cms` / `framework`.

2. **Step 2 – Premiers filtres UI**
   - Ajouter les selects CMS/framework + wiring JS sur la page `entreprises`.
   - Utiliser les mêmes filtres dans le mode “Par critères” de `campagnes` (ciblage direct).

3. **Step 3 – Flags contenu & UX**
   - Ajouter flags `has_blog` / `has_form` / `has_tunnel` en BDD + backend.
   - Ajouter les checkboxes correspondantes sur `entreprises` + `campagnes`.
   - Mettre en place les skeletons et micro‑interactions sur les filtres.

4. **Step 4 – Segments avancés**
   - Implémenter `/api/ciblage/segments/<id>/preview`.
   - Résumé lisible + panneau de prévisualisation dans `campagnes` (étape 1).
   - (v2) Builder de règles complet pour créer des segments à partir de la liste entreprises ou du wizard campagnes.

