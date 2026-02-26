"""
Tâches Celery pour les services email (analyse et envoi)

Ces tâches enveloppent EmailAnalyzer et EmailSender pour exécuter
les opérations en arrière-plan.
"""

from celery_app import celery
from services.email_analyzer import EmailAnalyzer
from services.email_sender import EmailSender
from services.email_tracker import EmailTracker
from services.logging_config import setup_logger
import logging

# Configurer le logger pour cette tâche
logger = setup_logger(__name__, 'email_tasks.log', level=logging.DEBUG)


@celery.task(bind=True)
def analyze_emails_task(self, emails, source_url=None):
    """
    Analyse une liste d'emails en tâche asynchrone.

    Args:
        self: Instance de la tâche Celery (bind=True)
        emails (list[str]): Liste d'adresses email à analyser
        source_url (str, optional): URL source d'où proviennent les emails

    Returns:
        dict: Résultats avec la liste analysée
    """
    try:
        if not emails:
            logger.info(f'[Analyse Emails] Aucun email à analyser (source_url={source_url})')
            return {'success': True, 'results': []}

        logger.info(
            f'[Analyse Emails] Démarrage de l\'analyse de {len(emails)} email(s) '
            f'(source_url={source_url})'
        )

        analyzer = EmailAnalyzer()
        results = []
        total = len(emails)

        for idx, email in enumerate(emails, start=1):
            try:
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': int(idx / total * 100),
                        'message': f'Analyse de {email} ({idx}/{total})'
                    }
                )
                logger.debug(f'[Analyse Emails] Analyse de {email} ({idx}/{total})')
                
                analysis = analyzer.analyze_email(email, source_url=source_url)
                if analysis:
                    results.append(analysis)
                    logger.debug(
                        f'[Analyse Emails] ✓ {email} analysé: '
                        f'type={analysis.get("type")}, provider={analysis.get("provider")}, '
                        f'mx_valid={analysis.get("mx_valid")}'
                    )
                else:
                    logger.warning(f'[Analyse Emails] ⚠ Aucun résultat pour {email}')
            except Exception as email_error:
                logger.error(
                    f'[Analyse Emails] ✗ Erreur lors de l\'analyse de {email}: {email_error}',
                    exc_info=True
                )
                # Continuer avec l'email suivant même en cas d'erreur

        logger.info(
            f'[Analyse Emails] Analyse terminée: {len(results)}/{total} email(s) analysé(s) avec succès '
            f'(source_url={source_url})'
        )

        return {'success': True, 'results': results, 'total': total}
    except Exception as e:
        logger.error(f'[Analyse Emails] Erreur critique lors de l\'analyse des emails: {e}', exc_info=True)
        raise


@celery.task(bind=True)
def send_email_task(self, to, subject, body, recipient_name=None, html_body=None):
    """
    Envoie un email individuel via EmailSender.
    """
    try:
        sender = EmailSender()
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Préparation de l\'email...'})
        result = sender.send_email(to=to, subject=subject, body=body, recipient_name=recipient_name, html_body=html_body)
        self.update_state(state='PROGRESS', meta={'progress': 100, 'message': 'Email envoyé'})
        return result
    except Exception as e:
        logger.error(f'Erreur envoi email: {e}', exc_info=True)
        raise


@celery.task(bind=True)
def send_bulk_emails_task(self, recipients, subject_template, body_template, delay=2):
    """
    Envoie un lot d'emails avec personnalisation simple.

    Args:
        recipients (list[dict]): {email, nom, entreprise}
        subject_template (str): Sujet avec placeholders {nom}, {entreprise}
        body_template (str): Corps texte avec placeholders {nom}, {entreprise}
        delay (int): Délai entre envois
    """
    try:
        sender = EmailSender()
        total = len(recipients) if recipients else 0
        results = []

        for idx, recipient in enumerate(recipients or [], start=1):
            self.update_state(
                state='PROGRESS',
                meta={'progress': int(idx / max(total, 1) * 100), 'message': f'Envoi {idx}/{total}'}
            )
            result = sender.send_email(
                to=recipient.get('email'),
                subject=subject_template.format(nom=recipient.get('nom', ''), entreprise=recipient.get('entreprise', '')),
                body=body_template.format(nom=recipient.get('nom', ''), entreprise=recipient.get('entreprise', ''))
            )
            results.append({**recipient, **result})

        return {'success': True, 'results': results, 'total': total}
    except Exception as e:
        logger.error(f'Erreur envoi bulk emails: {e}', exc_info=True)
        raise


