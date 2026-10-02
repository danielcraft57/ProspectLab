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

_redis_client = None
_GEMINI_SLOT_KEY = 'prospectlab:gemini_full_report:slots'
_GEMINI_SLOT_TTL = 900


def _redis():
    """Client Redis lazy (broker Celery)."""
    global _redis_client
    if _redis_client is None:
        import redis
        from config import CELERY_BROKER_URL
        _redis_client = redis.Redis.from_url(
            CELERY_BROKER_URL or 'redis://127.0.0.1:6379/0',
            decode_responses=True,
        )
    return _redis_client


def _acquire_gemini_slot(
    *,
    max_concurrent: int = 1,
    wait_sec: int = 1800,
    progress_cb=None,
) -> bool:
    """
    Reserve un slot Gemini (evite le burst 429 sur free tier).

    @param max_concurrent: Nb max d'appels Vision en parallele
    @param wait_sec: Attente max (defaut 30 min pour files de 20+)
    @param progress_cb: Callback optionnel (message, pct) pendant l'attente
    @returns: True si slot acquis
    """
    import time as _time
    max_c = max(1, int(max_concurrent or 1))
    deadline = _time.time() + max(30, int(wait_sec or 1800))
    script = """
local key = KEYS[1]
local maxc = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local value = tonumber(redis.call('get', key) or '0')
if value < maxc then
  local next = value + 1
  redis.call('set', key, next, 'EX', ttl)
  return 1
end
return 0
"""
    last_emit = 0.0
    waited = 0
    while _time.time() < deadline:
        # Circuit quota ouvert → inutile d'attendre un slot Vision
        try:
            from services.gemini_queue import is_gemini_quota_circuit_open
            if is_gemini_quota_circuit_open():
                if progress_cb:
                    try:
                        from services.gemini_queue import format_gemini_circuit_message
                        progress_cb(format_gemini_circuit_message(), 63)
                    except Exception:
                        progress_cb('Quota Gemini epuise — sortie de file', 63)
                return False
        except Exception:
            pass
        try:
            ok = _redis().eval(script, 1, _GEMINI_SLOT_KEY, max_c, _GEMINI_SLOT_TTL)
            if int(ok or 0) == 1:
                return True
        except Exception as exc:
            logger.warning('Gemini slot acquire ignore: %s', exc)
            return True  # ne bloque pas si Redis HS
        now = _time.time()
        if progress_cb and (now - last_emit) >= 8.0:
            last_emit = now
            left = max(0, int(deadline - now))
            try:
                progress_cb(
                    f'File Gemini saturee — attente d\'un slot libre (~{left // 60} min)…',
                    63,
                )
            except Exception:
                pass
        waited += 1
        _time.sleep(3.0)
    return False


def _release_gemini_slot() -> None:
    """Libere un slot Gemini."""
    script = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local value = tonumber(redis.call('get', key) or '0')
if value <= 0 then
  redis.call('set', key, 0, 'EX', ttl)
  return 0
end
local next = value - 1
if next <= 0 then
  redis.call('set', key, 0, 'EX', ttl)
  return 0
