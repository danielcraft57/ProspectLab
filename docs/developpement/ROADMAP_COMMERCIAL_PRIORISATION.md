# Roadmap — Chaîne commerciale & priorisation (ProspectLab)

Vue synthétique des trois vagues prévues : **chaîne de vente exploitable**, **priorisation intelligente**, **rétention & différenciation**. Les détails techniques vivent dans le code et les guides API (`API_PIPELINE_KANBAN.md`, `ROADMAP_GLOBAL.md` pour le contexte produit plus large).

---

## Sprint 1 — Impact direct vente (1 à 2 semaines)

**Objectif** : une vraie chaîne commerciale utilisable immédiatement.

| Thème | Livrable | Statut |
|--------|-----------|--------|
| Touchpoints CRM (v1) | Journal par entreprise : email / appel / RDV / note / date | Fait |
| Kanban prospection (v1) | Colonnes : À prospecter → Contacté → RDV → Proposition → Gagné / Perdu (`etape_prospection`) | Fait |
| Actions rapides | Depuis la fiche : ajouter un touchpoint, changer d’étape, raccourcis canal | Fait |

**Pourquoi maintenant** : donner aux commerciaux un fil conducteur clair (interactions + étapes) sans confondre avec le `statut` historique (campagnes / email).

---

## Sprint 2 — Priorisation intelligente (≈ 1 semaine)

**Objectif** : accélérer le choix des leads à contacter en premier.

| Thème | Livrable | Statut |
|--------|-----------|--------|
| Scores de priorité configurables (v1) | Poids SEO / sécu / perf / opportunité ; profils nommés en base (`commercial_priority_profiles`) | Fait (v1 API + migration auto) |
| Vues « Commercial » | `GET /api/entreprises/commercial/top` + bouton « Top 50 à appeler » (liste) | Fait (v1) |
| Segments enrichis | Liste + ciblage : `etape_prospection` ; ciblage : `sort_commercial`, `priority_min`, `commercial_profile_id`, `commercial_limit` (JSON `criteres`) | Fait (v1 API + campagnes) |
| Segments — UX campagnes | Formulaire « Par critères » : pipeline CRM + tri / seuil / profil / limite ; **résumé** sous le segment choisi ; **enregistrer** les critères courants comme nouveau segment | Fait (v1) |
| Prévisualisation segment (API) | `GET /api/ciblage/segments/<id>/preview?limit=` → `{ total, items[], segment }` | Fait (v1 ; coût identique au chargement liste tant qu’il n’y a pas de `COUNT` SQL dédié) |
| Thème clair / sombre | Toolbar commerciale, cartes priorité, score dans campagnes, touchpoints | Fait (v1) |

**Pourquoi maintenant** : réduire le temps passé à trier la liste et aligner l’effort sur les comptes à fort potentiel et à faible récence de contact.

**Suite courte (hors Sprint 3)** : builder visuel de règles, `COUNT` SQL pour les gros segments, slide-over « entreprises du segment » sans tout charger côté client.

---

## Sprint 3 — Rétention & valeur différenciante (1 à 2 semaines)

**Objectif** : renforcer l’argumentaire et les relances automatiques.

| Thème | Livrable | Statut |
|--------|-----------|--------|
| Rescan planifié + avant/après (v1) | Comparaison de snapshots (perf / SEO / sécu) sur entreprises suivies | À faire |
| Alertes intelligentes (v1) | SSL qui expire, forte baisse perf/SEO, site KO | À faire |
| Radar concurrence (MVP) | Écran comparatif simple par secteur / ville | À faire |

**Pourquoi maintenant** : matérialiser la valeur dans le temps (suivi, preuves, urgency) au-delà du premier contact.

---

## Liens utiles

- Rôle du **profil de pondération** (utilisateurs & dev) : `docs/guides/PROFIL_PONDERATION_PRIORITE_COMMERCIALE.md`
- Pipeline CRM vs statut campagne : `docs/guides/API_PIPELINE_KANBAN.md`
- Segmentation & segments campagnes : `docs/developpement/SEGMENTATION_AVANCEE_PROSPECTS.md`, API ciblage `/api/ciblage/segments`, prévisualisation `/api/ciblage/segments/<id>/preview`
