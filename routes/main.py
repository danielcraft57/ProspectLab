"""
Blueprint pour les routes principales de l'application

Contient toutes les routes qui affichent des pages HTML.
"""

from flask import Blueprint, render_template, redirect, url_for

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """
    Redirection vers le dashboard (nouvelle page d'accueil)
    
    Returns:
        Response: Redirection vers le dashboard
    """
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
def dashboard():
    """
    Dashboard avec statistiques
    
    Returns:
        str: Template HTML du dashboard
    """
    return render_template('dashboard.html')


@main_bp.route('/entreprises')
def liste_entreprises():
    """
    Page de liste des entreprises avec filtres
    
    Returns:
        str: Template HTML de la liste des entreprises
    """
    return render_template('entreprises.html')


@main_bp.route('/entreprise/<int:entreprise_id>')
def entreprise_detail(entreprise_id):
    """
    Page de détail d'une entreprise
    
    Args:
        entreprise_id (int): ID de l'entreprise
        
    Returns:
        str: Template HTML du détail de l'entreprise
    """
    return render_template('entreprise_detail.html', entreprise_id=entreprise_id)


@main_bp.route('/analyses-techniques')
def liste_analyses_techniques():
    """
    Page de liste des analyses techniques
    
    Returns:
        str: Template HTML de la liste des analyses techniques
    """
    return render_template('analyses_techniques.html')


@main_bp.route('/analyses-osint')
def liste_analyses_osint():
    """
    Page de liste des analyses OSINT
    
    Returns:
        str: Template HTML de la liste des analyses OSINT
    """
    return render_template('analyses_osint.html')


@main_bp.route('/analyses-pentest')
def liste_analyses_pentest():
    """
    Page de liste des analyses Pentest
    
    Returns:
        str: Template HTML de la liste des analyses Pentest
    """
    return render_template('analyses_pentest.html')


@main_bp.route('/carte-entreprises')
def carte_entreprises():
    """
    Page de visualisation cartographique des entreprises
    
    Returns:
        str: Template HTML de la carte des entreprises
    """
    return render_template('carte_entreprises.html')


@main_bp.route('/analyse-technique/<int:analysis_id>')
def analyse_technique_detail(analysis_id):
    """
    Page de détail d'une analyse technique
    
    Args:
        analysis_id (int): ID de l'analyse technique
        
    Returns:
        str: Template HTML du détail de l'analyse technique
    """
    return render_template('analyse_technique_detail.html', analysis_id=analysis_id)

