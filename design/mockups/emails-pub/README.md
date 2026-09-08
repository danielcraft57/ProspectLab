# Maquettes emails - Offres / Échantillons / Bouquins

Galerie : ouvrir `index.html`.

Base scrape (20 aout 2026) :
- https://danielcraft.fr/nos-offres
- https://danielcraft.fr/echantillons/
- https://danielcraft.fr/bouquins/

## Categories ProspectLab proposees

| Categorie UI | Usage | CTA |
|--------------|-------|-----|
| `offres` | Prospection commerces / artisans | `/nos-offres` |
| `echantillons` | Projection métier avant devis | `/echantillons/` |
| `bouquins` | Pub PDF / packs low-ticket | `/bouquins/` |

(Les IDs techniques futurs : `html_dc_offres_*`, `html_dc_echantillons_*`, `html_dc_bouquins_*`.)

## Variantes maquettes

| # | Fichier | Angle | Objet |
|---|---------|-------|-------|
| 01 | `01-offres-réputation.html` | Pack Maps + avis (offre semaine) | On te trouvé sur Google ? Pack réputation locale |
| 02 | `02-offres-vitrine-390.html` | Entree de gamme site | Un site clair - a partir de 390 € HT |
| 03 | `03-offres-whatsapp.html` | Mobile / messagerie | Tes clients écrivent sur WhatsApp |
| 04 | `04-offres-assistant-ia.html` | Assistants magasin | Un assistant pour répondre aux clients |
| 05 | `05-echantillons-métier.html` | Catalogue demos | Modele dans ton métier |
| 06 | `06-echantillons-enseigne.html` | Closing doux | On pose ton enseigne dessus ? |
| 09 | `09-echantillons-restauration.html` | Secteur restau | Un modèle resto |
| 10 | `10-echantillons-auto.html` | Secteur auto | Garage / atelier |
| 11 | `11-echantillons-sante.html` | Secteur santé | Cabinet / santé |
| 15 | `15-echantillons-30s.html` | Semaine Lun | 30 secondes - modèle secteur |
| 16 | `16-echantillons-mobile.html` | Semaine Mar | Sur téléphone ça passe ? |
| 17 | `17-echantillons-demo-live.html` | Semaine Mer | Démo live en ligne |
| 18 | `18-echantillons-avant-devis.html` | Semaine Jeu | Avant le devis |
| 19 | `19-echantillons-catalogue.html` | Semaine Ven | Catalogue + secteur |
| 20 | `20-echantillons-projection.html` | Semaine Sam | Projection enseigne |
| 21 | `21-echantillons-secteur-semaine.html` | Semaine Dim | Modèle de la semaine |
| 07 | `07-bouquins-050.html` | Prix d'appel PDF | PDF a 0,50 € |
| 08 | `08-bouquins-commerce.html` | Pack vente | 4 PDF commerce & vente |

Rotation semaine (génériques, lien auto vers le slug sitemap du secteur) :

| Jour | Template ID | Angle |
|------|-------------|-------|
| Lun | `html_dc_echantillons_30s` | 30 sec |
| Mar | `html_dc_echantillons_mobile` | Mobile |
| Mer | `html_dc_echantillons_demo_live` | Démo live |
| Jeu | `html_dc_echantillons_avant_devis` | Avant devis |
| Ven | `html_dc_echantillons_catalogue` | Catalogue |
| Sam | `html_dc_echantillons_projection` | Projection |
| Dim | `html_dc_echantillons_secteur_semaine` | Secteur semaine |

Les CTA pointent vers `https://danielcraft.fr/echantillons/{slug}/` (ou `/demo/`) selon le secteur BDD via `utils.secteurs`.

Sitemap de reference : https://danielcraft.fr/sitemap-echantillons.xml


## Assets

Heroes prets dans `assets/` : issus des images danielcraft.fr (prestations, echantillons, covers bouquins).
Detail du mapping : `IMAGE_PROMPTS.md`.

**Screenshots echantillons (email)** : `assets/echantillons/{slug}.jpg` (1200x742, crop haut + nombre d'or).
Generes depuis le sitemap `https://danielcraft.fr/sitemap-echantillons.xml`.

```powershell
python scripts/prepare_emails_pub_assets.py --echantillons-only
```

Envoi : `{echantillon_screenshot_url}` pointe vers
`{base_url}/static/email/danielcraft/pub/echantillons/{slug}.jpg` si le fichier existe.

**Galerie unifiee (preview live + params)** : `../emails/index.html`

## Variables secteur (nouvelles)

Utilisables dans les templates (via `utils.secteurs` + `TemplateManager`) :

| Variable | Exemple |
|----------|---------|
| `{secteur}` / `{secteur_label}` | Automobile |
| `{secteur_brut}` | car_repair |
| `{secteur_groupe}` | Automobile |
| `{secteur_accroche}` | atelier, RDV et devis qui rassurent |
| `{echantillon_slug}` | automobile |
| `{echantillon_url}` | https://danielcraft.fr/echantillons/automobile/ |
| `{echantillon_demo_url}` | .../demo/index.html |
| `{echantillon_screenshot_url}` | .../screenshots/tablet_1024x2500.webp |
| `{#if_secteur_label}...{#endif}` | bloc conditionnel |

17 secteurs FR cibles : Technologie, Services, Restauration, Commerce, Education, Automobile, Beaute, Immobilier, BTP, Communication, Sante, Industrie, Finance, Hotellerie, Juridique, Transport, Artisanat.

Normaliser la BDD (dry-run d'abord) :

```powershell
python scripts/google_maps_tools/apply_secteurs_mapping_db.py --dry-run
```

## Variables utiles (a brancher plus tard)

- `{nom}`, `{entreprise}`, `{email}`
- `{secteur}` (matcher echantillon)
- `{analysis_url}`, `{unsubscribe_url}`
- liens fixes : `https://danielcraft.fr/nos-offres`, `/echantillons/`, `/bouquins/`
