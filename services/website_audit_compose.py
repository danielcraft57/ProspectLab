"""
Composition deterministe du rapport complet (PDF) sans agent Cursor.

Reprend le meme modele de donnees que GET /api/public/entreprises/<id>/gemini-report
(include_document=true) et le croise avec le pipeline mesure ProspectLab.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from services.database import Database
from services.website_audit_data import (
    build_audit_narrative_sections,
    build_executive_summary,
)

_REFONTE_LABELS = {
    'aucune': 'Aucune refonte nécessaire',
    'legere': 'Retouches légères',
    'partielle': 'Refonte partielle recommandée',
    'totale': 'Refonte complète recommandée',
}

_PRIORITY_ORDER = {
    'haute': 0,
    'high': 0,
    'elevee': 0,
    'élevée': 0,
    'moyenne': 1,
    'medium': 1,
    'basse': 2,
    'low': 2,
}

# Titres Markdown reconnus (hors jargon IA pour le client)
_MD_HEADING_RE = re.compile(r'^(#{1,3})\s+(.+)$')
_MD_BULLET_RE = re.compile(r'^[-*•]\s+(.+)$')
_MD_NUM_RE = re.compile(r'^\d+[.)]\s+(.+)$')


def _norm_key(text: str) -> str:
    """Cle de deduplication (minuscules, espaces compacts)."""
    return re.sub(r'\s+', ' ', (text or '').strip().lower())


def _split_sentences(text: str, *, limit: int = 6) -> List[str]:
    """Decoupe un bloc en phrases courtes pour puces ou paragraphes."""
    raw = re.sub(r'\s+', ' ', (text or '').strip())
    if not raw:
        return []
    parts = re.split(r'(?<=[.!?])\s+', raw)
    out: List[str] = []
    for p in parts:
        s = p.strip()
        if len(s) >= 12:
            out.append(s[:320])
        if len(out) >= limit:
            break
    return out


def _priority_rank(label: Any) -> int:
    return _PRIORITY_ORDER.get(str(label or '').strip().lower(), 1)


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def load_gemini_public_payload(
    database: Database,
    entreprise_id: int,
    *,
    include_document: bool = True,
) -> Dict[str, Any]:
    """
    Charge le rapport Gemini au format public API
    (meme logique que GET .../gemini-report?include_document=...).

    @param database: Acces BDD
    @param entreprise_id: ID entreprise
    @param include_document: Inclure le Markdown report_document
    @returns: Payload aplati (status, report, report_document, …)
    """
    eid = int(entreprise_id or 0)
    if eid <= 0:
        return {'success': True, 'status': 'never', 'report': None}

    latest = database.get_latest_entreprise_gemini_report(eid)
    if not latest:
        return {
            'success': True,
            'entreprise_id': eid,
            'status': 'never',
            'report': None,
            'report_document': None if include_document else None,
        }

    report = latest.get('report') if isinstance(latest.get('report'), dict) else {}
    modules_src = report.get('modules') if isinstance(report.get('modules'), dict) else {}
    indicators: Dict[str, Any] = {}
    for key in ('design', 'technical', 'seo', 'osint', 'pentest'):
        block = modules_src.get(key) if isinstance(modules_src.get(key), dict) else {}
        score = block.get('score')
        if score is None:
            score = latest.get(f'score_{key}')
        notes = block.get('notes') or latest.get(f'notes_{key}') or ''
        if score is not None or str(notes).strip():
            indicators[key] = {
                'score': score,
                'notes': str(notes).strip() if notes else '',
            }

    design = report.get('design_analysis') if isinstance(report.get('design_analysis'), dict) else None
    if not design and any(
        latest.get(k) for k in ('design_score', 'design_summary', 'design_ux_notes', 'design_ui_notes')
    ):
        design = {
            'score': latest.get('design_score'),
            'summary': latest.get('design_summary') or '',
            'ux_notes': latest.get('design_ux_notes') or '',
            'ui_notes': latest.get('design_ui_notes') or '',
            'to_keep': [],
            'to_redo': [],
        }

    status = str(latest.get('status') or 'done').strip().lower() or 'done'
    if status in ('ok',):
        status = 'done'

    public_report: Dict[str, Any] = {
        'overall_score': (
            latest.get('overall_score')
            if latest.get('overall_score') is not None
            else report.get('overall_score')
        ),
        'refonte_recommendation': latest.get('refonte_recommendation') or report.get('refonte_recommendation'),
        'executive_summary': (
            latest.get('executive_summary') or report.get('executive_summary') or ''
        ).strip(),
        'commercial_pitch': (
            latest.get('commercial_pitch') or report.get('commercial_pitch') or ''
        ).strip(),
        'what_works': list(report.get('what_works') or []),
        'whats_wrong': list(report.get('whats_wrong') or []),
        'priority_actions': list(report.get('priority_actions') or []),
        'improvements': list(report.get('improvements') or []),
        'modules': indicators,
        'design_analysis': design,
        'source': latest.get('source') or report.get('source'),
    }

    doc = ''
    if include_document:
        doc = (
            latest.get('report_document')
            or report.get('report_document')
            or ''
        ).strip()
        public_report['report_document'] = doc

    return {
        'success': True,
        'entreprise_id': eid,
        'status': status,
        'overall_score': public_report['overall_score'],
        'refonte_recommendation': public_report['refonte_recommendation'],
        'source': public_report['source'],
        'analyzed_at': latest.get('analyzed_at'),
        'executive_summary': public_report['executive_summary'],
        'commercial_pitch': public_report['commercial_pitch'],
        'indicators': indicators,
        'what_works': public_report['what_works'],
        'whats_wrong': public_report['whats_wrong'],
        'priority_actions': public_report['priority_actions'],
        'improvements': public_report['improvements'],
        'design_analysis': design,
        'report': public_report,
        'report_id': latest.get('id'),
        'screenshot_set_id': latest.get('screenshot_set_id'),
        'error_message': latest.get('error_message'),
        'report_document': doc if include_document else None,
        'latest': latest,
    }


def ensure_gemini_report_for_compose(
    database: Database,
    entreprise_id: int,
    *,
    progress_cb: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """
    Garantit un rapport Gemini utilisable pour le PDF.

    Si aucun rapport done en base : lance build_full_report_for_entreprise
    (meme moteur que POST .../gemini-report).

    @param database: Acces BDD
    @param entreprise_id: ID entreprise
    @param progress_cb: Callback optionnel (message, pct)
    @returns: Payload public apres generation / lecture
    """
    payload = load_gemini_public_payload(database, entreprise_id, include_document=True)
    status = str(payload.get('status') or '').lower()
    has_content = bool(
        payload.get('executive_summary')
        or payload.get('report_document')
        or payload.get('what_works')
        or payload.get('design_analysis')
        or payload.get('overall_score') is not None
    )
    if status in ('done', 'ok') and has_content:
        return payload

    try:
        from services.gemini_full_report_service import build_full_report_for_entreprise

        def _emit(msg: str, pct: Optional[int] = None) -> None:
            if not progress_cb:
                return
            try:
                progress_cb(msg, pct)
            except TypeError:
                progress_cb(msg)

        _emit('Préparation de la synthèse design pour le rapport complet…', 84)
        result = build_full_report_for_entreprise(
            database,
            int(entreprise_id),
            ensure_screenshots=True,
            progress_cb=_emit,
        )
        if not result.get('success'):
            _emit(f'Synthèse design indisponible : {result.get("error") or "erreur"}', 86)
    except Exception as exc:
        if progress_cb:
            try:
                progress_cb(f'Synthèse design sautée : {exc}', 86)
            except Exception:
                pass

    return load_gemini_public_payload(database, entreprise_id, include_document=True)


def _gemini_dict_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Aplatit le payload public vers le dict utilise par les builders de sections."""
    report = payload.get('report') if isinstance(payload.get('report'), dict) else {}
    gemini = dict(report)
    # Preferer les champs racine (alignes API publique)
    for key in (
        'overall_score',
        'refonte_recommendation',
        'executive_summary',
        'commercial_pitch',
        'what_works',
        'whats_wrong',
        'priority_actions',
        'improvements',
        'design_analysis',
        'source',
        'report_document',
    ):
        val = payload.get(key)
        if val not in (None, '', [], {}):
            gemini[key] = val
    if payload.get('indicators') and not gemini.get('modules'):
        gemini['modules'] = payload['indicators']
    return gemini


