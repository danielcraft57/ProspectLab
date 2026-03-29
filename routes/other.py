"""
Blueprint pour les routes supplémentaires non encore migrées

Contient les routes pour les emails, templates, scraping et téléchargements.
"""

from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
import os
from services.email_sender import EmailSender
from config import MAIL_DEFAULT_RECIPIENT
from services.template_manager import TemplateManager
from config import EXPORT_FOLDER
from utils.template_helpers import render_page
from services.auth import login_required, admin_required

other_bp = Blueprint('other', __name__)

# Initialiser les services
template_manager = TemplateManager()


@other_bp.route('/analyse/scraping')
@login_required
def analyse_scraping_page():
    """
    Page d'analyse/scraping unifiée
    
    Returns:
        str: Template HTML de la page d'analyse/scraping
    """
    return render_page('analyse_scraping.html')


@other_bp.route('/scrape-emails', methods=['GET', 'POST'])
@login_required
def scrape_emails():
    """
    Scrape les emails d'un site web (route HTTP pour compatibilité)
    
    Methods:
        GET: Affiche le formulaire de scraping
        POST: Retourne un message indiquant d'utiliser WebSocket
        
    Returns:
        str ou JSON: Template HTML ou message JSON
    """
    if request.method == 'POST':
        return jsonify({
            'message': 'Utilisez WebSocket pour les mises à jour en temps réel',
            'use_websocket': True
        }), 200
    
    return render_page('scrape_emails.html')


