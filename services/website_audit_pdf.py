"""
Génération PDF du rapport d'audit site (design enrichi, graphiques, narratif).
"""

from __future__ import annotations

import html
import shutil
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --- Palette moderne (teal / indigo / slate) ---
INK = colors.HexColor('#0f172a')
INK_SOFT = colors.HexColor('#334155')
TEAL = colors.HexColor('#0f766e')
TEAL_LIGHT = colors.HexColor('#ccfbf1')
TEAL_MID = colors.HexColor('#14b8a6')
INDIGO = colors.HexColor('#4f46e5')
INDIGO_LIGHT = colors.HexColor('#eef2ff')
AMBER = colors.HexColor('#d97706')
AMBER_LIGHT = colors.HexColor('#fffbeb')
SURFACE = colors.HexColor('#f8fafc')
SURFACE_CARD = colors.HexColor('#ffffff')
BORDER = colors.HexColor('#e2e8f0')
WHITE = colors.white
TEXT_MUTED = colors.HexColor('#64748b')

STATUS_COLORS = {
    'on_track': colors.HexColor('#059669'),
    'in_progress': colors.HexColor('#d97706'),
    'at_risk': colors.HexColor('#dc2626'),
    'unknown': colors.HexColor('#94a3b8'),
}
STATUS_LABELS = {
    'on_track': 'Conforme',
    'in_progress': 'À améliorer',
    'at_risk': 'À risque',
    'unknown': 'N/A',
}
STATUS_HEX = {
    'on_track': '#059669',
    'in_progress': '#d97706',
    'at_risk': '#dc2626',
    'unknown': '#94a3b8',
}

CHART_COLORS = ['#0f766e', '#4f46e5', '#0891b2', '#d97706', '#64748b']
CHART_BG = '#f8fafc'

# Hauteur max utile d'une frame A4 (marges incluses) ~ 27 cm ; on laisse de la marge pour titres.
_MAX_SCREENSHOT_HEIGHT_DESKTOP = 20 * cm
_MAX_SCREENSHOT_HEIGHT_DEVICE = 9 * cm


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _esc(text: str) -> str:
    return html.escape(str(text or ''), quote=False)


def _chart_scores_donut(scores: Dict[str, Optional[float]], out_path: Path) -> bool:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    labels: List[str] = []
    values: List[float] = []
    for label, key in (
        ('SEO', 'seo'),
        ('Sécurité', 'security'),
        ('Performance', 'performance'),
        ('Risque pentest', 'pentest_risk'),
        ('Opportunité', 'opportunity'),
    ):
        v = scores.get(key)
        if v is None:
            continue
        if key == 'pentest_risk':
            v = max(0.0, 100.0 - float(v))
        labels.append(label)
        values.append(max(0.0, min(100.0, float(v))))

    if not values:
        return False

    fig, ax = plt.subplots(figsize=(5.4, 4.0), facecolor=CHART_BG)
    _texts, _ltexts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct='%1.0f',
        startangle=90,
        colors=CHART_COLORS[: len(values)],
        wedgeprops=dict(width=0.42, edgecolor='white', linewidth=2.5),
        textprops={'fontsize': 9, 'color': '#334155'},
    )
    for t in autotexts:
        t.set_color('white')
        t.set_fontweight('bold')
        t.set_fontsize(10)
    ax.set_title('Synthèse des scores', fontsize=13, fontweight='bold', color='#0f172a', pad=14)
    fig.tight_layout()
    fig.savefig(str(out_path), dpi=160, bbox_inches='tight', facecolor=CHART_BG)
    plt.close(fig)
    return True


def _chart_scores_bars(scores: Dict[str, Optional[float]], out_path: Path) -> bool:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    items = [
        ('SEO', scores.get('seo')),
        ('Sécurité', scores.get('security')),
        ('Performance', scores.get('performance')),
        ('Opportunité', scores.get('opportunity')),
    ]
    items = [(n, v) for n, v in items if v is not None]
    if not items:
        return False

    names = [x[0] for x in items]
    vals = [float(x[1]) for x in items]
    fig, ax = plt.subplots(figsize=(5.6, 3.4), facecolor=CHART_BG)
    y_pos = range(len(names))
    bars = ax.barh(list(y_pos), vals, color=CHART_COLORS[: len(vals)], height=0.5, edgecolor='white')
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(names, fontsize=10, color='#334155')
    ax.set_xlim(0, 100)
    ax.set_xlabel('Score / 100', fontsize=9, color='#64748b')
    ax.set_title('Comparatif des métriques', fontsize=12, fontweight='bold', color='#0f172a', pad=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.25, linestyle='--')
    for bar, val in zip(bars, vals):
        ax.text(
            min(val + 2, 96),
            bar.get_y() + bar.get_height() / 2,
            f'{int(val)}',
            va='center',
            fontsize=10,
            fontweight='bold',
            color='#0f172a',
        )
    fig.tight_layout()
    fig.savefig(str(out_path), dpi=160, bbox_inches='tight', facecolor=CHART_BG)
    plt.close(fig)
    return True


