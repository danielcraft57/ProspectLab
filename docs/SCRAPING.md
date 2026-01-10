# Guide du scraping unifie

## Vue d'ensemble

ProspectLab utilise un systeme de scraping unifie et complet qui extrait automatiquement toutes les informations pertinentes d'un site web en une seule passe.

## Architecture du scraping

### Flux de traitement

1. **Analyse Excel** : Extraction des informations de base des entreprises
   - Nom, adresse, telephone, categorie
   - Detection du site web
   - Sauvegarde en base de donnees

2. **Scraping complet** : Extraction detaillee (tache Celery separee)
   - Emails (avec contexte et page source)
   - Personnes (nom, titre, email, telephone)
   - Telephones (avec page source)
   - Reseaux sociaux (Facebook, LinkedIn, Twitter, Instagram, YouTube, etc.)
   - Technologies (frameworks, CMS, analytics, hebergement)
   - Images (avec dimensions et alt text)
   - Metadonnees (titre, description, favicon, logo, OpenGraph)

3. **Mise a jour temps reel** : WebSocket pour suivre la progression
   - Compteurs par categorie (emails, personnes, telephones, etc.)
   - Affichage du site en cours de scraping
   - Progression globale (X/Y entreprises)

### UnifiedScraper

Le `UnifiedScraper` est le moteur central qui orchestre toute l'extraction :

```python
from services.unified_scraper import UnifiedScraper

scraper = UnifiedScraper(
    base_url='https://example.com',
    max_workers=5,        # Nombre de threads paralleles
    max_depth=3,          # Profondeur de navigation
    max_time=300,         # Temps max en secondes
    max_pages=50,         # Nombre max de pages
    progress_callback=callback_function  # Callback pour progression
)

results = scraper.scrape()
```

#### Resultats retournes

```python
{
    'emails': [
        {'email': 'contact@example.com', 'page_url': 'https://...', 'context': '...'},
        ...
    ],
    'people': [
        {
            'name': 'Jean Dupont',
            'title': 'Directeur',
            'email': 'jean.dupont@example.com',
            'phone': '+33 1 23 45 67 89',
            'page_url': 'https://...'
        },
        ...
    ],
    'phones': [
        {'phone': '+33 1 23 45 67 89', 'page_url': 'https://...'},
        ...
    ],
    'social_links': {
        'facebook': ['https://facebook.com/...'],
        'linkedin': ['https://linkedin.com/company/...'],
        'twitter': ['https://twitter.com/...'],
        ...
    },
    'technologies': {
        'cms': ['WordPress 6.4'],
        'frameworks': ['React 18.2'],
        'analytics': ['Google Analytics'],
        'hosting': ['OVH'],
        ...
    },
    'images': [
        {
            'url': 'https://example.com/image.jpg',
            'alt': 'Description',
            'width': 1920,
            'height': 1080,
            'page_url': 'https://...'
        },
        ...
    ],
    'metadata': {
        'title': 'Titre du site',
        'description': 'Description du site',
        'icons': {
            'favicon': 'https://example.com/favicon.ico',
            'logo': 'https://example.com/logo.png',
            'og_image': 'https://example.com/og-image.jpg'
        },
        'open_graph': {
            'og:title': 'Titre OpenGraph',
            'og:description': 'Description OpenGraph',
            'og:image': 'https://example.com/og-image.jpg',
            ...
        }
    },
    'resume': 'Resume automatique du site...',
    'visited_urls': 42,
    'duration': 15.3,
    'total_emails': 5,
    'total_people': 3,
    'total_phones': 8,
    'total_social_platforms': 4,
    'total_technologies': 12,
    'total_images': 156
}
```

## Base de donnees

### Tables principales

#### entreprises
Informations de base sur les entreprises.

#### scrapers
Resultats de scraping avec totaux et metadonnees.

#### scraper_emails
Liste des emails trouves avec contexte.

#### scraper_people
Personnes identifiees avec leurs coordonnees.

#### scraper_phones
Telephones extraits avec page source.

#### scraper_social
Profils de reseaux sociaux detectes.

#### scraper_technologies
Technologies utilisees par categorie.

#### scraper_images
Images du site avec dimensions et alt text.

#### entreprise_og_data
Donnees OpenGraph normalisees (titre, description, type, etc.).

#### entreprise_og_images
Images OpenGraph avec dimensions et type.

#### entreprise_og_videos
Videos OpenGraph (si presentes).

#### entreprise_og_audios
Audios OpenGraph (si presents).

#### entreprise_og_locales
Locales supportees par le site.

### Relations

- `scrapers.entreprise_id` -> `entreprises.id` (CASCADE DELETE)
- `scraper_emails.scraper_id` -> `scrapers.id` (CASCADE DELETE)
- `scraper_people.scraper_id` -> `scrapers.id` (CASCADE DELETE)
- `scraper_phones.scraper_id` -> `scrapers.id` (CASCADE DELETE)
- `scraper_social.scraper_id` -> `scrapers.id` (CASCADE DELETE)
- `scraper_technologies.scraper_id` -> `scrapers.id` (CASCADE DELETE)
- `scraper_images.scraper_id` -> `scrapers.id` (CASCADE DELETE)
- `entreprise_og_data.entreprise_id` -> `entreprises.id` (CASCADE DELETE)
- `entreprise_og_images.og_data_id` -> `entreprise_og_data.id` (CASCADE DELETE)
- `entreprise_og_videos.og_data_id` -> `entreprise_og_data.id` (CASCADE DELETE)
- `entreprise_og_audios.og_data_id` -> `entreprise_og_data.id` (CASCADE DELETE)
- `entreprise_og_locales.og_data_id` -> `entreprise_og_data.id` (CASCADE DELETE)

## Bonnes pratiques

### Parametres recommandes

- **max_workers** : 3-5 pour eviter de surcharger les serveurs
- **max_depth** : 2-3 pour un bon equilibre couverture/temps
- **max_time** : 300 secondes (5 minutes) par site
- **max_pages** : 50 pages pour limiter le temps de scraping
- **delay** : 2 secondes entre requetes pour eviter les blocages

### Gestion des erreurs

Le scraper gere automatiquement :
- Timeouts de connexion
- Erreurs HTTP (404, 500, etc.)
- Sites inaccessibles
- Redirections infinies
- Contenu invalide

### Performance

- Scraping parallele avec threads
- Cache des pages visitees
- Deduplication automatique
- Limitation du nombre de pages
- Timeout par site

## Progression temps reel

Le scraping envoie des mises a jour en temps reel via WebSocket :

```javascript
socket.on('scraping_progress', function(data) {
    console.log(data.message);
    console.log('Emails:', data.total_emails);
    console.log('Personnes:', data.total_people);
    console.log('Telephones:', data.total_phones);
    console.log('Reseaux sociaux:', data.total_social_platforms);
    console.log('Technologies:', data.total_technologies);
    console.log('Images:', data.total_images);
});

socket.on('scraping_complete', function(data) {
    console.log('Scraping termine !');
    console.log('Total emails:', data.total_emails);
    // Redirection automatique vers /entreprises
});
```

## Limitations

- Respect du fichier `robots.txt` (optionnel, configurable)
- Pas de scraping de sites protegés par authentification
- Pas de scraping de contenu JavaScript dynamique (necessiterait Selenium)
- Limite de temps par site pour eviter les blocages

## Voir aussi

- [Architecture](architecture/ARCHITECTURE.md)
- [API REST](guides/API.md)
- [WebSocket](techniques/WEBSOCKET.md)

