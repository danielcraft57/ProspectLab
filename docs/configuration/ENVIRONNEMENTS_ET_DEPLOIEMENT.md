# Environnements, base de données et déploiement de ProspectLab

Ce document explique comment organiser ProspectLab en plusieurs environnements (dev / prod), gérer SQLite ou PostgreSQL, utiliser WSL ou Debian pour les outils OSINT / Pentest, et déployer l'application derrière `node12.lan` avec les sous-domaines `prospectlab.danielcraft.fr` et `campaigns.danielcraft.fr`.

**Note** : Pour un guide détaillé du déploiement en production avec toutes les étapes, voir [DEPLOIEMENT_PRODUCTION.md](DEPLOIEMENT_PRODUCTION.md).

L'objectif est que tu puisses:

- travailler confortablement en local (Windows + WSL ou Linux natif) ;
- déployer proprement sur un serveur Debian (`node15.lan`) ;
- exposer l'application via un reverse proxy sur `node12.lan` avec les bons sous-domaines.

---

## 1. Organisation des environnements (dev / prod)

ProspectLab utilise déjà un fichier `.env` et le module `config.py` pour sa configuration.

La logique recommandée:

- **dev local**: fichier `.env` simple, SQLite local, WSL activé si besoin ;
- **prod**: `.env` séparé sur le serveur, SQLite (ou plus tard Postgres), pas de debug, services lancés par `systemd`.

### 1.1. Variables communes

Les principales variables sont déjà décrites dans `env.example` et `docs/configuration/CONFIGURATION.md`:

- `SECRET_KEY`
- `DATABASE_PATH`
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `WSL_DISTRO`, `WSL_USER`
- Clés API OSINT (Shodan, Censys, Hunter, BuiltWith, HIBP, etc.)

En dev comme en prod, on garde la même logique: tout passe par les variables d'environnement.

### 1.2. Fichiers .env par environnement

Tu peux utiliser plusieurs fichiers `.env` et simplement en copier un au bon moment:

- `.env.dev` pour le développement ;
- `.env.prod` pour la prod.

Exemple de `.env.dev` (simplifié, Windows + WSL, SQLite locale):

```bash
SECRET_KEY=dev-secret-key-change-in-production

DATABASE_PATH=prospectlab.db

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

WSL_DISTRO=kali-linux
WSL_USER=loupix

OSINT_TOOL_TIMEOUT=60
PENTEST_TOOL_TIMEOUT=120

# Accès HTTP
RESTRICT_TO_LOCAL_NETWORK=false
```

Exemple de `.env.prod` (serveur Debian ou node15.lan, sans WSL, SQLite/Postgres en prod):

```bash
SECRET_KEY=ta-cle-ultra-secrete-en-prod

DATABASE_PATH=/var/lib/prospectlab/prospectlab.db

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

OSINT_TOOL_TIMEOUT=60
PENTEST_TOOL_TIMEOUT=120

# Accès HTTP
RESTRICT_TO_LOCAL_NETWORK=true
```

En dev, tu peux faire:

```bash
cp .env.dev .env
```

Sur le serveur de prod:

```bash
cp .env.prod .env
```

Le code ne change pas, seul le contenu du `.env` change selon l'environnement.

### 1.4. Restriction d'accès HTTP par réseau local

ProspectLab peut être protégé non pas par un système de login classique, mais par une **restriction d'accès HTTP au réseau local/VPN**.

- Quand `RESTRICT_TO_LOCAL_NETWORK=false` (dev local) :
  - l'application est accessible depuis n'importe quelle IP qui peut joindre le serveur ;
