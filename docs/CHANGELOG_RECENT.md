# Modifications récentes (résumé technique)

Ce document résume les changements techniques importants pour la maintenance et le déploiement.

## UI Entreprises, notifications et relance analyses (mars 2026)

- **Détection d’obsolescence et tags intelligents**  
  - Calcul des signaux d’obsolescence (WordPress ancien, Bootstrap 3, jQuery lourd, HTTP only, mixed content, domaine très ancien, scores faibles) dans `services/database/technical.py` ; tag `fort_potentiel_refonte` mis à jour automatiquement à chaque analyse technique.  
  - Détection de la langue principale du contenu dans `services/technical_analyzer.py` (heuristique stopwords) ; tags `lang_fr`, `lang_en`, etc. gérés dans `services/database/entreprises.py`.  
  - Affichage des tags avec libellés lisibles et styles dédiés (refonte, risque, SEO, perf, HTTPS, langue) sur les cartes et lignes entreprises ; filtre par tags dans les filtres avancés.

- **Vue entreprises (grille + liste) et relance analyses**  
  - Vue liste : refonte complète avec logo à gauche, tags sous le nom, mini-jauges circulaires (Sécurité, SEO, Risque/Pentest) et boutons de relance par type ; animations d’entrée en escalier, hover et thèmes clair/sombre alignés avec les cartes.  
  - Vue cartes : mêmes jauges circulaires + boutons de relance, et nouveaux emplacements “Lancer” pour les analyses jamais effectuées (technique, SEO, Pentest) qui se transforment automatiquement en jauge dès que l’analyse est terminée.  
  - Les filtres “Score sécurité / SEO / Risque (Pentest)” considèrent désormais les analyses non faites comme score 0 (via `COALESCE` en SQL), ce qui permet de filtrer facilement les entreprises jamais analysées en mettant un seuil minimum > 0.  
  - Après chaque `*_analysis_complete`, les scores sont rafraîchis côté frontend via le pipeline d’audit (`/api/entreprise/<id>/audit-pipeline`) afin que les jauges et les filtres reflètent immédiatement les nouvelles valeurs (y compris `score_pentest`).

- **Sélection multiple et actions de masse**  
  - Ajout de cases à cocher sur les cartes et lignes entreprises, avec liens “Tous / Aucun” et compteur de sélection.  
  - Menu d’actions de masse : lancer/relancer les analyses (technique, SEO, Pentest ou toutes), ajouter/retirer les entreprises sélectionnées à/depuis un groupe, avec chargement dynamique de la liste des groupes.  
  - Les actions de relance réutilisent exactement la logique existante (WebSocket, loaders, notifications, rafraîchissement temps réel), appliquée à toutes les entreprises sélectionnées.

- **Notifications**  
  - Bouton “Tout effacer” à la place de “Tout marquer comme lu” : méthode `clearAll()` dans `static/js/modules/utils/notifications.js`, panneau vidé au clic.  
  - Nouveau style des toasts et du panneau : couleurs par type (info/success/error/warning), icônes dans pastilles, animations slide ; panneau avec en-tête et liste harmonisés, thème sombre pris en charge (`static/css/modules/notifications.css`).  
  - Panneau fermé par défaut au chargement : règle `.notifications-panel[hidden] { display: none !important; }` et appel à `closePanel()` en fin d’init dans `static/js/main.js`.

## Tables BDD : quand sont-elles remplies ?

Beaucoup de tables restent à 0 enregistrement tant que l’usage ou les outils ne les alimentent pas. Résumé utile :

- **users (0)** : Aucun utilisateur créé. Pour pouvoir se connecter, créer un admin : `python scripts/create_admin_user.py` (puis suivre les questions).
- **segments_ciblage (0)** : Remplie quand on crée un segment depuis l’interface Campagnes (étape 1, mode Ciblage par segment, puis « Enregistrer ce segment »).
- **email_tracking_events (0)** : Remplie quand un destinataire ouvre un email (pixel) ou clique sur un lien. Reste à 0 tant qu’aucun ouvert/clic. Vérifier que `BASE_URL` pointe vers une URL accessible depuis l’extérieur.
- **api_tokens (0)** : Remplie quand un utilisateur crée un token API depuis l’interface.
- **analysis_technique_security_headers (0)** : Les security headers étaient dans chaque `page` et pas à la racine du résultat. Corrigé : la sauvegarde agrège désormais les headers de la première page (ou des pages) pour remplir cette table. Les **nouvelles** analyses techniques la rempliront.
- **analysis_osint_technologies**, **analysis_pentest_vulnerabilities**, etc. : Remplies uniquement si les analyseurs (OSINT, Pentest) retournent ces données (ex. WhatWeb pour technologies, vulnérabilités trouvées). 0 peut être normal si l’outil n’a rien trouvé ou n’est pas disponible (WSL, Kali, etc.).
- **personnes_*** (professional_history, hobbies, photos, …) : Données enrichies OSINT ; souvent vides si les sources ne fournissent pas ces infos.

