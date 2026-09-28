"""
Rooms Socket.IO stables pour les notifications (survivent au reconnect).

Un client rejoint :
- ``user:{id}`` si session Flask authentifiee
- ``client:{uuid}`` (localStorage navigateur) via l'event ``join_notify_room``

Les monitors Celery doivent appeler :func:`freeze_notify_rooms` au demarrage
(pour garder la room client/user meme si le sid change ensuite).
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# sid Socket.IO -> set de rooms stables (user:…, client:…)
_sid_rooms: Dict[str, Set[str]] = {}

_CLIENT_ID_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')


def client_room(client_id: str) -> str:
    """
    Construit le nom de room pour un client navigateur.

    @param client_id: UUID / token localStorage
    @returns: Room ``client:…``
    """
    return f'client:{client_id}'


def user_room(user_id: int) -> str:
    """
    Construit le nom de room pour un utilisateur logge.

    @param user_id: ID utilisateur ProspectLab
    @returns: Room ``user:…``
    """
    return f'user:{int(user_id)}'


def sanitize_client_id(raw) -> Optional[str]:
    """
    Valide un client_id envoye par le navigateur.

    @param raw: Valeur brute
    @returns: client_id ou None si invalide
    """
    if raw is None:
        return None
    value = str(raw).strip()
    if not _CLIENT_ID_RE.match(value):
        return None
    return value


def register_sid_room(sid: str, room: str) -> None:
    """
    Associe une room stable a un sid (pour freeze ulterieur).

    @param sid: Socket.IO session id
    @param room: Nom de room
    """
    if not sid or not room:
        return
    with _lock:
        bucket = _sid_rooms.setdefault(sid, set())
        bucket.add(room)


def unregister_sid(sid: str) -> None:
    """
    Oublie le mapping sid -> rooms (disconnect).

    @param sid: Socket.IO session id
    """
    if not sid:
        return
    with _lock:
        _sid_rooms.pop(sid, None)


def rooms_for_sid(sid: str) -> List[str]:
    """
    Rooms stables actuellement connues pour un sid.

    @param sid: Socket.IO session id
    @returns: Liste de rooms (sans le sid lui-meme)
    """
    if not sid:
        return []
    with _lock:
        return list(_sid_rooms.get(sid) or ())


def primary_notify_room(sid: Optional[str]) -> Optional[str]:
    """
    Choisit UNE room cible pour eviter les toasts en double.

    Priorite : ``user:`` > ``client:`` > sid.
    (Si on emit vers plusieurs rooms ou le meme socket est membre,
    Socket.IO livre l'event N fois = N notifications.)

    @param sid: request.sid
    @returns: Room unique ou None
    """
    if not sid:
        return None
    stables = rooms_for_sid(sid)
    for prefix in ('user:', 'client:'):
        for room in stables:
            if room.startswith(prefix):
                return room
    return sid


def freeze_notify_rooms(sid: Optional[str]) -> List[str]:
    """
    Snapshot d'emission pour un job long : **une seule** room (stable si possible).

    A appeler au demarrage du handler / avant le monitor, pas a la fin.
    Important : ne pas renvoyer sid + client + user ensemble, sinon le navigateur
    recoit l'event 3-4 fois (membre de toutes ces rooms).

    @param sid: request.sid au moment du lancement
    @returns: Liste d'une room ``[user:…]`` ou ``[client:…]`` ou ``[sid]``
    """
    primary = primary_notify_room(sid)
    return [primary] if primary else []


def normalize_rooms(
    room=None,
    also_rooms: Optional[Iterable[str]] = None,
) -> List[Optional[str]]:
    """
    Normalise room / also_rooms en liste de cibles pour safe_emit.

    Si plusieurs cibles sont passees (ex. ancien freeze multi-rooms), on ne
    garde que la meilleure (user > client > autre) pour eviter les doublons.

    @param room: sid, room stable, ou liste
    @param also_rooms: Rooms supplementaires (ignorees si room suffit)
    @returns: Liste d'au plus une room (ou ``[None]`` = broadcast)
    """
    candidates: List[Optional[str]] = []

    def _push(value) -> None:
        if value is None:
            if None not in candidates:
                candidates.append(None)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                _push(item)
            return
        text = str(value).strip()
        if text and text not in candidates:
            candidates.append(text)

    _push(room)
    if also_rooms is not None:
        _push(also_rooms)

    if not candidates:
        return [None]

    # Broadcast explicite
    if len(candidates) == 1 and candidates[0] is None:
        return [None]

    # Une seule cible : si c'est un sid encore mappe, preferer sa room stable
    if len(candidates) == 1:
        only = candidates[0]
        if isinstance(only, str) and not only.startswith(('user:', 'client:')):
            preferred = primary_notify_room(only)
            return [preferred] if preferred else [only]
        return [only]

    # Plusieurs cibles (legacy) → dedupe en priorite user / client / reste
    for prefix in ('user:', 'client:'):
        for c in candidates:
            if isinstance(c, str) and c.startswith(prefix):
                return [c]
    for c in candidates:
        if c is not None:
            return [c]
    return [None]
