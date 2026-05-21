"""
Collecte des données d'audit site pour génération PDF / email.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.database import Database
from utils.helpers import clean_json_dict


def _score_status(value: Optional[float], *, high_good: bool = True) -> str:
    """Retourne on_track | in_progress | at_risk selon un score 0-100."""
    if value is None:
        return 'unknown'
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 'unknown'
    if high_good:
        if v >= 70:
            return 'on_track'
        if v >= 45:
            return 'in_progress'
        return 'at_risk'
    # Pentest risk : plus haut = pire
    if v < 40:
        return 'on_track'
    if v < 70:
        return 'in_progress'
    return 'at_risk'


AUDIT_MODULES_BY_MODE: Dict[str, List[str]] = {
    'simple': ['scraping', 'technical', 'seo', 'pentest'],
    'complete': ['scraping', 'technical', 'seo', 'screenshot', 'osint', 'pentest'],
}


def pipeline_module_done(pipeline: Dict[str, Any], module: str) -> bool:
    return (pipeline.get(module) or {}).get('status') == 'done'


def audit_missing_modules(pipeline: Dict[str, Any], mode: str) -> List[str]:
    """Modules requis pour le mode donné qui ne sont pas encore en base."""
    required = AUDIT_MODULES_BY_MODE.get(mode) or []
    return [m for m in required if not pipeline_module_done(pipeline, m)]


def audit_data_ready(pipeline: Dict[str, Any], mode: str) -> bool:
    """True si toutes les analyses requises pour ce mode sont déjà présentes."""
    return len(audit_missing_modules(pipeline, mode)) == 0


def _contact_label(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()[:120]
    if isinstance(item, dict):
        email = (item.get('email') or item.get('value') or '').strip()
        name = (item.get('name') or item.get('full_name') or item.get('person') or '').strip()
        role = (item.get('role') or item.get('title') or item.get('job') or '').strip()
        phone = (item.get('phone') or item.get('number') or '').strip()
        if email and name:
            return f'{name} — {email}'[:120]
        if email:
            return email[:120]
        if name and role:
            return f'{name} ({role})'[:120]
        if name:
            return name[:120]
        if phone:
            return phone[:120]
    return str(item)[:120]


def _sample_items(items: Any, *, limit: int = 8) -> List[str]:
    if not items:
        return []
    if isinstance(items, dict):
        items = items.get('items') or items.get('emails') or items.get('people') or list(items.values())
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for it in items[:limit]:
        label = _contact_label(it)
        if label and label not in out:
            out.append(label)
    return out


def _technical_flags_summary(technical_details: Any) -> Dict[str, Any]:
    if not isinstance(technical_details, dict):
        return {}
    keys = [
        'robots_txt_exists',
        'sitemap_exists',
        'sitemap_url_count',
        'mixed_content_detected',
        'mobile_friendly',
        'viewport_meta',
        'html_language',
        'https_redirect',
        'http_status',
    ]
    return {k: technical_details[k] for k in keys if k in technical_details}


def _seo_meta_summary(technical: Dict[str, Any]) -> Dict[str, Any]:
    seo_meta = technical.get('seo_meta') or {}
    if not isinstance(seo_meta, dict):
        details = technical.get('technical_details') or {}
        seo_meta = details.get('seo_meta') if isinstance(details, dict) else {}
    if not isinstance(seo_meta, dict):
        return {}
    return {
        'meta_title': (seo_meta.get('meta_title') or '')[:80],
        'meta_title_length': seo_meta.get('meta_title_length'),
        'meta_description': (seo_meta.get('meta_description') or '')[:120],
        'meta_description_length': seo_meta.get('meta_description_length'),
        'canonical_url': (seo_meta.get('canonical_url') or '')[:100],
    }


def _performance_summary(technical: Dict[str, Any]) -> Dict[str, Any]:
    pages = technical.get('pages_summary') or {}
    perf = technical.get('performance_metrics') or {}
    out: Dict[str, Any] = {}
    if isinstance(pages, dict):
        for k in ('avg_response_time_ms', 'avg_weight_bytes', 'pages_scanned'):
            if pages.get(k) is not None:
                out[k] = pages[k]
    if isinstance(perf, dict):
        for k, v in list(perf.items())[:12]:
            if isinstance(v, (int, float, str, bool)) and v not in (None, ''):
                out[k] = v
            elif isinstance(v, dict) and 'value' in v:
                out[k] = v.get('value')
    return out


def build_audit_pipeline(database: Database, entreprise_id: int) -> Dict[str, Any]:
    """Résumé pipeline (aligné sur /api/entreprise/<id>/audit-pipeline)."""
    pipeline: Dict[str, Any] = {}

    try:
        scrapers = database.get_scrapers_by_entreprise(entreprise_id) or []
    except Exception:
        scrapers = []
    if scrapers:
        latest = scrapers[0]
        emails = latest.get('emails') or []
        people = latest.get('people') or []
        phones = latest.get('phones') or []
        forms = latest.get('forms') or []
        pipeline['scraping'] = {
            'status': 'done',
            'last_date': latest.get('date_modification') or latest.get('date_creation'),
            'url': latest.get('url'),
            'emails_count': len(emails),
            'people_count': len(people),
            'phones_count': len(phones),
            'forms_count': len(forms) if isinstance(forms, list) else int(latest.get('total_forms') or 0),
            'visited_urls': latest.get('visited_urls'),
            'technologies': latest.get('technologies'),
            'sample_emails': _sample_items(emails, limit=6),
            'sample_people': _sample_items(people, limit=6),
            'sample_phones': _sample_items(phones, limit=5),
        }
    else:
        pipeline['scraping'] = {'status': 'never'}

    try:
        technical = database.get_technical_analysis(entreprise_id)
    except Exception:
        technical = None
    if technical:
        details = technical.get('technical_details') or {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {}
        pipeline['technical'] = {
            'status': 'done',
            'last_date': technical.get('date_analyse'),
            'url': technical.get('url'),
            'security_score': technical.get('security_score'),
            'performance_score': technical.get('performance_score'),
            'ssl_grade': technical.get('ssl_grade'),
            'http_status': technical.get('http_status') or (details.get('http_status') if isinstance(details, dict) else None),
            'server': technical.get('server_software') or technical.get('server'),
            'technologies': technical.get('technologies'),
            'issues': technical.get('issues') or technical.get('security_issues') or [],
            'seo_meta': _seo_meta_summary(technical),
            'technical_flags': _technical_flags_summary(details),
            'performance_summary': _performance_summary(technical),
            'security_headers': technical.get('security_headers') if isinstance(technical.get('security_headers'), dict) else {},
        }
    else:
        pipeline['technical'] = {'status': 'never'}

    try:
        seo_list = database.get_seo_analyses_by_entreprise(entreprise_id, limit=1) or []
        seo = seo_list[0] if seo_list else None
    except Exception:
        seo = None
    if seo:
        pipeline['seo'] = {
            'status': 'done',
            'last_date': seo.get('date_analyse'),
            'url': seo.get('url'),
            'score': seo.get('score'),
            'issues': seo.get('issues') or seo.get('recommendations') or [],
            'summary': (seo.get('summary') or seo.get('resume') or '')[:400] if seo.get('summary') or seo.get('resume') else '',
        }
    else:
        pipeline['seo'] = {'status': 'never'}

    try:
        screenshots = database.get_latest_entreprise_screenshots(entreprise_id) or {}
    except Exception:
        screenshots = {}
    if screenshots:
        pipeline['screenshots'] = {'status': 'done', 'latest': screenshots}
    else:
        pipeline['screenshots'] = {'status': 'never'}

    try:
        osint = database.get_osint_analysis_by_entreprise(entreprise_id)
    except Exception:
        osint = None
    if osint:
        emails = osint.get('emails') or []
        people_data = osint.get('people') or {}
        enriched: List[Any] = []
        if isinstance(people_data, dict):
            enriched = people_data.get('enriched') or people_data.get('people') or []
        elif isinstance(people_data, list):
            enriched = people_data
        pipeline['osint'] = {
            'status': 'done',
            'last_date': osint.get('date_analyse'),
            'url': osint.get('url'),
            'emails_count': len(emails),
            'people_count': len(enriched),
            'sample_emails': _sample_items(emails, limit=5),
            'sample_people': _sample_items(enriched, limit=5),
        }
    else:
        pipeline['osint'] = {'status': 'never'}

    try:
        pentest = database.get_pentest_analysis_by_entreprise(entreprise_id)
    except Exception:
        pentest = None
    if pentest:
        vulnerabilities = pentest.get('vulnerabilities') or []
        forms_checks = pentest.get('forms_checks') or pentest.get('form_checks') or []
        headers_check = pentest.get('security_headers') or pentest.get('headers_analysis')
        pipeline['pentest'] = {
            'status': 'done',
            'last_date': pentest.get('date_analyse'),
            'url': pentest.get('url'),
            'risk_score': pentest.get('risk_score'),
            'vulnerabilities_count': len(vulnerabilities),
            'vulnerabilities': vulnerabilities[:15],
            'critical_count': len([v for v in vulnerabilities if str(v.get('severity', '')).lower() in ('critical', 'critique')]),
            'high_count': len([v for v in vulnerabilities if str(v.get('severity', '')).lower() in ('high', 'haute', 'élevée', 'elevee')]),
            'forms_checks_count': len(forms_checks) if isinstance(forms_checks, list) else 0,
            'summary': (pentest.get('summary') or '')[:300] if pentest.get('summary') else '',
        }
    else:
        pipeline['pentest'] = {'status': 'never'}

    return pipeline


def _fmt_bool(value: Any) -> str:
    if value is True:
        return 'Oui'
    if value is False:
        return 'Non'
    if value is None:
        return '—'
    return str(value)


def _add_table(
    tables: List[Dict[str, Any]],
    *,
    table_id: str,
    title: str,
    rows: List[List[str]],
) -> None:
    if rows:
        tables.append({'id': table_id, 'title': title, 'rows': rows})


def build_audit_essential_rows(pipeline: Dict[str, Any], opportunity: Optional[Dict[str, Any]]) -> List[List[str]]:
    """Lignes condensées pour le PDF gratuit (1 tableau, pas de chapitres)."""
    rows: List[List[str]] = []
    tech = pipeline.get('technical') or {}
    seo = pipeline.get('seo') or {}
    pentest = pipeline.get('pentest') or {}
    scraping = pipeline.get('scraping') or {}
    if seo.get('score') is not None:
        rows.append(['Score SEO', f'{int(seo["score"])}/100'])
    if tech.get('security_score') is not None:
        rows.append(['Sécurité technique', f'{int(tech["security_score"])}/100'])
    if tech.get('performance_score') is not None:
        rows.append(['Performance', f'{int(tech["performance_score"])}/100'])
    if pentest.get('risk_score') is not None:
        rows.append(['Risque pentest', f'{int(pentest["risk_score"])}/100'])
    if opportunity and opportunity.get('score') is not None:
        rows.append(['Opportunité', f'{int(opportunity["score"])}/100'])
    if scraping.get('status') == 'done':
        rows.append(['Contacts trouvés', f'{scraping.get("emails_count", 0)} email(s)'])
    for email in (scraping.get('sample_emails') or [])[:2]:
        rows.append(['Email', str(email)])
    return rows[:10]


def build_audit_detail_tables(
    pipeline: Dict[str, Any],
    *,
    tier: str = 'full',
) -> List[Dict[str, Any]]:
    """Tableaux structurés pour le PDF (données mesurées, sans invention)."""
    if tier == 'essential':
        return []
    tables: List[Dict[str, Any]] = []

    scraping = pipeline.get('scraping') or {}
    if scraping.get('status') == 'done':
        rows: List[List[str]] = []
        for label, key in (
            ('Emails trouvés', 'emails_count'),
            ('Contacts / personnes', 'people_count'),
            ('Téléphones', 'phones_count'),
            ('Formulaires', 'forms_count'),
            ('URLs visitées', 'visited_urls'),
        ):
            if scraping.get(key) is not None:
                rows.append([label, str(scraping[key])])
        for email in scraping.get('sample_emails') or []:
            rows.append(['Email', str(email)])
        for person in scraping.get('sample_people') or []:
            rows.append(['Contact', str(person)])
        _add_table(tables, table_id='scraping', title='Exploration & contacts', rows=rows)

    tech = pipeline.get('technical') or {}
    if tech.get('status') == 'done':
        rows = []
        for label, key in (
            ('Score sécurité', 'security_score'),
            ('Score performance', 'performance_score'),
            ('Grade SSL', 'ssl_grade'),
            ('Statut HTTP', 'http_status'),
            ('Serveur', 'server'),
        ):
            if tech.get(key) not in (None, ''):
                rows.append([label, str(tech[key])])
        for label, key in (
            ('Titre page', 'meta_title'),
            ('Longueur titre', 'meta_title_length'),
            ('Meta description', 'meta_description'),
            ('Longueur description', 'meta_description_length'),
        ):
            val = (tech.get('seo_meta') or {}).get(key)
            if val not in (None, ''):
                rows.append([label, str(val)[:100]])
        canon = (tech.get('seo_meta') or {}).get('canonical_url')
        if canon:
            rows.append(['URL canonique', str(canon)[:100]])
        flag_labels = {
            'robots_txt_exists': 'robots.txt',
            'sitemap_exists': 'sitemap.xml',
            'sitemap_url_count': 'URLs sitemap',
            'mixed_content_detected': 'Contenu mixte HTTP/HTTPS',
            'mobile_friendly': 'Mobile-friendly',
            'viewport_meta': 'Balise viewport',
            'html_language': 'Langue HTML',
        }
        for key, label in flag_labels.items():
            if key in (tech.get('technical_flags') or {}):
                rows.append([label, _fmt_bool((tech.get('technical_flags') or {}).get(key))])
        for metric, val in (tech.get('performance_summary') or {}).items():
            rows.append([str(metric).replace('_', ' ').title(), str(val)])
        _add_table(tables, table_id='technical', title='Analyse technique détaillée', rows=rows)

    seo = pipeline.get('seo') or {}
    if seo.get('status') == 'done':
        rows = []
        if seo.get('score') is not None:
            rows.append(['Score SEO global', f'{int(seo["score"])}/100'])
        if seo.get('summary'):
            rows.append(['Synthèse', str(seo['summary'])[:200]])
        for bullet in _format_issue_bullets(seo.get('issues') or [], limit=8):
            rows.append(['Recommandation', bullet])
        _add_table(tables, table_id='seo', title='SEO — indicateurs & recommandations', rows=rows)

    osint = pipeline.get('osint') or {}
    if osint.get('status') == 'done':
        rows = [
            ['Emails OSINT', str(osint.get('emails_count', 0))],
            ['Profils / personnes', str(osint.get('people_count', 0))],
        ]
        for email in osint.get('sample_emails') or []:
            rows.append(['Email', str(email)])
        for person in osint.get('sample_people') or []:
            rows.append(['Profil', str(person)])
        _add_table(tables, table_id='osint', title='OSINT — exposition publique', rows=rows)

    pentest = pipeline.get('pentest') or {}
    if pentest.get('status') == 'done':
        rows = [
            ['Indice de risque', f'{int(pentest["risk_score"])}/100' if pentest.get('risk_score') is not None else '—'],
            ['Vulnérabilités', str(pentest.get('vulnerabilities_count', 0))],
            ['Critiques', str(pentest.get('critical_count', 0))],
            ['Haute sévérité', str(pentest.get('high_count', 0))],
            ['Formulaires testés', str(pentest.get('forms_checks_count', 0))],
        ]
        if pentest.get('summary'):
            rows.append(['Synthèse pentest', str(pentest['summary'])[:200]])
        _add_table(tables, table_id='pentest_summary', title='Pentest — synthèse', rows=rows)

    shots = (pipeline.get('screenshots') or {}).get('latest') or {}
    if shots:
        rows = []
        if shots.get('page_url'):
            rows.append(['Page capturée', str(shots['page_url'])[:120]])
        if shots.get('captured_at'):
            rows.append(['Date capture', str(shots['captured_at'])])
        for device, label in (('desktop', 'Desktop'), ('tablet', 'Tablette'), ('mobile', 'Mobile')):
            block = shots.get(device) or {}
            if block.get('file_path') or block.get('public_url'):
                rows.append([label, 'Disponible'])
            elif block.get('error'):
                rows.append([label, f'Erreur : {str(block["error"])[:80]}'])
        if rows:
            _add_table(tables, table_id='screenshots', title='Captures d\'écran', rows=rows)

    return tables


def build_health_rows(pipeline: Dict[str, Any], opportunity: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Lignes « carte santé » pour le PDF (style rapport hebdomadaire)."""
    rows: List[Dict[str, str]] = []

    seo = pipeline.get('seo') or {}
    tech = pipeline.get('technical') or {}
    pentest = pipeline.get('pentest') or {}
    scraping = pipeline.get('scraping') or {}
    osint = pipeline.get('osint') or {}

    def add(area: str, status: str, detail: str) -> None:
        rows.append({'area': area, 'status': status, 'detail': detail})

    seo_score = seo.get('score') if seo.get('status') == 'done' else None
    st = _score_status(seo_score, high_good=True)
    add(
        'SEO & visibilité',
        st,
        f'Score SEO : {int(seo_score)}/100' if seo_score is not None else 'Analyse non disponible',
    )

    sec = tech.get('security_score') if tech.get('status') == 'done' else None
    st = _score_status(sec, high_good=True)
    add(
        'Sécurité technique',
        st,
        f'Score sécurité : {int(sec)}/100' if sec is not None else 'Analyse non disponible',
    )

    perf = tech.get('performance_score') if tech.get('status') == 'done' else None
    st = _score_status(perf, high_good=True)
    add(
        'Performance',
        st,
        f'Score performance : {int(perf)}/100' if perf is not None else 'Analyse non disponible',
    )

    risk = pentest.get('risk_score') if pentest.get('status') == 'done' else None
    st = _score_status(risk, high_good=False)
    vuln_n = pentest.get('vulnerabilities_count', 0)
    add(
        'Pentest & vulnérabilités',
        st,
        f'Risque {int(risk)}/100 — {vuln_n} finding(s)' if risk is not None else 'Analyse non disponible',
    )

    if scraping.get('status') == 'done':
        add(
            'Contenu & contacts',
            'on_track' if scraping.get('emails_count', 0) > 0 else 'in_progress',
            f'{scraping.get("emails_count", 0)} email(s), {scraping.get("people_count", 0)} contact(s)',
        )
    else:
        add('Contenu & contacts', 'unknown', 'Scraping non effectué')

    if osint.get('status') == 'done':
        add(
            'OSINT',
            'on_track' if osint.get('people_count', 0) > 0 else 'in_progress',
            f'{osint.get("people_count", 0)} personne(s) enrichie(s)',
        )
    else:
        add('OSINT', 'unknown', 'OSINT non effectué')

    opp_score = opportunity.get('score') if opportunity else None
    if opp_score is not None:
        st = _score_status(float(opp_score), high_good=True)
        add('Opportunité globale', st, f'Score {int(opp_score)}/100 — {opportunity.get("opportunity", "")}')
    else:
        add('Opportunité globale', 'unknown', 'Non calculée')

    return rows


