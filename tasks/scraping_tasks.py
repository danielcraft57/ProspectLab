"""
Tâches Celery pour le scraping de sites web

Ces tâches permettent d'exécuter le scraping de manière asynchrone,
évitant ainsi de bloquer l'application Flask principale.
"""

import time

from celery_app import celery
from services.unified_scraper import UnifiedScraper, merge_scraper_metadata_for_storage
from services.database import Database
from services.logging_config import setup_logger
from services.name_validator import is_valid_human_name, validate_name_pair
import logging
import os
import json
from typing import Callable, Dict, Optional

# Configurer le logger pour cette tâche (niveau INFO pour limiter le bruit)
logger = setup_logger(__name__, 'scraping_tasks.log', level=logging.INFO)

from tasks.heavy_schedule import BulkSubtaskStagger
from tasks.phone_tasks import analyze_phones_dict_for_storage

try:
    from config import CELERY_BULK_STAGGER_SEC, SEO_USE_LIGHTHOUSE_DEFAULT
except ImportError:
    CELERY_BULK_STAGGER_SEC = 0.75
    SEO_USE_LIGHTHOUSE_DEFAULT = False

_SCRAPE_ANALYSIS_BATCH_SIZE = max(1, int(os.environ.get('SCRAPE_ANALYSIS_BATCH_SIZE', '20')))
_SCRAPE_ANALYSIS_BATCH_RETRY_MAX = max(0, int(os.environ.get('SCRAPE_ANALYSIS_BATCH_RETRY_MAX', '1')))


# Verrou global optionnel (désactivé par défaut) : si activé, un seul scrape à la fois sur tout le cluster.
# Par défaut : parallélisme = Celery worker (--concurrency) + étalement côté enqueue, comme avant.
def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None or str(v).strip() == '':
        return default
    return str(v).strip().lower() in ('1', 'true', 'yes', 'on')


_SCRAPING_GLOBAL_LOCK_ENABLED = _env_bool('SCRAPING_GLOBAL_LOCK_ENABLED', False)

_SCRAPING_LOCK_KEY = os.environ.get('SCRAPING_LOCK_KEY', 'prospectlab:lock:scraping:global')
_SCRAPING_LOCK_TTL_SEC = int(os.environ.get('SCRAPING_LOCK_TTL_SEC', '3600'))
_SCRAPING_LOCK_RETRY_SEC = float(os.environ.get('SCRAPING_LOCK_RETRY_SEC', '10'))
# Attente du verrou dans la même exécution Celery (pas de self.retry() : évite MaxRetriesExceeded en bulk).
try:
    _SCRAPING_LOCK_WAIT_MAX_SEC = int(os.environ.get('SCRAPING_LOCK_WAIT_MAX_SEC', str(86400)))
except ValueError:
    _SCRAPING_LOCK_WAIT_MAX_SEC = 86400
_SCRAPING_LOCK_WAIT_MAX_SEC = max(int(_SCRAPING_LOCK_RETRY_SEC) * 2, _SCRAPING_LOCK_WAIT_MAX_SEC)

_redis_lock_client = None
_redis_lock_release_script = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
"""


def _redis_lock():
    global _redis_lock_client
    if _redis_lock_client is None:
        import redis
        from config import CELERY_BROKER_URL

        _redis_lock_client = redis.Redis.from_url(
            CELERY_BROKER_URL,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
    return _redis_lock_client


def _acquire_scraping_lock(lock_value: str) -> bool:
    r = _redis_lock()
    return bool(r.set(_SCRAPING_LOCK_KEY, lock_value, nx=True, ex=_SCRAPING_LOCK_TTL_SEC))


def _release_scraping_lock(lock_value: str) -> None:
    r = _redis_lock()
    try:
        r.eval(_redis_lock_release_script, 1, _SCRAPING_LOCK_KEY, lock_value)
    except Exception:
        # Si Redis est instable, on évite d'écraser l'exécution de la tâche.
        pass


def _wait_acquire_scraping_lock(lock_value: str, task_self=None, wait_label: str = 'Scraping') -> bool:
    """
    Attend le verrou Redis sans utiliser Celery retry (sinon max_retries épuisé sur les gros bulk).

    Returns:
        True si le verrou a été acquis, False si délai max dépassé.
    """
    deadline = time.monotonic() + float(_SCRAPING_LOCK_WAIT_MAX_SEC)
    logged_wait = False
    last_meta = 0.0

    while time.monotonic() < deadline:
        if _acquire_scraping_lock(lock_value):
            return True
        if not logged_wait:
            logger.info(
                f'{wait_label}: verrou déjà pris, attente active (file « un à un », '
                f'jusqu’à {_SCRAPING_LOCK_WAIT_MAX_SEC}s)...'
            )
            logged_wait = True
        now = time.monotonic()
        if task_self is not None and (now - last_meta) >= 30.0:
            last_meta = now
            try:
                task_self.update_state(
                    state='PROGRESS',
                    meta={'message': 'En file d’attente (scraping global, verrou)...'},
                )
            except Exception:
                pass
        time.sleep(_SCRAPING_LOCK_RETRY_SEC)

    logger.warning(
        f'{wait_label}: délai max d’attente sur le verrou global dépassé ({_SCRAPING_LOCK_WAIT_MAX_SEC}s).'
    )
    return False


def _safe_update_state(task, task_id, **kwargs):
    """
    Met à jour l'état d'une tâche Celery seulement si un task_id est disponible.
    
    Args:
        task: Instance de la tâche Celery (bindée avec bind=True)
        task_id: ID connu de la tâche (optionnel, utilisé pour vérification)
        **kwargs: Arguments passés à update_state (state, meta, etc.)
    """
    try:
        # Pour une tâche bindée, task.request.id devrait être disponible
        # Si ce n'est pas le cas, on essaie avec task_id en paramètre
        if hasattr(task, 'request') and hasattr(task.request, 'id') and task.request.id:
            # La tâche est bindée et a un ID, on peut utiliser update_state directement
            task.update_state(**kwargs)
        elif task_id:
            # On a un task_id en paramètre, on peut quand même essayer
            task.update_state(**kwargs)
        else:
            # Pas de task_id disponible, on ne peut pas mettre à jour l'état
            # On ne log pas pour éviter de polluer les logs
            return
    except Exception as exc:
        # Ne log que si ce n'est pas une erreur de task_id vide
        if 'task_id' not in str(exc).lower() and 'empty' not in str(exc).lower():
            logger.warning(f'update_state impossible: {exc}')


def _build_email_analyses_dict(emails_found, source_url: str, log_prefix: str = '') -> Dict:
    """Analyse les emails scrapés (MX, Hunter, Abstract, etc.) pour la persistance scraper_emails."""
    email_analyses: Dict = {}
    if not emails_found:
        return email_analyses
    prefix = f'{log_prefix} ' if log_prefix else ''
    logger.info(f'{prefix}{len(emails_found)} email(s) trouvé(s), lancement de l\'analyse...')
    try:
        from services.email_analyzer import EmailAnalyzer

        emails_list = []
        for email in emails_found:
            if isinstance(email, dict):
                email_str = email.get('email') or email.get('value') or str(email)
            else:
                email_str = str(email)
            if email_str:
                emails_list.append(email_str)

        analyzer = EmailAnalyzer()
        analyzed_count = 0
        for idx, email_str in enumerate(emails_list, start=1):
            try:
                logger.debug(f'{prefix}Analyse de {email_str} ({idx}/{len(emails_list)})')
                analysis = analyzer.analyze_email(email_str, source_url=source_url)
                if analysis:
                    email_analyses[email_str] = analysis
                    analyzed_count += 1
                    logger.debug(
                        f'{prefix}✓ {email_str} analysé: type={analysis.get("type")}, '
                        f'provider={analysis.get("provider")}, mx_valid={analysis.get("mx_valid")}'
                    )
            except Exception as email_error:
                logger.warning(f'{prefix}Erreur lors de l\'analyse de {email_str}: {email_error}')

        logger.info(
            f'{prefix}Analyse des emails terminée: {analyzed_count}/{len(emails_list)} analysé(s)'
        )
    except Exception as email_error:
        logger.error(f'{prefix}Erreur lors de l\'analyse des emails: {email_error}', exc_info=True)
    return email_analyses


def _persist_personnes_from_email_analyses(db, entreprise_id: int, email_analyses: Dict, log_context: str) -> int:
    """Enregistre les contacts détectés depuis les analyses d'emails (table personnes)."""
    if not email_analyses:
        return 0
    people_saved = 0
    for email_str, analysis in email_analyses.items():
        if not analysis.get('is_person') or not analysis.get('name_info'):
            continue
        name_info = analysis['name_info']
        first_name = name_info.get('first_name')
        last_name = name_info.get('last_name')
        if not (first_name and last_name):
            continue
        validated = validate_name_pair(first_name, last_name)
        if not validated:
            full_name = f'{first_name} {last_name}'
            if not is_valid_human_name(full_name):
                logger.debug(
                    f'{log_context} ⚠ Nom invalide ignoré depuis email: '
                    f'{first_name} {last_name} ({email_str})'
                )
                continue
            if not is_valid_human_name(first_name) or not is_valid_human_name(last_name):
                logger.debug(
                    f'{log_context} ⚠ Nom invalide ignoré depuis email: '
                    f'{first_name} {last_name} ({email_str})'
                )
                continue
        else:
            first_name, last_name = validated
        try:
            db.save_personne(
                entreprise_id=entreprise_id,
                prenom=first_name,
                nom=last_name,
                email=email_str,
                source='scraper_email',
            )
            people_saved += 1
            logger.debug(
                f'{log_context} ✓ Personne enregistrée: {first_name} {last_name} ({email_str})'
            )
        except Exception as person_error:
            logger.warning(
                f'{log_context} ⚠ Erreur enregistrement personne {first_name} {last_name}: {person_error}'
            )
    if people_saved > 0:
        logger.info(f'{log_context} ✓ {people_saved} personne(s) enregistrée(s) depuis les emails')
    return people_saved


