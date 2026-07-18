"""
Tâches Celery : rapport d'audit par email.

- simple : scraping → technique → SEO → pentest → PDF local → email
- complete : pack complet (6 modules) → rapport expert PDF → email

Si les analyses requises sont déjà en base pour la fiche entreprise, génération PDF + email directe.
"""

from __future__ import annotations

import re
import shutil
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from celery_app import celery
from config import (
    AUDIT_REPORTS_DIR,
    SEO_USE_LIGHTHOUSE_DEFAULT,
    WEBSITE_AUDIT_CURSOR_ALERT_EMAIL,
    WEBSITE_AUDIT_EMAIL_SUBJECT,
    WEBSITE_AUDIT_PENTEST_TIMEOUT_SEC,
    WEBSITE_AUDIT_SCRAPING_TIMEOUT_SEC,
    WEBSITE_AUDIT_SEO_TIMEOUT_SEC,
    BASE_URL,
    PUBLIC_WEBSITE_AUDIT_LEAD_KEY,
    WEBSITE_AUDIT_AGENT_FALLBACK_LOCAL,
    WEBSITE_AUDIT_AGENT_PAUSE_ON_AGENT_FAILURE,
    WEBSITE_AUDIT_SOFT_FAIL_MODULES,
    WEBSITE_AUDIT_TECHNICAL_TIMEOUT_SEC,
    WEBSITE_AUDIT_USAGE_LIMIT_RETRIES,
    WEBSITE_AUDIT_USAGE_LIMIT_RETRY_DELAY_SEC,
)
from services.database import Database
from services.email_sender import EmailSender
from services.logging_config import setup_logger
from services.cursor_usage_limit import CursorUsageLimitError
from services.website_audit_data import (
    audit_data_ready,
    audit_missing_modules,
    build_audit_pipeline,
    collect_audit_report_context,
)
from services.website_audit_pending import audit_site_slug, load_pending_agent_job, save_pending_agent_job
from services.website_audit_pdf import WebsiteAuditPdfGenerator
from utils.url_utils import canonical_website_https_url

logger = setup_logger(__name__, 'website_audit_report.log')

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

SIMPLE_MODULES = ['scraping', 'technical', 'seo', 'ux', 'pentest']
COMPLETE_MODULES = ['scraping', 'technical', 'seo', 'ux', 'screenshot', 'osint', 'pentest']
SIMPLE_MODULE_ORDER = SIMPLE_MODULES


def _task_label(self) -> str:
    return str(getattr(getattr(self, 'request', None), 'id', None) or '?')


def _audit_log(
    self,
    phase: str,
    message: str,
    *,
    level: str = 'info',
    website: str = '',
    mode: str = '',
    **extra: Any,
) -> None:
    tid = _task_label(self)
    parts = [f'[audit task={tid} mode={mode or "?"} phase={phase}]', message]
    if website:
        parts.append(f'website={website}')
    if extra:
        parts.append(' '.join(f'{k}={v!r}' for k, v in extra.items()))
    line = ' | '.join(parts)
    if level == 'exception':
        logger.exception(line)
    elif level == 'error':
        logger.error(line)
    elif level == 'warning':
        logger.warning(line)
    else:
        logger.info(line)


def _normalize_email(raw: str) -> Optional[str]:
    s = (raw or '').strip().lower()
    if not s or not _EMAIL_RE.match(s):
        return None
    return s


def _audit_email_scores(context: Optional[Dict[str, Any]]) -> List[tuple[str, str, str]]:
    """(label, valeur affichée, couleur) pour les pastilles de l'email."""
    if not context:
        return []
    pipeline = context.get('pipeline') or {}
    opp = context.get('opportunity') or {}
    chips: List[tuple[str, str, str]] = []

    def _add(label: str, raw: Any, *, invert: bool = False) -> None:
        if raw is None:
            return
        try:
            v = int(float(raw))
        except (TypeError, ValueError):
            return
        display = str(max(0, 100 - v) if invert else v)
        if v >= 70 and not invert:
            color = '#059669'
        elif v >= 45 and not invert:
            color = '#d97706'
        elif v < 40 and invert:
            color = '#059669'
        elif v < 70 and invert:
            color = '#d97706'
        else:
            color = '#dc2626'
        chips.append((label, f'{display}/100', color))

    tech = pipeline.get('technical') or {}
    if tech.get('status') == 'done':
        _add('Sécurité', tech.get('security_score'))
        _add('Performance', tech.get('performance_score'))
    seo = pipeline.get('seo') or {}
    if seo.get('status') == 'done':
        _add('SEO', seo.get('score'))
    pentest = pipeline.get('pentest') or {}
    if pentest.get('status') == 'done':
        _add('Risque pentest', pentest.get('risk_score'), invert=True)
    if opp.get('score') is not None:
        chips.append(('Opportunité', f'{int(opp["score"])}/100', '#4f46e5'))
    return chips[:5]


