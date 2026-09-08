# Assets DanielCraft (preferes aux images generees)

Les heroes des maquettes `emails-pub` reutilisent des visuels deja en prod sur danielcraft.fr.
Pas besoin de generer d'abord - seulement si un angle n'a vraiment pas d'equivalent.

## Mapping maquette -> source

| Fichier local | Source DanielCraft |
|---------------|-------------------|
| `assets/hero-offres-reputation.jpg` | `/assets/images/prestations/cards/pack-reputation-locale.jpg` |
| `assets/hero-offres-vitrine.jpg` | `/assets/images/prestations/cards/site-vitrine-essentiel.jpg` |
| `assets/hero-offres-whatsapp.jpg` | `/assets/images/prestations/cards/pack-whatsapp-commerce.jpg` |
| `assets/hero-offres-ia.jpg` | `/assets/images/prestations/cards/repondeur-intelligent.jpg` |
| `assets/hero-echantillons.jpg` | alias -> `echantillons/beaute.jpg` |
| `assets/hero-echantillons-enseigne.jpg` | alias -> `echantillons/commerce.jpg` |
| `assets/echantillons/{slug}.jpg` | crop haut de `/echantillons/{slug}/screenshots/tablet_1024x2500.webp` (1200x742) |

Tous les slugs du sitemap sont generes via :

```powershell
python scripts/prepare_emails_pub_assets.py --echantillons-only
```

Dans les mails, `{echantillon_screenshot_url}` pointe vers le JPG local
`{base_url}/static/email/danielcraft/pub/echantillons/{slug}.jpg`.

| `assets/hero-bouquins.jpg` | collage covers HTML/CSS, Python, IA, Git |
| `assets/hero-bouquins-commerce.jpg` | collage covers Commerce, Vente, Ecom clients |

Format final : JPG 1200x630, ~email-ready.

## Autres assets utiles (pas encore branches)

Categories :
- `/assets/images/prestations/categories/{packs,identite,ia,mobile,technique,site-contenu,maintenance,eco}.webp`

Cartes offres (exemples) :
- `pack-etre-trouve.jpg`, `pack-presence-telephone.jpg`, `whatsapp-business-setup.jpg`
- `ia-automatisation.jpg`, `visible-assistants-ia.jpg`, `fiche-google-mobile.jpg`

Covers bouquins :
- `/assets/images/livres/covers/*.jpg`

Screenshots echantillons :
- `/echantillons/<slug>/screenshots/tablet_1024x2500.webp`

## Quand regenerer / creer

Seulement si :
- aucun visuel proche dans le catalogue prestations
- besoin d'un hero "campagne" tres specifique

Sinon : telecharger + crop/collage (script a recreer si besoin) plutot que IA.

## Prompts de secours (si vraiment manquant)

Voir section archive ci-dessous - a n'utiliser qu'en dernier recours.

---

### Archive prompts IA (fallback)

Format 1200x630, palette metal-blue DanielCraft, sans texte.

**Reputation** :
```
Soft 3D Google Business profile card above smartphone, gold stars, map pin, teal-navy palette, no text
```

**WhatsApp commerce** :
```
Smartphone chat bubbles beside local storefront, teal-blue friendly commerce vibe, no logos, no text
```
