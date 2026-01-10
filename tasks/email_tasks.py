"""
Tâches Celery pour les services email (analyse et envoi)

Ces tâches enveloppent EmailAnalyzer et EmailSender pour exécuter
les opérations en arrière-plan.
"""

from celery_app import celery
from services.email_analyzer import EmailAnalyzer
from services.email_sender import EmailSender
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
            return {'success': True, 'results': []}

        analyzer = EmailAnalyzer()
        results = []

        total = len(emails)
        for idx, email in enumerate(emails, start=1):
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': int(idx / total * 100),
                    'message': f'Analyse de {email} ({idx}/{total})'
                }
            )
            analysis = analyzer.analyze_email(email, source_url=source_url)
            if analysis:
                results.append(analysis)

        return {'success': True, 'results': results, 'total': total}
    except Exception as e:
        logger.error(f'Erreur analyse emails: {e}', exc_info=True)
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

