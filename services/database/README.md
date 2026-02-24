# Architecture modulaire de la base de données

## Structure

Le module `services/database/` est organisé en modules spécialisés :

```
services/database/
├── __init__.py          # Point d'entrée - Classe Database combinée
├── base.py              # Connexion et méthodes de base
├── schema.py            # Création des tables et migrations
├── entreprises.py       # Gestion des entreprises
├── groupes.py           # Groupes d'entreprises (listes sauvegardées)
├── analyses.py          # Analyses générales
├── scrapers.py          # Gestion des scrapers
├── personnes.py         # Gestion des personnes
├── campagnes.py         # Campagnes email
├── osint.py             # Analyses OSINT
├── technical.py         # Analyses techniques
├── pentest.py           # Analyses Pentest
└── seo.py               # Analyses SEO
```

## Architecture

La classe `Database` utilise l'héritage multiple (mixins) pour combiner toutes les fonctionnalités.  
L'implémentation actuelle correspond à :

```python
from .base import DatabaseBase
from .schema import DatabaseSchema
from .entreprises import EntrepriseManager
from .groupes import GroupeEntrepriseManager
from .analyses import DatabaseAnalyses
from .scrapers import ScraperManager
from .personnes import PersonneManager
from .campagnes import CampagneManager
from .osint import OSINTManager
from .technical import TechnicalManager
from .pentest import PentestManager
from .seo import SEOManager


class Database(
    DatabaseSchema,          # Schéma + migrations
    EntrepriseManager,       # Entreprises
    GroupeEntrepriseManager, # Groupes d'entreprises (listes sauvegardées)
    DatabaseAnalyses,        # Analyses globales
    ScraperManager,          # Scrapers et données associées
    PersonneManager,         # Personnes
    CampagneManager,         # Campagnes email
    OSINTManager,            # Analyses OSINT
    TechnicalManager,        # Analyses techniques
    PentestManager,          # Analyses Pentest
    SEOManager,              # Analyses SEO
    DatabaseBase             # Connexion (en dernier pour le MRO)
):
    pass
```

## Migration depuis database.py

Le fichier `services/database.py` (5159 lignes) doit être migré vers cette architecture modulaire.

### Stratégie de migration

1. **Étape 1** : Créer la structure (✅ fait)
2. **Étape 2** : Extraire le schéma (init_database) vers `schema.py`
3. **Étape 3** : Extraire les méthodes par domaine vers les modules correspondants
4. **Étape 4** : Tester que tout fonctionne
5. **Étape 5** : Supprimer l'ancien `database.py` et mettre à jour les imports

### Méthodes à migrer par module

#### `schema.py`
- `init_database()` - Toute la création des tables (lignes 38-1354)
- `migrate_foreign_keys_cascade()` - Migration des clés étrangères

#### `entreprises.py`
- `find_duplicate_entreprise()`
- `save_entreprise()`
- `_save_og_data_in_transaction()`
- `_save_multiple_og_data_in_transaction()`
- `get_og_data()`
- `get_entreprises()`
- `update_entreprise_tags()`
- `update_entreprise_notes()`
- `toggle_favori()`
- `get_statistics()`
- `get_nearby_entreprises()`
- `get_entreprises_by_secteur_nearby()`
- `get_competition_analysis()`

#### `analyses.py`
- `save_analysis()`
- `get_analyses()`

#### `scrapers.py`
- `save_scraper()`
- `_save_scraper_emails_in_transaction()`
- `save_scraper_emails()`
- `_save_scraper_phones_in_transaction()`
- `save_scraper_phones()`
- `_save_scraper_social_profiles_in_transaction()`
- `save_scraper_social_profiles()`
- `_save_scraper_technologies_in_transaction()`
- `save_scraper_technologies()`
- `_save_scraper_people_in_transaction()`
- `save_scraper_people()`
- `_save_images_in_transaction()`
- `save_images()`
- `_save_scraper_forms_in_transaction()`
- `save_scraper_forms()`
- `get_scraper_forms()`
- `get_images_by_scraper()`
- `get_scraper_emails()`
- `get_scraper_phones()`
- `get_scraper_social_profiles()`
- `get_scraper_technologies()`
- `get_scraper_people()`
- `get_images_by_entreprise()`
- `get_scrapers_by_entreprise()`
- `get_scraper_by_url()`
- `update_scraper()`
- `delete_scraper()`
- `clean_duplicate_scraper_data()`

#### `personnes.py`
- `save_person_osint_details()`
- Toutes les méthodes de sauvegarde des données OSINT enrichies sur les personnes

#### `campagnes.py`
- Méthodes liées aux campagnes email (si elles existent)

#### `osint.py`
- `save_osint_analysis()`
- `update_osint_analysis()`
- `get_osint_analysis_by_url()`
- `get_osint_analysis()`
- `get_osint_analysis_by_entreprise()`
- `get_all_osint_analyses()`
- `delete_osint_analysis()`
- `_load_osint_analysis_normalized_data()`

#### `technical.py`
- `save_technical_analysis()`
- `get_technical_analysis()`
- `get_all_technical_analyses()`
- `get_technical_analysis_by_id()`
- `get_technical_analysis_by_url()`
- `update_technical_analysis()`
- `delete_technical_analysis()`
- `_load_technical_analysis_normalized_data()`

#### `pentest.py`
- `save_pentest_analysis()`
- `update_pentest_analysis()`
- `get_pentest_analysis_by_url()`
- `get_pentest_analysis()`
- `get_pentest_analysis_by_entreprise()`
- `get_all_pentest_analyses()`
- `delete_pentest_analysis()`
- `_load_pentest_analysis_normalized_data()`

## Avantages de cette architecture

1. **Maintenabilité** : Code organisé par domaine fonctionnel
2. **Lisibilité** : Fichiers plus petits et focalisés
3. **Testabilité** : Chaque module peut être testé indépendamment
4. **Évolutivité** : Facile d'ajouter de nouvelles fonctionnalités
5. **Collaboration** : Plusieurs développeurs peuvent travailler en parallèle

## Compatibilité

L'import reste identique :
```python
from services.database import Database
```

La classe `Database` expose toutes les méthodes comme avant, donc aucun changement n'est nécessaire dans le reste du code.

