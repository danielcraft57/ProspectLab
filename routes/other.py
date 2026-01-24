"""
Blueprint pour les routes supplémentaires non encore migrées

Contient les routes pour les emails, templates, scraping et téléchargements.
"""

from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
import os
from services.email_sender import EmailSender
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
                content=data.get('content')
            )
            return jsonify({'success': True, 'template': template})
        
        elif action == 'delete':
            template_manager.delete_template(data.get('template_id'))
            return jsonify({'success': True})
    
    # GET: Liste des templates
    templates = template_manager.list_templates()
    return render_page('templates.html', templates=templates)


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


@other_bp.route('/api/templates')
@login_required
def api_templates():
    """
    API: Liste des templates
    
    Returns:
        JSON: Liste des templates
    """
    templates = template_manager.list_templates()
    return jsonify(templates)


@other_bp.route('/api/templates/<template_id>')
@login_required
def api_template_detail(template_id):
    """
    API: Détails d'un template
    
    Args:
        template_id (str): ID du template
        
    Returns:
        JSON: Détails du template ou erreur 404
    """
    template = template_manager.get_template(template_id)
    if template:
        return jsonify(template)
    return jsonify({'error': 'Template introuvable'}), 404


# ==================== ROUTES POUR LES CAMPAGNES EMAIL ====================

@other_bp.route('/campagnes', methods=['GET'])
@login_required
def list_campagnes():
    """
    Liste toutes les campagnes email.

    Returns:
        str: Template HTML de la liste des campagnes
    """
    from services.database.campagnes import CampagneManager
    campagne_manager = CampagneManager()
    campagnes = campagne_manager.list_campagnes(limit=100)
    return render_page('campagnes.html', campagnes=campagnes)


@other_bp.route('/api/campagnes', methods=['GET'])
@login_required
def api_list_campagnes():
    """
    API: Liste des campagnes.

    Returns:
        JSON: Liste des campagnes
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
    API: Crée une nouvelle campagne et lance l'envoi via Celery.

    Returns:
        JSON: Campagne créée + task_id
    """
    from tasks.email_tasks import send_campagne_task
    from services.database.campagnes import CampagneManager

    data = request.get_json() or {}

    nom = data.get('nom')  # Peut être None, sera généré si absent
    template_id = data.get('template_id')
    recipients = data.get('recipients', [])
    sujet = data.get('sujet')
    custom_message = data.get('custom_message')
    delay = data.get('delay', 2)

    # Générer un nom automatique si non fourni
    if not nom:
        from datetime import datetime
        now = datetime.now()
        date_str = now.strftime('%d.%m')
        time_str = now.strftime('%Hh%M')
        template_name = template_id or 'Custom'
        recipient_count = len(recipients) if recipients else 0
        nom = f'📧 {date_str} {time_str} - {template_name[:10]} ({recipient_count})'

    if not recipients:
        return jsonify({'error': 'Aucun destinataire fourni'}), 400
    if not sujet:
        return jsonify({'error': 'Le sujet est requis'}), 400

    campagne_manager = CampagneManager()

    campagne_id = campagne_manager.create_campagne(
        nom=nom,
        template_id=template_id,
        sujet=sujet,
        total_destinataires=len(recipients),
        statut='draft'
    )

    task = send_campagne_task.delay(
        campagne_id=campagne_id,
        recipients=recipients,
        template_id=template_id,
        subject=sujet,
        custom_message=custom_message,
        delay=delay
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


@other_bp.route('/api/entreprises/emails', methods=['GET'])
@login_required
def api_get_entreprises_with_emails():
    """
    API: Liste des entreprises avec leurs emails disponibles.

    Returns:
        JSON: Liste des entreprises avec emails
    """
    from services.database.entreprises import EntrepriseManager
    entreprise_manager = EntrepriseManager()
    entreprises = entreprise_manager.get_entreprises_with_emails()
    return jsonify(entreprises)


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

