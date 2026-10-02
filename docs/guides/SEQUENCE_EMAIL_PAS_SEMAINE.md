# Sequence email PAS - campagne semaine (DanielCraft)

Playbook commercial pour une campagne sur **les memes entreprises** pendant une semaine.
Methode : **PAS** (Probleme, Agitation, Solution) + preuve echantillon / rapport.
Ton : **vouvoiement**, oral simple (voir [DANIELCRAFT_EMAIL_VOICE.md](DANIELCRAFT_EMAIL_VOICE.md)).

Technique campagnes / tracking : [CAMPAGNES_EMAIL.md](CAMPAGNES_EMAIL.md).

---

## Objectif commercial

1. Montrer un **echantillon deja fait** dans le metier du prospect (`secteur` → slug catalogue).
2. Proposer des **echantillons specifiques** a son enseigne si le style interesse.
3. Appuyer avec le **rapport d'analyse** (preuve site actuel).
4. Decrocher un **echange court** (autour de midi).
5. Clore proprement (**breakup**) sans harceler.

Public cible : commerces, artisans, independants, cabinets (Grand Est / metiers locaux).

---

## Cadence recommandee (1 semaine)

| Jour | Angle | Preuve principale | Objectif |
|------|--------|-------------------|--------|
| J0 (lun) | Exemple deja fait | `{echantillon_*}` | Clic demo / fiche |
| J1 (mar) | Style + custom | `{echantillon_style_cta}` | Reponse "Oui" |
| J2 (mer) | Constat site | `{analysis_url}` | Ouverture rapport |
| J3 (jeu) | Projection enseigne | echantillon (+ landing si dispo) | Projection visuelle |
| J4 (ven) | Autour de midi | contact humain | Creneau / OK |
| J5 (sam ou lun+) | Breakup | derniers liens | Sortie propre + reponses tardives |

Espacement ideal hors contrainte "semaine" : 2 a 3 jours entre touches.
Sur une semaine serree : un mail par jour ouvré + breakup en fin de cycle.

Regles :
- **1 seul CTA** par mail
- **Angle different** a chaque envoi (jamais "je reviens vers vous")
- Stop immediat si reponse, refus ou desinscription
- Preuve echantillon en heros (J0-J1-J4) ; audit en soutien (J2)

---

## Structure PAS (modele B2B)

Chaque mail suit ce squelette :

1. **Objet** - question ou angle concret
2. **Bonjour + contexte** - `{nom}`, `{entreprise}`, ville / secteur
3. **Probleme + Agitation** - 2 a 4 phrases (frein metier, consequence)
4. **Solution + preuve** - echantillon catalogue, rapport, ou creneau
5. **CTA** - question fermee / semi-ouverte + lien ou reponse courte
6. **Signature** - Loic Daniel, danielcraft.fr, Metz

Longueur cible : ~120 a 180 mots (corps), pas un roman.

Exemple de logique (reference) :

```text
Objet : question pertinente
Bonjour [Prenom],
Contexte perso (entreprise / ville / signal).
Probleme + Agitation (ce qui freine + consequence).
Solution + preuve (exemple deja fait / concurrent-like demo).
CTA (question + lien).
Signature.
```

---

## Variables utiles (sequence)

| Variable | Usage |
|----------|--------|
| `{nom}`, `{entreprise}`, `{website}` | Contact |
| `{ville}`, `{ville_ou_secteur}` | Ancrage local |
| `{secteur_label}`, `{metier}`, `{secteur_accroche}` | Metier |
| `{echantillon_titre}`, `{echantillon_metier}`, `{echantillon_pitch}` | Preuve catalogue |
| `{echantillon_style_cta}` | "Le style vous interesse-t-il ?" |
| `{echantillon_demo_url}`, `{echantillon_fiche_url}`, `{echantillon_url}` | Liens demo |
| `{echantillon_screenshot_url}` | Hero visuel |
| `{analysis_url}` | Rapport |
| `{landing_variant_url}` | Projection perso (si generee) |
| `{dc_contact_url}` | Contact |

Conditionnels : `{#if_ville}`, `{#if_echantillon}`, `{#if_landing_variant}`, etc.

Detail complet : [DANIELCRAFT_EMAIL_VOICE.md](DANIELCRAFT_EMAIL_VOICE.md).

---

## Textes valides (copie de travail)

Prospect type pour lecture : Claire · Cabinet des Lilas · Metz · osteo.

### Mail 1 - Exemple deja fait (J0)

**Objet :** Un modele {secteur_label} pour {entreprise} ?

```text
Bonjour {nom},

J'ai regarde le site de {entreprise}{#if_ville} a {ville}{#endif}, et votre activite cote {secteur_label} / {metier}.

Souvent, dans ce metier, le site ne montre pas assez clairement les creneaux, les tarifs ou la prise de RDV. Les visiteurs hesitent, et une partie part chez un voisin plus lisible sur telephone.

J'ai deja un exemple en ligne dans votre univers : {echantillon_titre} ({echantillon_metier}). {echantillon_pitch} Ca donne une idee concrete du rendu, sans engagement.

Est-ce que ce style de presentation vous interesse pour {entreprise} en ce moment ?
→ Voir la demo : {echantillon_demo_url}
→ Fiche : {echantillon_fiche_url}

A plus,
Loic Daniel - danielcraft.fr · Metz
```

### Mail 2 - Style + custom (J1)

**Objet :** Des echantillons specifiques pour {entreprise} ?

