/**
 * Script de gestion de la page de prévisualisation et d'analyse
 * Gère le lancement de l'analyse, le suivi du scraping et de l'analyse technique en temps réel
 */

(function() {
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
    progressFill.style.cssText = 'height: 100%; background: linear-gradient(90deg, #3498db, #2980b9); width: 0%; transition: width 0.3s ease; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 12px;';
    
    const progressText = document.createElement('div');
    progressText.className = 'progress-text';
    progressText.style.cssText = 'padding: 0.5rem; text-align: center; color: #666;';
    
    progressBar.appendChild(progressFill);
    progressContainer.appendChild(progressBar);
    progressContainer.appendChild(progressText);
    
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
    pentestProgressContainer.style.cssText = 'margin-top: 1.5rem; padding: 1.25rem; background: #ffffff; border-radius: 10px; border: 1px solid #f8d7da; border-left: 5px solid #c0392b; display: none; box-shadow: 0 6px 16px rgba(17,24,39,0.08);';

    const pentestProgressTitleRow = document.createElement('div');
    pentestProgressTitleRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.75rem;';

    const pentestProgressTitle = document.createElement('div');
    pentestProgressTitle.style.cssText = 'font-weight: 700; color: #111827;';
    pentestProgressTitle.textContent = 'Analyse Pentest';

    const pentestProgressCountBadge = document.createElement('div');
    pentestProgressCountBadge.id = 'pentest-progress-count';
    pentestProgressCountBadge.style.cssText = 'background: #fdecea; color: #c0392b; border: 1px solid #e6a1a1; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700; white-space: nowrap;';
    pentestProgressCountBadge.textContent = '0 / 0 entreprises';

    pentestProgressTitleRow.appendChild(pentestProgressTitle);
    pentestProgressTitleRow.appendChild(pentestProgressCountBadge);

    const pentestCurrentLabelRow = document.createElement('div');
    pentestCurrentLabelRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem;';

    const pentestCurrentLabel = document.createElement('div');
    pentestCurrentLabel.style.cssText = 'font-size: 0.85rem; color: #6b7280; font-weight: 600;';
    pentestCurrentLabel.textContent = 'Entreprise en cours :';

    const pentestCurrentInfo = document.createElement('div');
    pentestCurrentInfo.id = 'pentest-current-info';
    pentestCurrentInfo.style.cssText = 'font-size: 0.85rem; color: #111827; font-weight: 500; flex: 1; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;';
    pentestCurrentInfo.textContent = '';

    pentestCurrentLabelRow.appendChild(pentestCurrentLabel);
    pentestCurrentLabelRow.appendChild(pentestCurrentInfo);

    const pentestCurrentBar = document.createElement('div');
    pentestCurrentBar.style.cssText = 'width: 100%; height: 18px; background: #e5e7eb; border-radius: 10px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';

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
    pentestTotalLabel.style.cssText = 'font-size: 0.85rem; color: #6b7280; font-weight: 600;';
    pentestTotalLabel.textContent = 'Progression globale :';

    const pentestTotalInfo = document.createElement('div');
    pentestTotalInfo.id = 'pentest-total-info';
    pentestTotalInfo.style.cssText = 'font-size: 0.85rem; color: #111827; font-weight: 500; flex: 1; text-align: right;';
    pentestTotalInfo.textContent = '';

    pentestTotalLabelRow.appendChild(pentestTotalLabel);
    pentestTotalLabelRow.appendChild(pentestTotalInfo);

    const pentestTotalBar = document.createElement('div');
    pentestTotalBar.style.cssText = 'width: 100%; height: 18px; background: #e5e7eb; border-radius: 10px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';

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
    pentestCumulativeBox.style.cssText = 'background: #fef2f2; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid #fecaca; border-left: 4px solid #dc2626; margin-top: 0.75rem;';
    
    const pentestCumulativeLabel = document.createElement('div');
    pentestCumulativeLabel.style.cssText = 'font-size: 0.78rem; color: #991b1b; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;';
    pentestCumulativeLabel.textContent = 'Total cumulé';
    
    const pentestCumulativeContent = document.createElement('div');
    pentestCumulativeContent.id = 'pentest-cumulative-content';
    pentestCumulativeContent.style.cssText = 'color: #111827; font-size: 0.95rem; font-weight: 700; line-height: 1.6; display: flex; flex-wrap: wrap; align-items: center;';
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
        
        progressFill.style.width = '0%';
        progressFill.textContent = '0%';
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
    
    document.addEventListener('analysis:progress', function(e) {
        const data = e.detail;
        const percentage = data.percentage || 0;
        
        progressFill.style.width = percentage + '%';
        progressFill.textContent = percentage + '%';
        progressText.textContent = data.message || `${data.current}/${data.total} entreprises analysées`;
        
        if (data.current_entreprise) {
            statusDiv.innerHTML = `Analyse en cours: <strong>${data.current_entreprise}</strong> (${data.current}/${data.total})`;
        }
    });
    
    // Écouter les événements de scraping
    function setupScrapingListener() {
        if (window.wsManager && window.wsManager.socket) {
            // Retirer l'ancien listener s'il existe
            window.wsManager.socket.off('scraping_progress');
            window.wsManager.socket.off('scraping_complete');
            
            window.wsManager.socket.on('scraping_progress', function(data) {
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
                    htmlContent += `<div style="background: #e6f0ff; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid #b6d4fe; border-left: 4px solid #1f6feb; margin-bottom: 0.75rem;">`;
                    htmlContent += `<div style="font-size: 0.78rem; color: #0b5bd3; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;">Entreprise actuelle</div>`;
                    htmlContent += `<div style="color: #111827; font-size: 0.95rem; font-weight: 600;">${currentStats}</div>`;
                    htmlContent += `</div>`;
                }
                
                // Total cumulé dans une balise stylisée différente (contraste renforcé)
                if (totalStats) {
                    htmlContent += `<div style="background: #e9fbf1; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid #a7f3d0; border-left: 4px solid #16a34a;">`;
                    htmlContent += `<div style="font-size: 0.78rem; color: #166534; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;">Total cumulé</div>`;
                    htmlContent += `<div style="color: #111827; font-size: 0.95rem; font-weight: 700;">${totalStats}</div>`;
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
                        htmlContent += `<div style="background: #e9fbf1; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid #a7f3d0; border-left: 4px solid #16a34a;">`;
                        htmlContent += `<div style="font-size: 0.78rem; color: #166534; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;">Total cumulé</div>`;
                        htmlContent += `<div style="color: #111827; font-size: 0.95rem; font-weight: 700;">${counters.join(', ')}</div>`;
                        htmlContent += `</div>`;
                    }
                }

                scrapingProgressText.innerHTML = htmlContent || 'Scraping en cours...';
            });

            // Afficher un résumé final quand le scraping est terminé
            window.wsManager.socket.on('scraping_complete', function(data) {
                if (!scrapingProgressContainer.parentNode) {
                    progressContainer.after(scrapingProgressContainer);
                }
                scrapingProgressContainer.style.display = 'block';
                
                // Mettre à jour la barre de progression à 100%
                if (data.current && data.total) {
                    entreprisesProgressFill.style.width = '100%';
                    entreprisesProgressText.textContent = `${data.total} / ${data.total} entreprises`;
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

                // Afficher le résumé final avec le même style
                let htmlContent = '<div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); padding: 1rem; border-radius: 6px; border-left: 3px solid #27ae60;">';
                htmlContent += '<div style="font-size: 0.9rem; color: #229954; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;"><i class="fas fa-check"></i> Scraping terminé</div>';
                if (counters.length > 0) {
                    htmlContent += `<div style="color: #2c3e50; font-size: 0.95rem; font-weight: 500;">${counters.join(', ')}</div>`;
                } else {
                    htmlContent += '<div style="color: #2c3e50; font-size: 0.95rem;">Scraping terminé avec succès</div>';
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
                // Si on a le total dans les données, l'afficher, sinon afficher un message générique
                if (data.total && data.total > 0) {
                    entreprisesProgressText.textContent = `0 / ${data.total} entreprises`;
                } else {
                    entreprisesProgressText.textContent = 'Initialisation...';
                }
                scrapingProgressText.innerHTML = '<div style="color: #666;">Initialisation du scraping...</div>';
                
                // Scroll automatique vers le conteneur de scraping
                setTimeout(() => {
                    scrapingProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            });
        }
    }
    
    // Section pour l'avancement de l'analyse technique
    const technicalProgressContainer = document.createElement('div');
    technicalProgressContainer.id = 'technical-progress-container';
    technicalProgressContainer.style.cssText = 'margin-top: 1.5rem; padding: 1.25rem; background: #ffffff; border-radius: 10px; border: 1px solid #d1fae5; border-left: 5px solid #16a34a; display: none; box-shadow: 0 6px 16px rgba(17,24,39,0.08);';
    
    const technicalProgressTitleRow = document.createElement('div');
    technicalProgressTitleRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.75rem;';
    
    const technicalProgressTitle = document.createElement('div');
    technicalProgressTitle.style.cssText = 'font-weight: 700; color: #111827;';
    technicalProgressTitle.textContent = 'Analyse technique en cours...';
    
    const technicalProgressCountBadge = document.createElement('div');
    technicalProgressCountBadge.id = 'technical-progress-count';
    technicalProgressCountBadge.style.cssText = 'background: #dcfce7; color: #166534; border: 1px solid #86efac; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700; white-space: nowrap;';
    technicalProgressCountBadge.textContent = '0 / 0 entreprises';
    
    technicalProgressTitleRow.appendChild(technicalProgressTitle);
    technicalProgressTitleRow.appendChild(technicalProgressCountBadge);
    
    const technicalProgressBar = document.createElement('div');
    technicalProgressBar.style.cssText = 'width: 100%; height: 20px; background: #e5e7eb; border-radius: 12px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';
    
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
                
                const message = data.message || 'Analyse technique en cours...';
                
                // Compteur X/Y entreprises (analyse technique)
                if (typeof data.current === 'number' && typeof data.total === 'number' && data.total > 0) {
                    technicalProgressCountBadge.textContent = `${data.current} / ${data.total} entreprises`;
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
            
            window.wsManager.socket.on('technical_analysis_progress', function(data) {
                if (!technicalProgressContainer.parentNode) {
                    scrapingProgressContainer.after(technicalProgressContainer);
                }
                technicalProgressContainer.style.display = 'block';
                
                const message = data.message || 'Analyse technique en cours...';
                const percent = typeof data.progress === 'number' ? Math.min(100, Math.max(0, data.progress)) : null;
                
                // Compteur X/Y entreprises (analyse technique)
                if (typeof data.current === 'number' && typeof data.total === 'number' && data.total > 0) {
                    technicalProgressCountBadge.textContent = `${data.current} / ${data.total} entreprises`;
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
            });
            
            window.wsManager.socket.on('technical_analysis_complete', function(data) {
                if (!technicalProgressContainer.parentNode) {
                    scrapingProgressContainer.after(technicalProgressContainer);
                }
                technicalProgressContainer.style.display = 'block';
                technicalProgressFill.style.width = '100%';
                technicalProgressLabel.textContent = '100%';
                
                const current = typeof data.current === 'number' ? data.current : null;
                const total = typeof data.total === 'number' ? data.total : null;
                
                if (current !== null && total !== null && total > 0) {
                    technicalProgressCountBadge.textContent = `${current} / ${total} entreprises`;
                    technicalProgressText.textContent = `Analyses techniques terminées pour ${current}/${total} entreprises.`;
                    // Ne marquer comme terminé que si toutes les analyses sont vraiment terminées
                    if (current >= total) {
                        technicalDone = true;
                        technicalProgressText.textContent = `Analyses techniques terminées pour ${total}/${total} entreprises.`;
                    }
                } else {
                    // Si pas de compteur, considérer comme terminé
                    technicalDone = true;
                    technicalProgressText.textContent = data.message || 'Analyse technique terminée';
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
                technicalProgressText.textContent = data.error || 'Erreur lors de l\'analyse technique';
            });
        }
    }
    
    // Section pour l'avancement de l'analyse OSINT
    const osintProgressContainer = document.createElement('div');
    osintProgressContainer.id = 'osint-progress-container';
    osintProgressContainer.style.cssText = 'margin-top: 1.5rem; padding: 1.5rem; background: #ffffff; border-radius: 10px; border: 1px solid #d7e3f0; border-left: 5px solid #9333ea; display: none; box-shadow: 0 6px 16px rgba(17,24,39,0.08);';
    
    const osintProgressTitleRow = document.createElement('div');
    osintProgressTitleRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.75rem;';
    
    const osintProgressTitle = document.createElement('div');
    osintProgressTitle.style.cssText = 'font-weight: 700; color: #111827;';
    osintProgressTitle.textContent = 'Analyse OSINT en cours...';
    
    const osintProgressCountBadge = document.createElement('div');
    osintProgressCountBadge.id = 'osint-progress-count';
    osintProgressCountBadge.style.cssText = 'background: #f3e8ff; color: #6b21a8; border: 1px solid #c084fc; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700; white-space: nowrap;';
    osintProgressCountBadge.textContent = '0 / 0 entreprises';
    
    osintProgressTitleRow.appendChild(osintProgressTitle);
    osintProgressTitleRow.appendChild(osintProgressCountBadge);
    
    // Jauge pour l'entreprise en cours
    const osintCurrentLabelRow = document.createElement('div');
    osintCurrentLabelRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem;';
    
    const osintCurrentLabel = document.createElement('div');
    osintCurrentLabel.style.cssText = 'font-size: 0.85rem; color: #6b7280; font-weight: 600;';
    osintCurrentLabel.textContent = 'Entreprise en cours :';
    
    const osintCurrentInfo = document.createElement('div');
    osintCurrentInfo.id = 'osint-current-info';
    osintCurrentInfo.style.cssText = 'font-size: 0.85rem; color: #111827; font-weight: 500; flex: 1; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;';
    osintCurrentInfo.textContent = '';
    
    osintCurrentLabelRow.appendChild(osintCurrentLabel);
    osintCurrentLabelRow.appendChild(osintCurrentInfo);
    
    const osintCurrentBar = document.createElement('div');
    osintCurrentBar.style.cssText = 'width: 100%; height: 18px; background: #e5e7eb; border-radius: 10px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';
    
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
    osintTotalLabel.style.cssText = 'font-size: 0.85rem; color: #6b7280; font-weight: 600;';
    osintTotalLabel.textContent = 'Progression globale :';
    
    const osintTotalInfo = document.createElement('div');
    osintTotalInfo.id = 'osint-total-info';
    osintTotalInfo.style.cssText = 'font-size: 0.85rem; color: #111827; font-weight: 500; flex: 1; text-align: right;';
    osintTotalInfo.textContent = '';
    
    osintTotalLabelRow.appendChild(osintTotalLabel);
    osintTotalLabelRow.appendChild(osintTotalInfo);
    
    const osintTotalBar = document.createElement('div');
    osintTotalBar.style.cssText = 'width: 100%; height: 18px; background: #e5e7eb; border-radius: 10px; overflow: hidden; margin-bottom: 0.75rem; position: relative;';
    
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
    osintCumulativeBox.style.cssText = 'background: #e9fbf1; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid #a7f3d0; border-left: 4px solid #16a34a; margin-top: 0.75rem;';
    
    const osintCumulativeLabel = document.createElement('div');
    osintCumulativeLabel.style.cssText = 'font-size: 0.78rem; color: #166534; font-weight: 800; margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.6px;';
    osintCumulativeLabel.textContent = 'Total cumulé';
    
    const osintCumulativeContent = document.createElement('div');
    osintCumulativeContent.id = 'osint-cumulative-content';
    osintCumulativeContent.style.cssText = 'color: #111827; font-size: 0.95rem; font-weight: 700; line-height: 1.6; display: flex; flex-wrap: wrap; align-items: center;';
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
                
                // Compteur X/Y entreprises (OSINT)
                if (typeof data.current === 'number' && typeof data.total === 'number' && data.total > 0) {
                    osintProgressCountBadge.textContent = `${data.current} / ${data.total} entreprises`;
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
                if (typeof data.current === 'number' && typeof data.total === 'number' && data.total > 0) {
                    totalProgress = Math.round((data.current / data.total) * 100);
                    osintProgressCountBadge.textContent = `${data.current} / ${data.total} entreprises`;
                    osintTotalInfo.textContent = `${data.current} / ${data.total} terminées`;
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
                
                // Mettre à jour la jauge globale
                if (typeof data.current === 'number' && typeof data.total === 'number' && data.total > 0) {
                    const totalProgress = Math.round((data.current / data.total) * 100);
                    osintTotalFill.style.width = totalProgress + '%';
                    osintTotalLabelInner.textContent = `${totalProgress}%`;
                }
                
                const current = typeof data.current === 'number' ? data.current : null;
                const total = typeof data.total === 'number' ? data.total : null;
                
                if (current !== null && total !== null && total > 0) {
                    osintProgressCountBadge.textContent = `${current} / ${total} entreprises`;
                    osintTotalInfo.textContent = `${current} / ${total} terminées`;
                    if (current >= total) {
                        osintDone = true;
                        osintTotalInfo.textContent = `${total} / ${total} terminées`;
                        showToast(`<i class="fas fa-check"></i> Analyse OSINT terminée pour ${total} entreprise(s)`, 'info');
                    }
                } else {
                    osintDone = true;
                    osintTotalInfo.textContent = 'Terminé';
                    showToast('<i class="fas fa-check"></i> Analyse OSINT terminée', 'info');
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

                pentestProgressCountBadge.textContent = `${data.current || 0} / ${data.total || 0} entreprises`;
                pentestCurrentInfo.textContent = 'En cours...';
                pentestCurrentFill.style.width = '0%';
                pentestCurrentLabelInner.textContent = '0%';
                pentestTotalFill.style.width = '0%';
                pentestTotalLabelInner.textContent = '0%';
                pentestTotalInfo.textContent = 'En cours...';

                setTimeout(() => {
                    pentestProgressContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            });

            window.wsManager.socket.on('pentest_analysis_progress', function(data) {
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

                const totalProgress = typeof data.progress === 'number' ? data.progress : null;
                const taskProgress = typeof data.task_progress === 'number' ? data.task_progress : null;

                if (typeof data.current === 'number' && typeof data.total === 'number' && data.total > 0) {
                    pentestProgressCountBadge.textContent = `${data.current} / ${data.total} entreprises`;
                    pentestTotalInfo.textContent = `${data.current} / ${data.total} terminées`;
                }

                if (taskProgress !== null) {
                    const currentPercent = Math.min(100, Math.max(0, taskProgress));
                    pentestCurrentFill.style.width = `${currentPercent}%`;
                    pentestCurrentLabelInner.textContent = `${Math.round(currentPercent)}%`;
                }

                if (totalProgress !== null) {
                    const totalPercent = Math.min(100, Math.max(0, totalProgress));
                    pentestTotalFill.style.width = `${totalPercent}%`;
                    pentestTotalLabelInner.textContent = `${Math.round(totalPercent)}%`;
                }

                const labelText = data.entreprise || data.url || data.message || 'En cours...';
                pentestCurrentInfo.textContent = labelText.length > 40 ? `${labelText.slice(0, 37)}...` : labelText;
                
                // Afficher les totaux cumulés Pentest
                const cumulativeTotals = data.cumulative_totals || {};
                const pentestCumulativeContent = document.getElementById('pentest-cumulative-content');
                const pentestCumulativeBox = document.getElementById('pentest-cumulative-box');
                
                if (pentestCumulativeContent && pentestCumulativeBox && cumulativeTotals) {
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
                        pentestCumulativeBox.style.display = 'block';
                    } else {
                        pentestCumulativeContent.innerHTML = '<span style="color: #6b7280; font-size: 0.9rem; font-style: italic;">Aucune donnée collectée pour le moment</span>';
                        pentestCumulativeBox.style.display = 'block';
                    }
                } else if (pentestCumulativeBox) {
                    pentestCumulativeBox.style.display = 'none';
                }
            });

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

                const current = typeof data.current === 'number' ? data.current : null;
                const total = typeof data.total === 'number' ? data.total : null;
                if (current !== null && total !== null) {
                    pentestProgressCountBadge.textContent = `${current} / ${total} entreprises`;
                    pentestTotalInfo.textContent = `${current} / ${total} terminées`;
                } else {
                    pentestTotalInfo.textContent = 'Terminé';
                }

                pentestDone = true;
                
                // Toast de notification (réutiliser les variables déjà déclarées)
                if (current !== null && total !== null && current >= total) {
                    showToast(`<i class="fas fa-check"></i> Analyse Pentest terminée pour ${total} entreprise(s)`, 'success');
                } else {
                    showToast('<i class="fas fa-check"></i> Analyse Pentest terminée', 'success');
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
        const totalProcessed = data.total_processed || data.total || 0;
        progressText.textContent = `Terminé ! ${totalProcessed} entreprises analysées`;
        
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

