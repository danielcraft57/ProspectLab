# Template Studio (templates email)

## Objectif
Isoler la génération des templates d’emails HTML dans un “dossier source” dédié, pour éviter les gros blocs de HTML en dur dans `scripts/` et rendre la preview et la maintenance plus simples.

## Arborescence
Le cœur de la refonte se trouve ici :
`template_studio/`

- `template_studio/html_sources/<template_id>.html` : fichiers HTML sources (source de vérité)
- `template_studio/export_html_sources.py` : exporte depuis `template_studio/templates_data.json` vers `template_studio/html_sources/`
- `template_studio/html_templates_generator.py` : régénère `template_studio/templates_data.default.json` puis `template_studio/templates_data.json` depuis `template_studio/html_sources/`
- `template_studio/template_repo.py` : repository JSON utilitaire

La CLI interactive de preview :
- `template_studio/preview_cli.py`

La CLI de génération (Template Studio) :
- `template_studio/generate_cli.py`

## Source de vérité
Le dossier :
- `template_studio/html_sources/`

Une génération `python -m template_studio.generate_cli --sync` lit les fichiers de ce dossier. Si une source manque pour un `template_id`, la génération échoue (pour éviter les “silencieux fallback”).

## Placeholders et conditionnels

Les templates utilisent des placeholders gérés par `services/template_manager.py` :
- variables simples : `{nom}`, `{entreprise}`, `{email}`
- variables enrichies côté `TemplateManager` : `analysis_url`, `unsubscribe_url`, `dc_contact_url`, etc.

Conditionnels (deux syntaxes possibles, la première est “normalisée” par `TemplateManager`) :
- compatibilité (encore utilisée dans certains templates) :
  - `{{#if_website}} ... {{#endif}}`
- forme normalisée (celle qui est ensuite traitée) :
  - `{#if_website} ... {#endif}`

Cas “générique” :
- `{#if_<xxx>}` ... `{#endif}` : le bloc est conservé si `variables["<xxx>"]` est “truthy” côté rendu.

## Morceaux communs (include)
Tu peux factoriser du HTML via des fragments partagés.

Syntaxe (chargée par `services/template_manager.py`) :
- `{#include:footer_standard}` (ou `{#include_footer_standard}`)

Les fragments sont chargés depuis `template_studio/fragments/<nom>.html`.

Exemple :
```html
{#include:footer_standard}
```

### Includes imbriqués (récursifs)
Les includes sont **récursifs** : un fragment peut inclure un autre fragment.  
Une protection empêche les boucles infinies (profondeur max).

### Fragments fournis (standardisation)
- `footer_standard` : footer “familier” (robot + réponse + lien ne plus recevoir d’email)
- `signature_standard` : signature type (Cordialement, **Prénom Nom**, lien `https://exemple.fr`)
- `cta_primary_15min` : CTA principal “Oui, je réserve 15 min” (pill)
- `cta_secondary_analysis` : CTA secondaire “Voir l’analyse du site” (avec `{#if_website}`)
- `cta_dual_analysis_and_15min` : double CTA (analyse + réserver 15 min) style bleu/noir

## Commandes (workflow)

1. Export initial / ré-export des sources depuis le JSON actuel
```powershell
python -m template_studio.export_html_sources --overwrite
```

2. Générer `templates_data.default.json`
```powershell
python -m template_studio.generate_cli --write-default
```

3. Synchroniser `templates_data.json` depuis `html_sources/`
```powershell
python -m template_studio.generate_cli --sync
```

4. Preview (rendu navigateur + regénération)
```powershell
python -m template_studio.preview_cli --defaults --template-id html_decouverte_hero
```

## Preview CLI : modes

Exemples utiles :
```powershell
# Preview “complète” avec données non vides (affiche les blocs conditionnels)
python -m template_studio.preview_cli --defaults --template-id html_seo_chatgpt

# Preview sans ouvrir le navigateur
python -m template_studio.preview_cli --defaults --template-id html_seo_chatgpt --no-open
```

Le rendu HTML est affiché via :
- un fichier `./.template_studio_preview/preview_<template_id>_<timestamp>.html`
- ouvert automatiquement dans ton navigateur (sauf `--no-open`)

## Notes
- `TemplateManager.render_template()` accepte `extended_overrides` (utile pour la preview en `--defaults`/mock).
- Même si `templates_data*.json` est bien régénéré, l’application peut aussi charger des templates depuis la BDD si elle est connectée. En dev/CLI, le fallback JSON est prévu.