def build_executive_summary(
    pipeline: Dict[str, Any],
    opportunity: Optional[Dict[str, Any]],
) -> List[str]:
    """Points clés pour le résumé exécutif."""
    lines: List[str] = []
    if opportunity:
        opp = opportunity.get('opportunity')
        score = opportunity.get('score')
        if opp and score is not None:
            lines.append(
                f"L'opportunité commerciale est évaluée « {opp} » avec un score global d'environ {int(score)}/100."
            )
    tech = pipeline.get('technical') or {}
    if tech.get('status') == 'done' and tech.get('security_score') is not None:
        s = int(tech['security_score'])
        if s < 50:
            lines.append(f'La sécurité technique est faible (score ~{s}/100).')
        elif s < 70:
            lines.append(f'La sécurité technique est moyenne (score ~{s}/100).')
        else:
            lines.append(f'La sécurité technique est correcte (score ~{s}/100).')
    seo = pipeline.get('seo') or {}
    if seo.get('status') == 'done' and seo.get('score') is not None:
        s = int(seo['score'])
        if s < 50:
            lines.append(f'Le référencement naturel est faible (SEO ~{s}/100).')
        elif s < 70:
            lines.append(f'Le SEO est perfectible (score ~{s}/100).')
    pentest = pipeline.get('pentest') or {}
    if pentest.get('status') == 'done' and pentest.get('risk_score') is not None:
        r = int(pentest['risk_score'])
        if r >= 70:
            lines.append(f'Le risque de sécurité identifié par pentest est élevé (~{r}/100).')
        elif r >= 40:
            lines.append(f'Le risque pentest est modéré (~{r}/100).')
    if not lines:
        lines.append("Les analyses sont partielles ; relancez un scan complet pour enrichir ce rapport.")
    return lines