def parse_report_document_sections(
    markdown: str,
    *,
    max_sections: int = 8,
    max_paras: int = 5,
    max_bullets: int = 10,
) -> List[Dict[str, Any]]:
    """
    Transforme le Markdown ``report_document`` Gemini en sections PDF.

    Algo simple, sans IA : titres # / ## / ###, paragraphes, listes -/*.

    @param markdown: Document Markdown
    @returns: Liste de sections {id, title, paragraphs, bullets}
    """
    text = (markdown or '').replace('\r\n', '\n').strip()
    if not text:
        return []

    sections: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    def _flush() -> None:
        nonlocal current
        if not current:
            return
        if current.get('paragraphs') or current.get('bullets'):
            sections.append(current)
        current = None

    for raw_line in text.split('\n'):
        line = raw_line.rstrip()
        if not line.strip():
            continue

        heading = _MD_HEADING_RE.match(line.strip())
        if heading:
            _flush()
            title = heading.group(2).strip()[:120]
            # Eviter de recoller le titre global du doc
            if _norm_key(title) in (
                'rapport',
                'rapport complet',
                'audit',
                'sommaire',
                'table des matieres',
            ):
                continue
            current = {
                'id': f'gemini_doc_{len(sections) + 1}',
                'title': title,
                'paragraphs': [],
                'bullets': [],
            }
            continue

        if current is None:
            current = {
                'id': 'gemini_doc_intro',
                'title': 'Lecture détaillée',
                'paragraphs': [],
                'bullets': [],
            }

        bullet = _MD_BULLET_RE.match(line.strip()) or _MD_NUM_RE.match(line.strip())
        if bullet:
            if len(current['bullets']) < max_bullets:
                current['bullets'].append(bullet.group(1).strip()[:260])
            continue

        # Ligne gras type **Titre** seule -> sous-titre leger
        bold_only = re.match(r'^\*\*(.+?)\*\*\s*$', line.strip())
        if bold_only and len(current['paragraphs']) < max_paras:
            current['paragraphs'].append(f'<b>{bold_only.group(1).strip()[:200]}</b>')
            continue

        cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', line.strip())
        cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
        if len(cleaned) >= 20 and len(current['paragraphs']) < max_paras:
            current['paragraphs'].append(cleaned[:900])

        if len(sections) >= max_sections:
            break

    _flush()
    return sections[:max_sections]


