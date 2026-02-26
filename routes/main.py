"""
Blueprint pour les routes principales de l'application

Contient toutes les routes qui affichent des pages HTML.
"""

from flask import Blueprint, redirect, url_for
from utils.template_helpers import render_page
from services.auth import login_required

main_bp = Blueprint('main', __name__)


@main_bp.route('/home')
@login_required
def home():
    """
    Page d'accueil après connexion.
    Redirige vers le dashboard principal.
    
    Returns:
        Response: Redirection vers le dashboard
    """
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard avec statistiques
    
    Returns:
        str: Template HTML du dashboard
    """
    return render_page('dashboard.html')


@main_bp.route('/entreprises')
@login_required
def liste_entreprises():
    """
    Page de liste des entreprises avec filtres
    
    Returns:
        str: Template HTML de la liste des entreprises
    """
    return render_page('entreprises.html')


@main_bp.route('/entreprise/<int:entreprise_id>')
@login_required
def entreprise_detail(entreprise_id):
    """
    Page de détail d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        str: Template HTML du détail de l'entreprise
    """
    return render_page('entreprise_detail.html', entreprise_id=entreprise_id)


@main_bp.route('/analyses-techniques')
@login_required
def liste_analyses_techniques():
    """
    Page de liste des analyses techniques
    
    Returns:
        str: Template HTML de la liste des analyses techniques
    """
    return render_page('analyses_techniques.html')


@main_bp.route('/analyses-osint')
@login_required
def liste_analyses_osint():
    """
    Page de liste des analyses OSINT
    
    Returns:
        str: Template HTML de la liste des analyses OSINT
    """
    return render_page('analyses_osint.html')


@main_bp.route('/analyses-pentest')
@login_required
def liste_analyses_pentest():
    """
    Page de liste des analyses Pentest
    
    Returns:
        str: Template HTML de la liste des analyses Pentest
    """
    return render_page('analyses_pentest.html')


@main_bp.route('/analyses-seo')
@login_required
def liste_analyses_seo():
    """
    Page de liste des analyses SEO
    
    Returns:
        str: Template HTML de la liste des analyses SEO
    """
    return render_page('analyses_seo.html')


@main_bp.route('/carte-entreprises')
@login_required
def carte_entreprises():
    """
    Page de visualisation cartographique des entreprises
    
    Returns:
        str: Template HTML de la carte des entreprises
    """
    return render_page('carte_entreprises.html')


@main_bp.route('/analyse-technique/<int:analysis_id>')
@login_required
def analyse_technique_detail(analysis_id):
    """
    Page de détail d'une analyse technique
    
    Args:
        analysis_id (int): ID de l'analyse technique
        
    Returns:
        str: Template HTML du détail de l'analyse technique
    """
    return render_page('analyse_technique_detail.html', analysis_id=analysis_id)

