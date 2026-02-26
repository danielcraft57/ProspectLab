# Modifications récentes (résumé technique)

Ce document résume les changements techniques importants pour la maintenance et le déploiement.

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
- **Script generate_html_templates.py** : Correction encodage (prints sans Unicode) ; option `--restore` / `-r` pour recréer `templates_data.json` à partir du fichier par défaut (2 Cold Email + 5 HTML).
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

## Documentation et confidentialité

- Les guides de déploiement et configuration utilisent des placeholders (`<SERVEUR_APP>`, `<VOTRE_DOMAINE>`, `<UTILISATEUR>`, etc.) au lieu de noms de serveurs ou domaines réels.
- Les chemins d'installation dans les docs (ex. WSL) utilisent `/chemin/vers/ProspectLab` au lieu de chemins personnels.
- Les logs de diagnostic dans `save_scraper` (db_type, scraper_id, etc.) sont en `logger.debug` pour ne pas encombrer les logs en production.
