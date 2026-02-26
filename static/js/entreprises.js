/**
 * JavaScript pour la page de liste des entreprises
 * Gestion des filtres, recherche, tags et notes
 * 
 * ⚠️ FICHIER OBSOLÈTE ⚠️
 * Ce fichier a été remplacé par entreprises.refactored.js qui utilise une architecture modulaire.
 * Ce fichier est conservé à titre de référence/backup uniquement.
 * Ne pas utiliser dans de nouveaux développements.
 */

(function() {
    let currentView = 'grid';
    let currentPage = 1;
    const itemsPerPage = 20;
    let allEntreprises = [];
    let filteredEntreprises = [];
    
    // Initialisation
    document.addEventListener('DOMContentLoaded', () => {
        loadSecteurs();
        loadEntreprises();
        setupEventListeners();
    });
    
    // Charger les secteurs pour le filtre
    async function loadSecteurs() {
        try {
            const response = await fetch('/api/secteurs');
            const secteurs = await response.json();
            
            const select = document.getElementById('filter-secteur');
            secteurs.forEach(secteur => {
                const option = document.createElement('option');
                option.value = secteur;
                option.textContent = secteur;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Erreur lors du chargement des secteurs:', error);
        }
    }
    
    // Charger les entreprises
    async function loadEntreprises() {
        try {
            const response = await fetch('/api/entreprises');
            allEntreprises = await response.json();
            filteredEntreprises = [...allEntreprises];
            applyFilters();
        } catch (error) {
            console.error('Erreur lors du chargement des entreprises:', error);
            document.getElementById('entreprises-container').innerHTML = 
                '<p class="error">Erreur lors du chargement des entreprises</p>';
        }
    }
    
    // Appliquer les filtres
    function applyFilters() {
        const search = document.getElementById('search-input').value.toLowerCase();
        const secteur = document.getElementById('filter-secteur').value;
        const statut = document.getElementById('filter-statut').value;
        const opportunite = document.getElementById('filter-opportunite').value;
        const favori = document.getElementById('filter-favori').checked;
        
        filteredEntreprises = allEntreprises.filter(entreprise => {
            if (search && !matchesSearch(entreprise, search)) return false;
            if (secteur && entreprise.secteur !== secteur) return false;
            if (statut && entreprise.statut !== statut) return false;
            if (opportunite && entreprise.opportunite !== opportunite) return false;
            if (favori && !entreprise.favori) return false;
            return true;
        });
        
        currentPage = 1;
        renderEntreprises();
    }
    
    function matchesSearch(entreprise, search) {
        const searchFields = [
            entreprise.nom,
            entreprise.secteur,
            entreprise.email_principal,
            entreprise.responsable,
            entreprise.website
        ].filter(f => f).map(f => f.toLowerCase());
        
        return searchFields.some(field => field.includes(search));
    }
    
    // Rendre les entreprises
    function renderEntreprises() {
        const container = document.getElementById('entreprises-container');
        const start = (currentPage - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const pageEntreprises = filteredEntreprises.slice(start, end);
        
        document.getElementById('results-count').textContent = 
            `${filteredEntreprises.length} entreprise${filteredEntreprises.length > 1 ? 's' : ''} trouvée${filteredEntreprises.length > 1 ? 's' : ''}`;
        
        if (pageEntreprises.length === 0) {
            container.innerHTML = '<p class="no-results">Aucune entreprise ne correspond aux critères</p>';
            document.getElementById('pagination').innerHTML = '';
            return;
        }
        
        if (currentView === 'grid') {
            container.className = 'entreprises-grid';
            container.innerHTML = pageEntreprises.map(entreprise => createEntrepriseCard(entreprise)).join('');
        } else {
            container.className = 'entreprises-list';
            container.innerHTML = pageEntreprises.map(entreprise => createEntrepriseRow(entreprise)).join('');
        }
        
        renderPagination();
        
        // Ajouter les event listeners pour les actions
        pageEntreprises.forEach(entreprise => {
            setupEntrepriseActions(entreprise.id);
        });
    }
    
    function createEntrepriseCard(entreprise) {
        const tagsHtml = entreprise.tags && entreprise.tags.length > 0
            ? entreprise.tags.map(tag => `<span class="tag">${tag}</span>`).join('')
            : '';
        
        // Générer un aperçu du résumé (150 premiers caractères)
        let resumePreview = '';
        if (entreprise.resume) {
            resumePreview = entreprise.resume.length > 150 
                ? entreprise.resume.substring(0, 147) + '...' 
                : entreprise.resume;
        }
        
        // Récupérer l'image principale (og_image, logo ou favicon)
        const mainImage = entreprise.og_image || entreprise.logo || entreprise.favicon || null;
        
        return `
            <div class="entreprise-card" data-id="${entreprise.id}">
                <div class="card-header-with-logo">
                    ${mainImage ? `
                    <div class="card-logo-container">
                        <img src="${mainImage}" alt="${entreprise.nom || 'Logo'}" class="card-logo" onerror="this.style.display='none'">
                    </div>
                    ` : ''}
                    <div class="card-header">
                        <div style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
                            <h3>${entreprise.nom || 'Sans nom'}</h3>
                            <div style="display:flex; align-items:center; gap:0.5rem;">
                                ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null && entreprise.score_pentest >= 40 ? `
                                <i class="fas fa-exclamation-triangle" style="color: ${entreprise.score_pentest >= 70 ? '#e74c3c' : '#f39c12'}; font-size: 1.2rem;" title="Score Pentest: ${entreprise.score_pentest}/100"></i>
                                ` : ''}
                            <button class="btn-favori ${entreprise.favori ? 'active' : ''}" data-id="${entreprise.id}" title="Favori">
                                    <i class="fas fa-star"></i>
                            </button>
                        </div>
                        </div>
                    </div>
                </div>
                <div class="card-body">
                    ${resumePreview ? `<p class="resume-preview" style="color: #666; font-size: 0.9rem; margin-bottom: 0.75rem; font-style: italic;">${resumePreview}</p>` : ''}
                    ${entreprise.website ? `<p><strong>Site:</strong> <a href="${entreprise.website}" target="_blank">${entreprise.website}</a></p>` : ''}
                    ${entreprise.secteur ? `<p><strong>Secteur:</strong> ${entreprise.secteur}</p>` : ''}
                    ${entreprise.statut ? `<p><strong>Statut:</strong> <span class="badge badge-${getStatusClass(entreprise.statut)}">${entreprise.statut}</span></p>` : ''}
                    ${(typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null) || (typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null) ? `
                    <div style="margin-top:0.5rem; padding-top:0.5rem; border-top:1px solid #e5e7eb;">
                        ${typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null ? `
                        <p style="margin:0.25rem 0;">
                            <strong>Sécurité:</strong> ${getSecurityScoreBadge(entreprise.score_securite)}
                        </p>
                        ` : ''}
                        ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null ? `
                        <p style="margin:0.25rem 0;">
                            <strong>Pentest:</strong> 
                            <span class="badge badge-${entreprise.score_pentest >= 70 ? 'danger' : entreprise.score_pentest >= 40 ? 'warning' : 'success'}">${entreprise.score_pentest}/100</span>
                        </p>
                        ` : ''}
                    </div>
                    ` : ''}
                    ${entreprise.email_principal ? `<p><strong>Email:</strong> ${entreprise.email_principal}</p>` : ''}
                    ${entreprise.responsable ? `<p><strong>Responsable:</strong> ${entreprise.responsable}</p>` : ''}
                    ${tagsHtml ? `<div class="tags-container">${tagsHtml}</div>` : ''}
                </div>
                <div class="card-footer">
                    <button class="btn btn-small btn-primary btn-view-details" data-id="${entreprise.id}">Voir détails</button>
                    <button class="btn btn-small btn-secondary btn-edit-tags" data-id="${entreprise.id}">Tags</button>
                    <button class="btn btn-small btn-danger btn-delete-entreprise" data-id="${entreprise.id}" data-name="${entreprise.nom || 'Sans nom'}" title="Supprimer"><i class="fas fa-trash"></i></button>
                </div>
            </div>
        `;
    }
    
    function createEntrepriseRow(entreprise) {
        const tagsHtml = entreprise.tags && entreprise.tags.length > 0
            ? entreprise.tags.map(tag => `<span class="tag">${tag}</span>`).join('')
            : '';
        
        return `
            <div class="entreprise-row" data-id="${entreprise.id}">
                <div class="row-main">
                    <div class="row-name">
                        <div style="display:flex; align-items:center; gap:0.5rem;">
                        <h3>${entreprise.nom || 'Sans nom'}</h3>
                            ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null && entreprise.score_pentest >= 40 ? `
                            <i class="fas fa-exclamation-triangle" style="color: ${entreprise.score_pentest >= 70 ? '#e74c3c' : '#f39c12'}; font-size: 1.1rem;" title="Score Pentest: ${entreprise.score_pentest}/100"></i>
                            ` : ''}
                        </div>
                        ${tagsHtml ? `<div class="tags-container">${tagsHtml}</div>` : ''}
                    </div>
                    <div class="row-info">
                        ${entreprise.secteur ? `<span>${entreprise.secteur}</span>` : ''}
                        ${entreprise.statut ? `<span class="badge badge-${getStatusClass(entreprise.statut)}">${entreprise.statut}</span>` : ''}
                        ${typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null ? `<span>${getSecurityScoreBadge(entreprise.score_securite)}</span>` : ''}
                        ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null ? `
                        <span>
                            <span class="badge badge-${entreprise.score_pentest >= 70 ? 'danger' : entreprise.score_pentest >= 40 ? 'warning' : 'success'}">Pentest: ${entreprise.score_pentest}/100</span>
                        </span>
                        ` : ''}
                        ${entreprise.email_principal ? `<span>${entreprise.email_principal}</span>` : ''}
                    </div>
                </div>
                <div class="row-actions">
                    <button class="btn-favori ${entreprise.favori ? 'active' : ''}" data-id="${entreprise.id}" title="Favori"><i class="fas fa-star"></i></button>
                    <button class="btn btn-small btn-secondary btn-edit-tags" data-id="${entreprise.id}">Tags</button>
                    <button class="btn btn-small btn-primary btn-view-details" data-id="${entreprise.id}">Détails</button>
                    <button class="btn btn-small btn-danger btn-delete-entreprise" data-id="${entreprise.id}" data-name="${entreprise.nom || 'Sans nom'}" title="Supprimer"><i class="fas fa-trash"></i></button>
                </div>
            </div>
        `;
    }
    
    function getStatusClass(statut) {
        const classes = {
            'Nouveau': 'primary',
            'À qualifier': 'warning',
            'Relance': 'relance',
            'Gagné': 'success',
            'Perdu': 'danger'
        };
        return classes[statut] || 'secondary';
    }
    
    function renderPagination() {
        const totalPages = Math.ceil(filteredEntreprises.length / itemsPerPage);
        const pagination = document.getElementById('pagination');
        
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }
        
        let html = '<div class="pagination-controls">';
        
        // Bouton précédent
        html += `<button class="btn-pagination ${currentPage === 1 ? 'disabled' : ''}" data-page="${currentPage - 1}">← Précédent</button>`;
        
        // Numéros de page
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
                html += `<button class="btn-pagination ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
            } else if (i === currentPage - 3 || i === currentPage + 3) {
                html += '<span class="pagination-ellipsis">...</span>';
            }
        }
        
        // Bouton suivant
        html += `<button class="btn-pagination ${currentPage === totalPages ? 'disabled' : ''}" data-page="${currentPage + 1}">Suivant →</button>`;
        
        html += '</div>';
        pagination.innerHTML = html;
        
        // Event listeners pour la pagination
        pagination.querySelectorAll('.btn-pagination').forEach(btn => {
            btn.addEventListener('click', () => {
                const page = parseInt(btn.dataset.page);
                if (page >= 1 && page <= totalPages && !btn.classList.contains('disabled')) {
                    currentPage = page;
                    renderEntreprises();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        });
    }
    
    function setupEntrepriseActions(entrepriseId) {
        // Favori
        const favoriBtn = document.querySelector(`.btn-favori[data-id="${entrepriseId}"]`);
        if (favoriBtn) {
            favoriBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await toggleFavori(entrepriseId);
            });
        }
        
        // Tags
        const tagsBtn = document.querySelector(`.btn-edit-tags[data-id="${entrepriseId}"]`);
        if (tagsBtn) {
            tagsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                showTagsModal(entrepriseId);
            });
        }
        
        // Suppression
        const deleteBtn = document.querySelector(`.btn-delete-entreprise[data-id="${entrepriseId}"]`);
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const entrepriseName = deleteBtn.getAttribute('data-name') || 'Sans nom';
                await deleteEntreprise(entrepriseId, entrepriseName);
            });
        }
        
        // Voir détails (ouvre la modale)
        const viewDetailsBtn = document.querySelector(`.btn-view-details[data-id="${entrepriseId}"]`);
        if (viewDetailsBtn) {
            viewDetailsBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await openEntrepriseModal(entrepriseId);
            });
        }
    }
    
    async function toggleFavori(entrepriseId) {
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/favori`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                const entreprise = allEntreprises.find(e => e.id === entrepriseId);
                if (entreprise) {
                    entreprise.favori = data.favori;
                }
                applyFilters();
            }
        } catch (error) {
            console.error('Erreur lors du toggle favori:', error);
        }
    }
    
    function showTagsModal(entrepriseId) {
        const entreprise = allEntreprises.find(e => e.id === entrepriseId);
        if (!entreprise) return;
        
        const currentTags = entreprise.tags || [];
        const tagsInput = prompt('Tags (séparés par des virgules):', currentTags.join(', '));
        
        if (tagsInput !== null) {
            const newTags = tagsInput.split(',').map(t => t.trim()).filter(t => t);
            updateTags(entrepriseId, newTags);
        }
    }
    
    async function updateTags(entrepriseId, tags) {
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/tags`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tags })
            });
            const data = await response.json();
            
            if (data.success) {
                const entreprise = allEntreprises.find(e => e.id === entrepriseId);
                if (entreprise) {
                    entreprise.tags = tags;
                }
                applyFilters();
            }
        } catch (error) {
            console.error('Erreur lors de la mise à jour des tags:', error);
        }
    }
    
    // Suppression d'entreprise
    async function deleteEntreprise(entrepriseId, entrepriseName) {
        if (!confirm(`Êtes-vous sûr de vouloir supprimer "${entrepriseName}" ?\n\nCette action est irréversible.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                showNotification(`Entreprise "${entrepriseName}" supprimée avec succès`, 'success');
                
                // Retirer de la liste sans rechargement
                allEntreprises = allEntreprises.filter(e => e.id !== entrepriseId);
                applyFilters();
            } else {
                showNotification(data.error || 'Erreur lors de la suppression', 'error');
            }
        } catch (error) {
            console.error('Erreur lors de la suppression:', error);
            showNotification('Erreur lors de la suppression de l\'entreprise', 'error');
        }
    }
    
    // Export CSV avec AJAX
    async function exportCSV() {
        const secteur = document.getElementById('filter-secteur').value;
        const statut = document.getElementById('filter-statut').value;
        const opportunite = document.getElementById('filter-opportunite').value;
        const search = document.getElementById('search-input').value;
        
        const params = new URLSearchParams();
        if (secteur) params.append('secteur', secteur);
        if (statut) params.append('statut', statut);
        if (opportunite) params.append('opportunite', opportunite);
        if (search) params.append('search', search);
        
        try {
            // Afficher un indicateur de chargement
            const exportBtn = document.getElementById('btn-export');
            const originalText = exportBtn ? exportBtn.textContent : '';
            if (exportBtn) {
                exportBtn.disabled = true;
                exportBtn.textContent = 'Export en cours...';
            }
            
            const response = await fetch(`/api/export/csv?${params.toString()}`);
            
            if (response.ok) {
                // Récupérer le fichier en blob
                const blob = await response.blob();
                
                // Créer un lien de téléchargement
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `entreprises_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                // Afficher une notification de succès
                showNotification('Export CSV réussi !', 'success');
            } else {
                const error = await response.json();
                showNotification(error.error || 'Erreur lors de l\'export', 'error');
            }
        } catch (error) {
            console.error('Erreur lors de l\'export:', error);
            showNotification('Erreur lors de l\'export CSV', 'error');
        } finally {
            // Réactiver le bouton
            const exportBtn = document.getElementById('btn-export');
            if (exportBtn) {
                exportBtn.disabled = false;
                exportBtn.textContent = originalText || 'Exporter';
            }
        }
    }
    
    // Fonction utilitaire pour afficher des notifications
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'success' ? '#d4edda' : type === 'error' ? '#f8d7da' : '#d1ecf1'};
            color: ${type === 'success' ? '#155724' : type === 'error' ? '#721c24' : '#0c5460'};
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    
    function setupEventListeners() {
        // Filtres
        document.getElementById('btn-apply-filters').addEventListener('click', applyFilters);
        document.getElementById('btn-reset-filters').addEventListener('click', () => {
            document.getElementById('search-input').value = '';
            document.getElementById('filter-secteur').value = '';
            document.getElementById('filter-statut').value = '';
            document.getElementById('filter-opportunite').value = '';
            document.getElementById('filter-favori').checked = false;
            applyFilters();
        });
        
        // Recherche en temps réel
        document.getElementById('search-input').addEventListener('input', debounce(applyFilters, 300));
        
        // Export
        document.getElementById('btn-export').addEventListener('click', async () => {
            await exportCSV();
        });
        
        // Vue grille/liste
        document.getElementById('btn-view-grid').addEventListener('click', () => {
            currentView = 'grid';
            document.getElementById('btn-view-grid').classList.add('active');
            document.getElementById('btn-view-list').classList.remove('active');
            renderEntreprises();
        });
        
        document.getElementById('btn-view-list').addEventListener('click', () => {
            currentView = 'list';
            document.getElementById('btn-view-list').classList.add('active');
            document.getElementById('btn-view-grid').classList.remove('active');
            renderEntreprises();
        });
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
    
    // Modale de détails d'entreprise
    let currentModalEntrepriseId = null;
    let currentModalEntrepriseData = null;
    let currentModalPentestScore = null;
    
    async function openEntrepriseModal(entrepriseId) {
        currentModalEntrepriseId = entrepriseId;
        const modal = document.getElementById('entreprise-modal');
        const modalBody = document.getElementById('modal-entreprise-body');
        const modalTitle = document.getElementById('modal-entreprise-nom');
        
        if (!modal || !modalBody || !modalTitle) {
            console.error('Éléments de la modale introuvables');
            return;
        }
        
        modal.style.display = 'flex';
        modalBody.innerHTML = '<div class="loading">Chargement des détails...</div>';
        modalTitle.textContent = 'Chargement...';
        
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}`);
            if (!response.ok) {
                throw new Error('Entreprise introuvable');
            }
            
            currentModalEntrepriseData = await response.json();
            currentModalPentestScore = null; // Réinitialiser le score pentest
            modalTitle.textContent = currentModalEntrepriseData.nom || 'Sans nom';
            modalBody.innerHTML = createModalContent(currentModalEntrepriseData);
            
            // Setup des interactions de la modale
            setupModalInteractions();
            
            // Charger les images dans l'onglet Images principal
            loadEntrepriseImages(entrepriseId);
            
            // Charger les résultats scraping
            loadScrapingResults(entrepriseId);
            
            // Charger les analyses existantes
            loadTechnicalAnalysis(entrepriseId);
            loadOSINTAnalysis(entrepriseId);
            loadPentestAnalysis(entrepriseId);
        } catch (error) {
            console.error('Erreur lors du chargement:', error);
            modalBody.innerHTML = `
                <div class="error">
                    <p>Erreur lors du chargement des détails</p>
                    <p style="font-size: 0.9rem; color: #666; margin-top: 0.5rem;">${error.message || 'Erreur inconnue'}</p>
                    <button class="btn btn-secondary" style="margin-top: 1rem;" onclick="document.getElementById('entreprise-modal').style.display='none'">Fermer</button>
                </div>
            `;
            // S'assurer que la modal peut quand même se fermer
            setupModalInteractions();
        }
    }
    
    function createModalContent(entreprise) {
        const tags = entreprise.tags || [];
        const notes = entreprise.notes || '';
        
        return `
            <div class="entreprise-modal-tabs">
                <div class="tabs-header">
                    <button class="tab-btn active" data-tab="info">Info</button>
                    <button class="tab-btn" data-tab="images">Images</button>
                    <button class="tab-btn" data-tab="pages">Pages</button>
                    <button class="tab-btn" data-tab="scraping">Résultats scraping</button>
                    <button class="tab-btn" data-tab="technique">Analyse technique</button>
                    <button class="tab-btn" data-tab="osint">Analyse OSINT</button>
                    <button class="tab-btn" data-tab="pentest">Analyse Pentest</button>
                </div>
                
                <div class="tabs-content">
                    <!-- Onglet Informations -->
                    <div class="tab-panel active" id="tab-info">
                        ${(entreprise.og_image || entreprise.logo || entreprise.favicon || entreprise.og_data) ? `
                        <div class="detail-section" style="margin-bottom: 1.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 8px;">
                            ${(entreprise.og_image || entreprise.logo || entreprise.favicon) ? `
                            <div style="text-align: center; margin-bottom: 2rem;">
                                <div style="display: flex; align-items: center; justify-content: center; gap: 2rem; flex-wrap: wrap;">
                                    ${entreprise.og_image ? `
                                    <div style="flex: 1; min-width: 200px;">
                                        <h4 style="color: white; margin: 0 0 1rem 0; font-size: 0.9rem; text-transform: uppercase; opacity: 0.9;">Image OpenGraph</h4>
                                        <img src="${entreprise.og_image}" alt="Image OpenGraph" style="max-width: 100%; max-height: 300px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); background: white; padding: 0.5rem;" onerror="this.style.display='none'">
                                    </div>
                                    ` : ''}
                                    ${entreprise.logo ? `
                                    <div style="flex: 1; min-width: 150px;">
                                        <h4 style="color: white; margin: 0 0 1rem 0; font-size: 0.9rem; text-transform: uppercase; opacity: 0.9;">Logo</h4>
                                        <img src="${entreprise.logo}" alt="Logo" style="max-width: 100%; max-height: 150px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); background: white; padding: 0.5rem;" onerror="this.style.display='none'">
                                    </div>
                                    ` : ''}
                                    ${entreprise.favicon ? `
                                    <div style="flex: 1; min-width: 100px;">
                                        <h4 style="color: white; margin: 0 0 1rem 0; font-size: 0.9rem; text-transform: uppercase; opacity: 0.9;">Favicon</h4>
                                        <img src="${entreprise.favicon}" alt="Favicon" style="max-width: 64px; max-height: 64px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); background: white; padding: 0.5rem;" onerror="this.style.display='none'">
                                    </div>
                                    ` : ''}
                                </div>
                            </div>
                            ` : ''}
                        </div>
                        ` : ''}
                        ${entreprise.resume ? `
                        <div class="detail-section" style="margin-bottom: 1.5rem; background: #f8f9fa; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #667eea;">
                            <h3 style="margin: 0 0 0.75rem 0; color: #2c3e50; font-size: 1.1rem;"><i class="fas fa-file-alt"></i> Résumé de l'entreprise</h3>
                            <p style="margin: 0; color: #555; line-height: 1.6; font-size: 0.95rem;">${entreprise.resume}</p>
                        </div>
                        ` : ''}
                        <div class="info-grid">
                            ${createInfoRow('Nom', entreprise.nom)}
                            ${createInfoRow('Site web', entreprise.website, true)}
                            ${createInfoRow('Secteur', entreprise.secteur)}
                            ${createInfoRow('Statut', entreprise.statut, false, getStatusBadge(entreprise.statut))}
                            ${typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null ? `
                            <div class="info-row">
                                <span class="info-label">Score sécurité:</span>
                                <span class="info-value">${getSecurityScoreBadge(entreprise.score_securite)}</span>
                            </div>
                            ` : ''}
                            <div class="info-row" id="pentest-score-row" style="display: none;">
                                <span class="info-label">Score Pentest:</span>
                                <span class="info-value" id="pentest-score-value"></span>
                            </div>
                            ${createInfoRow('Opportunité', entreprise.opportunite)}
                            ${createInfoRow('Taille estimée', entreprise.taille_estimee)}
                            ${createInfoRow('Adresse 1', entreprise.address_1)}
                            ${createInfoRow('Adresse 2', entreprise.address_2)}
                            ${createInfoRow('Pays', entreprise.pays)}
                            ${createInfoRow('Téléphone', entreprise.telephone)}
                            ${createInfoRow('Email principal', entreprise.email_principal, true)}
                            ${createInfoRow('Emails secondaires', entreprise.emails_secondaires)}
                            ${createInfoRow('Responsable', entreprise.responsable)}
                            ${createInfoRow('Note Google', entreprise.note_google ? `${entreprise.note_google}/5` : '')}
                            ${createInfoRow('Nombre d\'avis', entreprise.nb_avis_google)}
                        </div>
                        
                        ${entreprise.hosting_provider || entreprise.framework ? `
                        <div class="tech-info-section">
                            <h3>Informations techniques</h3>
                            <div class="info-grid">
                                ${createInfoRow('Hébergeur', entreprise.hosting_provider)}
                                ${createInfoRow('Framework', entreprise.framework)}
                                ${createInfoRow('CMS', entreprise.cms)}
                            </div>
                        </div>
                        ` : ''}
                    </div>
                    
                    <!-- Onglet Images -->
                    <div class="tab-panel" id="tab-images">
                        <div id="entreprise-images-container" class="images-tab-content">
                            <p class="empty-state">Aucune image disponible pour le moment. Lancez un scraping pour récupérer les visuels du site.</p>
                        </div>
                    </div>
                    
                    <!-- Onglet Pages (OpenGraph) -->
                    <div class="tab-panel" id="tab-pages">
                        <div id="entreprise-pages-container" class="pages-tab-content">
                            ${entreprise.og_data ? (() => {
                                try {
                                    const ogDataList = Array.isArray(entreprise.og_data) ? entreprise.og_data : [entreprise.og_data];
                                    const validOgData = ogDataList.filter(ogData => ogData && (ogData.og_title || ogData.og_type || ogData.og_url || ogData.page_url || (ogData.images && ogData.images.length > 0)));
                                    
                                    if (validOgData.length > 0) {
                                        return validOgData.map((ogData, idx) => {
                                            const hasImage = ogData.images && ogData.images.length > 0 && ogData.images[0].image_url;
                                            return `
                                                <div class="page-card" style="background: white; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid #667eea;">
                                                    <div style="display: flex; gap: 1.5rem; align-items: flex-start;">
                                                        ${hasImage ? `
                                                        <div style="flex: 0 0 200px;">
                                                            <img src="${ogData.images[0].image_url}" alt="${ogData.og_title || 'Page preview'}" 
                                                                 style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);"
                                                                 onerror="this.style.display='none'">
                                                        </div>
                                                        ` : ''}
                                                        <div style="flex: 1; min-width: 0;">
                                                            ${ogData.page_url ? `
                                                            <div style="margin-bottom: 0.75rem;">
                                                                <a href="${ogData.page_url}" target="_blank" 
                                                                   style="color: #667eea; font-weight: 600; font-size: 0.9rem; text-decoration: none; word-break: break-all; display: inline-block; max-width: 100%;">
                                                                    ${ogData.page_url}
                                                                </a>
                                                            </div>
                                                            ` : ''}
                                                            ${ogData.og_title ? `
                                                            <h3 style="margin: 0 0 0.75rem 0; color: #2c3e50; font-size: 1.2rem; font-weight: 600;">
                                                                ${ogData.og_title}
                                                            </h3>
                                                            ` : ''}
                                                            ${ogData.og_description ? `
                                                            <p style="margin: 0 0 1rem 0; color: #555; line-height: 1.6; font-size: 0.95rem;">
                                                                ${ogData.og_description}
                                                            </p>
                                                            ` : ''}
                                                            <div style="display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1rem;">
                                                                ${ogData.og_type ? `
                                                                <span style="background: #e8f0fe; color: #1967d2; padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.85rem; font-weight: 500;">
                                                                    ${ogData.og_type}
                                                                </span>
                                                                ` : ''}
                                                                ${ogData.og_site_name ? `
                                                                <span style="background: #f0f4f8; color: #4a5568; padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.85rem;">
                                                                    Site: ${ogData.og_site_name}
                                                                </span>
                                                                ` : ''}
                                                                ${ogData.og_locale ? `
                                                                <span style="background: #f0f4f8; color: #4a5568; padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.85rem;">
                                                                    ${ogData.og_locale}
                                                                </span>
                                                                ` : ''}
                                                            </div>
                                                            ${ogData.images && ogData.images.length > 1 ? `
                                                            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;">
                                                                <div style="font-size: 0.85rem; color: #718096; margin-bottom: 0.5rem;">
                                                                    ${ogData.images.length} image(s) supplémentaire(s)
                                                                </div>
                                                                <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
                                                                    ${ogData.images.slice(1).map(img => `
                                                                        <img src="${img.image_url}" alt="${img.alt_text || 'OG Image'}" 
                                                                             style="max-width: 100px; max-height: 100px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); cursor: pointer;"
                                                                             onclick="window.open('${img.image_url}', '_blank')"
                                                                             onerror="this.style.display='none'"
                                                                             title="${img.alt_text || ''}">
                                                                    `).join('')}
                                                                </div>
                                                            </div>
                                                            ` : ''}
                                                            ${(ogData.videos && ogData.videos.length > 0) || (ogData.audios && ogData.audios.length > 0) ? `
                                                            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; display: flex; gap: 1rem; flex-wrap: wrap;">
                                                                ${ogData.videos && ogData.videos.length > 0 ? `
                                                                <span style="font-size: 0.85rem; color: #718096;">
                                                                    <i class="fas fa-video"></i> ${ogData.videos.length} vidéo(s)
                                                                </span>
                                                                ` : ''}
                                                                ${ogData.audios && ogData.audios.length > 0 ? `
                                                                <span style="font-size: 0.85rem; color: #718096;">
                                                                    <i class="fas fa-music"></i> ${ogData.audios.length} audio(s)
                                                                </span>
                                                                ` : ''}
                                                            </div>
                                                            ` : ''}
                                                        </div>
                                                    </div>
                                                </div>
                                            `;
                                        }).join('');
                                    }
                                    return '<p class="empty-state">Aucune donnée OpenGraph disponible pour le moment. Lancez un scraping pour récupérer les métadonnées des pages.</p>';
                                } catch(e) {
                                    console.error('Erreur affichage og_data:', e);
                                    return '<p class="empty-state">Erreur lors du chargement des données OpenGraph.</p>';
                                }
                            })() : '<p class="empty-state">Aucune donnée OpenGraph disponible pour le moment. Lancez un scraping pour récupérer les métadonnées des pages.</p>'}
                        </div>
                    </div>
                    
                    <!-- Onglet Résultats scraping -->
                    <div class="tab-panel" id="tab-scraping">
                        
                        <div id="scraping-results" class="scraping-results" style="display: block;">
                            <h3>Résultats de l'analyse</h3>
                            
                            <div class="results-tabs" style="display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #e9ecef; flex-wrap: wrap;">
                                <button class="tab-button active" data-tab="emails">Emails (<span id="count-emails-modal">0</span>)</button>
                                <button class="tab-button" data-tab="people">Personnes (<span id="count-people-modal">0</span>)</button>
                                <button class="tab-button" data-tab="phones">Téléphones (<span id="count-phones-modal">0</span>)</button>
                                <button class="tab-button" data-tab="social">Réseaux sociaux (<span id="count-social-modal">0</span>)</button>
                                <button class="tab-button" data-tab="technologies">Technologies (<span id="count-tech-modal">0</span>)</button>
                                <button class="tab-button" data-tab="metadata">Métadonnées</button>
                            </div>
                            
                            <div id="tab-emails-modal" class="tab-content active">
                                <div id="emails-list-modal" class="results-list"></div>
                            </div>
                            
                            <div id="tab-people-modal" class="tab-content">
                                <div id="people-list-modal" class="results-list"></div>
                            </div>
                            
                            <div id="tab-phones-modal" class="tab-content">
                                <div id="phones-list-modal" class="results-list"></div>
                            </div>
                            
                            <div id="tab-social-modal" class="tab-content">
                                <div id="social-list-modal" class="results-list"></div>
                            </div>
                            
                            <div id="tab-technologies-modal" class="tab-content">
                                <div id="technologies-list-modal" class="results-list"></div>
                            </div>
                            
                            <div id="tab-metadata-modal" class="tab-content">
                                <div id="metadata-list-modal" class="results-list"></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Onglet Analyse technique -->
                    <div class="tab-panel" id="tab-technique">
                        <div id="technique-results" class="analysis-results">
                            <div id="technique-results-content">Chargement de l'analyse technique...</div>
                        </div>
                    </div>
                    
                    <!-- Onglet Analyse OSINT -->
                    <div class="tab-panel" id="tab-osint">
                        <div id="osint-results" class="analysis-results">
                            <div id="osint-results-content">Chargement de l'analyse OSINT...</div>
                        </div>
                    </div>
                    
                    <!-- Onglet Analyse Pentest -->
                    <div class="tab-panel" id="tab-pentest">
                        <div id="pentest-results" class="analysis-results">
                            <div id="pentest-results-content">Chargement de l'analyse Pentest...</div>
                            </div>
                            </div>
                            
                </div>
            </div>
            
            <div class="modal-footer">
                <button class="btn btn-secondary" id="modal-close-footer-btn">Fermer</button>
                <button class="btn btn-outline ${entreprise.favori ? 'active' : ''}" id="modal-toggle-favori">
                    ${entreprise.favori ? '<i class="fas fa-star"></i> Favori' : '<i class="far fa-star"></i> Ajouter aux favoris'}
                </button>
            </div>
        `;
    }
    
    function createInfoRow(label, value, isLink = false, customContent = null) {
        if (!value && !customContent) return '';
        
        const content = customContent || (isLink ? `<a href="${value}" target="_blank" rel="noopener">${value}</a>` : value);
        
        return `
            <div class="info-row">
                <span class="info-label">${label}:</span>
                <span class="info-value">${content}</span>
            </div>
        `;
    }
    
    /**
     * Calcule les infos de score de securite a partir d'un score numerique 0-100.
     * @param {number|null|undefined} score
     * @returns {{label: string, className: string}}
     */
    function getSecurityScoreInfo(score) {
        if (score === null || score === undefined || Number.isNaN(Number(score))) {
            return { label: 'Non analyse', className: 'secondary' };
        }
        const s = Math.max(0, Math.min(100, Number(score)));
        if (s >= 80) {
            return { label: `${s}/100 (Securise)`, className: 'success' };
        }
        if (s >= 50) {
            return { label: `${s}/100 (Moyen)`, className: 'warning' };
        }
        return { label: `${s}/100 (Faible)`, className: 'danger' };
    }
    
    /**
     * Genere un badge HTML pour le score de securite.
     * @param {number|null|undefined} score
     * @param {string|null} id
     * @returns {string}
     */
    function getSecurityScoreBadge(score, id = null) {
        const info = getSecurityScoreInfo(score);
        const idAttr = id ? ` id="${id}"` : '';
        return `<span${idAttr} class="badge badge-${info.className}">${info.label}</span>`;
    }

    /**
     * Calcule un badge de performance simple (0-100).
     * @param {number|null|undefined} score
     * @returns {{label: string, className: string}}
     */
    function getPerformanceScoreInfo(score) {
        if (score === null || score === undefined || Number.isNaN(Number(score))) {
            return { label: 'Non analysé', className: 'secondary' };
        }
        const s = Math.max(0, Math.min(100, Number(score)));
        if (s >= 80) return { label: `${s}/100 (Rapide)`, className: 'success' };
        if (s >= 50) return { label: `${s}/100 (Moyen)`, className: 'warning' };
        return { label: `${s}/100 (Lent)`, className: 'danger' };
    }

    /**
     * Génère un badge HTML pour le score de perf.
     * @param {number|null|undefined} score
     * @returns {string}
     */
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
    
    function getStatusBadge(statut) {
        if (!statut) return '';
        const classes = {
            'Nouveau': 'primary',
            'À qualifier': 'warning',
            'Relance': 'relance',
            'Gagné': 'success',
            'Perdu': 'danger'
        };
        const class_name = classes[statut] || 'secondary';
        return `<span class="badge badge-${class_name}">${statut}</span>`;
    }
    
    function closeEntrepriseModal() {
        const modal = document.getElementById('entreprise-modal');
        if (modal) {
            modal.style.display = 'none';
            currentModalEntrepriseId = null;
            currentModalEntrepriseData = null;
            currentModalPentestScore = null;
        }
    }
    
    function setupModalInteractions() {
        // Fermeture de la modale
        const closeBtn = document.getElementById('modal-close-btn');
        const closeFooterBtn = document.getElementById('modal-close-footer-btn');
        const modal = document.getElementById('entreprise-modal');
        
        // Fermeture au clic sur le bouton X
        if (closeBtn) {
            closeBtn.onclick = (e) => {
                e.stopPropagation();
                closeEntrepriseModal();
            };
        }
        
        // Fermeture au clic sur le bouton "Fermer"
        if (closeFooterBtn) {
            closeFooterBtn.onclick = (e) => {
                e.stopPropagation();
                closeEntrepriseModal();
            };
        }
        
        // Fermeture au clic sur l'overlay (fond sombre)
        if (modal) {
            modal.onclick = (e) => {
                if (e.target === modal) {
                    closeEntrepriseModal();
                }
            };
        }
        
        // Fermeture avec la touche Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal && modal.style.display !== 'none') {
                closeEntrepriseModal();
                }
            });
        
        // Fermer en cliquant en dehors (déjà géré par la fonction closeEntrepriseModal)
        
        // Onglets
        const tabBtns = document.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.getAttribute('data-tab');
                
                // Désactiver tous les onglets
                tabBtns.forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                
                // Activer l'onglet sélectionné
                btn.classList.add('active');
                const targetPanel = document.getElementById(`tab-${tabName}`);
                if (targetPanel) {
                    targetPanel.classList.add('active');
                }
            });
        });
        
        // Favori
        const favoriBtn = document.getElementById('modal-toggle-favori');
        if (favoriBtn) {
            favoriBtn.addEventListener('click', async () => {
                await toggleModalFavori();
            });
        }
        
        
        // Lancement du scraping (délégation d'événements pour les éléments créés dynamiquement)
        const modalBody = document.getElementById('modal-entreprise-body');
        if (modalBody) {
            modalBody.addEventListener('click', async (e) => {
                if (e.target.closest('.btn-launch-scraping')) {
                    const btn = e.target.closest('.btn-launch-scraping');
                    const entrepriseId = btn.getAttribute('data-id');
                    const url = btn.getAttribute('data-url');
                    await launchScraping(entrepriseId, url);
                }
                // Gestion des onglets
                if (e.target.closest('.tab-button')) {
                    const tabBtn = e.target.closest('.tab-button');
                    const tabName = tabBtn.getAttribute('data-tab');
                    
                    // Désactiver tous les onglets
                    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    
                    // Activer l'onglet sélectionné
                    tabBtn.classList.add('active');
                    const targetPanel = document.getElementById(`tab-${tabName}-modal`);
                    if (targetPanel) {
                        targetPanel.classList.add('active');
                    }
                }
            });
        }
        
        // Recharger les résultats quand on clique sur les onglets d'analyse
        const techniqueTab = document.querySelector('.tab-btn[data-tab="technique"]');
        if (techniqueTab) {
            techniqueTab.addEventListener('click', () => {
                if (currentModalEntrepriseId) {
                    loadTechnicalAnalysis(currentModalEntrepriseId);
                }
            });
        }
        
        const osintTab = document.querySelector('.tab-btn[data-tab="osint"]');
        if (osintTab) {
            osintTab.addEventListener('click', () => {
                if (currentModalEntrepriseId) {
                    loadOSINTAnalysis(currentModalEntrepriseId);
                }
            });
        }
        
        const pentestTab = document.querySelector('.tab-btn[data-tab="pentest"]');
        if (pentestTab) {
            pentestTab.addEventListener('click', () => {
                if (currentModalEntrepriseId) {
                    loadPentestAnalysis(currentModalEntrepriseId);
                }
            });
        }
        
        // Recharger les résultats quand on clique sur l'onglet Scraping
        const scrapingTab = document.querySelector('.tab-btn[data-tab="scraping"]');
        if (scrapingTab) {
            scrapingTab.addEventListener('click', () => {
                if (currentModalEntrepriseId) {
                    loadScrapingResults(currentModalEntrepriseId);
                }
            });
        }
        
    }
    
    async function loadTechnicalAnalysis(entrepriseId) {
        const resultsContent = document.getElementById('technique-results-content');
        if (!resultsContent) return;
        
        try {
            resultsContent.innerHTML = 'Chargement...';
            
            const response = await fetch(`/api/entreprise/${entrepriseId}/analyse-technique`);
            if (response.ok) {
                const analysis = await response.json();
                displayTechnicalAnalysis(analysis);
            } else if (response.status === 404) {
                resultsContent.innerHTML = '<p class="empty-state">Aucune analyse technique disponible pour le moment.</p>';
            } else {
                resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse technique</p>';
            }
        } catch (error) {
            console.error('Erreur lors du chargement de l\'analyse technique:', error);
            resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse technique</p>';
        }
    }
    
    async function loadOSINTAnalysis(entrepriseId) {
        const resultsContent = document.getElementById('osint-results-content');
        if (!resultsContent) return;
        
        try {
            resultsContent.innerHTML = 'Chargement...';
            
            const response = await fetch(`/api/entreprise/${entrepriseId}/analyse-osint`);
            if (response.ok) {
                const analysis = await response.json();
                displayOSINTAnalysis(analysis);
            } else if (response.status === 404) {
                resultsContent.innerHTML = '<p class="empty-state">Aucune analyse OSINT disponible pour le moment.</p>';
            } else {
                resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse OSINT</p>';
            }
        } catch (error) {
            console.error('Erreur lors du chargement de l\'analyse OSINT:', error);
            resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse OSINT</p>';
        }
    }
    
    async function loadPentestAnalysis(entrepriseId) {
        const resultsContent = document.getElementById('pentest-results-content');
        if (!resultsContent) return;
        
        try {
            resultsContent.innerHTML = 'Chargement...';
            
            const response = await fetch(`/api/entreprise/${entrepriseId}/analyse-pentest`);
            if (response.ok) {
                const analysis = await response.json();
                // Stocker le score pentest pour l'afficher dans l'en-tête
                currentModalPentestScore = analysis.risk_score || null;
                displayPentestAnalysis(analysis);
                
                // Mettre à jour l'affichage du score dans l'en-tête si présent
                if (currentModalPentestScore !== null) {
                    const pentestRow = document.getElementById('pentest-score-row');
                    const pentestValue = document.getElementById('pentest-score-value');
                    if (pentestRow && pentestValue) {
                        const icon = currentModalPentestScore >= 70 ? '<i class="fas fa-exclamation-circle"></i> ' : currentModalPentestScore >= 40 ? '<i class="fas fa-exclamation-triangle"></i> ' : '';
                        const badgeClass = currentModalPentestScore >= 70 ? 'danger' : currentModalPentestScore >= 40 ? 'warning' : 'success';
                        pentestValue.innerHTML = `${icon}<span class="badge badge-${badgeClass}">${currentModalPentestScore}/100</span>`;
                        pentestRow.style.display = '';
                    }
                } else {
                    const pentestRow = document.getElementById('pentest-score-row');
                    if (pentestRow) {
                        pentestRow.style.display = 'none';
                    }
                }
            } else if (response.status === 404) {
                currentModalPentestScore = null;
                resultsContent.innerHTML = '<p class="empty-state">Aucune analyse Pentest disponible pour le moment.</p>';
            } else {
                currentModalPentestScore = null;
                resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse Pentest</p>';
            }
        } catch (error) {
            console.error('Erreur lors du chargement de l\'analyse Pentest:', error);
            currentModalPentestScore = null;
            resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse Pentest</p>';
        }
    }
    
    async function toggleModalFavori() {
        if (!currentModalEntrepriseId) return;
        
        try {
            const response = await fetch(`/api/entreprise/${currentModalEntrepriseId}/favori`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                currentModalEntrepriseData.favori = data.favori;
                const favoriBtn = document.getElementById('modal-toggle-favori');
                if (favoriBtn) {
                    if (data.favori) {
                        favoriBtn.classList.add('active');
                        favoriBtn.innerHTML = '<i class="fas fa-star"></i> Favori';
                    } else {
                        favoriBtn.classList.remove('active');
                        favoriBtn.textContent = '☆ Ajouter aux favoris';
                    }
                }
                
                // Mettre à jour dans la liste aussi
                const entreprise = allEntreprises.find(e => e.id === currentModalEntrepriseId);
                if (entreprise) {
                    entreprise.favori = data.favori;
                }
                applyFilters();
            }
        } catch (error) {
            console.error('Erreur lors du toggle favori:', error);
            showNotification('Erreur lors de la mise à jour du favori', 'error');
        }
    }
    
    async function addModalTag(tagText) {
        if (!tagText || !currentModalEntrepriseId) return;
        
        const tags = currentModalEntrepriseData.tags || [];
        if (tags.includes(tagText)) return;
        
        tags.push(tagText);
        await updateModalTags(tags);
    }
    
    async function removeModalTag(tagText) {
        if (!currentModalEntrepriseId) return;
        
        const tags = (currentModalEntrepriseData.tags || []).filter(t => t !== tagText);
        await updateModalTags(tags);
    }
    
    async function updateModalTags(tags) {
        if (!currentModalEntrepriseId) return;
        
        try {
            const response = await fetch(`/api/entreprise/${currentModalEntrepriseId}/tags`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tags })
            });
            const data = await response.json();
            
            if (data.success) {
                currentModalEntrepriseData.tags = tags;
                
                // Mettre à jour l'affichage des tags
                const tagsContainer = document.getElementById('modal-tags-container');
                if (tagsContainer) {
                    tagsContainer.innerHTML = tags.map(tag => 
                        `<span class="tag editable" data-tag="${tag}">${tag} <button class="tag-remove"><i class="fas fa-times"></i></button></span>`
                    ).join('') + '<input type="text" id="modal-tag-input" placeholder="Ajouter un tag (Entrée pour valider)" class="tag-input">';
                    
                    // Re-setup les event listeners
                    const tagInput = document.getElementById('modal-tag-input');
                    if (tagInput) {
                        tagInput.addEventListener('keypress', (e) => {
                            if (e.key === 'Enter') {
                                e.preventDefault();
                                addModalTag(tagInput.value.trim());
                                tagInput.value = '';
                            }
                        });
                    }
                    
                    document.querySelectorAll('#modal-tags-container .tag-remove').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const tag = e.target.closest('.tag').dataset.tag;
                            removeModalTag(tag);
                        });
                    });
                }
                
                // Mettre à jour dans la liste aussi
                const entreprise = allEntreprises.find(e => e.id === currentModalEntrepriseId);
                if (entreprise) {
                    entreprise.tags = tags;
                }
                applyFilters();
            }
        } catch (error) {
            console.error('Erreur lors de la mise à jour des tags:', error);
            showNotification('Erreur lors de la mise à jour des tags', 'error');
        }
    }
    
    async function saveModalNotes() {
        if (!currentModalEntrepriseId) return;
        
        const notesTextarea = document.getElementById('modal-notes-textarea');
        if (!notesTextarea) return;
        
        const notes = notesTextarea.value;
        
        try {
            const response = await fetch(`/api/entreprise/${currentModalEntrepriseId}/notes`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes })
            });
            const data = await response.json();
            
            if (data.success) {
                currentModalEntrepriseData.notes = notes;
                const btn = document.getElementById('modal-btn-save-notes');
                if (btn) {
                    const originalText = btn.textContent;
                    btn.innerHTML = '<i class="fas fa-check"></i> Enregistré !';
                    btn.classList.add('success');
                    setTimeout(() => {
                        btn.textContent = originalText;
                        btn.classList.remove('success');
                    }, 2000);
                }
            }
        } catch (error) {
            console.error('Erreur lors de la sauvegarde des notes:', error);
            showNotification('Erreur lors de la sauvegarde des notes', 'error');
        }
    }
    
    async function launchScraping(entrepriseId, url) {
        if (!url) {
            showNotification('Aucun site web disponible pour lancer une analyse', 'error');
            return;
        }
        
        const statusDiv = document.getElementById('scraping-status');
        const progressDiv = document.getElementById('scraping-progress');
        const progressBar = document.getElementById('scraping-progress-bar');
        const progressText = document.getElementById('scraping-progress-text');
        const btn = document.querySelector('.btn-launch-scraping');
        
        if (!window.wsManager || !window.wsManager.socket) {
            showNotification('WebSocket non connecté', 'error');
            return;
        }
        
        try {
            if (btn) {
                btn.disabled = true;
            }
            if (statusDiv) {
                statusDiv.style.display = 'block';
                statusDiv.innerHTML = '<div class="status-info">Lancement de l\'analyse...</div>';
            }
            if (progressDiv) {
                progressDiv.style.display = 'flex';
            }
            
            // Réinitialiser les listes
            document.getElementById('emails-list-modal').innerHTML = '<div class="empty-state">Aucun email trouvé pour le moment...</div>';
            document.getElementById('people-list-modal').innerHTML = '<div class="empty-state">Aucune personne trouvée pour le moment...</div>';
            document.getElementById('phones-list-modal').innerHTML = '<div class="empty-state">Aucun téléphone trouvé pour le moment...</div>';
            document.getElementById('social-list-modal').innerHTML = '<div class="empty-state">Aucun réseau social trouvé pour le moment...</div>';
            document.getElementById('technologies-list-modal').innerHTML = '<div class="empty-state">Aucune technologie détectée pour le moment...</div>';
            document.getElementById('metadata-list-modal').innerHTML = '<div class="empty-state">Aucune métadonnée extraite pour le moment...</div>';
            
            // Réinitialiser les compteurs
            updateModalCount('emails', 0);
            updateModalCount('people', 0);
            updateModalCount('phones', 0);
            updateModalCount('social', 0);
            updateModalCount('tech', 0);
            
            scrapingResultsData = {
                emails: [],
                people: [],
                phones: [],
                social: {}
            };
            
            // Écouter les événements
            const socket = window.wsManager.socket;
            if (socket && socket.off) {
                socket.off('scraping_started');
                socket.off('scraping_progress');
                socket.off('scraping_complete');
                socket.off('scraping_stopped');
                socket.off('scraping_error');
            }
            
            socket.on('scraping_started', (data) => {
                if (statusDiv) {
                    statusDiv.innerHTML = '<div class="status-info">Analyse démarrée...</div>';
                }
                if (progressBar) progressBar.style.width = '0%';
                if (progressText) progressText.textContent = 'Initialisation...';
            });
            
            socket.on('scraping_progress', (data) => {
                if (progressBar) {
                    // Utiliser le pourcentage basé sur current/total si disponible
                    if (data.current && data.total) {
                        const percent = Math.min(90, (data.current / data.total) * 90);
                        progressBar.style.width = percent + '%';
                    } else {
                    const percent = Math.min(90, (data.visited || 0) * 5);
                    progressBar.style.width = percent + '%';
                    }
                }
                if (progressText) {
                    // Afficher le message formaté s'il est disponible, sinon utiliser les données individuelles
                    if (data.message) {
                        progressText.textContent = data.message;
                    } else {
                    progressText.textContent = `${data.visited || 0} page(s) analysée(s) - ${data.emails || 0} emails, ${data.people || 0} personnes`;
                    }
                }
            });
            
            socket.on('scraping_email_found', (data) => {
                if (!scrapingResultsData.emails.includes(data.email)) {
                    scrapingResultsData.emails.push(data.email);
                    addEmailToModal(data.email, data.analysis);
                    updateModalCount('emails', scrapingResultsData.emails.length);
                }
            });
            
            socket.on('scraping_person_found', (data) => {
                const person = data.person;
                if (person && !scrapingResultsData.people.find(p => p.name === person.name)) {
                    scrapingResultsData.people.push(person);
                    addPersonToModal(person);
                    updateModalCount('people', scrapingResultsData.people.length);
                }
            });
            
            socket.on('scraping_phone_found', (data) => {
                if (!scrapingResultsData.phones.includes(data.phone)) {
                    scrapingResultsData.phones.push(data.phone);
                    addPhoneToModal(data.phone);
                    updateModalCount('phones', scrapingResultsData.phones.length);
                }
            });
            
            socket.on('scraping_social_found', (data) => {
                const platform = data.platform;
                if (!scrapingResultsData.social[platform]) {
                    scrapingResultsData.social[platform] = [];
                }
                if (!scrapingResultsData.social[platform].find(s => s.url === data.url)) {
                    scrapingResultsData.social[platform].push({ url: data.url, text: data.text || '' });
                    addSocialToModal(platform, data.url);
                    updateModalCount('social', Object.keys(scrapingResultsData.social).length);
                }
            });
            
            socket.on('scraping_complete', (data) => {
                if (progressBar) progressBar.style.width = '100%';
                if (progressText) progressText.textContent = 'Analyse terminée';
                if (statusDiv) {
                    statusDiv.innerHTML = `<div class="status-success">Analyse terminée ! ${data.total_emails || 0} emails, ${data.total_people || 0} personnes, ${data.total_phones || 0} téléphones</div>`;
                }
                
                // Afficher tous les résultats
                displayAllScrapingResults(data);
                
                // Mettre à jour l'onglet Images principal avec les images collectées pendant ce scraping
                try {
                    if (data.images && Array.isArray(data.images)) {
                        // Convertir le format vers celui attendu par renderEntrepriseImages
                        const formattedImages = data.images.map(img => ({
                            url: img.url || img,
                            alt: img.alt || img.alt_text || '',
                            width: img.width,
                            height: img.height
                        }));
                        renderEntrepriseImages(formattedImages);
                    }
                } catch (e) {
                    console.error('Erreur lors de l\'affichage des images de scraping:', e);
                }
                if (btn) btn.disabled = false;
                
                // Ne pas recharger depuis la base car on a déjà les données en temps réel
                // Les données sont déjà affichées via displayAllScrapingResults
            });
            
            socket.on('scraping_stopped', (data) => {
                if (statusDiv) {
                    statusDiv.innerHTML = '<div class="status-warning">Analyse arrêtée</div>';
                }
                if (progressBar) progressBar.style.width = '0%';
                if (progressText) progressText.textContent = 'Arrêté';
                
                if (btn) btn.disabled = false;
            });
            
            socket.on('scraping_error', (data) => {
                if (statusDiv) {
                    statusDiv.innerHTML = `<div class="status-error">Erreur: ${data.error || 'Erreur inconnue'}</div>`;
                }
                
                if (btn) btn.disabled = false;
                showNotification('Erreur lors du lancement de l\'analyse', 'error');
            });
            
            // Lancer le scraping
            socket.emit('start_scraping', {
                url: url,
                max_depth: 3,
                max_workers: 5,
                max_time: 300,
                entreprise_id: entrepriseId
            });
            
        } catch (error) {
            console.error('Erreur lors du lancement du scraping:', error);
            if (statusDiv) {
                statusDiv.innerHTML = `<div class="status-error">Erreur: ${error.message}</div>`;
            }
            btn.style.display = 'inline-block';
            btn.disabled = false;
            if (btnStop) {
                btnStop.style.display = 'none';
            }
            showNotification('Erreur lors du lancement de l\'analyse', 'error');
        }
    }
    
    let scrapingResultsData = {
        emails: [],
        people: [],
        phones: [],
        social: {}
    };
    
    /**
     * Charge les images d'une entreprise depuis l'API et les affiche dans l'onglet Images principal
     * @param {number} entrepriseId - ID de l'entreprise
     */
    async function loadEntrepriseImages(entrepriseId) {
        try {
            const imagesResponse = await fetch(`/api/entreprise/${entrepriseId}/images`);
            if (imagesResponse.ok) {
                const images = await imagesResponse.json();
                // Convertir le format BDD vers le format attendu par renderEntrepriseImages
                const formattedImages = images.map(img => ({
                    url: img.url,
                    alt: img.alt_text || img.alt || '',
                    width: img.width,
                    height: img.height
                }));
                renderEntrepriseImages(formattedImages);
            }
        } catch (e) {
            console.error('Erreur lors du chargement des images:', e);
        }
    }
    
    /**
     * Affiche les images collectées (depuis le scraper) dans l'onglet Images de la fiche entreprise.
     * @param {Array} images - Liste d'objets {url, alt, width, height}
     */
    function renderEntrepriseImages(images) {
        const container = document.getElementById('entreprise-images-container');
        if (!container) return;
        
        if (!images || images.length === 0) {
            container.innerHTML = '<p class="empty-state">Aucune image trouvée pour ce site.</p>';
            return;
        }
        
        const maxImages = 60; // éviter de surcharger la modale
        const limited = images.slice(0, maxImages);
        
        let html = '<div class="entreprise-images-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px;">';
        for (const img of limited) {
            const url = img.url || img;
            const alt = img.alt || '';
            html += `
                <div class="entreprise-image-card" style="background: #ffffff; border-radius: 8px; box-shadow: 0 2px 6px rgba(15,23,42,0.08); padding: 8px; display: flex; flex-direction: column; align-items: center;">
                    <div class="entreprise-image-thumb" style="width: 100%; height: 120px; border-radius: 6px; overflow: hidden; background: #f3f4f6; display: flex; align-items: center; justify-content: center;">
                        <img src="${url}" alt="${escapeHtml(alt || '')}" loading="lazy" onerror="this.style.display='none'" style="width: 100%; height: 100%; object-fit: cover;">
                    </div>
                    <div class="entreprise-image-info" style="margin-top: 6px; width: 100%; text-align: left;">
                        ${alt ? `<div class="entreprise-image-alt" title="${escapeHtml(alt)}" style="font-size: 0.8rem; color: #374151; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(alt)}</div>` : '<div class="entreprise-image-alt empty" style="font-size: 0.8rem; color: #9ca3af; margin-bottom: 4px;">Sans texte alternatif</div>'}
                        <a href="${url}" target="_blank" class="entreprise-image-link" style="font-size: 0.8rem; color: #2563eb; text-decoration: none;">Ouvrir l'image</a>
                    </div>
                </div>
            `;
        }
        html += '</div>';
        container.innerHTML = html;
    }
    
    function updateScrapingResults(type, email, person, phone, social) {
        const resultsDiv = document.getElementById('scraping-results-content');
        if (!resultsDiv) return;
        
        // Supprimer le message vide si présent
        const emptyState = resultsDiv.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        if (type === 'email' && email && !scrapingResultsData.emails.includes(email)) {
            scrapingResultsData.emails.push(email);
        } else if (type === 'person' && person && !scrapingResultsData.people.find(p => p.name === person.name)) {
            scrapingResultsData.people.push(person);
        } else if (type === 'phone' && phone && !scrapingResultsData.phones.includes(phone)) {
            scrapingResultsData.phones.push(phone);
        } else if (type === 'social' && social) {
            if (!scrapingResultsData.social[social.platform]) {
                scrapingResultsData.social[social.platform] = [];
            }
            if (!scrapingResultsData.social[social.platform].find(s => s.url === social.url)) {
                scrapingResultsData.social[social.platform].push(social);
            }
        }
        
        // Afficher les résultats en temps réel
        displayScrapingResultsRealTime();
    }
    
    function displayScrapingResultsRealTime() {
        const resultsDiv = document.getElementById('scraping-results-content');
        if (!resultsDiv) return;
        
        let html = '<div class="scraping-results-grid">';
        
        // Emails
        html += `
            <div class="scraping-result-card">
                <h4><i class="fas fa-envelope"></i> Emails (${scrapingResultsData.emails.length})</h4>
                <div class="scraping-result-list">
                    ${scrapingResultsData.emails.length > 0 ? 
                        scrapingResultsData.emails.map(email => `<div class="scraping-result-item">${email}</div>`).join('') :
                        '<div class="empty-state-small">Aucun email trouvé</div>'
                    }
                </div>
            </div>
        `;
        
        // Personnes
        html += `
            <div class="scraping-result-card">
                <h4>👤 Personnes (${scrapingResultsData.people.length})</h4>
                <div class="scraping-result-list">
                    ${scrapingResultsData.people.length > 0 ? 
                        scrapingResultsData.people.map(person => `
                            <div class="scraping-result-item">
                                <strong>${person.name || ''}</strong>
                                ${person.title ? `<div style="font-size: 0.85rem; color: #666;">${person.title}</div>` : ''}
                                ${person.email ? `<div style="font-size: 0.85rem; color: #3498db;">${person.email}</div>` : ''}
                            </div>
                        `).join('') :
                        '<div class="empty-state-small">Aucune personne trouvée</div>'
                    }
                </div>
            </div>
        `;
        
        // Téléphones
        html += `
            <div class="scraping-result-card">
                <h4><i class="fas fa-phone"></i> Téléphones (${scrapingResultsData.phones.length})</h4>
                <div class="scraping-result-list">
                    ${scrapingResultsData.phones.length > 0 ? 
                        scrapingResultsData.phones.map(phone => `<div class="scraping-result-item">${phone}</div>`).join('') :
                        '<div class="empty-state-small">Aucun téléphone trouvé</div>'
                    }
                </div>
            </div>
        `;
        
        // Réseaux sociaux
        const socialCount = Object.keys(scrapingResultsData.social).length;
        html += `
            <div class="scraping-result-card">
                <h4><i class="fas fa-link"></i> Réseaux sociaux (${socialCount})</h4>
                <div class="scraping-result-list">
                    ${socialCount > 0 ? 
                        Object.entries(scrapingResultsData.social).map(([platform, links]) => `
                            <div class="scraping-result-item">
                                <strong>${platform}</strong>
                                ${links.map(link => `<div style="font-size: 0.85rem;"><a href="${link.url}" target="_blank">${link.url}</a></div>`).join('')}
                            </div>
                        `).join('') :
                        '<div class="empty-state-small">Aucun réseau social trouvé</div>'
                    }
                </div>
            </div>
        `;
        
        html += '</div>';
        resultsDiv.innerHTML = html;
    }
    
    function displayAllScrapingResults(data) {
        // Mettre à jour les données
        scrapingResultsData = {
            emails: data.emails || [],
            people: data.people || [],
            phones: data.phones || [],
            social: data.social_links || {}
        };
        
        // Afficher tous les emails
        const emailsList = document.getElementById('emails-list-modal');
        if (emailsList) {
            emailsList.innerHTML = '';
            scrapingResultsData.emails.forEach(email => {
                addEmailToModal(email, null);
            });
            updateModalCount('emails', scrapingResultsData.emails.length);
        }
        
        // Afficher toutes les personnes
        const peopleList = document.getElementById('people-list-modal');
        if (peopleList) {
            peopleList.innerHTML = '';
            scrapingResultsData.people.forEach(person => {
                addPersonToModal(person);
            });
            updateModalCount('people', scrapingResultsData.people.length);
        }
        
        // Afficher tous les téléphones
        const phonesList = document.getElementById('phones-list-modal');
        if (phonesList) {
            phonesList.innerHTML = '';
            scrapingResultsData.phones.forEach(phoneData => {
                // phoneData peut être un objet {phone: "...", page_url: "..."} ou une string
                const phoneStr = typeof phoneData === 'object' && phoneData !== null && phoneData.phone 
                    ? phoneData.phone 
                    : (typeof phoneData === 'string' ? phoneData : String(phoneData));
                addPhoneToModal(phoneStr);
            });
            updateModalCount('phones', scrapingResultsData.phones.length);
        }
        
        // Afficher tous les réseaux sociaux
        const socialList = document.getElementById('social-list-modal');
        if (socialList) {
            socialList.innerHTML = '';
            Object.entries(scrapingResultsData.social).forEach(([platform, links]) => {
                const linkList = Array.isArray(links) ? links : [links];
                linkList.forEach(link => {
                    const url = typeof link === 'object' ? link.url : link;
                    addSocialToModal(platform, url);
                });
            });
            updateModalCount('social', Object.keys(scrapingResultsData.social).length);
        }
        
        // Afficher les technologies
        if (data.technologies) {
            const techList = document.getElementById('technologies-list-modal');
            if (techList) {
                techList.innerHTML = '';
                Object.entries(data.technologies).forEach(([category, techs]) => {
                    const techListStr = Array.isArray(techs) ? techs : [techs];
                    const categoryDiv = document.createElement('div');
                    categoryDiv.className = 'result-item tech-item';
                    categoryDiv.innerHTML = `
                        <div class="result-item-icon"><i class="fas fa-cog"></i></div>
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
                });
                updateModalCount('tech', Object.keys(data.technologies).length);
            }
        }
        
        // Afficher les métadonnées
        if (data.metadata && data.metadata.meta_tags) {
            const metaList = document.getElementById('metadata-list-modal');
            if (metaList) {
                metaList.innerHTML = '';
                const importantKeys = ['title', 'description', 'og:title', 'og:description', 'og:url', 'og:image'];
                Object.entries(data.metadata.meta_tags).forEach(([key, value]) => {
                    if (importantKeys.includes(key)) {
                        const displayKey = key.replace('og:', '').replace(/:/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        const item = document.createElement('div');
                        item.className = 'result-item metadata-item';
                        item.innerHTML = `
                            <div class="result-item-content">
                                <div class="result-item-header">
                                    <strong class="result-item-title">${escapeHtml(displayKey)}</strong>
                                </div>
                                <div class="result-item-meta">${escapeHtml(String(value))}</div>
                            </div>
                        `;
                        metaList.appendChild(item);
                    }
                });
            }
        }
    }
    
    function updateModalCount(type, count) {
        const countElement = document.getElementById(`count-${type}-modal`);
        if (countElement) {
            countElement.textContent = count;
        }
    }
    
    function addEmailToModal(email, analysis) {
        const list = document.getElementById('emails-list-modal');
        if (!list) return;
        
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        // Extraire l'email string si c'est un objet
        let emailStr = email;
        if (typeof email === 'object' && email !== null) {
            emailStr = email.email || email.value || String(email);
            // Si analysis n'est pas fourni mais que l'objet email contient analysis
            if (!analysis && email.analysis) {
                analysis = email.analysis;
            }
        }
        
        const existingEmail = Array.from(list.children).find(item => {
            const emailText = item.querySelector('.result-item-title')?.textContent;
            return emailText === emailStr;
        });
        if (existingEmail) return;
        
        const item = document.createElement('div');
        item.className = 'result-item email-item';
        item.innerHTML = `
            <div class="result-item-icon"><i class="fas fa-envelope"></i></div>
            <div class="result-item-content">
                <div class="result-item-header">
                    <strong class="result-item-title">${escapeHtml(emailStr)}</strong>
                    ${analysis && analysis.type ? `<span class="result-item-badge">${escapeHtml(analysis.type)}</span>` : ''}
                </div>
                ${analysis && analysis.provider ? `<div class="result-item-meta">Fournisseur: ${escapeHtml(analysis.provider)}</div>` : ''}
            </div>
        `;
        list.appendChild(item);
        
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    }
    
    function addPersonToModal(person) {
        const list = document.getElementById('people-list-modal');
        if (!list) return;
        
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
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
                contactInfo += `<div class="contact-item"><span class="contact-icon"><i class="fas fa-envelope"></i></span><a href="mailto:${escapeHtml(person.email)}">${escapeHtml(person.email)}</a></div>`;
            }
            if (person.phone) {
                contactInfo += `<div class="contact-item"><span class="contact-icon"><i class="fas fa-phone"></i></span><a href="tel:${escapeHtml(person.phone)}">${escapeHtml(person.phone)}</a></div>`;
            }
            if (person.linkedin_url) {
                contactInfo += `<div class="contact-item"><span class="contact-icon"><i class="fab fa-linkedin"></i></span><a href="${escapeHtml(person.linkedin_url)}" target="_blank">Profil LinkedIn</a></div>`;
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
        
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    }
    
    function addPhoneToModal(phone) {
        const list = document.getElementById('phones-list-modal');
        if (!list) return;
        
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        const existingPhone = Array.from(list.children).find(item => {
            const phoneText = item.querySelector('.result-item-title')?.textContent;
            return phoneText === phone;
        });
        if (existingPhone) return;
        
        const item = document.createElement('div');
        item.className = 'result-item phone-item';
        item.innerHTML = `
            <div class="result-item-icon"><i class="fas fa-phone"></i></div>
            <div class="result-item-content">
                <div class="result-item-header">
                    <strong class="result-item-title">${escapeHtml(phone)}</strong>
                </div>
                <div class="result-item-meta"><a href="tel:${escapeHtml(phone)}" class="phone-link">Appeler</a></div>
            </div>
        `;
        list.appendChild(item);
        
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    }
    
    function addSocialToModal(platform, url) {
        const list = document.getElementById('social-list-modal');
        if (!list) return;
        
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        const existingSocial = Array.from(list.children).find(item => {
            const urlLink = item.querySelector('a')?.href;
            return urlLink === url;
        });
        if (existingSocial) return;
        
        const platformIcons = {
            'facebook': '<i class="fab fa-facebook"></i>',
            'twitter': '<i class="fab fa-twitter"></i>',
            'linkedin': '<i class="fab fa-linkedin"></i>',
            'instagram': '<i class="fab fa-instagram"></i>',
            'youtube': '<i class="fab fa-youtube"></i>',
            'github': '<i class="fab fa-github"></i>'
        };
        
        const icon = platformIcons[platform.toLowerCase()] || '<i class="fas fa-link"></i>';
        
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
        
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    async function loadScrapingResults(entrepriseId) {
        // Réinitialiser les listes
        document.getElementById('emails-list-modal').innerHTML = '<div class="empty-state">Aucun email trouvé</div>';
        document.getElementById('people-list-modal').innerHTML = '<div class="empty-state">Aucune personne trouvée</div>';
        document.getElementById('phones-list-modal').innerHTML = '<div class="empty-state">Aucun téléphone trouvé</div>';
        document.getElementById('social-list-modal').innerHTML = '<div class="empty-state">Aucun réseau social trouvé</div>';
        document.getElementById('technologies-list-modal').innerHTML = '<div class="empty-state">Aucune technologie détectée</div>';
        document.getElementById('metadata-list-modal').innerHTML = '<div class="empty-state">Aucune métadonnée extraite</div>';
        
        // Réinitialiser les compteurs
        updateModalCount('emails', 0);
        updateModalCount('people', 0);
        updateModalCount('phones', 0);
        updateModalCount('social', 0);
        updateModalCount('tech', 0);
        
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/scrapers`);
            
            if (response.ok) {
                const scrapers = await response.json();
                
                // Prendre le scraper le plus récent de type "unified_scraper"
                const unifiedScrapers = scrapers.filter(s => s.scraper_type === 'unified_scraper').sort((a, b) => {
                    const dateA = new Date(a.date_modification || a.date_creation || 0);
                    const dateB = new Date(b.date_modification || b.date_creation || 0);
                    return dateB - dateA;
                });
                
                if (unifiedScrapers.length > 0) {
                    const latestScraper = unifiedScrapers[0];
                    
                    // Construire l'objet data au format attendu
                    // Les emails sont une liste de strings depuis get_scraper_emails
                    let emails = latestScraper.emails || [];
                    if (!Array.isArray(emails)) {
                        emails = [];
                    }
                    
                    // Les people sont une liste de dicts depuis get_scraper_people
                    let people = latestScraper.people || [];
                    if (!Array.isArray(people)) {
                        people = [];
                    }
                    
                    // Les téléphones sont une liste de dicts {phone: "...", page_url: "..."} depuis get_scraper_phones
                    let phones = latestScraper.phones || [];
                    if (!Array.isArray(phones)) {
                        phones = [];
                    }
                    
                    const data = {
                        emails: emails,
                        people: people,
                        phones: phones,
                        social_links: latestScraper.social_profiles || {},
                        technologies: latestScraper.technologies || {},
                        metadata: latestScraper.metadata || {}
                    };
                    
                    // Afficher les résultats avec le même style que la page scraping
                    displayAllScrapingResults(data);
                    
                    // Charger les images depuis la table images (optimisation BDD) et les afficher dans l'onglet Images principal
                    loadEntrepriseImages(entrepriseId);
                } else {
                    // Aucun scraper trouvé, garder les messages vides
                }
            }
        } catch (error) {
            console.error('Erreur lors du chargement des résultats:', error);
        }
    }
    
    async function launchAnalysis(analysisType, entrepriseId) {
        if (!currentModalEntrepriseData || !currentModalEntrepriseData.website) {
            showNotification('Aucun site web disponible pour lancer une analyse', 'error');
            return;
        }
        
        const statusDiv = document.getElementById('analyses-status');
        const url = currentModalEntrepriseData.website;
        
        // Vérifier que le WebSocket est disponible
        if (typeof window.wsManager === 'undefined' || !window.wsManager || !window.wsManager.socket || !window.wsManager.connected) {
            showNotification('Connexion WebSocket non disponible. Veuillez recharger la page.', 'error');
            return;
        }
        
        try {
            if (statusDiv) {
                statusDiv.innerHTML = `<div class="status-info">Lancement de l'analyse ${analysisType}...</div>`;
            }
            
            if (analysisType === 'technique') {
                // Rediriger vers la page d'analyses techniques avec les paramètres dans l'URL
                const params = new URLSearchParams({
                    url: url,
                    enable_nmap: 'true',
                    entreprise_id: entrepriseId || '',
                    auto_start: 'true'
                });
                window.location.href = `/analyses-techniques?${params.toString()}`;
                
            } else if (analysisType === 'osint') {
                // Rediriger vers la page d'analyses OSINT avec les paramètres dans l'URL
                const params = new URLSearchParams({
                    url: url,
                    entreprise_id: entrepriseId || '',
                    auto_start: 'true'
                });
                window.location.href = `/analyses-osint?${params.toString()}`;
            } else if (analysisType === 'pentest') {
                // Rediriger vers la page d'analyses Pentest avec les paramètres dans l'URL
                const params = new URLSearchParams({
                    url: url,
                    entreprise_id: entrepriseId || '',
                    auto_start: 'true'
                });
                window.location.href = `/analyses-pentest?${params.toString()}`;
            } else if (analysisType === 'seo') {
                // Rediriger vers la page d'analyses SEO avec les paramètres dans l'URL
                const params = new URLSearchParams({
                    url: url,
                    entreprise_id: entrepriseId || '',
                    auto_start: 'true'
                });
                window.location.href = `/analyses-seo?${params.toString()}`;
            }
            
            showNotification(`Analyse ${analysisType} lancée. Redirection...`, 'success');
        } catch (error) {
            console.error('Erreur lors du lancement de l\'analyse:', error);
            showNotification('Erreur lors du lancement de l\'analyse', 'error');
            if (statusDiv) {
                statusDiv.innerHTML = '<div class="status-error">Erreur lors du lancement de l\'analyse</div>';
            }
        }
    }
    
    // Fonctions pour lancer les analyses techniques, OSINT et Pentest
    async function launchTechnicalAnalysis(entrepriseId, url) {
        if (!url) {
            showNotification('Aucun site web disponible pour lancer une analyse', 'error');
            return;
        }
        
        const btn = document.querySelector('.btn-launch-technique');
        const progressDiv = document.getElementById('technique-progress');
        const progressBar = document.getElementById('technique-progress-bar');
        const progressText = document.getElementById('technique-progress-text');
        if (!window.wsManager || !window.wsManager.socket || !window.wsManager.connected) {
            showNotification('Connexion WebSocket non disponible. Veuillez recharger la page.', 'error');
            return;
        }
        
        try {
            if (btn) btn.disabled = true;
            if (progressDiv) {
                progressDiv.style.display = 'flex';
                if (progressBar) progressBar.style.width = '5%';
                if (progressText) progressText.textContent = 'Démarrage...';
            }
            
            const socket = window.wsManager.socket;
            if (socket && socket.off) {
                socket.off('technical_analysis_progress');
                socket.off('technical_analysis_complete');
                socket.off('technical_analysis_stopped');
                socket.off('technical_analysis_error');
            }
            
            // Listeners WebSocket
            socket.on('technical_analysis_progress', (data) => {
                if (progressBar) progressBar.style.width = `${data.progress || 0}%`;
                if (progressText) progressText.textContent = data.message || '';
            });
            
            socket.on('technical_analysis_complete', (data) => {
                if (progressBar) progressBar.style.width = '100%';
                if (progressText) progressText.textContent = 'Analyse terminée';
                
                if (btn) btn.disabled = false;
                
                // Recharger les résultats
                loadTechnicalAnalysis(entrepriseId);
            });
            
            socket.on('technical_analysis_stopped', (data) => {
                if (progressBar) progressBar.style.width = '0%';
                if (progressText) progressText.textContent = 'Arrêté';
                if (btn) btn.disabled = false;
            });
            
            socket.on('technical_analysis_error', (data) => {
                if (progressText) progressText.textContent = `Erreur: ${data.error || 'Erreur inconnue'}`;
                if (btn) btn.disabled = false;
                showNotification('Erreur lors de l\'analyse technique', 'error');
            });
            
            socket.emit('start_technical_analysis', {
                url: url,
                entreprise_id: entrepriseId,
                enable_nmap: true
            });
            
        } catch (error) {
            console.error('Erreur lors du lancement de l\'analyse technique:', error);
            if (progressText) progressText.textContent = `Erreur: ${error.message}`;
            if (btn) btn.disabled = false;
            showNotification('Erreur lors du lancement de l\'analyse', 'error');
        }
    }
    
    async function launchOSINTAnalysis(entrepriseId, url) {
        if (!url) {
            showNotification('Aucun site web disponible pour lancer une analyse', 'error');
            return;
        }
        
        const btn = document.querySelector('.btn-launch-osint');
        const btnStop = document.querySelector('.btn-stop-osint');
        const progressDiv = document.getElementById('osint-progress');
        const progressBar = document.getElementById('osint-progress-bar');
        const progressText = document.getElementById('osint-progress-text');
        
        if (!window.wsManager || !window.wsManager.socket || !window.wsManager.connected) {
            showNotification('Connexion WebSocket non disponible. Veuillez recharger la page.', 'error');
            return;
        }
        
        try {
            btn.style.display = 'none';
            if (btnStop) btnStop.style.display = 'inline-block';
            if (progressDiv) progressDiv.style.display = 'block';
            
            const socket = window.wsManager.socket;
            
            // Listeners WebSocket
            socket.on('osint_analysis_progress', (data) => {
                if (progressBar) progressBar.style.width = `${data.progress || 0}%`;
                if (progressText) progressText.textContent = data.message || '';
            });
            
            socket.on('osint_analysis_complete', (data) => {
                if (progressBar) progressBar.style.width = '100%';
                if (progressText) progressText.textContent = 'Analyse terminée';
                
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
                
                // Recharger les résultats
                loadOSINTAnalysis(entrepriseId);
            });
            
            socket.on('osint_analysis_stopped', (data) => {
                if (progressBar) progressBar.style.width = '0%';
                if (progressText) progressText.textContent = 'Arrêté';
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
            });
            
            socket.on('osint_analysis_error', (data) => {
                if (progressText) progressText.textContent = `Erreur: ${data.error || 'Erreur inconnue'}`;
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
                showNotification('Erreur lors de l\'analyse OSINT', 'error');
            });
            
            socket.emit('start_osint_analysis', {
                url: url,
                entreprise_id: entrepriseId
            });
            
        } catch (error) {
            console.error('Erreur lors du lancement de l\'analyse OSINT:', error);
            if (progressText) progressText.textContent = `Erreur: ${error.message}`;
            btn.style.display = 'inline-block';
            if (btnStop) btnStop.style.display = 'none';
            showNotification('Erreur lors du lancement de l\'analyse', 'error');
        }
    }
    
    async function launchPentestAnalysis(entrepriseId, url) {
        if (!url) {
            showNotification('Aucun site web disponible pour lancer une analyse', 'error');
            return;
        }
        
        const btn = document.querySelector('.btn-launch-pentest');
        const btnStop = document.querySelector('.btn-stop-pentest');
        const progressDiv = document.getElementById('pentest-progress');
        const progressBar = document.getElementById('pentest-progress-bar');
        const progressText = document.getElementById('pentest-progress-text');
        
        if (!window.wsManager || !window.wsManager.socket || !window.wsManager.connected) {
            showNotification('Connexion WebSocket non disponible. Veuillez recharger la page.', 'error');
            return;
        }
        
        try {
            btn.style.display = 'none';
            if (btnStop) btnStop.style.display = 'inline-block';
            if (progressDiv) progressDiv.style.display = 'block';
            
            const socket = window.wsManager.socket;
            
            // Listeners WebSocket
            socket.on('pentest_analysis_progress', (data) => {
                if (progressBar) progressBar.style.width = `${data.progress || 0}%`;
                if (progressText) progressText.textContent = data.message || '';
            });
            
            socket.on('pentest_analysis_complete', (data) => {
                if (progressBar) progressBar.style.width = '100%';
                if (progressText) progressText.textContent = 'Analyse terminée';
                
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
                
                // Recharger les résultats
                loadPentestAnalysis(entrepriseId);
            });
            
            socket.on('pentest_analysis_stopped', (data) => {
                if (progressBar) progressBar.style.width = '0%';
                if (progressText) progressText.textContent = 'Arrêté';
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
            });
            
            socket.on('pentest_analysis_error', (data) => {
                if (progressText) progressText.textContent = `Erreur: ${data.error || 'Erreur inconnue'}`;
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
                showNotification('Erreur lors de l\'analyse Pentest', 'error');
            });
            
            socket.emit('start_pentest_analysis', {
                url: url,
                entreprise_id: entrepriseId,
                options: {}
            });
            
        } catch (error) {
            console.error('Erreur lors du lancement de l\'analyse Pentest:', error);
            if (progressText) progressText.textContent = `Erreur: ${error.message}`;
            btn.style.display = 'inline-block';
            if (btnStop) btnStop.style.display = 'none';
            showNotification('Erreur lors du lancement de l\'analyse', 'error');
        }
    }
    
    // Fonctions pour afficher les résultats des analyses
    function displayTechnicalAnalysis(analysis) {
        const resultsContent = document.getElementById('technique-results-content');
        if (!resultsContent) return;
        
        const date = new Date(analysis.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        // Petites variables pour un résumé rapide plus lisible
        const serverLabel = analysis.server_software || 'Inconnu';
        const frameworkLabel = analysis.framework ? `${analysis.framework}${analysis.framework_version ? ' ' + analysis.framework_version : ''}` : 'Aucun détecté';
        const cmsLabel = analysis.cms ? `${analysis.cms}${analysis.cms_version ? ' ' + analysis.cms_version : ''}` : 'Aucun détecté';
        const sslLabel = analysis.ssl_valid ? 'SSL valide' : 'SSL non valide';
        const wafLabel = analysis.waf || 'Aucun détecté';
        const cdnLabel = analysis.cdn || 'Aucun détecté';
        const analyticsCount = analysis.analytics && Array.isArray(analysis.analytics) ? analysis.analytics.length : 0;
        const analyticsLabel = analyticsCount > 0 ? `${analyticsCount} outil(s)` : 'Aucun outil détecté';
        
        const pagesSummary = analysis.pages_summary || {};
        const pagesList = Array.isArray(analysis.pages) ? analysis.pages : [];
        const perfScore = typeof analysis.performance_score === 'number'
            ? analysis.performance_score
            : (pagesSummary.performance_score !== undefined ? pagesSummary.performance_score : null);

        // Score global sécurité: priorité au calcul backend, sinon fallback local
        let securityScore = typeof analysis.security_score === 'number'
            ? analysis.security_score
            : (pagesSummary.security_score !== undefined ? pagesSummary.security_score : null);

        if (securityScore === null || securityScore === undefined) {
            securityScore = 0;
            if (analysis.ssl_valid) {
                securityScore += 40;
            }
            if (analysis.waf) {
                securityScore += 25;
            }
            if (analysis.cdn) {
                securityScore += 10;
            }
            if (analysis.security_headers && typeof analysis.security_headers === 'object' && !Array.isArray(analysis.security_headers)) {
                const headers = analysis.security_headers;
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

        let html = `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- En-tête avec informations générales -->
                <div class="detail-section" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 8px;">
                    <h3 style="margin: 0 0 1rem 0; color: white;"><i class="fas fa-chart-bar"></i> Informations générales</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; color: white;">
                        <div><strong><i class="fas fa-calendar"></i> Date:</strong> ${date}</div>
                        <div><strong><i class="fas fa-globe"></i> URL:</strong> <a href="${analysis.url}" target="_blank" style="color: #ffd700; text-decoration: underline;">${analysis.url}</a></div>
                        <div><strong><i class="fas fa-tag"></i> Domaine:</strong> ${analysis.domain || 'N/A'}</div>
                        <div><strong><i class="fas fa-hashtag"></i> IP:</strong> ${analysis.ip_address || 'N/A'}</div>
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
                                <div><strong>Score global:</strong> <span class="badge badge-${securityInfo.className}">${securityInfo.label}</span></div>
                            </div>
                        </div>
                        <div style="padding: 1rem; background: #f9fafb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Suivi & analytics</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>Outils d'analyse:</strong> ${escapeHtml(analyticsLabel)}</div>
                                ${analysis.performance_grade ? `<div><strong>Score performance:</strong> ${escapeHtml(String(analysis.performance_grade))}</div>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
                
                ${(() => {
                    const pagesCount = pagesSummary.pages_count || pagesSummary.pages_scanned || pagesList.length || 0;
                    if (!pagesCount) return '';
                    const pagesOk = pagesSummary.pages_ok || 0;
                    const pagesError = pagesSummary.pages_error || 0;
                    const trackersCount = pagesSummary.trackers_count || analysis.trackers_count || 0;
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
                            <h3 style="margin: 0 0 0.75rem 0; color: #1f2937;"><i class="fas fa-satellite"></i> Analyse multi-pages (${pagesCount} page${pagesCount > 1 ? 's' : ''})</h3>
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
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-server"></i> Serveur et infrastructure</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${analysis.server_software ? `<div class="info-row"><span class="info-label">Logiciel serveur:</span><span class="info-value"><span class="badge badge-info">${analysis.server_software}</span></span></div>` : ''}
                        ${analysis.framework ? `<div class="info-row"><span class="info-label">Framework:</span><span class="info-value"><span class="badge badge-primary">${analysis.framework}${analysis.framework_version ? ' ' + analysis.framework_version : ''}</span></span></div>` : ''}
                        ${analysis.cms ? `<div class="info-row"><span class="info-label">CMS:</span><span class="info-value"><span class="badge badge-success">${analysis.cms}${analysis.cms_version ? ' ' + analysis.cms_version : ''}</span></span></div>` : ''}
                        ${analysis.hosting_provider ? `<div class="info-row"><span class="info-label">Hébergeur:</span><span class="info-value">${analysis.hosting_provider}</span></div>` : ''}
                        ${analysis.cdn ? `<div class="info-row"><span class="info-label">CDN:</span><span class="info-value"><span class="badge badge-secondary">${analysis.cdn}</span></span></div>` : ''}
                        ${analysis.waf ? `<div class="info-row"><span class="info-label">WAF:</span><span class="info-value"><span class="badge badge-warning">${analysis.waf}</span></span></div>` : ''}
                    </div>
                </div>
                
                ${analysis.cms_plugins && Array.isArray(analysis.cms_plugins) && analysis.cms_plugins.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-plug"></i> Plugins CMS <span class="badge badge-info">${analysis.cms_plugins.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysis.cms_plugins.map(plugin => `<span class="badge badge-outline">${plugin}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                <!-- Domaine et DNS -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-globe-europe"></i> Domaine et DNS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${analysis.domain_creation_date ? `<div class="info-row"><span class="info-label">Date de création:</span><span class="info-value">${analysis.domain_creation_date}</span></div>` : ''}
                        ${analysis.domain_updated_date ? `<div class="info-row"><span class="info-label">Dernière mise à jour:</span><span class="info-value">${analysis.domain_updated_date}</span></div>` : ''}
                        ${analysis.domain_registrar ? `<div class="info-row"><span class="info-label">Registrar:</span><span class="info-value">${analysis.domain_registrar}</span></div>` : ''}
                    </div>
                </div>
                
                <!-- SSL/TLS -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-lock"></i> SSL/TLS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        <div class="info-row">
                            <span class="info-label">SSL valide:</span>
                            <span class="info-value">
                                <span class="badge ${analysis.ssl_valid ? 'badge-success' : 'badge-danger'}">${analysis.ssl_valid ? '<i class="fas fa-check"></i> Oui' : '<i class="fas fa-times"></i> Non'}</span>
                            </span>
                        </div>
                        ${analysis.ssl_expiry_date ? `<div class="info-row"><span class="info-label">Date d'expiration:</span><span class="info-value">${analysis.ssl_expiry_date}</span></div>` : ''}
                    </div>
                </div>
                
                ${analysis.security_headers && typeof analysis.security_headers === 'object' && !Array.isArray(analysis.security_headers) && Object.keys(analysis.security_headers).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-shield-alt"></i> En-têtes de sécurité</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem;">
                        ${Object.entries(analysis.security_headers).map(([key, value]) => {
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
                
                ${analysis.analytics && Array.isArray(analysis.analytics) && analysis.analytics.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-chart-line"></i> Outils d'analyse <span class="badge badge-info">${analysis.analytics.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysis.analytics.map(tool => {
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
                
                ${analysis.seo_meta && typeof analysis.seo_meta === 'object' && !Array.isArray(analysis.seo_meta) ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-search"></i> SEO et métadonnées</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: 1fr; gap: 1rem;">
                        ${analysis.seo_meta.meta_title ? `<div class="info-row"><span class="info-label">Titre:</span><span class="info-value">${analysis.seo_meta.meta_title}</span></div>` : ''}
                        ${analysis.seo_meta.meta_description ? `<div class="info-row"><span class="info-label">Description:</span><span class="info-value">${analysis.seo_meta.meta_description}</span></div>` : ''}
                        ${analysis.seo_meta.canonical_url ? `<div class="info-row"><span class="info-label">URL canonique:</span><span class="info-value"><a href="${analysis.seo_meta.canonical_url}" target="_blank" style="color: #667eea;">${analysis.seo_meta.canonical_url}</a></span></div>` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.performance_metrics && typeof analysis.performance_metrics === 'object' && !Array.isArray(analysis.performance_metrics) && Object.keys(analysis.performance_metrics).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-bolt"></i> Métriques de performance</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${Object.entries(analysis.performance_metrics).map(([key, value]) => 
                            `<div class="info-row"><span class="info-label">${key}:</span><span class="info-value"><strong>${value || 'N/A'}</strong></span></div>`
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.nmap_scan ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-search"></i> Scan Nmap</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les détails du scan</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.nmap_scan, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.technical_details ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-tools"></i> Détails techniques</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir tous les détails</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.technical_details, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
            </div>
        `;
        
        resultsContent.innerHTML = html;
        
        // Mettre a jour le score securite dans la fiche info si possible
        try {
            if (typeof securityScore !== 'undefined') {
                if (window.currentModalEntrepriseData) {
                    window.currentModalEntrepriseData.score_securite = securityScore;
                }
                const badge = document.getElementById('security-score-badge');
                if (badge) {
                    const info = getSecurityScoreInfo(securityScore);
                    badge.className = `badge badge-${info.className}`;
                    badge.textContent = info.label;
                }
            }
        } catch (e) {
            // Erreur silencieuse lors de la mise à jour du badge de score sécurité
        }
    }
    
    function displayOSINTAnalysis(analysis) {
        const resultsContent = document.getElementById('osint-results-content');
        if (!resultsContent) return;
        
        const date = new Date(analysis.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        // Utiliser les données normalisées de la BDD
        const subdomains = analysis.subdomains || [];
        const emails = analysis.emails || analysis.emails_found || [];
        const socialMedia = analysis.social_media || {};
        const technologies = analysis.technologies_detected || analysis.technologies || {};
        const dnsRecords = analysis.dns_records || {};
        const whoisInfo = analysis.whois_data || analysis.whois_info || {};
        
        // Compter les éléments
        const emailCount = Array.isArray(emails) ? emails.length : 0;
        const socialCount = Object.keys(socialMedia).reduce((sum, platform) => {
            const urls = Array.isArray(socialMedia[platform]) ? socialMedia[platform] : [];
            return sum + urls.length;
        }, 0);
        const techCount = Object.keys(technologies).reduce((sum, category) => {
            const techs = Array.isArray(technologies[category]) ? technologies[category] : [];
            return sum + techs.length;
        }, 0);
        
        // Fonction helper pour créer une carte de statistique
        const createStatCard = (icon, label, value, color = '#9333ea') => `
            <div style="background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <div style="width: 40px; height: 40px; border-radius: 8px; background: ${color}15; display: flex; align-items: center; justify-content: center; font-size: 1.25rem;">
                        ${icon}
                    </div>
                    <div>
                        <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 0.25rem;">${label}</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #111827;">${value}</div>
                    </div>
                </div>
            </div>
        `;
        
        let html = `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- En-tête avec statistiques -->
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(103, 116, 222, 0.35);">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1.5rem;">
                        <div>
                            <h3 style="margin: 0 0 0.5rem 0; color: white; font-size: 1.5rem; font-weight: 700;">Analyse OSINT</h3>
                            <div style="font-size: 0.9rem; opacity: 0.9;">${date}</div>
                    </div>
                        <div style="background: rgba(255,255,255,0.2); padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem;">
                            ${analysis.domain || 'N/A'}
                </div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem;">
                        ${createStatCard('<i class="fas fa-globe"></i>', 'Sous-domaines', subdomains.length, '#9333ea')}
                        ${createStatCard('<i class="fas fa-envelope"></i>', 'Emails', emailCount, '#3b82f6')}
                        ${createStatCard('<i class="fas fa-users"></i>', 'Réseaux sociaux', socialCount, '#10b981')}
                        ${createStatCard('<i class="fas fa-cog"></i>', 'Technologies', techCount, '#f59e0b')}
                </div>
                    ${analysis.url ? `
                        <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.2);">
                            <a href="${analysis.url}" target="_blank" style="color: white; text-decoration: none; font-weight: 500; display: inline-flex; align-items: center; gap: 0.5rem;">
                                <i class="fas fa-globe"></i>
                                <span>${analysis.url}</span>
                                <i class="fas fa-external-link-alt" style="font-size: 0.75rem;"></i>
                            </a>
                </div>
                ` : ''}
                </div>
                
                ${subdomains.length > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-globe"></i>
                        <span>Sous-domaines</span>
                        <span style="background: #e9d5ff; color: #6b21a8; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">${subdomains.length}</span>
                    </h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${subdomains.map(sub => `
                            <div style="background: #f3f4f6; padding: 0.5rem 0.75rem; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.9rem; color: #374151; border: 1px solid #e5e7eb;">
                                ${escapeHtml(sub)}
                    </div>
                        `).join('')}
                </div>
                </div>
                ` : ''}
                
                ${emailCount > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <span>📧</span>
                        <span>Emails trouvés</span>
                        <span style="background: #dbeafe; color: #1e40af; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">${emailCount}</span>
                    </h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${emails.map(emailData => {
                            const email = typeof emailData === 'string' ? emailData : (emailData.email || emailData.value || '');
                            const source = typeof emailData === 'object' && emailData.source ? emailData.source : null;
                            return `
                                <a href="mailto:${email}" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 0.5rem 0.75rem; border-radius: 6px; text-decoration: none; font-size: 0.9rem; display: inline-flex; align-items: center; gap: 0.5rem; box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3); transition: transform 0.2s;">
                                    <span>✉️</span>
                                    <span>${escapeHtml(email)}</span>
                                    ${source ? `<span style="font-size: 0.75rem; opacity: 0.8;">(${escapeHtml(source)})</span>` : ''}
                                </a>
                            `;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${socialCount > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-users"></i>
                        <span>Réseaux sociaux</span>
                        <span style="background: #d1fae5; color: #065f46; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">${socialCount}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${Object.entries(socialMedia).map(([platform, urls]) => {
                            const urlList = Array.isArray(urls) ? urls : [urls];
                            return `
                                <div>
                                    <div style="font-weight: 600; color: #374151; margin-bottom: 0.5rem; text-transform: capitalize;">${escapeHtml(platform)}</div>
                                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                        ${urlList.map(url => `
                                            <a href="${url}" target="_blank" style="background: #f3f4f6; padding: 0.5rem 0.75rem; border-radius: 6px; text-decoration: none; color: #2563eb; font-size: 0.9rem; border: 1px solid #e5e7eb; display: inline-flex; align-items: center; gap: 0.5rem; transition: background 0.2s;" onmouseover="this.style.background='#e5e7eb'" onmouseout="this.style.background='#f3f4f6'">
                                                <i class="fas fa-link"></i>
                                                <span>${escapeHtml(url)}</span>
                                                <i class="fas fa-external-link-alt" style="font-size: 0.75rem;"></i>
                                            </a>
                                        `).join('')}
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${techCount > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <span>⚙️</span>
                        <span>Technologies détectées</span>
                        <span style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">${techCount}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 1rem;">
                        ${Object.entries(technologies)
                            .filter(([category]) => {
                                // Filtrer les clés indésirables
                                const lowerCategory = category.toLowerCase();
                                return !lowerCategory.includes('raw_output') && 
                                       !lowerCategory.includes('error') && 
                                       !lowerCategory.includes('non disponible') &&
                                       category !== 'raw_output' &&
                                       category !== 'error';
                            })
                            .map(([category, techs]) => {
                            const techList = Array.isArray(techs) ? techs : [techs];
                                // Filtrer aussi les valeurs vides ou d'erreur
                                const validTechs = techList.filter(tech => {
                                    if (!tech) return false;
                                    const techStr = String(tech).toLowerCase();
                                    return !techStr.includes('non disponible') && 
                                           !techStr.includes('error') &&
                                           techStr.trim().length > 0;
                                });
                                
                                if (validTechs.length === 0) return '';
                                
                            return `
                                <div>
                                        <div style="font-weight: 600; color: #374151; margin-bottom: 0.5rem; text-transform: capitalize; font-size: 0.95rem;">
                                            ${escapeHtml(category.replace(/_/g, ' '))}
                                        </div>
                                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                            ${validTechs.map(tech => `
                                                <div style="background: #fef3c7; padding: 0.5rem 0.75rem; border-radius: 6px; font-size: 0.9rem; color: #92400e; border: 1px solid #fde68a; font-weight: 500;">
                                                    ${escapeHtml(String(tech))}
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                            `;
                            })
                            .filter(html => html !== '')
                            .join('')}
                    </div>
                </div>
                ` : ''}
                
                ${Object.keys(dnsRecords).length > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-satellite-dish"></i>
                        <span>Enregistrements DNS</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${Object.entries(dnsRecords).map(([type, records]) => {
                            const recordList = Array.isArray(records) ? records : [records];
                            return `
                                <div>
                                    <div style="font-weight: 600; color: #374151; margin-bottom: 0.5rem; font-family: 'Courier New', monospace;">${escapeHtml(type)}</div>
                                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                        ${recordList.map(record => `
                                            <div style="background: #f3f4f6; padding: 0.5rem 0.75rem; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; color: #374151; border: 1px solid #e5e7eb;">
                                                ${escapeHtml(String(record))}
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${Object.keys(whoisInfo).length > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-clipboard"></i>
                        <span>Informations WHOIS</span>
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${Object.entries(whoisInfo).filter(([key, value]) => value && typeof value !== 'object').map(([key, value]) => `
                            <div>
                                <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 0.25rem; text-transform: capitalize;">${escapeHtml(key.replace(/_/g, ' '))}</div>
                                <div style="font-weight: 500; color: #111827;">${escapeHtml(String(value))}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${(!subdomains.length && !emailCount && !socialCount && !techCount && !Object.keys(dnsRecords).length && !Object.keys(whoisInfo).length) ? `
                <div style="text-align: center; padding: 3rem; color: #6b7280;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;"><i class="fas fa-search"></i></div>
                    <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">Aucune donnée OSINT disponible</div>
                    <div style="font-size: 0.9rem;">Lancez une analyse OSINT pour collecter des informations.</div>
                </div>
                ` : ''}
            </div>
        `;
        
        resultsContent.innerHTML = html;
    }
    
    function displayPentestAnalysis(analysis) {
        const resultsContent = document.getElementById('pentest-results-content');
        if (!resultsContent) return;
        
        const date = new Date(analysis.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const riskScore = analysis.risk_score || 0;
        const riskColor = riskScore >= 70 ? '#e74c3c' : riskScore >= 40 ? '#f39c12' : '#27ae60';
        const riskLabel = riskScore >= 70 ? 'Élevé' : riskScore >= 40 ? 'Moyen' : 'Faible';
        
        // Extraire forms_checks et résultats des outils depuis pentest_details
        let forms_checks = [];
        let ffuf_results = null;
        let gobuster_results = null;
        let dirsearch_results = null;
        let masscan_results = null;
        let nmap_results = null;
        
        if (analysis.pentest_details && typeof analysis.pentest_details === 'object') {
            if (Array.isArray(analysis.pentest_details.forms_checks)) {
                forms_checks = analysis.pentest_details.forms_checks;
            } else if (analysis.pentest_details.forms_checks) {
                forms_checks = [analysis.pentest_details.forms_checks];
            }
            
            // Extraire les résultats des outils de scan
            ffuf_results = analysis.pentest_details.ffuf || null;
            gobuster_results = analysis.pentest_details.gobuster || null;
            dirsearch_results = analysis.pentest_details.dirsearch || null;
            masscan_results = analysis.pentest_details.masscan || null;
            nmap_results = analysis.pentest_details.nmap || null;
        }
        
        // Fonction helper pour obtenir la couleur de sévérité
        function getSeverityColor(severity) {
            if (!severity) return '#6b7280';
            const s = severity.toLowerCase();
            if (s.includes('crit') || s.includes('high')) return '#e74c3c';
            if (s.includes('medium') || s.includes('moyen')) return '#f39c12';
            if (s.includes('low') || s.includes('faible')) return '#3498db';
            return '#6b7280';
        }
        
        // Fonction helper pour formater les vulnérabilités normalisées
        function formatVulnerability(vuln) {
            if (typeof vuln === 'string') {
                return `<div style="padding: 0.75rem; background: #fee; border-left: 3px solid #e74c3c; border-radius: 6px; margin-bottom: 0.5rem;">
                    <strong style="color: #c33;"><i class="fas fa-exclamation-triangle"></i></strong> ${escapeHtml(vuln)}
                </div>`;
            }
            const name = vuln.name || vuln.title || 'Vulnérabilité inconnue';
            const severity = vuln.severity || 'Non spécifiée';
            const description = vuln.description || '';
            const recommendation = vuln.recommendation || vuln.fix || '';
            const severityColor = getSeverityColor(severity);
            
            return `<div style="padding: 1rem; background: #fff; border-left: 4px solid ${severityColor}; border-radius: 8px; margin-bottom: 0.75rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                    <strong style="color: #2c3e50; font-size: 1rem;">${escapeHtml(name)}</strong>
                    <span style="background: ${severityColor}; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">${escapeHtml(severity)}</span>
                </div>
                ${description ? `<div style="color: #555; margin-bottom: 0.5rem; line-height: 1.5;">${escapeHtml(description)}</div>` : ''}
                ${recommendation ? `<div style="background: #f0f9ff; padding: 0.75rem; border-radius: 6px; border-left: 3px solid #3498db; margin-top: 0.5rem;">
                    <strong style="color: #1e40af; font-size: 0.85rem;"><i class="fas fa-lightbulb"></i> Recommandation:</strong>
                    <div style="color: #1e3a8a; margin-top: 0.25rem;">${escapeHtml(recommendation)}</div>
                </div>` : ''}
            </div>`;
        }
        
        let html = `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- En-tête avec score de risque -->
                <div class="detail-section" style="background: linear-gradient(135deg, #dc2626 0%, #f59e0b 100%); color: white; padding: 1.75rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
                        <div>
                            <h3 style="margin: 0 0 0.5rem 0; color: white; font-size: 1.5rem;"><i class="fas fa-shield-alt"></i> Analyse de sécurité</h3>
                            <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 0.95rem; opacity: 0.95;">
                                <div><strong><i class="fas fa-calendar"></i></strong> ${date}</div>
                                <div><strong><i class="fas fa-globe"></i></strong> <a href="${escapeHtml(analysis.url)}" target="_blank" style="color: #ffd700; text-decoration: underline;">${escapeHtml(analysis.url)}</a></div>
                                <div><strong><i class="fas fa-tag"></i></strong> ${escapeHtml(analysis.domain || 'N/A')}</div>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.85rem; opacity: 0.9; margin-bottom: 0.5rem;">Score de risque</div>
                            <div style="background: ${riskColor}; padding: 0.5rem 1.25rem; border-radius: 20px; font-weight: bold; font-size: 1.25rem; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
                                ${riskScore}/100
                            </div>
                            <div style="font-size: 0.85rem; margin-top: 0.25rem; opacity: 0.9;">${riskLabel}</div>
                        </div>
                    </div>
                </div>
                
                ${analysis.vulnerabilities && Array.isArray(analysis.vulnerabilities) && analysis.vulnerabilities.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #e74c3c; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-exclamation-circle" style="font-size: 1.5rem;"></i>
                        Vulnérabilités détectées
                        <span style="background: #fee; color: #c33; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${analysis.vulnerabilities.length}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        ${analysis.vulnerabilities.map(vuln => formatVulnerability(vuln)).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.security_headers && Object.keys(analysis.security_headers).length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #3498db; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-shield-alt" style="font-size: 1.5rem;"></i>
                        En-têtes de sécurité
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.75rem;">
                        ${Object.entries(analysis.security_headers).map(([header, data]) => {
                            const status = data.status || (typeof data === 'string' ? data : 'present');
                            const isPresent = status === 'present' || status === 'ok' || status === 'true';
                            const statusColor = isPresent ? '#10b981' : '#ef4444';
                            const statusText = isPresent ? '<i class="fas fa-check"></i> Présent' : '<i class="fas fa-times"></i> Absent';
                            return `<div style="padding: 0.75rem; background: ${isPresent ? '#f0fdf4' : '#fef2f2'}; border-left: 3px solid ${statusColor}; border-radius: 6px;">
                                <div style="font-weight: 600; color: #1f2937; margin-bottom: 0.25rem;">${escapeHtml(header)}</div>
                                <div style="color: ${statusColor}; font-size: 0.85rem; font-weight: 600;">${statusText}</div>
                            </div>`;
                        }).join('')}
                    </div>
                </div>
                ` : analysis.security_headers_analysis && Object.keys(analysis.security_headers_analysis).length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #3498db; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-shield-alt" style="font-size: 1.5rem;"></i>
                        En-têtes de sécurité
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.75rem;">
                        ${Object.entries(analysis.security_headers_analysis).map(([header, data]) => {
                            const status = data.status || (typeof data === 'string' ? data : 'present');
                            const isPresent = status === 'present' || status === 'ok' || status === 'true';
                            const statusColor = isPresent ? '#10b981' : '#ef4444';
                            const statusText = isPresent ? '<i class="fas fa-check"></i> Présent' : '<i class="fas fa-times"></i> Absent';
                            return `<div style="padding: 0.75rem; background: ${isPresent ? '#f0fdf4' : '#fef2f2'}; border-left: 3px solid ${statusColor}; border-radius: 6px;">
                                <div style="font-weight: 600; color: #1f2937; margin-bottom: 0.25rem;">${escapeHtml(header)}</div>
                                <div style="color: ${statusColor}; font-size: 0.85rem; font-weight: 600;">${statusText}</div>
                            </div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.cms_vulnerabilities && Object.keys(analysis.cms_vulnerabilities).length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #e74c3c; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-exclamation-triangle" style="font-size: 1.5rem;"></i>
                        Vulnérabilités CMS
                        <span style="background: #fee; color: #c33; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${Object.keys(analysis.cms_vulnerabilities).length}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${Object.entries(analysis.cms_vulnerabilities).map(([name, vuln]) => {
                            const severity = (typeof vuln === 'object' && vuln.severity) ? vuln.severity : 'Non spécifiée';
                            const description = (typeof vuln === 'object' && vuln.description) ? vuln.description : (typeof vuln === 'string' ? vuln : '');
                            const severityColor = getSeverityColor(severity);
                            return `<div style="padding: 1rem; background: #fff; border-left: 4px solid ${severityColor}; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                                    <strong style="color: #2c3e50;">${escapeHtml(name)}</strong>
                                    <span style="background: ${severityColor}; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">${escapeHtml(severity)}</span>
                                </div>
                                ${description ? `<div style="color: #555; line-height: 1.5;">${escapeHtml(description)}</div>` : ''}
                            </div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.open_ports && Array.isArray(analysis.open_ports) && analysis.open_ports.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #8b5cf6; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-globe" style="font-size: 1.5rem;"></i>
                        Ports ouverts
                        <span style="background: #f3e8ff; color: #6b21a8; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${analysis.open_ports.length}</span>
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem;">
                        ${analysis.open_ports.map(port => {
                            const portNum = port.port || port;
                            const service = port.service || 'Inconnu';
                            return `<div style="padding: 0.75rem; background: #f9fafb; border-left: 3px solid #8b5cf6; border-radius: 6px;">
                                <div style="font-weight: 600; color: #1f2937;">Port ${portNum}</div>
                                <div style="color: #6b7280; font-size: 0.85rem; margin-top: 0.25rem;">${escapeHtml(service)}</div>
                            </div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${forms_checks.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #10b981; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">📝</span>
                        Formulaires testés
                        <span style="background: #f0fdf4; color: #059669; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${forms_checks.length}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${forms_checks.map((form, idx) => {
                            const hasError = form.error;
                            const isOk = form.ok === true || form.status_code === 200;
                            const statusColor = hasError ? '#ef4444' : (isOk ? '#10b981' : '#f59e0b');
                            const statusText = hasError ? '<i class="fas fa-times"></i> Erreur' : (isOk ? '<i class="fas fa-check"></i> Accessible' : `<i class="fas fa-exclamation-triangle"></i> ${form.status_code || 'Inconnu'}`);
                            return `<div style="padding: 1rem; background: ${hasError ? '#fef2f2' : (isOk ? '#f0fdf4' : '#fffbeb')}; border-left: 4px solid ${statusColor}; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; flex-wrap: wrap;">
                                    <strong style="color: #1f2937;">Formulaire #${idx + 1}</strong>
                                    <span style="background: ${statusColor}; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">${statusText}</span>
                                    <span style="background: #e5e7eb; color: #4b5563; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">${escapeHtml(form.method || 'GET')}</span>
                                </div>
                                <div style="color: #6b7280; font-size: 0.9rem; word-break: break-all;">
                                    <strong>Action:</strong> ${escapeHtml(form.action || 'N/A')}
                                </div>
                                ${form.status_code ? `<div style="color: #6b7280; font-size: 0.9rem; margin-top: 0.25rem;">
                                    <strong>Code HTTP:</strong> ${form.status_code}
                                </div>` : ''}
                                ${form.error ? `<div style="color: #dc2626; font-size: 0.85rem; margin-top: 0.5rem; padding: 0.5rem; background: #fee; border-radius: 4px;">
                                    <strong>Erreur:</strong> ${escapeHtml(form.error)}
                                </div>` : ''}
                            </div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.sql_injection ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #e74c3c; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">💉</span>
                        Injection SQL
                    </h3>
                    <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; overflow-x: auto;">
                        <pre style="margin: 0; font-size: 0.85rem; line-height: 1.6; color: #374151;">${escapeHtml(JSON.stringify(analysis.sql_injection, null, 2))}</pre>
                    </div>
                </div>
                ` : ''}
                
                ${analysis.xss_vulnerabilities && Array.isArray(analysis.xss_vulnerabilities) && analysis.xss_vulnerabilities.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #f39c12; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">🔓</span>
                        Vulnérabilités XSS
                        <span style="background: #fff3cd; color: #856404; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${analysis.xss_vulnerabilities.length}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.xss_vulnerabilities.map(xss => `<div style="padding: 0.75rem; background: #fff3cd; border-left: 3px solid #f39c12; border-radius: 6px; color: #856404;">${escapeHtml(typeof xss === 'string' ? xss : JSON.stringify(xss))}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.csrf_vulnerabilities && Array.isArray(analysis.csrf_vulnerabilities) && analysis.csrf_vulnerabilities.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #f39c12; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">🔄</span>
                        Vulnérabilités CSRF
                        <span style="background: #fff3cd; color: #856404; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${analysis.csrf_vulnerabilities.length}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.csrf_vulnerabilities.map(csrf => `<div style="padding: 0.75rem; background: #fff3cd; border-left: 3px solid #f39c12; border-radius: 6px; color: #856404;">${escapeHtml(typeof csrf === 'string' ? csrf : JSON.stringify(csrf))}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.authentication_issues && Array.isArray(analysis.authentication_issues) && analysis.authentication_issues.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #3498db; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-key" style="font-size: 1.5rem;"></i>
                        Problèmes d'authentification
                        <span style="background: #dbeafe; color: #1e40af; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${analysis.authentication_issues.length}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.authentication_issues.map(issue => `<div style="padding: 0.75rem; background: #dbeafe; border-left: 3px solid #3498db; border-radius: 6px; color: #1e40af;">${escapeHtml(typeof issue === 'string' ? issue : JSON.stringify(issue))}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.authorization_issues && Array.isArray(analysis.authorization_issues) && analysis.authorization_issues.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #3498db; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">👤</span>
                        Problèmes d'autorisation
                        <span style="background: #dbeafe; color: #1e40af; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${analysis.authorization_issues.length}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.authorization_issues.map(issue => `<div style="padding: 0.75rem; background: #dbeafe; border-left: 3px solid #3498db; border-radius: 6px; color: #1e40af;">${escapeHtml(typeof issue === 'string' ? issue : JSON.stringify(issue))}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.sensitive_data_exposure && Array.isArray(analysis.sensitive_data_exposure) && analysis.sensitive_data_exposure.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #e74c3c; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-lock" style="font-size: 1.5rem;"></i>
                        Exposition de données sensibles
                        <span style="background: #fee; color: #c33; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${analysis.sensitive_data_exposure.length}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.sensitive_data_exposure.map(data => `<div style="padding: 0.75rem; background: #fee; border-left: 3px solid #e74c3c; border-radius: 6px; color: #c33;"><strong>⚠️</strong> ${escapeHtml(typeof data === 'string' ? data : JSON.stringify(data))}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.ssl_tls_analysis ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #10b981; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">🔒</span>
                        Analyse SSL/TLS
                    </h3>
                    <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; overflow-x: auto;">
                        <pre style="margin: 0; font-size: 0.85rem; line-height: 1.6; color: #374151;">${escapeHtml(JSON.stringify(analysis.ssl_tls_analysis, null, 2))}</pre>
                    </div>
                </div>
                ` : ''}
                
                ${analysis.waf_detection ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #8b5cf6; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">🚧</span>
                        Détection WAF
                    </h3>
                    <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; overflow-x: auto;">
                        <pre style="margin: 0; font-size: 0.85rem; line-height: 1.6; color: #374151;">${escapeHtml(JSON.stringify(analysis.waf_detection, null, 2))}</pre>
                    </div>
                </div>
                ` : ''}
                
                ${analysis.api_security ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #06b6d4; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-plug" style="font-size: 1.5rem;"></i>
                        Sécurité API
                    </h3>
                    <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; overflow-x: auto;">
                        <pre style="margin: 0; font-size: 0.85rem; line-height: 1.6; color: #374151;">${escapeHtml(JSON.stringify(analysis.api_security, null, 2))}</pre>
                    </div>
                </div>
                ` : ''}
                
                ${analysis.network_scan && typeof analysis.network_scan === 'object' && Object.keys(analysis.network_scan).length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #6366f1; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-globe" style="font-size: 1.5rem;"></i>
                        Scan réseau
                    </h3>
                    <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; overflow-x: auto;">
                        <pre style="margin: 0; font-size: 0.85rem; line-height: 1.6; color: #374151;">${escapeHtml(JSON.stringify(analysis.network_scan, null, 2))}</pre>
                    </div>
                </div>
                ` : ''}
                
                ${ffuf_results && !ffuf_results.error ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-search" style="font-size: 1.5rem;"></i>
                        Scan FFUF (Directory Bruteforce)
                        ${ffuf_results.vulnerabilities && ffuf_results.vulnerabilities.length > 0 ? `
                        <span style="background: #dbeafe; color: #1e40af; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${ffuf_results.vulnerabilities.length} ressources</span>
                        ` : ''}
                    </h3>
                    ${ffuf_results.vulnerabilities && ffuf_results.vulnerabilities.length > 0 ? `
                    <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 300px; overflow-y: auto;">
                        ${ffuf_results.vulnerabilities.slice(0, 50).map(v => `
                            <div style="padding: 0.5rem; background: #eff6ff; border-left: 3px solid #3b82f6; border-radius: 4px; font-size: 0.9rem;">
                                ${escapeHtml(v.description || JSON.stringify(v))}
                            </div>
                        `).join('')}
                    </div>
                    ` : '<div style="color: #6b7280; font-style: italic;">Aucune ressource trouvée</div>'}
                </div>
                ` : ''}
                
                ${gobuster_results && !gobuster_results.error ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #8b5cf6; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">🔍</span>
                        Scan Gobuster (Directory Bruteforce)
                        ${gobuster_results.vulnerabilities && gobuster_results.vulnerabilities.length > 0 ? `
                        <span style="background: #f3e8ff; color: #6b21a8; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${gobuster_results.vulnerabilities.length} ressources</span>
                        ` : ''}
                    </h3>
                    ${gobuster_results.vulnerabilities && gobuster_results.vulnerabilities.length > 0 ? `
                    <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 300px; overflow-y: auto;">
                        ${gobuster_results.vulnerabilities.slice(0, 50).map(v => `
                            <div style="padding: 0.5rem; background: #faf5ff; border-left: 3px solid #8b5cf6; border-radius: 4px; font-size: 0.9rem;">
                                ${escapeHtml(v.description || JSON.stringify(v))}
                            </div>
                        `).join('')}
                    </div>
                    ` : '<div style="color: #6b7280; font-style: italic;">Aucune ressource trouvée</div>'}
                </div>
                ` : ''}
                
                ${dirsearch_results && !dirsearch_results.error ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #ec4899; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">🔍</span>
                        Scan Dirsearch (Directory Bruteforce)
                        ${dirsearch_results.vulnerabilities && dirsearch_results.vulnerabilities.length > 0 ? `
                        <span style="background: #fce7f3; color: #9f1239; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${dirsearch_results.vulnerabilities.length} ressources</span>
                        ` : ''}
                    </h3>
                    ${dirsearch_results.vulnerabilities && dirsearch_results.vulnerabilities.length > 0 ? `
                    <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 300px; overflow-y: auto;">
                        ${dirsearch_results.vulnerabilities.slice(0, 50).map(v => `
                            <div style="padding: 0.5rem; background: #fdf2f8; border-left: 3px solid #ec4899; border-radius: 4px; font-size: 0.9rem;">
                                ${escapeHtml(v.description || JSON.stringify(v))}
                            </div>
                        `).join('')}
                    </div>
                    ` : '<div style="color: #6b7280; font-style: italic;">Aucune ressource trouvée</div>'}
                </div>
                ` : ''}
                
                ${masscan_results && !masscan_results.error && masscan_results.open_ports && masscan_results.open_ports.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #f59e0b; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <i class="fas fa-plug" style="font-size: 1.5rem;"></i>
                        Scan Masscan (Ports ouverts)
                        <span style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${masscan_results.open_ports.length} ports</span>
                    </h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${masscan_results.open_ports.map(port => `
                            <div style="background: #fef3c7; padding: 0.5rem 0.75rem; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.9rem; color: #92400e; border: 1px solid #fde68a;">
                                ${port.port || port}${port.protocol ? `/${port.protocol}` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${nmap_results && nmap_results.services && nmap_results.services.length > 0 ? `
                <div class="detail-section" style="background: #fff; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #10b981; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <h3 style="margin: 0 0 1.25rem 0; color: #2c3e50; font-size: 1.2rem; display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">🔍</span>
                        Scan Nmap (Services détectés)
                        <span style="background: #d1fae5; color: #065f46; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 700;">${nmap_results.services.length} services</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        ${nmap_results.services.map(svc => `
                            <div style="padding: 0.75rem; background: #f0fdf4; border-left: 3px solid #10b981; border-radius: 6px;">
                                <div style="font-weight: 600; color: #065f46; margin-bottom: 0.25rem;">
                                    Port ${svc.port || 'N/A'} / ${svc.protocol || 'tcp'}
                                </div>
                                ${svc.service ? `<div style="color: #047857; font-size: 0.9rem;">Service: ${escapeHtml(svc.service)}</div>` : ''}
                                ${svc.version ? `<div style="color: #6b7280; font-size: 0.85rem; margin-top: 0.25rem;">Version: ${escapeHtml(svc.version)}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
        
        resultsContent.innerHTML = html;
    }
})();