def _build_audit_email_bodies(
    company: str,
    website: str,
    *,
    variant: str = 'complete',
    context: Optional[Dict[str, Any]] = None,
    skipped_analysis: bool = False,
) -> tuple[str, str]:
    label = 'audit essentiel' if variant == 'simple' else 'audit complet'
    exec_lines = (context or {}).get('executive_summary') or []
    chips = _audit_email_scores(context)
    cache_note = (
        ' Les analyses en base ont été réutilisées (pas de nouveau scan).'
        if skipped_analysis
        else ''
    )

    text_lines = [
        'Bonjour,',
        '',
        f'Votre {label} pour {company} ({website}) est prêt.',
        (
            'Le PDF essentiel (scores + actions prioritaires) est en pièce jointe.'
            if variant == 'simple'
            else 'Le rapport complet est en pièce jointe.'
        ),
    ]
    if chips:
        text_lines.append('')
        text_lines.append('Scores clés :')
        for name, val, _ in chips:
            text_lines.append(f'  • {name} : {val}')
    if exec_lines:
        text_lines.append('')
        text_lines.append('Synthèse :')
        for line in exec_lines[:4]:
            text_lines.append(f'  • {line}')
    if skipped_analysis:
        text_lines.append('')
        text_lines.append('(Données issues du cache — analyse non relancée.)')
    text_lines.extend(['', 'Cordialement,', 'DanielCraft'])
    text = '\n'.join(text_lines)

    chip_html = ''
    if chips:
        cells = ''.join(
            f'<td style="padding:6px 10px;text-align:center;">'
            f'<div style="font-size:22px;font-weight:700;color:{color};">{val}</div>'
            f'<div style="font-size:11px;color:#64748b;margin-top:4px;">{name}</div>'
            f'</td>'
            for name, val, color in chips
        )
        chip_html = (
            '<table role="presentation" cellpadding="0" cellspacing="0" '
            'style="width:100%;margin:18px 0;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">'
            f'<tr>{cells}</tr></table>'
        )

    summary_html = ''
    if exec_lines:
        items = ''.join(
            f'<li style="margin-bottom:8px;line-height:1.45;color:#334155;">{line}</li>'
            for line in exec_lines[:4]
        )
        summary_html = (
            '<p style="font-size:13px;font-weight:600;color:#0f766e;margin:16px 0 8px;">'
            'Synthèse exécutive</p><ul style="margin:0;padding-left:20px;font-size:13px;">'
            f'{items}</ul>'
        )

    cache_html = ''
    if skipped_analysis:
        cache_html = (
            '<p style="font-size:12px;color:#64748b;background:#f1f5f9;padding:10px 12px;'
            'border-radius:6px;margin-top:14px;">'
            'Analyses récentes déjà en base — rapport généré sans relancer les modules.'
            '</p>'
        )

    intro_html = (
        'Votre audit essentiel est prêt : synthèse courte, scores et priorités.'
        if variant == 'simple'
        else (
            'Votre audit complet est prêt : synthèse experte, données mesurées, '
            'captures et plan d\'action.'
        )
    )
    attach_html = (
        '<strong>Pièce jointe :</strong> audit essentiel (version gratuite).'
        if variant == 'simple'
        else '<strong>Pièce jointe :</strong> audit complet (version détaillée).'
    )
    html = (
        '<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto;color:#0f172a;">'
        '<div style="background:linear-gradient(135deg,#0f766e 0%,#134e4a 100%);color:#fff;'
        'padding:28px 26px;border-radius:10px 10px 0 0;">'
        f'<p style="margin:0;font-size:11px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;">'
        'DanielCraft</p>'
        f'<h1 style="margin:10px 0 0;font-size:22px;font-weight:600;">{label.capitalize()}</h1>'
        f'<p style="margin:8px 0 0;font-size:14px;opacity:0.95;">{company}</p>'
        f'<p style="margin:4px 0 0;font-size:12px;opacity:0.8;">{website}</p></div>'
        '<div style="background:#ffffff;padding:26px;border:1px solid #e2e8f0;border-top:none;'
        'border-radius:0 0 10px 10px;">'
        f'<p style="font-size:14px;line-height:1.55;margin:0;color:#334155;">{intro_html}{cache_note}</p>'
        f'{chip_html}{summary_html}'
        '<p style="font-size:13px;margin:20px 0 0;padding:14px;background:#ecfdf5;border-left:4px solid #0f766e;'
        'border-radius:0 6px 6px 0;color:#134e4a;">'
        f'{attach_html}</p>'
        f'{cache_html}'
        '<p style="font-size:11px;color:#94a3b8;margin-top:24px;border-top:1px solid #e2e8f0;padding-top:14px;">'
        'DanielCraft · Message automatique</p></div></div>'
    )
    return text, html


def _ensure_entreprise(
    db: Database,
    *,
    url: str,
    email: str,
    entreprise_id: Optional[int],
    analyse_id: Optional[int],
) -> int:
    netloc = urlparse(url).netloc or url
    if not entreprise_id:
        entreprise_id = db.save_entreprise(
            analyse_id=analyse_id,
            entreprise_data={
                'name': netloc,
                'website': url,
                'statut': 'Nouveau',
                'email_principal': email,
            },
            skip_duplicates=True,
        )
    if not entreprise_id:
        raise RuntimeError('Impossible de créer ou retrouver la fiche entreprise')
    return int(entreprise_id)


def _run_audit_module(
    self,
    module: str,
    task,
    *,
    url: str,
    mode: str,
    timeout_sec: int,
    soft_fail: bool,
    **kwargs: Any,
) -> Tuple[str, Any]:
    """Exécute un sous-module avec timeout optionnel ; ne bloque pas les suivants si soft_fail."""
    from tasks.full_website_analysis import _run_subtask_eager

    run_kwargs = {'url': url, **kwargs}
    t0 = time.monotonic()
    _audit_log(
        self,
        f'module.{module}',
        'démarrage',
        website=url,
        mode=mode,
        timeout_sec=timeout_sec,
        kwargs_keys=sorted(run_kwargs.keys()),
    )
    try:
        if timeout_sec and timeout_sec > 0:
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix=f'audit-{module}') as pool:
                fut = pool.submit(_run_subtask_eager, task, **run_kwargs)
                result = fut.result(timeout=timeout_sec)
        else:
            result = _run_subtask_eager(task, **run_kwargs)
        elapsed = time.monotonic() - t0
        _audit_log(
            self,
            f'module.{module}',
            'terminé OK',
            website=url,
            mode=mode,
            elapsed_sec=round(elapsed, 1),
        )
        return 'ok', result
    except FuturesTimeoutError:
        elapsed = time.monotonic() - t0
        _audit_log(
            self,
            f'module.{module}',
            f'TIMEOUT après {timeout_sec}s — poursuite pipeline',
            level='error',
            website=url,
            mode=mode,
            elapsed_sec=round(elapsed, 1),
        )
        if soft_fail:
            return f'timeout:{timeout_sec}s', None
        raise RuntimeError(f'Module {module} timeout ({timeout_sec}s)') from None
    except Exception as exc:
        elapsed = time.monotonic() - t0
        _audit_log(
            self,
            f'module.{module}',
            f'échec: {exc!s}',
            level='exception',
            website=url,
            mode=mode,
            elapsed_sec=round(elapsed, 1),
        )
        logger.exception('Module audit %s échoué pour %s', module, url)
        if soft_fail:
            return f'erreur:{exc!s}'[:200], None
        raise


