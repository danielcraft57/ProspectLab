/**
 * JavaScript pour la page de liste des entreprises
 * Gestion des filtres, recherche, tags et notes
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
                    <h3>${entreprise.nom || 'Sans nom'}</h3>
                    <button class="btn-favori ${entreprise.favori ? 'active' : ''}" data-id="${entreprise.id}" title="Favori">
                        ⭐
                    </button>
                    </div>
                </div>
                <div class="card-body">
                    ${resumePreview ? `<p class="resume-preview" style="color: #666; font-size: 0.9rem; margin-bottom: 0.75rem; font-style: italic;">${resumePreview}</p>` : ''}
                    ${entreprise.website ? `<p><strong>Site:</strong> <a href="${entreprise.website}" target="_blank">${entreprise.website}</a></p>` : ''}
                    ${entreprise.secteur ? `<p><strong>Secteur:</strong> ${entreprise.secteur}</p>` : ''}
                    ${entreprise.statut ? `<p><strong>Statut:</strong> <span class="badge badge-${getStatusClass(entreprise.statut)}">${entreprise.statut}</span></p>` : ''}
                    ${entreprise.email_principal ? `<p><strong>Email:</strong> ${entreprise.email_principal}</p>` : ''}
                    ${entreprise.responsable ? `<p><strong>Responsable:</strong> ${entreprise.responsable}</p>` : ''}
                    ${tagsHtml ? `<div class="tags-container">${tagsHtml}</div>` : ''}
                </div>
                <div class="card-footer">
                    <button class="btn btn-small btn-primary btn-view-details" data-id="${entreprise.id}">Voir détails</button>
                    <button class="btn btn-small btn-secondary btn-edit-tags" data-id="${entreprise.id}">Tags</button>
                    <button class="btn btn-small btn-danger btn-delete-entreprise" data-id="${entreprise.id}" data-name="${entreprise.nom || 'Sans nom'}" title="Supprimer">🗑️</button>
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
                        <h3>${entreprise.nom || 'Sans nom'}</h3>
                        ${tagsHtml ? `<div class="tags-container">${tagsHtml}</div>` : ''}
                    </div>
                    <div class="row-info">
                        ${entreprise.secteur ? `<span>${entreprise.secteur}</span>` : ''}
                        ${entreprise.statut ? `<span class="badge badge-${getStatusClass(entreprise.statut)}">${entreprise.statut}</span>` : ''}
                        ${entreprise.email_principal ? `<span>${entreprise.email_principal}</span>` : ''}
                    </div>
                </div>
                <div class="row-actions">
                    <button class="btn-favori ${entreprise.favori ? 'active' : ''}" data-id="${entreprise.id}" title="Favori">⭐</button>
                    <button class="btn btn-small btn-secondary btn-edit-tags" data-id="${entreprise.id}">Tags</button>
                    <button class="btn btn-small btn-primary btn-view-details" data-id="${entreprise.id}">Détails</button>
                    <button class="btn btn-small btn-danger btn-delete-entreprise" data-id="${entreprise.id}" data-name="${entreprise.nom || 'Sans nom'}" title="Supprimer">🗑️</button>
                </div>
            </div>
        `;
    }
    
    function getStatusClass(statut) {
        const classes = {
            'Prospect intéressant': 'success',
            'À contacter': 'warning',
            'En cours': 'info',
            'Clos': 'secondary'
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
                    <button class="tab-btn" data-tab="scraping">Résultats scraping</button>
                    <button class="tab-btn" data-tab="technique">Analyse technique</button>
                    <button class="tab-btn" data-tab="osint">Analyse OSINT</button>
                    <button class="tab-btn" data-tab="pentest">Analyse Pentest</button>
                    <button class="tab-btn" data-tab="notes">Note</button>
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
                            ${entreprise.og_data ? (() => {
                                try {
                                    const ogData = entreprise.og_data;
                                    if (ogData && (ogData.og_title || ogData.og_type || ogData.og_url || ogData.images?.length > 0)) {
                                        return `
                                            <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 8px;">
                                                <h3 style="color: white; margin: 0 0 1rem 0; font-size: 1.1rem;">Données OpenGraph</h3>
                                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; color: white;">
                                                    ${ogData.og_title ? `<div><strong>Titre:</strong> ${ogData.og_title}</div>` : ''}
                                                    ${ogData.og_type ? `<div><strong>Type:</strong> <span style="background: rgba(255,255,255,0.2); padding: 0.25rem 0.5rem; border-radius: 4px;">${ogData.og_type}</span></div>` : ''}
                                                    ${ogData.og_url ? `<div><strong>URL:</strong> <a href="${ogData.og_url}" target="_blank" style="color: #ffd700; text-decoration: underline;">${ogData.og_url}</a></div>` : ''}
                                                    ${ogData.og_site_name ? `<div><strong>Site:</strong> ${ogData.og_site_name}</div>` : ''}
                                                    ${ogData.og_description ? `<div style="grid-column: 1 / -1;"><strong>Description:</strong> ${ogData.og_description}</div>` : ''}
                                                    ${ogData.og_locale ? `<div><strong>Locale:</strong> ${ogData.og_locale}</div>` : ''}
                                                    ${ogData.locales_alternate && ogData.locales_alternate.length > 0 ? `<div><strong>Locales alternatives:</strong> ${ogData.locales_alternate.join(', ')}</div>` : ''}
                                                    ${ogData.images && ogData.images.length > 0 ? `
                                                        <div style="grid-column: 1 / -1;">
                                                            <strong>Images OpenGraph:</strong>
                                                            <div style="display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.5rem;">
                                                                ${ogData.images.map(img => `
                                                                    <div style="flex: 0 0 auto;">
                                                                        <img src="${img.image_url}" alt="${img.alt_text || 'OG Image'}" 
                                                                             style="max-width: 150px; max-height: 150px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);"
                                                                             onerror="this.style.display='none'">
                                                                        ${img.width && img.height ? `<div style="font-size: 0.8rem; opacity: 0.8; margin-top: 0.25rem;">${img.width}x${img.height}</div>` : ''}
                                                                    </div>
                                                                `).join('')}
                                                            </div>
                                                        </div>
                                                    ` : ''}
                                                    ${ogData.videos && ogData.videos.length > 0 ? `
                                                        <div style="grid-column: 1 / -1;">
                                                            <strong>Vidéos OpenGraph:</strong> ${ogData.videos.length} vidéo(s)
                                                        </div>
                                                    ` : ''}
                                                    ${ogData.audios && ogData.audios.length > 0 ? `
                                                        <div style="grid-column: 1 / -1;">
                                                            <strong>Audios OpenGraph:</strong> ${ogData.audios.length} audio(s)
                                                        </div>
                                                    ` : ''}
                                                </div>
                                            </div>
                                        `;
                                    }
                                } catch(e) {
                                    console.error('Erreur affichage og_data:', e);
                                }
                                return '';
                            })() : ''}
                        </div>
                        ` : ''}
                        ${entreprise.resume ? `
                        <div class="detail-section" style="margin-bottom: 1.5rem; background: #f8f9fa; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #667eea;">
                            <h3 style="margin: 0 0 0.75rem 0; color: #2c3e50; font-size: 1.1rem;">📝 Résumé de l'entreprise</h3>
                            <p style="margin: 0; color: #555; line-height: 1.6; font-size: 0.95rem;">${entreprise.resume}</p>
                        </div>
                        ` : ''}
                        <div class="info-grid">
                            ${createInfoRow('Nom', entreprise.nom)}
                            ${createInfoRow('Site web', entreprise.website, true)}
                            ${createInfoRow('Secteur', entreprise.secteur)}
                            ${createInfoRow('Statut', entreprise.statut, false, getStatusBadge(entreprise.statut))}
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
                                ${createInfoRow('Score sécurité', entreprise.score_securite)}
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
                    
                    <!-- Onglet Résultats scraping -->
                    <div class="tab-panel" id="tab-scraping">
                        <div class="scraping-actions">
                            <h3>Analyse du site web</h3>
                            <p style="color: #666; margin-bottom: 1rem;">Analyse complète du site web : emails, personnes, téléphones, réseaux sociaux, technologies et métadonnées</p>
                            <div class="scraping-buttons" style="display: flex; gap: 0.5rem; align-items: center;">
                                ${entreprise.website ? `
                                <button class="btn btn-primary btn-launch-scraping" data-id="${entreprise.id}" data-url="${entreprise.website}">
                                    🔍 Lancer l'analyse scraping
                                </button>
                                <button class="btn btn-danger btn-stop-scraping" data-id="${entreprise.id}" style="display: none;">
                                    ⏹️ Arrêter
                                </button>
                                ` : '<p class="warning-box">Aucun site web disponible pour lancer une analyse</p>'}
                            </div>
                            
                            <div id="scraping-status" class="scraping-status" style="margin-top: 1rem; display: none;"></div>
                            <div id="scraping-progress" class="scraping-progress" style="margin-top: 1rem; display: none;">
                                <div class="progress-bar-container" style="height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
                                    <div id="scraping-progress-bar" class="progress-bar" style="height: 100%; background: #3498db; width: 0%; transition: width 0.3s;"></div>
                                </div>
                                <p id="scraping-progress-text" style="margin-top: 0.5rem; font-size: 0.9rem; color: #666;"></p>
                            </div>
                        </div>
                        
                        <div id="scraping-results" class="scraping-results" style="margin-top: 2rem; display: block;">
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
                        <div class="analysis-actions">
                            <h3>Analyse technique</h3>
                            <p style="color: #666; margin-bottom: 1rem;">Analyse approfondie de l'infrastructure technique : serveurs, frameworks, CMS, sécurité, performance</p>
                            <div class="analysis-buttons" style="display: flex; gap: 0.5rem; align-items: center;">
                                ${entreprise.website ? `
                                <button class="btn btn-primary btn-launch-technique" data-id="${entreprise.id}" data-url="${entreprise.website}">
                                    🔍 Lancer l'analyse technique
                                </button>
                                <button class="btn btn-danger btn-stop-technique" data-id="${entreprise.id}" style="display: none;">
                                    ⏹️ Arrêter
                                </button>
                                ` : '<p class="warning-box">Aucun site web disponible pour lancer une analyse</p>'}
                            </div>
                            
                            <div id="technique-progress" class="analysis-progress" style="margin-top: 1rem; display: none;">
                                <div class="progress-bar-container" style="height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
                                    <div id="technique-progress-bar" class="progress-bar" style="height: 100%; background: #3498db; width: 0%; transition: width 0.3s;"></div>
                                </div>
                                <p id="technique-progress-text" style="margin-top: 0.5rem; font-size: 0.9rem; color: #666;"></p>
                            </div>
                            
                        </div>
                        
                        <div id="technique-results" class="analysis-results" style="margin-top: 2rem;">
                            <h3>Résultats de l'analyse technique</h3>
                            <div id="technique-results-content">Aucune analyse disponible</div>
                        </div>
                    </div>
                    
                    <!-- Onglet Analyse OSINT -->
                    <div class="tab-panel" id="tab-osint">
                        <div class="analysis-actions">
                            <h3>Analyse OSINT</h3>
                            <p style="color: #666; margin-bottom: 1rem;">Collecte d'informations publiques : sous-domaines, DNS, WHOIS, emails, réseaux sociaux, technologies</p>
                            <div class="analysis-buttons" style="display: flex; gap: 0.5rem; align-items: center;">
                                ${entreprise.website ? `
                                <button class="btn btn-primary btn-launch-osint" data-id="${entreprise.id}" data-url="${entreprise.website}">
                                    🔎 Lancer l'analyse OSINT
                                </button>
                                <button class="btn btn-danger btn-stop-osint" data-id="${entreprise.id}" style="display: none;">
                                    ⏹️ Arrêter
                                </button>
                                ` : '<p class="warning-box">Aucun site web disponible pour lancer une analyse</p>'}
                            </div>
                            
                            <div id="osint-progress" class="analysis-progress" style="margin-top: 1rem; display: none;">
                                <div class="progress-bar-container" style="height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
                                    <div id="osint-progress-bar" class="progress-bar" style="height: 100%; background: #3498db; width: 0%; transition: width 0.3s;"></div>
                                </div>
                                <p id="osint-progress-text" style="margin-top: 0.5rem; font-size: 0.9rem; color: #666;"></p>
                            </div>
                            
                        </div>
                        
                        <div id="osint-results" class="analysis-results" style="margin-top: 2rem;">
                            <h3>Résultats de l'analyse OSINT</h3>
                            <div id="osint-results-content">Aucune analyse disponible</div>
                        </div>
                    </div>
                    
                    <!-- Onglet Analyse Pentest -->
                    <div class="tab-panel" id="tab-pentest">
                        <div class="analysis-actions">
                            <h3>Analyse Pentest</h3>
                            <p style="color: #666; margin-bottom: 1rem;">Test de pénétration et analyse de sécurité : vulnérabilités, injection SQL, XSS, authentification, autorisation</p>
                            <div class="analysis-buttons" style="display: flex; gap: 0.5rem; align-items: center;">
                                ${entreprise.website ? `
                                <button class="btn btn-primary btn-launch-pentest" data-id="${entreprise.id}" data-url="${entreprise.website}">
                                    🛡️ Lancer l'analyse Pentest
                                </button>
                                <button class="btn btn-danger btn-stop-pentest" data-id="${entreprise.id}" style="display: none;">
                                    ⏹️ Arrêter
                                </button>
                                ` : '<p class="warning-box">Aucun site web disponible pour lancer une analyse</p>'}
                            </div>
                            
                            <div id="pentest-progress" class="analysis-progress" style="margin-top: 1rem; display: none;">
                                <div class="progress-bar-container" style="height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
                                    <div id="pentest-progress-bar" class="progress-bar" style="height: 100%; background: #3498db; width: 0%; transition: width 0.3s;"></div>
                                </div>
                                <p id="pentest-progress-text" style="margin-top: 0.5rem; font-size: 0.9rem; color: #666;"></p>
                            </div>
                            
                        </div>
                        
                        <div id="pentest-results" class="analysis-results" style="margin-top: 2rem;">
                            <h3>Résultats de l'analyse Pentest</h3>
                            <div id="pentest-results-content">Aucune analyse disponible</div>
                        </div>
                    </div>
                    
                    <!-- Onglet Notes & Tags -->
                    <div class="tab-panel" id="tab-notes">
                        <div class="notes-section">
                            <h3>Notes</h3>
                            <textarea id="modal-notes-textarea" class="notes-textarea" placeholder="Ajoutez vos notes sur cette entreprise...">${notes}</textarea>
                            <button id="modal-btn-save-notes" class="btn btn-primary">Enregistrer les notes</button>
                        </div>
                        
                        <div class="tags-section" style="margin-top: 2rem;">
                            <h3>Tags</h3>
                            <div id="modal-tags-container" class="tags-editable">
                                ${tags.map(tag => `<span class="tag editable" data-tag="${tag}">${tag} <button class="tag-remove">×</button></span>`).join('')}
                                <input type="text" id="modal-tag-input" placeholder="Ajouter un tag (Entrée pour valider)" class="tag-input">
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="modal-footer">
                <button class="btn btn-secondary" id="modal-close-footer-btn">Fermer</button>
                <button class="btn btn-outline ${entreprise.favori ? 'active' : ''}" id="modal-toggle-favori">
                    ${entreprise.favori ? '⭐ Favori' : '☆ Ajouter aux favoris'}
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
    
    function getStatusBadge(statut) {
        if (!statut) return '';
        const classes = {
            'Prospect intéressant': 'success',
            'À contacter': 'warning',
            'En cours': 'info',
            'Clos': 'secondary'
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
        
        // Tags
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
        
        // Suppression de tags
        document.querySelectorAll('#modal-tags-container .tag-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tag = e.target.closest('.tag').dataset.tag;
                removeModalTag(tag);
            });
        });
        
        // Notes
        const notesBtn = document.getElementById('modal-btn-save-notes');
        if (notesBtn) {
            notesBtn.addEventListener('click', () => {
                saveModalNotes();
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
                if (e.target.closest('.btn-stop-scraping')) {
                    if (window.wsManager && window.wsManager.socket) {
                        window.wsManager.socket.emit('stop_scraping');
                    }
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
        
        // Gestion des boutons d'analyse
        if (modalBody) {
            modalBody.addEventListener('click', async (e) => {
                if (e.target.closest('.btn-launch-technique')) {
                    const btn = e.target.closest('.btn-launch-technique');
                    const entrepriseId = btn.getAttribute('data-id');
                    const url = btn.getAttribute('data-url');
                    await launchTechnicalAnalysis(entrepriseId, url);
                }
                if (e.target.closest('.btn-stop-technique')) {
                    if (window.wsManager && window.wsManager.socket) {
                        window.wsManager.socket.emit('stop_technical_analysis', {
                            url: currentModalEntrepriseData?.website,
                            entreprise_id: currentModalEntrepriseId
                        });
                    }
                }
                if (e.target.closest('.btn-launch-osint')) {
                    const btn = e.target.closest('.btn-launch-osint');
                    const entrepriseId = btn.getAttribute('data-id');
                    const url = btn.getAttribute('data-url');
                    await launchOSINTAnalysis(entrepriseId, url);
                }
                if (e.target.closest('.btn-stop-osint')) {
                    if (window.wsManager && window.wsManager.socket) {
                        window.wsManager.socket.emit('stop_osint_analysis', { url: currentModalEntrepriseData?.website });
                    }
                }
                if (e.target.closest('.btn-launch-pentest')) {
                    const btn = e.target.closest('.btn-launch-pentest');
                    const entrepriseId = btn.getAttribute('data-id');
                    const url = btn.getAttribute('data-url');
                    await launchPentestAnalysis(entrepriseId, url);
                }
                if (e.target.closest('.btn-stop-pentest')) {
                    if (window.wsManager && window.wsManager.socket) {
                        window.wsManager.socket.emit('stop_pentest_analysis', { url: currentModalEntrepriseData?.website });
                    }
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
                resultsContent.innerHTML = '<p class="empty-state">Aucune analyse technique disponible. Lancez une analyse pour commencer.</p>';
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
                resultsContent.innerHTML = '<p class="empty-state">Aucune analyse OSINT disponible. Lancez une analyse pour commencer.</p>';
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
                displayPentestAnalysis(analysis);
            } else if (response.status === 404) {
                resultsContent.innerHTML = '<p class="empty-state">Aucune analyse Pentest disponible. Lancez une analyse pour commencer.</p>';
            } else {
                resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse Pentest</p>';
            }
        } catch (error) {
            console.error('Erreur lors du chargement de l\'analyse Pentest:', error);
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
                        favoriBtn.textContent = '⭐ Favori';
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
                        `<span class="tag editable" data-tag="${tag}">${tag} <button class="tag-remove">×</button></span>`
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
                    btn.textContent = '✓ Enregistré !';
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
        const btnStop = document.querySelector('.btn-stop-scraping');
        
        if (!window.wsManager || !window.wsManager.socket) {
            showNotification('WebSocket non connecté', 'error');
            return;
        }
        
        try {
            btn.disabled = true;
            btn.style.display = 'none';
            if (btnStop) {
                btnStop.style.display = 'inline-block';
            }
            if (statusDiv) {
                statusDiv.style.display = 'block';
                statusDiv.innerHTML = '<div class="status-info">Lancement de l\'analyse...</div>';
            }
            if (progressDiv) {
                progressDiv.style.display = 'block';
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
            
            socket.on('scraping_started', (data) => {
                if (statusDiv) {
                    statusDiv.innerHTML = '<div class="status-info">Analyse démarrée...</div>';
                }
                if (progressBar) progressBar.style.width = '0%';
                if (progressText) progressText.textContent = 'Initialisation...';
            });
            
            socket.on('scraping_progress', (data) => {
                if (progressBar) {
                    const percent = Math.min(90, (data.visited || 0) * 5);
                    progressBar.style.width = percent + '%';
                }
                if (progressText) {
                    progressText.textContent = `${data.visited || 0} page(s) analysée(s) - ${data.emails || 0} emails, ${data.people || 0} personnes`;
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
                // Cacher le bouton stop et réafficher le bouton start
                btn.style.display = 'inline-block';
                btn.disabled = false;
                if (btnStop) {
                    btnStop.style.display = 'none';
                }
                
                // Ne pas recharger depuis la base car on a déjà les données en temps réel
                // Les données sont déjà affichées via displayAllScrapingResults
            });
            
            socket.on('scraping_stopped', (data) => {
                if (statusDiv) {
                    statusDiv.innerHTML = '<div class="status-warning">Analyse arrêtée</div>';
                }
                if (progressBar) progressBar.style.width = '0%';
                if (progressText) progressText.textContent = 'Arrêté';
                
                // Cacher le bouton stop et réafficher le bouton start
                btn.style.display = 'inline-block';
                btn.disabled = false;
                if (btnStop) {
                    btnStop.style.display = 'none';
                }
            });
            
            socket.on('scraping_error', (data) => {
                if (statusDiv) {
                    statusDiv.innerHTML = `<div class="status-error">Erreur: ${data.error || 'Erreur inconnue'}</div>`;
                }
                
                // Cacher le bouton stop et réafficher le bouton start
                btn.style.display = 'inline-block';
                btn.disabled = false;
                if (btnStop) {
                    btnStop.style.display = 'none';
                }
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
                <h4>📧 Emails (${scrapingResultsData.emails.length})</h4>
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
                <h4>📞 Téléphones (${scrapingResultsData.phones.length})</h4>
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
                <h4>🔗 Réseaux sociaux (${socialCount})</h4>
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
        
        const existingEmail = Array.from(list.children).find(item => {
            const emailText = item.querySelector('.result-item-title')?.textContent;
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
            <div class="result-item-icon">📞</div>
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
            'facebook': '📘',
            'twitter': '🐦',
            'linkedin': '💼',
            'instagram': '📷',
            'youtube': '📺',
            'github': '💻'
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
                console.log('Tous les scrapers récupérés:', scrapers);
                console.log('Types de scrapers:', scrapers.map(s => s.scraper_type));
                
                // Prendre le scraper le plus récent de type "unified_scraper"
                const unifiedScrapers = scrapers.filter(s => s.scraper_type === 'unified_scraper').sort((a, b) => {
                    const dateA = new Date(a.date_modification || a.date_creation || 0);
                    const dateB = new Date(b.date_modification || b.date_creation || 0);
                    return dateB - dateA;
                });
                
                console.log('Scrapers unifiés trouvés:', unifiedScrapers.length);
                
                if (unifiedScrapers.length > 0) {
                    const latestScraper = unifiedScrapers[0];
                    console.log('Scraper trouvé:', latestScraper);
                    console.log('Emails:', latestScraper.emails);
                    console.log('People:', latestScraper.people);
                    console.log('Phones:', latestScraper.phones);
                    
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
                    
                    console.log('Data formatée:', data);
                    
                    // Afficher les résultats avec le même style que la page scraping
                    displayAllScrapingResults(data);
                    
                    // Charger les images depuis la table images (optimisation BDD) et les afficher dans l'onglet Images principal
                    loadEntrepriseImages(entrepriseId);
                } else {
                    console.log('Aucun scraper unifié trouvé');
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
        const btnStop = document.querySelector('.btn-stop-technique');
        const progressDiv = document.getElementById('technique-progress');
        const progressBar = document.getElementById('technique-progress-bar');
        const progressText = document.getElementById('technique-progress-text');
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
            socket.on('technical_analysis_progress', (data) => {
                if (progressBar) progressBar.style.width = `${data.progress || 0}%`;
                if (progressText) progressText.textContent = data.message || '';
            });
            
            socket.on('technical_analysis_complete', (data) => {
                if (progressBar) progressBar.style.width = '100%';
                if (progressText) progressText.textContent = 'Analyse terminée';
                
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
                
                // Recharger les résultats
                loadTechnicalAnalysis(entrepriseId);
            });
            
            socket.on('technical_analysis_stopped', (data) => {
                if (progressBar) progressBar.style.width = '0%';
                if (progressText) progressText.textContent = 'Arrêté';
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
            });
            
            socket.on('technical_analysis_error', (data) => {
                if (progressText) progressText.textContent = `Erreur: ${data.error || 'Erreur inconnue'}`;
                btn.style.display = 'inline-block';
                if (btnStop) btnStop.style.display = 'none';
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
            btn.style.display = 'inline-block';
            if (btnStop) btnStop.style.display = 'none';
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
        
        let html = `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- En-tête avec informations générales -->
                <div class="detail-section" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 8px;">
                    <h3 style="margin: 0 0 1rem 0; color: white;">📊 Informations générales</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; color: white;">
                        <div><strong>📅 Date:</strong> ${date}</div>
                        <div><strong>🌐 URL:</strong> <a href="${analysis.url}" target="_blank" style="color: #ffd700; text-decoration: underline;">${analysis.url}</a></div>
                        <div><strong>🏷️ Domaine:</strong> ${analysis.domain || 'N/A'}</div>
                        <div><strong>🔢 IP:</strong> ${analysis.ip_address || 'N/A'}</div>
                    </div>
                </div>
                
                <!-- Serveur et infrastructure -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🖥️ Serveur et infrastructure</h3>
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
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔌 Plugins CMS <span class="badge badge-info">${analysis.cms_plugins.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysis.cms_plugins.map(plugin => `<span class="badge badge-outline">${plugin}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                <!-- Domaine et DNS -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🌍 Domaine et DNS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${analysis.domain_creation_date ? `<div class="info-row"><span class="info-label">Date de création:</span><span class="info-value">${analysis.domain_creation_date}</span></div>` : ''}
                        ${analysis.domain_updated_date ? `<div class="info-row"><span class="info-label">Dernière mise à jour:</span><span class="info-value">${analysis.domain_updated_date}</span></div>` : ''}
                        ${analysis.domain_registrar ? `<div class="info-row"><span class="info-label">Registrar:</span><span class="info-value">${analysis.domain_registrar}</span></div>` : ''}
                    </div>
                </div>
                
                <!-- SSL/TLS -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔒 SSL/TLS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        <div class="info-row">
                            <span class="info-label">SSL valide:</span>
                            <span class="info-value">
                                <span class="badge ${analysis.ssl_valid ? 'badge-success' : 'badge-danger'}">${analysis.ssl_valid ? '✓ Oui' : '✗ Non'}</span>
                            </span>
                        </div>
                        ${analysis.ssl_expiry_date ? `<div class="info-row"><span class="info-label">Date d'expiration:</span><span class="info-value">${analysis.ssl_expiry_date}</span></div>` : ''}
                    </div>
                </div>
                
                ${analysis.security_headers && typeof analysis.security_headers === 'object' && !Array.isArray(analysis.security_headers) && Object.keys(analysis.security_headers).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🛡️ En-têtes de sécurité</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem;">
                        ${Object.entries(analysis.security_headers).map(([key, value]) => 
                            `<div class="info-row"><span class="info-label">${key}:</span><span class="info-value"><code style="background: #f5f5f5; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem;">${value || 'N/A'}</code></span></div>`
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.analytics && Array.isArray(analysis.analytics) && analysis.analytics.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">📈 Outils d'analyse <span class="badge badge-info">${analysis.analytics.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysis.analytics.map(tool => `<span class="badge badge-secondary">${tool}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.seo_meta && typeof analysis.seo_meta === 'object' && !Array.isArray(analysis.seo_meta) ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔍 SEO et métadonnées</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: 1fr; gap: 1rem;">
                        ${analysis.seo_meta.meta_title ? `<div class="info-row"><span class="info-label">Titre:</span><span class="info-value">${analysis.seo_meta.meta_title}</span></div>` : ''}
                        ${analysis.seo_meta.meta_description ? `<div class="info-row"><span class="info-label">Description:</span><span class="info-value">${analysis.seo_meta.meta_description}</span></div>` : ''}
                        ${analysis.seo_meta.canonical_url ? `<div class="info-row"><span class="info-label">URL canonique:</span><span class="info-value"><a href="${analysis.seo_meta.canonical_url}" target="_blank" style="color: #667eea;">${analysis.seo_meta.canonical_url}</a></span></div>` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.performance_metrics && typeof analysis.performance_metrics === 'object' && !Array.isArray(analysis.performance_metrics) && Object.keys(analysis.performance_metrics).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">⚡ Métriques de performance</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${Object.entries(analysis.performance_metrics).map(([key, value]) => 
                            `<div class="info-row"><span class="info-label">${key}:</span><span class="info-value"><strong>${value || 'N/A'}</strong></span></div>`
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.nmap_scan ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔍 Scan Nmap</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les détails du scan</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.nmap_scan, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.technical_details ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔧 Détails techniques</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir tous les détails</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.technical_details, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
            </div>
        `;
        
        resultsContent.innerHTML = html;
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
        
        let html = `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- En-tête -->
                <div class="detail-section" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 1.5rem; border-radius: 8px;">
                    <h3 style="margin: 0 0 1rem 0; color: white;">🔎 Informations générales</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; color: white;">
                        <div><strong>📅 Date:</strong> ${date}</div>
                        <div><strong>🌐 URL:</strong> <a href="${analysis.url}" target="_blank" style="color: #ffd700; text-decoration: underline;">${analysis.url}</a></div>
                        <div><strong>🏷️ Domaine:</strong> ${analysis.domain || 'N/A'}</div>
                    </div>
                </div>
                
                ${analysis.subdomains && Array.isArray(analysis.subdomains) && analysis.subdomains.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">🌐 Sous-domaines <span class="badge badge-info">${analysis.subdomains.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysis.subdomains.map(sub => `<span class="badge badge-outline" style="font-family: monospace;">${sub}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.dns_records ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">📡 Enregistrements DNS</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les enregistrements DNS</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.dns_records, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.whois_data || analysis.whois_info ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">📋 Informations WHOIS</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les informations WHOIS</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.whois_data || analysis.whois_info, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.emails_found && Array.isArray(analysis.emails_found) && analysis.emails_found.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">📧 Emails trouvés <span class="badge badge-info">${analysis.emails_found.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysis.emails_found.map(email => `<a href="mailto:${email}" class="badge badge-primary" style="text-decoration: none;">${email}</a>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.social_media ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">👥 Réseaux sociaux et personnes</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les détails</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.social_media, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.technologies_detected ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">⚙️ Technologies détectées</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les technologies</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.technologies_detected, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.ssl_info ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">🔒 Informations SSL</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les informations SSL</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.ssl_info, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.ip_info ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">🌍 Informations IP</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les informations IP</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.ip_info, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.shodan_data ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">🔍 Données Shodan</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les données Shodan</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.shodan_data, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.censys_data ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">🔎 Données Censys</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les données Censys</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.censys_data, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.osint_details ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #f5576c; padding-bottom: 0.5rem;">📊 Détails OSINT complets</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir tous les détails</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.osint_details, null, 2)}</pre>
                    </details>
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
        
        let html = `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- En-tête avec score de risque -->
                <div class="detail-section" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: white; padding: 1.5rem; border-radius: 8px;">
                    <h3 style="margin: 0 0 1rem 0; color: white;">🛡️ Informations générales</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; color: white;">
                        <div><strong>📅 Date:</strong> ${date}</div>
                        <div><strong>🌐 URL:</strong> <a href="${analysis.url}" target="_blank" style="color: #ffd700; text-decoration: underline;">${analysis.url}</a></div>
                        <div><strong>🏷️ Domaine:</strong> ${analysis.domain || 'N/A'}</div>
                        <div><strong>⚠️ Score de risque:</strong> <span style="background: ${riskColor}; padding: 0.25rem 0.75rem; border-radius: 12px; font-weight: bold; color: white;">${riskScore}/100 (${riskLabel})</span></div>
                    </div>
                </div>
                
                ${analysis.vulnerabilities && Array.isArray(analysis.vulnerabilities) && analysis.vulnerabilities.length > 0 ? `
                <div class="detail-section" style="border-left: 4px solid #e74c3c;">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🚨 Vulnérabilités <span class="badge badge-danger">${analysis.vulnerabilities.length}</span></h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.vulnerabilities.map(vuln => `<div style="padding: 0.75rem; background: #fee; border-left: 3px solid #e74c3c; border-radius: 4px;"><strong>⚠️</strong> ${vuln}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.sql_injection ? `
                <div class="detail-section" style="border-left: 4px solid #e74c3c;">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">💉 Injection SQL</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #fee; border-radius: 4px; margin-bottom: 0.5rem; color: #c33;">⚠️ Voir les détails d'injection SQL</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.sql_injection, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.xss_vulnerabilities && Array.isArray(analysis.xss_vulnerabilities) && analysis.xss_vulnerabilities.length > 0 ? `
                <div class="detail-section" style="border-left: 4px solid #f39c12;">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🔓 Vulnérabilités XSS <span class="badge badge-warning">${analysis.xss_vulnerabilities.length}</span></h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.xss_vulnerabilities.map(xss => `<div style="padding: 0.75rem; background: #fff3cd; border-left: 3px solid #f39c12; border-radius: 4px;">${xss}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.csrf_vulnerabilities && Array.isArray(analysis.csrf_vulnerabilities) && analysis.csrf_vulnerabilities.length > 0 ? `
                <div class="detail-section" style="border-left: 4px solid #f39c12;">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🔄 Vulnérabilités CSRF <span class="badge badge-warning">${analysis.csrf_vulnerabilities.length}</span></h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.csrf_vulnerabilities.map(csrf => `<div style="padding: 0.75rem; background: #fff3cd; border-left: 3px solid #f39c12; border-radius: 4px;">${csrf}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.authentication_issues && Array.isArray(analysis.authentication_issues) && analysis.authentication_issues.length > 0 ? `
                <div class="detail-section" style="border-left: 4px solid #3498db;">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🔐 Problèmes d'authentification <span class="badge badge-info">${analysis.authentication_issues.length}</span></h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.authentication_issues.map(issue => `<div style="padding: 0.75rem; background: #d1ecf1; border-left: 3px solid #3498db; border-radius: 4px;">${issue}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.authorization_issues && Array.isArray(analysis.authorization_issues) && analysis.authorization_issues.length > 0 ? `
                <div class="detail-section" style="border-left: 4px solid #3498db;">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">👤 Problèmes d'autorisation <span class="badge badge-info">${analysis.authorization_issues.length}</span></h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.authorization_issues.map(issue => `<div style="padding: 0.75rem; background: #d1ecf1; border-left: 3px solid #3498db; border-radius: 4px;">${issue}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.sensitive_data_exposure && Array.isArray(analysis.sensitive_data_exposure) && analysis.sensitive_data_exposure.length > 0 ? `
                <div class="detail-section" style="border-left: 4px solid #e74c3c;">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🔒 Exposition de données sensibles <span class="badge badge-danger">${analysis.sensitive_data_exposure.length}</span></h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${analysis.sensitive_data_exposure.map(data => `<div style="padding: 0.75rem; background: #fee; border-left: 3px solid #e74c3c; border-radius: 4px;"><strong>⚠️</strong> ${data}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.security_headers_analysis ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🛡️ Analyse des en-têtes de sécurité</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir l'analyse des en-têtes</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.security_headers_analysis, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.ssl_tls_analysis ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🔒 Analyse SSL/TLS</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir l'analyse SSL/TLS</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.ssl_tls_analysis, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.waf_detection ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🚧 Détection WAF</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir la détection WAF</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.waf_detection, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.cms_vulnerabilities ? `
                <div class="detail-section" style="border-left: 4px solid #e74c3c;">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">⚠️ Vulnérabilités CMS</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #fee; border-radius: 4px; margin-bottom: 0.5rem; color: #c33;">Voir les vulnérabilités CMS</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.cms_vulnerabilities, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.api_security ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🔌 Sécurité API</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir l'analyse de sécurité API</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.api_security, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.network_scan ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">🌐 Scan réseau</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir le scan réseau</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.network_scan, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.pentest_details ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #fa709a; padding-bottom: 0.5rem;">📊 Détails complets du Pentest</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir tous les détails</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${JSON.stringify(analysis.pentest_details, null, 2)}</pre>
                    </details>
                </div>
                ` : ''}
            </div>
        `;
        
        resultsContent.innerHTML = html;
    }
})();

