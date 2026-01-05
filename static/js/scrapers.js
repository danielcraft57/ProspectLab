/**
 * Gestion des scrapers (emails et personnes)
 */

(function() {
    'use strict';
    
    // Gestion des onglets
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.getAttribute('data-tab');
            
            // Désactiver tous les onglets
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => {
                content.classList.remove('active');
                content.style.display = 'none';
            });
            
            // Activer l'onglet sélectionné
            button.classList.add('active');
            const targetContent = document.getElementById(`tab-${targetTab}`);
            if (targetContent) {
                targetContent.classList.add('active');
                targetContent.style.display = 'block';
            }
        });
    });
    
    // Fonction utilitaire pour échapper le HTML
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // ========== SCRAPER EMAILS ==========
    const emailsForm = document.getElementById('scrape-emails-form');
    if (emailsForm) {
        emailsForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('emails-url').value;
            const maxDepth = parseInt(document.getElementById('emails-max-depth').value) || 3;
            const maxWorkers = parseInt(document.getElementById('emails-max-workers').value) || 5;
            const maxTime = parseInt(document.getElementById('emails-max-time').value) || 300;
            
            if (!url) {
                showStatus('emails', 'Veuillez entrer une URL', 'error');
                return;
            }
            
            startEmailsScraping(url, maxDepth, maxWorkers, maxTime);
        });
    }
    
    function startEmailsScraping(url, maxDepth, maxWorkers, maxTime) {
        const statusDiv = document.getElementById('emails-scrape-status');
        const resultsDiv = document.getElementById('emails-scrape-results');
        const emailsList = document.getElementById('emails-list');
        const btnStart = document.getElementById('btn-start-emails-scraping');
        const btnStop = document.getElementById('btn-stop-emails-scraping');
        
        btnStart.disabled = true;
        btnStop.style.display = 'inline-block';
        showStatus('emails', 'Connexion au serveur...', 'info');
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
                showStatus('emails', data.message || 'Scraping démarré...', 'info');
                resultsDiv.style.display = 'block';
            });
            
            window.wsManager.socket.on('scraping_progress', (data) => {
                showStatus('emails', `${data.visited || 0} pages visitées, ${data.emails || 0} emails trouvés`, 'info');
            });
            
            window.wsManager.socket.on('scraping_email_found', (data) => {
                addEmailToList(emailsList, data.email, data.analysis);
            });
            
            window.wsManager.socket.on('scraping_complete', (data) => {
                showStatus('emails', `Scraping terminé ! ${data.total_emails || 0} emails trouvés`, 'success');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('scraping_error', (data) => {
                showStatus('emails', `Erreur: ${data.error || 'Erreur inconnue'}`, 'error');
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
    
    // ========== SCRAPER PERSONNES ==========
    const peopleForm = document.getElementById('scrape-people-form');
    if (peopleForm) {
        peopleForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('people-url').value;
            const maxPages = parseInt(document.getElementById('people-max-pages').value) || 20;
            const maxDepth = parseInt(document.getElementById('people-max-depth').value) || 3;
            
            if (!url) {
                showStatus('people', 'Veuillez entrer une URL', 'error');
                return;
            }
            
            startPeopleScraping(url, maxPages, maxDepth);
        });
    }
    
    function startPeopleScraping(url, maxPages, maxDepth) {
        const statusDiv = document.getElementById('people-scrape-status');
        const resultsDiv = document.getElementById('people-scrape-results');
        const peopleList = document.getElementById('people-list');
        const btnStart = document.getElementById('btn-start-people-scraping');
        const btnStop = document.getElementById('btn-stop-people-scraping');
        
        btnStart.disabled = true;
        btnStop.style.display = 'inline-block';
        showStatus('people', 'Connexion au serveur...', 'info');
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
                showStatus('people', data.message || 'Scraping démarré...', 'info');
                resultsDiv.style.display = 'block';
            });
            
            window.wsManager.socket.on('people_scraping_progress', (data) => {
                showStatus('people', data.message || 'Scraping en cours...', 'info');
            });
            
            window.wsManager.socket.on('people_scraping_complete', (data) => {
                showStatus('people', `Scraping terminé ! ${data.total_people || 0} personnes trouvées`, 'success');
                displayPeople(peopleList, data.people || []);
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('people_scraping_error', (data) => {
                showStatus('people', `Erreur: ${data.error || 'Erreur inconnue'}`, 'error');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
        }
    }
    
    document.getElementById('btn-stop-people-scraping')?.addEventListener('click', () => {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('stop_people_scraping');
        }
    });
    
    // ========== SCRAPER COMPLET ==========
    const bothForm = document.getElementById('scrape-both-form');
    if (bothForm) {
        bothForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('both-url').value;
            const maxPages = parseInt(document.getElementById('both-max-pages').value) || 20;
            const maxDepth = parseInt(document.getElementById('both-max-depth').value) || 3;
            const maxWorkers = parseInt(document.getElementById('both-max-workers').value) || 5;
            const maxTime = parseInt(document.getElementById('both-max-time').value) || 300;
            
            if (!url) {
                showStatus('both', 'Veuillez entrer une URL', 'error');
                return;
            }
            
            startBothScraping(url, maxPages, maxDepth, maxWorkers, maxTime);
        });
    }
    
    function startBothScraping(url, maxPages, maxDepth, maxWorkers, maxTime) {
        // Lancer les deux scrapers en parallèle
        startEmailsScraping(url, maxDepth, maxWorkers, maxTime);
        startPeopleScraping(url, maxPages, maxDepth);
    }
    
    // ========== FONCTIONS UTILITAIRES ==========
    function showStatus(type, message, statusType) {
        const statusDiv = document.getElementById(`${type}-scrape-status`);
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
    
    function displayPeople(container, people) {
        if (!people || people.length === 0) {
            container.innerHTML = '<p>Aucune personne trouvée.</p>';
            return;
        }
        
        container.innerHTML = people.map(person => `
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


