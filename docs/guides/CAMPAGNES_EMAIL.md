# Guide des Campagnes Email

## Vue d'ensemble

Le système de campagnes email permet d'envoyer des emails en masse à des entreprises avec suivi en temps réel, tracking des ouvertures et clics, et personnalisation via templates HTML.

## Fonctionnalités principales

### 1. Création de campagne

- **Nom automatique** : Le nom de la campagne est généré automatiquement (format lisible sans emoji, ex. "Présence en ligne - Technologie").

- **Paramètres d'envoi** :
  - **Mode** : "Envoyer maintenant" ou "Programmer l'envoi" (segmented control).
  - **Délai entre envois** : En secondes, pour étaler les envois et rester naturel.
  - **Date et heure d'envoi** : Visibles uniquement en mode "Programmer l'envoi", initialisées à la date/heure actuelle.
  - **Suggestions rapides** : Affichées uniquement en mode programmé ; calcul intelligent selon la date du jour :
    - Jours ouvrés uniquement (week-ends exclus).
    - Jours fériés français exclus (1er janv., Pâques, 1er mai, 8 mai, Ascension, Pentecôte, 14 juil., 15 août, Toussaint, 11 nov., Noël).
    - Heures type bureau : 9h (matin) et 14h (après-midi).
    - Exemples : "Demain matin" (prochain jour ouvré 9h), "Demain après-midi" (14h), "Lundi matin" (prochain lundi 9h).

- **Templates HTML** : Support de templates HTML professionnels avec :
  - Données dynamiques (nom, entreprise, données techniques, OSINT, pentest, scraping)
  - Blocs conditionnels (`{#if_xxx}`)
  - Tracking automatique des liens vers `danielcraft.fr`
  - Design responsive et compatible clients email

