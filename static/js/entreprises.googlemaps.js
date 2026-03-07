'use strict';

(function () {
    let map = null;
    let placesService = null;
    let infoWindow = null;
    let markers = [];

    const state = {
        items: [],
        pagination: null,
        isLoadingNextPage: false,
        entrepriseById: {}
    };

    function getEl(id) {
        return document.getElementById(id);
    }

    function showNotification(message, type) {
        if (window.Notifications && typeof window.Notifications.show === 'function') {
            window.Notifications.show(message, type || 'info');
        }
    }

    function clearMarkers() {
        markers.forEach(m => m.setMap(null));
        markers = [];
    }

    function updateResultsCount(count) {
        const el = getEl('gmap-results-count');
        if (!el) return;
        if (!count) {
            el.textContent = 'Aucun résultat pour le moment';
            return;
        }
        el.textContent = `${count} établissement${count > 1 ? 's' : ''} trouvé${count > 1 ? 's' : ''}`;
    }

    function toggleEmptyState(showEmpty) {
        const empty = getEl('gmap-results-empty');
        const list = getEl('gmap-results-list');
        if (!empty || !list) return;
        if (showEmpty) {
            empty.style.display = 'flex';
            list.style.display = 'none';
        } else {
            empty.style.display = 'none';
            list.style.display = 'grid';
        }
    }

    function normalizePlace(place, details) {
        const src = details || place || {};
        const geometry = src.geometry || place.geometry || {};
        const location = geometry.location || {};

        const address = src.formatted_address || place.formatted_address || '';
        const rating = typeof src.rating === 'number' ? src.rating : null;
        const reviewsCount = typeof src.user_ratings_total === 'number' ? src.user_ratings_total : null;
        const types = Array.isArray(src.types) ? src.types : (Array.isArray(place.types) ? place.types : []);

        // On ne retient que les vrais sites web (domicile de l'entreprise),
        // pas l'URL de la fiche Google Maps.
        const website = src.website || '';
        const phone = src.formatted_phone_number || src.international_phone_number || '';

        const lat = typeof location.lat === 'function' ? location.lat() : location.lat;
        const lng = typeof location.lng === 'function' ? location.lng() : location.lng;

        return {
            placeId: src.place_id || place.place_id,
            name: src.name || place.name || '',
            address,
            rating,
            reviewsCount,
            types,
            website,
            phone,
            lat,
            lng
        };
    }

    function createMarker(item, index) {
        if (!map || item.lat == null || item.lng == null) {
            return null;
        }
        const position = { lat: item.lat, lng: item.lng };
        const marker = new google.maps.Marker({
            map,
            position,
            title: item.name || '',
            label: String(index + 1)
        });

        marker.addListener('click', () => {
            openInfoWindow(item, marker);
            scrollToResult(index);
        });

        return marker;
    }

    function openInfoWindow(item, marker) {
        if (!map || !marker) return;
        if (!infoWindow) {
            infoWindow = new google.maps.InfoWindow();
        }
        const parts = [];
        parts.push(`<strong>${escapeHtml(item.name || '')}</strong>`);
        if (item.rating != null) {
            parts.push(`<div style="margin-top:2px;font-size:12px;color:#f59e0b;">★ ${item.rating.toFixed(1)} (${item.reviewsCount || 0})</div>`);
        }
        if (item.address) {
            parts.push(`<div style="margin-top:4px;font-size:12px;color:#4b5563;">${escapeHtml(item.address)}</div>`);
        }
        if (item.phone) {
            parts.push(`<div style="margin-top:2px;font-size:12px;color:#4b5563;">${escapeHtml(item.phone)}</div>`);
        }
        if (item.website) {
            const safeUrl = escapeAttribute(item.website);
            parts.push(`<div style="margin-top:4px;font-size:12px;"><a href="${safeUrl}" target="_blank" rel="noopener" style="color:#2563eb;">Site web</a></div>`);
        }
        infoWindow.setContent(parts.join(''));
        infoWindow.open(map, marker);
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    function escapeAttribute(text) {
        return escapeHtml(text).replace(/"/g, '&quot;');
    }

    function renderResults(items, options) {
        const opts = options || {};
        const append = !!opts.append;
        const list = getEl('gmap-results-list');
        if (!list) return;

        if (!append) {
            state.items = items || [];
            list.innerHTML = '';
        } else if (items && items.length) {
            state.items = state.items.concat(items);
        }

        const allItems = append ? items : (items || []);

        if (!state.items.length) {
            updateResultsCount(0);
            toggleEmptyState(true);
            return;
        }

        const startIndex = append ? state.items.length - allItems.length : 0;

        const html = allItems.map((item, idx) => {
            const index = startIndex + idx;
            const cat = Array.isArray(item.types) && item.types.length ? item.types[0].replace(/_/g, ' ') : '';
            const metaParts = [];
            if (cat) metaParts.push(cat);
            if (item.rating != null) metaParts.push(`★ ${item.rating.toFixed(1)}`);
            if (item.reviewsCount != null) metaParts.push(`${item.reviewsCount} avis`);

            return `
                <article class="gmap-result" data-index="${index}">
                    <div class="gmap-result-title">
                        <h3>${escapeHtml(item.name || '')}</h3>
                        ${item.rating != null ? `<div class="gmap-result-rating">★ ${item.rating.toFixed(1)}</div>` : ''}
                    </div>
                    ${metaParts.length ? `
                        <div class="gmap-result-meta">
                            ${metaParts.map(m => `<span>${escapeHtml(m)}</span>`).join('')}
                        </div>
                    ` : ''}
                    ${item.address ? `<div class="gmap-result-address">${escapeHtml(item.address)}</div>` : ''}
                    ${item.phone ? `<div class="gmap-result-phone">${escapeHtml(item.phone)}</div>` : ''}
                    ${item.website ? `<div class="gmap-result-website"><a href="${escapeAttribute(item.website)}" target="_blank" rel="noopener">${escapeHtml(item.website)}</a></div>` : ''}
                    <div class="gmap-result-actions">
                        <button type="button" class="btn btn-secondary btn-xs" data-role="import-place">Importer</button>
                        ${item.importStatus === 'created'
                            ? `<span class="gmap-result-import-status gmap-result-import-status-created">Importée (nouvelle)</span>`
                            : item.importStatus === 'existing'
                                ? `<span class="gmap-result-import-status gmap-result-import-status-existing">Déjà présente</span>`
                                : ''}
                    </div>
                </article>
            `;
        }).join('');

        if (append) {
            list.insertAdjacentHTML('beforeend', html);
        } else {
            list.innerHTML = html;
        }

        updateResultsCount(state.items.length);
        toggleEmptyState(false);

        list.querySelectorAll('.gmap-result').forEach(el => {
            el.addEventListener('click', () => {
                const indexStr = el.getAttribute('data-index');
                const idx = indexStr ? parseInt(indexStr, 10) : -1;
                if (idx >= 0 && markers[idx]) {
                    const item = state.items[idx];
                    map.panTo(markers[idx].getPosition());
                    map.setZoom(Math.max(map.getZoom(), 14));
                    openInfoWindow(item, markers[idx]);
                }
            });
        });
    }

    function scrollToResult(index) {
        const list = getEl('gmap-results-list');
        if (!list) return;
        const el = list.querySelector(`.gmap-result[data-index="${index}"]`);
        if (el && typeof el.scrollIntoView === 'function') {
            el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            el.classList.add('is-highlighted');
            setTimeout(() => el.classList.remove('is-highlighted'), 800);
        }
    }

    function performSearch() {
        const queryInput = getEl('gmap-query');
        const regionInput = getEl('gmap-region');
        if (!queryInput || !placesService) {
            return;
        }
        const query = (queryInput.value || '').trim();
        const region = (regionInput && regionInput.value || '').trim();

        if (!query) {
            showNotification('Saisissez une requête Google Maps (ex : boulangerie Paris).', 'warning');
            return;
        }

        clearMarkers();
        renderResults([]);
        toggleEmptyState(false);
        updateResultsCount(0);
        state.pagination = null;

        const request = { query: query };
        if (region) {
            request.region = region;
        }

        placesService.textSearch(request, (results, status, pagination) => {
            // Quel que soit le résultat, on considère que le chargement de page est terminé
            state.isLoadingNextPage = false;

            if (status !== google.maps.places.PlacesServiceStatus.OK || !results || !results.length) {
                console.error('[gmap] textSearch status:', status);
                // Si on a déjà des résultats (cas d'une page suivante), ne pas casser l'UI
                if (!state.items.length) {
                    showNotification('Aucun résultat trouvé ou erreur côté Google Maps.', 'warning');
                    renderResults([]);
                }
                state.pagination = null;
                return;
            }

            state.pagination = (pagination && pagination.hasNextPage) ? pagination : null;

            // Mémoriser la dernière recherche (Memento via Caretaker)
            try {
                if (window.Memento && window.MementoCaretaker) {
                    const memento = new window.Memento({ query, region, ts: Date.now() });
                    window.MementoCaretaker.save('gmap_last_search', memento);
                }
            } catch (e) {
                // stockage non critique
            }

            const limited = results;
            const bounds = new google.maps.LatLngBounds();

            const detailPromises = limited.map(place => {
                if (!place.place_id) {
                    return Promise.resolve({ place, details: null });
                }
                return new Promise(resolve => {
                    placesService.getDetails(
                        {
                            placeId: place.place_id,
                            fields: [
                                'name',
                                'formatted_address',
                                'geometry',
                                'rating',
                                'user_ratings_total',
                                'types',
                                'website',
                                'url',
                                'formatted_phone_number',
                                'international_phone_number',
                                'address_component'
                            ]
                        },
                        (details, st) => {
                            if (st === google.maps.places.PlacesServiceStatus.OK && details) {
                                resolve({ place, details });
                            } else {
                                resolve({ place, details: null });
                            }
                        }
                    );
                });
            });

            Promise.all(detailPromises).then(items => {
                // Normaliser tous les lieux puis filtrer ceux qui n'ont pas de site web
                const normalized = items
                    .map(({ place, details }) => normalizePlace(place, details))
                    .filter(item => item.website && String(item.website).trim() !== '');

                if (!normalized.length) {
                    showNotification('Aucun établissement avec site web trouvé pour cette recherche.', 'warning');
                    renderResults([]);
                    return;
                }

                normalized.forEach((item, index) => {
                    if (item.lat != null && item.lng != null) {
                        bounds.extend(new google.maps.LatLng(item.lat, item.lng));
                        const marker = createMarker(item, index);
                        if (marker) {
                            markers.push(marker);
                        } else {
                            markers.push(null);
                        }
                    } else {
                        markers.push(null);
                    }
                });

                if (!bounds.isEmpty()) {
                    map.fitBounds(bounds);
                }

                renderResults(normalized, { append: false });
            }).catch(err => {
                console.error('[gmap] Error while fetching details:', err);
                showNotification('Erreur lors de la récupération des détails des lieux.', 'error');
            });
        });
    }

    function clearSearch() {
        const queryInput = getEl('gmap-query');
        if (queryInput) {
            queryInput.value = '';
        }
        clearMarkers();
        renderResults([]);
        updateResultsCount(0);
        toggleEmptyState(true);
        state.pagination = null;
        state.isLoadingNextPage = false;
        if (infoWindow) {
            infoWindow.close();
        }
    }

    function loadMoreResults() {
        if (!state.pagination || !state.pagination.hasNextPage || state.isLoadingNextPage) {
            return;
        }
        state.isLoadingNextPage = true;
        showNotification('Chargement de résultats supplémentaires...', 'info');
        try {
            state.pagination.nextPage();
        } catch (e) {
            console.error('[gmap] Erreur lors du chargement de la page suivante:', e);
            state.isLoadingNextPage = false;
        }
    }

    function initMap() {
        const mapEl = getEl('gmap-map');
        if (!mapEl) {
            console.error('[gmap] Élément #gmap-map introuvable.');
            return;
        }
        if (!window.google || !google.maps || !google.maps.places) {
            console.error('[gmap] Bibliothèque Google Maps / Places non chargée.');
            showNotification('Impossible de charger Google Maps. Vérifiez votre clé API.', 'error');
            return;
        }

        map = new google.maps.Map(mapEl, {
            center: { lat: 48.8566, lng: 2.3522 }, // Paris par défaut
            zoom: 12,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: true
        });

        placesService = new google.maps.places.PlacesService(map);

        let lastZoom = map.getZoom();
        map.addListener('zoom_changed', () => {
            const newZoom = map.getZoom();
            if (newZoom < lastZoom && state.pagination && !state.isLoadingNextPage) {
                loadMoreResults();
            }
            lastZoom = newZoom;
        });
    }

    function initControls() {
        const searchBtn = getEl('gmap-search-btn');
        const clearBtn = getEl('gmap-clear-btn');
        const queryInput = getEl('gmap-query');
        const regionInput = getEl('gmap-region');

        if (searchBtn) {
            searchBtn.addEventListener('click', () => performSearch());
        }
        if (clearBtn) {
            clearBtn.addEventListener('click', () => clearSearch());
        }
        if (queryInput) {
            queryInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    performSearch();
                }
            });
        }

        // Restaurer la dernière recherche (Memento via Caretaker)
        try {
            if (window.MementoCaretaker) {
                const memento = window.MementoCaretaker.load('gmap_last_search');
                if (memento && memento.getState) {
                    const saved = memento.getState();
                    if (saved && typeof saved === 'object') {
                        if (queryInput && saved.query) {
                            queryInput.value = saved.query;
                        }
                        if (regionInput && saved.region) {
                            regionInput.value = saved.region;
                        }
                        if (saved.query) {
                            performSearch();
                        }
                    }
                }
            }
        } catch (e) {
            // en cas d'erreur, on ignore
        }

        const list = getEl('gmap-results-list');
        if (list) {
            list.addEventListener('scroll', () => {
                const threshold = 80;
                if (list.scrollTop + list.clientHeight >= list.scrollHeight - threshold) {
                    if (state.pagination && !state.isLoadingNextPage) {
                        loadMoreResults();
                    }
                }
            });

            list.addEventListener('click', (e) => {
                const importBtn = e.target.closest('[data-role="import-place"]');
                if (importBtn) {
                    e.preventDefault();
                    e.stopPropagation();
                    const card = importBtn.closest('.gmap-result');
                    if (!card) return;
                    const indexStr = card.getAttribute('data-index');
                    const idx = indexStr ? parseInt(indexStr, 10) : -1;
                    if (idx >= 0) {
                        importPlace(idx, card, importBtn);
                    }
                }
            });
        }
    }

    function launchAnalysesForImported(item) {
        if (!item) return;
        const url = (item.website || '').trim();
        if (!url) {
            showNotification('Aucun site web pour lancer les analyses.', 'warning');
            return;
        }
        const entrepriseId = item.entrepriseId;
        if (!entrepriseId) {
            showNotification('Entreprise non encore importée, analyses non lancées.', 'warning');
            return;
        }
        const socket = window.wsManager && window.wsManager.socket;
        if (!socket) {
            showNotification('Connexion temps réel non disponible. Rechargez la page pour lancer les analyses.', 'warning');
            return;
        }

        ensureGMapWsListeners();

        const name = item.name || 'Entreprise';

        // Ordre des analyses : SEO -> OSINT -> Pentest
        const sequence = [
            () => {
                socket.emit('start_seo_analysis', { url: url, entreprise_id: entrepriseId, use_lighthouse: true });
                showNotification(name + ' — Analyse SEO lancée…', 'info', 'fa-play-circle');
            },
            () => {
                socket.emit('start_osint_analysis', { url: url, entreprise_id: entrepriseId });
                showNotification(name + ' — Analyse OSINT lancée…', 'info', 'fa-play-circle');
            },
            () => {
                socket.emit('start_pentest_analysis', { url: url, entreprise_id: entrepriseId });
                showNotification(name + ' — Analyse Pentest lancée…', 'info', 'fa-play-circle');
            }
        ];

        sequence.forEach((fn, idx) => {
            setTimeout(fn, idx * 500);
        });
    }

    function ensureGMapWsListeners() {
        if (window._gmapWsListenersSetup || !window.wsManager || !window.wsManager.socket) return;
        const s = window.wsManager.socket;

        const getName = (entrepriseId) => {
            const item = state.entrepriseById[entrepriseId];
            return (item && item.name) ? item.name : 'Entreprise';
        };

        s.on('seo_analysis_complete', function (data) {
            if (!data || data.entreprise_id == null) return;
            const nom = getName(data.entreprise_id);
            showNotification(nom + ' — Analyse SEO terminée', 'success', 'fa-check-circle');
        });
        s.on('seo_analysis_error', function (data) {
            if (data && data.entreprise_id != null) {
                const nom = getName(data.entreprise_id);
                showNotification(nom + ' — ' + (data.error || 'Erreur analyse SEO'), 'error', 'fa-exclamation-circle');
            }
        });
        s.on('osint_analysis_complete', function (data) {
            if (data && data.entreprise_id != null) {
                const nom = getName(data.entreprise_id);
                showNotification(nom + ' — Analyse OSINT terminée', 'success', 'fa-check-circle');
            }
        });
        s.on('osint_analysis_error', function (data) {
            if (data && data.entreprise_id != null) {
                const nom = getName(data.entreprise_id);
                showNotification(nom + ' — ' + (data.error || 'Erreur analyse OSINT'), 'error', 'fa-exclamation-circle');
            }
        });
        s.on('pentest_analysis_complete', function (data) {
            if (!data || data.entreprise_id == null) return;
            const nom = getName(data.entreprise_id);
            showNotification(nom + ' — Analyse Pentest terminée', 'success', 'fa-check-circle');
        });
        s.on('pentest_analysis_error', function (data) {
            if (data && data.entreprise_id != null) {
                const nom = getName(data.entreprise_id);
                showNotification(nom + ' — ' + (data.error || 'Erreur analyse Pentest'), 'error', 'fa-exclamation-circle');
            }
        });

        window._gmapWsListenersSetup = true;
    }

    function importPlace(index, cardEl, buttonEl) {
        const item = state.items[index];
        if (!item) return;

        if (item.importStatus === 'created' || item.importStatus === 'existing') {
            showNotification('Ce lieu a déjà été importé.', 'info');
            return;
        }

        if (buttonEl) {
            buttonEl.disabled = true;
        }

        const payloadPlace = {
            place_id: item.placeId || item.place_id,
            name: item.name,
            website: item.website || '',
            phone_number: item.phone || '',
            country: item.country || '',
            address_1: item.address || '',
            address_2: '',
            latitude: item.lat,
            longitude: item.lng,
            rating: item.rating,
            reviews_count: item.reviewsCount,
            category: Array.isArray(item.types) && item.types.length ? item.types[0] : ''
        };

        fetch('/api/google-maps/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ places: [payloadPlace] })
        })
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error('Erreur lors de l\'import');
                }
                return await response.json();
            })
            .then((data) => {
                const results = data && Array.isArray(data.results) ? data.results : [];
                const r = results[0] || {};
                if (r.error) {
                    throw new Error(r.error);
                }
                item.entrepriseId = r.entreprise_id;
                item.importStatus = r.created ? 'created' : 'existing';
                if (r.entreprise_id != null) {
                    state.entrepriseById[r.entreprise_id] = item;
                }

                const baseMsg = r.created
                    ? 'Entreprise importée dans ProspectLab.'
                    : 'Entreprise déjà présente dans ProspectLab.';
                showNotification(baseMsg + ' Analyses SEO, OSINT et Pentest lancées.', 'success');

                // Lancer automatiquement les analyses en arrière-plan (Celery via WebSocket)
                launchAnalysesForImported(item);

                // Rafraîchir visuellement la carte de résultat
                renderResults(state.items, { append: false });
            })
            .catch((error) => {
                console.error('[gmap] Import error:', error);
                showNotification('Erreur lors de l\'import dans ProspectLab.', 'error');
            })
            .finally(() => {
                if (buttonEl) {
                    buttonEl.disabled = false;
                }
            });
    }

    function initPage() {
        try {
            initMap();
            initControls();
            ensureGMapWsListeners();
            toggleEmptyState(true);
        } catch (e) {
            console.error('[gmap] Erreur lors de l\'initialisation de la page Google Maps:', e);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPage);
    } else {
        initPage();
    }
})();

