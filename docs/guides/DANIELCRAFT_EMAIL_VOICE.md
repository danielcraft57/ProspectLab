# DanielCraft - voix, vocabulaire et palette (emails)

Reference pour rediger / designer les campagnes email ProspectLab vers des clients DanielCraft
(commerces, artisans, independants du Grand Est).

Sources :
- Palette : [main.css danielcraft.fr](https://danielcraft.fr/assets/css/main.css) (variables `:root`)
- Vocabulaire / ton : `DanielCraftFr/AGENTS.md` (copie adaptee ci-dessous pour l'usage mail)

Maquettes locales : `design/mockups/emails-audit/`.

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

### Ton Grand Est / Lorrain (léger)

Dosage : **1 touche locale max** par mail (hero, PS ou CTA soft) - pas un mot dialectal par phrase.
Le client doit comprendre du **premier coup**.

#### Le plus connu / populaire (à privilégier)

| Dire | Sens | Exemple mail |
|------|------|----------------|
| `entre midi` | entre 12 h et 14 h | « On peut se parler entre midi si t'es au magasin. » |
| `dis voir` / `regarde voir` | impératif + voir | « Regarde voir, c'est prêt. » / « Dis voir ce qui bloque. » |
| `nareux` / `nareuse` | tatillon / difficile | « Pas pour faire le nareux. » / « Cette note est un peu nareuse. » |
| `clanche` / `clancher` | poignée / fermer la porte | « La clanche web est un peu ouverte. » |
| `cornet` | sac plastique | métaphore rare OK |
| `schneck` | pain au raisin | touche très légère, humour |
| `prendre une rincée` | être trempé / vieillir sous les intempéries | « Ton site a pris une rincée du temps. » |
| article + prénom | « le Loïc » | très léger, signature / bio |

À l'oral Metz = **Mess** ; à l'écrit garder **Metz**.

#### Moins universel (1 max, ou éviter en mail froid)

`couarail`, `bassoter`, `beugner`, `trisser`, `chawée`, `ça geths` - OK entre Lorrains,
mais moins connus hors Moselle. Préférer la colonne du dessus.

**Exemples de ton (avec accents)** :

- « On peut se parler entre midi si t'es au magasin. »
- « Pas la peine de faire le nareux avec le devis : prix affiché, PDF direct. »
- « Dis voir ce qui bloque - on démêle ça ensemble. »
- « Regarde voir, le rapport est prêt. »

#### Accents (obligatoire)

Écrire le français correctement : `prêt`, `Loïc`, `téléphone`, `priorité`, `créneau`,
`français`, `réglé`, `passée`, `réponse`, `démêle`, `rincée`, `clanchée`, `préfère`, etc.
Pas de français « sans accents » dans les maquettes ni les modèles envoyés.

#### Grammaire (mails)

Garder le ton oral, mais corriger le socle :

- Tutoiement cohérent partout (CTA inclus : « Regarde… », pas « Regarder… »)
- Ne pas avaler le `ne` : `ce n'est pas`, `il faut`, `qui n'a pas`, `Il y a`
- Phrase complète : `Tu préfères en parler…` (pas `Préfères en parler…`)
- Accords : `nareuse` (fém.), `clanchée`, `priorités`, `Loïc`
- Virgules utiles : `Moi, c'est Loïc`

OK à l'oral léger : `t'es`, `À plus`, `Dis voir`, `Regarde voir`.

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

Libelles CTA preferes (francais simple, oriente click) :
- « Ouvrir mon rapport (30 sec) »
- « Regarde voir le rapport »
- « Voir ou ca laisse entrer »
- « Allez, je regarde »

Eviter : « Lancer le pentest », « Voir les CVE », « Audit Lighthouse ».

### Sujets d'email (max clicks)

Formules qui marchent bien avec le ton DanielCraft :
- curiosite : « 30 secondes - regarde voir ce que j'ai vu »
- metaphore locale : « Ta clanche web est un peu ouverte »
- contraste : « 3 notes… une est un peu nareuse »
- social : « Le commerce d'a cote est plus facile a trouver »
- age : « Ton site a pris une rincee du temps »
- friction : « Ton site bassote un peu cote demandes »

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
| `{analysis_url}` | Lien `/analyse` (website, full=1, email, name) |
| `{dc_contact_url}` | Ancre contact DanielCraft |
| `{unsubscribe_url}` | Desinscription |
| `{base_url}` | Base ProspectLab (images `static/`) |
| `{security_score}` / `{score_securite}` | Jauge **technique** UI (plus haut = mieux) |
| `{risk_score}` / `{score_pentest}` | Jauge **Pentest** UI = risque brut (plus haut = pire) - **pas** `100 - risk` |
| `{performance_score}` | Score perf (si dispo) |
| `{pentest_surface_score}` | Optionnel : `100 - risk` (évité dans les mails urgence) |
| `{performance_score}` | Score perf (si dispo) |

Conditionnels : `{#if_website}...{#endif}`, `{#if_security}...{#endif}`, `{#if_risk}...{#endif}`, `{#if_performance}...{#endif}`.

Includes utiles : `{#include:dc_signature_a_plus}`, `{#include:dc_footer_audit}`, `{#include:dc_pastilles_scores}`.

Images audit : `{base_url}/static/email/danielcraft/audit/...`

IDs campagnes audit : `html_dc_audit_rapport`, `html_dc_clanche`, `html_dc_scores_nareuse`, `html_dc_relance`, `html_dc_franchement`, `html_dc_secu_clanche`, `html_dc_anciennete_rincee`, `html_dc_voisin_google`, `html_dc_ca_coince`, `html_dc_30_sec`.

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