@celery.task(bind=True)
def send_campagne_task(self, campagne_id, recipients, template_id=None, subject=None, custom_message=None, delay=2):
    """
    Envoie une campagne email complète avec suivi en temps réel.

    Args:
        campagne_id (int): ID de la campagne en BDD
        recipients (list[dict]): Liste {email, nom, entreprise, entreprise_id}
        template_id (str|None): ID du template (optionnel)
        subject (str|None): Sujet de l'email
        custom_message (str|None): Message personnalisé si pas de template
        delay (int): Délai entre envois (secondes)

    Returns:
        dict: Résultats de la campagne
    """
    from services.database import Database
    from services.database.campagnes import CampagneManager
    from services.template_manager import TemplateManager
    import time

    logger.info(f'[Campagne {campagne_id}] Démarrage de la campagne avec {len(recipients) if recipients else 0} destinataires')

    db = Database()
    campagne_manager = CampagneManager()
    template_manager = TemplateManager()

    # URL de base pour les liens de tracking
    try:
        from config import BASE_URL
        base_url = BASE_URL if BASE_URL else 'http://localhost:5000'
    except Exception:
        base_url = 'http://localhost:5000'

    tracker = EmailTracker(base_url=base_url)
    email_sender = EmailSender()

    total = len(recipients) if recipients else 0
    results = []
    total_sent = 0
    total_failed = 0
    logs = []

    campagne_manager.update_campagne(campagne_id, statut='running', total_destinataires=total)

    template = None
    if template_id:
        template = template_manager.get_template(template_id)

    try:
        for idx, recipient in enumerate(recipients or [], start=1):
            recipient_email = recipient.get('email', 'N/A')

            progress = int((idx / max(total, 1)) * 100)
            logs.append({
                'timestamp': time.strftime('%H:%M:%S'),
                'level': 'info',
                'message': f'Traitement {idx}/{total}: {recipient_email}'
            })

            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': progress,
                    'message': f'Envoi {idx}/{total} : {recipient_email}',
                    'current': idx,
                    'total': total,
                    'sent': total_sent,
                    'failed': total_failed,
                    'logs': logs[-20:]
                }
            )

            # Formater le nom du destinataire si nécessaire
            from utils.name_formatter import format_name
            recipient_nom = format_name(recipient.get('nom', ''))
            
            # Rendre le template avec les données de l'entreprise
            entreprise_id = recipient.get('entreprise_id')
            if template_id and template:
                content, is_html = template_manager.render_template(
                    template_id,
                    recipient_nom,
                    recipient.get('entreprise', ''),
                    recipient.get('email', ''),
                    entreprise_id=entreprise_id
                )
                # Formater le sujet avec les variables
                subject_template = subject or template.get('subject', 'Prospection')
                email_subject = subject_template.format(
                    nom=recipient_nom or 'Monsieur/Madame',
                    entreprise=recipient.get('entreprise', 'votre entreprise')
                )
                if is_html:
                    html_message = content
                    text_message = None  # EmailSender extraira le texte depuis HTML si besoin
                else:
                    html_message = tracker.convert_text_to_html(content)
                    text_message = content
            elif custom_message:
                message = custom_message.format(
                    nom=recipient_nom or 'Monsieur/Madame',
                    entreprise=recipient.get('entreprise', 'votre entreprise'),
                    email=recipient.get('email', '')
                )
                email_subject = subject or 'Prospection'
                html_message = tracker.convert_text_to_html(message)
                text_message = message
            else:
                total_failed += 1
                campagne_manager.save_email_envoye(
                    campagne_id=campagne_id,
                    entreprise_id=recipient.get('entreprise_id'),
                    email=recipient.get('email'),
                    nom_destinataire=recipient_nom or recipient.get('nom', ''),
                    entreprise=recipient.get('entreprise'),
                    sujet=subject or 'Prospection',
                    statut='failed',
                    erreur='Template ou message requis'
                )
                continue

            # Générer le token de tracking
            tracking_token = tracker.generate_tracking_token()

            # Traiter le contenu HTML pour ajouter le tracking
            if html_message:
                html_message = tracker.process_email_content(html_message, tracking_token)

            # Envoyer l'email
            result = email_sender.send_email(
                to=recipient.get('email'),
                subject=email_subject,
                body=text_message or 'Email HTML',
                recipient_name=recipient_nom or '',
                html_body=html_message,
                tracking_token=tracking_token
            )

            # Sauvegarder l'email envoyé
            email_id = campagne_manager.save_email_envoye(
                campagne_id=campagne_id,
                entreprise_id=recipient.get('entreprise_id'),
                email=recipient.get('email'),
                nom_destinataire=recipient_nom or recipient.get('nom', ''),
                entreprise=recipient.get('entreprise'),
                sujet=email_subject,
                statut='sent' if result.get('success') else 'failed',
                erreur=None if result.get('success') else result.get('message', 'Erreur inconnue'),
                tracking_token=tracking_token
            )

            if result.get('success'):
                total_sent += 1
            else:
                total_failed += 1

            results.append({**recipient, **result})

            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': progress,
                    'message': f'Envoi {idx}/{total} : {recipient_email}',
                    'current': idx,
                    'total': total,
                    'sent': total_sent,
                    'failed': total_failed,
                    'logs': logs[-20:]
                }
            )

            if delay > 0 and idx < total:
                time.sleep(delay)

        final_statut = 'completed' if (total_sent > 0 or total == 0) else 'failed'
        campagne_manager.update_campagne(
            campagne_id,
            statut=final_statut,
            total_envoyes=total,
            total_reussis=total_sent
        )

        # En fin de campagne : passer en "Perdu" les entreprises restées Nouveau/À qualifier sans open ni clic
        if final_statut == 'completed':
            try:
                marked_lost = campagne_manager.mark_campaign_lost_entreprises(campagne_id)
                if marked_lost:
                    logger.info(f'[Campagne {campagne_id}] {marked_lost} entreprise(s) passée(s) en statut Perdu (0 open, 0 clic)')
            except Exception as e:
                logger.warning(f'[Campagne {campagne_id}] mark_campaign_lost_entreprises: {e}')

        return {
            'success': True,
            'campagne_id': campagne_id,
            'results': results,
            'total': total,
            'total_sent': total_sent,
            'total_failed': total_failed,
            'logs': logs
        }
    except Exception as e:
        logger.error(f'Erreur campagne {campagne_id}: {e}', exc_info=True)
        campagne_manager.update_campagne(campagne_id, statut='failed')
        raise