def _send_audit_email(
    self,
    *,
    to: str,
    company: str,
    website: str,
    pdf_path: Path,
    variant: str,
    mode: str,
    context: Optional[Dict[str, Any]] = None,
    skipped_analysis: bool = False,
) -> None:
    subject = WEBSITE_AUDIT_EMAIL_SUBJECT.format(company=company, website=website)
    text_body, html_body = _build_audit_email_bodies(
        company,
        website,
        variant=variant,
        context=context,
        skipped_analysis=skipped_analysis,
    )
    size_kb = round(pdf_path.stat().st_size / 1024, 1) if pdf_path.is_file() else 0
    _audit_log(
        self,
        'email',
        'envoi SMTP',
        website=website,
        mode=mode,
        to=to,
        subject=subject,
        pdf=pdf_path.name,
        size_kb=size_kb,
    )
    send_result = EmailSender().send_email(
        to=to,
        subject=subject,
        body=text_body,
        html_body=html_body,
        attachments=[{
            'path': str(pdf_path),
            'filename': _customer_pdf_filename(variant, company),
        }],
    )
    if not send_result.get('success'):
        _audit_log(
            self,
            'email',
            f'échec: {send_result.get("message")}',
            level='error',
            website=website,
            mode=mode,
        )
        raise RuntimeError(send_result.get('message') or 'Échec envoi email')
    _audit_log(
        self,
        'email',
        'envoyé avec succès',
        website=website,
        mode=mode,
        to=to,
        message_id=send_result.get('message_id'),
    )


def _forms_from_latest_scraper(db: Database, entreprise_id: int, url: str) -> Optional[List[Dict[str, Any]]]:
    """Formulaires du dernier scraping (pour pentest si scraping déjà en cache)."""
    try:
        scrapers = db.get_scrapers_by_entreprise(entreprise_id) or []
    except Exception:
        return None
    if not scrapers:
        return None
    forms = scrapers[0].get('forms') or []
    if not forms:
        return None
    from services.pentest_analyzer import deduplicate_forms_for_storage

    return deduplicate_forms_for_storage(forms, url)


def _run_audit_scraping(
    self,
    db: Database,
    url: str,
    entreprise_id: int,
    *,
    mode: str,
    max_depth: int,
    max_workers: int,
    max_time: int,
    max_pages: int,
    soft_fail: bool,
) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
    from tasks.scraping_tasks import run_scrape_emails_inline
    from tasks.full_website_analysis import _apply_scrape_to_entreprise, _persist_scraper_branding_and_og
    from services.pentest_analyzer import deduplicate_forms_for_storage

    timeout_sec = WEBSITE_AUDIT_SCRAPING_TIMEOUT_SEC
    t0 = time.monotonic()
    _audit_log(
        self,
        'module.scraping',
        'démarrage scraping inline',
        website=url,
        mode=mode,
        max_depth=max_depth,
        max_pages=max_pages,
        timeout_sec=timeout_sec,
    )

    def _do_scrape():
        return run_scrape_emails_inline(
            url=url,
            max_depth=max_depth,
            max_workers=max_workers,
            max_time=max_time,
            max_pages=max_pages,
            entreprise_id=entreprise_id,
        )

    try:
        if timeout_sec and timeout_sec > 0:
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix='audit-scraping') as pool:
                scrape_out = pool.submit(_do_scrape).result(timeout=timeout_sec)
        else:
            scrape_out = _do_scrape()
        if scrape_out.get('success') and scrape_out.get('results'):
            flat = scrape_out['results']
            _apply_scrape_to_entreprise(db, entreprise_id, flat)
            _persist_scraper_branding_and_og(db, entreprise_id, url, flat)
            forms = flat.get('forms') or []
            if isinstance(forms, list) and forms:
                forms = deduplicate_forms_for_storage(forms, url)
            _audit_log(
                self,
                'module.scraping',
                'terminé OK',
                website=url,
                mode=mode,
                elapsed_sec=round(time.monotonic() - t0, 1),
                emails=int(flat.get('total_emails') or 0),
                forms=len(forms) if forms else 0,
            )
            return 'ok', forms or None
        _audit_log(
            self,
            'module.scraping',
            'échec scraping (success=false)',
            level='error',
            website=url,
            mode=mode,
            detail=str(scrape_out.get('error') or '')[:200],
        )
        if soft_fail:
            return 'erreur:scraping_failed', None
        raise RuntimeError(scrape_out.get('error') or 'Scraping échoué')
    except FuturesTimeoutError:
        _audit_log(
            self,
            'module.scraping',
            f'TIMEOUT après {timeout_sec}s',
            level='error',
            website=url,
            mode=mode,
        )
        if soft_fail:
            return f'timeout:{timeout_sec}s', None
        raise RuntimeError(f'Scraping timeout ({timeout_sec}s)') from None
    except Exception as exc:
        logger.exception('Scraping audit échoué pour %s', url)
        if soft_fail:
            return f'erreur:{exc!s}'[:200], None
        raise