def _resolve_screenshot_path(file_path: Optional[str]) -> Optional[Path]:
    if not file_path:
        return None
    p = Path(file_path)
    if p.is_file():
        return p
    from config import APP_DIR

    for base in (APP_DIR, APP_DIR.parent):
        candidate = base / file_path
        if candidate.is_file():
            return candidate
        candidate = base / str(file_path).lstrip('/')
        if candidate.is_file():
            return candidate
    return None


def _image_from_path(path: Path, width: float, height: float) -> Image:
    data = path.read_bytes()
    return Image(BytesIO(data), width=width, height=height)


def _fit_pdf_image_size(
    display_width: float,
    aspect_ratio: float,
    *,
    max_display_height: Optional[float] = None,
) -> Tuple[float, float]:
    """Ajuste largeur/hauteur PDF pour tenir dans la page."""
    pdf_w = display_width
    pdf_h = display_width * aspect_ratio
    if max_display_height and pdf_h > max_display_height:
        scale = max_display_height / pdf_h
        pdf_h = max_display_height
        pdf_w = display_width * scale
    return pdf_w, pdf_h


def _styled_screenshot_image(
    path: Path,
    *,
    display_width: float,
    device_label: str,
    max_px_width: int = 1280,
    max_display_height: Optional[float] = None,
) -> Optional[Image]:
    """Cadre visuel (barre titre, ombre, coins) pour les captures dans le PDF."""
    try:
        from PIL import Image as PILImage
        from PIL import ImageDraw, ImageFilter, ImageFont
    except ImportError:
        h = display_width * 0.56
        if max_display_height:
            h = min(h, max_display_height)
        return _image_from_path(path, display_width, h)

    try:
        src = PILImage.open(path).convert('RGB')
    except Exception:
        return None

    w, h = src.size
    max_px_height = max_px_width * 2
    if max_display_height and display_width > 0:
        max_px_height = min(max_px_height, int(max_px_width * (max_display_height / display_width)))
    if h > max_px_height:
        src = src.resize((int(w * max_px_height / h), max_px_height), PILImage.Resampling.LANCZOS)
        w, h = src.size
    if w > max_px_width:
        ratio = max_px_width / float(w)
        src = src.resize((max_px_width, int(h * ratio)), PILImage.Resampling.LANCZOS)
        w, h = src.size

    header_h = 36
    pad = 20
    shadow = 10
    frame_w = w + pad * 2
    frame_h = h + pad * 2 + header_h

    canvas = PILImage.new('RGB', (frame_w + shadow, frame_h + shadow), (248, 250, 252))
    card = PILImage.new('RGB', (frame_w, frame_h), (255, 255, 255))
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, 0, frame_w - 1, header_h - 1], fill=(15, 118, 110))
    try:
        font = ImageFont.truetype('arial.ttf', 15)
    except Exception:
        font = ImageFont.load_default()
    draw.text((14, 10), device_label, fill=(255, 255, 255), font=font)
    card.paste(src, (pad, header_h + pad))
    draw.rectangle(
        [pad - 1, header_h + pad - 1, pad + w, header_h + pad + h],
        outline=(226, 232, 240),
        width=1,
    )
    shadow_layer = PILImage.new('RGBA', canvas.size, (0, 0, 0, 0))
    shadow_layer.paste((15, 23, 42, 28), (shadow + 4, shadow + 6, shadow + 4 + frame_w, shadow + 6 + frame_h))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    canvas.paste(shadow_layer, (0, 0), shadow_layer)
    canvas.paste(card, (shadow, shadow))

    buf = BytesIO()
    canvas.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    ratio = canvas.height / float(canvas.width)
    pdf_w, pdf_h = _fit_pdf_image_size(
        display_width,
        ratio,
        max_display_height=max_display_height,
    )
    return Image(buf, width=pdf_w, height=pdf_h)


