"""
Service d'analyse UX (corpus @clea_ux).

Heuristiques HTML + rattachement aux principes / transcripts TikTok UX.
Chaque « outil » est activable via options (pattern proche de PentestAnalyzer).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from services.ux_corpus import CLEA_UX_CHAPTERS, UXCorpus, get_ux_corpus

logger = logging.getLogger(__name__)

try:
    from config import (
        UX_FETCH_CONNECT_TIMEOUT,
        UX_FETCH_READ_TIMEOUT,
        UX_TRANSCRIPTS_DIR,
    )
except ImportError:
    UX_FETCH_CONNECT_TIMEOUT = float(os.environ.get('UX_FETCH_CONNECT_TIMEOUT', '12'))
    UX_FETCH_READ_TIMEOUT = float(os.environ.get('UX_FETCH_READ_TIMEOUT', '25'))
    UX_TRANSCRIPTS_DIR = os.environ.get('UX_TRANSCRIPTS_DIR') or None

# CTA génériques (produit) vs formulations orientées résultat (CTV)
_GENERIC_CTA = re.compile(
    r'\b(s[\']?inscrire|s[\']?enregistrer|commencer|essayer|try|sign\s*up|'
    r'get\s*started|créer\s*(un\s*)?compte|en\s*savoir\s*plus|découvrir|'
    r'contactez[- ]nous|demander\s*un\s*devis)\b',
    re.I,
)
_VALUE_CTA = re.compile(
    r'\b(voir|recevoir|obtenir|calculer|générer|lancer|analyser|comparer|'
    r'économiser|gagner|ne\s*plus|en\s*\d+\s*min|gratuit|audit|rapport|'
    r'opportunités|devis)\b',
    re.I,
)
_LOSS_WORDS = re.compile(
    r'\b(perdre|perte|manquer|risque|trop\s*tard|avant\s*qu|ne\s*plus|'
    r'abandonner|oubli|fuite|churn)\b',
    re.I,
)
_SOCIAL_PROOF = re.compile(
    r'\b(avis|témoignage|clients?|utilisateurs?|entreprises?|'
    r'\d+\s*\+?\s*(clients|utilisateurs|avis|entreprises)|note\s*\d|'
    r'trustpilot|google\s*reviews?)\b',
    re.I,
)
_PROGRESS = re.compile(r'progress|étape\s*\d|step\s*\d|wizard|onboarding', re.I)
_PAYWALL = re.compile(r'pro\b|premium|upgrade|essai|trial|abonnement|pricing|tarif', re.I)
_LOCK = re.compile(r'cadenas|lock|verrouill|disponible\s+(avec|sur)\s+(le\s+)?plan', re.I)


class UXAnalyzer:
    """
    Analyse UX d'un site web calée sur le corpus @clea_ux.

    Les outils sont des heuristiques Python (pas de CLI externes).
    Le corpus transcripts alimente les références et la recherche.
    """

    def __init__(self, transcripts_dir: Optional[str] = None):
        """
        Initialise l'analyseur et vérifie la dispo des outils.

        @param transcripts_dir: Dossier transcripts (sinon config / défaut).
        """
        self.transcripts_dir = transcripts_dir or UX_TRANSCRIPTS_DIR
        self.corpus: UXCorpus = get_ux_corpus(self.transcripts_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (compatible; ProspectLab-UXAnalyzer/1.0; '
                '+https://danielcraft.fr)'
            ),
            'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.5',
        })
        self._check_tools_availability()

    def _check_tools_availability(self) -> None:
        """Remplit self.tools (tous les outils heuristiques + corpus)."""
        corpus_ok = self.corpus.ensure_loaded()
        # Outils toujours « disponibles » (code Python) ; corpus_index dépend des fichiers
        tool_names = [
            'corpus_index',
            'corpus_search',
            'chapter_map',
            'corpus_rules_extract',
            'page_corpus_relevance',
            'hick_law',
            'ctv_call_to_value',
            'contrast_pricing',
            'loss_aversion',
            'hero_clarity',
            'onboarding_flow',
            'time_to_value',
            'aha_moment',
            'error_guidance',
            'empty_states',
            'navigation_sidebar',
            'friction_forms',
            'adaptive_persona',
            'social_proof',
            'paywall_vitrine',
            'peak_end',
            'zeigarnik_progress',
            'gamification',
            'search_experience',
            'mobile_viewport',
            'notification_patterns',
            'trust_consistency',
            'dashboard_necessity',
            'fogg_behavior',
            'retention_signals',
            'feature_adoption',
            'microcopy_validation',
            'phantom_modals',
            'heading_hierarchy',
            'link_density',
            'accessibility_basics',
            'corpus_principle_match',
        ]
        self.tools: Dict[str, bool] = {name: True for name in tool_names}
        self.tools['corpus_index'] = corpus_ok
        self.tools['corpus_search'] = corpus_ok
        self.tools['chapter_map'] = True
        self.tools['corpus_rules_extract'] = corpus_ok
        self.tools['page_corpus_relevance'] = corpus_ok
        self.tools['corpus_principle_match'] = corpus_ok

    def get_diagnostic(self) -> Dict[str, Any]:
        """
        Diagnostic environnement UX (outils + corpus).

        @returns: Dict tools_available / tools_missing / corpus / message.
        """
        available = [k for k, v in self.tools.items() if v]
        missing = [k for k, v in self.tools.items() if not v]
        stats = self.corpus.get_stats()
        return {
            'execution_mode': 'python_heuristics',
            'tools_available': available,
            'tools_missing': missing,
            'tools_count': len(available),
            'tools_total': len(self.tools),
            'corpus': stats,
            'message': (
                f'{len(available)}/{len(self.tools)} outils UX prêts ; '
                f'corpus {stats.get("transcript_count", 0)} transcripts'
            ),
        }

    # ------------------------------------------------------------------
    # Fetch HTML
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> Tuple[Optional[str], Optional[BeautifulSoup], Dict[str, Any]]:
        """
        Télécharge et parse une page HTML.

        @param url: URL cible.
        @returns: (html, soup, meta) — soup/html None si échec.
        """
        meta: Dict[str, Any] = {'url': url, 'final_url': url, 'status_code': None}
        try:
            resp = self.session.get(
                url,
                timeout=(UX_FETCH_CONNECT_TIMEOUT, UX_FETCH_READ_TIMEOUT),
                allow_redirects=True,
            )
            meta['status_code'] = resp.status_code
            meta['final_url'] = str(resp.url)
            meta['content_type'] = (resp.headers.get('Content-Type') or '')[:80]
            if resp.status_code >= 400:
                meta['error'] = f'HTTP {resp.status_code}'
                return None, None, meta
            html = resp.text or ''
            soup = BeautifulSoup(html, 'lxml') if html else BeautifulSoup(html, 'html.parser')
            return html, soup, meta
        except requests.RequestException as exc:
            meta['error'] = str(exc)
            return None, None, meta

    def _page_text(self, soup: BeautifulSoup) -> str:
        """Texte visible approximatif (sans muter le soup partagé)."""
        clone = BeautifulSoup(str(soup), 'lxml')
        for tag in clone(['script', 'style', 'noscript', 'svg']):
            tag.decompose()
        return ' '.join(clone.get_text(' ', strip=True).split())

    def _cta_candidates(self, soup: BeautifulSoup) -> List[str]:
        """Libellés de boutons / liens CTA."""
        labels: List[str] = []
        for el in soup.select('a, button, [role="button"], input[type="submit"]'):
            txt = (el.get_text(' ', strip=True) or el.get('value') or el.get('aria-label') or '').strip()
            if 2 <= len(txt) <= 80:
                labels.append(txt)
        return labels

    def _nav_items(self, soup: BeautifulSoup) -> List[str]:
        """Items de navigation principale."""
        items: List[str] = []
        for nav in soup.select('nav, header, [role="navigation"], .navbar, .sidebar, aside'):
            for a in nav.select('a'):
                t = a.get_text(' ', strip=True)
                if t and len(t) < 60 and t not in items:
                    items.append(t)
            if len(items) > 40:
                break
        return items

    def _finding(
        self,
        *,
        tool: str,
        chapter: int,
        severity: str,
        title: str,
        message: str,
        recommendation: str,
        evidence: Optional[Dict[str, Any]] = None,
        score_delta: int = 0,
    ) -> Dict[str, Any]:
        """Construit un finding standard + match contre tout le corpus."""
        ch = next((c for c in CLEA_UX_CHAPTERS if c['id'] == chapter), None)
        finding: Dict[str, Any] = {
            'tool': tool,
            'chapter': chapter,
            'chapter_title': (ch or {}).get('title'),
            'principle': (ch or {}).get('principle'),
            'severity': severity,
            'title': title,
            'message': message,
            'recommendation': recommendation,
            'score_delta': score_delta,
            'corpus_refs': [],
            'corpus_quotes': [],
            'corpus_rules': [],
            'evidence': evidence or {},
        }
        if self.tools.get('corpus_index'):
            try:
                matched = self.corpus.match_finding(finding, limit=5)
                finding['corpus_refs'] = [
                    h.get('title') for h in (matched.get('hits') or []) if h.get('title')
                ]
                finding['corpus_quotes'] = [
                    {
                        'source': h.get('title'),
                        'excerpt': h.get('excerpt'),
                        'score': h.get('score'),
                    }
                    for h in (matched.get('hits') or [])[:3]
                ]
                finding['corpus_rules'] = [
                    {
                        'rule': r.get('rule'),
                        'source': r.get('source_title'),
                    }
                    for r in (matched.get('rules') or [])[:3]
                ]
                finding['corpus_best_quote'] = matched.get('best_quote')
                finding['corpus_best_source'] = matched.get('best_source')
                finding['corpus_docs_scanned'] = matched.get('corpus_docs_scanned')
            except Exception as exc:
                logger.debug('match_finding échoué: %s', exc)
                finding['corpus_refs'] = self.corpus.refs_for_chapter(chapter, limit=5)
        return finding

    # ------------------------------------------------------------------
    # Outils corpus
    # ------------------------------------------------------------------

    def tool_corpus_index(self, _ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Indexe / expose les stats du corpus transcripts."""
        if not self.tools.get('corpus_index'):
            return {'error': 'Corpus transcripts indisponible', 'scan_completed': False}
        stats = self.corpus.get_stats()
        return {
            'scan_completed': True,
            'stats': stats,
            'findings': [],
            'summary': f'{stats["transcript_count"]} transcripts indexés',
        }

    def tool_corpus_search(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Recherche dans le corpus à partir du hero / H1 de la page."""
        if not self.tools.get('corpus_search'):
            return {'error': 'Corpus indisponible', 'scan_completed': False}
        soup = ctx.get('soup')
        query_bits: List[str] = []
        if soup:
            h1 = soup.find('h1')
            if h1:
                query_bits.append(h1.get_text(' ', strip=True)[:80])
            title = soup.find('title')
            if title:
                query_bits.append(title.get_text(' ', strip=True)[:80])
        query = ' '.join(query_bits) or 'onboarding conversion landing'
        hits = self.corpus.search(query, limit=6)
        return {
            'scan_completed': True,
            'query': query,
            'hits': hits,
            'findings': [],
            'summary': f'{len(hits)} hits corpus pour « {query[:40]} »',
        }

    def tool_chapter_map(self, _ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Expose la grille des 14 chapitres clea_ux."""
        return {
            'scan_completed': True,
            'chapters': CLEA_UX_CHAPTERS,
            'findings': [],
            'summary': f'{len(CLEA_UX_CHAPTERS)} chapitres de référence',
        }

    def tool_corpus_rules_extract(self, _ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Extrait la grille de règles depuis tous les transcripts indexés."""
        if not self.tools.get('corpus_rules_extract'):
            return {'error': 'Corpus indisponible', 'scan_completed': False}
        grid = self.corpus.get_rules_grid(limit_per_chapter=8)
        return {
            'scan_completed': True,
            'rules_total': grid.get('rules_total', 0),
            'transcript_count': grid.get('transcript_count', 0),
            'chapters': grid.get('chapters', []),
            'findings': [],
            'summary': (
                f'{grid.get("rules_total", 0)} règles extraites de '
                f'{grid.get("transcript_count", 0)} transcripts'
            ),
        }

    def tool_page_corpus_relevance(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Croise le texte de la page avec tout le corpus (gaps / forces)."""
        if not self.tools.get('page_corpus_relevance'):
            return {'error': 'Corpus indisponible', 'scan_completed': False}
        relevance = self.corpus.score_page_against_corpus(ctx.get('text') or '')
        findings: List[Dict[str, Any]] = []
        for gap in (relevance.get('gaps') or [])[:3]:
            findings.append(self._finding(
                tool='page_corpus_relevance',
                chapter=int(gap.get('chapter') or 14),
                severity='low',
                title=f'Angle @clea_ux peu couvert : {gap.get("title")}',
                message=(
                    f'Peu de signaux page liés au chapitre « {gap.get("title")} » '
                    f'({gap.get("transcripts_in_chapter", 0)} transcripts corpus).'
                ),
                recommendation=gap.get('principle') or 'Renforce cet angle UX sur la page.',
                evidence={'gap': gap},
                score_delta=-3,
            ))
        return {
            'scan_completed': True,
            'relevance': relevance,
            'findings': findings,
            'summary': (
                f'Corpus {relevance.get("corpus_docs", 0)} docs — '
                f'{len(relevance.get("gaps") or [])} gaps, '
                f'{len(relevance.get("strengths") or [])} forces'
            ),
        }

    # ------------------------------------------------------------------
    # Outils heuristiques page
    # ------------------------------------------------------------------

    def tool_hick_law(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Loi de Hick : trop de choix au même niveau (nav + CTA)."""
        soup = ctx['soup']
        nav = self._nav_items(soup)
        ctas = self._cta_candidates(soup)
        findings: List[Dict[str, Any]] = []
        if len(nav) > 7:
            findings.append(self._finding(
                tool='hick_law',
                chapter=5,
                severity='high' if len(nav) > 12 else 'medium',
                title='Trop de choix de navigation (loi de Hick)',
                message=(
                    f'{len(nav)} items de navigation détectés au premier niveau '
                    f'(seuil recommandé : 7).'
                ),
                recommendation=(
                    'Regroupe par intention, garde max 7 espaces principaux, '
                    'et mets l\'action prioritaire en tête.'
                ),
                evidence={'nav_count': len(nav), 'nav_sample': nav[:12]},
                score_delta=-min(25, (len(nav) - 7) * 2),
            ))
        primary_ctas = [c for c in ctas if _GENERIC_CTA.search(c) or _VALUE_CTA.search(c)]
        if len(primary_ctas) > 5:
            findings.append(self._finding(
                tool='hick_law',
                chapter=5,
                severity='medium',
                title='Trop de CTA concurrents',
                message=f'{len(primary_ctas)} CTA potentiels détectés — l\'utilisateur reporte la décision.',
                recommendation='Une action principale claire : « commence par ça ».',
                evidence={'cta_sample': primary_ctas[:10]},
                score_delta=-10,
            ))
        return {
            'scan_completed': True,
            'nav_count': len(nav),
            'cta_count': len(ctas),
            'findings': findings,
            'summary': f'Nav={len(nav)}, CTA={len(ctas)}',
        }

    def tool_ctv_call_to_value(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """CTV vs CTA : les boutons parlent-ils résultat ou produit ?"""
        ctas = self._cta_candidates(ctx['soup'])
        generic = [c for c in ctas if _GENERIC_CTA.search(c)]
        valued = [c for c in ctas if _VALUE_CTA.search(c)]
        findings: List[Dict[str, Any]] = []
        if generic and len(generic) >= len(valued):
            findings.append(self._finding(
                tool='ctv_call_to_value',
                chapter=4,
                severity='high' if len(generic) >= 3 else 'medium',
                title='CTA orientés produit plutôt que CTV',
                message=(
                    f'{len(generic)} CTA génériques vs {len(valued)} orientés résultat. '
                    'Un CTA parle au produit ; un CTV parle à l\'utilisateur.'
                ),
                recommendation=(
                    'Remplace « S\'inscrire / Commencer » par un résultat concret '
                    '(ex. « Voir mes opportunités en 5 min »).'
                ),
                evidence={'generic': generic[:8], 'valued': valued[:8]},
                score_delta=-15,
            ))
        return {
            'scan_completed': True,
            'generic_cta': generic[:15],
            'value_cta': valued[:15],
            'findings': findings,
            'summary': f'génériques={len(generic)}, valeur={len(valued)}',
        }

    def tool_contrast_pricing(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Effet de contraste sur pricing / offres."""
        text = ctx['text']
        soup = ctx['soup']
        prices = re.findall(r'(\d[\d\s]*)\s*€', text)
        price_nums = []
        for p in prices:
            try:
                price_nums.append(int(re.sub(r'\s+', '', p)))
            except ValueError:
                pass
        plan_blocks = soup.select(
            '.pricing, .price, .tarif, [class*="pricing"], [class*="plan"], [class*="tarif"]'
        )
        findings: List[Dict[str, Any]] = []
        if len(set(price_nums)) >= 2:
            hi, lo = max(price_nums), min(price_nums)
            if lo > 0 and hi / lo >= 8:
                findings.append(self._finding(
                    tool='contrast_pricing',
                    chapter=4,
                    severity='high',
                    title='Écart tarifaire extrême sans pont',
                    message=f'Écart {lo} € → {hi} € détecté (x{hi / lo:.1f}).',
                    recommendation=(
                        'Ajoute un plan milieu mis en avant + ancre haute + '
                        'comparatif honnête (effet de contraste).'
                    ),
                    evidence={'prices': sorted(set(price_nums))[:10]},
                    score_delta=-12,
                ))
        if not plan_blocks and price_nums:
            findings.append(self._finding(
                tool='contrast_pricing',
                chapter=11,
                severity='low',
                title='Prix présents sans structure de plans claire',
                message='Des montants apparaissent hors bloc pricing identifiable.',
                recommendation='Structure pricing : ancre + plan cible + entrée.',
                evidence={'price_count': len(price_nums)},
                score_delta=-5,
            ))
        return {
            'scan_completed': True,
            'prices_found': sorted(set(price_nums))[:15],
            'plan_blocks': len(plan_blocks),
            'findings': findings,
            'summary': f'{len(set(price_nums))} prix, {len(plan_blocks)} blocs',
        }

    def tool_loss_aversion(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Aversion à la perte dans le copy."""
        text = ctx['text']
        hits = _LOSS_WORDS.findall(text)
        findings: List[Dict[str, Any]] = []
        if len(hits) == 0:
            findings.append(self._finding(
                tool='loss_aversion',
                chapter=4,
                severity='low',
                title='Peu d\'aversion à la perte dans le discours',
                message='Le copy parle surtout de gains, pas de ce que l\'utilisateur perd en ne faisant rien.',
                recommendation='Nomme ce qui est perdu sans action (temps, deals, clients).',
                evidence={'loss_word_hits': 0},
                score_delta=-4,
            ))
        return {
            'scan_completed': True,
            'loss_hits': len(hits),
            'findings': findings,
            'summary': f'{len(hits)} signaux perte',
        }

    def tool_hero_clarity(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Clarté du hero : un H1 + une promesse."""
        soup = ctx['soup']
        h1s = [h.get_text(' ', strip=True) for h in soup.find_all('h1')]
        findings: List[Dict[str, Any]] = []
        if not h1s:
            findings.append(self._finding(
                tool='hero_clarity',
                chapter=4,
                severity='high',
                title='Pas de H1 (hero flou)',
                message='Aucun H1 détecté — promesse peu identifiable.',
                recommendation='Un H1 = une promesse de résultat pour la cible.',
                score_delta=-15,
            ))
        elif len(h1s) > 2:
            findings.append(self._finding(
                tool='hero_clarity',
                chapter=4,
                severity='medium',
                title='Plusieurs H1 concurrents',
                message=f'{len(h1s)} balises H1 — le message hero se dilue.',
                recommendation='Un seul H1 hero ; le reste en H2.',
                evidence={'h1s': h1s[:5]},
                score_delta=-8,
            ))
        return {
            'scan_completed': True,
            'h1s': h1s[:5],
            'findings': findings,
            'summary': f'{len(h1s)} H1',
        }

    def tool_onboarding_flow(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Signaux d'onboarding / wizard."""
        soup = ctx['soup']
        text = ctx['text']
        steps = soup.select('[class*="step"], [class*="wizard"], [class*="onboarding"], progress')
        has_progress = bool(_PROGRESS.search(text)) or bool(steps)
        findings: List[Dict[str, Any]] = []
        signup = soup.select('form input[type="password"], form input[name*="email" i]')
        if signup and not has_progress:
            findings.append(self._finding(
                tool='onboarding_flow',
                chapter=1,
                severity='medium',
                title='Inscription sans parcours de valeur visible',
                message='Formulaire d\'accès détecté sans barre / étapes d\'onboarding.',
                recommendation=(
                    'Définis l\'action clé, construis à rebours, réduit au minimum, '
                    'ajoute progression + micro-victoires.'
                ),
                evidence={'signup_fields': len(signup)},
                score_delta=-10,
            ))
        return {
            'scan_completed': True,
            'has_progress_signal': has_progress,
            'step_nodes': len(steps),
            'findings': findings,
            'summary': f'progress={has_progress}',
        }

    def tool_time_to_value(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Friction formulaires = TTV long."""
        soup = ctx['soup']
        forms = soup.find_all('form')
        findings: List[Dict[str, Any]] = []
        heavy = []
        for form in forms:
            fields = form.find_all(['input', 'select', 'textarea'])
            visible = [
                f for f in fields
                if (f.get('type') or '').lower() not in ('hidden', 'submit', 'button', 'reset', 'image')
            ]
            if len(visible) >= 8:
                heavy.append(len(visible))
        if heavy:
            findings.append(self._finding(
                tool='time_to_value',
                chapter=2,
                severity='high',
                title='Formulaire lourd (Time to Value élevé)',
                message=f'Formulaire(s) avec jusqu\'à {max(heavy)} champs visibles.',
                recommendation=(
                    'Résultat d\'abord, config ensuite. Règle des 2 minutes : '
                    'première preuve de valeur avant la config complète.'
                ),
                evidence={'heavy_field_counts': heavy[:5]},
                score_delta=-14,
            ))
        return {
            'scan_completed': True,
            'form_count': len(forms),
            'heavy_forms': heavy,
            'findings': findings,
            'summary': f'{len(forms)} forms, {len(heavy)} lourds',
        }

    def tool_aha_moment(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Preuve de valeur visible (demo, rapport, exemple)."""
        text = ctx['text'].lower()
        signals = []
        for kw in ('exemple', 'démo', 'demo', 'aperçu', 'preview', 'avant/après', 'résultat', 'rapport', 'sample'):
            if kw in text:
                signals.append(kw)
        findings: List[Dict[str, Any]] = []
        if not signals:
            findings.append(self._finding(
                tool='aha_moment',
                chapter=3,
                severity='medium',
                title='Peu de signaux d\'aha moment',
                message='Pas d\'aperçu / démo / résultat visible détecté sur la page.',
                recommendation='Montre la promesse réalisée avant ou juste après l\'inscription.',
                score_delta=-8,
            ))
        return {
            'scan_completed': True,
            'signals': signals,
            'findings': findings,
            'summary': f'{len(signals)} signaux valeur',
        }

    def tool_error_guidance(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Page 404 / erreurs qui guident."""
        url = ctx['meta'].get('final_url') or ctx['url']
        parsed = urlparse(url)
        base = f'{parsed.scheme}://{parsed.netloc}'
        findings: List[Dict[str, Any]] = []
        probe_url = urljoin(base + '/', 'page-qui-nexiste-pas-prospectlab-ux-404')
        html, soup, meta = self._fetch(probe_url)
        status = meta.get('status_code')
        body = (html or '').lower()
        has_cta = False
        if soup:
            labels = self._cta_candidates(soup)
            has_cta = any(_VALUE_CTA.search(x) or _GENERIC_CTA.search(x) for x in labels)
        if status == 404 or '404' in body or 'introuvable' in body or 'not found' in body:
            if not has_cta:
                findings.append(self._finding(
                    tool='error_guidance',
                    chapter=8,
                    severity='medium',
                    title='404 sans sortie actionnable',
                    message='Page d\'erreur sans CTA clair pour reprendre le parcours.',
                    recommendation='Expliquer + CTV immédiat (« Audit gratuit », « Retour devis »).',
                    evidence={'status': status, 'probe': probe_url},
                    score_delta=-10,
                ))
        return {
            'scan_completed': True,
            'probe_status': status,
            'findings': findings,
            'summary': f'404 probe status={status}',
        }

    def tool_empty_states(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Empty states / no-data."""
        text = ctx['text'].lower()
        hits = [p for p in ('aucune donnée', 'no data', 'rien à afficher', 'empty', 'pas encore') if p in text]
        findings: List[Dict[str, Any]] = []
        if hits:
            findings.append(self._finding(
                tool='empty_states',
                chapter=9,
                severity='low',
                title='Empty state détecté',
                message=f'Signaux empty state: {", ".join(hits)}.',
                recommendation='Jamais face au vide : CTA + exemple / template / vote feature.',
                evidence={'phrases': hits},
                score_delta=-5,
            ))
        return {'scan_completed': True, 'findings': findings, 'summary': f'{len(hits)} empty'}

    def tool_navigation_sidebar(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """3 règles sidebar (intention, max 7, action en tête)."""
        # Réutilise hick mais cible aside/sidebar
        soup = ctx['soup']
        side = soup.select('aside, .sidebar, [class*="sidebar"], nav.sidebar')
        items: List[str] = []
        for block in side:
            for a in block.select('a'):
                t = a.get_text(' ', strip=True)
                if t and t not in items:
                    items.append(t)
        findings: List[Dict[str, Any]] = []
        if items and len(items) > 7:
            findings.append(self._finding(
                tool='navigation_sidebar',
                chapter=5,
                severity='medium',
                title='Sidebar trop chargée',
                message=f'{len(items)} liens sidebar (max 7 au 1er niveau).',
                recommendation='Regroupe par intention ; action principale en haut.',
                evidence={'items': items[:15]},
                score_delta=-8,
            ))
        return {
            'scan_completed': True,
            'sidebar_items': len(items),
            'findings': findings,
            'summary': f'sidebar={len(items)}',
        }

    def tool_friction_forms(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Friction : champs required excessifs, captcha, multi-étapes cachées."""
        soup = ctx['soup']
        required = soup.select('input[required], select[required], textarea[required]')
        captcha = soup.select('[class*="captcha"], [id*="captcha"], iframe[src*="recaptcha"]')
        findings: List[Dict[str, Any]] = []
        if len(required) >= 6:
            findings.append(self._finding(
                tool='friction_forms',
                chapter=6,
                severity='medium',
                title='Friction toxique sur formulaire',
                message=f'{len(required)} champs obligatoires — active le système 2 trop tôt.',
                recommendation='Garde la friction pour actions critiques ; le reste en système 1.',
                evidence={'required_count': len(required), 'captcha': len(captcha)},
                score_delta=-10,
            ))
        return {
            'scan_completed': True,
            'required_fields': len(required),
            'captcha_nodes': len(captcha),
            'findings': findings,
            'summary': f'required={len(required)}',
        }

    def tool_adaptive_persona(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Signaux multi-cibles / segmentation."""
        text = ctx['text'].lower()
        personas = []
        for kw in ('artisan', 'tpe', 'pme', 'saas', 'freelance', 'agence', 'entreprise', 'particulier'):
            if kw in text:
                personas.append(kw)
        findings: List[Dict[str, Any]] = []
        if len(personas) >= 3:
            findings.append(self._finding(
                tool='adaptive_persona',
                chapter=7,
                severity='medium',
                title='Discours multi-cibles mélangés',
                message=f'Plusieurs personas évoqués: {", ".join(personas[:6])}.',
                recommendation='Deux cibles ≠ deux produits : deux entrées / landings / onboarding.',
                evidence={'personas': personas},
                score_delta=-7,
            ))
        return {
            'scan_completed': True,
            'personas': personas,
            'findings': findings,
            'summary': f'{len(personas)} personas',
        }

    def tool_social_proof(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Social proof vérifiable."""
        text = ctx['text']
        hits = _SOCIAL_PROOF.findall(text)
        logos = ctx['soup'].select('img[alt*="client" i], img[alt*="logo" i], .logo-cloud, .clients')
        findings: List[Dict[str, Any]] = []
        if len(hits) == 0 and len(logos) == 0:
            findings.append(self._finding(
                tool='social_proof',
                chapter=12,
                severity='medium',
                title='Social proof faible',
                message='Peu de preuves sociales détectées (avis, logos, compteurs).',
                recommendation='Preuves vérifiables près du CTV (pas des badges vagues).',
                score_delta=-8,
            ))
        return {
            'scan_completed': True,
            'proof_hits': len(hits),
            'logo_nodes': len(logos),
            'findings': findings,
            'summary': f'hits={len(hits)}, logos={len(logos)}',
        }

    def tool_paywall_vitrine(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Cadenas vs vitrine payante."""
        text = ctx['text']
        lock_hits = _LOCK.findall(text)
        pay_hits = _PAYWALL.findall(text)
        findings: List[Dict[str, Any]] = []
        if lock_hits:
            findings.append(self._finding(
                tool='paywall_vitrine',
                chapter=11,
                severity='high',
                title='Paywall type cadenas',
                message='Formulations de verrouillage détectées — frustration sans envie.',
                recommendation='Vitrine : montrer le bénéfice sans donner ; pas un mur « plan Pro ».',
                evidence={'locks': lock_hits[:5], 'pay_terms': pay_hits[:8]},
                score_delta=-12,
            ))
        return {
            'scan_completed': True,
            'lock_hits': len(lock_hits),
            'findings': findings,
            'summary': f'locks={len(lock_hits)}',
        }

    def tool_peak_end(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Peak-End : fin nette / victoire."""
        text = ctx['text'].lower()
        victory = [k for k in ('félicitations', 'bravo', 'succès', 'victoire', 'terminé', 'checklist', 'c\'est fait') if k in text]
        findings: List[Dict[str, Any]] = []
        # Sur une landing, l'absence n'est pas critique ; on signale en low
        if not victory:
            findings.append(self._finding(
                tool='peak_end',
                chapter=12,
                severity='low',
                title='Fin de parcours peu marquée',
                message='Pas d\'écran / message de victoire identifiable.',
                recommendation='Pic de valeur tôt + fin nette (écran de victoire, email de réussite).',
                score_delta=-3,
            ))
        return {
            'scan_completed': True,
            'victory_signals': victory,
            'findings': findings,
            'summary': f'victory={len(victory)}',
        }

    def tool_zeigarnik_progress(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Effet Zeigarnik : progression visible."""
        soup = ctx['soup']
        bars = soup.select('progress, [role="progressbar"], .progress, [class*="progress"]')
        return {
            'scan_completed': True,
            'progress_nodes': len(bars),
            'findings': (
                []
                if bars
                else [self._finding(
                    tool='zeigarnik_progress',
                    chapter=13,
                    severity='low',
                    title='Pas de barre de progression',
                    message='Aucune progression visible (Zeigarnik non exploité).',
                    recommendation='Montre ce qui reste à terminer avec du sens, pas juste un compteur.',
                    score_delta=-4,
                )]
            ),
            'summary': f'progress_nodes={len(bars)}',
        }

    def tool_gamification(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Gamification : badges vs déblocage."""
        text = ctx['text'].lower()
        badges = [k for k in ('badge', 'points', 'niveau', 'streak', 'récompense') if k in text]
        unlock = [k for k in ('débloqu', 'unlock', 'disponible après') if k in text]
        findings: List[Dict[str, Any]] = []
        if badges and not unlock:
            findings.append(self._finding(
                tool='gamification',
                chapter=13,
                severity='low',
                title='Gamification orientée badges',
                message='Signaux badges/points sans logique de déblocage.',
                recommendation='Gamification = influencer un comportement (progression, inachevé), pas des badges.',
                evidence={'badges': badges, 'unlock': unlock},
                score_delta=-3,
            ))
        return {
            'scan_completed': True,
            'badge_signals': badges,
            'unlock_signals': unlock,
            'findings': findings,
            'summary': f'badges={len(badges)}',
        }

    def tool_search_experience(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Barre de recherche présente ?"""
        soup = ctx['soup']
        search = soup.select('input[type="search"], input[name*="search" i], input[placeholder*="recherch" i], form[role="search"]')
        findings: List[Dict[str, Any]] = []
        # Presence alone is ok; we note for corpus match later
        return {
            'scan_completed': True,
            'search_inputs': len(search),
            'findings': findings,
            'summary': f'search={len(search)}',
            'note': (
                'Si recherche sans résultat : bestseller + vote feature + correcteur d\'intention'
                if search else None
            ),
        }

    def tool_mobile_viewport(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Viewport mobile."""
        soup = ctx['soup']
        vp = soup.find('meta', attrs={'name': re.compile(r'^viewport$', re.I)})
        findings: List[Dict[str, Any]] = []
        if not vp:
            findings.append(self._finding(
                tool='mobile_viewport',
                chapter=6,
                severity='high',
                title='Meta viewport absent',
                message='Pas de viewport — expérience mobile probablement cassée.',
                recommendation='Ajoute <meta name="viewport" content="width=device-width, initial-scale=1">.',
                score_delta=-15,
            ))
        return {
            'scan_completed': True,
            'has_viewport': bool(vp),
            'findings': findings,
            'summary': f'viewport={bool(vp)}',
        }

    def tool_notification_patterns(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Bannières / popups agressifs."""
        soup = ctx['soup']
        banners = soup.select(
            '[class*="cookie"], [id*="cookie"], [class*="banner"], [class*="popup"], '
            '[class*="modal"], [class*="newsletter"], [aria-modal="true"]'
        )
        findings: List[Dict[str, Any]] = []
        if len(banners) >= 4:
            findings.append(self._finding(
                tool='notification_patterns',
                chapter=10,
                severity='medium',
                title='Trop d\'interruptions (bannières / modales)',
                message=f'{len(banners)} couches d\'interruption potentielles.',
                recommendation='Une notification = une action, au bon moment (fenêtre d\'intention).',
                evidence={'count': len(banners)},
                score_delta=-8,
            ))
        return {
            'scan_completed': True,
            'interrupt_nodes': len(banners),
            'findings': findings,
            'summary': f'interrupt={len(banners)}',
        }

    def tool_trust_consistency(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Incohérences de délais / promesses (24h vs 48h…)."""
        text = ctx['text']
        delays = re.findall(r'\b(\d+)\s*h(?:eures?)?\b', text, flags=re.I)
        delays += re.findall(r'\b(\d+)\s*jours?\b', text, flags=re.I)
        unique = sorted(set(delays))
        findings: List[Dict[str, Any]] = []
        if len(unique) >= 3:
            findings.append(self._finding(
                tool='trust_consistency',
                chapter=12,
                severity='medium',
                title='Promesses de délai incohérentes',
                message=f'Plusieurs délais distincts détectés: {", ".join(unique[:8])}.',
                recommendation='Un délai unique partout — la cohérence construit la confiance.',
                evidence={'delays': unique[:10]},
                score_delta=-10,
            ))
        return {
            'scan_completed': True,
            'delays': unique[:15],
            'findings': findings,
            'summary': f'{len(unique)} délais',
        }

    def tool_dashboard_necessity(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Dashboard / grille de choix trop dense."""
        soup = ctx['soup']
        cards = soup.select('.card, [class*="card"], .tile, .grid > *, .row > .col')
        findings: List[Dict[str, Any]] = []
        if len(cards) > 24:
            findings.append(self._finding(
                tool='dashboard_necessity',
                chapter=9,
                severity='medium',
                title='Grille de choix type dashboard',
                message=f'{len(cards)} cartes/blocs — surcharge de décision.',
                recommendation='Dashboard seulement si utile ; sinon chemin direct vers l\'action.',
                evidence={'card_count': len(cards)},
                score_delta=-9,
            ))
        return {
            'scan_completed': True,
            'card_like_nodes': len(cards),
            'findings': findings,
            'summary': f'cards≈{len(cards)}',
        }

    def tool_fogg_behavior(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Fogg : motivation / capacité / prompt (heuristique copy)."""
        text = ctx['text'].lower()
        motivation = any(k in text for k in ('bénéfice', 'gagner', 'résultat', 'économ', 'opportunité'))
        ability = any(k in text for k in ('simple', 'facile', '2 min', 'quelques secondes', 'sans engagement'))
        prompt = bool(self._cta_candidates(ctx['soup']))
        missing = []
        if not motivation:
            missing.append('motivation')
        if not ability:
            missing.append('capacité (facilité)')
        if not prompt:
            missing.append('prompt (CTA)')
        findings: List[Dict[str, Any]] = []
        if missing:
            findings.append(self._finding(
                tool='fogg_behavior',
                chapter=11,
                severity='low',
                title='Triangle Fogg incomplet',
                message=f'Éléments faibles: {", ".join(missing)}.',
                recommendation='Comportement = Motivation × Capacité × Prompt — renforce le maillon faible.',
                evidence={'motivation': motivation, 'ability': ability, 'prompt': prompt},
                score_delta=-5,
            ))
        return {
            'scan_completed': True,
            'fogg': {'motivation': motivation, 'ability': ability, 'prompt': prompt},
            'findings': findings,
            'summary': f'missing={len(missing)}',
        }

    def tool_retention_signals(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Signaux rétention (compte, login, retour)."""
        text = ctx['text'].lower()
        signals = [k for k in ('connexion', 'login', 'mon compte', 'espace client', 'réessayer', 'retour') if k in text]
        return {
            'scan_completed': True,
            'signals': signals,
            'findings': [],
            'summary': f'{len(signals)} signaux rétention',
        }

    def tool_feature_adoption(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Adoption de features (nouveauté, tooltip)."""
        soup = ctx['soup']
        tips = soup.select('[class*="tooltip"], [data-tour], .coachmark, [class*="spotlight"], .new-badge, .badge-new')
        findings: List[Dict[str, Any]] = []
        return {
            'scan_completed': True,
            'adoption_nodes': len(tips),
            'findings': findings,
            'summary': f'adoption_ui={len(tips)}',
            'note': 'Pour adopter une feature : la montrer au moment d\'intention, pas en tour guidé long.',
        }

    def tool_microcopy_validation(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Validation / aide contextuelle sur champs."""
        soup = ctx['soup']
        helps = soup.select('.help-text, .form-text, .hint, [class*="error"], small, .invalid-feedback')
        return {
            'scan_completed': True,
            'help_nodes': len(helps),
            'findings': (
                []
                if helps
                else [self._finding(
                    tool='microcopy_validation',
                    chapter=8,
                    severity='low',
                    title='Peu d\'aide / validation visible',
                    message='Peu de microcopy d\'aide autour des formulaires.',
                    recommendation='Validation temps réel : dire tôt ce qui ne va pas + CTA.',
                    score_delta=-4,
                )]
            ),
            'summary': f'help={len(helps)}',
        }

    def tool_phantom_modals(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Édition fantôme : trop de modales."""
        soup = ctx['soup']
        modals = soup.select('.modal, [class*="modal"], dialog, [role="dialog"]')
        findings: List[Dict[str, Any]] = []
        if len(modals) >= 5:
            findings.append(self._finding(
                tool='phantom_modals',
                chapter=6,
                severity='medium',
                title='Trop de modales (édition fantôme négligée)',
                message=f'{len(modals)} modales/dialogs — micro-interruptions cumulées.',
                recommendation='Valeurs simples → édition inline ; complexe → une modale dédiée.',
                evidence={'modal_count': len(modals)},
                score_delta=-7,
            ))
        return {
            'scan_completed': True,
            'modal_count': len(modals),
            'findings': findings,
            'summary': f'modals={len(modals)}',
        }

    def tool_heading_hierarchy(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Hiérarchie de titres."""
        soup = ctx['soup']
        levels = {i: len(soup.find_all(f'h{i}')) for i in range(1, 7)}
        findings: List[Dict[str, Any]] = []
        if levels[1] == 0 and sum(levels.values()) > 0:
            findings.append(self._finding(
                tool='heading_hierarchy',
                chapter=4,
                severity='medium',
                title='Hiérarchie de titres cassée',
                message='Titres présents sans H1.',
                recommendation='H1 unique puis H2/H3 cohérents pour scannabilité.',
                evidence=levels,
                score_delta=-6,
            ))
        return {
            'scan_completed': True,
            'heading_counts': levels,
            'findings': findings,
            'summary': f'h1={levels[1]} h2={levels[2]}',
        }

    def tool_link_density(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Densité de liens (surcharge Hick)."""
        soup = ctx['soup']
        links = soup.find_all('a', href=True)
        findings: List[Dict[str, Any]] = []
        if len(links) > 120:
            findings.append(self._finding(
                tool='link_density',
                chapter=5,
                severity='medium',
                title='Densité de liens élevée',
                message=f'{len(links)} liens sur la page — charge cognitive forte.',
                recommendation='Simplifier ≠ tout enlever : structure et priorise.',
                evidence={'link_count': len(links)},
                score_delta=-6,
            ))
        return {
            'scan_completed': True,
            'link_count': len(links),
            'findings': findings,
            'summary': f'links={len(links)}',
        }

    def tool_accessibility_basics(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Bases a11y qui impactent l'UX."""
        soup = ctx['soup']
        imgs = soup.find_all('img')
        missing_alt = [i for i in imgs if not (i.get('alt') or '').strip() and not i.get('role') == 'presentation']
        findings: List[Dict[str, Any]] = []
        if missing_alt:
            findings.append(self._finding(
                tool='accessibility_basics',
                chapter=6,
                severity='medium',
                title='Images sans alt',
                message=f'{len(missing_alt)}/{len(imgs)} images sans alternative textuelle.',
                recommendation='Alt descriptifs pour compréhension et confiance.',
                evidence={'missing_alt': len(missing_alt), 'img_total': len(imgs)},
                score_delta=-6,
            ))
        lang = soup.html.get('lang') if soup.html else None
        if not lang:
            findings.append(self._finding(
                tool='accessibility_basics',
                chapter=6,
                severity='low',
                title='Attribut lang manquant',
                message='Balise html sans lang — lecture / SEO / a11y dégradés.',
                recommendation='Ajoute lang="fr" (ou la langue du site).',
                score_delta=-3,
            ))
        return {
            'scan_completed': True,
            'missing_alt': len(missing_alt),
            'lang': lang,
            'findings': findings,
            'summary': f'missing_alt={len(missing_alt)}',
        }

    def tool_corpus_principle_match(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Rattache chaque finding à des citations / règles sur tout le corpus."""
        if not self.tools.get('corpus_principle_match'):
            return {'error': 'Corpus indisponible', 'scan_completed': False}
        prior: List[Dict[str, Any]] = ctx.get('findings_so_far') or []
        enriched = []
        for f in prior:
            matched = self.corpus.match_finding(f, limit=5)
            # Enrichit le finding en place pour le résultat final
            f['corpus_refs'] = [
                h.get('title') for h in (matched.get('hits') or []) if h.get('title')
            ] or f.get('corpus_refs') or []
            f['corpus_quotes'] = [
                {
                    'source': h.get('title'),
                    'excerpt': h.get('excerpt'),
                    'score': h.get('score'),
                }
                for h in (matched.get('hits') or [])[:3]
            ]
            f['corpus_rules'] = [
                {'rule': r.get('rule'), 'source': r.get('source_title')}
                for r in (matched.get('rules') or [])[:3]
            ]
            f['corpus_best_quote'] = matched.get('best_quote')
            f['corpus_best_source'] = matched.get('best_source')
            f['corpus_docs_scanned'] = matched.get('corpus_docs_scanned')
            enriched.append({
                'finding_title': f.get('title'),
                'chapter': f.get('chapter'),
                'hits_count': len(matched.get('hits') or []),
                'rules_count': len(matched.get('rules') or []),
                'best_source': matched.get('best_source'),
                'corpus_hits': matched.get('hits') or [],
            })
        return {
            'scan_completed': True,
            'matches': enriched,
            'findings': [],
            'summary': (
                f'{len(enriched)} findings matchés sur '
                f'{self.corpus.get_stats().get("transcript_count", 0)} transcripts'
            ),
        }

    # ------------------------------------------------------------------
    # Orchestrateur
    # ------------------------------------------------------------------

    def _default_options(self) -> Dict[str, bool]:
        """Options par défaut : tous les outils ON sauf probes lourds optionnels."""
        opts = {name: True for name in self.tools}
        return opts

    def analyze_ux(
        self,
        url: str,
        options: Optional[Dict[str, bool]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Lance l'analyse UX complète sur une URL.

        @param url: Site à analyser.
        @param options: Dict outil -> bool (défaut : tout activé).
        @param progress_callback: Callback message de progression.
        @returns: Dict score, findings, tools_results, corpus, summary.
        @example
            >>> UXAnalyzer().analyze_ux('https://example.com')
        """
        def prog(msg: str) -> None:
            if progress_callback:
                try:
                    progress_callback(msg)
                except Exception:
                    pass

        opts = self._default_options()
        if options:
            opts.update({k: bool(v) for k, v in options.items()})

        prog('Chargement du corpus @clea_ux…')
        self.corpus.ensure_loaded()

        prog(f'Téléchargement de {url}…')
        html, soup, meta = self._fetch(url)
        if soup is None:
            return {
                'error': meta.get('error') or 'Impossible de charger la page',
                'url': url,
                'meta': meta,
                'score': 0,
                'findings': [],
            }

        text = self._page_text(soup)
        ctx: Dict[str, Any] = {
            'url': url,
            'html': html,
            'soup': soup,
            'text': text,
            'meta': meta,
            'findings_so_far': [],
        }

        tool_map: List[Tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = [
            ('corpus_index', self.tool_corpus_index),
            ('chapter_map', self.tool_chapter_map),
            ('corpus_search', self.tool_corpus_search),
            ('corpus_rules_extract', self.tool_corpus_rules_extract),
            ('page_corpus_relevance', self.tool_page_corpus_relevance),
            ('hick_law', self.tool_hick_law),
            ('ctv_call_to_value', self.tool_ctv_call_to_value),
            ('contrast_pricing', self.tool_contrast_pricing),
            ('loss_aversion', self.tool_loss_aversion),
            ('hero_clarity', self.tool_hero_clarity),
            ('onboarding_flow', self.tool_onboarding_flow),
            ('time_to_value', self.tool_time_to_value),
            ('aha_moment', self.tool_aha_moment),
            ('error_guidance', self.tool_error_guidance),
            ('empty_states', self.tool_empty_states),
            ('navigation_sidebar', self.tool_navigation_sidebar),
            ('friction_forms', self.tool_friction_forms),
            ('adaptive_persona', self.tool_adaptive_persona),
            ('social_proof', self.tool_social_proof),
            ('paywall_vitrine', self.tool_paywall_vitrine),
            ('peak_end', self.tool_peak_end),
            ('zeigarnik_progress', self.tool_zeigarnik_progress),
            ('gamification', self.tool_gamification),
            ('search_experience', self.tool_search_experience),
            ('mobile_viewport', self.tool_mobile_viewport),
            ('notification_patterns', self.tool_notification_patterns),
            ('trust_consistency', self.tool_trust_consistency),
            ('dashboard_necessity', self.tool_dashboard_necessity),
            ('fogg_behavior', self.tool_fogg_behavior),
            ('retention_signals', self.tool_retention_signals),
            ('feature_adoption', self.tool_feature_adoption),
            ('microcopy_validation', self.tool_microcopy_validation),
            ('phantom_modals', self.tool_phantom_modals),
            ('heading_hierarchy', self.tool_heading_hierarchy),
            ('link_density', self.tool_link_density),
            ('accessibility_basics', self.tool_accessibility_basics),
            ('corpus_principle_match', self.tool_corpus_principle_match),
        ]

        tools_results: Dict[str, Any] = {}
        all_findings: List[Dict[str, Any]] = []
        total = sum(1 for name, _ in tool_map if opts.get(name, False))
        done = 0

        for name, fn in tool_map:
            if not opts.get(name, False):
                continue
            if not self.tools.get(name, True) and name.startswith('corpus'):
                tools_results[name] = {'error': 'outil indisponible', 'scan_completed': False}
                continue
            prog(f'Outil UX « {name} »…')
            try:
                ctx['findings_so_far'] = list(all_findings)
                result = fn(ctx)
            except Exception as exc:
                logger.exception('Outil UX %s échoué', name)
                result = {'error': str(exc), 'scan_completed': False, 'findings': []}
            tools_results[name] = {k: v for k, v in result.items() if k != 'findings'}
            for f in result.get('findings') or []:
                all_findings.append(f)
            # garder aussi findings dans tools_results pour debug
            tools_results[name]['findings_count'] = len(result.get('findings') or [])
            done += 1
            if total:
                prog(f'Progression UX {done}/{total}')

        score = self._calculate_score(all_findings)
        summary = self._build_summary(all_findings, score)

        return {
            'url': url,
            'final_url': meta.get('final_url'),
            'status_code': meta.get('status_code'),
            'score': score,
            'findings': all_findings,
            'issues': all_findings,  # alias SEO-like
            'tools_results': tools_results,
            'tools_run': [n for n, _ in tool_map if opts.get(n)],
            'corpus': self.corpus.build_knowledge_pack() if self.tools.get('corpus_index') else {},
            'rules_grid': (
                self.corpus.get_rules_grid(limit_per_chapter=5)
                if self.tools.get('corpus_rules_extract')
                else {}
            ),
            'summary': summary,
            'diagnostic': self.get_diagnostic(),
        }

    def _calculate_score(self, findings: List[Dict[str, Any]]) -> int:
        """Score 0–100 à partir des score_delta (base 78)."""
        score = 78
        for f in findings:
            try:
                score += int(f.get('score_delta') or 0)
            except (TypeError, ValueError):
                pass
            sev = f.get('severity')
            if sev == 'high':
                score -= 2
            elif sev == 'medium':
                score -= 1
        return max(0, min(100, score))

    def _build_summary(self, findings: List[Dict[str, Any]], score: int) -> Dict[str, Any]:
        """Résumé agrégé pour UI / PDF."""
        by_sev = {'high': 0, 'medium': 0, 'low': 0}
        by_chapter: Dict[int, int] = {}
        for f in findings:
            sev = f.get('severity') or 'low'
            by_sev[sev] = by_sev.get(sev, 0) + 1
            ch = f.get('chapter')
            if ch:
                by_chapter[ch] = by_chapter.get(ch, 0) + 1
        top = sorted(
            findings,
            key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x.get('severity'), 3),
        )[:5]
        return {
            'score': score,
            'findings_count': len(findings),
            'by_severity': by_sev,
            'by_chapter': by_chapter,
            'top_issues': [
                {'title': t.get('title'), 'severity': t.get('severity'), 'tool': t.get('tool')}
                for t in top
            ],
            'verdict': (
                'UX solide (corpus clea_ux)'
                if score >= 75
                else 'UX à améliorer'
                if score >= 50
                else 'UX à risque — frictions majeures'
            ),
        }
