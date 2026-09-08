#!/usr/bin/env python3
"""Genere les maquettes emails pub (offres / echantillons / bouquins)."""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "design" / "mockups" / "emails-pub"
OUT.mkdir(parents=True, exist_ok=True)


def email(
    title_subject: str,
    preheader: str,
    badge: str,
    h1: str,
    sub: str,
    body_html: str,
    cta_label: str,
    cta_url: str,
    hero_alt: str,
    hero_file: str = "assets/hero-placeholder.jpg",
) -> str:
    """
    Construit un HTML email DanielCraft (maquette).

    @param title_subject: Objet / titre page
    @param preheader: Texte cache preheader
    @param badge: Pastille header
    @param h1: Titre hero
    @param sub: Sous-titre hero
    @param body_html: Corps HTML
    @param cta_label: Libelle bouton
    @param cta_url: URL bouton
    @param hero_alt: Alt image hero
    @param hero_file: Chemin image hero
    @returns: Document HTML complet
    """
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Objet: {title_subject}</title>
</head>
<body style="margin:0;padding:0;background:#dff8f8;font-family:Inter,'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;">
  <!-- SUBJECT: {title_subject} -->
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">{preheader}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#dff8f8;border-collapse:collapse;">
    <tr>
      <td style="padding:36px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 28px rgba(24,76,112,0.18);">
          <tr>
            <td style="padding:22px 28px 16px;background:linear-gradient(140deg,#9fd4ea 0%,#5faed8 28%,#2f78a6 62%,#184c70 100%);">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="display:inline-block;width:38px;height:38px;line-height:38px;text-align:center;background:rgba(255,255,255,0.28);border-radius:11px;color:#0f3550;font-weight:800;font-size:13px;">DC</span>
                    <span style="display:inline-block;margin-left:10px;color:#ffffff;font-size:17px;font-weight:700;vertical-align:middle;">DanielCraft</span>
                  </td>
                  <td style="text-align:right;">
                    <span style="display:inline-block;background:rgba(255,255,255,0.22);color:#ffffff;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;padding:6px 10px;border-radius:999px;">{badge}</span>
                  </td>
                </tr>
              </table>
              <h1 style="margin:18px 0 8px;color:#ffffff;font-size:25px;line-height:1.25;font-weight:700;">{h1}</h1>
              <p style="margin:0 0 8px;color:rgba(255,255,255,0.95);font-size:15px;">{sub}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:0;line-height:0;font-size:0;">
              <img src="{hero_file}" alt="{hero_alt}" width="600" style="display:block;width:100%;max-width:600px;height:auto;border:0;background:#c9f4f2;min-height:180px;" />
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px;">
              {body_html}
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 10px;">
                <tr>
                  <td style="text-align:center;">
                    <a href="{cta_url}" style="display:inline-block;background:linear-gradient(140deg,#9fd4ea 0%,#5faed8 28%,#2f78a6 62%,#184c70 100%);color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;padding:15px 28px;border-radius:12px;line-height:1.2;box-shadow:0 10px 28px rgba(24,76,112,0.35);">{cta_label}</a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 22px;text-align:center;color:#6b7280;font-size:13px;">Sans engagement - devis PDF par e-mail</p>
              <p style="margin:0;color:#1f2937;font-size:15px;line-height:1.6;">
                A plus,<br /><strong>Loic Daniel</strong><br />
                <a href="https://danielcraft.fr" style="color:#4da9d6;text-decoration:none;font-weight:600;">danielcraft.fr</a> - Metz
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 28px 26px;background:#f9fafb;text-align:center;border-top:1px solid #e5e7eb;">
              <p style="margin:0;color:#6b7280;font-size:12px;line-height:1.5;">
                Pas un robot -
                <a href="mailto:contact@danielcraft.fr" style="color:#6b7280;text-decoration:none;font-weight:600;">contact@danielcraft.fr</a>
                - <a href="https://danielcraft.fr/desabonnement" style="color:#6b7280;text-decoration:none;font-weight:600;">Ne plus recevoir d'email</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def para(text: str) -> str:
    """Paragraphe standard du corps email."""
    return f'<p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">{text}</p>'


