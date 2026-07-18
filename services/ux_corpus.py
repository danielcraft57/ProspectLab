"""
Corpus UX @clea_ux — indexation complète des transcripts TikTok.

Charge tous les .txt non vides, construit un index de tokens, extrait une
grille de règles actionnables, et expose un matching findings ↔ corpus entier.
"""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Chapitres du playbook clea_ux (juillet 2026) — grille de référence
CLEA_UX_CHAPTERS: List[Dict[str, Any]] = [
    {
        'id': 1,
        'slug': 'onboarding',
        'title': 'Onboarding & action clé',
        'principle': 'Parcours à rebours depuis le moment de valeur',
        'keywords': ['onboarding', 'action clé', 'inscription', 'tutoriel', 'étape', 'micro-victoire'],
    },
    {
        'id': 2,
        'slug': 'time_to_value',
        'title': 'Time to Value',
        'principle': 'Résultat d\'abord, config ensuite',
        'keywords': ['time to value', 'ttv', '2 minutes', 'première valeur', 'preuve de valeur', 'résultat'],
    },
    {
        'id': 3,
        'slug': 'aha_moment',
        'title': 'Aha moment',
        'principle': 'La promesse doit devenir visible',
        'keywords': ['aha', 'aha moment', 'valeur visible', 'upgrade', 'promesse'],
    },
    {
        'id': 4,
        'slug': 'landing_ctv',
        'title': 'Landing & CTV',
        'principle': 'Promettre un résultat, pas une action',
        'keywords': ['ctv', 'call to value', 'cta', 'landing', 'contraste', 'aversion', 'conversion'],
    },
    {
        'id': 5,
        'slug': 'navigation_hick',
        'title': 'Navigation & Hick',
        'principle': 'Max 7 choix au même niveau',
        'keywords': ['hick', 'sidebar', 'choix', 'navigation', 'menu', 'décision'],
    },
    {
        'id': 6,
        'slug': 'friction',
        'title': 'Friction utile / toxique',
        'principle': 'Système 1 vs système 2',
        'keywords': ['friction', 'système 1', 'édition fantôme', 'validation', 'effort'],
    },
    {
        'id': 7,
        'slug': 'adaptive_ux',
        'title': 'UX adaptative',
        'principle': 'Un parcours par profil',
        'keywords': ['cible', 'persona', 'profil', 'deux cibles', 'segment'],
    },
    {
        'id': 8,
        'slug': 'errors',
        'title': 'Erreurs & validation',
        'principle': 'Expliquer + CTA immédiat',
        'keywords': ['erreur', 'blocage', 'validation', '404', 'expliquer'],
    },
    {
        'id': 9,
        'slug': 'empty_search',
        'title': 'Empty states & recherche',
        'principle': 'Jamais face au vide',
        'keywords': ['empty', 'recherche', 'dashboard', 'no data', 'zéro résultat', 'vide'],
    },
    {
        'id': 10,
        'slug': 'notifications',
        'title': 'Notifications',
        'principle': 'Une action, au bon moment',
        'keywords': ['notification', 'relance', 'fenêtre d\'intention', 'email'],
    },
    {
        'id': 11,
        'slug': 'paywall',
        'title': 'Paywall & trial',
        'principle': 'Vitrine, pas cadenas',
        'keywords': ['paywall', 'cadenas', 'vitrine', 'trial', 'upgrade', 'pricing', 'tarif'],
    },
    {
        'id': 12,
        'slug': 'retention',
        'title': 'Rétention & fidélisation',
        'principle': 'Réparer avant de scaler',
        'keywords': ['rétention', 'fidélisation', 'peak-end', 'ikea', 'churn'],
    },
    {
        'id': 13,
        'slug': 'gamification',
        'title': 'Gamification & progression',
        'principle': 'Déblocage, pas badges',
        'keywords': ['gamification', 'zeigarnik', 'progression', 'badge', 'déblocage'],
    },
    {
        'id': 14,
        'slug': 'method_analytics',
        'title': 'Méthode & analytics',
        'principle': 'Données + UX = diagnostic',
        'keywords': ['analytics', 'méthode', 'diagnostic', 'données', 'mesure'],
    },
]

