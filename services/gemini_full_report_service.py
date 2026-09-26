"""
Rapport d'audit complet via Gemini Vision (screenshots + tech/SEO/OSINT/pentest).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FULL_REPORT_SYSTEM_PROMPT = (
    "Tu es un consultant digital senior B2B francophone (audit site vitrine / PME). "
    "Tu analyses le site COMPLETEMENT : URL fournie (outil url_context si dispo), "
    "screenshots desktop/mobile/tablette, et les modules ProspectLab "
    "(technique, SEO, OSINT, pentest, scraping, age/refonte). "
    "Priorite absolue a l'audit design / UX / UI / parcours conversion / credibilite, "
    "puis technique / SEO / securite. "
    "Ne te contente JAMAIS de constater que des captures existent : "
    "decrit ce que tu vois (hierarchie visuelle, typo, couleurs, CTA, responsive, "
    "obsolescence, trust, accessibilite). "
    "Liste concretement ce qu'il faut garder, corriger ou refaire. "
    "Reponds UNIQUEMENT en JSON valide avec les cles: "
    "overall_score (0-100, plus bas = site plus problematique), "
    "refonte_recommendation (aucune|legere|partielle|totale), "
    "executive_summary (3-6 phrases FR, synthese business), "
    "design_analysis (objet {score 0-100, summary, ux_notes, ui_notes, "
    "to_keep liste, to_redo liste}), "
    "what_works (liste 3-8 points forts concrets, jamais 'captures disponibles'), "
    "whats_wrong (liste 4-10 problemes concrets design+tech+seo+securite), "
    "improvements (liste d'objets {area, priority, action} avec area dans "
    "design|ux|ui|technique|seo|securite|contenu|conversion et priority haute|moyenne|basse), "
    "modules (objet design/technical/seo/osint/pentest avec score et notes), "
    "priority_actions (liste 4-7 actions prioritaires ordonnees, tres concretes), "
    "commercial_pitch (2-3 phrases pour motiver un devis audit/refonte)."
)


def _mime_for_path(path: Path) -> str:
    """Retourne le MIME estime selon l'extension."""
    ext = path.suffix.lower()
    if ext in ('.jpg', '.jpeg'):
        return 'image/jpeg'
    if ext == '.png':
        return 'image/png'
    return 'image/webp'


