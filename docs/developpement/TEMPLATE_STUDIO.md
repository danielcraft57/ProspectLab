# Template Studio (templates email)

## Objectif

Isoler la génération des emails HTML dans un dossier source (`template_studio/html_sources/`) et des fragments réutilisables, pour limiter le HTML en dur ailleurs, faciliter la preview et garder un flux de génération reproductible.

## Arborescence

Racine : `template_studio/`

| Élément | Rôle |
|--------|------|
| `html_sources/<template_id>.html` | **Source de vérité** du contenu (un fichier = un `template_id`) |
| `fragments/<nom>.html` | Morceaux inclus via `{#include:nom}` |
| `export_html_sources.py` | Outil optionnel : exporte le HTML **depuis** un JSON vers `html_sources/` (migration / rattrapage) |
| `html_templates_generator.py` | Assemble les specs et le HTML (utilisé par `generate_cli`) |
| `template_repo.py` | Lecture / écriture des fichiers `templates_data*.json` |
| `generate_cli.py` | Génération des bundles JSON |
| `preview_cli.py` | Preview navigateur avec rendu `TemplateManager` |

**Multi-marque** (`--brand <slug>`) :

- `brands/<slug>/html_sources/` puis fallback `html_sources/`
- `brands/<slug>/fragments/` puis fallback `fragments/`
- Bundles JSON par marque sous `brands/<slug>/` (mêmes noms de fichiers que le commun)

## Versionnement Git

Les fichiers suivants **ne sont pas suivis** (voir `.gitignore` à la racine) :

- `template_studio/templates_data.json`
- `template_studio/templates_data.default.json`
- `template_studio/brands/**/templates_data.json`
- `template_studio/brands/**/templates_data.default.json`

Les préviews locales sont ignorées : `.template_studio_preview/`.

**Après un clone** (ou si ces JSON manquent), régénérer depuis les sources :

```powershell
python -m template_studio.generate_cli --sync
```

`TemplateManager` peut recopier le `.default` vers `templates_data.json` au premier lancement si le fichier manque, mais pour un bundle à jour il faut lancer la commande ci-dessus (ou `--write-default` puis `--restore` selon le besoin).

## Source de vérité et génération

1. Éditer `html_sources/*.html` et `fragments/*.html`.
2. Régénérer les JSON :

```powershell
# Recréer default + recopier vers templates_data.json (recommandé au quotidien)
python -m template_studio.generate_cli --sync
```

Si une entrée `template_id` existe dans le JSON mais que le fichier `html_sources/<template_id>.html` manque, la génération **échoue** (pas de fallback silencieux).

### Régénérer seulement quelques modèles

Sans resynchroniser tout le bundle :

```powershell
python -m template_studio.generate_cli --only-ids html_tech_sonar_alert,html_tech_site_qui_freine
```

Même principe avec `--brand jammy`.

### Autres commandes utiles

```powershell
# Export optionnel HTML depuis un JSON existant (rattrapage)
python -m template_studio.export_html_sources --overwrite

# Écrire seulement le default
python -m template_studio.generate_cli --write-default

# Recopier default -> templates_data.json
python -m template_studio.generate_cli --restore
```

## Placeholders et conditionnels

Gérés par `services/template_manager.py` :

- Variables simples : `{nom}`, `{entreprise}`, `{email}`
- Enrichies : `analysis_url`, `unsubscribe_url`, `dc_contact_url`, `website`, `secteur`, scores, listes HTML, etc.

**Conditionnels** (normalisés en `{#if_…}…{#endif}` ; l’ancienne forme `{{#if_…}}` est encore acceptée puis convertie) :

- `{#if_website}…{#endif}` : conservé si `website` est renseigné
- `{#if_<nom>}…{#endif}` : conservé si `variables["<nom>"]` est truthy

## Includes

Syntaxe : `{#include:footer_standard}` (alias `{#include_footer_standard}`). Chargement depuis `fragments/` (ou override marque). Includes **récursifs**, avec limite de profondeur anti-boucle.

Fragments fournis courants : `footer_standard`, `signature_standard`, `cta_primary_15min`, `cta_secondary_analysis`, `cta_dual_analysis_and_15min`.

## Variables utiles (analyse technique, pentest, SEO)

Injectées notamment via `_get_entreprise_extended_data()` lors du rendu avec `entreprise_id` :

- **`analysis_url`** : lien analyse en ligne (`/analyse?website=…&full=1`, email de tracking si présent).
- **Pentest** : `vulnerabilities_count`, `vulnerabilities_top`, `has_vulnerabilities_top`, `security_headers_missing_top`, `has_security_headers_missing_top`, `has_pentest`.
- **Scores distincts pour les templates** :
  - **`pentest_surface_score`** + **`has_pentest_surface_score`** : indice issu du pentest (risque / vulnérabilités), libellé côté copy email à part du score sécurité “analyse technique”.
  - **`technical_security_score`** + **`has_technical_security_score`** : score sécurité de surface **avant** fusion pentest.
  - **`show_technical_security_score`** : afficher le bloc “analyse technique” seulement quand il n’y a pas d’indice pentest calculé (évite doublon).
- **Fallback sécurité (analyse technique)** : `security_issues_top`, `show_security_issues_fallback`.
- **SEO** : `seo_issues` (liste `<li>…</li>`), condition `{#if_seo_issues}`.

Les booléens `{#if_performance}` / `{#if_security}` reflètent la présence des scores `performance_score` / `security_score` (usage selon les modèles).

### Largeur des cartes à l’envoi

Dans `render_template()`, le HTML des emails subit une normalisation : les `max-width` des cartes courantes (**560px à 680px**) sont ramenées à **760px**, y compris pour d’anciens modèles encore en base. Les sources dans `html_sources/` utilisent déjà **760px** sur le conteneur principal.

## Modèles « analyse technique difficile » (exemples)

Trois modèles dédiés aux prospects avec signaux faibles, ton direct, lien d’analyse mis en avant (sans s’appuyer sur le score performance dans le copy) :

- `html_tech_sonar_alert`
- `html_tech_site_qui_freine`
- `html_tech_risques_visibles`

## Preview CLI

```powershell
python -m template_studio.preview_cli --defaults --template-id html_tech_sonar_alert
python -m template_studio.preview_cli --defaults --template-id html_seo_chatgpt --no-open
```

Le HTML est écrit sous `.template_studio_preview/preview_<template_id>_<timestamp>.html`. Le mode `--defaults` utilise des `extended_overrides` (scores bas, SEO, pentest mock, etc.) pour afficher un maximum de blocs conditionnels.

## Notes

- `render_template()` accepte `extended_overrides` (preview, tests).
- En production, les modèles peuvent venir de la **BDD** ; le JSON local sert de repli (dev, CLI, premier boot).
- Page « modèles d’email » : certains liens peuvent être affichés en démo ; l’envoi réel repasse par `render_template()` avec les données entreprise.
