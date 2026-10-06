# DanielCraft - voix, vocabulaire et palette (emails)

Reference pour rediger / designer les campagnes email ProspectLab vers des clients DanielCraft
(commerces, artisans, independants du Grand Est).

Sources :
- Palette : [main.css danielcraft.fr](https://danielcraft.fr/assets/css/main.css) (variables `:root`)
- Vocabulaire / ton : `DanielCraftFr/AGENTS.md` (copie adaptee ci-dessous pour l'usage mail)

Maquettes locales : `design/mockups/emails-audit/`.

Playbook commercial (sequence semaine, methode PAS) : [SEQUENCE_EMAIL_PAS_SEMAINE.md](SEQUENCE_EMAIL_PAS_SEMAINE.md).

---

## Palette (pastel nature bleu)

| Token | Hex | Usage mail |
|-------|-----|------------|
| `--primary-color` | `#4da9d6` | Liens, accents, puces |
| `--primary-dark` | `#0f3550` | Titres forts, texte hero |
| `--primary-light` | `#7bcde3` | Survols / highlights soft |
| `--metal-blue-1` | `#9fd4ea` | Gradient CTA (clair) |
| `--metal-blue-2` | `#5faed8` | Gradient CTA |
| `--metal-blue-3` | `#2f78a6` | Gradient CTA |
| `--metal-blue-4` | `#184c70` | Gradient CTA (fonce), navy |
| `--secondary-color` | `#dff8f8` | Encadres soft, fond de bloc |
| `--accent-color` | `#c9f4f2` | Pastilles / chips |
| `--amber-color` | `#d97706` | Attention douce (pas alarmiste) |
| `--amber-soft` | `#fef3c7` | Fond alerte douce |
| `--green-color` | `#2f9e6a` | Score / point positif |
| `--green-soft` | `#eef8f1` | Fond positif |
| `--gray-50` … `--gray-900` | `#f9fafb` … `#111827` | Neutres texte / fonds |
| `--white` | `#ffffff` | Carte mail |

**CTA principal (meme ADN logo / boutons metal)** :

```css
background: linear-gradient(140deg, #9fd4ea 0%, #5faed8 28%, #2f78a6 62%, #184c70 100%);
box-shadow: 0 10px 28px rgba(24, 76, 112, 0.45);
```

Fond page autour de la carte : `#dff8f8` ou `#f9fafb` (pas du gris froid).

Typo de marque : Inter / Segoe UI en fallback (clients mail).

---

## Style des textes (obligatoire)

Ecrire comme une personne reelle :

- Naturel, spontane, vivant - discussion entre amis
- Eviter phrases toutes faites, jargon formel, formulations trop parfaites
- Tournures simples, claires, directes ; un peu imparfaites si besoin
- Ne doit **pas** sembler ecrit par une IA ni ressembler a un chatbot

### Ponctuation

- Apostrophes droites uniquement : `'`
- Tirets simples uniquement : `-` (jamais `—`)

### Ton oral, francais simple

Pas d'argot regional. Le client doit comprendre du **premier coup**, partout en France.

Formulations preferes :

| Dire | Exemple mail |
|------|----------------|
| `autour de midi` | « On peut se parler autour de midi si vous etes au magasin. » |
| `dites-moi` / `jetez un oeil` | « Jetez un oeil, c'est pret. » / « Dites-moi ce qui bloque. » |
| `tatillon` / `pas terrible` | « Pas pour faire le tatillon. » / « Cette note n'est pas terrible. » |
| `porte` / `fermer` | « Votre porte web est un peu ouverte. » |
| `coup de vieux` | « Votre site a pris un coup de vieux. » |

**Exemples de ton (avec accents, vouvoiement)** :

- « On peut se parler autour de midi si vous etes au magasin. »
- « Pas la peine de faire le tatillon avec le devis : prix affiche, PDF direct. »
- « Dites-moi ce qui bloque - on demele ca ensemble. »
- « Jetez un oeil, le rapport est pret. »

#### Accents (obligatoire)

Ecrire le francais correctement : `pret`, `Loic`, `telephone`, `priorite`, `creneau`,
`francais`, `regle`, `passee`, `reponse`, `demele`, `prefere`, etc.
Pas de francais « sans accents » dans les maquettes ni les modeles envoyes.

#### Grammaire (mails)

Garder le ton oral, mais corriger le socle :

- Vouvoiement coherent partout (CTA inclus : « Regardez… », pas « Regarder… »)
- Ne pas avaler le `ne` : `ce n'est pas`, `il faut`, `qui n'a pas`, `Il y a`
- Phrase complete : `Vous preferez en parler…` (pas `Preferez en parler…`)
- Accords : `priorites`, `Loic`
- Virgules utiles : `Moi, c'est Loic`

OK a l'oral leger : `A plus`, `Dites-moi`, `Jetez un oeil`.

### Public client (prioritaire)

Les destinataires **ne sont pas informaticiens**.

**Interdit** dans un mail grand public (sauf si le prospect est clairement tech) :
CMS, SSR, Lighthouse, framework, TypeScript, Astro, Next, API, DevOps, CI/CD, refactoring,
pentest (mot brut), headers, CSP, HSTS, CVE, etc.

**Préférer** :
- site rapide, clair sur téléphone, trouvé sur Google
- bien protégé / points à renforcer
- devis simple, livraison en jours, un seul interlocuteur
- bénéfice avant le moyen

Si un terme tech est indispensable : le traduire en une phrase simple juste après.
Ne jamais faire sentir le client « nul » en info.

### Positionnement IA (si évoqué)

- IA depuis **2025**, pour aller **environ 3x plus vite**
- Loïc **valide, corrige, livre** - pas un mail « envoyé par un robot »
- Dev depuis **2011**, licence **2018**, Metz / Grand Est
- **À ne pas dire** : pourcentages d'études, noms d'outils IA, LLM, hallucination

Formulation type : « j'utilise l'IA pour aller plus vite, et je contrôle tout avant de livrer ».

### Stack / CMS

Ne jamais présenter le travail comme « un site WordPress » / « sous CMS ».
Préférer : site **fait sur-mesure**, rapide, clair.

---

## CTA analyse (ProspectLab)

URL type :

```
https://danielcraft.fr/analyse?website=...&full=1&email=...&name=...
```

Params : `website`, `full=1`, `email`, `name`.

Libelles CTA preferes (francais simple, oriente click, vouvoiement) :
- « Ouvrir mon rapport (30 sec) »
- « Jetez un oeil au rapport »
- « Voir ou ca laisse entrer »
- « Allez, je regarde »
- « Voir la demo »
- « Le style vous interesse-t-il ? »

Eviter : « Lancer le pentest », « Voir les CVE », « Audit Lighthouse ».

### Sujets d'email (max clicks)

Formules qui marchent bien avec le ton DanielCraft (vouvoiement) :
- curiosite : « 30 secondes - jetez un oeil a ce que j'ai vu »
- metaphore : « Votre porte web est un peu ouverte »
- echantillon : « Un modele {secteur_label} pour {entreprise} ? »
- style custom : « Des echantillons specifiques pour {entreprise} ? »
- friction : « Les gens arrivent - puis ca coince »
- breakup : « Je ferme le dossier {entreprise} »

Toujours : prenom ou nom de site dans l'objet quand possible, preheader qui complete (pas qui repete).

---

## Images et graphiques (recommandé)

Les mails peuvent (et devraient) etre **visuels** : un hero + un graphique de scores attire plus qu'un mur de texte.

### Ce qui marche bien en client mail

| Type | Format | Notes |
|------|--------|--------|
| Hero / illustration | JPG ~600px de large, &lt; 80 Ko | Inline CID via `static/email/` ou URL absolue |
| Graphique scores | PNG genere (Pillow) | Barres / jauge palette DanielCraft |
| Fallback | Barres en tables HTML | Si images bloquees (Outlook / Gmail strict) |

Eviter : SVG seuls, CSS `background-image` pour le contenu cle, animations, canvas.

### Pipeline maquettes

```powershell
# Regenerer les charts PNG (palette)
python design/mockups/emails-audit/generate_charts.py
```

Assets : `design/mockups/emails-audit/assets/`
- `hero-*-email.jpg` : illustrations
- `chart-*.png` : scores / jauge / priorites

En prod ProspectLab : images sous `static/email/` + `services/email_inline_images.py` (CID).

### Contenu interesting a montrer

- 3 scores (technique / protection / vitesse) en barres ou pastilles
- Jauge « niveau de protection » (ambre soft, pas rouge panique)
- Mini hero qui montre telephone + rapport (benefice, pas stack tech)
- Toujours un **texte alternatif** (`alt`) et un mini resume HTML si l'image est masquee

---

## Variables ProspectLab (a utiliser dans les HTML)

| Placeholder | Role |
|-------------|------|
| `{nom}` | Prenom / nom du contact |
| `{entreprise}` | Raison sociale |
| `{website}` | Site du prospect |
| `{email}` | Email du destinataire |
| `{ville}` | Ville (BDD) |
| `{code_postal}` | Code postal |
| `{telephone}` | Telephone entreprise |
| `{metier}` / `{categorie}` | Metier fin (ex. osteopathie) |
| `{secteur_label}` | Groupe secteur FR (ex. Sante) |
| `{secteur_accroche}` | Phrase metier (vouvoiement) |
| `{secteur_raw}` | Brut BDD / type Google |
| `{ville_ou_secteur}` | `à Metz` ou `dans le sante` (fallback) |
| `{echantillon_slug}` | Slug demo (ex. osteo) |
| `{echantillon_titre}` | Nom demo catalogue (ex. Cabinet des Ponts) |
| `{echantillon_metier}` | Tagline demo (ex. Osteopathie) |
| `{echantillon_pitch}` | Excerpt catalogue / accroche |
| `{echantillon_style_cta}` | « Le style vous interesse-t-il ? » |
| `{echantillon_url}` / `{echantillon_fiche_url}` | Fiche echantillon |
| `{echantillon_demo_url}` | Demo live |
| `{echantillon_screenshot_url}` | Hero email (crop) |
| `{echantillon_2_titre}` / `{echantillon_2_*}` | 2e echantillon meme categorie |
| `{echantillon_3_titre}` / `{echantillon_3_*}` | 3e echantillon (si dispo) |
| `{related_cards_html}` | Table HTML 1-2 cartes related (pre-rendue) |
| `{related_cards_html}` | Cartes related seulement |
| `{echantillons_cards_html}` | Galerie complete (primaire + related) screenshot + CTA |
| `{has_echantillons_cards}` | Flag galerie echantillons |
| `{character_url}` | Personnage (compat = slot 1) |
| `{character_1_url}` / `{character_2_url}` | 2 persos par mail (gauche puis droite) |
| `{character_left_url}` / `{character_right_url}` | Compat duo (= slots 1 et 2) |
| `{has_character}` / `{has_character_1}` ... | Flags personnages |
| `{analysis_url}` | Lien `/analyse` (website, full=1, email, name) |
| `{dc_contact_url}` | Ancre contact DanielCraft |
| `{unsubscribe_url}` | Desinscription |
| `{base_url}` | Base ProspectLab (images `static/`) |
| `{security_score}` / `{score_securite}` | Jauge **technique** UI (plus haut = mieux) |
| `{risk_score}` / `{score_pentest}` | Jauge **Pentest** UI = risque brut (plus haut = pire) - **pas** `100 - risk` |
| `{performance_score}` | Score perf (si dispo) |
| `{pentest_surface_score}` | Optionnel : `100 - risk` (evite dans les mails urgence) |

Conditionnels utiles : `{#if_website}`, `{#if_ville}`, `{#if_metier}`, `{#if_echantillon}`, `{#if_echantillon_titre}`, `{#if_echantillon_pitch}`, `{#if_security}`, `{#if_risk}`, `{#if_performance}`.

Includes utiles : `{#include:dc_signature_a_plus}`, `{#include:dc_footer_audit}`, `{#include:dc_pastilles_scores}`.

Images audit : `{base_url}/static/email/danielcraft/audit/...`

Ton des modeles : **vouvoiement** (pas de tutoiement dans les mails clients).

IDs campagnes audit (one-shot) : `html_dc_audit_rapport`, `html_dc_clanche`, `html_dc_scores_nareuse`, `html_dc_relance`, `html_dc_franchement`, `html_dc_secu_clanche`, `html_dc_anciennete_rincee`, `html_dc_voisin_google`, `html_dc_ca_coince`, `html_dc_30_sec`.

Suite audit semaine (campagne) : `html_dc_as_rapport`, `html_dc_as_notes`, `html_dc_as_porte`, `html_dc_as_friction`, `html_dc_as_midi`, `html_dc_as_breakup` - voir [SEQUENCE_EMAIL_AUDIT_SEMAINE.md](SEQUENCE_EMAIL_AUDIT_SEMAINE.md).

---

## Checklist avant envoi d'un modele

1. Palette metal-blue + secondary / accent (pas de rouge panique sauf cas rare)
2. Ton humain + 0 ou 1 touche lorraine max
3. Zero jargon client
4. Apostrophes `'` et tirets `-`
5. CTA vers `/analyse` avec les 4 params quand possible
6. Signature Loic + danielcraft.fr + reponse possible au mail
7. Image hero + graphique (ou barres HTML) + `alt` utiles
8. Variables de la table ci-dessus (pas d'anciens placeholders maison)
