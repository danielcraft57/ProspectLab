# Configuration de ProspectLab

## Configuration via variables d'environnement

ProspectLab utilise des variables d'environnement pour la configuration. La méthode recommandée est d'utiliser un fichier `.env`.

### Installation de python-dotenv

Le package `python-dotenv` est inclus dans `requirements.txt` et sera installé automatiquement.

### Configuration initiale

1. Copiez le fichier d'exemple :
   ```bash
   cp env.example .env
   ```

2. Éditez le fichier `.env` avec vos valeurs

3. Le fichier `.env` est automatiquement chargé au démarrage de l'application

### Variables d'environnement disponibles

#### Sécurité
- **SECRET_KEY** : Clé secrète Flask (obligatoire en production)
  - Générer avec: `python -c "import secrets; print(secrets.token_hex(32))"`

#### Base de données
- **DATABASE_PATH** : (Optionnel) Chemin personnalisé vers la base de données SQLite
  - Par défaut: `prospectlab/prospectlab.db`

#### API Sirene (data.gouv.fr)
- **SIRENE_API_KEY** : (Optionnel) Clé API pour l'API Sirene
  - Obtenir une clé: https://api.gouv.fr/les-api/sirene_v3
  - L'API fonctionne sans clé mais avec des limites
- **SIRENE_API_URL** : URL de l'API Sirene (défaut: https://recherche-entreprises.api.gouv.fr/search)
- **SIRENE_API_RATE_LIMIT** : Limite de requêtes par minute (défaut: 10)

#### Configuration WSL (pour outils OSINT/Pentest)
- **WSL_DISTRO** : Distribution WSL à utiliser (défaut: kali-linux)
- **WSL_USER** : Utilisateur WSL (défaut: loupix)

#### Timeouts
- **OSINT_TOOL_TIMEOUT** : Timeout pour les outils OSINT en secondes (défaut: 60)
- **PENTEST_TOOL_TIMEOUT** : Timeout pour les outils Pentest en secondes (défaut: 120)

#### Pentest — formulaires web (tâches Celery)
Utilisées par `tasks/pentest_tasks.py` et `services/pentest_analyzer.py` pour les sondes sur les formulaires détectés au scraping.

- **PENTEST_FORM_PARALLEL_WORKERS** : Nombre de threads HTTP en parallèle pour les tests « légers » par formulaire (défaut: **8**). Sur machine peu de cœurs (ex. worker cluster 2 vCPU), baisser à **2**. Avec **PENTEST_FORM_SQLMAP_PROBE** actif, le code force **1** fil (sqlmap / WSL).
- **PENTEST_FORM_HTTP_TIMEOUT** : Timeout en secondes des requêtes HTTP de ces tests (défaut: **4**).
- **PENTEST_FORM_SQLMAP_PROBE** : `1` / `true` / `yes` pour activer une sonde **sqlmap** par formulaire (lourd, souvent **WSL** sous Windows). Défaut: désactivé.
- **PENTEST_SQLMAP_FORM_TIMEOUT** : Timeout en secondes pour l’exécution sqlmap par formulaire si la sonde est active (défaut: **90**).

Les modèles locaux **`.env.prod`** / **`.env.cluster`** (souvent ignorés par Git, voir `.gitignore`) peuvent fixer des valeurs conservatrices selon le matériel (ex. Pi 5 en prod seule, worker 2 vCPU en cluster) ; à recopier en `.env` sur chaque machine et à ajuster.

## Configuration Email

Pour pouvoir envoyer des emails, configurez les paramètres SMTP dans `config.py` ou via les variables d'environnement.

### Exemple avec Gmail

```python
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'votre-email@gmail.com'
MAIL_PASSWORD = 'votre-mot-de-passe-app'  # Utilisez un mot de passe d'application
MAIL_DEFAULT_SENDER = 'Votre Nom <votre-email@gmail.com>'
```

### Variables d'environnement

Vous pouvez aussi définir ces variables dans votre environnement :

```bash
export MAIL_SERVER=smtp.gmail.com
export MAIL_PORT=587
export MAIL_USE_TLS=True
export MAIL_USERNAME=votre-email@gmail.com
export MAIL_PASSWORD=votre-mot-de-passe
export MAIL_DEFAULT_SENDER="Votre Nom <votre-email@gmail.com>"
```

### Gmail - Mot de passe d'application

Si vous utilisez Gmail, vous devez créer un mot de passe d'application :

1. Allez dans votre compte Google
2. Sécurité → Validation en deux étapes (doit être activée)
3. Mots de passe des applications
4. Créez un nouveau mot de passe d'application
5. Utilisez ce mot de passe dans MAIL_PASSWORD

## Configuration du scraping

Les paramètres de scraping peuvent être ajustés dans `config.py` :

```python
SCRAPING_DELAY = 2.0  # Délai entre requêtes (secondes)
SCRAPING_MAX_WORKERS = 3  # Nombre de threads parallèles
SCRAPING_MAX_DEPTH = 3  # Profondeur maximale de scraping
```

## Sécurité

En production, changez le SECRET_KEY dans `config.py` :

```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'votre-secret-key-tres-long-et-aleatoire')
```

Ou définissez-le via une variable d'environnement :

```bash
export SECRET_KEY=votre-secret-key-tres-long-et-aleatoire
```

