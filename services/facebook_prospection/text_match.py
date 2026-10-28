"""
Correspondance de noms (port facebook-search.mjs / facebook-actions normalizeText).
"""

from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    """
    Normalise pour comparaison insensible accents / casse.

    @param value: Texte brut
    @returns: Texte normalise minuscule sans accents superflus
    """
    raw = unicodedata.normalize('NFKD', str(value or ''))
    stripped = ''.join(ch for ch in raw if not unicodedata.combining(ch))
    cleaned = re.sub(r'[^\w\s]', ' ', stripped, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', cleaned).strip().lower()


def name_matches(candidate: str, target: str) -> bool:
    """
    True si les noms se recouvrent (inclusion ou mots significatifs communs).

    @param candidate: Nom trouve sur Facebook
    @param target: Nom attendu (entreprise)
    @returns: Correspondance approximative
    """
    a = normalize_text(candidate)
    b = normalize_text(target)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    aw = [w for w in a.split() if len(w) > 3]
    bw = [w for w in b.split() if len(w) > 3]
    if not aw or not bw:
        return False
    overlap = sum(1 for w in aw if any(w in x or x in w for x in bw))
    need = min(2, min(len(aw), len(bw)))
    return overlap >= need


def group_name_score(candidate: str, query: str) -> float:
    """
    Score mot-cle (0..n) inspire groupNameScore.

    @param candidate: Libelle candidat
    @param query: Requete de recherche
    @returns: Nombre de mots longs de la requete presents dans le candidat
    """
    name = normalize_text(candidate)
    words = [w for w in normalize_text(query).split() if len(w) > 3]
    if not words:
        return 0.0
    return float(sum(1 for w in words if w in name))
