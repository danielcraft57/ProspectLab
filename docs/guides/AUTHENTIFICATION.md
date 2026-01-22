# Guide d'Authentification

## Vue d'ensemble

Le système d'authentification de ProspectLab protège toutes les routes de l'application et permet de gérer les accès utilisateurs de manière sécurisée.

## Fonctionnalités

### 1. Authentification par session

- **Sessions Flask** : Utilisation des sessions Flask pour maintenir l'état de connexion
- **Sessions permanentes** : Les sessions sont configurées comme permanentes pour une meilleure expérience utilisateur
- **Hashage des mots de passe** : Utilisation de bcrypt pour le hashage sécurisé des mots de passe

### 2. Gestion des utilisateurs

- **Création d'utilisateurs** : Support de la création d'utilisateurs avec rôle administrateur
- **Activation/Désactivation** : Les utilisateurs peuvent être activés ou désactivés
- **Suivi des connexions** : Enregistrement de la dernière connexion de chaque utilisateur

### 3. Protection des routes

- **Décorateur `@login_required`** : Protège toutes les routes nécessitant une authentification
- **Décorateur `@admin_required`** : Protège les routes nécessitant des droits administrateur
- **Routes publiques** : Les routes de tracking email (`/track/pixel` et `/track/click`) restent publiques

## Architecture

### Composants principaux

#### Backend
- **`services/auth.py`** : Module d'authentification avec `AuthManager` et décorateurs
- **`routes/auth.py`** : Routes de login/logout et page d'accueil
- **`services/database/schema.py`** : Table `users` dans la base de données

#### Frontend
- **`templates/login.html`** : Page de connexion
- **`templates/home.html`** : Page d'accueil après connexion
- **`templates/partials/navigation.html`** : Navigation avec bouton de déconnexion

### Base de données

#### Table `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    is_admin INTEGER DEFAULT 0,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    derniere_connexion TIMESTAMP
)
```

## Utilisation

### Créer le premier utilisateur administrateur

Utilisez le script fourni :

```bash
python scripts/create_admin_user.py
```

Le script vous demandera :
- Nom d'utilisateur
- Email
- Mot de passe (minimum 8 caractères recommandé)

### Se connecter

1. Accédez à l'application : `http://localhost:5000/`
2. Vous serez redirigé vers `/login` si non connecté
3. Entrez vos identifiants
4. Vous serez redirigé vers `/home` après connexion

### Se déconnecter

Cliquez sur le bouton "Déconnexion" dans la barre de navigation.

## Protection des routes

### Routes protégées

Toutes les routes suivantes sont protégées par `@login_required` :

- **Routes principales** (`routes/main.py`) :
  - `/home` : Page d'accueil
  - `/dashboard` : Dashboard
  - `/entreprises` : Liste des entreprises
  - `/entreprise/<id>` : Détail d'une entreprise
  - `/analyses-techniques` : Analyses techniques
  - `/analyses-osint` : Analyses OSINT
  - `/analyses-pentest` : Analyses Pentest
  - `/carte-entreprises` : Carte des entreprises

- **Routes API** (`routes/api.py`, `routes/api_extended.py`) :
  - Toutes les routes `/api/*` nécessitent une authentification

- **Routes upload** (`routes/upload.py`) :
  - `/upload` : Upload de fichiers
  - `/preview/<filename>` : Prévisualisation
  - `/api/upload` : API d'upload
  - `/analyze/<filename>` : Analyse de fichiers

- **Routes autres** (`routes/other.py`) :
  - `/campagnes` : Campagnes email
  - `/send-emails` : Envoi d'emails
  - `/templates` : Gestion des templates
  - `/analyse/scraping` : Scraping web
  - Toutes les routes API de campagnes

### Routes publiques

Les routes suivantes restent publiques (nécessaires pour le tracking email) :

- `/track/pixel/<tracking_token>` : Tracking des ouvertures d'email
- `/track/click/<tracking_token>` : Tracking des clics dans les emails

## Sécurité

### Hashage des mots de passe

Les mots de passe sont hashés avec **bcrypt** :
- Salt automatique généré pour chaque mot de passe
- Coût de hashage configurable (par défaut : 12 rounds)
- Protection contre les attaques par force brute

### Sessions

- **Secret key** : Configurée via `SECRET_KEY` dans `config.py` ou `.env`
- **Sessions permanentes** : Activées pour une meilleure expérience utilisateur
- **Expiration** : Gérée par Flask (par défaut : 31 jours)

### Bonnes pratiques

1. **En production** :
   - Changez `SECRET_KEY` dans `.env`
   - Utilisez HTTPS pour protéger les sessions
   - Configurez des sessions sécurisées (SameSite, Secure)

2. **Gestion des utilisateurs** :
   - Utilisez des mots de passe forts (minimum 8 caractères)
   - Ne partagez jamais les mots de passe
   - Désactivez les comptes inactifs

3. **Monitoring** :
   - Surveillez les tentatives de connexion échouées
   - Loggez les accès administrateur

## Dépannage

### Erreur "Vous devez être connecté"

- Vérifiez que vous êtes bien connecté
- Vérifiez que la session n'a pas expiré
- Essayez de vous reconnecter

### Erreur lors de la création d'utilisateur

- Vérifiez que l'utilisateur ou l'email n'existe pas déjà
- Vérifiez que le mot de passe fait au moins 8 caractères
- Vérifiez les logs pour plus de détails

### Session perdue après redémarrage

- C'est normal : les sessions Flask sont stockées en mémoire par défaut
- En production, utilisez un backend de session (Redis, database)

## Améliorations futures

- [ ] Réinitialisation de mot de passe par email
- [ ] Authentification à deux facteurs (2FA)
- [ ] Gestion des rôles et permissions granulaires
- [ ] Audit des connexions et actions
- [ ] Limitation des tentatives de connexion
- [ ] Sessions persistantes en base de données