@celery.task(
    name='tasks.scraping_tasks.enrich_external_links_mini_scrape_task',
    queue='mini_scrape',
)
def enrich_external_links_mini_scrape_task(entreprise_id: int, scraper_id: int):
    """
    Mini-scrape asynchrone (Celery, file « mini_scrape ») des domaines externes après sauvegarde du scraper.
    Met à jour ``metadata.external_links`` puis ``web_external_links``.
    """
    from services.external_mini_scraper import enrich_external_links_in_place
    from utils.celery_socketio_emit import emit_from_celery_worker

    logger.info(
        '[enrich_external_links_mini_scrape] démarrage entreprise_id=%s scraper_id=%s',
        entreprise_id,
        scraper_id,
    )

    if not entreprise_id or not scraper_id:
        logger.warning('[enrich_external_links_mini_scrape] paramètres manquants')
        return {'ok': False, 'error': 'paramètres manquants'}

    db = Database()
    row = db.get_scraper_by_id(scraper_id)
    if not row:
        logger.warning('[enrich_external_links_mini_scrape] scraper_id=%s introuvable', scraper_id)
        return {'ok': False, 'error': 'scraper introuvable'}
    if int(row.get('entreprise_id') or 0) != int(entreprise_id):
        logger.warning(
            '[enrich_external_links_mini_scrape] entreprise_id incohérent (attendu %s, scraper %s)',
            entreprise_id,
            row.get('entreprise_id'),
        )
        return {'ok': False, 'error': 'entreprise_id incohérent'}

    md = row.get('metadata')
    if not isinstance(md, dict):
        logger.info('[enrich_external_links_mini_scrape] ignoré: metadata absente scraper_id=%s', scraper_id)
        emit_from_celery_worker(
            'external_mini_scrape_complete',
            {
                'entreprise_id': int(entreprise_id),
                'scraper_id': int(scraper_id),
                'skipped': True,
                'reason': 'metadata absente',
            },
        )
        return {'ok': True, 'skipped': True, 'reason': 'metadata absente'}

    ext = md.get('external_links')
    if not ext or not isinstance(ext, list):
        logger.info('[enrich_external_links_mini_scrape] ignoré: pas de external_links scraper_id=%s', scraper_id)
        emit_from_celery_worker(
            'external_mini_scrape_complete',
            {
                'entreprise_id': int(entreprise_id),
                'scraper_id': int(scraper_id),
                'skipped': True,
                'reason': 'pas de external_links',
            },
        )
        return {'ok': True, 'skipped': True, 'reason': 'pas de external_links'}

    co = (
        os.environ.get('EXTERNAL_MINI_SCRAPE_CREDIT_ONLY')
        or os.environ.get('AGENCY_MINI_SCRAPE_CREDIT_ONLY')
        or ''
    )
    credit_only = str(co).strip().lower() in ('1', 'true', 'yes', 'on')
    if credit_only and not any(isinstance(x, dict) and x.get('likely_credit') for x in ext):
        logger.info(
            '[enrich_external_links_mini_scrape] ignoré: CREDIT_ONLY sans lien likely_credit scraper_id=%s',
            scraper_id,
        )
        emit_from_celery_worker(
            'external_mini_scrape_complete',
            {
                'entreprise_id': int(entreprise_id),
                'scraper_id': int(scraper_id),
                'skipped': True,
                'reason': 'CREDIT_ONLY',
            },
        )
        return {'ok': True, 'skipped': True, 'reason': 'pas de crédit à enrichir (CREDIT_ONLY)'}

    n_links = len([x for x in ext if isinstance(x, dict)])
    logger.info(
        '[enrich_external_links_mini_scrape] mini-scrape sur %s entrée(s) external_links scraper_id=%s',
        n_links,
        scraper_id,
    )

    emit_from_celery_worker(
        'external_mini_scrape_started',
        {
            'entreprise_id': int(entreprise_id),
            'scraper_id': int(scraper_id),
            'external_links_count': n_links,
        },
    )

    n_dom = enrich_external_links_in_place(ext)
    md['external_links'] = ext

    try:
        db.update_scraper_metadata_json(scraper_id, md)
    except Exception as e:
        logger.error('[enrich_external_links_mini_scrape] metadata %s', e, exc_info=True)
        emit_from_celery_worker(
            'external_mini_scrape_complete',
            {
                'entreprise_id': int(entreprise_id),
                'scraper_id': int(scraper_id),
                'ok': False,
                'error': str(e),
            },
        )
        return {'ok': False, 'error': str(e)}

    client_url = row.get('url') or ''
    try:
        db.replace_web_external_links_for_scraper(
            entreprise_id, scraper_id, client_url, ext
        )
    except Exception as e:
        logger.warning('[enrich_external_links_mini_scrape] web_external_links %s', e)

    logger.info(
        '[enrich_external_links_mini_scrape] terminé entreprise_id=%s scraper_id=%s domaines_scannés=%s',
        entreprise_id,
        scraper_id,
        n_dom,
    )
    domains_payload = []
    try:
        seen_domains = set()
        for it in ext:
            if not isinstance(it, dict):
                continue
            dom = str(it.get('domain') or '').strip().lower()
            if not dom or dom in seen_domains:
                continue
            seen_domains.add(dom)
            snap = it.get('external_snapshot') if isinstance(it.get('external_snapshot'), dict) else {}
            payload = {
                'domain_host': dom,
                'external_href': str(it.get('url') or '').strip(),
                'target_entreprise_id': int(it.get('target_entreprise_id') or 0) or None,
                'site_title': str(snap.get('title') or '').strip(),
                'site_description': str(snap.get('description') or '').strip(),
                'resolved_url': str(snap.get('final_url') or '').strip(),
                'thumb_url': str(snap.get('favicon_url') or '').strip(),
            }
            domains_payload.append(payload)
            # Un emit par domaine mini-scrapé terminé: sert de source unique
            # pour créer nœud + lien en temps réel côté graphe.
            try:
                emit_from_celery_worker(
                    'external_mini_scrape_domain_complete',
                    {
                        'entreprise_id': int(entreprise_id),
                        'scraper_id': int(scraper_id),
                        'domain': payload,
                    },
                )
            except Exception:
                pass
    except Exception:
        domains_payload = []

    emit_from_celery_worker(
        'external_mini_scrape_complete',
        {
            'entreprise_id': int(entreprise_id),
            'scraper_id': int(scraper_id),
            'ok': True,
            'domains_scanned': int(n_dom or 0),
            'domains': domains_payload[:120],
        },
    )
    return {'ok': True, 'domains_scanned': n_dom}


