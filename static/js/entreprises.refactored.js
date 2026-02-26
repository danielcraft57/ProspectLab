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
        const entrepriseGroupsCache = {};
        
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
        
        /** Construit l'objet de filtres à partir du formulaire (pour l'API). */
        function getCurrentFilters() {
            const search = document.getElementById('search-input').value.trim();
            const secteur = document.getElementById('filter-secteur').value;
            const statut = document.getElementById('filter-statut').value;
            const opportunite = document.getElementById('filter-opportunite').value;
            const favori = document.getElementById('filter-favori').checked;
            const securityMin = document.getElementById('filter-security-min').value;
            const securityMax = document.getElementById('filter-security-max').value;
            const pentestMin = document.getElementById('filter-pentest-min').value;
            const pentestMax = document.getElementById('filter-pentest-max').value;
            const filters = {};
            if (search) filters.search = search;
            if (secteur) filters.secteur = secteur;
            if (statut) filters.statut = statut;
            if (opportunite) filters.opportunite = opportunite;
            if (favori) filters.favori = 'true';
            if (securityMin !== '') filters.security_min = securityMin;
            if (securityMax !== '') filters.security_max = securityMax;
            if (pentestMin !== '') filters.pentest_min = pentestMin;
            if (pentestMax !== '') filters.pentest_max = pentestMax;
            return filters;
        }

        /** Charge les entreprises avec les filtres courants (côté serveur). */
        async function loadEntreprises() {
            try {
                const filters = getCurrentFilters();
                allEntreprises = await EntreprisesAPI.loadAll(filters);
                filteredEntreprises = [...allEntreprises];
                currentPage = 1;
                renderEntreprises();
            } catch (error) {
                console.error('Erreur lors du chargement des entreprises:', error);
                document.getElementById('entreprises-container').innerHTML =
                    '<p class="error">Erreur lors du chargement des entreprises</p>';
            }
        }

        /** Réapplique les filtres (recharge depuis l'API avec les critères du formulaire). */
        async function applyFilters() {
            await loadEntreprises();
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
            
            // Animer les graphiques circulaires après le rendu
            setTimeout(() => {
                const charts = document.querySelectorAll('.circular-chart-progress');
                charts.forEach((chart, index) => {
                    setTimeout(() => {
                        const targetOffset = chart.getAttribute('data-target-offset');
                        if (targetOffset) {
                            chart.style.strokeDashoffset = targetOffset;
                        }
                    }, index * 150);
                });
            }, 200);
        }
        
        // Fonction pour générer un graphique circulaire SVG
        function createCircularChart(score, label, color, size = 60) {
            if (score === null || score === undefined) {
                return `<div class="circular-chart-container circular-chart-na" style="width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center; color: #999; font-size: 0.75rem;">N/A</div>`;
            }
            
            const normalizedScore = Math.max(0, Math.min(100, score));
            const circumference = 2 * Math.PI * (size / 2 - 4);
            const offset = circumference - (normalizedScore / 100) * circumference;
            
            // Déterminer la couleur selon le score
            let strokeColor = color;
            if (!color) {
                if (normalizedScore >= 75) strokeColor = '#22c55e'; // vert
                else if (normalizedScore >= 50) strokeColor = '#3b82f6'; // bleu
                else if (normalizedScore >= 25) strokeColor = '#eab308'; // jaune
                else strokeColor = '#ef4444'; // rouge
            }
            
            const chartId = `chart-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            
            return `
                <div class="circular-chart-container" style="position: relative; width: ${size}px; height: ${size}px;">
                    <svg width="${size}" height="${size}" style="transform: rotate(-90deg);" class="circular-chart-svg">
                        <circle
                            cx="${size/2}"
                            cy="${size/2}"
                            r="${size/2 - 4}"
                            fill="none"
                            stroke="rgba(229, 231, 235, 0.3)"
                            stroke-width="6"
                            class="circular-chart-bg"
                        />
                        <circle
                            cx="${size/2}"
                            cy="${size/2}"
                            r="${size/2 - 4}"
                            fill="none"
                            stroke="${strokeColor}"
                            stroke-width="6"
                            stroke-dasharray="${circumference}"
                            stroke-dashoffset="${circumference}"
                            stroke-linecap="round"
                            class="circular-chart-progress"
                            data-chart-id="${chartId}"
                            data-target-offset="${offset}"
                            style="transition: stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1);"
                        />
                    </svg>
                    <div class="circular-chart-label">
                        <div class="circular-chart-value">${normalizedScore}</div>
                        <div class="circular-chart-text">${label}</div>
                    </div>
                </div>
            `;
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
            
            // Générer les graphiques circulaires pour Sécurité et SEO
            const hasSecurityScore = typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null;
            const hasSeoScore = typeof entreprise.score_seo !== 'undefined' && entreprise.score_seo !== null;
            const scoresSection = (hasSecurityScore || hasSeoScore) ? `
                <div class="card-scores-section">
                    ${hasSecurityScore ? `
                    <div class="score-chart-item">
                        ${createCircularChart(entreprise.score_securite, 'Sécurité', null, 60)}
                    </div>
                    ` : ''}
                    ${hasSeoScore ? `
                    <div class="score-chart-item">
                        ${createCircularChart(entreprise.score_seo, 'SEO', null, 60)}
                    </div>
                    ` : ''}
                </div>
            ` : '';
            
            return `
                <div class="entreprise-card" data-id="${entreprise.id}">
                    <div class="card-header-with-logo">
                        ${mainImage ? `
                        <div class="card-logo-container">
                            <img src="${mainImage}" alt="${Formatters.escapeHtml(entreprise.nom || 'Logo')}" class="card-logo" onerror="this.style.display='none'">
                        </div>
                        ` : ''}
                        <div class="card-header">
                            <div style="display:flex; align-items:center; gap:0.4rem; min-width:0;">
                                ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null && entreprise.score_pentest >= 40 ? `
                                <i class="fas fa-exclamation-triangle" style="color: ${entreprise.score_pentest >= 70 ? '#e74c3c' : '#f39c12'}; font-size: 1.1rem;" title="Score Pentest: ${entreprise.score_pentest}/100"></i>
                                ` : ''}
                                <h3 style="white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">${Formatters.escapeHtml(entreprise.nom || 'Sans nom')}</h3>
                            </div>
                            <button class="btn-favori ${entreprise.favori ? 'active' : ''}" data-id="${entreprise.id}" title="Favori">
                                <i class="fas fa-star"></i>
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        ${resumePreview ? `<p class="resume-preview" style="color: #666; font-size: 0.9rem; margin-bottom: 0.75rem; font-style: italic;">${Formatters.escapeHtml(resumePreview)}</p>` : ''}
                        ${entreprise.website ? `<p><strong>Site:</strong> <a href="${entreprise.website}" target="_blank">${Formatters.escapeHtml(entreprise.website)}</a></p>` : ''}
                        ${entreprise.secteur ? `<p><strong>Secteur:</strong> ${Formatters.escapeHtml(entreprise.secteur)}</p>` : ''}
                        ${scoresSection}
                        ${tagsHtml ? `<div class="tags-container">${tagsHtml}</div>` : ''}
                    </div>
                    <div class="card-footer">
                        <div class="card-footer-left">
                            <button class="btn-icon btn-groups" data-id="${entreprise.id}" title="Gérer les groupes">
                                <i class="fas fa-layer-group"></i>
                            </button>
                        </div>
                        <div class="card-footer-right">
                            <button class="btn btn-small btn-primary btn-view-details" data-id="${entreprise.id}" title="Voir détails"><i class="fas fa-eye"></i> Voir détails</button>
                            <button class="btn btn-small btn-danger btn-delete-entreprise" data-id="${entreprise.id}" data-name="${Formatters.escapeHtml(entreprise.nom || 'Sans nom')}" title="Supprimer"><i class="fas fa-trash"></i></button>
                        </div>
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
                        <button class="btn-icon btn-groups" data-id="${entreprise.id}" title="Gérer les groupes"><i class="fas fa-layer-group"></i></button>
                        <button class="btn-favori ${entreprise.favori ? 'active' : ''}" data-id="${entreprise.id}" title="Favori"><i class="fas fa-star"></i></button>
                        <button class="btn btn-small btn-primary btn-view-details" data-id="${entreprise.id}" title="Voir détails"><i class="fas fa-eye"></i> Détails</button>
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
            const groupsBtn = document.querySelector(`.btn-groups[data-id="${entrepriseId}"]`);
            if (groupsBtn) {
                groupsBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await openGroupsDropdown(entrepriseId, groupsBtn);
                });
            }
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
                            await applyFilters();
                            Notifications.show('Entreprise supprimée', 'success');
                        } catch (error) {
                            console.error('Erreur:', error);
                            Notifications.show('Erreur lors de la suppression', 'error');
                        }
                    }
                });
            }
        }

        async function openGroupsDropdown(entrepriseId, anchorEl) {
            // Fermer un éventuel menu déjà ouvert
            document.querySelectorAll('.group-dropdown').forEach(el => {
                try {
                    if (typeof el.__cleanup === 'function') {
                        el.__cleanup();
                    }
                } catch (e) {
                    // ignore
                }
                el.remove();
            });

            const rect = anchorEl.getBoundingClientRect();
            const dropdown = document.createElement('div');
            dropdown.className = 'group-dropdown';
            dropdown.dataset.entrepriseId = String(entrepriseId);
            dropdown.innerHTML = `
                <div class="group-dropdown-inner">
                    <div class="group-dropdown-header">
                        <span class="group-dropdown-title">Groupes de l'entreprise</span>
                        <button type="button" class="group-dropdown-close" aria-label="Fermer">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="group-dropdown-section">
                        <p class="group-dropdown-label">Ajouter / retirer des groupes</p>
                        <div class="group-list" data-role="group-list">
                            <div class="group-list-empty">Chargement des groupes...</div>
                        </div>
                    </div>
                    <div class="group-dropdown-section group-dropdown-section-create">
                        <p class="group-dropdown-label">Créer un nouveau groupe</p>
                        <form class="group-create-form">
                            <input type="text" name="nom" class="form-input group-create-input" placeholder="Nom du groupe" autocomplete="off">
                            <button type="submit" class="btn btn-small btn-primary group-create-btn">Créer</button>
                        </form>
                    </div>
                </div>
            `;

            document.body.appendChild(dropdown);

            const top = window.scrollY + rect.bottom + 8;
            const left = Math.min(window.scrollX + rect.left, window.innerWidth - 280);
            dropdown.style.top = `${top}px`;
            dropdown.style.left = `${left}px`;

            const cleanup = () => {
                document.removeEventListener('pointerdown', onPointerDown, true);
                document.removeEventListener('keydown', onKeyDown, true);
            };

            const closeDropdown = () => {
                cleanup();
                dropdown.remove();
            };

            const onPointerDown = (e) => {
                const target = e.target;
                if (!dropdown.contains(target) && !(anchorEl && anchorEl.contains(target))) {
                    closeDropdown();
                }
            };

            const onKeyDown = (e) => {
                if (e.key === 'Escape') {
                    closeDropdown();
                }
            };

            // Permet de nettoyer quand on ferme en ouvrant un autre dropdown
            dropdown.__cleanup = cleanup;

            // Fermer au clic en dehors + touche Échap
            setTimeout(() => {
                document.addEventListener('pointerdown', onPointerDown, true);
            }, 0);
            document.addEventListener('keydown', onKeyDown, true);

            const closeBtn = dropdown.querySelector('.group-dropdown-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => closeDropdown());
            }

            const createForm = dropdown.querySelector('.group-create-form');
            if (createForm) {
                createForm.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    const input = createForm.querySelector('.group-create-input');
                    const nom = input.value.trim();
                    if (!nom) {
                        Notifications.show('Le nom du groupe est requis', 'warning');
                        return;
                    }
                    try {
                        // Création du groupe (la réponse peut varier entre dev/prod, on ne dépend pas de groupe.id ici)
                        await EntreprisesAPI.createGroupe({ nom });
                        // Invalider le cache pour toutes les entreprises :
                        Object.keys(entrepriseGroupsCache).forEach(k => {
                            entrepriseGroupsCache[k] = null;
                        });
                        // Recharger la liste puis essayer d'attacher automatiquement l'entreprise
                        await loadGroupsIntoDropdown(entrepriseId, dropdown, true);
                        let autoAttached = false;
                        const items = dropdown.querySelectorAll('.group-item');
                        items.forEach((item) => {
                            if (autoAttached) return;
                            const nameEl = item.querySelector('.group-name');
                            if (nameEl && nameEl.textContent.trim() === nom.trim()) {
                                // Si pas déjà actif, on déclenche le clic pour utiliser la logique existante
                                if (!item.classList.contains('active')) {
                                    item.click();
                                }
                                autoAttached = true;
                            }
                        });
                        if (autoAttached) {
                            Notifications.show('Groupe créé et entreprise ajoutée', 'success');
                        } else {
                            Notifications.show('Groupe créé. L\'entreprise n\'a pas été ajoutée au groupe.', 'warning');
                        }
                        input.value = '';
                    } catch (error) {
                        console.error(error);
                        Notifications.show('Erreur lors de la création du groupe', 'error');
                        await loadGroupsIntoDropdown(entrepriseId, dropdown, true);
                    }
                });
            }

            await loadGroupsIntoDropdown(entrepriseId, dropdown);
        }

        async function loadGroupsIntoDropdown(entrepriseId, dropdown, forceRefresh) {
            const listEl = dropdown && dropdown.querySelector ? dropdown.querySelector('[data-role="group-list"]') : null;
            if (!listEl) return;

            try {
                if (forceRefresh) {
                    entrepriseGroupsCache[entrepriseId] = null;
                }
                let groupes = entrepriseGroupsCache[entrepriseId];
                if (!groupes) {
                    groupes = await EntreprisesAPI.loadGroupes(entrepriseId);
                    entrepriseGroupsCache[entrepriseId] = groupes;
                }

                if (!groupes || groupes.length === 0) {
                    listEl.innerHTML = '<div class="group-list-empty">Aucun groupe pour le moment.</div>';
                    return;
                }

                listEl.innerHTML = groupes.map(g => `
                    <div class="group-item ${g.is_member ? 'active' : ''}" data-group-id="${g.id}">
                        <div class="group-item-main">
                            <span class="group-dot" style="background-color:${g.couleur || '#4b5563'};"></span>
                            <span class="group-name">${Formatters.escapeHtml(g.nom || '')}</span>
                            ${typeof g.entreprises_count !== 'undefined' ? `<span class="group-count">${g.entreprises_count}</span>` : ''}
                        </div>
                        <div class="group-item-actions">
                            ${g.is_member ? '<span class="group-badge">Dans le groupe</span>' : ''}
                            <button type="button" class="group-delete-btn" title="Supprimer le groupe"><i class="fas fa-trash"></i></button>
                        </div>
                    </div>
                `).join('');

                // Clic sur toute la ligne pour ajouter / retirer
                listEl.querySelectorAll('.group-item').forEach(item => {
                    item.addEventListener('click', async (e) => {
                        // Ne pas interpréter le clic sur le bouton poubelle
                        if (e.target.closest('.group-delete-btn')) {
                            return;
                        }
                        const groupId = parseInt(item.dataset.groupId, 10);
                        const isActive = item.classList.contains('active');
                        try {
                            if (isActive) {
                                await EntreprisesAPI.removeEntrepriseFromGroupe(entrepriseId, groupId);
                                Notifications.show('Entreprise retirée du groupe', 'success');
                            } else {
                                await EntreprisesAPI.addEntrepriseToGroupe(entrepriseId, groupId);
                                Notifications.show('Entreprise ajoutée au groupe', 'success');
                            }
                            // Invalider le cache pour toutes les entreprises
                            Object.keys(entrepriseGroupsCache).forEach(k => {
                                entrepriseGroupsCache[k] = null;
                            });
                            await loadGroupsIntoDropdown(entrepriseId, dropdown);
                        } catch (error) {
                            console.error(error);
                            Notifications.show('Erreur lors de la mise à jour du groupe', 'error');
                        }
                    });
                });

                listEl.querySelectorAll('.group-delete-btn').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        const item = btn.closest('.group-item');
                        if (!item) return;
                        const groupId = parseInt(item.dataset.groupId, 10);
                        if (!confirm('Supprimer ce groupe pour toutes les entreprises ?')) {
                            return;
                        }
                        try {
                            await EntreprisesAPI.deleteGroupe(groupId);
                            Object.keys(entrepriseGroupsCache).forEach(k => {
                                entrepriseGroupsCache[k] = null;
                            });
                            Notifications.show('Groupe supprimé', 'success');
                            await loadGroupsIntoDropdown(entrepriseId, dropdown);
                        } catch (error) {
                            console.error(error);
                            Notifications.show('Erreur lors de la suppression du groupe', 'error');
                        }
                    });
                });
            } catch (error) {
                console.error(error);
                listEl.innerHTML = '<div class="group-list-empty error">Erreur lors du chargement des groupes.</div>';
            }
        }
        
        function setupEventListeners() {
            const debouncedApplyFilters = debounceFn(applyFilters, 300);

            // Recherche texte en temps réel
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.addEventListener('input', () => debouncedApplyFilters());
            }

            // Changement des filtres avancés => rafraîchissement auto
            const advancedFilterIds = [
                'filter-secteur',
                'filter-statut',
                'filter-opportunite',
                'filter-security-min',
                'filter-security-max',
                'filter-pentest-min',
                'filter-pentest-max'
            ];

            advancedFilterIds.forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.addEventListener('change', () => {
                        updateAdvancedFiltersBadge();
                        debouncedApplyFilters();
                    });
                }
            });

            const favoriCheckbox = document.getElementById('filter-favori');
            if (favoriCheckbox) {
                favoriCheckbox.addEventListener('change', () => {
                    updateAdvancedFiltersBadge();
                    debouncedApplyFilters();
                });
            }
            
            // Ouverture / fermeture des filtres avancés
            const advancedFiltersEl = document.getElementById('advanced-filters');
            const toggleBtn = document.getElementById('btn-toggle-advanced-filters');
            if (advancedFiltersEl && toggleBtn) {
                toggleBtn.addEventListener('click', () => {
                    advancedFiltersEl.classList.toggle('collapsed');
                    toggleBtn.classList.toggle('filters-toggle-open');
                });
            }
            
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

        /** Met à jour le badge qui indique le nombre de filtres avancés actifs. */
        function updateAdvancedFiltersBadge() {
            const badge = document.getElementById('active-filters-count');
            const toggleBtn = document.getElementById('btn-toggle-advanced-filters');
            if (!badge || !toggleBtn) {
                return;
            }

            let count = 0;
            const secteur = document.getElementById('filter-secteur')?.value;
            const statut = document.getElementById('filter-statut')?.value;
            const opportunite = document.getElementById('filter-opportunite')?.value;
            const favori = document.getElementById('filter-favori')?.checked;
            const securityMin = document.getElementById('filter-security-min')?.value;
            const securityMax = document.getElementById('filter-security-max')?.value;
            const pentestMin = document.getElementById('filter-pentest-min')?.value;
            const pentestMax = document.getElementById('filter-pentest-max')?.value;

            if (secteur) count += 1;
            if (statut) count += 1;
            if (opportunite) count += 1;
            if (favori) count += 1;
            if (securityMin) count += 1;
            if (securityMax) count += 1;
            if (pentestMin) count += 1;
            if (pentestMax) count += 1;

            if (count > 0) {
                badge.textContent = String(count);
                badge.style.display = 'inline-flex';
                toggleBtn.classList.add('filters-toggle-open');
            } else {
                badge.style.display = 'none';
                toggleBtn.classList.remove('filters-toggle-open');
            }
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
                        <button class="tabs-arrow tabs-arrow-left" type="button" aria-label="Onglets précédents">
                            <i class="fas fa-chevron-left"></i>
                        </button>
                        <div class="tabs-header-scroll">
                            <button class="tab-btn active" data-tab="info">Info</button>
                            <button class="tab-btn" data-tab="images">Images (${nbImages})</button>
                            <button class="tab-btn" data-tab="pages">Pages (${nbPages})</button>
                            <button class="tab-btn" data-tab="scraping">Résultats scraping</button>
                            <button class="tab-btn" data-tab="technique">Analyse technique</button>
                            <button class="tab-btn" data-tab="seo">Analyse SEO</button>
                            <button class="tab-btn" data-tab="osint">Analyse OSINT</button>
                            <button class="tab-btn" data-tab="pentest">Analyse Pentest</button>
                        </div>
                        <button class="tabs-arrow tabs-arrow-right" type="button" aria-label="Onglets suivants">
                            <i class="fas fa-chevron-right"></i>
                        </button>
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
                                <div class="scraping-results-header">
                                    <div class="scraping-results-title-row">
                                        <h3 class="scraping-results-title">
                                            <i class="fas fa-spider"></i>
                                            Résultats du scraping
                                        </h3>
                                    </div>
                                    <div id="scraping-stats" class="scraping-stats-summary">
                                        <!-- Les statistiques seront injectées ici -->
                                    </div>
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

                        <div class="tab-panel" id="tab-seo">
                            <div id="seo-results" class="analysis-results">
                                <div id="seo-results-content">Chargement de l'analyse SEO...</div>
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
            const modalBody = document.getElementById('modal-entreprise-body');
            
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

            // Initialiser l'état des flèches d'onglets (visible/caché selon le scroll possible)
            if (modalBody) {
                const scrollContainer = modalBody.querySelector('.tabs-header-scroll');
                const leftArrowEl = modalBody.querySelector('.tabs-arrow-left');
                const rightArrowEl = modalBody.querySelector('.tabs-arrow-right');

                const updateTabArrows = () => {
                    if (!scrollContainer || !leftArrowEl || !rightArrowEl) return;
                    const maxScroll = scrollContainer.scrollWidth - scrollContainer.clientWidth - 1;
                    const atStart = scrollContainer.scrollLeft <= 1;
                    const atEnd = scrollContainer.scrollLeft >= maxScroll;
                    const noScroll = maxScroll <= 0;
                    leftArrowEl.classList.toggle('tabs-arrow-hidden', atStart || noScroll);
                    rightArrowEl.classList.toggle('tabs-arrow-hidden', atEnd || noScroll);
                };

                if (scrollContainer) {
                    scrollContainer.addEventListener('scroll', updateTabArrows);
                    window.addEventListener('resize', updateTabArrows);
                    setTimeout(updateTabArrows, 0);
                }
            }
            
            if (modalBody) {
                modalBody.addEventListener('click', async (e) => {
                    // Flèches de défilement des onglets
                    const leftArrow = e.target.closest('.tabs-arrow-left');
                    const rightArrow = e.target.closest('.tabs-arrow-right');
                    if (leftArrow || rightArrow) {
                        const scrollContainer = modalBody.querySelector('.tabs-header-scroll');
                        if (scrollContainer) {
                            const delta = 160;
                            const direction = rightArrow ? 1 : -1;
                            scrollContainer.scrollBy({ left: direction * delta, behavior: 'smooth' });
                        }
                        return;
                    }

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
                    const activePanel = scrapingResults.querySelector('.tab-content.active[id^="tab-"][id$="-modal"]');
                    const tabName = activePanel ? activePanel.id.replace('tab-','').replace('-modal','') : null;
                    if (tabName) {
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
                            const activePanel = scrapingResults.querySelector('.tab-content.active[id^="tab-"][id$="-modal"]');
                            const tabName = activePanel ? activePanel.id.replace('tab-','').replace('-modal','') : null;
                            if (tabName) {
                                filterScrapingResults(tabName, '');
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

            const seoTab = document.querySelector('.tab-btn[data-tab="seo"]');
            if (seoTab) {
                seoTab.addEventListener('click', () => {
                    if (currentModalEntrepriseId) {
                        loadSEOAnalysis(currentModalEntrepriseId);
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

        /**
         * Charge et affiche l'analyse SEO détaillée pour une entreprise dans la modale.
         * @param {number} entrepriseId
         */
        async function loadSEOAnalysis(entrepriseId) {
            const resultsContent = document.getElementById('seo-results-content');
            if (!resultsContent) return;
            
            try {
                resultsContent.innerHTML = 'Chargement...';
                const response = await fetch(`/api/entreprise/${entrepriseId}/analyse-seo`);
                if (!response.ok) {
                    if (response.status === 404) {
                        resultsContent.innerHTML = '<p class="empty-state">Aucune analyse SEO disponible pour le moment.</p>';
                    } else {
                        resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse SEO</p>';
                    }
                    return;
                }
                
                const analysis = await response.json();
                resultsContent.innerHTML = renderSEOExpertise(analysis);
            } catch (error) {
                console.error('Erreur lors du chargement de l\'analyse SEO:', error);
                resultsContent.innerHTML = '<p class="error">Erreur lors du chargement de l\'analyse SEO</p>';
            }
        }
        /**
         * Génère le HTML de l'expertise SEO détaillée pour une analyse.
         * Reprend la logique principale de rendu de la page d'analyses SEO,
         * mais adaptée à l'affichage dans la modale entreprise.
         * @param {Object} analysis
         * @returns {string}
         */
        function renderSEOExpertise(analysis) {
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
                console.error('Erreur parsing JSON SEO:', e);
            }
            
            const score = analysis.score || 0;
            const scoreClass = score >= 80 ? 'score-excellent' : score >= 60 ? 'score-good' : score >= 40 ? 'score-medium' : 'score-low';
            
            return `
                <div class="seo-details">
                    <div class="seo-score-section">
                        <h3>Score SEO global</h3>
                        <div class="score-display ${scoreClass}">
                            <span class="score-value">${score}/100</span>
                        </div>
                        ${summary.main_message ? `<p class="seo-summary-main">${Formatters.escapeHtml(summary.main_message)}</p>` : ''}
                    </div>
                    
                    ${Object.keys(metaTags).length > 0 ? `
                    <div class="seo-section">
                        <h3>Meta tags principaux</h3>
                        <dl class="meta-tags-list">
                            ${Object.entries(metaTags).map(([key, value]) => `
                                <dt>${Formatters.escapeHtml(key)}</dt>
                                <dd>${Formatters.escapeHtml(String(value))}</dd>
                            `).join('')}
                        </dl>
                    </div>
                    ` : ''}
                    
                    ${Object.keys(structure).length > 0 ? `
                    <div class="seo-section">
                        <h3>Structure de la page</h3>
                        <ul class="structure-list">
                            ${structure.h1_count !== undefined ? `<li><strong>H1:</strong> ${structure.h1_count}</li>` : ''}
                            ${structure.h2_count !== undefined ? `<li><strong>H2:</strong> ${structure.h2_count}</li>` : ''}
                            ${structure.h3_count !== undefined ? `<li><strong>H3:</strong> ${structure.h3_count}</li>` : ''}
                            ${structure.images_total !== undefined ? `<li><strong>Images:</strong> ${structure.images_total} (dont ${structure.images_without_alt || 0} sans attribut alt)</li>` : ''}
                            ${structure.internal_links_count !== undefined ? `<li><strong>Liens internes:</strong> ${structure.internal_links_count}</li>` : ''}
                            ${structure.external_links_count !== undefined ? `<li><strong>Liens externes:</strong> ${structure.external_links_count}</li>` : ''}
                        </ul>
                    </div>
                    ` : ''}
                    
                    ${lighthouse ? `
                    <div class="seo-section">
                        <h3>Scores Lighthouse</h3>
                        <ul class="lighthouse-scores">
                            ${lighthouse.score !== undefined ? `<li><strong>Score SEO:</strong> ${Math.round(lighthouse.score * 100)}/100</li>` : ''}
                            ${lighthouse.performance_score !== undefined ? `<li><strong>Performance:</strong> ${Math.round(lighthouse.performance_score * 100)}/100</li>` : ''}
                            ${lighthouse.accessibility_score !== undefined ? `<li><strong>Accessibilité:</strong> ${Math.round(lighthouse.accessibility_score * 100)}/100</li>` : ''}
                        </ul>
                    </div>
                    ` : ''}
                    
                    ${issues.length > 0 ? `
                    <div class="seo-section">
                        <h3>Problèmes SEO clés</h3>
                        <ul class="issues-list">
                            ${issues.map(issue => `
                                <li class="issue-${issue.type || 'info'}">
                                    <strong>${Formatters.escapeHtml(issue.category || 'Général')}:</strong>
                                    ${Formatters.escapeHtml(issue.message || '')}
                                    ${issue.impact ? `<span class="impact-${issue.impact}">(${Formatters.escapeHtml(issue.impact)})</span>` : ''}
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                    ` : ''}
                </div>
            `;
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
                        <div class="page-card page-card-og">
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