En résumé : plusieurs tables sont « à la demande » (users, segments, tokens, tracking) ; d’autres dépendent des résultats des tâches (technique, OSINT, pentest). La correction sur **analysis_technique_security_headers** permet de remplir cette table à partir des prochaines analyses techniques.

## Modèles de messages : page Gestion + restauration (fév. 2026)

- **Page Gestion des modèles** : Bloc "Variables disponibles" (nom, entreprise, email, blocs conditionnels, variables générées) ; catégorie "Email HTML" ; badge et preview pour les modèles HTML ; formulaire avec rappel des variables.
- **Template_manager** : Création/mise à jour préserve `is_html` selon la catégorie ; si `templates_data.json` absent, copie depuis `templates_data.default.json` si présent.
- **Template Studio (CLI)** : Génération/sync des templates HTML via `python -m template_studio.generate_cli --sync` depuis les sources `template_studio/html_sources/` (bootstrap possible si besoin).
- **Fragments HTML (includes)** : Factorisation via `{#include:...}` (`footer_standard`, `signature_standard`, `cta_*`) pour garder un rendu cohérent et maintenir vite.
- **Campagnes (dropdown Modèle de message)** : Chargement des templates plus robuste (réponse API non tableau, select manquant) ; listener "change" attaché une seule fois.

## Campagnes email : paramètres d'envoi, suggestions et reset (fév. 2026)

