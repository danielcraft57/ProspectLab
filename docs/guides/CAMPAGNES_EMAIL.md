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
  - Tracking automatique des liens vers le domaine principal configuré (ex. `BASE_URL` / site vitrine)
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
- **Lien vers le site principal** : bouton "Découvrir mes services et tarifs" (tracké automatiquement)
- **Données dynamiques** : Injection automatique des données d'entreprise (technique, OSINT, pentest, scraping)
- **Icônes centrées** : Utilisation de `text-align: center` et `line-height` pour compatibilité email
- **CTA robustes** : Pour la compatibilité clients mail, les CTA sont idéalement mis en forme via des tables (`<table role="presentation">`) et des styles inline.

#### Variables et liens d'analyse
- **`analysis_url`** est construit au rendu à partir du `website` de l'entreprise (`/analyse?website=...&full=1`).
- Si un ancien template stocké en BDD contient encore un lien de démo (`exemple.com`), le rendu remplace ce lien par l'URL calculée pour l'entreprise au moment de l'envoi.

### 5. Multi-domaines (comptes SMTP)

ProspectLab peut envoyer depuis plusieurs domaines (ex. `danielcraft.fr`, `jammy.fr`) avec une base entreprises commune.

- **Compte SMTP par domaine** : table `mail_accounts` (host, port, auth, sender, domain_name, statut, tests).
- **Rattachement des campagnes** : `campagnes_email.mail_account_id`.
- **Rattachement des templates** : `email_templates.mail_account_id`.
- **Sélection du domaine actif** : via le menu `Domaines` (session utilisateur) et page `Gestion domaines & comptes SMTP`.
- **Fallback** : si aucun compte n'est sélectionné, l'app utilise le mode par défaut (DanielCraft / configuration globale).
- **Sécurité** : mot de passe SMTP stocké chiffré en base.

En asynchrone, les workers Celery résolvent automatiquement l'expéditeur à partir de `mail_account_id` de la campagne.

## Architecture technique

### Composants principaux

#### Backend
- **`services/database/campagnes.py`** : Gestion des campagnes, emails envoyés et événements de tracking
- **`services/database/mail_accounts.py`** : CRUD des comptes SMTP multi-domaines
- **`services/email_tracker.py`** : Injection du pixel de tracking et modification des liens
- **`services/template_manager.py`** : Rendu des templates avec données dynamiques
- **`services/email_sender.py`** : Envoi des emails via SMTP
- **`tasks/email_tasks.py`** : Tâche Celery pour l'envoi asynchrone
- **`routes/other.py`** : Routes campagnes/tracking + sélection du domaine actif
- **`routes/mail_accounts.py`** : API de gestion des comptes SMTP/domaines (create/update/delete/probe/check DNS/test send)