# Phrases-conseil typiques dans les transcripts clea_ux
_RULE_START = re.compile(
    r'^(?:donc|alors|le mieux|il faut|tu dois|tu peux|pense à|arrête|commence|'
    r'évite|ajoute|montre|réduis|garde|mets|choisis|remplace|utilise|'
    r'une bonne|un bon|l\'idée|le truc|règle|principe)',
    re.I,
)
_STOPWORDS = {
    'les', 'des', 'une', 'un', 'le', 'la', 'de', 'du', 'et', 'en', 'au', 'aux',
    'pour', 'pas', 'que', 'qui', 'dans', 'sur', 'par', 'est', 'sont', 'avec',
    'plus', 'tout', 'tous', 'ton', 'ta', 'tes', 'son', 'sa', 'ses', 'ce', 'cette',
    'ces', 'il', 'elle', 'ils', 'elles', 'tu', 'vous', 'nous', 'oui', 'non',
    'mais', 'ou', 'donc', 'car', 'comme', 'très', 'bien', 'fait', 'faire',
    'être', 'avoir', 'peut', 'peuvent', 'ça', 'c\'est', 'd\'un', 'd\'une',
}


@dataclass
class TranscriptDoc:
    """Document transcript indexé (texte + métadonnées)."""

    path: str
    title: str
    text: str
    chapters: List[int] = field(default_factory=list)
    word_count: int = 0
    rules: List[str] = field(default_factory=list)
    tokens: Set[str] = field(default_factory=set)