def schedule_enrich_external_links_mini_scrape(entreprise_id: int, scraper_id: int) -> None:
    """Enfile la tâche Celery (désactivable via EXTERNAL_MINI_SCRAPE_DISABLE_CELERY=1)."""
    if _env_bool('EXTERNAL_MINI_SCRAPE_DISABLE_CELERY', False) or _env_bool(
        'AGENCY_MINI_SCRAPE_DISABLE_CELERY', False
    ):
        return
    if not entreprise_id or not scraper_id:
        return
    try:
        enrich_external_links_mini_scrape_task.delay(int(entreprise_id), int(scraper_id))
    except Exception as e:
        logger.warning('Impossible d\'enfiler enrich_external_links_mini_scrape: %s', e)


def run_scrape_emails_inline(
    url: str,
    max_depth: int = 3,
    max_workers: int = 5,
    max_time: int = 300,
    max_pages: int = 50,
    on_email_found=None,
    on_person_found=None,
    on_phone_found=None,
    on_social_found=None,
    on_external_link_found=None,
    entreprise_id=None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict:
    """
    Corps du scraping (UnifiedScraper + persistance BDD), utilisable sans broker Celery
    (fallback Socket.IO en développement).
    """
    logger.info(f'Démarrage du scraping pour {url}')

    scraper = UnifiedScraper(
        base_url=url,
        max_workers=max_workers,
        max_depth=max_depth,
        max_time=max_time,
        max_pages=max_pages,
        progress_callback=progress_callback,
        on_email_found=on_email_found,
        on_person_found=on_person_found,
        on_phone_found=on_phone_found,
        on_social_found=on_social_found,
        on_external_link_found=on_external_link_found,
    )

    results = scraper.scrape()

    scraper_id = None
    if entreprise_id:
        try:
            db = Database()
            social_profiles = results.get('social_links')
            visited_urls = results.get('visited_urls', 0)
            if isinstance(visited_urls, list):
                visited_urls_count = len(visited_urls)
            else:
                visited_urls_count = visited_urls or 0

            metadata_value = merge_scraper_metadata_for_storage(
                results.get('metadata'),
                results.get('external_links'),
                results.get('scraped_location'),
            )
            metadata_total = len(metadata_value) if isinstance(metadata_value, dict) else 0

            emails_found = results.get('emails') or []
            email_analyses = _build_email_analyses_dict(
                emails_found,
                url,
                log_prefix=f'[Relance scraping entreprise_id={entreprise_id}]',
            )

            phone_analyses = {}
            phones_found = results.get('phones') or []
            if phones_found:
                phone_analyses = analyze_phones_dict_for_storage(phones_found, source_url=url)

            scraper_id = db.save_scraper(
                entreprise_id=entreprise_id,
                url=url,
                scraper_type='unified_scraper',
                emails=results.get('emails'),
                people=results.get('people'),
                phones=results.get('phones'),
                social_profiles=social_profiles,
                technologies=results.get('technologies'),
                metadata=metadata_value,
                images=results.get('images'),
                forms=results.get('forms'),
                visited_urls=visited_urls_count,
                total_emails=results.get('total_emails', 0),
                total_people=results.get('total_people', 0),
                total_phones=results.get('total_phones', 0),
                total_social_profiles=results.get('total_social_platforms', 0),
                total_technologies=results.get('total_technologies', 0),
                total_metadata=metadata_total,
                total_images=results.get('total_images', 0),
                total_forms=results.get('total_forms', 0),
                duration=results.get('duration', 0),
                email_analyses=email_analyses if email_analyses else None,
                phone_analyses=phone_analyses if phone_analyses else None,
            )
            try:
                db.replace_web_external_links_for_scraper(
                    entreprise_id=entreprise_id,
                    scraper_id=scraper_id,
                    client_site_url=url,
                    external_links=results.get('external_links'),
                )
            except Exception as wce:
                logger.warning('web_external_links (relance scrape): %s', wce)
            schedule_enrich_external_links_mini_scrape(entreprise_id, scraper_id)
            _persist_personnes_from_email_analyses(
                db,
                entreprise_id,
                email_analyses,
                f'[Relance scraping entreprise_id={entreprise_id}]',
            )
            try:
                if db.patch_entreprise_location_from_scrape(entreprise_id, results.get('scraped_location')):
                    logger.info(
                        f'[Relance scraping entreprise_id={entreprise_id}] Fiche : adresse / lieu complétés depuis le scraping'
                    )
            except Exception as loc_e:
                logger.warning('patch_entreprise_location (relance scrape): %s', loc_e)
        except Exception as e:
            logger.warning(f'Erreur lors de la sauvegarde du scraper pour {url}: {e}')

    logger.info(f'Scraping terminé pour {url}: {len(results.get("emails", []))} emails trouvés')

    return {
        'success': True,
        'url': url,
        'results': results,
        'entreprise_id': entreprise_id,
        'scraper_id': scraper_id,
    }


@celery.task(bind=True)
def scrape_emails_task(self, url, max_depth=3, max_workers=5, max_time=300, 
                       max_pages=50, on_email_found=None, on_person_found=None,
                       on_phone_found=None, on_social_found=None, entreprise_id=None):
    """
    Tâche Celery pour scraper les emails d'un site web
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        url (str): URL de départ pour le scraping
        max_depth (int): Profondeur maximale de navigation (défaut: 3)
        max_workers (int): Nombre de threads parallèles (défaut: 5)
        max_time (int): Temps maximum en secondes (défaut: 300)
        max_pages (int): Nombre maximum de pages à scraper (défaut: 50)
        on_email_found (callable, optional): Callback quand un email est trouvé
        on_person_found (callable, optional): Callback quand une personne est trouvée
        on_phone_found (callable, optional): Callback quand un téléphone est trouvé
        on_social_found (callable, optional): Callback quand un réseau social est trouvé
        entreprise_id (int, optional): ID de l'entreprise pour sauvegarder en BDD
        
    Returns:
        dict: Résultats du scraping avec emails, personnes, téléphones, etc.
        
    Example:
        >>> result = scrape_emails_task.delay('https://example.com')
        >>> result.get()  # Attendre le résultat
    """
    lock_value = str(getattr(self.request, "id", None) or id(self))
    lock_acquired = False
    try:
        if _SCRAPING_GLOBAL_LOCK_ENABLED:
            if not _wait_acquire_scraping_lock(lock_value, task_self=self, wait_label='Scraping'):
                return {
                    'success': False,
                    'url': url,
                    'entreprise_id': entreprise_id,
                    'error': 'scraping_lock_wait_timeout',
                    'results': {},
                }
            lock_acquired = True

        def progress_callback(message):
            self.update_state(state='PROGRESS', meta={'message': message})

        return run_scrape_emails_inline(
            url=url,
            max_depth=max_depth,
            max_workers=max_workers,
            max_time=max_time,
            max_pages=max_pages,
            on_email_found=on_email_found,
            on_person_found=on_person_found,
            on_phone_found=on_phone_found,
            on_social_found=on_social_found,
            entreprise_id=entreprise_id,
            progress_callback=progress_callback,
        )
    except Exception as e:
        logger.error(f'Erreur lors du scraping de {url}: {e}', exc_info=True)
        raise
    finally:
        if lock_acquired:
            _release_scraping_lock(lock_value)


@celery.task(bind=True)
def scrape_analysis_task(self, analysis_id: int, max_depth: int = 2, max_workers: int = 5,
                         max_time: int = 180, max_pages: int = 30,
                         entreprise_ids: list | None = None) -> Dict:
    """
    Tâche Celery pour scraper automatiquement toutes les entreprises d'une analyse.
    
    Cette tâche utilise UnifiedScraper pour chaque entreprise ayant un site web,
    sauvegarde les résultats complets en base (emails, personnes, téléphones,
    réseaux sociaux, technologies, métadonnées, images) et remonte une
    progression détaillée.
    
    Args:
        self: Instance de la tâche Celery (bind=True)
        analysis_id (int): ID de l'analyse (table analyses)
        max_depth (int): Profondeur maximale de navigation
        max_workers (int): Nombre de workers parallèles
        max_time (int): Temps max par site en secondes
        max_pages (int): Nombre max de pages par site
    
    Returns:
        dict: Statistiques globales du scraping pour cette analyse.
    """
    logger.info(f'Demarrage du scraping pour l analyse {analysis_id}')

    # Verrou global optionnel pour le pack analyse (même interrupteur que scrape_emails_task).
    lock_value = str(getattr(self.request, 'id', None) or id(self))
    lock_acquired = False
    if _SCRAPING_GLOBAL_LOCK_ENABLED:
        if not _wait_acquire_scraping_lock(
            lock_value, task_self=self, wait_label=f'Scraping pack analyse {analysis_id}'
        ):
            return {
                'success': False,
                'analysis_id': analysis_id,
                'error': 'scraping_lock_wait_timeout',
                'scraped_count': 0,
                'stats': {},
            }
        lock_acquired = True

    task_id = getattr(self.request, 'id', None)
    if not task_id:
        logger.debug('task_id introuvable au demarrage de scrape_analysis_task')
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    db.execute_sql(
        cursor,
        '''
        SELECT id, nom, website
        FROM entreprises
        WHERE analyse_id = ?
          AND website IS NOT NULL
          AND TRIM(website) <> ''
        ''',
        (analysis_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    if entreprise_ids:
        allowed = set()
        for rid in entreprise_ids:
            try:
                allowed.add(int(rid))
            except Exception:
                continue
        filtered_rows = []
        for row in rows:
            try:
                row_id = row.get('id') if isinstance(row, dict) else row[0]
                if row_id is not None and int(row_id) in allowed:
                    filtered_rows.append(row)
            except Exception:
                continue
        rows = filtered_rows
    
    if not rows:
        logger.info(f'Aucune entreprise avec website pour l analyse {analysis_id}')
        if lock_acquired:
            _release_scraping_lock(lock_value)
        return {
            'success': True,
            'analysis_id': analysis_id,
            'scraped_count': 0,
            'stats': {
                'total_emails': 0,
                'total_people': 0,
                'total_phones': 0,
                'total_social_platforms': 0,
                'total_technologies': 0,
                'total_images': 0
            }
        }
    
    total = len(rows)
    scraped_count = 0
    global_stats = {
        'total_emails': 0,
        'total_people': 0,
        'total_phones': 0,
        'total_social_platforms': 0,
        'total_technologies': 0,
        'total_images': 0
    }
    tech_tasks = []   # Stocker les tâches d'analyse technique lancées
    osint_tasks = []  # Stocker les tâches d'analyse OSINT lancées
    pentest_tasks = []  # Stocker les tâches d'analyse Pentest lancées
    seo_tasks = []    # Stocker les tâches d'analyse SEO lancées
    screenshot_tasks = []  # Stocker les tâches de screenshots lancées

    # Compteur partagé : technique + OSINT + SEO + Pentest (évite de poster 200 tâches instantanément)
    bulk_stagger = BulkSubtaskStagger()
    
    # Lancer les analyses techniques avec étalement (countdown) — pas toutes en même tick
    from tasks.technical_analysis_tasks import technical_analysis_task
    logger.info(
        f'[Scraping Analyse {analysis_id}] Planification des analyses techniques '
        f'({CELERY_BULK_STAGGER_SEC}s entre chaque sous-tâche)...'
    )
    for row in rows:
        # Gérer les dictionnaires PostgreSQL et les tuples SQLite
        if isinstance(row, dict):
            entreprise_id = row.get('id')
            nom = row.get('nom')
            website = row.get('website')
        else:
            entreprise_id, nom, website = row
        website_str = str(website or '').strip()
        entreprise_name = nom or 'Entreprise inconnue'

        # Valider l'URL de base
        if website_str and website_str != 'website':
            try:
                from urllib.parse import urlparse
                parsed = urlparse(website_str)
                if parsed.scheme and parsed.netloc:
                    # URL valide
                    pass
                else:
                    # Essayer d'ajouter http:// si c'est juste un domaine
                    if '.' in website_str and ' ' not in website_str:
                        website_str = f'https://{website_str}'
                        logger.info(f'[Scraping Analyse {analysis_id}] URL corrigée: {website_str}')
                    else:
                        logger.warning(f'[Scraping Analyse {analysis_id}] URL invalide ignorée: {website_str}')
                        website_str = None
            except Exception as e:
                logger.warning(f'[Scraping Analyse {analysis_id}] Erreur validation URL {website_str}: {e}')
                website_str = None

        if website_str:
            try:
                cd = bulk_stagger.next_countdown()
                tech_task = technical_analysis_task.apply_async(
                    kwargs=dict(url=website_str, entreprise_id=entreprise_id, enable_nmap=False),
                    countdown=cd,
                    queue='technical',
                )
                tech_tasks.append({
                    'task': tech_task,
                    'entreprise_id': entreprise_id,
                    'url': website_str,
                    'nom': entreprise_name
                })
                logger.info(
                    f'[Scraping Analyse {analysis_id}] Analyse technique planifiée pour {entreprise_name} '
                    f'({website_str}) countdown={cd}s - task_id={tech_task.id}'
                )
            except Exception as e:
                logger.warning(f'[Scraping Analyse {analysis_id}] Erreur lors du lancement de l\'analyse technique pour {entreprise_name}: {e}')
    
    logger.info(
        f'[Scraping Analyse {analysis_id}] {len(tech_tasks)} analyses techniques planifiées (étalées), '
        f'démarrage du scraping...'
    )
    
    # Inclure les IDs des tâches techniques dans le meta pour le monitoring en temps réel
    tech_tasks_launched_ids = [{'task_id': t['task'].id, 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']} for t in tech_tasks]
    
    def update_progress(message: str, current_index: int, entreprise_name: str, website: str,
                        current_stats: Dict, extra_meta: Dict = None):
        """Met à jour la progression globale pour l'UI."""
        # Recalculer les IDs OSINT / SEO à chaque fois car ils sont ajoutés progressivement
        osint_tasks_launched_ids = [
            {'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']}
            for t in osint_tasks
        ]
        seo_tasks_launched_ids = [
            {'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']}
            for t in seo_tasks
        ]
        screenshot_tasks_launched_ids = [
            {'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']}
            for t in screenshot_tasks
        ]
        
        meta = {
            'current': current_index,
            'total': total,
            'message': message,
            'entreprise': entreprise_name,
            'url': website,
            'total_emails': current_stats['total_emails'],
            'total_people': current_stats['total_people'],
            'total_phones': current_stats['total_phones'],
            'total_social_platforms': current_stats['total_social_platforms'],
            'total_technologies': current_stats['total_technologies'],
            'total_images': current_stats['total_images'],
            'tech_tasks_launched_ids': tech_tasks_launched_ids,  # IDs analyses techniques
            'osint_tasks_launched_ids': osint_tasks_launched_ids,  # IDs analyses OSINT
            'seo_tasks_launched_ids': seo_tasks_launched_ids,  # IDs analyses SEO
            'screenshot_tasks_launched_ids': screenshot_tasks_launched_ids,  # IDs screenshots
            'pentest_tasks_launched_ids': [
                {'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']}
                for t in pentest_tasks
            ]  # IDs analyses Pentest
        }
        if extra_meta and isinstance(extra_meta, dict):
            meta.update(extra_meta)
        _safe_update_state(self, task_id, state='PROGRESS', meta=meta)
    
    for idx, row in enumerate(rows):
        # Gérer les dictionnaires PostgreSQL et les tuples SQLite
        if isinstance(row, dict):
            entreprise_id = row.get('id')
            nom = row.get('nom')
            website = row.get('website')
        else:
            entreprise_id, nom, website = row
        
        current_index = idx + 1
        entreprise_name = nom or 'Entreprise inconnue'
        website_str = str(website or '').strip()
        
        if not website_str:
            continue
        
        logger.info(f'[Scraping Analyse {analysis_id}] {current_index}/{total} - {entreprise_name} ({website_str})')
        
        scraper = None
        
        def progress_callback(message: str):
            """Callback appelé par UnifiedScraper pour cette entreprise."""
            nonlocal scraper
            try:
                # Récupérer des compteurs en temps réel depuis le scraper pour cette entreprise uniquement
                # Ne pas ajouter aux global_stats ici car ils seront mis à jour après le scraping complet
                if scraper:
                    with scraper.lock:
                        emails_count = len(scraper.emails)
                        people_count = len(scraper.people)
                        phones_count = len(scraper.phones)
                        social_count = len(scraper.social_links)
                        tech_count = sum(
                            len(v) if isinstance(v, list) else 1
                            for v in scraper.technologies.values()
                        )
                        images_count = len(scraper.images)
                else:
                    emails_count = people_count = phones_count = social_count = tech_count = images_count = 0
                
                # Formater le message avec les compteurs de cette entreprise uniquement
                # Les totaux globaux sont passés séparément dans global_stats
                current_stats_str = f"{emails_count} emails, {people_count} personnes, {phones_count} téléphones, {social_count} réseaux sociaux"
                if tech_count > 0:
                    current_stats_str += f", {tech_count} technos"
                if images_count > 0:
                    current_stats_str += f", {images_count} images"
                
                # Message formaté : entreprise actuelle | total cumulé
                total_stats_str = f"{global_stats['total_emails']} emails, {global_stats['total_people']} personnes, {global_stats['total_phones']} téléphones"
                if global_stats['total_social_platforms'] > 0:
                    total_stats_str += f", {global_stats['total_social_platforms']} réseaux sociaux"
                if global_stats['total_technologies'] > 0:
                    total_stats_str += f", {global_stats['total_technologies']} technos"
                if global_stats['total_images'] > 0:
                    total_stats_str += f", {global_stats['total_images']} images"
                
                message_with_counters = f"{message} - {current_stats_str} | Total: {total_stats_str}"
                
                # Utiliser les totaux globaux actuels (sans ajouter les compteurs de cette entreprise)
                # car cette entreprise n'est pas encore terminée
                update_progress(message_with_counters, current_index, entreprise_name, website_str, global_stats)
            except Exception as e:
                logger.warning(f'Erreur dans progress_callback pour {website_str}: {e}')
        
        try:
            scraper = UnifiedScraper(
                base_url=website_str,
                max_workers=max_workers,
                max_depth=max_depth,
                max_time=max_time,
                max_pages=max_pages,
                progress_callback=progress_callback
            )
            
            results = scraper.scrape()
            
            emails_found = results.get('emails', [])
            if not emails_found:
                logger.info(
                    f'[Scraping Analyse {analysis_id}] Aucun email trouvé pour {entreprise_name}, '
                    f'pas d\'analyse nécessaire'
                )
            email_analyses = _build_email_analyses_dict(
                emails_found,
                website_str,
                log_prefix=f'[Scraping Analyse {analysis_id}] {entreprise_name}',
            )
            
            phone_analyses = {}
            phones_found = results.get('phones') or []
            if phones_found:
                try:
                    phone_analyses = analyze_phones_dict_for_storage(
                        phones_found, source_url=website_str
                    )
                except Exception as pe:
                    logger.warning(
                        f'[Scraping Analyse {analysis_id}] Analyse téléphones pour BDD: {pe}'
                    )
            
            # Sauvegarder les résultats complets en BDD avec les analyses
            try:
                db = Database()
                social_profiles = results.get('social_links')
                visited_urls = results.get('visited_urls', 0)
                if isinstance(visited_urls, list):
                    visited_urls_count = len(visited_urls)
                else:
                    visited_urls_count = visited_urls or 0
                
                metadata_value = merge_scraper_metadata_for_storage(
                    results.get('metadata'),
                    results.get('external_links'),
                    results.get('scraped_location'),
                )
                metadata_total = len(metadata_value) if isinstance(metadata_value, dict) else 0
                
                
                scraper_id = db.save_scraper(
                    entreprise_id=entreprise_id,
                    url=website_str,
                    scraper_type='unified_scraper',
                    emails=results.get('emails'),
                    people=results.get('people'),
                    phones=results.get('phones'),
                    social_profiles=social_profiles,
                    technologies=results.get('technologies'),
                    metadata=metadata_value,
                    images=results.get('images'),
                    forms=results.get('forms'),
                    visited_urls=visited_urls_count,
                    total_emails=results.get('total_emails', 0),
                    total_people=results.get('total_people', 0),
                    total_phones=results.get('total_phones', 0),
                    total_social_profiles=results.get('total_social_platforms', 0),
                    total_technologies=results.get('total_technologies', 0),
                    total_metadata=metadata_total,
                    total_images=results.get('total_images', 0),
                    total_forms=results.get('total_forms', 0),
                    duration=results.get('duration', 0),
                    email_analyses=email_analyses if email_analyses else None,
                    phone_analyses=phone_analyses if phone_analyses else None,
                )
                try:
                    db.replace_web_external_links_for_scraper(
                        entreprise_id=entreprise_id,
                        scraper_id=scraper_id,
                        client_site_url=website_str,
                        external_links=results.get('external_links'),
                    )
                except Exception as wce:
                    logger.warning('web_external_links (analyse scrape): %s', wce)
                schedule_enrich_external_links_mini_scrape(entreprise_id, scraper_id)
                
                _persist_personnes_from_email_analyses(
                    db,
                    entreprise_id,
                    email_analyses,
                    f'[Scraping Analyse {analysis_id}] {entreprise_name}',
                )
                try:
                    if db.patch_entreprise_location_from_scrape(entreprise_id, results.get('scraped_location')):
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] Fiche entreprise {entreprise_id} : adresse / lieu complétés depuis le scraping'
                        )
                except Exception as loc_e:
                    logger.warning('patch_entreprise_location (analyse scrape save): %s', loc_e)
                
                # Enregistrer les personnes trouvées dans les textes des pages
                scraper_people = results.get('people', [])
                if scraper_people:
                    people_from_text_saved = 0
                    for person in scraper_people:
                        person_name = person.get('name', '')
                        first_name = person.get('first_name')
                        last_name = person.get('last_name')
                        
                        # Si on a first_name et last_name séparés, les utiliser
                        if not first_name or not last_name:
                            # Essayer de séparer le nom
                            name_parts = person_name.split()
                            if len(name_parts) >= 2:
                                first_name = name_parts[0]
                                last_name = ' '.join(name_parts[1:])
                            else:
                                continue
                        
                        # Valider que c'est bien un nom humain avant de sauvegarder
                        if first_name and last_name:
                            # Valider avec validate_name_pair (plus strict)
                            validated = validate_name_pair(first_name, last_name)
                            if not validated:
                                # Si validate_name_pair échoue, essayer avec is_valid_human_name sur le nom complet
                                full_name = f'{first_name} {last_name}'
                                if not is_valid_human_name(full_name):
                                    logger.debug(
                                        f'[Scraping Analyse {analysis_id}] ⚠ Nom invalide ignoré: '
                                        f'{first_name} {last_name}'
                                    )
                                    continue
                                # Si is_valid_human_name passe mais pas validate_name_pair, 
                                # valider chaque partie individuellement
                                if not is_valid_human_name(first_name) or not is_valid_human_name(last_name):
                                    logger.debug(
                                        f'[Scraping Analyse {analysis_id}] ⚠ Nom invalide ignoré: '
                                        f'{first_name} {last_name}'
                                    )
                                    continue
                            else:
                                # Utiliser les versions validées
                                first_name, last_name = validated
                            
                            try:
                                personne_id = db.save_personne(
                                    entreprise_id=entreprise_id,
                                    prenom=first_name,
                                    nom=last_name,
                                    email=person.get('email'),
                                    telephone=person.get('phone'),
                                    linkedin_url=person.get('linkedin_url'),
                                    titre=person.get('title'),
                                    source=person.get('source', 'website_scraping')
                                )
                                people_from_text_saved += 1
                                logger.debug(
                                    f'[Scraping Analyse {analysis_id}] ✓ Personne trouvée dans le texte: '
                                    f'{first_name} {last_name}'
                                )
                            except Exception as person_error:
                                logger.warning(
                                    f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors de l\'enregistrement '
                                    f'de la personne {first_name} {last_name}: {person_error}'
                                )
                    
                    if people_from_text_saved > 0:
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] ✓ {people_from_text_saved} personne(s) enregistrée(s) '
                            f'depuis les textes des pages pour {entreprise_name}'
                        )
                logger.info(
                    f'Scraper sauvegardé (id={scraper_id}) pour entreprise {entreprise_id} '
                    f'avec {results.get("total_emails", 0)} emails, '
                    f'{results.get("total_people", 0)} personnes, '
                    f'{results.get("total_phones", 0)} téléphones, '
                    f'{results.get("total_social_platforms", 0)} réseaux sociaux, '
                    f'{results.get("total_technologies", 0)} technos, '
                    f'{results.get("total_images", 0)} images'
                )
                
                # Lancer les analyses OSINT / SEO / Pentest après le scraper (utilise les données du scraper)
                # Important : une tâche OSINT et une tâche Pentest sont ajoutées à la fin du scraping
                # de chaque site. Les listes osint_tasks / pentest_tasks grossissent au fil du loop
                # (1 après le 1er site, 2 après le 2e, etc.). Le meta envoyé par update_progress
                # contient osint_tasks_launched_ids et pentest_tasks_launched_ids ; le monitoring
                # WebSocket utilise expected_total (meta["total"] = nb d'entreprises) pour afficher X/N.
                try:
                    from tasks.osint_tasks import osint_analysis_task
                    from tasks.seo_tasks import seo_analysis_task
                    from tasks.pentest_tasks import pentest_analysis_task
                    from tasks.screenshot_tasks import website_screenshot_task

                    # Préparer les données du scraper pour l'OSINT
                    people_from_scrapers = results.get('people', [])
                    emails_from_scrapers = []
                    for email_data in results.get('emails', []):
                        if isinstance(email_data, dict):
                            email_str = email_data.get('email') or email_data.get('value') or str(email_data)
                        else:
                            email_str = str(email_data)
                        if email_str:
                            emails_from_scrapers.append(email_str)
                    
                    social_profiles_from_scrapers = results.get('social_links', [])
                    phones_from_scrapers = results.get('phones', [])
                    
                    logger.info(
                        f'[Scraping Analyse {analysis_id}] Lancement des analyses OSINT / SEO / Pentest pour {entreprise_name} '
                        f'avec {len(people_from_scrapers)} personne(s), {len(emails_from_scrapers)} email(s), '
                        f'{len(social_profiles_from_scrapers)} reseau(x) social/social, {len(phones_from_scrapers)} telephone(s) du scraper'
                    )

                    # Lancer la tâche OSINT en arrière-plan (ne pas attendre)
                    # Une tâche OSINT par site scrapé ; ajoutée ici à la fin du scraping de ce site.
                    osint_cd = bulk_stagger.next_countdown()
                    osint_task = osint_analysis_task.apply_async(
                        kwargs=dict(
                            url=website_str,
                            entreprise_id=entreprise_id,
                            people_from_scrapers=people_from_scrapers,
                            emails_from_scrapers=emails_from_scrapers,
                            social_profiles_from_scrapers=social_profiles_from_scrapers,
                            phones_from_scrapers=phones_from_scrapers,
                        ),
                        countdown=osint_cd,
                        queue='osint',
                    )
                    
                    # Stocker la tâche OSINT pour le monitoring (liste alimentée à chaque fin de site scrapé)
                    osint_tasks.append({
                        'task': osint_task,
                        'task_id': osint_task.id,
                        'entreprise_id': entreprise_id,
                        'url': website_str,
                        'nom': entreprise_name
                    })

                    logger.info(
                        f'[Scraping Analyse {analysis_id}] ✓ Analyse OSINT lancee pour {entreprise_name} '
                        f'(task_id={osint_task.id}), total_osint_tasks={len(osint_tasks)}'
                    )
                    # Lancer l'analyse SEO en parallèle
                    try:
                        seo_cd = bulk_stagger.next_countdown()
                        seo_task = seo_analysis_task.apply_async(
                            kwargs=dict(
                                url=website_str,
                                entreprise_id=entreprise_id,
                                use_lighthouse=SEO_USE_LIGHTHOUSE_DEFAULT,
                            ),
                            countdown=seo_cd,
                            queue='seo',
                        )
                        seo_tasks.append({
                            'task': seo_task,
                            'task_id': seo_task.id,
                            'entreprise_id': entreprise_id,
                            'url': website_str,
                            'nom': entreprise_name
                        })
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] ✓ Analyse SEO lancee pour {entreprise_name} (task_id={seo_task.id})'
                        )
                    except Exception as seo_error:
                        logger.warning(
                            f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors du lancement de l analyse SEO pour {entreprise_name}: {seo_error}',
                            exc_info=True
                        )

                    # Lancer la capture screenshots en parallèle
                    try:
                        screenshot_cd = bulk_stagger.next_countdown()
                        screenshot_task = website_screenshot_task.apply_async(
                            kwargs=dict(
                                url=website_str,
                                entreprise_id=entreprise_id,
                                analysis_id=analysis_id,
                                full_page=False,
                            ),
                            countdown=screenshot_cd,
                            queue='screenshot',
                        )
                        screenshot_tasks.append({
                            'task': screenshot_task,
                            'task_id': screenshot_task.id,
                            'entreprise_id': entreprise_id,
                            'url': website_str,
                            'nom': entreprise_name,
                        })
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] ✓ Screenshots planifiés pour {entreprise_name} (task_id={screenshot_task.id})'
                        )
                    except Exception as screenshot_error:
                        logger.warning(
                            f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors du lancement des screenshots pour {entreprise_name}: {screenshot_error}',
                            exc_info=True
                        )

                    # Lancer l'analyse Pentest (tâche dédiée, même si aucun formulaire détecté)
                    # Une tâche Pentest par site scrapé ; ajoutée ici à la fin du scraping de ce site.
                    try:
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] Lancement de l analyse Pentest pour {entreprise_name} ({website_str})'
                        )

                        # Récupérer les formulaires du scraper si disponibles, sinon liste vide
                        forms_from_scrapers = results.get('forms') if results else None

                        pentest_cd = bulk_stagger.next_countdown()
                        pentest_task = pentest_analysis_task.apply_async(
                            kwargs=dict(
                                url=website_str,
                                entreprise_id=entreprise_id,
                                options={},
                                forms_from_scrapers=forms_from_scrapers,
                            ),
                            countdown=pentest_cd,
                            queue='heavy',
                        )

                        # Stocker pour le monitoring (liste alimentée à chaque fin de site scrapé)
                        pentest_tasks.append({
                            'task': pentest_task,
                            'task_id': pentest_task.id,
                            'entreprise_id': entreprise_id,
                            'url': website_str,
                            'nom': entreprise_name
                        })

                        logger.info(
                            f'[Scraping Analyse {analysis_id}] ✓ Analyse Pentest lancee pour {entreprise_name} (task_id={pentest_task.id})'
                        )
                    except Exception as pentest_error:
                        logger.warning(
                            f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors du lancement de l analyse Pentest pour {entreprise_name}: {pentest_error}',
                            exc_info=True
                        )
                except Exception as e:
                    logger.warning(
                        f'Erreur lors du lancement des analyses OSINT/SEO/Pentest (analyse {analysis_id}, entreprise {entreprise_id}): {e}',
                        exc_info=True
                    )
                
                # Mettre à jour l'entreprise avec resume, logo, favicon, og_image depuis les résultats du scraper
                # Les données OpenGraph sont sauvegardées dans les tables normalisées
                try:
                    resume = results.get('resume', '')
                    metadata_dict = metadata_value if isinstance(metadata_value, dict) else {}
                    icons = metadata_dict.get('icons', {}) if isinstance(metadata_dict, dict) else {}
                    logo = icons.get('logo') if isinstance(icons, dict) else None
                    favicon = icons.get('favicon') if isinstance(icons, dict) else None
                    og_image = icons.get('og_image') if isinstance(icons, dict) else None
                    
                    # Récupérer les OG de toutes les pages scrapées
                    og_data_by_page = results.get('og_data_by_page', {})
                    logger.info(f'[Scraping Analyse {analysis_id}] OG récupérés pour {entreprise_name}: {len(og_data_by_page)} page(s) depuis le scraper')
                    
                    if not og_data_by_page:
                        # Fallback : utiliser les OG de la page d'accueil si disponibles
                        og_tags = metadata_dict.get('open_graph', {}) if isinstance(metadata_dict, dict) else {}
                        if og_tags:
                            og_data_by_page = {website_str: og_tags}
                            logger.info(f'[Scraping Analyse {analysis_id}] Utilisation des OG de la page d\'accueil pour {entreprise_name} (fallback)')
                        else:
                            logger.warning(f'[Scraping Analyse {analysis_id}] ⚠ Aucun OG trouvé pour {entreprise_name} (ni dans og_data_by_page ni dans metadata)')
                    else:
                        # Log des URLs des pages avec OG
                        page_urls = list(og_data_by_page.keys())
                        logger.info(f'[Scraping Analyse {analysis_id}] Pages avec OG pour {entreprise_name}: {len(page_urls)} page(s) - {page_urls[:3]}...' if len(page_urls) > 3 else f'[Scraping Analyse {analysis_id}] Pages avec OG pour {entreprise_name}: {page_urls}')
                    
                    # Convertir les URLs relatives en absolues si nécessaire
                    if website_str:
                        from urllib.parse import urljoin
                        if logo and not logo.startswith(('http://', 'https://')):
                            logo = urljoin(website_str, logo)
                        if favicon and not favicon.startswith(('http://', 'https://')):
                            favicon = urljoin(website_str, favicon)
                        if og_image and not og_image.startswith(('http://', 'https://')):
                            og_image = urljoin(website_str, og_image)
                    
                    # Mettre à jour la table entreprises (resume, logo, favicon, og_image)
                    conn_update = db.get_connection()
                    cursor_update = conn_update.cursor()
                    db.execute_sql(cursor_update, '''
                        UPDATE entreprises 
                        SET resume = ?, logo = ?, favicon = ?, og_image = ?
                        WHERE id = ?
                    ''', (resume, logo, favicon, og_image, entreprise_id))
                    
                    # Sauvegarder toutes les données OpenGraph de toutes les pages dans les tables normalisées
                    if og_data_by_page:
                        logger.info(
                            f'[Scraping Analyse {analysis_id}] Sauvegarde de {len(og_data_by_page)} page(s) avec OG pour entreprise {entreprise_id} ({entreprise_name})'
                        )
                        try:
                            db._save_multiple_og_data_in_transaction(cursor_update, entreprise_id, og_data_by_page)
                            logger.info(
                                f'[Scraping Analyse {analysis_id}] ✓ OG sauvegardés avec succès pour entreprise {entreprise_id}: {len(og_data_by_page)} page(s)'
                            )
                        except Exception as og_error:
                            logger.error(
                                f'[Scraping Analyse {analysis_id}] ✗ Erreur lors de la sauvegarde des OG pour entreprise {entreprise_id}: {og_error}',
                                exc_info=True
                            )
                    
                    conn_update.commit()
                    conn_update.close()
                    
                    logger.info(
                        f'Entreprise {entreprise_id} mise à jour: resume={bool(resume)}, '
                        f'logo={bool(logo)}, favicon={bool(favicon)}, og_image={bool(og_image)}, '
                        f'og_pages={len(og_data_by_page)}'
                    )
                except Exception as e:
                    logger.error(f'Erreur lors de la mise à jour de l\'entreprise {entreprise_id} (resume/logo/favicon/og_data): {e}', exc_info=True)
            except Exception as e:
                logger.warning(f'Erreur lors de la sauvegarde du scraper (analyse {analysis_id}, entreprise {entreprise_id}): {e}')
            
            # Mettre à jour les stats globales à partir des résultats finaux
            global_stats['total_emails'] += results.get('total_emails', 0)
            global_stats['total_people'] += results.get('total_people', 0)
            global_stats['total_phones'] += results.get('total_phones', 0)
            global_stats['total_social_platforms'] += results.get('total_social_platforms', 0)
            global_stats['total_technologies'] += results.get('total_technologies', 0)
            global_stats['total_images'] += results.get('total_images', 0)
            
            scraped_count += 1
            
            # Mise à jour de progression après l'entreprise
            update_progress(
                f'Scraping et analyse terminés pour {entreprise_name}',
                current_index,
                entreprise_name,
                website_str,
                global_stats
            )
        
        except Exception as e:
            logger.error(f'Erreur lors du scraping de {website_str}: {e}', exc_info=True)
            
            # Même si le scraping échoue, on lance quand même l'analyse Pentest
            # car elle peut fonctionner avec juste l'URL
            try:
                logger.info(
                    f'[Scraping Analyse {analysis_id}] Lancement de l analyse Pentest pour {entreprise_name} ({website_str}) '
                    f'(scraping échoué, mais on lance quand même Pentest)'
                )
                
                pentest_cd = bulk_stagger.next_countdown()
                pentest_task = pentest_analysis_task.apply_async(
                    kwargs=dict(
                        url=website_str,
                        entreprise_id=entreprise_id,
                        options={},
                        forms_from_scrapers=None,
                    ),
                    countdown=pentest_cd,
                    queue='heavy',
                )
                
                pentest_tasks.append({
                    'task': pentest_task,
                    'task_id': pentest_task.id,
                    'entreprise_id': entreprise_id,
                    'url': website_str,
                    'nom': entreprise_name
                })
                
                logger.info(
                    f'[Scraping Analyse {analysis_id}] ✓ Analyse Pentest lancee pour {entreprise_name} '
                    f'(task_id={pentest_task.id}) malgré l\'erreur de scraping'
                )
            except Exception as pentest_error:
                logger.warning(
                    f'[Scraping Analyse {analysis_id}] ⚠ Erreur lors du lancement de l analyse Pentest pour {entreprise_name}: {pentest_error}',
                    exc_info=True
                )
            
            update_progress(
                f'Erreur lors du scraping de {entreprise_name}: {e}',
                current_index,
                entreprise_name,
                website_str,
                global_stats
            )
    
    logger.info(
        f'Scraping terminé pour l\'analyse {analysis_id}: '
        f'{scraped_count}/{total} entreprises traitées'
    )

    if lock_acquired:
        _release_scraping_lock(lock_value)

    return {
        'success': True,
        'analysis_id': analysis_id,
        'scraped_count': scraped_count,
        'total_entreprises': total,
        'stats': global_stats,
        'tech_tasks': [
            {'task_id': t['task'].id, 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']}
            for t in tech_tasks
        ],
        'osint_tasks': [
            {'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']}
            for t in osint_tasks
        ],
        'seo_tasks': [
            {'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']}
            for t in seo_tasks
        ],
        'pentest_tasks': [
            {'task_id': t['task_id'], 'entreprise_id': t['entreprise_id'], 'url': t['url'], 'nom': t['nom']}
            for t in pentest_tasks
        ]
    }


