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

- Une **barre « Pipeline »** sous l’en-tête des résultats affiche les effectifs par statut pour les **mêmes filtres** que la liste (recherche, secteur, scores, tags, etc.). Elle est mise à jour après chaque chargement de liste. Seuls les statuts avec au moins **un** prospect sont affichés (pas les zéros).
- Dans la **modale de détail**, l’onglet **Prospection** permet de :
  - modifier le **statut pipeline** (liste alignée sur `/api/entreprise/statuts`) ;
  - consulter, **ajouter** et **supprimer** des **touchpoints** (journal d’interactions).

L’onglet **Pipeline d’audit** existant reste dédié au suivi des analyses (scraping, technique, SEO, etc.), distinct du pipeline commercial.

## Schéma base de données

Table **`entreprise_touchpoints`** : `entreprise_id`, `canal`, `sujet`, `note`, `happened_at`, `created_at`, `created_by` (voir `services/database/schema.py`, migrations au démarrage).
