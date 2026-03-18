"""
Script pour générer les modèles HTML d'emails et les ajouter au JSON
"""

import json
from pathlib import Path
from datetime import datetime

# Couleurs de la charte graphique (exemple)
COLOR_PRIMARY = "#E53935"
COLOR_BG = "#F8F8F8"
COLOR_WHITE = "#FFFFFF"
COLOR_TEXT_DARK = "#333333"
COLOR_TEXT_MEDIUM = "#666666"

def get_template_1_html():
    """Modèle 1 : Modernisation technique"""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Modernisation de votre site web</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Analyse rapide + 2–3 améliorations concrètes pour moderniser votre site.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 30px; background-color: {COLOR_PRIMARY}; border-radius: 8px 8px 0 0; text-align: center;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 28px; font-weight: 600;">Modernisation de votre site web</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Bonjour {{nom}},
                            </p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                {{#if_secteur}}Dans le secteur <strong>{{secteur}}</strong>, {{#endif}}j'ai analysé {{#if_website}}le site <strong>{{website}}</strong> de {{#endif}}<strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong> et j'ai identifié plusieurs opportunités d'amélioration pour moderniser votre présence digitale.
                            </p>
                            {{#if_website}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Vous pouvez consulter un aperçu détaillé de cette analyse ici :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_tech_data}}
                            <div style="background-color: {COLOR_BG}; padding: 20px; border-radius: 6px; margin: 25px 0;">
                                <h3 style="margin: 0 0 15px 0; color: {COLOR_PRIMARY}; font-size: 18px;">Observations techniques</h3>
                                <ul style="margin: 0; padding-left: 20px; color: {COLOR_TEXT_MEDIUM}; font-size: 15px; line-height: 1.8;">
                                    {{framework_info}}
                                    {{cms_info}}
                                    {{hosting_info}}
                                    {{performance_info}}
                                </ul>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                En tant que développeur web freelance spécialisé en TypeScript, React et Node.js, je peux vous accompagner pour :
                            </p>
                            <ul style="margin: 0 0 25px 0; padding-left: 20px; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.8;">
                                <li style="margin-bottom: 10px;"><strong style="color: {COLOR_PRIMARY};">Moderniser votre stack technique</strong> avec des technologies performantes et maintenables</li>
                                <li style="margin-bottom: 10px;"><strong style="color: {COLOR_PRIMARY};">Améliorer les performances</strong> (vitesse de chargement, expérience utilisateur)</li>
                                <li style="margin-bottom: 10px;"><strong style="color: {COLOR_PRIMARY};">Optimiser pour mobile</strong> avec un design responsive moderne</li>
                                <li style="margin-bottom: 10px;"><strong style="color: {COLOR_PRIMARY};">Renforcer la sécurité</strong> et la conformité aux standards</li>
                            </ul>
                            <div style="background-color: {COLOR_PRIMARY}; padding: 20px; border-radius: 6px; text-align: center; margin: 30px 0;">
                                <p style="margin: 0 0 15px 0; color: {COLOR_WHITE}; font-size: 18px; font-weight: 600;">Je propose un audit gratuit</p>
                                <p style="margin: 0; color: {COLOR_WHITE}; font-size: 14px;">Pour identifier les opportunités d'amélioration spécifiques à votre site</p>
                            </div>
                            <table role="presentation" style="width:100%; margin: 22px 0 10px 0;">
                                <tr>
                                    <td style="text-align:center;">
                                        {{#if_website}}
                                        <a href="{{analysis_url}}" style="display:inline-block;background:{COLOR_PRIMARY};color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Voir le rapport d'analyse
                                        </a>
                                        <span style="display:inline-block;width:10px;"></span>
                                        {{#endif}}
                                        <a href="{{base_url}}/contact" style="display:inline-block;background:#111827;color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Échanger 15 min
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Seriez-vous disponible pour un échange de 15 minutes cette semaine pour discuter de vos besoins ?
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="{{base_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">{{base_url}}</a>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 30px; background-color: {COLOR_BG}; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 12px;">
                                Vous recevez cet email car votre entreprise a été identifiée comme potentiellement intéressée par nos services de développement web.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

def get_template_2_html():
    """Modèle 2 : Optimisation performance"""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optimisation de performance</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Votre site peut charger plus vite et convertir davantage (audit gratuit).
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 30px; background-color: {COLOR_PRIMARY}; border-radius: 8px 8px 0 0; text-align: center;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 28px; font-weight: 600;">Optimiser les performances de votre site</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Bonjour {{nom}},
                            </p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                La performance du site de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>{{#if_website}} ({{website}}){{#endif}} a un impact direct sur l'expérience de vos visiteurs et votre positionnement dans les moteurs de recherche.
                            </p>
                            {{#if_website}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Un rapport technique détaillé est disponible en ligne :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_performance}}
                            <div style="background-color: {COLOR_BG}; padding: 20px; border-radius: 6px; margin: 25px 0; border-left: 4px solid {COLOR_PRIMARY};">
                                <h3 style="margin: 0 0 10px 0; color: {COLOR_PRIMARY}; font-size: 18px;">Score de performance actuel</h3>
                                <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 15px;">
                                    Votre site obtient un score de <strong style="color: {COLOR_TEXT_DARK};">{{performance_score}}/100</strong>. 
                                    Une optimisation pourrait améliorer significativement ce score et l'expérience utilisateur.
                                </p>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                <strong style="color: {COLOR_PRIMARY};">Les bénéfices concrets d'une optimisation :</strong>
                            </p>
                            <div style="margin: 25px 0;">
                                <div style="display: table; width: 100%; margin-bottom: 15px;">
                                    <div style="display: table-cell; width: 50px; vertical-align: top;">
                                        <div style="width: 40px; height: 40px; background-color: {COLOR_PRIMARY}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: {COLOR_WHITE}; font-size: 20px; font-weight: bold;">⚡</div>
                                    </div>
                                    <div style="display: table-cell; vertical-align: top; padding-left: 15px;">
                                        <h4 style="margin: 0 0 5px 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Vitesse de chargement améliorée</h4>
                                        <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px;">Réduction de 40 à 60% du temps de chargement</p>
                                    </div>
                                </div>
                                <div style="display: table; width: 100%; margin-bottom: 15px;">
                                    <div style="display: table-cell; width: 50px; vertical-align: top;">
                                        <div style="width: 40px; height: 40px; background-color: {COLOR_PRIMARY}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: {COLOR_WHITE}; font-size: 20px; font-weight: bold;">📱</div>
                                    </div>
                                    <div style="display: table-cell; vertical-align: top; padding-left: 15px;">
                                        <h4 style="margin: 0 0 5px 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Meilleure expérience mobile</h4>
                                        <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px;">Optimisation pour tous les appareils</p>
                                    </div>
                                </div>
                                <div style="display: table; width: 100%; margin-bottom: 15px;">
                                    <div style="display: table-cell; width: 50px; vertical-align: top;">
                                        <div style="width: 40px; height: 40px; background-color: {COLOR_PRIMARY}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: {COLOR_WHITE}; font-size: 20px; font-weight: bold;">🔍</div>
                                    </div>
                                    <div style="display: table-cell; vertical-align: top; padding-left: 15px;">
                                        <h4 style="margin: 0 0 5px 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Amélioration du référencement</h4>
                                        <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px;">Meilleur positionnement dans Google</p>
                                    </div>
                                </div>
                            </div>
                            <div style="background-color: {COLOR_PRIMARY}; padding: 20px; border-radius: 6px; text-align: center; margin: 30px 0;">
                                <p style="margin: 0 0 10px 0; color: {COLOR_WHITE}; font-size: 18px; font-weight: 600;">Audit & Optimisation - 800€</p>
                                <p style="margin: 0; color: {COLOR_WHITE}; font-size: 14px;">Audit complet + correctifs prioritaires + métriques avant/après</p>
                            </div>
                            <table role="presentation" style="width:100%; margin: 22px 0 10px 0;">
                                <tr>
                                    <td style="text-align:center;">
                                        {{#if_website}}
                                        <a href="{{analysis_url}}" style="display:inline-block;background:{COLOR_PRIMARY};color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Voir le rapport d'analyse
                                        </a>
                                        <span style="display:inline-block;width:10px;"></span>
                                        {{#endif}}
                                        <a href="{{base_url}}/contact" style="display:inline-block;background:#111827;color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Échanger 15 min
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Je propose un audit gratuit pour identifier les points d'amélioration prioritaires de votre site.
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="{{base_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">{{base_url}}</a>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 30px; background-color: {COLOR_BG}; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 12px;">
                                Vous recevez cet email car votre entreprise a été identifiée comme potentiellement intéressée par nos services de développement web.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

def get_template_3_html():
    """Modèle 3 : Sécurité et conformité (version soft)"""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sécurité et conformité</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Sécurité & conformité : 2–3 correctifs prioritaires pour réduire les risques.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 30px; background-color: {COLOR_PRIMARY}; border-radius: 8px 8px 0 0; text-align: center;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 28px; font-weight: 600;">Renforcer la sécurité de votre site</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Bonjour {{nom}},
                            </p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                La sécurité et la conformité du site de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>{{#if_website}} ({{website}}){{#endif}} sont essentielles pour protéger vos données et celles de vos clients, ainsi que pour maintenir la confiance de vos visiteurs.
                            </p>
                            {{#if_website}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Vous pouvez consulter le détail de l'analyse sécurité ici :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_security}}
                            <div style="background-color: #FFF3E0; padding: 20px; border-radius: 6px; margin: 25px 0; border-left: 4px solid {COLOR_PRIMARY};">
                                <h3 style="margin: 0 0 10px 0; color: {COLOR_PRIMARY}; font-size: 18px;">Niveau de sécurité actuel</h3>
                                <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 15px;">
                                    Votre site présente un score de sécurité de <strong style="color: {COLOR_TEXT_DARK};">{{security_score}}/100</strong>. 
                                    Des améliorations peuvent être apportées pour renforcer la protection.
                                </p>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                <strong style="color: {COLOR_PRIMARY};">Les éléments essentiels à vérifier :</strong>
                            </p>
                            <ul style="margin: 0 0 25px 0; padding-left: 20px; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.8;">
                                <li style="margin-bottom: 10px;"><strong style="color: {COLOR_PRIMARY};">Certificat SSL</strong> et configuration HTTPS</li>
                                <li style="margin-bottom: 10px;"><strong style="color: {COLOR_PRIMARY};">Headers de sécurité</strong> pour protéger contre les attaques courantes</li>
                                <li style="margin-bottom: 10px;"><strong style="color: {COLOR_PRIMARY};">Mises à jour</strong> des composants et dépendances</li>
                                <li style="margin-bottom: 10px;"><strong style="color: {COLOR_PRIMARY};">Conformité RGPD</strong> et protection des données</li>
                            </ul>
                            <div style="background-color: #E8F5E9; padding: 20px; border-radius: 6px; margin: 25px 0;">
                                <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 15px; line-height: 1.6;">
                                    <strong style="color: #2E7D32;">💡 Pourquoi c'est important :</strong><br>
                                    Un site sécurisé renforce la confiance de vos clients, améliore votre référencement, et protège votre entreprise contre les risques de perte de données ou d'interruption de service.
                                </p>
                            </div>
                            <div style="background-color: {COLOR_PRIMARY}; padding: 20px; border-radius: 6px; text-align: center; margin: 30px 0;">
                                <p style="margin: 0 0 10px 0; color: {COLOR_WHITE}; font-size: 18px; font-weight: 600;">Audit de sécurité gratuit</p>
                                <p style="margin: 0; color: {COLOR_WHITE}; font-size: 14px;">Analyse complète et recommandations personnalisées</p>
                            </div>
                            <table role="presentation" style="width:100%; margin: 22px 0 10px 0;">
                                <tr>
                                    <td style="text-align:center;">
                                        {{#if_website}}
                                        <a href="{{analysis_url}}" style="display:inline-block;background:{COLOR_PRIMARY};color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Voir le rapport d'analyse
                                        </a>
                                        <span style="display:inline-block;width:10px;"></span>
                                        {{#endif}}
                                        <a href="{{base_url}}/contact" style="display:inline-block;background:#111827;color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Échanger 15 min
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Je propose un audit de sécurité gratuit pour identifier les points d'amélioration prioritaires et vous accompagner dans la mise en conformité.
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="{{base_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">{{base_url}}</a>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 30px; background-color: {COLOR_BG}; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 12px;">
                                Vous recevez cet email car votre entreprise a été identifiée comme potentiellement intéressée par nos services de développement web.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

def get_template_4_html():
    """Modèle 4 : Présence digitale (scraping/OSINT)"""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Présence digitale</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Quelques opportunités concrètes pour gagner en visibilité et en conversions.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 30px; background-color: {COLOR_PRIMARY}; border-radius: 8px 8px 0 0; text-align: center;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 28px; font-weight: 600;">Améliorer votre présence digitale</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Bonjour {{nom}},
                            </p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                {{#if_secteur}}Dans le secteur <strong>{{secteur}}</strong>, {{#endif}}j'ai analysé la présence digitale de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>{{#if_website}} ({{website}}){{#endif}} et j'ai identifié plusieurs opportunités pour renforcer votre visibilité en ligne et améliorer votre communication digitale.
                            </p>
                            {{#if_website}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Un rapport d'analyse en ligne est disponible ici :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_scraping_data}}
                            <div style="background-color: {COLOR_BG}; padding: 20px; border-radius: 6px; margin: 25px 0;">
                                <h3 style="margin: 0 0 15px 0; color: {COLOR_PRIMARY}; font-size: 18px;">Votre présence actuelle</h3>
                                <ul style="margin: 0; padding-left: 20px; color: {COLOR_TEXT_MEDIUM}; font-size: 15px; line-height: 1.8;">
                                    {{scraping_info}}
                                </ul>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                <strong style="color: {COLOR_PRIMARY};">Comment je peux vous aider :</strong>
                            </p>
                            <div style="margin: 25px 0;">
                                <div style="display: table; width: 100%; margin-bottom: 15px;">
                                    <div style="display: table-cell; width: 50px; vertical-align: top;">
                                        <div style="width: 40px; height: 40px; background-color: {COLOR_PRIMARY}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: {COLOR_WHITE}; font-size: 20px; font-weight: bold;">🌐</div>
                                    </div>
                                    <div style="display: table-cell; vertical-align: top; padding-left: 15px;">
                                        <h4 style="margin: 0 0 5px 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Site vitrine moderne</h4>
                                        <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px;">Design professionnel, responsive et optimisé (600€)</p>
                                    </div>
                                </div>
                                <div style="display: table; width: 100%; margin-bottom: 15px;">
                                    <div style="display: table-cell; width: 50px; vertical-align: top;">
                                        <div style="width: 40px; height: 40px; background-color: {COLOR_PRIMARY}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: {COLOR_WHITE}; font-size: 20px; font-weight: bold;">⚙️</div>
                                    </div>
                                    <div style="display: table-cell; vertical-align: top; padding-left: 15px;">
                                        <h4 style="margin: 0 0 5px 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Automatisation</h4>
                                        <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px;">Scripts et intégrations pour gagner du temps (900€)</p>
                                    </div>
                                </div>
                                <div style="display: table; width: 100%; margin-bottom: 15px;">
                                    <div style="display: table-cell; width: 50px; vertical-align: top;">
                                        <div style="width: 40px; height: 40px; background-color: {COLOR_PRIMARY}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: {COLOR_WHITE}; font-size: 20px; font-weight: bold;">📊</div>
                                    </div>
                                    <div style="display: table-cell; vertical-align: top; padding-left: 15px;">
                                        <h4 style="margin: 0 0 5px 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Audit et optimisation</h4>
                                        <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px;">Analyse complète et améliorations ciblées (800€)</p>
                                    </div>
                                </div>
                            </div>
                            <div style="background-color: {COLOR_PRIMARY}; padding: 20px; border-radius: 6px; text-align: center; margin: 30px 0;">
                                <p style="margin: 0 0 10px 0; color: {COLOR_WHITE}; font-size: 18px; font-weight: 600;">Livraison rapide en 5-8 jours</p>
                                <p style="margin: 0; color: {COLOR_WHITE}; font-size: 14px;">Code source inclus + documentation + 14 jours de support</p>
                            </div>
                            <table role="presentation" style="width:100%; margin: 22px 0 10px 0;">
                                <tr>
                                    <td style="text-align:center;">
                                        {{#if_website}}
                                        <a href="{{analysis_url}}" style="display:inline-block;background:{COLOR_PRIMARY};color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Voir le rapport d'analyse
                                        </a>
                                        <span style="display:inline-block;width:10px;"></span>
                                        {{#endif}}
                                        <a href="{{base_url}}/contact" style="display:inline-block;background:#111827;color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Échanger 15 min
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Seriez-vous disponible pour un échange de 15 minutes cette semaine pour discuter de vos besoins en développement web ?
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="{{base_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">{{base_url}}</a>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 30px; background-color: {COLOR_BG}; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 12px;">
                                Vous recevez cet email car votre entreprise a été identifiée comme potentiellement intéressée par nos services de développement web.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

def get_template_5_html():
    """Modèle 5 : Audit complet (toutes données)"""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audit complet de votre présence digitale</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Audit complet : performance, sécurité, SEO, quick wins prioritaires.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding: 30px; background-color: {COLOR_PRIMARY}; border-radius: 8px 8px 0 0; text-align: center;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 28px; font-weight: 600;">Audit complet de votre présence digitale</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Bonjour {{nom}},
                            </p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                {{#if_secteur}}Dans le secteur <strong>{{secteur}}</strong>, {{#endif}}j'ai effectué une analyse complète de la présence digitale de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>{{#if_website}} ({{website}}){{#endif}} et j'ai identifié plusieurs axes d'amélioration pour optimiser votre visibilité et vos performances en ligne.
                            </p>
                            {{#if_website}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Vous pouvez consulter le rapport en ligne ici :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_all_data}}
                            <div style="background-color: {COLOR_BG}; padding: 25px; border-radius: 6px; margin: 25px 0;">
                                <h3 style="margin: 0 0 20px 0; color: {COLOR_PRIMARY}; font-size: 18px; text-align: center;">Synthèse de l'analyse</h3>
                                <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                    {{analysis_summary}}
                                </table>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                <strong style="color: {COLOR_PRIMARY};">Mes recommandations prioritaires :</strong>
                            </p>
                            <ol style="margin: 0 0 25px 0; padding-left: 20px; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.8;">
                                <li style="margin-bottom: 12px;"><strong style="color: {COLOR_PRIMARY};">Modernisation technique</strong> : Mise à jour des technologies et amélioration de l'architecture</li>
                                <li style="margin-bottom: 12px;"><strong style="color: {COLOR_PRIMARY};">Optimisation des performances</strong> : Réduction des temps de chargement et amélioration de l'expérience utilisateur</li>
                                <li style="margin-bottom: 12px;"><strong style="color: {COLOR_PRIMARY};">Renforcement de la sécurité</strong> : Mise en conformité et protection des données</li>
                                <li style="margin-bottom: 12px;"><strong style="color: {COLOR_PRIMARY};">Amélioration de la présence digitale</strong> : Optimisation du référencement et de la visibilité</li>
                            </ol>
                            <div style="background-color: {COLOR_PRIMARY}; padding: 25px; border-radius: 6px; text-align: center; margin: 30px 0;">
                                <p style="margin: 0 0 15px 0; color: {COLOR_WHITE}; font-size: 20px; font-weight: 600;">Audit & Optimisation - 800€</p>
                                <p style="margin: 0 0 10px 0; color: {COLOR_WHITE}; font-size: 14px;">✓ Audit complet de votre site</p>
                                <p style="margin: 0 0 10px 0; color: {COLOR_WHITE}; font-size: 14px;">✓ Correctifs prioritaires</p>
                                <p style="margin: 0 0 10px 0; color: {COLOR_WHITE}; font-size: 14px;">✓ Métriques avant/après</p>
                                <p style="margin: 0; color: {COLOR_WHITE}; font-size: 14px;">✓ Rapport détaillé + 14 jours de support</p>
                            </div>
                            <table role="presentation" style="width:100%; margin: 22px 0 10px 0;">
                                <tr>
                                    <td style="text-align:center;">
                                        {{#if_website}}
                                        <a href="{{analysis_url}}" style="display:inline-block;background:{COLOR_PRIMARY};color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Voir le rapport d'analyse
                                        </a>
                                        <span style="display:inline-block;width:10px;"></span>
                                        {{#endif}}
                                        <a href="{{base_url}}/contact" style="display:inline-block;background:#111827;color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Échanger 15 min
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Je propose un échange de 15 minutes pour vous présenter les résultats détaillés de cette analyse et discuter des opportunités d'amélioration spécifiques à votre entreprise.
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="{{base_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">{{base_url}}</a>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 30px; background-color: {COLOR_BG}; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 12px;">
                                Vous recevez cet email car votre entreprise a été identifiée comme potentiellement intéressée par nos services de développement web.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_template_decouverte_hero_html():
    """Découverte, UX moderne, données secteur/website (sans hero ni CTA)."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Un mot pour {{entreprise}}</title>
    <style type="text/css">
        @media only screen and (max-width: 600px) {{ .mobile-pad {{ padding: 20px 16px !important; }} }}
    </style>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        15 minutes pour identifier 2–3 améliorations concrètes sur votre site.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 32px 20px;" class="mobile-pad">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden;">
                    <tr>
                        <td style="padding: 24px 32px; background: linear-gradient(135deg, {COLOR_PRIMARY} 0%, #C62828 100%);">
                            <p style="margin: 0; color: rgba(255,255,255,0.9); font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em;">Premier contact</p>
                            <h1 style="margin: 8px 0 0; color: {COLOR_WHITE}; font-size: 22px; font-weight: 600;">Un mot pour {{entreprise}}</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 36px 32px 28px;" class="mobile-pad">
                            <h2 style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 20px; font-weight: 600;">Bonjour {{nom}},</h2>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Je m'adresse à vous au nom de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>.
                                {{#if_secteur}}Vous évoluez dans le secteur <strong>{{secteur}}</strong>. {{#endif}}
                                {{#if_website}}Votre site <strong>{{website}}</strong> {{#endif}}m'a donné envie de vous proposer un accompagnement sur mesure.
                            </p>
                            <p style="margin: 0 0 24px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                <strong style="color: {COLOR_PRIMARY};">En 15 minutes</strong>, je peux vous présenter 2–3 pistes concrètes issues de cette analyse pour moderniser votre présence en ligne et gagner en visibilité.
                            </p>
                            <table role="presentation" style="width:100%; margin: 24px 0 10px 0;">
                                <tr>
                                    <td style="text-align:center;">
                                        {{#if_website}}
                                        <a href="{{analysis_url}}" style="display:inline-block;background:{COLOR_PRIMARY};color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Voir l'analyse de votre site
                                        </a>
                                        <span style="display:inline-block;width:10px;"></span>
                                        {{#endif}}
                                        <a href="{{base_url}}/contact" style="display:inline-block;background:#111827;color:{COLOR_WHITE};text-decoration:none;font-size:15px;font-weight:600;padding:14px 18px;border-radius:10px;line-height:1;">
                                            Réserver 15 min
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 28px 0 0; color: {COLOR_TEXT_MEDIUM}; font-size: 15px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre · {{base_url}}{{#if_email}} · Répondre : {{email}}{{#endif}}
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 32px; background-color: {COLOR_BG}; border-radius: 0 0 12px 12px; text-align: center;">
                            <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 12px;">Vous recevez ce message car votre entreprise a été identifiée comme susceptible d'être intéressée par nos services.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_template_relance_html():
    """Relance courte et ergonomique."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relance - {{entreprise}}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Petite relance, même valeur : audit rapide + 2–3 améliorations concrètes.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 560px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 12px; box-shadow: 0 2px 16px rgba(0,0,0,0.06);">
                    <tr>
                        <td style="padding: 32px 36px;">
                            <p style="margin: 0 0 8px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 13px;">Relance amicale</p>
                            <h1 style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 22px; font-weight: 600;">Bonjour {{nom}},</h1>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Je me permets de revenir vers vous concernant ma proposition pour <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>.
                            </p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Si le moment n'est pas le bon, pas de souci. Sinon, je peux toujours vous partager un court retour d'analyse et 2–3 actions prioritaires sur votre site.
                            </p>
                            <table role="presentation" style="margin: 0 0 18px 0;">
                                <tr>
                                    <td style="background-color: {COLOR_PRIMARY}; border-radius: 8px; padding: 12px 22px; text-align: center;">
                                        <a href="{{base_url}}/contact" style="color: {COLOR_WHITE}; font-size: 15px; font-weight: 600; text-decoration: none;">Proposer un créneau</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Bien à vous,<br><strong style="color: {COLOR_PRIMARY};">Votre nom</strong>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_template_secteur_html():
    """Personnalisé par secteur, avec données techniques si disponibles."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Proposition pour le secteur {{secteur}} - {{entreprise}}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Audit ciblé sur votre secteur pour améliorer performance, sécurité et visibilité.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
                    <tr>
                        <td style="padding: 28px 32px; background: linear-gradient(135deg, {COLOR_PRIMARY}, #C62828); border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 22px; font-weight: 600;">Proposition adaptée à votre secteur</h1>
                            <p style="margin: 8px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{{#if_secteur}}{{secteur}} · {{#endif}}{{entreprise}}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 36px 32px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Bonjour {{nom}},
                            </p>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                {{#if_secteur}}Les entreprises du secteur <strong style="color: {COLOR_PRIMARY};">{{secteur}}</strong> comme {{#endif}}<strong>{{entreprise}}</strong> ont souvent les mêmes enjeux : visibilité, performance du site, et mise en conformité.
                            </p>
                            {{#if_tech_data}}
                            <div style="background-color: {COLOR_BG}; padding: 20px; border-radius: 8px; margin: 24px 0; border-left: 4px solid {COLOR_PRIMARY};">
                                <p style="margin: 0 0 8px 0; color: {COLOR_PRIMARY}; font-size: 14px; font-weight: 600;">Votre stack actuelle</p>
                                <p style="margin: 0; color: {COLOR_TEXT_MEDIUM}; font-size: 15px;">Framework / CMS : {{framework}} {{cms}} · Hébergement : {{hosting_provider}}</p>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Je vous propose un audit gratuit ciblé sur votre secteur pour identifier les leviers les plus impactants (2–3 priorités concrètes à court terme).
                            </p>
                            <table role="presentation" style="margin: 24px 0;">
                                <tr>
                                    <td style="background-color: {COLOR_PRIMARY}; border-radius: 8px; padding: 14px 24px; text-align: center;">
                                        <a href="{{base_url}}/audit" style="color: {COLOR_WHITE}; font-size: 15px; font-weight: 600; text-decoration: none;">Demander l'audit gratuit</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 24px 0 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Cordialement,<br><strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>Votre titre
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_template_post_demo_html():
    """Remerciement après démo / suivi."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Suite à notre échange - {{entreprise}}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Récapitulatif synthétique + prochaines étapes concrètes pour votre projet.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 560px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 12px; box-shadow: 0 2px 16px rgba(0,0,0,0.06);">
                    <tr>
                        <td style="padding: 32px 36px;">
                            <p style="margin: 0 0 8px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 13px;">Suite à notre échange</p>
                            <h1 style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 22px; font-weight: 600;">Bonjour {{nom}},</h1>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Merci d'avoir pris le temps d'échanger avec moi concernant <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>.
                            </p>
                            <p style="margin: 0 0 24px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Comme convenu, je vous envoie un récapitulatif des points abordés et des prochaines étapes possibles. N'hésitez pas à me recontacter pour toute question.
                            </p>
                            <table role="presentation" style="margin: 24px 0;">
                                <tr>
                                    <td style="background-color: {COLOR_PRIMARY}; border-radius: 8px; padding: 14px 24px; text-align: center;">
                                        <a href="{{base_url}}/contact" style="color: {COLOR_WHITE}; font-size: 15px; font-weight: 600; text-decoration: none;">Voir / confirmer le récapitulatif</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 24px 0 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Bien cordialement,<br><strong style="color: {COLOR_PRIMARY};">Votre nom</strong>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_template_relance2_html():
    """Deuxième relance, dernière chance."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dernière relance - {{entreprise}}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Dernière relance, sans pression, pour décider si on avance ou non.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 560px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 12px; box-shadow: 0 2px 16px rgba(0,0,0,0.06);">
                    <tr>
                        <td style="padding: 32px 36px;">
                            <p style="margin: 0 0 8px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 13px;">Dernière relance</p>
                            <h1 style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 22px; font-weight: 600;">Bonjour {{nom}},</h1>
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Je me permets de revenir une dernière fois vers vous pour ma proposition destinée à <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>.
                            </p>
                            <p style="margin: 0 0 24px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Si vous souhaitez en discuter, je reste disponible. Sinon, je ne vous solliciterai plus et vous remercie pour votre attention.
                            </p>
                            <table role="presentation" style="margin: 24px 0;">
                                <tr>
                                    <td style="background-color: {COLOR_PRIMARY}; border-radius: 8px; padding: 14px 24px; text-align: center;">
                                        <a href="{{base_url}}/contact" style="color: {COLOR_WHITE}; font-size: 15px; font-weight: 600; text-decoration: none;">Répondre à ce message</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 24px 0 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Cordialement,<br><strong style="color: {COLOR_PRIMARY};">Votre nom</strong>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_template_technique_avance_html():
    """Technique avancé : framework, cms, performance, sécurité (données complètes)."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analyse technique - {{entreprise}}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
                    <tr>
                        <td style="padding: 28px 32px; background: linear-gradient(135deg, {COLOR_PRIMARY}, #C62828); border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 22px; font-weight: 600;">Analyse technique de votre site</h1>
                            <p style="margin: 8px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{{entreprise}} {{#if_website}}· {{website}} {{#endif}}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 36px 32px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">Bonjour {{nom}},</p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                J'ai réalisé une analyse technique de la présence en ligne de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>. Voici une synthèse.
                            </p>
                            {{#if_website}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Le rapport complet est également accessible en ligne :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_all_data}}
                            <div style="background-color: {COLOR_BG}; padding: 24px; border-radius: 8px; margin: 24px 0; border-left: 4px solid {COLOR_PRIMARY};">
                                <h3 style="margin: 0 0 16px 0; color: {COLOR_PRIMARY}; font-size: 18px;">Résultats de l'analyse</h3>
                                <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                    {{analysis_summary}}
                                </table>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 24px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Je peux vous détailler ces points et proposer un plan d'action personnalisé lors d'un court échange.
                            </p>
                            <table role="presentation" style="margin: 24px 0;">
                                <tr>
                                    <td style="background-color: {COLOR_PRIMARY}; border-radius: 8px; padding: 14px 24px; text-align: center;">
                                        <a href="{{base_url}}/audit" style="color: {COLOR_WHITE}; font-size: 15px; font-weight: 600; text-decoration: none;">Obtenir le rapport détaillé</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 24px 0 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Cordialement,<br><strong style="color: {COLOR_PRIMARY};">Votre nom</strong></p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_template_securite_html():
    """Focus sécurité : score, vulnérabilités (si données pentest)."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sécurité de votre site - {{entreprise}}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
                    <tr>
                        <td style="padding: 28px 32px; background: linear-gradient(135deg, #2E7D32, #1B5E20); border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 22px; font-weight: 600;">Sécurité et conformité</h1>
                            <p style="margin: 8px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{{entreprise}}{{#if_website}} · {{website}}{{#endif}}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 36px 32px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">Bonjour {{nom}},</p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                La sécurité du site de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>{{#if_website}} ({{website}}){{#endif}} est un enjeu majeur pour protéger vos données et celles de vos clients.
                            </p>
                            {{#if_website}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Détail de l'analyse sécurité disponible ici :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_security}}
                            <div style="background-color: #FFF3E0; padding: 20px; border-radius: 8px; margin: 24px 0; border-left: 4px solid #E65100;">
                                <p style="margin: 0 0 8px 0; color: #E65100; font-size: 14px; font-weight: 600;">Score de sécurité actuel</p>
                                <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 15px;">Votre site obtient un score de <strong>{{security_score}}/100</strong>. Des améliorations sont possibles.</p>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 24px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Je propose un audit de sécurité gratuit : analyse des headers, SSL, bonnes pratiques et recommandations personnalisées.
                            </p>
                            <table role="presentation" style="margin: 24px 0;">
                                <tr>
                                    <td style="background-color: #2E7D32; border-radius: 8px; padding: 14px 24px; text-align: center;">
                                        <a href="{{base_url}}/security-audit" style="color: {COLOR_WHITE}; font-size: 15px; font-weight: 600; text-decoration: none;">Demander l'audit sécurité</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 24px 0 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Cordialement,<br><strong style="color: #2E7D32;">Votre nom</strong></p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_template_contacts_html():
    """Découverte basée sur les contacts / scraping (total_emails, total_people)."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Votre présence en ligne - {{entreprise}}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {COLOR_BG};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
        Vue synthétique de votre présence en ligne + 2–3 actions prioritaires.
    </div>
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: {COLOR_BG};">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {COLOR_WHITE}; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
                    <tr>
                        <td style="padding: 28px 32px; background: linear-gradient(135deg, {COLOR_PRIMARY}, #C62828); border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: {COLOR_WHITE}; font-size: 22px; font-weight: 600;">Votre présence digitale</h1>
                            <p style="margin: 8px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{{entreprise}}{{#if_website}} · {{website}}{{#endif}}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 36px 32px;">
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">Bonjour {{nom}},</p>
                            <p style="margin: 0 0 16px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                {{#if_secteur}}Dans le secteur <strong>{{secteur}}</strong>, {{#endif}}j'ai analysé la présence en ligne de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong>{{#if_website}} ({{website}}){{#endif}}.
                            </p>
                            {{#if_website}}
                            <p style="margin: 0 0 18px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Un rapport détaillé de cette analyse est disponible ici :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_website}}
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_MEDIUM}; font-size: 14px; line-height: 1.6;">
                                Un rapport d'analyse de votre site est disponible ici :
                                <a href="{{analysis_url}}" style="color: {COLOR_PRIMARY}; text-decoration: none;">voir l'analyse de votre site</a>.
                            </p>
                            {{#endif}}
                            {{#if_scraping_data}}
                            <div style="background-color: {COLOR_BG}; padding: 20px; border-radius: 8px; margin: 24px 0;">
                                <h3 style="margin: 0 0 12px 0; color: {COLOR_PRIMARY}; font-size: 18px;">Ce que j'ai observé</h3>
                                <ul style="margin: 0; padding-left: 20px; color: {COLOR_TEXT_MEDIUM}; font-size: 15px; line-height: 1.8;">
                                    {{scraping_info}}
                                </ul>
                            </div>
                            {{#endif}}
                            <p style="margin: 0 0 24px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.65;">
                                Je peux vous aider à structurer votre communication digitale et à mieux toucher vos cibles. Souhaitez-vous en parler 15 minutes ?
                            </p>
                            <table role="presentation" style="margin: 24px 0;">
                                <tr>
                                    <td style="background-color: {COLOR_PRIMARY}; border-radius: 8px; padding: 14px 24px; text-align: center;">
                                        <a href="{{base_url}}/contact" style="color: {COLOR_WHITE}; font-size: 15px; font-weight: 600; text-decoration: none;">Échanger 15 min</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 24px 0 0; color: {COLOR_TEXT_DARK}; font-size: 16px;">Cordialement,<br><strong style="color: {COLOR_PRIMARY};">Votre nom</strong></p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def get_cold_email_templates():
    """Retourne les 2 modèles texte (cold email) pour le fichier par défaut."""
    from datetime import datetime
    now = datetime.now().isoformat()
    return [
        {
            'id': 'cold_email_1',
            'name': 'Cold Email - Entreprise Locale',
            'category': 'cold_email',
            'subject': 'Développeur web freelance - Partenariat pour vos startups',
            'content': """Bonjour,

Je suis {Votre nom}, développeur web freelance, spécialisé en TypeScript, React et Node.js.

Je vois que {entreprise} accompagne de nombreuses startups et entreprises innovantes. Beaucoup d'entre elles ont besoin de sites web modernes, d'applications web ou d'optimisation de leurs outils numériques.

Je propose mes services aux entreprises que vous accompagnez :
- Sites vitrines modernes et performants (600€)
- Applications web sur mesure
- Audit et optimisation de sites existants (800€)
- Automatisation de processus (900€)

Pourriez-vous me mettre en relation avec des entreprises qui auraient des besoins en développement web ? Je peux également intervenir lors d'événements ou proposer des ateliers techniques.

Disponible pour un échange de 15 minutes cette semaine pour discuter d'un éventuel partenariat ?

Cordialement,
{Votre nom}
{Votre titre}
{votre-site.example.com}""",
            'created_at': now,
            'updated_at': now
        },
        {
            'id': 'cold_email_2',
            'name': 'Cold Email - PME avec site obsolète',
            'category': 'cold_email',
            'subject': 'Modernisation de votre site web - {entreprise}',
            'content': """Bonjour {nom},

J'ai remarqué que le site web de {entreprise} pourrait bénéficier d'une modernisation pour améliorer l'expérience utilisateur et les performances.

En tant que développeur web freelance spécialisé en TypeScript, React et Node.js, j'ai aidé plusieurs entreprises similaires à moderniser leur présence en ligne, avec des résultats concrets :
- Amélioration de la vitesse de chargement (réduction de 40-60%)
- Meilleure expérience utilisateur mobile
- Optimisation SEO pour plus de visibilité

Je propose un audit gratuit de votre site actuel pour identifier les opportunités d'amélioration.

Seriez-vous disponible pour un échange de 15 minutes cette semaine ?

Cordialement,
{Votre nom}
{Votre titre}
{votre-site.example.com}""",
            'created_at': now,
            'updated_at': now
        }
    ]


if __name__ == "__main__":
    import sys
    root = Path(__file__).parent.parent
    templates_file = root / 'templates_data.json'
    default_file = root / 'templates_data.default.json'
    now = datetime.now().isoformat()

    def _html(id_, name, subject, content):
        return {'id': id_, 'name': name, 'category': 'html_email', 'subject': subject, 'content': content, 'is_html': True, 'created_at': now, 'updated_at': now}

    # Option --write-default : genere templates_data.default.json (HTML uniquement, pas de cold email)
    if '--write-default' in sys.argv or '-w' in sys.argv:
        default_templates = [
            _html('html_modernisation_technique', 'HTML - Modernisation technique', 'Modernisation de votre site web - {entreprise}', get_template_1_html()),
            _html('html_optimisation_performance', 'HTML - Optimisation performance', 'Optimiser les performances de votre site - {entreprise}', get_template_2_html()),
            _html('html_securite_conformite', 'HTML - Sécurité et conformité', 'Renforcer la sécurité de votre site - {entreprise}', get_template_3_html()),
            _html('html_presence_digitale', 'HTML - Présence digitale', 'Améliorer votre présence digitale - {entreprise}', get_template_4_html()),
            _html('html_audit_complet', 'HTML - Audit complet', 'Audit complet de votre présence digitale - {entreprise}', get_template_5_html()),
            _html('html_decouverte_hero', 'HTML - Découverte', 'Un mot pour {entreprise}', get_template_decouverte_hero_html()),
            _html('html_relance', 'HTML - Relance courte', 'Relance - {entreprise}', get_template_relance_html()),
            _html('html_relance2', 'HTML - Relance 2', 'Dernière relance - {entreprise}', get_template_relance2_html()),
            _html('html_secteur', 'HTML - Par secteur', 'Proposition pour votre secteur - {entreprise}', get_template_secteur_html()),
            _html('html_post_demo', 'HTML - Post-démo', 'Suite à notre échange - {entreprise}', get_template_post_demo_html()),
            _html('html_technique_avance', 'HTML - Technique avancé', 'Analyse technique - {entreprise}', get_template_technique_avance_html()),
            _html('html_securite', 'HTML - Sécurité', 'Sécurité de votre site - {entreprise}', get_template_securite_html()),
            _html('html_contacts', 'HTML - Contacts / présence', 'Votre présence en ligne - {entreprise}', get_template_contacts_html()),
        ]
        with open(default_file, 'w', encoding='utf-8') as f:
            json.dump({'templates': default_templates}, f, ensure_ascii=False, indent=2)
        print("OK: " + str(default_file) + " ecrit avec " + str(len(default_templates)) + " modeles HTML.")
        sys.exit(0)

    # Option --restore : recopie le fichier par defaut (HTML uniquement) sur templates_data.json
    if '--restore' in sys.argv or '-r' in sys.argv:
        if not default_file.exists():
            print("Erreur: templates_data.default.json introuvable. Lancez d'abord: python scripts/generate_html_templates.py --write-default")
            sys.exit(1)
        import shutil
        shutil.copy(default_file, templates_file)
        with open(default_file, 'r', encoding='utf-8') as f:
            n = len(json.load(f).get('templates', []))
        print("Restauration OK: templates_data.json recree avec " + str(n) + " modeles HTML.")
        sys.exit(0)

    # Charger les templates existants
    if templates_file.exists():
        with open(templates_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {'templates': []}
    
    # Ajouter les nouveaux templates HTML (ids a ajouter si absents)
    new_templates = [
        _html('html_modernisation_technique', 'HTML - Modernisation technique', 'Modernisation de votre site web - {entreprise}', get_template_1_html()),
        _html('html_optimisation_performance', 'HTML - Optimisation performance', 'Optimiser les performances de votre site - {entreprise}', get_template_2_html()),
        _html('html_securite_conformite', 'HTML - Sécurité et conformité', 'Renforcer la sécurité de votre site - {entreprise}', get_template_3_html()),
        _html('html_presence_digitale', 'HTML - Présence digitale', 'Améliorer votre présence digitale - {entreprise}', get_template_4_html()),
        _html('html_audit_complet', 'HTML - Audit complet', 'Audit complet de votre présence digitale - {entreprise}', get_template_5_html()),
        _html('html_decouverte_hero', 'HTML - Découverte', 'Un mot pour {entreprise}', get_template_decouverte_hero_html()),
        _html('html_relance', 'HTML - Relance courte', 'Relance - {entreprise}', get_template_relance_html()),
        _html('html_relance2', 'HTML - Relance 2', 'Dernière relance - {entreprise}', get_template_relance2_html()),
        _html('html_secteur', 'HTML - Par secteur', 'Proposition pour votre secteur - {entreprise}', get_template_secteur_html()),
        _html('html_post_demo', 'HTML - Post-démo', 'Suite à notre échange - {entreprise}', get_template_post_demo_html()),
        _html('html_technique_avance', 'HTML - Technique avancé', 'Analyse technique - {entreprise}', get_template_technique_avance_html()),
        _html('html_securite', 'HTML - Sécurité', 'Sécurité de votre site - {entreprise}', get_template_securite_html()),
        _html('html_contacts', 'HTML - Contacts / présence', 'Votre présence en ligne - {entreprise}', get_template_contacts_html()),
    ]
    
    existing_ids = {t.get('id') for t in data.get('templates', [])}
    added = 0
    for template in new_templates:
        if template['id'] not in existing_ids:
            data['templates'].append(template)
            added += 1
            print("Ajoute : " + template['name'])
        else:
            print("Deja present : " + template['name'])
    
    with open(templates_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("\n" + str(len(new_templates)) + " modeles HTML (ajoutes: " + str(added) + ") dans " + str(templates_file))

