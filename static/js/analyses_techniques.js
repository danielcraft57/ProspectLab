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
    
    function createDetailHTML(date) {
        const techDetails = currentAnalysisData.technical_details || {};
        
        return `
            <div class="detail-grid">
                <div class="detail-section">
                    <h3>Informations générales</h3>
                    <div class="info-grid">
                        ${createInfoRow('URL', currentAnalysisData.url, true)}
                        ${createInfoRow('Domaine', currentAnalysisData.domain)}
                        ${createInfoRow('Adresse IP', currentAnalysisData.ip_address)}
                        ${createInfoRow('Date d\'analyse', date)}
                    </div>
                </div>
                
                ${currentAnalysisData.server_software ? `
                <div class="detail-section">
                    <h3>Serveur</h3>
                    <div class="info-grid">
                        ${createInfoRow('Logiciel serveur', currentAnalysisData.server_software)}
                        ${createInfoRow('Powered By', techDetails.powered_by)}
                        ${createInfoRow('Version PHP', techDetails.php_version)}
                        ${createInfoRow('Version ASP.NET', techDetails.aspnet_version)}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.framework || currentAnalysisData.cms ? `
                <div class="detail-section">
                    <h3>Framework & CMS</h3>
                    <div class="info-grid">
                        ${createInfoRow('Framework', currentAnalysisData.framework)}
                        ${createInfoRow('Version framework', currentAnalysisData.framework_version)}
                        ${createInfoRow('CMS', currentAnalysisData.cms)}
                        ${createInfoRow('Version CMS', currentAnalysisData.cms_version)}
                        ${currentAnalysisData.cms_plugins && currentAnalysisData.cms_plugins.length > 0 ? `
                            <div class="info-row">
                                <span class="info-label">Plugins CMS:</span>
                                <span class="info-value">
                                    ${Array.isArray(currentAnalysisData.cms_plugins) 
                                        ? currentAnalysisData.cms_plugins.map(p => `<span class="tag">${p}</span>`).join('')
                                        : currentAnalysisData.cms_plugins}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.hosting_provider ? `
                <div class="detail-section">
                    <h3>Hébergement</h3>
                    <div class="info-grid">
                        ${createInfoRow('Hébergeur', currentAnalysisData.hosting_provider)}
                        ${createInfoRow('Date création domaine', currentAnalysisData.domain_creation_date)}
                        ${createInfoRow('Date mise à jour', currentAnalysisData.domain_updated_date)}
                        ${createInfoRow('Registrar', currentAnalysisData.domain_registrar)}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.ssl_valid !== null ? `
                <div class="detail-section">
                    <h3>Sécurité SSL/TLS</h3>
                    <div class="info-grid">
                        ${createInfoRow('Certificat valide', currentAnalysisData.ssl_valid ? 'Oui ✓' : 'Non ✗', false, 
                            currentAnalysisData.ssl_valid ? '<span class="badge badge-success">Valide</span>' : '<span class="badge badge-error">Invalide</span>')}
                        ${createInfoRow('Date d\'expiration', currentAnalysisData.ssl_expiry_date)}
                        ${createInfoRow('Version SSL', techDetails.ssl_version)}
                        ${createInfoRow('Cipher', techDetails.ssl_cipher)}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.security_headers ? `
                <div class="detail-section">
                    <h3>En-têtes de sécurité</h3>
                    <div class="info-grid">
                        ${Object.entries(currentAnalysisData.security_headers).map(([key, value]) => 
                            createInfoRow(key.replace(/_/g, ' '), value ? '✓ Présent' : '✗ Absent', false,
                                value ? '<span class="badge badge-success">Oui</span>' : '<span class="badge badge-error">Non</span>')
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.waf ? `
                <div class="detail-section">
                    <h3>WAF (Web Application Firewall)</h3>
                    <div class="info-grid">
                        ${createInfoRow('WAF détecté', currentAnalysisData.waf)}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.cdn ? `
                <div class="detail-section">
                    <h3>CDN</h3>
                    <div class="info-grid">
                        ${createInfoRow('CDN', currentAnalysisData.cdn)}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.analytics && currentAnalysisData.analytics.length > 0 ? `
                <div class="detail-section">
                    <h3>Analytics & Tracking</h3>
                    <div class="info-grid">
                        ${currentAnalysisData.analytics.map(a => createInfoRow('Service', a)).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.seo_meta ? `
                <div class="detail-section full-width">
                    <h3>SEO</h3>
                    <div class="info-grid">
                        ${Object.entries(currentAnalysisData.seo_meta).slice(0, 10).map(([key, value]) => 
                            createInfoRow(key.replace(/_/g, ' '), value)
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.performance_metrics ? `
                <div class="detail-section full-width">
                    <h3>Performance</h3>
                    <div class="info-grid">
                        ${Object.entries(currentAnalysisData.performance_metrics).map(([key, value]) => 
                            createInfoRow(key.replace(/_/g, ' '), value)
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${currentAnalysisData.nmap_scan ? `
                <div class="detail-section full-width">
                    <h3>Scan Nmap</h3>
                    <div class="info-grid">
                        ${typeof currentAnalysisData.nmap_scan === 'object' 
                            ? Object.entries(currentAnalysisData.nmap_scan).map(([key, value]) => 
                                createInfoRow(key.replace(/_/g, ' '), value)
                            ).join('')
                            : createInfoRow('Résultat', currentAnalysisData.nmap_scan)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['response_time_ms', 'page_size_kb', 'images_count', 'scripts_count']) ? `
                <div class="detail-section">
                    <h3>Performance avancée</h3>
                    <div class="info-grid">
                        ${createInfoRow('Temps de réponse', techDetails.response_time_ms ? `${techDetails.response_time_ms} ms` : null)}
                        ${createInfoRow('Taille de la page', techDetails.page_size_kb ? `${techDetails.page_size_kb} KB` : null)}
                        ${createInfoRow('Nombre d\'images', techDetails.images_count)}
                        ${createInfoRow('Images sans alt', techDetails.images_missing_alt ? `${techDetails.images_missing_alt} images` : null)}
                        ${createInfoRow('Nombre de scripts', techDetails.scripts_count)}
                        ${createInfoRow('Scripts externes', techDetails.external_scripts_count)}
                        ${createInfoRow('Feuilles de style', techDetails.stylesheets_count)}
                        ${createInfoRow('Polices', techDetails.fonts_count)}
                        ${createInfoRow('Liens', techDetails.links_count)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['nextjs', 'nuxtjs', 'svelte', 'gatsby', 'remix', 'astro', 'webpack', 'vite']) ? `
                <div class="detail-section">
                    <h3>Frameworks modernes</h3>
                    <div class="info-grid">
                        ${createInfoRow('Next.js', techDetails.nextjs ? '✓ Détecté' + (techDetails.nextjs_version ? ` (v${techDetails.nextjs_version})` : '') : null)}
                        ${createInfoRow('Nuxt.js', techDetails.nuxtjs ? '✓ Détecté' : null)}
                        ${createInfoRow('Svelte', techDetails.svelte ? '✓ Détecté' : null)}
                        ${createInfoRow('Gatsby', techDetails.gatsby ? '✓ Détecté' : null)}
                        ${createInfoRow('Remix', techDetails.remix ? '✓ Détecté' : null)}
                        ${createInfoRow('Astro', techDetails.astro ? '✓ Détecté' : null)}
                        ${createInfoRow('SvelteKit', techDetails.sveltekit ? '✓ Détecté' : null)}
                        ${createInfoRow('Webpack', techDetails.webpack ? '✓ Détecté' : null)}
                        ${createInfoRow('Vite', techDetails.vite ? '✓ Détecté' : null)}
                        ${createInfoRow('Parcel', techDetails.parcel ? '✓ Détecté' : null)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['html_language', 'charset', 'semantic_html_tags', 'headings_structure']) ? `
                <div class="detail-section">
                    <h3>Structure du contenu</h3>
                    <div class="info-grid">
                        ${createInfoRow('Langue HTML', techDetails.html_language)}
                        ${createInfoRow('Encodage', techDetails.charset)}
                        ${techDetails.semantic_html_tags ? `
                            <div class="info-row">
                                <span class="info-label">Tags sémantiques:</span>
                                <span class="info-value">
                                    ${Object.entries(techDetails.semantic_html_tags).map(([tag, count]) => 
                                        `<span class="tag">${tag}: ${count}</span>`
                                    ).join('')}
                                </span>
                            </div>
                        ` : ''}
                        ${techDetails.headings_structure ? `
                            <div class="info-row">
                                <span class="info-label">Structure des titres:</span>
                                <span class="info-value">
                                    ${Object.entries(techDetails.headings_structure).map(([tag, count]) => 
                                        `<span class="tag">${tag}: ${count}</span>`
                                    ).join('')}
                                </span>
                            </div>
                        ` : ''}
                        ${createInfoRow('Liens externes', techDetails.external_links_count)}
                        ${createInfoRow('Liens internes', techDetails.internal_links_count)}
                        ${createInfoRow('Formulaires', techDetails.forms_count)}
                        ${createInfoRow('Iframes', techDetails.iframes_count)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['mx_records', 'spf_record', 'dmarc_record', 'dkim_record', 'ipv6_support']) ? `
                <div class="detail-section">
                    <h3>DNS avancé</h3>
                    <div class="info-grid">
                        ${createInfoRow('Enregistrements MX', techDetails.mx_records ? '✓ Présents' : null)}
                        ${createInfoRow('SPF', techDetails.spf_record ? '✓ Configuré' : '✗ Non configuré')}
                        ${createInfoRow('DMARC', techDetails.dmarc_record ? '✓ Configuré' : '✗ Non configuré')}
                        ${createInfoRow('DKIM', techDetails.dkim_record ? '✓ Configuré' : '✗ Non configuré')}
                        ${createInfoRow('Support IPv6', techDetails.ipv6_support ? '✓ Oui' : '✗ Non')}
                        ${techDetails.ipv6_addresses ? `
                            <div class="info-row">
                                <span class="info-label">Adresses IPv6:</span>
                                <span class="info-value">
                                    ${techDetails.ipv6_addresses.map(ip => `<span class="tag">${ip}</span>`).join('')}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['mixed_content_detected', 'scripts_without_sri', 'scripts_with_sri', 'cors_enabled']) ? `
                <div class="detail-section">
                    <h3>Sécurité avancée</h3>
                    <div class="info-grid">
                        ${createInfoRow('Contenu mixte', techDetails.mixed_content_detected ? 
                            `<span class="badge badge-error">${techDetails.mixed_content_detected}</span>` : 
                            '<span class="badge badge-success">Aucun</span>')}
                        ${createInfoRow('Scripts sans SRI', techDetails.scripts_without_sri ? 
                            `<span class="badge badge-warning">${techDetails.scripts_without_sri} scripts</span>` : 
                            '<span class="badge badge-success">Tous protégés</span>')}
                        ${createInfoRow('Scripts avec SRI', techDetails.scripts_with_sri ? `${techDetails.scripts_with_sri} scripts` : null)}
                        ${createInfoRow('CORS activé', techDetails.cors_enabled ? techDetails.cors_enabled : null)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['viewport_meta', 'mobile_friendly', 'apple_touch_icon', 'images_missing_alt_count']) ? `
                <div class="detail-section">
                    <h3>Mobilité & Accessibilité</h3>
                    <div class="info-grid">
                        ${createInfoRow('Viewport meta', techDetails.viewport_meta ? 
                            (techDetails.viewport_meta === 'Manquant' ? 
                                '<span class="badge badge-error">Manquant</span>' : 
                                techDetails.viewport_meta) : null)}
                        ${createInfoRow('Mobile-friendly', techDetails.mobile_friendly ? 
                            '<span class="badge badge-success">Oui</span>' : 
                            '<span class="badge badge-error">Non</span>')}
                        ${createInfoRow('Apple Touch Icon', techDetails.apple_touch_icon ? '✓ Présent' : '✗ Absent')}
                        ${createInfoRow('Theme color', techDetails.theme_color)}
                        ${createInfoRow('Images sans alt', techDetails.images_missing_alt_count ? 
                            `<span class="badge badge-warning">${techDetails.images_missing_alt_count} images</span>` : 
                            '<span class="badge badge-success">Toutes ont un alt</span>')}
                        ${createInfoRow('ARIA labels', techDetails.aria_labels_count ? `${techDetails.aria_labels_count} éléments` : null)}
                        ${createInfoRow('Skip links', techDetails.skip_links ? '✓ Présents' : '✗ Absents')}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['graphql_detected', 'api_endpoints_detected', 'websocket_detected', 'json_ld_count']) ? `
                <div class="detail-section">
                    <h3>API & Endpoints</h3>
                    <div class="info-grid">
                        ${createInfoRow('GraphQL', techDetails.graphql_detected ? '✓ Détecté' : null)}
                        ${createInfoRow('Endpoints API', techDetails.api_endpoints_detected)}
                        ${createInfoRow('WebSocket', techDetails.websocket_detected ? '✓ Détecté' : null)}
                        ${createInfoRow('JSON-LD', techDetails.json_ld_count ? `${techDetails.json_ld_count} schémas` : null)}
                        ${techDetails.structured_data_types ? `
                            <div class="info-row">
                                <span class="info-label">Types de données structurées:</span>
                                <span class="info-value">
                                    ${techDetails.structured_data_types.split(', ').map(type => 
                                        `<span class="tag">${type}</span>`
                                    ).join('')}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['crm_service', 'video_service', 'map_service', 'font_service', 'comment_system']) ? `
                <div class="detail-section">
                    <h3>Services tiers supplémentaires</h3>
                    <div class="info-grid">
                        ${createInfoRow('CRM', techDetails.crm_service)}
                        ${techDetails.video_service ? `
                            <div class="info-row">
                                <span class="info-label">Services vidéo:</span>
                                <span class="info-value">
                                    ${Array.isArray(techDetails.video_service) 
                                        ? techDetails.video_service.map(s => `<span class="tag">${s}</span>`).join('')
                                        : `<span class="tag">${techDetails.video_service}</span>`}
                                </span>
                            </div>
                        ` : ''}
                        ${createInfoRow('Service de cartes', techDetails.map_service)}
                        ${techDetails.font_service ? `
                            <div class="info-row">
                                <span class="info-label">Services de polices:</span>
                                <span class="info-value">
                                    ${Array.isArray(techDetails.font_service) 
                                        ? techDetails.font_service.map(s => `<span class="tag">${s}</span>`).join('')
                                        : `<span class="tag">${techDetails.font_service}</span>`}
                                </span>
                            </div>
                        ` : ''}
                        ${createInfoRow('Système de commentaires', techDetails.comment_system)}
                    </div>
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