@celery.task(bind=True)
def scrape_analysis_orchestrator_task(
    self,
    analysis_id: int,
    max_depth: int = 2,
    max_workers: int = 5,
    max_time: int = 180,
    max_pages: int = 30,
    batch_size: int = _SCRAPE_ANALYSIS_BATCH_SIZE,
) -> Dict:
    """
    Orchestrateur du scraping d'analyse:
    - découpe les entreprises en lots,
    - lance un scrape_analysis_task par lot,
    - agrège la progression websocket,
    - retry simple par lot en cas d'échec.
    """
    logger.info(
        '[Scraping Orchestrator %s] Démarrage analysis_id=%s batch_size=%s',
        getattr(self.request, 'id', None),
        analysis_id,
        batch_size,
    )

    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    db.execute_sql(
        cursor,
        '''
        SELECT id
        FROM entreprises
        WHERE analyse_id = ?
          AND website IS NOT NULL
          AND TRIM(website) <> ''
        ''',
        (analysis_id,),
    )
    raw_ids = cursor.fetchall()
    conn.close()

    entreprise_ids = []
    for row in raw_ids:
        try:
            eid = row.get('id') if isinstance(row, dict) else row[0]
            if eid is not None:
                entreprise_ids.append(int(eid))
        except Exception:
            continue

    total_entreprises = len(entreprise_ids)
    if total_entreprises == 0:
        return {
            'success': True,
            'analysis_id': analysis_id,
            'scraped_count': 0,
            'total_entreprises': 0,
            'stats': {
                'total_emails': 0,
                'total_people': 0,
                'total_phones': 0,
                'total_social_platforms': 0,
                'total_technologies': 0,
                'total_images': 0,
            },
            'tech_tasks': [],
            'osint_tasks': [],
            'seo_tasks': [],
            'pentest_tasks': [],
            'failed_batches': [],
        }

    bs = max(1, int(batch_size or _SCRAPE_ANALYSIS_BATCH_SIZE))
    batches = [entreprise_ids[i:i + bs] for i in range(0, total_entreprises, bs)]

    # Aggregats globaux
    global_stats = {
        'total_emails': 0,
        'total_people': 0,
        'total_phones': 0,
        'total_social_platforms': 0,
        'total_technologies': 0,
        'total_images': 0,
    }
    scraped_count = 0
    tech_tasks_all = {}
    osint_tasks_all = {}
    seo_tasks_all = {}
    pentest_tasks_all = {}
    failed_batches = []

    # Map tid -> metadata batch
    running = {}
    completed_tids = set()

    def _launch_batch(batch_idx: int, ids: list[int], retry_count: int = 0):
        res = scrape_analysis_task.apply_async(
            kwargs=dict(
                analysis_id=analysis_id,
                max_depth=max_depth,
                max_workers=max_workers,
                max_time=max_time,
                max_pages=max_pages,
                entreprise_ids=ids,
            ),
            queue='heavy',
        )
        running[res.id] = {
            'batch_idx': batch_idx,
            'ids': ids,
            'retry_count': retry_count,
        }

    for idx, ids in enumerate(batches):
        _launch_batch(idx, ids, retry_count=0)

    while len(completed_tids) < len(running):
        # snapshot car running peut changer (retry -> nouveau tid)
        for tid, meta in list(running.items()):
            if tid in completed_tids:
                continue
            r = celery.AsyncResult(tid)
            state = r.state

            if state == 'PROGRESS':
                info = r.info if isinstance(r.info, dict) else {}
                for t in info.get('tech_tasks_launched_ids', []) or []:
                    if isinstance(t, dict) and t.get('task_id'):
                        tech_tasks_all[t['task_id']] = t
                for t in info.get('osint_tasks_launched_ids', []) or []:
                    if isinstance(t, dict) and t.get('task_id'):
                        osint_tasks_all[t['task_id']] = t
                for t in info.get('seo_tasks_launched_ids', []) or []:
                    if isinstance(t, dict) and t.get('task_id'):
                        seo_tasks_all[t['task_id']] = t
                for t in info.get('pentest_tasks_launched_ids', []) or []:
                    if isinstance(t, dict) and t.get('task_id'):
                        pentest_tasks_all[t['task_id']] = t

            elif state == 'SUCCESS':
                completed_tids.add(tid)
                res = r.result if isinstance(r.result, dict) else {}
                scraped_count += int(res.get('scraped_count', 0) or 0)
                s = res.get('stats', {}) if isinstance(res.get('stats', {}), dict) else {}
                for k in global_stats.keys():
                    global_stats[k] += int(s.get(k, 0) or 0)

                for t in res.get('tech_tasks', []) or []:
                    if isinstance(t, dict) and t.get('task_id'):
                        tech_tasks_all[t['task_id']] = t
                for t in res.get('osint_tasks', []) or []:
                    if isinstance(t, dict) and t.get('task_id'):
                        osint_tasks_all[t['task_id']] = t
                for t in res.get('seo_tasks', []) or []:
                    if isinstance(t, dict) and t.get('task_id'):
                        seo_tasks_all[t['task_id']] = t
                for t in res.get('pentest_tasks', []) or []:
                    if isinstance(t, dict) and t.get('task_id'):
                        pentest_tasks_all[t['task_id']] = t

            elif state in ('FAILURE', 'REVOKED'):
                retry_count = int(meta.get('retry_count', 0) or 0)
                if retry_count < _SCRAPE_ANALYSIS_BATCH_RETRY_MAX:
                    # Retry du batch uniquement
                    completed_tids.add(tid)
                    _launch_batch(meta['batch_idx'], meta['ids'], retry_count=retry_count + 1)
                else:
                    completed_tids.add(tid)
                    failed_batches.append(
                        {
                            'batch_idx': meta.get('batch_idx'),
                            'size': len(meta.get('ids') or []),
                            'error': str(r.info),
                        }
                    )

        percentage = int((scraped_count / total_entreprises) * 100) if total_entreprises > 0 else 0
        self.update_state(
            state='PROGRESS',
            meta={
                'analysis_id': analysis_id,
                'current': scraped_count,
                'total': total_entreprises,
                'message': f'Scraping en cours ({scraped_count}/{total_entreprises})',
                'total_emails': global_stats['total_emails'],
                'total_people': global_stats['total_people'],
                'total_phones': global_stats['total_phones'],
                'total_social_platforms': global_stats['total_social_platforms'],
                'total_technologies': global_stats['total_technologies'],
                'total_images': global_stats['total_images'],
                'tech_tasks_launched_ids': list(tech_tasks_all.values()),
                'osint_tasks_launched_ids': list(osint_tasks_all.values()),
                'seo_tasks_launched_ids': list(seo_tasks_all.values()),
                'pentest_tasks_launched_ids': list(pentest_tasks_all.values()),
                'failed_batches': failed_batches,
                'progress': percentage,
            },
        )
        time.sleep(1.0)

    return {
        'success': len(failed_batches) == 0,
        'analysis_id': analysis_id,
        'scraped_count': scraped_count,
        'total_entreprises': total_entreprises,
        'stats': global_stats,
        'tech_tasks': list(tech_tasks_all.values()),
        'osint_tasks': list(osint_tasks_all.values()),
        'seo_tasks': list(seo_tasks_all.values()),
        'pentest_tasks': list(pentest_tasks_all.values()),
        'failed_batches': failed_batches,
    }