def _run_simple_analysis(
    self,
    db: Database,
    url: str,
    entreprise_id: int,
    *,
    missing_modules: List[str],
    enable_nmap: bool,
    use_lighthouse: bool,
    max_depth: int,
    max_workers: int,
    max_time: int,
    max_pages: int,
) -> Dict[str, str]:
    """Scraping puis technique, SEO, pentest — uniquement les modules manquants."""
    from tasks.technical_analysis_tasks import technical_analysis_task
    from tasks.seo_tasks import seo_analysis_task
    from tasks.ux_tasks import ux_analysis_task
    from tasks.pentest_tasks import pentest_analysis_task

    soft = WEBSITE_AUDIT_SOFT_FAIL_MODULES
    steps: Dict[str, str] = {m: 'cached' for m in SIMPLE_MODULE_ORDER if m not in missing_modules}
    forms_pentest: Optional[List[Dict[str, Any]]] = None
    progress_map = {'scraping': 20, 'technical': 35, 'seo': 50, 'ux': 60, 'pentest': 75}

    for module in SIMPLE_MODULE_ORDER:
        if module not in missing_modules:
            continue

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'simple_analysis',
                'progress': progress_map.get(module, 50),
                'module': module,
                'steps': steps,
            },
        )

        if module == 'scraping':
            status, forms_pentest = _run_audit_scraping(
                self,
                db,
                url,
                entreprise_id,
                mode='simple',
                max_depth=max_depth,
                max_workers=max_workers,
                max_time=max_time,
                max_pages=max_pages,
                soft_fail=soft,
            )
            steps['scraping'] = status
            continue

        if module == 'pentest' and forms_pentest is None:
            forms_pentest = _forms_from_latest_scraper(db, entreprise_id, url)

        if module == 'technical':
            status, _ = _run_audit_module(
                self,
                'technical',
                technical_analysis_task,
                url=url,
                mode='simple',
                timeout_sec=WEBSITE_AUDIT_TECHNICAL_TIMEOUT_SEC,
                soft_fail=soft,
                entreprise_id=entreprise_id,
                enable_nmap=enable_nmap,
            )
            steps['technical'] = status
        elif module == 'seo':
            status, _ = _run_audit_module(
                self,
                'seo',
                seo_analysis_task,
                url=url,
                mode='simple',
                timeout_sec=WEBSITE_AUDIT_SEO_TIMEOUT_SEC,
                soft_fail=soft,
                entreprise_id=entreprise_id,
                use_lighthouse=use_lighthouse,
            )
            steps['seo'] = status
        elif module == 'ux':
            status, _ = _run_audit_module(
                self,
                'ux',
                ux_analysis_task,
                url=url,
                mode='simple',
                timeout_sec=WEBSITE_AUDIT_SEO_TIMEOUT_SEC,
                soft_fail=soft,
                entreprise_id=entreprise_id,
            )
            steps['ux'] = status
        elif module == 'pentest':
            status, _ = _run_audit_module(
                self,
                'pentest',
                pentest_analysis_task,
                url=url,
                mode='simple',
                timeout_sec=WEBSITE_AUDIT_PENTEST_TIMEOUT_SEC,
                soft_fail=soft,
                entreprise_id=entreprise_id,
                options={},
                forms_from_scrapers=forms_pentest,
            )
            steps['pentest'] = status

    _audit_log(self, 'simple_analysis', 'résumé modules', website=url, mode='simple', steps=steps)
    return steps


def _cached_analysis_steps(mode: str) -> Dict[str, str]:
    modules = SIMPLE_MODULES if mode == 'simple' else COMPLETE_MODULES
    return {m: 'cached' for m in modules}


def _build_agent_resume_url(
    pending_id: str,
    *,
    resume_token: Optional[str] = None,
    website: Optional[str] = None,
) -> str:
    from urllib.parse import quote

    base = (BASE_URL or 'http://localhost:5000').rstrip('/')
    url = f'{base}/api/public/website-audit-report/complete/resume?pending_id={quote(pending_id, safe="")}'
    token = (resume_token or '').strip()
    if not token:
        pending = load_pending_agent_job(pending_id=pending_id, website=website)
        token = ((pending or {}).get('resume_token') or '').strip()
    if token:
        url += f'&resume_token={quote(token, safe="")}'
    elif PUBLIC_WEBSITE_AUDIT_LEAD_KEY:
        url += f'&audit_key={quote(PUBLIC_WEBSITE_AUDIT_LEAD_KEY, safe="")}'
    return url


def _send_agent_pause_alert(
    *,
    website: str,
    company: str,
    pending_id: str,
    task_id: str,
    recipient_email: str,
    reason: str,
    detail: Optional[str] = None,
    local_pdf_path: Optional[str] = None,
    resume_token: Optional[str] = None,
) -> None:
    alert_to = WEBSITE_AUDIT_CURSOR_ALERT_EMAIL
    if not alert_to:
        logger.warning(
            '[audit agent_pause] WEBSITE_AUDIT_CURSOR_ALERT_EMAIL non configuré — alerte non envoyée | website=%s',
            website,
        )
        return
    resume_url = _build_agent_resume_url(
        pending_id,
        resume_token=resume_token,
        website=website,
    )
    if reason == 'cursor_usage_limit':
        cause = 'Quota de production du rapport atteint (recharger le compte ou réessayer plus tard).'
        subject = f'[Audit] Rapport complet en pause — quota ({company})'
    else:
        cause = 'La production du rapport complet n\'a pas abouti (indisponibilité ou délai dépassé).'
        subject = f'[Audit] Rapport complet en pause — reprise requise ({company})'
    text = (
        f'La génération du rapport complet (audit payant) est en PAUSE pour {company} ({website}).\n\n'
        f'Cause : {cause}\n'
        f'Tâche Celery : {task_id}\n'
        f'Pending : {pending_id}\n'
        f'Lead : {recipient_email}\n'
    )
    if detail:
        text += f'Détail : {detail[:800]}\n'
    if local_pdf_path:
        text += f'PDF de référence interne : {local_pdf_path}\n'
    text += (
        f'\nReprendre la génération (un clic) :\n{resume_url}\n\n'
        f'Alternative API : POST {(BASE_URL or "http://localhost:5000").rstrip("/")}/api/public/website-audit-report/complete/resume '
        f'avec pending_id={pending_id}\n'
    )
    html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:560px;">'
        '<div style="background:#7f1d1d;color:#fff;padding:18px 20px;border-radius:8px 8px 0 0;">'
        '<h1 style="margin:0;font-size:18px;">Audit complet en pause</h1></div>'
        '<div style="padding:20px;border:1px solid #fecaca;background:#fff;">'
        f'<p><strong>{company}</strong><br/>{website}</p>'
        f'<p>{cause}</p>'
        f'<p style="font-size:13px;color:#334155;">Tâche : <code>{task_id}</code><br/>'
        f'Pending : <code>{pending_id}</code><br/>Lead : {recipient_email}</p>'
        f'<p style="margin:20px 0;"><a href="{resume_url}" '
        'style="display:inline-block;background:#0f766e;color:#fff;padding:12px 18px;'
        'border-radius:6px;text-decoration:none;font-weight:600;">'
        'Reprendre la génération PDF + envoi</a></p>'
        f'<p style="font-size:11px;color:#64748b;word-break:break-all;">{resume_url}</p>'
        '</div></div>'
    )
    try:
        EmailSender().send_email(to=alert_to, subject=subject, body=text, html_body=html)
    except Exception as exc:
        logger.warning('Alerte pause agent non envoyée: %s', exc)


