## Roadmap - Liste d'entreprises, groupes et campagnes

Cette roadmap décrit les évolutions prévues pour améliorer la page "Entreprises", la gestion de groupes d'entreprises et leur utilisation dans la création de campagnes.

Objectifs principaux :

- Améliorer le moteur de recherche des entreprises avec des filtres avancés sur les scores de sécurité et de pentest.
- Simplifier l'interface des cartes entreprises en retirant le bouton "Tags" et en gardant des actions claires.
- Ajouter une vraie gestion de groupes d'entreprises (CRUD complet).
- Permettre de cibler des groupes d'entreprises directement depuis la création de campagne.
- Soigner l'UX/UI (animations, micro-interactions, feedbacks clairs).

Dernière mise à jour : 23/02/2026

---

## Phase 1 - Filtres Sécurité et Pentest sur la liste des entreprises

But : permettre de filtrer rapidement les entreprises selon leurs scores de sécurité et de pentest, sans casser la simplicité de l'interface.

### 1.1 Conception UX/UI

- Définir le type de contrôle :
  - Soit double sliders (min/max) pour Sécurité et Pentest.
  - Soit liste de tranches prédéfinies (exemple : 0-49, 50-79, 80-100).
- Positionner les filtres dans le bloc "Filtres et recherche" sans alourdir la ligne principale.
- Prévoir des tooltips pour expliquer la signification des scores.
- Définir le comportement responsive (repli des filtres secondaires en accordéon sur petit écran).
- Lister les micro-animations :
  - Transition douce à l'ouverture/fermeture de la zone de filtres avancés.
  - Mise en surbrillance des scores sur les cartes quand un filtre est actif.

### 1.2 Backend

- Étendre les paramètres de recherche des entreprises :
  - Ajouter `security_min`, `security_max`, `pentest_min`, `pentest_max` dans les endpoints REST concernés.
  - Valider les bornes (entre 0 et 100, min <= max, valeurs manquantes acceptées).
- Adapter la couche d'accès aux données pour filtrer sur ces plages.
- Mettre à jour la documentation API (docs techniques + commentaires dans le code).

### 1.3 Frontend

- Ajouter les contrôles de filtres dans le template de la page liste d'entreprises.
- Lier les filtres au système existant de recherche (query params, formulaires).
- Gérer le reset complet des filtres, incluant Sécurité/Pentest.
- S'assurer que l'export utilise les mêmes filtres que l'affichage.
- Ajouter des états visuels clairs quand des filtres sont actifs (badges, couleurs).

### 1.4 Tests et validation

- Tests backend sur les cas suivants :
  - Plage valide (exemple : 50-80) sur Sécurité et/ou Pentest.
  - Un seul côté renseigné (min seulement, max seulement).
  - Valeurs invalides rejetées proprement.
- Tests frontend :
  - Changement de filtres met bien à jour la liste sans erreur.
  - Les filtres sont persistants lors d'un rafraîchissement (selon le design retenu).
- Validation UX :
  - Vérifier que la zone de filtres reste lisible, même avec de nombreux critères.

---

## Phase 2 - Simplification de la carte entreprise (suppression du bouton "Tags")

But : alléger visuellement la carte d'entreprise tout en gardant les actions importantes évidentes.

### 2.1 UX/UI

- Revoir la zone d'actions de la carte :
  - Conserver uniquement les boutons vraiment utilisés (exemple : "Voir détails").
  - Recentrer ou réaligner les boutons restants pour éviter les espaces vides.