def _as_list(value: Any) -> List[str]:
    """Normalise une valeur en liste de strings courtes."""
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()][:12]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_full_report(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Normalise le JSON Gemini (ou fallback) vers un schema stable.

    @param raw: Dict brut
    @param source: gemini|heuristic
    @returns: Rapport normalise
    """
    try:
        score = int(raw.get('overall_score', raw.get('score', 50)))
    except (TypeError, ValueError):
        score = 50
    score = max(0, min(100, score))

    refonte = str(raw.get('refonte_recommendation') or raw.get('refonte') or 'moyenne').lower()
    mapping = {
        'aucune': 'aucune',
        'none': 'aucune',
        'faible': 'legere',
        'legere': 'legere',
        'légère': 'legere',
        'moyenne': 'partielle',
        'partielle': 'partielle',
        'elevee': 'totale',
        'élevée': 'totale',
        'forte': 'totale',
        'totale': 'totale',
        'complete': 'totale',
        'complète': 'totale',
    }
    refonte = mapping.get(refonte, 'partielle')
    if refonte not in ('aucune', 'legere', 'partielle', 'totale'):
        if score < 35:
            refonte = 'totale'
        elif score < 55:
            refonte = 'partielle'
        elif score < 75:
            refonte = 'legere'
        else:
            refonte = 'aucune'

    improvements: List[Dict[str, str]] = []
    for item in raw.get('improvements') or []:
        if isinstance(item, dict):
            improvements.append({
                'area': str(item.get('area') or 'technique').strip()[:40],
                'priority': str(item.get('priority') or 'moyenne').strip()[:20],
                'action': str(item.get('action') or item.get('text') or '').strip()[:400],
            })
        elif isinstance(item, str) and item.strip():
            improvements.append({
                'area': 'technique',
                'priority': 'moyenne',
                'action': item.strip()[:400],
            })
    improvements = [i for i in improvements if i.get('action')][:12]

    modules_in = raw.get('modules') if isinstance(raw.get('modules'), dict) else {}
    modules_out: Dict[str, Any] = {}
    for key in ('design', 'technical', 'seo', 'osint', 'pentest'):
        block = modules_in.get(key)
        if isinstance(block, dict):
            modules_out[key] = {
                'score': block.get('score'),
                'notes': str(block.get('notes') or block.get('summary') or '').strip()[:600],
            }

    design_raw = raw.get('design_analysis') if isinstance(raw.get('design_analysis'), dict) else {}
    design_analysis: Dict[str, Any] = {}
    if design_raw:
        try:
            d_score = int(design_raw.get('score')) if design_raw.get('score') is not None else None
        except (TypeError, ValueError):
            d_score = None
        if d_score is not None:
            d_score = max(0, min(100, d_score))
        design_analysis = {
            'score': d_score,
            'summary': str(design_raw.get('summary') or '').strip()[:800],
            'ux_notes': str(design_raw.get('ux_notes') or '').strip()[:800],
            'ui_notes': str(design_raw.get('ui_notes') or '').strip()[:800],
            'to_keep': _as_list(design_raw.get('to_keep'))[:8],
            'to_redo': _as_list(design_raw.get('to_redo'))[:10],
        }
        if 'design' not in modules_out and d_score is not None:
            modules_out['design'] = {
                'score': d_score,
                'notes': design_analysis.get('summary') or '',
            }

    return {
        'overall_score': score,
        'refonte_recommendation': refonte,
        'executive_summary': str(raw.get('executive_summary') or raw.get('summary') or '').strip()[:1600],
        'design_analysis': design_analysis,
        'what_works': _as_list(raw.get('what_works') or raw.get('positives')),
        'whats_wrong': _as_list(raw.get('whats_wrong') or raw.get('negatives')),
        'improvements': improvements,
        'modules': modules_out,
        'priority_actions': _as_list(raw.get('priority_actions'))[:10],
        'commercial_pitch': str(raw.get('commercial_pitch') or raw.get('pitch') or '').strip()[:1000],
        'source': source,
    }


def _heuristic_full_report(pipeline: Dict[str, Any], opportunity: Any = None) -> Dict[str, Any]:
    """
    Fallback local si Gemini indisponible.

    Produit une synthese basee sur les modules ProspectLab (pas un audit Vision).
    """
    score = 58
    wrong: List[str] = []
    works: List[str] = []
    improvements: List[Dict[str, str]] = []
    modules_out: Dict[str, Any] = {}

    tech = pipeline.get('technical') or {}
    seo = pipeline.get('seo') or {}
    pentest = pipeline.get('pentest') or {}
    osint = pipeline.get('osint') or {}
    shots = pipeline.get('screenshots') or {}
    latest_shots = shots.get('latest') or {}

    if tech.get('status') == 'done':
        sec = tech.get('security_score')
        try:
            sec_i = int(sec) if sec is not None else None
        except (TypeError, ValueError):
            sec_i = None
        if sec_i is not None:
            modules_out['technical'] = {
                'score': sec_i,
                'notes': f'Score securite technique ProspectLab: {sec_i}/100',
            }
            if sec_i < 50:
                score -= 12
                wrong.append(f'Securite technique faible ({sec_i}/100)')
                improvements.append({
                    'area': 'securite',
                    'priority': 'haute',
                    'action': 'Corriger HTTPS, headers de securite et points techniques critiques',
                })
            elif sec_i >= 70:
                works.append(f'Base technique correcte (securite {sec_i}/100)')
        issues = tech.get('issues') or []
        if isinstance(issues, list) and issues:
            for issue in issues[:3]:
                txt = str(issue.get('title') or issue.get('message') or issue).strip()
                if txt:
                    wrong.append(txt[:180])
            wrong.append(f'{min(len(issues), 8)} points techniques signales au total')
    else:
        wrong.append('Analyse technique absente — relancer le module technique')

    if seo.get('status') == 'done':
        try:
            seo_score = int(seo.get('score')) if seo.get('score') is not None else None
        except (TypeError, ValueError):
            seo_score = None
        if seo_score is not None:
            modules_out['seo'] = {
                'score': seo_score,
                'notes': f'Score SEO ProspectLab: {seo_score}/100',
            }
            if seo_score < 50:
                score -= 10
                wrong.append(f'SEO faible ({seo_score}/100)')
                improvements.append({
                    'area': 'seo',
                    'priority': 'haute',
                    'action': 'Revoir meta title/description, structure Hn et signaux SEO',
                })
            elif seo_score >= 70:
                works.append(f'SEO deja correct ({seo_score}/100)')
    else:
        wrong.append('Analyse SEO absente — relancer le module SEO')

    if pentest.get('status') == 'done':
        try:
            risk = int(pentest.get('risk_score')) if pentest.get('risk_score') is not None else None
        except (TypeError, ValueError):
            risk = None
        if risk is not None:
            modules_out['pentest'] = {
                'score': max(0, 100 - risk),
                'notes': f'Risque pentest ProspectLab: {risk}/100',
            }
            if risk >= 60:
                score -= 15
                wrong.append(f'Risque pentest eleve ({risk}/100)')
                improvements.append({
                    'area': 'securite',
                    'priority': 'haute',
                    'action': 'Traiter les vulnerabilites critiques / hautes detectees',
                })
            elif risk < 30:
                works.append(f'Risque pentest contenu ({risk}/100)')
    else:
        wrong.append('Analyse pentest absente')

    if osint.get('status') == 'done':
        modules_out['osint'] = {
            'score': None,
            'notes': 'Module OSINT disponible — croiser exposition et surface',
        }
        works.append('Donnees OSINT disponibles pour contextualiser la surface')
    else:
        wrong.append('Analyse OSINT absente')

    design_score = latest_shots.get('design_score')
    try:
        design_score_i = int(design_score) if design_score is not None else None
    except (TypeError, ValueError):
        design_score_i = None

    design_analysis: Dict[str, Any] = {
        'score': design_score_i,
        'summary': (
            'Revue visuelle Gemini indisponible : pas d\'analyse UX/UI detaillee. '
            'Relancer le rapport une fois le modele Vision operationnel.'
        ),
        'ux_notes': 'Non evalue (fallback heuristique sans Vision).',
        'ui_notes': 'Non evalue (fallback heuristique sans Vision).',
        'to_keep': [],
        'to_redo': [
            'Relancer l\'audit Gemini Vision pour un diagnostic design/UX complet',
        ],
    }
    if design_score_i is not None:
        modules_out['design'] = {
            'score': design_score_i,
            'notes': f'Score design precedent: {design_score_i}/100',
        }
        if design_score_i < 45:
            score -= 10
            wrong.append(f'Score design faible ({design_score_i}/100) sur une revue precedente')
            improvements.append({
                'area': 'design',
                'priority': 'haute',
                'action': 'Moderniser UI/UX (hierarchie, CTA, responsive, trust)',
            })
        elif design_score_i >= 70:
            works.append(f'Score design precedent correct ({design_score_i}/100)')

    if shots.get('status') != 'done':
        wrong.append('Screenshots indisponibles — impossible de juger le rendu actuel')
        score -= 8
    else:
        improvements.append({
            'area': 'ux',
            'priority': 'haute',
            'action': (
                'Auditer parcours, CTA et lisibilite mobile/desktop '
                '(attente d\'une analyse Vision complete)'
            ),
        })

    if opportunity and isinstance(opportunity, dict):
        niveau = str(opportunity.get('opportunite') or opportunity.get('niveau') or '')
        if 'Très' in niveau or 'Elevee' in niveau or 'Élevée' in niveau:
            score = min(score, 45)

    score = max(0, min(100, score))
    if score < 35:
        refonte = 'totale'
    elif score < 55:
        refonte = 'partielle'
    elif score < 75:
        refonte = 'legere'
    else:
        refonte = 'aucune'

    if not works:
        works.append('Donnees d\'audit ProspectLab partielles exploitees')
    if not wrong:
        wrong.append('Pas de signal critique majeur dans les modules disponibles')
    if not improvements:
        improvements.append({
            'area': 'design',
            'priority': 'haute',
            'action': 'Relancer l\'audit Gemini Vision des que le modele API est disponible',
        })

    return _normalize_full_report(
        {
            'overall_score': score,
            'refonte_recommendation': refonte,
            'executive_summary': (
                'Synthese heuristique basee sur les modules ProspectLab '
                '(technique / SEO / OSINT / pentest). '
                'Gemini Vision etait indisponible : pas d\'audit design/UX du site '
                'via URL + screenshots. Relancer pour obtenir le rapport complet.'
            ),
            'design_analysis': design_analysis,
            'what_works': works,
            'whats_wrong': wrong,
            'improvements': improvements,
            'modules': modules_out,
            'priority_actions': [i['action'] for i in improvements[:6]],
            'commercial_pitch': (
                'Un vrai audit Gemini (URL + captures + modules) + modernisation '
                'ciblée renforcerait credibilite et conversion.'
                if refonte in ('partielle', 'totale')
                else 'Quelques optimisations ciblées suffisent probablement — confirmer via Vision.'
            ),
        },
        'heuristic',
    )


def _screenshot_files_ok(latest: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Verifie qu'au moins un fichier screenshot desktop/tablette/mobile existe sur disque.

    @returns: (ok, chemin_principal)
    """
    if not latest:
        return False, None
    for device in ('desktop', 'tablet', 'mobile'):
        block = latest.get(device) or {}
        fp = block.get('file_path')
        if fp and Path(str(fp)).is_file():
            return True, str(fp)
    return False, None


def ensure_entreprise_screenshots(
    database,
    entreprise_id: int,
    website: str,
    progress_cb=None,
) -> Dict[str, Any]:
    """
    S'assure qu'un set de screenshots valide existe (sinon capture synchrone).

    @param database: Instance Database
    @param entreprise_id: ID entreprise
    @param website: URL canonique
    @param progress_cb: Callback optionnel (message, pct?)
    @returns: Dict latest screenshots (peut etre vide si echec)
    """
    def _emit(msg: str, pct: Optional[int] = None) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(msg, pct)
        except TypeError:
            progress_cb(msg)

    _emit('Screenshots: lecture du dernier set en base…', 12)
    latest = database.get_latest_entreprise_screenshots(int(entreprise_id)) or {}
    ok, path = _screenshot_files_ok(latest)
    if ok:
        _emit(f'Screenshots OK sur disque ({path})', 22)
        return latest

    if latest:
        _emit('Screenshots en base mais fichiers absents / 404 — nouvelle capture…', 15)
    else:
        _emit('Aucun screenshot — lancement capture Playwright (desktop/tablette/mobile)…', 15)

    try:
        from tasks.screenshot_tasks import website_screenshot_task

        _emit(f'Capture en cours pour {website} (peut prendre 1-3 min)…', 18)
        # apply() execute dans le process courant (pas de deadlock Celery)
        website_screenshot_task.apply(
            kwargs=dict(
                url=website,
                entreprise_id=int(entreprise_id),
            )
        )
        _emit('Capture Playwright terminee — relecture BDD…', 28)
    except Exception as exc:
        logger.warning('ensure_entreprise_screenshots echec capture: %s', exc)
        _emit(f'Echec capture screenshots: {exc}', 28)

    latest = database.get_latest_entreprise_screenshots(int(entreprise_id)) or {}
    ok2, path2 = _screenshot_files_ok(latest)
    if ok2:
        _emit(f'Screenshots prets ({path2})', 30)
    else:
        _emit('Screenshots toujours indisponibles apres capture', 30)
    return latest


def _load_screenshot_images(latest: Dict[str, Any], max_images: int = 3) -> List[Dict[str, Any]]:
    """Charge jusqu'a max_images fichiers (desktop puis mobile puis tablette) pour Gemini."""
    images: List[Dict[str, Any]] = []
    for device in ('desktop', 'mobile', 'tablet'):
        if len(images) >= max_images:
            break
        block = latest.get(device) or {}
        fp = block.get('file_path')
        if not fp:
            continue
        path = Path(str(fp))
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
            # Limite taille ~4 Mo pour rester raisonnable
            if len(data) > 4_500_000:
                continue
            images.append({
                'bytes': data,
                'mime_type': _mime_for_path(path),
                'device': device,
            })
        except Exception as exc:
            logger.warning('Lecture screenshot %s: %s', path, exc)
    return images


def _compact_pipeline_for_prompt(pipeline: Dict[str, Any]) -> Dict[str, Any]:
    """Reduit le pipeline pour le prompt (tokens)."""
    out: Dict[str, Any] = {}
    for key, block in (pipeline or {}).items():
        if not isinstance(block, dict):
            continue
        if key == 'screenshots':
            latest = block.get('latest') or {}
            out[key] = {
                'status': block.get('status'),
                'design_score': latest.get('design_score'),
                'design_source': latest.get('design_source'),
                'has_desktop': bool((latest.get('desktop') or {}).get('file_path')),
                'page_url': latest.get('page_url'),
            }
            continue
        slim = {k: v for k, v in block.items() if k != 'latest'}
        # Tronquer listes issues
        for list_key in ('issues', 'vulnerabilities'):
            if isinstance(slim.get(list_key), list):
                slim[list_key] = slim[list_key][:12]
        out[key] = slim
    return out


def build_full_report_for_entreprise(
    database,
    entreprise_id: int,
    *,
    ensure_screenshots: bool = True,
    progress_cb=None,
) -> Dict[str, Any]:
    """
    Construit le rapport Gemini complet pour une entreprise.

    @param database: Instance Database
    @param entreprise_id: ID
    @param ensure_screenshots: Capture si manquant / 404 disque
    @param progress_cb: Callback progression (str)
    @returns: Dict success, report, meta
    """
    from services.website_audit_data import build_audit_pipeline
    from utils.url_utils import canonical_website_https_url

    def _emit(msg: str, pct: Optional[int] = None) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(msg, pct)
        except TypeError:
            progress_cb(msg)

    eid = int(entreprise_id)
    _emit(f'Chargement entreprise #{eid}…', 5)
    entreprise = database.get_entreprise(eid) or {}
    if not entreprise:
        return {'success': False, 'error': 'Entreprise introuvable', 'entreprise_id': eid}

    website = canonical_website_https_url(entreprise.get('website'))
    if not website:
        return {'success': False, 'error': 'Aucun website valide', 'entreprise_id': eid}

    _emit(f'Site cible: {website}', 8)
    analyzed_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    screenshot_set_id = None
    screenshots_ensured = False

    if ensure_screenshots:
        _emit('Etape screenshots (verif / capture si besoin)…', 10)
        latest = ensure_entreprise_screenshots(database, eid, website, progress_cb=progress_cb)
        screenshots_ensured = True
    else:
        _emit('Screenshots: mode sans capture forcee', 12)
        latest = database.get_latest_entreprise_screenshots(eid) or {}

    if latest.get('id'):
        try:
            screenshot_set_id = int(latest.get('id'))
            _emit(f'Set screenshot id={screenshot_set_id}', 32)
        except (TypeError, ValueError):
            screenshot_set_id = None
    else:
        _emit('Aucun set screenshot disponible', 32)

    _emit('Aggregation pipeline audit (scraping / tech / SEO / OSINT / pentest)…', 35)

    pipeline = build_audit_pipeline(database, eid)
    for mod in ('scraping', 'technical', 'seo', 'osint', 'pentest', 'screenshots'):
        st = (pipeline.get(mod) or {}).get('status') or 'never'
        _emit(f'  · Module {mod}: {st}', 38)

    opportunity = None
    try:
        _emit('Calcul score opportunite…', 42)
        opportunity = database.get_opportunity_score(eid) if hasattr(database, 'get_opportunity_score') else None
        if opportunity is None and hasattr(database, 'update_opportunity_score'):
            opportunity = database.update_opportunity_score(eid)
        if opportunity:
            _emit(f'Opportunite: {opportunity.get("opportunite") or opportunity.get("niveau") or "ok"}', 44)
    except Exception as opp_exc:
        _emit(f'Opportunite indisponible ({opp_exc})', 44)
        opportunity = None

    _emit('Compression du contexte pour Gemini…', 48)
    compact = _compact_pipeline_for_prompt(pipeline)
    context_text = json.dumps(
        {
            'entreprise': {
                'id': eid,
                'nom': entreprise.get('nom'),
                'website': website,
                'secteur': entreprise.get('secteur'),
                'categorie': entreprise.get('categorie'),
                'tags': entreprise.get('tags'),
                'site_age_score': entreprise.get('site_age_score'),
                'site_indicators': entreprise.get('site_indicators'),
                'http_last_modified': entreprise.get('http_last_modified'),
            },
            'opportunity': opportunity,
            'pipeline': compact,
        },
        ensure_ascii=False,
        default=str,
    )
    if len(context_text) > 28000:
        context_text = context_text[:28000] + '…'
    _emit(f'Contexte pret (~{len(context_text)} caracteres)', 52)

    _emit('Chargement images screenshots pour Vision…', 55)
    images = _load_screenshot_images(latest, max_images=3)
    for img in images:
        _emit(f'  · Image {img.get("device")}: {len(img.get("bytes") or b"")} octets', 56)
    if not images:
        _emit('Aucune image jointe — analyse texte + URL seule', 56)

    modules_used = {
        'scraping': (pipeline.get('scraping') or {}).get('status'),
        'technical': (pipeline.get('technical') or {}).get('status'),
        'seo': (pipeline.get('seo') or {}).get('status'),
        'osint': (pipeline.get('osint') or {}).get('status'),
        'pentest': (pipeline.get('pentest') or {}).get('status'),
        'screenshots': 'done' if images else ((pipeline.get('screenshots') or {}).get('status') or 'never'),
        'screenshot_images_sent': len(images),
        'url_context': True,
    }

    use_gemini = bool(
        os.environ.get('GEMINI_API_KEY')
        or os.environ.get('GEMINI_API_KEYS')
        or os.environ.get('GEMINI_API_KEY_2')
    )

    report: Dict[str, Any]
    source = 'heuristic'
    gemini_tools = [{'url_context': {}}]
    if use_gemini:
        _emit(
            f'Appel Gemini Vision ({len(images)} image(s) + URL {website}) — patience…',
            60,
        )
        try:
            from services.gemini_client import gemini_vision_multi_json, gemini_generate_content

            devices = ', '.join(str(i.get('device')) for i in images) or 'aucune'
            prompt = (
                f"Audit complet du site : {website}\n\n"
                "Mission :\n"
                "1) Consulte l'URL ci-dessus (outil url_context) pour comprendre le site reel.\n"
                "2) Analyse les screenshots joints (devices: "
                f"{devices}) pour le design, l'UX/UI, le responsive et la conversion.\n"
                "3) Croise avec les modules ProspectLab du contexte JSON "
                "(technique, SEO, OSINT, pentest, age/refonte).\n"
                "4) Produis un rapport actionnable : ce qui marche, ce qui cloche, "
                "ce qu'il faut refaire (design + tech + SEO + securite).\n"
                "Interdit : se contenter de dire que des captures existent.\n\n"
                f"CONTEXTE PROSPECTLAB:\n{context_text}"
            )
            if images:
                _emit('Envoi multimodal (URL + texte + images) a Gemini…', 65)
                raw = gemini_vision_multi_json(
                    prompt=prompt,
                    images=images,
                    system_instruction=FULL_REPORT_SYSTEM_PROMPT,
                    max_tokens=8192,
                    timeout_ms=120_000,
                    tools=gemini_tools,
                )
            else:
                _emit('Envoi texte + URL a Gemini…', 65)
                text = gemini_generate_content(
                    parts=[{'text': prompt}],
                    system_instruction=FULL_REPORT_SYSTEM_PROMPT,
                    json_mode=True,
                    temperature=0.25,
                    max_tokens=8192,
                    timeout_ms=120_000,
                    tools=gemini_tools,
                )
                raw = json.loads(text) if isinstance(text, str) else text
            _emit('Reponse Gemini recue — normalisation JSON…', 85)
            report = _normalize_full_report(raw if isinstance(raw, dict) else {}, 'gemini')
            source = 'gemini'
            _emit(
                f'Rapport Gemini OK — score {report.get("overall_score")}/100, '
                f'refonte={report.get("refonte_recommendation")}',
                90,
            )
        except Exception as exc:
            logger.warning('Gemini full report echec, fallback: %s', exc)
            _emit(f'Gemini en echec ({exc}) — fallback heuristique…', 80)
            report = _heuristic_full_report(pipeline, opportunity)
            source = 'heuristic'
            report['fallback_error'] = str(exc)[:300]
    else:
        _emit('Pas de cle Gemini — fallback heuristique local…', 70)
        report = _heuristic_full_report(pipeline, opportunity)

    report['analyzed_at'] = analyzed_at
    report['entreprise_id'] = eid
    report['website'] = website
    report['modules_used'] = modules_used
    _emit('Finalisation du rapport…', 95)

    return {
        'success': True,
        'entreprise_id': eid,
        'website': website,
        'report': report,
        'overall_score': report.get('overall_score'),
        'refonte_recommendation': report.get('refonte_recommendation'),
        'source': source,
        'screenshot_set_id': screenshot_set_id,
        'screenshots_ensured': screenshots_ensured,
        'modules_used': modules_used,
        'analyzed_at': analyzed_at,
    }