def _pause_agent_pdf_generation(
    self,
    *,
    eid: int,
    url: str,
    email: str,
    context: Dict[str, Any],
    analysis_steps: Dict[str, str],
    skipped_analysis: bool,
    extra_instructions: Optional[str],
    local_baseline: Path,
    reason: str,
    detail: str,
    pending_id: Optional[str] = None,
) -> Dict[str, Any]:
    from services.website_audit_pending import release_audit_resume_lock

    if pending_id:
        release_audit_resume_lock(pending_id)
    pending_payload = {
        'status': 'paused_agent',
        'reason': reason,
        'website': url,
        'recipient_email': email,
        'entreprise_id': eid,
        'company_name': context.get('company_name'),
        'extra_instructions': extra_instructions,
        'analysis_steps': analysis_steps,
        'skipped_analysis': skipped_analysis,
        'agent_only': True,
        'celery_task_id': _task_label(self),
        'local_pdf_path': str(local_baseline),
        'detail': detail[:1500] if detail else '',
    }
    if pending_id:
        pending_payload['pending_id'] = pending_id
    pending_id = save_pending_agent_job(pending_payload)
    pending_loaded = load_pending_agent_job(pending_id=pending_id, website=url) or pending_payload
    resume_token = (pending_loaded.get('resume_token') or '').strip()
    company = context.get('company_name') or urlparse(url).netloc or url
    _send_agent_pause_alert(
        website=url,
        company=company,
        pending_id=pending_id,
        task_id=_task_label(self),
        recipient_email=email,
        reason=reason,
        detail=detail,
        local_pdf_path=str(local_baseline),
        resume_token=resume_token,
    )
    resume_url = _build_agent_resume_url(pending_id, resume_token=resume_token, website=url)
    self.update_state(
        state='PROGRESS',
        meta={
            'step': 'paused_agent',
            'progress': 88,
            'paused': True,
            'reason': reason,
            'pending_id': pending_id,
            'resume_url': resume_url,
            'resume_endpoint': '/api/public/website-audit-report/complete/resume',
            'local_pdf_path': str(local_baseline),
        },
    )
    _audit_log(
        self,
        'agent_pdf',
        f'pause — agent indisponible ({reason}), alerte admin envoyée',
        level='warning',
        website=url,
        mode='complete',
        pending_id=pending_id,
        reason=reason,
        detail=(detail[:1200] if detail else ''),
    )
    return {
        'success': False,
        'paused': True,
        'reason': reason,
        'pending_id': pending_id,
        'resume_url': resume_url,
        'website': url,
        'recipient_email': email,
        'entreprise_id': eid,
        'local_pdf_path': str(local_baseline),
        'email_sent': False,
        'message': (
            'Analyses terminées ; production du rapport complet en pause. '
            'Utilisez le lien de reprise dans l\'email admin ou POST .../complete/resume.'
        ),
    }


def _audit_output_dir(url: str) -> Path:
    d = AUDIT_REPORTS_DIR / audit_site_slug(url)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _customer_pdf_filename(variant: str, company: str) -> str:
    safe = re.sub(r'[^\w\-]+', '_', (company or 'site').strip())[:48].strip('_') or 'site'
    if variant == 'simple':
        return f'audit-essentiel-{safe}.pdf'
    return f'audit-complet-{safe}.pdf'


def _generate_local_baseline_pdf(
    context: Dict[str, Any],
    *,
    url: str,
) -> Path:
    """PDF interne (référence agent uniquement — jamais envoyé au client)."""
    return WebsiteAuditPdfGenerator(_audit_output_dir(url)).generate(
        context,
        filename='audit_report_reference_baseline.pdf',
        report_tier='full',
    )


