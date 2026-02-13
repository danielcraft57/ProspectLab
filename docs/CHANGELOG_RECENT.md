# Modifications récentes (résumé technique)

Ce document résume les changements techniques importants pour la maintenance et le déploiement.

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

## Modale entreprise : compteurs Images et Pages

- L'API `get_entreprise` renvoie désormais `images_count` et `pages_count` (calculés côté serveur à partir des tables `images`, `entreprise_og_data`, etc.).
- La modale affiche « Images (n) » et « Pages (n) » sur les onglets ; le nombre est mis à jour après chargement des images si besoin (`updateModalTabCount`).

## Templates et déploiement

- Les pages HTML sont centralisées dans `templates/pages/` ; les doublons à la racine de `templates/` ont été supprimés. Le helper `render_page('nom.html')` charge d'abord `pages/nom.html`.
- Scripts de déploiement (`deploy_production.ps1`, `deploy_production.sh`) : le dossier `scripts/` est inclus ; après le transfert principal, chaque dossier (routes, services, tasks, templates, static, utils, scripts) est envoyé explicitement via `scp -r` pour éviter les problèmes d'archive (tar sous Windows). Script optionnel `sync_templates_static.ps1` pour ne synchroniser que templates et static.
- Correction du nettoyage dans le script PowerShell : les motifs d'exclusion `deploy`, `logs`, `logs_server` s'appliquent au nom du dossier uniquement, pas au chemin, pour ne pas supprimer le contenu du dossier de déploiement.

## Documentation et confidentialité

- Les guides de déploiement et configuration utilisent des placeholders (`<SERVEUR_APP>`, `<VOTRE_DOMAINE>`, `<UTILISATEUR>`, etc.) au lieu de noms de serveurs ou domaines réels.
- Les chemins d'installation dans les docs (ex. WSL) utilisent `/chemin/vers/ProspectLab` au lieu de chemins personnels.
- Les logs de diagnostic dans `save_scraper` (db_type, scraper_id, etc.) sont en `logger.debug` pour ne pas encombrer les logs en production.
