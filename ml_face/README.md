## Objectif

Ce dossier sert a developper un pipeline de deep learning pour la reconnaissance faciale sur un gros volume de photos, sans melanger avec le reste de l'app.

L'idee:
- indexer les photos (chemins + metadata)
- extraire des embeddings de visages
- faire de l'identification (recherche de similarite)
- garder un historique d'experiences et des artefacts reproductibles

## Structure

- `engineering/` - modeles d'ingenierie (spec, ADR, dataset card, etc.)
- `configs/` - fichiers de config (chemins, parametres, modeles)
- `src/` - code Python du pipeline (packages)
- `scripts/` - scripts CLI pour lancer les jobs
- `data_raw/` - photos brutes (non versionne)
- `data/` - donnees intermediaires (index, caches) (non versionne)
- `artifacts/` - modeles, embeddings, index (non versionne)
- `runs/` - logs d'experiences (non versionne)

## Installation (environnement local)

Depuis la racine du repo:

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r ml_face\\requirements.txt
```

## Premier run (exemple)

```bash
python ml_face\\scripts\\index_photos.py --input "C:\\chemin\\vers\\mes_photos"
```

## Pipeline complet (suggestion)

Depuis la racine du repo:

1) Indexer toutes les photos

```bash
python ml_face\\scripts\\index_photos.py --input "C:\\chemin\\vers\\mes_photos" --output "ml_face\\data\\photos_index.json"
```

2) Detecter les visages et sauver les crops

```bash
python ml_face\\scripts\\extract_faces.py --index "ml_face\\data\\photos_index.json" --out-dir "ml_face\\artifacts\\faces_crops" --min-prob 0.90
```

3) Calculer les embeddings

```bash
python ml_face\\scripts\\build_embeddings.py --manifest "ml_face\\artifacts\\faces_crops\\manifest.jsonl" --out-dir "ml_face\\artifacts\\embeddings" --batch-size 32
```

4) Faire une requete (trouver les visages les plus proches)

```bash
python ml_face\\scripts\\query_face.py --image "C:\\chemin\\vers\\une_photo.jpg" --emb-dir "ml_face\\artifacts\\embeddings" --topk 10
```

5) Construire des "identites" (clusters) + une galerie (optionnel)

```bash
python ml_face\\scripts\\build_identities.py --emb-dir "ml_face\\artifacts\\embeddings" --out-dir "ml_face\\artifacts\\identities" --threshold 0.75 --min-size 2 --copy-crops
```

6) (Optionnel) dessin debug des bboxes depuis la BDD

```bash
python ml_face\\scripts\\draw_bboxes_from_db.py --env-file ".env.cluster" --run-id 5 --out-dir "ml_face\\artifacts\\debug_bbox"
```

## BDD prod (PostgreSQL)

En prod, l'app utilise `DATABASE_URL` (PostgreSQL). Le plus simple est de charger `.env.cluster`.

### Workflow "lot prod" recommande

1) Telecharger un lot d'images via URLs de la table `images`

```bash
python ml_face\\scripts\\download_prod_images.py --env-file ".env.cluster" --out-dir "ml_face\\data_raw\\prod_100" --limit 100 --min-bytes 20000
```

2) Indexer le lot (les metadonnees `image_id` / `entreprise_id` sont conservees)

```bash
python ml_face\\scripts\\index_photos.py --input "ml_face\\data_raw\\prod_100" --output "ml_face\\data\\photos_index_100.json"
```

3) Extraire les visages puis calculer les embeddings

```bash
python ml_face\\scripts\\extract_faces.py --index "ml_face\\data\\photos_index_100.json" --out-dir "ml_face\\artifacts\\faces_crops\\prod_100" --min-prob 0.85 --device cpu
python ml_face\\scripts\\build_embeddings.py --manifest "ml_face\\artifacts\\faces_crops\\prod_100\\manifest.jsonl" --out-dir "ml_face\\artifacts\\embeddings\\prod_100" --batch-size 16
```

4) Pousser en BDD (creation d'un run)

```bash
python ml_face\\scripts\\push_embeddings_to_db.py --env-file ".env.cluster" --emb-dir "ml_face\\artifacts\\embeddings\\prod_100" --run-name "prod_100"
```

5) (Optionnel) pousser les identites

```bash
python ml_face\\scripts\\push_identities_to_db.py --env-file ".env.cluster" --identities "ml_face\\artifacts\\identities\\identities.json" --run-id 123
```

### Liaison avec `images` (important)

Quand tu utilises un lot telecharge depuis `download_prod_images.py`, les metadonnees `image_id` et `entreprise_id` sont propagees jusqu'a `ml_face_embeddings`.

- `ml_face_embeddings.image_id` est une FK vers `images.id` avec suppression en cascade
- `ml_face_embeddings.entreprise_id` est renseigne pour retrouver directement l'entreprise
- tu peux joindre `ml_face_embeddings -> images -> entreprises` pour enrichir l'affichage

## Matching des personnes (assisté)

Objectif: proposer une personne pour chaque visage detecte, avec validation humaine.

1) Construire la galerie de reference des personnes (URLs dans `personnes_photos`, et/ou JSON `photos_urls` dans `personnes_osint_details`). Sans aucune de ces sources, le matching personnes restera vide.

```bash
python ml_face\\scripts\\build_person_gallery_embeddings.py --env-file ".env.cluster" --entreprise-id 0 --device cpu
```

2) Lancer le matching pour un run de visages

```bash
python ml_face\\scripts\\match_faces_to_persons.py --env-file ".env.cluster" --run-id 5 --topk 3 --min-score 0.55
```

3) API de review
- `GET /api/ml-face/person-matches?run_id=5`
- `PATCH /api/ml-face/person-matches/<match_id>/status` avec `{ "status": "validated" }`

Exemple de jointure utile:

```sql
SELECT
  e.id AS embedding_id,
  e.run_id,
  e.image_id,
  e.source_path,
  e.face_index,
  e.box_json,
  i.url,
  i.entreprise_id,
  ent.nom AS entreprise_nom
FROM ml_face_embeddings e
JOIN images i ON i.id = e.image_id
LEFT JOIN entreprises ent ON ent.id = e.entreprise_id
WHERE e.run_id = 5;
```

## Notes pratiques

- Les dossiers `ml_face/data_raw`, `ml_face/data`, `ml_face/artifacts`, `ml_face/runs` sont ignores par Git.
- Pour des milliers de photos, le mode "brute force cosine" passe deja bien. Si on monte a des millions, on ajoutera un index ANN (FAISS/HNSW).
- `download_prod_images.py` force des noms de fichiers locaux uniques (`image_id + hash`) pour eviter les collisions.

