/**
 * JavaScript pour la page de liste des entreprises (Version modulaire)
 * Charge les modules nécessaires dans le bon ordre
 */

(function() {
    'use strict';
    
    // Attendre que les modules soient chargés
    async function init() {
        // Vérifier que les modules sont disponibles
        if (typeof window.Formatters === 'undefined' ||
            typeof window.Badges === 'undefined' ||
            typeof window.EntreprisesAPI === 'undefined' ||
            typeof window.Notifications === 'undefined' ||
            typeof window.debounce === 'undefined') {
            console.error('Modules non chargés. Vérifiez que les modules sont chargés avant ce script.');
            return;
        }
        
        // Utiliser les modules globaux
        const { Formatters, Badges, EntreprisesAPI, Notifications } = window;
        const debounceFn = window.debounce;
        
        // Variables d'état
        let currentView = 'grid';
        let currentPage = 1;
        const itemsPerPage = 20;
        let allEntreprises = [];
        let filteredEntreprises = [];
        let currentModalEntrepriseId = null;
        let currentModalEntrepriseData = null;
        let currentModalPentestScore = null;
        
        // Charger les secteurs pour le filtre
        async function loadSecteurs() {
            try {
                const secteurs = await EntreprisesAPI.loadSecteurs();
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
                allEntreprises = await EntreprisesAPI.loadAll();
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
                ? entreprise.tags.map(tag => `<span class="tag">${Formatters.escapeHtml(tag)}</span>`).join('')
                : '';
            
            let resumePreview = '';
            if (entreprise.resume) {
                resumePreview = entreprise.resume.length > 150 
                    ? entreprise.resume.substring(0, 147) + '...' 
                    : entreprise.resume;
            }
            
            // Chercher l'image principale : og_image, logo, favicon, ou première image OG
            let mainImage = entreprise.og_image || entreprise.logo || entreprise.favicon || null;
            
            // Si pas d'image principale, essayer de récupérer depuis og_data
            if (!mainImage && entreprise.og_data) {
                const ogDataList = Array.isArray(entreprise.og_data) ? entreprise.og_data : [entreprise.og_data];
                for (const ogData of ogDataList) {
                    if (ogData && ogData.images && ogData.images.length > 0 && ogData.images[0].image_url) {
                        mainImage = ogData.images[0].image_url;
                        break;
                    }
                }
            }
            
            return `
                <div class="entreprise-card" data-id="${entreprise.id}">
                    <div class="card-header-with-logo">
                        ${mainImage ? `
                        <div class="card-logo-container">
                            <img src="${mainImage}" alt="${Formatters.escapeHtml(entreprise.nom || 'Logo')}" class="card-logo" onerror="this.style.display='none'">
                        </div>
                        ` : ''}
                        <div class="card-header">
                            <div style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
                                <h3>${Formatters.escapeHtml(entreprise.nom || 'Sans nom')}</h3>
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
                        ${resumePreview ? `<p class="resume-preview" style="color: #666; font-size: 0.9rem; margin-bottom: 0.75rem; font-style: italic;">${Formatters.escapeHtml(resumePreview)}</p>` : ''}
                        ${entreprise.website ? `<p><strong>Site:</strong> <a href="${entreprise.website}" target="_blank">${Formatters.escapeHtml(entreprise.website)}</a></p>` : ''}
                        ${entreprise.secteur ? `<p><strong>Secteur:</strong> ${Formatters.escapeHtml(entreprise.secteur)}</p>` : ''}
                        ${entreprise.statut ? `<p><strong>Statut:</strong> ${Badges.getStatusBadge(entreprise.statut)}</p>` : ''}
                        ${(typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null) || (typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null) ? `
                        <div style="margin-top:0.5rem; padding-top:0.5rem; border-top:1px solid #e5e7eb;">
                            ${typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null ? `
                            <p style="margin:0.25rem 0;">
                                <strong>Sécurité:</strong> ${Badges.getSecurityScoreBadge(entreprise.score_securite)}
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
                        ${entreprise.email_principal ? `<p><strong>Email:</strong> ${Formatters.escapeHtml(entreprise.email_principal)}</p>` : ''}
                        ${entreprise.responsable ? `<p><strong>Responsable:</strong> ${Formatters.escapeHtml(entreprise.responsable)}</p>` : ''}
                        ${tagsHtml ? `<div class="tags-container">${tagsHtml}</div>` : ''}
                    </div>
                    <div class="card-footer">
                        <button class="btn btn-small btn-primary btn-view-details" data-id="${entreprise.id}">Voir détails</button>
                        <button class="btn btn-small btn-secondary btn-edit-tags" data-id="${entreprise.id}">Tags</button>
                        <button class="btn btn-small btn-danger btn-delete-entreprise" data-id="${entreprise.id}" data-name="${Formatters.escapeHtml(entreprise.nom || 'Sans nom')}" title="Supprimer"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `;
        }
        
        function createEntrepriseRow(entreprise) {
            const tagsHtml = entreprise.tags && entreprise.tags.length > 0
                ? entreprise.tags.map(tag => `<span class="tag">${Formatters.escapeHtml(tag)}</span>`).join('')
                : '';
            
            return `
                <div class="entreprise-row" data-id="${entreprise.id}">
                    <div class="row-main">
                        <div class="row-name">
                            <div style="display:flex; align-items:center; gap:0.5rem;">
                            <h3>${Formatters.escapeHtml(entreprise.nom || 'Sans nom')}</h3>
                                ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null && entreprise.score_pentest >= 40 ? `
                                <i class="fas fa-exclamation-triangle" style="color: ${entreprise.score_pentest >= 70 ? '#e74c3c' : '#f39c12'}; font-size: 1.1rem;" title="Score Pentest: ${entreprise.score_pentest}/100"></i>
                                ` : ''}
                            </div>
                            ${tagsHtml ? `<div class="tags-container">${tagsHtml}</div>` : ''}
                        </div>
                        <div class="row-info">
                            ${entreprise.secteur ? `<span>${Formatters.escapeHtml(entreprise.secteur)}</span>` : ''}
                            ${entreprise.statut ? `<span>${Badges.getStatusBadge(entreprise.statut)}</span>` : ''}
                            ${typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null ? `<span>${Badges.getSecurityScoreBadge(entreprise.score_securite)}</span>` : ''}
                            ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null ? `
                            <span>
                                <span class="badge badge-${entreprise.score_pentest >= 70 ? 'danger' : entreprise.score_pentest >= 40 ? 'warning' : 'success'}">Pentest: ${entreprise.score_pentest}/100</span>
                            </span>
                            ` : ''}
                            ${entreprise.email_principal ? `<span>${Formatters.escapeHtml(entreprise.email_principal)}</span>` : ''}
                        </div>
                    </div>
                    <div class="row-actions">
                        <button class="btn-favori ${entreprise.favori ? 'active' : ''}" data-id="${entreprise.id}" title="Favori"><i class="fas fa-star"></i></button>
                        <button class="btn btn-small btn-secondary btn-edit-tags" data-id="${entreprise.id}">Tags</button>
                        <button class="btn btn-small btn-primary btn-view-details" data-id="${entreprise.id}">Détails</button>
                        <button class="btn btn-small btn-danger btn-delete-entreprise" data-id="${entreprise.id}" data-name="${Formatters.escapeHtml(entreprise.nom || 'Sans nom')}" title="Supprimer"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `;
        }
        
        function renderPagination() {
            const totalPages = Math.ceil(filteredEntreprises.length / itemsPerPage);
            const pagination = document.getElementById('pagination');
            
            if (totalPages <= 1) {
                pagination.innerHTML = '';
                return;
            }
            
            let html = '<div class="pagination-controls">';
            html += `<button class="btn-pagination ${currentPage === 1 ? 'disabled' : ''}" data-page="${currentPage - 1}">← Précédent</button>`;
            
            for (let i = 1; i <= totalPages; i++) {
                if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
                    html += `<button class="btn-pagination ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
                } else if (i === currentPage - 3 || i === currentPage + 3) {
                    html += '<span class="pagination-ellipsis">...</span>';
                }
            }
            
            html += `<button class="btn-pagination ${currentPage === totalPages ? 'disabled' : ''}" data-page="${currentPage + 1}">Suivant →</button>`;
            html += '</div>';
            pagination.innerHTML = html;
            
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
        
        async function toggleFavori(entrepriseId) {
            try {
                await EntreprisesAPI.toggleFavori(entrepriseId);
                const entreprise = allEntreprises.find(e => e.id === entrepriseId);
                if (entreprise) {
                    entreprise.favori = !entreprise.favori;
                }
                renderEntreprises();
                Notifications.show('Favori mis à jour', 'success');
            } catch (error) {
                console.error('Erreur:', error);
                Notifications.show('Erreur lors de la mise à jour du favori', 'error');
            }
        }
        
        async function exportCSV() {
            try {
                const blob = await EntreprisesAPI.exportCSV();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `entreprises_${new Date().toISOString().split('T')[0]}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                Notifications.show('Export CSV réussi', 'success');
            } catch (error) {
                console.error('Erreur:', error);
                Notifications.show('Erreur lors de l\'export CSV', 'error');
            }
        }
        
        function setupEntrepriseActions(entrepriseId) {
            const favoriBtn = document.querySelector(`.btn-favori[data-id="${entrepriseId}"]`);
            if (favoriBtn) {
                favoriBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await toggleFavori(entrepriseId);
                });
            }
            
            const viewBtn = document.querySelector(`.btn-view-details[data-id="${entrepriseId}"]`);
            if (viewBtn) {
                viewBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openEntrepriseModal(entrepriseId);
                });
            }
            
            const deleteBtn = document.querySelector(`.btn-delete-entreprise[data-id="${entrepriseId}"]`);
            if (deleteBtn) {
                deleteBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const name = deleteBtn.dataset.name || 'Sans nom';
                    if (confirm(`Êtes-vous sûr de vouloir supprimer "${name}" ?`)) {
                        try {
                            await EntreprisesAPI.delete(entrepriseId);
                            allEntreprises = allEntreprises.filter(e => e.id !== entrepriseId);
                            applyFilters();
                            Notifications.show('Entreprise supprimée', 'success');
                        } catch (error) {
                            console.error('Erreur:', error);
                            Notifications.show('Erreur lors de la suppression', 'error');
                        }
                    }
                });
            }
        }
        
        function setupEventListeners() {
            document.getElementById('btn-apply-filters').addEventListener('click', applyFilters);
            document.getElementById('btn-reset-filters').addEventListener('click', () => {
                document.getElementById('search-input').value = '';
                document.getElementById('filter-secteur').value = '';
                document.getElementById('filter-statut').value = '';
                document.getElementById('filter-opportunite').value = '';
                document.getElementById('filter-favori').checked = false;
                applyFilters();
            });
            
            document.getElementById('search-input').addEventListener('input', debounceFn(applyFilters, 300));
            
            document.getElementById('btn-export').addEventListener('click', async () => {
                await exportCSV();
            });
            
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
        
        // Ouvrir la modal d'entreprise
        async function openEntrepriseModal(entrepriseId) {
            currentModalEntrepriseId = entrepriseId;
            const modal = document.getElementById('entreprise-modal');
            const modalBody = document.getElementById('modal-entreprise-body');
            const modalTitle = document.getElementById('modal-entreprise-nom');
            
            if (!modal || !modalBody || !modalTitle) {
                console.error('Éléments de la modale introuvables');
                Notifications.show('Erreur: éléments de la modal introuvables', 'error');
                return;
            }
            
            modal.style.display = 'flex';
            modalBody.innerHTML = '<div class="loading">Chargement des détails...</div>';
            modalTitle.textContent = 'Chargement...';
            
            try {
                currentModalEntrepriseData = await EntreprisesAPI.loadDetails(entrepriseId);
                currentModalPentestScore = null;
                modalTitle.textContent = currentModalEntrepriseData.nom || 'Sans nom';
                modalBody.innerHTML = createModalContent(currentModalEntrepriseData);
                
                setupModalInteractions();
                loadEntrepriseImages(entrepriseId);
                loadEntreprisePages(currentModalEntrepriseData);
                loadScrapingResults(entrepriseId);
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
                setupModalInteractions();
            }
        }
        
        function updateModalTabCount(tabKey, count) {
            const btn = document.querySelector(`.tab-btn[data-tab="${tabKey}"]`);
            if (!btn) return;
            const labels = { images: 'Images', pages: 'Pages' };
            btn.textContent = (labels[tabKey] || tabKey) + ' (' + (count || 0) + ')';
        }
        
        function createModalContent(entreprise) {
            const tags = entreprise.tags || [];
            const nbPages = (entreprise.pages_count != null && entreprise.pages_count !== '') ? Number(entreprise.pages_count) : (() => {
                const ogDataList = Array.isArray(entreprise.og_data) ? entreprise.og_data : (entreprise.og_data ? [entreprise.og_data] : []);
                return ogDataList.length;
            })();
            const nbImages = (entreprise.images_count != null && entreprise.images_count !== '') ? Number(entreprise.images_count) : (() => {
                let n = (entreprise.og_image ? 1 : 0) + (entreprise.logo ? 1 : 0) + (entreprise.favicon ? 1 : 0);
                const ogDataList = Array.isArray(entreprise.og_data) ? entreprise.og_data : (entreprise.og_data ? [entreprise.og_data] : []);
                ogDataList.forEach(og => { if (og && og.images && og.images.length) n += og.images.length; });
                return n;
            })();

            return `
                <div class="entreprise-modal-tabs">
                    <div class="tabs-header">
                        <button class="tab-btn active" data-tab="info">Info</button>
                        <button class="tab-btn" data-tab="images">Images (${nbImages})</button>
                        <button class="tab-btn" data-tab="pages">Pages (${nbPages})</button>
                        <button class="tab-btn" data-tab="scraping">Résultats scraping</button>
                        <button class="tab-btn" data-tab="technique">Analyse technique</button>
                        <button class="tab-btn" data-tab="osint">Analyse OSINT</button>
                        <button class="tab-btn" data-tab="pentest">Analyse Pentest</button>
                    </div>
                    
                    <div class="tabs-content">
                        <div class="tab-panel active" id="tab-info">
                            ${(function() {
                                // Récupérer toutes les images disponibles
                                const imagesToShow = [];
                                
                                if (entreprise.og_image) {
                                    imagesToShow.push({url: entreprise.og_image, type: 'Image OpenGraph'});
                                }
                                if (entreprise.logo) {
                                    imagesToShow.push({url: entreprise.logo, type: 'Logo'});
                                }
                                if (entreprise.favicon) {
                                    imagesToShow.push({url: entreprise.favicon, type: 'Favicon'});
                                }
                                
                                // Ajouter les images depuis og_data
                                if (entreprise.og_data) {
                                    const ogDataList = Array.isArray(entreprise.og_data) ? entreprise.og_data : [entreprise.og_data];
                                    ogDataList.forEach(ogData => {
                                        if (ogData && ogData.images && Array.isArray(ogData.images)) {
                                            ogData.images.forEach(img => {
                                                if (img && img.image_url && !imagesToShow.find(i => i.url === img.image_url)) {
                                                    imagesToShow.push({url: img.image_url, type: 'Image OpenGraph', alt: img.alt_text});
                                                }
                                            });
                                        }
                                    });
                                }
                                
                                if (imagesToShow.length === 0) return '';
                                
                                let html = '<div class="detail-section" style="margin-bottom: 1.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 8px;"><div style="text-align: center;"><div style="display: flex; align-items: center; justify-content: center; gap: 2rem; flex-wrap: wrap;">';
                                
                                imagesToShow.forEach(img => {
                                    const maxHeight = img.type === 'Favicon' ? '64px' : img.type === 'Logo' ? '150px' : '300px';
                                    html += `<div style="flex: 1; min-width: ${img.type === 'Favicon' ? '100px' : img.type === 'Logo' ? '150px' : '200px'};">
                                        <h4 style="color: white; margin: 0 0 1rem 0; font-size: 0.9rem; text-transform: uppercase; opacity: 0.9;">${Formatters.escapeHtml(img.type)}</h4>
                                        <img src="${Formatters.escapeHtml(img.url)}" alt="${Formatters.escapeHtml(img.alt || img.type)}" style="max-width: 100%; max-height: ${maxHeight}; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); background: white; padding: 0.5rem;" onerror="this.style.display='none'">
                                    </div>`;
                                });
                                
                                html += '</div></div></div>';
                                return html;
                            })()}
                            ${entreprise.resume ? `
                            <div class="detail-section" style="margin-bottom: 1.5rem; background: #f8f9fa; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #667eea;">
                                <h3 style="margin: 0 0 0.75rem 0; color: #2c3e50; font-size: 1.1rem;"><i class="fas fa-file-alt"></i> Résumé de l'entreprise</h3>
                                <p style="margin: 0; color: #555; line-height: 1.6; font-size: 0.95rem;">${Formatters.escapeHtml(entreprise.resume)}</p>
                            </div>
                            ` : ''}
                            <div class="info-grid">
                                ${createInfoRow('Nom', entreprise.nom)}
                                ${createInfoRow('Site web', entreprise.website, true)}
                                ${createInfoRow('Secteur', entreprise.secteur)}
                                ${createInfoRow('Statut', entreprise.statut, false, Badges.getStatusBadge(entreprise.statut))}
                                ${typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null ? `
                                <div class="info-row">
                                    <span class="info-label">Score sécurité:</span>
                                    <span class="info-value">${Badges.getSecurityScoreBadge(entreprise.score_securite)}</span>
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
                        </div>
                        
                        <div class="tab-panel" id="tab-images">
                            <div id="entreprise-images-container" class="images-tab-content">
                                <p class="empty-state">Aucune image disponible pour le moment. Lancez un scraping pour récupérer les visuels du site.</p>
                            </div>
                        </div>
                        
                        <div class="tab-panel" id="tab-pages">
                            <div id="entreprise-pages-container" class="pages-tab-content">
                                <p class="empty-state">Aucune donnée OpenGraph disponible pour le moment. Lancez un scraping pour récupérer les métadonnées des pages.</p>
                            </div>
                        </div>
                        
                        <div class="tab-panel" id="tab-scraping">
                            <div id="scraping-results" class="scraping-results" style="display: block;">
                                <div style="margin-bottom: 1.5rem;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                                        <h3 style="margin: 0; color: #1e293b; font-size: 1.5rem; font-weight: 600;">
                                            <i class="fas fa-spider" style="margin-right: 0.5rem; color: #667eea;"></i>
                                            Résultats du scraping
                                        </h3>
                                        <div style="display: flex; gap: 0.5rem;">
                                            <button id="scraping-export-btn" class="btn btn-small" style="padding: 0.5rem 1rem; font-size: 0.875rem;" title="Exporter les résultats">
                                                <i class="fas fa-download" style="margin-right: 0.5rem;"></i>
                                                Exporter
                                            </button>
                                        </div>
                                    </div>
                                    <div id="scraping-stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
                                        <!-- Les statistiques seront injectées ici -->
                                    </div>
                                </div>
                                <div class="results-tabs" style="display: flex; gap: 0.5rem; margin-bottom: 1rem; border-bottom: 2px solid #e2e8f0; flex-wrap: wrap; overflow-x: auto;">
                                    <button class="tab-button active" data-tab="emails" style="padding: 0.75rem 1.25rem; border: none; background: transparent; color: #64748b; font-weight: 500; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap; position: relative;">
                                        <i class="fas fa-envelope" style="margin-right: 0.5rem;"></i>
                                        Emails (<span id="count-emails-modal">0</span>)
                                    </button>
                                    <button class="tab-button" data-tab="people" style="padding: 0.75rem 1.25rem; border: none; background: transparent; color: #64748b; font-weight: 500; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;">
                                        <i class="fas fa-users" style="margin-right: 0.5rem;"></i>
                                        Personnes (<span id="count-people-modal">0</span>)
                                    </button>
                                    <button class="tab-button" data-tab="phones" style="padding: 0.75rem 1.25rem; border: none; background: transparent; color: #64748b; font-weight: 500; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;">
                                        <i class="fas fa-phone" style="margin-right: 0.5rem;"></i>
                                        Téléphones (<span id="count-phones-modal">0</span>)
                                    </button>
                                    <button class="tab-button" data-tab="social" style="padding: 0.75rem 1.25rem; border: none; background: transparent; color: #64748b; font-weight: 500; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;">
                                        <i class="fas fa-share-alt" style="margin-right: 0.5rem;"></i>
                                        Réseaux sociaux (<span id="count-social-modal">0</span>)
                                    </button>
                                    <button class="tab-button" data-tab="technologies" style="padding: 0.75rem 1.25rem; border: none; background: transparent; color: #64748b; font-weight: 500; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;">
                                        <i class="fas fa-code" style="margin-right: 0.5rem;"></i>
                                        Technologies (<span id="count-tech-modal">0</span>)
                                    </button>
                                    <button class="tab-button" data-tab="metadata" style="padding: 0.75rem 1.25rem; border: none; background: transparent; color: #64748b; font-weight: 500; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;">
                                        <i class="fas fa-info-circle" style="margin-right: 0.5rem;"></i>
                                        Métadonnées
                                    </button>
                                </div>
                                <div id="scraping-search-container" style="margin-bottom: 1rem; display: none;">
                                    <div style="position: relative;">
                                        <i class="fas fa-search" style="position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: #94a3b8;"></i>
                                        <input type="text" id="scraping-search-input" placeholder="Rechercher dans cette section..." 
                                               style="width: 100%; padding: 0.75rem 1rem 0.75rem 2.75rem; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem; transition: border-color 0.2s;"
                                               onfocus="this.style.borderColor='#667eea';" onblur="this.style.borderColor='#e2e8f0';">
                                        <button id="scraping-search-clear" style="position: absolute; right: 0.75rem; top: 50%; transform: translateY(-50%); background: none; border: none; color: #94a3b8; cursor: pointer; display: none; padding: 0.25rem;">
                                            <i class="fas fa-times"></i>
                                        </button>
                                    </div>
                                </div>
                                <div id="tab-emails-modal" class="tab-content active" style="display: block;">
                                    <div id="emails-list-modal" class="results-list" style="display: grid; gap: 0.75rem;"></div>
                                </div>
                                <div id="tab-people-modal" class="tab-content" style="display: none;">
                                    <div id="people-list-modal" class="results-list" style="display: grid; gap: 0.75rem;"></div>
                                </div>
                                <div id="tab-phones-modal" class="tab-content" style="display: none;">
                                    <div id="phones-list-modal" class="results-list" style="display: grid; gap: 0.75rem;"></div>
                                </div>
                                <div id="tab-social-modal" class="tab-content" style="display: none;">
                                    <div id="social-list-modal" class="results-list" style="display: grid; gap: 0.75rem;"></div>
                                </div>
                                <div id="tab-technologies-modal" class="tab-content" style="display: none;">
                                    <div id="technologies-list-modal" class="results-list" style="display: grid; gap: 1rem;"></div>
                                </div>
                                <div id="tab-metadata-modal" class="tab-content" style="display: none;">
                                    <div id="metadata-list-modal" class="results-list" style="display: grid; gap: 1rem;"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="tab-panel" id="tab-technique">
                            <div id="technique-results" class="analysis-results">
                                <div id="technique-results-content">Chargement de l'analyse technique...</div>
                            </div>
                        </div>
                        
                        <div class="tab-panel" id="tab-osint">
                            <div id="osint-results" class="analysis-results">
                                <div id="osint-results-content">Chargement de l'analyse OSINT...</div>
                            </div>
                        </div>
                        
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
            const content = customContent || (isLink ? `<a href="${value}" target="_blank" rel="noopener">${Formatters.escapeHtml(value)}</a>` : Formatters.escapeHtml(value));
            return `
                <div class="info-row">
                    <span class="info-label">${label}:</span>
                    <span class="info-value">${content}</span>
                </div>
            `;
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
            const closeBtn = document.getElementById('modal-close-btn');
            const closeFooterBtn = document.getElementById('modal-close-footer-btn');
            const modal = document.getElementById('entreprise-modal');
            
            if (closeBtn) {
                closeBtn.onclick = (e) => {
                    e.stopPropagation();
                    closeEntrepriseModal();
                };
            }
            
            if (closeFooterBtn) {
                closeFooterBtn.onclick = (e) => {
                    e.stopPropagation();
                    closeEntrepriseModal();
                };
            }
            
            if (modal) {
                modal.onclick = (e) => {
                    if (e.target === modal) {
                        closeEntrepriseModal();
                    }
                };
            }
            
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && modal && modal.style.display !== 'none') {
                    closeEntrepriseModal();
                }
            });
            
            const tabBtns = document.querySelectorAll('.tab-btn');
            tabBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    const tabName = btn.getAttribute('data-tab');
                    tabBtns.forEach(b => b.classList.remove('active'));
                    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                    btn.classList.add('active');
                    const targetPanel = document.getElementById(`tab-${tabName}`);
                    if (targetPanel) {
                        targetPanel.classList.add('active');
                    }
                });
            });
            
            const favoriBtn = document.getElementById('modal-toggle-favori');
            if (favoriBtn) {
                favoriBtn.addEventListener('click', async () => {
                    if (!currentModalEntrepriseId) return;
                    try {
                        await EntreprisesAPI.toggleFavori(currentModalEntrepriseId);
                        const entreprise = allEntreprises.find(e => e.id === currentModalEntrepriseId);
                        if (entreprise) {
                            entreprise.favori = !entreprise.favori;
                        }
                        favoriBtn.classList.toggle('active');
                        favoriBtn.innerHTML = currentModalEntrepriseData.favori ? '<i class="fas fa-star"></i> Favori' : '<i class="far fa-star"></i> Ajouter aux favoris';
                        currentModalEntrepriseData.favori = !currentModalEntrepriseData.favori;
                        Notifications.show('Favori mis à jour', 'success');
                    } catch (error) {
                        console.error('Erreur:', error);
                        Notifications.show('Erreur lors de la mise à jour du favori', 'error');
                    }
                });
            }
            
            const modalBody = document.getElementById('modal-entreprise-body');
            if (modalBody) {
                modalBody.addEventListener('click', async (e) => {
                    // Gestion des onglets principaux de la modale
                    if (e.target.closest('.tab-btn')) {
                        const tabBtn = e.target.closest('.tab-btn');
                        const tabName = tabBtn.getAttribute('data-tab');
                        modalBody.querySelectorAll('.tab-btn').forEach(b => {
                            b.classList.remove('active');
                        });
                        modalBody.querySelectorAll('.tab-panel').forEach(p => {
                            p.classList.remove('active');
                            p.style.display = 'none';
                        });
                        tabBtn.classList.add('active');
                        const targetPanel = modalBody.querySelector(`#tab-${tabName}`);
                        if (targetPanel) {
                            targetPanel.classList.add('active');
                            targetPanel.style.display = 'block';
                        }
                        return;
                    }
                    
                    // Gestion des onglets de scraping (sous-onglets)
                    if (e.target.closest('.results-tabs .tab-button')) {
                        const tabBtn = e.target.closest('.tab-button');
                        const tabName = tabBtn.getAttribute('data-tab');
                        const scrapingResults = document.getElementById('scraping-results');
                        if (!scrapingResults) return;
                        
                        scrapingResults.querySelectorAll('.tab-button').forEach(b => {
                            b.classList.remove('active');
                            b.style.borderBottomColor = 'transparent';
                            b.style.color = '#64748b';
                        });
                        scrapingResults.querySelectorAll('.tab-content').forEach(c => {
                            c.classList.remove('active');
                            c.style.display = 'none';
                        });
                        tabBtn.classList.add('active');
                        tabBtn.style.borderBottomColor = '#667eea';
                        tabBtn.style.color = '#667eea';
                        const targetPanel = document.getElementById(`tab-${tabName}-modal`);
                        if (targetPanel) {
                            targetPanel.classList.add('active');
                            targetPanel.style.display = 'block';
                        }
                        
                        // Afficher/masquer la barre de recherche selon l'onglet
                        const searchContainer = document.getElementById('scraping-search-container');
                        if (searchContainer && ['emails', 'people', 'phones', 'social', 'technologies'].includes(tabName)) {
                            searchContainer.style.display = 'block';
                            const searchInput = document.getElementById('scraping-search-input');
                            if (searchInput) {
                                searchInput.value = '';
                                searchInput.placeholder = `Rechercher dans ${tabName === 'emails' ? 'les emails' : tabName === 'people' ? 'les personnes' : tabName === 'phones' ? 'les téléphones' : tabName === 'social' ? 'les réseaux sociaux' : 'les technologies'}...`;
                                filterScrapingResults(tabName, '');
                            }
                        } else {
                            if (searchContainer) searchContainer.style.display = 'none';
                        }
                    }
                });
            }
            
            // Gestion de la recherche dans les résultats de scraping
            const scrapingSearchInput = document.getElementById('scraping-search-input');
            if (scrapingSearchInput) {
                scrapingSearchInput.addEventListener('input', function() {
                    const scrapingResults = document.getElementById('scraping-results');
                    if (!scrapingResults) return;
                    const activeTab = scrapingResults.querySelector('.tab-button.active[data-tab]');
                    if (activeTab) {
                        const tabName = activeTab.getAttribute('data-tab');
                        filterScrapingResults(tabName, this.value);
                        const clearBtn = document.getElementById('scraping-search-clear');
                        if (clearBtn) {
                            clearBtn.style.display = this.value ? 'block' : 'none';
                        }
                    }
                });
            }
            
            const scrapingSearchClear = document.getElementById('scraping-search-clear');
            if (scrapingSearchClear) {
                scrapingSearchClear.addEventListener('click', function() {
                    const searchInput = document.getElementById('scraping-search-input');
                    if (searchInput) {
                        searchInput.value = '';
                        this.style.display = 'none';
                        const scrapingResults = document.getElementById('scraping-results');
                        if (scrapingResults) {
                            const activeTab = scrapingResults.querySelector('.tab-button.active[data-tab]');
                            if (activeTab) {
                                filterScrapingResults(activeTab.getAttribute('data-tab'), '');
                            }
                        }
                    }
                });
            }
            
            // Fonction de filtrage des résultats
            function filterScrapingResults(tabName, searchTerm) {
                const listId = `${tabName}-list-modal`;
                const listContainer = document.getElementById(listId);
                if (!listContainer) return;
                
                const items = listContainer.querySelectorAll('[data-searchable]');
                const term = searchTerm.toLowerCase().trim();
                
                if (!term) {
                    items.forEach(item => item.style.display = '');
                    return;
                }
                
                items.forEach(item => {
                    const text = item.getAttribute('data-searchable').toLowerCase();
                    item.style.display = text.includes(term) ? '' : 'none';
                });
                
                // Afficher un message si aucun résultat
                const visibleItems = Array.from(items).filter(item => item.style.display !== 'none');
                const emptyMsg = listContainer.querySelector('.no-results-message');
                if (visibleItems.length === 0 && term) {
                    if (!emptyMsg) {
                        const msg = document.createElement('div');
                        msg.className = 'no-results-message';
                        msg.style.cssText = 'text-align: center; padding: 2rem; color: #94a3b8; grid-column: 1 / -1;';
                        msg.innerHTML = '<i class="fas fa-search" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><p>Aucun résultat trouvé pour "' + Formatters.escapeHtml(searchTerm) + '"</p>';
                        listContainer.appendChild(msg);
                    }
                } else if (emptyMsg) {
                    emptyMsg.remove();
                }
            }
            
            // Bouton d'export
            const scrapingExportBtn = document.getElementById('scraping-export-btn');
            if (scrapingExportBtn) {
                scrapingExportBtn.addEventListener('click', function() {
                    // TODO: Implémenter l'export
                    if (typeof window.Notifications !== 'undefined') {
                        window.Notifications.show('Fonctionnalité d\'export à venir', 'info');
                    }
                });
            }
            
            // Gestionnaires pour les boutons de copie (délégation d'événements)
            if (modalBody) {
                modalBody.addEventListener('click', function(e) {
                    const copyEmailBtn = e.target.closest('[data-copy-email]');
                    if (copyEmailBtn) {
                        const email = copyEmailBtn.getAttribute('data-copy-email');
                        navigator.clipboard.writeText(email).then(() => {
                            if (typeof window.Notifications !== 'undefined') {
                                window.Notifications.show('Email copié', 'success');
                            }
                        }).catch(err => {
                            console.error('Erreur lors de la copie:', err);
                        });
                        e.preventDefault();
                        return;
                    }
                    
                    const copyPhoneBtn = e.target.closest('[data-copy-phone]');
                    if (copyPhoneBtn) {
                        const phone = copyPhoneBtn.getAttribute('data-copy-phone');
                        navigator.clipboard.writeText(phone).then(() => {
                            if (typeof window.Notifications !== 'undefined') {
                                window.Notifications.show('Téléphone copié', 'success');
                            }
                        }).catch(err => {
                            console.error('Erreur lors de la copie:', err);
                        });
                        e.preventDefault();
                        return;
                    }
                });
            }
            
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
            
            const scrapingTab = document.querySelector('.tab-btn[data-tab="scraping"]');
            if (scrapingTab) {
                scrapingTab.addEventListener('click', () => {
                    if (currentModalEntrepriseId) {
                        loadScrapingResults(currentModalEntrepriseId);
                    }
                });
            }
            
            const imagesTab = document.querySelector('.tab-btn[data-tab="images"]');
            if (imagesTab) {
                imagesTab.addEventListener('click', () => {
                    if (currentModalEntrepriseId) {
                        loadEntrepriseImages(currentModalEntrepriseId);
                    }
                });
            }
            
            const pagesTab = document.querySelector('.tab-btn[data-tab="pages"]');
            if (pagesTab) {
                pagesTab.addEventListener('click', () => {
                    if (currentModalEntrepriseData) {
                        loadEntreprisePages(currentModalEntrepriseData);
                    }
                });
            }
        }
        async function loadTechnicalAnalysis(entrepriseId) {
            const resultsContent = document.getElementById('technique-results-content');
            if (!resultsContent) return;
            
            try {
                resultsContent.innerHTML = 'Chargement...';
                const analysis = await EntreprisesAPI.loadTechnicalAnalysis(entrepriseId);
                if (analysis) {
                    if (window.TechnicalAnalysisDisplay && window.TechnicalAnalysisDisplay.displayTechnicalAnalysis) {
                        window.TechnicalAnalysisDisplay.displayTechnicalAnalysis(analysis, resultsContent);
                    } else {
                        console.error('Module TechnicalAnalysisDisplay non disponible');
                        resultsContent.innerHTML = '<p class="error">Module d\'affichage non disponible</p>';
                    }
                } else {
                    resultsContent.innerHTML = '<p class="empty-state">Aucune analyse technique disponible pour le moment.</p>';
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
                const analysis = await EntreprisesAPI.loadOSINTAnalysis(entrepriseId);
                if (analysis) {
                    if (window.OSINTAnalysisDisplay && window.OSINTAnalysisDisplay.displayOSINTAnalysis) {
                        window.OSINTAnalysisDisplay.displayOSINTAnalysis(analysis, resultsContent);
                    } else {
                        console.error('Module OSINTAnalysisDisplay non disponible');
                        resultsContent.innerHTML = '<p class="error">Module d\'affichage non disponible</p>';
                    }
                } else {
                    resultsContent.innerHTML = '<p class="empty-state">Aucune analyse OSINT disponible pour le moment.</p>';
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
                const analysis = await EntreprisesAPI.loadPentestAnalysis(entrepriseId);
                if (analysis) {
                    currentModalPentestScore = analysis.risk_score || null;
                    if (window.PentestAnalysisDisplay && window.PentestAnalysisDisplay.displayPentestAnalysis) {
                        window.PentestAnalysisDisplay.displayPentestAnalysis(analysis, resultsContent);
                    } else {
                        console.error('Module PentestAnalysisDisplay non disponible');
                        resultsContent.innerHTML = '<p class="error">Module d\'affichage non disponible</p>';
                    }
                    
                    if (currentModalPentestScore !== null) {
                        const pentestRow = document.getElementById('pentest-score-row');
                        const pentestValue = document.getElementById('pentest-score-value');
                        if (pentestRow && pentestValue) {
                            const icon = currentModalPentestScore >= 70 ? '<i class="fas fa-exclamation-circle"></i> ' : currentModalPentestScore >= 40 ? '<i class="fas fa-exclamation-triangle"></i> ' : '';
                            const badgeClass = currentModalPentestScore >= 70 ? 'danger' : currentModalPentestScore >= 40 ? 'warning' : 'success';
                            pentestValue.innerHTML = `${icon}<span class="badge badge-${badgeClass}">${currentModalPentestScore}/100</span>`;
                            pentestRow.style.display = '';
                        }
                    }
                } else {
                    currentModalPentestScore = null;
                    resultsContent.innerHTML = '<p class="empty-state">Aucune analyse Pentest disponible pour le moment.</p>';
                }
            } catch (error) {
                console.error('Erreur lors du chargement de l\'analyse Pentest:', error);
                currentModalPentestScore = null;
                resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse Pentest</p>';
            }
        }
        
        async function loadScrapingResults(entrepriseId) {
            // Réinitialiser les conteneurs
            const containers = {
                'emails-list-modal': '<div class="empty-state">Aucun email trouvé</div>',
                'people-list-modal': '<div class="empty-state">Aucune personne trouvée</div>',
                'phones-list-modal': '<div class="empty-state">Aucun téléphone trouvé</div>',
                'social-list-modal': '<div class="empty-state">Aucun réseau social trouvé</div>',
                'technologies-list-modal': '<div class="empty-state">Aucune technologie détectée</div>',
                'metadata-list-modal': '<div class="empty-state">Aucune métadonnée extraite</div>'
            };
            
            Object.entries(containers).forEach(([id, html]) => {
                const el = document.getElementById(id);
                if (el) el.innerHTML = html;
            });
            
            // Réinitialiser les compteurs via le module
            if (typeof window.ScrapingAnalysisDisplay !== 'undefined') {
                window.ScrapingAnalysisDisplay.updateCount('emails', 0);
                window.ScrapingAnalysisDisplay.updateCount('people', 0);
                window.ScrapingAnalysisDisplay.updateCount('phones', 0);
                window.ScrapingAnalysisDisplay.updateCount('social', 0);
                window.ScrapingAnalysisDisplay.updateCount('tech', 0);
            }
            
            try {
                const scrapers = await EntreprisesAPI.loadScrapingResults(entrepriseId);
                const unifiedScrapers = scrapers.filter(s => s.scraper_type === 'unified_scraper').sort((a, b) => {
                    const dateA = new Date(a.date_modification || a.date_creation || 0);
                    const dateB = new Date(b.date_modification || b.date_creation || 0);
                    return dateB - dateA;
                });
                
                if (unifiedScrapers.length > 0) {
                    const latestScraper = unifiedScrapers[0];
                    const data = {
                        emails: Array.isArray(latestScraper.emails) ? latestScraper.emails : [],
                        people: Array.isArray(latestScraper.people) ? latestScraper.people : [],
                        phones: Array.isArray(latestScraper.phones) ? latestScraper.phones : [],
                        social_links: latestScraper.social_profiles || {},
                        technologies: latestScraper.technologies || {},
                        metadata: latestScraper.metadata || {}
                    };
                    if (typeof window.ScrapingAnalysisDisplay !== 'undefined') {
                        window.ScrapingAnalysisDisplay.displayAll(data);
                    } else {
                        console.error('Module ScrapingAnalysisDisplay non disponible');
                    }
                    loadEntrepriseImages(entrepriseId);
                }
            } catch (error) {
                console.error('Erreur lors du chargement des résultats:', error);
            }
        }
        
        function displayAllScrapingResults(data) {
            if (typeof window.ScrapingAnalysisDisplay === 'undefined') {
                console.error('Module ScrapingAnalysisDisplay non disponible');
                return;
            }
            window.ScrapingAnalysisDisplay.displayAll(data);
        }
        
        async function loadEntrepriseImages(entrepriseId) {
            try {
                const response = await fetch(`/api/entreprise/${entrepriseId}/images`);
                if (response.ok) {
                    const images = await response.json();
                    const container = document.getElementById('entreprise-images-container');
                    if (!container) return;
                    
                    if (!images || images.length === 0) {
                        container.innerHTML = '<p class="empty-state">Aucune image trouvée pour ce site.</p>';
                        updateModalTabCount('images', 0);
                        return;
                    }
                    
                    updateModalTabCount('images', images.length);
                    const maxImages = 60;
                    const limited = images.slice(0, maxImages);
                    let html = '<div class="entreprise-images-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px;">';
                    for (const img of limited) {
                        const url = img.url || img;
                        const alt = img.alt_text || img.alt || '';
                        html += `
                            <div class="entreprise-image-card" style="background: #ffffff; border-radius: 8px; box-shadow: 0 2px 6px rgba(15,23,42,0.08); padding: 8px;">
                                <div style="width: 100%; height: 120px; border-radius: 6px; overflow: hidden; background: #f3f4f6; display: flex; align-items: center; justify-content: center;">
                                    <img src="${url}" alt="${Formatters.escapeHtml(alt)}" loading="lazy" onerror="this.style.display='none'" style="width: 100%; height: 100%; object-fit: cover;">
                                </div>
                                <div style="margin-top: 6px;">
                                    ${alt ? `<div title="${Formatters.escapeHtml(alt)}" style="font-size: 0.8rem; color: #374151; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${Formatters.escapeHtml(alt)}</div>` : '<div style="font-size: 0.8rem; color: #9ca3af; margin-bottom: 4px;">Sans texte alternatif</div>'}
                                    <a href="${url}" target="_blank" style="font-size: 0.8rem; color: #2563eb; text-decoration: none;">Ouvrir l'image</a>
                                </div>
                            </div>
                        `;
                    }
                    html += '</div>';
                    container.innerHTML = html;
                }
            } catch (e) {
                console.error('Erreur lors du chargement des images:', e);
            }
        }
        
        function loadEntreprisePages(entreprise) {
            const container = document.getElementById('entreprise-pages-container');
            if (!container) return;
            
            try {
                if (!entreprise || !entreprise.og_data) {
                    container.innerHTML = '<p class="empty-state">Aucune donnée OpenGraph disponible pour le moment. Lancez un scraping pour récupérer les métadonnées des pages.</p>';
                    return;
                }
                
                const ogDataList = Array.isArray(entreprise.og_data) ? entreprise.og_data : [entreprise.og_data];
                const validOgData = ogDataList.filter(ogData => ogData && (ogData.og_title || ogData.og_type || ogData.og_url || ogData.page_url || (ogData.images && ogData.images.length > 0)));
                
                if (validOgData.length === 0) {
                    container.innerHTML = '<p class="empty-state">Aucune donnée OpenGraph disponible pour le moment. Lancez un scraping pour récupérer les métadonnées des pages.</p>';
                    return;
                }
                
                let html = '';
                validOgData.forEach((ogData, idx) => {
                    const hasImage = ogData.images && ogData.images.length > 0 && ogData.images[0].image_url;
                    html += `
                        <div class="page-card" style="background: white; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid #667eea;">
                            <div style="display: flex; gap: 1.5rem; align-items: flex-start;">
                                ${hasImage ? `
                                <div style="flex: 0 0 200px;">
                                    <img src="${Formatters.escapeHtml(ogData.images[0].image_url)}" alt="${Formatters.escapeHtml(ogData.og_title || 'Page preview')}" 
                                         style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); cursor: pointer;"
                                         onclick="window.open('${Formatters.escapeHtml(ogData.images[0].image_url)}', '_blank')"
                                         onerror="this.style.display='none'">
                                </div>
                                ` : ''}
                                <div style="flex: 1; min-width: 0;">
                                    ${ogData.page_url ? `
                                    <div style="margin-bottom: 0.75rem;">
                                        <a href="${Formatters.escapeHtml(ogData.page_url)}" target="_blank" 
                                           style="color: #667eea; font-weight: 600; font-size: 0.9rem; text-decoration: none; word-break: break-all; display: inline-block; max-width: 100%;">
                                            <i class="fas fa-link"></i> ${Formatters.escapeHtml(ogData.page_url)}
                                        </a>
                                    </div>
                                    ` : ''}
                                    ${ogData.og_title ? `
                                    <h3 style="margin: 0 0 0.75rem 0; color: #2c3e50; font-size: 1.2rem; font-weight: 600;">
                                        ${Formatters.escapeHtml(ogData.og_title)}
                                    </h3>
                                    ` : ''}
                                    ${ogData.og_description ? `
                                    <p style="margin: 0 0 1rem 0; color: #555; line-height: 1.6; font-size: 0.95rem;">
                                        ${Formatters.escapeHtml(ogData.og_description)}
                                    </p>
                                    ` : ''}
                                    <div style="display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1rem;">
                                        ${ogData.og_type ? `
                                        <span style="background: #e8f0fe; color: #1967d2; padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.85rem; font-weight: 500;">
                                            <i class="fas fa-tag"></i> ${Formatters.escapeHtml(ogData.og_type)}
                                        </span>
                                        ` : ''}
                                        ${ogData.og_site_name ? `
                                        <span style="background: #f0f4f8; color: #4a5568; padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.85rem;">
                                            <i class="fas fa-globe"></i> ${Formatters.escapeHtml(ogData.og_site_name)}
                                        </span>
                                        ` : ''}
                                        ${ogData.og_locale ? `
                                        <span style="background: #f0f4f8; color: #4a5568; padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.85rem;">
                                            <i class="fas fa-language"></i> ${Formatters.escapeHtml(ogData.og_locale)}
                                        </span>
                                        ` : ''}
                                    </div>
                                    ${ogData.images && ogData.images.length > 1 ? `
                                    <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;">
                                        <div style="font-size: 0.85rem; color: #718096; margin-bottom: 0.5rem; font-weight: 600;">
                                            <i class="fas fa-images"></i> ${ogData.images.length} image(s) supplémentaire(s)
                                        </div>
                                        <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
                                            ${ogData.images.slice(1).map(img => `
                                                <img src="${Formatters.escapeHtml(img.image_url)}" alt="${Formatters.escapeHtml(img.alt_text || 'OG Image')}" 
                                                     style="max-width: 100px; max-height: 100px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); cursor: pointer;"
                                                     onclick="window.open('${Formatters.escapeHtml(img.image_url)}', '_blank')"
                                                     onerror="this.style.display='none'"
                                                     title="${Formatters.escapeHtml(img.alt_text || '')}">
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
                });
                
                container.innerHTML = html;
            } catch (e) {
                console.error('Erreur lors du chargement des pages:', e);
                container.innerHTML = '<p class="empty-state">Erreur lors du chargement des données OpenGraph.</p>';
            }
        }
        
        // Initialisation
        document.addEventListener('DOMContentLoaded', () => {
            loadSecteurs();
            loadEntreprises();
            setupEventListeners();
        });
    }
    
    // Attendre que le DOM soit prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

