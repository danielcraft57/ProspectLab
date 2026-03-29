"""
Orchestration : analyse complète d'un site (scraping → technique → SEO → OSINT → pentest).

Exécution séquentielle dans le worker pour transmettre emails/personnes/formulaires
du scraper à l'OSINT et au pentest sans course avec les autres tâches.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from services.database import Database
from services.logging_config import setup_logger
from tasks.scraping_tasks import scrape_emails_task
from tasks.technical_analysis_tasks import technical_analysis_task
from tasks.seo_tasks import seo_analysis_task
from tasks.osint_tasks import osint_analysis_task
from tasks.pentest_tasks import pentest_analysis_task

try:
    from config import FULL_ANALYSIS_INTER_STEP_PAUSE_SEC
except ImportError:
    FULL_ANALYSIS_INTER_STEP_PAUSE_SEC = float(os.environ.get('FULL_ANALYSIS_INTER_STEP_PAUSE_SEC', '3'))

logger = setup_logger(__name__, 'full_website_analysis.log', level=logging.INFO)


def _run_subtask_eager(task, **kwargs):
    """
    Exécute une sous-tâche dans le même processus (apply local).
    Ne pas utiliser AsyncResult.get() depuis une tâche Celery : Celery 5 lève une erreur
    (assert_will_not_block), même pour un EagerResult retourné par apply().
    """
    r = task.apply(kwargs=kwargs)
    if not r.successful():
        r.maybe_throw(propagate=True)
    return r.result


def _flatten_social(social_links: Optional[dict]) -> List[dict]:
    out: List[dict] = []
    if not social_links:
        return out
    for platform, urls in social_links.items():
        if isinstance(urls, list):
            for u in urls:
                out.append({'platform': platform, 'url': u})
        elif urls:
            out.append({'platform': platform, 'url': urls})
    return out


def _map_people_for_osint(people: Optional[List[dict]]) -> List[dict]:
    mapped: List[dict] = []
    for p in people or []:
        name = (p.get('name') or '').strip()
        if not name:
            fn = (p.get('first_name') or p.get('prenom') or '').strip()
            ln = (p.get('last_name') or p.get('nom') or '').strip()
            name = f'{fn} {ln}'.strip()
        if not name:
            continue
        mapped.append({
            'name': name,
            'email': p.get('email'),
            'title': p.get('title'),
            'role': p.get('role'),
            'linkedin_url': p.get('linkedin_url'),
        })
    return mapped


def _emails_as_strings(emails: Optional[List[Any]]) -> List[str]:
    out: List[str] = []
    for e in emails or []:
        if isinstance(e, str) and e.strip():
            out.append(e.strip())
        elif isinstance(e, dict) and e.get('email'):
            out.append(str(e['email']).strip())
    return out


def _phones_as_strings(phones: Optional[List[Any]]) -> List[str]:
    out: List[str] = []
    for p in phones or []:
        if isinstance(p, str) and p.strip():
            out.append(p.strip())
        elif isinstance(p, dict):
            ph = p.get('phone') or p.get('value')
            if ph:
                out.append(str(ph).strip())
    return out


def _apply_scrape_to_entreprise(database: Database, entreprise_id: int, flat: dict) -> None:
    if not entreprise_id or not flat:
        return
    email = None
    for e in flat.get('emails') or []:
        if isinstance(e, dict) and e.get('email'):
            email = e['email']
            break
    phone = None
    for p in flat.get('phones') or []:
        if isinstance(p, dict):
            phone = p.get('phone')
        elif isinstance(p, str):
            phone = p
        if phone:
            break
    resume = flat.get('resume')
    ent = database.get_entreprise(entreprise_id)
    if not ent:
        return
    updates = []
    params: List[Any] = []
    if email and not (ent.get('email_principal') or '').strip():
        updates.append('email_principal = ?')
        params.append(email)
    if phone and not (ent.get('telephone') or '').strip():
        updates.append('telephone = ?')
        params.append(phone)
    if resume and str(resume).strip():
        updates.append('resume = ?')
        params.append(str(resume)[:20000])
    if not updates:
        return
    params.append(entreprise_id)
    conn = database.get_connection()
    cursor = conn.cursor()
    sql = f'UPDATE entreprises SET {", ".join(updates)} WHERE id = ?'
    database.execute_sql(cursor, sql, tuple(params))
    conn.commit()
    conn.close()


def _collect_scores(database: Database, entreprise_id: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        'technical_security_score': None,
        'technical_performance_score': None,
        'seo_score': None,
        'pentest_risk_score': None,
    }
    tech = database.get_technical_analysis(entreprise_id)
    if tech:
        out['technical_security_score'] = tech.get('security_score')
        out['technical_performance_score'] = tech.get('performance_score')
    try:
        seo_list = database.get_seo_analyses_by_entreprise(entreprise_id, limit=1) or []
        if seo_list:
            out['seo_score'] = seo_list[0].get('score')
    except Exception:
        pass
    try:
        pent = database.get_pentest_analysis_by_entreprise(entreprise_id)
        if pent:
            out['pentest_risk_score'] = pent.get('risk_score')
    except Exception:
        pass
    return out


def run_full_website_analysis_impl(
    self,
    url: str,
    entreprise_id: int,
    analyse_id: Optional[int] = None,
    max_depth: int = 2,
    max_workers: int = 5,
    max_time: int = 240,
    max_pages: int = 40,
    enable_nmap: bool = False,
    use_lighthouse: bool = False,
):
    """
    Corps du pack d’analyses (appelé par la tâche Celery enregistrée dans analysis_tasks).
    """
    t0 = time.monotonic()
    database = Database()
    steps: Dict[str, str] = {}
    scrape_counts: Dict[str, int] = {}
    image_urls: List[str] = []

    def progress(step: str, pct: int, message: str):
        self.update_state(
            state='PROGRESS',
            meta={
                'step': step,
                'progress': pct,
                'message': message,
                'steps': dict(steps),
                'entreprise_id': entreprise_id,
                'analyse_id': analyse_id,
                'website': url,
            },
        )

    progress('init', 2, 'Préparation du pack d\'analyses…')

    flat_results: dict = {}

    # 1) Scraping
    try:
        progress('scraping', 8, 'Scraping (emails, images, formulaires)…')
        scrape_out = _run_subtask_eager(
            scrape_emails_task,
            url=url,
            max_depth=max_depth,
            max_workers=max_workers,
            max_time=max_time,
            max_pages=max_pages,
            entreprise_id=entreprise_id,
        )
        if scrape_out.get('success') and scrape_out.get('results'):
            flat_results = scrape_out['results']
            scrape_counts = {
                'emails': int(flat_results.get('total_emails') or 0),
                'people': int(flat_results.get('total_people') or 0),
                'phones': int(flat_results.get('total_phones') or 0),
                'images': int(flat_results.get('total_images') or 0),
                'forms': int(flat_results.get('total_forms') or 0),
            }
            for img in flat_results.get('images') or []:
                if isinstance(img, dict):
                    u = img.get('url') or img.get('src')
                    if u:
                        image_urls.append(u)
                elif isinstance(img, str):
                    image_urls.append(img)
            image_urls = image_urls[:80]
            _apply_scrape_to_entreprise(database, entreprise_id, flat_results)
        steps['scraping'] = 'ok' if scrape_out.get('success') else 'erreur'
    except Exception as e:
        logger.exception('Full analysis: scraping échoué')
        steps['scraping'] = f'erreur: {e!s}'[:200]

    # Scraping réellement terminé (UnifiedScraper attend tous les threads) avant toute autre étape.
    if steps.get('scraping') == 'ok':
        progress(
            'scraping',
            22,
            'Scraping terminé, lancement des analyses (technique, SEO, OSINT, pentest)…',
        )
    else:
        progress(
            'scraping',
            22,
            'Scraping terminé avec des erreurs ; poursuite des analyses sur l’URL…',
        )

    # Réduit les HTTP 429 quand le même hôte vient d’être sollicité par le scrape + technique.
    if FULL_ANALYSIS_INTER_STEP_PAUSE_SEC > 0:
        logger.info(
            'Pause %.1fs avant analyse technique (FULL_ANALYSIS_INTER_STEP_PAUSE_SEC).',
            FULL_ANALYSIS_INTER_STEP_PAUSE_SEC,
        )
        time.sleep(FULL_ANALYSIS_INTER_STEP_PAUSE_SEC)

    people_osint = _map_people_for_osint(flat_results.get('people'))
    emails_osint = _emails_as_strings(flat_results.get('emails'))
    social_osint = _flatten_social(flat_results.get('social_links'))
    phones_osint = _phones_as_strings(flat_results.get('phones'))
    forms_pentest = flat_results.get('forms') or []

    # 2) Technique
    try:
        progress('technical', 28, 'Analyse technique…')
        _run_subtask_eager(
            technical_analysis_task,
            url=url,
            entreprise_id=entreprise_id,
            enable_nmap=enable_nmap,
        )
        steps['technical'] = 'ok'
    except Exception as e:
        logger.exception('Full analysis: technique échouée')
        steps['technical'] = f'erreur: {e!s}'[:200]

    # 3) SEO
    try:
        progress('seo', 48, 'Analyse SEO…')
        _run_subtask_eager(
            seo_analysis_task,
            url=url,
            entreprise_id=entreprise_id,
            use_lighthouse=use_lighthouse,
        )
        steps['seo'] = 'ok'
    except Exception as e:
        logger.exception('Full analysis: SEO échouée')
        steps['seo'] = f'erreur: {e!s}'[:200]

    # 4) OSINT
    try:
        progress('osint', 65, 'Analyse OSINT…')
        _run_subtask_eager(
            osint_analysis_task,
            url=url,
            entreprise_id=entreprise_id,
            people_from_scrapers=people_osint or None,
            emails_from_scrapers=emails_osint or None,
            social_profiles_from_scrapers=social_osint or None,
            phones_from_scrapers=phones_osint or None,
        )
        steps['osint'] = 'ok'
    except Exception as e:
        logger.exception('Full analysis: OSINT échoué')
        steps['osint'] = f'erreur: {e!s}'[:200]

    # 5) Pentest
    try:
        progress('pentest', 82, 'Analyse pentest / sécurité applicative…')
        _run_subtask_eager(
            pentest_analysis_task,
            url=url,
            entreprise_id=entreprise_id,
            options={},
            forms_from_scrapers=forms_pentest or None,
        )
        steps['pentest'] = 'ok'
    except Exception as e:
        logger.exception('Full analysis: pentest échoué')
        steps['pentest'] = f'erreur: {e!s}'[:200]

    duree = time.monotonic() - t0
    if analyse_id:
        try:
            database.finalize_analysis(analyse_id, statut='Terminé', duree_secondes=round(duree, 2))
        except Exception as e:
            logger.warning('finalize_analysis: %s', e)

    scores = _collect_scores(database, entreprise_id)

    summary = {
        'success': True,
        'website': url,
        'entreprise_id': entreprise_id,
        'analyse_id': analyse_id,
        'steps': steps,
        'scrape_counts': scrape_counts,
        'scores': scores,
        'image_urls_sample': image_urls[:24],
        'duration_seconds': round(duree, 2),
    }

    progress('done', 100, 'Analyse complète terminée')
    logger.info(
        'Full website analysis terminée pour %s (entreprise_id=%s) steps=%s',
        url,
        entreprise_id,
        steps,
    )
    return summary
