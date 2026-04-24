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
import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import json
from config import MAIL_DEFAULT_RECIPIENT
from config import (
    BOUNCE_SCAN_ENABLED,
    BOUNCE_SCAN_PROFILES,
    BOUNCE_SCAN_DAYS,
    BOUNCE_SCAN_AFTER_CAMPAIGN_DAYS,
    BOUNCE_SCAN_LIMIT,
    BOUNCE_SCAN_DELETE_PROCESSED,
    BOUNCE_SCAN_POST_CAMPAIGN_DELAY_SEC,
)
import subprocess
import sys

# Configurer le logger pour cette tâche
logger = setup_logger(__name__, 'email_tasks.log', level=logging.DEBUG)

# Fichier cache pour le suivi d'évolution des stats de campagnes
STATS_CACHE_PATH = Path(__file__).resolve().parents[1] / 'logs' / 'campagne_stats_cache.json'


def _resolve_email_sender(mail_account_id, campagne_row):
    """
    Choisit le transport SMTP : compte BDD (mail_accounts) ou variables d'environnement (.env).
    """
    mid = mail_account_id
    if mid is None and campagne_row:
        mid = campagne_row.get('mail_account_id')
    if mid is not None:
        try:
            from services.database.mail_accounts import MailAccountManager

            mam = MailAccountManager()
            acc = mam.get_mail_account_decrypted(int(mid))
            if acc:
                return EmailSender.from_mail_account(acc)
        except Exception as e:
            logger.warning(f'Compte mail {mid} indisponible, fallback .env: {e}')
    return EmailSender()


