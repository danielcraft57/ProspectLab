"""
Fonctions utilitaires pour ProspectLab
"""

import os
import math
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS


def allowed_file(filename):
    """
    Vérifie si le fichier a une extension autorisée
    
    Args:
        filename (str): Nom du fichier à vérifier
        
    Returns:
        bool: True si l'extension est autorisée, False sinon
        
    Example:
        >>> allowed_file('test.xlsx')
        True
        >>> allowed_file('test.pdf')
        False
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_emit(socketio, event, data, room=None, also_rooms=None):
    """
    Émet un événement WebSocket de manière sécurisée.

    ``room`` peut être un sid, une room stable (``user:`` / ``client:``),
    ou une liste (``freeze_notify_rooms``). Une seule cible est utilisee
    (priorite user > client > sid) pour ne pas multiplier les toasts.

    Args:
        socketio: Instance de SocketIO
        event (str): Nom de l'événement à émettre
        data (dict): Données à envoyer
        room: Room, sid, ou liste de rooms
        also_rooms: Rooms supplémentaires (fusionnées puis dedupliquées)

    Example:
        >>> safe_emit(socketio, 'progress', {'percent': 50}, room='client:abc')
        >>> safe_emit(socketio, 'done', payload, room=freeze_notify_rooms(sid))
    """
    try:
        if not socketio:
            return

        try:
            from utils.ws_rooms import normalize_rooms
            targets = normalize_rooms(room=room, also_rooms=also_rooms)
        except Exception:
            if isinstance(room, (list, tuple, set)):
                targets = list(room)[:1] or [None]
            else:
                targets = [room]

        # Une seule emission (evite N toasts si le client est dans N rooms)
        target = targets[0] if targets else None
        try:
            if target is None:
                socketio.emit(event, data)
            else:
                socketio.emit(event, data, room=target)
        except (RuntimeError, ConnectionError, OSError):
            pass
        except Exception:
            pass
    except Exception:
        pass


def get_file_path(upload_folder, filename):
    """
    Construit le chemin complet d'un fichier uploadé
    
    Args:
        upload_folder (str): Dossier d'upload
        filename (str): Nom du fichier
        
    Returns:
        str: Chemin complet du fichier
        
    Example:
        >>> get_file_path('/uploads', 'test.xlsx')
        '/uploads/test.xlsx'
    """
    return os.path.join(upload_folder, secure_filename(filename))


def clean_json_value(value):
    """
    Convertit les valeurs NaN et Infinity en None pour la sérialisation JSON
    
    Args:
        value: Valeur à nettoyer (peut être de n'importe quel type)
        
    Returns:
        Valeur nettoyée (None si NaN ou Infinity, sinon valeur originale)
        
    Example:
        >>> import math
        >>> clean_json_value(math.nan)
        None
        >>> clean_json_value(5.0)
        5.0
        >>> clean_json_value({'key': math.nan})
        {'key': None}
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def clean_json_dict(data):
    """
    Nettoie récursivement un dictionnaire ou une liste des valeurs NaN et Infinity
    pour la sérialisation JSON
    
    Args:
        data: Données à nettoyer (dict, list, ou valeur simple)
        
    Returns:
        Données nettoyées avec NaN/Infinity remplacés par None
        
    Example:
        >>> import math
        >>> clean_json_dict({'note': math.nan, 'score': 5.0})
        {'note': None, 'score': 5.0}
        >>> clean_json_dict([{'a': math.nan}, {'b': 10}])
        [{'a': None}, {'b': 10}]
    """
    if isinstance(data, dict):
        return {k: clean_json_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json_dict(item) for item in data]
    else:
        return clean_json_value(data)

