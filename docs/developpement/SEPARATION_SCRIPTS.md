# Séparation des Scripts JavaScript

Ce document décrit la refactorisation des scripts JavaScript inline vers des fichiers externes pour améliorer la maintenabilité et les performances.

## Vue d'ensemble

Les scripts JavaScript qui étaient intégrés directement dans les templates HTML ont été extraits vers des fichiers séparés dans `static/js/`. Cette séparation améliore la maintenabilité, la réutilisabilité et permet une meilleure mise en cache par le navigateur.

## Fichiers modifiés

### Templates HTML

- **`templates/preview.html`** : Script extrait vers `static/js/preview.js`
- **`templates/upload.html`** : Script extrait vers `static/js/upload.js`

### Nouveaux fichiers JavaScript

- **`static/js/preview.js`** : Gestion de la page de prévisualisation et d'analyse
- **`static/js/upload.js`** : Gestion de l'upload de fichiers Excel avec progression

## Détails techniques

### Passage de variables Jinja2 aux scripts externes

Pour passer les variables Jinja2 (comme `filename` et `url_for()`) aux scripts externes, on utilise des **data attributes** sur les éléments HTML.

**Exemple dans `preview.html` :**

```html
<div class="page-header" data-filename="{{ filename }}" data-download-file-url="{{ url_for('other.download_file', filename='') }}">
    <h1>Prévisualisation du fichier</h1>
    <p>Fichier : <strong>{{ filename }}</strong> ({{ total_rows }} lignes)</p>
</div>
```

**Récupération dans `preview.js` :**

```javascript
const pageHeader = document.querySelector('.page-header');
const filename = pageHeader ? pageHeader.dataset.filename || '' : '';
const downloadFileUrl = pageHeader ? pageHeader.dataset.downloadFileUrl || '' : '';
```

### Référencement des scripts dans les templates

Les scripts sont maintenant référencés via `url_for()` dans le bloc `extra_js` :

```html
{% block extra_js %}
<script src="{{ url_for('static', filename='js/preview.js') }}"></script>
{% endblock %}
```

## Avantages

### 1. Maintenabilité

- Code JavaScript séparé du HTML, plus facile à lire et maintenir
- Syntax highlighting et autocomplétion améliorés dans les éditeurs
- Facilite le débogage avec les outils de développement

### 2. Performance

- **Mise en cache** : Les fichiers JS sont mis en cache par le navigateur, réduisant les requêtes HTTP
- **Compression** : Les fichiers externes peuvent être compressés plus efficacement
- **Parallélisation** : Le navigateur peut charger les scripts en parallèle avec le HTML

### 3. Réutilisabilité

- Les scripts peuvent être réutilisés dans d'autres templates si nécessaire
- Facilite la création de composants JavaScript modulaires

### 4. Séparation des préoccupations

- HTML pour la structure
- CSS pour le style
- JavaScript pour le comportement

## Structure des fichiers

### `static/js/preview.js`

Gère :
- Le lancement de l'analyse Excel
- Le suivi en temps réel du scraping via WebSocket
- Le suivi en temps réel de l'analyse technique
- Les barres de progression et statistiques
- La redirection automatique après la fin des processus
- Le scroll automatique vers les sections actives

**Variables nécessaires :**
- `filename` : Nom du fichier Excel à analyser
- `downloadFileUrl` : URL de base pour télécharger les fichiers

### `static/js/upload.js`

Gère :
- L'upload de fichiers Excel avec progression en temps réel
- Le calcul de la vitesse de transfert et de l'ETA
- La validation de la taille du fichier (max 50MB)
- La simulation de la progression du traitement serveur
- La redirection vers la page de prévisualisation

## Migration future

Si d'autres templates contiennent des scripts inline importants, ils peuvent être extraits de la même manière :

1. Créer un nouveau fichier dans `static/js/`
2. Extraire le code JavaScript
3. Identifier les variables Jinja2 nécessaires
4. Les passer via des data attributes
5. Remplacer le script inline par une référence au fichier externe

## Bonnes pratiques

1. **Nommage** : Utiliser des noms de fichiers clairs correspondant au template (ex: `preview.js` pour `preview.html`)
2. **Data attributes** : Utiliser des noms en kebab-case pour les data attributes (ex: `data-filename`, `data-download-file-url`)
3. **Vérifications** : Toujours vérifier l'existence des éléments avant d'accéder à leurs data attributes
4. **Documentation** : Documenter les variables nécessaires en commentaires dans les fichiers JS

## Exemple complet

**Avant (script inline) :**

```html
{% block extra_js %}
<script>
(function() {
    const filename = '{{ filename }}';
    // ... code JavaScript ...
})();
</script>
{% endblock %}
```

**Après (fichier externe) :**

```html
<!-- Dans le template -->
<div class="page-header" data-filename="{{ filename }}">
    <!-- ... -->
</div>

{% block extra_js %}
<script src="{{ url_for('static', filename='js/preview.js') }}"></script>
{% endblock %}
```

```javascript
// Dans static/js/preview.js
(function() {
    const pageHeader = document.querySelector('.page-header');
    const filename = pageHeader ? pageHeader.dataset.filename || '' : '';
    // ... code JavaScript ...
})();
```

## Impact

- **Taille des templates** : Réduction significative de la taille des fichiers HTML
- **Temps de chargement** : Amélioration grâce à la mise en cache
- **Maintenabilité** : Code plus organisé et facile à maintenir
- **Expérience développeur** : Meilleure avec les outils de développement modernes

