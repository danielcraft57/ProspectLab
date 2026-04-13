# API Pipeline, Kanban et touchpoints (session web)

Ces routes sont sous préfixe `/api`, protégées par `@login_required` (session utilisateur connecté). Elles ne font pas partie de l’API publique Bearer documentée dans `API_PUBLIQUE.md`.

## Liste des statuts référentiels

**GET** `/api/entreprise/statuts`

Réponse : tableau JSON de chaînes (statuts supportés pour `PATCH` / mise à jour entreprise).

## Mise à jour du statut pipeline

**POST**, **PUT** ou **PATCH** `/api/entreprise/<entreprise_id>/statut`

Body JSON :

```json
{ "statut": "Gagné" }
```

Si le statut n’est pas dans le référentiel : **400** avec `statut invalide`.

## Vue Kanban (effectifs par colonne)

**GET** `/api/entreprise/pipeline/kanban`

### Paramètres de requête

- **analyse_id** (int, optionnel) : ne garder que les entreprises rattachées à cette analyse.

Tous les filtres optionnels de **GET** `/api/entreprises` sont également reconnus (même noms et sémantique), par exemple :

| Paramètre | Rôle |
|-----------|------|
| secteur | Filtre secteur exact |
| statut | Filtre statut (avec extension Gagné / Perdu / Relance comme sur la liste) |
| opportunite | Opportunité |
| favori | `true` pour favoris uniquement |
| search | Recherche multi-mots |
| security_min, security_max, security_null | Filtres score sécurité |
| pentest_min, pentest_max, pentest_null | Filtres score pentest |
| seo_min, seo_max, seo_null | Filtres score SEO |
| groupe_id, no_group | Groupe d’entreprises |
| has_email | Au moins un email connu |
| cms, framework, has_blog, has_form, has_tunnel | Segmentation |
| performance_min, performance_max | Score performance |
| tags_contains, tags_any, tags_all | Filtres sur le champ tags |

Dès qu’au moins un de ces filtres est actif, l’agrégation Kanban utilise la **même sous-requête** que le comptage liste (`count_entreprises`), y compris les conditions sur les scores.

### Réponse (champs utiles)

- **success** : booléen
- **total** : nombre d’entreprises correspondant aux critères
- **sans_statut** : nombre sans statut (NULL ou vide)
- **counts** : objet `statut -> effectif` pour les statuts du référentiel (y compris les zéros)
- **columns** : liste ordonnée `{ statut, count, couleur }` (hex pour pastilles UI)
- **hors_referentiel** : `{ statut, count }` pour les valeurs en base hors référentiel
- **filtered** : `true` si des filtres liste ont été appliqués
- **filters** : présent seulement si **filtered** est `true` (filtres effectivement pris en compte)

L’interface web **n’affiche dans la barre Pipeline que les colonnes avec effectif strictement supérieur à 0** (idem pour la ligne « hors référentiel » : entrées à 0 masquées).

## Distinction `statut` vs prospection CRM

- **`statut`** (champ historique) : statuts campagne / email / délivrabilité, alignés sur **GET** `/api/entreprise/statuts` et **GET** `/api/entreprise/pipeline/kanban`.
- **`etape_prospection`** : étape du **Kanban commercial** (À prospecter → Contacté → RDV → Proposition → Gagné / Perdu), sans remplacer le champ `statut`.

## Étapes CRM (référentiel Kanban prospection)

**GET** `/api/entreprise/crm/etapes`

Réponse : tableau JSON ordonné des étapes valides pour `etape_prospection`.

## Mise à jour de l’étape prospection

**PATCH** ou **PUT** `/api/entreprise/<entreprise_id>/etape-prospection`

Body JSON :

```json
{ "etape": "Contacté" }
```

Si l’étape n’est pas dans le référentiel CRM : **400** avec `etape invalide`. Entreprise introuvable : **404**.

## Vue Kanban prospection CRM (effectifs par étape)

**GET** `/api/entreprise/pipeline/kanban-crm`

Mêmes query params que **GET** `/api/entreprise/pipeline/kanban` (y compris filtres liste et scores).

### Réponse (champs utiles)

