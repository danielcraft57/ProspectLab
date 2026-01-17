/**
 * Script de gestion de l'upload de fichiers Excel
 * Gère l'upload avec progression en temps réel, calcul de vitesse et ETA
 */

(function() {
    const form = document.getElementById('upload-form');
    const fileInput = document.getElementById('file');
    const uploadBtn = document.getElementById('upload-btn');
    const progressContainer = document.getElementById('upload-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const statusDiv = document.getElementById('upload-status');
    
    function showStatus(message, type = 'info') {
        statusDiv.style.display = 'block';
        statusDiv.className = `status-message status-${type}`;
        statusDiv.textContent = message;
    }
    
    function hideStatus() {
        statusDiv.style.display = 'none';
    }
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const file = fileInput.files[0];
        if (!file) {
            showStatus('Veuillez sélectionner un fichier', 'error');
            return;
        }
        
        // Vérifier la taille du fichier (max 50MB)
        const maxSize = 50 * 1024 * 1024; // 50MB
        if (file.size > maxSize) {
            showStatus('Le fichier est trop volumineux (max 50MB)', 'error');
            return;
        }
        
        // Désactiver le bouton et afficher la progression
        uploadBtn.disabled = true;
        progressContainer.style.display = 'block';
        progressFill.style.width = '0%';
        progressFill.textContent = '0%';
        progressText.textContent = 'Préparation de l\'upload...';
        hideStatus();
        
        // Créer FormData
        const formData = new FormData();
        formData.append('file', file);
        
        // Utiliser XMLHttpRequest pour avoir la progression
        const xhr = new XMLHttpRequest();
        
        // Variables pour le calcul de vitesse et ETA
        let startTime = null;
        let lastLoaded = 0;
        let lastTime = null;
        let processingProgress = 0;
        
        // Fonction pour formater les octets
        const formatBytes = (bytes) => {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
        };
        
        // Fonction pour formater le temps
        const formatTime = (seconds) => {
            if (seconds < 60) {
                return Math.round(seconds) + 's';
            } else if (seconds < 3600) {
                const mins = Math.floor(seconds / 60);
                const secs = Math.round(seconds % 60);
                return mins + 'm ' + secs + 's';
            } else {
                const hours = Math.floor(seconds / 3600);
                const mins = Math.floor((seconds % 3600) / 60);
                return hours + 'h ' + mins + 'm';
            }
        };
        
        // Écouter la progression de l'upload
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const now = Date.now();
                const loaded = e.loaded;
                const total = e.total;
                const percentComplete = Math.round((loaded / total) * 100);
                
                // Initialiser les variables au premier événement
                if (startTime === null) {
                    startTime = now;
                    lastTime = now;
                    lastLoaded = loaded;
                }
                
                // Calculer la vitesse (octets/seconde)
                const timeDiff = (now - lastTime) / 1000; // en secondes
                const loadedDiff = loaded - lastLoaded;
                let speed = 0;
                if (timeDiff > 0) {
                    speed = loadedDiff / timeDiff; // octets/seconde
                }
                
                // Calculer l'ETA
                const remaining = total - loaded;
                let eta = 0;
                if (speed > 0) {
                    eta = remaining / speed; // secondes
                }
                
                // Mettre à jour l'affichage
                const progressSpeedEl = document.getElementById('progress-speed');
                const progressEtaEl = document.getElementById('progress-eta');
                const progressLoadedEl = document.getElementById('progress-loaded');
                const progressTotalEl = document.getElementById('progress-total');
                
                // L'upload représente 70% du processus total
                const uploadPercent = Math.round(percentComplete * 0.7);
                progressFill.style.width = uploadPercent + '%';
                progressFill.textContent = uploadPercent + '%';
                progressText.textContent = `Upload en cours... ${percentComplete}%`;
                
                // Afficher les statistiques
                if (progressSpeedEl) {
                    progressSpeedEl.textContent = speed > 0 ? formatBytes(speed) + '/s' : '-';
                }
                if (progressEtaEl) {
                    progressEtaEl.textContent = eta > 0 ? 'ETA: ' + formatTime(eta) : '-';
                }
                if (progressLoadedEl) {
                    progressLoadedEl.textContent = formatBytes(loaded);
                }
                if (progressTotalEl) {
                    progressTotalEl.textContent = formatBytes(total);
                }
                
                // Mettre à jour pour le prochain calcul
                lastTime = now;
                lastLoaded = loaded;
            }
        });
        
        // Écouter le chargement complet
        xhr.addEventListener('load', function() {
            if (xhr.status === 200) {
                let data;
                try {
                    // Vérifier que la réponse n'est pas vide
                    if (!xhr.responseText || xhr.responseText.trim() === '') {
                        throw new Error('Réponse vide du serveur');
                    }
                    data = JSON.parse(xhr.responseText);
                } catch (error) {
                    showStatus('Erreur lors de la lecture de la réponse: ' + error.message, 'error');
                    uploadBtn.disabled = false;
                    progressContainer.style.display = 'none';
                    return;
                }
                
                if (data && data.success) {
                    // Masquer les stats de vitesse/ETA pendant le traitement serveur
                    const progressSpeedEl = document.getElementById('progress-speed');
                    const progressEtaEl = document.getElementById('progress-eta');
                    if (progressSpeedEl) progressSpeedEl.textContent = '-';
                    if (progressEtaEl) progressEtaEl.textContent = '-';
                    
                    // Simuler la progression du traitement serveur (70% -> 100%)
                    const simulateProcessing = () => {
                        if (processingProgress < 30) {
                            processingProgress += 2;
                            const totalProgress = 70 + processingProgress;
                            progressFill.style.width = Math.min(totalProgress, 100) + '%';
                            progressFill.textContent = Math.min(totalProgress, 100) + '%';
                            
                            if (processingProgress < 10) {
                                progressText.textContent = 'Lecture du fichier Excel...';
                            } else if (processingProgress < 20) {
                                progressText.textContent = 'Validation des données...';
                            } else {
                                progressText.textContent = 'Préparation de la prévisualisation...';
                            }
                            
                            if (processingProgress < 30) {
                                setTimeout(simulateProcessing, 100);
                            } else {
                                // Traitement terminé
                                progressFill.style.width = '100%';
                                progressFill.textContent = '100%';
                                progressFill.style.background = 'linear-gradient(90deg, #27ae60, #229954)';
                                progressText.textContent = 'Upload réussi ! Redirection...';
                                
                                // Masquer les stats
                                if (progressSpeedEl) progressSpeedEl.textContent = '';
                                if (progressEtaEl) progressEtaEl.textContent = '';
                                
                                // Afficher les avertissements de validation si présents
                                if (data.validation_warnings && data.validation_warnings.length > 0) {
                                    const warnings = data.validation_warnings.slice(0, 5).join(', ');
                                    showStatus(`Upload réussi. Avertissements: ${warnings}${data.validation_warnings.length > 5 ? '...' : ''}`, 'warning');
                                }
                                
                                // Rediriger vers la prévisualisation après un court délai
                                setTimeout(() => {
                                    window.location.href = `/preview/${data.filename}`;
                                }, 500);
                            }
                        }
                    };
                    
                    // Démarrer la simulation du traitement
                    setTimeout(simulateProcessing, 50);
                } else {
                    showStatus(data?.error || 'Erreur lors de l\'upload', 'error');
                    uploadBtn.disabled = false;
                    progressContainer.style.display = 'none';
                }
            } else {
                try {
                    const error = JSON.parse(xhr.responseText);
                    showStatus(error.error || 'Erreur lors de l\'upload', 'error');
                } catch {
                    showStatus('Erreur lors de l\'upload (code ' + xhr.status + ')', 'error');
                }
                uploadBtn.disabled = false;
                progressContainer.style.display = 'none';
            }
        });
        
        // Écouter les erreurs
        xhr.addEventListener('error', function() {
            showStatus('Erreur de connexion lors de l\'upload', 'error');
            uploadBtn.disabled = false;
            progressContainer.style.display = 'none';
        });
        
        // Écouter l'annulation
        xhr.addEventListener('abort', function() {
            showStatus('Upload annulé', 'warning');
            uploadBtn.disabled = false;
            progressContainer.style.display = 'none';
        });
        
        // Envoyer la requête
        xhr.open('POST', '/api/upload');
        xhr.send(formData);
    });
})();