def _format_issue_bullets(items: Any, *, limit: int = 6) -> List[str]:
    """Transforme issues / recommandations en puces lisibles."""
    bullets: List[str] = []
    if not items:
        return bullets
    if isinstance(items, dict):
        items = items.get('items') or items.get('issues') or list(items.values())
    if not isinstance(items, list):
        return bullets
    for it in items[:limit]:
        if isinstance(it, str) and it.strip():
            bullets.append(it.strip()[:220])
        elif isinstance(it, dict):
            title = (it.get('title') or it.get('name') or '').strip()
            desc = (it.get('description') or it.get('message') or it.get('detail') or '').strip()
            line = title or desc or str(it)
            if title and desc and title != desc:
                line = f'{title} — {desc}'
            if line:
                bullets.append(str(line)[:220])
    return bullets


def build_audit_narrative_sections(
    context: Dict[str, Any],
    *,
    tier: str = 'full',
) -> List[Dict[str, Any]]:
    """
    Sections textuelles pour le PDF (titres, paragraphes, puces).
    tier=essential : synthèse courte uniquement (offre gratuite).
    """
    website = (context.get('website') or '').strip()
    company = (context.get('company_name') or website).strip()
    secteur = (context.get('secteur') or '').strip()
    pipeline = context.get('pipeline') or {}
    opportunity = context.get('opportunity') or {}
    exec_lines = context.get('executive_summary') or build_executive_summary(pipeline, opportunity)
    sections: List[Dict[str, Any]] = []

    if tier == 'essential':
        opp_txt = ''
        if opportunity.get('score') is not None:
            opp_txt = f' Opportunité : {opportunity.get("opportunity", "—")} ({int(opportunity["score"])}/100).'
        sections.append({
            'id': 'context',
            'title': 'Synthèse essentielle',
            'paragraphs': [
                (
                    f'Audit condensé de <b>{company}</b> ({website}) — scores et actions prioritaires.{opp_txt} '
                    'Pour un rapport expert détaillé (captures, OSINT, plan de remédiation), '
                    'choisissez l\'offre complète.'
                ),
            ],
            'bullets': exec_lines[:5],
        })
        return sections

    opp_label = opportunity.get('opportunity') or '—'
    opp_score = opportunity.get('score')
    opp_txt = (
        f' Le potentiel commercial est classé « {opp_label} » ({int(opp_score)}/100).'
        if opp_score is not None
        else ''
    )

    sections.append({
        'id': 'context',
        'title': 'Contexte & méthodologie',
        'paragraphs': [
            (
                f'Ce document synthétise l\'audit digital de <b>{company}</b> ({website}). '
                f'Il agrège les résultats automatisés : exploration du site, analyse '
                f'technique, SEO, sécurité applicative (pentest) et, le cas échéant, OSINT.{opp_txt}'
            ),
            (
                'Les scores et graphiques reflètent les données mesurées au moment de l\'analyse. '
                'Les paragraphes ci-dessous détaillent les constats par domaine et proposent '
                'des axes d\'amélioration concrets, classés par priorité en fin de rapport.'
            ),
        ],
        'bullets': [
            f'Secteur d\'activité renseigné : {secteur or "non précisé"}',
            'Méthode : crawl du site, tests HTTP/TLS, audit éditorial SEO, tests de surface pentest',
        ],
    })

    scraping = pipeline.get('scraping') or {}
    if scraping.get('status') == 'done':
        emails_n = scraping.get('emails_count', 0)
        people_n = scraping.get('people_count', 0)
        phones_n = scraping.get('phones_count', 0)
        forms_n = scraping.get('forms_count', 0)
        techs = scraping.get('technologies')
        tech_hint = ''
        if techs:
            if isinstance(techs, list):
                tech_hint = ', '.join(str(t) for t in techs[:5])
            elif isinstance(techs, str):
                tech_hint = techs[:120]
        sections.append({
            'id': 'scraping',
            'title': 'Présence digitale & contenu',
            'paragraphs': [
                (
                    f'L\'exploration automatisée du site a identifié <b>{emails_n}</b> adresse(s) email, '
                    f'<b>{people_n}</b> contact(s), <b>{phones_n}</b> numéro(s) et <b>{forms_n}</b> formulaire(s) exposés. '
                    'Ces éléments alimentent la compréhension de votre surface de contact et la cohérence '
                    'des informations diffusées.'
                ),
                (
                    'Un inventaire riche facilite la prospection légitime et la détection de fuites '
                    '(emails génériques, formulaires non protégés, technologies obsolètes visibles).'
                    + (f' Technologies détectées : {tech_hint}.' if tech_hint else '')
                ),
            ],
            'bullets': [],
        })
    else:
        sections.append({
            'id': 'scraping',
            'title': 'Présence digitale & contenu',
            'paragraphs': [
                'Le module de scraping n\'a pas encore été exécuté pour ce site. Relancez une analyse '
                'complète pour cartographier emails, contacts et formulaires avant d\'engager des actions marketing.',
            ],
            'bullets': [],
        })

    tech = pipeline.get('technical') or {}
    if tech.get('status') == 'done':
        sec = tech.get('security_score')
        perf = tech.get('performance_score')
        ssl = tech.get('ssl_grade') or '—'
        issues = _format_issue_bullets(tech.get('issues') or [])
        sec_i = int(sec) if sec is not None else None
        perf_i = int(perf) if perf is not None else None
        tone = (
            'La posture technique est solide pour un site vitrine professionnel.'
            if sec_i is not None and sec_i >= 75
            else 'Des renforts sur la configuration et les bonnes pratiques HTTP sont recommandés.'
        )
        seo_meta = tech.get('seo_meta') or {}
        meta_title = (seo_meta.get('meta_title') or '').strip()
        meta_extra = ''
        if meta_title:
            meta_extra = f' Titre détecté : « {meta_title[:70]} ».'
        flags = tech.get('technical_flags') or {}
        flag_hints: List[str] = []
        if flags.get('sitemap_exists') is False:
            flag_hints.append('Aucun sitemap.xml détecté.')
        if flags.get('robots_txt_exists') is False:
            flag_hints.append('Pas de fichier robots.txt.')
        if flags.get('mixed_content_detected'):
            flag_hints.append('Contenu mixte HTTP/HTTPS détecté.')
        sections.append({
            'id': 'technical',
            'title': 'Analyse technique',
            'paragraphs': [
                (
                    f'L\'audit technique mesure la robustesse de l\'hébergement, des en-têtes HTTP, du certificat TLS '
                    f'(grade SSL : <b>{ssl}</b>) et des signaux de performance perçue.'
                    + (f' Sécurité : <b>{sec_i}/100</b>.' if sec_i is not None else '')
                    + (f' Performance : <b>{perf_i}/100</b>.' if perf_i is not None else '')
                    + meta_extra
                ),
                tone + (
                    ' Une performance élevée améliore l\'expérience utilisateur et soutient le référencement ; '
                    'la sécurité limite les détournements et la perte de confiance.'
                    if perf_i is not None and perf_i >= 80
                    else ' Optimiser temps de chargement et compression reste un levier SEO et conversion.'
                ),
            ],
            'bullets': (issues or []) + flag_hints or ['Aucun point bloquant listé automatiquement — vérifier manuellement les en-têtes de sécurité.'],
        })
    else:
        sections.append({
            'id': 'technical',
            'title': 'Analyse technique',
            'paragraphs': ['Analyse technique non disponible pour cette fiche.'],
            'bullets': [],
        })

    seo = pipeline.get('seo') or {}
    if seo.get('status') == 'done':
        score = seo.get('score')
        score_i = int(score) if score is not None else None
        recs = _format_issue_bullets(seo.get('issues') or [])
        sections.append({
            'id': 'seo',
            'title': 'Référencement naturel (SEO)',
            'paragraphs': [
                (
                    f'Le score SEO consolidé s\'élève à <b>{score_i}/100</b>. '
                    'Il combine structure HTML, balises meta, lisibilité mobile, vitesse perçue '
                    'et signaux d\'indexabilité détectés lors du crawl.'
                ),
                (
                    'Un SEO solide augmente la visibilité organique sur les requêtes métier ; '
                    'en dessous de 60/100, prioriser titres, contenus, maillage interne et données structurées.'
                    if score_i is not None and score_i < 60
                    else 'Maintenir la qualité éditoriale et surveiller les régressions après chaque mise en production.'
                ),
            ],
            'bullets': recs or ['Poursuivre la production de contenus ciblés et le maillage entre pages clés.'],
        })
    else:
        sections.append({
            'id': 'seo',
            'title': 'Référencement naturel (SEO)',
            'paragraphs': ['Analyse SEO non disponible.'],
            'bullets': [],
        })

    pentest = pipeline.get('pentest') or {}
    if pentest.get('status') == 'done':
        risk = pentest.get('risk_score')
        risk_i = int(risk) if risk is not None else None
        vuln_n = pentest.get('vulnerabilities_count', 0)
        crit = pentest.get('critical_count', 0)
        high = pentest.get('high_count', 0)
        sections.append({
            'id': 'pentest',
            'title': 'Sécurité applicative (pentest)',
            'paragraphs': [
                (
                    f'Le pentest de surface évalue les formulaires, en-têtes et comportements exposés. '
                    f'Indice de risque : <b>{risk_i}/100</b> ({vuln_n} constat(s) recensé(s), '
                    f'dont {crit} critique(s) et {high} haute(s) sévérité).'
                ),
                (
                    'Un risque modéré à faible ne signifie pas l\'absence de travail : corriger les findings '
                    'critiques en priorité, puis durcir les configurations (CSP, cookies, rate limiting).'
                    if risk_i is not None and risk_i < 70
                    else 'Le niveau de risque élevé appelle un plan de remédiation court terme et une revue des déploiements récents.'
                ),
            ],
            'bullets': [],
        })
    else:
        sections.append({
            'id': 'pentest',
            'title': 'Sécurité applicative (pentest)',
            'paragraphs': ['Pentest non réalisé sur ce périmètre.'],
            'bullets': [],
        })

    osint = pipeline.get('osint') or {}
    if osint.get('status') == 'done':
        sections.append({
            'id': 'osint',
            'title': 'OSINT & exposition publique',
            'paragraphs': [
                (
                    f'L\'OSINT a recoupé <b>{osint.get("emails_count", 0)}</b> email(s) et '
                    f'<b>{osint.get("people_count", 0)}</b> profil(s) / personne(s) liés au domaine. '
                    'Cette vue complète le scraping par des sources ouvertes (réseaux, annuaires, fuites potentielles).'
                ),
            ],
            'bullets': [],
        })

    exec_lines = context.get('executive_summary') or build_executive_summary(pipeline, opportunity)
    sections.append({
        'id': 'synthesis',
        'title': 'Synthèse & lecture direction',
        'paragraphs': [
            'Les indicateurs ci-dessus traduisent la maturité digitale actuelle du site. '
            'La carte de santé résume chaque domaine ; les graphiques permettent une comparaison rapide.',
        ],
        'bullets': exec_lines,
    })

    return sections