end
redis.call('set', key, next, 'EX', ttl)
return next
"""
    try:
        _redis().eval(script, 1, _GEMINI_SLOT_KEY, _GEMINI_SLOT_TTL)
    except Exception as exc:
        logger.warning('Gemini slot release ignore: %s', exc)


FULL_REPORT_WRITING_STYLE = (
    "STYLE D'ECRITURE (obligatoire pour TOUS les textes FR du JSON, "
    "surtout report_document, executive_summary, notes, pitch) : "
    "Tu es une personne reelle qui s'exprime de maniere naturelle, spontanee et vivante. "
    "Evite les phrases toutes faites, les mots trop formels ou techniques, "
    "et les expressions trop parfaites. Utilise des tournures simples, "
    "comme dans une discussion entre amis. Sois clair, direct, un peu imparfait "
    "si besoin, mais toujours humain. Tu peux meme parfois raccourcir des phrases "
    "ou employer un ton plus detendu. Donne une reponse qui ne semble pas ecrite par une IA. "
    "Consignes de ponctuation : utilise des apostrophes droites (') et non des "
    "apostrophes courbees. N'utilise pas de tirets cadratins, uniquement des tirets simples (-). "
    "Adapte le langage pour que le style soit plus humain, moins formate, "
    "et ne ressemble pas a une reponse de chatbot. "
    "ORTHOGRAPHE ET GRAMMAIRE : soigne l'orthographe et la grammaire francaises "
    "(accords, conjugaisons, accents, elisions). Ton detendu OK, fautes non. "
    "Des phrases qui se lisent bien a voix haute."
)

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
    + FULL_REPORT_WRITING_STYLE
    + " "
    "Le champ report_document est le coeur lisible du livrable : "
    "un vrai document Markdown structure (titres # ## ###, paragraphes courts, "
    "listes a puces, sous-sections). Sections minimales : "
    "Resume, Design UX/UI, Technique, SEO, Securite / confiance, "
    "Ce qui marche, Ce qui cloche, Plan d'action, Pitch. "
    "Paragraphes aeres, titres clairs, pas de pavé unique, pas de JSON dans ce champ. "
    "Reponds UNIQUEMENT en JSON valide avec les cles: "
    "overall_score (0-100, plus bas = site plus problematique), "
    "refonte_recommendation (aucune|legere|partielle|totale), "
    "executive_summary (3-6 phrases FR, synthese business), "
    "report_document (string Markdown FR, doc d'audit complet et bien structure, "
    "cible 600-1800 mots), "
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


def _compress_screenshot_bytes(
    data: bytes,
    *,
    max_width: int = 1280,
    jpeg_quality: int = 72,
) -> Tuple[bytes, str]:
    """
    Redimensionne / recompresse une capture pour alleger l'appel Vision.

    @param data: Octets image source
    @param max_width: Largeur max (px)
    @param jpeg_quality: Qualite JPEG 40-90
    @returns: (octets, mime_type)
    """
    try:
        from io import BytesIO
        from PIL import Image

        img = Image.open(BytesIO(data))
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        elif img.mode == 'L':
            img = img.convert('RGB')
        w, h = img.size
        if w > max_width and max_width > 0:
            nh = max(1, int(h * (max_width / float(w))))
            img = img.resize((max_width, nh), Image.Resampling.LANCZOS)
        buf = BytesIO()
        q = max(40, min(90, int(jpeg_quality)))
        img.save(buf, format='JPEG', quality=q, optimize=True)
        return buf.getvalue(), 'image/jpeg'
    except Exception as exc:
        logger.debug('Compression screenshot ignoree: %s', exc)
        return data, 'image/webp'


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

    report_doc = str(
        raw.get('report_document')
        or raw.get('document')
        or raw.get('markdown')
        or ''
    ).strip()
    if len(report_doc) > 24000:
        report_doc = report_doc[:24000] + '\n\n…'

    return {
        'overall_score': score,
        'refonte_recommendation': refonte,
        'executive_summary': str(raw.get('executive_summary') or raw.get('summary') or '').strip()[:1600],
        'report_document': report_doc,
        'design_analysis': design_analysis,
        'what_works': _as_list(raw.get('what_works') or raw.get('positives')),
        'whats_wrong': _as_list(raw.get('whats_wrong') or raw.get('negatives')),
        'improvements': improvements,
        'modules': modules_out,
        'priority_actions': _as_list(raw.get('priority_actions'))[:10],
        'commercial_pitch': str(raw.get('commercial_pitch') or raw.get('pitch') or '').strip()[:1000],
        'source': source,
    }


def _heuristic_full_report(
    pipeline: Dict[str, Any],
    opportunity: Any = None,
    *,
    fallback_reason: str | None = None,
) -> Dict[str, Any]:
    """
    Fallback local si Gemini indisponible.

    Produit une synthese basee sur les modules ProspectLab (pas un audit Vision).

    @param pipeline: Pipeline modules
    @param opportunity: Score opportunite optionnel
    @param fallback_reason: Cause (quota 429, pas de cle, …)
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

    reason = str(fallback_reason or '').strip()
    reason_low = reason.lower()
    if '503' in reason or 'high demand' in reason_low or 'surcharge' in reason_low:
        why = (
            'Gemini en surcharge (503 high demand) — ce n\'est pas un quota. '
            'Relancer dans quelques minutes pour un vrai audit Vision.'
        )
    elif '429' in reason or 'quota' in reason_low or 'resource_exhausted' in reason_low:
        why = (
            'Gemini en quota (free tier / trop de requetes). '
            'Relancer plus tard pour un vrai audit Vision.'
        )
    elif reason:
        why = f'Gemini indisponible ({reason[:180]}). Relancer pour le rapport Vision.'
    else:
        why = (
            'Gemini Vision etait indisponible : pas d\'audit design/UX du site '
            'via URL + screenshots. Relancer pour obtenir le rapport complet.'
        )

    return _normalize_full_report(
        {
            'overall_score': score,
            'refonte_recommendation': refonte,
            'executive_summary': (
                'Synthese heuristique basee sur les modules ProspectLab '
                f'(technique / SEO / OSINT / pentest). {why}'
            ),
            'report_document': (
                '# Resume\n\n'
                'Synthese locale a partir des modules ProspectLab '
                '(pas d\'analyse Vision des captures).\n\n'
                f'{why}\n\n'
                '## Ce qui marche\n\n'
                + ''.join(f'- {w}\n' for w in works[:8])
                + '\n## Ce qui cloche\n\n'
                + ''.join(f'- {w}\n' for w in wrong[:10])
                + '\n## Plan d\'action\n\n'
                + ''.join(f'1. {i["action"]}\n' for i in improvements[:6])
                + '\n## Note\n\n'
                'Relancer l\'audit Gemini Vision pour un vrai document design / UX structure.\n'
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


def _load_screenshot_images(latest: Dict[str, Any], max_images: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Charge jusqu'a max_images fichiers (desktop puis mobile puis tablette) pour Gemini.

    Compresse / redimensionne par defaut pour limiter les 503 (requetes plus legeres).
    Variables : GEMINI_VISION_MAX_IMAGES (defaut 1), GEMINI_VISION_MAX_WIDTH (1280),
    GEMINI_VISION_JPEG_QUALITY (72), GEMINI_VISION_COMPRESS (1/0).
    """
    if max_images is None:
        try:
            max_images = int(os.environ.get('GEMINI_VISION_MAX_IMAGES') or 1)
        except (TypeError, ValueError):
            max_images = 1
    max_images = max(1, min(3, int(max_images)))
    try:
        max_width = int(os.environ.get('GEMINI_VISION_MAX_WIDTH') or 1280)
    except (TypeError, ValueError):
        max_width = 1280
    try:
        jpeg_q = int(os.environ.get('GEMINI_VISION_JPEG_QUALITY') or 72)
    except (TypeError, ValueError):
        jpeg_q = 72
    do_compress = str(os.environ.get('GEMINI_VISION_COMPRESS') or '1').strip().lower() not in (
        '0', 'false', 'no', 'off',
    )

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
            if len(data) > 4_500_000 and not do_compress:
                continue
            mime = _mime_for_path(path)
            if do_compress:
                data, mime = _compress_screenshot_bytes(
                    data,
                    max_width=max_width,
                    jpeg_quality=jpeg_q,
                )
            if len(data) > 4_500_000:
                continue
            images.append({
                'bytes': data,
                'mime_type': mime,
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
    # 1 image (desktop) + compression : moins de 503 qu'avec 2-3 captures brutes
    images = _load_screenshot_images(latest)
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
        'url_context': False,
    }

    use_gemini = bool(
        os.environ.get('GEMINI_API_KEY')
        or os.environ.get('GEMINI_API_KEYS')
        or os.environ.get('GEMINI_API_KEY_2')
    )

    # Circuit breaker : un job precedent a deja epuise toutes les cles → skip Vision
    circuit_open = False
    circuit_msg = ''
    try:
        from services.gemini_queue import (
            get_gemini_quota_circuit,
            format_gemini_circuit_message,
        )
        circuit = get_gemini_quota_circuit()
        if circuit:
            circuit_open = True
            circuit_msg = format_gemini_circuit_message(circuit)
            use_gemini = False
            _emit(circuit_msg, 60)
    except Exception:
        pass

    report: Dict[str, Any]
    source = 'heuristic'
    if use_gemini:
        _emit(
            f'Appel Gemini Vision ({len(images)} image(s), site {website})…',
            60,
        )
        try:
            from services.gemini_client import gemini_vision_multi_json, gemini_generate_content

            devices = ', '.join(str(i.get('device')) for i in images) or 'aucune'
            prompt = (
                f"Audit complet du site : {website}\n\n"
                "Mission :\n"
                "1) Analyse les screenshots joints (devices: "
                f"{devices}) pour le design, l'UX/UI, le responsive et la conversion.\n"
                "2) Croise avec les modules ProspectLab du contexte JSON "
                "(technique, SEO, OSINT, pentest, age/refonte).\n"
                "3) Produis un rapport actionnable : ce qui marche, ce qui cloche, "
                "ce qu'il faut refaire (design + tech + SEO + securite).\n"
                "4) Remplis surtout report_document en Markdown bien structure "
                "(titres, sous-titres, paragraphes courts, listes) - une vraie doc lisible.\n"
                "5) Style humain + orthographe / grammaire soignees "
                "(voir consignes systeme).\n"
                "Interdit : se contenter de dire que des captures existent.\n\n"
                f"CONTEXTE PROSPECTLAB:\n{context_text}"
            )

            def _call_gemini(with_url_tool: bool) -> Dict[str, Any]:
                """
                Appelle Gemini (vision ou texte).

                @param with_url_tool: Active l'outil url_context
                @returns: Dict JSON brut
                """
                tools = [{'url_context': {}}] if with_url_tool else None
                # Vague sequentielle sur les cles : peu de rounds globaux suffisent
                retries = 2
                if images:
                    return gemini_vision_multi_json(
                        prompt=prompt,
                        images=images,
                        system_instruction=FULL_REPORT_SYSTEM_PROMPT,
                        max_tokens=8192,
                        timeout_ms=90_000,
                        tools=tools,
                        quota_retry_rounds=retries,
                        progress_cb=_emit,
                    )
                text = gemini_generate_content(
                    parts=[{'text': prompt}],
                    system_instruction=FULL_REPORT_SYSTEM_PROMPT,
                    json_mode=True,
                    temperature=0.35,
                    max_tokens=8192,
                    timeout_ms=90_000,
                    tools=tools,
                    quota_retry_rounds=retries,
                    progress_cb=_emit,
                )
                return json.loads(text) if isinstance(text, str) else text

            from services.gemini_client import gemini_config as _gemini_cfg
            # 1 Vision a la fois : plusieurs jobs crament tous les comptes free-tier
            max_conc = int((_gemini_cfg() or {}).get('max_concurrent_full_reports') or 1)
            wait_api = int(os.environ.get('GEMINI_SLOT_WAIT_SEC') or 900)
            _emit(f'File d\'attente Gemini (max {max_conc} Vision en parallele)…', 62)
            got_slot = _acquire_gemini_slot(
                max_concurrent=max_conc,
                wait_sec=wait_api,
                progress_cb=_emit,
            )
            if not got_slot:
                raise RuntimeError(
                    'Timeout file d\'attente Gemini (trop de jobs simultanés). '
                    'Réessaie plus tard — le quota free tier est limite.'
                )

            # 1) Vision + contexte ProspectLab (rapide / fiable)
            _emit('Envoi multimodal (texte + images) a Gemini…', 65)
            try:
                try:
                    raw = _call_gemini(with_url_tool=False)
                except Exception as first_exc:
                    # 2) Retry avec url_context si le 1er tour echoue
                    _emit(f'1er appel echoue ({first_exc}) — retry avec url_context…', 70)
                    modules_used['url_context'] = True
                    raw = _call_gemini(with_url_tool=True)
            finally:
                _release_gemini_slot()

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
            from services.gemini_client import is_gemini_quota_error
            quota_hit = is_gemini_quota_error(exc)
            err_low = str(exc or '').lower()
            overload = ('503' in err_low) or ('high demand' in err_low)
            if quota_hit:
                _emit(
                    'Quota Gemini atteint (429) — fallback heuristique local…',
                    80,
                )
            elif overload:
                _emit(
                    'Gemini en surcharge (503 high demand) — fallback heuristique… '
                    'Relancer dans quelques minutes pour Vision.',
                    80,
                )
            else:
                _emit(f'Gemini en echec ({exc}) — fallback heuristique…', 80)
            report = _heuristic_full_report(
                pipeline,
                opportunity,
                fallback_reason=str(exc)[:300],
            )
            source = 'heuristic'
            report['fallback_error'] = str(exc)[:300]
            report['quota_exceeded'] = bool(quota_hit)
            report['transient_overload'] = bool(overload)
            if quota_hit:
                try:
                    from services.gemini_queue import (
                        arm_gemini_quota_circuit,
                        abort_pending_gemini_queue,
                    )
                    arm_gemini_quota_circuit(str(exc)[:300], kind='rpm')
                    abort_info = abort_pending_gemini_queue(
                        str(exc)[:300],
                        exclude_entreprise_id=eid,
                    )
                    report['queue_aborted_ids'] = abort_info.get('aborted_ids') or []
                except Exception as circ_exc:
                    logger.debug('abort file apres quota ignore: %s', circ_exc)
    elif circuit_open:
        _emit(circuit_msg or 'Quota Gemini epuise — fallback heuristique (file skip)', 70)
        report = _heuristic_full_report(
            pipeline,
            opportunity,
            fallback_reason=circuit_msg or 'circuit quota ouvert',
        )
        report['quota_exceeded'] = True
        report['fallback_error'] = (circuit_msg or 'circuit quota ouvert')[:300]
        report['circuit_skipped'] = True
    else:
        _emit('Pas de cle Gemini — fallback heuristique local…', 70)
        report = _heuristic_full_report(
            pipeline,
            opportunity,
            fallback_reason='pas de cle API',
        )

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
        'quota_exceeded': bool((report or {}).get('quota_exceeded')),
        'fallback_error': (report or {}).get('fallback_error'),
        'queue_aborted_ids': list((report or {}).get('queue_aborted_ids') or []),
        'circuit_skipped': bool((report or {}).get('circuit_skipped')),
        'screenshot_set_id': screenshot_set_id,
        'screenshots_ensured': screenshots_ensured,
        'modules_used': modules_used,
        'analyzed_at': analyzed_at,
    }