def _generate_complete_fallback_pdf(
    context: Dict[str, Any],
    *,
    url: str,
    eid: int,
) -> Path:
    """Repli payant si l'agent échoue : rapport détaillé local, distinct du gratuit."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return WebsiteAuditPdfGenerator(_audit_output_dir(url)).generate(
        context,
        filename=f'audit_complet_local_{eid}_{ts}.pdf',
        report_tier='complete_fallback',
    )


def _deliver_audit_report(
    self,
    db: Database,
    *,
    eid: int,
    url: str,
    email: str,
    mode: str,
    variant: str,
    analysis_steps: Dict[str, str],
    skipped_analysis: bool,
    extra_instructions: Optional[str] = None,
    agent_only: bool = False,
    pending_local_pdf: Optional[str] = None,
    resume_pending_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Collecte contexte, génère PDF, envoie email."""
    self.update_state(
        state='PROGRESS',
        meta={'step': 'collect', 'progress': 78, 'steps': analysis_steps, 'skipped_analysis': skipped_analysis},
    )
    context = collect_audit_report_context(
        db, eid, website=url, recipient_email=email, report_mode=mode,
    )
    _audit_log(
        self,
        'collect',
        'contexte audit agrégé',
        website=url,
        mode=mode,
        skipped_analysis=skipped_analysis,
        pipeline_keys=list((context.get('pipeline') or {}).keys()),
    )

    if mode == 'complete':
        pdf_engine_used = 'expert'
        local_baseline: Optional[Path] = None
        if agent_only and pending_local_pdf:
            candidate = Path(pending_local_pdf)
            if candidate.is_file() and candidate.stat().st_size > 1024:
                local_baseline = candidate
                _audit_log(
                    self,
                    'pdf_baseline',
                    'PDF de référence réutilisé (reprise, sans régénération)',
                    website=url,
                    mode=mode,
                    path=str(local_baseline),
                )
        if local_baseline is None:
            local_baseline = _generate_local_baseline_pdf(context, url=url)
        context = {
            **context,
            'local_pdf_path': str(local_baseline),
            'resume_import_only': bool(agent_only),
        }
        if not agent_only or not pending_local_pdf:
            _audit_log(
                self,
                'pdf_baseline',
                'PDF de référence interne pour agent',
                website=url,
                mode=mode,
                path=str(local_baseline),
            )
        try:
            raw_agent_pdf = _generate_pdf_agent(self, context, extra_instructions=extra_instructions, url=url)
            from services.website_audit_agent import resolve_agent_audit_pdf

            pdf_path = resolve_agent_audit_pdf(url, AUDIT_REPORTS_DIR, hinted_path=raw_agent_pdf)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            delivered = _audit_output_dir(url) / f'audit_complet_{ts}.pdf'
            shutil.copy2(pdf_path, delivered)
            pdf_path = delivered
            _audit_log(
                self,
                'agent_pdf',
                'PDF agent livré au client',
                website=url,
                mode=mode,
                path=str(pdf_path),
                size_kb=round(pdf_path.stat().st_size / 1024, 1),
            )
        except CursorUsageLimitError as cul:
            if WEBSITE_AUDIT_AGENT_PAUSE_ON_AGENT_FAILURE:
                return _pause_agent_pdf_generation(
                    self,
                    eid=eid,
                    url=url,
                    email=email,
                    context=context,
                    analysis_steps=analysis_steps,
                    skipped_analysis=skipped_analysis,
                    extra_instructions=extra_instructions,
                    local_baseline=local_baseline,
                    reason='cursor_usage_limit',
                    detail=cul.detail if cul.detail else str(cul),
                    pending_id=resume_pending_id,
                )
            raise
        except Exception as agent_err:
            if WEBSITE_AUDIT_AGENT_PAUSE_ON_AGENT_FAILURE:
                return _pause_agent_pdf_generation(
                    self,
                    eid=eid,
                    url=url,
                    email=email,
                    context=context,
                    analysis_steps=analysis_steps,
                    skipped_analysis=skipped_analysis,
                    extra_instructions=extra_instructions,
                    local_baseline=local_baseline,
                    reason='agent_unavailable',
                    detail=str(agent_err),
                    pending_id=resume_pending_id,
                )
            if WEBSITE_AUDIT_AGENT_FALLBACK_LOCAL:
                _audit_log(
                    self,
                    'agent_pdf',
                    f'échec agent, repli local (FALLBACK_LOCAL): {agent_err!s}',
                    level='warning',
                    website=url,
                    mode=mode,
                )
                self.update_state(state='PROGRESS', meta={'step': 'pdf_local_fallback', 'progress': 88})
                pdf_path = _generate_complete_fallback_pdf(context, url=url, eid=eid)
                pdf_engine_used = 'local_fallback'
                _audit_log(
                    self,
                    'agent_pdf',
                    'repli rapport complet local (agent indisponible)',
                    level='warning',
                    website=url,
                    mode=mode,
                    path=str(pdf_path),
                )
            else:
                raise
    else:
        self.update_state(state='PROGRESS', meta={'step': 'pdf_local', 'progress': 85})
        pdf_path = _generate_pdf_local(self, context, url=url, mode=mode)
        pdf_engine_used = 'local'

    self.update_state(state='PROGRESS', meta={'step': 'email', 'progress': 94})
    company = context.get('company_name') or urlparse(url).netloc or url
    _send_audit_email(
        self,
        to=email,
        company=company,
        website=url,
        pdf_path=pdf_path,
        variant=variant,
        mode=mode,
        context=context,
        skipped_analysis=skipped_analysis,
    )

    modules = SIMPLE_MODULES if mode == 'simple' else COMPLETE_MODULES
    return {
        'success': True,
        'mode': mode,
        'website': url,
        'recipient_email': email,
        'entreprise_id': eid,
        'pdf_path': str(pdf_path),
        'pdf_engine': pdf_engine_used,
        'analysis_modules': modules,
        'analysis_steps': analysis_steps,
        'skipped_analysis': skipped_analysis,
        'email_sent': True,
        'company_name': company,
    }


def _generate_pdf_local(
    self,
    context: Dict[str, Any],
    *,
    url: str,
    mode: str,
) -> Path:
    _audit_log(self, 'pdf_local', 'génération ReportLab', website=url, mode=mode)
    t0 = time.monotonic()
    pdf_path = WebsiteAuditPdfGenerator(_audit_output_dir(url)).generate(
        context,
        report_tier='essential' if mode == 'simple' else 'full',
    )
    size_kb = round(pdf_path.stat().st_size / 1024, 1) if pdf_path.is_file() else 0
    _audit_log(
        self,
        'pdf_local',
        'PDF prêt',
        website=url,
        mode=mode,
        path=str(pdf_path),
        size_kb=size_kb,
        elapsed_sec=round(time.monotonic() - t0, 1),
    )
    return pdf_path


def _generate_pdf_agent(
    self,
    context: Dict[str, Any],
    *,
    extra_instructions: Optional[str],
    url: str,
) -> Path:
    from tasks.landing_variant_tasks import _release_slot, _wait_for_slot
    from services.website_audit_agent import generate_audit_pdf_via_agent

    _audit_log(self, 'agent_pdf', 'attente slot agent Cursor', website=url, mode='complete')
    if not _wait_for_slot(self):
        raise RuntimeError("Timeout d'attente du slot agent Cursor (occupé)")
    try:
        self.update_state(state='PROGRESS', meta={'step': 'agent_pdf', 'progress': 86})
        _audit_log(self, 'agent_pdf', 'génération PDF par agent Cursor', website=url, mode='complete')
        t0 = time.monotonic()
        try:
            pdf_path = generate_audit_pdf_via_agent(
                context,
                output_dir=AUDIT_REPORTS_DIR,
                extra_instructions=extra_instructions,
            )
        except CursorUsageLimitError:
            retries = int(getattr(getattr(self, 'request', None), 'retries', 0) or 0)
            if retries < WEBSITE_AUDIT_USAGE_LIMIT_RETRIES:
                _audit_log(
                    self,
                    'agent_pdf',
                    f'usage limit — retry {retries + 1}/{WEBSITE_AUDIT_USAGE_LIMIT_RETRIES}',
                    level='warning',
                    website=url,
                    mode='complete',
                )
                raise self.retry(
                    countdown=WEBSITE_AUDIT_USAGE_LIMIT_RETRY_DELAY_SEC,
                    exc=CursorUsageLimitError('usage_limit_retry'),
                )
            raise
        _audit_log(
            self,
            'agent_pdf',
            'PDF agent reçu',
            website=url,
            mode='complete',
            path=str(pdf_path),
            elapsed_sec=round(time.monotonic() - t0, 1),
        )
        return pdf_path
    finally:
        _release_slot()


