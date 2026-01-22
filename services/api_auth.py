"""
Module d'authentification API publique
Gère les tokens API pour l'accès aux données depuis des applications externes
"""

import secrets
from functools import wraps
from typing import Optional
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
            str: Token API (32 caractères hexadécimaux)
        """
        return secrets.token_urlsafe(32)
    
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
        
        cursor.execute('''
            INSERT INTO api_tokens 
            (token, name, app_url, user_id, is_active, can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
        ''', (
            token, 
            name, 
            app_url, 
            user_id,
            1 if can_read_entreprises else 0,
            1 if can_read_emails else 0,
            1 if can_read_statistics else 0,
            1 if can_read_campagnes else 0
        ))
        
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
    
    def validate_token(self, token: str) -> Optional[dict]:
        """
        Valide un token API et retourne ses informations.
        
        Args:
            token (str): Token à valider
            
        Returns:
            dict|None: Informations du token si valide, None sinon
        """
        conn = self.db.get_connection()
        conn.row_factory = lambda cursor, row: {
            'id': row[0],
            'token': row[1],
            'name': row[2],
            'app_url': row[3],
            'user_id': row[4],
            'is_active': bool(row[5]),
            'can_read_entreprises': bool(row[6]),
            'can_read_emails': bool(row[7]),
            'can_read_statistics': bool(row[8]),
            'can_read_campagnes': bool(row[9]),
            'date_creation': row[10],
            'last_used': row[11]
        }
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, token, name, app_url, user_id, is_active, 
                   can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes,
                   date_creation, last_used
            FROM api_tokens
            WHERE token = ? AND is_active = 1
        ''', (token,))
        
        token_data = cursor.fetchone()
        
        if token_data:
            # Mettre à jour la dernière utilisation
            cursor.execute('''
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
        conn.row_factory = lambda cursor, row: {
            'id': row[0],
            'token': row[1][:8] + '...' if row[1] else None,  # Masquer le token complet
            'name': row[2],
            'app_url': row[3],
            'user_id': row[4],
            'is_active': bool(row[5]),
            'can_read_entreprises': bool(row[6]),
            'can_read_emails': bool(row[7]),
            'can_read_statistics': bool(row[8]),
            'can_read_campagnes': bool(row[9]),
            'date_creation': row[10],
            'last_used': row[11]
        }
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT id, token, name, app_url, user_id, is_active,
                       can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes,
                       date_creation, last_used
                FROM api_tokens
                WHERE user_id = ?
                ORDER BY date_creation DESC
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT id, token, name, app_url, user_id, is_active,
                       can_read_entreprises, can_read_emails, can_read_statistics, can_read_campagnes,
                       date_creation, last_used
                FROM api_tokens
                ORDER BY date_creation DESC
            ''')
        
        tokens = cursor.fetchall()
        conn.close()
        return tokens
    
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
        
        cursor.execute('''
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
        
        cursor.execute('DELETE FROM api_tokens WHERE id = ?', (token_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted


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