@celery.task
def start_scheduled_campagnes():
    """
    Tâche périodique (Celery Beat) : lance les campagnes dont l'heure d'envoi programmée est atteinte (UTC).
    À exécuter toutes les minutes.
    """
    from datetime import datetime, timezone
    from services.database.campagnes import CampagneManager
    import json

    now_utc = datetime.now(timezone.utc)
    now_utc_iso = now_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')

    campagne_manager = CampagneManager()
    due = campagne_manager.get_campagnes_due_for_send(now_utc_iso)

    for row in due:
        campagne_id = row.get('id')
        params_json = row.get('campaign_params_json')
        if not campagne_id or not params_json:
            continue
        try:
            params = json.loads(params_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f'[Beat] Campagne {campagne_id}: campaign_params_json invalide')
            continue

        recipients = params.get('recipients', [])
        if not recipients:
            continue

        # Marquer comme en cours pour que le beat ne la reprenne pas
        campagne_manager.update_campagne(campagne_id, statut='running')

        send_campagne_task.delay(
            campagne_id=campagne_id,
            recipients=recipients,
            template_id=params.get('template_id'),
            subject=params.get('subject'),
            custom_message=params.get('custom_message'),
            delay=params.get('delay', 2),
        )
        logger.info(f'[Beat] Campagne {campagne_id} programmée démarrée ({len(recipients)} destinataires)')

