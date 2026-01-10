/**
 * Gestion de l'analyse/scraping unifié
 */

(function() {
    'use strict';
    
    const form = document.getElementById('scrape-form');
    const statusDiv = document.getElementById('scrape-status');
    const progressDiv = document.getElementById('scrape-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const resultsDiv = document.getElementById('scrape-results');
    const btnStart = document.getElementById('btn-start-scraping');
    const btnStop = document.getElementById('btn-stop-scraping');
    
    // Données collectées
    let collectedData = {
        emails: [],
        people: [],
        phones: [],
        social: {},
        technologies: {},
        metadata: {}
    };
    
    // Gestion des onglets
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');
            
            // Désactiver tous les onglets
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Activer l'onglet sélectionné
            button.classList.add('active');
            document.getElementById(`tab-${tabName}`).classList.add('active');
        });
    });
    
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const url = document.getElementById('scrape-url').value;
            const maxDepth = parseInt(document.getElementById('max-depth').value) || 3;
            const maxWorkers = parseInt(document.getElementById('max-workers').value) || 5;
            const maxTime = parseInt(document.getElementById('max-time').value) || 300;
            const entrepriseId = document.getElementById('entreprise-id').value ? parseInt(document.getElementById('entreprise-id').value) : null;
            
            if (!url) {
                showStatus('Veuillez entrer une URL', 'error');
                return;
            }
            
            startScraping(url, maxDepth, maxWorkers, maxTime, entrepriseId);
        });
    }
    
    if (btnStop) {
        btnStop.addEventListener('click', function() {
            if (window.wsManager && window.wsManager.socket) {
                window.wsManager.socket.emit('stop_scraping');
            }
        });
    }
    
    function startScraping(url, maxDepth, maxWorkers, maxTime, entrepriseId) {
        // Réinitialiser les données
        collectedData = {
            emails: [],
            people: [],
            phones: [],
            social: {},
            technologies: {},
            metadata: {}
        };
        
        btnStart.disabled = true;
        btnStop.style.display = 'inline-block';
        showStatus('Connexion au serveur...', 'info');
        progressDiv.style.display = 'block';
        resultsDiv.style.display = 'block'; // Afficher dès le début
        
        // Réinitialiser les listes
        document.getElementById('emails-list').innerHTML = '<div class="empty-state">Aucun email trouvé pour le moment...</div>';
        document.getElementById('people-list').innerHTML = '<div class="empty-state">Aucune personne trouvée pour le moment...</div>';
        document.getElementById('phones-list').innerHTML = '<div class="empty-state">Aucun téléphone trouvé pour le moment...</div>';
        document.getElementById('social-list').innerHTML = '<div class="empty-state">Aucun réseau social trouvé pour le moment...</div>';
        document.getElementById('technologies-list').innerHTML = '<div class="empty-state">Aucune technologie détectée pour le moment...</div>';
        document.getElementById('metadata-list').innerHTML = '<div class="empty-state">Aucune métadonnée extraite pour le moment...</div>';
        
        // Réinitialiser les compteurs
        updateCount('emails', 0);
        updateCount('people', 0);
        updateCount('phones', 0);
        updateCount('social', 0);
        updateCount('tech', 0);
        
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
                showStatus(data.message || 'Analyse démarrée...', 'info');
                updateProgress(0, 'Initialisation...');
            });
            
            window.wsManager.socket.on('scraping_progress', (data) => {
                const message = data.message || `Page ${data.visited || 0} - ${data.emails || 0} emails, ${data.people || 0} personnes`;
                showStatus(message, 'info');
                updateProgress(
                    Math.min(90, (data.visited || 0) * 2),
                    message
                );
            });
            
            window.wsManager.socket.on('scraping_email_found', (data) => {
                if (!collectedData.emails.includes(data.email)) {
                    collectedData.emails.push(data.email);
                    addEmailToList(data.email, data.analysis);
                    updateCount('emails', collectedData.emails.length);
                }
            });
            
            window.wsManager.socket.on('scraping_person_found', (data) => {
                const person = data.person;
                if (person && !collectedData.people.find(p => p.name === person.name)) {
                    collectedData.people.push(person);
                    addPersonToList(person);
                    updateCount('people', collectedData.people.length);
                }
            });
            
            window.wsManager.socket.on('scraping_phone_found', (data) => {
                if (!collectedData.phones.includes(data.phone)) {
                    collectedData.phones.push(data.phone);
                    addPhoneToList(data.phone);
                    updateCount('phones', collectedData.phones.length);
                }
            });
            
            window.wsManager.socket.on('scraping_social_found', (data) => {
                const platform = data.platform;
                if (!collectedData.social[platform]) {
                    collectedData.social[platform] = [];
                }
                if (!collectedData.social[platform].find(s => s.url === data.url)) {
                    collectedData.social[platform].push({ url: data.url, text: data.text || '' });
                    addSocialToList(platform, data.url);
                    updateCount('social', Object.keys(collectedData.social).length);
                }
            });
            
            window.wsManager.socket.on('scraping_complete', (data) => {
                updateProgress(100, 'Analyse terminée');
                showStatus(`Analyse terminée avec succès ! ${data.total_emails || 0} emails, ${data.total_people || 0} personnes, ${data.total_phones || 0} téléphones`, 'success');
                
                // Mettre à jour les compteurs
                if (data.emails) {
                    updateCount('emails', data.emails.length);
                    data.emails.forEach(email => {
                        if (!collectedData.emails.includes(email)) {
                            collectedData.emails.push(email);
                            addEmailToList(email, null);
                        }
                    });
                }
                
                if (data.people) {
                    updateCount('people', data.people.length);
                    data.people.forEach(person => {
                        if (!collectedData.people.find(p => p.name === person.name)) {
                            collectedData.people.push(person);
                            addPersonToList(person);
                        }
                    });
                }
                
                if (data.phones) {
                    updateCount('phones', data.phones.length);
                    data.phones.forEach(phoneObj => {
                        const phone = phoneObj.phone || phoneObj;
                        if (!collectedData.phones.includes(phone)) {
                            collectedData.phones.push(phone);
                            addPhoneToList(phone);
                        }
                    });
                }
                
                if (data.social_links) {
                    updateCount('social', Object.keys(data.social_links).length);
                    for (const [platform, links] of Object.entries(data.social_links)) {
                        if (!collectedData.social[platform]) {
                            collectedData.social[platform] = [];
                        }
                        links.forEach(linkData => {
                            if (!collectedData.social[platform].find(s => s.url === linkData.url)) {
                                collectedData.social[platform].push(linkData);
                                addSocialToList(platform, linkData.url);
                            }
                        });
                    }
                }
                
                // Afficher technologies et métadonnées
                displayAllResults(data);
                
                // La section résultats est déjà affichée depuis le début
                
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('scraping_stopped', (data) => {
                showStatus('Analyse arrêtée', 'warning');
                updateProgress(0, 'Arrêté');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
            
            window.wsManager.socket.on('scraping_error', (data) => {
                showStatus('Erreur: ' + (data.error || 'Erreur inconnue'), 'error');
                updateProgress(0, 'Erreur');
                btnStart.disabled = false;
                btnStop.style.display = 'none';
            });
        } else {
            showStatus('Erreur: WebSocket non connecté', 'error');
            btnStart.disabled = false;
            btnStop.style.display = 'none';
        }
    }
    
    function showStatus(message, type) {
        if (!statusDiv) return;
        statusDiv.textContent = message;
        statusDiv.className = `status-message status-${type}`;
        statusDiv.style.display = 'block';
    }
    
    function updateProgress(percent, text) {
        if (progressBar) {
            progressBar.style.width = percent + '%';
        }
        if (progressText) {
            progressText.textContent = text || '';
        }
    }
    
    function updateCount(type, count) {
        const countElement = document.getElementById(`count-${type}`);
        if (countElement) {
            countElement.textContent = count;
        }
    }
    
    function addEmailToList(email, analysis) {
        const list = document.getElementById('emails-list');
        if (!list) return;
        
        // Supprimer le message "vide" si présent
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        // Vérifier si l'email n'existe pas déjà
        const existingEmail = Array.from(list.children).find(item => {
            const emailText = item.querySelector('strong')?.textContent;
            return emailText === email;
        });
        if (existingEmail) return;
        
        const item = document.createElement('div');
        item.className = 'result-item email-item';
        item.innerHTML = `
            <div class="result-item-icon">📧</div>
            <div class="result-item-content">
                <div class="result-item-header">
                    <strong class="result-item-title">${escapeHtml(email)}</strong>
                    ${analysis ? `<span class="result-item-badge">${escapeHtml(analysis.format || 'Email')}</span>` : ''}
                </div>
                ${analysis && analysis.provider ? `<div class="result-item-meta">Fournisseur: ${escapeHtml(analysis.provider)}</div>` : ''}
            </div>
        `;
        list.appendChild(item);
        
        // Animation d'apparition
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    }
    
    function addPersonToList(person) {
        const list = document.getElementById('people-list');
        if (!list) return;
        
        // Supprimer le message "vide" si présent
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        // Vérifier si la personne n'existe pas déjà
        const existingPerson = Array.from(list.children).find(item => {
            const nameText = item.querySelector('.result-item-title')?.textContent;
            return nameText === person.name;
        });
        if (existingPerson) return;
        
        const item = document.createElement('div');
        item.className = 'result-item person-item';
        
        let contactInfo = '';
        if (person.email || person.phone || person.linkedin_url) {
            contactInfo = '<div class="result-item-contacts">';
            if (person.email) {
                contactInfo += `<div class="contact-item"><span class="contact-icon">📧</span><a href="mailto:${escapeHtml(person.email)}">${escapeHtml(person.email)}</a></div>`;
            }
            if (person.phone) {
                contactInfo += `<div class="contact-item"><span class="contact-icon">📞</span><a href="tel:${escapeHtml(person.phone)}">${escapeHtml(person.phone)}</a></div>`;
            }
            if (person.linkedin_url) {
                contactInfo += `<div class="contact-item"><span class="contact-icon">💼</span><a href="${escapeHtml(person.linkedin_url)}" target="_blank">Profil LinkedIn</a></div>`;
            }
            contactInfo += '</div>';
        }
        
        item.innerHTML = `
            <div class="result-item-icon">👤</div>
            <div class="result-item-content">
                <div class="result-item-header">
                    <strong class="result-item-title">${escapeHtml(person.name || '')}</strong>
                </div>
                ${person.title ? `<div class="result-item-meta result-item-role">${escapeHtml(person.title)}</div>` : ''}
                ${contactInfo}
            </div>
        `;
        list.appendChild(item);
        
        // Animation d'apparition
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    }
    
    function addPhoneToList(phone) {
        const list = document.getElementById('phones-list');
        if (!list) return;
        
        // Supprimer le message "vide" si présent
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        // Vérifier si le téléphone n'existe pas déjà
        const existingPhone = Array.from(list.children).find(item => {
            const phoneText = item.querySelector('strong')?.textContent;
            return phoneText === phone;
        });
        if (existingPhone) return;
        
        const item = document.createElement('div');
        item.className = 'result-item phone-item';
        item.innerHTML = `
            <div class="result-item-icon">📞</div>
            <div class="result-item-content">
                <div class="result-item-header">
                    <strong class="result-item-title">${escapeHtml(phone)}</strong>
                </div>
                <div class="result-item-meta"><a href="tel:${escapeHtml(phone)}" class="phone-link">Appeler</a></div>
            </div>
        `;
        list.appendChild(item);
        
        // Animation d'apparition
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    }
    
    function addSocialToList(platform, url) {
        const list = document.getElementById('social-list');
        if (!list) return;
        
        // Supprimer le message "vide" si présent
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        // Vérifier si le réseau social n'existe pas déjà
        const existingSocial = Array.from(list.children).find(item => {
            const urlLink = item.querySelector('a')?.href;
            return urlLink === url;
        });
        if (existingSocial) return;
        
        const platformIcons = {
            'facebook': '📘',
            'twitter': '🐦',
            'linkedin': '💼',
            'instagram': '📷',
            'youtube': '📺',
            'github': '💻',
            'gitlab': '🔧',
            'medium': '✍️'
        };
        
        const icon = platformIcons[platform.toLowerCase()] || '🔗';
        
        const item = document.createElement('div');
        item.className = 'result-item social-item';
        item.innerHTML = `
            <div class="result-item-icon">${icon}</div>
            <div class="result-item-content">
                <div class="result-item-header">
                    <strong class="result-item-title">${escapeHtml(platform.charAt(0).toUpperCase() + platform.slice(1))}</strong>
                </div>
                <div class="result-item-meta"><a href="${escapeHtml(url)}" target="_blank" class="social-link">${escapeHtml(url)}</a></div>
            </div>
        `;
        list.appendChild(item);
        
        // Animation d'apparition
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    }
    
    function displayAllResults(data) {
        // Technologies
        if (data.technologies && Object.keys(data.technologies).length > 0) {
            const techList = document.getElementById('technologies-list');
            if (techList) {
                const emptyState = techList.querySelector('.empty-state');
                if (emptyState) {
                    emptyState.remove();
                }
                
                for (const [category, techs] of Object.entries(data.technologies)) {
                    const categoryDiv = document.createElement('div');
                    categoryDiv.className = 'result-item tech-item';
                    const techListStr = Array.isArray(techs) ? techs : [techs];
                    categoryDiv.innerHTML = `
                        <div class="result-item-icon">⚙️</div>
                        <div class="result-item-content">
                            <div class="result-item-header">
                                <strong class="result-item-title">${escapeHtml(category.charAt(0).toUpperCase() + category.slice(1))}</strong>
                            </div>
                            <div class="tech-tags">
                                ${techListStr.map(tech => `<span class="tech-tag">${escapeHtml(tech)}</span>`).join('')}
                            </div>
                        </div>
                    `;
                    techList.appendChild(categoryDiv);
                }
                updateCount('tech', Object.keys(data.technologies).length);
            }
        }
        
        // Métadonnées
        if (data.metadata && data.metadata.meta_tags) {
            const metaList = document.getElementById('metadata-list');
            if (metaList) {
                const emptyState = metaList.querySelector('.empty-state');
                if (emptyState) {
                    emptyState.remove();
                }
                
                // Afficher seulement les métadonnées importantes
                const importantKeys = ['title', 'description', 'og:title', 'og:description', 'og:url', 'og:image', 'twitter:card', 'language'];
                const otherKeys = Object.keys(data.metadata.meta_tags).filter(k => !importantKeys.includes(k));
                
                // Afficher les importantes en premier
                importantKeys.forEach(key => {
                    if (data.metadata.meta_tags[key]) {
                        const item = document.createElement('div');
                        item.className = 'result-item metadata-item';
                        const displayKey = key.replace('og:', '').replace(/:/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        item.innerHTML = `
                            <div class="result-item-content">
                                <div class="result-item-header">
                                    <strong class="result-item-title">${escapeHtml(displayKey)}</strong>
                                </div>
                                <div class="result-item-meta">${escapeHtml(String(data.metadata.meta_tags[key]))}</div>
                            </div>
                        `;
                        metaList.appendChild(item);
                    }
                });
                
                // Afficher les autres dans une section réduite
                if (otherKeys.length > 0) {
                    const collapseDiv = document.createElement('details');
                    collapseDiv.className = 'metadata-collapse';
                    collapseDiv.innerHTML = `
                        <summary>Autres métadonnées (${otherKeys.length})</summary>
                        <div class="metadata-other">
                            ${otherKeys.map(key => `
                                <div class="metadata-other-item">
                                    <strong>${escapeHtml(key)}:</strong> 
                                    <span>${escapeHtml(String(data.metadata.meta_tags[key]))}</span>
                                </div>
                            `).join('')}
                        </div>
                    `;
                    metaList.appendChild(collapseDiv);
                }
            }
        }
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
})();

