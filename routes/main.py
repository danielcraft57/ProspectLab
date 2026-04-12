"""
Blueprint pour les routes principales de l'application

Contient toutes les routes qui affichent des pages HTML.
"""

import os

from flask import Blueprint, redirect, url_for, current_app
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


@main_bp.route('/analyse-concurrence-marche')
@login_required
def analyse_concurrence_marche():
    """
    Vision produit : analyse concurrence et marché, fiche d’idées à activer
    (battlecards, radar gagnable, alertes, A/B commercial).
    """
    return render_page('analyse_concurrence_marche.html')


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


@main_bp.route('/entreprise/<int:entreprise_id>/rapport-audit')
@login_required
def entreprise_rapport_audit(entreprise_id):
    """
    Page de rapport d'audit commercial pour une entreprise.
    Utilise les analyses existantes (technique, SEO, OSINT, Pentest, scraping)
    et le score d'opportunité composite.
    """
    return render_page('entreprise_rapport_audit.html', entreprise_id=entreprise_id)


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


@main_bp.route('/analyse-site-complet')
@login_required
def analyse_site_complet():
    """
    Page unique : saisie d'un site, lancement du pack d'analyses (AJAX + suivi Celery),
    graphiques et aperçu des données persistées en base.
    """
    return render_page('analyse_site_complet.html')


@main_bp.route('/graph-entreprises')
@login_required
def graph_entreprises():
    """
    Graphe des liens entre fiches entreprises et domaines externes (crédits, liens, portfolio).
    """
    return render_page('graph_entreprises.html')


@main_bp.route('/agences-reseau')
@login_required
def agences_reseau_redirect():
    """Ancienne URL « Réseau agences » : redirection vers Graph entreprises."""
    return redirect(url_for('main.graph_entreprises'), code=301)


@main_bp.route('/carte-entreprises')
@login_required
def carte_entreprises():
    """
    Page de visualisation cartographique des entreprises
    
    Returns:
        str: Template HTML de la carte des entreprises
    """
    return render_page('carte_entreprises.html')


@main_bp.route('/entreprises-google-maps')
@login_required
def entreprises_google_maps():
    """
    Page dédiée à l'exploration de prospects via Google Maps.
    Utilise l'API JavaScript Google Maps (Places) côté front.
    """
    api_key = ''
    try:
        if current_app and current_app.config:
            api_key = current_app.config.get('GOOGLE_MAPS_JS_API_KEY') or ''
    except Exception:
        api_key = ''

    if not api_key:
        api_key = os.environ.get('GOOGLE_MAPS_JS_API_KEY', '')

    return render_page('entreprises_google_maps.html', google_maps_api_key=api_key)


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

