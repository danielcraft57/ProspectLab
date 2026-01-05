/**
 * JavaScript pour la page de liste des analyses OSINT
 */

(function() {
    let allAnalyses = [];
    
    document.addEventListener('DOMContentLoaded', () => {
        loadAnalyses();
        setupEventListeners();
        
        // Vérifier les paramètres d'URL pour auto-remplir et lancer l'analyse
        const urlParams = new URLSearchParams(window.location.search);
        const autoUrl = urlParams.get('url');
        const autoStart = urlParams.get('auto_start') === 'true';
        const entrepriseId = urlParams.get('entreprise_id');
        
        if (autoUrl) {
            // Préremplir le formulaire
            const urlInput = document.getElementById('osint-url');
            
            if (urlInput) {
                urlInput.value = autoUrl;
            }
            
            // Nettoyer l'URL des paramètres
            if (autoStart) {
                // Attendre un peu que la page soit chargée puis lancer l'analyse
                setTimeout(() => {
                    if (urlInput && urlInput.value) {
                        handleFormSubmit(new Event('submit'), autoUrl, entrepriseId);
                    }
                }, 500);
            }
            
            // Nettoyer l'URL après traitement
            const cleanUrl = window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
        }
    });
    
    async function loadAnalyses() {
        try {
            const response = await fetch('/api/analyses-osint');
            allAnalyses = await response.json();
            renderAnalyses();
        } catch (error) {
            console.error('Erreur lors du chargement des analyses:', error);
            document.getElementById('analyses-container').innerHTML = 
                '<p class="error">Erreur lors du chargement des analyses</p>';
        }
    }
    
    function renderAnalyses() {
        const container = document.getElementById('analyses-container');
        
        document.getElementById('results-count').textContent = 
            allAnalyses.length + ' analyse' + (allAnalyses.length > 1 ? 's' : '') + ' OSINT trouvée' + (allAnalyses.length > 1 ? 's' : '');
        
        if (allAnalyses.length === 0) {
            container.innerHTML = '<p class="no-results">Aucune analyse OSINT disponible</p>';
            return;
        }
        
        container.innerHTML = allAnalyses.map(analysis => createAnalysisCard(analysis)).join('');
        
        // Ajouter les event listeners pour les boutons "Voir détails"
        container.querySelectorAll('.btn-view-details').forEach(btn => {
            btn.addEventListener('click', function() {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'));
                console.log('Ouverture de la modale OSINT pour l\'analyse:', analysisId);
                if (isNaN(analysisId)) {
                    console.error('ID d\'analyse invalide:', this.getAttribute('data-analysis-id'));
                    return;
                }
                openOSINTModal(analysisId);
            });
        });
        
        // Ajouter les event listeners pour les boutons "Supprimer"
        container.querySelectorAll('.btn-delete-analysis').forEach(btn => {
            btn.addEventListener('click', function() {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'));
                const url = this.getAttribute('data-url');
                if (confirm('Êtes-vous sûr de vouloir supprimer cette analyse OSINT ?')) {
                    deleteOSINTAnalysis(analysisId, url);
                }
            });
        });
    }
    
    async function deleteOSINTAnalysis(analysisId, url) {
        try {
            const response = await fetch(`/api/analyse-osint/${analysisId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Erreur lors de la suppression');
            }
            
            const result = await response.json();
            showNotification(result.message || 'Analyse OSINT supprimée avec succès', 'success');
            
            // Recharger la liste
            loadAnalyses();
            
            // Fermer le modal si ouvert
            closeOSINTModal();
        } catch (error) {
            console.error('Erreur lors de la suppression:', error);
            showNotification('Erreur lors de la suppression: ' + error.message, 'error');
        }
    }
    
    function createAnalysisCard(analysis) {
        const date = new Date(analysis.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const subdomainsCount = analysis.subdomains_count || 0;
        const emailsCount = analysis.emails_count || 0;
        const domain = analysis.domain || analysis.url || 'N/A';
        
        // Extraire le nombre de personnes depuis osint_details ou social_media
        let peopleCount = 0;
        if (analysis.osint_details) {
            try {
                const details = typeof analysis.osint_details === 'string' 
                    ? JSON.parse(analysis.osint_details) 
                    : analysis.osint_details;
                if (details.people && details.people.summary) {
                    peopleCount = details.people.summary.total_people || 0;
                }
            } catch (e) {
                // Ignorer les erreurs de parsing
            }
        }
        if (peopleCount === 0 && analysis.social_media) {
            try {
                const socialData = typeof analysis.social_media === 'string' 
                    ? JSON.parse(analysis.social_media) 
                    : analysis.social_media;
                if (socialData && socialData.summary) {
                    peopleCount = socialData.summary.total_people || 0;
                }
            } catch (e) {
                // Ignorer les erreurs de parsing
            }
        }
        
        return `
            <div class="analysis-tech-card">
                <div class="card-header">
                    <h3>${escapeHtml(domain)}</h3>
                    <span class="date-badge">${date}</span>
                </div>
                <div class="card-body">
                    <p><strong>URL:</strong> <a href="${escapeHtml(analysis.url)}" target="_blank">${escapeHtml(analysis.url)}</a></p>
                    <div class="analysis-stats">
                        <span class="stat-item"><strong>Sous-domaines:</strong> ${subdomainsCount}</span>
                        <span class="stat-item"><strong>Emails:</strong> ${emailsCount}</span>
                        ${peopleCount > 0 ? `<span class="stat-item"><strong>Personnes:</strong> ${peopleCount}</span>` : ''}
                    </div>
                </div>
                <div class="card-footer">
                    <button class="btn btn-small btn-primary btn-view-details" data-analysis-id="${analysis.id}">Voir détails</button>
                    <button class="btn btn-small btn-danger btn-delete-analysis" data-analysis-id="${analysis.id}" data-url="${escapeHtml(analysis.url)}">Supprimer</button>
                </div>
            </div>
        `;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function setupEventListeners() {
        const formNewOSINT = document.getElementById('form-new-osint');
        if (formNewOSINT) {
            formNewOSINT.addEventListener('submit', handleNewOSINT);
        }
    }
    
    function handleNewOSINT(e) {
        e.preventDefault();
        
        let url = document.getElementById('osint-url').value.trim();
        
        handleFormSubmit(e, url);
    }
    
    function handleFormSubmit(e, url, entrepriseId = null) {
        if (e) {
            e.preventDefault();
        }
        
        if (!url) {
            alert('Veuillez saisir une URL ou un domaine');
            return;
        }
        
        // Ajouter https:// si manquant
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            url = 'https://' + url;
        }
        
        // Désactiver le formulaire
        const btn = document.getElementById('btn-start-osint');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        const progressSection = document.getElementById('osint-progress');
        const progressBar = document.getElementById('osint-progress-bar');
        const progressMessage = document.getElementById('osint-progress-message');
        
        if (btn) {
            btn.disabled = true;
        }
        if (btnText) {
            btnText.style.display = 'none';
        }
        if (btnLoading) {
            btnLoading.style.display = 'inline';
        }
        if (progressSection) {
            progressSection.style.display = 'block';
        }
        if (progressBar) {
            progressBar.style.width = '0%';
        }
        if (progressMessage) {
            progressMessage.textContent = 'Démarrage de l\'analyse OSINT...';
        }
        
        // Initialiser WebSocket si nécessaire
        if (window.wsManager && window.wsManager.socket) {
            startOSINTAnalysis(url, entrepriseId);
        } else if (typeof io !== 'undefined') {
            const socket = io();
            startOSINTAnalysisWithSocket(socket, url, entrepriseId);
        } else {
            alert('WebSocket non disponible. Veuillez recharger la page.');
            resetForm();
        }
    }
    
    function startOSINTAnalysis(url, entrepriseId = null) {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_osint_analysis', { 
                url: url,
                entreprise_id: entrepriseId
            });
            
            // Écouter les événements
            window.wsManager.socket.on('osint_analysis_progress', (data) => {
                updateProgress(data);
            });
            
            window.wsManager.socket.on('osint_analysis_complete', (data) => {
                handleAnalysisComplete(data);
            });
            
            window.wsManager.socket.on('osint_analysis_error', (data) => {
                handleAnalysisError(data);
            });
        }
    }
    
    function startOSINTAnalysisWithSocket(socket, url, entrepriseId = null) {
        socket.emit('start_osint_analysis', { 
            url: url,
            entreprise_id: entrepriseId
        });
        
        socket.on('osint_analysis_progress', (data) => {
            updateProgress(data);
        });
        
        socket.on('osint_analysis_complete', (data) => {
            handleAnalysisComplete(data);
            socket.disconnect();
        });
        
        socket.on('osint_analysis_error', (data) => {
            handleAnalysisError(data);
            socket.disconnect();
        });
    }
    
    function updateProgress(data) {
        const progressBar = document.getElementById('osint-progress-bar');
        const progressMessage = document.getElementById('osint-progress-message');
        
        if (progressBar) {
            progressBar.style.width = data.progress + '%';
        }
        if (progressMessage) {
            progressMessage.textContent = data.message || 'Analyse en cours...';
        }
    }
    
    function handleAnalysisComplete(data) {
        const progressBar = document.getElementById('osint-progress-bar');
        const progressMessage = document.getElementById('osint-progress-message');
        
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.classList.add('success');
        }
        if (progressMessage) {
            progressMessage.textContent = 'Analyse OSINT terminée avec succès !';
        }
        
        showNotification('Analyse OSINT terminée avec succès !', 'success');
        
        // Recharger la liste
        setTimeout(() => {
            loadAnalyses();
            resetForm();
            
            // Ouvrir automatiquement la modale avec les détails de l'analyse
            if (data.analysis_id) {
                setTimeout(() => {
                    openOSINTModal(data.analysis_id);
                }, 500);
            }
        }, 1000);
    }
    
    function handleAnalysisError(data) {
        showNotification(data.error || 'Erreur lors de l\'analyse OSINT', 'error');
        resetForm();
    }
    
    function resetForm() {
        const btn = document.getElementById('btn-start-osint');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        const progressSection = document.getElementById('osint-progress');
        
        btn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        progressSection.style.display = 'none';
        document.getElementById('osint-url').value = '';
    }
    
    // Fonctions pour la modale
    let currentOSINTData = null;
    let currentOSINTId = null;
    
    function openOSINTModal(analysisId) {
        currentOSINTId = analysisId;
        const modal = document.getElementById('osint-modal');
        if (!modal) {
            console.error('Modal OSINT introuvable');
            return;
        }
        
        const modalBody = document.getElementById('osint-modal-body');
        const modalTitle = document.getElementById('osint-modal-title');
        const modalFooter = document.getElementById('osint-modal-footer');
        
        // Afficher le modal
        modal.style.display = 'flex';
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        
        if (modalBody) {
            modalBody.innerHTML = '<div class="loading">Chargement des détails...</div>';
        }
        if (modalFooter) {
            modalFooter.innerHTML = '';
        }
        
        loadOSINTDetail(analysisId);
    }
    
    function closeOSINTModal() {
        const modal = document.getElementById('osint-modal');
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
        currentOSINTData = null;
        currentOSINTId = null;
    }
    
    async function loadOSINTDetail(analysisId) {
        try {
            console.log('Chargement des détails OSINT pour l\'ID:', analysisId);
            const response = await fetch('/api/analyse-osint/' + analysisId);
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Erreur HTTP:', response.status, errorText);
                throw new Error('Analyse OSINT introuvable');
            }
            
            currentOSINTData = await response.json();
            console.log('Données OSINT chargées:', currentOSINTData);
            renderOSINTDetail();
        } catch (error) {
            console.error('Erreur lors du chargement:', error);
            const modalBody = document.getElementById('osint-modal-body');
            if (modalBody) {
                modalBody.innerHTML = 
                    '<div class="error">Erreur lors du chargement des détails: ' + error.message + '</div>';
            }
        }
    }
    
    function renderOSINTDetail() {
        if (!currentOSINTData) return;
        
        const date = new Date(currentOSINTData.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        document.getElementById('osint-modal-title').textContent = 
            'Analyse OSINT - ' + (currentOSINTData.domain || currentOSINTData.url || 'Site web');
        
        const modalBody = document.getElementById('osint-modal-body');
        modalBody.innerHTML = createOSINTDetailHTML(date);
        
        // Ajouter les boutons dans le footer
        const modalFooter = document.getElementById('osint-modal-footer');
        modalFooter.innerHTML = `
            <button class="btn btn-danger" id="btn-delete-osint-analysis" data-analysis-id="${currentOSINTId}" data-url="${currentOSINTData.url}">Supprimer</button>
            <button class="btn btn-secondary" id="btn-close-osint-modal">Fermer</button>
        `;
        
        // Event listener pour fermer
        document.getElementById('btn-close-osint-modal').addEventListener('click', closeOSINTModal);
        
        // Event listener pour supprimer
        const deleteBtn = document.getElementById('btn-delete-osint-analysis');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function() {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'));
                const url = this.getAttribute('data-url');
                if (confirm('Êtes-vous sûr de vouloir supprimer cette analyse OSINT ?')) {
                    deleteOSINTAnalysis(analysisId, url);
                }
            });
        }
    }
    
    function createOSINTDetailHTML(date) {
        const subdomains = currentOSINTData.subdomains || [];
        const dnsRecords = currentOSINTData.dns_records || {};
        const whoisInfo = currentOSINTData.whois_info || {};
        const emails = currentOSINTData.emails_found || [];
        const sslInfo = currentOSINTData.ssl_info || {};
        const technologies = currentOSINTData.technologies_detected || {};
        const ipInfo = currentOSINTData.ip_info || {};
        
        // Parser les données de personnes depuis osint_details ou social_media
        let peopleData = {};
        
        // Essayer d'abord social_media (nouveau format)
        if (currentOSINTData.social_media) {
            try {
                const socialData = typeof currentOSINTData.social_media === 'string' 
                    ? JSON.parse(currentOSINTData.social_media) 
                    : currentOSINTData.social_media;
                if (socialData && (socialData.people || socialData.linkedin_profiles)) {
                    peopleData = socialData;
                }
            } catch (e) {
                console.error('Erreur parsing social_media:', e);
            }
        }
        
        // Sinon essayer osint_details (ancien format)
        if (!peopleData.people && !peopleData.linkedin_profiles && currentOSINTData.osint_details) {
            try {
                const details = typeof currentOSINTData.osint_details === 'string' 
                    ? JSON.parse(currentOSINTData.osint_details) 
                    : currentOSINTData.osint_details;
                peopleData = details.people || {};
            } catch (e) {
                console.error('Erreur parsing osint_details:', e);
            }
        }
        
        const people = peopleData.people || [];
        const linkedinProfiles = peopleData.linkedin_profiles || [];
        const socialProfiles = peopleData.social_profiles || {};
        
        // Parser les données financières depuis osint_details
        let financialData = {};
        if (currentOSINTData.osint_details) {
            try {
                const details = typeof currentOSINTData.osint_details === 'string' 
                    ? JSON.parse(currentOSINTData.osint_details) 
                    : currentOSINTData.osint_details;
                financialData = details.financial_data || {};
            } catch (e) {
                console.error('Erreur parsing financial_data:', e);
            }
        }
        
        return `
            <div class="detail-grid">
                <div class="detail-section">
                    <h3>Informations générales</h3>
                    <div class="info-grid">
                        ${createInfoRow('URL', currentOSINTData.url, true)}
                        ${createInfoRow('Domaine', currentOSINTData.domain)}
                        ${createInfoRow('Date d\'analyse', date)}
                        ${ipInfo.ip ? createInfoRow('Adresse IP', ipInfo.ip) : ''}
                    </div>
                </div>
                
                ${people.length > 0 || linkedinProfiles.length > 0 ? `
                <div class="detail-section full-width">
                    <h3>👥 Personnes liées à l'entreprise (${people.length + linkedinProfiles.length})</h3>
                    ${peopleData.summary ? `
                        <div class="people-summary" style="margin-bottom: 1rem; padding: 1rem; background: #f8f9fa; border-radius: 4px;">
                            <strong>Résumé:</strong> 
                            ${peopleData.summary.with_emails || 0} avec email, 
                            ${peopleData.summary.with_linkedin || 0} avec LinkedIn, 
                            ${peopleData.summary.with_social_profiles || 0} avec profils sociaux
                        </div>
                    ` : ''}
                    <div class="people-list">
                        ${people.map(person => createPersonCard(person, socialProfiles)).join('')}
                        ${linkedinProfiles.map(person => createPersonCard(person, socialProfiles)).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${createFinancialDataSection(financialData)}
                
                ${subdomains.length > 0 ? `
                <div class="detail-section">
                    <h3>Sous-domaines (${subdomains.length})</h3>
                    <div class="info-grid">
                        ${subdomains.map(sub => `<div class="info-row"><span class="info-value"><span class="tag">${escapeHtml(sub)}</span></span></div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${Object.keys(dnsRecords).length > 0 ? `
                <div class="detail-section">
                    <h3>Enregistrements DNS</h3>
                    <div class="info-grid">
                        ${Object.entries(dnsRecords).map(([type, records]) => 
                            Array.isArray(records) && records.length > 0 
                                ? createInfoRow(type, records.join(', '))
                                : ''
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${Object.keys(whoisInfo).length > 0 ? `
                <div class="detail-section">
                    <h3>Informations WHOIS</h3>
                    <div class="info-grid">
                        ${createInfoRow('Registrar', whoisInfo.registrar)}
                        ${createInfoRow('Date de création', whoisInfo.creation_date)}
                        ${createInfoRow('Date d\'expiration', whoisInfo.expiration_date)}
                        ${createInfoRow('Organisation', whoisInfo.org)}
                        ${createInfoRow('Pays', whoisInfo.country)}
                    </div>
                </div>
                ` : ''}
                
                ${emails.length > 0 ? `
                <div class="detail-section">
                    <h3>Emails trouvés (${emails.length})</h3>
                    <div class="info-grid">
                        ${emails.map(email => `<div class="info-row"><span class="info-value"><span class="tag">${escapeHtml(email)}</span></span></div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${Object.keys(sslInfo).length > 0 ? `
                <div class="detail-section">
                    <h3>Informations SSL/TLS</h3>
                    <div class="info-grid">
                        ${Object.entries(sslInfo).map(([key, value]) => 
                            createInfoRow(key.replace(/_/g, ' '), value)
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${Object.keys(technologies).length > 0 ? `
                <div class="detail-section">
                    <h3>Technologies détectées</h3>
                    <div class="info-grid">
                        ${technologies.raw_output ? `
                            <div class="info-row full-width">
                                <span class="info-label">Détails techniques:</span>
                                <span class="info-value">
                                    <pre style="white-space: pre-wrap; font-size: 0.85em; background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; max-height: 300px; overflow-y: auto; border: 1px solid #e0e0e0;">${escapeHtml(cleanAnsiCodes(technologies.raw_output))}</pre>
                                </span>
                            </div>
                        ` : ''}
                        ${Object.entries(technologies).filter(([key]) => key !== 'raw_output').map(([key, value]) => {
                            if (Array.isArray(value) && value.length > 0) {
                                return `<div class="info-row">
                                    <span class="info-label">${escapeHtml(key.replace(/_/g, ' '))}:</span>
                                    <span class="info-value">
                                        ${value.map(v => `<span class="tag">${escapeHtml(String(v))}</span>`).join(' ')}
                                    </span>
                                </div>`;
                            } else if (typeof value === 'object' && value !== null) {
                                return `<div class="info-row">
                                    <span class="info-label">${escapeHtml(key.replace(/_/g, ' '))}:</span>
                                    <span class="info-value">${escapeHtml(JSON.stringify(value, null, 2))}</span>
                                </div>`;
                            } else if (value) {
                                return createInfoRow(key.replace(/_/g, ' '), value);
                            }
                            return '';
                        }).filter(html => html).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    function createInfoRow(label, value, isLink = false) {
        if (!value) return '';
        
        const content = isLink ? '<a href="' + value + '" target="_blank">' + escapeHtml(value) + '</a>' : escapeHtml(value);
        
        return `
            <div class="info-row">
                <span class="info-label">${label}:</span>
                <span class="info-value">${content}</span>
            </div>
        `;
    }
    
    function createFinancialDataSection(financialData) {
        if (!financialData || (!financialData.legal_info && !financialData.financial_info)) {
            return '';
        }
        
        const legalInfo = financialData.legal_info || {};
        const financialInfo = financialData.financial_info || {};
        const directors = financialData.directors || [];
        
        return `
            <div class="detail-section full-width">
                <h3>💰 Données financières et juridiques</h3>
                
                ${Object.keys(legalInfo).length > 0 ? `
                    <div class="financial-subsection">
                        <h4>📋 Informations juridiques</h4>
                        <div class="info-grid">
                            ${legalInfo.siren ? createInfoRow('SIREN', legalInfo.siren) : ''}
                            ${legalInfo.siret ? createInfoRow('SIRET', legalInfo.siret) : ''}
                            ${legalInfo.denomination ? createInfoRow('Dénomination', legalInfo.denomination) : ''}
                            ${legalInfo.forme_juridique ? createInfoRow('Forme juridique', legalInfo.forme_juridique) : ''}
                            ${legalInfo.activite_principale ? createInfoRow('Activité principale', legalInfo.activite_principale) : ''}
                            ${legalInfo.date_creation ? createInfoRow('Date de création', legalInfo.date_creation) : ''}
                            ${legalInfo.tranche_effectif ? createInfoRow('Tranche d\'effectif', legalInfo.tranche_effectif) : ''}
                            ${legalInfo.etat_administratif ? createInfoRow('État administratif', legalInfo.etat_administratif) : ''}
                            ${legalInfo.capital_social ? createInfoRow('Capital social', formatCurrency(legalInfo.capital_social)) : ''}
                            ${legalInfo.adresse ? createInfoRow('Adresse', legalInfo.adresse) : ''}
                        </div>
                    </div>
                ` : ''}
                
                ${Object.keys(financialInfo).length > 0 ? `
                    <div class="financial-subsection" style="margin-top: 1.5rem;">
                        <h4>💵 Informations financières</h4>
                        <div class="info-grid">
                            ${financialInfo.chiffre_affaires ? createInfoRow('Chiffre d\'affaires', formatCurrency(financialInfo.chiffre_affaires)) : ''}
                            ${financialInfo.bilans && financialInfo.bilans.length > 0 ? `
                                <div class="info-row">
                                    <span class="info-label">Bilans disponibles:</span>
                                    <span class="info-value">${financialInfo.bilans.length} bilan(s)</span>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                ` : ''}
                
                ${directors.length > 0 ? `
                    <div class="financial-subsection" style="margin-top: 1.5rem;">
                        <h4>👔 Dirigeants (${directors.length})</h4>
                        <div class="directors-list">
                            ${directors.map(director => `
                                <div class="director-card">
                                    <strong>${escapeHtml(director.nom || director.name || 'Nom inconnu')}</strong>
                                    ${director.fonction || director.role ? `<span class="director-role">${escapeHtml(director.fonction || director.role)}</span>` : ''}
                                    ${director.date_naissance ? `<span class="director-info">Né(e) le: ${escapeHtml(director.date_naissance)}</span>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${financialData.summary ? `
                    <div class="financial-summary" style="margin-top: 1rem; padding: 1rem; background: #f8f9fa; border-radius: 4px;">
                        <strong>Résumé:</strong> 
                        ${financialData.summary.has_legal_info ? 'Informations juridiques disponibles' : 'Aucune information juridique'}
                        ${financialData.summary.has_financial_info ? ', Informations financières disponibles' : ''}
                        ${financialData.summary.directors_count > 0 ? `, ${financialData.summary.directors_count} dirigeant(s)` : ''}
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    function formatCurrency(amount) {
        if (!amount) return 'N/A';
        if (typeof amount === 'string') {
            amount = parseFloat(amount);
        }
        if (isNaN(amount)) return 'N/A';
        
        // Formater en euros
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'EUR',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }
    
    function createPersonCard(person, socialProfiles = {}) {
        const name = person.name || person.username || 'Nom inconnu';
        const email = person.email || '';
        const title = person.title || '';
        const linkedinUrl = person.linkedin_url || '';
        const username = person.username || '';
        const personSocialProfiles = person.social_profiles || socialProfiles[username] || [];
        
        // Compter les informations disponibles
        const infoCount = [email, linkedinUrl, personSocialProfiles.length > 0].filter(Boolean).length;
        
        return `
            <div class="person-card">
                <div class="person-header">
                    <h4>${escapeHtml(name)}</h4>
                    ${title ? `<span class="person-title">${escapeHtml(title)}</span>` : ''}
                    ${infoCount > 0 ? `<span class="person-badge">${infoCount} info${infoCount > 1 ? 's' : ''}</span>` : ''}
                </div>
                <div class="person-details">
                    ${email ? `
                        <div class="person-info">
                            <strong>📧 Email:</strong> 
                            <a href="mailto:${escapeHtml(email)}" class="person-link">${escapeHtml(email)}</a>
                        </div>
                    ` : ''}
                    ${linkedinUrl ? `
                        <div class="person-info">
                            <strong>💼 LinkedIn:</strong> 
                            <a href="${escapeHtml(linkedinUrl)}" target="_blank" class="person-link" rel="noopener noreferrer">
                                Voir le profil
                            </a>
                        </div>
                    ` : ''}
                    ${personSocialProfiles.length > 0 ? `
                        <div class="person-info">
                            <strong>🌐 Réseaux sociaux (${personSocialProfiles.length}):</strong>
                            <div class="social-profiles">
                                ${personSocialProfiles.map(profile => {
                                    const domain = profile.url ? new URL(profile.url).hostname.replace('www.', '') : '';
                                    return `<a href="${escapeHtml(profile.url)}" target="_blank" class="social-link" rel="noopener noreferrer" title="${escapeHtml(profile.url)}">
                                        ${domain || 'Profil'}
                                    </a>`;
                                }).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${!email && !linkedinUrl && personSocialProfiles.length === 0 ? `
                        <div class="person-info" style="color: #6c757d; font-style: italic;">
                            Informations limitées disponibles
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = 'notification notification-' + type;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
            color: white;
            border-radius: 4px;
            z-index: 10000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    
    // Event listeners pour fermer la modale
    document.addEventListener('DOMContentLoaded', () => {
        const modal = document.getElementById('osint-modal');
        const modalClose = document.getElementById('osint-modal-close');
        const modalOverlay = modal?.querySelector('.modal-overlay');
        
        if (modalClose) {
            modalClose.addEventListener('click', closeOSINTModal);
        }
        
        if (modalOverlay) {
            modalOverlay.addEventListener('click', closeOSINTModal);
        }
        
        // Fermer avec la touche Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal?.classList.contains('active')) {
                closeOSINTModal();
            }
        });
    });
})();

