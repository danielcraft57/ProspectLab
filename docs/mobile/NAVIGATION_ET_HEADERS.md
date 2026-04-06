# Navigation, headers et ergonomie des écrans détail (mobile)

Documentation de référence pour les **principes** (iOS Human Interface Guidelines, Material Design, usage réel) et leur **implémentation** dans l’app Expo (`mobile/`). Elle complète [UX_UI.md](UX_UI.md) (lisibilité, graphiques, thème).

---

## Sommaire

1. Pourquoi ce document  
2. Principes  
3. Implémentation dans ProspectLab  
4. Écrans concernés aujourd’hui  
5. Évolutions possibles  
6. Checklist pour un nouvel écran détail  

---

## Pourquoi ce document

Sur mobile, la **navigation** et la **barre supérieure** structurent la confiance de l’utilisateur : il doit toujours savoir **où il est** et **comment revenir** sans hésitation. Les recommandations Apple (HIG) et Google (Material) convergent avec les attentes des utilisateurs sur le terrain (parcours courts, une main, interruption fréquente).

Ce document fixe les **règles** adoptées dans l’app et **où** elles sont codées, pour garder une cohérence quand on ajoute de nouveaux écrans.

---

## Principes

### 1. Un seul moyen clair de remonter

**Règle :** le retour principal se fait **en haut**, dans la **barre de navigation système** (header natif), pas via un second gros bouton « Retour » dans le corps de la page.

**Pourquoi :**

- **Évite la double action** : l’utilisateur ne se demande pas lequel des deux boutons utiliser.
- **Libère l’écran** pour le contenu utile (données, graphiques, actions métier).
- **Alignement HIG / Material** : la navigation hiérarchique s’exprime typiquement par un contrôle en barre supérieure (back / up), pas par des CTA redondants dans le scroll.

**Contre-exemple à éviter :** un `H1` + bouton « Retour » pleine largeur **en plus** du header natif.

---

### 2. Titre = contexte

**Règle :** le titre du header indique **précisément** l’objet affiché dès que les données le permettent (nom d’entreprise, nom de campagne), et non un libellé générique figé (« Entreprise », « Détail ») une fois le chargement terminé.

**Pourquoi :**

- Réduit la charge cognitive : pas besoin de relire tout le haut de page pour savoir quelle fiche est ouverte.
- Utile en **multitâche** ou après un changement d’app : au retour, le titre rappelle le contexte.

**Pendant le chargement :** un **titre de repli** explicite reste acceptable (`Entreprise`, `Campagne #42`) jusqu’à ce que le nom réel soit disponible.

**Évolution :** si les titres sont très longs, prévoir une **troncature** dans le header (`numberOfLines` / largeur max) et reporter le libellé complet dans le **corps** de la page (sous-titre ou première section).

---

### 3. Hiérarchie : sous-page ≠ onglet

**Règle :** une **sous-page** (détail depuis une liste) ne doit pas donner l’impression d’être au **même niveau** que les onglets principaux du bas.

**Pourquoi :**

- Les onglets suggèrent des **sections racines** interchangeables ; un détail est une **descente** dans une section.
- Si la barre d’onglets reste visible, l’utilisateur peut croire qu’il peut passer à « Campagnes » ou « Scan » **sans** être sorti du détail, ce qui brouille le modèle mental.

**Pratique dans l’app :** masquer la **tab bar** lorsque l’URL correspond à un écran dont le chemin contient `/details`, pour renforcer l’idée « tu es dans une fiche, remonte d’abord ».

---

### 4. Deep links et pile de navigation

**Règle :** si l’utilisateur ouvre un écran détail **sans historique** (lien profond, scénario de test, restauration d’état), un simple **retour arrière** peut ne rien faire ou sortir de l’app de façon inattendue.

**Pratique :** si `navigation.canGoBack()` est faux, effectuer un **`replace`** (ou équivalent) vers la **liste parente** connue (`/(tabs)/entreprises`, `/(tabs)/campagnes`, etc.) plutôt qu’un `goBack` vide.

**Pourquoi :** l’utilisateur obtient toujours une **sortie prévisible** vers un écran cohérent dans l’app.

---

### 5. Adaptations par plateforme

| Aspect | iOS (HIG, usage) | Android (Material, usage) |
|--------|------------------|---------------------------|
| Contrôle retour | Souvent **chevron seul** à gauche du titre ; éviter d’encombrer avec un long libellé du niveau précédent si ce n’est pas nécessaire. | **Chevron + libellé** « Retour » (ou up) est courant et attendu. |
| Titre précédent (back title) | Désactiver ou limiter le **back title** à côté du chevron quand il n’apporte pas de valeur (écran étroit, titre long). | Moins central ; le texte « Retour » sur le bouton suffit souvent. |

**Dans l’implémentation :** iOS utilise `headerBackTitleVisible: false` ; Android affiche le texte « Retour » à côté du chevron dans le bouton personnalisé.

---

## Implémentation dans ProspectLab

### Hook `useDetailScreenHeader`

**Fichier :** `mobile/src/ui/useDetailScreenHeader.tsx`

**Rôle :**