_generate_pdf_serv1 = _generate_pdf_agent


@celery.task(
    bind=True,
    name='tasks.website_audit_report_tasks.website_audit_simple_report_task',
    time_limit=3600,
    soft_time_limit=3500,
)
def website_audit_simple_report_task(
    self,
    website: str,
    recipient_email: str,
    entreprise_id: Optional[int] = None,
    analyse_id: Optional[int] = None,
    enable_nmap: bool = False,
    use_lighthouse: Optional[bool] = None,
    max_depth: int = 2,
    max_workers: int = 5,
    max_time: int = 300,
    max_pages: int = 40,
) -> Dict[str, Any]:
    """Scraping → technique → SEO → pentest → PDF local → email (ou PDF direct si déjà analysé)."""
    db = Database()
    email = _normalize_email(recipient_email)
    url = canonical_website_https_url((website or '').strip())
    if not url:
        raise ValueError('URL de site invalide')
    if not email:
        raise ValueError('Adresse email invalide')

    if use_lighthouse is None:
        use_lighthouse = SEO_USE_LIGHTHOUSE_DEFAULT

    _audit_log(
        self,
        'init',
        'tâche simple démarrée',
        website=url,
        mode='simple',
        recipient=email,
        entreprise_id=entreprise_id,
        enable_nmap=enable_nmap,
        use_lighthouse=use_lighthouse,
    )

    self.update_state(
        state='PROGRESS',
        meta={
            'step': 'init',
            'progress': 5,
            'website': url,
            'mode': 'simple',
            'modules': SIMPLE_MODULES,
        },
    )

    try:
        eid = _ensure_entreprise(db, url=url, email=email, entreprise_id=entreprise_id, analyse_id=analyse_id)
        _audit_log(self, 'entreprise', 'fiche prête', website=url, mode='simple', entreprise_id=eid)

        pipeline = build_audit_pipeline(db, eid)
        missing = audit_missing_modules(pipeline, 'simple')
        if audit_data_ready(pipeline, 'simple'):
            _audit_log(
                self,
                'cache',
                'analyses déjà en base — génération PDF + email sans relance',
                website=url,
                mode='simple',
                entreprise_id=eid,
            )
            self.update_state(
                state='PROGRESS',
                meta={'step': 'cached', 'progress': 75, 'skipped_analysis': True, 'modules': SIMPLE_MODULES},
            )
            analysis_steps = _cached_analysis_steps('simple')
            skipped = True
        else:
            _audit_log(
                self,
                'analysis',
                'modules à exécuter (ordre scraping → technique → seo → pentest)',
                website=url,
                mode='simple',
                missing=missing,
            )
            self.update_state(
                state='PROGRESS',
                meta={'step': 'simple_analysis', 'progress': 15, 'modules': SIMPLE_MODULES, 'missing': missing},
            )
            analysis_steps = _run_simple_analysis(
                self,
                db,
                url,
                eid,
                missing_modules=missing,
                enable_nmap=enable_nmap,
                use_lighthouse=bool(use_lighthouse),
                max_depth=max_depth,
                max_workers=max_workers,
                max_time=max_time,
                max_pages=max_pages,
            )
            skipped = False

        result = _deliver_audit_report(
            self,
            db,
            eid=eid,
            url=url,
            email=email,
            mode='simple',
            variant='simple',
            analysis_steps=analysis_steps,
            skipped_analysis=skipped,
        )
        _audit_log(self, 'done', 'rapport simple terminé', website=url, mode='simple', skipped_analysis=skipped)
        return result
    except Exception:
        _audit_log(self, 'failed', 'tâche simple en échec', level='exception', website=url, mode='simple')
        raise


