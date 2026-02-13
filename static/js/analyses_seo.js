/**
 * JavaScript pour la page de liste des analyses SEO
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
            const urlInput = document.getElementById('seo-url');
            
            if (urlInput) {
                urlInput.value = autoUrl;
            }
            
            // Nettoyer l'URL des paramètres
            if (autoStart) {
                // Attendre un peu que la page soit chargée puis lancer l'analyse
                setTimeout(() => {
                    if (urlInput && urlInput.value) {
                        const useLighthouse = document.getElementById('seo-use-lighthouse')?.checked ?? true;
                        handleFormSubmit(new Event('submit'), autoUrl, entrepriseId, useLighthouse);
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
            const response = await fetch('/api/analyses-seo');
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
            allAnalyses.length + ' analyse' + (allAnalyses.length > 1 ? 's' : '') + ' SEO trouvée' + (allAnalyses.length > 1 ? 's' : '');
        
        if (allAnalyses.length === 0) {
            container.innerHTML = '<p class="no-results">Aucune analyse SEO disponible</p>';
            return;
        }
        
        container.innerHTML = allAnalyses.map(analysis => createAnalysisCard(analysis)).join('');
        
        // Ajouter les event listeners pour les boutons "Voir détails"
        container.querySelectorAll('.btn-view-details').forEach(btn => {
            btn.addEventListener('click', function() {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'));
                if (isNaN(analysisId)) {
                    console.error('ID d\'analyse invalide:', this.getAttribute('data-analysis-id'));
                    return;
                }
                openSEOModal(analysisId);
            });
        });
        
        // Ajouter les event listeners pour les boutons "Supprimer"
        container.querySelectorAll('.btn-delete-analysis').forEach(btn => {
            btn.addEventListener('click', function() {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'));
                const url = this.getAttribute('data-url');
                if (confirm('Êtes-vous sûr de vouloir supprimer cette analyse SEO ?')) {
                    deleteSEOAnalysis(analysisId, url);
                }
            });
        });
    }
    
    async function deleteSEOAnalysis(analysisId, url) {
        try {
            const response = await fetch(`/api/analyse-seo/${analysisId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Erreur lors de la suppression');
            }
            
            const result = await response.json();
            showNotification(result.message || 'Analyse SEO supprimée avec succès', 'success');
            
            // Recharger la liste
            loadAnalyses();
            
            // Fermer le modal si ouvert
            closeSEOModal();
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
        
        const score = analysis.score || 0;
        const scoreClass = score >= 80 ? 'score-excellent' : score >= 60 ? 'score-good' : score >= 40 ? 'score-medium' : 'score-low';
        
        let metaTagsCount = 0;
        let issuesCount = 0;
        let lighthouseScore = null;
        
        try {
            if (analysis.meta_tags_json) {
                const metaTags = typeof analysis.meta_tags_json === 'string' 
                    ? JSON.parse(analysis.meta_tags_json) 
                    : analysis.meta_tags_json;
                metaTagsCount = Object.keys(metaTags).length;
            }
            if (analysis.issues_json) {
                const issues = typeof analysis.issues_json === 'string' 
                    ? JSON.parse(analysis.issues_json) 
                    : analysis.issues_json;
                issuesCount = Array.isArray(issues) ? issues.length : 0;
            }
            if (analysis.lighthouse_json) {
                const lighthouse = typeof analysis.lighthouse_json === 'string' 
                    ? JSON.parse(analysis.lighthouse_json) 
                    : analysis.lighthouse_json;
                lighthouseScore = lighthouse.score ? Math.round(lighthouse.score * 100) : null;
            }
        } catch (e) {
            // Ignorer les erreurs de parsing
        }
        
        return `
            <div class="analysis-card">
                <div class="analysis-card-header">
                    <h3>${analysis.url || 'N/A'}</h3>
                    <span class="analysis-date">${date}</span>
                </div>
                <div class="analysis-card-body">
                    <div class="analysis-metrics">
                        <div class="metric">
                            <span class="metric-label">Score SEO</span>
                            <span class="metric-value ${scoreClass}">${score}/100</span>
                        </div>
                        ${lighthouseScore !== null ? `
                        <div class="metric">
                            <span class="metric-label">Lighthouse</span>
                            <span class="metric-value">${lighthouseScore}/100</span>
                        </div>
                        ` : ''}
                        <div class="metric">
                            <span class="metric-label">Meta tags</span>
                            <span class="metric-value">${metaTagsCount}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Problèmes</span>
                            <span class="metric-value ${issuesCount > 0 ? 'has-issues' : ''}">${issuesCount}</span>
                        </div>
                    </div>
                </div>
                <div class="analysis-card-footer">
                    <button class="btn btn-secondary btn-view-details" data-analysis-id="${analysis.id}">
                        <i class="fas fa-eye"></i> Voir détails
                    </button>
                    <button class="btn btn-danger btn-delete-analysis" data-analysis-id="${analysis.id}" data-url="${analysis.url || ''}">
                        <i class="fas fa-trash"></i> Supprimer
                    </button>
                </div>
            </div>
        `;
    }
    
    function setupEventListeners() {
        const form = document.getElementById('form-new-seo');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const urlInput = document.getElementById('seo-url');
                const url = urlInput.value.trim();
                const useLighthouse = document.getElementById('seo-use-lighthouse')?.checked ?? true;
                
                if (!url) {
                    alert('Veuillez saisir une URL');
                    return;
                }
                
                handleFormSubmit(e, url, null, useLighthouse);
            });
        }
        
        // Modal
        const modal = document.getElementById('seo-modal');
        const modalClose = document.getElementById('seo-modal-close');
        if (modalClose) {
            modalClose.addEventListener('click', closeSEOModal);
        }
        if (modal) {
            modal.querySelector('.modal-overlay')?.addEventListener('click', closeSEOModal);
        }
    }
    
    function handleFormSubmit(e, url, entrepriseId = null, useLighthouse = true) {
        if (e) {
            e.preventDefault();
        }
        
        if (!url) {
            alert('Veuillez saisir une URL');
            return;
        }
        
        // Ajouter https:// si manquant
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            url = 'https://' + url;
        }
        
        // Désactiver le formulaire
        const btn = document.getElementById('btn-start-seo');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        const progressSection = document.getElementById('seo-progress');
        const progressBar = document.getElementById('seo-progress-bar');
        const progressMessage = document.getElementById('seo-progress-message');
        
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
            progressMessage.textContent = 'Démarrage de l\'analyse SEO...';
        }
        
        // Initialiser WebSocket si nécessaire
        if (window.wsManager && window.wsManager.socket) {
            startSEOAnalysis(url, entrepriseId, useLighthouse);
        } else if (typeof io !== 'undefined') {
            const socket = io();
            startSEOAnalysisWithSocket(socket, url, entrepriseId, useLighthouse);
        } else {
            alert('WebSocket non disponible. Veuillez recharger la page.');
            resetForm();
        }
    }
    
    function startSEOAnalysis(url, entrepriseId = null, useLighthouse = true) {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_seo_analysis', { 
                url: url,
                entreprise_id: entrepriseId,
                use_lighthouse: useLighthouse
            });
            
            // Écouter les événements
            window.wsManager.socket.on('seo_analysis_progress', (data) => {
                updateProgress(data);
            });
            
            window.wsManager.socket.on('seo_analysis_complete', (data) => {
                handleAnalysisComplete(data);
            });
            
            window.wsManager.socket.on('seo_analysis_error', (data) => {
                handleAnalysisError(data);
            });
        }
    }
    
    function startSEOAnalysisWithSocket(socket, url, entrepriseId = null, useLighthouse = true) {
        socket.emit('start_seo_analysis', { 
            url: url,
            entreprise_id: entrepriseId,
            use_lighthouse: useLighthouse
        });
        
        socket.on('seo_analysis_progress', (data) => {
            updateProgress(data);
        });
        
        socket.on('seo_analysis_complete', (data) => {
            handleAnalysisComplete(data);
            socket.disconnect();
        });
        
        socket.on('seo_analysis_error', (data) => {
            handleAnalysisError(data);
            socket.disconnect();
        });
    }
    
    function updateProgress(data) {
        const progressBar = document.getElementById('seo-progress-bar');
        const progressMessage = document.getElementById('seo-progress-message');
        
        if (progressBar) {
            progressBar.style.width = data.progress + '%';
        }
        if (progressMessage) {
            progressMessage.textContent = data.message || 'Analyse en cours...';
        }
    }
    
    function handleAnalysisComplete(data) {
        const progressBar = document.getElementById('seo-progress-bar');
        const progressMessage = document.getElementById('seo-progress-message');
        
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.classList.add('success');
        }
        if (progressMessage) {
            progressMessage.textContent = 'Analyse SEO terminée avec succès !';
        }
        
        showNotification('Analyse SEO terminée avec succès !', 'success');
        
        // Recharger la liste
        setTimeout(() => {
            loadAnalyses();
            resetForm();
            
            // Ouvrir automatiquement la modale avec les détails de l'analyse
            if (data.analysis_id) {
                setTimeout(() => {
                    openSEOModal(data.analysis_id);
                }, 500);
            }
        }, 1000);
    }
    
    function handleAnalysisError(data) {
        showNotification(data.error || 'Erreur lors de l\'analyse SEO', 'error');
        resetForm();
    }
    
    function resetForm() {
        const btn = document.getElementById('btn-start-seo');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        const progressSection = document.getElementById('seo-progress');
        
        if (btn) {
            btn.disabled = false;
        }
        if (btnText) {
            btnText.style.display = 'inline';
        }
        if (btnLoading) {
            btnLoading.style.display = 'none';
        }
        if (progressSection) {
            progressSection.style.display = 'none';
        }
    }
    
    async function openSEOModal(analysisId) {
        const modal = document.getElementById('seo-modal');
        const modalBody = document.getElementById('seo-modal-body');
        const modalTitle = document.getElementById('seo-modal-title');
        
        if (!modal || !modalBody) {
            console.error('Modal SEO non trouvé');
            return;
        }
        
        modal.style.display = 'flex';
        modalBody.innerHTML = '<div class="loading">Chargement des détails...</div>';
        
        try {
            const response = await fetch(`/api/analyse-seo/${analysisId}`);
            if (!response.ok) {
                throw new Error('Erreur lors du chargement des détails');
            }
            
            const analysis = await response.json();
            
            if (modalTitle) {
                modalTitle.textContent = `Analyse SEO - ${analysis.url || 'N/A'}`;
            }
            
            modalBody.innerHTML = renderSEODetails(analysis);
        } catch (error) {
            console.error('Erreur lors du chargement des détails:', error);
            modalBody.innerHTML = `<p class="error">Erreur lors du chargement des détails: ${error.message}</p>`;
        }
    }
    
    function closeSEOModal() {
        const modal = document.getElementById('seo-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    
    function renderSEODetails(analysis) {
        let metaTags = {};
        let headers = {};
        let structure = {};
        let sitemap = null;
        let robots = null;
        let lighthouse = null;
        let issues = [];
        let summary = {};
        
        try {
            if (analysis.meta_tags_json) {
                metaTags = typeof analysis.meta_tags_json === 'string' 
                    ? JSON.parse(analysis.meta_tags_json) 
                    : analysis.meta_tags_json;
            }
            if (analysis.headers_json) {
                headers = typeof analysis.headers_json === 'string' 
                    ? JSON.parse(analysis.headers_json) 
                    : analysis.headers_json;
            }
            if (analysis.structure_json) {
                structure = typeof analysis.structure_json === 'string' 
                    ? JSON.parse(analysis.structure_json) 
                    : analysis.structure_json;
            }
            if (analysis.sitemap_json) {
                sitemap = typeof analysis.sitemap_json === 'string' 
                    ? JSON.parse(analysis.sitemap_json) 
                    : analysis.sitemap_json;
            }
            if (analysis.robots_json) {
                robots = typeof analysis.robots_json === 'string' 
                    ? JSON.parse(analysis.robots_json) 
                    : analysis.robots_json;
            }
            if (analysis.lighthouse_json) {
                lighthouse = typeof analysis.lighthouse_json === 'string' 
                    ? JSON.parse(analysis.lighthouse_json) 
                    : analysis.lighthouse_json;
            }
            if (analysis.issues_json) {
                issues = typeof analysis.issues_json === 'string' 
                    ? JSON.parse(analysis.issues_json) 
                    : analysis.issues_json;
                if (!Array.isArray(issues)) {
                    issues = [];
                }
            }
            if (analysis.seo_details) {
                const details = typeof analysis.seo_details === 'string' 
                    ? JSON.parse(analysis.seo_details) 
                    : analysis.seo_details;
                summary = details.summary || {};
            }
        } catch (e) {
            console.error('Erreur parsing JSON:', e);
        }
        
        const score = analysis.score || 0;
        const scoreClass = score >= 80 ? 'score-excellent' : score >= 60 ? 'score-good' : score >= 40 ? 'score-medium' : 'score-low';
        
        return `
            <div class="seo-details">
                <div class="seo-score-section">
                    <h3>Score SEO</h3>
                    <div class="score-display ${scoreClass}">
                        <span class="score-value">${score}/100</span>
                    </div>
                </div>
                
                ${Object.keys(metaTags).length > 0 ? `
                <div class="seo-section">
                    <h3>Meta Tags</h3>
                    <dl class="meta-tags-list">
                        ${Object.entries(metaTags).map(([key, value]) => `
                            <dt>${key}</dt>
                            <dd>${value}</dd>
                        `).join('')}
                    </dl>
                </div>
                ` : ''}
                
                ${Object.keys(headers).length > 0 ? `
                <div class="seo-section">
                    <h3>Headers HTTP</h3>
                    <dl class="headers-list">
                        ${Object.entries(headers).map(([key, value]) => `
                            <dt>${key}</dt>
                            <dd>${value}</dd>
                        `).join('')}
                    </dl>
                </div>
                ` : ''}
                
                ${Object.keys(structure).length > 0 ? `
                <div class="seo-section">
                    <h3>Structure HTML</h3>
                    <ul class="structure-list">
                        ${structure.h1_count !== undefined ? `<li>H1: ${structure.h1_count}</li>` : ''}
                        ${structure.h2_count !== undefined ? `<li>H2: ${structure.h2_count}</li>` : ''}
                        ${structure.h3_count !== undefined ? `<li>H3: ${structure.h3_count}</li>` : ''}
                        ${structure.images_total !== undefined ? `<li>Images: ${structure.images_total} (${structure.images_without_alt || 0} sans alt)</li>` : ''}
                        ${structure.internal_links_count !== undefined ? `<li>Liens internes: ${structure.internal_links_count}</li>` : ''}
                        ${structure.external_links_count !== undefined ? `<li>Liens externes: ${structure.external_links_count}</li>` : ''}
                    </ul>
                </div>
                ` : ''}
                
                ${sitemap ? `
                <div class="seo-section">
                    <h3>Sitemap</h3>
                    <p><strong>URL:</strong> <a href="${sitemap.url}" target="_blank">${sitemap.url}</a></p>
                    <p><strong>Statut:</strong> ${sitemap.status}</p>
                </div>
                ` : ''}
                
                ${robots ? `
                <div class="seo-section">
                    <h3>robots.txt</h3>
                    <p><strong>URL:</strong> <a href="${robots.url}" target="_blank">${robots.url}</a></p>
                    <p><strong>Statut:</strong> ${robots.status}</p>
                </div>
                ` : ''}
                
                ${lighthouse ? `
                <div class="seo-section">
                    <h3>Lighthouse</h3>
                    ${lighthouse.score !== undefined ? `<p><strong>Score SEO:</strong> ${Math.round(lighthouse.score * 100)}/100</p>` : ''}
                    ${lighthouse.performance_score !== undefined ? `<p><strong>Score Performance:</strong> ${Math.round(lighthouse.performance_score * 100)}/100</p>` : ''}
                </div>
                ` : ''}
                
                ${issues.length > 0 ? `
                <div class="seo-section">
                    <h3>Problèmes détectés</h3>
                    <ul class="issues-list">
                        ${issues.map(issue => `
                            <li class="issue-${issue.type || 'info'}">
                                <strong>${issue.category || 'Général'}:</strong> ${issue.message || ''}
                                <span class="impact-${issue.impact || 'low'}">(${issue.impact || 'low'})</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
                ` : ''}
            </div>
        `;
    }
})();