def collect_audit_report_context(
    database: Database,
    entreprise_id: int,
    *,
    website: str,
    recipient_email: str,
    report_mode: str = 'simple',
) -> Dict[str, Any]:
    """Contexte complet pour PDF et email. report_mode: simple | complete."""
    tier = 'essential' if report_mode == 'simple' else 'full'
    entreprise = database.get_entreprise(entreprise_id) or {}
    opportunity = None
    try:
        opportunity = database.update_opportunity_score(entreprise_id)
    except Exception:
        opportunity = None

    pipeline = build_audit_pipeline(database, entreprise_id)
    health_rows = build_health_rows(pipeline, opportunity)
    executive_summary = build_executive_summary(pipeline, opportunity)
    quick_wins: List[str] = []
    if opportunity and isinstance(opportunity.get('indicators'), list):
        for ind in opportunity['indicators'][:6]:
            s = str(ind or '').strip()
            if s:
                quick_wins.append(s)

    ctx_payload = {
        'website': website,
        'company_name': (entreprise.get('nom') or entreprise.get('name') or website).strip(),
        'secteur': (entreprise.get('secteur') or '').strip(),
        'pipeline': pipeline,
        'opportunity': opportunity,
        'executive_summary': executive_summary,
    }
    narrative_sections = build_audit_narrative_sections(ctx_payload, tier=tier)
    detail_tables = build_audit_detail_tables(pipeline, tier=tier)
    essential_rows = build_audit_essential_rows(pipeline, opportunity) if tier == 'essential' else []

    return {
        'entreprise_id': entreprise_id,
        'entreprise': entreprise,
        'website': website,
        'recipient_email': recipient_email,
        'company_name': (entreprise.get('nom') or entreprise.get('name') or website).strip(),
        'secteur': (entreprise.get('secteur') or '').strip(),
        'opportunity': opportunity,
        'pipeline': pipeline,
        'health_rows': health_rows,
        'executive_summary': executive_summary,
        'quick_wins': quick_wins,
        'narrative_sections': narrative_sections,
        'detail_tables': detail_tables,
        'essential_rows': essential_rows,
        'report_mode': report_mode,
        'report_tier': tier,
    }


