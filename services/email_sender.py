"""
Service d'envoi d'emails de prospection
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour importer config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS,
    MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
)


class EmailSender:
    def __init__(self):
        self.mail_server = MAIL_SERVER
        self.mail_port = MAIL_PORT
        self.mail_use_tls = MAIL_USE_TLS
        self.mail_username = MAIL_USERNAME
        self.mail_password = MAIL_PASSWORD
        self.default_sender = MAIL_DEFAULT_SENDER
    
    def send_email(self, to, subject, body, recipient_name=None, html_body=None):
        """
        Envoie un email
        
        Args:
            to: Adresse email du destinataire
            subject: Sujet de l'email
            body: Corps de l'email (texte)
            recipient_name: Nom du destinataire (optionnel)
            html_body: Corps HTML (optionnel)
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        if not self.mail_username or not self.mail_password:
            return {
                'success': False,
                'message': 'Configuration email manquante. Veuillez configurer MAIL_USERNAME et MAIL_PASSWORD dans config.py ou variables d\'environnement.'
            }
        
        try:
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.default_sender
            msg['To'] = to
            msg['Subject'] = subject
            
            # Ajouter le corps texte
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Ajouter le corps HTML si fourni
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Envoyer l'email
            with smtplib.SMTP(self.mail_server, self.mail_port) as server:
                if self.mail_use_tls:
                    server.starttls()
                server.login(self.mail_username, self.mail_password)
                server.send_message(msg)
            
            return {
                'success': True,
                'message': f'Email envoyé avec succès à {to}'
            }
        
        except smtplib.SMTPAuthenticationError:
            return {
                'success': False,
                'message': 'Erreur d\'authentification. Vérifiez vos identifiants email.'
            }
        except smtplib.SMTPRecipientsRefused:
            return {
                'success': False,
                'message': f'Adresse email invalide: {to}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Erreur lors de l\'envoi: {str(e)}'
            }
    
    def send_bulk_emails(self, recipients, subject_template, body_template, delay=2):
        """
        Envoie plusieurs emails avec un délai entre chaque envoi
        
        Args:
            recipients: Liste de dicts {'email': str, 'nom': str, 'entreprise': str}
            subject_template: Template du sujet (peut contenir {nom}, {entreprise})
            body_template: Template du corps (peut contenir {nom}, {entreprise})
            delay: Délai en secondes entre chaque envoi
        
        Returns:
            list: Liste de résultats pour chaque destinataire
        """
        results = []
        
        for recipient in recipients:
            # Personnaliser le sujet et le corps
            subject = subject_template.format(
                nom=recipient.get('nom', ''),
                entreprise=recipient.get('entreprise', '')
            )
            body = body_template.format(
                nom=recipient.get('nom', ''),
                entreprise=recipient.get('entreprise', '')
            )
            
            # Envoyer l'email
            result = self.send_email(
                to=recipient['email'],
                subject=subject,
                body=body,
                recipient_name=recipient.get('nom')
            )
            
            results.append({
                'email': recipient['email'],
                'success': result['success'],
                'message': result['message']
            })
            
            # Délai entre les envois pour éviter le spam
            if delay > 0:
                import time
                time.sleep(delay)
        
        return results