```text
Bonjour {nom},

Je reviens suite a l'exemple {echantillon_titre} que je vous ai transmis.

Beaucoup de professionnels trouvent le modele interessant… mais peinent a se projeter tant que ce n'est pas leur enseigne, leurs services, leur ville. Du coup le sujet reste en suspens.

{echantillon_style_cta} Si oui, je peux vous developper des echantillons specifiques pour {entreprise}{#if_ville}, a {ville}{#endif} - sur la base de ce qui existe deja dans le {secteur_label}.

Est-ce un sujet pertinent pour vous ce mois-ci ?
→ Repondez Oui - ou dites-moi ce qui ne vous convient pas dans le style actuel.

A plus,
Loic Daniel - danielcraft.fr · Metz
```

### Mail 3 - Constat site (J2)

**Objet :** {entreprise} - ce que j'ai vu sur votre site

```text
Bonjour {nom},

En parallele de l'echantillon, j'ai passe {website} a la loupe - sans jargon, juste ce qui compte pour un cabinet / commerce local.

Souvent, un site "a peu pret ok" freine quand meme : lenteur sur telephone, infos difficiles a trouver, ou details de protection a renforcer. Resultat : des petites pertes de contact qui s'accumulent sans qu'on les voie.

J'ai resume 2-3 points concrets dans un rapport court, lisible en 30 secondes, avec les priorites classees clairement.

Est-ce utile pour vous de jeter un oeil ce trimestre ?
→ Ouvrir mon rapport : {analysis_url}

A plus,
Loic Daniel - danielcraft.fr · Metz
```

### Mail 4 - Projection (J3)

**Objet :** Imaginez le site de {entreprise} dans ce style

```text
Bonjour {nom},

Avant de parler devis, le frein le plus frequent c'est l'inconnu : "est-ce que ca ira vraiment pour nous ?"

Sans projection visuelle, on discute dans le vide, on compare des impressions, et on reporte. C'est classique - et ca fait perdre du temps des deux cotes.

Le plus simple : vous projeter sur le modele {echantillon_metier} ({echantillon_titre}), comme si l'enseigne de {entreprise} etait deja dessus.
{#if_landing_variant}J'ai aussi une maquette plus proche de votre site : {landing_variant_url}.{#endif}

Est-ce que cette approche "voir avant de decider" vous parle ?
→ Je me projette : {echantillon_url}

A plus,
Loic Daniel - danielcraft.fr · Metz
```

### Mail 5 - Autour de midi (J4)

**Objet :** 15 minutes pour {entreprise} - autour de midi ?

```text
Bonjour {nom},

Entre l'echantillon, le rapport et le quotidien du cabinet, ce n'est pas toujours simple de trancher seul devant sa boite mail.

Du coup le sujet glisse, les liens restent ouverts "pour plus tard", et rien n'avance - alors qu'un court echange suffirait souvent a clarifier.

Je vous propose 15 minutes pour demeler ca ensemble : ce qui vous plait dans le style {echantillon_titre}, ce qui bloque sur votre site, et si un echantillon sur-mesure a du sens pour {entreprise}. Autour de midi si vous etes sur place, ca me va tres bien.

Est-ce un creneau pertinent pour vous cette semaine ?
→ Repondez OK ou proposez un horaire
→ Contact : {dc_contact_url}

A plus,
Loic Daniel - danielcraft.fr · Metz
```

### Mail 6 - Breakup (J5)

**Objet :** Je ferme le dossier {entreprise}

```text
Bonjour {nom},

Je n'ai pas eu de retour de votre cote - et c'est tout a fait possible que le timing ne soit pas le bon.

Je prefere ne pas vous relancer encore : trop de mails sans reponse, ca devient du bruit, et ce n'est pas mon objectif.

Je ferme donc le dossier {entreprise} de mon cote. Je vous laisse les liens au cas ou la situation evolue : demo {echantillon_metier} et rapport restent accessibles.

Si le sujet redevient pertinent pour vous plus tard, vous pourrez me repondre sur ce fil.
→ Demo : {echantillon_demo_url}
→ Rapport : {analysis_url}

A plus,
Loic Daniel - danielcraft.fr · Metz
(Plus de mail apres celui-ci.)
```

---

## IDs modeles cibles (a creer en BDD)

| ID propose | Categorie | Jour |
|------------|-----------|------|
| `html_dc_pas_echantillon` | echantillons | J0 |
| `html_dc_pas_style_custom` | echantillons | J1 |
| `html_dc_pas_constat_site` | audit | J2 |
| `html_dc_pas_projection` | echantillons | J3 |
| `html_dc_pas_midi` | offres | J4 |
| `html_dc_pas_breakup` | audit | J5 |

---

## Checklist avant lancement campagne

1. Fichier entreprises avec `secteur` (ou `secteur_raw`) renseigne → matching echantillon OK
2. Preferee : `ville` renseignee pour `{ville_ou_secteur}`
3. Analyses / rapports dispo pour le J2 (`analysis_url`)
4. Heroes echantillons presents sous `static/email/danielcraft/pub/echantillons/`
5. Vouvoiement partout (objets, corps, CTA)
6. Apostrophes droites `'` et tirets simples `-`
7. Un seul CTA tracke par mail
8. Signature Loic + lien desinscription

---

## Liens utiles

- Voix / palette / variables : [DANIELCRAFT_EMAIL_VOICE.md](DANIELCRAFT_EMAIL_VOICE.md)
- Campagnes techniques : [CAMPAGNES_EMAIL.md](CAMPAGNES_EMAIL.md)
- Catalogue echantillons : `static/danielcraft/vitrines.json`
- Mapping secteur → slug : `utils/secteurs.py`