@other_bp.route('/send-emails', methods=['GET', 'POST'])
@login_required
def send_emails():
    """
    Envoi d'emails de prospection
    
    Methods:
        GET: Affiche le formulaire d'envoi
        POST: Envoie les emails
        
    Returns:
        str ou JSON: Template HTML ou résultats JSON
    """
    if request.method == 'POST':
        data = request.get_json()
        
        # Récupérer les données
        recipients = data.get('recipients', [])  # Liste de {email, nom, entreprise}
        template_id = data.get('template_id')
        subject = data.get('subject')
        custom_message = data.get('custom_message')
        
        if not recipients:
            return jsonify({'error': 'Aucun destinataire'}), 400
        
        try:
            email_sender = EmailSender()
            
            # Charger le template si fourni
            template = None
            if template_id:
                template = template_manager.get_template(template_id)
                if not template:
                    return jsonify({'error': 'Template introuvable'}), 404
            
            results = []
            for recipient in recipients:
                # Personnaliser le message
                html_body = None
                if template_id and template:
                    message, is_html = template_manager.render_template(
                        template_id,
                        recipient.get('nom', ''),
                        recipient.get('entreprise', ''),
                        recipient.get('email', ''),
                        recipient.get('entreprise_id')  # Passer l'ID si disponible
                    )
                    if is_html:
                        html_body = message
                        # Pour HTML, créer une version texte simplifiée
                        import re
                        message = re.sub(r'<[^>]+>', '', message)  # Enlever les balises HTML
                        message = re.sub(r'\s+', ' ', message).strip()  # Nettoyer les espaces
                elif custom_message:
                    message = custom_message
                else:
                    return jsonify({'error': 'Template ou message requis'}), 400
                
                # Personnaliser le sujet
                subject_template = subject or (template.get('subject', 'Prospection') if template else 'Prospection')
                try:
                    personalized_subject = subject_template.format(
                        nom=recipient.get('nom', ''),
                        entreprise=recipient.get('entreprise', '')
                    )
                except:
                    personalized_subject = subject_template
                
                # Envoyer l'email
                result = email_sender.send_email(
                    to=recipient['email'],
                    subject=personalized_subject,
                    body=message,
                    recipient_name=recipient.get('nom', ''),
                    html_body=html_body
                )
                
                results.append({
                    'email': recipient['email'],
                    'success': result['success'],
                    'message': result.get('message', '')
                })
            
            return jsonify({
                'success': True,
                'results': results,
                'total_sent': sum(1 for r in results if r['success']),
                'total_failed': sum(1 for r in results if not r['success'])
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET: Afficher le formulaire
    templates = template_manager.list_templates()
    return render_page('send_emails.html', templates=templates)


@other_bp.route('/templates', methods=['GET', 'POST'])
@login_required
def manage_templates():
    """
    Gestion des modèles de messages
    
    Methods:
        GET: Affiche la liste des templates
        POST: Crée, modifie ou supprime un template
        
    Returns:
        str ou JSON: Template HTML ou résultats JSON
    """
    if request.method == 'POST':
        data = request.get_json()
        action = data.get('action')
        
        if action == 'create':
            template = template_manager.create_template(
                name=data.get('name'),
                subject=data.get('subject'),
                content=data.get('content'),
                category=data.get('category', 'cold_email')
            )
            return jsonify({'success': True, 'template': template})
        
        elif action == 'update':
            template = template_manager.update_template(
                template_id=data.get('template_id'),
                name=data.get('name'),
                subject=data.get('subject'),
                content=data.get('content'),
                category=data.get('category')
            )
            return jsonify({'success': True, 'template': template})
        
        elif action == 'delete':
            template_manager.delete_template(data.get('template_id'))
            return jsonify({'success': True})
    
    # GET: Liste des templates
    templates = template_manager.list_templates()
    return render_page('templates.html', templates=templates)


@other_bp.route('/emails/templates', methods=['GET'])
@login_required
def manage_templates_db_page():
    """
    Nouvelle page de gestion des modèles (stockage BDD).
    UI moderne + CRUD via API /api/templates.
    """
    return render_page('email_templates_manager.html')


@other_bp.route('/download/<filename>')
@login_required
def download_file(filename):
    """
    Télécharger un fichier exporté
    
    Args:
        filename (str): Nom du fichier à télécharger
        
    Returns:
        Response: Fichier en téléchargement ou redirection avec message d'erreur
    """
    from flask import render_template
    
    filepath = os.path.join(EXPORT_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        # Fichier introuvable - afficher une page d'erreur avec message clair
        flash('Le fichier exporté n\'existe plus. Il a peut-être été supprimé automatiquement après 6 heures.', 'error')
        return render_template('error.html', 
                             error_title='Fichier introuvable',
                             error_message=f'Le fichier "{filename}" n\'a pas été trouvé dans les exports.',
                             error_details='Les fichiers exportés sont automatiquement supprimés après 6 heures pour libérer de l\'espace. Veuillez relancer l\'analyse pour générer un nouvel export.',
                             back_url=url_for('main.index'))


@other_bp.route('/api/templates', methods=['GET', 'POST'])
@login_required
def api_templates():
    """
    API: Liste des templates
    
    Returns:
        JSON: Liste des templates
    """
    if request.method == 'GET':
        templates = template_manager.list_templates()
        return jsonify(templates)

    # POST: créer un template (REST)
    data = request.get_json() or {}
    explicit_id = (data.get('id') or '').strip()
    name = (data.get('name') or '').strip()
    category = (data.get('category') or 'cold_email').strip()
    subject = (data.get('subject') or '').strip()
    content = data.get('content') or ''

    if not name or not content:
        return jsonify({'error': 'Champs requis: name, content'}), 400

    tpl = template_manager.create_template(
        name=name,
        subject=subject,
        content=content,
        category=category,
        template_id=explicit_id or None
    )
    return jsonify({'success': True, 'template': tpl}), 201


@other_bp.route('/api/templates/<template_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_template_detail(template_id):
    """
    API: Détails d'un template
    
    Args:
        template_id (str): ID du template
        
    Returns:
        JSON: Détails du template ou erreur 404
    """
    if request.method == 'GET':
        template = template_manager.get_template(template_id)
        if template:
            return jsonify(template)
        return jsonify({'error': 'Template introuvable'}), 404

    if request.method == 'DELETE':
        ok = template_manager.delete_template(template_id)
        if ok:
            return jsonify({'success': True})
        return jsonify({'error': 'Template introuvable'}), 404

    # PUT: update
    data = request.get_json() or {}
    tpl = template_manager.update_template(
        template_id=template_id,
        name=data.get('name'),
        subject=data.get('subject'),
        content=data.get('content'),
        category=data.get('category')
    )
    if tpl:
        return jsonify({'success': True, 'template': tpl})
    return jsonify({'error': 'Template introuvable'}), 404


@other_bp.route('/api/entreprise/<int:entreprise_id>/template-suggestions', methods=['GET'])
@login_required
def api_entreprise_template_suggestions(entreprise_id):
    """
    API: Suggestions de templates pour une entreprise donnée.
    
    Retourne une liste de templates recommandés avec une raison et un score.
    """
    try:
        max_results = request.args.get('limit', type=int) or 3
        suggestions = template_manager.suggest_templates_for_entreprise(entreprise_id, max_results=max_results)
        return jsonify(suggestions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@other_bp.route('/api/entreprise/<int:entreprise_id>/generate-contact-email', methods=['GET'])
@login_required
def api_generate_contact_email(entreprise_id):
    """
    API: Génère un brouillon d'email de prise de contact basé sur l'audit.

    Returns:
        JSON: {subject, body}
    """
    try:
        draft = template_manager.generate_contact_email_draft(entreprise_id)
        return jsonify(draft)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ROUTES POUR LES CAMPAGNES EMAIL ====================

@other_bp.route('/campagnes', methods=['GET'])
@login_required
def list_campagnes():
    """
    Liste toutes les campagnes email.
    Utilise le template 3 étapes situé dans templates/pages/campagnes.html.
    """
    from services.database.campagnes import CampagneManager
    from flask import make_response
    from utils.template_helpers import render_page

    campagne_manager = CampagneManager()
    campagnes = campagne_manager.list_campagnes(limit=100)

    # On cible explicitement pages/campagnes.html pour coller à la structure de déploiement
    resp = make_response(render_page('pages/campagnes.html', campagnes=campagnes))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@other_bp.route('/api/campagnes', methods=['GET'])
@login_required
def api_list_campagnes():
    """
    API: Liste des campagnes.
    date_creation est renvoyé tel quel (serveur déjà en Europe/Paris).
    """
    from services.database.campagnes import CampagneManager
    campagne_manager = CampagneManager()
    statut = request.args.get('statut')
    campagnes = campagne_manager.list_campagnes(statut=statut, limit=100)
    return jsonify(campagnes)


@other_bp.route('/api/campagnes', methods=['POST'])
@login_required
def api_create_campagne():
    """
    API: Crée une nouvelle campagne. Envoi immédiat via Celery ou programmé (stocké en BDD, déclenché par Celery Beat).

    Returns:
        JSON: Campagne créée + task_id (null si programmé)
    """
    from datetime import datetime, timezone
    from tasks.email_tasks import send_campagne_task
    from services.database.campagnes import CampagneManager
    import json

    data = request.get_json() or {}

    nom = data.get('nom')
    template_id = data.get('template_id')
    recipients = data.get('recipients', [])
    sujet = data.get('sujet')
    custom_message = data.get('custom_message')
    delay = data.get('delay', 2)
    send_mode = data.get('send_mode', 'now')
    scheduled_at_iso = data.get('scheduled_at_iso')

    if not nom:
        now = datetime.now()
        date_str = now.strftime('%d.%m')
        time_str = now.strftime('%Hh%M')
        template_name = template_id or 'Campagne email'
        nom = f'{template_name[:40]} - {date_str} {time_str}'

    if not recipients:
        return jsonify({'error': 'Aucun destinataire fourni'}), 400
    if not sujet:
        return jsonify({'error': 'Le sujet est requis'}), 400

    campagne_manager = CampagneManager()

    if send_mode == 'scheduled' and scheduled_at_iso:
        # Envoi programmé : stocker en BDD, ne pas lancer la tâche tout de suite (Beat s'en charge)
        try:
            # scheduled_at_iso est en UTC (envoyé par le front en toISOString())
            parsed = datetime.fromisoformat(scheduled_at_iso.replace('Z', '+00:00'))
            now_utc = datetime.now(timezone.utc)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            scheduled_at_str = parsed.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        except (ValueError, TypeError):
            return jsonify({'error': 'Date/heure programmée invalide'}), 400

        campaign_params = {
            'recipients': recipients,
            'template_id': template_id,
            'subject': sujet,
            'custom_message': custom_message,
            'delay': delay,
        }
        params_json = json.dumps(campaign_params)

        campagne_id = campagne_manager.create_campagne(
            nom=nom,
            template_id=template_id,
            sujet=sujet,
            total_destinataires=len(recipients),
            statut='scheduled',
            scheduled_at=scheduled_at_str,
            campaign_params_json=params_json,
        )
        return jsonify({'success': True, 'campagne_id': campagne_id, 'task_id': None, 'scheduled_at': scheduled_at_str})
    else:
        # Envoi immédiat
        campagne_id = campagne_manager.create_campagne(
            nom=nom,
            template_id=template_id,
            sujet=sujet,
            total_destinataires=len(recipients),
            statut='draft',
        )
        task = send_campagne_task.delay(
            campagne_id=campagne_id,
            recipients=recipients,
            template_id=template_id,
            subject=sujet,
            custom_message=custom_message,
            delay=delay,
        )
        campagne_manager.update_campagne(campagne_id, statut='scheduled')
        return jsonify({'success': True, 'campagne_id': campagne_id, 'task_id': task.id})


@other_bp.route('/api/campagnes/<int:campagne_id>', methods=['GET'])
@login_required
def api_get_campagne(campagne_id):
    """
    API: Détails d'une campagne.

    Args:
        campagne_id (int): ID de la campagne

    Returns:
        JSON: Détails de la campagne + emails
    """
    from services.database.campagnes import CampagneManager
    campagne_manager = CampagneManager()
    campagne = campagne_manager.get_campagne(campagne_id)
    if not campagne:
        return jsonify({'error': 'Campagne introuvable'}), 404

    campagne['emails'] = campagne_manager.get_emails_campagne(campagne_id)
    return jsonify(campagne)


@other_bp.route('/api/campagnes/<int:campagne_id>', methods=['DELETE'])
@login_required
def api_delete_campagne(campagne_id):
    """
    API: Supprime une campagne.

    Args:
        campagne_id (int): ID de la campagne

    Returns:
        JSON: Résultat de la suppression
    """
    from services.database import Database

    database = Database()
    conn = database.get_connection()
    cursor = conn.cursor()

    database.execute_sql(cursor, 'DELETE FROM campagnes_email WHERE id = ?', (campagne_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()

    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Campagne introuvable'}), 404


@other_bp.route('/api/campagnes/<int:campagne_id>/relaunch', methods=['POST'])
@login_required
def api_relaunch_campagne(campagne_id):
    """
    API: Relance une campagne existante en recréant un envoi immédiat
    avec les mêmes destinataires.

    Args:
        campagne_id (int): ID de la campagne source

    Returns:
        JSON: {'success': bool, 'campagne_id': int, 'task_id': str}
    """
    from services.database.campagnes import CampagneManager
    from tasks.email_tasks import send_campagne_task
    import json

    campagne_manager = CampagneManager()
    campagne = campagne_manager.get_campagne(campagne_id)
    if not campagne:
        return jsonify({'error': 'Campagne introuvable'}), 404

    existing_emails = campagne_manager.get_emails_campagne(campagne_id)
    if not existing_emails:
        return jsonify({'error': 'Aucun destinataire trouvé pour cette campagne'}), 400

    recipients = []
    seen = set()
    for email_row in existing_emails:
        email = (email_row.get('email') or '').strip()
        if not email:
            continue
        entreprise_id = email_row.get('entreprise_id')
        uniq_key = f"{email.lower()}::{entreprise_id or ''}"
        if uniq_key in seen:
            continue
        seen.add(uniq_key)
        recipients.append({
            'email': email,
            'nom': email_row.get('nom_destinataire'),
            'entreprise': email_row.get('entreprise') or email_row.get('entreprise_nom'),
            'entreprise_id': entreprise_id
        })

    if not recipients:
        return jsonify({'error': 'Destinataires invalides pour la relance'}), 400

    template_id = campagne.get('template_id')
    sujet = campagne.get('sujet')
    custom_message = None

    params_json = campagne.get('campaign_params_json')
    if params_json:
        try:
            params = json.loads(params_json)
            custom_message = params.get('custom_message')
        except (ValueError, TypeError):
            custom_message = None

    if not template_id and not custom_message:
        return jsonify({'error': 'Impossible de relancer: campagne sans template ni message source'}), 400

    source_name = campagne.get('nom') or f'Campagne #{campagne_id}'
    new_name = f"{source_name} Relance"
    new_campagne_id = campagne_manager.create_campagne(
        nom=new_name[:190],
        template_id=template_id,
        sujet=sujet,
        total_destinataires=len(recipients),
        statut='draft'
    )

    task = send_campagne_task.delay(
        campagne_id=new_campagne_id,
        recipients=recipients,
        template_id=template_id,
        subject=sujet,
        custom_message=custom_message,
        delay=2
    )
    campagne_manager.update_campagne(new_campagne_id, statut='scheduled')

    return jsonify({'success': True, 'campagne_id': new_campagne_id, 'task_id': task.id})


@other_bp.route('/api/campagnes/<int:campagne_id>/send-report-email', methods=['POST'])
@login_required
def api_send_campagne_report_email(campagne_id):
    """
    API: Envoie par email le rapport détaillé d'une campagne
    (statistiques globales + tableau des contacts).

    L'email est envoyé à contact@danielcraft.fr.

    Returns:
        JSON: {'success': bool, 'message': str}
    """
    from services.database.campagnes import CampagneManager
    from services.email_sender import EmailSender

    campagne_manager = CampagneManager()
    campagne = campagne_manager.get_campagne(campagne_id)
    if not campagne:
        return jsonify({'error': 'Campagne introuvable'}), 404

    stats = campagne_manager.get_campagne_tracking_stats(campagne_id)

    # Métadonnées utiles
    raw_date_creation = campagne.get('date_creation') or ''
    sujet_email = campagne.get('sujet') or ''
    total_emails = stats.get('total_emails', 0)
    total_opens = stats.get('total_opens', 0)
    total_clicks = stats.get('total_clicks', 0)
    open_rate = stats.get('open_rate', 0)
    click_rate = stats.get('click_rate', 0)

    # Formattage dates (plus lisibles)
    from datetime import datetime

    def _format_dt(value: str) -> str:
        if not value:
            return ''
        try:
            # Gère "YYYY-MM-DD HH:MM:SS" ou ISO
            s = str(value).replace('T', ' ')
            dt = datetime.fromisoformat(s)
            return dt.strftime('%d/%m/%Y %H:%M')
        except Exception:
            return str(value)

    date_creation = _format_dt(raw_date_creation)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report_generated_at = _format_dt(now_str)

    # Sujet d'email plus convivial
    # Exemple: "Rapport du 19/03/2026 – Optimisation conversion Technologie"
    date_for_subject = report_generated_at.split(' ')[0] if report_generated_at else ''
    subject = f"Rapport du {date_for_subject} – {campagne.get('nom') or f'Campagne #{campagne_id}'}"

    # Corps texte simple
    lines = [
        f"Rapport du {date_for_subject} – campagne #{campagne_id}",
        f"Nom : {campagne.get('nom') or '-'}",
        f"Sujet : {sujet_email or '-'}",
        f"Date de création : {date_creation}",
        f"Rapport généré : {report_generated_at}",
        "",
        f"Emails envoyés : {total_emails}",
        f"Ouvertures uniques : {total_opens} (taux {open_rate:.1f}%)",
        f"Clics uniques : {total_clicks} (taux {click_rate:.1f}%)",
        "",
        "Détail par contact :"
    ]
    for email in stats.get('emails', []):
        lines.append(
            f"- {email.get('nom_destinataire') or 'N/A'} <{email.get('email')}> "
            f"({email.get('entreprise') or 'N/A'}) "
            f"– statut={email.get('statut')}, opens={email.get('opens', 0)}, clicks={email.get('clicks', 0)}"
        )
    text_body = "\n".join(lines)

    # Corps HTML : ne lister que les contacts ayant au moins une ouverture ou un clic
    engaged_emails = [
        e for e in stats.get('emails', [])
        if (e.get('opens', 0) or 0) > 0 or (e.get('clicks', 0) or 0) > 0
    ]

    # Regrouper par entreprise pour un affichage plus lisible
    grouped_by_company = {}
    for email in engaged_emails:
        key = email.get('entreprise') or email.get('entreprise_nom') or 'Sans entreprise'
        grouped_by_company.setdefault(key, []).append(email)

    emails_rows = ""
    for company, emails in grouped_by_company.items():
        # Totaux par entreprise
        company_opens = sum(e.get('opens', 0) or 0 for e in emails)
        company_clicks = sum(e.get('clicks', 0) or 0 for e in emails)

        # Ligne "header" d'entreprise
        emails_rows += f"""
            <tr style="background:#f9fafb;">
                <td style="padding:7px 10px; border-bottom:1px solid #e5e7eb; font-weight:600; color:#111827;">
                    {company}
                    <span style="font-size:11px; font-weight:400; color:#6b7280; margin-left:6px;">
                        {len(emails)} email(s)
                    </span>
                </td>
                <td style="padding:7px 10px; border-bottom:1px solid #e5e7eb;"></td>
                <td style="padding:7px 10px; border-bottom:1px solid #e5e7eb; text-align:center; font-size:12px; color:#4b5563;">
                    Total
                </td>
                <td style="padding:7px 10px; border-bottom:1px solid #e5e7eb; text-align:center; color:#16a34a; font-weight:600;">
                    {company_opens}
                </td>
                <td style="padding:7px 10px; border-bottom:1px solid #e5e7eb; text-align:center; color:#2563eb; font-weight:600;">
                    {company_clicks}
                </td>
            </tr>
        """
        # Sous-lignes par email (détails discrets, décalés à gauche)
        for email in emails:
            emails_rows += f"""
            <tr>
                <td style="padding:4px 10px 5px 22px; border-bottom:1px solid #f3f4f6;">
                    <div style="font-weight:500; font-size:12px; margin-bottom:1px;">{(email.get('nom_destinataire') or 'Contact')}</div>
                    <div style="font-size:11px;color:#6b7280;">{(email.get('email') or '')}</div>
                </td>
                <td style="padding:4px 10px 5px 10px; border-bottom:1px solid #f3f4f6; font-size:11px; color:#6b7280;">
                    Canal email
                </td>
                <td style="padding:4px 10px 5px 10px; border-bottom:1px solid #f3f4f6; text-align:center; font-size:11px; color:#6b7280;">
                    {email.get('statut') or '-'}
                </td>
                <td style="padding:4px 10px 5px 10px; border-bottom:1px solid #f3f4f6; text-align:center; color:#16a34a; font-size:11px;">
                    {email.get('opens', 0)}
                </td>
                <td style="padding:4px 10px 5px 10px; border-bottom:1px solid #f3f4f6; text-align:center; color:#2563eb; font-size:11px;">
                    {email.get('clicks', 0)}
                </td>
            </tr>
            """

    html_body = f"""
    <html>
      <body style="margin:0; padding:24px; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif; background:#f3f4f6; color:#111827;">
        <div style="max-width:840px; margin:0 auto; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 18px 40px rgba(15,23,42,0.12); border:1px solid #e5e7eb;">
          <!-- Header -->
          <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6); padding:18px 22px 14px; color:#ffffff;">
            <div style="font-size:13px; opacity:0.9; margin-bottom:4px;">Rapport du {date_for_subject}</div>
            <div style="font-size:20px; font-weight:600; margin-bottom:10px;">{(campagne.get('nom') or f"Campagne #{campagne_id}")}</div>
            <div style="display:flex; flex-wrap:wrap; gap:18px; font-size:12px; opacity:0.96;">
              <div>📅 <strong>Créée :</strong> {date_creation or 'N/A'}</div>
              <div>🕒 <strong>Rapport :</strong> {report_generated_at}</div>
              <div style="flex:1 1 100%; margin-top:2px;">✉️ <strong>Sujet :</strong> {sujet_email or '-'}</div>
            </div>
          </div>

          <!-- Corps -->
          <div style="padding:18px 22px 22px;">
            <!-- Vue d'ensemble (2 colonnes + 1 colonne ratios) -->
            <div style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:18px;">
              <div style="flex:1 1 180px; background:#f9fafb; border-radius:12px; padding:12px 14px; border:1px solid #e5e7eb;">
                <div style="font-size:13px; color:#6b7280; margin-bottom:4px;">Volume envoyé</div>
                <div style="font-size:24px; font-weight:600; color:#111827;">{total_emails}</div>
                <div style="font-size:12px; color:#6b7280;">emails</div>
              </div>
              <div style="flex:1 1 180px; background:#ecfdf3; border-radius:12px; padding:12px 14px; border:1px solid #bbf7d0;">
                <div style="font-size:13px; color:#15803d; margin-bottom:4px;">Engagement</div>
                <div style="font-size:20px; font-weight:600; color:#14532d;">{total_opens} ouvertures</div>
                <div style="font-size:12px; color:#16a34a;">{open_rate:.1f}% d'ouverture</div>
              </div>
              <div style="flex:1 1 180px; background:#eff6ff; border-radius:12px; padding:12px 14px; border:1px solid #bfdbfe;">
                <div style="font-size:13px; color:#1d4ed8; margin-bottom:4px;">Intérêt fort</div>
                <div style="font-size:20px; font-weight:600; color:#1e40af;">{total_clicks} clics</div>
                <div style="font-size:12px; color:#2563eb;">{click_rate:.1f}% de clic</div>
              </div>
            </div>

            <!-- Détail par contact -->
            <div style="border-radius:12px; border:1px solid #e5e7eb; overflow:hidden; background:#f9fafb;">
              <div style="padding:10px 12px; background:#eef2ff; border-bottom:1px solid #e5e7eb; font-size:13px; font-weight:600; display:flex; justify-content:space-between; align-items:center; color:#1e293b;">
                <span>Contacts engagés (ouverture ou clic)</span>
                <span style="font-size:12px; color:#4b5563;">{len(engaged_emails)} contact(s)</span>
              </div>
              <table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse; font-size:13px; background:#ffffff;">
                <thead>
                  <tr style="background:#e5e7eb;">
                    <th align="left" style="padding:8px 10px; border-bottom:1px solid #e5e7eb; color:#374151;">Contact</th>
                    <th align="left" style="padding:8px 10px; border-bottom:1px solid #e5e7eb; color:#374151;">Entreprise</th>
                    <th align="center" style="padding:8px 10px; border-bottom:1px solid #e5e7eb; color:#374151;">Statut</th>
                    <th align="center" style="padding:8px 10px; border-bottom:1px solid #e5e7eb; color:#374151;">Ouvertures</th>
                    <th align="center" style="padding:8px 10px; border-bottom:1px solid #e5e7eb; color:#374151;">Clics</th>
                  </tr>
                </thead>
                <tbody>
                  {emails_rows or '<tr><td colspan="5" style="padding:10px 12px; text-align:center; color:#6b7280; background:#f9fafb;">Aucun contact n&#39;a encore ouvert ou cliqué cet email.</td></tr>'}
                </tbody>
              </table>
            </div>

            <div style="margin-top:14px; font-size:12px; color:#6b7280;">
              Astuce : compare ces chiffres avec tes autres campagnes pour identifier ce qui fonctionne le mieux (objet, accroche, ciblage…).
            </div>
          </div>
        </div>
      </body>
    </html>
    """

    sender = EmailSender()
    result = sender.send_email(
        to=MAIL_DEFAULT_RECIPIENT,
        subject=subject,
        body=text_body,
        html_body=html_body,
    )

    if not result.get('success'):
        return jsonify({'success': False, 'message': result.get('message', 'Erreur lors de l\'envoi')}), 500

    return jsonify({'success': True, 'message': 'Rapport de campagne envoyé à l\'adresse de réception par défaut'})


@other_bp.route('/api/entreprises/emails', methods=['GET'])
@login_required
def api_get_entreprises_with_emails():
    """
    API: Liste des entreprises avec leurs emails disponibles.

    Returns:
        JSON: Liste des entreprises avec emails
    """
    from services.database.entreprises import EntrepriseManager
    from utils.helpers import clean_json_dict
    entreprise_manager = EntrepriseManager()
    entreprises = entreprise_manager.get_entreprises_with_emails()
    entreprises = clean_json_dict(entreprises)
    return jsonify(entreprises)


@other_bp.route('/api/ciblage/objectifs', methods=['GET'])
@login_required
def api_ciblage_objectifs():
    """
    API: Liste des objectifs de ciblage prédéfinis (Formations, Modernisation, etc.).
    """
    from services.ciblage_objectifs import get_objectifs
    return jsonify(get_objectifs())


@other_bp.route('/api/ciblage/suggestions', methods=['GET'])
@login_required
def api_ciblage_suggestions():
    """
    API: Valeurs distinctes pour autocomplétion (secteurs, opportunités, statuts, tags).
    Query: with_counts=1 pour avoir les effectifs (value, count).
    """
    from services.database.entreprises import EntrepriseManager
    manager = EntrepriseManager()
    if request.args.get('with_counts') in ('1', 'true', 'True'):
        return jsonify(manager.get_ciblage_suggestions_with_counts())
    return jsonify(manager.get_ciblage_suggestions())


@other_bp.route('/api/ciblage/entreprises', methods=['GET'])
@login_required
def api_ciblage_entreprises():
    """
    API: Entreprises avec emails pour campagne, avec filtres de ciblage.
    Query params: secteur, secteur_contains, opportunite (virgule), statut, tags_contains,
    favori (1/0), search, score_securite_max, exclude_already_contacted (1/true),
    groupe_ids (virgule) : liste d'IDs de groupes d'entreprises.
    """
    from services.database.entreprises import EntrepriseManager
    from utils.helpers import clean_json_dict
    filters = {}
    if request.args.get('secteur'):
        filters['secteur'] = request.args.get('secteur')
    if request.args.get('secteur_contains'):
        filters['secteur_contains'] = request.args.get('secteur_contains')
    if request.args.get('opportunite'):
        filters['opportunite'] = [s.strip() for s in request.args.get('opportunite').split(',') if s.strip()]
    if request.args.get('statut'):
        filters['statut'] = request.args.get('statut')
    if request.args.get('tags_contains'):
        filters['tags_contains'] = request.args.get('tags_contains')
    if request.args.get('favori') in ('1', 'true', 'True'):
        filters['favori'] = True
    if request.args.get('search'):
        filters['search'] = request.args.get('search')
    if request.args.get('score_securite_max'):
        try:
            filters['score_securite_max'] = int(request.args.get('score_securite_max'))
        except ValueError:
            pass
    if request.args.get('exclude_already_contacted') in ('1', 'true', 'True'):
        filters['exclude_already_contacted'] = True
    if request.args.get('groupe_ids'):
        try:
            groupe_ids = [int(s.strip()) for s in request.args.get('groupe_ids').split(',') if s.strip()]
            filters['groupe_ids'] = groupe_ids
        except ValueError:
            pass
    # Filtres de segmentation avancée réutilisables dans les campagnes
    if request.args.get('cms'):
        filters['cms'] = request.args.get('cms')
    if request.args.get('framework'):
        filters['framework'] = request.args.get('framework')
    if request.args.get('has_blog') in ('1', 'true', 'True'):
        filters['has_blog'] = True
    if request.args.get('has_form') in ('1', 'true', 'True'):
        filters['has_form'] = True
    if request.args.get('has_tunnel') in ('1', 'true', 'True'):
        filters['has_tunnel'] = True
    if request.args.get('performance_max'):
        try:
            filters['performance_max'] = int(request.args.get('performance_max'))
        except ValueError:
            pass
    entreprise_manager = EntrepriseManager()
    entreprises = entreprise_manager.get_entreprises_for_campagne(filters)
    return jsonify(clean_json_dict(entreprises))


@other_bp.route('/api/ciblage/segments', methods=['GET', 'POST'])
@login_required
def api_ciblage_segments():
    """
    GET: Liste des segments de ciblage sauvegardés.
    POST: Crée un segment (body: nom, description?, criteres?).
    """
    from services.database.campagnes import CampagneManager
    db = CampagneManager()
    if request.method == 'GET':
        segments = db.get_segments()
        return jsonify(segments)
    data = request.get_json() or {}
    nom = data.get('nom') or request.form.get('nom')
    if not nom:
        return jsonify({'error': 'nom requis'}), 400
    segment_id = db.create_segment(
        nom=nom,
        description=data.get('description') or request.form.get('description'),
        criteres=data.get('criteres') or {}
    )
    return jsonify({'id': segment_id, 'nom': nom}), 201


@other_bp.route('/api/ciblage/segments/<int:segment_id>', methods=['DELETE'])
@login_required
def api_ciblage_segment_delete(segment_id):
    """Supprime un segment de ciblage."""
    from services.database.campagnes import CampagneManager
    db = CampagneManager()
    if db.delete_segment(segment_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Segment introuvable'}), 404


@other_bp.route('/track/pixel/<tracking_token>')
def track_pixel(tracking_token):
    """
    Route de tracking pour le pixel invisible (ouverture d'email).

    Args:
        tracking_token (str): Token de tracking unique

    Returns:
        Response: Image 1x1 transparente
    """
    from services.database.campagnes import CampagneManager
    from flask import request, send_file
    import io
    import logging

    logger = logging.getLogger(__name__)
    
    campagne_manager = CampagneManager()
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    
    # Logger pour déboguer
    logger.info(f'Tracking pixel appelé: token={tracking_token[:10]}..., IP={ip_address}, UA={user_agent[:50]}')

    try:
        event_id = campagne_manager.save_tracking_event(
            tracking_token=tracking_token,
            event_type='open',
            event_data=None,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if event_id:
            logger.info(f'Événement de tracking enregistré: event_id={event_id}')
        else:
            logger.warning(f'Échec enregistrement tracking: token={tracking_token[:10]}...')
    except Exception as e:
        logger.error(f'Erreur lors de l\'enregistrement du tracking: {e}', exc_info=True)

    # Retourner une image 1x1 transparente
    img = io.BytesIO()
    img.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82')
    img.seek(0)
    return send_file(img, mimetype='image/png')


@other_bp.route('/track/click/<tracking_token>')
def track_click(tracking_token):
    """
    Route de tracking pour les clics sur les liens.

    Args:
        tracking_token (str): Token de tracking unique

    Returns:
        Response: Redirection vers l'URL originale
    """
    from services.database.campagnes import CampagneManager
    from flask import request, redirect
    from urllib.parse import unquote

    campagne_manager = CampagneManager()
    url = request.args.get('url', '')
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')

    if url:
        campagne_manager.save_tracking_event(
            tracking_token=tracking_token,
            event_type='click',
            event_data={'url': url},
            ip_address=ip_address,
            user_agent=user_agent
        )

        decoded_url = unquote(url)
        return redirect(decoded_url, code=302)

    return redirect('/', code=302)


@other_bp.route('/api/tracking/email/<int:email_id>', methods=['GET'])
@login_required
def api_get_email_tracking(email_id):
    """
    API: Stats de tracking pour un email.

    Args:
        email_id (int): ID de l'email

    Returns:
        JSON: Statistiques de tracking
    """
    from services.database.campagnes import CampagneManager
    campagne_manager = CampagneManager()
    stats = campagne_manager.get_email_tracking_stats(email_id)
    return jsonify(stats)


@other_bp.route('/api/emails-envoyes/<int:email_id>/preview', methods=['GET'])
@login_required
def api_get_sent_email_preview(email_id):
    """
    API: Récupère le contenu envoyé pour un email précis.

    Args:
        email_id (int): ID de l'email envoyé

    Returns:
        JSON: sujet + contenu + méta utiles à l'affichage
    """
    from services.database.campagnes import CampagneManager

    campagne_manager = CampagneManager()
    email_data = campagne_manager.get_email_envoye(email_id)
    if not email_data:
        return jsonify({'error': 'Email introuvable'}), 404

    return jsonify({
        'id': email_data.get('id'),
        'campagne_id': email_data.get('campagne_id'),
        'email': email_data.get('email'),
        'nom_destinataire': email_data.get('nom_destinataire'),
        'entreprise': email_data.get('entreprise'),
        'sujet': email_data.get('sujet'),
        'contenu_envoye': email_data.get('contenu_envoye'),
        'date_envoi': email_data.get('date_envoi'),
    })


@other_bp.route('/api/tracking/campagne/<int:campagne_id>', methods=['GET'])
@login_required
def api_get_campagne_tracking(campagne_id):
    """
    API: Statistiques de tracking d'une campagne
    
    Args:
        campagne_id (int): ID de la campagne
        
    Returns:
        JSON: Statistiques de tracking
    """
    from services.database.campagnes import CampagneManager
    
    campagne_manager = CampagneManager()
    stats = campagne_manager.get_campagne_tracking_stats(campagne_id)
    
    return jsonify(stats)


@other_bp.route('/tokens')
@login_required
@admin_required
def api_tokens_page():
    """
    Page de gestion des tokens API (admin uniquement)
    
    Returns:
        str: Template HTML de la page de gestion des tokens
    """
    return render_page('api_tokens.html')


@other_bp.route('/documentation-api')
@login_required
def api_doc_page():
    """
    Page de documentation des endpoints API.
    
    Returns:
        str: Template HTML de la page documentation API
    """
    return render_page('api_doc.html')

