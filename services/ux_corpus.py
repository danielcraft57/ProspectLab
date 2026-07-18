"""
Corpus UX @clea_ux — indexation des transcripts TikTok pour l'analyse UX.

Charge les fichiers .txt / .json du dossier transcripts et expose une base
de principes (14 chapitres du playbook) pour alimenter UXAnalyzer.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Chapitres du playbook clea_ux (juillet 2026) — grille de référence
CLEA_UX_CHAPTERS: List[Dict[str, Any]] = [
    {
        'id': 1,
        'slug': 'onboarding',
        'title': 'Onboarding & action clé',
        'principle': 'Parcours à rebours depuis le moment de valeur',
        'keywords': ['onboarding', 'action clé', 'inscription', 'tutoriel', 'étape'],
    },
    {
        'id': 2,
        'slug': 'time_to_value',
        'title': 'Time to Value',
        'principle': 'Résultat d\'abord, config ensuite',
        'keywords': ['time to value', 'ttv', '2 minutes', 'première valeur', 'preuve de valeur'],
    },
    {
        'id': 3,
        'slug': 'aha_moment',
        'title': 'Aha moment',
        'principle': 'La promesse doit devenir visible',
        'keywords': ['aha', 'aha moment', 'valeur visible', 'upgrade'],
    },
    {
        'id': 4,
        'slug': 'landing_ctv',
        'title': 'Landing & CTV',
        'principle': 'Promettre un résultat, pas une action',
        'keywords': ['ctv', 'call to value', 'cta', 'landing', 'contraste', 'aversion'],
    },
    {
        'id': 5,
        'slug': 'navigation_hick',
        'title': 'Navigation & Hick',
        'principle': 'Max 7 choix au même niveau',
        'keywords': ['hick', 'sidebar', 'choix', 'navigation', 'menu'],
    },
    {
        'id': 6,
        'slug': 'friction',
        'title': 'Friction utile / toxique',
        'principle': 'Système 1 vs système 2',
        'keywords': ['friction', 'système 1', 'édition fantôme', 'validation'],
    },
    {
        'id': 7,
        'slug': 'adaptive_ux',
        'title': 'UX adaptative',
        'principle': 'Un parcours par profil',
        'keywords': ['cible', 'persona', 'profil', 'deux cibles'],
    },
    {
        'id': 8,
        'slug': 'errors',
        'title': 'Erreurs & validation',
        'principle': 'Expliquer + CTA immédiat',
        'keywords': ['erreur', 'blocage', 'validation', '404'],
    },
    {
        'id': 9,
        'slug': 'empty_search',
        'title': 'Empty states & recherche',
        'principle': 'Jamais face au vide',
        'keywords': ['empty', 'recherche', 'dashboard', 'no data', 'zéro résultat'],
    },
    {
        'id': 10,
        'slug': 'notifications',
        'title': 'Notifications',
        'principle': 'Une action, au bon moment',
        'keywords': ['notification', 'relance', 'fenêtre d\'intention'],
    },
    {
        'id': 11,
        'slug': 'paywall',
        'title': 'Paywall & trial',
        'principle': 'Vitrine, pas cadenas',
        'keywords': ['paywall', 'cadenas', 'vitrine', 'trial', 'upgrade', 'pricing'],
    },
    {
        'id': 12,
        'slug': 'retention',
        'title': 'Rétention & fidélisation',
        'principle': 'Réparer avant de scaler',
        'keywords': ['rétention', 'fidélisation', 'peak-end', 'ikea'],
    },
    {
        'id': 13,
        'slug': 'gamification',
        'title': 'Gamification & progression',
        'principle': 'Déblocage, pas badges',
        'keywords': ['gamification', 'zeigarnik', 'progression', 'badge'],
    },
    {
        'id': 14,
        'slug': 'method_analytics',
        'title': 'Méthode & analytics',
        'principle': 'Données + UX = diagnostic',
        'keywords': ['analytics', 'méthode', 'diagnostic', 'données'],
    },
]


@dataclass
class TranscriptDoc:
    """Document transcript indexé (texte + métadonnées)."""

    path: str
    title: str
    text: str
    chapters: List[int] = field(default_factory=list)
    word_count: int = 0


class UXCorpus:
    """
    Index local des transcripts @clea_ux.

    Charge les .txt du dossier transcripts (et métadonnées .json si présentes),
    puis permet recherche plein texte et rattachement aux chapitres.
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
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning('Chargement corpus UX échoué: %s', exc)
            return False
        return len(self.docs) > 0

    def _index_directory(self) -> None:
        """Parcourt le dossier et indexe chaque .txt."""
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
                continue
            title = path.stem
            chapters = self._infer_chapters(f'{title}\n{text}')
            self.docs.append(
                TranscriptDoc(
                    path=str(path),
                    title=title,
                    text=text,
                    chapters=chapters,
                    word_count=len(text.split()),
                )
            )
        logger.info(
            'Corpus UX indexé: %s transcripts depuis %s',
            len(self.docs),
            self.transcripts_dir,
        )

    @staticmethod
    def _infer_chapters(blob: str) -> List[int]:
        """Rattache un texte aux chapitres via mots-clés."""
        low = blob.lower()
        found: List[int] = []
        for ch in CLEA_UX_CHAPTERS:
            if any(kw.lower() in low for kw in ch['keywords']):
                found.append(ch['id'])
        return found

    def get_stats(self) -> Dict[str, Any]:
        """
        Statistiques du corpus.

        @returns: Compteurs transcripts, mots, chapitres couverts, chemin.
        """
        self.ensure_loaded()
        chapter_hits: Dict[int, int] = {c['id']: 0 for c in CLEA_UX_CHAPTERS}
        for doc in self.docs:
            for cid in doc.chapters:
                chapter_hits[cid] = chapter_hits.get(cid, 0) + 1
        return {
            'transcripts_dir': str(self.transcripts_dir),
            'transcript_count': len(self.docs),
            'total_words': sum(d.word_count for d in self.docs),
            'load_error': self._load_error,
            'chapters': [
                {
                    **ch,
                    'transcript_hits': chapter_hits.get(ch['id'], 0),
                }
                for ch in CLEA_UX_CHAPTERS
            ],
        }

    def search(self, query: str, *, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Recherche plein texte simple dans les transcripts.

        @param query: Mots à chercher (AND approximatif sur tokens).
        @param limit: Nombre max de résultats.
        @returns: Liste de hits {title, excerpt, score, chapters, path}.
        """
        self.ensure_loaded()
        tokens = [t for t in re.split(r'\W+', (query or '').lower()) if len(t) > 2]
        if not tokens:
            return []
        scored: List[Tuple[float, TranscriptDoc, str]] = []
        for doc in self.docs:
            low = f'{doc.title}\n{doc.text}'.lower()
            hits = sum(1 for t in tokens if t in low)
            if hits == 0:
                continue
            score = hits / len(tokens)
            # Bonus si tous les tokens sont présents
            if hits == len(tokens):
                score += 0.5
            excerpt = self._excerpt_around(doc.text, tokens[0])
            scored.append((score, doc, excerpt))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[Dict[str, Any]] = []
        for score, doc, excerpt in scored[:limit]:
            out.append({
                'title': doc.title,
                'excerpt': excerpt,
                'score': round(score, 3),
                'chapters': doc.chapters,
                'path': doc.path,
                'word_count': doc.word_count,
            })
        return out

    @staticmethod
    def _excerpt_around(text: str, needle: str, *, radius: int = 120) -> str:
        """Extrait un passage autour du premier mot trouvé."""
        low = text.lower()
        idx = low.find(needle.lower())
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

    def refs_for_chapter(self, chapter_id: int, *, limit: int = 3) -> List[str]:
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

        @returns: Stats + principes + citations échantillon.
        """
        stats = self.get_stats()
        samples: List[Dict[str, Any]] = []
        for ch in CLEA_UX_CHAPTERS:
            refs = self.refs_for_chapter(ch['id'], limit=2)
            if not refs:
                continue
            hit = self.search(ch['keywords'][0], limit=1)
            samples.append({
                'chapter': ch['id'],
                'title': ch['title'],
                'principle': ch['principle'],
                'transcript_examples': refs,
                'quote': (hit[0]['excerpt'] if hit else None),
            })
        return {
            'source': '@clea_ux',
            'stats': {
                'transcript_count': stats['transcript_count'],
                'total_words': stats['total_words'],
                'transcripts_dir': stats['transcripts_dir'],
            },
            'chapters': CLEA_UX_CHAPTERS,
            'samples': samples,
        }


# Singleton lazy pour éviter de réindexer à chaque outil
_CORPUS: Optional[UXCorpus] = None


def get_ux_corpus(transcripts_dir: Optional[str] = None) -> UXCorpus:
    """
    Retourne l'instance partagée du corpus UX.

    @param transcripts_dir: Override du dossier (réinitialise si différent).
    @returns: UXCorpus prêt à l'emploi.
    """
    global _CORPUS
    if transcripts_dir:
        return UXCorpus(transcripts_dir)
    if _CORPUS is None:
        _CORPUS = UXCorpus()
    return _CORPUS
