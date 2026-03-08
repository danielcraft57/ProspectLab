## Roadmap globale ProspectLab

Cette roadmap regroupe les grandes idées de développement orientées prospection pour le service de dev web.

### 1. Détection d’anciens sites / techno obsolète

- **Statut**: ✅ Implémenté (détection + tag automatique)

- Détection automatique des stacks “à moderniser” (dans `services/database/technical.py` et `services/technical_analyzer.py`) :
  - WordPress très ancien (≤ 4.x) ou à mettre à jour (5.x &lt; 5.5), Bootstrap ≤ 3, jQuery &lt; 3.5.
  - Sites en HTTP uniquement, SSL invalide, mixed content.
  - Domaine très ancien (création ≤ 2014, mise à jour ≤ 2018), scores sécurité/performance faibles.
- Tag automatique sur les entreprises concernées : **`fort_potentiel_refonte`** (affiché “Fort potentiel refonte” dans l’UI).
- Tags intelligents supplémentaires (langue détectée, risque cyber, SEO à améliorer, perf lente, sans HTTPS) gérés dans `services/database/entreprises.py` et affichés avec styles dédiés et filtres (liste entreprises).
- Les indicateurs sont calculés à chaque sauvegarde/mise à jour d’analyse technique ; aucun changement de schéma BDD (utilisation de la colonne `tags` JSON existante).

### 2. Segmentation avancée des prospects

- **Statut**: ✅ Largement implémenté (liste entreprises + campagnes)  
  Filtres avancés et segments de ciblage déjà disponibles dans la page `campagnes` et l’API de ciblage des entreprises.

- Filtres combinés dans la liste d’entreprises et le ciblage campagnes :
  - Secteur.
  - CMS détecté (WordPress, PrestaShop, Symfony, SPA React, etc.).
  - Technos front/back principales.
  - Note SEO minimale.
  - Présence ou non de formulaires / tunnel e‑commerce / blog.
- Sauvegarde de **segments** (ex: “PME BTP avec WordPress ancien, mauvais mobile”).

### 3. Workflows de prospection intégrés (Kanban)

- **Statut**: 🔴 À faire (UI Kanban + persistance par entreprise)

- Kanban par étapes :
  - “À prospecter → Contacté → RDV pris → Proposition envoyée → Gagné / Perdu”.
- Lier chaque carte à :
  - Une entreprise.
  - Le rapport d’audit généré (lien rapide vers le rapport HTML/PDF).

### 4. Templates d’emails basés sur l’audit

- **Statut**: 🟡 Partiellement implémenté  
  - Moteur de templates alimentés par les analyses (technique/SEO/scraping, etc.).  
  - Suggestions automatiques de modèles par entreprise (`/api/entreprise/<id>/template-suggestions` + UI à l’étape 3 des campagnes).  
  - **À faire**: bouton “Générer email de prise de contact” qui insère automatiquement 2–3 problèmes + quick wins dans un brouillon.

- Bouton “Générer email de prise de contact” :
  - Insérer automatiquement **2–3 problèmes détectés** sur le site.
  - Proposer **1–2 quick wins**.
  - Ajouter un **CTA** (RDV, audit gratuit, etc.).
- Variantes de templates :
  - Cold email initial.
  - Relance.
  - Email post‑RDV / post‑démo.

### 5. Suivi des modifications de site dans le temps

- **Statut**: 🔴 À faire (planification re‑scan + comparaison avant/après)

- Re‑scan programmé (hebdo / mensuel) pour certains prospects :
  - Détecter les changements :
    - Nouveau site / refonte.
    - HTTPS activé.
    - Nouveau CMS / nouvelle techno.
  - Notifier si le prospect a agi sans nous :
    - Idée : relance ou mise à jour du score d’opportunité.

### 6. Enrichissement “business” automatique

- **Statut**: 🟡 En partie en place (Sirene)  
  Sirene est déjà utilisé côté backend pour enrichir certaines données, mais la priorisation automatique par CA/effectif/région reste à formaliser dans l’UI et les scores.

- Via API publiques (Sirene déjà branché, et autres si besoin) :
  - CA, effectif, date de création, région.
- Aider à **prioriser les prospects** selon leur capacité d’investissement.

### 7. Vue “Radar concurrence locale”

- **Statut**: 🔴 À faire

- Pour un mot‑clé / région (via Google Maps) :
  - Comparer plusieurs entreprises sur un seul écran :
    - Perf, SEO, techno, note Google, volume d’avis, etc.
  - Identifier les “maillons faibles” dans une zone donnée.

### 8. Bibliothèque de “cas d’usage / success stories”

- **Statut**: 🔴 À faire

- Associer à une entreprise gagnée :
  - Avant : techno ancienne → problèmes.
  - Après : refonte → gains (perf, SEO, conversions).
- Sur une nouvelle fiche entreprise :
  - Suggérer des cas similaires à présenter en RDV.

