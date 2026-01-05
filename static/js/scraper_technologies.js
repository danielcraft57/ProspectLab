/**
 * Gestion du scraper technologies
 */

(function() {
    'use strict';
    
    const urlParams = new URLSearchParams(window.location.search);
    const url = urlParams.get('url');
    const entrepriseId = urlParams.get('entreprise_id') ? parseInt(urlParams.get('entreprise_id')) : null;
    const autoStart = urlParams.get('auto_start') === 'true';
    
    if (url) {
        document.getElementById('technologies-url').value = url;
    }
    if (entrepriseId) {
        document.getElementById('technologies-entreprise-id').value = entrepriseId;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    const technologiesForm = document.getElementById('scrape-technologies-form');
    if (technologiesForm) {
        technologiesForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('technologies-url').value;
            const entrepriseIdValue = document.getElementById('technologies-entreprise-id').value ? parseInt(document.getElementById('technologies-entreprise-id').value) : null;
            
            if (!url) {
                showStatus('Veuillez entrer une URL', 'error');
                return;
            }
            
            startTechnologiesScraping(url, entrepriseIdValue);
        });
    }
    
    if (autoStart && url) {
        setTimeout(() => technologiesForm?.dispatchEvent(new Event('submit')), 500);
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    function startTechnologiesScraping(url, entrepriseId) {
        const statusDiv = document.getElementById('technologies-scrape-status');
        const resultsDiv = document.getElementById('technologies-scrape-results');
        const technologiesList = document.getElementById('technologies-list');
        const btnStart = document.getElementById('btn-start-technologies-scraping');
        
        btnStart.disabled = true;
        showStatus('Analyse en cours...', 'info');
        resultsDiv.style.display = 'none';
        technologiesList.innerHTML = '';
        
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_technology_scraping', {
                url: url,
                entreprise_id: entrepriseId
            });
            
            window.wsManager.socket.on('technology_scraping_progress', (data) => {
                showStatus(data.message || 'Analyse en cours...', 'info');
            });
            
            window.wsManager.socket.on('technology_scraping_complete', (data) => {
                showStatus(`Analyse terminée ! ${data.total_technologies || 0} technologies détectées`, 'success');
                displayTechnologies(technologiesList, data.technologies || {});
                btnStart.disabled = false;
            });
            
            window.wsManager.socket.on('technology_scraping_error', (data) => {
                showStatus(`Erreur: ${data.error || 'Erreur inconnue'}`, 'error');
                btnStart.disabled = false;
            });
        }
    }
    
    function showStatus(message, statusType) {
        const statusDiv = document.getElementById('technologies-scrape-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `status-message status-${statusType}`;
            statusDiv.style.display = 'block';
        }
    }
    
    function displayTechnologies(container, technologies) {
        if (!technologies || Object.keys(technologies).length === 0) {
            container.innerHTML = '<p>Aucune technologie détectée.</p>';
            return;
        }
        
        const categoryNames = {
            'cms': 'CMS',
            'framework': 'Framework',
            'server': 'Serveur',
            'language': 'Langage',
            'analytics': 'Analytics',
            'cdn': 'CDN'
        };
        
        let html = '';
        for (const [category, techs] of Object.entries(technologies)) {
            const categoryName = categoryNames[category] || category;
            html += `<div style="margin-bottom: 1.5rem;"><h4>${escapeHtml(categoryName)}</h4><ul>`;
            techs.forEach(tech => {
                html += `<li>${escapeHtml(tech)}</li>`;
            });
            html += '</ul></div>';
        }
        container.innerHTML = html;
    }
})();

