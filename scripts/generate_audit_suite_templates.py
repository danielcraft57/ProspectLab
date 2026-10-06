#!/usr/bin/env python3
"""
Genere les 6 HTML de la suite audit semaine (html_dc_as_*).

Usage:
  python scripts/generate_audit_suite_templates.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "template_studio" / "html_sources"

# Duos uniques (12 persos)
CHARS = {
    "rapport": ("dc-character-loic.jpg", "dc-character-commerce.jpg"),
    "notes": ("dc-character-sante.jpg", "dc-character-artisan.jpg"),
    "porte": ("dc-character-resto.jpg", "dc-character-auto.jpg"),
    "friction": ("dc-character-coiffure.jpg", "dc-character-immo.jpg"),
    "midi": ("dc-character-sport.jpg", "dc-character-batiment.jpg"),
    "breakup": ("dc-character-bureau.jpg", "dc-character-fleuriste.jpg"),
}


def _img(name: str, side: str) -> str:
    """
    Cellule image personnage.

    @param name: Fichier jpg
    @param side: left|right
    @returns: HTML td
    """
    pad = "0 12px 0 0" if side == "left" else "0 0 0 12px"
    return (
        f'<td width="168" style="width:168px;vertical-align:bottom;padding:{pad};text-align:center;">\n'
        f'                    <img src="{{base_url}}/static/email/danielcraft/characters/{name}" alt="" width="156" '
        f'style="display:block;width:156px;max-width:156px;height:auto;border:0;margin:0 auto;" />\n'
        f"                  </td>"
    )


def _shell(
    *,
    subject: str,
    preheader: str,
    badge: str,
    h1: str,
    subtitle: str,
    left_char: str,
    right_char: str,
    p1a: str,
    p1b: str,
    p2a: str,
    p2b: str,
    box_title: str,
    box_body: str,
    mid_extra: str,
    cta_href: str,
    cta_label: str,
    under_cta: str,
    secondary_cta: str = "",
) -> str:
    """
    Gabarit HTML card DC pour un mail de la suite.

    @returns: Document HTML complet
    """
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Objet: {subject}</title>
</head>
<body style="margin:0;padding:0;background:#dff8f8;font-family:Inter,'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;">
  <!-- SUBJECT: {subject} -->
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
              <p style="margin:0 0 8px;color:rgba(255,255,255,0.95);font-size:15px;">{subtitle}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px;">
              <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Bonjour <strong>{{nom}}</strong>,</p>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;margin:0 0 16px 0;">
                <tr>
                  {_img(left_char, "left")}
                  <td style="vertical-align:middle;padding:0;">
                    <p style="margin:0 0 12px;color:#1f2937;font-size:16px;line-height:1.65;">
                      {p1a}
                    </p>
                    <p style="margin:0;color:#1f2937;font-size:16px;line-height:1.65;">
                      {p1b}
                    </p>
                  </td>
                </tr>
              </table>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;margin:0 0 18px 0;">
                <tr>
                  <td style="vertical-align:middle;padding:0;">
                    <p style="margin:0 0 12px;color:#1f2937;font-size:16px;line-height:1.65;">
                      {p2a}
                    </p>
                    <p style="margin:0;color:#1f2937;font-size:16px;line-height:1.65;">
                      {p2b}
                    </p>
                  </td>
                  {_img(right_char, "right")}
                </tr>
              </table>

              {mid_extra}
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;background:#c9f4f2;border-radius:12px;border:1px solid #9fd4ea;">
                <tr><td style="padding:16px 18px;">
                  <p style="margin:0 0 8px;color:#0f3550;font-size:13px;font-weight:700;">{box_title}</p>
                  <p style="margin:0;color:#374151;font-size:14px;line-height:1.55;">{box_body}</p>
                </td></tr>
              </table>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 10px;">
                <tr>
                  <td style="text-align:center;">
                    <a href="{cta_href}" style="display:inline-block;background:linear-gradient(140deg,#9fd4ea 0%,#5faed8 28%,#2f78a6 62%,#184c70 100%);color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;padding:15px 28px;border-radius:12px;line-height:1.2;box-shadow:0 10px 28px rgba(24,76,112,0.35);">{cta_label}</a>
                  </td>
                </tr>
              </table>
              {secondary_cta}
              <p style="margin:0 0 22px;text-align:center;color:#6b7280;font-size:13px;">{under_cta}</p>
              <p style="margin:0;color:#1f2937;font-size:15px;line-height:1.6;">
                À plus,<br /><strong>Loïc Daniel</strong><br />
                <a href="https://danielcraft.fr" style="color:#4da9d6;text-decoration:none;font-weight:600;">danielcraft.fr</a> - Metz
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 28px 26px;background:#f9fafb;text-align:center;border-top:1px solid #e5e7eb;">
              <p style="margin:0;color:#6b7280;font-size:12px;line-height:1.5;">
                <a href="https://danielcraft.fr/mentions-legales" style="color:#6b7280;text-decoration:none;font-weight:600;">Mentions légales</a>
                -
                <a href="mailto:contact@danielcraft.fr" style="color:#6b7280;text-decoration:none;font-weight:600;">contact@danielcraft.fr</a>
                -
                <a href="{{unsubscribe_url}}" style="color:#6b7280;text-decoration:none;font-weight:600;">Ne plus recevoir d'email</a>
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


def main() -> int:
    """
    Genere les 6 fichiers HTML.

    @returns: Code shell
    """
    OUT.mkdir(parents=True, exist_ok=True)
    specs = [
        (
            "html_dc_as_rapport.html",
            _shell(
                subject="{entreprise} - votre rapport est prêt",
                preheader="2-3 points concrets, lisibles en 30 secondes, sans jargon.",
                badge="Rapport",
                h1="Votre rapport est prêt",
                subtitle="{entreprise}{#if_ville} - {ville}{#endif}",
                left_char=CHARS["rapport"][0],
                right_char=CHARS["rapport"][1],
                p1a="J'ai passé{#if_website} <strong>{website}</strong>{#endif} à la loupe - pas pour faire le tatillon, juste pour voir ce qui freine concrètement pour <strong>{entreprise}</strong>.",
                p1b="Souvent, un site « à peu près ok » laisse quand même filer des contacts : téléphone peu visible, lenteur sur mobile, ou détails de protection à renforcer.",
                p2a="J'ai résumé ça dans un rapport court, avec les priorités classées clairement. C'est lisible en une demi-minute.",
                p2b="Est-ce utile pour vous d'y jeter un oeil cette semaine ?",
                mid_extra="{#include:dc_pastilles_scores}\n",
                box_title="Dedans, en gros",
                box_body="Téléphone, lisibilité, protection - et 2-3 priorités pour avancer sans vous prendre la tête.",
                cta_href="{analysis_url}",
                cta_label="Ouvrir mon rapport (30 sec)",
                under_cta="Sans engagement - un clic, vous voyez tout",
            ),
        ),
        (
            "html_dc_as_notes.html",
            _shell(
                subject="3 notes sur le site de {entreprise}",
                preheader="Sécurité / risque : ce qui ressort en premier pour votre site.",
                badge="Notes",
                h1="Trois notes, sans jargon",
                subtitle="{entreprise}{#if_website} - {website}{#endif}",
                left_char=CHARS["notes"][0],
                right_char=CHARS["notes"][1],
                p1a="Dans le rapport, j'ai mis des notes simples pour situer le site de <strong>{entreprise}</strong> - surtout côté protection et risque.",
                p1b="L'idée n'est pas de vous noyer sous les détails techniques : c'est de voir vite ce qui mérite d'être traité en premier.",
                p2a="Si une note tire vers le bas, ce n'est pas forcément « catastrophique ». En revanche, laisser traîner trop longtemps, ça finit souvent par coûter plus cher (temps, image, ou stress).",
                p2b="Voulez-vous regarder les notes avec les priorités associées ?",
                mid_extra="{#include:dc_pastilles_scores}\n",
                box_title="Ce que ça veut dire",
                box_body="Une note basse = un point à traiter en priorité. Le rapport explique pourquoi, en français.",
                cta_href="{analysis_url}",
                cta_label="Voir les notes du rapport",
                under_cta="30 secondes - sans engagement",
            ),
        ),
        (
            "html_dc_as_porte.html",
            _shell(
                subject="{entreprise} - la porte web un peu ouverte ?",
                preheader="Protection du site : 2-3 points à regarder avant que ça coince.",
                badge="Protection",
                h1="La porte un peu ouverte",
                subtitle="{entreprise}{#if_ville} - {ville}{#endif}",
                left_char=CHARS["porte"][0],
                right_char=CHARS["porte"][1],
                p1a="Sur beaucoup de sites locaux, la « porte » numérique n'est pas grande ouverte - mais elle n'est pas toujours bien calée non plus.",
                p1b="Mises à jour, certificats, petits trous visibles… Rien de spectaculaire au quotidien, jusqu'au jour où ça le devient.",
                p2a="Dans le rapport de <strong>{entreprise}</strong>, j'ai isolé ce qui touche à la protection : ce qui est ok, et ce qui mériterait un coup d'oeil bientôt.",
                p2b="Est-ce un sujet pour vous en ce moment, ou plutôt plus tard ?",
                mid_extra="",
                box_title="Priorité protection",
                box_body="2-3 points concrets, classés - pour savoir quoi faire en premier sans tout refaire.",
                cta_href="{analysis_url}",
                cta_label="Voir le volet protection",
                under_cta="Sans jargon - juste l'essentiel",
            ),
        ),
        (
            "html_dc_as_friction.html",
            _shell(
                subject="Les gens arrivent sur {entreprise} - puis ça coince ?",
                preheader="Téléphone, CTA, lenteur : ce qui freine les demandes sur votre site.",
                badge="Friction",
                h1="Puis ça coince",
                subtitle="{entreprise}{#if_secteur_label} · {secteur_label}{#endif}",
                left_char=CHARS["friction"][0],
                right_char=CHARS["friction"][1],
                p1a="Un site peut être « joli » et pourtant freiner les demandes : bouton peu clair, numéro caché, page lente sur téléphone.",
                p1b="Résultat classique : le visiteur hésite, referme, et appelle le voisin qui a rendu le contact évident en deux secondes.",
                p2a="Pour <strong>{entreprise}</strong>, j'ai noté dans le rapport ce qui peut créer cette friction - sans vous demander de tout changer d'un coup.",
                p2b="Est-ce que récupérer 1 ou 2 contacts de plus par semaine aurait du sens pour vous ?",
                mid_extra="",
                box_title="Ce qui freine souvent",
                box_body="Téléphone visible, CTA clair, vitesse mobile - les 3 leviers les plus fréquents chez les commerces et cabinets locaux.",
                cta_href="{analysis_url}",
                cta_label="Voir ce qui freine",
                under_cta="Rapport court - sans engagement",
            ),
        ),
        (
            "html_dc_as_midi.html",
            _shell(
                subject="15 minutes pour {entreprise} - autour de midi ?",
                preheader="Un échange court pour démêler le rapport, sans jargon.",
                badge="Créneau",
                h1="Autour de midi ?",
                subtitle="{entreprise}",
                left_char=CHARS["midi"][0],
                right_char=CHARS["midi"][1],
                p1a="Entre le rapport, le quotidien et le reste, ce n'est pas toujours simple de trancher seul devant sa boîte mail.",
                p1b="Du coup le sujet glisse, le lien reste ouvert « pour plus tard », et rien n'avance - alors qu'un court échange suffirait souvent.",
                p2a="Je vous propose 15 minutes pour démêler ça ensemble : ce qui compte vraiment pour <strong>{entreprise}</strong>, et ce qui peut attendre.",
                p2b="Autour de midi si vous êtes sur place, ça me va très bien. Est-ce un créneau pertinent cette semaine ?",
                mid_extra="",
                box_title="Ce qu'on peut voir ensemble",
                box_body="Les priorités du rapport, ce qui bloque, et si un coup de main a du sens - ou pas.",
                cta_href="{dc_contact_url}",
                cta_label="Proposer un créneau",
                under_cta="Répondez OK ou proposez un horaire",
                secondary_cta=(
                    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 10px;">\n'
                    '                <tr>\n'
                    '                  <td style="text-align:center;">\n'
                    '                    <a href="{analysis_url}" style="display:inline-block;color:#4da9d6;text-decoration:underline;font-size:14px;font-weight:600;padding:6px 12px;">Rouvrir le rapport</a>\n'
                    '                  </td>\n'
                    '                </tr>\n'
                    '              </table>\n'
                ),
            ),
        ),
        (
            "html_dc_as_breakup.html",
            _shell(
                subject="Je ferme le dossier {entreprise}",
                preheader="Dernier lien vers le rapport. Plus de mail après celui-ci.",
                badge="Dossier",
                h1="Je ferme le dossier",
                subtitle="{entreprise}",
                left_char=CHARS["breakup"][0],
                right_char=CHARS["breakup"][1],
                p1a="Je n'ai pas eu de retour de votre côté - et c'est tout à fait possible que le timing ne soit pas le bon.",
                p1b="Je préfère ne pas vous relancer encore : trop de mails sans réponse, ça devient du bruit, et ce n'est pas mon objectif.",
                p2a="Je ferme donc le dossier <strong>{entreprise}</strong> de mon côté. Je vous laisse le lien du rapport au cas où la situation évolue.",
                p2b="Si le sujet redevient pertinent plus tard, vous pourrez me répondre sur ce fil.",
                mid_extra="",
                box_title="Lien au cas où",
                box_body="Le rapport reste accessible. Pas d'autre mail après celui-ci.",
                cta_href="{analysis_url}",
                cta_label="Dernier lien - le rapport",
                under_cta="Plus de mail après celui-ci",
            ),
        ),
    ]

    for name, html in specs:
        path = OUT / name
        path.write_text(html, encoding="utf-8")
        print(f"ok {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