def context_for_agent_prompt(context: Dict[str, Any]) -> Dict[str, Any]:
    """Payload JSON sérialisable pour le prompt agent (sans objets ORM bruts)."""
    pipeline = context.get('pipeline') or {}
    shots = (pipeline.get('screenshots') or {}).get('latest') or {}
    screenshot_paths: Dict[str, str] = {}
    for device in ('desktop', 'tablet', 'mobile'):
        block = shots.get(device) or {}
        fp = block.get('file_path')
        if fp:
            screenshot_paths[device] = str(fp)

    payload = {
        'website': context.get('website'),
        'company_name': context.get('company_name'),
        'secteur': context.get('secteur'),
        'recipient_email': context.get('recipient_email'),
        'opportunity': context.get('opportunity'),
        'pipeline': pipeline,
        'health_rows': context.get('health_rows'),
        'executive_summary': context.get('executive_summary'),
        'quick_wins': context.get('quick_wins'),
        'detail_tables': context.get('detail_tables'),
        'screenshot_file_paths': screenshot_paths,
        'local_pdf_path': context.get('local_pdf_path'),
    }
    return clean_json_dict(payload)


context_for_serv1_prompt = context_for_agent_prompt


def write_audit_context_json(context: Dict[str, Any], target_path: Path) -> Path:
    """Écrit le contexte d'audit sur disque pour l'agent distant."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    data = context_for_agent_prompt(context)
    target_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return target_path
