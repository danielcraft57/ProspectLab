"""
Blueprint pour l'authentification
Gère les routes de login, logout et page d'accueil
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from services.auth import AuthManager, login_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Page de connexion.
    
    GET: Affiche le formulaire de connexion
    POST: Traite le formulaire et connecte l'utilisateur
    """
    auth_manager = AuthManager()
    
    # Si déjà connecté, rediriger vers la page d'accueil
    if auth_manager.is_authenticated():
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Veuillez remplir tous les champs.', 'error')
            return render_template('login.html')
        
        # Authentifier l'utilisateur
        user = auth_manager.authenticate(username, password)
        
        if user:
            auth_manager.login_user(user)
            flash(f'Bienvenue, {user["username"]} !', 'success')
            
            # Rediriger vers la page demandée ou la page d'accueil
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.home'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')
    
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Déconnexion de l'utilisateur.
    """
    auth_manager = AuthManager()
    username = session.get('username', 'Utilisateur')
    auth_manager.logout_user()
    flash(f'À bientôt, {username} !', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/')
def index():
    """
    Page d'accueil publique (redirige vers login si non connecté, sinon vers home).
    """
    auth_manager = AuthManager()
    
    if auth_manager.is_authenticated():
        return redirect(url_for('main.home'))
    
    return redirect(url_for('auth.login'))

