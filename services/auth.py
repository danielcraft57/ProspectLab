"""
Module d'authentification ProspectLab
Gère les utilisateurs, les sessions et la sécurité d'accès
"""

import bcrypt
from functools import wraps
from typing import Optional
from flask import session, redirect, url_for, request, flash
from services.database import Database


class AuthManager:
    """
    Gère l'authentification des utilisateurs.
    Dans la version actuelle de ProspectLab, l'application est
    protégée principalement par la restriction réseau (LAN),
    l'auth par utilisateur est donc désactivée.
    """
    
    def __init__(self):
        """Initialise le gestionnaire d'authentification (DB disponible pour compatibilité)."""
        self.db = Database()
    
    def hash_password(self, password: str) -> str:
        """
        Hash un mot de passe avec bcrypt.
        
        Args:
            password (str): Mot de passe en clair
            
        Returns:
            str: Hash du mot de passe
        """
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Vérifie un mot de passe contre son hash.
        
        Args:
            password (str): Mot de passe en clair
            password_hash (str): Hash du mot de passe
            
        Returns:
            bool: True si le mot de passe correspond
        """
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def create_user(self, username: str, email: str, password: str, is_admin: bool = False) -> int:
        """
        Crée un nouvel utilisateur.
        
        Args:
            username (str): Nom d'utilisateur
            email (str): Email de l'utilisateur
            password (str): Mot de passe en clair
            is_admin (bool): Si True, l'utilisateur est administrateur
            
        Returns:
            int: ID de l'utilisateur créé
            
        Raises:
            ValueError: Si l'utilisateur ou l'email existe déjà
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Vérifier si l'utilisateur existe déjà
        cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if cursor.fetchone():
            conn.close()
            raise ValueError('Un utilisateur avec ce nom ou cet email existe déjà')
        
        # Créer l'utilisateur
        password_hash = self.hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, is_admin, is_active)
            VALUES (?, ?, ?, ?, 1)
        ''', (username, email, password_hash, 1 if is_admin else 0))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return user_id
    
    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """
        Authentifie un utilisateur.
        
        Args:
            username (str): Nom d'utilisateur ou email
            password (str): Mot de passe
            
        Returns:
            dict|None: Dictionnaire avec les infos de l'utilisateur si authentifié, None sinon
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Chercher par username ou email
        cursor.execute('''
            SELECT id, username, email, password_hash, is_admin, is_active
            FROM users
            WHERE (username = ? OR email = ?) AND is_active = 1
        ''', (username, username))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return None
        
        user_dict = {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'password_hash': user[3],
            'is_admin': bool(user[4]),
            'is_active': bool(user[5])
        }
        
        # Vérifier le mot de passe
        if not self.verify_password(password, user_dict['password_hash']):
            return None
        
        # Mettre à jour la dernière connexion
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET derniere_connexion = CURRENT_TIMESTAMP WHERE id = ?
        ''', (user_dict['id'],))
        conn.commit()
        conn.close()
        
        return user_dict
    
    def get_user(self, user_id: int) -> Optional[dict]:
        """
        Récupère un utilisateur par son ID.
        
        Args:
            user_id (int): ID de l'utilisateur
            
        Returns:
            dict|None: Dictionnaire avec les infos de l'utilisateur, None si non trouvé
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, email, is_admin, is_active
            FROM users
            WHERE id = ? AND is_active = 1
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return None
        
        return {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'is_admin': bool(user[3]),
            'is_active': bool(user[4])
        }
    
    def login_user(self, user: dict):
        """
        Connecte un utilisateur (met à jour la session).
        
        Args:
            user (dict): Dictionnaire avec les infos de l'utilisateur
        """
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = user['is_admin']
        session.permanent = True  # Session permanente
    
    def logout_user(self):
        """
        Déconnecte l'utilisateur (vide la session).
        """
        session.clear()
    
    def is_authenticated(self) -> bool:
        """
        Indique si l'utilisateur est authentifié.
        
        Dans la configuration actuelle, l'accès est limité au réseau local
        (voir RESTRICT_TO_LOCAL_NETWORK) et on considère donc que toute
        requête autorisée au niveau réseau est "authentifiée".
        
        Returns:
            bool: Toujours True (auth désactivée)
        """
        return True
    
    def get_current_user(self) -> Optional[dict]:
        """
        Récupère l'utilisateur actuellement connecté.
        
        Returns:
            dict|None: Dictionnaire avec les infos de l'utilisateur, None si non connecté
        """
        if not self.is_authenticated():
            return None
        
        return self.get_user(session['user_id'])
    
    def require_admin(self):
        """
        Vérifie si l'utilisateur est administrateur.
        
        Dans la configuration actuelle sans authentification utilisateur,
        on considère que toute personne ayant accès à l'application
        (donc au réseau interne) peut accéder aux fonctions admin.
        
        Returns:
            bool: Toujours True
        """
        return True


def login_required(f):
    """
    Decorator pour protéger une route.
    
    Dans la nouvelle configuration sans login, ce décorateur
    est conservé pour compatibilité mais ne bloque plus l'accès.
    
    Usage:
        @auth_bp.route('/dashboard')
        @login_required
        def dashboard():
            return render_template('dashboard.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Auth désactivée: on laisse simplement passer la requête.
        return f(*args, **kwargs)
    
    return decorated_function


def admin_required(f):
    """
    Decorator pour protéger une route "admin".
    
    Dans la nouvelle configuration sans gestion de rôles, ce décorateur
    est conservé pour compatibilité mais ne restreint plus l'accès.
    L'accès est supposé déjà filtré par le réseau interne.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Auth / rôles désactivés: on laisse passer la requête.
        return f(*args, **kwargs)
    
    return decorated_function

