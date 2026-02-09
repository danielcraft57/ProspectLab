# Architecture des Templates

## Structure

```
templates/
├── base.html              # Template de base (layout principal)
├── error.html             # Page d'erreur
├── index.html             # Page d'accueil
├── components/            # Composants réutilisables (macros Jinja2)
│   ├── __init__.html      # Import centralisé des macros
│   ├── page_header.html   # En-tête de page
│   ├── filters_section.html # Section de filtres
│   ├── modal.html         # Modale générique
│   ├── progress_section.html # Barre de progression
│   ├── card.html          # Carte générique
│   └── stats_grid.html    # Grille de statistiques
├── partials/              # Partials réutilisables (includes)
│   ├── head_meta.html     # Meta tags et favicons
│   ├── navigation.html    # Navigation principale
│   ├── footer.html        # Pied de page
│   ├── flash_messages.html # Messages flash
│   ├── websocket_indicator.html # Indicateur WebSocket
│   └── base_scripts.html  # Scripts de base (Socket.IO, main.js, websocket.js)
└── pages/                 # Pages principales
    ├── dashboard.html
    ├── entreprises.html
    ├── analyses_techniques.html
    ├── analyses_osint.html
    ├── analyses_pentest.html
    └── ...
```

## Composants (Macros)

Les composants sont des macros Jinja2 réutilisables. Importez-les dans vos templates :

```jinja2
{% from 'components/page_header.html' import page_header %}
{% from 'components/modal.html' import modal %}

{{ page_header('Titre', 'Description') }}
{{ modal('my-modal', 'Titre de la modale', size='large') }}
```

### Composants disponibles

- **page_header** : En-tête de page avec titre et description optionnels
- **filters_section** : Section de filtres avec grille et actions
- **modal** : Modale générique avec header, body et footer optionnels
- **progress_section** : Barre de progression avec message
- **card** : Carte avec header, body et footer optionnels
- **stats_grid** : Grille de statistiques

## Partials (Includes)

Les partials sont des fragments HTML réutilisables inclus via `{% include %}` :

```jinja2
{% include 'partials/navigation.html' %}
{% include 'partials/flash_messages.html' %}
```

### Partials disponibles

- **head_meta.html** : Meta tags, favicons, viewport
- **navigation.html** : Navigation principale avec menus déroulants
- **footer.html** : Pied de page
- **flash_messages.html** : Affichage des messages flash Flask
- **websocket_indicator.html** : Indicateur de statut WebSocket
- **base_scripts.html** : Scripts JavaScript de base (Socket.IO, main.js, websocket.js)

## Pages

Les pages principales utilisent `base.html` et les composants/partials :

```jinja2
{% extends "base.html" %}
{% from 'components/page_header.html' import page_header %}

{% block title %}Ma Page - ProspectLab{% endblock %}

{% block content %}
{{ page_header('Titre', 'Description') }}
<!-- Contenu de la page -->
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/mon-script.js') }}" defer></script>
{% endblock %}
```

## Optimisation des dépendances

### CSS
- **style.css** : Chargé dans `base.html` (global)
- **extra_css** : Bloc pour CSS spécifiques à une page

### JavaScript
- **Socket.IO** : Chargé dans `base_scripts.html` (global)
- **main.js** : Chargé dans `base_scripts.html` (global)
- **websocket.js** : Chargé dans `base_scripts.html` (global)
- **extra_js** : Bloc pour scripts spécifiques à une page (avec `defer` recommandé)

### Chargement conditionnel

Pour les bibliothèques externes (Chart.js, Leaflet, etc.), chargez-les uniquement dans les pages qui en ont besoin via `extra_js` :

```jinja2
{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="{{ url_for('static', filename='js/dashboard.js') }}" defer></script>
{% endblock %}
```

## Où sont les pages

Les pages principales sont dans `pages/`. Le helper `render_page('nom.html')` charge d’abord `pages/nom.html`, puis en secours le fichier à la racine. Les doublons à la racine ont été supprimés : une seule source par page dans `pages/`.

À la racine de `templates/` restent : `base.html`, `error.html`, `home.html`, `index.html`, `login.html`, `api_tokens.html`, `campagnes.html`, `restricted.html`, plus `components/` et `partials/`.

## Bonnes pratiques

1. **Réutiliser les composants** : Utilisez les macros plutôt que de dupliquer le HTML
2. **Séparer les préoccupations** : Logique dans les routes, présentation dans les templates
3. **Optimiser le chargement** : Chargez les scripts lourds uniquement où nécessaire
4. **Documenter les composants** : Ajoutez des commentaires pour les paramètres complexes
5. **Tester la responsivité** : Vérifiez que les composants fonctionnent sur mobile