@celery.task(
    bind=True,
    name='tasks.website_audit_report_tasks.website_audit_complete_report_task',
    time_limit=5400,
    soft_time_limit=5200,
)
def website_audit_complete_report_task(
    self,
    website: str,
    recipient_email: str,
    entreprise_id: Optional[int] = None,
    analyse_id: Optional[int] = None,
    max_depth: int = 2,
    max_workers: int = 5,
    max_time: int = 300,
    max_pages: int = 40,
    enable_nmap: bool = False,
    use_lighthouse: Optional[bool] = None,
    extra_instructions: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyse complète (6 modules) → PDF agent Cursor → email."""
    db = Database()
    email = _normalize_email(recipient_email)
    url = canonical_website_https_url((website or '').strip())
    if not url:
        raise ValueError('URL de site invalide')
    if not email:
        raise ValueError('Adresse email invalide')

    if use_lighthouse is None:
        use_lighthouse = SEO_USE_LIGHTHOUSE_DEFAULT

    _audit_log(
        self,
        'init',
        'tâche complète démarrée',
        website=url,
        mode='complete',
        recipient=email,
        entreprise_id=entreprise_id,
        max_depth=max_depth,
        max_workers=max_workers,
        max_time=max_time,
        max_pages=max_pages,
        enable_nmap=enable_nmap,
    )

    self.update_state(
        state='PROGRESS',
        meta={
            'step': 'init',
            'progress': 2,
            'website': url,
            'mode': 'complete',
            'pdf_engine': 'expert',
            'modules': COMPLETE_MODULES,
        },
    )

    try:
        eid = _ensure_entreprise(db, url=url, email=email, entreprise_id=entreprise_id, analyse_id=analyse_id)
        _audit_log(self, 'entreprise', 'fiche prête', website=url, mode='complete', entreprise_id=eid)

        pipeline = build_audit_pipeline(db, eid)
        missing = audit_missing_modules(pipeline, 'complete')
        if audit_data_ready(pipeline, 'complete'):
            _audit_log(
                self,
                'cache',
                'pack complet déjà en base — génération PDF + email sans relance',
                website=url,
                mode='complete',
                entreprise_id=eid,
            )
            self.update_state(
                state='PROGRESS',
                meta={'step': 'cached', 'progress': 80, 'skipped_analysis': True, 'modules': COMPLETE_MODULES},
            )
            analysis_steps = _cached_analysis_steps('complete')
            skipped = True
        else:
            _audit_log(
                self,
                'analysis',
                'lancement pack complet (scraping puis modules)',
                website=url,
                mode='complete',
                missing=missing,
            )
            self.update_state(
                state='PROGRESS',
                meta={'step': 'full_analysis', 'progress': 10, 'modules': COMPLETE_MODULES, 'missing': missing},
            )

            from tasks.full_website_analysis import run_full_website_analysis_impl

            t0 = time.monotonic()
            pack_summary = run_full_website_analysis_impl(
                self,
                url,
                eid,
                analyse_id=analyse_id,
                max_depth=max_depth,
                max_workers=max_workers,
                max_time=max_time,
                max_pages=max_pages,
                enable_nmap=enable_nmap,
                use_lighthouse=bool(use_lighthouse),
                enable_technical=True,
                enable_seo=True,
                enable_ux=True,
                enable_screenshot=True,
                enable_osint=True,
                enable_pentest=True,
            )
            analysis_steps = (pack_summary or {}).get('steps') or {}
            _audit_log(
                self,
                'full_analysis',
                'pipeline terminé',
                website=url,
                mode='complete',
                elapsed_sec=round(time.monotonic() - t0, 1),
                steps=analysis_steps,
                duration_seconds=(pack_summary or {}).get('duration_seconds'),
            )
            skipped = False

        result = _deliver_audit_report(
            self,
            db,
            eid=eid,
            url=url,
            email=email,
            mode='complete',
            variant='complete',
            analysis_steps=analysis_steps,
            skipped_analysis=skipped,
            extra_instructions=extra_instructions,
        )
        if result.get('paused'):
            _audit_log(
                self,
                'paused',
                f"rapport en pause ({result.get('reason') or 'agent'})",
                level='warning',
                website=url,
                mode='complete',
                pending_id=result.get('pending_id'),
            )
        else:
            _audit_log(
                self,
                'done',
                'rapport complet terminé',
                website=url,
                mode='complete',
                pdf_engine=result.get('pdf_engine'),
                skipped_analysis=skipped,
            )
        return result
    except Exception:
        _audit_log(self, 'failed', 'tâche complète en échec', level='exception', website=url, mode='complete')
        raise


@celery.task(
    bind=True,
    name='tasks.website_audit_report_tasks.website_audit_complete_resume_task',
    time_limit=3600,
    soft_time_limit=3400,
)
def website_audit_complete_resume_task(
    self,
    *,
    pending_id: Optional[str] = None,
    website: Optional[str] = None,
    recipient_email: Optional[str] = None,
    extra_instructions: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Reprise après pause Cursor : PDF agent + email lead (analyses déjà en base).
    """
    pending = load_pending_agent_job(pending_id=pending_id, website=website)
    if not pending or pending.get('status') not in (
        'paused_agent',
        'paused_cursor',
        'resume_queued',
    ):
        raise ValueError('Aucun job en pause trouvé (pending_id ou website requis)')

    pid = (pending.get('pending_id') or pending_id or '').strip()
    from services.website_audit_pending import get_audit_resume_task_id, bind_audit_resume_task_id

    locked_tid = get_audit_resume_task_id(pid)
    current_tid = _task_label(self)
    if locked_tid and locked_tid not in ('__enqueue__',) and locked_tid != current_tid:
        _audit_log(
            self,
            'resume',
            'tâche doublon ignorée (reprise déjà en cours)',
            level='warning',
            website=pending.get('website') or website or '',
            mode='complete',
            pending_id=pid,
            detail=f'lock={locked_tid} current={current_tid}',
        )
        return {
            'success': False,
            'duplicate': True,
            'task_id': locked_tid,
            'pending_id': pid,
            'message': 'Une autre reprise est déjà en cours pour ce pending_id.',
        }
    bind_audit_resume_task_id(pid, current_tid)

    url = canonical_website_https_url((pending.get('website') or website or '').strip())
    email = _normalize_email(recipient_email or pending.get('recipient_email') or '')
    if not url or not email:
        raise ValueError('website et email requis pour la reprise')

    eid = int(pending['entreprise_id'])
    extra = (extra_instructions or pending.get('extra_instructions') or '').strip() or None
    analysis_steps = pending.get('analysis_steps') or _cached_analysis_steps('complete')
    skipped = bool(pending.get('skipped_analysis', True))

    _audit_log(
        self,
        'resume',
        'reprise génération agent + email',
        website=url,
        mode='complete',
        pending_id=pending.get('pending_id'),
        entreprise_id=eid,
    )
    self.update_state(
        state='PROGRESS',
        meta={'step': 'resume_agent', 'progress': 80, 'pending_id': pending.get('pending_id')},
    )

    db = Database()
    try:
        result = _deliver_audit_report(
            self,
            db,
            eid=eid,
            url=url,
            email=email,
            mode='complete',
            variant='complete',
            analysis_steps=analysis_steps,
            skipped_analysis=skipped,
            extra_instructions=extra,
            agent_only=True,
            pending_local_pdf=pending.get('local_pdf_path'),
            resume_pending_id=pid,
        )
        if result.get('paused'):
            return result
        from services.website_audit_pending import release_audit_resume_lock

        release_audit_resume_lock(pid)
        result['resumed_from_pending'] = pid
        _audit_log(self, 'done', 'reprise terminée', website=url, mode='complete', pdf_engine=result.get('pdf_engine'))
        return result
    except Exception:
        from services.website_audit_pending import (
            release_audit_resume_lock,
            reopen_pending_after_failed_resume,
        )

        release_audit_resume_lock(pid)
        reopen_pending_after_failed_resume(pending)
        _audit_log(
            self,
            'failed',
            'reprise en échec — job réouvert pour nouvel essai',
            level='exception',
            website=url,
            mode='complete',
            pending_id=pid,
        )
        raise


# Alias rétrocompatibilité (anciens appels Celery / code)
website_audit_report_task = website_audit_complete_report_task