- Quand `RESTRICT_TO_LOCAL_NETWORK=true` (recommandé en prod interne) :
  - toutes les routes HTTP Flask sont bloquées si l'IP cliente n'est pas dans les réseaux privés classiques (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`) ou localhost ;
  - **exceptions** importantes :
    - `/track/...` (pixel et clics de tracking pour les emails sortants) reste toujours accessible ;
    - `/api/public/...` (API publique protégée par token) reste accessible pour les intégrations externes.

La détection IP côté Flask utilise en priorité les en-têtes `X-Forwarded-For` / `X-Real-IP` envoyés par Nginx, puis `request.remote_addr`.  
Assure-toi que ta conf Nginx sur `node12.lan` envoie bien ces en-têtes (voir `DEPLOIEMENT_PRODUCTION.md`).

### 1.3. Option: variable APP_ENV

Si tu veux aller plus loin, tu peux ajouter une variable:

- `APP_ENV=development`
- `APP_ENV=production`

Puis l'utiliser dans `config.py` pour ajuster certains paramètres (logs plus verbeux en dev, désactivation du debug en prod, etc.).

Pour l'instant, c'est optionnel: le simple fait d'avoir deux `.env` séparés est déjà suffisant.

---

## 2. Base de données: SQLite en dev, et préparation pour Postgres

Actuellement, le projet utilise directement `sqlite3` dans `services/database/base.py`. Toute la couche base de données est pensée pour SQLite.

```python
class DatabaseBase:
    def __init__(self, db_path: Optional[str] = None):
        ...
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
```

### 2.1. Environnement de développement (SQLite)

En dev, le plus simple est:

- ne pas définir `DATABASE_PATH` dans `.env` ;
- laisser la valeur par défaut: fichier `prospectlab.db` à la racine du projet.

Si tu veux un chemin personnalisé, tu peux définir:

```bash
DATABASE_PATH=/chemin/vers/ton/prospectlab-dev.db
```

Les scripts existants (`scripts/clear_db.py`, etc.) continueront de fonctionner avec cette base.

### 2.2. Environnement de production (SQLite robuste)

Même si SQLite n'est pas aussi puissant que Postgres, il est souvent suffisant pour une première prod, surtout sur un projet solo ou avec peu d'utilisateurs en parallèle.

Recommandations:

- stocker la base dans un répertoire dédié, par exemple `/var/lib/prospectlab/prospectlab.db` ;
- s'assurer que l'utilisateur système qui lance l'app (par exemple `prospectlab`) a les droits en lecture/écriture ;
- prévoir une sauvegarde régulière du fichier (snapshot ou script de backup).

Configuration dans `.env.prod`:

```bash
DATABASE_PATH=/var/lib/prospectlab/prospectlab.db
```

Tu n'as pas besoin de modifier le code: `DatabaseBase` lit déjà `DATABASE_PATH` si elle est définie.

### 2.3. PostgreSQL en production

**✅ PostgreSQL est maintenant supporté en production !**

Le système détecte automatiquement le type de base de données via la variable `DATABASE_URL` :

- Si `DATABASE_URL` est défini et commence par `postgresql://`, PostgreSQL est utilisé
- Sinon, SQLite est utilisé avec `DATABASE_PATH`

**Configuration PostgreSQL** :

```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

**Migration SQLite → PostgreSQL** :

1. Les requêtes SQL sont automatiquement adaptées (INSERT OR REPLACE → INSERT ... ON CONFLICT)
2. L'initialisation de la base crée automatiquement toutes les tables
3. Les scripts de migration sont gérés automatiquement

**En production** :
- PostgreSQL est utilisé sur `node15.lan`
- La base est initialisée automatiquement au premier démarrage
- Voir [DEPLOIEMENT_PRODUCTION.md](DEPLOIEMENT_PRODUCTION.md) pour les détails complets

---

## 3. Utilisation de WSL ou Debian pour les outils OSINT / Pentest

ProspectLab est prévu pour utiliser des outils externes OSINT / Pentest via WSL ou directement sous Linux.

Les docs existantes à lire en complément:

- `docs/INSTALL_OSINT_TOOLS.md`
- `docs/techniques/OSINT_TOOLS.md`
- `docs/techniques/PENTEST_TOOLS.md`

### 3.1. Dev sous Windows avec WSL

En dev sous Windows:

1. Installer WSL et une distribution (par exemple Kali ou Debian).
2. Installer les outils OSINT / Pentest dans WSL (suivre `INSTALL_OSINT_TOOLS.md`).
3. Configurer dans ton `.env.dev`:

   ```bash
   WSL_DISTRO=kali-linux
   WSL_USER=ton_user_wsl
   OSINT_TOOL_TIMEOUT=60
   PENTEST_TOOL_TIMEOUT=120
   ```

4. Utiliser les scripts PowerShell dans `scripts/windows` pour piloter certains services (Redis, Celery, etc.).

Le code lit `WSL_DISTRO` et `WSL_USER` dans `config.py` et les utilise pour lancer les commandes côté WSL.

### 3.2. Dev / prod sous Debian (sans WSL)

Sur une machine Debian (ou autre Linux), tu peux installer directement les outils OSINT / Pentest:

1. Connecte-toi au serveur Linux (par exemple `node15.lan`).
2. Suis les instructions de `docs/INSTALL_OSINT_TOOLS.md` côté Linux.
3. Dans ton `.env` sur ce serveur:

   - tu peux ignorer `WSL_DISTRO` et `WSL_USER` si le code ne les utilise que pour Windows ;
   - ou les définir à vide pour bien marquer que WSL n'est pas utilisé.

L'idée:

- en **dev Windows**, WSL sert de couche Linux pour lancer les outils ;
- en **prod Debian**, tout tourne nativement, sans WSL.

### 3.3. Séparation logique des environnements OSINT

Tu peux aussi décider:

- dev: utiliser des clés API de test, des cibles limitées ;
- prod: utiliser des clés API réelles, avec des quotas plus élevés.

Cela se gère simplement via les variables d'environnement (deux fichiers `.env` différents).

---

## 4. Déploiement sur node15.lan

Hypothèse:

- `node15.lan` est une machine Debian qui fera tourner l'application Flask + Celery + Redis ;
- `node12.lan` reçoit déjà le trafic HTTP/HTTPS sur les ports 80 et 443 et jouera le rôle de reverse proxy.

### 4.1. Préparation de node15.lan

Étapes typiques sur `node15.lan`:

1. Créer un utilisateur système dédié, par exemple `prospectlab`.
2. Cloner le dépôt dans `/opt/prospectlab` (par exemple).
3. Créer un environnement virtuel Python et installer les dépendances:

   ```bash
   cd /opt/prospectlab
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Créer un répertoire pour la base SQLite:

   ```bash
   sudo mkdir -p /var/lib/prospectlab
   sudo chown -R prospectlab:prospectlab /var/lib/prospectlab
   ```

5. Créer le `.env` de prod dans `/opt/prospectlab/.env` avec au minimum:

   ```bash
   SECRET_KEY=ta-cle-ultra-secrete
   DATABASE_PATH=/var/lib/prospectlab/prospectlab.db
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   ```

### 4.2. Lancer l'application Flask en service

En prod, plutôt que d'utiliser `python app.py`, on conseille un serveur WSGI comme `gunicorn`, compatible avec Flask-SocketIO (par exemple avec `eventlet`).

Exemple de commande (à adapter selon ton choix de worker):

```bash
cd /opt/prospectlab
source venv/bin/activate
gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 app:app
```

Tu peux ensuite créer un service `systemd` `prospectlab.service` qui:

- se place dans `/etc/systemd/system/prospectlab.service` ;
- lance cette commande avec l'utilisateur `prospectlab` ;
- redémarre automatiquement en cas de crash.

Même principe pour un service `celery.service` et éventuellement `celery-beat.service`.

L'important pour la suite:

- l'application écoute sur `node15.lan:5000` (HTTP interne) ;
- le reverse proxy sur `node12.lan` pointera vers cette adresse.

---

## 5. Reverse proxy sur node12.lan et sous-domaines

`node12.lan` reçoit déjà le trafic sur les ports 80 et 443. On peut donc y installer Nginx ou Apache et rediriger les sous-domaines vers `node15.lan`.

L'objectif:

- `https://prospectlab.danielcraft.fr` → backend sur `http://node15.lan:5000` ;
- `https://campaigns.danielcraft.fr` → même backend (ou une instance dédiée) avec éventuellement une configuration ou des routes différentes.

### 5.1. Exemple de configuration Nginx pour prospectlab.danielcraft.fr

Sur `node12.lan`, dans un fichier de site Nginx, par exemple `/etc/nginx/sites-available/prospectlab.conf`:

```nginx
server {
    listen 80;
    server_name prospectlab.danielcraft.fr;

    # Option: redirection HTTP -> HTTPS si tu as un certificat
    # return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name prospectlab.danielcraft.fr;

    ssl_certificate /etc/letsencrypt/live/prospectlab.danielcraft.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/prospectlab.danielcraft.fr/privkey.pem;

    location / {
        proxy_pass http://node15.lan:5000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Tu adaptes les chemins de certificats selon ta config (Let’s Encrypt ou autre).

### 5.2. Exemple de configuration Nginx pour campaigns.danielcraft.fr

Pour `campaigns.danielcraft.fr`, il y a deux options:

1. **Même instance de ProspectLab**, mais tu utilises ce sous-domaine pour accéder à une partie "campagnes" de l'app (par exemple une page dédiée ou des endpoints spécifiques).
2. **Instance séparée** (autre process, autre base, autre `.env`) sur un autre port, par exemple `node15.lan:5001`.

Exemple simple où `campaigns.danielcraft.fr` pointe aussi sur `node15.lan:5000`:

```nginx
server {
    listen 80;
    server_name campaigns.danielcraft.fr;
}

server {
    listen 443 ssl;
    server_name campaigns.danielcraft.fr;

    ssl_certificate /etc/letsencrypt/live/campaigns.danielcraft.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/campaigns.danielcraft.fr/privkey.pem;

    location / {
        proxy_pass http://node15.lan:5000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Si tu veux vraiment isoler la partie "campagnes":

- tu peux lancer une seconde instance de l'app sur `node15.lan:5001` avec un `.env` différent (par exemple une autre base, d'autres limites) ;
- et dans Nginx, tu mets `proxy_pass http://node15.lan:5001;` uniquement pour `campaigns.danielcraft.fr`.

### 5.3. DNS et résolution interne

Pour que tout fonctionne:

- les enregistrements DNS publics de `prospectlab.danielcraft.fr` et `campaigns.danielcraft.fr` doivent pointer vers l'IP publique de `node12.lan` ;
- sur le réseau interne, `node12.lan` doit pouvoir résoudre `node15.lan` (via DNS interne ou `/etc/hosts`) ;
- les ports internes (5000, 5001, etc.) doivent être accessibles depuis `node12.lan`.

---

## 6. Résumé des scénarios d'utilisation

Pour résumer:

- **Dev local (Windows + WSL)**:
  - `.env.dev` avec `DATABASE_PATH` local, `WSL_DISTRO` et `WSL_USER` définis ;
  - SQLite locale dans le projet ;
  - outils OSINT / Pentest installés dans WSL.

- **Dev / test sur Debian**:
  - `.env` avec `DATABASE_PATH` dans `/var/lib/prospectlab/prospectlab-dev.db` ;
  - outils OSINT / Pentest installés directement sur Debian ;
  - application lancée sur un port interne (ex: 5000).

- **Prod sur node15.lan derrière node12.lan**:
  - application et Celery tournent sur `node15.lan` (Debian) ;
  - Nginx sur `node12.lan` fait le reverse proxy vers `node15.lan:5000` (et éventuellement 5001 pour campaigns) ;
  - `prospectlab.danielcraft.fr` et `campaigns.danielcraft.fr` pointent vers `node12.lan` au niveau DNS.

Cette organisation te permet:

- de séparer proprement dev et prod sans changer le code ;
- de rester sur SQLite pour commencer, tout en gardant une porte ouverte vers Postgres plus tard ;
- d'utiliser WSL uniquement là où c'est utile (Windows) et Debian nativement en prod ;
- d'exposer l'application proprement via tes sous-domaines existants.


