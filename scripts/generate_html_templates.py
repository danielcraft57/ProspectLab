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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                J'ai analysé le site web de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong> et j'ai identifié plusieurs opportunités d'amélioration pour moderniser votre présence digitale.
                            </p>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Seriez-vous disponible pour un échange de 15 minutes cette semaine pour discuter de vos besoins ?
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="https://example.com" style="color: {COLOR_PRIMARY}; text-decoration: none;">example.com</a>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                La performance de votre site web <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong> a un impact direct sur l'expérience de vos visiteurs et votre positionnement dans les moteurs de recherche.
                            </p>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Je propose un audit gratuit pour identifier les points d'amélioration prioritaires de votre site.
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="https://example.com" style="color: {COLOR_PRIMARY}; text-decoration: none;">example.com</a>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                La sécurité et la conformité de votre site web <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong> sont essentielles pour protéger vos données et celles de vos clients, ainsi que pour maintenir la confiance de vos visiteurs.
                            </p>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Je propose un audit de sécurité gratuit pour identifier les points d'amélioration prioritaires et vous accompagner dans la mise en conformité.
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="https://example.com" style="color: {COLOR_PRIMARY}; text-decoration: none;">example.com</a>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                J'ai analysé la présence digitale de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong> et j'ai identifié plusieurs opportunités pour renforcer votre visibilité en ligne et améliorer votre communication digitale.
                            </p>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Seriez-vous disponible pour un échange de 15 minutes cette semaine pour discuter de vos besoins en développement web ?
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="https://example.com" style="color: {COLOR_PRIMARY}; text-decoration: none;">example.com</a>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                J'ai effectué une analyse complète de la présence digitale de <strong style="color: {COLOR_PRIMARY};">{{entreprise}}</strong> et j'ai identifié plusieurs axes d'amélioration pour optimiser votre visibilité et vos performances en ligne.
                            </p>
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
                            <p style="margin: 0 0 20px 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Je propose un échange de 15 minutes pour vous présenter les résultats détaillés de cette analyse et discuter des opportunités d'amélioration spécifiques à votre entreprise.
                            </p>
                            <p style="margin: 0; color: {COLOR_TEXT_DARK}; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: {COLOR_PRIMARY};">Votre nom</strong><br>
                                Votre titre<br>
                                <a href="https://example.com" style="color: {COLOR_PRIMARY}; text-decoration: none;">example.com</a>
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

if __name__ == "__main__":
    import sys
    root = Path(__file__).parent.parent
    templates_file = root / 'templates_data.json'
    default_file = root / 'templates_data.default.json'

    # Option --restore : recopie le fichier par defaut (tous les modeles) sur templates_data.json
    if '--restore' in sys.argv or '-r' in sys.argv:
        if not default_file.exists():
            print("Erreur: templates_data.default.json introuvable.")
            sys.exit(1)
        import shutil
        shutil.copy(default_file, templates_file)
        print("Restauration OK: templates_data.json recree avec tous les modeles (2 Cold Email + 5 HTML).")
        sys.exit(0)

    # Charger les templates existants
    if templates_file.exists():
        with open(templates_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {'templates': []}
    
    # Ajouter les nouveaux templates HTML
    new_templates = [
        {
            'id': 'html_modernisation_technique',
            'name': 'HTML - Modernisation technique',
            'category': 'html_email',
            'subject': 'Modernisation de votre site web - {entreprise}',
            'content': get_template_1_html(),
            'is_html': True,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        },
        {
            'id': 'html_optimisation_performance',
            'name': 'HTML - Optimisation performance',
            'category': 'html_email',
            'subject': 'Optimiser les performances de votre site - {entreprise}',
            'content': get_template_2_html(),
            'is_html': True,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        },
        {
            'id': 'html_securite_conformite',
            'name': 'HTML - Sécurité et conformité',
            'category': 'html_email',
            'subject': 'Renforcer la sécurité de votre site - {entreprise}',
            'content': get_template_3_html(),
            'is_html': True,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        },
        {
            'id': 'html_presence_digitale',
            'name': 'HTML - Présence digitale',
            'category': 'html_email',
            'subject': 'Améliorer votre présence digitale - {entreprise}',
            'content': get_template_4_html(),
            'is_html': True,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        },
        {
            'id': 'html_audit_complet',
            'name': 'HTML - Audit complet',
            'category': 'html_email',
            'subject': 'Audit complet de votre présence digitale - {entreprise}',
            'content': get_template_5_html(),
            'is_html': True,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
    ]
    
    # Vérifier si les templates existent déjà
    existing_ids = {t.get('id') for t in data.get('templates', [])}
    added = 0
    for template in new_templates:
        if template['id'] not in existing_ids:
            data['templates'].append(template)
            added += 1
            print("Ajoute : " + template['name'])
        else:
            print("Deja present : " + template['name'])
    
    # Sauvegarder
    with open(templates_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("\n" + str(len(new_templates)) + " modeles HTML (ajoutes: " + str(added) + ") dans " + str(templates_file))

