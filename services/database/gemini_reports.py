# -*- coding: utf-8 -*-
"""
Rapports Gemini normalises (tables + variables email).

Responsabilites :
- persistance denormalisee (colonnes scalaires + items enfants FK)
- reconstruction du rapport pour l'UI
- bundle de variables pour les modeles d'email
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple


# Kinds stockes dans entreprise_gemini_report_items.kind
GEMINI_ITEM_KINDS = (
    'what_works',
    'whats_wrong',
    'priority_action',
    'improvement',
    'to_keep',
    'to_redo',
)

# Colonnes scalaires ajoutees sur entreprise_gemini_reports
GEMINI_SCALAR_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ('executive_summary', 'TEXT'),
    ('report_document', 'TEXT'),
    ('commercial_pitch', 'TEXT'),
    ('design_score', 'INTEGER'),
    ('design_summary', 'TEXT'),
    ('design_ux_notes', 'TEXT'),
    ('design_ui_notes', 'TEXT'),
    ('score_design', 'INTEGER'),
    ('score_technical', 'INTEGER'),
    ('score_seo', 'INTEGER'),
    ('score_osint', 'INTEGER'),
    ('score_pentest', 'INTEGER'),
    ('notes_design', 'TEXT'),
    ('notes_technical', 'TEXT'),
    ('notes_seo', 'TEXT'),
    ('notes_osint', 'TEXT'),
    ('notes_pentest', 'TEXT'),
)


def _slugify_section(title: str) -> str:
    """
    Transforme un titre Markdown en cle variable email.

    @param title: Titre de section
    @returns: Slug ASCII snake_case
    """
    raw = unicodedata.normalize('NFKD', str(title or ''))
    ascii_txt = ''.join(ch for ch in raw if not unicodedata.combining(ch))
    ascii_txt = ascii_txt.lower()
    ascii_txt = re.sub(r'[^a-z0-9]+', '_', ascii_txt).strip('_')
    return ascii_txt[:48] or 'section'


def extract_markdown_sections(md: str, *, max_sections: int = 16) -> Dict[str, str]:
    """
    Decoupe un document Markdown en sections (titres # / ## / ###).

    @param md: Texte Markdown
    @param max_sections: Nombre max de sections conservees
    @returns: Dict slug -> contenu texte (sans le titre)
    """
    text = str(md or '').replace('\r\n', '\n').strip()
    if not text:
        return {}
    sections: Dict[str, str] = {}
    current_key: Optional[str] = None
    buf: List[str] = []
    used: Dict[str, int] = {}

    def flush() -> None:
        nonlocal current_key, buf
        if not current_key:
            buf = []
            return
        body = '\n'.join(buf).strip()
        if body and current_key not in sections:
            sections[current_key] = body[:4000]
        buf = []

    for line in text.split('\n'):
        m = re.match(r'^(#{1,3})\s+(.+)$', line.strip())
        if m:
            flush()
            if len(sections) >= max_sections:
                current_key = None
                continue
            base = _slugify_section(m.group(2))
            n = used.get(base, 0) + 1
            used[base] = n
            current_key = base if n == 1 else f'{base}_{n}'
            continue
        if current_key is not None:
            buf.append(line)
    flush()
    return sections


def _as_str_list(value: Any, *, limit: int = 12) -> List[str]:
    """
    Normalise une valeur en liste de strings.

    @param value: Liste ou string
    @param limit: Taille max
    @returns: Liste de strings
    """
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()][:limit]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _score_or_none(value: Any) -> Optional[int]:
    """
    Cast un score 0-100, sinon None.

    @param value: Valeur brute
    @returns: Int ou None
    """
    if value is None or value == '':
        return None
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return None


def flatten_report_for_storage(report: Optional[dict]) -> Dict[str, Any]:
    """
    Extrait les colonnes scalaires + items a partir du dict rapport.

    @param report: Rapport normalise Gemini
    @returns: Dict {scalars, items}
    """
    r = report if isinstance(report, dict) else {}
    design = r.get('design_analysis') if isinstance(r.get('design_analysis'), dict) else {}
    modules = r.get('modules') if isinstance(r.get('modules'), dict) else {}

    def _mod_score(key: str) -> Optional[int]:
        block = modules.get(key) if isinstance(modules.get(key), dict) else {}
        return _score_or_none(block.get('score'))

    def _mod_notes(key: str) -> str:
        block = modules.get(key) if isinstance(modules.get(key), dict) else {}
        return str(block.get('notes') or '').strip()[:800]

    scalars = {
        'executive_summary': str(r.get('executive_summary') or '').strip()[:4000],
        'report_document': str(r.get('report_document') or '').strip()[:50000],
        'commercial_pitch': str(r.get('commercial_pitch') or '').strip()[:2000],
        'design_score': _score_or_none(design.get('score')),
        'design_summary': str(design.get('summary') or '').strip()[:2000],
        'design_ux_notes': str(design.get('ux_notes') or '').strip()[:2000],
        'design_ui_notes': str(design.get('ui_notes') or '').strip()[:2000],
        'score_design': _mod_score('design') if _mod_score('design') is not None else _score_or_none(design.get('score')),
        'score_technical': _mod_score('technical'),
        'score_seo': _mod_score('seo'),
        'score_osint': _mod_score('osint'),
        'score_pentest': _mod_score('pentest'),
        'notes_design': _mod_notes('design') or str(design.get('summary') or '').strip()[:800],
        'notes_technical': _mod_notes('technical'),
        'notes_seo': _mod_notes('seo'),
        'notes_osint': _mod_notes('osint'),
        'notes_pentest': _mod_notes('pentest'),
    }

    items: List[Dict[str, Any]] = []

    def _push(kind: str, texts: List[str], *, area: str = '', priority: str = '') -> None:
        for i, txt in enumerate(texts):
            items.append({
                'kind': kind,
                'position': i,
                'text_content': str(txt).strip()[:1200],
                'area': (area or '')[:40] or None,
                'priority': (priority or '')[:20] or None,
            })

    _push('what_works', _as_str_list(r.get('what_works')))
    _push('whats_wrong', _as_str_list(r.get('whats_wrong')))
    _push('priority_action', _as_str_list(r.get('priority_actions')))
    _push('to_keep', _as_str_list(design.get('to_keep')))
    _push('to_redo', _as_str_list(design.get('to_redo')))

    for i, imp in enumerate(r.get('improvements') or []):
        if not isinstance(imp, dict):
            if isinstance(imp, str) and imp.strip():
                items.append({
                    'kind': 'improvement',
                    'position': i,
                    'text_content': imp.strip()[:1200],
                    'area': 'technique',
                    'priority': 'moyenne',
                })
            continue
        action = str(imp.get('action') or imp.get('text') or '').strip()
        if not action:
            continue
        items.append({
            'kind': 'improvement',
            'position': i,
            'text_content': action[:1200],
            'area': str(imp.get('area') or 'technique').strip()[:40] or None,
            'priority': str(imp.get('priority') or 'moyenne').strip()[:20] or None,
        })

    return {'scalars': scalars, 'items': items}


def rebuild_report_from_normalized(row: dict, items: List[dict]) -> dict:
    """
    Reconstruit un dict rapport a partir des colonnes + items.

    @param row: Ligne entreprise_gemini_reports
    @param items: Lignes enfant
    @returns: Dict rapport compatible UI
    """
    by_kind: Dict[str, List[dict]] = {k: [] for k in GEMINI_ITEM_KINDS}
    for it in items or []:
        kind = str(it.get('kind') or '')
        if kind in by_kind:
            by_kind[kind].append(it)
    for kind in by_kind:
        by_kind[kind].sort(key=lambda x: int(x.get('position') or 0))

    modules: Dict[str, Any] = {}
    for key in ('design', 'technical', 'seo', 'osint', 'pentest'):
        sc = row.get(f'score_{key}')
        notes = row.get(f'notes_{key}')
        if sc is not None or notes:
            modules[key] = {
                'score': sc,
                'notes': notes or '',
            }

    design_analysis = {}
    if any(row.get(k) for k in ('design_score', 'design_summary', 'design_ux_notes', 'design_ui_notes')) or by_kind['to_keep'] or by_kind['to_redo']:
        design_analysis = {
            'score': row.get('design_score'),
            'summary': row.get('design_summary') or '',
            'ux_notes': row.get('design_ux_notes') or '',
            'ui_notes': row.get('design_ui_notes') or '',
            'to_keep': [x.get('text_content') for x in by_kind['to_keep'] if x.get('text_content')],
            'to_redo': [x.get('text_content') for x in by_kind['to_redo'] if x.get('text_content')],
        }

    improvements = []
    for it in by_kind['improvement']:
        improvements.append({
            'area': it.get('area') or 'technique',
            'priority': it.get('priority') or 'moyenne',
            'action': it.get('text_content') or '',
        })

    return {
        'overall_score': row.get('overall_score'),
        'refonte_recommendation': row.get('refonte_recommendation'),
        'executive_summary': row.get('executive_summary') or '',
        'report_document': row.get('report_document') or '',
        'commercial_pitch': row.get('commercial_pitch') or '',
        'design_analysis': design_analysis,
        'what_works': [x.get('text_content') for x in by_kind['what_works'] if x.get('text_content')],
        'whats_wrong': [x.get('text_content') for x in by_kind['whats_wrong'] if x.get('text_content')],
        'priority_actions': [x.get('text_content') for x in by_kind['priority_action'] if x.get('text_content')],
        'improvements': improvements,
        'modules': modules,
        'source': row.get('source'),
    }


def build_gemini_email_variables(latest: Optional[dict]) -> Dict[str, Any]:
    """
    Construit le dict de variables email a partir d'un rapport latest.

    @param latest: Resultat get_latest_entreprise_gemini_report
    @returns: Variables plates pour template_manager
    """
    out: Dict[str, Any] = {
        'gemini': False,
        'gemini_has_report': False,
        'gemini_score': '',
        'gemini_refonte': '',
        'gemini_source': '',
        'gemini_summary': '',
        'gemini_pitch': '',
        'gemini_design_score': '',
        'gemini_design_summary': '',
        'gemini_analyzed_at': '',
        'gemini_problems_html': '',
        'gemini_actions_html': '',
        'gemini_works_html': '',
        'gemini_improvements_html': '',
        'gemini_problem_1': '',
        'gemini_problem_2': '',
        'gemini_problem_3': '',
        'gemini_action_1': '',
        'gemini_action_2': '',
        'gemini_action_3': '',
        'gemini_works_1': '',
        'gemini_works_2': '',
        'gemini_works_3': '',
    }
    for key in ('design', 'technical', 'seo', 'osint', 'pentest'):
        out[f'gemini_score_{key}'] = ''
        out[f'gemini_notes_{key}'] = ''

    if not latest or str(latest.get('status') or '').lower() not in ('done', 'ok', ''):
        # Accepte aussi status done uniquement pour "has"
        pass
    if not latest:
        return out

    report = latest.get('report') if isinstance(latest.get('report'), dict) else {}
    status = str(latest.get('status') or '').lower()
    if status and status not in ('done', 'ok'):
        return out

    score = latest.get('overall_score')
    if score is None:
        score = report.get('overall_score')
    out['gemini'] = True
    out['gemini_has_report'] = True
    out['gemini_score'] = '' if score is None else str(score)
    out['gemini_refonte'] = str(
        latest.get('refonte_recommendation') or report.get('refonte_recommendation') or ''
    ).strip()
    out['gemini_source'] = str(latest.get('source') or report.get('source') or '').strip()
    out['gemini_summary'] = str(
        latest.get('executive_summary') or report.get('executive_summary') or ''
    ).strip()
    out['gemini_pitch'] = str(
        latest.get('commercial_pitch') or report.get('commercial_pitch') or ''
    ).strip()
    out['gemini_analyzed_at'] = str(latest.get('analyzed_at') or '')[:19]

    design = report.get('design_analysis') if isinstance(report.get('design_analysis'), dict) else {}
    d_score = latest.get('design_score')
    if d_score is None:
        d_score = design.get('score')
    out['gemini_design_score'] = '' if d_score is None else str(d_score)
    out['gemini_design_summary'] = str(
        latest.get('design_summary') or design.get('summary') or ''
    ).strip()

    modules = report.get('modules') if isinstance(report.get('modules'), dict) else {}
    for key in ('design', 'technical', 'seo', 'osint', 'pentest'):
        sc = latest.get(f'score_{key}')
        notes = latest.get(f'notes_{key}')
        block = modules.get(key) if isinstance(modules.get(key), dict) else {}
        if sc is None:
            sc = block.get('score')
        if not notes:
            notes = block.get('notes')
        out[f'gemini_score_{key}'] = '' if sc is None else str(sc)
        out[f'gemini_notes_{key}'] = str(notes or '').strip()

    wrongs = _as_str_list(report.get('whats_wrong'), limit=8)
    works = _as_str_list(report.get('what_works'), limit=8)
    actions = _as_str_list(report.get('priority_actions'), limit=8)
    improvements = report.get('improvements') if isinstance(report.get('improvements'), list) else []

    for i in range(5):
        out[f'gemini_problem_{i + 1}'] = wrongs[i] if i < len(wrongs) else ''
        out[f'gemini_action_{i + 1}'] = actions[i] if i < len(actions) else ''
        out[f'gemini_works_{i + 1}'] = works[i] if i < len(works) else ''
        imp_txt = ''
        if i < len(improvements) and isinstance(improvements[i], dict):
            area = improvements[i].get('area') or ''
            prio = improvements[i].get('priority') or ''
            action = improvements[i].get('action') or ''
            bits = [b for b in (area, prio, action) if b]
            imp_txt = ' - '.join(bits) if bits else ''
        elif i < len(improvements):
            imp_txt = str(improvements[i] or '')
        out[f'gemini_improvement_{i + 1}'] = imp_txt

    if wrongs:
        out['gemini_problems_html'] = '<ul>' + ''.join(f'<li>{_escape_html(w)}</li>' for w in wrongs[:5]) + '</ul>'
    if actions:
        out['gemini_actions_html'] = '<ol>' + ''.join(f'<li>{_escape_html(a)}</li>' for a in actions[:5]) + '</ol>'
    if works:
        out['gemini_works_html'] = '<ul>' + ''.join(f'<li>{_escape_html(w)}</li>' for w in works[:5]) + '</ul>'
    if improvements:
        lis = []
        for imp in improvements[:5]:
            if isinstance(imp, dict):
                action = str(imp.get('action') or '').strip()
                if action:
                    lis.append(f'<li>{_escape_html(action)}</li>')
            elif str(imp).strip():
                lis.append(f'<li>{_escape_html(str(imp))}</li>')
        if lis:
            out['gemini_improvements_html'] = '<ul>' + ''.join(lis) + '</ul>'

    doc = str(latest.get('report_document') or report.get('report_document') or '').strip()
    if doc:
        sections = extract_markdown_sections(doc)
        for slug, body in sections.items():
            # Premiere phrase / extrait court pour email
            short = re.split(r'\n\n+', body.strip())[0].strip()[:700]
            out[f'gemini_doc_{slug}'] = short
            out[f'gemini_doc_{slug}_full'] = body[:2500]
        # Intro = premier paragraphe hors titre
        first_para = ''
        for line in doc.split('\n'):
            t = line.strip()
            if not t or t.startswith('#'):
                continue
            if t.startswith('-') or re.match(r'^\d+[.)]\s', t):
                continue
            first_para = t
            break
        out['gemini_doc_intro'] = first_para[:700]

    return out


def _escape_html(txt: str) -> str:
    """
    Echappe le HTML pour insertions dans listes email.

    @param txt: Texte brut
    @returns: Texte echappe
    """
    return (
        str(txt or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


class GeminiReportManager:
    """
    Mixin : CRUD rapports Gemini normalises + variables email.

    Depend de DatabaseBase (execute_sql, get_connection, is_postgresql, clean_row_dict).
    """

    def save_entreprise_gemini_report(
        self,
        *,
        entreprise_id: int,
        report: dict | None = None,
        overall_score: int | None = None,
        refonte_recommendation: str | None = None,
        source: str | None = None,
        status: str = 'done',
        error_message: str | None = None,
        modules_used: dict | None = None,
        screenshot_set_id: int | None = None,
        analyzed_at: str | None = None,
    ) -> int:
        """
        Persiste un rapport Gemini (JSON + colonnes + items enfants).

        @param entreprise_id: ID entreprise
        @param report: Dict rapport
        @param overall_score: Score 0-100
        @param refonte_recommendation: aucune|legere|partielle|totale
        @param source: gemini|heuristic
        @param status: done|failed|pending
        @param error_message: Message d'erreur optionnel
        @param modules_used: Dict modules utilises
        @param screenshot_set_id: ID set screenshots
        @param analyzed_at: Timestamp
        @returns: ID de la ligne creee
        """
        flat = flatten_report_for_storage(report)
        scalars = flat['scalars']
        items = flat['items']

        conn = self.get_connection()
        cursor = conn.cursor()
        score = _score_or_none(overall_score)
        if score is None and isinstance(report, dict):
            score = _score_or_none(report.get('overall_score'))

        report_json = None
        if report is not None:
            try:
                report_json = json.dumps(report, ensure_ascii=False, default=str)
            except Exception:
                report_json = None
        modules_json = None
        if modules_used is not None:
            try:
                modules_json = json.dumps(modules_used, ensure_ascii=False, default=str)
            except Exception:
                modules_json = None

        cols = [
            'entreprise_id', 'status', 'report_json', 'overall_score', 'refonte_recommendation',
            'source', 'error_message', 'modules_used_json', 'screenshot_set_id', 'analyzed_at',
            'executive_summary', 'report_document', 'commercial_pitch',
            'design_score', 'design_summary', 'design_ux_notes', 'design_ui_notes',
            'score_design', 'score_technical', 'score_seo', 'score_osint', 'score_pentest',
            'notes_design', 'notes_technical', 'notes_seo', 'notes_osint', 'notes_pentest',
        ]
        values = [
            int(entreprise_id),
            (str(status).strip()[:40] if status else 'done'),
            report_json,
            score,
            (str(refonte_recommendation).strip()[:40] if refonte_recommendation else None),
            (str(source).strip()[:40] if source else None),
            (str(error_message).strip()[:2000] if error_message else None),
            modules_json,
            int(screenshot_set_id) if screenshot_set_id else None,
            analyzed_at,
            scalars.get('executive_summary') or None,
            scalars.get('report_document') or None,
            scalars.get('commercial_pitch') or None,
            scalars.get('design_score'),
            scalars.get('design_summary') or None,
            scalars.get('design_ux_notes') or None,
            scalars.get('design_ui_notes') or None,
            scalars.get('score_design'),
            scalars.get('score_technical'),
            scalars.get('score_seo'),
            scalars.get('score_osint'),
            scalars.get('score_pentest'),
            scalars.get('notes_design') or None,
            scalars.get('notes_technical') or None,
            scalars.get('notes_seo') or None,
            scalars.get('notes_osint') or None,
            scalars.get('notes_pentest') or None,
        ]

        placeholders = ', '.join(['?'] * len(cols))
        # analyzed_at : COALESCE cote SQL
        set_cols = []
        set_vals = []
        for c, v in zip(cols, values):
            if c == 'analyzed_at':
                set_cols.append('analyzed_at')
                set_vals.append(v)
            else:
                set_cols.append(c)
                set_vals.append(v)

        col_sql = ', '.join(set_cols)
        # Rebuild placeholders with COALESCE for analyzed_at
        ph_parts = []
        for c in set_cols:
            if c == 'analyzed_at':
                ph_parts.append('COALESCE(?, CURRENT_TIMESTAMP)')
            else:
                ph_parts.append('?')
        ph_sql = ', '.join(ph_parts)

        if self.is_postgresql():
            cursor.execute(
                f'''
                INSERT INTO entreprise_gemini_reports ({col_sql})
                VALUES ({ph_sql.replace('?', '%s')})
                RETURNING id
                ''',
                tuple(set_vals),
            )
            row = cursor.fetchone()
            if not row:
                rid = 0
            elif isinstance(row, dict):
                rid = row.get('id') or 0
            else:
                rid = row[0] or 0
        else:
            self.execute_sql(
                cursor,
                f'''
                INSERT INTO entreprise_gemini_reports ({col_sql})
                VALUES ({ph_sql})
                ''',
                tuple(set_vals),
            )
            rid = cursor.lastrowid

        rid = int(rid or 0)
        if rid and items:
            for it in items:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO entreprise_gemini_report_items (
                        report_id, kind, position, text_content, area, priority
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        rid,
                        it.get('kind'),
                        int(it.get('position') or 0),
                        it.get('text_content'),
                        it.get('area'),
                        it.get('priority'),
                    ),
                )

        conn.commit()
        conn.close()
        try:
            if str(status or 'done').strip().lower() == 'done':
                self.refresh_has_gemini_report(int(entreprise_id))
        except Exception:
            pass
        return rid

    def _fetch_gemini_report_items(self, report_id: int, conn=None) -> List[dict]:
        """
        Charge les items enfants d'un rapport.

        @param report_id: ID rapport
        @param conn: Connexion optionnelle (sinon ouvre/ferme)
        @returns: Liste de dicts
        """
        own = conn is None
        if own:
            conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(
            cursor,
            '''
            SELECT id, report_id, kind, position, text_content, area, priority
            FROM entreprise_gemini_report_items
            WHERE report_id = ?
            ORDER BY kind ASC, position ASC, id ASC
            ''',
            (int(report_id),),
        )
        rows = cursor.fetchall() or []
        if own:
            conn.close()
        return [self.clean_row_dict(dict(r)) for r in rows]

    def _hydrate_gemini_report_row(self, row: dict, *, include_report_json: bool = True) -> dict:
        """
        Parse une ligne rapport + items -> dict API.

        @param row: Ligne brute
        @param include_report_json: Inclure le JSON complet dans report
        @returns: Dict hydrate
        """
        d = self.clean_row_dict(dict(row))
        rid = int(d.get('id') or 0)
        items = self._fetch_gemini_report_items(rid) if rid else []
        raw = d.pop('report_json', None) if include_report_json else d.pop('report_json', None)
        report = None
        if include_report_json:
            if isinstance(raw, dict):
                report = raw
            elif isinstance(raw, str) and raw.strip():
                try:
                    parsed = json.loads(raw)
                    report = parsed if isinstance(parsed, dict) else None
                except Exception:
                    report = None
        rebuilt = rebuild_report_from_normalized(d, items)
        if report and isinstance(report, dict):
            # Preferer colonnes/items normalises quand presents
            for k, v in rebuilt.items():
                if v in (None, '', [], {}):
                    continue
                report[k] = v
        else:
            report = rebuilt
        d['report'] = report
        mods = d.pop('modules_used_json', None)
        if isinstance(mods, str) and mods.strip():
            try:
                d['modules_used'] = json.loads(mods)
            except Exception:
                d['modules_used'] = None
        elif isinstance(mods, dict):
            d['modules_used'] = mods
        else:
            d['modules_used'] = None
        d['items'] = items
        return d

    def get_latest_entreprise_gemini_report(self, entreprise_id: int) -> dict | None:
        """
        Retourne le dernier rapport Gemini d'une entreprise (normalise + JSON).

        @param entreprise_id: ID entreprise
        @returns: Dict ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(
            cursor,
            '''
            SELECT *
            FROM entreprise_gemini_reports
            WHERE entreprise_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            ''',
            (int(entreprise_id),),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._hydrate_gemini_report_row(dict(row), include_report_json=True)

    def list_entreprise_gemini_reports(
        self,
        entreprise_id: int,
        limit: int = 10,
        *,
        include_report_json: bool = True,
    ) -> list[dict]:
        """
        Historique des rapports Gemini (plus recent en premier).

        @param entreprise_id: ID entreprise
        @param limit: Nombre max
        @param include_report_json: Si False, omet le gros JSON (liste legere)
        @returns: Liste de dicts
        """
        lim = max(1, min(int(limit or 10), 50))
        conn = self.get_connection()
        cursor = conn.cursor()
        if include_report_json:
            self.execute_sql(
                cursor,
                '''
                SELECT *
                FROM entreprise_gemini_reports
                WHERE entreprise_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                ''',
                (int(entreprise_id), lim),
            )
        else:
            self.execute_sql(
                cursor,
                '''
                SELECT id, entreprise_id, status, overall_score, refonte_recommendation,
                       source, error_message, screenshot_set_id, analyzed_at,
                       created_at, updated_at, executive_summary, commercial_pitch,
                       design_score, score_design, score_technical, score_seo,
                       score_osint, score_pentest
                FROM entreprise_gemini_reports
                WHERE entreprise_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                ''',
                (int(entreprise_id), lim),
            )
        rows = cursor.fetchall() or []
        conn.close()
        out = []
        for r in rows:
            d = self._hydrate_gemini_report_row(dict(r), include_report_json=include_report_json)
            if not include_report_json and isinstance(d.get('report'), dict):
                # garder un resume leger
                rep = d['report']
                d['report'] = {
                    'overall_score': rep.get('overall_score'),
                    'refonte_recommendation': rep.get('refonte_recommendation'),
                    'executive_summary': (rep.get('executive_summary') or '')[:400],
                    'commercial_pitch': (rep.get('commercial_pitch') or '')[:300],
                }
            out.append(d)
        return out

    def get_entreprise_gemini_email_variables(self, entreprise_id: int) -> dict:
        """
        Variables Gemini pretes pour les modeles d'email.

        @param entreprise_id: ID entreprise
        @returns: Dict de placeholders (gemini_score, gemini_pitch, …)
        """
        latest = self.get_latest_entreprise_gemini_report(int(entreprise_id))
        return build_gemini_email_variables(latest)

    def backfill_gemini_reports_normalized(self, *, limit: int = 500) -> int:
        """
        Remplit colonnes/items depuis report_json pour les anciens rapports.

        @param limit: Nombre max de lignes a traiter
        @returns: Nombre de rapports mis a jour
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(
            cursor,
            '''
            SELECT id, report_json
            FROM entreprise_gemini_reports
            WHERE report_json IS NOT NULL
              AND (executive_summary IS NULL OR executive_summary = '')
            ORDER BY id DESC
            LIMIT ?
            ''',
            (max(1, min(int(limit or 500), 5000)),),
        )
        rows = cursor.fetchall() or []
        updated = 0
        for row in rows:
            d = self.clean_row_dict(dict(row))
            rid = int(d.get('id') or 0)
            raw = d.get('report_json')
            report = None
            if isinstance(raw, dict):
                report = raw
            elif isinstance(raw, str) and raw.strip():
                try:
                    parsed = json.loads(raw)
                    report = parsed if isinstance(parsed, dict) else None
                except Exception:
                    report = None
            if not report or not rid:
                continue
            flat = flatten_report_for_storage(report)
            sc = flat['scalars']
            self.execute_sql(
                cursor,
                '''
                UPDATE entreprise_gemini_reports SET
                    executive_summary = ?,
                    report_document = ?,
                    commercial_pitch = ?,
                    design_score = ?,
                    design_summary = ?,
                    design_ux_notes = ?,
                    design_ui_notes = ?,
                    score_design = ?,
                    score_technical = ?,
                    score_seo = ?,
                    score_osint = ?,
                    score_pentest = ?,
                    notes_design = ?,
                    notes_technical = ?,
                    notes_seo = ?,
                    notes_osint = ?,
                    notes_pentest = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    sc.get('executive_summary') or None,
                    sc.get('report_document') or None,
                    sc.get('commercial_pitch') or None,
                    sc.get('design_score'),
                    sc.get('design_summary') or None,
                    sc.get('design_ux_notes') or None,
                    sc.get('design_ui_notes') or None,
                    sc.get('score_design'),
                    sc.get('score_technical'),
                    sc.get('score_seo'),
                    sc.get('score_osint'),
                    sc.get('score_pentest'),
                    sc.get('notes_design') or None,
                    sc.get('notes_technical') or None,
                    sc.get('notes_seo') or None,
                    sc.get('notes_osint') or None,
                    sc.get('notes_pentest') or None,
                    rid,
                ),
            )
            self.execute_sql(
                cursor,
                'DELETE FROM entreprise_gemini_report_items WHERE report_id = ?',
                (rid,),
            )
            for it in flat['items']:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO entreprise_gemini_report_items (
                        report_id, kind, position, text_content, area, priority
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        rid,
                        it.get('kind'),
                        int(it.get('position') or 0),
                        it.get('text_content'),
                        it.get('area'),
                        it.get('priority'),
                    ),
                )
            updated += 1
        conn.commit()
        conn.close()
        return updated

    def save_entreprise_gemini_mockup(
        self,
        *,
        entreprise_id: int,
        report_id: int | None = None,
        device: str = 'desktop',
        file_path: str | None = None,
        public_url: str | None = None,
        prompt_summary: str | None = None,
        status: str = 'done',
        error_message: str | None = None,
    ) -> int:
        """
        Persiste une maquette Gemini generee.

        @param entreprise_id: ID entreprise
        @param report_id: ID rapport source (FK optionnelle)
        @param device: desktop|mobile|tablet
        @param file_path: Chemin disque
        @param public_url: URL publique /static/...
        @param prompt_summary: Extrait du prompt
        @param status: done|failed
        @param error_message: Erreur optionnelle
        @returns: ID cree
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        vals = (
            int(entreprise_id),
            int(report_id) if report_id else None,
            (str(device).strip()[:20] or 'desktop'),
            (str(file_path).strip()[:1000] if file_path else None),
            (str(public_url).strip()[:1000] if public_url else None),
            (str(prompt_summary).strip()[:2000] if prompt_summary else None),
            (str(status).strip()[:40] if status else 'done'),
            (str(error_message).strip()[:2000] if error_message else None),
        )
        if self.is_postgresql():
            cursor.execute(
                '''
                INSERT INTO entreprise_gemini_mockups (
                    entreprise_id, report_id, device, file_path, public_url,
                    prompt_summary, status, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                ''',
                vals,
            )
            row = cursor.fetchone()
            if not row:
                rid = 0
            elif isinstance(row, dict):
                rid = row.get('id') or 0
            else:
                rid = row[0] or 0
        else:
            self.execute_sql(
                cursor,
                '''
                INSERT INTO entreprise_gemini_mockups (
                    entreprise_id, report_id, device, file_path, public_url,
                    prompt_summary, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                vals,
            )
            rid = cursor.lastrowid
        conn.commit()
        conn.close()
        return int(rid or 0)

    def list_entreprise_gemini_mockups(
        self,
        entreprise_id: int,
        *,
        limit: int = 20,
    ) -> list[dict]:
        """
        Liste les maquettes Gemini d'une entreprise (plus recentes d'abord).

        @param entreprise_id: ID entreprise
        @param limit: Max lignes
        @returns: Liste de dicts
        """
        lim = max(1, min(int(limit or 20), 100))
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(
            cursor,
            '''
            SELECT id, entreprise_id, report_id, device, file_path, public_url,
                   prompt_summary, status, error_message, created_at
            FROM entreprise_gemini_mockups
            WHERE entreprise_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            ''',
            (int(entreprise_id), lim),
        )
        rows = cursor.fetchall() or []
        conn.close()
        return [self.clean_row_dict(dict(r)) for r in rows]

    def get_latest_entreprise_gemini_mockup_bundle(self, entreprise_id: int) -> dict:
        """
        Bundle des dernieres maquettes (par device) pour l'UI.

        @param entreprise_id: ID entreprise
        @returns: {items, by_device}
        """
        items = self.list_entreprise_gemini_mockups(int(entreprise_id), limit=12)
        by_device: dict = {}
        for it in items:
            device = str(it.get('device') or 'desktop')
            if device not in by_device and str(it.get('status') or '') == 'done':
                by_device[device] = it
        return {'items': items, 'by_device': by_device}
