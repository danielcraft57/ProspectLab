# Guide de l'interface utilisateur

## Vue d'ensemble

L'interface utilisateur de ProspectLab est organisee en plusieurs pages principales permettant de gerer les entreprises, analyser les donnees et suivre les analyses en temps reel.

## Pages principales

### Page d'accueil (Dashboard)

Page principale affichant les statistiques globales et les actions rapides.

### Upload Excel

Permet d'importer un fichier Excel contenant les informations des entreprises a analyser.

#### Parametres de scraping

- **Nombre de workers** : Nombre de threads paralleles pour le scraping (recommandation : 3-5)
- **Delai entre requetes** : Temps d'attente en secondes entre chaque requete HTTP (recommandation : 2.0)

#### Progression en temps reel

Lors du scraping, l'interface affiche :

1. **Barre de progression globale** : Affiche le nombre d'entreprises scrapees (X / Y entreprises)
2. **Statistiques de l'entreprise actuelle** :
   - Nombre de pages visitees
   - Emails, personnes, telephones, reseaux sociaux trouves pour cette entreprise
3. **Statistiques cumulees** :
   - Totaux globaux de toutes les entreprises scrapees
   - Emails, personnes, telephones, reseaux sociaux, technologies, images

Une fois le scraping termine, redirection automatique vers la liste des entreprises.

### Liste des entreprises

Affiche toutes les entreprises importees avec leurs informations principales.

#### Filtres disponibles

- **Recherche textuelle** : Recherche dans le nom, secteur, email, responsable, site web
- **Secteur** : Filtre par secteur d'activite
- **Statut** : Filtre par statut (A analyser, Analyse en cours, etc.)
- **Opportunite** : Filtre par niveau d'opportunite
- **Favoris** : Afficher uniquement les entreprises marquees comme favoris

#### Affichage

- **Vue grille** : Cartes avec informations principales
- **Vue liste** : Tableau detaille avec toutes les colonnes
- **Indicateurs circulaires** : pour chaque entreprise, affichage de 2 jauges 0‑100 :
  - **Score de securite** (analyse technique)
  - **Score SEO**

#### Actions rapides

- **Clic sur une carte / ligne** : Ouvre la fiche detaillee dans une modal
- **Etoile** : Marquer / demarquer comme favori (mise a jour temps reel)
- **Bouton de scraping** : Lancer un scraping pour une entreprise specifique

### Graph entreprises (liens externes)

Page dediee listant les **relations entre fiches et domaines tiers** (liens sortants detectes au scraping). Filtres, carte detail au clic, infobulles enrichies, export PNG. Voir le guide detaille : [GRAPH_ENTREPRISES.md](GRAPH_ENTREPRISES.md).
- **Boutons de relance sur les indicateurs** :
  - un petit bouton `↻` sous la jauge **Securite** relance l'**analyse technique** pour l'entreprise courante,
  - un bouton `↻` sous la jauge **SEO** relance l'**analyse SEO**,
  - l'etat de connexion WebSocket est verifie avant d'envoyer la commande; en cas de probleme un toast d'avertissement est affiche.
- Lorsqu'une analyse est relancee :
  - un **loader circulaire** recouvre uniquement la jauge concernee,
  - a la fin de l'analyse, la jauge est mise a jour en temps reel (sans recharger la page),
  - une **notification** en haut de l'ecran affiche le resultat : `"NomEntreprise — Analyse technique/SEO terminee"` ou un message d'erreur.

### Fiche entreprise detaillee

Modal affichant toutes les informations d'une entreprise avec plusieurs onglets.

#### Onglet Info

Informations de base de l'entreprise :
- Nom, adresse, telephone, email
- Secteur, statut, opportunite
- Informations techniques (hebergeur, framework, CMS)
- Resume automatique du site

#### Onglet Images

Affiche toutes les images collectees lors du scraping :
- Images avec dimensions
- Alt text si disponible
- Lien vers la page source

#### Onglet Pages

Affiche les donnees OpenGraph collectees de toutes les pages scrapees :

- **Carte par page** : Chaque page scrapee avec ses metadonnees OG
- **Image de prevue** : Image OpenGraph principale de la page
- **URL de la page** : Lien cliquable vers la page source
- **Titre et description** : Metadonnees principales
- **Badges** : Type OG, nom du site, locale
- **Images supplementaires** : Miniatures cliquables des autres images OG
- **Indicateurs** : Nombre de videos et audios si presents

Les cartes sont organisees de maniere ergonomique avec :
- Design epure avec bordures et ombres
- Animations au survol
- Images cliquables pour agrandissement

#### Onglet Resultats scraping

Affiche les resultats detailles du scraping :
- Emails avec contexte
- Personnes identifiees
- Telephones avec page source
- Reseaux sociaux detectes
- Technologies utilisees

Bouton pour lancer un nouveau scraping si necessaire.

#### Onglet Analyse technique

Affiche une vue synthetique et detaillee de la fiche technique du site :
- Serveur et hebergeur
- Framework / CMS detectes
- SSL (valide ou non, date d'expiration)
- En-tetes de securite principaux
- Outils d'analyse (Analytics, Tag managers, etc.)
- Score de securite global (0-100) avec code couleur
- Metriques de performance et details techniques complets (section deroulante)

Un bouton **"Relancer l'analyse"** permet de declencher une nouvelle analyse technique pour l'entreprise courante. La progression et le resultat sont suivis via WebSocket, avec mise a jour automatique du score dans la modal et sur la carte entreprise.

#### Onglet Analyse OSINT

Resultats de l'analyse OSINT (recherche approfondie sur les responsables).

#### Onglet Analyse Pentest

Resultats des tests de penetration.

Comme pour les onglets Technique et SEO, des boutons de **relance d'analyse** sont disponibles; les evenements WebSocket mettent a jour automatiquement les resultats et le score de risque dans la fiche entreprise.

#### Onglet Notes

Notes et tags personnalises pour l'entreprise.

## Fonctionnalites WebSocket

L'interface utilise WebSocket pour les mises a jour en temps reel :

- **Progression du scraping** : Mise a jour automatique des compteurs
- **Statut de connexion** : Indicateur visuel en bas a droite
- **Notifications** : Alertes pour les erreurs ou completions

## Raccourcis clavier

- **Echap** : Fermer la modal de detail d'entreprise
- **Clic sur l'overlay** : Fermer la modal

## Design et ergonomie

- Interface responsive adaptee a tous les ecrans
- Animations fluides pour une meilleure experience utilisateur
- Couleurs et contrastes optimises pour la lisibilite
- Feedback visuel pour toutes les actions utilisateur

