/**
 * Gestion du scraper emails
 */

(function() {
    'use strict';
    
    // Récupérer les paramètres depuis l'URL
    const urlParams = new URLSearchParams(window.location.search);
    const url = urlParams.get('url');
    const entrepriseId = urlParams.get('entreprise_id') ? parseInt(urlParams.get('entreprise_id')) : null;
    const autoStart = urlParams.get('auto_start') === 'true';
    
    // Pré-remplir le formulaire si des paramètres sont présents
    if (url) {
        const urlInput = document.getElementById('emails-url');
        if (urlInput) {
            urlInput.value = url;
        }
    }
    
    if (entrepriseId) {
        const entrepriseIdInput = document.getElementById('emails-entreprise-id');
        if (entrepriseIdInput) {
            entrepriseIdInput.value = entrepriseId;
        }
    }
    
    // Fonction utilitaire pour échapper le HTML
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    const emailsForm = document.getElementById('scrape-emails-form');
    if (emailsForm) {
        emailsForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('emails-url').value;
            const maxDepth = parseInt(document.getElementById('emails-max-depth').value) || 3;
            const maxWorkers = parseInt(document.getElementById('emails-max-workers').value) || 5;
            const maxTime = parseInt(document.getElementById('emails-max-time').value) || 300;
            const entrepriseIdValue = document.getElementById('emails-entreprise-id').value ? parseInt(document.getElementById('emails-entreprise-id').value) : null;
            
            if (!url) {
                showStatus('Veuillez entrer une URL', 'error');
                return;
            }
            
            startEmailsScraping(url, maxDepth, maxWorkers, maxTime, entrepriseIdValue);
        });
    }
    
    // Lancer automatiquement si autoStart est true
    if (autoStart && url) {
        setTimeout(() => {
            emailsForm?.dispatchEvent(new Event('submit'));
        }, 500);
        // Nettoyer l'URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    function startEmailsScraping(url, maxDepth, maxWorkers, maxTime, entrepriseId) {
        const statusDiv = document.getElementById('emails-scrape-status');
        const resultsDiv = document.getElementById('emails-scrape-results');
        const emailsList = document.getElementById('emails-list');
        const btnStart = document.getElementById('btn-start-emails-scraping');
        const btnStop = document.getElementById('btn-stop-emails-scraping');
        
        btnStart.disabled = true;
        btnStop.style.display = 'inline-block';
        showStatus('Connexion au serveur...', 'info');
        resultsDiv.style.display = 'none';
        emailsList.innerHTML = '';
        
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_scraping', {
                url: url,
                max_depth: maxDepth,
                max_workers: maxWorkers,
                max_time: maxTime,
                entreprise_id: entrepriseId
            });
            
            // Écouter les événements
            window.wsManager.socket.on('scraping_started', (data) => {
                showStatus(data.message || 'Scraping démarré...', 'info');
                resultsDiv.style.display = 'block';
            });
            
            window.wsManager.socket.on('scraping_progress', (data) => {
                showStatus(`${data.visited || 0} pages visitées, ${data.emails || 0} emails trouvés`, 'info');
            });
            
            window.wsManager.socket.on('scraping_email_found', (data) => {
                addEmailToList(emailsList, data.email, data.analysis);
            });
            
            window.wsManager.socket.on('scraping_complete', (data) => {
                showStatus(`Scraping terminé ! ${data.total_emails || 0} emails trouvés`, 'success');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('scraping_error', (data) => {
                showStatus(`Erreur: ${data.error || 'Erreur inconnue'}`, 'error');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
        }
    }
    
    document.getElementById('btn-stop-emails-scraping')?.addEventListener('click', () => {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('stop_scraping');
        }
    });
    
    function showStatus(message, statusType) {
        const statusDiv = document.getElementById('emails-scrape-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `status-message status-${statusType}`;
            statusDiv.style.display = 'block';
        }
    }
    
    function addEmailToList(container, email, analysis) {
        const emailCard = document.createElement('div');
        emailCard.className = 'email-card';
        emailCard.style.cssText = 'padding: 1rem; margin-bottom: 1rem; border: 1px solid #ddd; border-radius: 8px; background: white;';
        emailCard.innerHTML = `
            <div style="font-weight: bold; color: #333; margin-bottom: 0.5rem;">
                ${escapeHtml(email)}
            </div>
            ${analysis ? `
                <div style="font-size: 0.9rem; color: #666;">
                    ${analysis.type ? `<span class="badge">${escapeHtml(analysis.type)}</span>` : ''}
                    ${analysis.provider ? `<span class="badge">${escapeHtml(analysis.provider)}</span>` : ''}
                </div>
            ` : '<div style="color: #999; font-size: 0.9rem;">Analyse en cours...</div>'}
        `;
        container.appendChild(emailCard);
    }
})();