def box(title: str, text: str) -> str:
    """Bloc info accent turquoise."""
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;background:#c9f4f2;border-radius:12px;border:1px solid #9fd4ea;">
<tr><td style="padding:16px 18px;">
<p style="margin:0 0 8px;color:#0f3550;font-size:13px;font-weight:700;">{title}</p>
<p style="margin:0;color:#374151;font-size:14px;line-height:1.55;">{text}</p>
</td></tr></table>'''


def bullets(items: list[str]) -> str:
    """Liste a puces."""
    lis = "".join(f'<li style="margin:0 0 6px;">{i}</li>' for i in items)
    return f'<ul style="margin:0 0 18px;padding-left:20px;color:#374151;font-size:15px;line-height:1.5;">{lis}</ul>'


def main() -> None:
    """Ecrit les 8 maquettes HTML dans emails-pub/."""
    emails = [
        (
            "01-offres-reputation.html",
            email(
                title_subject="On te trouve sur Google ? Pack reputation locale",
                preheader="Fiche Maps + avis + petit coup de propre SEO. Prix HT, devis PDF.",
                badge="Offre",
                h1="Pack reputation locale",
                sub="Maps + avis + coup de propre Google",
                body_html="".join(
                    [
                        para("Salut <strong>Claire</strong>,"),
                        para(
                            "Si tes clients te cherchent sur Google et que la fiche est incomplete, "
                            "tu perds des appels. Le pack du moment regroupe le minimum utile."
                        ),
                        box(
                            "Dedans",
                            "Fiche Google a jour, parcours pour collecter des avis, bases de visibilite locale corrigees.",
                        ),
                        bullets(
                            [
                                "Prix HT affiches",
                                "Devis PDF en quelques minutes",
                                "Un seul interlocuteur - Metz / Grand Est",
                            ]
                        ),
                    ]
                ),
                cta_label="Voir le pack",
                cta_url="https://danielcraft.fr/nos-offres",
                hero_alt="Pack reputation locale Maps et avis",
                hero_file="assets/hero-offres-reputation.jpg",
            ),
        ),
        (
            "02-offres-vitrine-390.html",
            email(
                title_subject="Un site clair pour ton commerce - a partir de 390 EUR HT",
                preheader="Site vitrine sur mesure, delais annonces des le devis, PDF sans engagement.",
                badge="Site",
                h1="Un site qui parle clair",
                sub="Des 390 EUR HT - devis PDF en 2 min",
                body_html="".join(
                    [
                        para("Salut <strong>Claire</strong>,"),
                        para(
                            "Pour un commerce local, le site doit surtout etre clair sur telephone, "
                            "trouve sur Google, et simple a mettre a jour."
                        ),
                        box(
                            "Ce que tu recois",
                            "Pages utiles, formulaires, textes soignes - pas un CMS generique pose a la va-vite.",
                        ),
                        bullets(
                            [
                                "Planning annonce des le devis",
                                "Paiement securise",
                                "Reponse sous 24 h ouvrees",
                            ]
                        ),
                    ]
                ),
                cta_label="Recevoir mon devis PDF",
                cta_url="https://danielcraft.fr/nos-offres",
                hero_alt="Site vitrine commerce local",
                hero_file="assets/hero-offres-vitrine.jpg",
            ),
        ),
        (
            "03-offres-whatsapp.html",
            email(
                title_subject="Tes clients ecrivent sur WhatsApp - ton site peut suivre",
                preheader="Mobile, Maps, messagerie : etre joignable depuis le telephone.",
                badge="Mobile",
                h1="Joignable depuis le telephone",
                sub="WhatsApp + Maps + site sur ecran d'accueil",
                body_html="".join(
                    [
                        para("Salut <strong>Claire</strong>,"),
                        para(
                            "Beaucoup de clients ecrivent avant d'appeler. "
                            "Si le parcours telephone est casse, les demandes partent ailleurs."
                        ),
                        box(
                            "Idee simple",
                            "Un parcours mobile propre : site lisible, bouton WhatsApp, fiche Maps coherente.",
                        ),
                        bullets(
                            [
                                "5 offres cote mobile & messagerie",
                                "Sans jargon",
                                "Devis PDF si tu veux chiffrer",
                            ]
                        ),
                    ]
                ),
                cta_label="Voir Mobile & WhatsApp",
                cta_url="https://danielcraft.fr/nos-offres",
                hero_alt="WhatsApp et site mobile commerce",
                hero_file="assets/hero-offres-whatsapp.jpg",
            ),
        ),
        (
            "04-offres-assistant-ia.html",
            email(
                title_subject="Un assistant pour repondre aux clients (sans te prendre la tete)",
                preheader="Reponses utiles au quotidien du magasin - 14 offres assistants & automatisation.",
                badge="IA",
                h1="Reponses utiles, sans jargon",
                sub="Assistants & automatisation pour le magasin",
                body_html="".join(
                    [
                        para("Salut <strong>Claire</strong>,"),
                        para(
                            "L'idee n'est pas de remplacer ton equipe. "
                            "C'est de repondre plus vite aux questions qui reviennent : horaires, devis, disponibilite."
                        ),
                        box(
                            "Pour qui",
                            "Commerces et artisans du Grand Est qui veulent gagner du temps au comptoir.",
                        ),
                        bullets(
                            [
                                "Formulations simples",
                                "Branche sur ton site / WhatsApp selon l'offre",
                                "Devis PDF a la demande",
                            ]
                        ),
                    ]
                ),
                cta_label="Explorer les assistants",
                cta_url="https://danielcraft.fr/nos-offres",
                hero_alt="Assistant intelligent pour commerce",
                hero_file="assets/hero-offres-ia.jpg",
            ),
        ),
        (
            "05-echantillons-metier.html",
            email(
                title_subject="J'ai un modele dans ton metier - regarde avant de commander",
                preheader="Echantillons complets par metier (restau, garage, sante...). Pas a vendre : pour te projeter.",
                badge="Demo",
                h1="Regarde un modele dans ton metier",
                sub="Sites complets, metier par metier",
                body_html="".join(
                    [
                        para("Salut <strong>Claire</strong>,"),
                        para(
                            "Avant de parler devis, tu peux voir a quoi ressemble un site dans ton univers : "
                            "restaurant, garage, institut, cabinet..."
                        ),
                        box(
                            "Exemples",
                            "Brasserie, spa, dentaire, garage, commerce drive, comptable, immo, sport, hotel...",
                        ),
                        bullets(
                            [
                                "Demo live",
                                "Pas a vendre : base pour poser ton enseigne",
                                "Sur mesure des 390 EUR HT",
                            ]
                        ),
                    ]
                ),
                cta_label="Voir les echantillons",
                cta_url="https://danielcraft.fr/echantillons/",
                hero_alt="Echantillons de sites par metier",
                hero_file="assets/hero-echantillons.jpg",
            ),
        ),
        (
            "06-echantillons-enseigne.html",
            email(
                title_subject="On pose ton enseigne dessus ?",
                preheader="Tu choisis un echantillon proche de ton activite, on adapte textes, photos, couleurs.",
                badge="Projet",
                h1="Ton enseigne sur un modele solide",
                sub="Echantillon -> site a toi",
                body_html="".join(
                    [
                        para("Salut <strong>Claire</strong>,"),
                        para(
                            "Le plus simple : tu pointes un echantillon qui colle a ton metier. "
                            "Ensuite on change le contenu, les photos, le ton - et c'est ton site."
                        ),
                        box(
                            "Pourquoi ca marche",
                            "Tu te projettes tout de suite. Moins de blabla, plus de decisions concretes.",
                        ),
                        bullets(
                            [
                                "Grand Est",
                                "Un seul interlocuteur",
                                "Devis PDF sans engagement",
                            ]
                        ),
                    ]
                ),
                cta_label="Choisir un echantillon",
                cta_url="https://danielcraft.fr/echantillons/",
                hero_alt="Personnaliser un echantillon DanielCraft",
                hero_file="assets/hero-echantillons-enseigne.jpg",
            ),
        ),
        (
            "07-bouquins-050.html",
            email(
                title_subject="PDF clairs a 0,50 EUR - packs encore moins cher",
                preheader="Bouquins PDF : code, commerce, IA, finance. Paiement securise, envoi par e-mail.",
                badge="PDF",
                h1="Avancer sans te prendre la tete",
                sub="Livre a 0,50 EUR - packs en remise volume",
                body_html="".join(
                    [
                        para("Salut <strong>Claire</strong>,"),
                        para(
                            "Des PDF courts et pratiques : web, Python, SQL, IA, securite, commerce & vente... "
                            "Telechargement immediat."
                        ),
                        box(
                            "Packs utiles",
                            "Pack Debutant code, Pack Web, Pack Commerce & vente, Pack Marketing...",
                        ),
                        bullets(
                            [
                                "Paiement securise",
                                "Compatible tous appareils",
                                "Support reactif",
                            ]
                        ),
                    ]
                ),
                cta_label="Voir le catalogue",
                cta_url="https://danielcraft.fr/bouquins/",
                hero_alt="Catalogue bouquins PDF DanielCraft",
                hero_file="assets/hero-bouquins.jpg",
            ),
        ),
        (
            "08-bouquins-commerce.html",
            email(
                title_subject="4 PDF commerce & vente - moins cher qu'a l'unite",
                preheader="Pack Commerce & vente : bases, vente avancee, trouver des clients, fideliser.",
                badge="Pack",
                h1="Vendre mieux, en PDF courts",
                sub="Pack Commerce & vente - 1,49 EUR TTC",
                body_html="".join(
                    [
                        para("Salut <strong>Claire</strong>,"),
                        para(
                            "Si tu preferes lire 20 minutes plutot qu'un cours interminable : "
                            "4 PDF pour clarifier offre, clients, objections et fidelisation."
                        ),
                        box(
                            "Contenu",
                            "Commerce bases + vente avancee + trouver des clients + fideliser.",
                        ),
                        bullets(
                            [
                                "Remise volume vs a l'unite",
                                "Envoi immediat par e-mail",
                                "Aussi : Pack Marketing & com",
                            ]
                        ),
                    ]
                ),
                cta_label="Voir le pack commerce",
                cta_url="https://danielcraft.fr/bouquins/",
                hero_alt="Pack PDF commerce et vente",
                hero_file="assets/hero-bouquins-commerce.jpg",
            ),
        ),
        (
            "09-echantillons-restauration.html",
            email(
                title_subject="Un modele resto pour {entreprise} - jette un oeil",
                preheader="Echantillon restauration : carte, photos, reservation sur telephone.",
                badge="Restau",
                h1="Un resto qui donne envie",
                sub="Echantillon restauration - demo live",
                body_html="".join(
                    [
                        para("Salut <strong>{nom}</strong>,"),
                        para(
                            "Pour <strong>{entreprise}</strong>, voila a quoi peut ressembler un site resto "
                            "clair : carte, photos, reservation - sans te perdre en scroll."
                        ),
                        box("Idee", "{secteur_accroche}"),
                        bullets(["Demo live", "Pas a vendre : base a personnaliser", "Devis PDF si ca te parle"]),
                    ]
                ),
                cta_label="Voir la demo resto",
                cta_url="{echantillon_demo_url}",
                hero_alt="Echantillon restauration",
                hero_file="assets/hero-echantillons-restauration.jpg",
            ),
        ),
        (
            "10-echantillons-auto.html",
            email(
                title_subject="Garage / atelier : un modele deja pret ({secteur_label})",
                preheader="Echantillon automobile : atelier, RDV, devis qui rassurent.",
                badge="Auto",
                h1="Un site atelier qui rassure",
                sub="Echantillon automobile - demi-ecran haut, ratio d'or",
                body_html="".join(
                    [
                        para("Salut <strong>{nom}</strong>,"),
                        para(
                            "Avant de parler prix pour <strong>{entreprise}</strong>, "
                            "tu peux voir un modele garage / atelier deja structure."
                        ),
                        box("Pourquoi", "{secteur_accroche}"),
                        bullets(["RDV et devis visibles", "Demo live", "On pose ton enseigne dessus"]),
                    ]
                ),
                cta_label="Voir le modele auto",
                cta_url="{echantillon_demo_url}",
                hero_alt="Echantillon automobile",
                hero_file="assets/hero-echantillons-automobile.jpg",
            ),
        ),
        (
            "11-echantillons-sante.html",
            email(
                title_subject="Cabinet / sante : un modele pour te projeter",
                preheader="Echantillon sante : tarifs, creneaux, rappel telephonique.",
                badge="Sante",
                h1="Un cabinet clair sur telephone",
                sub="Echantillon sante / cabinet",
                body_html="".join(
                    [
                        para("Salut <strong>{nom}</strong>,"),
                        para(
                            "Pour <strong>{entreprise}</strong>, le site doit surtout rassurer : "
                            "tarifs, creneaux, contact - sans jargon."
                        ),
                        box("Angle", "{secteur_accroche}"),
                        bullets(["Demo live", "Base a personnaliser", "Devis PDF sans engagement"]),
                    ]
                ),
                cta_label="Voir la demo sante",
                cta_url="{echantillon_demo_url}",
                hero_alt="Echantillon sante",
                hero_file="assets/hero-echantillons-sante.jpg",
            ),
        ),
        (
            "12-bouquins-ia.html",
            email(
                title_subject="PDF IA sans bla-bla - a partir de 0,50 EUR",
                preheader="Bases IA, machine learning, deep learning - PDF courts.",
                badge="IA",
                h1="Comprendre l'IA sans te noyer",
                sub="PDF clairs - packs si tu en prends plusieurs",
                body_html="".join(
                    [
                        para("Salut <strong>{nom}</strong>,"),
                        para(
                            "Si tu veux juste les idees utiles (pas un cours de 40 h) : "
                            "PDF courts sur les bases IA, ML et deep learning."
                        ),
                        box("Packs", "IA bases + ML + deep learning - aussi en catalogue unitaires."),
                        bullets(["0,50 EUR le PDF", "Telechargement immediat", "Paiement securise"]),
                    ]
                ),
                cta_label="Voir les PDF IA",
                cta_url="https://danielcraft.fr/bouquins/",
                hero_alt="Pack PDF intelligence artificielle",
                hero_file="assets/hero-bouquins-ia.jpg",
            ),
        ),
        (
            "13-bouquins-secu.html",
            email(
                title_subject="Securite web en PDF - bases jusqu'a expert",
                preheader="Trois niveaux de PDF securite web, clairs et concrets.",
                badge="Secu",
                h1="Secu web, niveau par niveau",
                sub="Bases / intermediaire / expert",
                body_html="".join(
                    [
                        para("Salut <strong>{nom}</strong>,"),
                        para(
                            "Pour <strong>{entreprise}</strong> ou pour toi : des PDF securite web "
                            "qui vont droit au but, sans jargon inutile."
                        ),
                        box("Parcours", "Bases -> intermediaire -> expert. Tu prends ce dont tu as besoin."),
                        bullets(["PDF a 0,50 EUR", "Packs en remise", "Envoi par e-mail"]),
                    ]
                ),
                cta_label="Voir la secu web",
                cta_url="https://danielcraft.fr/bouquins/",
                hero_alt="Pack PDF securite web",
                hero_file="assets/hero-bouquins-secu.jpg",
            ),
        ),
        (
            "14-bouquins-code.html",
            email(
                title_subject="HTML, JS, Python, Git - PDF a 0,50 EUR",
                preheader="Les bases code en PDF courts. Ideal pour demarrer ou reviser.",
                badge="Code",
                h1="Les bases code, version courte",
                sub="HTML/CSS, JavaScript, Python, Git",
                body_html="".join(
                    [
                        para("Salut <strong>{nom}</strong>,"),
                        para(
                            "Pas un pavé : des PDF pour avancer vite sur le web et le code. "
                            "Utile pour toi ou pour former quelqu'un dans l'equipe."
                        ),
                        box("Idee", "Pack debutant code, ou PDF a l'unite a 0,50 EUR."),
                        bullets(["Telechargement immediat", "Tous appareils", "Support reactif"]),
                    ]
                ),
                cta_label="Voir le catalogue code",
                cta_url="https://danielcraft.fr/bouquins/",
                hero_alt="Pack PDF bases code",
                hero_file="assets/hero-bouquins-code.jpg",
            ),
        ),
    ]

    # N'ecrase pas 05/06 deja personnalises (variables secteur) : on ecrit tout sauf ceux-la si --keep
    skip = {"05-echantillons-metier.html", "06-echantillons-enseigne.html"}
    for name, html in emails:
        if name in skip and (OUT / name).exists():
            print("skip", name, "(deja personnalise)")
            continue
        (OUT / name).write_text(html, encoding="utf-8", newline="\n")
        print("wrote", name)
    print("done", len(emails))


if __name__ == "__main__":
    main()