class UXCorpus:
    """
    Index local des transcripts @clea_ux.

    Charge tous les .txt non vides, indexe les tokens, extrait des règles
    actionnables, et permet un matching findings ↔ corpus entier.
    """

    def __init__(self, transcripts_dir: Optional[str] = None):
        """
        Initialise le corpus.

        @param transcripts_dir: Dossier des transcripts (.txt/.json/.srt).
            Défaut : UX_TRANSCRIPTS_DIR ou chemin Windows local tiktokUX.
        """
        self.transcripts_dir = Path(
            transcripts_dir
            or os.environ.get('UX_TRANSCRIPTS_DIR')
            or r'C:\Users\loicDaniel\Videos\tiktokUX\transcripts'
        )
        self.docs: List[TranscriptDoc] = []
        self.skipped_empty: List[str] = []
        self.rules_by_chapter: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self._token_index: Dict[str, Set[int]] = defaultdict(set)
        self._loaded = False
        self._load_error: Optional[str] = None

    def ensure_loaded(self) -> bool:
        """
        Charge le corpus une fois (idempotent).

        @returns: True si au moins un transcript est indexé.
        """
        if self._loaded:
            return len(self.docs) > 0
        self._loaded = True
        try:
            self._index_directory()
            self._build_token_index()
            self._build_rules_grid()
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning('Chargement corpus UX échoué: %s', exc)
            return False
        return len(self.docs) > 0

    def _index_directory(self) -> None:
        """Parcourt le dossier et indexe chaque .txt non vide."""
        if not self.transcripts_dir.is_dir():
            self._load_error = f'Dossier introuvable: {self.transcripts_dir}'
            logger.warning(self._load_error)
            return

        txt_files = sorted(self.transcripts_dir.glob('*.txt'))
        for path in txt_files:
            try:
                text = path.read_text(encoding='utf-8', errors='replace').strip()
            except OSError:
                continue
            if not text:
                self.skipped_empty.append(path.name)
                continue
            title = path.stem
            blob = f'{title}\n{text}'
            chapters = self._infer_chapters(blob)
            tokens = self._tokenize(blob)
            rules = self._extract_rules_from_text(text)
            self.docs.append(
                TranscriptDoc(
                    path=str(path),
                    title=title,
                    text=text,
                    chapters=chapters,
                    word_count=len(text.split()),
                    rules=rules,
                    tokens=tokens,
                )
            )
        logger.info(
            'Corpus UX indexé: %s transcripts (%s vides ignorés) depuis %s',
            len(self.docs),
            len(self.skipped_empty),
            self.transcripts_dir,
        )

    def _build_token_index(self) -> None:
        """Construit l'index inversé token -> indices de docs."""
        self._token_index.clear()
        for idx, doc in enumerate(self.docs):
            for tok in doc.tokens:
                self._token_index[tok].add(idx)

    def _build_rules_grid(self) -> None:
        """Agrège les règles extraites par chapitre (tous les transcripts)."""
        self.rules_by_chapter = defaultdict(list)
        seen_per_ch: Dict[int, Set[str]] = defaultdict(set)
        for doc in self.docs:
            chapter_ids = doc.chapters or [0]
            for rule in doc.rules:
                key = rule.lower()[:120]
                for cid in chapter_ids:
                    if key in seen_per_ch[cid]:
                        continue
                    seen_per_ch[cid].add(key)
                    self.rules_by_chapter[cid].append({
                        'rule': rule,
                        'source_title': doc.title,
                        'source_path': doc.path,
                        'chapter': cid,
                    })

    @staticmethod
    def _tokenize(blob: str) -> Set[str]:
        """Tokenise un texte (minuscules, hors stopwords courts)."""
        raw = re.split(r'\W+', (blob or '').lower())
        return {t for t in raw if len(t) > 2 and t not in _STOPWORDS}

    @staticmethod
    def _infer_chapters(blob: str) -> List[int]:
        """Rattache un texte aux chapitres via mots-clés."""
        low = blob.lower()
        found: List[int] = []
        for ch in CLEA_UX_CHAPTERS:
            if any(kw.lower() in low for kw in ch['keywords']):
                found.append(ch['id'])
        return found

    @classmethod
    def _extract_rules_from_text(cls, text: str) -> List[str]:
        """
        Extrait des phrases-conseil actionnables d'un transcript.

        @param text: Corps du transcript.
        @returns: Liste de règles (max ~12 par vidéo).
        """
        # Découpe phrases (point / point d'interrogation / point d'exclamation)
        parts = re.split(r'(?<=[.!?])\s+', text.replace('\n', ' '))
        rules: List[str] = []
        for part in parts:
            s = ' '.join(part.split()).strip(' «»"\'')
            if len(s) < 35 or len(s) > 280:
                continue
            if _RULE_START.search(s) or re.search(
                r'\b(il faut|tu dois|arrête|commence par|le mieux|règle|principe|'
                r'au lieu de|plutôt que|ne .* pas)\b',
                s,
                re.I,
            ):
                rules.append(s)
            if len(rules) >= 12:
                break
        return rules

    def get_stats(self) -> Dict[str, Any]:
        """
        Statistiques du corpus.

        @returns: Compteurs transcripts, mots, chapitres, règles, fichiers vides.
        """
        self.ensure_loaded()
        chapter_hits: Dict[int, int] = {c['id']: 0 for c in CLEA_UX_CHAPTERS}
        for doc in self.docs:
            for cid in doc.chapters:
                chapter_hits[cid] = chapter_hits.get(cid, 0) + 1
        rules_total = sum(len(v) for v in self.rules_by_chapter.values())
        return {
            'transcripts_dir': str(self.transcripts_dir),
            'transcript_count': len(self.docs),
            'transcripts_on_disk_txt': len(self.docs) + len(self.skipped_empty),
            'skipped_empty': list(self.skipped_empty),
            'total_words': sum(d.word_count for d in self.docs),
            'rules_extracted': rules_total,
            'token_index_size': len(self._token_index),
            'coverage_ratio': (
                round(len(self.docs) / max(1, len(self.docs) + len(self.skipped_empty)), 4)
            ),
            'load_error': self._load_error,
            'chapters': [
                {
                    **ch,
                    'transcript_hits': chapter_hits.get(ch['id'], 0),
                    'rules_count': len(self.rules_by_chapter.get(ch['id'], [])),
                }
                for ch in CLEA_UX_CHAPTERS
            ],
        }

    def search(self, query: str, *, limit: int = 8, chapter: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Recherche plein texte sur tout le corpus (index de tokens).

        @param query: Mots à chercher.
        @param limit: Nombre max de résultats.
        @param chapter: Filtre optionnel sur un chapitre.
        @returns: Liste de hits {title, excerpt, score, chapters, path, matched_tokens}.
        """
        self.ensure_loaded()
        tokens = [t for t in self._tokenize(query or '')]
        if not tokens:
            # fallback tokens bruts si tout filtré
            tokens = [t for t in re.split(r'\W+', (query or '').lower()) if len(t) > 2]
        if not tokens:
            return []

        candidate_idxs: Optional[Set[int]] = None
        for tok in tokens:
            idxs = self._token_index.get(tok) or set()
            if candidate_idxs is None:
                candidate_idxs = set(idxs)
            else:
                # Union pour recall (OR), scoring gère la précision
                candidate_idxs |= idxs
        if not candidate_idxs:
            # Fallback scan linéaire si tokens absents de l'index
            candidate_idxs = set(range(len(self.docs)))

        scored: List[Tuple[float, TranscriptDoc, str, List[str]]] = []
        for idx in candidate_idxs:
            doc = self.docs[idx]
            if chapter is not None and chapter not in doc.chapters:
                continue
            matched = [t for t in tokens if t in doc.tokens]
            if not matched:
                # check substring for multi-word phrases leftover in query
                low = f'{doc.title}\n{doc.text}'.lower()
                matched = [t for t in tokens if t in low]
            if not matched:
                continue
            score = len(matched) / len(tokens)
            if len(matched) == len(tokens):
                score += 0.5
            # Bonus titre
            title_low = doc.title.lower()
            score += 0.15 * sum(1 for t in matched if t in title_low)
            # Bonus chapitre exact
            if chapter is not None and chapter in doc.chapters:
                score += 0.2
            needle = matched[0]
            excerpt = self._excerpt_around(doc.text, needle)
            scored.append((score, doc, excerpt, matched))

        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[Dict[str, Any]] = []
        for score, doc, excerpt, matched in scored[:limit]:
            out.append({
                'title': doc.title,
                'excerpt': excerpt,
                'score': round(score, 3),
                'chapters': doc.chapters,
                'path': doc.path,
                'word_count': doc.word_count,
                'matched_tokens': matched,
            })
        return out

    def match_finding(
        self,
        finding: Dict[str, Any],
        *,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Match un finding contre l'intégralité du corpus.

        @param finding: Dict finding (title, message, recommendation, chapter…).
        @param limit: Max citations / règles.
        @returns: Dict {hits, rules, query_used, corpus_coverage}.
        """
        self.ensure_loaded()
        chapter = finding.get('chapter')
        parts = [
            finding.get('title') or '',
            finding.get('message') or '',
            finding.get('recommendation') or '',
            finding.get('chapter_title') or '',
            finding.get('principle') or '',
            finding.get('tool') or '',
        ]
        ch = next((c for c in CLEA_UX_CHAPTERS if c['id'] == chapter), None)
        if ch:
            parts.extend(ch.get('keywords') or [])
        query = ' '.join(p for p in parts if p)
        hits = self.search(query, limit=limit, chapter=int(chapter) if chapter else None)
        # Si filtre chapitre trop strict, élargir
        if len(hits) < 2:
            hits = self.search(query, limit=limit, chapter=None)

        rules: List[Dict[str, Any]] = []
        if chapter:
            for rule in self.rules_by_chapter.get(int(chapter), [])[:limit]:
                rules.append(rule)
        # Compléter avec règles des hits
        if len(rules) < limit:
            for hit in hits:
                doc = next((d for d in self.docs if d.path == hit.get('path')), None)
                if not doc:
                    continue
                for r in doc.rules[:2]:
                    rules.append({
                        'rule': r,
                        'source_title': doc.title,
                        'source_path': doc.path,
                        'chapter': chapter,
                    })
                    if len(rules) >= limit:
                        break
                if len(rules) >= limit:
                    break

        return {
            'query_used': query[:240],
            'hits': hits,
            'rules': rules[:limit],
            'corpus_docs_scanned': len(self.docs),
            'best_quote': (hits[0]['excerpt'] if hits else None),
            'best_source': (hits[0]['title'] if hits else None),
        }

    def score_page_against_corpus(
        self,
        page_text: str,
        *,
        limit_per_chapter: int = 3,
    ) -> Dict[str, Any]:
        """
        Croise le contenu d'une page avec tout le corpus, chapitre par chapitre.

        @param page_text: Texte visible de la page.
        @param limit_per_chapter: Hits max par chapitre.
        @returns: Dict relevances + top gaps (chapitres peu couverts sur la page).
        """
        self.ensure_loaded()
        page_tokens = self._tokenize(page_text or '')
        relevances: List[Dict[str, Any]] = []
        for ch in CLEA_UX_CHAPTERS:
            # Docs du chapitre
            chapter_docs = [d for d in self.docs if ch['id'] in d.chapters]
            if not chapter_docs:
                continue
            # Overlap moyen page ↔ transcripts du chapitre
            overlaps = []
            top_docs = []
            for doc in chapter_docs:
                if not doc.tokens:
                    continue
                inter = page_tokens & doc.tokens
                if not inter:
                    continue
                ov = len(inter) / max(1, min(len(page_tokens), len(doc.tokens)))
                overlaps.append(ov)
                top_docs.append((ov, doc, sorted(inter)[:8]))
            top_docs.sort(key=lambda x: x[0], reverse=True)
            avg = sum(overlaps) / len(overlaps) if overlaps else 0.0
            kw_present = sum(1 for kw in ch['keywords'] if kw.lower() in (page_text or '').lower())
            relevances.append({
                'chapter': ch['id'],
                'title': ch['title'],
                'principle': ch['principle'],
                'transcripts_in_chapter': len(chapter_docs),
                'overlap_score': round(avg, 4),
                'keyword_hits': kw_present,
                'top_matches': [
                    {
                        'title': d.title,
                        'overlap': round(ov, 4),
                        'shared_tokens': toks,
                        'excerpt': self._excerpt_around(d.text, toks[0] if toks else 'ux'),
                    }
                    for ov, d, toks in top_docs[:limit_per_chapter]
                ],
            })

        relevances.sort(key=lambda x: (x['overlap_score'], x['keyword_hits']))
        gaps = [r for r in relevances if r['overlap_score'] < 0.02 and r['keyword_hits'] == 0][:5]
        strengths = sorted(relevances, key=lambda x: x['overlap_score'], reverse=True)[:5]
        return {
            'corpus_docs': len(self.docs),
            'page_token_count': len(page_tokens),
            'by_chapter': relevances,
            'gaps': gaps,
            'strengths': strengths,
        }

    def get_rules_grid(self, *, limit_per_chapter: int = 8) -> Dict[str, Any]:
        """
        Grille de règles extraites de tous les transcripts, par chapitre.

        @param limit_per_chapter: Max règles par chapitre.
        @returns: Dict chapters -> rules + compteurs.
        """
        self.ensure_loaded()
        chapters_out = []
        total = 0
        for ch in CLEA_UX_CHAPTERS:
            rules = self.rules_by_chapter.get(ch['id'], [])[:limit_per_chapter]
            total += len(self.rules_by_chapter.get(ch['id'], []))
            chapters_out.append({
                **ch,
                'rules': rules,
                'rules_total': len(self.rules_by_chapter.get(ch['id'], [])),
            })
        return {
            'source': '@clea_ux',
            'transcript_count': len(self.docs),
            'rules_total': total,
            'chapters': chapters_out,
        }

    @staticmethod
    def _excerpt_around(text: str, needle: str, *, radius: int = 140) -> str:
        """Extrait un passage autour du premier mot trouvé."""
        low = text.lower()
        idx = low.find((needle or '').lower())
        if idx < 0:
            return (text[: radius * 2] + '…') if len(text) > radius * 2 else text
        start = max(0, idx - radius)
        end = min(len(text), idx + len(needle) + radius)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = '…' + snippet
        if end < len(text):
            snippet = snippet + '…'
        return snippet

    def refs_for_chapter(self, chapter_id: int, *, limit: int = 5) -> List[str]:
        """
        Titres de transcripts rattachés à un chapitre.

        @param chapter_id: Numéro de chapitre (1–14).
        @param limit: Nombre max de titres.
        @returns: Liste de titres.
        """
        self.ensure_loaded()
        titles = [d.title for d in self.docs if chapter_id in d.chapters]
        return titles[:limit]

    def principle_for_tool(self, chapter_slug: str) -> Optional[Dict[str, Any]]:
        """
        Retourne le chapitre correspondant à un slug d'outil.

        @param chapter_slug: Slug (ex. landing_ctv).
        @returns: Dict chapitre ou None.
        """
        for ch in CLEA_UX_CHAPTERS:
            if ch['slug'] == chapter_slug:
                return ch
        return None

    def build_knowledge_pack(self) -> Dict[str, Any]:
        """
        Pack compact pour le prompt d'audit / diagnostic.

        @returns: Stats + principes + citations + règles échantillon.
        """
        stats = self.get_stats()
        samples: List[Dict[str, Any]] = []
        for ch in CLEA_UX_CHAPTERS:
            refs = self.refs_for_chapter(ch['id'], limit=3)
            if not refs:
                continue
            hit = self.search(ch['keywords'][0], limit=1, chapter=ch['id'])
            chapter_rules = self.rules_by_chapter.get(ch['id'], [])[:3]
            samples.append({
                'chapter': ch['id'],
                'title': ch['title'],
                'principle': ch['principle'],
                'transcript_examples': refs,
                'quote': (hit[0]['excerpt'] if hit else None),
                'rules_sample': [r['rule'] for r in chapter_rules],
            })
        return {
            'source': '@clea_ux',
            'stats': {
                'transcript_count': stats['transcript_count'],
                'transcripts_on_disk_txt': stats['transcripts_on_disk_txt'],
                'skipped_empty': stats['skipped_empty'],
                'total_words': stats['total_words'],
                'rules_extracted': stats['rules_extracted'],
                'coverage_ratio': stats['coverage_ratio'],
                'transcripts_dir': stats['transcripts_dir'],
            },
            'chapters': CLEA_UX_CHAPTERS,
            'samples': samples,
            'rules_grid_summary': {
                cid: len(rules) for cid, rules in self.rules_by_chapter.items()
            },
        }


# Singleton lazy pour éviter de réindexer à chaque outil
_CORPUS: Optional[UXCorpus] = None
_CORPUS_DIR: Optional[str] = None


def get_ux_corpus(transcripts_dir: Optional[str] = None) -> UXCorpus:
    """
    Retourne l'instance partagée du corpus UX.

    @param transcripts_dir: Override du dossier (réinitialise si différent).
    @returns: UXCorpus prêt à l'emploi.
    """
    global _CORPUS, _CORPUS_DIR
    if transcripts_dir:
        path = str(transcripts_dir)
        if _CORPUS is None or _CORPUS_DIR != path:
            _CORPUS = UXCorpus(path)
            _CORPUS_DIR = path
        return _CORPUS
    if _CORPUS is None:
        _CORPUS = UXCorpus()
        _CORPUS_DIR = str(_CORPUS.transcripts_dir)
    return _CORPUS


def reset_ux_corpus() -> None:
    """Réinitialise le singleton (tests / reload transcripts)."""
    global _CORPUS, _CORPUS_DIR
    _CORPUS = None
    _CORPUS_DIR = None