### 9. Alertes intelligentes

- **Statut**: 🔴 À faire (notifications + règles d’alerte)

- Notifications quand :
  - Un domaine surveillé expire bientôt.
  - SSL proche d’expiration.
  - Gros soucis :
    - HTTP only.
    - Erreurs 5xx récurrentes.
    - Pages très lentes.

### 10. API publique légère

- **Statut**: 🟡 Partiellement présent  
  Une API publique existe déjà (`docs/guides/API_PUBLIQUE.md`), à simplifier/compléter pour le cas d’usage Notion/CRM/Zapier.

- Pour brancher ProspectLab à d’autres outils (Notion, CRM externe, Zapier/Make) :
  - Récupérer la liste d’entreprises avec scores.
  - Lancer une analyse.
  - Récupérer un rapport d’audit.

### 11. Vue “Pipeline d’audit” par entreprise

- **Statut**: ✅ Implémenté (v1)  
  Onglet “Pipeline d’audit” dans la modale entreprise (Scraper → Technique → SEO → OSINT → Pentest) + API `/api/entreprise/<id>/audit-pipeline`.

- Timeline claire :
  - Scraper → Technique → SEO → OSINT → Pentest.
  - Horodatage, durée, état (OK / erreur), lien vers logs.
- Un clic pour relancer uniquement une brique :
  - “Relancer SEO”, “Relancer OSINT”, etc.

### 12. Mode “campagne ciblée”

- **Statut**: ✅ Implémenté (v1)  
  Wizard 3 étapes des campagnes avec modes de ciblage (toutes, objectifs, critères, groupes, segments sauvegardés) et filtres combinés.

- Créer une campagne de type :
  - “Artisans Lyon HTTPS absent”.
- Critères :
  - Zone géographique.
  - Technos / CMS.
  - Erreurs détectées (pas HTTPS, perf faible, SEO mauvais…).
- Lancer l’audit + génération d’emails pour tout le groupe.
- Suivi dédié des réponses / RDV pour cette campagne.

### 13. Détection de signaux d’intention / maturité

- **Statut**: 🔴 À faire

- Marquer les sites avec :
  - Blog actif.
  - Offres d’emploi tech.
  - Stack moderne mais SEO pourri.
- Aide à repérer les boîtes déjà **sensibilisées au digital** (plus prêtes à acheter).

### 14. Comparateur avant / après pour clients signés

- **Statut**: 🔴 À faire

- Garder :
  - Un snapshot de l’ancien site.
  - Un scan du nouveau.
- Générer des graphiques “avant/après” :
  - Performance.
  - SEO.
  - Sécurité.
- Utilisable en argumentaire commercial et dans les success stories.

### 15. Intégration agenda / prise de RDV

- **Statut**: 🔴 À faire

- Depuis la fiche entreprise ou le rapport :
  - Bouton “Proposer un créneau” (Cal.com / Calendly / Cronofy / autre).
- Remonter dans ProspectLab :
  - Statut “RDV planifié / passé”.

### 16. Scores de priorité multi‑critères configurables

- **Statut**: 🟡 Base existante, configuration à ajouter  
  Le calcul d’opportunité composite existe déjà (OpportunityCalculator) ; resterait à exposer une configuration des poids et des profils de scoring dans l’UI.

- Poids configurables par l’utilisateur :
  - Exemple : sécurité + SEO > perf front.
- Profils de scoring :
  - “Priorité SEO”.
  - “Priorité cybersécu”.
  - “Priorité e‑commerce”.

### 17. Vue “Opportunités par techno”

- **Statut**: 🔴 À faire

- Dashboard :
  - Nombre de prospects par techno :
    - WordPress, PrestaShop, Symfony, React, etc.
- Aide à focaliser la prospection :
  - Sur les stacks où l’équipe est la plus forte ou les plus rentables.

### 18. Suggestions automatiques d’offres / packs

- **Statut**: 🔴 À faire

- En fonction des problèmes détectés :
  - Exemple : “WP vieux + pas de HTTPS + lenteur mobile” → pack “Refonte WP + perf + sécurité”.
- Lien direct vers un **catalogue d’offres** (au départ via templates simples / pages HTML).

### 19. Suivi “touchpoints” de prospection

- **Statut**: 🟡 Partiellement couvert (notes + tags)  
  La fiche entreprise gère déjà tags et notes libres ; un vrai journal structuré des interactions reste à mettre en place.

- Journal par entreprise :
  - Emails envoyés.
  - Appels.
  - LinkedIn.
  - Réponses.
  - Notes de RDV.
- Raccourcis dans l’UI pour créer un “log” en 2 clics.

### 20. Mode “démonstration / sandbox”

- **Statut**: 🔴 À faire

- Faux dataset et fausses entreprises pour faire des démos live sans exposer de vrais leads.
- Bouton pour basculer entre :
  - “prod”.
  - “demo” (base SQLite différente, bannière visible).

