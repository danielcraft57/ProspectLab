/**
 * Carte des entreprises – visualisation, sélection et gestion des groupes
 * Utilise Leaflet et la même API groupes que les campagnes.
 */

(function() {
    'use strict';

    let map;
    let markers = [];
    let currentLayer = null;
    let displayedEntreprises = [];
    let selectionMode = false;
    const selectedIds = new Set();
    let groupes = [];

    document.addEventListener('DOMContentLoaded', () => {
        initMap();
        loadSecteurs();
        loadGroupes();
        setupEventListeners();
        loadAllEntreprises();
    });

    function initMap() {
        map = L.map('map').setView([49.1193, 6.1757], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        map.on('click', function(e) {
            const latInput = document.getElementById('search-lat');
            const lngInput = document.getElementById('search-lng');
            if (latInput) latInput.value = e.latlng.lat.toFixed(6);
            if (lngInput) lngInput.value = e.latlng.lng.toFixed(6);
        });
    }

    async function loadSecteurs() {
        try {
            const response = await fetch('/api/entreprises');
            const entreprises = await response.json();
            const secteurs = [...new Set(entreprises.map(e => e.secteur).filter(Boolean))].sort();
            const select = document.getElementById('filter-secteur');
            if (!select) return;
            secteurs.forEach(secteur => {
                const option = document.createElement('option');
                option.value = secteur;
                option.textContent = secteur;
                select.appendChild(option);
            });
        } catch (err) {
            console.error('Erreur chargement secteurs:', err);
        }
    }

    async function loadGroupes() {
        try {
            if (typeof window.EntreprisesAPI !== 'undefined') {
                groupes = await window.EntreprisesAPI.loadGroupes();
            } else {
                const response = await fetch('/api/groupes-entreprises');
                groupes = await response.json();
            }
            renderGroupsDropdown();
        } catch (err) {
            console.error('Erreur chargement groupes:', err);
            groupes = [];
            renderGroupsDropdown();
        }
    }

    function renderGroupsDropdown() {
        const listEl = document.getElementById('groups-dropdown-list');
        const emptyEl = document.getElementById('groups-dropdown-empty');
        if (!listEl) return;

        listEl.innerHTML = '';
        if (!groupes || groupes.length === 0) {
            if (emptyEl) {
                emptyEl.style.display = 'block';
                emptyEl.textContent = 'Aucun groupe. Créez-en un avec « Créer un groupe ».';
            }
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';

        groupes.forEach(g => {
            const item = document.createElement('div');
            item.className = 'group-item-map';
            item.setAttribute('role', 'menuitem');
            item.dataset.groupeId = g.id;
            const couleur = g.couleur || '#6366f1';
            const count = g.entreprises_count != null ? g.entreprises_count : 0;
            item.innerHTML = '<span class="group-dot" style="background-color:' + escapeHtml(couleur) + '"></span>' +
                '<span class="group-name">' + escapeHtml(g.nom || 'Sans nom') + '</span>' +
                '<span class="group-count">' + count + '</span>';
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                addSelectedToGroupe(parseInt(g.id, 10));
                closeGroupsDropdown();
            });
            listEl.appendChild(item);
        });
    }

    function setupEventListeners() {
        const btnSearch = document.getElementById('btn-search-nearby');
        const btnLoadAll = document.getElementById('btn-load-all');
        const filterSecteur = document.getElementById('filter-secteur');
        const selectionToggle = document.getElementById('selection-mode-toggle');
        const btnAddToGroup = document.getElementById('btn-add-to-group');
        const btnCreateGroup = document.getElementById('btn-create-group');
        const btnClearSelection = document.getElementById('btn-clear-selection');
        const panel = document.getElementById('groups-dropdown-panel');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const createInline = document.getElementById('carte-create-group-inline');
        const newGroupName = document.getElementById('new-group-name');
        const btnConfirmCreate = document.getElementById('btn-confirm-create-group');
        const btnCancelCreate = document.getElementById('btn-cancel-create-group');

        if (btnSearch) btnSearch.addEventListener('click', searchNearby);
        if (btnLoadAll) btnLoadAll.addEventListener('click', loadAllEntreprises);
        if (filterSecteur) filterSecteur.addEventListener('change', filterBySecteur);

        if (selectionToggle) {
            selectionToggle.addEventListener('click', () => {
                selectionMode = !selectionMode;
                selectionToggle.classList.toggle('is-active', selectionMode);
                selectionToggle.setAttribute('aria-pressed', selectionMode);
                refreshResultsList();
                updateSelectionBar();
            });
        }

        if (btnAddToGroup) {
            btnAddToGroup.addEventListener('click', (e) => {
                e.stopPropagation();
                if (selectedIds.size === 0) {
                    if (window.Notifications) window.Notifications.show('Sélectionnez au moins une entreprise', 'warning');
                    return;
                }
                const isOpen = panel && !panel.hidden;
                if (isOpen) closeGroupsDropdown();
                else openGroupsDropdown();
            });
        }

        if (btnCreateGroup) {
            btnCreateGroup.addEventListener('click', () => {
                if (selectedIds.size === 0) {
                    if (window.Notifications) window.Notifications.show('Sélectionnez au moins une entreprise', 'warning');
                    return;
                }
                if (createInline) createInline.style.display = 'flex';
                if (newGroupName) {
                    newGroupName.value = '';
                    newGroupName.focus();
                }
            });
        }

        if (btnClearSelection) {
            btnClearSelection.addEventListener('click', clearSelection);
        }

        if (btnConfirmCreate) {
            btnConfirmCreate.addEventListener('click', confirmCreateGroup);
        }
        if (btnCancelCreate) {
            btnCancelCreate.addEventListener('click', () => {
                if (createInline) createInline.style.display = 'none';
                if (newGroupName) newGroupName.value = '';
            });
        }
        if (newGroupName) {
            newGroupName.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') confirmCreateGroup();
            });
        }

        document.addEventListener('click', (e) => {
            if (panel && !panel.hidden && btnAddToGroup && !panel.contains(e.target) && !btnAddToGroup.contains(e.target)) {
                closeGroupsDropdown();
            }
        });

        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                const sidebar = document.getElementById('carte-sidebar');
                if (sidebar) {
                    sidebar.classList.toggle('carte-sidebar-collapsed');
                    const icon = sidebarToggle.querySelector('i');
                    if (icon) {
                        icon.classList.toggle('fa-chevron-right', !sidebar.classList.contains('carte-sidebar-collapsed'));
                        icon.classList.toggle('fa-chevron-left', sidebar.classList.contains('carte-sidebar-collapsed'));
                    }
                }
            });
        }
    }

    function openGroupsDropdown() {
        const panel = document.getElementById('groups-dropdown-panel');
        const btn = document.getElementById('btn-add-to-group');
        if (panel && btn) {
            panel.hidden = false;
            btn.setAttribute('aria-expanded', 'true');
        }
    }

    function closeGroupsDropdown() {
        const panel = document.getElementById('groups-dropdown-panel');
        const btn = document.getElementById('btn-add-to-group');
        if (panel && btn) {
            panel.hidden = true;
            btn.setAttribute('aria-expanded', 'false');
        }
    }

    async function addSelectedToGroupe(groupeId) {
        const ids = Array.from(selectedIds);
        const api = window.EntreprisesAPI;
        if (!api) {
            if (window.Notifications) window.Notifications.show('API entreprises non disponible', 'error');
            return;
        }
        let done = 0;
        let err = false;
        for (const id of ids) {
            try {
                await api.addEntrepriseToGroupe(id, groupeId);
                done++;
            } catch (e) {
                err = true;
            }
        }
        await loadGroupes();
        if (window.Notifications) {
            if (err) window.Notifications.show(done + ' ajoutée(s), certaines erreurs possibles', 'warning');
            else window.Notifications.show(done + ' entreprise(s) ajoutée(s) au groupe', 'success');
        }
    }

    function clearSelection() {
        selectedIds.clear();
        refreshResultsList();
        updateSelectionBar();
        updateMarkersSelection();
    }

    async function confirmCreateGroup() {
        const nameInput = document.getElementById('new-group-name');
        const name = (nameInput && nameInput.value || '').trim();
        if (!name) {
            if (window.Notifications) window.Notifications.show('Indiquez un nom pour le groupe', 'warning');
            return;
        }
        const api = window.EntreprisesAPI;
        if (!api) {
            if (window.Notifications) window.Notifications.show('API entreprises non disponible', 'error');
            return;
        }
        try {
            const groupe = await api.createGroupe({ nom: name });
            const groupeId = groupe.id;
            const ids = Array.from(selectedIds);
            for (const id of ids) {
                await api.addEntrepriseToGroupe(id, groupeId);
            }
            await loadGroupes();
            document.getElementById('carte-create-group-inline').style.display = 'none';
            nameInput.value = '';
            if (window.Notifications) window.Notifications.show('Groupe créé et entreprises ajoutées', 'success');
        } catch (e) {
            if (window.Notifications) window.Notifications.show('Erreur : ' + (e.message || 'création du groupe'), 'error');
        }
    }

    async function searchNearby() {
        const lat = parseFloat(document.getElementById('search-lat').value);
        const lng = parseFloat(document.getElementById('search-lng').value);
        const radius = parseFloat(document.getElementById('search-radius').value);
        const secteur = document.getElementById('filter-secteur').value;

        if (!lat || !lng || isNaN(lat) || isNaN(lng)) {
            if (window.Notifications) window.Notifications.show('Définissez un point (cliquez sur la carte ou saisissez lat/lng)', 'warning');
            return;
        }

        try {
            let url = '/api/entreprises/nearby?latitude=' + lat + '&longitude=' + lng + '&radius_km=' + radius;
            if (secteur) url += '&secteur=' + encodeURIComponent(secteur);
            const response = await fetch(url);
            const data = await response.json();

            if (data.success && data.entreprises) {
                displayEntreprises(data.entreprises, lat, lng);
                map.setView([lat, lng], 12);
                if (currentLayer) map.removeLayer(currentLayer);
                currentLayer = L.circle([lat, lng], {
                    radius: radius * 1000,
                    color: '#6366f1',
                    fillColor: '#6366f1',
                    fillOpacity: 0.15
                }).addTo(map);
            } else {
                if (window.Notifications) window.Notifications.show('Aucun résultat ou erreur serveur', 'info');
            }
        } catch (err) {
            console.error(err);
            if (window.Notifications) window.Notifications.show('Erreur lors de la recherche', 'error');
        }
    }

    async function loadAllEntreprises() {
        try {
            const response = await fetch('/api/entreprises');
            const entreprises = await response.json();
            const withCoords = entreprises.filter(e => e.latitude && e.longitude);
            displayEntreprises(withCoords);
            if (currentLayer) {
                map.removeLayer(currentLayer);
                currentLayer = null;
            }
            if (withCoords.length > 0 && markers.length > 0) {
                const group = new L.featureGroup(markers);
                map.fitBounds(group.getBounds().pad(0.1));
            }
        } catch (err) {
            console.error(err);
            if (window.Notifications) window.Notifications.show('Erreur lors du chargement', 'error');
        }
    }

    function filterBySecteur() {
        const secteur = document.getElementById('filter-secteur').value;
        markers.forEach(marker => {
            const ent = marker.entreprise;
            if (!ent) return;
            if (!secteur || ent.secteur === secteur) {
                if (!map.hasLayer(marker)) marker.addTo(map);
            } else {
                if (map.hasLayer(marker)) map.removeLayer(marker);
            }
        });
    }

    function displayEntreprises(entreprises) {
        clearMarkers();
        displayedEntreprises = Array.isArray(entreprises) ? entreprises : [];

        const countEl = document.getElementById('results-count');
        const listEl = document.getElementById('results-list');
        const emptyEl = document.getElementById('results-empty');

        if (countEl) {
            const num = displayedEntreprises.length;
            countEl.innerHTML = '<span class="count-num">' + num + '</span> entreprise' + (num !== 1 ? 's' : '');
        }

        if (emptyEl) {
            emptyEl.style.display = displayedEntreprises.length === 0 ? 'flex' : 'none';
        }
        if (listEl) {
            listEl.style.display = displayedEntreprises.length === 0 ? 'none' : 'block';
            listEl.innerHTML = displayedEntreprises.map((e, i) => createEntrepriseCard(e, i)).join('');
        }

        displayedEntreprises.forEach((entreprise, index) => {
            const marker = L.marker([entreprise.latitude, entreprise.longitude], {
                alt: entreprise.nom || 'Entreprise'
            });
            const popupContent = createPopupContent(entreprise);
            const wrapper = document.createElement('div');
            wrapper.className = 'carte-popup';
            wrapper.innerHTML = popupContent;
            marker.bindPopup(wrapper, { className: 'carte-popup' });
            marker.entreprise = entreprise;
            marker.addTo(map);
            markers.push(marker);

            marker.on('popupopen', () => {
                if (marker._icon) marker._icon.classList.add('marker-selected');
            });
            marker.on('popupclose', () => {
                if (marker._icon) marker._icon.classList.remove('marker-selected');
            });
        });

        if (markers.length > 0) {
            const group = new L.featureGroup(markers);
            if (markers.length === 1) {
                map.setView([displayedEntreprises[0].latitude, displayedEntreprises[0].longitude], 13);
            } else {
                map.fitBounds(group.getBounds().pad(0.1));
            }
        }

        bindCardEvents();
        updateMarkersSelection();
    }

    function createPopupContent(entreprise) {
        const distance = entreprise.distance_km
            ? '<p class="distance-badge">Distance: ' + escapeHtml(String(entreprise.distance_km)) + ' km</p>'
            : '';
        return '<div class="info-popup">' +
            '<h4>' + escapeHtml(entreprise.nom || 'Sans nom') + '</h4>' +
            (entreprise.secteur ? '<p><strong>Secteur:</strong> ' + escapeHtml(entreprise.secteur) + '</p>' : '') +
            (entreprise.website ? '<p><strong>Site:</strong> <a href="' + escapeHtml(entreprise.website) + '" target="_blank" rel="noopener">' + escapeHtml(entreprise.website) + '</a></p>' : '') +
            (entreprise.telephone ? '<p><strong>Tél:</strong> ' + escapeHtml(entreprise.telephone) + '</p>' : '') +
            ((entreprise.address_1 || entreprise.address_2) ? '<p><strong>Adresse:</strong> ' + escapeHtml([entreprise.address_1, entreprise.address_2].filter(Boolean).join(', ')) + '</p>' : '') +
            (entreprise.note_google != null ? '<p><strong>Note Google:</strong> ' + escapeHtml(String(entreprise.note_google)) + '/5 (' + (entreprise.nb_avis_google || 0) + ' avis)</p>' : '') +
            distance +
            '</div>';
    }

    function createEntrepriseCard(entreprise, index) {
        const id = entreprise.id != null ? parseInt(entreprise.id, 10) : null;
        const hasId = id !== null && !isNaN(id);
        const checked = hasId && selectedIds.has(id) ? ' checked' : '';
        const selectedClass = hasId && selectedIds.has(id) ? ' is-selected' : '';
        const checkboxHtml = selectionMode && hasId
            ? '<input type="checkbox" class="card-checkbox" data-id="' + id + '" data-index="' + index + '"' + checked + ' aria-label="Sélectionner">'
            : '';
        const distanceBadge = entreprise.distance_km
            ? '<span class="badge badge-info">' + escapeHtml(String(entreprise.distance_km)) + ' km</span>'
            : '';
        const sectorMeta = entreprise.secteur ? '<p class="card-meta">' + escapeHtml(entreprise.secteur) + '</p>' : '';
        const badges = '<div class="card-badges">' + distanceBadge + '</div>';
        return '<div class="carte-entreprise-card' + selectedClass + '" data-id="' + (id != null ? id : '') + '" data-index="' + index + '" data-lat="' + entreprise.latitude + '" data-lng="' + entreprise.longitude + '">' +
            checkboxHtml +
            '<div class="card-content">' +
            '<div class="card-title">' + escapeHtml(entreprise.nom || 'Sans nom') + '</div>' +
            sectorMeta +
            badges +
            '</div></div>';
    }

    function bindCardEvents() {
        const listEl = document.getElementById('results-list');
        if (!listEl) return;

        listEl.querySelectorAll('.carte-entreprise-card').forEach(card => {
            const rawId = card.dataset.id;
            const id = rawId !== '' && rawId != null ? parseInt(rawId, 10) : null;
            const hasId = id !== null && !isNaN(id);
            const lat = parseFloat(card.dataset.lat);
            const lng = parseFloat(card.dataset.lng);
            const checkbox = card.querySelector('.card-checkbox');

            if (checkbox && hasId) {
                checkbox.addEventListener('click', (e) => e.stopPropagation());
                checkbox.addEventListener('change', () => {
                    if (checkbox.checked) selectedIds.add(id);
                    else selectedIds.delete(id);
                    card.classList.toggle('is-selected', selectedIds.has(id));
                    updateSelectionBar();
                    updateMarkersSelection();
                });
            }

            card.addEventListener('click', (e) => {
                if (checkbox && e.target === checkbox) return;
                if (selectionMode && checkbox && hasId) {
                    checkbox.checked = !checkbox.checked;
                    if (checkbox.checked) selectedIds.add(id);
                    else selectedIds.delete(id);
                    card.classList.toggle('is-selected', selectedIds.has(id));
                    updateSelectionBar();
                    updateMarkersSelection();
                } else {
                    focusOnEntreprise(lat, lng);
                }
            });
        });
    }

    function refreshResultsList() {
        const listEl = document.getElementById('results-list');
        if (!listEl || !displayedEntreprises.length) return;
        listEl.innerHTML = displayedEntreprises.map((e, i) => createEntrepriseCard(e, i)).join('');
        bindCardEvents();
    }

    function updateSelectionBar() {
        const bar = document.getElementById('selection-bar');
        const label = document.getElementById('selection-label');
        if (bar) bar.classList.toggle('is-visible', selectedIds.size > 0);
        if (label) label.textContent = selectedIds.size + ' sélectionnée(s)';
    }

    function updateMarkersSelection() {
        markers.forEach(marker => {
            const ent = marker.entreprise;
            if (!ent || !ent.id) return;
            if (marker._icon) {
                if (selectedIds.has(ent.id)) marker._icon.classList.add('marker-selected');
                else marker._icon.classList.remove('marker-selected');
            }
        });
    }

    function focusOnEntreprise(lat, lng) {
        map.setView([lat, lng], 15);
        markers.forEach(marker => {
            const ll = marker.getLatLng();
            if (Math.abs(ll.lat - lat) < 1e-6 && Math.abs(ll.lng - lng) < 1e-6) {
                marker.openPopup();
                if (marker._icon) marker._icon.classList.add('marker-selected');
            }
        });
    }

    function clearMarkers() {
        markers.forEach(marker => map.removeLayer(marker));
        markers = [];
    }

    function escapeHtml(text) {
        if (text == null) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    window.focusOnEntreprise = focusOnEntreprise;
})();
