/**
 * Gestion du scraper métadonnées
 */

(function() {
    'use strict';
    
    const urlParams = new URLSearchParams(window.location.search);
    const url = urlParams.get('url');
    const entrepriseId = urlParams.get('entreprise_id') ? parseInt(urlParams.get('entreprise_id')) : null;
    const autoStart = urlParams.get('auto_start') === 'true';
    
    if (url) {
        document.getElementById('metadata-url').value = url;
    }
    if (entrepriseId) {
        document.getElementById('metadata-entreprise-id').value = entrepriseId;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    const metadataForm = document.getElementById('scrape-metadata-form');
    if (metadataForm) {
        metadataForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('metadata-url').value;
            const entrepriseIdValue = document.getElementById('metadata-entreprise-id').value ? parseInt(document.getElementById('metadata-entreprise-id').value) : null;
            
            if (!url) {
                showStatus('Veuillez entrer une URL', 'error');
                return;
            }
            
            startMetadataScraping(url, entrepriseIdValue);
        });
    }
    
    if (autoStart && url) {
        setTimeout(() => metadataForm?.dispatchEvent(new Event('submit')), 500);
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    function startMetadataScraping(url, entrepriseId) {
        const statusDiv = document.getElementById('metadata-scrape-status');
        const resultsDiv = document.getElementById('metadata-scrape-results');
        const metadataList = document.getElementById('metadata-list');
        const btnStart = document.getElementById('btn-start-metadata-scraping');
        
        btnStart.disabled = true;
        showStatus('Extraction en cours...', 'info');
        resultsDiv.style.display = 'none';
        metadataList.innerHTML = '';
        
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_metadata_scraping', {
                url: url,
                entreprise_id: entrepriseId
            });
            
            window.wsManager.socket.on('metadata_scraping_progress', (data) => {
                showStatus(data.message || 'Extraction en cours...', 'info');
            });
            
            window.wsManager.socket.on('metadata_scraping_complete', (data) => {
                showStatus(`Extraction terminée ! ${data.total_meta_tags || 0} meta tags trouvés`, 'success');
                displayMetadata(metadataList, data.metadata || {});
                btnStart.disabled = false;
            });
            
            window.wsManager.socket.on('metadata_scraping_error', (data) => {
                showStatus(`Erreur: ${data.error || 'Erreur inconnue'}`, 'error');
                btnStart.disabled = false;
            });
        }
    }
    
    function showStatus(message, statusType) {
        const statusDiv = document.getElementById('metadata-scrape-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `status-message status-${statusType}`;
            statusDiv.style.display = 'block';
        }
    }
    
    function displayMetadata(container, metadata) {
        if (!metadata || Object.keys(metadata).length === 0) {
            container.innerHTML = '<p>Aucune métadonnée trouvée.</p>';
            return;
        }
        
        let html = '';
        
        if (metadata.meta_tags) {
            html += '<div style="margin-bottom: 1.5rem;"><h4>Meta Tags</h4><dl>';
            for (const [name, content] of Object.entries(metadata.meta_tags)) {
                html += `<dt><strong>${escapeHtml(name)}:</strong></dt><dd>${escapeHtml(content)}</dd>`;
            }
            html += '</dl></div>';
        }
        
        if (metadata.open_graph && Object.keys(metadata.open_graph).length > 0) {
            html += '<div style="margin-bottom: 1.5rem;"><h4>Open Graph</h4><dl>';
            for (const [name, content] of Object.entries(metadata.open_graph)) {
                html += `<dt><strong>${escapeHtml(name)}:</strong></dt><dd>${escapeHtml(content)}</dd>`;
            }
            html += '</dl></div>';
        }
        
        if (metadata.twitter_cards && Object.keys(metadata.twitter_cards).length > 0) {
            html += '<div style="margin-bottom: 1.5rem;"><h4>Twitter Cards</h4><dl>';
            for (const [name, content] of Object.entries(metadata.twitter_cards)) {
                html += `<dt><strong>${escapeHtml(name)}:</strong></dt><dd>${escapeHtml(content)}</dd>`;
            }
            html += '</dl></div>';
        }
        
        if (metadata.keywords && metadata.keywords.length > 0) {
            html += `<div style="margin-bottom: 1.5rem;"><h4>Mots-clés</h4><p>${metadata.keywords.map(k => escapeHtml(k)).join(', ')}</p></div>`;
        }
        
        if (metadata.language) {
            html += `<div style="margin-bottom: 1.5rem;"><h4>Langue</h4><p>${escapeHtml(metadata.language)}</p></div>`;
        }
        
        container.innerHTML = html || '<p>Aucune métadonnée trouvée.</p>';
    }
})();