@celery.task
def run_bounce_scan_task(days=None, profiles=None, delete_processed=None, limit=None, debug=False):
    """
    Lance le scan IMAP des bounces via le script dédié.
    """
    if not BOUNCE_SCAN_ENABLED:
        logger.info('[BounceScan] Désactivé (BOUNCE_SCAN_ENABLED=false)')
        return {'success': True, 'skipped': True, 'reason': 'disabled'}

    root = Path(__file__).resolve().parents[1]
    script = root / 'scripts' / 'fetch_bounces_imap.py'
    if not script.exists():
        logger.warning(f'[BounceScan] Script introuvable: {script}')
        return {'success': False, 'error': 'script_not_found'}

    _days = int(days) if days is not None else int(BOUNCE_SCAN_DAYS)
    _profiles = (profiles or BOUNCE_SCAN_PROFILES or 'default').strip()
    _delete = bool(BOUNCE_SCAN_DELETE_PROCESSED if delete_processed is None else delete_processed)
    _limit = int(BOUNCE_SCAN_LIMIT if limit is None else limit)

    cmd = [
        sys.executable,
        str(script),
        '--apply',
        '--days', str(_days),
        '--profiles', _profiles,
        '--limit', str(_limit),
    ]
    if _delete:
        cmd.append('--delete-processed')
    if debug:
        cmd.append('--debug')

    logger.info(f'[BounceScan] Run: {" ".join(cmd)}')
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60 * 20,  # 20 min max
            check=False,
        )
        out = (completed.stdout or '').strip()
        err = (completed.stderr or '').strip()
        if out:
            logger.info(f'[BounceScan] stdout:\n{out}')
        if err:
            logger.warning(f'[BounceScan] stderr:\n{err}')
        return {
            'success': completed.returncode == 0,
            'returncode': completed.returncode,
            'stdout': out[-4000:],
            'stderr': err[-2000:],
        }
    except Exception as e:
        logger.error(f'[BounceScan] Erreur exécution: {e}', exc_info=True)
        return {'success': False, 'error': str(e)}


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
def send_campagne_task(self, campagne_id, recipients, template_id=None, subject=None, custom_message=None, delay=2, mail_account_id=None):
    """
    Envoie une campagne email complète avec suivi en temps réel.

    Args:
        campagne_id (int): ID de la campagne en BDD
        recipients (list[dict]): Liste {email, nom, entreprise, entreprise_id}
        template_id (str|None): ID du template (optionnel)
        subject (str|None): Sujet de l'email
        custom_message (str|None): Message personnalisé si pas de template
        delay (int): Délai entre envois (secondes)
        mail_account_id (int|None): Compte SMTP en base (prioritaire sur .env)

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
    campagne_row = campagne_manager.get_campagne(campagne_id)

    # URL de base pour les liens de tracking
    try:
        from config import BASE_URL
        base_url = BASE_URL if BASE_URL else 'http://localhost:5000'
    except Exception:
        base_url = 'http://localhost:5000'

    tracker = EmailTracker(base_url=base_url)
    email_sender = _resolve_email_sender(mail_account_id, campagne_row)
    brand_domain = 'danielcraft.fr'
    try:
        mid_for_brand = mail_account_id
        if mid_for_brand is None and campagne_row:
            mid_for_brand = campagne_row.get('mail_account_id')
        if mid_for_brand is not None:
            from services.database.mail_accounts import MailAccountManager

            mam = MailAccountManager()
            acc = mam.get_mail_account(int(mid_for_brand))
            if acc and acc.get('domain_name'):
                brand_domain = acc.get('domain_name') or brand_domain
    except Exception:
        pass

    total = len(recipients) if recipients else 0
    results = []
    total_sent = 0
    total_failed = 0
    logs = []

    campagne_manager.update_campagne(campagne_id, statut='running', total_destinataires=total)
    # Déclencher un scan bounces peu après le lancement de campagne.
    # Le scan périodique (Beat) tournera aussi 2x/jour.
    if BOUNCE_SCAN_ENABLED:
        try:
            run_bounce_scan_task.apply_async(
                kwargs={
                    'days': int(BOUNCE_SCAN_AFTER_CAMPAIGN_DAYS),
                    'profiles': BOUNCE_SCAN_PROFILES,
                    'delete_processed': bool(BOUNCE_SCAN_DELETE_PROCESSED),
                    'limit': int(BOUNCE_SCAN_LIMIT),
                    'debug': False,
                },
                countdown=int(BOUNCE_SCAN_POST_CAMPAIGN_DELAY_SEC),
            )
            logger.info(
                f'[Campagne {campagne_id}] Bounce scan planifié dans '
                f'{int(BOUNCE_SCAN_POST_CAMPAIGN_DELAY_SEC)}s '
                f'(days={int(BOUNCE_SCAN_AFTER_CAMPAIGN_DAYS)}, limit={int(BOUNCE_SCAN_LIMIT)})'
            )
        except Exception as e:
            logger.warning(f'[Campagne {campagne_id}] Impossible de planifier le bounce scan: {e}')

    template = None
    if template_id:
        template = template_manager.get_template(
            template_id,
            for_preview=False,
            mail_account_id=mail_account_id,
        )

    try:
        for idx, recipient in enumerate(recipients or [], start=1):
            recipient_email = recipient.get('email', 'N/A')
            entreprise_id = recipient.get('entreprise_id')

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

            # Ne jamais renvoyer vers une adresse déjà reconnue en bounce
            # (même entreprise ou historique global de la même adresse).
            if campagne_manager.is_email_blocked_for_campaign(recipient_email, entreprise_id=entreprise_id):
                total_failed += 1
                campagne_manager.save_email_envoye(
                    campagne_id=campagne_id,
                    entreprise_id=entreprise_id,
                    email=recipient.get('email'),
                    nom_destinataire=recipient.get('nom', ''),
                    entreprise=recipient.get('entreprise'),
                    sujet=subject or 'Prospection',
                    statut='failed',
                    erreur='Envoi bloqué: adresse déjà marquée bounced',
                )
                logs.append({
                    'timestamp': time.strftime('%H:%M:%S'),
                    'level': 'warning',
                    'message': f'Adresse ignorée (bounce connu): {recipient_email}',
                })
                continue

            # Formater le nom du destinataire si nécessaire
            from utils.name_formatter import format_name
            recipient_nom = format_name(recipient.get('nom', ''))
            
            # Rendre le template avec les données de l'entreprise
            if template_id and template:
                content, is_html = template_manager.render_template(
                    template_id,
                    recipient_nom,
                    recipient.get('entreprise', ''),
                    recipient.get('email', ''),
                    entreprise_id=entreprise_id,
                    brand_domain=brand_domain,
                    mail_account_id=mail_account_id,
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
                tracking_token=tracking_token,
                contenu_envoye=html_message or text_message
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

        # Statut final campagne:
        # - completed: tout est parti sans échec (ou campagne vide)
        # - completed_with_errors: envoi partiel (au moins 1 succès + au moins 1 échec)
        # - failed: aucun email n'a pu être envoyé avec succès
        if total == 0:
            final_statut = 'completed'
        elif total_sent > 0 and total_failed > 0:
            final_statut = 'completed_with_errors'
        elif total_sent > 0:
            final_statut = 'completed'
        else:
            final_statut = 'failed'
        campagne_manager.update_campagne(
            campagne_id,
            statut=final_statut,
            total_envoyes=total,
            total_reussis=total_sent
        )

        # En fin de campagne: le passage auto en "Perdu" est désactivé par défaut,
        # car il peut fausser fortement le pipeline quand le tracking open/click
        # est partiellement bloqué (Apple MPP, anti-trackers, clients mail).
        auto_mark_lost = str(os.getenv('AUTO_MARK_LOST_ON_CAMPAIGN_COMPLETE', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
        if final_statut == 'completed' and auto_mark_lost:
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
            mail_account_id=params.get('mail_account_id'),
        )
        logger.info(f'[Beat] Campagne {campagne_id} programmée démarrée ({len(recipients)} destinataires)')
        

def _get_paris_now():
    """Retourne la datetime courante en Europe/Paris (timezone aware)."""
    paris_tz = ZoneInfo('Europe/Paris')
    return datetime.now(paris_tz)


def _to_utc_iso(dt):
    """Convertit une datetime aware en UTC ISO string avec suffixe Z."""
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')


def _build_campaigns_report_html(title, campagnes_stats):
    """
    Version claire / moderne du rapport campagnes (fond clair, cartes).
    """
    # Section tableau (même si vide on garde un bloc propre)
    if not campagnes_stats:
        rows_html = """
          <tr>
            <td colspan="6" style="padding:10px 12px; text-align:center; color:#6b7280;">
              Aucune campagne correspondante sur la période analysée.
            </td>
          </tr>
        """
    else:
        rows_html = ""
        for cs in campagnes_stats:
            rows_html += f"""
              <tr>
                <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">{cs.get('id')}</td>
                <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">{cs.get('nom') or ''}</td>
                <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb; text-transform:capitalize; color:#4b5563;">{cs.get('statut') or ''}</td>
                <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">{cs.get('total_emails')}</td>
                <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">{cs.get('open_rate'):.1f}%</td>
                <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">{cs.get('click_rate'):.1f}%</td>
              </tr>
            """

    total_emails = sum(cs.get('total_emails', 0) for cs in campagnes_stats) if campagnes_stats else 0
    avg_open = sum(cs.get('open_rate', 0.0) for cs in campagnes_stats) / max(len(campagnes_stats), 1) if campagnes_stats else 0.0
    avg_click = sum(cs.get('click_rate', 0.0) for cs in campagnes_stats) / max(len(campagnes_stats), 1) if campagnes_stats else 0.0

    return f"""
    <html>
      <body style="margin:0; padding:24px; font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif; background:#f3f4f6;">
        <div style="max-width:840px; margin:0 auto; background:#ffffff; border-radius:16px; box-shadow:0 18px 40px rgba(15,23,42,0.12); overflow:hidden; border:1px solid #e5e7eb;">
          <!-- Bandeau -->
          <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6); padding:18px 22px; color:#ffffff;">
            <div style="font-size:13px; opacity:0.9; margin-bottom:4px;">Rapport campagnes ProspectLab</div>
            <div style="font-size:20px; font-weight:600;">{title}</div>
          </div>

          <!-- Contenu principal -->
          <div style="padding:18px 22px 22px;">
            <!-- Cartes synthèse -->
            <div style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:18px;">
              <div style="flex:1 1 150px; background:#f9fafb; border-radius:12px; padding:12px 14px; border:1px solid #e5e7eb;">
                <div style="font-size:13px; color:#6b7280; margin-bottom:4px;">Campagnes sur la période</div>
                <div style="font-size:22px; font-weight:600; color:#111827;">{len(campagnes_stats) if campagnes_stats else 0}</div>
              </div>
              <div style="flex:1 1 150px; background:#f9fafb; border-radius:12px; padding:12px 14px; border:1px solid #e5e7eb;">
                <div style="font-size:13px; color:#6b7280; margin-bottom:4px;">Emails envoyés (total)</div>
                <div style="font-size:22px; font-weight:600; color:#111827;">{total_emails}</div>
              </div>
              <div style="flex:1 1 150px; background:#ecfdf3; border-radius:12px; padding:12px 14px; border:1px solid #bbf7d0;">
                <div style="font-size:13px; color:#15803d; margin-bottom:4px;">Ouverture moyenne</div>
                <div style="font-size:22px; font-weight:600; color:#14532d;">{avg_open:.1f}%</div>
              </div>
              <div style="flex:1 1 150px; background:#eff6ff; border-radius:12px; padding:12px 14px; border:1px solid #bfdbfe;">
                <div style="font-size:13px; color:#1d4ed8; margin-bottom:4px;">Clic moyen</div>
                <div style="font-size:22px; font-weight:600; color:#1e40af;">{avg_click:.1f}%</div>
              </div>
            </div>

            <!-- Tableau -->
            <div style="border-radius:12px; border:1px solid #e5e7eb; overflow:hidden;">
              <div style="padding:10px 12px; background:#f9fafb; border-bottom:1px solid #e5e7eb; font-size:13px; font-weight:600; color:#111827;">
                Détail par campagne
              </div>
              <table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse; font-size:13px; color:#111827;">
                <thead>
                  <tr style="background:#f3f4f6;">
                    <th align="left" style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">ID</th>
                    <th align="left" style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">Nom</th>
                    <th align="left" style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">Statut</th>
                    <th align="left" style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">Emails</th>
                    <th align="left" style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">Ouverture</th>
                    <th align="left" style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">Clic</th>
                  </tr>
                </thead>
                <tbody>
                  {rows_html}
                </tbody>
              </table>
            </div>

            <div style="margin-top:14px; font-size:12px; color:#6b7280;">
              Astuce : surveille les fortes variations de taux d'ouverture/clic pour identifier les séquences qui performent le mieux.
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def _build_campaigns_report_text(title, campagnes_stats):
    """Version texte brut du rapport de campagnes."""
    if not campagnes_stats:
        return f"{title}\n\nAucune campagne correspondante sur la période analysée."

    lines = [title, "", "Récapitulatif des campagnes :"]
    for cs in campagnes_stats:
        line = (
            f"- #{cs.get('id')} - {cs.get('nom') or ''} "
            f"(statut={cs.get('statut') or ''}, "
            f"emails={cs.get('total_emails')}, "
            f"open={cs.get('open_rate'):.1f}%, "
            f"click={cs.get('click_rate'):.1f}%)"
        )
        lines.append(line)
    return "\n".join(lines)