def _merge_executive_summary(
    pipeline: Dict[str, Any],
    opportunity: Optional[Dict[str, Any]],
    gemini: Dict[str, Any],
) -> List[str]:
    """Fusionne synthese pipeline + executive_summary Gemini (sans doublons)."""
    lines: List[str] = []
    seen: set[str] = set()

    for block in (
        gemini.get('executive_summary'),
        gemini.get('commercial_pitch'),
    ):
        for sent in _split_sentences(str(block or ''), limit=4):
            key = _norm_key(sent)
            if key and key not in seen:
                seen.add(key)
                lines.append(sent)

    for line in build_executive_summary(pipeline, opportunity):
        key = _norm_key(line)
        if key and key not in seen:
            seen.add(key)
            lines.append(line)

    return lines[:8]


def _merge_priority_actions(
    pipeline: Dict[str, Any],
    gemini: Dict[str, Any],
    *,
    limit: int = 12,
) -> List[str]:
    """Priorise les actions : improvements Gemini, priority_actions, issues pipeline."""
    items: List[tuple[int, str]] = []
    seen: set[str] = set()

    def _add(text: str, priority: Any = 'moyenne') -> None:
        t = (text or '').strip()
        if len(t) < 8:
            return
        key = _norm_key(t)
        if key in seen:
            return
        seen.add(key)
        items.append((_priority_rank(priority), t[:260]))

    for imp in gemini.get('improvements') or []:
        if isinstance(imp, dict):
            _add(imp.get('action') or imp.get('text') or '', imp.get('priority'))
        elif isinstance(imp, str):
            _add(imp)

    for act in gemini.get('priority_actions') or []:
        _add(str(act), 'haute')

    for mod_key in ('seo', 'technical', 'pentest'):
        mod = pipeline.get(mod_key) or {}
        if mod.get('status') != 'done':
            continue
        issues = mod.get('issues') or []
        if isinstance(issues, dict):
            issues = issues.get('items') or list(issues.values())
        for it in (issues or [])[:4]:
            if isinstance(it, str):
                _add(it, 'moyenne')
            elif isinstance(it, dict):
                _add(
                    it.get('message') or it.get('title') or it.get('description') or '',
                    it.get('impact'),
                )

    items.sort(key=lambda x: (x[0], x[1]))
    return [t for _, t in items[:limit]]


