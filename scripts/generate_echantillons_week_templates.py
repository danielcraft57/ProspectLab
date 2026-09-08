#!/usr/bin/env python3
"""
Genere des maquettes echantillons generiques (rotation semaine)
branchees sur les slugs du sitemap danielcraft.fr/echantillons/.

Usage:
    python scripts/generate_echantillons_week_templates.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design" / "mockups" / "emails-pub"

# Angles generiques : un par jour, variables secteur / echantillon live
# Slugs cibles (sitemap) : restauration, beaute, odontologie, automobile, commerce,
# comptable, industrie, immobilier, juridique, architecture, fitness, photographie,
# association, education, services, etablissement, technologie, boulangerie, artisan,
# fleuriste, caviste, osteo (+ saas-* pour Techno).
TEMPLATES: list[dict] = [
    {
        "file": "15-echantillons-30s.html",
        "studio_id": "html_dc_echantillons_30s",
        "badge": "30 sec",
        "subject": "30 secondes - un modèle pour {secteur_label}",
        "preheader": "Démo live par métier. Pas à vendre : juste pour te projeter.",
        "h1": "30 secondes pour te projeter",
        "sub": "{secteur_accroche}",
        "idea_title": "L'idée",
        "idea_body": "Un échantillon {secteur_label} déjà structuré. Tu cliques, tu vois, tu te fais une idée.",
        "body": (
            "Pour <strong>{entreprise}</strong>, j'ai un modèle "
            "{#if_secteur_label}<strong>{secteur_label}</strong> {#endif}"
            "en ligne. Pas besoin d'attendre un devis pour voir à quoi ça peut ressembler."
        ),
        "cta": "Voir en 30 secondes",
        "cta_href": "{echantillon_demo_url}",
        "footer_note": "Sans engagement - devis PDF par e-mail",
    },
    {
        "file": "16-echantillons-mobile.html",
        "studio_id": "html_dc_echantillons_mobile",
        "badge": "Mobile",
        "subject": "Sur téléphone, ton métier {secteur_label} ça passe ?",
        "preheader": "La plupart des gens arrivent depuis le téléphone. Jette un oeil au modèle.",
        "h1": "Sur téléphone, ça passe ?",
        "sub": "Modèle {secteur_label} - lisible sur petit écran",
        "idea_title": "Ce qui compte",
        "idea_body": "{secteur_accroche} - et surtout : ça doit être clair sur téléphone.",
        "body": (
            "Point rapide pour <strong>{entreprise}</strong> : "
            "tes clients cherchent {#if_secteur_label}en <strong>{secteur_label}</strong> {#endif}"
            "souvent depuis le téléphone. Le modèle ci-dessous est pensé pour ça."
        ),
        "cta": "Ouvrir la démo mobile",
        "cta_href": "{echantillon_demo_url}",
        "footer_note": "Sans engagement - devis PDF par e-mail",
    },
    {
        "file": "17-echantillons-demo-live.html",
        "studio_id": "html_dc_echantillons_demo_live",
        "badge": "Live",
        "subject": "La démo {secteur_label} est en ligne - jette un oeil",
        "preheader": "Démo navigable, pas une image figée. Tu cliques comme un vrai site.",
        "h1": "La démo est en ligne",
        "sub": "Échantillon {secteur_label} - cliquable",
        "idea_title": "Pas une image",
        "idea_body": "Tu navigues vraiment. Menu, pages, contact - comme si c'était déjà ton site.",
        "body": (
            "Pour <strong>{entreprise}</strong>, plutôt qu'un long discours : "
            "voici une démo {#if_secteur_label}<strong>{secteur_label}</strong> {#endif}"
            "déjà en ligne. Tu cliques, tu te balades, tu me dis ce qui te parle."
        ),
        "cta": "Ouvrir la démo live",
        "cta_href": "{echantillon_demo_url}",
        "footer_note": "Sans engagement - devis PDF par e-mail",
    },
    {
        "file": "18-echantillons-avant-devis.html",
        "studio_id": "html_dc_echantillons_avant_devis",
        "badge": "Devis",
        "subject": "Avant le devis pour {entreprise} - regarde ce modèle",
        "preheader": "On parle prix après. D'abord un modèle concret dans ton univers.",
        "h1": "Avant le devis, regarde ça",
        "sub": "{secteur_accroche}",
        "idea_title": "Pourquoi dans cet ordre",
        "idea_body": "Tu vois le rendu {secteur_label}. Ensuite on parle budget - pas l'inverse.",
        "body": (
            "Je préfère que tu voies un modèle "
            "{#if_secteur_label}<strong>{secteur_label}</strong> {#endif}"
            "avant qu'on parle chiffres pour <strong>{entreprise}</strong>. "
            "Comme ça tu sais ce que tu achètes."
        ),
        "cta": "Voir le modèle d'abord",
        "cta_href": "{echantillon_url}",
        "footer_note": "Ensuite devis PDF si ça te parle - sans engagement",
    },
    {
        "file": "19-echantillons-catalogue.html",
        "studio_id": "html_dc_echantillons_catalogue",
        "badge": "Catalogue",
        "subject": "Y'a un échantillon pour {secteur_label} - et d'autres à côté",
        "preheader": "Commerce, restau, garage, santé, artisan... démos par métier.",
        "h1": "Un pour ton métier - et le catalogue à côté",
        "sub": "Base : échantillon {secteur_label}",
        "idea_title": "Comment ça marche",
        "idea_body": "Tu commences par {secteur_label}. Si un autre modèle te parle plus, tu switches.",
        "body": (
            "Pour <strong>{entreprise}</strong>, je te pointe d'abord le modèle "
            "{#if_secteur_label}<strong>{secteur_label}</strong>{#endif}. "
            "Le catalogue complet est juste à côté si tu veux comparer."
        ),
        "cta": "Voir {secteur_label}",
        "cta_href": "{echantillon_url}",
        "cta2": "Tout le catalogue",
        "cta2_href": "{echantillon_catalog_url}",
        "footer_note": "Sans engagement - devis PDF par e-mail",
    },
    {
        "file": "20-echantillons-projection.html",
        "studio_id": "html_dc_echantillons_projection",
        "badge": "Idée",
        "subject": "{nom}, imagine le site de {entreprise} comme ça",
        "preheader": "Pas à vendre tel quel : un point de départ dans ton métier.",
        "h1": "Imagine ton enseigne là-dessus",
        "sub": "Point de départ {secteur_label}",
        "idea_title": "Projection",
        "idea_body": "{secteur_accroche} - on adapte textes, photos, couleurs à {entreprise}.",
        "body": (
            "Voilà à quoi pourrait ressembler le site de <strong>{entreprise}</strong> "
            "en partant d'un échantillon "
            "{#if_secteur_label}<strong>{secteur_label}</strong>{#endif}. "
            "C'est un point de départ, pas un truc figé."
        ),
        "cta": "Me projeter",
        "cta_href": "{echantillon_demo_url}",
        "footer_note": "Sans engagement - devis PDF par e-mail",
    },
    {
        "file": "21-echantillons-secteur-semaine.html",
        "studio_id": "html_dc_echantillons_secteur_semaine",
        "badge": "Semaine",
        "subject": "Cette semaine : modèle {secteur_label} prêt à regarder",
        "preheader": "Démo branchée sur ton secteur. Jette un oeil quand tu as 1 minute.",
        "h1": "Cette semaine : ton secteur",
        "sub": "Échantillon {secteur_label} prêt",
        "idea_title": "Pour cette campagne",
        "idea_body": "Même base pour tout le monde - le lien pointe vers le modèle de ton métier.",
        "body": (
            "Petit mail de la semaine pour <strong>{entreprise}</strong> : "
            "le modèle "
            "{#if_secteur_label}<strong>{secteur_label}</strong> {#endif}"
            "est prêt. Tu regardes quand tu as une minute, tu me dis ce que tu en penses."
        ),
        "cta": "Voir le modèle de la semaine",
        "cta_href": "{echantillon_demo_url}",
        "footer_note": "Sans engagement - devis PDF par e-mail",
    },
]


def render(tpl: dict) -> str:
    """
    Construit le HTML email a partir d'un dictionnaire d'angle.

    @param tpl: Champs subject, h1, body, cta, etc.
    @returns: Document HTML complet
    """
    subject = tpl["subject"]
    cta2_block = ""
    if tpl.get("cta2"):
        cta2_block = f"""
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 10px;">
                <tr>
                  <td style="text-align:center;">
                    <a href="{tpl['cta2_href']}" style="display:inline-block;color:#184c70;text-decoration:underline;font-size:14px;font-weight:700;padding:8px 12px;">{tpl['cta2']}</a>
                  </td>
                </tr>
              </table>"""

    body = tpl["body"].strip()
    body_html = (
        f'<p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">'
        f'Salut <strong>{{nom}}</strong>,</p>\n'
        f'              <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">\n'
        f"                {body}\n"
        f"              </p>"
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Objet: {subject}</title>
</head>
<body style="margin:0;padding:0;background:#dff8f8;font-family:Inter,'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;">
  <!-- SUBJECT: {subject} -->
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">{tpl['preheader']}</div>
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
                    <span style="display:inline-block;background:rgba(255,255,255,0.22);color:#ffffff;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;padding:6px 10px;border-radius:999px;">{tpl['badge']}</span>
                  </td>
                </tr>
              </table>
              <h1 style="margin:18px 0 8px;color:#ffffff;font-size:25px;line-height:1.25;font-weight:700;">{tpl['h1']}</h1>
              <p style="margin:0 0 8px;color:rgba(255,255,255,0.95);font-size:15px;">{tpl['sub']}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:0;line-height:0;font-size:0;">
              <img src="{{echantillon_screenshot_url}}" alt="Echantillon {{secteur_label}}" width="600" height="371" style="display:block;width:100%;max-width:600px;height:auto;border:0;background:#c9f4f2;aspect-ratio:1.618/1;" />
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px;">
              {body_html}
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;background:#c9f4f2;border-radius:12px;border:1px solid #9fd4ea;">
                <tr><td style="padding:16px 18px;">
                  <p style="margin:0 0 8px;color:#0f3550;font-size:13px;font-weight:700;">{tpl['idea_title']}</p>
                  <p style="margin:0;color:#374151;font-size:14px;line-height:1.55;">{tpl['idea_body']}</p>
                </td></tr>
              </table>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 10px;">
                <tr>
                  <td style="text-align:center;">
                    <a href="{tpl['cta_href']}" style="display:inline-block;background:linear-gradient(140deg,#9fd4ea 0%,#5faed8 28%,#2f78a6 62%,#184c70 100%);color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;padding:15px 28px;border-radius:12px;line-height:1.2;box-shadow:0 10px 28px rgba(24,76,112,0.35);">{tpl['cta']}</a>
                  </td>
                </tr>
              </table>{cta2_block}
              <p style="margin:0 0 22px;text-align:center;color:#6b7280;font-size:13px;">{tpl['footer_note']}</p>
              <p style="margin:0;color:#1f2937;font-size:15px;line-height:1.6;">
                À plus,<br /><strong>Loïc Daniel</strong><br />
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


def main() -> None:
    """Ecrit les maquettes HTML dans emails-pub."""
    OUT.mkdir(parents=True, exist_ok=True)
    for tpl in TEMPLATES:
        path = OUT / tpl["file"]
        path.write_text(render(tpl), encoding="utf-8", newline="\n")
        print("ok", tpl["file"], "->", tpl["studio_id"])
    print(f"done {len(TEMPLATES)} templates")


if __name__ == "__main__":
    main()
