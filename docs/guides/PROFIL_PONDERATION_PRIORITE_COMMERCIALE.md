# Profil de pondération et priorité commerciale

Ce document explique **à quoi sert le profil de pondération** dans ProspectLab, pour les utilisateurs comme pour les développeurs qui brancheraient l’API.

## En une phrase

Le profil de pondération **ne filtre pas** la liste à lui seul : il définit **quels critères comptent le plus** lorsque l’application calcule un **score de priorité commerciale**, notamment pour répondre à la question « **qui appeler en premier ?** ».

## Contexte : la vue « Top commercial »

Lorsque vous utilisez la fonctionnalité du type **« Top 50 à appeler »** (liste entreprises), ProspectLab doit **classer** les comptes. Le calcul combine en général plusieurs signaux, par exemple :

- **SEO** — site peu optimisé → angle de prospection « visibilité / référencement » ;
- **Sécurité** — HTTPS, indicateurs de risque → angle « conformité / cyber » ;
- **Performance** — lenteur, expérience utilisateur → angle « refonte / perf » ;
- **Opportunité** — potentiel déjà estimé dans la base (champ / logique métier associée).

Un **profil** est un ensemble de **poids** (souvent notés `w_seo`, `w_secu`, `w_perf`, `w_opp`) qui indique la part relative de chaque axe dans ce score. Même données en entrée, **l’ordre du classement peut changer** selon le profil choisi.

## Exemples d’usage métier

| Besoin | Idée |
|--------|------|
| Vous vendez surtout de l’**audit sécurité** | Privilégier un profil **sécurité** pour faire remonter les comptes les plus « vendables » sur ce thème. |
| Vous vendez surtout du **SEO** | Profil **SEO prioritaire** pour prioriser les scores SEO défavorables comme levier de discussion. |
| Pas de priorité fixe | **Défaut (équilibré)** ou profil **Équilibré** : répartition équitable entre les axes. |

## Ce que ce n’est pas

- **Ce n’est pas** les curseurs **min / max** des filtres « Score technique », « Score SEO », « Score pentest » dans les filtres avancés. Ceux-ci servent à **restreindre** les entreprises affichées selon des **seuils** sur les scores stockés (ex. SEO entre 40 et 60).
- Changer de profil **ne déplace pas** ces curseurs : il change la **recette du tri priorité** lorsque la **vue Top commercial** (ou un ciblage campagne équivalent) applique le score pondéré.

## Où c’est utilisé dans l’application

- **Page Entreprises** : filtres avancés (section Scores) — profil + visualisation des poids ; bouton **Top 50 à appeler**.
- **Campagnes** (ciblage par critères) : options de tri / priorité alignées sur les mêmes idées (`sort_commercial`, `commercial_profile_id`, etc., selon l’évolution du produit).

## API et données

- Liste des profils : `GET /api/commercial/priority-profiles` (champ `poids` par item).
- Table : `commercial_priority_profiles` (`nom`, `poids_json`).
- Les profils par défaut sont insérés de façon **idempotente** au démarrage / migration (voir `schema_commercial_priority_profile_seeds()` dans `services/database/schema.py`).

## Voir aussi

- Roadmap commerciale : `docs/developpement/ROADMAP_COMMERCIAL_PRIORISATION.md`
- Pipeline CRM / prospection : `docs/guides/API_PIPELINE_KANBAN.md`
- Segmentation et ciblage : `docs/developpement/SEGMENTATION_AVANCEE_PROSPECTS.md`
