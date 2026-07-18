# Outils UX (@clea_ux)

Analyse UX de sites web calée sur le corpus TikTok [@clea_ux](https://www.tiktok.com/@clea_ux)
(transcripts locaux : `UX_TRANSCRIPTS_DIR`, défaut Windows
`C:\Users\loicDaniel\Videos\tiktokUX\transcripts`).

## Principe

Contrairement au pentest (binaires CLI), les « outils » UX sont des **heuristiques Python**
+ un **index corpus** (164 transcripts). Chaque outil peut être activé/désactivé via
`options` dans `UXAnalyzer.analyze_ux` / Socket.IO `start_ux_analysis`.

## Fichiers

| Fichier | Rôle |
|---------|------|
| `services/ux_corpus.py` | Index transcripts + 14 chapitres playbook |
| `services/ux_analyzer.py` | `UXAnalyzer` + catalogue d'outils |
| `services/database/ux.py` | Persistance `analyses_ux` / `analysis_ux_findings` |
| `tasks/ux_tasks.py` | Celery `ux_analysis_task` (queue `seo`) |

## Catalogue d'outils (37)

### Corpus

| Outil | Description |
|-------|-------------|
| `corpus_index` | Stats du dossier transcripts (163/164, règles, coverage) |
| `corpus_search` | Recherche plein texte indexée (tous les transcripts) |
| `chapter_map` | Grille des 14 chapitres |
| `corpus_rules_extract` | Grille de ~2000 règles extraites de tous les .txt |
| `page_corpus_relevance` | Croise le texte page vs tout le corpus (gaps/forces) |
| `corpus_principle_match` | Match chaque finding contre les 163 transcripts |

Chaque finding enrichi contient `corpus_quotes`, `corpus_rules`, `corpus_best_quote`
et `corpus_docs_scanned` (scan intégral du corpus).

### Landing / conversion

| Outil | Chapitre | Description |
|-------|----------|-------------|
| `hick_law` | 5 | Trop de choix nav / CTA |
| `ctv_call_to_value` | 4 | CTA génériques vs CTV |
| `contrast_pricing` | 4 / 11 | Écart tarifaire / plans |
| `loss_aversion` | 4 | Copy aversion à la perte |
| `hero_clarity` | 4 | H1 / promesse hero |

### Parcours produit

| Outil | Chapitre | Description |
|-------|----------|-------------|
| `onboarding_flow` | 1 | Inscription sans progression |
| `time_to_value` | 2 | Formulaires lourds |
| `aha_moment` | 3 | Preuve de valeur visible |
| `friction_forms` | 6 | Required / captcha |
| `phantom_modals` | 6 | Trop de modales |
| `adaptive_persona` | 7 | Multi-cibles mélangés |
| `peak_end` | 12 | Fin / victoire |
| `zeigarnik_progress` | 13 | Barre de progression |
| `gamification` | 13 | Badges vs déblocage |
| `fogg_behavior` | 11 | Motivation × capacité × prompt |
| `paywall_vitrine` | 11 | Cadenas vs vitrine |
| `retention_signals` | 12 | Login / compte |
| `feature_adoption` | - | Tooltips / nouveautés |

### Contenu / structure

| Outil | Chapitre | Description |
|-------|----------|-------------|
| `error_guidance` | 8 | Probe 404 + CTA |
| `empty_states` | 9 | Empty / no data |
| `navigation_sidebar` | 5 | Sidebar max 7 |
| `search_experience` | 9 | Présence recherche |
| `social_proof` | 12 | Avis / logos |
| `notification_patterns` | 10 | Bannières / popups |
| `trust_consistency` | 12 | Délais incohérents |
| `dashboard_necessity` | 9 | Grille de cartes |
| `microcopy_validation` | 8 | Aide formulaires |
| `heading_hierarchy` | 4 | H1/H2 |
| `link_density` | 5 | Trop de liens |
| `accessibility_basics` | 6 | Alt / lang |
| `mobile_viewport` | 6 | Meta viewport |

## API / Socket.IO

- `GET /api/ux/diagnostic` — outils + stats corpus
- `GET /api/ux/corpus/search?q=...` — recherche transcripts
- Socket.IO `start_ux_analysis` → events `ux_analysis_*`

## Config

```text
UX_TRANSCRIPTS_DIR=C:\Users\loicDaniel\Videos\tiktokUX\transcripts
UX_FETCH_CONNECT_TIMEOUT=12
UX_FETCH_READ_TIMEOUT=25
```

## Pipeline

Inclus dans :
- pack analyse site complète (`enable_ux=True`)
- modules audit PDF `simple` et `complete`
- score d'opportunité (breakdown `ux`)
