"""
Module d'authentification API publique
Gère les tokens API pour l'accès aux données depuis des applications externes
"""

import secrets
from functools import wraps
from typing import Optional, Dict, Any
from flask import request, jsonify
from services.database import Database


class APITokenManager:
    """
    Gère les tokens API pour l'authentification des requêtes publiques
    """
    
    def __init__(self):
        """Initialise le gestionnaire de tokens API"""
        self.db = Database()
    
    def generate_token(self) -> str:
        """
        Génère un nouveau token API sécurisé.
        
        Returns:
            str: Token API (uniquement lettres/chiffres, sans caractères spéciaux)
        """
        # token_urlsafe() inclut souvent '-' et '_' (pas souhaité ici).
        # token_hex() renvoie uniquement [0-9a-f], donc aucun caractère spécial.
        return secrets.token_hex(32)
    
    def create_token(
        self, 
        name: str, 
        app_url: Optional[str] = None,
        user_id: Optional[int] = None,
        can_read_entreprises: bool = True,
        can_read_emails: bool = True,
        can_read_statistics: bool = True,
        can_read_campagnes: bool = True
    ) -> dict:
        """
        Crée un nouveau token API.
        
        Args:
            name (str): Nom/description du token
            app_url (str|None): URL de l'application qui utilisera le token
            user_id (int|None): ID de l'utilisateur propriétaire (optionnel)
            can_read_entreprises (bool): Permission de lire les entreprises
            can_read_emails (bool): Permission de lire les emails
            can_read_statistics (bool): Permission de lire les statistiques
            
        Returns:
            dict: Dictionnaire avec le token et ses informations
        """
        token = self.generate_token()
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        params = (
            token, 
            name, 
            app_url, 
            user_id,
            1 if can_read_entreprises else 0,
            1 if can_read_emails else 0,
            1 if can_read_statistics else 0,
            1 if can_read_campagnes else 0
        )
        
        # Compatibilité SQLite / PostgreSQL
        if self.db.is_postgresql():
            self.db.execute_sql(cursor, '''
                INSERT INTO api_tokens 
                (token, name, app_url, user_id, is_active, can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                RETURNING id
            ''', params)
            row = cursor.fetchone()
            if isinstance(row, dict):
                token_id = row.get('id')
            else:
                token_id = row[0] if row else None
        else:
            self.db.execute_sql(cursor, '''
                INSERT INTO api_tokens 
                (token, name, app_url, user_id, is_active, can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            ''', params)
            token_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return {
            'id': token_id,
            'token': token,
            'name': name,
            'app_url': app_url,
            'user_id': user_id,
            'is_active': True,
            'can_read_entreprises': can_read_entreprises,
            'can_read_emails': can_read_emails,
            'can_read_statistics': can_read_statistics,
            'can_read_campagnes': can_read_campagnes
        }
    
    def _row_to_token_dict(self, row, mask_token: bool = False) -> dict:
        """Convertit une ligne DB (Row ou RealDictRow) en dict. Compatible SQLite et PostgreSQL."""
        d = dict(row)
        token_val = d.get('token')
        return {
            'id': d.get('id'),
            'token': (token_val[:8] + '...') if mask_token and token_val else token_val,
            'name': d.get('name'),
            'app_url': d.get('app_url'),
            'user_id': d.get('user_id'),
            'is_active': bool(d.get('is_active', 0)),
            'can_read_entreprises': bool(d.get('can_read_entreprises', 0)),
            'can_read_emails': bool(d.get('can_read_emails', 0)),
            'can_read_statistics': bool(d.get('can_read_statistics', 0)),
            'can_read_campagnes': bool(d.get('can_read_campagnes', 0)),
            'date_creation': d.get('date_creation'),
            'last_used': d.get('last_used')
        }
    
    def validate_token(self, token: str) -> Optional[dict]:
        """
        Valide un token API et retourne ses informations.
        
        Args:
            token (str): Token à valider
            
        Returns:
            dict|None: Informations du token si valide, None sinon
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        self.db.execute_sql(cursor, '''
            SELECT id, token, name, app_url, user_id, is_active, 
                   can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes,
                   date_creation, last_used
            FROM api_tokens
            WHERE token = ? AND is_active = 1
        ''', (token,))
        
        row = cursor.fetchone()
        token_data = self._row_to_token_dict(row, mask_token=False) if row else None
        
        if token_data:
            # Mettre à jour la dernière utilisation
            self.db.execute_sql(cursor, '''
                UPDATE api_tokens 
                SET last_used = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (token_data['id'],))
            conn.commit()
        
        conn.close()
        return token_data
    
    def list_tokens(self, user_id: Optional[int] = None) -> list:
        """
        Liste tous les tokens API (ou ceux d'un utilisateur spécifique).
        
        Args:
            user_id (int|None): Filtrer par utilisateur (optionnel)
            
        Returns:
            list: Liste des tokens
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if user_id:
            self.db.execute_sql(cursor, '''
                SELECT id, token, name, app_url, user_id, is_active,
                       can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes,
                       date_creation, last_used
                FROM api_tokens
                WHERE user_id = ?
                ORDER BY date_creation DESC
            ''', (user_id,))
        else:
            self.db.execute_sql(cursor, '''
                SELECT id, token, name, app_url, user_id, is_active,
                       can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes,
                       date_creation, last_used
                FROM api_tokens
                ORDER BY date_creation DESC
            ''')
        
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_token_dict(row, mask_token=True) for row in rows]
    
    def revoke_token(self, token_id: int) -> bool:
        """
        Révoque un token API (le désactive).
        
        Args:
            token_id (int): ID du token à révoquer
            
        Returns:
            bool: True si révoqué, False si non trouvé
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        self.db.execute_sql(cursor, '''
            UPDATE api_tokens 
            SET is_active = 0 
            WHERE id = ?
        ''', (token_id,))
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    def delete_token(self, token_id: int) -> bool:
        """
        Supprime définitivement un token API.
        
        Args:
            token_id (int): ID du token à supprimer
            
        Returns:
            bool: True si supprimé, False si non trouvé
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        self.db.execute_sql(cursor, 'DELETE FROM api_tokens WHERE id = ?', (token_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted


# Mapping logique permission -> champ booléen dans api_tokens
API_PERMISSION_FIELD_MAP = {
    'entreprises': 'can_read_entreprises',
    'emails': 'can_read_emails',
    'statistics': 'can_read_statistics',
    'campagnes': 'can_read_campagnes',
}

class ClientAppManager:
    """
    Gère les applications clientes internes (Facturio, MailPilot, VocalGuard, etc.)
    authentifiées via une clé d'API transmise dans le header `x-api-key`.
    """

    def __init__(self):
        self.db = Database()

    def validate_api_key(self, api_key: str, request_obj=None) -> Optional[Dict[str, Any]]:
        """
        Valide une clé API d'application cliente et met à jour les métadonnées d'usage.

        Args:
            api_key: Clé API reçue (header ou query)
            request_obj: Objet Flask request (optionnel, pour logger IP / endpoint)

        Returns:
            dict|None: Informations de l'application cliente si valide, None sinon
        """
        conn = self.db.get_connection()
        # row_factory déjà configuré dans get_connection()
        cursor = conn.cursor()

        self.db.execute_sql(cursor, '''
            SELECT id, name, api_key, active, description, created_at, last_used, last_ip, last_endpoint, last_status
            FROM application_clients
            WHERE api_key = ? AND active = 1
        ''', (api_key,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        # Supporter à la fois sqlite3.Row et RealDictRow
        app_data = dict(row)

        # Mettre à jour les métadonnées d'usage (logging minimal des appels)
        try:
            client_ip = None
            endpoint = None
            if request_obj is not None:
                client_ip = request_obj.headers.get('X-Forwarded-For') or request_obj.headers.get('X-Real-IP') or request_obj.remote_addr
                endpoint = request_obj.path

            self.db.execute_sql(cursor, '''
                UPDATE application_clients
                SET last_used = CURRENT_TIMESTAMP,
                    last_ip = ?,
                    last_endpoint = ?
                WHERE id = ?
            ''', (client_ip, endpoint, app_data.get('id')))
            conn.commit()
        except Exception:
            # En cas d'erreur de logging, ne pas bloquer l'authentification
            conn.rollback()
        finally:
            conn.close()

        return app_data


def api_token_required(f):
    """
    Decorator pour protéger une route API publique (nécessite un token API valide).
    
    Le token doit être fourni dans :
    - Header : `Authorization: Bearer <token>`
    - Ou paramètre : `?api_token=<token>`
    
    Usage:
        @api_public_bp.route('/entreprises')
        @api_token_required
        def get_entreprises():
            return jsonify(entreprises)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token_manager = APITokenManager()

        # Chercher le token dans le header Authorization
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()

        # Sinon, chercher dans les paramètres de requête
        if not token:
            token = request.args.get('api_token') or request.form.get('api_token')

        if not token:
            return jsonify({
                'error': 'Token API requis',
                'message': 'Fournissez un token API dans le header Authorization: Bearer <token> ou en paramètre ?api_token=<token>'
            }), 401

        # Valider le token
        token_data = token_manager.validate_token(token)

        if not token_data:
            return jsonify({
                'error': 'Token API invalide ou révoqué',
                'message': 'Le token fourni n\'est pas valide ou a été révoqué'
            }), 401

        # Ajouter les infos du token au contexte de la requête
        request.api_token = token_data

        return f(*args, **kwargs)
    
    return decorated_function


def client_api_key_required(f):
    """
    Decorator pour protéger une route d'intégration interne (applications clientes).

    L'application doit fournir une clé API dans :
    - Header : `x-api-key: <clé>`
    - Ou paramètre : `?api_key=<clé>`
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        manager = ClientAppManager()

        # Chercher la clé dans le header x-api-key en priorité
        api_key = request.headers.get('x-api-key')

        # Fallback éventuel via paramètre de requête
        if not api_key:
            api_key = request.args.get('api_key') or request.form.get('api_key')

        if not api_key:
            return jsonify({
                'error': 'Clé API requise',
                'message': 'Fournissez une clé dans le header x-api-key ou le paramètre ?api_key='
            }), 401

        app_data = manager.validate_api_key(api_key, request_obj=request)
        if not app_data:
            return jsonify({
                'error': 'Clé API invalide ou désactivée',
                'message': 'La clé fournie ne correspond à aucune application active'
            }), 401

        # Ajouter l'application cliente au contexte de la requête
        request.client_app = app_data

        return f(*args, **kwargs)

    return decorated_function


def require_api_permission(permission_key: str):
    """
    Decorator à utiliser APRES api_token_required pour vérifier une permission fine.
    
    Exemple:
        @api_public_bp.route('/entreprises')
        @api_token_required
        @require_api_permission('entreprises')
        def get_entreprises():
            ...
    
    Permissions possibles (clé -> champ BDD):
        - 'entreprises' -> can_read_entreprises
        - 'emails'      -> can_read_emails
        - 'statistics'  -> can_read_statistics
        - 'campagnes'   -> can_read_campagnes
    """
    from functools import wraps as _wraps

    def decorator(f):
        @_wraps(f)
        def wrapper(*args, **kwargs):
            token_data = getattr(request, 'api_token', None)
            if not token_data:
                # api_token_required aurait dû être appliqué avant
                return jsonify({
                    'error': 'Configuration API invalide',
                    'message': 'Le décorateur api_token_required doit être appliqué avant require_api_permission.'
                }), 500

            field = API_PERMISSION_FIELD_MAP.get(permission_key)
            if not field:
                # Permission inconnue : mieux vaut bloquer que laisser passer silencieusement
                return jsonify({
                    'error': 'Permission API inconnue',
                    'permission': permission_key
                }), 500

            if not token_data.get(field, False):
                return jsonify({
                    'error': 'Permission API insuffisante',
                    'permission': field,
                    'message': f'Le token API ne dispose pas de la permission requise pour cette ressource ({field}).'
                }), 403

            return f(*args, **kwargs)

        return wrapper

    return decorator

