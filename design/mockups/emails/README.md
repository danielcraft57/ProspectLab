# Galerie emails unifiee

Ouvrir directement (file:// OK) :

`design/mockups/emails/index.html`

Les HTML sont embarques dans `templates-bundle.js` (plus de CORS / fetch).

Apres modif d'une maquette, regenerer le bundle :

```powershell
python scripts/build_emails_mockups_bundle.py
```

- Categories cliquables : Audit / Offres / Echantillons / Bouquins
- Fiche parametres (nom, entreprise, email, site, secteur) avec valeurs par defaut
- Rendu live des variables (`{nom}`, `{secteur_label}`, `{echantillon_*}`…)
- Sources HTML : `emails-audit/` et `emails-pub/`

Deep-link :

```
emails/index.html?cat=echantillons&id=e01
emails/index.html?cat=audit&id=a01
```
