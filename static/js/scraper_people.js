/**
 * Gestion du scraper personnes
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
        const urlInput = document.getElementById('people-url');
        if (urlInput) {
            urlInput.value = url;
        }
    }
    
    if (entrepriseId) {
        const entrepriseIdInput = document.getElementById('people-entreprise-id');
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
    
    const peopleForm = document.getElementById('scrape-people-form');
    if (peopleForm) {
        peopleForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('people-url').value;
            const maxPages = parseInt(document.getElementById('people-max-pages').value) || 20;
            const maxDepth = parseInt(document.getElementById('people-max-depth').value) || 3;
            const entrepriseIdValue = document.getElementById('people-entreprise-id').value ? parseInt(document.getElementById('people-entreprise-id').value) : null;
            
            if (!url) {
                showStatus('Veuillez entrer une URL', 'error');
                return;
            }
            
            startPeopleScraping(url, maxPages, maxDepth, entrepriseIdValue);
        });
    }
    
    // Lancer automatiquement si autoStart est true
    if (autoStart && url) {
        setTimeout(() => {
            peopleForm?.dispatchEvent(new Event('submit'));
        }, 500);
        // Nettoyer l'URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    function startPeopleScraping(url, maxPages, maxDepth, entrepriseId) {
        const statusDiv = document.getElementById('people-scrape-status');
        const resultsDiv = document.getElementById('people-scrape-results');
        const peopleList = document.getElementById('people-list');
        const btnStart = document.getElementById('btn-start-people-scraping');
        const btnStop = document.getElementById('btn-stop-people-scraping');
        
        btnStart.disabled = true;
        btnStop.style.display = 'inline-block';
        showStatus('Connexion au serveur...', 'info');
        resultsDiv.style.display = 'none';
        peopleList.innerHTML = '';
        
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_people_scraping', {
                url: url,
                max_pages: maxPages,
                max_depth: maxDepth,
                entreprise_id: entrepriseId
            });
            
            // Écouter les événements
            window.wsManager.socket.on('people_scraping_started', (data) => {
                showStatus(data.message || 'Scraping démarré...', 'info');
                resultsDiv.style.display = 'block';
            });
            
            window.wsManager.socket.on('people_scraping_progress', (data) => {
                showStatus(data.message || 'Scraping en cours...', 'info');
                // Afficher progressivement les personnes trouvées
                if (data.people && data.people.length > 0) {
                    displayPeople(peopleList, data.people, true);
                }
            });
            
            window.wsManager.socket.on('people_scraping_complete', (data) => {
                showStatus(`Scraping terminé ! ${data.total_people || 0} personnes trouvées`, 'success');
                displayPeople(peopleList, data.people || [], false);
                allPeople = [];
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('people_scraping_error', (data) => {
                showStatus(`Erreur: ${data.error || 'Erreur inconnue'}`, 'error');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('people_scraping_stopping', (data) => {
                showStatus(data.message || 'Arrêt en cours...', 'warning');
            });
        }
    }
    
    document.getElementById('btn-stop-people-scraping')?.addEventListener('click', () => {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('stop_people_scraping');
        }
    });
    
    function showStatus(message, statusType) {
        const statusDiv = document.getElementById('people-scrape-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `status-message status-${statusType}`;
            statusDiv.style.display = 'block';
        }
    }
    
    let allPeople = [];
    
    function displayPeople(container, people, append = false) {
        if (!people || people.length === 0) {
            if (!append) {
                container.innerHTML = '<p>Aucune personne trouvée.</p>';
            }
            return;
        }
        
        if (append) {
            // Ajouter seulement les nouvelles personnes
            people.forEach(person => {
                const nameLower = (person.name || '').toLowerCase();
                if (!allPeople.find(p => (p.name || '').toLowerCase() === nameLower)) {
                    allPeople.push(person);
                }
            });
        } else {
            allPeople = people;
        }
        
        container.innerHTML = allPeople.map(person => `
            <div class="person-card">
                <h4>${escapeHtml(person.name || 'Nom inconnu')}</h4>
                ${person.title ? `<div class="person-title">${escapeHtml(person.title)}</div>` : ''}
                ${person.email ? `<div class="person-info"><strong>Email:</strong> <a href="mailto:${escapeHtml(person.email)}">${escapeHtml(person.email)}</a></div>` : ''}
                ${person.linkedin_url ? `<div class="person-info"><strong>LinkedIn:</strong> <a href="${escapeHtml(person.linkedin_url)}" target="_blank">Voir le profil</a></div>` : ''}
                ${person.phone ? `<div class="person-info"><strong>Téléphone:</strong> ${escapeHtml(person.phone)}</div>` : ''}
                ${person.page_url ? `<div class="person-info"><strong>Source:</strong> <a href="${escapeHtml(person.page_url)}" target="_blank">${escapeHtml(person.page_url)}</a></div>` : ''}
            </div>
        `).join('');
    }
})();