- **Sélection des destinataires** : 
  - Sélection par entreprise (tous les emails d'une entreprise)
  - Sélection individuelle d'emails
  - Affichage du nom du contact formaté depuis JSON

### 2. Tracking des emails

#### Tracking des ouvertures
- Pixel invisible (1x1 PNG transparent) injecté dans chaque email HTML
- Route : `/track/pixel/<tracking_token>`
- Enregistrement de l'IP, User-Agent et timestamp

#### Tracking des clics
- Tous les liens sont redirigés via `/track/click/<tracking_token>?url=<url_originale>`
- Enregistrement du lien cliqué, IP, User-Agent et timestamp

#### Configuration du tracking
- Variable d'environnement `BASE_URL` dans `.env` :
  ```env
  BASE_URL=https://votre-domaine.com
  ```
  - En production : URL publique accessible
  - En développement : Utiliser ngrok ou IP publique
  - **Important** : Ne pas utiliser `localhost:5000` car inaccessible depuis l'extérieur

### 3. Suivi en temps réel

- **WebSocket** : Progression en temps réel via Socket.IO
- **Barre de progression** : Affichage du pourcentage d'envoi
- **Statistiques** : Destinataires, envoyés, réussis, échecs
- **Logs** : Derniers événements affichés dans l'interface

### 4. Templates d'email

#### Templates HTML disponibles
- Modernisation technique
- Optimisation performance
- Sécurité et conformité
- Présence digitale
- Audit complet
- Site vitrine
- Application sur mesure
- Automatisation processus

#### Caractéristiques
- **Pas de prix** : Les templates mettent en avant les performances et bénéfices
- **Lien vers danielcraft.fr** : Bouton "Découvrir mes services et tarifs" (tracké automatiquement)
- **Données dynamiques** : Injection automatique des données d'entreprise (technique, OSINT, pentest, scraping)
- **Icônes centrées** : Utilisation de `text-align: center` et `line-height` pour compatibilité email

## Architecture technique

### Composants principaux

#### Backend
- **`services/database/campagnes.py`** : Gestion des campagnes, emails envoyés et événements de tracking
- **`services/email_tracker.py`** : Injection du pixel de tracking et modification des liens
- **`services/template_manager.py`** : Rendu des templates avec données dynamiques
- **`services/email_sender.py`** : Envoi des emails via SMTP
- **`tasks/email_tasks.py`** : Tâche Celery pour l'envoi asynchrone
- **`routes/other.py`** : Routes API et tracking

#### Frontend
- **`static/js/campagnes.js`** : Gestion de l'interface, WebSocket, génération de noms, paramètres d'envoi (programmation, suggestions intelligentes, reset formulaire)
- **`static/css/modules/pages/campagnes.css`** : Styles des campagnes (cartes, barre de progression, mode d'envoi, bloc programmation, suggestions, dark mode)
- **`templates/pages/campagnes.html`** : Interface de gestion des campagnes

### Base de données

#### Tables
- **`campagnes_email`** : Métadonnées des campagnes
- **`emails_envoyes`** : Détails de chaque email envoyé (avec `tracking_token`)
- **`email_tracking_events`** : Événements de tracking (open, click)

### Formatage des noms

Le système utilise `utils/name_formatter.py` pour formater les noms de contacts depuis :
- Chaînes JSON : `{"first_name": "John", "last_name": "Doe"}`
- Dictionnaires Python
- Chaînes simples

## Utilisation

### Créer une campagne

1. Cliquer sur "+ Nouvelle campagne"
2. Étape 1 : Cibler les entreprises (toutes, objectif, critères ou segment) puis sélectionner les entreprises
3. Étape 2 : Choisir les emails par destinataire (ou tout sélectionner par entreprise)
4. Étape 3 : Sélectionner un template HTML (optionnel), sujet, message personnalisé
5. **Paramètres d'envoi** : Délai entre envois ; mode "Envoyer maintenant" ou "Programmer l'envoi" (date/heure, suggestions rapides)
6. Cliquer sur "Lancer la campagne"

À la fermeture du modal (Annuler ou après envoi réussi), le formulaire et la sélection des entreprises sont réinitialisés.

### Suivre une campagne

- La progression s'affiche en temps réel dans la carte de campagne
- Les statistiques sont mises à jour automatiquement
- Les logs montrent les derniers événements

### Consulter les résultats

- Cliquer sur "Voir détails" pour voir :
  - Liste des emails envoyés
  - Statut de chaque email (sent, failed)
  - Statistiques de tracking (ouvertures, clics)

## Configuration

### Variables d'environnement

```env
# Tracking des emails (IMPORTANT)
BASE_URL=https://votre-domaine.com

# Configuration SMTP
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=votre-email@gmail.com
MAIL_PASSWORD=votre-mot-de-passe-app
MAIL_DEFAULT_SENDER="Votre Nom <votre-email@gmail.com>"
```

### Logs

Les logs des campagnes sont enregistrés dans `logs/email_tasks.log` avec :
- Démarrage de campagne
- Envoi de chaque email
- Erreurs éventuelles

## Dépannage

### Le tracking ne fonctionne pas

1. Vérifier que `BASE_URL` est configuré avec une URL publique (pas `localhost`)
2. Vérifier que la table `email_tracking_events` existe
3. Vérifier les logs dans `logs/email_tasks.log`
4. Vérifier que le pixel est bien injecté dans les emails HTML

### Le texte sous la barre de progression ne s'affiche pas

- Le problème a été corrigé avec des styles inline et `appendChild`
- Vérifier que le CSS `.progress-text` est bien chargé
- Vérifier la console JavaScript pour d'éventuelles erreurs

### Erreur `get_latest_scraper`

- Corrigé : Utilisation de `get_scrapers_by_entreprise()` et prise du premier élément
- Vérifier que `services/database/scrapers.py` contient bien cette méthode

## Améliorations futures

- [ ] Statistiques avancées (taux d'ouverture, taux de clic)
- [ ] A/B testing de templates
- [ ] Templates personnalisables par l'utilisateur
- [ ] Export des résultats en CSV/Excel

## Temps de lecture moyen (spécification)

Actuellement, le champ "Temps de lecture moyen" dans la modale de résultats affiche **"Non mesuré"** car aucun événement `read_time` n'est encore enregistré.

Spécification cible :

- **Objectif** : mesurer approximativement le temps pendant lequel un destinataire lit le contenu lié à la campagne (par exemple une landing page).
- **Événement de tracking** :
  - Type : `read_time`
  - Table : `email_tracking_events`
  - Colonne `event_data` (JSON) contenant au minimum :
    ```json
    { "read_time": 42 }
    ```
    où `read_time` est exprimé en secondes.
- **Calcul** :
  - Pour un email donné : moyenne des `read_time` enregistrés pour `email_id` et `event_type = 'read_time'`.
  - Pour une campagne : moyenne de tous les `read_time` des emails de la campagne (champ `avg_read_time` renvoyé par l'API).
- **Collecte côté frontend** (à implémenter dans un second temps) :
  - Sur les pages de destination (site `danielcraft.fr` ou autre) liées depuis l'email :
    - Récupérer un identifiant de tracking (par exemple `tracking_token` ou `email_id`) dans l'URL.
    - Mesurer le temps passé sur la page (timer JS démarré au `DOMContentLoaded`, interrompu au `beforeunload`).
    - Envoyer une requête HTTP (par ex. `POST /track/read_time/<tracking_token>?seconds=42`) qui créera un événement `read_time`.
  - Important : les clients email bloquent le JavaScript, donc la mesure doit se faire sur une page web contrôlée (landing page), pas dans l'email lui-même.

