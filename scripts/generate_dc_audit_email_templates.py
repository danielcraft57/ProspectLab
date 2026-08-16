#!/usr/bin/env python3
"""Génère les html_sources DanielCraft audit depuis les maquettes (variables ProspectLab)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "template_studio" / "html_sources"
IMG = "{base_url}/static/email/danielcraft/audit"


def shell(title: str, preheader: str, body_rows: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#dff8f8;font-family:Inter,'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        {preheader}
    </div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#dff8f8;border-collapse:collapse;">
        <tr>
            <td style="padding:36px 16px;">
                <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 28px rgba(24,76,112,0.18);">
{body_rows}
                    <tr>
                        <td style="padding:20px 28px 26px;background:#f9fafb;text-align:center;border-top:1px solid #e5e7eb;">
                            {{#include:dc_footer_audit}}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def header_band(h1: str, sub: str, badge: str = "Gratuit") -> str:
    return f"""                    <tr>
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
                    </tr>"""


def hero(src: str, alt: str) -> str:
    return f"""                    <tr>
                        <td style="padding:0;line-height:0;font-size:0;">
                            <img src="{src}" alt="{alt}" width="600" style="display:block;width:100%;max-width:600px;height:auto;border:0;">
                        </td>
                    </tr>"""


def cta(label: str) -> str:
    return f"""                            {{#if_website}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 10px;">
                                <tr>
                                    <td style="text-align:center;">
                                        <a href="{{analysis_url}}" style="display:inline-block;background:linear-gradient(140deg,#9fd4ea 0%,#5faed8 28%,#2f78a6 62%,#184c70 100%);color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;padding:15px 28px;border-radius:12px;line-height:1.2;box-shadow:0 10px 28px rgba(24,76,112,0.35);">{label}</a>
                                    </td>
                                </tr>
                            </table>
                            {{#endif}}"""


TEMPLATES: dict[str, tuple[str, str]] = {}


def add(tid: str, title: str, html: str) -> None:
    TEMPLATES[tid] = (title, html)


# --- 01 rapport ---
add(
    "html_dc_audit_rapport",
    "{nom}, ton rapport est prêt - regarde voir",
    shell(
        "{nom}, ton rapport est prêt - regarde voir",
        "2-3 trucs concrets sur {entreprise}, sans jargon.",
        header_band(
            "Regarde voir, c'est prêt",
            "{entreprise}{#if_website} - {website}{#endif}",
        )
        + hero(f"{IMG}/hero-audit-rapport-email.jpg", "Ton rapport d'analyse est prêt")
        + f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                J'ai passé ton site à la loupe. Pas pour faire le nareux - juste pour te dire clairement
                                ce qui freine, et ce qui se règle vite.
                            </p>
                            {{#include:dc_pastilles_scores}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;background:#c9f4f2;border-radius:12px;border:1px solid #9fd4ea;">
                                <tr>
                                    <td style="padding:16px 18px;">
                                        <p style="margin:0 0 8px;color:#0f3550;font-size:13px;font-weight:700;">Dedans, en gros</p>
                                        <p style="margin:0;color:#374151;font-size:14px;line-height:1.55;">
                                            Téléphone, vitesse, protection - et 2-3 priorités pour avancer sans te prendre la tête.
                                        </p>
                                    </td>
                                </tr>
                            </table>
{cta("Ouvrir mon rapport (30 sec)")}
                            <p style="margin:0 0 22px;text-align:center;color:#6b7280;font-size:13px;">Sans engagement - un clic, tu vois tout</p>
                            <p style="margin:0 0 22px;color:#4b5563;font-size:14px;line-height:1.6;">
                                Tu préfères en parler 15 minutes ? Réponds <strong>OK</strong> - entre midi si t'es au magasin, ça me va.
                            </p>
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_clanche",
    "Ta clanche web est un peu ouverte ({entreprise})",
    shell(
        "Ta clanche web est un peu ouverte ({entreprise})",
        "3 réglages simples - pas de panique, juste à fermer la porte.",
        header_band(
            "Ta clanche web est un peu ouverte",
            "{entreprise} - 3 priorités simples",
            "Protection",
        )
        + hero(f"{IMG}/hero-clanche-email.jpg", "La clanche web un peu ouverte")
        + f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                J'ai jeté un œil côté protection. Rien d'alarmiste - mais ouais, la porte n'est pas bien clanchée.
                                Souvent 2-3 réglages et ça change déjà le score.
                            </p>
                            {{#if_risk}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px;">
                                <tr>
                                    <td style="background:#fef3c7;border-left:4px solid #d97706;border-radius:10px;padding:16px 18px;">
                                        <p style="margin:0 0 4px;color:#b45309;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Score Pentest (risque)</p>
                                        <p style="margin:0;color:#0f3550;font-size:28px;font-weight:800;line-height:1.2;">{{risk_score}}<span style="font-size:16px;font-weight:600;color:#6b7280;"> / 100</span></p>
                                        <p style="margin:8px 0 0;color:#4b5563;font-size:13px;line-height:1.5;">Corrigeable vite - sans tout refaire.</p>
                                    </td>
                                </tr>
                            </table>
                            {{#endif}}
                            {{#if_security}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;">
                                <tr>
                                    <td style="background:#eef8f1;border-left:4px solid #2f9e6a;border-radius:10px;padding:14px 18px;">
                                        <p style="margin:0 0 4px;color:#1f6b48;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Score technique</p>
                                        <p style="margin:0;color:#0f3550;font-size:22px;font-weight:800;line-height:1.2;">{{security_score}}<span style="font-size:14px;font-weight:600;color:#6b7280;"> / 100</span></p>
                                    </td>
                                </tr>
                            </table>
                            {{#endif}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
                                <tr>
                                    <td style="padding:14px 16px;background:#dff8f8;border:1px solid #9fd4ea;border-radius:10px;">
                                        <p style="margin:0 0 4px;color:#184c70;font-size:12px;font-weight:800;">1 - Filets de protection</p>
                                        <p style="margin:0;color:#4b5563;font-size:14px;line-height:1.5;">Quelques garde-fous manquent encore côté navigateur / hébergement.</p>
                                    </td>
                                </tr>
                                <tr><td style="height:10px;"></td></tr>
                                <tr>
                                    <td style="padding:14px 16px;background:#dff8f8;border:1px solid #9fd4ea;border-radius:10px;">
                                        <p style="margin:0 0 4px;color:#184c70;font-size:12px;font-weight:800;">2 - Ce qui se voit trop</p>
                                        <p style="margin:0;color:#4b5563;font-size:14px;line-height:1.5;">Des coins du site sont un peu trop visibles depuis l'extérieur.</p>
                                    </td>
                                </tr>
                                <tr><td style="height:10px;"></td></tr>
                                <tr>
                                    <td style="padding:14px 16px;background:#dff8f8;border:1px solid #9fd4ea;border-radius:10px;">
                                        <p style="margin:0 0 4px;color:#184c70;font-size:12px;font-weight:800;">3 - Petits réglages</p>
                                        <p style="margin:0;color:#4b5563;font-size:14px;line-height:1.5;">Des ajustements simples qui réduisent le risque sans refonte.</p>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin:20px 0 18px;color:#4b5563;font-size:14px;line-height:1.6;">
                                Le détail est dans le rapport. Dis voir si tu veux qu'on en fasse le tour en 15 minutes.
                            </p>
{cta("Regarde le diagnostic")}
                            <p style="margin:0 0 24px;text-align:center;">
                                <a href="{{dc_contact_url}}" style="color:#184c70;font-weight:600;text-decoration:none;">Ou 15 minutes entre midi pour en parler</a>
                            </p>
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_scores_nareuse",
    "3 notes sur {entreprise} - une est un peu nareuse",
    shell(
        "3 notes sur {entreprise} - une est un peu nareuse",
        "Protection et vitesse - regarde voir laquelle tire vers le bas.",
        header_band(
            "3 notes - une est un peu nareuse",
            "{entreprise}",
            "Vue d'ensemble",
        )
        + hero(f"{IMG}/hero-scores-360-email.jpg", "Scores site web")
        + f"""
                    <tr>
                        <td style="padding:24px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                Voici la synthèse. Spoiler : ce n'est pas forcément la vitesse qui tire vers le bas.
                            </p>
                            {{#include:dc_pastilles_scores}}
                            {{#if_risk}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;background:#c9f4f2;border-radius:12px;border:1px solid #9fd4ea;">
                                <tr>
                                    <td style="padding:16px 18px;">
                                        <p style="margin:0 0 8px;color:#0f3550;font-size:13px;font-weight:700;">Priorité du jour</p>
                                        <p style="margin:0;color:#374151;font-size:14px;line-height:1.55;">
                                            Le pentest à <strong>{{risk_score}}</strong>/100 (risque), c'est souvent lui la note nareuse. Le rapport dit quoi corriger en premier.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            {{#endif}}
{cta("Ouvrir le compte-rendu")}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
                                <tr>
                                    <td style="text-align:center;">
                                        <a href="{{dc_contact_url}}" style="display:inline-block;background:#ffffff;color:#184c70;text-decoration:none;font-size:14px;font-weight:700;padding:12px 22px;border-radius:10px;border:2px solid #4da9d6;line-height:1.2;">15 minutes, on démêle ça</a>
                                    </td>
                                </tr>
                            </table>
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_relance",
    "Hop, je remets le lien - au cas où ça a filé ({entreprise})",
    shell(
        "Hop, je remets le lien - au cas où ça a filé",
        "Petite relance - le rapport pour {entreprise} est toujours là.",
        f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;">
                                <tr>
                                    <td>
                                        <span style="display:inline-block;width:38px;height:38px;line-height:38px;text-align:center;background:linear-gradient(140deg,#9fd4ea,#184c70);border-radius:11px;color:#ffffff;font-weight:800;font-size:13px;">DC</span>
                                        <span style="display:inline-block;margin-left:10px;color:#0f3550;font-size:17px;font-weight:700;vertical-align:middle;">DanielCraft</span>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin:0 0 6px;color:#4da9d6;font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;">Relance douce</p>
                            <h1 style="margin:0 0 16px;color:#0f3550;font-size:24px;line-height:1.3;font-weight:700;">Ça a filé sous la pile ?</h1>
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                Je t'avais envoyé l'analyse de <strong>{{entreprise}}</strong>{{#if_website}} ({{website}}){{#endif}}.
                                Pas de pression - je remets juste le lien au cas où ça a filé sous la pile.
                            </p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;background:#dff8f8;border-radius:12px;border-left:4px solid #4da9d6;">
                                <tr>
                                    <td style="padding:16px 18px;">
                                        <p style="margin:0;color:#374151;font-size:14px;line-height:1.55;">
                                            Dedans : ce qui freine, ce qui protège (ou pas), et 2-3 actions concrètes.
                                        </p>
                                    </td>
                                </tr>
                            </table>
{cta("Rouvrir mon rapport")}
                            <p style="margin:0 0 22px;text-align:center;color:#6b7280;font-size:13px;">Si ce n'est pas le bon moment, un simple « plus tard » suffit.</p>
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_franchement",
    "On en parle franchement ? (entre midi si tu veux) - {entreprise}",
    shell(
        "On en parle franchement ? (entre midi si tu veux)",
        "J'ai regardé {entreprise} de près - 2-3 trucs qui freinent, sans blabla.",
        header_band(
            "On en parle<br>franchement ?",
            "{entreprise} - entre midi si t'es au magasin",
            "Regard technique",
        )
        + hero(f"{IMG}/hero-audit-rapport-email.jpg", "Regard technique sur le site")
        + f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">
                                Moi, c'est Loïc, à Metz. Je fais des sites pour les commerces du coin.
                                J'ai regardé <strong>{{entreprise}}</strong>{{#if_website}} ({{website}}){{#endif}} - pas pour faire peur, juste pour être utile.
                            </p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                Il y a 2-3 points qui freinent. Je les ai posés dans un rapport, en français.
                            </p>
                            {{#include:dc_pastilles_scores}}
{cta("Regarde voir le rapport")}
                            <p style="margin:0 0 22px;text-align:center;color:#6b7280;font-size:13px;">Sans engagement - un seul interlocuteur</p>
                            <p style="margin:0 0 22px;color:#4b5563;font-size:14px;line-height:1.6;border-top:1px solid #e5e7eb;padding-top:18px;">
                                P.S. Dis voir ce qui bloque - on démêle ça ensemble, entre midi ou en fin de journée.
                            </p>
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_secu_clanche",
    "Sécu : ton site laisse la clanche ouverte ({entreprise})",
    shell(
        "Sécu : ton site laisse la clanche ouverte ({entreprise})",
        "Pas besoin de paniquer - il faut juste clancher la porte. 30 secondes.",
        header_band(
            "Ton site laisse la clanche ouverte",
            "{entreprise}{#if_website} ({website}){#endif} - sans panique",
            "Protection",
        )
        + hero(f"{IMG}/hero-clanche-email.jpg", "La clanche web")
        + f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                Je te le dis cash : côté protection, ton site laisse entrer trop facilement.
                                Pas besoin de paniquer - il faut juste clancher la porte.
                            </p>
                            {{#if_risk}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px;">
                                <tr>
                                    <td style="background:#fef3c7;border-left:4px solid #d97706;border-radius:10px;padding:16px 18px;">
                                        <p style="margin:0 0 4px;color:#b45309;font-size:12px;font-weight:700;text-transform:uppercase;">Score Pentest (risque)</p>
                                        <p style="margin:0;color:#0f3550;font-size:28px;font-weight:800;">{{risk_score}} <span style="font-size:16px;color:#6b7280;">/ 100</span></p>
                                    </td>
                                </tr>
                            </table>
                            {{#endif}}
                            {{#if_security}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;">
                                <tr>
                                    <td style="background:#eef8f1;border-left:4px solid #2f9e6a;border-radius:10px;padding:14px 18px;">
                                        <p style="margin:0 0 4px;color:#1f6b48;font-size:12px;font-weight:700;text-transform:uppercase;">Score technique</p>
                                        <p style="margin:0;color:#0f3550;font-size:22px;font-weight:800;">{{security_score}} <span style="font-size:14px;color:#6b7280;">/ 100</span></p>
                                    </td>
                                </tr>
                            </table>
                            {{#endif}}
                            <p style="margin:0 0 18px;color:#4b5563;font-size:14px;line-height:1.6;">
                                Le détail (en français) est dans le rapport. 30 secondes pour voir.
                            </p>
{cta("Voir comment fermer la clanche")}
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_anciennete_rincee",
    "Ton site a pris une rincée du temps ({entreprise})",
    shell(
        "Ton site a pris une rincée du temps ({entreprise})",
        "Ancienneté + téléphone + vitesse - regarde voir ce qui a vieilli.",
        header_band(
            "Ton site a pris une rincée du temps",
            "{entreprise} - sans tout casser",
        )
        + hero(f"{IMG}/hero-anciennete-email.jpg", "Le site a pris une rincée du temps")
        + f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                Ton site a l'air d'avoir pris une rincée du temps : téléphone un peu fatigué,
                                pages qui font un peu vieux, protection qui n'a pas suivi.
                            </p>
                            {{#include:dc_pastilles_scores}}
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;background:#c9f4f2;border-radius:12px;border:1px solid #9fd4ea;">
                                <tr>
                                    <td style="padding:16px 18px;">
                                        <p style="margin:0;color:#374151;font-size:14px;line-height:1.55;">
                                            Bonne nouvelle : on peut rafraîchir sans tout refaire -
                                            pas besoin de faire le nareux avec un devis monstre.
                                        </p>
                                    </td>
                                </tr>
                            </table>
{cta("Regarde voir ce qui a vieilli")}
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_voisin_google",
    "Le commerce d'à côté est plus facile à trouver ({entreprise})",
    shell(
        "Le commerce d'à côté est plus facile à trouver",
        "Sur Google et sur téléphone - regarde voir où {entreprise} perd des clients.",
        header_band(
            "Le commerce d'à côté est plus facile à trouver",
            "Pas une attaque - un constat sur Google / téléphone",
        )
        + hero(f"{IMG}/hero-scores-360-email.jpg", "Visibilité Google et téléphone")
        + f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                J'ai comparé les signaux que ton site envoie (clarté, vitesse, téléphone)
                                avec ce que les gens cherchent vraiment. Il y a des fuites.
                            </p>
                            {{#include:dc_pastilles_scores}}
                            <p style="margin:0 0 18px;color:#4b5563;font-size:14px;line-height:1.6;">
                                Pas de blabla - du concret, en français. Dis voir si tu veux le détail.
                            </p>
{cta("Regarde voir où ça fuit")}
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_ca_coince",
    "Les gens arrivent - puis ça coince ({entreprise})",
    shell(
        "Les gens arrivent - puis ça coince ({entreprise})",
        "Les gens arrivent - puis ça coince. Regarde voir les 2 freins principaux.",
        header_band(
            "Les gens arrivent - puis ça coince",
            "{entreprise} - demandes &amp; téléphone",
        )
        + f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                Souvent les gens arrivent sur le site... puis partent sans demander de devis.
                                Souvent c'est le téléphone, un bouton pas clair, ou une page trop lente.
                            </p>
                            {{#include:dc_pastilles_scores}}
                            <p style="margin:0 0 18px;color:#4b5563;font-size:14px;line-height:1.6;">
                                Regarde voir les 2 freins principaux - après, on peut en parler entre midi si tu veux.
                            </p>
{cta("Voir où ça coince")}
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)

add(
    "html_dc_30_sec",
    "30 secondes - regarde voir ce que j'ai vu ({entreprise})",
    shell(
        "30 secondes - regarde voir ce que j'ai vu",
        "Un point protection + un point téléphone. Rapport prêt.",
        header_band(
            "30 secondes.<br>Regarde voir.",
            "{entreprise}{#if_website} ({website}){#endif}",
        )
        + hero(f"{IMG}/hero-protection-email.jpg", "Ce que j'ai vu sur ton site")
        + f"""
                    <tr>
                        <td style="padding:28px 28px 8px;">
                            <p style="margin:0 0 16px;color:#1f2937;font-size:16px;line-height:1.65;">Salut <strong>{{nom}}</strong>,</p>
                            <p style="margin:0 0 18px;color:#1f2937;font-size:16px;line-height:1.65;">
                                Disons juste : un point protection + un point téléphone.
                                Le reste est dans le rapport - sans jargon.
                            </p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;background:#c9f4f2;border-radius:12px;border:1px solid #9fd4ea;">
                                <tr>
                                    <td style="padding:16px 18px;text-align:center;">
                                        <p style="margin:0;color:#0f3550;font-size:14px;font-weight:700;">
                                            1 clic · rapport prêt · sans engagement
                                        </p>
                                    </td>
                                </tr>
                            </table>
{cta("Ouvrir (30 sec)")}
                            <p style="margin:0 0 22px;color:#4b5563;font-size:14px;line-height:1.6;">
                                Entre midi si t'es au magasin, tu peux même me répondre OK.
                            </p>
                            {{#include:dc_signature_a_plus}}
                        </td>
                    </tr>""",
    ),
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for tid, (_title, html) in TEMPLATES.items():
        path = OUT / f"{tid}.html"
        path.write_text(html, encoding="utf-8")
        print(f"wrote {path.name}")
    print(f"total={len(TEMPLATES)}")


if __name__ == "__main__":
    main()
