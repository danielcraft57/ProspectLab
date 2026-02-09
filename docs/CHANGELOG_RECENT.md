# Modifications récentes (résumé technique)

Ce document résume les changements techniques importants pour la maintenance et le déploiement.

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
