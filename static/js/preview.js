/**
 * Script de gestion de la page de prévisualisation et d'analyse
 * Gère le lancement de l'analyse, le suivi du scraping et de l'analyse technique en temps réel
 */

(function() {
    // Throttle "trailing" : limite la fréquence de mise à jour UI
    // tout en appliquant la dernière valeur reçue (évite DOM storms + pertes de connexion).
    function createTrailingThrottle(fn, waitMs) {
        let lastCallTs = 0;
        let timer = null;
        let pendingArgs = null;
        return function throttled(...args) {
            const now = Date.now();
            pendingArgs = args;
            const elapsed = now - lastCallTs;
            const run = () => {
                timer = null;
                lastCallTs = Date.now();
                const a = pendingArgs;
                pendingArgs = null;
                try { fn.apply(null, a); } catch (e) {}
            };
            if (elapsed >= waitMs && !timer) {
                run();
                return;
            }
            if (!timer) {
                timer = setTimeout(run, Math.max(0, waitMs - elapsed));
            }
        };
    }

    // Récupérer les données depuis les data attributes
    const pageHeader = document.querySelector('.page-header');
    const filename = pageHeader ? pageHeader.dataset.filename || '' : '';
    const downloadFileUrl = pageHeader ? pageHeader.dataset.downloadFileUrl || '' : '';
    
    const form = document.getElementById('analyze-form');
    const statusDiv = document.getElementById('analyze-status');
    const progressContainer = document.createElement('div');
    progressContainer.id = 'progress-container';
    progressContainer.style.cssText = 'margin-top: 1rem;';
    
    // Barre de progression
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar';
    progressBar.style.cssText = 'width: 100%; height: 30px; background: #f0f0f0; border-radius: 4px; overflow: hidden; margin-bottom: 1rem;';
    
    const progressFill = document.createElement('div');
    progressFill.className = 'progress-fill';
    const DEFAULT_MAIN_PROGRESS_BG = 'linear-gradient(90deg, #3498db, #2980b9)';
    const SUCCESS_MAIN_PROGRESS_BG = 'linear-gradient(90deg, #56ab2f 0%, #a8e063 100%)';
    progressFill.style.cssText = 'height: 100%; background: ' + DEFAULT_MAIN_PROGRESS_BG + '; width: 0%; transition: width 0.3s ease; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 12px;';
    
    const progressText = document.createElement('div');
    progressText.className = 'progress-text';
    progressText.style.cssText = 'padding: 0.5rem; text-align: center; color: #666;';
    
    progressBar.appendChild(progressFill);
    progressContainer.appendChild(progressBar);
    progressContainer.appendChild(progressText);

    // Gestion du bloc de prévisualisation (ouverture/fermeture animée)
    const previewSection = document.getElementById('preview-section');
    const previewContent = document.getElementById('preview-content');
    const previewToggleBtn = document.getElementById('preview-toggle-btn');

    function setPreviewExpanded(expanded) {
        if (!previewSection || !previewContent || !previewToggleBtn) return;
        var icon = previewToggleBtn.querySelector('.preview-toggle-icon');
        var label = previewToggleBtn.querySelector('.preview-toggle-label');
        if (expanded) {
            previewSection.classList.remove('preview-collapsed');
            previewSection.classList.add('preview-expanded');
            previewContent.style.maxHeight = previewContent.scrollHeight + 'px';
            previewToggleBtn.setAttribute('aria-expanded', 'true');
            if (icon) { icon.classList.remove('fa-chevron-down'); icon.classList.add('fa-chevron-up'); }
            if (label) { label.textContent = 'Réduire l\'aperçu'; }
        } else {
            previewSection.classList.remove('preview-expanded');
            previewSection.classList.add('preview-collapsed');
            previewContent.style.maxHeight = '0px';
            previewToggleBtn.setAttribute('aria-expanded', 'false');
            if (icon) { icon.classList.remove('fa-chevron-up'); icon.classList.add('fa-chevron-down'); }
            if (label) { label.textContent = 'Afficher l\'aperçu détaillé'; }
        }
    }

    if (previewToggleBtn) {
        previewToggleBtn.addEventListener('click', function() {
            const isExpanded = previewSection.classList.contains('preview-expanded');
            setPreviewExpanded(!isExpanded);
        });

        // Initial: aperçu replié mais avec une petite animation si l'utilisateur ouvre
        setPreviewExpanded(false);
    }
    
    // Fonction pour vérifier et attendre la connexion WebSocket
    function waitForWebSocket(callback, maxWait = 10000) {
        const startTime = Date.now();
        
        function checkConnection() {
            if (typeof window.wsManager !== 'undefined' && window.wsManager && window.wsManager.connected) {
                callback(true);
                return;
            }
            
            if (Date.now() - startTime < maxWait) {
                setTimeout(checkConnection, 100);
            } else {
                // Essayer de se connecter une dernière fois
                if (typeof window.wsManager !== 'undefined' && window.wsManager) {
                    if (!window.wsManager.connected) {
                        window.wsManager.connect();
                        setTimeout(() => {
                            if (window.wsManager.connected) {
                                callback(true);
                            } else {
                                callback(false);
                            }
                        }, 1000);
                    } else {
                        callback(true);
                    }
                } else {
                    callback(false);
                }
            }
        }
        
        checkConnection();
    }
    
    // Section pour l'avancement de l'analyse Pentest
    const pentestProgressContainer = document.createElement('div');
    pentestProgressContainer.id = 'pentest-progress-container';
    // Style adapté au thème sombre (fond sombre + bordure rouge atténuée)
    pentestProgressContainer.style.cssText = 'margin-top: 1.5rem; padding: 1.25rem; background: rgba(15,23,42,0.95); border-radius: 10px; border: 1px solid rgba(248,113,113,0.35); border-left: 5px solid #ef4444; display: none; box-shadow: 0 8px 20px rgba(15,23,42,0.9);';

    const pentestProgressTitleRow = document.createElement('div');
    pentestProgressTitleRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.75rem;';

    const pentestProgressTitle = document.createElement('div');
    pentestProgressTitle.style.cssText = 'font-weight: 700; color: #e5e7eb;';
    pentestProgressTitle.textContent = 'Analyse Pentest';

    const pentestProgressCountBadge = document.createElement('div');
    pentestProgressCountBadge.id = 'pentest-progress-count';
    pentestProgressCountBadge.style.cssText = 'background: rgba(239,68,68,0.15); color: #fecaca; border: 1px solid rgba(248,113,113,0.6); padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700; white-space: nowrap;';
    pentestProgressCountBadge.textContent = '0 / 0 entreprises';

    pentestProgressTitleRow.appendChild(pentestProgressTitle);
    pentestProgressTitleRow.appendChild(pentestProgressCountBadge);

    const pentestCurrentLabelRow = document.createElement('div');
    pentestCurrentLabelRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem;';

    const pentestCurrentLabel = document.createElement('div');
    pentestCurrentLabel.style.cssText = 'font-size: 0.85rem; color: #9ca3af; font-weight: 600;';
    pentestCurrentLabel.textContent = 'Entreprise en cours :';

    const pentestCurrentInfo = document.createElement('div');
    pentestCurrentInfo.id = 'pentest-current-info';
    pentestCurrentInfo.style.cssText = 'font-size: 0.85rem; color: #e5e7eb; font-weight: 500; flex: 1; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;';
    pentestCurrentInfo.textContent = '';

    pentestCurrentLabelRow.appendChild(pentestCurrentLabel);
    pentestCurrentLabelRow.appendChild(pentestCurrentInfo);

    const pentestCurrentBar = document.createElement('div');
    pentestCurrentBar.style.cssText = 'width: 100%; height: 18px; background: rgba(15,23,42,0.8); border-radius: 10px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';

    const pentestCurrentFill = document.createElement('div');
    pentestCurrentFill.id = 'pentest-current-fill';
    pentestCurrentFill.style.cssText = 'height: 100%; background: linear-gradient(90deg, #e74c3c, #c0392b); width: 0%; transition: width 0.3s ease; display: flex; align-items: center; justify-content: center;';

    const pentestCurrentLabelInner = document.createElement('div');
    pentestCurrentLabelInner.id = 'pentest-current-label';
    pentestCurrentLabelInner.style.cssText = 'color: #ffffff; font-size: 0.8rem; font-weight: 600; white-space: nowrap;';
    pentestCurrentLabelInner.textContent = '0%';

    pentestCurrentBar.appendChild(pentestCurrentFill);
    pentestCurrentFill.appendChild(pentestCurrentLabelInner);

    const pentestTotalLabelRow = document.createElement('div');
    pentestTotalLabelRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem;';

    const pentestTotalLabel = document.createElement('div');
    pentestTotalLabel.style.cssText = 'font-size: 0.85rem; color: #9ca3af; font-weight: 600;';
    pentestTotalLabel.textContent = 'Progression globale :';

    const pentestTotalInfo = document.createElement('div');
    pentestTotalInfo.id = 'pentest-total-info';
    pentestTotalInfo.style.cssText = 'font-size: 0.85rem; color: #e5e7eb; font-weight: 500; flex: 1; text-align: right;';
    pentestTotalInfo.textContent = '';

    pentestTotalLabelRow.appendChild(pentestTotalLabel);
    pentestTotalLabelRow.appendChild(pentestTotalInfo);

    const pentestTotalBar = document.createElement('div');
    pentestTotalBar.style.cssText = 'width: 100%; height: 18px; background: rgba(15,23,42,0.8); border-radius: 10px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';

    const pentestTotalFill = document.createElement('div');
    pentestTotalFill.id = 'pentest-total-fill';
    pentestTotalFill.style.cssText = 'height: 100%; background: linear-gradient(90deg, #f39c12, #d35400); width: 0%; transition: width 0.3s ease; display: flex; align-items: center; justify-content: center;';

    const pentestTotalLabelInner = document.createElement('div');
    pentestTotalLabelInner.id = 'pentest-total-label';
    pentestTotalLabelInner.style.cssText = 'color: #ffffff; font-size: 0.8rem; font-weight: 600; white-space: nowrap;';
    pentestTotalLabelInner.textContent = '0%';

    pentestTotalBar.appendChild(pentestTotalFill);
    pentestTotalFill.appendChild(pentestTotalLabelInner);

    // Section pour les totaux cumulés Pentest (similaire à OSINT)
    const pentestCumulativeBox = document.createElement('div');
    pentestCumulativeBox.id = 'pentest-cumulative-box';
    pentestCumulativeBox.style.cssText = 'background: rgba(30,64,175,0.12); padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid rgba(59,130,246,0.4); border-left: 4px solid #3b82f6; margin-top: 0.75rem;';
    
    const pentestCumulativeLabel = document.createElement('div');
    pentestCumulativeLabel.style.cssText = 'font-size: 0.78rem; color: #bfdbfe; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;';
    pentestCumulativeLabel.textContent = 'Total cumulé';
    
    const pentestCumulativeContent = document.createElement('div');
    pentestCumulativeContent.id = 'pentest-cumulative-content';
    pentestCumulativeContent.style.cssText = 'color: #e5e7eb; font-size: 0.95rem; font-weight: 700; line-height: 1.6; display: flex; flex-wrap: wrap; align-items: center;';
    pentestCumulativeContent.textContent = '';
    
    pentestCumulativeBox.appendChild(pentestCumulativeLabel);
    pentestCumulativeBox.appendChild(pentestCumulativeContent);
    
    pentestProgressContainer.appendChild(pentestProgressTitleRow);
    pentestProgressContainer.appendChild(pentestCurrentLabelRow);
    pentestProgressContainer.appendChild(pentestCurrentBar);
    pentestProgressContainer.appendChild(pentestTotalLabelRow);
    pentestProgressContainer.appendChild(pentestTotalBar);
    pentestProgressContainer.appendChild(pentestCumulativeBox);

    // Fonction utilitaire pour afficher des toasts/notifications
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        const colors = {
            success: { bg: '#10b981', border: '#059669' },
            info: { bg: '#3b82f6', border: '#2563eb' },
            warning: { bg: '#f59e0b', border: '#d97706' },
            error: { bg: '#ef4444', border: '#dc2626' }
        };
        const color = colors[type] || colors.success;
        
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${color.bg};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            font-weight: 600;
            font-size: 0.95rem;
            max-width: 400px;
            border-left: 4px solid ${color.border};
            animation: slideIn 0.3s ease-out;
        `;
        toast.innerHTML = message;
        
        // Animation CSS
        if (!document.getElementById('toast-animations')) {
            const style = document.createElement('style');
            style.id = 'toast-animations';
            style.textContent = `
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 4000);
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Si aucune nouvelle entreprise, ne pas lancer l'analyse
        const totalEl = document.getElementById('preview-stat-total');
        if (totalEl) {
            const rawText = totalEl.textContent || totalEl.innerText || '0';
            const newTotal = parseInt(rawText.replace(/\D/g, '') || rawText, 10) || 0;
            if (newTotal === 0) {
                showToast('Aucune nouvelle entreprise à analyser pour ce fichier.', 'info');
                return;
            }
        }
        
        // Récupérer le nombre de workers depuis l'attribut data du page-header
        const pageHeader = document.querySelector('.page-header');
        const celeryWorkersAttr = pageHeader ? pageHeader.getAttribute('data-celery-workers') : null;
        const celeryWorkers = celeryWorkersAttr ? parseInt(celeryWorkersAttr, 10) : 4;
        
        // Debug: afficher la valeur récupérée
        console.log('Celery workers récupérés:', celeryWorkers, 'depuis data-celery-workers:', celeryWorkersAttr);
        
        // S'assurer que la valeur est valide (au moins 1)
        const validCeleryWorkers = isNaN(celeryWorkers) || celeryWorkers < 1 ? 4 : celeryWorkers;
        
        // Valeurs optimisées pour Celery avec --pool=threads --concurrency dynamique
        // Celery gère déjà la concurrence, pas besoin de délai artificiel
        const maxWorkers = validCeleryWorkers;  // Utilise la valeur depuis la config
        const delay = 0.1;     // Délai minimal, Celery gère la concurrence
        
        // Afficher le statut
        statusDiv.style.display = 'block';
        statusDiv.className = 'status-message status-info';
        statusDiv.innerHTML = 'Connexion au serveur...';
        
        // Ajouter la barre de progression
        if (!statusDiv.nextElementSibling || statusDiv.nextElementSibling.id !== 'progress-container') {
            statusDiv.after(progressContainer);
        }

        // Mettre en avant la carte d'analyse et replier l'aperçu pour focaliser l'attention
        const analyzeCard = document.querySelector('.analyze-card');
        if (analyzeCard) {
            analyzeCard.classList.add('analyze-active');
        }
        if (previewSection && previewContent && previewToggleBtn) {
            setPreviewExpanded(false);
        }
        
        progressFill.style.width = '0%';
        progressFill.textContent = '0%';
        // Important: réinitialiser la couleur si une analyse précédente a échoué (barre rouge)
        progressFill.style.background = DEFAULT_MAIN_PROGRESS_BG;
        progressText.textContent = 'Connexion en cours...';
        
        // Désactiver le formulaire et afficher le bouton stop
        const startBtn = document.getElementById('start-analysis-btn');
        const stopBtn = document.getElementById('stop-analysis-btn');
        startBtn.disabled = true;
        stopBtn.style.display = 'inline-block';
        
        // Attendre la connexion WebSocket avant de lancer l'analyse
        waitForWebSocket(function(connected) {
            if (!connected) {
                statusDiv.className = 'status-message status-error';
                statusDiv.textContent = 'Connexion WebSocket non disponible. Veuillez recharger la page.';
                startBtn.disabled = false;
                stopBtn.style.display = 'none';
                return;
            }
            
            // Connexion établie, lancer l'analyse
            statusDiv.className = 'status-message status-info';
            statusDiv.innerHTML = `Connexion établie. Démarrage de l'analyse avec Celery (${validCeleryWorkers} workers)...`;
            progressText.textContent = 'Initialisation...';
            
            window.wsManager.startAnalysis(filename, {
                max_workers: maxWorkers,
                delay: delay
            });
        });
    });
    
    // Gestion du bouton stop
    document.getElementById('stop-analysis-btn').addEventListener('click', function() {
        if (window.wsManager && window.wsManager.stopAnalysis) {
            window.wsManager.stopAnalysis();
        }
    });
    
    // Écouter les événements WebSocket
    document.addEventListener('analysis:started', function(e) {
        statusDiv.className = 'status-message status-info';
        statusDiv.textContent = e.detail.message || 'Analyse démarrée...';
        progressText.textContent = 'Analyse en cours...';
        // Si on relance après une erreur, revenir au style normal
        progressFill.style.background = DEFAULT_MAIN_PROGRESS_BG;
        pentestDone = false;
        pentestProgressContainer.style.display = 'none';
        
        // Faire défiler vers le bas pour voir les sections de progression
        setTimeout(() => {
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: 'smooth'
            });
        }, 300);
    });
    
    document.addEventListener('analysis:stopping', function(e) {
        statusDiv.className = 'status-message status-info';
        statusDiv.textContent = e.detail.message || 'Arrêt de l\'analyse en cours...';
        progressText.textContent = 'Arrêt en cours...';
    });
    
    document.addEventListener('analysis:stopped', function(e) {
        const data = e.detail;
        statusDiv.className = 'status-message status-warning';
        statusDiv.innerHTML = `
            ${data.message}<br>
            ${data.output_file ? `<a href="${downloadFileUrl}${data.output_file}" class="btn btn-success" style="margin-top: 1rem;">Télécharger les résultats partiels</a>` : ''}
        `;
        
        progressFill.style.background = '#f39c12';
        progressText.textContent = `Arrêté : ${data.current}/${data.total} entreprises analysées`;
        
        // Réactiver le formulaire et masquer le bouton stop
        const startBtn = document.getElementById('start-analysis-btn');
        const stopBtn = document.getElementById('stop-analysis-btn');
        startBtn.disabled = false;
        stopBtn.style.display = 'none';
    });
    
    // Section pour l'avancement du scraping
    const scrapingProgressContainer = document.createElement('div');
    scrapingProgressContainer.id = 'scraping-progress-container';
    scrapingProgressContainer.style.cssText = 'margin-top: 1.5rem; padding: 1.5rem; background: #ffffff; border-radius: 10px; border: 1px solid #d7e3f0; border-left: 5px solid #1f6feb; display: none; box-shadow: 0 6px 16px rgba(17,24,39,0.08);';
    
    const scrapingProgressTitle = document.createElement('div');
    scrapingProgressTitle.style.cssText = 'font-weight: 700; margin-bottom: 1rem; color: #111827; font-size: 1.1rem;';
    scrapingProgressTitle.textContent = 'Scraping du site web en cours...';
    
    // Barre de progression pour les entreprises
    const entreprisesProgressBar = document.createElement('div');
    entreprisesProgressBar.style.cssText = 'width: 100%; height: 24px; background: #e5e7eb; border-radius: 12px; overflow: hidden; margin-bottom: 1rem; position: relative;';
    
    const entreprisesProgressFill = document.createElement('div');
    entreprisesProgressFill.id = 'entreprises-progress-fill';
    entreprisesProgressFill.style.cssText = 'height: 100%; background: linear-gradient(90deg, #1f6feb, #0b5bd3); width: 0%; transition: width 0.3s ease; display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 11px;';
    
    const entreprisesProgressText = document.createElement('div');
    entreprisesProgressText.id = 'entreprises-progress-text';
    entreprisesProgressText.style.cssText = 'position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #ffffff; font-size: 0.85rem; font-weight: 600; pointer-events: none;';
    entreprisesProgressText.textContent = '0 / 0 entreprises';
    
    entreprisesProgressBar.appendChild(entreprisesProgressFill);
    entreprisesProgressBar.appendChild(entreprisesProgressText);
    
    // Conteneur pour les stats avec design amélioré
    const scrapingStatsContainer = document.createElement('div');
    scrapingStatsContainer.id = 'scraping-stats-container';
    scrapingStatsContainer.style.cssText = 'display: flex; flex-direction: column; gap: 0.75rem;';
    
    const scrapingProgressText = document.createElement('div');
    scrapingProgressText.id = 'scraping-progress-text';
    scrapingProgressText.style.cssText = 'color: #111827; font-size: 0.92rem; line-height: 1.6;';
    scrapingProgressText.textContent = 'Initialisation...';
    
    scrapingStatsContainer.appendChild(scrapingProgressText);
    
    scrapingProgressContainer.appendChild(scrapingProgressTitle);
    scrapingProgressContainer.appendChild(entreprisesProgressBar);
    scrapingProgressContainer.appendChild(scrapingStatsContainer);
    
    const throttledMainAnalysisProgress = createTrailingThrottle(function(e) {
        const data = e.detail;
        const percentage = data.percentage || 0;
        
        // Si une erreur précédente a coloré la barre en rouge, revenir au dégradé normal
        if (progressFill.style.background === 'rgb(231, 76, 60)' || progressFill.style.background === '#e74c3c') {
            progressFill.style.background = DEFAULT_MAIN_PROGRESS_BG;
        }
        progressFill.style.width = percentage + '%';
        progressFill.textContent = percentage + '%';
        progressText.textContent = data.message || `${data.current}/${data.total} entreprises analysées`;
        
        if (data.current_entreprise) {
            statusDiv.innerHTML = `Analyse en cours: <strong>${data.current_entreprise}</strong> (${data.current}/${data.total})`;
        }
    }, 120);
    document.addEventListener('analysis:progress', throttledMainAnalysisProgress);
    
    // Écouter les événements de scraping
    function setupScrapingListener() {
        if (window.wsManager && window.wsManager.socket) {
            // Retirer l'ancien listener s'il existe
            window.wsManager.socket.off('scraping_progress');
            window.wsManager.socket.off('scraping_complete');
            
            const throttledScrapingProgress = createTrailingThrottle(function(data) {
                if (!scrapingProgressContainer.parentNode) {
                    progressContainer.after(scrapingProgressContainer);
                }
                scrapingProgressContainer.style.display = 'block';
                
                // Mettre à jour la barre de progression des entreprises
                if (typeof data.current === 'number' && typeof data.total === 'number' && data.total > 0) {
                    const percent = Math.min(100, (data.current / data.total) * 100);
                    entreprisesProgressFill.style.width = percent + '%';
                    entreprisesProgressText.textContent = `${data.current} / ${data.total} entreprises`;
                } else if (typeof data.current === 'number' && data.current > 0) {
                    // Si on a seulement current, afficher quand même
                    entreprisesProgressFill.style.width = '0%';
                    entreprisesProgressText.textContent = `${data.current} entreprise(s) en cours...`;
                }
                
                const message = data.message || 'Scraping en cours...';
                
                // Extraire le domaine depuis l'URL si disponible
                let domaine = '';
                if (data.url) {
                    try {
                        const url = new URL(data.url);
                        domaine = url.hostname.replace('www.', '');
                    } catch (e) {
                        // Si l'URL n'est pas valide, essayer d'extraire le domaine manuellement
                        const match = data.url.match(/https?:\/\/(?:www\.)?([^\/]+)/);
                        if (match) {
                            domaine = match[1];
                        }
                    }
                }
                
                // Parser le message pour séparer les stats de l'entreprise et le total
                // Format attendu: "{message} - {stats entreprise} | Total: {stats globales}"
                // Ou: "{message} - {stats entreprise} - {domaine} ({entreprise}) - {stats entreprise}"
                let currentStats = '';
                let totalStats = '';
                let baseMessage = message;
                
                if (message.includes(' | Total: ')) {
                    const parts = message.split(' | Total: ');
                    const beforeTotal = parts[0];
                    totalStats = parts[1] || '';
                    
                    // Extraire le message de base (avant les stats)
                    // Format: "{message} - {stats entreprise}"
                    if (beforeTotal.includes(' - ')) {
                        const messageParts = beforeTotal.split(' - ');
                        // Le premier élément est le message de base (ex: "25 page(s)")
                        baseMessage = messageParts[0];
                        // Les éléments suivants sont les stats, mais il peut y avoir le domaine/entreprise dedans
                        // On cherche la partie qui contient les stats (emails, personnes, téléphones, etc.)
                        const statsParts = messageParts.slice(1);
                        // Filtrer pour ne garder que les parties avec des stats (contiennent "emails", "personnes", etc.)
                        currentStats = statsParts.filter(part => 
                            part.includes('emails') || part.includes('personnes') || 
                            part.includes('téléphones') || part.includes('réseaux') || 
                            part.includes('technos') || part.includes('images')
                        ).join(' - ');
                        
                        // Si on n'a pas trouvé de stats, prendre tout sauf le premier élément
                        if (!currentStats && statsParts.length > 0) {
                            currentStats = statsParts.join(' - ');
                        }
                    } else {
                        baseMessage = beforeTotal;
                    }
                } else if (message.includes(' - ')) {
                    // Format sans total séparé
                    const parts = message.split(' - ');
                    baseMessage = parts[0];
                    // Filtrer pour ne garder que les parties avec des stats
                    const statsParts = parts.slice(1).filter(part => 
                        part.includes('emails') || part.includes('personnes') || 
                        part.includes('téléphones') || part.includes('réseaux') || 
                        part.includes('technos') || part.includes('images')
                    );
                    currentStats = statsParts.length > 0 ? statsParts.join(' - ') : parts.slice(1).join(' - ');
                }
                
                // Construire l'affichage HTML avec des balises stylisées
                let htmlContent = '';
                const isDark = document.body && (document.body.getAttribute('data-theme') === 'dark');
                
                // Message de base avec entreprise et domaine
                if (baseMessage) {
                    htmlContent += `<div style="margin-bottom: 0.75rem; font-weight: 500; color: #2c3e50;">${baseMessage}`;
                if (domaine) {
                        htmlContent += ` <span style="color: #3498db;">- ${domaine}</span>`;
                    }
                    if (data.entreprise) {
                        htmlContent += ` <span style="color: #27ae60;">(${data.entreprise})</span>`;
                    }
                    htmlContent += `</div>`;
                }
                
                // Stats de l'entreprise courante dans une balise stylisée (contraste renforcé)
                if (currentStats) {
                    const boxBg = isDark ? '#0f172a' : '#e6f0ff';
                    const boxBorder = isDark ? '#1d4ed8' : '#b6d4fe';
                    const boxBorderLeft = isDark ? '#60a5fa' : '#1f6feb';
                    const labelColor = isDark ? '#bfdbfe' : '#0b5bd3';
                    const valueColor = isDark ? '#e5e7eb' : '#111827';
                    htmlContent += `<div style="background: ${boxBg}; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid ${boxBorder}; border-left: 4px solid ${boxBorderLeft}; margin-bottom: 0.75rem;">`;
                    htmlContent += `<div style="font-size: 0.78rem; color: ${labelColor}; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;">Entreprise actuelle</div>`;
                    htmlContent += `<div style="color: ${valueColor}; font-size: 0.95rem; font-weight: 600;">${currentStats}</div>`;
                    htmlContent += `</div>`;
                }
                
                // Total cumulé dans une balise stylisée différente (contraste renforcé)
                if (totalStats) {
                    const boxBg = isDark ? '#022c22' : '#e9fbf1';
                    const boxBorder = isDark ? '#059669' : '#a7f3d0';
                    const boxBorderLeft = isDark ? '#22c55e' : '#16a34a';
                    const labelColor = isDark ? '#bbf7d0' : '#166534';
                    const valueColor = isDark ? '#e5e7eb' : '#111827';
                    htmlContent += `<div style="background: ${boxBg}; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid ${boxBorder}; border-left: 4px solid ${boxBorderLeft};">`;
                    htmlContent += `<div style="font-size: 0.78rem; color: ${labelColor}; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;">Total cumulé</div>`;
                    htmlContent += `<div style="color: ${valueColor}; font-size: 0.95rem; font-weight: 700;">${totalStats}</div>`;
                    htmlContent += `</div>`;
                } else if (typeof data.total_emails === 'number' || typeof data.total_phones === 'number') {
                    // Fallback: utiliser les données individuelles si le parsing échoue
                    const counters = [];
                    if (typeof data.total_emails === 'number') counters.push(`${data.total_emails} emails`);
                    if (typeof data.total_people === 'number') counters.push(`${data.total_people} personnes`);
                    if (typeof data.total_phones === 'number') counters.push(`${data.total_phones} téléphones`);
                    if (typeof data.total_social_platforms === 'number') counters.push(`${data.total_social_platforms} réseaux sociaux`);
                    if (typeof data.total_technologies === 'number') counters.push(`${data.total_technologies} technos`);
                    if (typeof data.total_images === 'number') counters.push(`${data.total_images} images`);
                    
                    if (counters.length > 0) {
                        const boxBg = isDark ? '#022c22' : '#e9fbf1';
                        const boxBorder = isDark ? '#059669' : '#a7f3d0';
                        const boxBorderLeft = isDark ? '#22c55e' : '#16a34a';
                        const labelColor = isDark ? '#bbf7d0' : '#166534';
                        const valueColor = isDark ? '#e5e7eb' : '#111827';
                        htmlContent += `<div style="background: ${boxBg}; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid ${boxBorder}; border-left: 4px solid ${boxBorderLeft};">`;
                        htmlContent += `<div style="font-size: 0.78rem; color: ${labelColor}; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;">Total cumulé</div>`;
                        htmlContent += `<div style="color: ${valueColor}; font-size: 0.95rem; font-weight: 700;">${counters.join(', ')}</div>`;
                        htmlContent += `</div>`;
                    }
                }

                scrapingProgressText.innerHTML = htmlContent || 'Scraping en cours...';
            }, 200);
            window.wsManager.socket.on('scraping_progress', throttledScrapingProgress);

            // Afficher un résumé final quand le scraping est terminé
            window.wsManager.socket.on('scraping_complete', function(data) {
                if (!scrapingProgressContainer.parentNode) {
                    progressContainer.after(scrapingProgressContainer);
                }
                scrapingProgressContainer.style.display = 'block';
                // Dénominateur OSINT/Pentest : garder le total si pas encore défini
                const n = data.total_entreprises || data.scraped_count;
                if (typeof totalAnalysisEnterprises !== 'undefined' && typeof n === 'number' && n > 0 && totalAnalysisEnterprises === 0) {
                    totalAnalysisEnterprises = n;
                }
                // Mettre à jour la barre de progression à 100%
                const totalForBar = data.total || data.total_entreprises || data.scraped_count || 0;
                if (totalForBar > 0) {
                    entreprisesProgressFill.style.width = '100%';
                    entreprisesProgressText.textContent = `${totalForBar} / ${totalForBar} entreprises`;
                }

                const counters = [];
                if (typeof data.total_emails === 'number') {
                    counters.push(`${data.total_emails} emails`);
                }
                if (typeof data.total_people === 'number') {
                    counters.push(`${data.total_people} personnes`);
                }
                if (typeof data.total_phones === 'number') {
                    counters.push(`${data.total_phones} téléphones`);
                }
                if (typeof data.total_social_platforms === 'number') {
                    counters.push(`${data.total_social_platforms} réseaux sociaux`);
                }
                if (typeof data.total_technologies === 'number') {
                    counters.push(`${data.total_technologies} technos`);
                }
                if (typeof data.total_images === 'number') {
                    counters.push(`${data.total_images} images`);
                }

                // Afficher le résumé final avec un style adapté au thème
                const isDark = document.body && (document.body.getAttribute('data-theme') === 'dark');
                const summaryBg = isDark ? '#022c22' : 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)';
                const summaryBorderLeft = isDark ? '#22c55e' : '#27ae60';
                const titleColor = isDark ? '#bbf7d0' : '#229954';
                const textColor = isDark ? '#e5e7eb' : '#2c3e50';
                
                let htmlContent = `<div style="background: ${summaryBg}; padding: 1rem; border-radius: 6px; border-left: 3px solid ${summaryBorderLeft};">`;
                htmlContent += `<div style="font-size: 0.9rem; color: ${titleColor}; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;"><i class="fas fa-check"></i> Scraping terminé</div>`;
                if (counters.length > 0) {
                    htmlContent += `<div style="color: ${textColor}; font-size: 0.95rem; font-weight: 500;">${counters.join(', ')}</div>`;
                } else {
                    htmlContent += `<div style="color: ${textColor}; font-size: 0.95rem;">Scraping terminé avec succès</div>`;
                }
                htmlContent += '</div>';
                
                scrapingProgressText.innerHTML = htmlContent;
                
                // Toast de notification
                const scrapedCount = data.scraped_count || data.total_entreprises || 0;
                showToast(`<i class="fas fa-check"></i> Scraping terminé pour ${scrapedCount} entreprise(s)`, 'success');
                
                // Déclencher l'événement personnalisé pour la redirection
                const event = new CustomEvent('scraping_complete', { detail: data });
                document.dispatchEvent(event);
            });
            
            // Initialiser la barre de progression au démarrage
            window.wsManager.socket.on('scraping_started', function(data) {
                if (!scrapingProgressContainer.parentNode) {
                    progressContainer.after(scrapingProgressContainer);
                }
                scrapingProgressContainer.style.display = 'block';
                entreprisesProgressFill.style.width = '0%';
                // Total pour dénominateur OSINT/Pentest (utilisé aussi par technical_analysis_*)
                if (typeof data.total === 'number' && data.total > 0 && typeof totalAnalysisEnterprises !== 'undefined') {
                    totalAnalysisEnterprises = data.total;
                }
                if (data.total && data.total > 0) {
                    entreprisesProgressText.textContent = `0 / ${data.total} entreprises`;
                } else {
                    entreprisesProgressText.textContent = 'Initialisation...';
                }
                scrapingProgressText.innerHTML = '<div style="color: #666;">Initialisation du scraping...</div>';
                
                setTimeout(() => {
                    scrapingProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            });
        }
    }
    
    // Section pour l'avancement de l'analyse technique
    // Nombre total d'entreprises pour cette analyse (avec site),
    // utilisé aussi comme dénominateur pour OSINT et Pentest.
    let totalAnalysisEnterprises = 0;

    const technicalProgressContainer = document.createElement('div');
    technicalProgressContainer.id = 'technical-progress-container';
    // Fond sombre pour s'aligner avec le thème global
    technicalProgressContainer.style.cssText = 'margin-top: 1.5rem; padding: 1.25rem; background: rgba(15,23,42,0.95); border-radius: 10px; border: 1px solid rgba(34,197,94,0.35); border-left: 5px solid #22c55e; display: none; box-shadow: 0 8px 20px rgba(15,23,42,0.9);';
    
    const technicalProgressTitleRow = document.createElement('div');
    technicalProgressTitleRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.75rem;';
    
    const technicalProgressTitle = document.createElement('div');
    technicalProgressTitle.style.cssText = 'font-weight: 700; color: #e5e7eb;';
    // Mettre en avant que cette analyse inclut aussi SEO (Lighthouse)
    technicalProgressTitle.textContent = 'Analyse technique + SEO en cours...';
    
    const technicalProgressCountBadge = document.createElement('div');
    technicalProgressCountBadge.id = 'technical-progress-count';
    technicalProgressCountBadge.style.cssText = 'background: rgba(34,197,94,0.18); color: #bbf7d0; border: 1px solid rgba(74,222,128,0.7); padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700; white-space: nowrap;';
    technicalProgressCountBadge.textContent = '0 / 0 entreprises';
    
    technicalProgressTitleRow.appendChild(technicalProgressTitle);
    technicalProgressTitleRow.appendChild(technicalProgressCountBadge);
    
    const technicalProgressBar = document.createElement('div');
    technicalProgressBar.style.cssText = 'width: 100%; height: 20px; background: rgba(15,23,42,0.8); border-radius: 12px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';
    
    const technicalProgressFill = document.createElement('div');
    technicalProgressFill.id = 'technical-progress-fill';
    technicalProgressFill.style.cssText = 'height: 100%; background: linear-gradient(90deg, #22c55e, #16a34a); width: 0%; transition: width 0.3s ease; display: flex; align-items: center; justify-content: center;';
    
    const technicalProgressLabel = document.createElement('div');
    technicalProgressLabel.id = 'technical-progress-label';
    technicalProgressLabel.style.cssText = 'color: #ffffff; font-size: 0.85rem; font-weight: 600; white-space: nowrap;';
    technicalProgressLabel.textContent = '0%';
    
    technicalProgressBar.appendChild(technicalProgressFill);
    technicalProgressFill.appendChild(technicalProgressLabel);
    
    const technicalProgressText = document.createElement('div');
    technicalProgressText.id = 'technical-progress-text';
    technicalProgressText.style.cssText = 'color: #111827; font-size: 0.92rem;';
    technicalProgressText.textContent = 'Initialisation...';
    
    const technicalSummary = document.createElement('div');
    technicalSummary.id = 'technical-progress-summary';
    technicalSummary.style.cssText = 'margin-top: 0.75rem; display: none; gap: 0.5rem; flex-wrap: wrap; align-items: center;';
    
    technicalProgressContainer.appendChild(technicalProgressTitleRow);
    technicalProgressContainer.appendChild(technicalProgressBar);
    technicalProgressContainer.appendChild(technicalProgressText);
    technicalProgressContainer.appendChild(technicalSummary);
    
    // Écouter les événements de l'analyse technique
    function setupTechnicalListener() {
        if (window.wsManager && window.wsManager.socket) {
            // Retirer l'ancien listener s'il existe
            window.wsManager.socket.off('technical_analysis_started');
            window.wsManager.socket.off('technical_analysis_progress');
            window.wsManager.socket.off('technical_analysis_complete');
            window.wsManager.socket.off('technical_analysis_error');
            
            window.wsManager.socket.on('technical_analysis_started', function(data) {
                if (!technicalProgressContainer.parentNode) {
                    scrapingProgressContainer.after(technicalProgressContainer);
                }
                technicalProgressContainer.style.display = 'block';
                
                const message = data.message || 'Analyse technique + SEO en cours...';
                
                // Compteur X/Y entreprises (analyse technique)
                if (typeof data.total === 'number' && data.total > 0) {
                    totalAnalysisEnterprises = data.total;
                    const current = typeof data.current === 'number' ? data.current : 0;
                    technicalProgressCountBadge.textContent = `${current} / ${totalAnalysisEnterprises} entreprises`;
                } else {
                    technicalProgressCountBadge.textContent = 'Analyse en cours...';
                }
                
                technicalProgressText.textContent = message;
                
                // Si immediate_100 est true, afficher à 100% immédiatement
                if (data.immediate_100) {
                    technicalProgressFill.style.width = '100%';
                    technicalProgressLabel.textContent = '100%';
                } else {
                    technicalProgressFill.style.width = '0%';
                    technicalProgressLabel.textContent = '0%';
                }
                
                // Scroll automatique vers le conteneur d'analyse technique
                setTimeout(() => {
                    technicalProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            });
            
            const throttledTechnicalProgress = createTrailingThrottle(function(data) {
                if (!technicalProgressContainer.parentNode) {
                    scrapingProgressContainer.after(technicalProgressContainer);
                }
                technicalProgressContainer.style.display = 'block';
                
                const message = data.message || 'Analyse technique + SEO en cours...';
                const percent = typeof data.progress === 'number' ? Math.min(100, Math.max(0, data.progress)) : null;
                
                // Compteur X/Y entreprises (analyse technique)
                if (typeof data.total === 'number' && data.total > 0) {
                    totalAnalysisEnterprises = data.total;
                    const current = typeof data.current === 'number' ? data.current : 0;
                    technicalProgressCountBadge.textContent = `${current} / ${totalAnalysisEnterprises} entreprises`;
                } else {
                    technicalProgressCountBadge.textContent = 'Analyse en cours...';
                }
                
                // Extraire le domaine depuis l'URL si disponible
                let domaine = '';
                if (data.url) {
                    try {
                        const url = new URL(data.url);
                        domaine = url.hostname.replace('www.', '');
                    } catch (e) {
                        const match = data.url.match(/https?:\/\/(?:www\.)?([^\/]+)/);
                        if (match) {
                            domaine = match[1];
                        }
                    }
                }
                
                // Afficher le message avec le domaine et l'entreprise
                let displayText = message;
                if (domaine) {
                    displayText += ` - ${domaine}`;
                }
                if (data.entreprise) {
                    displayText += ` (${data.entreprise})`;
                }
                technicalProgressText.textContent = displayText;
                
                if (percent !== null) {
                    technicalProgressFill.style.width = percent + '%';
                    technicalProgressLabel.textContent = `${percent}%`;
                }
                
                // Résumé (petites pastilles)
                const summary = data.summary;
                if (summary && typeof summary === 'object') {
                    const chips = [];
                    const pushChip = (label, value) => {
                        if (!value) return;
                        chips.push(
                            `<span style="display:inline-flex;align-items:center;gap:0.35rem;background:#f3f4f6;border:1px solid #e5e7eb;color:#111827;padding:0.25rem 0.55rem;border-radius:999px;font-size:0.85rem;font-weight:600;">` +
                            `<span style="color:#374151;font-weight:700;">${label}:</span> ${value}` +
                            `</span>`
                        );
                    };
                    
                    pushChip('Serveur', summary.server);
                    pushChip('Framework', summary.framework);
                    pushChip('CMS', summary.cms);
                    pushChip('SSL', summary.ssl);
                    pushChip('WAF', summary.waf);
                    pushChip('CDN', summary.cdn);
                    pushChip('Analytics', summary.analytics);
                    pushChip('Headers', summary.headers);
                    
                    if (chips.length > 0) {
                        technicalSummary.style.display = 'flex';
                        technicalSummary.innerHTML = chips.join('');
                    } else {
                        technicalSummary.style.display = 'none';
                        technicalSummary.innerHTML = '';
                    }
                } else {
                    technicalSummary.style.display = 'none';
                    technicalSummary.innerHTML = '';
                }
            }, 160);
            window.wsManager.socket.on('technical_analysis_progress', throttledTechnicalProgress);
            
            window.wsManager.socket.on('technical_analysis_complete', function(data) {
                if (!technicalProgressContainer.parentNode) {
                    scrapingProgressContainer.after(technicalProgressContainer);
                }
                technicalProgressContainer.style.display = 'block';
                technicalProgressFill.style.width = '100%';
                technicalProgressLabel.textContent = '100%';
                
                const current = typeof data.current === 'number' ? data.current : null;
                const total = typeof data.total === 'number' ? data.total : null;

                let technicalSummaryText = '';
                if (current !== null && total !== null && total > 0) {
                    technicalProgressCountBadge.textContent = `${current} / ${total} entreprises`;
                    technicalProgressText.textContent = `Analyses techniques + SEO terminées pour ${current}/${total} entreprises.`;
                    // Ne marquer comme terminé que si toutes les analyses sont vraiment terminées
                    if (current >= total) {
                        technicalDone = true;
                        technicalSummaryText = `Analyses techniques + SEO terminées pour ${total}/${total} entreprises.`;
                        technicalProgressText.textContent = technicalSummaryText;
                    }
                } else {
                    // Si pas de compteur, considérer comme terminé
                    technicalDone = true;
                    technicalSummaryText = data.message || 'Analyse technique + SEO terminée';
                    technicalProgressText.textContent = technicalSummaryText;
                }

                // Afficher un cadre \"terminé\" similaire au scraping
                if (technicalDone) {
                    const isDark = document.body && (document.body.getAttribute('data-theme') === 'dark');
                    const summaryBg = isDark ? '#022c22' : 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)';
                    const summaryBorderLeft = isDark ? '#22c55e' : '#27ae60';
                    const titleColor = isDark ? '#bbf7d0' : '#229954';
                    const textColor = isDark ? '#e5e7eb' : '#2c3e50';

                    let box = document.getElementById('technical-summary-box');
                    if (!box) {
                        box = document.createElement('div');
                        box.id = 'technical-summary-box';
                        box.style.marginTop = '0.75rem';
                        technicalProgressContainer.appendChild(box);
                    }

                    const message = technicalSummaryText || 'Analyses techniques + SEO terminées.';
                    box.innerHTML =
                        `<div style=\"background: ${summaryBg}; padding: 1rem; border-radius: 6px; border-left: 3px solid ${summaryBorderLeft};\">` +
                        `<div style=\"font-size: 0.9rem; color: ${titleColor}; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;\">` +
                        `<i class=\"fas fa-check\"></i> Analyse technique + SEO terminée</div>` +
                        `<div style=\"color: ${textColor}; font-size: 0.95rem; font-weight: 500;\">${message}</div>` +
                        `</div>`;
                }
                
                if (data.analysis_id && (!lastScrapingResult || !lastScrapingResult.analysis_id)) {
                    lastScrapingResult = lastScrapingResult || {};
                    lastScrapingResult.analysis_id = data.analysis_id;
                }
                maybeRedirectAfterAllDone();
            });
            
            window.wsManager.socket.on('technical_analysis_error', function(data) {
                if (!technicalProgressContainer.parentNode) {
                    scrapingProgressContainer.after(technicalProgressContainer);
                }
                technicalProgressContainer.style.display = 'block';
                technicalProgressFill.style.background = '#e74c3c';
                technicalProgressFill.style.width = '100%';
                technicalProgressLabel.textContent = 'Erreur';
                technicalProgressText.textContent = data.error || 'Erreur lors de l\'analyse technique / SEO';
            });
        }
    }
    
    // Section pour l'avancement de l'analyse OSINT
    const osintProgressContainer = document.createElement('div');
    osintProgressContainer.id = 'osint-progress-container';
    // Fond et bordures adaptés au dark mode
    osintProgressContainer.style.cssText = 'margin-top: 1.5rem; padding: 1.5rem; background: rgba(15,23,42,0.95); border-radius: 10px; border: 1px solid rgba(129,140,248,0.45); border-left: 5px solid #8b5cf6; display: none; box-shadow: 0 8px 20px rgba(15,23,42,0.9);';
    
    const osintProgressTitleRow = document.createElement('div');
    osintProgressTitleRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.75rem;';
    
    const osintProgressTitle = document.createElement('div');
    osintProgressTitle.style.cssText = 'font-weight: 700; color: #e5e7eb;';
    osintProgressTitle.textContent = 'Analyse OSINT en cours...';
    
    const osintProgressCountBadge = document.createElement('div');
    osintProgressCountBadge.id = 'osint-progress-count';
    osintProgressCountBadge.style.cssText = 'background: rgba(129,140,248,0.18); color: #ede9fe; border: 1px solid rgba(167,139,250,0.7); padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700; white-space: nowrap;';
    osintProgressCountBadge.textContent = '0 / 0 entreprises';
    
    osintProgressTitleRow.appendChild(osintProgressTitle);
    osintProgressTitleRow.appendChild(osintProgressCountBadge);
    
    // Jauge pour l'entreprise en cours
    const osintCurrentLabelRow = document.createElement('div');
    osintCurrentLabelRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem;';
    
    const osintCurrentLabel = document.createElement('div');
    osintCurrentLabel.style.cssText = 'font-size: 0.85rem; color: #9ca3af; font-weight: 600;';
    osintCurrentLabel.textContent = 'Entreprise en cours :';
    
    const osintCurrentInfo = document.createElement('div');
    osintCurrentInfo.id = 'osint-current-info';
    osintCurrentInfo.style.cssText = 'font-size: 0.85rem; color: #e5e7eb; font-weight: 500; flex: 1; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;';
    osintCurrentInfo.textContent = '';
    
    osintCurrentLabelRow.appendChild(osintCurrentLabel);
    osintCurrentLabelRow.appendChild(osintCurrentInfo);
    
    const osintCurrentBar = document.createElement('div');
    osintCurrentBar.style.cssText = 'width: 100%; height: 18px; background: rgba(15,23,42,0.8); border-radius: 10px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';
    
    const osintCurrentFill = document.createElement('div');
    osintCurrentFill.id = 'osint-current-fill';
    osintCurrentFill.style.cssText = 'height: 100%; background: linear-gradient(90deg, #8b5cf6, #7c3aed); width: 0%; transition: width 0.3s ease; display: flex; align-items: center; justify-content: center;';
    
    const osintCurrentLabelInner = document.createElement('div');
    osintCurrentLabelInner.id = 'osint-current-label';
    osintCurrentLabelInner.style.cssText = 'color: #ffffff; font-size: 0.8rem; font-weight: 600; white-space: nowrap;';
    osintCurrentLabelInner.textContent = '0%';
    
    osintCurrentBar.appendChild(osintCurrentFill);
    osintCurrentFill.appendChild(osintCurrentLabelInner);
    
    // Jauge pour le total des entreprises
    const osintTotalLabelRow = document.createElement('div');
    osintTotalLabelRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem;';
    
    const osintTotalLabel = document.createElement('div');
    osintTotalLabel.style.cssText = 'font-size: 0.85rem; color: #9ca3af; font-weight: 600;';
    osintTotalLabel.textContent = 'Progression globale :';
    
    const osintTotalInfo = document.createElement('div');
    osintTotalInfo.id = 'osint-total-info';
    osintTotalInfo.style.cssText = 'font-size: 0.85rem; color: #e5e7eb; font-weight: 500; flex: 1; text-align: right;';
    osintTotalInfo.textContent = '';
    
    osintTotalLabelRow.appendChild(osintTotalLabel);
    osintTotalLabelRow.appendChild(osintTotalInfo);
    
    const osintTotalBar = document.createElement('div');
    osintTotalBar.style.cssText = 'width: 100%; height: 18px; background: rgba(15,23,42,0.8); border-radius: 10px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';
    
    const osintTotalFill = document.createElement('div');
    osintTotalFill.id = 'osint-total-fill';
    osintTotalFill.style.cssText = 'height: 100%; background: linear-gradient(90deg, #3b82f6, #2563eb); width: 0%; transition: width 0.3s ease; display: flex; align-items: center; justify-content: center;';
    
    const osintTotalLabelInner = document.createElement('div');
    osintTotalLabelInner.id = 'osint-total-label';
    osintTotalLabelInner.style.cssText = 'color: #ffffff; font-size: 0.8rem; font-weight: 600; white-space: nowrap;';
    osintTotalLabelInner.textContent = '0%';
    
    osintTotalBar.appendChild(osintTotalFill);
    osintTotalFill.appendChild(osintTotalLabelInner);
    
    // Section pour les totaux cumulés OSINT (similaire au scraping)
    const osintCumulativeBox = document.createElement('div');
    osintCumulativeBox.id = 'osint-cumulative-box';
    osintCumulativeBox.style.cssText = 'background: rgba(15,118,110,0.18); padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid rgba(45,212,191,0.6); border-left: 4px solid #14b8a6; margin-top: 0.75rem;';
    
    const osintCumulativeLabel = document.createElement('div');
    osintCumulativeLabel.style.cssText = 'font-size: 0.78rem; color: #ccfbf1; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;';
    osintCumulativeLabel.textContent = 'Total cumulé';
    
    const osintCumulativeContent = document.createElement('div');
    osintCumulativeContent.id = 'osint-cumulative-content';
    osintCumulativeContent.style.cssText = 'color: #e5e7eb; font-size: 0.95rem; font-weight: 700; line-height: 1.6; display: flex; flex-wrap: wrap; align-items: center;';
    osintCumulativeContent.textContent = '';
    
    osintCumulativeBox.appendChild(osintCumulativeLabel);
    osintCumulativeBox.appendChild(osintCumulativeContent);
    
    osintProgressContainer.appendChild(osintProgressTitleRow);
    osintProgressContainer.appendChild(osintCurrentLabelRow);
    osintProgressContainer.appendChild(osintCurrentBar);
    osintProgressContainer.appendChild(osintTotalLabelRow);
    osintProgressContainer.appendChild(osintTotalBar);
    osintProgressContainer.appendChild(osintCumulativeBox);
    
    function setupOSINTListener() {
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.on('osint_analysis_started', function(data) {
                // Ne pas afficher si aucune entreprise (total === 0)
                if (typeof data.total === 'number' && data.total === 0) {
                    osintProgressContainer.style.display = 'none';
                    return;
                }
                
                if (!osintProgressContainer.parentNode) {
                    // Ajouter après le conteneur d'analyse technique
                    if (document.getElementById('technical-progress-container')) {
                        document.getElementById('technical-progress-container').after(osintProgressContainer);
                    } else if (document.getElementById('scraping-progress-container')) {
                        document.getElementById('scraping-progress-container').after(osintProgressContainer);
                    } else {
                        progressContainer.after(osintProgressContainer);
                    }
                }
                osintProgressContainer.style.display = 'block';
                
                const message = data.message || 'Analyse OSINT en cours...';
                
                // Compteur X/Y entreprises (OSINT) — priorité: expected_total > totalAnalysisEnterprises > data.total
                const osintTotal = (typeof data.expected_total === 'number' && data.expected_total > 0)
                    ? data.expected_total
                    : (typeof totalAnalysisEnterprises === 'number' && totalAnalysisEnterprises > 0)
                        ? totalAnalysisEnterprises
                        : (typeof data.total === 'number' ? data.total : 0);
                const osintCurrent = typeof data.current === 'number' ? data.current : 0;
                if (osintTotal > 0) {
                    osintProgressCountBadge.textContent = `${osintCurrent} / ${osintTotal} entreprises`;
                } else {
                    osintProgressCountBadge.textContent = 'En cours...';
                }
                
                osintCurrentInfo.textContent = 'En cours...';
                osintTotalInfo.textContent = 'En cours...';
                osintCurrentFill.style.width = '0%';
                osintCurrentLabelInner.textContent = '0%';
                osintTotalFill.style.width = '0%';
                osintTotalLabelInner.textContent = '0%';
                
                // Réinitialiser les totaux cumulés
                const osintCumulativeContent = document.getElementById('osint-cumulative-content');
                const osintCumulativeBox = document.getElementById('osint-cumulative-box');
                if (osintCumulativeContent) {
                    osintCumulativeContent.innerHTML = '<span style="color: #6b7280; font-size: 0.9rem; font-style: italic;">Aucune donnée collectée pour le moment</span>';
                }
                if (osintCumulativeBox) {
                    osintCumulativeBox.style.display = 'block';
                }
                
                setTimeout(() => {
                    osintProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            });
            
            // Debouncing pour éviter les mises à jour trop fréquentes
            let osintProgressDebounceTimer = null;
            let pendingOSINTData = null;
            const OSINT_DEBOUNCE_MS = 150; // Attendre 150ms avant d'appliquer les mises à jour
            
            function applyOSINTProgress(data) {
                // Ne pas afficher si aucune entreprise (total === 0)
                if (typeof data.total === 'number' && data.total === 0) {
                    osintProgressContainer.style.display = 'none';
                    return;
                }
                
                // Cette fonction applique réellement les mises à jour
                if (!osintProgressContainer.parentNode) {
                    if (document.getElementById('technical-progress-container')) {
                        document.getElementById('technical-progress-container').after(osintProgressContainer);
                    } else if (document.getElementById('scraping-progress-container')) {
                        document.getElementById('scraping-progress-container').after(osintProgressContainer);
                    } else {
                        progressContainer.after(osintProgressContainer);
                    }
                }
                osintProgressContainer.style.display = 'block';
                
                const message = data.message || '';
                
                // Filtrer les messages qui concernent les personnes (photos, localisation, hobbies)
                const personMessages = [
                    'Recherche de photos pour',
                    'Recherche de localisation pour',
                    'Recherche de hobbies pour',
                    'Analyse OSINT approfondie pour',
                    'Recherche de comptes pour',
                    'Vérification des fuites de données pour'
                ];
                
                const isPersonMessage = personMessages.some(pattern => message.includes(pattern));
                
                // Ne pas afficher les messages de personnes au niveau entreprise
                if (isPersonMessage) {
                    return; // Ignorer ces messages
                }
                
                // Progression de l'entreprise en cours (utilise task_progress si disponible, sinon progress)
                const currentProgress = typeof data.task_progress === 'number' ? data.task_progress : 
                                       (typeof data.progress === 'number' ? data.progress : null);
                
                // Progression globale (basée sur current/total)
                let totalProgress = null;
                const osintTotal = (typeof data.expected_total === 'number' && data.expected_total > 0)
                    ? data.expected_total
                    : (typeof totalAnalysisEnterprises === 'number' && totalAnalysisEnterprises > 0)
                        ? totalAnalysisEnterprises
                        : (typeof data.total === 'number' ? data.total : 0);
                const osintCurrent = typeof data.current === 'number' ? data.current : 0;
                if (osintTotal > 0) {
                    totalProgress = Math.round((osintCurrent / osintTotal) * 100);
                    osintProgressCountBadge.textContent = `${osintCurrent} / ${osintTotal} entreprises`;
                    osintTotalInfo.textContent = `${osintCurrent} / ${osintTotal} terminées`;
                } else {
                    osintProgressCountBadge.textContent = 'En cours...';
                    osintTotalInfo.textContent = 'En cours...';
                }
                
                // Extraire le domaine depuis l'URL si disponible
                let domaine = '';
                let entrepriseName = '';
                if (data.url) {
                    try {
                        const url = new URL(data.url);
                        domaine = url.hostname.replace('www.', '');
                    } catch (e) {
                        const match = data.url.match(/https?:\/\/(?:www\.)?([^\/]+)/);
                        if (match) {
                            domaine = match[1];
                        }
                    }
                }
                
                if (data.entreprise) {
                    entrepriseName = data.entreprise;
                }
                
                // Afficher les infos après les labels
                if (domaine || entrepriseName) {
                    const currentInfoText = entrepriseName || domaine || '';
                    osintCurrentInfo.textContent = currentInfoText;
                } else if (message && !isPersonMessage) {
                    // Afficher le message si ce n'est pas un message de personne
                    osintCurrentInfo.textContent = message.length > 40 ? message.substring(0, 37) + '...' : message;
                } else {
                    // Afficher "En cours..." si aucune info disponible
                    osintCurrentInfo.textContent = 'En cours...';
                }
                
                // Mettre à jour la jauge de l'entreprise en cours (utilise task_progress si disponible)
                if (currentProgress !== null) {
                    const currentPercent = Math.min(100, Math.max(0, currentProgress));
                    osintCurrentFill.style.width = currentPercent + '%';
                    osintCurrentLabelInner.textContent = `${Math.round(currentPercent)}%`;
                } else {
                    // Si pas de task_progress, utiliser progress comme fallback
                    const fallbackProgress = typeof data.progress === 'number' ? data.progress : null;
                    if (fallbackProgress !== null) {
                        const currentPercent = Math.min(100, Math.max(0, fallbackProgress));
                        osintCurrentFill.style.width = currentPercent + '%';
                        osintCurrentLabelInner.textContent = `${Math.round(currentPercent)}%`;
                    }
                }
                
                // Mettre à jour la jauge globale (sans throttling car c'est basé sur current/total qui change de manière discrète)
                if (totalProgress !== null) {
                    osintTotalFill.style.width = totalProgress + '%';
                    osintTotalLabelInner.textContent = `${totalProgress}%`;
                }
                
                // Afficher les totaux cumulés OSINT avec un design amélioré
                const cumulativeTotals = data.cumulative_totals || {};
                const osintCumulativeContent = document.getElementById('osint-cumulative-content');
                const osintCumulativeBox = document.getElementById('osint-cumulative-box');
                
                if (osintCumulativeContent && osintCumulativeBox && cumulativeTotals) {
                    // Créer des badges pour chaque type de données
                    const badges = [];
                    
                    if (cumulativeTotals.subdomains > 0) {
                        badges.push(`<span style="display: inline-block; background: #dbeafe; color: #1e40af; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.subdomains} sous-domaines</span>`);
                    }
                    if (cumulativeTotals.emails > 0) {
                        badges.push(`<span style="display: inline-block; background: #fef3c7; color: #92400e; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.emails} emails</span>`);
                    }
                    if (cumulativeTotals.people > 0) {
                        badges.push(`<span style="display: inline-block; background: #fce7f3; color: #9f1239; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.people} personnes</span>`);
                    }
                    if (cumulativeTotals.dns_records > 0) {
                        badges.push(`<span style="display: inline-block; background: #e0e7ff; color: #3730a3; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.dns_records} DNS</span>`);
                    }
                    if (cumulativeTotals.ssl_analyses > 0) {
                        badges.push(`<span style="display: inline-block; background: #d1fae5; color: #065f46; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.ssl_analyses} SSL</span>`);
                    }
                    if (cumulativeTotals.waf_detections > 0) {
                        badges.push(`<span style="display: inline-block; background: #fee2e2; color: #991b1b; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.waf_detections} WAF</span>`);
                    }
                    if (cumulativeTotals.directories > 0) {
                        badges.push(`<span style="display: inline-block; background: #f3e8ff; color: #6b21a8; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.directories} répertoires</span>`);
                    }
                    if (cumulativeTotals.open_ports > 0) {
                        badges.push(`<span style="display: inline-block; background: #fef3c7; color: #92400e; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.open_ports} ports</span>`);
                    }
                    if (cumulativeTotals.services > 0) {
                        badges.push(`<span style="display: inline-block; background: #e0f2fe; color: #0c4a6e; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.services} services</span>`);
                    }
                    
                    if (badges.length > 0) {
                        osintCumulativeContent.innerHTML = badges.join('');
                        osintCumulativeBox.style.display = 'block';
                    } else {
                        osintCumulativeContent.innerHTML = '<span style="color: #6b7280; font-size: 0.9rem; font-style: italic;">Aucune donnée collectée pour le moment</span>';
                        osintCumulativeBox.style.display = 'block';
                    }
                } else if (osintCumulativeBox) {
                    osintCumulativeBox.style.display = 'none';
                }
            }
            
            window.wsManager.socket.on('osint_analysis_progress', function(data) {
                // Sauvegarder la dernière donnée reçue
                pendingOSINTData = data;
                
                // Annuler le timer précédent s'il existe
                if (osintProgressDebounceTimer) {
                    clearTimeout(osintProgressDebounceTimer);
                }
                
                // Programmer l'application de la mise à jour après le délai de debounce
                osintProgressDebounceTimer = setTimeout(function() {
                    if (pendingOSINTData) {
                        applyOSINTProgress(pendingOSINTData);
                        pendingOSINTData = null;
                    }
                    osintProgressDebounceTimer = null;
                }, OSINT_DEBOUNCE_MS);
            });
            
            window.wsManager.socket.on('osint_analysis_complete', function(data) {
                // Ne pas afficher si aucune entreprise (total === 0)
                if (typeof data.total === 'number' && data.total === 0) {
                    osintProgressContainer.style.display = 'none';
                    return;
                }
                
                if (!osintProgressContainer.parentNode) {
                    if (document.getElementById('technical-progress-container')) {
                        document.getElementById('technical-progress-container').after(osintProgressContainer);
                    } else if (document.getElementById('scraping-progress-container')) {
                        document.getElementById('scraping-progress-container').after(osintProgressContainer);
                    } else {
                        progressContainer.after(osintProgressContainer);
                    }
                }
                osintProgressContainer.style.display = 'block';
                osintCurrentFill.style.width = '100%';
                osintCurrentLabelInner.textContent = '100%';
                osintCurrentFill.style.background = 'linear-gradient(90deg, #8b5cf6, #7c3aed)';
                
                // Mettre à jour la jauge globale (utiliser expected_total pour le dénominateur si dispo)
                const expectedTotal = typeof data.expected_total === 'number' && data.expected_total > 0
                    ? data.expected_total
                    : (totalAnalysisEnterprises > 0 ? totalAnalysisEnterprises : (typeof data.total === 'number' ? data.total : 1));
                if (typeof data.current === 'number' && expectedTotal > 0) {
                    const totalProgress = Math.round((data.current / expectedTotal) * 100);
                    osintTotalFill.style.width = totalProgress + '%';
                    osintTotalLabelInner.textContent = `${totalProgress}%`;
                }
                
                const current = typeof data.current === 'number' ? data.current : null;
                const total = typeof data.total === 'number' ? data.total : null;
                
                if (current !== null && total !== null && expectedTotal > 0) {
                    osintProgressCountBadge.textContent = `${current} / ${expectedTotal} entreprises`;
                    osintTotalInfo.textContent = `${current} / ${expectedTotal} terminées`;
                    // Ne marquer OSINT terminé (et permettre la redirection) que quand la progression totale est 100 %
                    if (current >= expectedTotal) {
                        osintDone = true;
                        osintTotalInfo.textContent = `${expectedTotal} / ${expectedTotal} terminées`;
                        showToast(`<i class=\"fas fa-check\"></i> Analyse OSINT terminée pour ${expectedTotal} entreprise(s)`, 'info');
                    }
                } else {
                    osintDone = true;
                    osintTotalInfo.textContent = 'Terminé';
                    showToast('<i class="fas fa-check"></i> Analyse OSINT terminée', 'info');
                }

                // Afficher un cadre \"terminé\" pour l'OSINT (comme pour le scraping)
                if (osintDone) {
                    const isDark = document.body && (document.body.getAttribute('data-theme') === 'dark');
                    const summaryBg = isDark ? '#020617' : 'linear-gradient(135deg, #eef2ff 0%, #e0f2fe 100%)';
                    const summaryBorderLeft = isDark ? '#6366f1' : '#2563eb';
                    const titleColor = isDark ? '#c7d2fe' : '#1d4ed8';
                    const textColor = isDark ? '#e5e7eb' : '#1f2937';

                    let box = document.getElementById('osint-summary-box');
                    if (!box) {
                        box = document.createElement('div');
                        box.id = 'osint-summary-box';
                        box.style.marginTop = '0.75rem';
                        osintProgressContainer.appendChild(box);
                    }

                    const totalsBox = document.getElementById('osint-cumulative-content');
                    const totalsText = totalsBox && totalsBox.textContent.trim().length > 0
                        ? totalsBox.textContent.trim()
                        : 'Analyses OSINT terminées pour toutes les entreprises.';

                    box.innerHTML =
                        `<div style=\"background: ${summaryBg}; padding: 1rem; border-radius: 6px; border-left: 3px solid ${summaryBorderLeft};\">` +
                        `<div style=\"font-size: 0.9rem; color: ${titleColor}; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;\">` +
                        `<i class=\"fas fa-check\"></i> Analyse OSINT terminée</div>` +
                        `<div style=\"color: ${textColor}; font-size: 0.95rem; font-weight: 500;\">${totalsText}</div>` +
                        `</div>`;
                }
                
                maybeRedirectAfterAllDone();
            });
            
            window.wsManager.socket.on('osint_analysis_error', function(data) {
                osintCurrentFill.style.background = '#e74c3c';
                osintCurrentFill.style.width = '100%';
                osintCurrentLabelInner.textContent = 'Erreur';
                osintCurrentInfo.textContent = data.error || 'Erreur lors de l\'analyse OSINT';
            });
        }
    }

    function setupPentestListener() {
        if (window.wsManager && window.wsManager.socket) {
            if (window.wsManager.socket.off) {
                window.wsManager.socket.off('pentest_analysis_started');
                window.wsManager.socket.off('pentest_analysis_progress');
                window.wsManager.socket.off('pentest_analysis_complete');
                window.wsManager.socket.off('pentest_analysis_error');
            }

            // Mémorise la dernière progression globale affichée
            // (pour éviter de régressions lors d'évènements où total/expected_total sont temporairement absents)
            let pentestLastTotalPercent = null;

            window.wsManager.socket.on('pentest_analysis_started', function(data) {
                // Dispatch aussi un CustomEvent pour rester cohérent avec websocket.js
                document.dispatchEvent(new CustomEvent('pentest_analysis:started', { detail: data }));
                if (typeof data.total === 'number' && data.total === 0) {
                    pentestProgressContainer.style.display = 'none';
                    pentestDone = true;
                    return;
                }

                if (!pentestProgressContainer.parentNode) {
                    if (document.getElementById('osint-progress-container')) {
                        document.getElementById('osint-progress-container').after(pentestProgressContainer);
                    } else if (document.getElementById('technical-progress-container')) {
                        document.getElementById('technical-progress-container').after(pentestProgressContainer);
                    } else if (document.getElementById('scraping-progress-container')) {
                        document.getElementById('scraping-progress-container').after(pentestProgressContainer);
                    } else {
                        progressContainer.after(pentestProgressContainer);
                    }
                }

                pentestProgressContainer.style.display = 'block';
                pentestDone = false;

                // expected_total = nombre d'entreprises de l'analyse (envoyé par le backend), sinon totalAnalysisEnterprises, sinon data.total
                const pentestTotal = (typeof data.expected_total === 'number' && data.expected_total > 0)
                    ? data.expected_total
                    : (typeof totalAnalysisEnterprises === 'number' && totalAnalysisEnterprises > 0)
                        ? totalAnalysisEnterprises
                        : (typeof data.total === 'number' ? data.total : 0);
                const pentestCurrent = typeof data.current === 'number' ? data.current : 0;
                pentestProgressCountBadge.textContent = `${pentestCurrent} / ${pentestTotal} entreprises`;
                pentestCurrentInfo.textContent = 'En cours...';
                pentestCurrentFill.style.width = '0%';
                pentestCurrentLabelInner.textContent = '0%';
                pentestTotalFill.style.width = '0%';
                pentestTotalLabelInner.textContent = '0%';
                pentestTotalInfo.textContent = 'En cours...';
                // Permet d'éviter que des events "partiels" à total=0 écrasent la progression globale
                pentestLastTotalPercent = 0;

                setTimeout(() => {
                    pentestProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            });

            const throttledPentestProgress = createTrailingThrottle(function(data) {
                document.dispatchEvent(new CustomEvent('pentest_analysis:progress', { detail: data }));
                if (typeof data.total === 'number' && data.total === 0) {
                    pentestProgressContainer.style.display = 'none';
                    return;
                }

                if (!pentestProgressContainer.parentNode) {
                    if (document.getElementById('osint-progress-container')) {
                        document.getElementById('osint-progress-container').after(pentestProgressContainer);
                    } else if (document.getElementById('technical-progress-container')) {
                        document.getElementById('technical-progress-container').after(pentestProgressContainer);
                    } else if (document.getElementById('scraping-progress-container')) {
                        document.getElementById('scraping-progress-container').after(pentestProgressContainer);
                    } else {
                        progressContainer.after(pentestProgressContainer);
                    }
                }
                pentestProgressContainer.style.display = 'block';

                const taskProgress = typeof data.task_progress === 'number' ? data.task_progress : null;

                const pentestTotal = (typeof data.expected_total === 'number' && data.expected_total > 0)
                    ? data.expected_total
                    : (typeof totalAnalysisEnterprises === 'number' && totalAnalysisEnterprises > 0)
                        ? totalAnalysisEnterprises
                        : (typeof data.total === 'number' ? data.total : 0);
                const pentestCurrent = typeof data.current === 'number' ? data.current : 0;
                if (pentestTotal > 0) {
                    pentestProgressCountBadge.textContent = `${pentestCurrent} / ${pentestTotal} entreprises`;
                    pentestTotalInfo.textContent = `${pentestCurrent} / ${pentestTotal} terminées`;
                }

                if (taskProgress !== null) {
                    const currentPercent = Math.min(100, Math.max(0, taskProgress));
                    pentestCurrentFill.style.width = `${currentPercent}%`;
                    pentestCurrentLabelInner.textContent = `${Math.round(currentPercent)}%`;
                }

                // Pour la progression globale Pentest, on s'aligne sur la logique OSINT :
                // priorité au ratio entreprises terminées / total entreprises, pour éviter
                // les incohérences quand toutes les tâches ne sont pas encore connues.
                let nextTotalPercent = null;
                let shouldUpdateTotal = false;

                if (pentestTotal > 0) {
                    nextTotalPercent = Math.min(100, Math.max(0, (pentestCurrent / pentestTotal) * 100));
                    // Ne pas laisser un event "partiel" remettre la progression globale à 0
                    // (on évite les régressions visuelles)
                    if (pentestLastTotalPercent === null || nextTotalPercent >= pentestLastTotalPercent) {
                        shouldUpdateTotal = true;
                    }
                } else if (typeof data.progress === 'number') {
                    // Fallback seulement si ça ne régresse pas (évite le "reset à 0")
                    const fallbackPercent = Math.min(100, Math.max(0, data.progress));
                    if (pentestLastTotalPercent === null || fallbackPercent >= pentestLastTotalPercent) {
                        nextTotalPercent = fallbackPercent;
                        shouldUpdateTotal = true;
                    }
                }

                if (shouldUpdateTotal && nextTotalPercent !== null) {
                    pentestLastTotalPercent = nextTotalPercent;
                    pentestTotalFill.style.width = `${nextTotalPercent}%`;
                    pentestTotalLabelInner.textContent = `${Math.round(nextTotalPercent)}%`;
                }

                // Libellé \"entreprise en cours\" :
                // - Mettre à jour uniquement quand on reçoit une entreprise/url
                // - Ne pas l'écraser avec les events globaux qui n'ont qu'un message
                let labelText = null;
                if (typeof data.entreprise === 'string' && data.entreprise.trim().length > 0) {
                    labelText = data.entreprise.trim();
                } else if (typeof data.url === 'string' && data.url.trim().length > 0) {
                    labelText = data.url.trim();
                } else if (!pentestCurrentInfo.textContent) {
                    // Fallback uniquement si rien n'a encore été affiché
                    labelText = (data.message && data.message.trim().length > 0) ? data.message.trim() : 'En cours...';
                }

                if (labelText) {
                    pentestCurrentInfo.textContent =
                        labelText.length > 40 ? `${labelText.slice(0, 37)}...` : labelText;
                }
                
                // Afficher les totaux cumulés Pentest.
                // Important : si un évènement de progression n'embarque pas à nouveau
                // `cumulative_totals`, on NE touche pas à la box pour ne pas effacer
                // les valeurs déjà affichées.
                const pentestCumulativeContent = document.getElementById('pentest-cumulative-content');
                const pentestCumulativeBox = document.getElementById('pentest-cumulative-box');

                if (pentestCumulativeContent && pentestCumulativeBox && Object.prototype.hasOwnProperty.call(data, 'cumulative_totals')) {
                    const cumulativeTotals = data.cumulative_totals || {};
                    const badges = [];
                    
                    if (cumulativeTotals.vulnerabilities > 0) {
                        badges.push(`<span style="display: inline-block; background: #fee2e2; color: #991b1b; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.vulnerabilities} vulnérabilités</span>`);
                    }
                    if (cumulativeTotals.forms_tested > 0) {
                        badges.push(`<span style="display: inline-block; background: #fef3c7; color: #92400e; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.forms_tested} formulaires</span>`);
                    }
                    if (cumulativeTotals.sql_injections > 0) {
                        badges.push(`<span style="display: inline-block; background: #fee2e2; color: #991b1b; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.sql_injections} SQL</span>`);
                    }
                    if (cumulativeTotals.xss_vulnerabilities > 0) {
                        badges.push(`<span style="display: inline-block; background: #fee2e2; color: #991b1b; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">${cumulativeTotals.xss_vulnerabilities} XSS</span>`);
                    }
                    if (cumulativeTotals.risk_score > 0) {
                        badges.push(`<span style="display: inline-block; background: #fef3c7; color: #92400e; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin: 0.15rem 0.25rem 0.15rem 0;">Score: ${cumulativeTotals.risk_score}</span>`);
                    }
                    
                    if (badges.length > 0) {
                        pentestCumulativeContent.innerHTML = badges.join('');
                    } else {
                        pentestCumulativeContent.innerHTML = '<span style="color: #6b7280; font-size: 0.9rem; font-style: italic;">Aucune donnée collectée pour le moment</span>';
                    }
                    pentestCumulativeBox.style.display = 'block';
                }
            }, 160);
            window.wsManager.socket.on('pentest_analysis_progress', throttledPentestProgress);

            window.wsManager.socket.on('pentest_analysis_complete', function(data) {
                document.dispatchEvent(new CustomEvent('pentest_analysis:complete', { detail: data }));
                if (!pentestProgressContainer.parentNode) {
                    if (document.getElementById('osint-progress-container')) {
                        document.getElementById('osint-progress-container').after(pentestProgressContainer);
                    } else if (document.getElementById('technical-progress-container')) {
                        document.getElementById('technical-progress-container').after(pentestProgressContainer);
                    } else if (document.getElementById('scraping-progress-container')) {
                        document.getElementById('scraping-progress-container').after(pentestProgressContainer);
                    } else {
                        progressContainer.after(pentestProgressContainer);
                    }
                }
                pentestProgressContainer.style.display = 'block';

                pentestCurrentFill.style.width = '100%';
                pentestCurrentLabelInner.textContent = '100%';
                pentestTotalFill.style.width = '100%';
                pentestTotalLabelInner.textContent = '100%';
                pentestLastTotalPercent = 100;

                const current = typeof data.current === 'number' ? data.current : null;
                const total = typeof data.total === 'number' ? data.total : null;
                const expectedTotal = (typeof data.expected_total === 'number' && data.expected_total > 0)
                    ? data.expected_total
                    : (typeof totalAnalysisEnterprises === 'number' && totalAnalysisEnterprises > 0
                        ? totalAnalysisEnterprises
                        : (typeof total === 'number' && total > 0 ? total : 1));

                if (current !== null && expectedTotal > 0) {
                    pentestProgressCountBadge.textContent = `${current} / ${expectedTotal} entreprises`;
                    pentestTotalInfo.textContent = `${current} / ${expectedTotal} terminées`;
                } else if (current !== null && total !== null) {
                    // Fallback si expectedTotal n'est pas exploitable
                    pentestProgressCountBadge.textContent = `${current} / ${total} entreprises`;
                    pentestTotalInfo.textContent = `${current} / ${total} terminées`;
                } else {
                    pentestTotalInfo.textContent = 'Terminé';
                }

                // Ne marquer Pentest terminé (et permettre la redirection) que quand la progression totale est 100 %
                if (current !== null && expectedTotal > 0 && current >= expectedTotal) {
                    pentestDone = true;
                } else if (current === null && total === null) {
                    pentestDone = true;
                }
                
                // Toast de notification (basé sur expectedTotal si possible)
                if (current !== null && expectedTotal > 0 && current >= expectedTotal) {
                    showToast(`<i class="fas fa-check"></i> Analyse Pentest terminée pour ${expectedTotal} entreprise(s)`, 'success');
                } else if (current !== null && total !== null && current >= total) {
                    showToast(`<i class="fas fa-check"></i> Analyse Pentest terminée pour ${total} entreprise(s)`, 'success');
                } else {
                    showToast('<i class="fas fa-check"></i> Analyse Pentest terminée', 'success');
                }

                // Afficher un cadre \"terminé\" pour le Pentest (comme pour le scraping)
                if (pentestDone) {
                    // Mettre à jour le libellé d'état
                    pentestCurrentLabel.textContent = 'État :';
                    pentestCurrentInfo.textContent = 'Aucune entreprise en cours';

                    const isDark = document.body && (document.body.getAttribute('data-theme') === 'dark');
                    const summaryBg = isDark ? '#130b0b' : 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)';
                    const summaryBorderLeft = isDark ? '#f97316' : '#ef4444';
                    const titleColor = isDark ? '#fed7aa' : '#b91c1c';
                    const textColor = isDark ? '#e5e7eb' : '#1f2937';

                    let box = document.getElementById('pentest-summary-box');
                    if (!box) {
                        box = document.createElement('div');
                        box.id = 'pentest-summary-box';
                        box.style.marginTop = '0.75rem';
                        pentestProgressContainer.appendChild(box);
                    }

                    const cumulativeBox = document.getElementById('pentest-cumulative-content');
                    const cumulativeText = cumulativeBox && cumulativeBox.textContent.trim().length > 0
                        ? cumulativeBox.textContent.trim()
                        : 'Analyses Pentest terminées pour toutes les entreprises.';

                    box.innerHTML =
                        `<div style=\"background: ${summaryBg}; padding: 1rem; border-radius: 6px; border-left: 3px solid ${summaryBorderLeft};\">` +
                        `<div style=\"font-size: 0.9rem; color: ${titleColor}; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;\">` +
                        `<i class=\"fas fa-check\"></i> Analyse Pentest terminée</div>` +
                        `<div style=\"color: ${textColor}; font-size: 0.95rem; font-weight: 500;\">${cumulativeText}</div>` +
                        `</div>`;

                    // Cacher la box \"TOTAL CUMULÉ\" une fois le résumé final affiché
                    if (pentestCumulativeBox) {
                        pentestCumulativeBox.style.display = 'none';
                    }
                }

                maybeRedirectAfterAllDone();
            });

            window.wsManager.socket.on('pentest_analysis_error', function(data) {
                document.dispatchEvent(new CustomEvent('pentest_analysis:error', { detail: data }));
                pentestCurrentFill.style.background = '#e74c3c';
                pentestCurrentFill.style.width = '100%';
                pentestCurrentLabelInner.textContent = 'Erreur';
                pentestCurrentInfo.textContent = data.error || 'Erreur lors de l analyse Pentest';
            });
        }
    }
    
    // Configurer l'écoute au chargement et après connexion WebSocket
    function applyPreviewTheme() {
        const isDark = document.body && (document.body.getAttribute('data-theme') === 'dark');

        // Technique
        try {
            technicalProgressContainer.style.background = isDark ? 'rgba(15,23,42,0.95)' : '#ffffff';
            technicalProgressContainer.style.boxShadow = isDark ? '0 8px 20px rgba(15,23,42,0.9)' : '0 6px 16px rgba(17,24,39,0.08)';
            technicalProgressContainer.style.border = isDark ? '1px solid rgba(34,197,94,0.35)' : '1px solid #d7e3f0';
            technicalProgressContainer.style.borderLeft = isDark ? '5px solid #22c55e' : '5px solid #22c55e';
            technicalProgressTitle.style.color = isDark ? '#e5e7eb' : '#111827';
            technicalProgressText.style.color = isDark ? '#e5e7eb' : '#111827';
            technicalProgressLabel.style.color = isDark ? '#ffffff' : '#111827';
            technicalProgressCountBadge.style.background = isDark ? 'rgba(34,197,94,0.18)' : 'rgba(34,197,94,0.12)';
            technicalProgressCountBadge.style.color = isDark ? '#bbf7d0' : '#166534';
            technicalProgressCountBadge.style.border = isDark ? '1px solid rgba(74,222,128,0.7)' : '1px solid rgba(34,197,94,0.35)';
            technicalProgressBar.style.background = isDark ? 'rgba(15,23,42,0.8)' : '#e5e7eb';
        } catch (e) {}

        // OSINT
        try {
            osintProgressContainer.style.background = isDark ? 'rgba(15,23,42,0.95)' : '#ffffff';
            osintProgressContainer.style.boxShadow = isDark ? '0 8px 20px rgba(15,23,42,0.9)' : '0 6px 16px rgba(17,24,39,0.08)';
            osintProgressContainer.style.border = isDark ? '1px solid rgba(129,140,248,0.45)' : '1px solid #d7e3f0';
            osintProgressContainer.style.borderLeft = isDark ? '5px solid #8b5cf6' : '5px solid #8b5cf6';
            osintProgressTitle.style.color = isDark ? '#e5e7eb' : '#111827';
            osintCurrentLabel.style.color = isDark ? '#9ca3af' : '#374151';
            osintTotalLabel.style.color = isDark ? '#9ca3af' : '#374151';
            osintCurrentInfo.style.color = isDark ? '#e5e7eb' : '#111827';
            osintTotalInfo.style.color = isDark ? '#e5e7eb' : '#111827';
            osintProgressCountBadge.style.background = isDark ? 'rgba(129,140,248,0.18)' : 'rgba(129,140,248,0.12)';
            osintProgressCountBadge.style.color = isDark ? '#ede9fe' : '#3730a3';
            osintProgressCountBadge.style.border = isDark ? '1px solid rgba(167,139,250,0.7)' : '1px solid rgba(129,140,248,0.35)';
            osintCurrentLabelInner.style.color = isDark ? '#ffffff' : '#111827';
            osintTotalLabelInner.style.color = isDark ? '#ffffff' : '#111827';
            osintCurrentBar.style.background = isDark ? 'rgba(15,23,42,0.8)' : '#e5e7eb';
            osintTotalBar.style.background = isDark ? 'rgba(15,23,42,0.8)' : '#e5e7eb';
        } catch (e) {}

        // Pentest
        try {
            pentestProgressContainer.style.background = isDark ? 'rgba(15,23,42,0.95)' : '#ffffff';
            pentestProgressContainer.style.boxShadow = isDark ? '0 8px 20px rgba(15,23,42,0.9)' : '0 6px 16px rgba(17,24,39,0.08)';
            pentestProgressContainer.style.border = isDark ? '1px solid rgba(248,113,113,0.35)' : '1px solid #d7e3f0';
            pentestProgressContainer.style.borderLeft = isDark ? '5px solid #ef4444' : '5px solid #ef4444';
            pentestProgressTitle.style.color = isDark ? '#e5e7eb' : '#111827';
            pentestCurrentLabel.style.color = isDark ? '#9ca3af' : '#374151';
            pentestTotalLabel.style.color = isDark ? '#9ca3af' : '#374151';
            pentestCurrentInfo.style.color = isDark ? '#e5e7eb' : '#111827';
            pentestTotalInfo.style.color = isDark ? '#e5e7eb' : '#111827';
            pentestProgressCountBadge.style.background = isDark ? 'rgba(239,68,68,0.15)' : 'rgba(239,68,68,0.12)';
            pentestProgressCountBadge.style.color = isDark ? '#fecaca' : '#991b1b';
            pentestProgressCountBadge.style.border = isDark ? '1px solid rgba(248,113,113,0.6)' : '1px solid rgba(239,68,68,0.35)';
            pentestCurrentLabelInner.style.color = isDark ? '#ffffff' : '#111827';
            pentestTotalLabelInner.style.color = isDark ? '#ffffff' : '#111827';
            pentestCurrentBar.style.background = isDark ? 'rgba(15,23,42,0.8)' : '#e5e7eb';
            pentestTotalBar.style.background = isDark ? 'rgba(15,23,42,0.8)' : '#e5e7eb';
        } catch (e) {}

        // Summary boxes finales : re-coloriser au changement de thème
        try {
            const restyleSummaryBox = (box, summaryBg, summaryBorderLeft, titleColor, textColor) => {
                if (!box || !box.firstElementChild) return;
                const inner = box.firstElementChild;
                inner.style.background = summaryBg;
                inner.style.borderLeft = `3px solid ${summaryBorderLeft}`;

                const titleDiv = inner.children && inner.children.length > 0 ? inner.children[0] : null;
                const messageDiv = inner.children && inner.children.length > 1 ? inner.children[1] : null;
                if (titleDiv) titleDiv.style.color = titleColor;
                if (messageDiv) messageDiv.style.color = textColor;
            };

            // Technical summary
            const technicalBox = document.getElementById('technical-summary-box');
            if (technicalBox) {
                const summaryBg = isDark ? '#022c22' : 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)';
                const summaryBorderLeft = isDark ? '#22c55e' : '#27ae60';
                const titleColor = isDark ? '#bbf7d0' : '#229954';
                const textColor = isDark ? '#e5e7eb' : '#2c3e50';
                restyleSummaryBox(technicalBox, summaryBg, summaryBorderLeft, titleColor, textColor);
            }

            // OSINT summary
            const osintBox = document.getElementById('osint-summary-box');
            if (osintBox) {
                const summaryBg = isDark ? '#020617' : 'linear-gradient(135deg, #eef2ff 0%, #e0f2fe 100%)';
                const summaryBorderLeft = isDark ? '#6366f1' : '#2563eb';
                const titleColor = isDark ? '#c7d2fe' : '#1d4ed8';
                const textColor = isDark ? '#e5e7eb' : '#1f2937';
                restyleSummaryBox(osintBox, summaryBg, summaryBorderLeft, titleColor, textColor);
            }

            // Pentest summary
            const pentestBox = document.getElementById('pentest-summary-box');
            if (pentestBox) {
                const summaryBg = isDark ? '#130b0b' : 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)';
                const summaryBorderLeft = isDark ? '#f97316' : '#ef4444';
                const titleColor = isDark ? '#fed7aa' : '#b91c1c';
                const textColor = isDark ? '#e5e7eb' : '#1f2937';
                restyleSummaryBox(pentestBox, summaryBg, summaryBorderLeft, titleColor, textColor);
            }
        } catch (e) {}

        // Cumulative boxes : en light, elles restent lisibles (border + text)
        try {
            if (!isDark) {
                if (osintCumulativeBox) osintCumulativeBox.style.background = '#f8fafc';
                if (osintCumulativeContent) osintCumulativeContent.style.color = '#111827';
                if (pentestCumulativeBox) pentestCumulativeBox.style.background = '#f8fafc';
                if (pentestCumulativeContent) pentestCumulativeContent.style.color = '#111827';
            } else {
                if (osintCumulativeBox) osintCumulativeBox.style.background = 'rgba(15,118,110,0.18)';
                if (osintCumulativeContent) osintCumulativeContent.style.color = '#e5e7eb';
                if (pentestCumulativeBox) pentestCumulativeBox.style.background = 'rgba(30,64,175,0.12)';
                if (pentestCumulativeContent) pentestCumulativeContent.style.color = '#e5e7eb';
            }
        } catch (e) {}
    }

    // Appliquer une première fois + écouter les changements de thème (data-theme sur <body>)
    try {
        applyPreviewTheme();
        if (window.MutationObserver && document.body) {
            const mo = new MutationObserver(() => applyPreviewTheme());
            mo.observe(document.body, { attributes: true, attributeFilter: ['data-theme'] });
        }
    } catch (e) {}

    setupScrapingListener();
    setupTechnicalListener();
    setupOSINTListener();
    setupPentestListener();
    document.addEventListener('websocket:connected', function() {
        setupScrapingListener();
        setupTechnicalListener();
        setupOSINTListener();
        setupPentestListener();
    });
    
    // Suivi pour la redirection automatique une fois tout terminé
    let excelAnalysisDone = false;
    let scrapingDone = false;
    let technicalDone = false;
    let osintDone = false;
    let pentestDone = true; // Passer à false dès qu'une analyse Pentest démarre
    let lastScrapingResult = null;
    
    function maybeRedirectAfterAllDone() {
        if (!scrapingDone || !technicalDone || !osintDone || !pentestDone) {
            return;
        }
        // Utiliser l'analysis_id du scraping si disponible pour cibler la liste des entreprises
        const analysisId = lastScrapingResult && lastScrapingResult.analysis_id;
        if (analysisId) {
            window.location.href = `/entreprises?analyse_id=${analysisId}`;
        } else {
            window.location.href = '/entreprises';
        }
    }
    
    document.addEventListener('analysis:complete', function(e) {
        const data = e.detail;
        excelAnalysisDone = true;
        statusDiv.className = '';
        statusDiv.textContent = '';
        
        progressFill.style.width = '100%';
        progressFill.textContent = '100%';
        progressFill.style.background = SUCCESS_MAIN_PROGRESS_BG;
        const stats = data.stats || {};
        const inserted = typeof stats.inserted === 'number' ? stats.inserted : null;
        const totalProcessed = inserted !== null ? inserted : (data.total_processed || data.total || 0);
        progressText.textContent = `Terminé ! ${totalProcessed} nouvelles entreprises analysées`;
        
        // Réactiver le formulaire et masquer le bouton stop
        const startBtn = document.getElementById('start-analysis-btn');
        const stopBtn = document.getElementById('stop-analysis-btn');
        startBtn.disabled = false;
        stopBtn.style.display = 'none';
        
        // Ne pas rediriger ici: on attend aussi le scraping + analyse technique
    });

    // Evénement personnalisé déclenché quand le scraping Celery est terminé
    document.addEventListener('scraping_complete', function(e) {
        scrapingDone = true;
        lastScrapingResult = e.detail || null;
        maybeRedirectAfterAllDone();
    });
    
    // Événement pour marquer l'OSINT comme terminé (géré par les listeners WebSocket)
    // osintDone sera mis à true dans setupOSINTListener quand toutes les analyses OSINT sont terminées
    
    
    document.addEventListener('analysis:error', function(e) {
        statusDiv.className = 'status-message status-error';
        statusDiv.textContent = 'Erreur : ' + (e.detail.error || 'Erreur inconnue');
        
        progressFill.style.background = '#e74c3c';
        progressText.textContent = 'Erreur lors de l\'analyse';
        
        // Réactiver le formulaire et masquer le bouton stop
        const startBtn = document.getElementById('start-analysis-btn');
        const stopBtn = document.getElementById('stop-analysis-btn');
        startBtn.disabled = false;
        stopBtn.style.display = 'none';
    });
    
    document.addEventListener('analysis:error_item', function(e) {
        // Erreur silencieuse pour une entreprise individuelle
    });
    
    // Gestion de la connexion WebSocket
    document.addEventListener('websocket:connected', function() {
        // WebSocket connecté
    });
    
    document.addEventListener('websocket:disconnected', function() {
        statusDiv.className = 'status-message status-error';
        statusDiv.textContent = 'Connexion perdue. Reconnexion...';
    });
    
    document.addEventListener('websocket:error', function(e) {
        statusDiv.className = 'status-message status-error';
        statusDiv.textContent = 'Erreur de connexion WebSocket';
    });
})();

