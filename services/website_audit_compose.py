"""
Composition deterministe du rapport complet (PDF) sans agent Cursor.

Fusionne les donnees mesurees (pipeline ProspectLab) et la synthese Gemini
deja stockee en base pour produire un livrable coherent.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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


def _extract_gemini_report(latest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extrait le JSON rapport depuis la ligne BDD Gemini."""
    if not latest:
        return {}
    rep = latest.get('report')
    if isinstance(rep, dict):
        return rep
    if isinstance(rep, str) and rep.strip():
        return {}
    return {}


def _merge_executive_summary(
    pipeline: Dict[str, Any],
    opportunity: Optional[Dict[str, Any]],
    gemini: Dict[str, Any],
) -> List[str]:
    """
    Fusionne synthese pipeline + executive_summary Gemini (sans doublons).
    """
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
    """
    Priorise les actions : improvements Gemini, priority_actions, issues pipeline.
    """
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
                _add(it.get('message') or it.get('title') or it.get('description') or '', it.get('impact'))

    items.sort(key=lambda x: (x[0], x[1]))
    return [t for _, t in items[:limit]]


def _build_design_section(gemini: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Section design a partir de design_analysis Gemini."""
    design = gemini.get('design_analysis') if isinstance(gemini.get('design_analysis'), dict) else {}
    if not design and not gemini.get('modules', {}).get('design'):
        return None

    score = design.get('score')
    if score is None:
        mod = (gemini.get('modules') or {}).get('design') or {}
        score = mod.get('score')

    paragraphs: List[str] = []
    if score is not None:
        try:
            paragraphs.append(
                f'Le score design est estimé à <b>{int(score)}/100</b> '
                f'(lecture visuelle et cohérence de la vitrine).'
            )
        except (TypeError, ValueError):
            pass

    summary = (design.get('summary') or '').strip()
    if summary:
        paragraphs.append(summary[:900])
    elif (gemini.get('modules') or {}).get('design', {}).get('notes'):
        paragraphs.append(str(gemini['modules']['design']['notes'])[:900])

    ux = (design.get('ux_notes') or '').strip()
    if ux:
        paragraphs.append(f'<b>Experience utilisateur :</b> {ux[:700]}')

    bullets: List[str] = []
    for label, key in (('Points a conserver', 'to_keep'), ('A reprendre', 'to_redo')):
        for item in (design.get(key) or [])[:6]:
            s = str(item or '').strip()
            if s:
                bullets.append(f'{label} : {s[:200]}')

    if not paragraphs and not bullets:
        return None

    return {
        'id': 'design',
        'title': 'Design & experience',
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
        paragraphs.append('Ce qui fonctionne deja :')
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
    """Recommandation de refonte (regle metier, pas IA a la volée)."""
    refonte = str(gemini.get('refonte_recommendation') or '').strip().lower()
    if not refonte:
        return None
    label = _REFONTE_LABELS.get(refonte, refonte.capitalize())
    score = gemini.get('overall_score')
    score_txt = f' Score global estime : {int(score)}/100.' if score is not None else ''
    return {
        'id': 'refonte',
        'title': 'Niveau de refonte conseille',
        'paragraphs': [
            f'Après croisement des scores mesurés et de la lecture design : <b>{label}</b>.{score_txt}',
            'Ce niveau indique l\'effort probable pour remettre le site au niveau attendu par vos clients.',
        ],
        'bullets': [],
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

    @param context: Contexte audit (pipeline, company, …)
    @param gemini: Rapport Gemini normalise
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
        _build_refonte_section(gemini),
    ]
    sections = _inject_sections(sections, extras, after_id='seo')

    actions = _merge_priority_actions(context.get('pipeline') or {}, gemini)
    if actions:
        for sec in sections:
            if sec.get('id') == 'synthesis':
                sec['bullets'] = actions + [
                    b for b in (sec.get('bullets') or []) if _norm_key(b) not in {_norm_key(a) for a in actions}
                ][:12]
                sec['paragraphs'] = [
                    'Plan d\'action priorisé (données mesurées + synthèse design) :',
                    *(sec.get('paragraphs') or [])[:1],
                ]
                break

    return sections


def enrich_complete_report_context(
    database: Database,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enrichit le contexte pour le mode complete sans agent Cursor.

    @param database: Acces BDD ProspectLab
    @param context: Contexte collect_audit_report_context
    @returns: Contexte pret pour WebsiteAuditPdfGenerator (tier complete)
    """
    eid = int(context.get('entreprise_id') or 0)
    gemini_row = database.get_latest_entreprise_gemini_report(eid) if eid > 0 else None
    gemini = _extract_gemini_report(gemini_row)

    pipeline = context.get('pipeline') or {}
    opportunity = context.get('opportunity')

    executive_summary = _merge_executive_summary(pipeline, opportunity, gemini)
    narrative_sections = compose_complete_narrative_sections(
        {**context, 'executive_summary': executive_summary},
        gemini,
    )

    enriched = {
        **context,
        'executive_summary': executive_summary,
        'narrative_sections': narrative_sections,
        'report_tier': 'complete',
        'report_mode': 'complete',
        'pdf_engine': 'composed',
        'gemini_used': bool(gemini),
        'gemini_source': (gemini_row or {}).get('source') if gemini_row else None,
        'gemini_overall_score': gemini.get('overall_score') if gemini else None,
    }
    return enriched
