"""
Fonctions utilitaires pour ProspectLab
"""

import os
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


def safe_emit(socketio, event, data, room=None):
    """
    Émet un événement WebSocket de manière sécurisée en gérant les erreurs
    
    Args:
        socketio: Instance de SocketIO
        event (str): Nom de l'événement à émettre
        data (dict): Données à envoyer
        room (str, optional): Room spécifique pour l'émission
        
    Example:
        >>> safe_emit(socketio, 'progress', {'percent': 50}, room='session_123')
    """
    try:
        # Vérifier que socketio est valide
        if not socketio:
            return
        
        # Vérifier que la room existe si spécifiée
        if room:
            try:
                socketio.emit(event, data, room=room)
            except (RuntimeError, ConnectionError, OSError) as e:
                # Erreurs de connexion - client déconnecté ou connexion non établie
                pass
            except Exception:
                # Autres erreurs - ignorer silencieusement
                pass
        else:
            try:
                socketio.emit(event, data)
            except (RuntimeError, ConnectionError, OSError) as e:
                # Erreurs de connexion
                pass
            except Exception:
                # Autres erreurs
                pass
    except Exception:
        # Erreur générale - ignorer
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