def _build_design_section(gemini: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Section design a partir de design_analysis Gemini."""
    design = gemini.get('design_analysis') if isinstance(gemini.get('design_analysis'), dict) else {}
    if not design and not (gemini.get('modules') or {}).get('design'):
        return None

    score = design.get('score')
    if score is None:
        mod = (gemini.get('modules') or {}).get('design') or {}
        score = mod.get('score')

    paragraphs: List[str] = []
    score_i = _safe_int(score)
    if score_i is not None:
        paragraphs.append(
            f'Le score design est estimé à <b>{score_i}/100</b> '
            f'(lecture visuelle et cohérence de la vitrine).'
        )

    summary = (design.get('summary') or '').strip()
    if summary:
        paragraphs.append(summary[:900])
    elif (gemini.get('modules') or {}).get('design', {}).get('notes'):
        paragraphs.append(str(gemini['modules']['design']['notes'])[:900])

    ux = (design.get('ux_notes') or '').strip()
    if ux:
        paragraphs.append(f'<b>Expérience utilisateur :</b> {ux[:700]}')
    ui = (design.get('ui_notes') or '').strip()
    if ui:
        paragraphs.append(f'<b>Interface :</b> {ui[:700]}')

    bullets: List[str] = []
    for label, key in (('À conserver', 'to_keep'), ('À reprendre', 'to_redo')):
        for item in (design.get(key) or [])[:6]:
            s = str(item or '').strip()
            if s:
                bullets.append(f'{label} : {s[:200]}')

    if not paragraphs and not bullets:
        return None

    return {
        'id': 'design',
        'title': 'Design & expérience',
        'paragraphs': paragraphs or ['Analyse design disponible dans la synthèse.'],
        'bullets': bullets,
    }


def _build_strengths_section(gemini: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Forces et vigilance issues de Gemini."""
    works = [str(x).strip() for x in (gemini.get('what_works') or []) if str(x).strip()]
    wrong = [str(x).strip() for x in (gemini.get('whats_wrong') or []) if str(x).strip()]
    if not works and not wrong:
        return None

    paragraphs: List[str] = []
    bullets: List[str] = []
    if works:
        paragraphs.append('Ce qui fonctionne déjà :')
        bullets.extend(works[:6])
    if wrong:
        paragraphs.append('Points de vigilance :')
        bullets.extend(wrong[:6])

    return {
        'id': 'forces',
        'title': 'Forces & vigilance',
        'paragraphs': paragraphs,
        'bullets': bullets,
    }


def _build_refonte_section(gemini: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Recommandation de refonte (regle metier, pas IA a la volee)."""
    refonte = str(gemini.get('refonte_recommendation') or '').strip().lower()
    if not refonte:
        return None
    label = _REFONTE_LABELS.get(refonte, refonte.capitalize())
    score = _safe_int(gemini.get('overall_score'))
    score_txt = f' Score global estimé : {score}/100.' if score is not None else ''
    return {
        'id': 'refonte',
        'title': 'Niveau de refonte conseillé',
        'paragraphs': [
            f'Après croisement des scores mesurés et de la lecture design : <b>{label}</b>.{score_txt}',
            'Ce niveau indique l\'effort probable pour remettre le site au niveau attendu par vos clients.',
        ],
        'bullets': [],
    }


def _build_module_notes_section(gemini: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Notes modules Gemini (design/tech/seo/osint/pentest) en complement du pipeline."""
    modules = gemini.get('modules') if isinstance(gemini.get('modules'), dict) else {}
    if not modules:
        return None
    labels = {
        'design': 'Design',
        'technical': 'Technique',
        'seo': 'Visibilité',
        'osint': 'Exposition publique',
        'pentest': 'Sécurité applicative',
    }
    bullets: List[str] = []
    for key, label in labels.items():
        block = modules.get(key) if isinstance(modules.get(key), dict) else {}
        notes = str(block.get('notes') or '').strip()
        score = _safe_int(block.get('score'))
        if not notes and score is None:
            continue
        if score is not None and notes:
            bullets.append(f'{label} ({score}/100) : {notes[:200]}')
        elif score is not None:
            bullets.append(f'{label} : {score}/100')
        else:
            bullets.append(f'{label} : {notes[:220]}')
    if not bullets:
        return None
    return {
        'id': 'gemini_modules',
        'title': 'Indicateurs croisés',
        'paragraphs': [
            'Lecture complémentaire des modules (synthèse design + mesures) :',
        ],
        'bullets': bullets[:8],
    }


def _inject_sections(
    sections: List[Dict[str, Any]],
    extra: List[Optional[Dict[str, Any]]],
    *,
    after_id: str,
) -> List[Dict[str, Any]]:
    """Insere des sections apres un id donne."""
    out: List[Dict[str, Any]] = []
    inserted = False
    for sec in sections:
        out.append(sec)
        if sec.get('id') == after_id and not inserted:
            for block in extra:
                if block:
                    out.append(block)
            inserted = True
    if not inserted:
        out.extend([b for b in extra if b])
    return out


def compose_complete_narrative_sections(
    context: Dict[str, Any],
    gemini: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Reconstruit les sections narratives du rapport complet.

    Ordre :
    1. Sections pipeline (mesures)
    2. Design / forces / refonte / indicateurs Gemini
    3. Chapitres issus du Markdown report_document
    4. Plan d'action priorise fusionne

    @param context: Contexte audit (pipeline, company, …)
    @param gemini: Rapport Gemini (forme publique)
    @returns: Liste de sections pour le PDF
    """
    base_ctx = {
        **context,
        'executive_summary': _merge_executive_summary(
            context.get('pipeline') or {},
            context.get('opportunity'),
            gemini,
        ),
    }
    sections = build_audit_narrative_sections(base_ctx, tier='full')

    extras = [
        _build_design_section(gemini),
        _build_strengths_section(gemini),
        _build_module_notes_section(gemini),
        _build_refonte_section(gemini),
    ]
    sections = _inject_sections(sections, extras, after_id='seo')

    doc_sections = parse_report_document_sections(
        str(gemini.get('report_document') or ''),
    )
    if doc_sections:
        # Inserer avant la synthese finale
        out: List[Dict[str, Any]] = []
        inserted = False
        for sec in sections:
            if sec.get('id') == 'synthesis' and not inserted:
                out.extend(doc_sections)
                inserted = True
            out.append(sec)
        if not inserted:
            out.extend(doc_sections)
        sections = out

    actions = _merge_priority_actions(context.get('pipeline') or {}, gemini)
    if actions:
        for sec in sections:
            if sec.get('id') == 'synthesis':
                sec['bullets'] = actions + [
                    b for b in (sec.get('bullets') or [])
                    if _norm_key(b) not in {_norm_key(a) for a in actions}
                ][:12]
                sec['paragraphs'] = [
                    'Plan d\'action priorisé (données mesurées + synthèse design) :',
                    *(sec.get('paragraphs') or [])[:1],
                ]
                break
        # Aussi dans quick_wins du contexte amont
        context['quick_wins'] = actions[:8]

    return sections


def enrich_complete_report_context(
    database: Database,
    context: Dict[str, Any],
    *,
    progress_cb: Optional[Callable[..., None]] = None,
    ensure_gemini: bool = True,
) -> Dict[str, Any]:
    """
    Enrichit le contexte pour le mode complete sans agent Cursor.

    Utilise le rapport Gemini (GET public / include_document) puis compose
    le narratif PDF. Si aucun rapport : genere via build_full_report_for_entreprise.

    @param database: Acces BDD ProspectLab
    @param context: Contexte collect_audit_report_context
    @param progress_cb: Callback progression optionnel
    @param ensure_gemini: Generer le rapport Gemini s'il manque
    @returns: Contexte pret pour WebsiteAuditPdfGenerator (tier complete)
    """
    eid = int(context.get('entreprise_id') or 0)
    if ensure_gemini and eid > 0:
        payload = ensure_gemini_report_for_compose(database, eid, progress_cb=progress_cb)
    else:
        payload = load_gemini_public_payload(database, eid, include_document=True)

    gemini = _gemini_dict_from_payload(payload)
    pipeline = context.get('pipeline') or {}
    opportunity = context.get('opportunity')

    executive_summary = _merge_executive_summary(pipeline, opportunity, gemini)
    working_ctx = {**context, 'executive_summary': executive_summary}
    narrative_sections = compose_complete_narrative_sections(working_ctx, gemini)

    design_score = None
    design = gemini.get('design_analysis') if isinstance(gemini.get('design_analysis'), dict) else {}
    design_score = _safe_int(design.get('score'))
    if design_score is None:
        design_score = _safe_int((gemini.get('modules') or {}).get('design', {}).get('score'))

    enriched = {
        **working_ctx,
        'executive_summary': executive_summary,
        'narrative_sections': narrative_sections,
        'quick_wins': working_ctx.get('quick_wins') or context.get('quick_wins') or [],
        'report_tier': 'complete',
        'report_mode': 'complete',
        'pdf_engine': 'composed',
        'gemini_used': bool(gemini),
        'gemini_source': gemini.get('source') or payload.get('source'),
        'gemini_overall_score': gemini.get('overall_score'),
        'gemini_design_score': design_score,
        'gemini_report_id': payload.get('report_id'),
        'gemini_has_document': bool(str(gemini.get('report_document') or '').strip()),
    }
    return enriched