- Appelle `navigation.setOptions` dans un **`useLayoutEffect`** pour que le titre et le bouton retour soient appliqués **avant le premier paint**, sans flash de titre incorrect.
- Définit :
  - **`title`** : chaîne résolue (`title` trimé si non vide, sinon `fallbackTitle`).
  - **`headerLeft`** : `Pressable` avec chevron Material ; sur **Android** uniquement, ajout du texte **« Retour »**.
  - **Styles** : `headerStyle`, `headerTitleStyle`, `headerTintColor` alignés sur **`useTheme()`** (carte, texte, primaire).
  - **iOS :** `headerBackTitleVisible: false` pour limiter le bruit visuel du titre de l’écran précédent.
- **Action retour :** si `navigation.canGoBack()` alors `navigation.goBack()` ; sinon `router.replace(listPath)` avec `listPath` typé (`'/(tabs)/entreprises' | '/(tabs)/campagnes'`).

**Contrat d’usage :**

```ts
useDetailScreenHeader({
  title: string;        // ex. nom chargé depuis l’API ; '' tant que inconnu
  fallbackTitle: string; // ex. 'Entreprise', 'Campagne #12'
  listPath: '/(tabs)/entreprises' | '/(tabs)/campagnes';
});
```

---

### Tab bar masquée sur les détails

**Fichier :** `mobile/app/(tabs)/_layout.tsx`

**Logique :** lecture de `pathname` via `usePathname()` ; si `pathname.includes('/details')`, fusion dans `tabBarStyle` de `display: 'none'` pour retirer la barre d’onglets tant que l’utilisateur est sur une sous-route `*/details`.

**Effet :** renforce la hiérarchie « liste → détail » et évite la confusion avec les onglets racine.

---

### Écran détail entreprise

**Fichier :** `mobile/app/(tabs)/entreprises/details.tsx`

- **`useDetailScreenHeader`** avec :
  - `title` : nom ou site web une fois normalisé ;
  - `fallbackTitle` : `'Entreprise'` ;
  - `listPath` : `'/(tabs)/entreprises'`.
- **Suppression** du bandeau interne qui dupliquait **grand titre + bouton Retour** (le header natif porte désormais retour + titre).

---

### Écran détail campagne

**Fichier :** `mobile/app/(tabs)/campagnes/details.tsx`

- **`useDetailScreenHeader`** avec :
  - `title` : nom de campagne depuis l’API lorsqu’il existe ;
  - `fallbackTitle` : `'Campagne #<id>'` ou `'Campagne'` si pas d’id ;
  - `listPath` : `'/(tabs)/campagnes'`.
- **Suppression** de la ligne de navigation manuelle sous le header (chevron + « Campagnes »).

Le **contenu** de la page peut conserver un **H1** ou un hero dans le scroll pour l’impact visuel ; le **titre canonique** de contexte reste celui du header.

---

## Écrans concernés aujourd’hui

| Écran | Route (Expo Router) | Liste de secours (`replace`) |
|--------|----------------------|------------------------------|
| Détail entreprise | `(tabs)/entreprises/details` | `/(tabs)/entreprises` |
| Détail campagne | `(tabs)/campagnes/details` | `/(tabs)/campagnes` |

Les routes `*/details` sont déclarées avec `href: null` dans le layout des onglets pour **ne pas** apparaître comme onglets supplémentaires dans la barre du bas.

---

## Évolutions possibles

- **Titres longs :** passer `headerTitle` en composant custom (`Text` avec `numberOfLines={1}` + `ellipsizeMode`) si les noms dépassent la largeur utile.
- **Sous-titre dans le corps :** conserver dans le scroll une ligne du type « Fiche ProspectLab » ou métadonnées (ID, dernière mise à jour) sans les dupliquer comme titre principal.
- **Autres détails futurs** (ex. email unitaire, segment) : réutiliser le **même hook** avec un nouveau `listPath` typé ou une généralisation `Href` Expo si besoin.
- **Accessibilité :** le bouton retour du hook expose `accessibilityRole="button"` et `accessibilityLabel="Retour"` ; affiner le libellé si le contexte parent doit être vocalisé (ex. « Retour à la liste des entreprises »).

---

## Checklist pour un nouvel écran détail

1. Ajouter la route sous `(tabs)/…/details` avec `href: null` dans `_layout.tsx` si besoin.
2. Appeler **`useDetailScreenHeader`** dès que les paramètres (id, etc.) sont connus ; mettre à jour `title` quand les données arrivent.
3. **Ne pas** ajouter de gros bouton « Retour » dans le contenu sauf cas d’exception documenté (accessibilité spécifique, maquette imposée).
4. Vérifier que le chemin active bien **`/details`** dans `pathname` pour **masquer la tab bar**, ou étendre la condition si le motif d’URL diffère.
5. Choisir une **`listPath`** de secours cohérente pour les deep links.
6. Tester sur **iOS** et **Android** : chevron seul vs chevron + « Retour », et retour avec / sans historique.

---

## Voir aussi

- [UX_UI.md](UX_UI.md) — principes généraux mobile, graphiques, mode sombre  
- [ARCHITECTURE_MOBILE.md](ARCHITECTURE_MOBILE.md) — structure du projet Expo  
- [API_INTEGRATION.md](API_INTEGRATION.md) — consommation de l’API publique  

[← Index mobile](INDEX.md) · [Index documentation](../INDEX.md)
