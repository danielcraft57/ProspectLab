/**
 * JavaScript pour la page de liste des analyses techniques
 */

(function() {
    let allAnalyses = [];
    let filteredAnalyses = [];
    
    document.addEventListener('DOMContentLoaded', () => {
        loadAnalyses();
        setupEventListeners();
        
        // Vérifier les paramètres d'URL pour auto-remplir et lancer l'analyse
        const urlParams = new URLSearchParams(window.location.search);
        const autoUrl = urlParams.get('url');
        const autoNmap = urlParams.get('enable_nmap') === 'true';
        const autoStart = urlParams.get('auto_start') === 'true';
        const entrepriseId = urlParams.get('entreprise_id');
        
        if (autoUrl) {
            // Préremplir le formulaire
            const urlInput = document.getElementById('analysis-url');
            const nmapCheckbox = document.getElementById('enable-nmap');
            
            if (urlInput) {
                urlInput.value = autoUrl;
            }
            if (nmapCheckbox) {
                nmapCheckbox.checked = autoNmap;
            }
            
            // Nettoyer l'URL des paramètres
            if (autoStart) {
                // Attendre un peu que la page soit chargée puis lancer l'analyse
                setTimeout(() => {
                    if (urlInput && urlInput.value) {
                        handleFormSubmit(new Event('submit'), autoUrl, autoNmap, entrepriseId);
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
            const response = await fetch('/api/analyses-techniques');
            allAnalyses = await response.json();
            filteredAnalyses = [...allAnalyses];
            applyFilters();
        } catch (error) {
            console.error('Erreur lors du chargement des analyses:', error);
            document.getElementById('analyses-container').innerHTML = 
                '<p class="error">Erreur lors du chargement des analyses</p>';
        }
    }
    
    function applyFilters() {
        const framework = document.getElementById('filter-framework').value;
        const cms = document.getElementById('filter-cms').value;
        const hosting = document.getElementById('filter-hosting').value.toLowerCase();
        
        filteredAnalyses = allAnalyses.filter(analysis => {
            if (framework && analysis.framework !== framework) return false;
            if (cms && analysis.cms !== cms) return false;
            if (hosting && !analysis.hosting_provider?.toLowerCase().includes(hosting)) return false;
            return true;
        });
        
        renderAnalyses();
    }
    
    function renderAnalyses() {
        const container = document.getElementById('analyses-container');
        
        document.getElementById('results-count').textContent = 
            `${filteredAnalyses.length} analyse${filteredAnalyses.length > 1 ? 's' : ''} trouvée${filteredAnalyses.length > 1 ? 's' : ''}`;
        
        if (filteredAnalyses.length === 0) {
            container.innerHTML = '<p class="no-results">Aucune analyse ne correspond aux critères</p>';
            return;
        }
        
        container.innerHTML = filteredAnalyses.map(analysis => createAnalysisCard(analysis)).join('');
        
        // Ajouter les event listeners pour les boutons de suppression
        container.querySelectorAll('.btn-delete-analysis').forEach(btn => {
            btn.addEventListener('click', function() {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'));
                const analysisName = this.getAttribute('data-analysis-name');
                deleteAnalysis(analysisId, analysisName);
            });
        });
        
        // Ajouter les event listeners pour les boutons "Voir détails"
        container.querySelectorAll('.btn-view-details').forEach(btn => {
            btn.addEventListener('click', function() {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'));
                openAnalysisModal(analysisId);
            });
        });
    }
    
    // Fonctions utilitaires pour extraire le type de serveur et l'OS
    function extractServerType(serverHeader) {
        if (!serverHeader) return null;
        const header = serverHeader.toLowerCase();
        if (header.includes('apache')) return 'Apache';
        if (header.includes('nginx')) return 'Nginx';
        if (header.includes('iis') || header.includes('microsoft-iis')) return 'IIS';
        if (header.includes('lighttpd')) return 'Lighttpd';
        if (header.includes('caddy')) return 'Caddy';
        if (header.includes('litespeed')) return 'LiteSpeed';
        return null;
    }
    
    function extractOS(serverHeader) {
        if (!serverHeader) return null;
        const header = serverHeader.toLowerCase();
        if (header.includes('debian')) return 'Debian';
        if (header.includes('ubuntu')) return 'Ubuntu';
        if (header.includes('centos')) return 'CentOS';
        if (header.includes('red hat') || header.includes('redhat')) return 'Red Hat';
        if (header.includes('fedora')) return 'Fedora';
        if (header.includes('windows') || header.includes('win32')) return 'Windows';
        if (header.includes('freebsd')) return 'FreeBSD';
        if (header.includes('openbsd')) return 'OpenBSD';
        if (header.includes('linux') && !header.includes('debian') && !header.includes('ubuntu') && !header.includes('centos')) return 'Linux';
        return null;
    }
    
    function createAnalysisCard(analysis) {
        const date = new Date(analysis.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        const badges = [];
        
        // Fonction pour échapper les caractères HTML
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Tag domaine (pour différencier les doublons)
        if (analysis.domain) {
            badges.push(`<span class="badge badge-outline">${escapeHtml(analysis.domain)}</span>`);
        }
        
        if (analysis.framework) {
            const frameworkText = analysis.framework_version 
                ? `${analysis.framework} ${analysis.framework_version}`
                : analysis.framework;
            badges.push(`<span class="badge badge-info">${escapeHtml(frameworkText)}</span>`);
        }
        if (analysis.cms) {
            const cmsText = analysis.cms_version 
                ? `${analysis.cms} ${analysis.cms_version}`
                : analysis.cms;
            badges.push(`<span class="badge badge-success">${escapeHtml(cmsText)}</span>`);
        }
        if (analysis.hosting_provider) {
            badges.push(`<span class="badge badge-secondary">${escapeHtml(analysis.hosting_provider)}</span>`);
        }
        
        // Tag serveur amélioré avec type et OS
        let serverTag = '';
        const techDetails = analysis.technical_details || {};
        const serverType = techDetails.server_type || (analysis.server_software ? extractServerType(analysis.server_software) : null);
        const os = techDetails.os || techDetails.os_detected || (analysis.server_software ? extractOS(analysis.server_software) : null);
        const serverVersion = analysis.server_version || techDetails.server_version;
        
        if (serverType || analysis.server_software) {
            let serverText = serverType || 'Serveur';
            if (serverVersion) {
                serverText += ` ${serverVersion}`;
            } else if (analysis.server_software && !serverType) {
                // Utiliser le header Server complet si on n'a pas le type
                serverText = analysis.server_software;
            }
            if (os) {
                serverText += ` (${os})`;
            }
            badges.push(`<span class="badge badge-outline">${escapeHtml(serverText)}</span>`);
        }
        
        // Tag CDN si disponible
        if (analysis.cdn) {
            badges.push(`<span class="badge badge-outline">CDN: ${escapeHtml(analysis.cdn)}</span>`);
        }
        
        const analysisName = escapeHtml(analysis.entreprise_nom || analysis.url || 'cette analyse');
        const analysisTitle = escapeHtml(analysis.entreprise_nom || analysis.url || 'Site web');
        const analysisUrl = escapeHtml(analysis.url || '');
        const analysisDomain = escapeHtml(analysis.domain || '');
        const analysisIp = escapeHtml(analysis.ip_address || '');
        const analysisServer = escapeHtml(analysis.server_software || '');
        
        return `
            <div class="analysis-tech-card">
                <div class="card-header">
                    <h3>${analysisTitle}</h3>
                    <span class="date-badge">${date}</span>
                </div>
                <div class="card-body">
                    ${analysis.url ? `<p><strong>URL:</strong> <a href="${analysisUrl}" target="_blank">${analysisUrl}</a></p>` : ''}
                    ${analysis.domain ? `<p><strong>Domaine:</strong> ${analysisDomain}</p>` : ''}
                    ${analysis.ip_address ? `<p><strong>IP:</strong> ${analysisIp}</p>` : ''}
                    ${analysis.server_software ? `<p><strong>Serveur:</strong> ${analysisServer}</p>` : ''}
                    ${badges.length > 0 ? `<div class="badges-container">${badges.join('')}</div>` : ''}
                </div>
                <div class="card-footer">
                    <button class="btn btn-small btn-primary btn-view-details" data-analysis-id="${analysis.id}">Voir détails</button>
                    ${analysis.entreprise_id ? `<a href="/entreprise/${analysis.entreprise_id}" class="btn btn-small btn-secondary">Voir entreprise</a>` : ''}
                    <button class="btn btn-small btn-danger btn-delete-analysis" data-analysis-id="${analysis.id}" data-analysis-name="${analysisName}" title="Supprimer">
                        🗑️ Supprimer
                    </button>
                </div>
            </div>
        `;
    }
    
    function setupEventListeners() {
        document.getElementById('btn-apply-filters').addEventListener('click', applyFilters);
        document.getElementById('btn-reset-filters').addEventListener('click', () => {
            document.getElementById('filter-framework').value = '';
            document.getElementById('filter-cms').value = '';
            document.getElementById('filter-hosting').value = '';
            applyFilters();
        });
        
        // Recherche en temps réel pour l'hébergeur
        document.getElementById('filter-hosting').addEventListener('input', debounce(applyFilters, 300));
        
        // Formulaire de nouvelle analyse
        const formNewAnalysis = document.getElementById('form-new-analysis');
        if (formNewAnalysis) {
            formNewAnalysis.addEventListener('submit', handleNewAnalysis);
        }
    }
    
    function handleNewAnalysis(e) {
        e.preventDefault();
        
        const url = document.getElementById('analysis-url').value.trim();
        const enableNmap = document.getElementById('enable-nmap').checked;
        
        handleFormSubmit(e, url, enableNmap);
    }
    
    function handleFormSubmit(e, url, enableNmap, entrepriseId = null) {
        if (e) {
            e.preventDefault();
        }
        
        if (!url) {
            alert('Veuillez saisir une URL');
            return;
        }
        
        // Vérifier que l'URL est valide
        try {
            new URL(url);
        } catch {
            alert('URL invalide. Veuillez saisir une URL complète (ex: https://example.com)');
            return;
        }
        
        // Désactiver le formulaire
        const btn = document.getElementById('btn-start-analysis');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        const progressSection = document.getElementById('analysis-progress');
        const progressBar = document.getElementById('progress-bar');
        const progressMessage = document.getElementById('progress-message');
        
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
            progressMessage.textContent = 'Démarrage de l\'analyse...';
        }
        
        // Initialiser WebSocket si nécessaire
        if (typeof ProspectLabWebSocket !== 'undefined' && window.wsManager) {
            // WebSocket déjà initialisé
            startTechnicalAnalysis(url, enableNmap, false, entrepriseId);
        } else if (typeof io !== 'undefined') {
            // Socket.IO disponible, créer une connexion temporaire
            const socket = io();
            startTechnicalAnalysisWithSocket(socket, url, enableNmap, false, entrepriseId);
        } else {
            alert('WebSocket non disponible. Veuillez recharger la page.');
            resetForm();
        }
    }
    
    function startTechnicalAnalysis(url, enableNmap, force = false, entrepriseId = null) {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_technical_analysis', {
                url: url,
                enable_nmap: enableNmap,
                force: force,
                entreprise_id: entrepriseId
            });
            
            // Écouter les événements
            window.wsManager.socket.on('technical_analysis_progress', (data) => {
                updateProgress(data);
            });
            
            window.wsManager.socket.on('technical_analysis_complete', (data) => {
                handleAnalysisComplete(data);
            });
            
            window.wsManager.socket.on('technical_analysis_error', (data) => {
                handleAnalysisError(data);
            });
            
            window.wsManager.socket.on('technical_analysis_exists', (data) => {
                handleAnalysisExists(data, url, enableNmap);
            });
        }
    }
    
    function handleAnalysisExists(data, url, enableNmap) {
        const progressMessage = document.getElementById('progress-message');
        const progressSection = document.getElementById('analysis-progress');
        
        if (confirm(`Une analyse existe déjà pour cette URL.\n\nVoulez-vous la mettre à jour ?\n\nL'analyse existante sera mise à jour avec les nouvelles données.`)) {
            // Relancer avec force=true pour mettre à jour
            startTechnicalAnalysis(url, enableNmap, true);
        } else {
            // Rediriger vers l'analyse existante
            resetForm();
            if (data.analysis_id) {
                setTimeout(() => {
                    window.location.href = `/analyse-technique/${data.analysis_id}`;
                }, 500);
            }
        }
    }
    
    function startTechnicalAnalysisWithSocket(socket, url, enableNmap, force = false, entrepriseId = null) {
        socket.emit('start_technical_analysis', {
            url: url,
            enable_nmap: enableNmap,
            force: force,
            entreprise_id: entrepriseId
        });
        
        socket.on('technical_analysis_progress', (data) => {
            updateProgress(data);
        });
        
        socket.on('technical_analysis_complete', (data) => {
            handleAnalysisComplete(data);
            socket.disconnect();
        });
        
        socket.on('technical_analysis_error', (data) => {
            handleAnalysisError(data);
            socket.disconnect();
        });
        
        socket.on('technical_analysis_exists', (data) => {
            handleAnalysisExistsWithSocket(socket, data, url, enableNmap);
        });
    }
    
    function handleAnalysisExistsWithSocket(socket, data, url, enableNmap) {
        if (confirm(`Une analyse existe déjà pour cette URL.\n\nVoulez-vous la mettre à jour ?\n\nL'analyse existante sera mise à jour avec les nouvelles données.`)) {
            // Relancer avec force=true pour mettre à jour
            startTechnicalAnalysisWithSocket(socket, url, enableNmap, true);
        } else {
            // Rediriger vers l'analyse existante
            resetForm();
            socket.disconnect();
            if (data.analysis_id) {
                setTimeout(() => {
                    window.location.href = `/analyse-technique/${data.analysis_id}`;
                }, 500);
            }
        }
    }
    
    function updateProgress(data) {
        const progressBar = document.getElementById('progress-bar');
        const progressMessage = document.getElementById('progress-message');
        
        if (data.progress !== undefined) {
            progressBar.style.width = `${data.progress}%`;
        }
        
        if (data.message) {
            progressMessage.textContent = data.message;
        }
    }
    
    function handleAnalysisComplete(data) {
        const progressBar = document.getElementById('progress-bar');
        const progressMessage = document.getElementById('progress-message');
        
        progressBar.style.width = '100%';
        progressMessage.textContent = 'Analyse terminée avec succès !';
        progressBar.classList.add('success');
        
        showNotification('Analyse technique terminée avec succès !', 'success');
        
        // Recharger la liste des analyses après un court délai
        setTimeout(() => {
            loadAnalyses();
            resetForm();
            
            // Ouvrir automatiquement la modale avec les détails de l'analyse
            if (data.analysis_id) {
                setTimeout(() => {
                    openAnalysisModal(data.analysis_id);
                }, 500);
            } else if (data.results) {
                // Si pas d'analysis_id mais qu'on a les résultats, créer une analyse temporaire pour l'affichage
                showNotification('Analyse terminée mais non sauvegardée. Vérifiez les logs.', 'warning');
            }
        }, 1000);
    }
    
    function handleAnalysisError(data) {
        const progressMessage = document.getElementById('progress-message');
        progressMessage.textContent = `Erreur: ${data.error || 'Erreur inconnue'}`;
        progressMessage.classList.add('error');
        
        setTimeout(() => {
            resetForm();
        }, 3000);
    }
    
    function resetForm() {
        const btn = document.getElementById('btn-start-analysis');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        const progressSection = document.getElementById('analysis-progress');
        const progressBar = document.getElementById('progress-bar');
        const progressMessage = document.getElementById('progress-message');
        
        btn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        progressSection.style.display = 'none';
        progressBar.style.width = '0%';
        progressBar.classList.remove('success');
        progressMessage.classList.remove('error');
        document.getElementById('form-new-analysis').reset();
    }
    
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // Fonction pour la suppression
    async function deleteAnalysis(analysisId, analysisName) {
        if (!confirm(`Êtes-vous sûr de vouloir supprimer l'analyse technique "${analysisName}" ?\n\nCette action est irréversible.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/analyse-technique/${analysisId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                // Afficher un message de succès
                showNotification('Analyse technique supprimée avec succès', 'success');
                
                // Recharger la liste
                loadAnalyses();
            } else {
                showNotification(data.error || 'Erreur lors de la suppression', 'error');
            }
        } catch (error) {
            console.error('Erreur lors de la suppression:', error);
            showNotification('Erreur lors de la suppression de l\'analyse', 'error');
        }
    };
    
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
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
    
    // Fonctions pour la modale
    let currentAnalysisData = null;
    let currentAnalysisId = null;
    
    function openAnalysisModal(analysisId) {
        currentAnalysisId = analysisId;
        const modal = document.getElementById('analysis-modal');
        const modalBody = document.getElementById('modal-body');
        const modalTitle = document.getElementById('modal-title');
        const modalFooter = document.getElementById('modal-footer');
        
        if (!modal) {
            console.error('Modal d\'analyse technique introuvable');
            return;
        }
        
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
        
        loadAnalysisDetail(analysisId);
    }
    
    function closeAnalysisModal() {
        const modal = document.getElementById('analysis-modal');
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
        currentAnalysisData = null;
        currentAnalysisId = null;
    }
    
    async function loadAnalysisDetail(analysisId) {
        try {
            const response = await fetch(`/api/analyse-technique/${analysisId}`);
            if (!response.ok) {
                throw new Error('Analyse introuvable');
            }
            
            currentAnalysisData = await response.json();
            renderAnalysisDetail();
        } catch (error) {
            console.error('Erreur lors du chargement:', error);
            document.getElementById('modal-body').innerHTML = 
                '<div class="error">Erreur lors du chargement des détails</div>';
        }
    }
    
    function renderAnalysisDetail() {
        if (!currentAnalysisData) return;
        
        const date = new Date(currentAnalysisData.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        document.getElementById('modal-title').textContent = 
            `Analyse technique - ${currentAnalysisData.entreprise_nom || currentAnalysisData.url || 'Site web'}`;
        
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = createDetailHTML(date);
        
        // Ajouter les boutons dans le footer
        const modalFooter = document.getElementById('modal-footer');
        modalFooter.innerHTML = `
            <button class="btn btn-primary" id="btn-reanalyze-modal">🔄 Refaire l'analyse</button>
            <button class="btn btn-danger" id="btn-delete-modal">🗑️ Supprimer</button>
            <button class="btn btn-secondary" id="btn-close-modal">Fermer</button>
        `;
        
        // Event listeners pour les boutons
        document.getElementById('btn-close-modal').addEventListener('click', closeAnalysisModal);
        document.getElementById('btn-delete-modal').addEventListener('click', handleDeleteFromModal);
        document.getElementById('btn-reanalyze-modal').addEventListener('click', handleReanalyzeFromModal);
    }
    
    // Fonctions utilitaires pour les scores
    function getSecurityScoreInfo(score) {
        if (score === null || score === undefined || Number.isNaN(Number(score))) {
            return { label: 'Non analysé', className: 'secondary' };
        }
        const s = Math.max(0, Math.min(100, Number(score)));
        if (s >= 80) {
            return { label: `${s}/100 (Sécurisé)`, className: 'success' };
        }
        if (s >= 50) {
            return { label: `${s}/100 (Moyen)`, className: 'warning' };
        }
        return { label: `${s}/100 (Faible)`, className: 'danger' };
    }
    
    function getSecurityScoreBadge(score, id = null) {
        const info = getSecurityScoreInfo(score);
        const idAttr = id ? ` id="${id}"` : '';
        return `<span${idAttr} class="badge badge-${info.className}">${info.label}</span>`;
    }

    function getPerformanceScoreInfo(score) {
        if (score === null || score === undefined || Number.isNaN(Number(score))) {
            return { label: 'Non analysé', className: 'secondary' };
        }
        const s = Math.max(0, Math.min(100, Number(score)));
        if (s >= 80) return { label: `${s}/100 (Rapide)`, className: 'success' };
        if (s >= 50) return { label: `${s}/100 (Moyen)`, className: 'warning' };
        return { label: `${s}/100 (Lent)`, className: 'danger' };
    }

    function getPerformanceScoreBadge(score) {
        const info = getPerformanceScoreInfo(score);
        return `<span class="badge badge-${info.className}">${info.label}</span>`;
    }

    function formatMs(ms) {
        if (!ms && ms !== 0) return 'N/A';
        return `${ms} ms`;
    }

    function formatBytesShort(bytes) {
        if (!bytes && bytes !== 0) return 'N/A';
        const kb = bytes / 1024;
        if (kb < 1024) return `${kb.toFixed(1)} Ko`;
        return `${(kb / 1024).toFixed(2)} Mo`;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function createDetailHTML(date) {
        const techDetails = currentAnalysisData.technical_details || {};
        
        // Calculer le score de sécurité
        let securityScore = typeof currentAnalysisData.security_score === 'number'
            ? currentAnalysisData.security_score
            : (currentAnalysisData.pages_summary?.security_score !== undefined ? currentAnalysisData.pages_summary.security_score : null);

        if (securityScore === null || securityScore === undefined) {
            securityScore = 0;
            if (currentAnalysisData.ssl_valid) {
                securityScore += 40;
            }
            if (currentAnalysisData.waf) {
                securityScore += 25;
            }
            if (currentAnalysisData.cdn) {
                securityScore += 10;
            }
            if (currentAnalysisData.security_headers && typeof currentAnalysisData.security_headers === 'object' && !Array.isArray(currentAnalysisData.security_headers)) {
                const headers = currentAnalysisData.security_headers;
                const importantHeaders = [
                    'Content-Security-Policy',
                    'Strict-Transport-Security',
                    'X-Frame-Options',
                    'X-Content-Type-Options',
                    'Referrer-Policy'
                ];
                let count = 0;
                importantHeaders.forEach(name => {
                    if (headers[name]) {
                        count += 1;
                    }
                });
                securityScore += Math.min(count * 5, 25);
            }
            if (securityScore > 100) {
                securityScore = 100;
            }
        }
        const securityInfo = getSecurityScoreInfo(securityScore);
        
        const pagesSummary = currentAnalysisData.pages_summary || {};
        const pagesList = Array.isArray(currentAnalysisData.pages) ? currentAnalysisData.pages : [];
        const perfScore = typeof currentAnalysisData.performance_score === 'number'
            ? currentAnalysisData.performance_score
            : (pagesSummary.performance_score !== undefined ? pagesSummary.performance_score : null);
        
        const serverLabel = currentAnalysisData.server_software || 'Inconnu';
        const frameworkLabel = currentAnalysisData.framework ? `${currentAnalysisData.framework}${currentAnalysisData.framework_version ? ' ' + currentAnalysisData.framework_version : ''}` : 'Aucun détecté';
        const cmsLabel = currentAnalysisData.cms ? `${currentAnalysisData.cms}${currentAnalysisData.cms_version ? ' ' + currentAnalysisData.cms_version : ''}` : 'Aucun détecté';
        const sslLabel = currentAnalysisData.ssl_valid ? 'SSL valide' : 'SSL non valide';
        const wafLabel = currentAnalysisData.waf || 'Aucun détecté';
        const cdnLabel = currentAnalysisData.cdn || 'Aucun détecté';
        const analyticsCount = currentAnalysisData.analytics && Array.isArray(currentAnalysisData.analytics) ? currentAnalysisData.analytics.length : 0;
        const analyticsLabel = analyticsCount > 0 ? `${analyticsCount} outil(s)` : 'Aucun outil détecté';
        
        return `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- En-tête avec informations générales -->
                <div class="detail-section" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 8px;">
                    <h3 style="margin: 0 0 1rem 0; color: white;">📊 Informations générales</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; color: white;">
                        <div><strong>📅 Date:</strong> ${date}</div>
                        <div><strong>🌐 URL:</strong> <a href="${currentAnalysisData.url}" target="_blank" style="color: #ffd700; text-decoration: underline;">${currentAnalysisData.url}</a></div>
                        <div><strong>🏷️ Domaine:</strong> ${currentAnalysisData.domain || 'N/A'}</div>
                        <div><strong>🔢 IP:</strong> ${currentAnalysisData.ip_address || 'N/A'}</div>
                    </div>
                </div>
                
                <!-- Résumé rapide -->
                <div class="detail-section" style="padding: 0; border-radius: 8px; overflow: hidden;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0; border: 1px solid #e5e7eb;">
                        <div style="padding: 1rem; border-right: 1px solid #e5e7eb; background: #f9fafb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Stack</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>Serveur:</strong> ${escapeHtml(serverLabel)}</div>
                                <div><strong>Framework:</strong> ${escapeHtml(frameworkLabel)}</div>
                                <div><strong>CMS:</strong> ${escapeHtml(cmsLabel)}</div>
                    </div>
                </div>
                        <div style="padding: 1rem; border-right: 1px solid #e5e7eb; background: #fdfdfb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Sécurité</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>SSL:</strong> ${escapeHtml(sslLabel)}</div>
                                <div><strong>WAF:</strong> ${escapeHtml(wafLabel)}</div>
                                <div><strong>CDN:</strong> ${escapeHtml(cdnLabel)}</div>
                                <div><strong>Score global:</strong> ${getSecurityScoreBadge(securityScore)}</div>
                    </div>
                </div>
                        <div style="padding: 1rem; background: #f9fafb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Suivi & analytics</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>Outils d'analyse:</strong> ${escapeHtml(analyticsLabel)}</div>
                                ${perfScore !== null ? `<div><strong>Score performance:</strong> ${getPerformanceScoreBadge(perfScore)}</div>` : ''}
                    </div>
                </div>
                    </div>
                </div>
                
                ${(() => {
                    const pagesCount = pagesSummary.pages_count || pagesSummary.pages_scanned || pagesList.length || 0;
                    if (!pagesCount) return '';
                    const pagesOk = pagesSummary.pages_ok || 0;
                    const pagesError = pagesSummary.pages_error || 0;
                    const trackersCount = pagesSummary.trackers_count || currentAnalysisData.trackers_count || 0;
                    const avgResp = pagesSummary.avg_response_time_ms ? formatMs(pagesSummary.avg_response_time_ms) : 'N/A';
                    const avgWeight = pagesSummary.avg_weight_bytes ? formatBytesShort(pagesSummary.avg_weight_bytes) : 'N/A';
                    const perfBadge = getPerformanceScoreBadge(perfScore);

                    const rows = pagesList.slice(0, 20).map(page => {
                        const pageSecBadge = getSecurityScoreBadge(page.security_score);
                        const pagePerfBadge = getPerformanceScoreBadge(page.performance_score);
                        const statusLabel = page.status_code ? page.status_code : 'N/A';
                        return `
                            <tr>
                                <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis;">
                                    <a href="${page.final_url || page.url}" target="_blank" rel="noopener">${page.url || 'Page'}</a>
                                </td>
                                <td>${statusLabel}</td>
                                <td>${pageSecBadge}</td>
                                <td>${pagePerfBadge}</td>
                                <td>${page.trackers_count || 0}</td>
                            </tr>
                        `;
                    }).join('');

                    return `
                        <div class="detail-section" style="padding: 1rem; background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px;">
                            <h3 style="margin: 0 0 0.75rem 0; color: #1f2937;">🛰️ Analyse multi-pages (${pagesCount} page${pagesCount > 1 ? 's' : ''})</h3>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-bottom: 0.75rem;">
                                <div><strong>Score sécurité:</strong> ${getSecurityScoreBadge(securityScore)}</div>
                                <div><strong>Score perf:</strong> ${perfBadge}</div>
                                <div><strong>Pages OK/Erreur:</strong> <span class="badge badge-success">${pagesOk}</span> / <span class="badge badge-danger">${pagesError}</span></div>
                                <div><strong>Trackers trouvés:</strong> <span class="badge badge-info">${trackersCount}</span></div>
                                <div><strong>Temps moyen:</strong> ${avgResp}</div>
                                <div><strong>Poids moyen:</strong> ${avgWeight}</div>
                    </div>
                            ${rows ? `
                            <div style="overflow-x: auto;">
                                <table class="table" style="width: 100%; border-collapse: collapse;">
                                    <thead>
                                        <tr style="text-align: left; border-bottom: 1px solid #e5e7eb;">
                                            <th style="padding: 0.5rem 0.25rem;">Page</th>
                                            <th style="padding: 0.5rem 0.25rem;">Statut</th>
                                            <th style="padding: 0.5rem 0.25rem;">Sécurité</th>
                                            <th style="padding: 0.5rem 0.25rem;">Perf</th>
                                            <th style="padding: 0.5rem 0.25rem;">Trackers</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${rows}
                                    </tbody>
                                </table>
                            </div>` : ''}
                </div>
                    `;
                })()}
                
                <!-- Serveur et infrastructure -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🖥️ Serveur et infrastructure</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${currentAnalysisData.server_software ? `<div class="info-row"><span class="info-label">Logiciel serveur:</span><span class="info-value"><span class="badge badge-info">${currentAnalysisData.server_software}</span></span></div>` : ''}
                        ${currentAnalysisData.framework ? `<div class="info-row"><span class="info-label">Framework:</span><span class="info-value"><span class="badge badge-primary">${currentAnalysisData.framework}${currentAnalysisData.framework_version ? ' ' + currentAnalysisData.framework_version : ''}</span></span></div>` : ''}
                        ${currentAnalysisData.cms ? `<div class="info-row"><span class="info-label">CMS:</span><span class="info-value"><span class="badge badge-success">${currentAnalysisData.cms}${currentAnalysisData.cms_version ? ' ' + currentAnalysisData.cms_version : ''}</span></span></div>` : ''}
                        ${currentAnalysisData.hosting_provider ? `<div class="info-row"><span class="info-label">Hébergeur:</span><span class="info-value">${currentAnalysisData.hosting_provider}</span></div>` : ''}
                        ${currentAnalysisData.cdn ? `<div class="info-row"><span class="info-label">CDN:</span><span class="info-value"><span class="badge badge-secondary">${currentAnalysisData.cdn}</span></span></div>` : ''}
                        ${currentAnalysisData.waf ? `<div class="info-row"><span class="info-label">WAF:</span><span class="info-value"><span class="badge badge-warning">${currentAnalysisData.waf}</span></span></div>` : ''}
                    </div>
                </div>
                
                ${currentAnalysisData.cms_plugins && Array.isArray(currentAnalysisData.cms_plugins) && currentAnalysisData.cms_plugins.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔌 Plugins CMS <span class="badge badge-info">${currentAnalysisData.cms_plugins.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${currentAnalysisData.cms_plugins.map(plugin => `<span class="badge badge-outline">${escapeHtml(plugin)}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                <!-- Domaine et DNS -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🌍 Domaine et DNS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${currentAnalysisData.domain_creation_date ? `<div class="info-row"><span class="info-label">Date de création:</span><span class="info-value">${currentAnalysisData.domain_creation_date}</span></div>` : ''}
                        ${currentAnalysisData.domain_updated_date ? `<div class="info-row"><span class="info-label">Dernière mise à jour:</span><span class="info-value">${currentAnalysisData.domain_updated_date}</span></div>` : ''}
                        ${currentAnalysisData.domain_registrar ? `<div class="info-row"><span class="info-label">Registrar:</span><span class="info-value">${currentAnalysisData.domain_registrar}</span></div>` : ''}
                    </div>
                </div>
                
                <!-- SSL/TLS -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔒 SSL/TLS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                            <div class="info-row">
                            <span class="info-label">SSL valide:</span>
                                <span class="info-value">
                                <span class="badge ${currentAnalysisData.ssl_valid ? 'badge-success' : 'badge-danger'}">${currentAnalysisData.ssl_valid ? '✓ Oui' : '✗ Non'}</span>
                                </span>
                            </div>
                        ${currentAnalysisData.ssl_expiry_date ? `<div class="info-row"><span class="info-label">Date d'expiration:</span><span class="info-value">${currentAnalysisData.ssl_expiry_date}</span></div>` : ''}
                            </div>
                    </div>
                
                ${currentAnalysisData.security_headers && typeof currentAnalysisData.security_headers === 'object' && !Array.isArray(currentAnalysisData.security_headers) && Object.keys(currentAnalysisData.security_headers).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🛡️ En-têtes de sécurité</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem;">
                        ${Object.entries(currentAnalysisData.security_headers).map(([key, value]) => {
                            let display = '';
                            if (value && typeof value === 'object') {
                                const v = value.value || value.header || '';
                                const status = value.status || value.present;
                                display = v ? v : '';
                                if (status !== undefined && status !== null && status !== '') {
                                    display = display ? `${display} (${status})` : String(status);
                                }
                            } else {
                                display = value || 'N/A';
                            }
                            return `<div class="info-row"><span class="info-label">${escapeHtml(key)}:</span><span class="info-value"><code style="background: #f5f5f5; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem;">${escapeHtml(display)}</code></span></div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.analytics && Array.isArray(currentAnalysisData.analytics) && currentAnalysisData.analytics.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">📈 Outils d'analyse <span class="badge badge-info">${currentAnalysisData.analytics.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${currentAnalysisData.analytics.map(tool => {
                            let label = '';
                            if (tool && typeof tool === 'object') {
                                const name = tool.name || tool.tool || tool.id || tool.tracking_id || '';
                                const extra = tool.id && tool.id !== name ? ` (${tool.id})` :
                                              tool.tracking_id && tool.tracking_id !== name ? ` (${tool.tracking_id})` : '';
                                label = (name || '[Inconnu]') + extra;
                            } else {
                                label = String(tool);
                            }
                            return `<span class="badge badge-secondary">${escapeHtml(label)}</span>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.seo_meta && typeof currentAnalysisData.seo_meta === 'object' && !Array.isArray(currentAnalysisData.seo_meta) ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔍 SEO et métadonnées</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: 1fr; gap: 1rem;">
                        ${currentAnalysisData.seo_meta.meta_title ? `<div class="info-row"><span class="info-label">Titre:</span><span class="info-value">${escapeHtml(currentAnalysisData.seo_meta.meta_title)}</span></div>` : ''}
                        ${currentAnalysisData.seo_meta.meta_description ? `<div class="info-row"><span class="info-label">Description:</span><span class="info-value">${escapeHtml(currentAnalysisData.seo_meta.meta_description)}</span></div>` : ''}
                        ${currentAnalysisData.seo_meta.canonical_url ? `<div class="info-row"><span class="info-label">URL canonique:</span><span class="info-value"><a href="${currentAnalysisData.seo_meta.canonical_url}" target="_blank" style="color: #667eea;">${escapeHtml(currentAnalysisData.seo_meta.canonical_url)}</a></span></div>` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.performance_metrics && typeof currentAnalysisData.performance_metrics === 'object' && !Array.isArray(currentAnalysisData.performance_metrics) && Object.keys(currentAnalysisData.performance_metrics).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">⚡ Métriques de performance</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${Object.entries(currentAnalysisData.performance_metrics).map(([key, value]) => 
                            `<div class="info-row"><span class="info-label">${escapeHtml(key)}:</span><span class="info-value"><strong>${escapeHtml(String(value || 'N/A'))}</strong></span></div>`
                                    ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.nmap_scan ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔍 Scan Nmap</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les détails du scan</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${escapeHtml(JSON.stringify(currentAnalysisData.nmap_scan, null, 2))}</pre>
                    </details>
                            </div>
                        ` : ''}
                
                ${currentAnalysisData.technical_details ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔧 Détails techniques</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir tous les détails</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${escapeHtml(JSON.stringify(currentAnalysisData.technical_details, null, 2))}</pre>
                    </details>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    function hasData(obj, keys) {
        if (!obj) return false;
        return keys.some(key => obj[key] !== undefined && obj[key] !== null && obj[key] !== '');
    }
    
    function createInfoRow(label, value, isLink = false, customContent = null) {
        if (!value && !customContent) return '';
        
        const content = customContent || (isLink ? `<a href="${value}" target="_blank">${value}</a>` : value);
        
        return `
            <div class="info-row">
                <span class="info-label">${label}:</span>
                <span class="info-value">${content}</span>
            </div>
        `;
    }
    
    async function handleDeleteFromModal() {
        const analysisName = currentAnalysisData.entreprise_nom || currentAnalysisData.url || 'cette analyse';
        
        if (!confirm(`Êtes-vous sûr de vouloir supprimer l'analyse technique "${analysisName}" ?\n\nCette action est irréversible.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/analyse-technique/${currentAnalysisId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                showNotification('Analyse technique supprimée avec succès', 'success');
                closeAnalysisModal();
                loadAnalyses(); // Recharger la liste
            } else {
                showNotification(data.error || 'Erreur lors de la suppression', 'error');
            }
        } catch (error) {
            console.error('Erreur lors de la suppression:', error);
            showNotification('Erreur lors de la suppression de l\'analyse', 'error');
        }
    }
    
    function handleReanalyzeFromModal() {
        if (!currentAnalysisData || !currentAnalysisData.url) {
            showNotification('Impossible de relancer l\'analyse : URL introuvable', 'error');
            return;
        }
        
        if (!confirm(`Voulez-vous relancer l'analyse technique pour "${currentAnalysisData.url}" ?\n\nL'analyse existante sera mise à jour avec les nouvelles données.`)) {
            return;
        }
        
        closeAnalysisModal();
        
        // Lancer l'analyse via WebSocket
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('start_technical_analysis', {
                url: currentAnalysisData.url,
                enable_nmap: false,
                force: true
            });
            
            showNotification('Analyse relancée, suivez la progression ci-dessous', 'info');
        } else {
            showNotification('Erreur : WebSocket non disponible', 'error');
        }
    }
    
    // Event listeners pour fermer la modale
    document.addEventListener('DOMContentLoaded', () => {
        const modal = document.getElementById('analysis-modal');
        const modalClose = document.getElementById('modal-close');
        const modalOverlay = modal?.querySelector('.modal-overlay');
        
        if (modalClose) {
            modalClose.addEventListener('click', closeAnalysisModal);
        }
        
        if (modalOverlay) {
            modalOverlay.addEventListener('click', closeAnalysisModal);
        }
        
        // Fermer avec la touche Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal?.classList.contains('active')) {
                closeAnalysisModal();
            }
        });
    });
})();