- Vérifier la hiérarchie visuelle (titre de l'entreprise, scores, actions).
- Confirmer où et comment les tags restent consultables (si nécessaire) dans d'autres écrans.

### 2.2 Implémentation technique

- Supprimer le bouton "Tags" du template de carte d'entreprise.
- Nettoyer les handlers associés côté JavaScript.
- Vérifier qu'aucune route ou API n'est devenue inutile à cause de cette suppression.
- Faire une passe visuelle rapide sur desktop et mobile.

---

## Phase 3 - Gestion de groupes d'entreprises (CRUD complet)

But : permettre à l'utilisateur de créer des groupes d'entreprises (segments), de les maintenir facilement, et de s'en servir plus tard dans les campagnes.

### 3.1 Modèle de données et API

- Définir une entité `GroupeEntreprise` (nom, description, propriétaire, dates de création/mise à jour).
- Définir la relation many-to-many entre groupes et entreprises (table de liaison).
- Créer les endpoints API :
  - Création, liste, lecture détaillée, mise à jour, suppression de groupe.
  - Ajout et retrait d'entreprises dans un groupe.
- Gérer les erreurs métier :
  - Groupe introuvable.
  - Entreprise introuvable.
  - Ajout multiple de la même entreprise dans un groupe.

### 3.2 UX/UI - Écran de gestion des groupes

- Créer une page "Groupes d'entreprises" accessible depuis le menu ou la page entreprises.
- Contenu de la page :
  - Liste des groupes avec : nom, nombre d'entreprises, date de dernière mise à jour.
  - Actions : créer, modifier, supprimer.
- Formulaire de création/édition :
  - Champs : nom obligatoire, description optionnelle.
  - Validation simple et messages d'erreur clairs.
- États vides :
  - Aucun groupe créé : texte explicatif + bouton "Créer mon premier groupe".

### 3.3 UX/UI - Association d'entreprises à un groupe

- Sur la liste d'entreprises :
  - Ajouter une sélection multiple (checkbox ou autre système simple).
  - Ajouter une action de masse "Ajouter aux groupes".
- Dans la modale d'ajout aux groupes :
  - Liste des groupes existants avec recherche rapide.
  - Possibilité de créer un nouveau groupe à la volée (optionnel, à trancher).
- Feedbacks visuels :
  - Toast de succès pour l'ajout/retrait d'entreprises.
  - Indiquer rapidement sur la carte si l'entreprise appartient déjà à un ou plusieurs groupes (badge discret).

### 3.4 Tests

- Tests sur les opérations CRUD de groupes.
- Tests sur l'ajout/retrait d'entreprises dans un groupe.
- Tests UX manuels : gros volumes (beaucoup d'entreprises / beaucoup de groupes).

---

## Phase 4 - Intégration des groupes dans la création de campagne

But : permettre de cibler directement un ou plusieurs groupes d'entreprises lors de la création d'une campagne.

### 4.0 État actuel (février 2026)

- ✅ Backend :
  - L'endpoint `/api/ciblage/entreprises` accepte un paramètre `groupe_ids` (liste d'IDs séparés par des virgules).
  - `EntrepriseManager.get_entreprises_for_campagne()` supporte un filtre `groupe_ids` et ne retourne que les entreprises appartenant à au moins un des groupes sélectionnés.
- ✅ Frontend :
  - Étape 1 du wizard de campagne : ajout du mode de ciblage **« Par groupes »** avec des pills animées par groupe (nom + compteur d'entreprises, tooltip détaillé).
  - Sélection/désélection d'un ou plusieurs groupes met à jour dynamiquement la liste des entreprises cibles via l'API de ciblage.
  - Sélection des entreprises facilitée avec des actions rapides **Tout / Aucun / Inverser** et recherche instantanée.
  - Étape 2 : bloc **Filtres emails** repliable (filtres avancés) et actions rapides **Tout / Aucun / Inverser** sur les destinataires.
- ⏳ Restant à faire :
  - Persister explicitement les `group_ids` choisis dans le modèle de campagne (stockage et affichage a posteriori).
  - Afficher, dans le récapitulatif de campagne, un résumé clair des groupes utilisés pour le ciblage.

### 4.1 Backend

- Étendre le modèle de campagne pour référencer des `group_ids`.
- Adapter les endpoints de création/mise à jour de campagne pour accepter ces groupes.
- Définir la logique de calcul de la cible :
  - Entreprises issues des groupes sélectionnés.
  - Gestion des doublons si une entreprise est dans plusieurs groupes.
- Documenter cette nouvelle logique dans la documentation technique.

### 4.2 Frontend - Wizard de création de campagne

- Ajouter une étape ou un bloc "Cible" permettant :
  - De choisir un ou plusieurs groupes.
  - De combiner éventuellement groupes + filtres individuels existants (selon le design souhaité).
- Afficher un résumé de la cible :
  - Nombre d'entreprises total.
  - Liste partielle ou infos synthétiques (exemples d'entreprises, secteurs principaux).
- Gérer les erreurs :
  - Aucun groupe disponible.
  - Groupe vide (prévenir l'utilisateur).

### 4.3 Tests et validation

- Tests unitaires sur la composition de la cible (groupes, doublons).
- Tests manuels sur l'expérience complète :
  - Créer un groupe.
  - Le remplir avec des entreprises.
  - Créer une campagne ciblant ce groupe.
  - Vérifier que les entreprises cibles correspondent bien aux attentes.

---

## Phase 5 - Animations, micro-interactions et finition UX

But : rendre l'ensemble fluide, agréable à utiliser et cohérent avec le reste de l'application.

### 5.1 Animations à ajouter

- Transitions sur :
  - Ouverture/fermeture de la zone de filtres avancés.
  - Apparition/disparition d'un groupe dans la liste.
  - Sélection/désélection des entreprises dans la liste.
- Hovers :
  - Cartes d'entreprises légèrement mises en avant au survol.
  - Boutons principaux (voir détails, créer groupe, lancer campagne) avec feedback visuel.

### 5.2 Feedback utilisateur

- Toasters cohérents pour :
  - Création/édition/suppression de groupe.
  - Ajout/retrait d'entreprises à un groupe.
  - Création de campagne avec groupes.
- États de chargement :
  - Skeletons ou loaders intégrés pour la liste d'entreprises et la liste de groupes.
- États vides travaillés pour :
  - Aucun résultat avec les filtres.
  - Aucun groupe.
  - Aucun groupe sélectionné dans une campagne.

### 5.3 Revue finale

- Vérifier la cohérence graphique globale (couleurs, typographies, espacements).
- Tester le tout sur différents scénarios :
  - Premier usage (aucune donnée).
  - Usage avancé avec beaucoup d'entreprises et de groupes.
- Identifier les optimisations possibles pour une itération ultérieure (performance, ergonomie).

