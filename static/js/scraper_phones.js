/**
 * Gestion du scraper téléphones
 */

(function() {
    'use strict';
    
    const urlParams = new URLSearchParams(window.location.search);
    const url = urlParams.get('url');
    const entrepriseId = urlParams.get('entreprise_id') ? parseInt(urlParams.get('entreprise_id')) : null;
    const autoStart = urlParams.get('auto_start') === 'true';
    
    if (url) {
        document.getElementById('phones-url').value = url;
    }
    if (entrepriseId) {
        document.getElementById('phones-entreprise-id').value = entrepriseId;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    const phonesForm = document.getElementById('scrape-phones-form');
    if (phonesForm) {
        phonesForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('phones-url').value;
            const maxPages = parseInt(document.getElementById('phones-max-pages').value) || 20;
            const maxDepth = parseInt(document.getElementById('phones-max-depth').value) || 3;
            const entrepriseIdValue = document.getElementById('phones-entreprise-id').value ? parseInt(document.getElementById('phones-entreprise-id').value) : null;
            
            if (!url) {
                showStatus('Veuillez entrer une URL', 'error');
                return;
            }
            
            startPhonesScraping(url, maxPages, maxDepth, entrepriseIdValue);
        });
    }
    
    if (autoStart && url) {
        setTimeout(() => phonesForm?.dispatchEvent(new Event('submit')), 500);
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    function startPhonesScraping(url, maxPages, maxDepth, entrepriseId) {
        const statusDiv = document.getElementById('phones-scrape-status');
        const resultsDiv = document.getElementById('phones-scrape-results');
        const phonesList = document.getElementById('phones-list');
        const btnStart = document.getElementById('btn-start-phones-scraping');
        const btnStop = document.getElementById('btn-stop-phones-scraping');
        
        btnStart.disabled = true;
        btnStop.style.display = 'inline-block';
        showStatus('Connexion au serveur...', 'info');
        resultsDiv.style.display = 'none';
        phonesList.innerHTML = '';
        
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_phone_scraping', {
                url: url,
                max_pages: maxPages,
                max_depth: maxDepth,
                entreprise_id: entrepriseId
            });
            
            window.wsManager.socket.on('phone_scraping_started', (data) => {
                showStatus(data.message || 'Scraping démarré...', 'info');
                resultsDiv.style.display = 'block';
            });
            
            window.wsManager.socket.on('phone_scraping_progress', (data) => {
                showStatus(data.message || 'Scraping en cours...', 'info');
                // Afficher progressivement les téléphones trouvés
                if (data.phones && data.phones.length > 0) {
                    displayPhones(phonesList, data.phones, true);
                }
            });
            
            window.wsManager.socket.on('phone_scraping_complete', (data) => {
                showStatus(`Scraping terminé ! ${data.total_phones || 0} téléphones trouvés`, 'success');
                displayPhones(phonesList, data.phones || [], false);
                allPhones = [];
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('phone_scraping_error', (data) => {
                showStatus(`Erreur: ${data.error || 'Erreur inconnue'}`, 'error');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('phone_scraping_stopping', (data) => {
                showStatus(data.message || 'Arrêt en cours...', 'warning');
            });
        }
    }
    
    document.getElementById('btn-stop-phones-scraping')?.addEventListener('click', () => {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('stop_phone_scraping');
        }
    });
    
    function showStatus(message, statusType) {
        const statusDiv = document.getElementById('phones-scrape-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `status-message status-${statusType}`;
            statusDiv.style.display = 'block';
        }
    }
    
    function displayPhones(container, phones) {
        if (!phones || phones.length === 0) {
            container.innerHTML = '<p>Aucun téléphone trouvé.</p>';
            return;
        }
        
        container.innerHTML = phones.map(phoneData => `
            <div class="phone-card" style="padding: 1rem; margin-bottom: 1rem; border: 1px solid #ddd; border-radius: 8px; background: white;">
                <div style="font-weight: bold; color: #333; margin-bottom: 0.5rem;">
                    <a href="tel:${escapeHtml(phoneData.phone)}">${escapeHtml(phoneData.phone)}</a>
                </div>
                ${phoneData.page_url ? `<div style="font-size: 0.85rem; color: #666;">Source: <a href="${escapeHtml(phoneData.page_url)}" target="_blank">${escapeHtml(phoneData.page_url)}</a></div>` : ''}
            </div>
        `).join('');
    }
})();

