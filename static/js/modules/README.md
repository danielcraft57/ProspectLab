# Architecture modulaire JavaScript

## Structure

```
static/js/modules/
├── utils/              # Modules utilitaires partagés
│   ├── formatters.js  # Formatage (ms, bytes, HTML escape)
│   ├── badges.js      # Génération de badges (scores, statuts)
│   ├── notifications.js # Système de notifications
│   └── debounce.js    # Fonction debounce
├── entreprises/       # Modules spécifiques aux entreprises
│   └── api.js         # Appels API pour les entreprises
├── analyses/          # Modules pour les analyses
│   ├── technical.js  # Affichage des analyses techniques
│   ├── osint.js      # Affichage des analyses OSINT
│   ├── pentest.js    # Affichage des analyses Pentest
│   └── scraping.js   # Affichage des résultats de scraping
└── loader.js          # Chargeur de modules avec dépendances
```

## Principes

1. **Modules autonomes** : Chaque module expose ses fonctionnalités via un objet global (ex: `window.Formatters`)
2. **Pas de dépendances circulaires** : Les modules utils ne dépendent d'aucun autre module
3. **Chargement ordonné** : Les dépendances sont chargées avant les modules qui les utilisent
4. **Optimisation** : Utilisation de `defer` pour les scripts non critiques

## Utilisation

### Dans les templates

```html
{% block extra_js %}
<!-- Modules de base (chargement synchrone) -->
<script src="{{ url_for('static', filename='js/modules/utils/formatters.js') }}"></script>
<script src="{{ url_for('static', filename='js/modules/utils/badges.js') }}"></script>
<script src="{{ url_for('static', filename='js/modules/utils/notifications.js') }}"></script>
<script src="{{ url_for('static', filename='js/modules/utils/debounce.js') }}"></script>

<!-- Module API -->
<script src="{{ url_for('static', filename='js/modules/entreprises/api.js') }}"></script>

<!-- Modules d'affichage des analyses -->
<script src="{{ url_for('static', filename='js/modules/analyses/technical.js') }}"></script>
<script src="{{ url_for('static', filename='js/modules/analyses/osint.js') }}"></script>
<script src="{{ url_for('static', filename='js/modules/analyses/pentest.js') }}"></script>
<script src="{{ url_for('static', filename='js/modules/analyses/scraping.js') }}"></script>

<!-- Script principal (chargement différé) -->
<script src="{{ url_for('static', filename='js/entreprises.js') }}" defer></script>
{% endblock %}
```

### Dans le code JavaScript

```javascript
// Utiliser les modules globaux
const { Formatters, Badges, EntreprisesAPI, Notifications } = window;
const debounceFn = window.debounce;

// Exemple d'utilisation
const escaped = Formatters.escapeHtml(userInput);
const badge = Badges.getSecurityScoreBadge(score);
await EntreprisesAPI.loadAll();
Notifications.show('Message', 'success');
```

## Refactorisation terminée

Le fichier `entreprises.js` (3380 lignes) a été refactorisé en modules :

- ✅ Modules utilitaires créés (`utils/`)
- ✅ Module API créé (`entreprises/api.js`)
- ✅ Modules d'affichage des analyses créés (`analyses/`)
  - `technical.js` : Analyses techniques
  - `osint.js` : Analyses OSINT
  - `pentest.js` : Analyses Pentest
  - `scraping.js` : Résultats de scraping (emails, personnes, téléphones, réseaux sociaux, technologies, métadonnées)
- ✅ Version modulaire `entreprises.refactored.js` créée
- ✅ Fonctions d'affichage des pages et images intégrées
- ✅ Chargement automatique des données au clic sur les onglets

## Structure actuelle

- **`entreprises.js`** : Point d’entrée (nom cohérent) qui charge l’implémentation actuelle
- **`entreprises.refactored.js`** : Implémentation principale (à découper progressivement)
- **`modules/utils/`** : Fonctions utilitaires partagées
- **`modules/entreprises/api.js`** : Appels API centralisés
- **`modules/analyses/`** : Affichage des analyses (technique, OSINT, pentest, scraping)

## Optimisation du chargement

- **Sans `defer`** : Scripts critiques qui doivent être chargés immédiatement (modules de base)
- **Avec `defer`** : Scripts qui peuvent attendre la fin du parsing HTML (scripts principaux)
- **Avec `async`** : Scripts indépendants qui peuvent être chargés en parallèle (non utilisé pour l'instant)

