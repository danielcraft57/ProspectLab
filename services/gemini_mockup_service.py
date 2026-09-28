# -*- coding: utf-8 -*-
"""
Generation de maquettes visuelles Gemini a partir d'un rapport d'audit.

Produit 2 images (desktop 16:9 + mobile 9:16) illustrant un site refondu
selon les ameliorations du rapport.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

MOCKUP_SYSTEM = (
    "Tu generes une maquette UI realiste d'un site vitrine PME modernise. "
    "Style Material Design 3, propre, professionnel, lisible. "
    "Pas de texte illegible, pas de watermark, pas de logo invente trop complexe. "
    "Montre clairement : header, hero, CTA, sections confiance, footer. "
    "Applique les corrections demandees (HTTPS, UX, SEO visible, design moderne)."
)


def _static_root() -> Path:
    """Racine static du projet."""
    return Path(__file__).resolve().parent.parent / 'static'


def _mockup_dir(entreprise_id: int, stamp: str) -> Path:
    """
    Dossier de sortie pour une generation.

    @param entreprise_id: ID entreprise
    @param stamp: Horodatage fichier
    @returns: Path absolu
    """
    return _static_root() / 'generated' / 'gemini_mockups' / str(int(entreprise_id)) / stamp


def build_mockup_prompt(
    *,
    entreprise: dict,
    report: dict,
    device: str,
) -> str:
    """
    Construit le prompt image a partir du rapport.

    @param entreprise: Dict entreprise
    @param report: Rapport Gemini
    @param device: desktop|mobile
    @returns: Prompt texte
    """
    nom = str(entreprise.get('nom') or 'Entreprise').strip()
    website = str(entreprise.get('website') or '').strip()
    secteur = str(entreprise.get('secteur') or entreprise.get('categorie') or '').strip()
    wrongs = report.get('whats_wrong') or []
    actions = report.get('priority_actions') or []
    improvements = report.get('improvements') or []
    design = report.get('design_analysis') if isinstance(report.get('design_analysis'), dict) else {}
    redo = design.get('to_redo') or []
    pitch = str(report.get('commercial_pitch') or '').strip()

    lines = [
        f"Maquette UI {device} d'un nouveau site pour « {nom} »",
        f"Secteur : {secteur or 'PME / services'}.",
    ]
    if website:
        lines.append(f"Site actuel de reference : {website}.")
    lines.append(
        "Objectif : visualiser le site APRES refonte, avec les corrections du rapport."
    )
    if wrongs:
        lines.append('Problemes a corriger visuellement :')
        for w in wrongs[:6]:
            lines.append(f'- {w}')
    if actions:
        lines.append('Actions prioritaires a refleter :')
        for a in actions[:5]:
            lines.append(f'- {a}')
    if improvements:
        lines.append('Ameliorations :')
        for it in improvements[:6]:
            if isinstance(it, dict):
                area = it.get('area') or ''
                action = it.get('action') or ''
                lines.append(f'- [{area}] {action}')
            else:
                lines.append(f'- {it}')
    if redo:
        lines.append('A refaire cote design :')
        for r in redo[:5]:
            lines.append(f'- {r}')
    if pitch:
        lines.append(f'Ton commercial : {pitch[:240]}')
    if device == 'mobile':
        lines.append(
            'Composition smartphone portrait (9:16), navigation mobile claire, '
            'gros CTA, typo lisible.'
        )
    else:
        lines.append(
            'Composition desktop large (16:9), hero edge-to-edge, grille propre, '
            'hierarchie visuelle nette.'
        )
    lines.append('Rendu photorealiste d\'interface web, pas de wireframe gris.')
    return '\n'.join(lines)


def generate_mockups_for_entreprise(
    *,
    database,
    entreprise_id: int,
    progress_cb: Optional[Callable[[str, int], None]] = None,
) -> Dict[str, Any]:
    """
    Genere et persiste des maquettes Gemini pour une entreprise (rapport requis).

    @param database: Instance Database
    @param entreprise_id: ID entreprise
    @param progress_cb: Callback (message, pct)
    @returns: Dict success / mockups / error
    """
    def _emit(msg: str, pct: int) -> None:
        if progress_cb:
            try:
                progress_cb(msg, int(pct))
            except Exception:
                pass

    eid = int(entreprise_id)
    entreprise = database.get_entreprise(eid) or {}
    if not entreprise:
        return {'success': False, 'error': 'Entreprise introuvable', 'entreprise_id': eid}

    latest = database.get_latest_entreprise_gemini_report(eid)
    if not latest or not latest.get('report'):
        return {
            'success': False,
            'error': 'Rapport Gemini requis avant de generer des maquettes',
            'entreprise_id': eid,
        }
    if str(latest.get('status') or '').lower() not in ('done', 'ok', ''):
        return {
            'success': False,
            'error': 'Le rapport Gemini n\'est pas pret',
            'entreprise_id': eid,
        }

    report = latest.get('report') or {}
    report_id = latest.get('id')
    _emit('Preparation des prompts maquettes…', 10)

    from services.gemini_client import gemini_generate_images, GeminiClientError

    # Screenshots existants en reference (si dispo)
    refs: List[Dict[str, Any]] = []
    try:
        from services.gemini_full_report_service import _load_screenshot_images
        if hasattr(database, 'get_latest_entreprise_screenshots'):
            shot_row = database.get_latest_entreprise_screenshots(eid)
            if shot_row:
                refs = _load_screenshot_images(shot_row, max_images=1)
    except Exception as exc:
        logger.debug('Refs screenshots mockups ignorees: %s', exc)

    stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    out_dir = _mockup_dir(eid, stamp)
    out_dir.mkdir(parents=True, exist_ok=True)

    devices = (
        ('desktop', '16:9', 35),
        ('mobile', '9:16', 70),
    )
    saved: List[Dict[str, Any]] = []
    errors: List[str] = []

    for device, ratio, pct in devices:
        _emit(f'Generation maquette {device}…', pct)
        prompt = build_mockup_prompt(entreprise=entreprise, report=report, device=device)
        try:
            images = gemini_generate_images(
                prompt=prompt,
                system_instruction=MOCKUP_SYSTEM,
                aspect_ratio=ratio,
                reference_images=refs[:1] if refs else None,
                timeout_ms=120_000,
            )
        except GeminiClientError as exc:
            errors.append(f'{device}: {exc}')
            logger.warning('Mockup %s echec: %s', device, exc)
            continue
        except Exception as exc:
            errors.append(f'{device}: {exc}')
            logger.exception('Mockup %s erreur', device)
            continue

        if not images:
            errors.append(f'{device}: aucune image')
            continue

        img = images[0]
        mime = str(img.get('mime_type') or 'image/png')
        ext = '.png'
        if 'jpeg' in mime or 'jpg' in mime:
            ext = '.jpg'
        elif 'webp' in mime:
            ext = '.webp'
        fname = f'{device}{ext}'
        fpath = out_dir / fname
        fpath.write_bytes(img['bytes'])
        rel = f'/static/generated/gemini_mockups/{eid}/{stamp}/{fname}'
        row_id = database.save_entreprise_gemini_mockup(
            entreprise_id=eid,
            report_id=int(report_id) if report_id else None,
            device=device,
            file_path=str(fpath),
            public_url=rel,
            prompt_summary=prompt[:500],
            status='done',
        )
        saved.append({
            'id': row_id,
            'device': device,
            'public_url': rel,
            'mime_type': mime,
        })
        _emit(f'Maquette {device} enregistree', min(95, pct + 10))

    if not saved:
        from services.gemini_client import is_gemini_quota_error
        joined = '; '.join(errors) or 'Generation echouee'
        return {
            'success': False,
            'error': joined,
            'entreprise_id': eid,
            'errors': errors,
            'quota_exceeded': is_gemini_quota_error(joined),
        }
    _emit('Maquettes pretes', 100)
    return {
        'success': True,
        'entreprise_id': eid,
        'report_id': report_id,
        'mockups': saved,
        'errors': errors,
        'stamp': stamp,
    }
