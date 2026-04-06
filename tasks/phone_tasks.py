"""
Tâches Celery pour l'analyse OSINT des numéros de téléphone (PhoneInfoga, libphonenumber, etc.).
Même modèle que tasks.email_tasks.analyze_emails_task.
"""

from celery_app import celery
from services.osint_analyzer import OSINTAnalyzer
from services.logging_config import setup_logger
import logging

logger = setup_logger(__name__, 'phone_tasks.log', level=logging.INFO)


def normalize_phones_for_osint(phones) -> list[str]:
    out: list[str] = []
    for p in phones or []:
        if isinstance(p, str) and p.strip():
            out.append(p.strip())
        elif isinstance(p, dict):
            v = (p.get('phone') or p.get('value') or p.get('number') or '').strip()
            if v:
                out.append(v)
        elif p is not None:
            s = str(p).strip()
            if s:
                out.append(s)
    seen: set[str] = set()
    dedup: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            dedup.append(x)
    return dedup


def analyze_phones_dict_for_storage(phones_found, source_url=None):
    """
    Lance analyze_phones_osint sur les numéros scrapés pour persistance dans scraper_phones.
    Retourne un dict clé normalisée -> détails (libphonenumber, PhoneInfoga, Numverify, Abstract, etc.).
    """
    norm = normalize_phones_for_osint(phones_found or [])
    if not norm:
        return {}
    try:
        analyzer = OSINTAnalyzer()
        return analyzer.analyze_phones_osint(norm, progress_callback=None)
    except Exception as e:
        logger.warning(f'[Analyse téléphones stockage] Ignoré: {e}')
        return {}


@celery.task(bind=True)
def analyze_phones_task(self, phones, source_url=None, entreprise_id=None):
    """
    Analyse OSINT d'une liste de numéros (asynchrone, file « osint »).

    Args:
        phones: liste de str ou dict {phone, value, ...}
        source_url: URL / contexte (traçabilité)
        entreprise_id: optionnel

    Returns:
        dict: success, phone_osint (dict numéro -> détails), total
    """
    try:
        norm = normalize_phones_for_osint(phones)
        if not norm:
            logger.info(f'[Analyse téléphones] Aucun numéro (source_url={source_url})')
            return {'success': True, 'phone_osint': {}, 'total': 0, 'source_url': source_url}

        logger.info(
            f'[Analyse téléphones] {len(norm)} numéro(s) (source_url={source_url}, entreprise_id={entreprise_id})'
        )

        def progress_callback(message: str):
            try:
                self.update_state(
                    state='PROGRESS',
                    meta={'message': message, 'source_url': source_url, 'entreprise_id': entreprise_id},
                )
            except Exception:
                pass

        analyzer = OSINTAnalyzer()
        phone_osint = analyzer.analyze_phones_osint(norm, progress_callback=progress_callback)

        logger.info(f'[Analyse téléphones] Terminé : {len(phone_osint)} entrée(s)')

        return {
            'success': True,
            'phone_osint': phone_osint,
            'total': len(norm),
            'source_url': source_url,
            'entreprise_id': entreprise_id,
        }
    except Exception as e:
        logger.error(f'[Analyse téléphones] Erreur critique: {e}', exc_info=True)
        raise