@celery.task
def send_campagnes_report_task(report_type='evening'):
    """
    Envoie un rapport email sur les dernières campagnes.

    - Si report_type == 'evening' :
        Rapporte les campagnes lancées le matin même (06h-12h, heure de Paris).
    - Si report_type == 'morning' :
        Rapporte les campagnes lancées la veille après-midi/soir (12h-23h59).

    Le rapport est envoyé à MAIL_DEFAULT_RECIPIENT.
    """
    from services.database.campagnes import CampagneManager

    now_paris = _get_paris_now()
    today = now_paris.date()

    if report_type == 'evening':
        start_local = datetime.combine(today, time(6, 0), tzinfo=now_paris.tzinfo)
        end_local = datetime.combine(today, time(12, 0), tzinfo=now_paris.tzinfo)
        title = f"Rapport campagnes - Matin du {today.strftime('%d/%m/%Y')}"
    else:  # 'morning'
        yesterday = today - timedelta(days=1)
        start_local = datetime.combine(yesterday, time(12, 0), tzinfo=now_paris.tzinfo)
        end_local = datetime.combine(yesterday, time(23, 59, 59), tzinfo=now_paris.tzinfo)
        title = f"Rapport campagnes - Après-midi/soir du {yesterday.strftime('%d/%m/%Y')}"

    start_utc_iso = _to_utc_iso(start_local)
    end_utc_iso = _to_utc_iso(end_local)

    campagne_manager = CampagneManager()
    campagnes = campagne_manager.get_campagnes_launched_between(start_utc_iso, end_utc_iso)

    campagnes_stats = []
    for c in campagnes:
        cid = c.get('id')
        if not cid:
            continue
        stats = campagne_manager.get_campagne_tracking_stats(cid)
        total_emails = int(stats.get('total_emails', 0) or 0)
        # Ne pas inclure les campagnes sans envoi réel : date_creation / scheduled_at peut
        # tomber dans la fenêtre alors qu'aucun email n'est encore enregistré (brouillon,
        # programmation, échec avant enregistrement, etc.) → sinon rapports à 0 partout.
        if total_emails < 1:
            continue
        campagnes_stats.append(
            {
                'id': cid,
                'nom': c.get('nom'),
                'statut': c.get('statut'),
                'total_emails': total_emails,
                'open_rate': stats.get('open_rate', 0.0),
                'click_rate': stats.get('click_rate', 0.0),
            }
        )

    if not campagnes_stats:
        logger.info(
            f"[Rapport campagnes] Aucun envoi : aucune campagne avec emails envoyés sur la période "
            f"({report_type}, {len(campagnes)} campagne(s) trouvée(s) sans lignes emails_envoyes)."
        )
        return {'success': True, 'count': 0, 'skipped': True, 'reason': 'no_sent_emails_in_window'}

    sender = EmailSender()
    subject = f"[ProspectLab] {title}"
    text_body = _build_campaigns_report_text(title, campagnes_stats)
    html_body = _build_campaigns_report_html(title, campagnes_stats)

    logger.info(f"[Rapport campagnes] Envoi du rapport '{title}' pour {len(campagnes_stats)} campagne(s)")
    result = sender.send_email(
        to=MAIL_DEFAULT_RECIPIENT,
        subject=subject,
        body=text_body,
        html_body=html_body,
    )
    logger.info(f"[Rapport campagnes] Résultat envoi: {result}")
    return {'success': result.get('success', False), 'count': len(campagnes_stats)}


