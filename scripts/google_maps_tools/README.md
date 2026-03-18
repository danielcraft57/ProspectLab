## Outils Google Maps / Places (ProspectLab)

Ce dossier contient une copie **independante** des outils d'extraction Google Maps / Places,
pret a etre versionne sur GitHub sans inclure les donnees privees.

- Les scripts Python sont ici autonomes.
- Les donnees d'export restent dans `Data/` (ignore par git).

Scripts principaux:
- `places_search.py` : test unitaire / debug sur une requete
- `places_batch_export.py` : export par requetes (CSV/Excel)
- `export_city_sectors.py` : export complet d'une ville (secteurs + groupes)
- `main.py` : interface TUI (tableaux/couleurs) pour choisir region/ville/niveau et lancer l'export
- `rebuild_city_global.py` : reconstruit `Data/<Ville>/<Ville>.xlsx` a partir des xlsx existants (sans API)
- `secteurs_economiques.txt` : base de secteurs
- `groupes_secteurs_grands.json` : groupes de secteurs (a adapter)
- `presets_grand_est.json` : presets de villes (lat/lng + parametres centre/agglo/large)

### Export ville (par groupes de secteurs)

Commande type (Metz, mode texte, groupes par defaut) :

```bash
python scripts/google_maps_tools/export_city_sectors.py --city Metz --out-dir "Data" --groups-file scripts/experiments/google_maps_places_poc/groupes_secteurs_grands.json --details-max 200 --limit-per-sector 200
```

Pour utiliser un preset Grand-Est en mode grille (agglo Metz) :

```bash
python scripts/google_maps_tools/export_city_sectors.py --city Metz --out-dir "Data" --groups-file scripts/experiments/google_maps_places_poc/groupes_secteurs_grands.json --mode nearby-grid --lat 49.1193 --lng 6.1757 --radius 3000 --grid-step-m 3000 --grid-rings 3 --details-max 200 --limit-per-sector 200
```

### Export via interface TUI (recommande)

Installation (pour couleurs + tableaux):

```bash
pip install rich
```

Lancer:

```bash
python scripts/google_maps_tools/main.py
```

Les resultats se retrouvent dans :
- `Data/<Ville>/<Groupe>.xlsx`
- `Data/<Ville>/<Ville>.xlsx` (global, deduplique)