- **Paramètres d'envoi** : Refonte du bloc "Paramètres d'envoi" (étape 3) avec mode "Envoyer maintenant" / "Programmer l'envoi" en segmented control ; bloc date/heure et suggestions affiché uniquement en mode programmé.
- **Date/heure** : Champs date et heure d'envoi initialisés à la date/heure actuelle (au passage en mode programmé et à l'affichage de l'étape 3).
- **Suggestions intelligentes** : Trois boutons (ex. Demain matin, Demain après-midi, Lundi matin) calculent le prochain jour ouvré en excluant week-ends et jours fériés français (Pâques et fêtes fixes) ; heures type bureau 9h et 14h. Les libellés des boutons sont mis à jour dynamiquement.
- **Correctif** : Un clic sur une suggestion remplit bien les champs date/heure (plus d'écrasement par `setScheduleDateTimeToNow()` après le clic).
- **Reset formulaire** : À la fermeture du modal (Annuler ou après envoi), le formulaire est réinitialisé (étape 1, champs par défaut, bloc programmation masqué) et la **sélection des entreprises** est vidée (checkboxes étape 1 décochées, compteur destinataires mis à jour).
- **Fichiers** : `templates/pages/campagnes.html`, `static/js/campagnes.js`, `static/css/modules/pages/campagnes.css` (nouveau module) ; suppression de `static/css/campagnes.css` (styles déplacés dans modules/pages).

## PostgreSQL : récupération des ID après INSERT

En PostgreSQL, `cursor.lastrowid` n'existe pas ou n'est pas fiable. Les insertions qui ont besoin de l'ID généré utilisent désormais `INSERT ... RETURNING id` puis `cursor.fetchone()` :

- **scrapers** (`services/database/scrapers.py`) : création d'un scraper retourne son `id` via RETURNING ; les images et autres données normalisées sont bien rattachées au bon `scraper_id`.
- **entreprise_og_data** (`services/database/entreprises.py`) : dans `_save_og_data_in_transaction`, l'insert dans `entreprise_og_data` utilise RETURNING id pour obtenir `og_data_id`, puis les inserts dans `entreprise_og_images`, `entreprise_og_videos`, etc. utilisent ce bon id.

Sans cela, en production avec PostgreSQL, les tables `scrapers`, `images`, `entreprise_og_data` et `entreprise_og_images` restaient vides ou mal liées.

## Modale entreprise : compteurs Images/Pages, analyses et dark mode (fév. 2026)

- L'API `get_entreprise` renvoie désormais `images_count` et `pages_count` (calculés côté serveur à partir des tables `images`, `entreprise_og_data`, etc.).
- La modale affiche « Images (n) » et « Pages (n) » sur les onglets ; le nombre est mis à jour après chargement des images si besoin (`updateModalTabCount`).
- Les onglets de la modale sont désormais **scrollables** avec un ruban horizontal et des **flèches de navigation** gauche/droite (desktop + mobile), ce qui garantit l'accès à tous les onglets (« Résultats scraping », « Analyse technique », « Analyse SEO », « Analyse OSINT », « Analyse Pentest ») même sur petits écrans.
- Les blocs de résultats (OSINT, Pentest, technique, SEO, scraping) ont été harmonisés en **mode sombre** : cartes résumées, badges, tags, tableaux et blocs de détail n'utilisent plus de fonds clairs fixes (inline styles), le CSS dark override force un rendu cohérent.
- L'onglet « Analyse SEO » de la modale consomme maintenant l'API `/api/entreprise/<id>/analyse-seo` et réutilise le rendu détaillé de la page d'analyses SEO (`renderSEOExpertise`) directement dans la modale entreprise.

## Validation des noms/prénoms et faux positifs (fév. 2026)

- Le module `services/name_validator.py` a été renforcé :
  - **Liste d'exclusion élargie** (`EXCLUDED_KEYWORDS`) pour filtrer les mots techniques / UI fréquents : `react`, `vue`, `node`, `python`, `frontend`, `backend`, `data`, `machine`, `console`, `search`, `optimization`, `premiers`, `sain`, `choisir`, `des`, `dans`, `page`, `section`, `menu`, `nav`, etc.
  - Utilisation optionnelle de **gender-guesser** (si installé) pour rejeter les noms dont le premier mot **n'est pas un prénom connu** (évite par ex. `Choisir / Des`, `React / Frontend`, etc.).
  - Toujours basé sur `probablepeople` (Person vs Corporation) et `nameparser` pour la structure prénom/nom quand ces bibliothèques sont disponibles.
- Les extractions de personnes dans `services/unified_scraper.py`, `services/email_analyzer.py` et `tasks/scraping_tasks.py` s'appuient sur ces règles : beaucoup de faux positifs ne sont plus insérés dans `personnes` (meilleure qualité pour les filtres « prénom/nom » et pour les analyses OSINT).

## Templates et déploiement

- Les pages HTML sont centralisées dans `templates/pages/` ; les doublons à la racine de `templates/` ont été supprimés. Le helper `render_page('nom.html')` charge d'abord `pages/nom.html`.
- Scripts de déploiement (`deploy_production.ps1`, `deploy_production.sh`) : le dossier `scripts/` est inclus ; après le transfert principal, chaque dossier (routes, services, tasks, templates, static, utils, scripts) est envoyé explicitement via `scp -r` pour éviter les problèmes d'archive (tar sous Windows). Script optionnel `sync_templates_static.ps1` pour ne synchroniser que templates et static.
- Correction du nettoyage dans le script PowerShell : les motifs d'exclusion `deploy`, `logs`, `logs_server` s'appliquent au nom du dossier uniquement, pas au chemin, pour ne pas supprimer le contenu du dossier de déploiement.

## OSINT / Pentest : dépannage, prod sans WSL, nouveaux outils (fév. 2026)

- **Prod = exécution native** : En production (serveur Linux) il n’y a pas de WSL ; les outils sont exécutés directement sur le système (`shutil.which`). La doc et les messages de diagnostic distinguent clairement « natif » (prod) et « WSL » (dev Windows).
- **Diagnostic** : `get_diagnostic()` renvoie désormais `execution_mode` (`native` ou `wsl`) et des messages adaptés : en l’absence de WSL, on affiche « Exécution native (pas de WSL). X outil(s) disponible(s)... » au lieu de « WSL non disponible, rien ne sera exécuté ».
- **Doc** : `INSTALL_OSINT_TOOLS.md` précise en tête que prod = installation directe sur le serveur, dev = WSL + outils dans la distro. Section dépannage mise à jour en conséquence. Rappel des routes `/api/osint/diagnostic` et `/api/pentest/diagnostic`.
- **Nouveaux outils documentés** : Serposcope, Lighthouse, Screaming Frog (SEO) ; Social Analyzer, Sherlock, Maigret, Tinfoleak (réseaux sociaux).

## Prévisualisation Excel & suivi temps réel analyse (mars 2026)

- **Prévisualisation upload (`routes/upload.py`, `templates/pages/preview.html`)** :
  - Les compteurs du bloc résumé affichent maintenant :
    - `Entreprises dans le fichier` = toutes les lignes valides du fichier Excel.
    - `Nouvelles entreprises` = lignes réellement insérées (déduplication dans le fichier **et** en BDD via `find_duplicate_entreprise`).
    - `Avec téléphone` / `Avec adresse` / `Avec catégorie` = uniquement sur les **nouvelles** entreprises (pas sur les doublons).
  - `_preview_stats_from_df` utilise le même algorithme de doublons que la tâche Celery (`analyze_entreprise_task`) pour garantir que la prévisualisation reflète exactement ce qui sera traité.
- **Détection de doublons BDD (`services/database/entreprises.py`, `tasks/analysis_tasks.py`)** :
  - `find_duplicate_entreprise` gère correctement `sqlite3.Row` et accepte la recherche par **website seul** (cas `nom` vide).
  - `existing_ids_before` est initialisé en lisant `SELECT id FROM entreprises` et en extrayant l’ID depuis n’importe quel type de ligne (dict, tuple, `sqlite3.Row`), ce qui évite de réanalyser des entreprises déjà présentes.
- **Suivi temps réel OSINT / Pentest (`routes/websocket_handlers.py`, `static/js/preview.js`)** :
  - Les événements OSINT/Pentest véhiculent maintenant un `expected_total` qui correspond au nombre d’entreprises de l’analyse, ce qui permet d’afficher `X / N entreprises` correctement (et non plus `X / 1`).
  - Correction des conditions de course : le monitoring OSINT/Pentest synchronise les listes de tâches à partir du résultat final du scraping avant de se terminer ; avec plusieurs entreprises, les compteurs atteignent bien `2 / 2` (ou `N / N`) avant la redirection.
  - Le Pentest distingue la **progression de l’entreprise en cours** (`task_progress`) de la **progression globale** (moyenne de toutes les tâches) ; l’entreprise en cours et le compteur global ne restent plus bloqués au même pourcentage.
  - Une fois les analyses terminées, chaque bloc (Scraping, Technique+SEO, OSINT, Pentest) affiche un encadré « *… terminé* » avec un résumé lisible (ex. nombre de formulaires testés pour le Pentest, totaux cumulés OSINT).
 - **Compatibilité PostgreSQL pour les entreprises (`services/database/entreprises.py`)** :
   - `save_entreprise` utilisait `cursor.lastrowid`, correct en SQLite mais invalide en PostgreSQL (renvoyait 0). La méthode utilise maintenant `INSERT ... RETURNING id` en mode Postgres, et `lastrowid` uniquement en SQLite.
   - Conséquence : les IDs retournés sont corrects en production Postgres, les compteurs `inserted` / `duplicates` dans `tasks/analysis_tasks.py` sont fiables, et la déduplication BDD se comporte comme en dev.

## PostgreSQL & SMTP : compatibilité généralisée (mars 2026)

- **Couche BDD Postgres généralisée** :
  - `services/api_auth.py` (`APITokenManager.create_token`) : création de tokens API via `INSERT ... RETURNING id` en mode PostgreSQL, `cursor.lastrowid` conservé pour SQLite.
  - `services/auth.py` (`AuthManager.create_user`) : création d'utilisateur robuste en PostgreSQL (`RETURNING id`) avec fallback SQLite inchangé.
  - `services/database/personnes.py` (`PersonneManager.save_personne`) : création de contact (`personnes`) compatible dict/tuple ; l’ID retourné est fiable en Postgres comme en SQLite.
  - `services/database/groupes.py` (`GroupeEntrepriseManager.create_groupe_entreprise`) : création de groupes d’entreprises via `RETURNING id` en Postgres, `lastrowid` en SQLite.
  - `services/database/campagnes.py` (`CampagneManager.save_email_envoye`, `save_tracking_event`, création de segments) : tous les `INSERT` qui ont besoin de l’ID utilisent désormais `RETURNING id` en PostgreSQL ; plus de `id = 0` ou `NULL` dans `emails_envoyes`, `email_tracking_events`, `segments_ciblage`.
- **Campagnes email & SMTP (`services/email_sender.py`)** :
  - L’envoi SMTP utilise maintenant `starttls()` uniquement si `MAIL_USE_TLS=true` (cas typique : port 587 + STARTTLS).
  - L’authentification `server.login()` est tentée seulement si `MAIL_USERNAME` est défini, et l’erreur `SMTPNotSupportedError` (« SMTP AUTH extension not supported by server ») est gérée proprement : on continue l’envoi sans AUTH pour les relais internes.
  - En pratique : les campagnes ne passent plus en statut `FAILED` uniquement parce que le relais SMTP ne supporte pas AUTH, et les environnements Postgres/production et SQLite/dev partagent le même comportement fonctionnel côté campagnes email.

## Documentation et confidentialité

- Les guides de déploiement et configuration utilisent des placeholders (`<SERVEUR_APP>`, `<VOTRE_DOMAINE>`, `<UTILISATEUR>`, etc.) au lieu de noms de serveurs ou domaines réels.
- Les chemins d'installation dans les docs (ex. WSL) utilisent `/chemin/vers/ProspectLab` au lieu de chemins personnels.
- Les logs de diagnostic dans `save_scraper` (db_type, scraper_id, etc.) sont en `logger.debug` pour ne pas encombrer les logs en production.