def _load_stats_cache():
    """Charge le cache de stats de campagnes depuis le disque."""
    try:
        if STATS_CACHE_PATH.is_file():
            with STATS_CACHE_PATH.open('r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"[Campagnes stats cache] Impossible de charger le cache: {e}")
    return {}


def _save_stats_cache(cache):
    """Sauvegarde le cache de stats de campagnes sur le disque."""
    try:
        STATS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with STATS_CACHE_PATH.open('w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[Campagnes stats cache] Impossible d'écrire le cache: {e}")


@celery.task
def check_campaigns_significant_changes_task(
    open_rate_delta_threshold=5.0,
    click_rate_delta_threshold=2.0,
    stable_open_delta_threshold=1.0,
    stable_click_delta_threshold=0.5,
    stable_checks=3,
    min_emails_for_stability=5,
    other_cooldown_hours=12,
    report_day_start_hour=8,
    report_day_end_hour=20,
):
    """
    Monitoring étatful des campagnes :
    - Si une hausse est qualifiée (delta open/click >= seuils),
      on démarre une phase d'observation.
    - On n'envoie le rapport que quand le taux se stabilise :
      variations faibles pendant `stable_checks` exécutions consécutives.

    L'état (baseline / phase / compteur de stabilité) est conservé dans
    `logs/campagne_stats_cache.json` pour éviter les envois répétés.
    """
    from services.database.campagnes import CampagneManager

    campagne_manager = CampagneManager()
    # On regarde toutes les campagnes récentes (par exemple 60 derniers jours)
    # pour éviter de charger un historique énorme.
    now_paris = _get_paris_now()
    start_local = now_paris - timedelta(days=60)
    start_utc_iso = _to_utc_iso(start_local)
    end_utc_iso = _to_utc_iso(now_paris)

    campagnes = campagne_manager.get_campagnes_launched_between(start_utc_iso, end_utc_iso)

    # --- Nouveau monitoring : hausse qualifiée -> stabilisation -> 1er rapport ---
    cache = _load_stats_cache()
    candidates_latest = []
    candidates_others = []
    now_utc_iso = _to_utc_iso(now_paris)

    def _parse_iso_to_dt(value):
        """
        Parse une date ISO (avec éventuellement suffixe 'Z') en datetime timezone-aware.
        Retourne None si la date est invalide.
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except Exception:
            return None

    latest_cid_str = None
    try:
        latest_campaign = max(
            campagnes,
            key=lambda x: _parse_iso_to_dt(x.get('scheduled_at') or x.get('date_creation')) or datetime.min.replace(tzinfo=timezone.utc),
        )
        if latest_campaign and latest_campaign.get('id') is not None:
            latest_cid_str = str(latest_campaign.get('id'))
    except Exception:
        latest_cid_str = None

    for c in campagnes:
        cid = c.get('id')
        if not cid:
            continue
        cid_str = str(cid)

        stats = campagne_manager.get_campagne_tracking_stats(cid)
        total_emails = stats.get('total_emails', 0) or 0
        current_open = stats.get('open_rate', 0.0) or 0.0
        current_click = stats.get('click_rate', 0.0) or 0.0

        entry = cache.get(cid_str) or {}

        # Compatibilité avec anciens formats de cache
        if 'baseline_open_rate' not in entry:
            entry['baseline_open_rate'] = entry.get('open_rate', current_open) or current_open
            entry['baseline_click_rate'] = entry.get('click_rate', current_click) or current_click
            entry['triggered'] = False
            entry['stable_counter'] = 0
            entry['last_open_rate'] = entry.get('last_open_rate', current_open) or current_open
            entry['last_click_rate'] = entry.get('last_click_rate', current_click) or current_click
            entry['triggered_at'] = None
            entry['last_sent_at'] = entry.get('last_sent_at')

        entry['last_seen_at'] = now_utc_iso

        # Evite les faux signaux sur des campagnes avec trop peu de données.
        # Réinitialise l'état si la campagne repasse sous le seuil (données insuffisantes).
        if total_emails < min_emails_for_stability:
            entry['ready_to_send'] = False
            entry['triggered'] = False
            entry['stable_counter'] = 0
            entry['triggered_at'] = None
            cache[cid_str] = entry
            continue

        if not bool(entry.get('triggered', False)):
            baseline_open = float(entry.get('baseline_open_rate', current_open) or 0.0)
            baseline_click = float(entry.get('baseline_click_rate', current_click) or 0.0)

            delta_open = abs(current_open - baseline_open)
            delta_click = abs(current_click - baseline_click)

            entry['last_open_rate'] = current_open
            entry['last_click_rate'] = current_click

            # Hausse qualifiée : démarrer une fenêtre de stabilisation
            if delta_open >= open_rate_delta_threshold or delta_click >= click_rate_delta_threshold:
                entry['triggered'] = True
                entry['triggered_at'] = now_utc_iso
                entry['triggered_open_rate'] = current_open
                entry['triggered_click_rate'] = current_click
                entry['stable_counter'] = 0
        else:
            last_open = float(entry.get('last_open_rate', current_open) or 0.0)
            last_click = float(entry.get('last_click_rate', current_click) or 0.0)

            step_open_delta = abs(current_open - last_open)
            step_click_delta = abs(current_click - last_click)

            is_stable_step = (
                step_open_delta <= stable_open_delta_threshold
                and step_click_delta <= stable_click_delta_threshold
            )

            if is_stable_step:
                entry['stable_counter'] = int(entry.get('stable_counter', 0) or 0) + 1
            else:
                entry['stable_counter'] = 0

            entry['last_open_rate'] = current_open
            entry['last_click_rate'] = current_click

            if int(entry.get('stable_counter', 0) or 0) >= int(stable_checks) and not entry.get('ready_to_send', False):
                is_latest = (latest_cid_str is not None and cid_str == latest_cid_str)

                # Pour les autres campagnes : éviter d'envoyer trop souvent (écart plus espacé)
                if not is_latest:
                    last_sent_dt = _parse_iso_to_dt(entry.get('last_sent_at'))
                    if last_sent_dt:
                        cooldown_seconds = int(other_cooldown_hours * 3600)
                        if (datetime.now(timezone.utc) - last_sent_dt).total_seconds() < cooldown_seconds:
                            cache[cid_str] = entry
                            continue

                candidate = {
                    'cid_str': cid_str,
                    'id': cid,
                    'nom': c.get('nom') or '',
                    'statut': c.get('statut') or '',
                    'total_emails': total_emails,
                    'current_open': current_open,
                    'current_click': current_click,
                    'triggered_at': entry.get('triggered_at') or '',
                    'baseline_open': float(entry.get('baseline_open_rate', current_open) or 0.0),
                    'baseline_click': float(entry.get('baseline_click_rate', current_click) or 0.0),
                }

                # Marquer comme "prêt à envoyer" pour éviter des doublons tant qu'on n'a pas réellement envoyé
                entry['ready_to_send'] = True
                if is_latest:
                    candidates_latest.append(candidate)
                else:
                    candidates_others.append(candidate)

        cache[cid_str] = entry

    # Envoi uniquement en journée (heure Europe/Paris)
    # Exemple par défaut : [08:00 ; 20:00[
    is_daytime = int(now_paris.hour) >= int(report_day_start_hour) and int(now_paris.hour) < int(report_day_end_hour)

    # Construire la liste à envoyer à partir de l'état en cache,
    # pour gérer le cas "report déclenché la nuit => envoyé au prochain run".
    latest_ready = []
    others_ready = []
    for c in campagnes:
        cid = c.get('id')
        if not cid:
            continue
        cid_str = str(cid)
        entry = cache.get(cid_str) or {}
        if not bool(entry.get('ready_to_send', False)):
            continue

        stats_send = campagne_manager.get_campagne_tracking_stats(cid)
        te = int(stats_send.get('total_emails', 0) or 0)
        if te < min_emails_for_stability:
            # Cache obsolète ou campagne vidée : ne pas envoyer de rapport vide / incohérent
            entry['ready_to_send'] = False
            entry['triggered'] = False
            entry['stable_counter'] = 0
            cache[cid_str] = entry
            continue

        is_latest = (latest_cid_str is not None and cid_str == latest_cid_str)
        if is_latest:
            latest_ready.append(
                {
                    'cid_str': cid_str,
                    'id': cid,
                    'nom': c.get('nom') or '',
                    'statut': c.get('statut') or '',
                    'total_emails': te,
                    'current_open': float(entry.get('last_open_rate', 0.0) or 0.0),
                    'current_click': float(entry.get('last_click_rate', 0.0) or 0.0),
                }
            )
        else:
            # Le cooldown a été pris en compte lors du passage ready_to_send,
            # donc ici on n'applique pas un nouveau cooldown strict.
            others_ready.append(
                {
                    'cid_str': cid_str,
                    'id': cid,
                    'nom': c.get('nom') or '',
                    'statut': c.get('statut') or '',
                    'total_emails': te,
                    'current_open': float(entry.get('last_open_rate', 0.0) or 0.0),
                    'current_click': float(entry.get('last_click_rate', 0.0) or 0.0),
                }
            )

    # Persister l'état (1re boucle + invalidations ready_to_send de la 2e boucle)
    _save_stats_cache(cache)

    to_send = latest_ready if latest_ready else others_ready

    if not is_daytime:
        if to_send:
            logger.info(
                f"[Campagnes stabilization] Nuit : report prêt à envoyer différé ({len(to_send)} campagne(s))."
            )
        else:
            logger.info("[Campagnes stabilization] Nuit : aucun report prêt à envoyer.")
        # Important: on ne reset pas l'état, ready_to_send reste à True.
        return {'success': True, 'changes': 0, 'deferred': bool(to_send)}

    # Reset uniquement pour les campagnes réellement envoyées (sinon on perd l'état)
    for ch in to_send:
        cid_str = ch.get('cid_str')
        if not cid_str or cid_str not in cache:
            continue
        entry = cache[cid_str]
        entry['last_sent_at'] = now_utc_iso
        entry['baseline_open_rate'] = ch.get('current_open', entry.get('baseline_open_rate'))
        entry['baseline_click_rate'] = ch.get('current_click', entry.get('baseline_click_rate'))
        entry['triggered'] = False
        entry['stable_counter'] = 0
        entry['ready_to_send'] = False
        entry['triggered_at'] = None
        entry['triggered_open_rate'] = None
        entry['triggered_click_rate'] = None
        cache[cid_str] = entry

    _save_stats_cache(cache)

    if not to_send:
        logger.info("[Campagnes stabilization] Aucun rapport à envoyer.")
        return {'success': True, 'changes': 0}

    title = f"Campagnes - rapport de stabilisation ({len(to_send)} campagne(s))"
    lines = [title, ""]
    for ch in to_send:
        lines.append(
            f"- #{ch['id']} - {ch.get('nom') or ''} "
            f"(emails={ch['total_emails']}, open={ch['current_open']:.1f}% click={ch['current_click']:.1f}%)"
        )
    text_body = "\n".join(lines)

    # HTML simple (évite de ré-injecter des données personnelles détaillées)
    rows_html = ""
    for ch in to_send:
        rows_html += f"""
          <tr>
            <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">{ch['id']}</td>
            <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb;">{ch.get('nom') or ''}</td>
            <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb; text-align:center;">{ch['total_emails']}</td>
            <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb; text-align:center; color:#16a34a; font-weight:600;">{ch['current_open']:.1f}%</td>
            <td style="padding:8px 10px; border-bottom:1px solid #e5e7eb; text-align:center; color:#2563eb; font-weight:600;">{ch['current_click']:.1f}%</td>
          </tr>
        """

    html_body = f"""
    <html>
      <body style="margin:0; padding:24px; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif; background:#f3f4f6; color:#111827;">
        <div style="max-width:840px; margin:0 auto; background:#ffffff; border-radius:16px; box-shadow:0 18px 40px rgba(15,23,42,0.10); overflow:hidden; border:1px solid #e5e7eb;">
          <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6); padding:18px 22px; color:#fff;">
            <div style="font-size:13px; opacity:0.92; margin-bottom:4px;">ProspectLab</div>
            <div style="font-size:18px; font-weight:600;">Rapport de stabilisation</div>
          </div>
          <div style="padding:16px 22px 22px;">
            <table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse; font-size:13px;">
              <thead>
                <tr style="background:#f3f4f6;">
                  <th style="padding:10px 10px; border-bottom:1px solid #e5e7eb; text-align:left; color:#374151;">ID</th>
                  <th style="padding:10px 10px; border-bottom:1px solid #e5e7eb; text-align:left; color:#374151;">Nom</th>
                  <th style="padding:10px 10px; border-bottom:1px solid #e5e7eb; text-align:center; color:#374151;">Emails</th>
                  <th style="padding:10px 10px; border-bottom:1px solid #e5e7eb; text-align:center; color:#374151;">Open</th>
                  <th style="padding:10px 10px; border-bottom:1px solid #e5e7eb; text-align:center; color:#374151;">Click</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """

    sender = EmailSender()
    subject = "[ProspectLab] " + title
    logger.info(f"[Campagnes stabilization] Envoi d'un rapport pour {len(to_send)} campagne(s)")
    result = sender.send_email(
        to=MAIL_DEFAULT_RECIPIENT,
        subject=subject,
        body=text_body,
        html_body=html_body,
    )
    logger.info(f"[Campagnes stabilization] Résultat envoi: {result}")
    return {'success': result.get('success', False), 'changes': len(to_send)}

    # --- Ancien code (inatteignable car return ci-dessus) ---
    cache = _load_stats_cache()
    changed = []

    for c in campagnes:
        cid = c.get('id')
        if not cid:
            continue
        stats = campagne_manager.get_campagne_tracking_stats(cid)
        current = {
            'open_rate': stats.get('open_rate', 0.0),
            'click_rate': stats.get('click_rate', 0.0),
            'total_emails': stats.get('total_emails', 0),
        }

        prev = cache.get(str(cid))
        if prev:
            delta_open = abs(current['open_rate'] - prev.get('open_rate', 0.0))
            delta_click = abs(current['click_rate'] - prev.get('click_rate', 0.0))
            if delta_open >= open_rate_delta_threshold or delta_click >= click_rate_delta_threshold:
                changed.append(
                    {
                        'id': cid,
                        'nom': c.get('nom'),
                        'statut': c.get('statut'),
                        'total_emails': current['total_emails'],
                        'open_rate': current['open_rate'],
                        'click_rate': current['click_rate'],
                        'prev_open_rate': prev.get('open_rate', 0.0),
                        'prev_click_rate': prev.get('click_rate', 0.0),
                        'delta_open': delta_open,
                        'delta_click': delta_click,
                    }
                )

        # Mettre à jour le cache systématiquement
        cache[str(cid)] = current

    _save_stats_cache(cache)

    if not changed:
        logger.info("[Campagnes changes] Aucun changement significatif détecté.")
        return {'success': True, 'changes': 0}

    # Construire le rapport des changements
    title = "Campagnes - changements significatifs détectés"
    lines = [title, "", "Campagnes impactées :"]
    for ch in changed:
        lines.append(
            (
                f"- #{ch['id']} - {ch.get('nom') or ''} "
                f"(emails={ch['total_emails']}, "
                f"open: {ch['prev_open_rate']:.1f}% -> {ch['open_rate']:.1f}% (Δ={ch['delta_open']:.1f}), "
                f"click: {ch['prev_click_rate']:.1f}% -> {ch['click_rate']:.1f}% (Δ={ch['delta_click']:.1f}))"
            )
        )
    text_body = "\n".join(lines)

    rows_html = ""
    for ch in changed:
        rows_html += f"""
          <tr>
            <td>{ch['id']}</td>
            <td>{ch.get('nom') or ''}</td>
            <td>{ch.get('statut') or ''}</td>
            <td>{ch['total_emails']}</td>
            <td>{ch['prev_open_rate']:.1f}%</td>
            <td>{ch['open_rate']:.1f}%</td>
            <td>{ch['prev_click_rate']:.1f}%</td>
            <td>{ch['click_rate']:.1f}%</td>
          </tr>
        """

    html_body = f"""
    <html>
      <body>
        <h2>{title}</h2>
        <p>Les campagnes suivantes ont vu leurs performances évoluer de manière significative depuis la dernière vérification.</p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif; font-size: 13px;">
          <thead style="background-color: #f0f0f0;">
            <tr>
              <th>ID</th>
              <th>Nom</th>
              <th>Statut</th>
              <th>Emails envoyés</th>
              <th>Open (préc.)</th>
              <th>Open (actuel)</th>
              <th>Click (préc.)</th>
              <th>Click (actuel)</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </body>
    </html>
    """

    sender = EmailSender()
    subject = "[ProspectLab] " + title
    logger.info(f"[Campagnes changes] Envoi du rapport de changements pour {len(changed)} campagne(s)")
    result = sender.send_email(
        to=MAIL_DEFAULT_RECIPIENT,
        subject=subject,
        body=text_body,
        html_body=html_body,
    )
    logger.info(f"[Campagnes changes] Résultat envoi: {result}")
    return {'success': result.get('success', False), 'changes': len(changed)}
