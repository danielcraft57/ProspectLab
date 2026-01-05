/**
 * Gestion du scraper réseaux sociaux
 */

(function() {
    'use strict';
    
    const urlParams = new URLSearchParams(window.location.search);
    const url = urlParams.get('url');
    const entrepriseId = urlParams.get('entreprise_id') ? parseInt(urlParams.get('entreprise_id')) : null;
    const autoStart = urlParams.get('auto_start') === 'true';
    
    if (url) {
        document.getElementById('social-url').value = url;
    }
    if (entrepriseId) {
        document.getElementById('social-entreprise-id').value = entrepriseId;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    const socialForm = document.getElementById('scrape-social-form');
    if (socialForm) {
        socialForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('social-url').value;
            const entrepriseIdValue = document.getElementById('social-entreprise-id').value ? parseInt(document.getElementById('social-entreprise-id').value) : null;
            
            if (!url) {
                showStatus('Veuillez entrer une URL', 'error');
                return;
            }
            
            startSocialScraping(url, entrepriseIdValue);
        });
    }
    
    if (autoStart && url) {
        setTimeout(() => socialForm?.dispatchEvent(new Event('submit')), 500);
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    function startSocialScraping(url, entrepriseId) {
        const statusDiv = document.getElementById('social-scrape-status');
        const resultsDiv = document.getElementById('social-scrape-results');
        const socialList = document.getElementById('social-list');
        const btnStart = document.getElementById('btn-start-social-scraping');
        
        const btnStop = document.getElementById('btn-stop-social-scraping');
        btnStart.disabled = true;
        btnStop.style.display = 'inline-block';
        showStatus('Connexion au serveur...', 'info');
        resultsDiv.style.display = 'none';
        socialList.innerHTML = '';
        
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_social_scraping', {
                url: url,
                entreprise_id: entrepriseId
            });
            
            window.wsManager.socket.on('social_scraping_started', (data) => {
                showStatus(data.message || 'Scraping démarré...', 'info');
                resultsDiv.style.display = 'block';
            });
            
            window.wsManager.socket.on('social_scraping_progress', (data) => {
                showStatus(data.message || 'Scraping en cours...', 'info');
                // Afficher progressivement les réseaux sociaux trouvés
                if (data.social_links && Object.keys(data.social_links).length > 0) {
                    displaySocial(socialList, data.social_links);
                }
            });
            
            window.wsManager.socket.on('social_scraping_complete', (data) => {
                showStatus(`Scraping terminé ! ${data.total_platforms || 0} réseaux sociaux trouvés`, 'success');
                displaySocial(socialList, data.social_links || {});
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('social_scraping_error', (data) => {
                showStatus(`Erreur: ${data.error || 'Erreur inconnue'}`, 'error');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('social_scraping_stopping', (data) => {
                showStatus(data.message || 'Arrêt en cours...', 'warning');
            });
        }
    }
    
    document.getElementById('btn-stop-social-scraping')?.addEventListener('click', () => {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('stop_social_scraping');
        }
    });
    
    function showStatus(message, statusType) {
        const statusDiv = document.getElementById('social-scrape-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `status-message status-${statusType}`;
            statusDiv.style.display = 'block';
        }
    }
    
    function displaySocial(container, socialLinks) {
        if (!socialLinks || Object.keys(socialLinks).length === 0) {
            container.innerHTML = '<p>Aucun réseau social trouvé.</p>';
            return;
        }
        
        const platformNames = {
            'facebook': 'Facebook',
            'twitter': 'Twitter/X',
            'linkedin': 'LinkedIn',
            'instagram': 'Instagram',
            'youtube': 'YouTube',
            'tiktok': 'TikTok',
            'pinterest': 'Pinterest',
            'github': 'GitHub',
            'gitlab': 'GitLab'
        };
        
        let html = '';
        for (const [platform, links] of Object.entries(socialLinks)) {
            const platformName = platformNames[platform] || platform;
            html += `<div style="margin-bottom: 1.5rem;"><h4>${escapeHtml(platformName)}</h4>`;
            links.forEach(link => {
                html += `<div style="padding: 0.5rem; margin-bottom: 0.5rem; border: 1px solid #ddd; border-radius: 4px;">
                    <a href="${escapeHtml(link.url)}" target="_blank">${escapeHtml(link.url)}</a>
                    ${link.text ? `<div style="font-size: 0.85rem; color: #666;">${escapeHtml(link.text)}</div>` : ''}
                </div>`;
            });
            html += '</div>';
        }
        container.innerHTML = html;
    }
})();