- **success**, **total**, **filtered**, **filters** : comme le Kanban statut
- **counts** : objet `étape -> effectif` pour les étapes du référentiel CRM
- **columns** : liste ordonnée `{ etape, count, couleur }`
- **hors_referentiel** : `{ etape, count }` pour des valeurs en base hors référentiel CRM

## Touchpoints (journal d’interactions)

**GET** `/api/entreprise/<entreprise_id>/touchpoints`

Query : `limit` (défaut 50), `offset` (défaut 0).

**POST** `/api/entreprise/<entreprise_id>/touchpoints`

Body JSON : `canal`, `sujet` (requis), `note`, `happened_at` (optionnels).

**PATCH** `/api/entreprise/<entreprise_id>/touchpoints/<touchpoint_id>`

Body JSON partiel : `canal`, `sujet`, `note` (y compris `null` pour vider), `happened_at`.

**DELETE** `/api/entreprise/<entreprise_id>/touchpoints/<touchpoint_id>`

## Interface web (page Entreprises)

Fichiers principaux : `static/js/modules/entreprises/api.js` (appels API), `static/js/entreprises.refactored.js` (modale + barre), `static/css/modules/pages/entreprises.css` (barre + onglet Prospection, y compris **thème sombre**).

Sur la page **Entreprises** (`/entreprises`) :

- Une **barre « Prospection CRM »** sous l’en-tête des résultats affiche les effectifs par **étape prospection** (`etape_prospection`) pour les **mêmes filtres** que la liste. Seules les étapes avec au moins **un** prospect sont affichées (pas les zéros).
- Dans la **modale de détail**, l’onglet **Prospection** permet de :
  - modifier l’**étape prospection** (Kanban CRM, `/api/entreprise/crm/etapes`) ;
  - modifier le **statut campagnes / email** (référentiel `/api/entreprise/statuts`) ;
  - consulter, **ajouter** et **supprimer** des **touchpoints** (raccourcis canal Email / Appel / RDV / Note).

L’onglet **Pipeline d’audit** existant reste dédié au suivi des analyses (scraping, technique, SEO, etc.), distinct du pipeline commercial.

- Filtre avancé **Étape prospection** + bouton **Top 50 à appeler** : vue priorisée (score pondéré SEO / sécu / perf / opportunité, puis ancienneté du dernier touchpoint).

## Priorité commerciale (Sprint 2)

**GET** `/api/commercial/priority-profiles`

Réponse : `{ success, items: [{ id, nom, poids: { w_seo, w_secu, w_perf, w_opp }, date_creation }] }`

**GET** `/api/entreprises/commercial/top`

Mêmes filtres query que **GET** `/api/entreprises` (y compris `etape_prospection`).

Paramètres supplémentaires :

| Paramètre | Rôle |
|-----------|------|
| profile_id | ID d’un profil dans `commercial_priority_profiles` (poids prédéfinis) |
| w_seo, w_secu, w_perf, w_opp | Poids manuels (0–1, normalisés en somme 1) si pas de `profile_id` |
| priority_min | Seuil minimal sur `priority_score` (0–100) |
| limit | Défaut 50, max 200 |

Chaque entreprise retournée inclut **`priority_score`**, **`last_touchpoint_at`** (ou `NULL` si aucun touchpoint / table absente).

### Ciblage campagnes (`/api/ciblage/entreprises`)

Paramètres supplémentaires (query) : **`etape_prospection`**, **`sort_commercial`** (`1`), **`priority_min`**, **`commercial_profile_id`**, **`commercial_limit`**.  
Avec `sort_commercial`, la réponse est triée par `priority_score` décroissant ; chaque entreprise peut inclure **`priority_score`**.

## Schéma base de données

- Colonne **`entreprises.etape_prospection`** : étape Kanban CRM (texte, défaut « À prospecter »), migrations dans `services/database/schema.py`.
- Table **`entreprise_touchpoints`** : `entreprise_id`, `canal`, `sujet`, `note`, `happened_at`, `created_at`, `created_by`. Sur une vieille base SQLite sans cette table, `ensure_entreprise_touchpoints_table()` (instanciation `Database`) la crée au prochain redémarrage app / worker.
- Table **`commercial_priority_profiles`** : profils de pondération (`poids_json`), création / migration idempotente au démarrage (`ensure_commercial_priority_profiles_table`).
