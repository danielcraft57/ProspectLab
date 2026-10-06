# Sequence email AUDIT - campagne semaine (DanielCraft)

Playbook pour une campagne **rapport d'analyse** sur les memes entreprises pendant une semaine.
Methode : **PAS** (Probleme, Agitation, Solution) + preuve `{analysis_url}`.
Ton : **vouvoiement**, oral simple (voir [DANIELCRAFT_EMAIL_VOICE.md](DANIELCRAFT_EMAIL_VOICE.md)).

Complement echantillons / demo : [SEQUENCE_EMAIL_PAS_SEMAINE.md](SEQUENCE_EMAIL_PAS_SEMAINE.md).
Technique campagnes : [CAMPAGNES_EMAIL.md](CAMPAGNES_EMAIL.md).

---

## Objectif commercial

1. Faire ouvrir le **rapport** (preuve site actuel).
2. Faire comprendre **les notes** (securite / risque) sans jargon.
3. Isoler un angle **protection** puis un angle **friction** (demandes perdues).
4. Proposer un **echange court** (autour de midi).
5. Clore proprement (**breakup**) avec un dernier lien rapport.

Public : commerces, artisans, independants, cabinets (Grand Est / metiers locaux).

---

## Cadence recommandee (1 semaine)

| Jour | Modele | Angle | CTA |
|------|--------|--------|-----|
| J0 | `html_dc_as_rapport` | Rapport pret | `{analysis_url}` |
| J1 | `html_dc_as_notes` | 3 notes | `{analysis_url}` |
| J2 | `html_dc_as_porte` | Protection / porte | `{analysis_url}` |
| J3 | `html_dc_as_friction` | Friction demandes | `{analysis_url}` |
| J4 | `html_dc_as_midi` | 15 min autour de midi | `{dc_contact_url}` |
| J5 | `html_dc_as_breakup` | Fermeture dossier | `{analysis_url}` |

Espacement ideal : 1 mail / jour ouvre (ou 2-3 jours entre touches si moins serre).

Regles :
- **1 CTA principal** par mail
- **Angle different** a chaque envoi
- Stop immediat si reponse, refus ou desinscription
- Les anciens mails audit (`html_dc_audit_rapport`, `html_dc_clanche`...) restent dispo en one-shot ; cette suite est prevue **campagne**.

---

## Sync BDD

```powershell
python scripts/generate_audit_suite_templates.py
python scripts/sync_audit_suite_to_db.py
```

Prod (`node15`) :

```bash
cd /opt/prospectlab
PYTHONPATH=/opt/prospectlab /opt/prospectlab/env/bin/python scripts/sync_audit_suite_to_db.py
```

---

## Variables utiles

| Variable | Usage |
|----------|--------|
| `{nom}`, `{entreprise}`, `{website}` | Contact |
| `{ville}`, `{secteur_label}` | Ancrage |
| `{analysis_url}` | Rapport |
| `{security_score}`, `{risk_score}` | Pastilles (J0 / J1) |
| `{dc_contact_url}` | Creaneau (J4) |
| `{unsubscribe_url}` | Footer |

Include : `{#include:dc_pastilles_scores}` (affiche seulement si scores dispo).
