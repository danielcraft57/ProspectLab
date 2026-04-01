# Documentation mobile ProspectLab

L’application mobile (**Expo / React Native**) consomme l’**[API publique](../guides/API_PUBLIQUE.md)** (`/api/public`) avec un token Bearer. Ce dossier regroupe tout ce qui concerne l’app, sans dupliquer la référence complète des routes (voir le guide serveur).

---

## Liens rapides

| Document | Rôle |
|----------|------|
| [**Guide API publique (serveur)**](../guides/API_PUBLIQUE.md) | Référence officielle : endpoints, permissions, cache HTTP, cURL |
| [**Intégration API**](API_INTEGRATION.md) | Base URL, tableau des routes côté mobile, cache client, erreurs |
| [**Architecture**](ARCHITECTURE_MOBILE.md) | Dossiers, flux, couche `ProspectLabApi` |
| [**Modèles d’ingénierie**](MODELES_INGENIERIE.md) | Patterns, domaine |
| [**Sécurité**](SECURITE.md) | Token, stockage |
| [**OCR**](OCR.md) | Capture et extraction |
| [**UX / UI**](UX_UI.md) | Graphiques, thème |
| [**Navigation & headers**](NAVIGATION_ET_HEADERS.md) | Retour, titres dynamiques, tab bar, deep links (HIG / Material) |
| [**Workflow dev**](DEV_WORKFLOW.md) | Prérequis, commandes Expo |

Retour : [Index général de la documentation](../INDEX.md).

---

## Objectifs de l’app

- Scanner ou saisir du texte (OCR / manuel) pour en extraire emails, téléphones, sites.
- Retrouver les fiches **ProspectLab** et afficher analyses (SEO, technique, OSINT, pentest) quand elles existent.
- Parcourir un **tableau de bord** et des listes **entreprises / campagnes** alignés sur les données de l’API.

Pour la liste exhaustive des URLs et méthodes HTTP, ouvrir toujours le [**Guide API publique**](../guides/API_PUBLIQUE.md) : les deux documents sont maintenus **en parallèle** (serveur = référence ; mobile = consommation et outillage client).