class WebsiteAuditPdfGenerator:
    """Construit un PDF multi-sections à partir du contexte d'audit."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _styles(self) -> Dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()
        return {
            'title': ParagraphStyle(
                'AuditTitle',
                parent=base['Heading1'],
                fontSize=24,
                textColor=WHITE,
                alignment=TA_LEFT,
                spaceAfter=4,
                leading=28,
            ),
            'subtitle': ParagraphStyle(
                'AuditSub',
                parent=base['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#e2e8f0'),
                alignment=TA_LEFT,
                leading=15,
            ),
            'section': ParagraphStyle(
                'AuditSection',
                parent=base['Heading2'],
                fontSize=13,
                textColor=TEAL,
                spaceBefore=16,
                spaceAfter=10,
                fontName='Helvetica-Bold',
            ),
            'body': ParagraphStyle(
                'AuditBody',
                parent=base['Normal'],
                fontSize=10,
                textColor=INK_SOFT,
                leading=15,
                alignment=TA_JUSTIFY,
            ),
            'body_bold': ParagraphStyle(
                'AuditBodyBold',
                parent=base['Normal'],
                fontSize=10,
                textColor=INK,
                leading=15,
                fontName='Helvetica-Bold',
            ),
            'muted': ParagraphStyle(
                'AuditMuted',
                parent=base['Normal'],
                fontSize=8,
                textColor=TEXT_MUTED,
                leading=11,
            ),
            'kpi_value': ParagraphStyle(
                'KpiValue',
                parent=base['Normal'],
                fontSize=22,
                textColor=TEAL,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
            ),
            'kpi_label': ParagraphStyle(
                'KpiLabel',
                parent=base['Normal'],
                fontSize=8,
                textColor=TEXT_MUTED,
                alignment=TA_CENTER,
                leading=10,
            ),
            'bullet': ParagraphStyle(
                'AuditBullet',
                parent=base['Normal'],
                fontSize=9,
                textColor=INK_SOFT,
                leftIndent=14,
                bulletIndent=0,
                spaceBefore=3,
                leading=13,
            ),
        }

    def _section_header(self, title: str, st: Dict[str, ParagraphStyle]) -> Table:
        inner = Table(
            [[Paragraph(title, st['section'])]],
            colWidths=[16.4 * cm],
        )
        inner.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), SURFACE_CARD),
                    ('LEFTPADDING', (0, 0), (-1, -1), 14),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                    ('LINEBEFORE', (0, 0), (0, -1), 5, TEAL),
                ]
            )
        )
        return inner

    def _kpi_cards(self, scores: Dict[str, Optional[float]], st: Dict[str, ParagraphStyle]) -> Optional[Table]:
        items = [
            ('SEO', scores.get('seo'), TEAL),
            ('Sécurité', scores.get('security'), INDIGO),
            ('Perf.', scores.get('performance'), TEAL_MID),
            ('Pentest', scores.get('pentest_risk'), AMBER),
        ]
        cells = []
        col_w = 4.1 * cm
        for label, val, _c in items:
            if val is None:
                cells.append(
                    Paragraph(
                        f'<para align="center"><font size="8" color="#94a3b8">{_esc(label)}</font><br/>—</para>',
                        st['muted'],
                    )
                )
            else:
                display = int(val)
                if label == 'Pentest':
                    display = int(max(0, 100 - float(val)))
                cells.append(
                    [
                        Paragraph(str(display), st['kpi_value']),
                        Paragraph(label, st['kpi_label']),
                    ]
                )
        if not any(scores.get(k) is not None for k in ('seo', 'security', 'performance', 'pentest_risk')):
            return None

        row: List[Any] = []
        for cell in cells:
            if isinstance(cell, list):
                row.append(
                    Table(
                        [[cell[0]], [cell[1]]],
                        colWidths=[col_w - 0.2 * cm],
                    )
                )
            else:
                row.append(cell)

        while len(row) < 4:
            row.append(Paragraph('—', st['muted']))

        outer = Table([row], colWidths=[col_w] * 4, hAlign='CENTER')
        outer.setStyle(
            TableStyle(
                [
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('BACKGROUND', (0, 0), (-1, -1), INDIGO_LIGHT),
                    ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ]
            )
        )
        return outer

    def _append_narrative_block(
        self,
        story: List[Any],
        block: Dict[str, Any],
        st: Dict[str, ParagraphStyle],
    ) -> None:
        title = block.get('title') or ''
        if title:
            story.append(self._section_header(title, st))
            story.append(Spacer(1, 0.15 * cm))

        for para in block.get('paragraphs') or []:
            story.append(Paragraph(str(para), st['body']))
            story.append(Spacer(1, 0.12 * cm))

        bullets = block.get('bullets') or []
        if bullets:
            for b in bullets:
                story.append(Paragraph(f'• {_esc(b)}', st['bullet']))
            story.append(Spacer(1, 0.15 * cm))

    def _health_table(self, health_rows: List[Dict[str, str]], st: Dict[str, ParagraphStyle]) -> Table:
        data = [
            [
                Paragraph('<b>Domaine</b>', st['body_bold']),
                Paragraph('<b>Statut</b>', st['body_bold']),
                Paragraph('<b>Analyse</b>', st['body_bold']),
            ]
        ]
        for row in health_rows:
            status_key = row.get('status', 'unknown')
            hex_c = STATUS_HEX.get(status_key, STATUS_HEX['unknown'])
            label = STATUS_LABELS.get(status_key, 'N/A')
            status_cell = Paragraph(
                f'<font color="{hex_c}"><b>{label}</b></font>',
                ParagraphStyle('st', fontSize=9, alignment=TA_CENTER),
            )
            detail = row.get('detail', '')
            data.append([
                Paragraph(f'<b>{_esc(row.get("area", ""))}</b>', st['body']),
                status_cell,
                Paragraph(_esc(detail), st['body']),
            ])

        t = Table(data, colWidths=[4.8 * cm, 3.0 * cm, 9.2 * cm])
        t.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), TEAL),
                    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [SURFACE_CARD, SURFACE]),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ]
            )
        )
        return t

    def _detail_data_table(
        self,
        rows: List[List[str]],
        st: Dict[str, ParagraphStyle],
        *,
        col_widths: Optional[List[float]] = None,
    ) -> Table:
        data = [
            [
                Paragraph('<b>Indicateur</b>', st['body_bold']),
                Paragraph('<b>Valeur</b>', st['body_bold']),
            ]
        ]
        for row in rows:
            if len(row) < 2:
                continue
            data.append([
                Paragraph(_esc(str(row[0])), st['body']),
                Paragraph(_esc(str(row[1])), st['body']),
            ])
        widths = col_widths or [5.5 * cm, 11.8 * cm]
        t = Table(data, colWidths=widths)
        t.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), TEAL_LIGHT),
                    ('TEXTCOLOR', (0, 0), (-1, 0), TEAL),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.35, BORDER),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SURFACE]),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]
            )
        )
        return t

    def _append_detail_tables(
        self,
        story: List[Any],
        detail_tables: List[Dict[str, Any]],
        st: Dict[str, ParagraphStyle],
    ) -> None:
        if not detail_tables:
            return
        story.append(self._section_header('Données d\'analyse détaillées', st))
        story.append(Spacer(1, 0.12 * cm))
        story.append(
            Paragraph(
                'Tableaux issus des modules d\'analyse (scraping, technique, SEO, OSINT, pentest). '
                'Chaque ligne reprend une mesure ou un extrait enregistré lors du scan.',
                st['body'],
            )
        )
        story.append(Spacer(1, 0.18 * cm))
        for block in detail_tables:
            title = block.get('title') or ''
            rows = block.get('rows') or []
            if not rows:
                continue
            story.append(Paragraph(f'<b>{_esc(title)}</b>', st['body_bold']))
            story.append(Spacer(1, 0.08 * cm))
            story.append(self._detail_data_table(rows, st))
            story.append(Spacer(1, 0.22 * cm))

    def generate(
        self,
        context: Dict[str, Any],
        filename: Optional[str] = None,
        *,
        report_tier: Optional[str] = None,
    ) -> Path:
        tier = report_tier or context.get('report_tier') or 'full'
        if not filename:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            eid = context.get('entreprise_id', '0')
            slug = (context.get('website') or 'site').replace('https://', '').replace('http://', '').split('/')[0]
            slug = slug.replace(':', '_')[:40] or 'site'
            if tier == 'essential':
                filename = f'audit_essentiel_{eid}_{ts}.pdf'
            elif tier == 'complete_fallback':
                filename = f'audit_complet_local_{eid}_{ts}.pdf'
            else:
                filename = f'audit_site_{eid}_{ts}.pdf'
        out_path = self.output_dir / filename
        st = self._styles()
        is_essential = tier == 'essential'

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=A4,
            leftMargin=1.35 * cm,
            rightMargin=1.35 * cm,
            topMargin=1.1 * cm,
            bottomMargin=1.1 * cm,
        )
        story: List[Any] = []
        content_w = 17.3 * cm

        website = context.get('website') or ''
        company = context.get('company_name') or website
        secteur = context.get('secteur') or ''
        pipeline = context.get('pipeline') or {}
        opportunity = context.get('opportunity') or {}
        health_rows = context.get('health_rows') or []
        narrative_sections = context.get('narrative_sections') or []

        if tier == 'complete_fallback':
            story.append(
                Table(
                    [[Paragraph(
                        '<b>Rapport complet</b> — la synthèse experte n\'a pas pu être finalisée. '
                        'Ce document reprend les données mesurées en base.',
                        ParagraphStyle('Warn', parent=st['body'], textColor=colors.HexColor('#92400e'), fontSize=9),
                    )]],
                    colWidths=[content_w],
                )
            )
            story.append(Spacer(1, 0.25 * cm))

        hero_title = 'Audit essentiel' if is_essential else 'Rapport d\'audit digital'
        hero_tag = (
            'Version gratuite — synthèse & scores clés'
            if is_essential
            else 'Audit consolidé — technique, SEO, sécurité & visibilité'
        )
        hero = Table(
            [
                [Paragraph(hero_title, st['title'])],
                [
                    Paragraph(
                        f'<b>{_esc(company)}</b><br/>'
                        f'<font color="#94a3b8">{_esc(website)}</font>',
                        st['subtitle'],
                    )
                ],
                [
                    Paragraph(
                        hero_tag,
                        ParagraphStyle(
                            'Tag',
                            parent=st['subtitle'],
                            fontSize=9,
                            textColor=TEAL_LIGHT,
                        ),
                    )
                ],
            ],
            colWidths=[content_w],
        )
        hero.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), INK),
                    ('LEFTPADDING', (0, 0), (-1, -1), 20),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 20),
                    ('TOPPADDING', (0, 0), (-1, 0), 18),
                    ('BOTTOMPADDING', (0, -1), (-1, -1), 18),
                ]
            )
        )
        story.append(hero)

        opp_cell = '—'
        if opportunity.get('score') is not None:
            opp_cell = f'{opportunity.get("opportunity", "—")} · {int(opportunity["score"])}/100'

        meta = Table(
            [
                [
                    Paragraph(f'<b>Date</b><br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}', st['muted']),
                    Paragraph(f'<b>Secteur</b><br/>{_esc(secteur or "—")}', st['muted']),
                    Paragraph(f'<b>Opportunité</b><br/>{_esc(opp_cell)}', st['muted']),
                ]
            ],
            colWidths=[5.5 * cm, 5.5 * cm, 6.3 * cm],
        )
        meta.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), TEAL_LIGHT),
                    ('BOX', (0, 0), (-1, -1), 0.5, TEAL),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(meta)
        story.append(Spacer(1, 0.45 * cm))

        scores = self._extract_scores(context)
        kpi = self._kpi_cards(scores, st)
        if kpi:
            story.append(kpi)
            story.append(Spacer(1, 0.4 * cm))

        intro_blocks = [b for b in narrative_sections if b.get('id') == 'context']
        other_blocks = [b for b in narrative_sections if b.get('id') != 'context']
        for block in intro_blocks:
            self._append_narrative_block(story, block, st)
        story.append(Spacer(1, 0.2 * cm))

        if not is_essential:
            chart_tmp = Path(tempfile.mkdtemp(prefix='audit_charts_'))
            try:
                donut = chart_tmp / 'donut.png'
                bars = chart_tmp / 'bars.png'
                donut_ok = _chart_scores_donut(scores, donut)
                bars_ok = _chart_scores_bars(scores, bars)
                if donut_ok and bars_ok:
                    story.append(self._section_header('Vue d\'ensemble & indicateurs', st))
                    story.append(Spacer(1, 0.12 * cm))
                    row = [
                        _image_from_path(donut, 7.8 * cm, 5.8 * cm),
                        _image_from_path(bars, 7.8 * cm, 5.8 * cm),
                    ]
                    ct = Table([row], colWidths=[8.5 * cm, 8.5 * cm])
                    ct.setStyle(
                        TableStyle(
                            [
                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('BACKGROUND', (0, 0), (-1, -1), SURFACE),
                                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                                ('TOPPADDING', (0, 0), (-1, -1), 8),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                            ]
                        )
                    )
                    story.append(ct)
                    story.append(Spacer(1, 0.3 * cm))
                elif bars_ok:
                    story.append(self._section_header('Scores clés', st))
                    story.append(Spacer(1, 0.1 * cm))
                    story.append(_image_from_path(bars, 12.0 * cm, 5.5 * cm))
                    story.append(Spacer(1, 0.25 * cm))
            finally:
                shutil.rmtree(chart_tmp, ignore_errors=True)
        elif scores.get('seo') is not None or scores.get('security') is not None:
            chart_tmp = Path(tempfile.mkdtemp(prefix='audit_charts_'))
            try:
                bars = chart_tmp / 'bars.png'
                if _chart_scores_bars(scores, bars):
                    story.append(_image_from_path(bars, 14.0 * cm, 4.8 * cm))
            finally:
                shutil.rmtree(chart_tmp, ignore_errors=True)
            story.append(Spacer(1, 0.2 * cm))

        story.append(self._section_header('Carte de santé', st))
        story.append(Spacer(1, 0.1 * cm))
        story.append(self._health_table(health_rows, st))
        story.append(Spacer(1, 0.3 * cm))

        essential_rows = context.get('essential_rows') or []
        if is_essential and essential_rows:
            story.append(Paragraph('<b>Indicateurs mesurés</b>', st['body_bold']))
            story.append(Spacer(1, 0.08 * cm))
            story.append(self._detail_data_table(essential_rows, st))
            story.append(Spacer(1, 0.25 * cm))

        if not is_essential:
            detail_tables = context.get('detail_tables') or []
            self._append_detail_tables(story, detail_tables, st)
            if detail_tables:
                story.append(Spacer(1, 0.2 * cm))
            for block in other_blocks:
                if block.get('id') == 'synthesis':
                    continue
                self._append_narrative_block(story, block, st)

        qw = context.get('quick_wins') or []
        if qw:
            story.append(self._section_header('Actions prioritaires', st))
            story.append(Spacer(1, 0.1 * cm))
            qw_rows = []
            limit = 4 if is_essential else 8
            for i, w in enumerate(qw[:limit], 1):
                qw_rows.append(
                    [
                        Paragraph(f'<font color="#0f766e"><b>{i}</b></font>', st['body_bold']),
                        Paragraph(_esc(w), st['body']),
                    ]
                )
            qw_t = Table(qw_rows, colWidths=[1.0 * cm, 16.0 * cm])
            qw_t.setStyle(
                TableStyle(
                    [
                        ('BACKGROUND', (0, 0), (-1, -1), AMBER_LIGHT),
                        ('BOX', (0, 0), (-1, -1), 0.5, AMBER),
                        ('LEFTPADDING', (0, 0), (-1, -1), 10),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (0, -1), 6),
                        ('RIGHTPADDING', (0, 0), (0, -1), 4),
                    ]
                )
            )
            story.append(qw_t)
            story.append(Spacer(1, 0.35 * cm))

        if not is_essential:
            synth = [b for b in narrative_sections if b.get('id') == 'synthesis']
            for block in synth:
                self._append_narrative_block(story, block, st)

        shots = (pipeline.get('screenshots') or {}).get('latest') or {}
        include_screenshots = not is_essential and shots
        shot_specs = (
            ('desktop', 'Desktop — vue principale', content_w, _MAX_SCREENSHOT_HEIGHT_DESKTOP),
            ('mobile', 'Mobile', (content_w - 0.4 * cm) / 2, _MAX_SCREENSHOT_HEIGHT_DEVICE),
            ('tablet', 'Tablette', (content_w - 0.4 * cm) / 2, _MAX_SCREENSHOT_HEIGHT_DEVICE),
        )
        rendered: List[Tuple[str, Image]] = []
        for device, label, width, max_h in shot_specs:
            block = shots.get(device) or {}
            fp = _resolve_screenshot_path(block.get('file_path'))
            if not fp:
                continue
            img = _styled_screenshot_image(
                fp,
                display_width=width,
                device_label=label,
                max_display_height=max_h,
            )
            if img:
                rendered.append((device, img))

        if include_screenshots and rendered:
            story.append(PageBreak())
            story.append(self._section_header('Aperçu visuel du site', st))
            story.append(Spacer(1, 0.12 * cm))
            page_url = shots.get('page_url') or ''
            if page_url:
                story.append(Paragraph(f'<i>Page : {_esc(str(page_url)[:120])}</i>', st['muted']))
                story.append(Spacer(1, 0.1 * cm))
            desktop_img = next((img for dev, img in rendered if dev == 'desktop'), None)
            if desktop_img:
                story.append(desktop_img)
                story.append(Spacer(1, 0.25 * cm))
            secondary = [(dev, img) for dev, img in rendered if dev != 'desktop']
            if secondary:
                for _dev, img in secondary:
                    story.append(img)
                    story.append(Spacer(1, 0.2 * cm))
            story.append(Spacer(1, 0.3 * cm))

        pentest = pipeline.get('pentest') or {}
        vulns = pentest.get('vulnerabilities') or []
        if vulns and not is_essential:
            story.append(PageBreak())
            story.append(self._section_header('Annexe — vulnérabilités détectées', st))
            story.append(Spacer(1, 0.15 * cm))
            vdata = [
                [
                    Paragraph('<b>Sév.</b>', st['body_bold']),
                    Paragraph('<b>Titre</b>', st['body_bold']),
                    Paragraph('<b>Description</b>', st['body_bold']),
                ]
            ]
            sev_colors = {
                'critical': '#dc2626',
                'high': '#ea580c',
                'medium': '#d97706',
                'low': '#64748b',
            }
            for v in vulns[:12]:
                sev = str(v.get('severity') or v.get('level') or '—').lower()[:12]
                hex_c = sev_colors.get(sev, '#64748b')
                title = _esc(str(v.get('title') or v.get('name') or '—')[:56])
                desc = _esc(str(v.get('description') or v.get('detail') or '')[:200])
                vdata.append([
                    Paragraph(f'<font color="{hex_c}"><b>{_esc(sev.upper())}</b></font>', st['body']),
                    Paragraph(title, st['body']),
                    Paragraph(desc, st['body']),
                ])
            vt = Table(vdata, colWidths=[1.8 * cm, 5.2 * cm, 10.3 * cm])
            vt.setStyle(
                TableStyle(
                    [
                        ('BACKGROUND', (0, 0), (-1, 0), INK),
                        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                        ('GRID', (0, 0), (-1, -1), 0.35, BORDER),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SURFACE]),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(vt)
        elif vulns and is_essential:
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph('<b>Alertes sécurité</b>', st['body_bold']))
            for v in vulns[:3]:
                title = _esc(str(v.get('title') or v.get('name') or '—')[:80])
                story.append(Paragraph(f'• {title}', st['bullet']))

        footer_note = (
            'DanielCraft · Audit essentiel (offre gratuite)'
            if is_essential
            else 'DanielCraft · Rapport généré automatiquement'
        )
        story.append(Spacer(1, 0.6 * cm))
        footer_bar = Table(
            [[Paragraph(
                f'<i>{footer_note}</i>',
                ParagraphStyle('Footer', parent=st['muted'], alignment=TA_CENTER, fontSize=7),
            )]],
            colWidths=[content_w],
        )
        footer_bar.setStyle(
            TableStyle(
                [
                    ('LINEABOVE', (0, 0), (-1, 0), 1, BORDER),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(footer_bar)

        doc.build(story)
        return out_path

    def _extract_scores(self, context: Dict[str, Any]) -> Dict[str, Optional[float]]:
        pipeline = context.get('pipeline') or {}
        opp = context.get('opportunity') or {}
        tech = pipeline.get('technical') or {}
        seo = pipeline.get('seo') or {}
        pentest = pipeline.get('pentest') or {}
        return {
            'seo': _safe_float(seo.get('score')) if seo.get('status') == 'done' else None,
            'security': _safe_float(tech.get('security_score')) if tech.get('status') == 'done' else None,
            'performance': _safe_float(tech.get('performance_score')) if tech.get('status') == 'done' else None,
            'pentest_risk': _safe_float(pentest.get('risk_score')) if pentest.get('status') == 'done' else None,
            'opportunity': _safe_float(opp.get('score')),
        }
