"""
Orchestration : analyse complète d'un site (scraping → technique → SEO → OSINT → pentest).

Exécution séquentielle dans le worker pour transmettre emails/personnes/formulaires
du scraper à l'OSINT et au pentest sans course avec les autres tâches.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from services.database import Database
from services.logging_config import setup_logger
from tasks.scraping_tasks import run_scrape_emails_inline
from tasks.technical_analysis_tasks import technical_analysis_task
from tasks.seo_tasks import seo_analysis_task
from tasks.osint_tasks import osint_analysis_task
from tasks.phone_tasks import analyze_phones_task
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


def _host_key(url: str) -> str:
    try:
        h = (urlparse(url).netloc or '').strip().lower()
    except Exception:
        h = ''
    if h.startswith('www.'):
        h = h[4:]
    if ':' in h:
        h = h.split(':', 1)[0]
    return h


def _nom_looks_like_domain_placeholder(nom: str, url: str) -> bool:
    if not nom or not url:
        return False
    key = _host_key(url)
    n = nom.strip().lower()
    if n.startswith('www.'):
        n = n[4:]
    if not key:
        return False
    return n == key or n == key.split('.')[0]


def _clean_display_name(raw: Optional[str], max_len: int = 180) -> str:
    if not raw or not str(raw).strip():
        return ''
    t = str(raw).strip()
    for sep in (' | ', ' – ', ' - '):
        if sep in t:
            parts = [p.strip() for p in t.split(sep) if p.strip()]
            if parts:
                t = parts[0]
            break
    t = t.strip()
    if len(t) < 2 or t.lower() in ('accueil', 'home', 'welcome', 'bienvenue'):
        return ''
    return t[:max_len]


def _technologies_blob(technologies: Any) -> str:
    if not technologies or not isinstance(technologies, dict):
        return ''
    parts: List[str] = []
    for k, v in technologies.items():
        if isinstance(v, list):
            parts.append(f'{k}: {", ".join(str(x) for x in v if x)}')
        elif v:
            parts.append(f'{k}: {v}')
    return ' '.join(parts)


def _pick_responsable_from_people(people: Optional[List[dict]]) -> Optional[str]:
    if not people:
        return None
    keywords = (
        'dpo', 'délégué', 'delegue', 'rgpd', 'gdpr',
        'protection des donn', 'privacy officer', 'data protection',
        'correspondant informatique',
    )
    for p in people:
        if not isinstance(p, dict):
            continue
        blob = f"{p.get('title') or ''} {p.get('role') or ''}".lower()
        if any(k in blob for k in keywords):
            n = (p.get('name') or '').strip()
            if n:
                return n[:500]
    return None


def _persist_scraper_branding_and_og(
    database: Database,
    entreprise_id: int,
    website_url: str,
    flat: dict,
) -> None:
    """
    Alignement avec scrape_analysis_task : resume enrichi, logo/favicon/og_image,
    tables entreprise_og_data (aperçus / fiche).
    """
    if not entreprise_id or not flat:
        return
    resume = flat.get('resume') or ''
    metadata_dict = flat.get('metadata') if isinstance(flat.get('metadata'), dict) else {}
    icons = metadata_dict.get('icons', {}) if isinstance(metadata_dict, dict) else {}
    logo = icons.get('logo') if isinstance(icons, dict) else None
    favicon = icons.get('favicon') if isinstance(icons, dict) else None
    og_image = icons.get('og_image') if isinstance(icons, dict) else None

    og_data_by_page = flat.get('og_data_by_page') or {}
    if not og_data_by_page:
        og_tags = metadata_dict.get('open_graph', {}) if isinstance(metadata_dict, dict) else {}
        if og_tags:
            og_data_by_page = {website_url: og_tags}

    website_str = str(website_url or '').strip()
    if website_str:
        if logo and not str(logo).startswith(('http://', 'https://')):
            logo = urljoin(website_str, str(logo))
        if favicon and not str(favicon).startswith(('http://', 'https://')):
            favicon = urljoin(website_str, str(favicon))
        if og_image and not str(og_image).startswith(('http://', 'https://')):
            og_image = urljoin(website_str, str(og_image))

    conn = database.get_connection()
    cursor = conn.cursor()
    try:
        database.execute_sql(
            cursor,
            '''
            UPDATE entreprises
            SET resume = COALESCE(NULLIF(?, ''), resume),
                logo = COALESCE(?, logo),
                favicon = COALESCE(?, favicon),
                og_image = COALESCE(?, og_image)
            WHERE id = ?
            ''',
            (str(resume)[:20000] if resume else None, logo, favicon, og_image, entreprise_id),
        )
        if og_data_by_page and isinstance(og_data_by_page, dict):
            try:
                database._save_multiple_og_data_in_transaction(cursor, entreprise_id, og_data_by_page)
            except Exception as og_e:
                logger.warning('full_analysis: sauvegarde OG: %s', og_e)
        conn.commit()
    except Exception as e:
        logger.warning('full_analysis: branding/OG entreprise: %s', e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _finalize_entreprise_fiche_after_pack(
    database: Database,
    entreprise_id: int,
    url: str,
    flat_results: dict,
) -> None:
    """
    Complète la fiche entreprise (champs souvent présents sur import Maps / Excel)
    à partir du scrape, de l’analyse technique et de heuristiques locales.
    """
    if not entreprise_id:
        return
    ent = database.get_entreprise(entreprise_id)
    if not ent:
        return

    from services.entreprise_analyzer import EntrepriseAnalyzer

    analyzer = EntrepriseAnalyzer()
    tech = database.get_technical_analysis(entreprise_id) or {}

    updates: List[str] = []
    params: List[Any] = []

    def _empty(v) -> bool:
        return v is None or (isinstance(v, str) and not v.strip())

    # Nom lisible (remplace le domaine seul)
    if _nom_looks_like_domain_placeholder(str(ent.get('nom') or ''), url):
        og_meta = flat_results.get('metadata') if isinstance(flat_results.get('metadata'), dict) else {}
        ogp = og_meta.get('open_graph', {}) if isinstance(og_meta.get('open_graph'), dict) else {}
        meta_tags = og_meta.get('meta_tags', {}) if isinstance(og_meta.get('meta_tags'), dict) else {}
        candidate = (
            _clean_display_name(ogp.get('site_name'))
            or _clean_display_name(ogp.get('title'))
            or _clean_display_name(meta_tags.get('title'))
        )
        if not candidate and tech.get('seo_meta') and isinstance(tech['seo_meta'], dict):
            candidate = _clean_display_name(tech['seo_meta'].get('title'))
        if not candidate and tech.get('pages') and isinstance(tech['pages'], list):
            for pg in tech['pages'][:5]:
                if isinstance(pg, dict) and pg.get('title'):
                    candidate = _clean_display_name(pg.get('title'))
                    if candidate:
                        break
        if candidate:
            updates.append('nom = ?')
            params.append(candidate[:500])

    resume = str(ent.get('resume') or flat_results.get('resume') or '')
    tech_blob = ' '.join(
        filter(
            None,
            [
                str(tech.get('cms') or ''),
                str(tech.get('framework') or ''),
                _technologies_blob(flat_results.get('technologies')),
            ],
        )
    )
    text_for_sector = f'{resume} {tech_blob}'.strip()

    new_secteur: Optional[str] = None
    if _empty(ent.get('secteur')) and text_for_sector:
        new_secteur = analyzer.extract_sector('', text_for_sector, soup=None)
        if new_secteur and new_secteur != 'Non spécifié':
            updates.append('secteur = ?')
            params.append(str(new_secteur)[:300])

    if _empty(ent.get('taille_estimee')) and text_for_sector:
        cat_for_size = (new_secteur or str(ent.get('secteur') or '')).strip()
        taille = analyzer.estimate_company_size(None, text_for_sector, cat_for_size)
        if taille:
            updates.append('taille_estimee = ?')
            params.append(str(taille)[:300])

    if _empty(ent.get('responsable')):
        resp = _pick_responsable_from_people(flat_results.get('people'))
        if resp:
            updates.append('responsable = ?')
            params.append(resp)

    hp = str(tech.get('hosting_provider') or '').strip()
    if _empty(ent.get('hosting_provider')) and hp:
        updates.append('hosting_provider = ?')
        params.append(hp[:300])

    cp = str(ent.get('code_postal') or '').strip()
    ville = str(ent.get('ville') or '').strip()
    if _empty(ent.get('address_2')) and (cp or ville):
        line2 = f'{cp} {ville}'.strip()
        if line2:
            updates.append('address_2 = ?')
            params.append(line2[:500])

    if not updates:
        return

    params.append(entreprise_id)
    conn = database.get_connection()
    cursor = conn.cursor()
    try:
        sql = f'UPDATE entreprises SET {", ".join(updates)} WHERE id = ?'
        database.execute_sql(cursor, sql, tuple(params))
        conn.commit()
    except Exception as e:
        logger.warning('finalize_entreprise_fiche: %s', e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    try:
        database.update_opportunity_score(entreprise_id)
    except Exception as e:
        logger.debug('update_opportunity_score après finalize: %s', e)


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
    enable_technical: bool = True,
    enable_seo: bool = True,
    enable_osint: bool = True,
    enable_pentest: bool = True,
):
    """
    Corps du pack d’analyses (appelé par la tâche Celery enregistrée dans analysis_tasks).
    """
    t0 = time.monotonic()
    database = Database()
    steps: Dict[str, str] = {}
    scrape_counts: Dict[str, int] = {}
    image_urls: List[str] = []
    scraper_id: Optional[int] = None
    external_link_event_seq = 0
    last_external_link_ts = 0.0

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
                'scraper_id': scraper_id,
            },
        )

    progress('init', 2, 'Préparation du pack d\'analyses…')

    flat_results: dict = {}

    # 1) Scraping
    try:
        progress('scraping', 8, 'Scraping (emails, images, formulaires)…')
        def _scrape_progress_cb(msg: str):
            try:
                m = str(msg or '').strip()
            except Exception:
                m = ''
            if not m:
                return
            progress('scraping', 12, m[:260])

        def _on_external_link_found(entry: dict):
            nonlocal external_link_event_seq, last_external_link_ts
            now = time.monotonic()
            if now - last_external_link_ts < 0.25:
                return
            last_external_link_ts = now
            external_link_event_seq += 1
            try:
                domain_host = (entry.get('domain') or '')[:255]
                href = (entry.get('url') or '')[:1200]
                source_page = (entry.get('page_url') or '')[:1200]
                anchor_text = (entry.get('text') or '')[:400]
                likely_credit = bool(entry.get('likely_credit'))
                link_source = (entry.get('link_source') or '')[:80]
            except Exception:
                domain_host = href = source_page = anchor_text = link_source = ''
                likely_credit = False

            # On pousse un event “instantané” (avant persistance en base).
            self.update_state(
                state='PROGRESS',
                meta={
                    'step': 'scraping',
                    'progress': 14,
                    'message': 'Lien externe détecté…',
                    'steps': dict(steps),
                    'entreprise_id': entreprise_id,
                    'analyse_id': analyse_id,
                    'website': url,
                    'scraper_id': scraper_id,
                    'scraper_external_link_event_seq': external_link_event_seq,
                    'scraper_external_link_event': {
                        'domain_host': domain_host,
                        'external_href': href,
                        'source_page_url': source_page,
                        'anchor_text': anchor_text,
                        'likely_credit': likely_credit,
                        'link_source': link_source,
                    },
                },
            )

        scrape_out = run_scrape_emails_inline(
            url=url,
            max_depth=max_depth,
            max_workers=max_workers,
            max_time=max_time,
            max_pages=max_pages,
            entreprise_id=entreprise_id,
            progress_callback=_scrape_progress_cb,
            on_external_link_found=_on_external_link_found,
        )
        if scrape_out.get('success') and scrape_out.get('results'):
            flat_results = scrape_out['results']
            try:
                sid = scrape_out.get('scraper_id')
                scraper_id = int(sid) if sid is not None else None
            except Exception:
                scraper_id = None
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
            _persist_scraper_branding_and_og(database, entreprise_id, url, flat_results)
        steps['scraping'] = 'ok' if scrape_out.get('success') else 'erreur'
    except Exception as e:
        logger.exception('Full analysis: scraping échoué')
        steps['scraping'] = f'erreur: {e!s}'[:200]

    # Scraping réellement terminé (UnifiedScraper attend tous les threads) avant toute autre étape.
    modules_hint = ', '.join(
        n
        for n, on in (
            ('technique', enable_technical),
            ('SEO', enable_seo),
            ('OSINT', enable_osint),
            ('pentest', enable_pentest),
        )
        if on
    ) or 'aucun module optionnel'
    if steps.get('scraping') == 'ok':
        progress(
            'scraping',
            22,
            f'Scraping terminé, lancement des modules sélectionnés ({modules_hint})…',
        )
    else:
        progress(
            'scraping',
            22,
            f'Scraping terminé avec des erreurs ; poursuite ({modules_hint})…',
        )

    # Réduit les HTTP 429 avant la prochaine salve HTTP (technique / SEO / …).
    any_post_scrape = enable_technical or enable_seo or enable_osint or enable_pentest
    if any_post_scrape and FULL_ANALYSIS_INTER_STEP_PAUSE_SEC > 0:
        logger.info(
            'Pause %.1fs avant les analyses (FULL_ANALYSIS_INTER_STEP_PAUSE_SEC).',
            FULL_ANALYSIS_INTER_STEP_PAUSE_SEC,
        )
        time.sleep(FULL_ANALYSIS_INTER_STEP_PAUSE_SEC)

    people_osint = _map_people_for_osint(flat_results.get('people'))
    emails_osint = _emails_as_strings(flat_results.get('emails'))
    social_osint = _flatten_social(flat_results.get('social_links'))
    phones_osint = _phones_as_strings(flat_results.get('phones'))
    forms_pentest = flat_results.get('forms') or []
    if isinstance(forms_pentest, list) and forms_pentest:
        from services.pentest_analyzer import deduplicate_forms_for_storage

        n_forms_raw = len(forms_pentest)
        forms_pentest = deduplicate_forms_for_storage(forms_pentest, url)
        if n_forms_raw != len(forms_pentest):
            scrape_counts['forms'] = len(forms_pentest)

    # 2) Technique
    if enable_technical:
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
    else:
        steps['technical'] = 'désactivé'

    # 3) SEO
    if enable_seo:
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
    else:
        steps['seo'] = 'désactivé'

    # 4) OSINT (téléphones : tâche dédiée analyze_phones_task, comme analyze_emails_task)
    phone_pack = None
    if enable_osint:
        try:
            if phones_osint:
                progress('phone_osint', 58, 'Analyse OSINT des numéros de téléphone…')
                phone_pack = _run_subtask_eager(
                    analyze_phones_task,
                    phones=phones_osint,
                    source_url=url,
                    entreprise_id=entreprise_id,
                )
                steps['phone_osint'] = 'ok'
        except Exception as e:
            logger.exception('Full analysis: analyse téléphones échouée')
            steps['phone_osint'] = f'erreur: {e!s}'[:200]

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
                phone_osint_result=phone_pack,
            )
            steps['osint'] = 'ok'
        except Exception as e:
            logger.exception('Full analysis: OSINT échoué')
            steps['osint'] = f'erreur: {e!s}'[:200]
    else:
        steps['phone_osint'] = 'désactivé'
        steps['osint'] = 'désactivé'

    # 5) Pentest
    if enable_pentest:
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
    else:
        steps['pentest'] = 'désactivé'

    try:
        _finalize_entreprise_fiche_after_pack(database, entreprise_id, url, flat_results)
    except Exception as e:
        logger.warning('Full analysis: finalisation fiche entreprise: %s', e)

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
        'message': f'Analyse terminée ({modules_hint}).',
    }

    progress('done', 100, f'Analyse terminée ({modules_hint}).')
    logger.info(
        'Full website analysis terminée pour %s (entreprise_id=%s) steps=%s',
        url,
        entreprise_id,
        steps,
    )
    return summary