#### Frontend
- **`static/js/campagnes.js`** : Gestion de l'interface, WebSocket, génération de noms, paramètres d'envoi (programmation, suggestions intelligentes, reset formulaire)
- **`static/css/modules/pages/campagnes.css`** : Styles des campagnes (cartes, barre de progression, mode d'envoi, bloc programmation, suggestions, dark mode)
- **`templates/pages/campagnes.html`** : Interface de gestion des campagnes

### Base de données

#### Tables
- **`mail_accounts`** : Comptes SMTP multi-domaines
- **`campagnes_email`** : Métadonnées des campagnes
- **`emails_envoyes`** : Détails de chaque email envoyé (avec `tracking_token`)
- **`email_tracking_events`** : Événements de tracking (open, click)

## Délivrabilité et bounces (retours "Undelivered")

### Statuts d'emails (table `emails_envoyes`)

- `sent` : email envoyé (tentative SMTP OK)
- `failed` : erreur d'envoi (SMTP refusé, paramètre manquant, etc.)
- `bounced` : retour NDR reçu après coup (Undelivered / returned to sender)

### Statuts de campagne (table `campagnes_email`)

- `completed` : campagne terminée sans erreurs d'envoi
- `completed_with_errors` : campagne terminée avec erreurs (au moins 1 succès + au moins 1 échec)
- `failed` : zéro email n'a pu être envoyé avec succès

### KPI "Taux de délivrabilité" (strict)

Sur les cartes et dans la modale, le taux affiché est **strict**:

- **Délivrabilité** = \((total\_reussis - total\_bounced) / total\_destinataires\)

Donc ça exclut:
- les erreurs d'envoi (car elles ne sont pas dans `total_reussis`)
- les bounces (taggés après coup via IMAP)

### Tags CRM automatiques (table `entreprises.tags`)

Pour faciliter le filtrage dans les prospects:
- `email_envoye`
- `email_echec_envoi`
- `email_ouvert`
- `email_clique`
- `relance`
- `bounce` + `email_invalide`

### Règles importantes (anti-spam / qualité)

- **Blocage par email**: si une adresse a déjà été marquée `bounced` dans `emails_envoyes`, ProspectLab **n'enverra plus** de campagnes vers cette adresse a l'avenir.
- **Statut entreprise `Bounce`**: une entreprise passe en `Bounce` **uniquement si toutes les adresses email déjà utilisées en campagne** pour cette entreprise ont bouncé.

## Récupération automatique des bounces (IMAP)

ProspectLab n'analyse pas ta boite mail "tout seul" par magie. Pour tagger les bounces, on lit une (ou plusieurs) boites IMAP et on recroise avec `emails_envoyes`.

### Script IMAP

- `scripts/fetch_bounces_imap.py`

Support:
- multi-profils (`IMAP_PROFILES=gmail,node12`)
- suppression des bounces traités côté IMAP (Gmail: labels `\\Trash` / `\\Inbox`)

### Automatisation Celery

Le scan est automatisé:
- 1ère exécution **30 min après le lancement réel** d'une campagne (y compris les campagnes programmées)
- puis **2 fois par jour** via Celery Beat

Variables (`.env`) associées:
- `BOUNCE_SCAN_ENABLED`
- `BOUNCE_SCAN_PROFILES`
- `BOUNCE_SCAN_DAYS`
- `BOUNCE_SCAN_AFTER_CAMPAIGN_DAYS`
- `BOUNCE_SCAN_LIMIT` (0 = sans limite)
- `BOUNCE_SCAN_DELETE_PROCESSED`
- `BOUNCE_SCAN_POST_CAMPAIGN_DELAY_SEC`

### Script de rattrapage (recalcul des statuts Bounce)

Quand tu as un historique existant (ou un changement de regle), tu peux recalculer les statuts `Bounce` avec:

- `scripts/recalculate_bounce_statuses.py`

Par défaut c'est un **dry-run**. Utilise `--apply` pour écrire en base.

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
  - Statut de chaque email (sent, failed, bounced)
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

### Toutes les campagnes passent en FAILED / tous les emails sont en Échec

1. Vérifier la configuration SMTP réelle côté serveur (prod) :
   - `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`.
   - Pour un port 587 classique, le serveur attend généralement **STARTTLS** → `MAIL_USE_TLS` doit être à `True`.
2. Tester directement depuis le serveur (dans le venv) :
   ```bash
   python -c "from services.email_sender import EmailSender; s = EmailSender(); print(s.send_email('votre-email@exemple.com','Test SMTP','Ceci est un test'))"
   ```
   - Si le message contient `Must issue a STARTTLS command first` : activer `MAIL_USE_TLS=true`.
   - Si le message contient `SMTP AUTH extension not supported by server` : le relais ne supporte pas AUTH ; depuis mars 2026, l’envoi continue sans authentification et les campagnes ne devraient plus échouer juste pour cette raison.
3. Vérifier que les services (gunicorn, workers Celery) tournent bien avec les mêmes variables d’environnement (`.env` ou `EnvironmentFile` systemd) que le test manuel.

### Le texte sous la barre de progression ne s'affiche pas

- Le problème a été corrigé avec des styles inline et `appendChild`
- Vérifier que le CSS `.progress-text` est bien chargé
- Vérifier la console JavaScript pour d'éventuelles erreurs

### Erreur `get_latest_scraper`

- Corrigé : Utilisation de `get_scrapers_by_entreprise()` et prise du premier élément
- Vérifier que `services/database/scrapers.py` contient bien cette méthode

## Améliorations futures

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
  - Sur les pages de destination (landing du domaine configuré ou autre) liées depuis l'email :
    - Récupérer un identifiant de tracking (par exemple `tracking_token` ou `email_id`) dans l'URL.
    - Mesurer le temps passé sur la page (timer JS démarré au `DOMContentLoaded`, interrompu au `beforeunload`).
    - Envoyer une requête HTTP (par ex. `POST /track/read_time/<tracking_token>?seconds=42`) qui créera un événement `read_time`.
  - Important : les clients email bloquent le JavaScript, donc la mesure doit se faire sur une page web contrôlée (landing page), pas dans l'email lui-même.

