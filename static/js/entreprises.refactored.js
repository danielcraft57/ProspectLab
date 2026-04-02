/**
 * JavaScript pour la page de liste des entreprises (Version modulaire)
 * Charge les modules nécessaires dans le bon ordre
 */

'use strict';

// Attendre que les modules soient chargés
    async function init() {
    // S'assurer que l'API principale est disponible
    if (typeof window.EntreprisesAPI === 'undefined') {
        console.error('[entreprises] EntreprisesAPI non chargé. Vérifiez que js/modules/entreprises/api.js est bien inclus avant ce script.');
        return;
    }
    
    // Utiliser les modules globaux avec valeurs de secours pour éviter de bloquer l'initialisation
    const EntreprisesAPI = window.EntreprisesAPI;
    const Formatters = window.Formatters || {
        escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };
    const Badges = window.Badges || {};
    const Notifications = window.Notifications || {
        show(message, type) {
            // Fallback no-op si Notifications n'est pas défini
        }
    };
    
    function getDisplayDomain(url) {
        if (!url) return '';
        try {
            const normalized = url.startsWith('http://') || url.startsWith('https://')
                ? url
                : `https://${url}`;
            const { hostname } = new URL(normalized);
            return hostname || url;
        } catch (e) {
            return url;
        }
    }

    function getInitials(name) {
        const s = String(name || '').trim();
        if (!s) return '?';
        const parts = s.split(/\s+/).filter(Boolean);
        const first = parts[0] ? parts[0][0] : '';
        const second = parts.length > 1 ? parts[1][0] : (parts[0] && parts[0].length > 1 ? parts[0][1] : '');
        const initials = (first + second).toUpperCase();
        return initials || '?';
    }

    function normalizeToHttps(url) {
        if (!url) return '';
        const s = String(url).trim();
        if (!s) return '';
        if (s.startsWith('http://')) return 'https://' + s.slice('http://'.length);
        return s;
    }

    function faviconFallbackUrl(domain, provider) {
        const d = String(domain || '').trim();
        if (!d) return '';
        if (provider === 'ddg') {
            return `https://icons.duckduckgo.com/ip3/${encodeURIComponent(d)}.ico`;
        }
        // google s2 favicons (par défaut)
        return `https://www.google.com/s2/favicons?sz=128&domain=${encodeURIComponent(d)}`;
    }
    
    function setScoreRelaunchLoading(entrepriseId, analysisType, isLoading) {
        if (!entrepriseId || !analysisType) return;

        // Mémoriser l'état pour qu'il survive aux rechargements/rafraîchissements de la liste.
        // Exemple: l'utilisateur relance une analyse, puis change les filtres => les cartes sont re-renderées
        // et on doit ré-afficher les loaders tant que l'analyse n'est pas terminée.
        if (isLoading) {
            if (!relaunchLoadingState[entrepriseId]) relaunchLoadingState[entrepriseId] = {};
            relaunchLoadingState[entrepriseId][analysisType] = true;
        } else {
            if (relaunchLoadingState[entrepriseId] && relaunchLoadingState[entrepriseId][analysisType]) {
                delete relaunchLoadingState[entrepriseId][analysisType];
            }
            if (relaunchLoadingState[entrepriseId] && Object.keys(relaunchLoadingState[entrepriseId]).length === 0) {
                delete relaunchLoadingState[entrepriseId];
            }
        }

        const items = document.querySelectorAll(`.score-chart-item[data-entreprise-id="${entrepriseId}"][data-analysis-type="${analysisType}"]`);
        if (!items.length) return;
        items.forEach(item => {
            const btn = item.querySelector('.score-relaunch-btn');
            const loader = item.querySelector('.score-loader');
            if (!loader) return;
            if (isLoading) {
                if (btn) {
                    btn.disabled = true;
                    btn.setAttribute('aria-busy', 'true');
                }
                loader.style.display = 'flex';
                const emptyVisual = item.querySelector('.row-score-empty-visual');
                if (emptyVisual) emptyVisual.classList.add('is-loading');
            } else {
                if (btn) {
                    btn.disabled = false;
                    btn.removeAttribute('aria-busy');
                }
                loader.style.display = 'none';
                const emptyVisual = item.querySelector('.row-score-empty-visual');
                if (emptyVisual) emptyVisual.classList.remove('is-loading');
            }
        });
    }

    function setScrapingRelaunchLoading(entrepriseId, isLoading, message) {
        if (!entrepriseId) return;
        const btn = document.querySelector(`#entreprise-modal .btn-relancer-scraping[data-entreprise-id="${entrepriseId}"]`);
        const stats = document.getElementById('scraping-stats');
        if (!btn) return;

        if (isLoading) {
            btn.disabled = true;
            btn.setAttribute('aria-busy', 'true');
            btn.dataset.originalHtml = btn.dataset.originalHtml || btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Relance...';
            if (stats) {
                stats.innerHTML = `<div style="color:#64748b;"><i class="fas fa-spinner fa-spin"></i> ${Formatters.escapeHtml(message || 'Scraping en cours...')}</div>`;
            }
        } else {
            btn.disabled = false;
            btn.removeAttribute('aria-busy');
            if (btn.dataset.originalHtml) {
                btn.innerHTML = btn.dataset.originalHtml;
            }
        }
    }
    
    const debounceFn = typeof window.debounce === 'function'
        ? window.debounce
        : (fn) => fn;
    
    // Variables d'état
    const ENTREPRISES_VIEW_STORAGE_KEY = 'entreprises_view_v1';
    let currentView = (() => {
        try {
            if (!window.localStorage) return 'grid';
            const raw = window.localStorage.getItem(ENTREPRISES_VIEW_STORAGE_KEY);
            if (raw === 'list' || raw === 'grid') return raw;
            return 'grid';
        } catch (e) {
            return 'grid';
        }
    })();

    function persistEntreprisesViewMode() {
        try {
            if (window.localStorage) {
                window.localStorage.setItem(ENTREPRISES_VIEW_STORAGE_KEY, currentView);
            }
        } catch (e) {
            // ignore
        }
    }

    function syncViewToggleButtons() {
        const btnGrid = document.getElementById('btn-view-grid');
        const btnList = document.getElementById('btn-view-list');
        if (!btnGrid || !btnList) return;
        if (currentView === 'list') {
            btnList.classList.add('active');
            btnGrid.classList.remove('active');
        } else {
            btnGrid.classList.add('active');
            btnList.classList.remove('active');
        }
    }

    const ENTREPRISES_CURRENT_PAGE_STORAGE_KEY = 'entreprises_current_page_v1';
    let currentPage = (() => {
        try {
            const raw = window.localStorage ? window.localStorage.getItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY) : null;
            if (!raw) return 1;
            const n = parseInt(raw, 10);
            if (!Number.isFinite(n) || n < 1) return 1;
            return n;
        } catch (e) {
            return 1;
        }
    })();
    let itemsPerPage = (() => {
        try {
            const stored = window.localStorage && window.localStorage.getItem('entreprises_page_size');
            const n = stored ? parseInt(stored, 10) : NaN;
            if (!Number.isFinite(n)) return 20;
            return Math.min(200, Math.max(10, n));
        } catch (e) {
            return 20;
        }
    })();
    let allEntreprises = [];        // entreprises de la page courante
    let filteredEntreprises = [];   // idem (après éventuels filtres client si on en ajoute)
    let totalEntreprises = 0;       // total tous résultats côté serveur
    let currentModalEntrepriseId = null;
    let currentModalEntrepriseData = null;
    let currentModalPentestScore = null;
    const entrepriseGroupsCache = {};
    const selectedEntreprises = new Set();
    let tagsSuggestions = [];
    let activeTagFilters = [];
    let initialAnalyseId = null;
    /** Vue « Top N commercial » (score pondéré + dernier touchpoint), sans pagination classique. */
    let commercialTopMode = false;
    
    const ENTREPRISES_FILTERS_MEMENTO_KEY = 'entreprises_last_filters';
    const ENTREPRISES_FILTERS_STORAGE_KEY = 'entreprises_last_filters_v1';
    
    function getElValue(id) {
        const el = document.getElementById(id);
        return el ? el.value : '';
    }
    
    function getElChecked(id) {
        const el = document.getElementById(id);
        return el ? !!el.checked : false;
    }

    function formatScoreMinLabel(value) {
        const v = parseInt(value, 10) || 0;
        if (v <= 0) return '0 (tous)';
        if (v >= 75) return `≥ ${v} (excellent)`;
        if (v >= 50) return `≥ ${v} (bon)`;
        if (v >= 25) return `≥ ${v} (moyen)`;
        return `≥ ${v}`;
    }

    function formatScoreMaxLabel(value) {
        const v = parseInt(value, 10) || 100;
        if (v >= 100) return '100 (tous)';
        if (v <= 25) return `≤ ${v} (risqué)`;
        if (v <= 50) return `≤ ${v} (moyen)`;
        return `≤ ${v}`;
    }

    /** Désactive les jauges quand « sans score » est coché (filtre SQL IS NULL). */
    function syncScoreNullSlidersDisabled() {
        const triples = [
            ['filter-security-null', 'filter-security-min', 'filter-security-max', 'filter-security-min-value', 'filter-security-max-value'],
            ['filter-seo-null', 'filter-seo-min', 'filter-seo-max', 'filter-seo-min-value', 'filter-seo-max-value'],
            ['filter-pentest-null', 'filter-pentest-min', 'filter-pentest-max', 'filter-pentest-min-value', 'filter-pentest-max-value'],
        ];
        triples.forEach(([nullId, minId, maxId, minLabelId, maxLabelId]) => {
            const n = document.getElementById(nullId);
            const minEl = document.getElementById(minId);
            const maxEl = document.getElementById(maxId);
            const minL = document.getElementById(minLabelId);
            const maxL = document.getElementById(maxLabelId);
            if (!n || !minEl || !maxEl) return;
            const dis = !!n.checked;
            minEl.disabled = dis;
            maxEl.disabled = dis;
            if (dis) {
                minEl.value = '0';
                maxEl.value = '100';
            }
            if (minL) minL.textContent = formatScoreMinLabel(minEl.value);
            if (maxL) maxL.textContent = formatScoreMaxLabel(maxEl.value);
        });
    }
    
    function buildFiltersMementoState() {
        return {
            search: getElValue('search-input'),
            secteur: getElValue('filter-secteur'),
            groupe: getElValue('filter-groupe'), // '' | 'none' | <id>
            opportunite: getElValue('filter-opportunite'),
            statut: getElValue('filter-statut'),
            etape_prospection: getElValue('filter-etape-prospection'),
            commercial_profile: getElValue('filter-commercial-profile'),
            security_min: getElValue('filter-security-min'),
            security_max: getElValue('filter-security-max'),
            seo_min: getElValue('filter-seo-min'),
            seo_max: getElValue('filter-seo-max'),
            pentest_min: getElValue('filter-pentest-min'),
            pentest_max: getElValue('filter-pentest-max'),
            security_null: getElChecked('filter-security-null'),
            seo_null: getElChecked('filter-seo-null'),
            pentest_null: getElChecked('filter-pentest-null'),
            has_email: getElChecked('filter-has-email'),
            has_blog: getElChecked('filter-has-blog'),
            has_form: getElChecked('filter-has-form'),
            has_tunnel: getElChecked('filter-has-tunnel'),
            cms: getElValue('filter-cms'),
            framework: getElValue('filter-framework'),
            tags: Array.isArray(activeTagFilters) ? activeTagFilters.slice() : []
        };
    }
    
    function restoreFiltersFromMemento() {
        try {
            let s = null;
            
            // Priorité: Memento (si présent), sinon localStorage.
            if (window.MementoCaretaker && typeof window.MementoCaretaker.load === 'function') {
                const m = window.MementoCaretaker.load(ENTREPRISES_FILTERS_MEMENTO_KEY);
                if (m && m.getState) s = m.getState();
            }
            
            if (!s && window.localStorage) {
                const raw = window.localStorage.getItem(ENTREPRISES_FILTERS_STORAGE_KEY);
                if (raw) {
                    try {
                        s = JSON.parse(raw);
                    } catch (e) {
                        s = null;
                    }
                }
            }
            
            if (!s || typeof s !== 'object') return;
            
            const searchInput = document.getElementById('search-input');
            if (searchInput && typeof s.search === 'string') searchInput.value = s.search;
            
            const filterSecteur = document.getElementById('filter-secteur');
            if (filterSecteur && typeof s.secteur === 'string') filterSecteur.value = s.secteur;
            
            const filterGroupe = document.getElementById('filter-groupe');
            if (filterGroupe && typeof s.groupe === 'string') filterGroupe.value = s.groupe;
            const filterOpportunite = document.getElementById('filter-opportunite');
            if (filterOpportunite && typeof s.opportunite === 'string') filterOpportunite.value = s.opportunite;
            
            const filterStatutHidden = document.getElementById('filter-statut');
            const statut = typeof s.statut === 'string' ? s.statut : '';
            if (filterStatutHidden) filterStatutHidden.value = statut;
            // Synchroniser les pills visuelles
            const statutPills = document.querySelectorAll('#filter-statut-pills .pill');
            statutPills.forEach(p => {
                const v = p.getAttribute('data-value') || '';
                p.classList.toggle('active', v === statut);
            });

            const filterEtape = document.getElementById('filter-etape-prospection');
            if (filterEtape && typeof s.etape_prospection === 'string') filterEtape.value = s.etape_prospection;

            const filterCommercialProfile = document.getElementById('filter-commercial-profile');
            if (filterCommercialProfile && typeof s.commercial_profile === 'string') {
                filterCommercialProfile.value = s.commercial_profile;
            }
            
            const setSlider = (id, value) => {
                const el = document.getElementById(id);
                if (!el) return;
                const v = value != null ? String(value) : '';
                if (v !== '' && !Number.isNaN(parseInt(v, 10))) el.value = v;
            };
            setSlider('filter-security-min', s.security_min);
            setSlider('filter-security-max', s.security_max);
            setSlider('filter-seo-min', s.seo_min);
            setSlider('filter-seo-max', s.seo_max);
            setSlider('filter-pentest-min', s.pentest_min);
            setSlider('filter-pentest-max', s.pentest_max);
            
            const setCheckbox = (id, checked) => {
                const el = document.getElementById(id);
                if (!el) return;
                el.checked = !!checked;
            };
            setCheckbox('filter-security-null', s.security_null);
            setCheckbox('filter-seo-null', s.seo_null);
            setCheckbox('filter-pentest-null', s.pentest_null);
            setCheckbox('filter-has-email', s.has_email);
            setCheckbox('filter-has-blog', s.has_blog);
            setCheckbox('filter-has-form', s.has_form);
            setCheckbox('filter-has-tunnel', s.has_tunnel);
            
            const filterCms = document.getElementById('filter-cms');
            if (filterCms && typeof s.cms === 'string') filterCms.value = s.cms;
            const filterFramework = document.getElementById('filter-framework');
            if (filterFramework && typeof s.framework === 'string') filterFramework.value = s.framework;
            
            // Restauration tags: état dans activeTagFilters + rendu chips.
            if (Array.isArray(s.tags)) {
                activeTagFilters = s.tags.slice();
                renderTagFilterChips();
                const input = document.getElementById('filter-tags');
                if (input) input.value = '';
                const suggestions = document.getElementById('filter-tags-suggestions');
                if (suggestions) {
                    suggestions.innerHTML = '';
                    suggestions.classList.add('hidden');
                }
            }
            
            syncScoreNullSlidersDisabled();
            if (typeof updateAdvancedFiltersBadge === 'function') {
                updateAdvancedFiltersBadge();
            }
        } catch (e) {
            // Silencieux: non bloquant si Memento indisponible.
            console.error('[entreprises] restoreFiltersFromMemento:', e);
        }
    }
    
    let _persistFiltersTimer = null;
    function schedulePersistFiltersToMemento(delayMs = 150) {
        clearTimeout(_persistFiltersTimer);
        _persistFiltersTimer = setTimeout(() => {
            try {
                const state = buildFiltersMementoState();
                
                // Priorité: Memento (si présent), sinon localStorage.
                if (window.MementoCaretaker && typeof window.MementoCaretaker.save === 'function' && window.Memento) {
                    const m = new window.Memento(state);
                    window.MementoCaretaker.save(ENTREPRISES_FILTERS_MEMENTO_KEY, m);
                } else if (window.localStorage) {
                    window.localStorage.setItem(ENTREPRISES_FILTERS_STORAGE_KEY, JSON.stringify(state));
                }
            } catch (e) {
                // ignore
            }
        }, delayMs);
    }
    // Etat des relances en cours (technique/seo/pentest) pour conserver l'affichage après rechargement des filtres.
    // Structure: { [entrepriseId]: { technique: true, seo: true, pentest: true } }
    const relaunchLoadingState = {};

    function applyRelaunchLoadingStateToRenderedEnterprises(entreprises) {
        if (!Array.isArray(entreprises) || entreprises.length === 0) return;
        const types = ['technique', 'seo', 'pentest'];
        entreprises.forEach(e => {
            if (!e || e.id == null) return;
            const state = relaunchLoadingState[e.id];
            if (!state) return;
            types.forEach(t => {
                if (state[t]) {
                    setScoreRelaunchLoading(e.id, t, true);
                }
            });
        });
    }
    
    function getEntrepriseNom(entrepriseId) {
        if (entrepriseId == null) return 'Entreprise';
        const e = allEntreprises.find(x => x && x.id === entrepriseId)
            || filteredEntreprises.find(x => x && x.id === entrepriseId)
            || (currentModalEntrepriseData && currentModalEntrepriseData.id === entrepriseId ? currentModalEntrepriseData : null);
        return (e && e.nom) ? String(e.nom) : 'Entreprise';
    }
    
    async function triggerScrapingRelaunch(entrepriseId, options = {}) {
        const notify = options.notify !== false;
        const entreprise = allEntreprises.find(e => e && e.id === entrepriseId)
            || filteredEntreprises.find(e => e && e.id === entrepriseId);
        const url = entreprise && entreprise.website ? String(entreprise.website).trim() : '';
        if (!url) {
            if (notify) {
                Notifications.show('Aucune URL de site pour relancer le scraping.', 'warning');
            }
            return;
        }

        const socket = window.wsManager && window.wsManager.socket;
        if (!socket) {
            if (notify) {
                Notifications.show('Connexion temps réel non disponible. Rechargez la page.', 'warning');
            }
            return;
        }

        // S'assurer que les listeners WebSocket scraping (notifications, refresh) sont en place
        try {
            if (typeof ensureModalWebSocketListeners === 'function') {
                ensureModalWebSocketListeners();
            }
        } catch (e) {
            // silencieux : au pire on n'a que les notifs globales websocket
        }

        const nom = entreprise && entreprise.nom ? entreprise.nom : getEntrepriseNom(entrepriseId);
        if (notify) {
            Notifications.show(nom + ' — Scraping lancé...', 'info', 'fa-spider');
        }

        socket.emit('start_scraping', {
            url: url,
            max_depth: 3,
            max_workers: 5,
            max_time: 300,
            max_pages: 50,
            entreprise_id: entrepriseId
        });
    }
    
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

    async function loadOpportunites() {
        try {
            const opportunites = await EntreprisesAPI.loadOpportunites();
            const select = document.getElementById('filter-opportunite');
            if (!select) return;

            const currentValue = select.value;
            // Conserver uniquement l'option par defaut, puis recharger avec les valeurs reelles de la base.
            select.innerHTML = '<option value="">Toutes les opportunités</option>';
            opportunites.forEach((opportunite) => {
                if (!opportunite) return;
                const option = document.createElement('option');
                option.value = opportunite;
                option.textContent = opportunite;
                select.appendChild(option);
            });

            if (currentValue) {
                const matchingOption = select.querySelector(`option[value="${currentValue}"]`);
                if (matchingOption) {
                    select.value = currentValue;
                }
            }
        } catch (error) {
            console.error('Erreur lors du chargement des opportunités:', error);
        }
    }

    function renderTagFilterChips() {
        const chipsContainer = document.getElementById('filter-tags-chips');
        if (!chipsContainer) return;
        if (!Array.isArray(activeTagFilters)) activeTagFilters = [];
        chipsContainer.innerHTML = activeTagFilters.map(tag => `
            <span class="tags-filter-chip" data-tag="${Formatters.escapeHtml(tag)}">
                <i class="fas fa-tag" aria-hidden="true"></i>
                <span>${Formatters.escapeHtml(tag)}</span>
                <button type="button" class="tags-filter-chip-remove" aria-label="Retirer le tag" data-remove-tag="${Formatters.escapeHtml(tag)}">
                    <i class="fas fa-times"></i>
                </button>
            </span>
        `).join('');
    }

    function renderTagSuggestions(filterText) {
        const container = document.getElementById('filter-tags-suggestions');
        if (!container) return;
        const query = (filterText || '').toLowerCase().trim();
        if (!tagsSuggestions || !tagsSuggestions.length) {
            container.classList.remove('hidden');
            container.innerHTML = `<div class="tag-suggestion-empty">Aucun résultat</div>`;
            return;
        }
        const available = tagsSuggestions
            .map(item => (typeof item === 'string' ? { value: item, count: null } : item))
            .filter(item => item && item.value && !activeTagFilters.includes(item.value));
        const filtered = query
            ? available.filter(item => item.value.toLowerCase().includes(query))
            : available;
        if (!filtered.length) {
            container.classList.remove('hidden');
            const text = query ? `Aucun tag pour \"${Formatters.escapeHtml(query)}\"` : 'Aucun résultat';
            container.innerHTML = `<div class="tag-suggestion-empty">${text}</div>`;
            return;
        }
        const maxToShow = 20;
        container.innerHTML = filtered.slice(0, maxToShow).map(item => {
            const value = item.value;
            const count = item.count;
            return `<button type="button" class="tag-suggestion" data-tag="${Formatters.escapeHtml(value)}">
                <span>${Formatters.escapeHtml(value)}</span>
                ${typeof count === 'number' ? `<small>${count}</small>` : ''}
            </button>`;
        }).join('');
        container.classList.remove('hidden');
    }

    function syncTagFilterInputAndApply() {
        const input = document.getElementById('filter-tags');
        if (input) {
            // On laisse toujours l'input visuellement vide, l'état réel est dans activeTagFilters
            input.value = '';
        }
        renderTagFilterChips();
        if (typeof updateAdvancedFiltersBadge === 'function') {
            updateAdvancedFiltersBadge();
        }
        if (typeof applyFilters === 'function') {
            applyFilters();
        }
        // Si aucun texte saisi, on masque complètement les suggestions
        if (input && input.value.trim() === '') {
            const container = document.getElementById('filter-tags-suggestions');
            if (container) {
                container.innerHTML = '';
                container.classList.add('hidden');
            }
        } else {
            renderTagSuggestions(input ? input.value : '');
        }
    }

    function addTagToFilter(rawTag) {
        const value = String(rawTag || '').trim();
        if (!value) return;
        if (!Array.isArray(activeTagFilters)) activeTagFilters = [];
        if (activeTagFilters.includes(value)) {
            return;
        }
        activeTagFilters.push(value);
        syncTagFilterInputAndApply();

        // Efface visuellement le champ après ajout
        const input = document.getElementById('filter-tags');
        if (input) {
            input.value = '';
        }

        // Masque la liste de suggestions quand on a choisi un tag
        const container = document.getElementById('filter-tags-suggestions');
        if (container) {
            container.innerHTML = '';
            container.classList.add('hidden');
        }
    }

    function removeTagFromFilter(rawTag) {
        const value = String(rawTag || '').trim();
        if (!value || !Array.isArray(activeTagFilters)) return;
        activeTagFilters = activeTagFilters.filter(t => t !== value);
        syncTagFilterInputAndApply();
    }

    async function loadTagsSuggestions() {
        try {
            const response = await fetch('/api/ciblage/suggestions?with_counts=1');
            if (response.ok) {
                const data = await response.json();
                tagsSuggestions = (data && data.tags) || [];
            } else {
                tagsSuggestions = [];
            }
        } catch (e) {
            console.error('Erreur chargement tags suggestions:', e);
            tagsSuggestions = [];
        }

    }

    // Charger les groupes pour le filtre
    async function loadGroupFilter() {
        const select = document.getElementById('filter-groupe');
        if (!select) return;
        try {
            // Ne pas perdre la sélection utilisateur pendant le refresh.
            // (La fonction recrée les options à partir de zéro.)
            const currentValue = select.value;

            // Réinitialiser les options de base
            select.innerHTML = '';
            const allOption = document.createElement('option');
            allOption.value = '';
            allOption.textContent = 'Tous les groupes';
            select.appendChild(allOption);

            const noneOption = document.createElement('option');
            noneOption.value = 'none';
            noneOption.textContent = 'Sans groupe';
            select.appendChild(noneOption);

            const groupes = await EntreprisesAPI.loadGroupes();
            if (Array.isArray(groupes)) {
                groupes.forEach(g => {
                    const option = document.createElement('option');
                    option.value = String(g.id);
                    const parts = [];
                    if (g.nom) {
                        parts.push(g.nom);
                    } else {
                        parts.push(`Groupe ${g.id}`);
                    }
                    if (typeof g.entreprises_count !== 'undefined' && g.entreprises_count !== null) {
                        parts.push(`(${g.entreprises_count})`);
                    }
                    option.textContent = parts.join(' ');
                    select.appendChild(option);
                });
            }

            // Restaurer la sélection si l'option existe encore.
            if (currentValue !== undefined && currentValue !== null) {
                const matchingOption = select.querySelector(`option[value="${currentValue}"]`);
                if (matchingOption) {
                    select.value = currentValue;
                }
            }
        } catch (error) {
            console.error('Erreur lors du chargement des groupes pour le filtre:', error);
        }
    }
    
    /** Construit l'objet de filtres à partir du formulaire (pour l'API). */
    function getCurrentFilters() {
        const get = (id) => (document.getElementById(id) || {}).value;
        const search = (get('search-input') || '').trim();
        const secteur = get('filter-secteur') || '';
        const groupeFilter = get('filter-groupe') || '';
        const opportunite = get('filter-opportunite') || '';
        const statut = get('filter-statut') || '';
        const securityMinRaw = get('filter-security-min') || '0';
        const securityMaxRaw = get('filter-security-max') || '100';
        const seoMinRaw = get('filter-seo-min') || '0';
        const seoMaxRaw = get('filter-seo-max') || '100';
        const pentestMinRaw = get('filter-pentest-min') || '0';
        const pentestMaxRaw = get('filter-pentest-max') || '100';
        const securityNull = document.getElementById('filter-security-null')?.checked;
        const seoNull = document.getElementById('filter-seo-null')?.checked;
        const pentestNull = document.getElementById('filter-pentest-null')?.checked;
        const tagsText = (get('filter-tags') || '').trim();
        const cms = (get('filter-cms') || '').trim();
        const framework = (get('filter-framework') || '').trim();

        let securityMin = parseInt(securityMinRaw, 10);
        let securityMax = parseInt(securityMaxRaw, 10);
        let seoMin = parseInt(seoMinRaw, 10);
        let seoMax = parseInt(seoMaxRaw, 10);
        let pentestMin = parseInt(pentestMinRaw, 10);
        let pentestMax = parseInt(pentestMaxRaw, 10);

        // Corriger si min > max (on swap pour éviter des requêtes vides)
        if (!Number.isNaN(securityMin) && !Number.isNaN(securityMax) && securityMin > securityMax) {
            [securityMin, securityMax] = [securityMax, securityMin];
        }
        if (!Number.isNaN(seoMin) && !Number.isNaN(seoMax) && seoMin > seoMax) {
            [seoMin, seoMax] = [seoMax, seoMin];
        }

        const filters = {};
        if (search) filters.search = search;
        if (secteur) filters.secteur = secteur;
        if (groupeFilter) {
            if (groupeFilter === 'none') {
                filters.no_group = 'true';
            } else {
                const gid = parseInt(groupeFilter, 10);
                if (!Number.isNaN(gid)) {
                    filters.groupe_id = gid;
                }
            }
        }
        if (statut) filters.statut = statut;
        if (opportunite) filters.opportunite = opportunite;
        const etapeProspection = get('filter-etape-prospection') || '';
        if (etapeProspection) filters.etape_prospection = etapeProspection;
        const hasEmailCheckbox = document.getElementById('filter-has-email');
        if (hasEmailCheckbox && hasEmailCheckbox.checked) {
            filters.has_email = 'true';
        }
        if (securityNull) {
            filters.security_null = 'true';
        } else {
            if (!Number.isNaN(securityMin) && securityMin > 0) {
                filters.security_min = securityMin;
            }
            if (!Number.isNaN(securityMax) && securityMax < 100) {
                filters.security_max = securityMax;
            }
        }
        if (seoNull) {
            filters.seo_null = 'true';
        } else {
            if (!Number.isNaN(seoMin) && seoMin > 0) {
                filters.seo_min = seoMin;
            }
            if (!Number.isNaN(seoMax) && seoMax < 100) {
                filters.seo_max = seoMax;
            }
        }
        if (pentestNull) {
            filters.pentest_null = 'true';
        } else {
            if (!Number.isNaN(pentestMin) && pentestMin > 0) {
                filters.pentest_min = pentestMin;
            }
            if (!Number.isNaN(pentestMax) && pentestMax < 100) {
                filters.pentest_max = pentestMax;
            }
        }
        const hasActiveTags = Array.isArray(activeTagFilters) && activeTagFilters.length > 0;
        let partsFromInput = [];
        if (tagsText) {
            partsFromInput = tagsText.split(/[, ]+/).map(s => s.trim()).filter(Boolean);
        }
        if (hasActiveTags) {
            const combined = Array.from(new Set([...activeTagFilters, ...partsFromInput])).filter(Boolean);
            if (combined.length === 1) {
                filters.tags_contains = combined[0];
            } else if (combined.length > 1) {
                filters.tags_all = combined;
            }
        } else if (partsFromInput.length) {
            if (partsFromInput.length === 1) {
                filters.tags_contains = partsFromInput[0];
            } else {
                filters.tags_any = partsFromInput;
            }
        }
        if (cms) {
            filters.cms = cms;
        }
        if (framework) {
            filters.framework = framework;
        }
        const hasBlogCheckbox = document.getElementById('filter-has-blog');
        if (hasBlogCheckbox && hasBlogCheckbox.checked) {
            filters.has_blog = 'true';
        }
        const hasFormCheckbox = document.getElementById('filter-has-form');
        if (hasFormCheckbox && hasFormCheckbox.checked) {
            filters.has_form = 'true';
        }
        const hasTunnelCheckbox = document.getElementById('filter-has-tunnel');
        if (hasTunnelCheckbox && hasTunnelCheckbox.checked) {
            filters.has_tunnel = 'true';
        }
        return filters;
    }

    /** Applique les filtres passés dans l'URL (?secteur=..., ?statut=..., ?tags_any=..., ?analyse_id=...). */
    function applyInitialFiltersFromUrl() {
        let hasAnyUrlFilter = false;
        try {
            const search = window.location ? window.location.search || '' : '';
            if (!search) return;
            const params = new URLSearchParams(search);

            // analyse_id (filtre backend, pas de champ dédié dans l'UI)
            const analyseParam = params.get('analyse_id') || params.get('analyse');
            if (analyseParam) {
                const id = Number.parseInt(analyseParam, 10);
                if (!Number.isNaN(id) && id > 0) {
                    initialAnalyseId = id;
                    hasAnyUrlFilter = true;
                }
            }

            // Secteur -> select
            const secteurParam = params.get('secteur');
            if (secteurParam) {
                const secteurSelect = document.getElementById('filter-secteur');
                if (secteurSelect) {
                    secteurSelect.value = secteurParam;
                }
                hasAnyUrlFilter = true;
            }

            // Statut -> champ caché + pills
            const statutParam = params.get('statut');
            if (statutParam) {
                const statutInput = document.getElementById('filter-statut');
                if (statutInput) {
                    statutInput.value = statutParam;
                }
                const pills = document.querySelectorAll('#filter-statut-pills .pill');
                pills.forEach((pill) => {
                    const v = pill.getAttribute('data-value') || '';
                    pill.classList.toggle('active', v === statutParam);
                });
                hasAnyUrlFilter = true;
            }

            // Opportunité -> select dédié
            const opportuniteParam = params.get('opportunite');
            if (opportuniteParam) {
                const opportuniteSelect = document.getElementById('filter-opportunite');
                if (opportuniteSelect) {
                    opportuniteSelect.value = opportuniteParam;
                }
                hasAnyUrlFilter = true;
            }

            // Tags_any -> initialisation des tags intelligents
            const tagsAnyParam = params.get('tags_any');
            if (tagsAnyParam) {
                const parts = tagsAnyParam.split(',').map((s) => s.trim()).filter(Boolean);
                if (parts.length) {
                    activeTagFilters = Array.from(new Set([...(activeTagFilters || []), ...parts]));
                    const input = document.getElementById('filter-tags');
                    if (input) {
                        // L'input reste visuellement vide: l'etat est porte par les chips.
                        input.value = '';
                    }
                    renderTagFilterChips();
                    hasAnyUrlFilter = true;
                }
            }
        } catch (e) {
            console.error('[entreprises] Erreur lors de la lecture des filtres URL:', e);
        }

        if (hasAnyUrlFilter) {
            updateAdvancedFiltersBadge();
        }
    }

    /**
     * Barre synthèse prospection CRM (effectifs par étape Kanban) alignée sur les filtres liste.
     */
    async function refreshKanbanStrip() {
        const el = document.getElementById('pipeline-kanban-strip');
        if (!el || !window.EntreprisesAPI) return;
        try {
            const filters = getCurrentFilters();
            const data = await EntreprisesAPI.loadPipelineKanbanCrm(filters, initialAnalyseId);
            if (!data || !data.columns) {
                el.style.display = 'none';
                el.innerHTML = '';
                return;
            }
            el.style.display = 'block';
            const esc = (t) => (Formatters && Formatters.escapeHtml ? Formatters.escapeHtml(String(t ?? '')) : String(t ?? ''));
            const total = typeof data.total === 'number' ? data.total : '';
            const filteredNote = data.filtered ? ' <span class="kanban-strip-filtered">(filtres actifs)</span>' : '';
            const columnsNonZero = (data.columns || []).filter((col) => Number(col.count) > 0);
            let cols = columnsNonZero.map((col) => {
                const raw = col.couleur && String(col.couleur).trim();
                const bg = raw && /^#[0-9A-Fa-f]{6}$/.test(raw) ? raw : '#94a3b8';
                const label = col.etape != null ? col.etape : '';
                return `<div class="kanban-strip-col" title="${esc(label)}">
                    <span class="kanban-strip-dot" style="background:${bg}"></span>
                    <span class="kanban-strip-label">${esc(label)}</span>
                    <span class="kanban-strip-count">${col.count}</span>
                </div>`;
            }).join('');
            let hors = '';
            const horsNonZero = (data.hors_referentiel || []).filter((h) => Number(h.count) > 0);
            if (horsNonZero.length) {
                const parts = horsNonZero.map((h) => `${esc(h.etape)} (${h.count})`);
                hors = `<div class="kanban-strip-hors">Autres étapes en base : ${parts.join(', ')}</div>`;
            }
            const colsHtml = cols ? `<div class="kanban-strip-columns">${cols}</div>` : '';
            el.innerHTML = `
                <div class="kanban-strip-inner">
                    <div class="kanban-strip-meta">
                        <strong>Prospection CRM</strong>${filteredNote}
                        <span class="kanban-strip-total">${total} prospect(s)</span>
                    </div>
                    ${colsHtml}
                    ${hors}
                </div>`;
        } catch (e) {
            console.warn('[entreprises] Kanban strip:', e);
            el.style.display = 'none';
        }
    }

    function updateCommercialProfileWeightsVisual() {
        const sel = document.getElementById('filter-commercial-profile');
        const host = document.getElementById('commercial-profile-weights-visual');
        if (!host) return;
        let w = { w_seo: 0.25, w_secu: 0.25, w_perf: 0.25, w_opp: 0.25 };
        const opt = sel && sel.options[sel.selectedIndex];
        if (sel && opt && opt.dataset && opt.dataset.poids) {
            try {
                const p = JSON.parse(opt.dataset.poids);
                if (p && typeof p === 'object') {
                    const a = Number(p.w_seo) || 0;
                    const b = Number(p.w_secu) || 0;
                    const c = Number(p.w_perf) || 0;
                    const d = Number(p.w_opp) || 0;
                    const sum = a + b + c + d;
                    if (sum > 0) {
                        w = { w_seo: a / sum, w_secu: b / sum, w_perf: c / sum, w_opp: d / sum };
                    }
                }
            } catch (e) {
                /* garder le défaut */
            }
        }
        const rows = [
            { cls: 'commercial-weight-bar--seo', label: 'SEO', pct: w.w_seo },
            { cls: 'commercial-weight-bar--secu', label: 'Sécurité', pct: w.w_secu },
            { cls: 'commercial-weight-bar--perf', label: 'Performance', pct: w.w_perf },
            { cls: 'commercial-weight-bar--opp', label: 'Opportunité', pct: w.w_opp },
        ];
        host.innerHTML = rows
            .map(
                (r) =>
                    `<div class="commercial-weight-row"><span class="commercial-weight-label">${r.label}</span>` +
                    `<div class="commercial-weight-bar-wrap"><div class="commercial-weight-bar ${r.cls}" style="width:${Math.round(r.pct * 100)}%"></div></div>` +
                    `<span class="commercial-weight-pct">${Math.round(r.pct * 100)}%</span></div>`,
            )
            .join('');
    }

    async function populateCommercialProfileSelect() {
        const sel = document.getElementById('filter-commercial-profile');
        if (!sel || !window.EntreprisesAPI) return;
        const previous = sel.value;
        try {
            const data = await EntreprisesAPI.loadCommercialPriorityProfiles();
            const items = (data && data.items) ? data.items : [];
            const first = sel.querySelector('option[value=""]');
            sel.innerHTML = '';
            if (first) {
                sel.appendChild(first);
            } else {
                const def = document.createElement('option');
                def.value = '';
                def.textContent = 'Défaut (équilibré)';
                sel.appendChild(def);
            }
            items.forEach((p) => {
                const o = document.createElement('option');
                o.value = String(p.id);
                o.textContent = p.nom || ('Profil ' + p.id);
                const po = p && p.poids && typeof p.poids === 'object' ? p.poids : {};
                o.dataset.poids = JSON.stringify(po);
                sel.appendChild(o);
            });
            if (previous && Array.from(sel.options).some((o) => o.value === previous)) {
                sel.value = previous;
            }
            updateCommercialProfileWeightsVisual();
        } catch (e) {
            console.warn('[entreprises] Profils priorité:', e);
        }
    }

    function setCommercialTopUi(on) {
        const btnTop = document.getElementById('btn-commercial-top');
        const btnOff = document.getElementById('btn-commercial-top-off');
        if (btnTop) btnTop.style.display = on ? 'none' : '';
        if (btnOff) btnOff.style.display = on ? 'inline-flex' : 'none';
    }

    /** Charge les entreprises avec les filtres courants (côté serveur, pagination). */
    async function loadEntreprises() {
        try {
            const filters = getCurrentFilters();
            if (commercialTopMode && window.EntreprisesAPI && typeof EntreprisesAPI.loadCommercialTop === 'function') {
                let profileId;
                const profileSel = document.getElementById('filter-commercial-profile');
                if (profileSel && profileSel.value) {
                    const pid = parseInt(profileSel.value, 10);
                    if (!Number.isNaN(pid)) profileId = pid;
                }
                const data = await EntreprisesAPI.loadCommercialTop(filters, initialAnalyseId, {
                    limit: 50,
                    profile_id: profileId,
                });
                const items = data && data.items ? data.items : [];
                allEntreprises = items;
                filteredEntreprises = [...items];
                totalEntreprises = items.length;
                setCommercialTopUi(true);
                renderEntreprises();
                refreshKanbanStrip();
                return;
            }
            setCommercialTopUi(false);
            const data = await EntreprisesAPI.loadAll(filters, currentPage, itemsPerPage, false, initialAnalyseId);
            const items = data && data.items ? data.items : [];
            allEntreprises = items;
            filteredEntreprises = [...items];
            totalEntreprises = data && typeof data.total === 'number' ? data.total : items.length;
            // S'assurer que la page reste dans les bornes si les filtres changent beaucoup
            if (!items.length && totalEntreprises > 0 && currentPage > 1) {
                currentPage = 1;
                try {
                    if (window.localStorage) {
                        window.localStorage.setItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY, String(currentPage));
                    }
                } catch (e) {}
                return loadEntreprises();
            }
            renderEntreprises();
            refreshKanbanStrip();
        } catch (error) {
            console.error('[entreprises] Erreur loadEntreprises:', error);
            document.getElementById('entreprises-container').innerHTML =
                '<p class="error">Erreur lors du chargement des entreprises</p>';
        }
    }

    /** Réapplique les filtres (recharge depuis l'API avec les critères du formulaire). */
    async function applyFilters(opts = {}) {
        const resetPage = opts.resetPage !== false; // par défaut: true
        if (resetPage) currentPage = 1;
        schedulePersistFiltersToMemento();
        try {
            if (window.localStorage) {
                window.localStorage.setItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY, String(currentPage));
            }
        } catch (e) {}
        await loadEntreprises();
    }
    
    // Rafraîchit la liste filtrée après un changement (groupe / scores),
    // mais en regroupant plusieurs événements rapprochés.
    let _applyFiltersTimer = null;
    let _applyFiltersLastAt = 0;
    function scheduleApplyFilters(delayMs = 500) {
        // Éviter de déclencher pendant que la page n'est pas prête.
        const container = document.getElementById('entreprises-container');
        if (!container) return;

        clearTimeout(_applyFiltersTimer);
        const now = Date.now();
        const minIntervalMs = 1500; // throttle minimal
        const remaining = Math.max(0, minIntervalMs - (now - _applyFiltersLastAt));
        const finalDelay = Math.max(delayMs, remaining);

        _applyFiltersTimer = setTimeout(async () => {
            _applyFiltersTimer = null;
            _applyFiltersLastAt = Date.now();
            try {
                // Rafraîchissement "live": ne pas réinitialiser la pagination.
                await applyFilters({ resetPage: false });
            } catch (e) {
                console.error('[entreprises] Erreur scheduleApplyFilters:', e);
            }
        }, finalDelay);
    }

    function isEntrepriseCurrentlyRendered(entrepriseId) {
        if (entrepriseId == null) return false;
        return Boolean(
            document.querySelector(`.entreprise-card[data-id="${entrepriseId}"], .entreprise-row[data-id="${entrepriseId}"]`)
        );
    }
    
    // Rendre les entreprises
    function renderEntreprises() {
        const container = document.getElementById('entreprises-container');
        const pageEntreprises = filteredEntreprises;
        
        const rc = document.getElementById('results-count');
        if (rc) {
            rc.textContent = commercialTopMode
                ? `${totalEntreprises} prospect(s) — vue « Top commercial » (priorité + dernier contact)`
                : `${totalEntreprises} entreprise${totalEntreprises > 1 ? 's' : ''} trouvée${totalEntreprises > 1 ? 's' : ''}`;
        }
        
        if (pageEntreprises.length === 0) {
            container.innerHTML = '<p class="no-results">Aucune entreprise ne correspond aux critères</p>';
            document.getElementById('pagination').innerHTML = '';
            return;
        }
        
        if (currentView === 'grid') {
            container.className = 'entreprises-grid pagination-transition';
            container.innerHTML = pageEntreprises.map(entreprise => createEntrepriseCard(entreprise)).join('');
        } else {
            container.className = 'entreprises-list pagination-transition';
            container.innerHTML = pageEntreprises.map(entreprise => createEntrepriseRow(entreprise)).join('');
        }
        
        renderPagination();
        
        // Ajouter les event listeners pour les actions
        pageEntreprises.forEach(entreprise => {
            setupEntrepriseActions(entreprise.id);
        });

        // Réappliquer l'état des relances (loaders) si l'utilisateur a relancé une analyse
        // avant de changer de filtres / recharger.
        applyRelaunchLoadingStateToRenderedEnterprises(pageEntreprises);

        // Appliquer la sélection existante (checkbox + surbrillance)
        pageEntreprises.forEach(entreprise => {
            const id = entreprise.id;
            const selected = selectedEntreprises.has(id);
            const checkboxes = document.querySelectorAll(`.entreprise-select-checkbox[data-entreprise-id="${id}"]`);
            checkboxes.forEach(cb => { cb.checked = selected; });
            const nodes = document.querySelectorAll(`.entreprise-card[data-id="${id}"], .entreprise-row[data-id="${id}"]`);
            nodes.forEach(el => el.classList.toggle('entreprise-selected', selected));
        });

        updateBulkSelectionUI();
        
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
    
    async function refreshEntrepriseFromServer(entrepriseId, opts) {
        if (!entrepriseId) return;
        const animateOnlyMetric = (opts && opts.animateOnlyMetric) || null;
        // Court délai pour laisser le backend persister score_securite / score_seo avant de refetch
        await new Promise(r => setTimeout(r, 600));
        try {
            const updated = await EntreprisesAPI.loadDetails(entrepriseId);
            // Compléter avec les scores d'analyse (SEO, Pentest, etc.) depuis le pipeline d'audit
            try {
                const audit = await EntreprisesAPI.loadAuditPipeline(entrepriseId);
                if (audit) {
                    const pipeline = audit.pipeline || audit;
                    if (pipeline) {
                        if (pipeline.seo && typeof pipeline.seo.score === 'number') {
                            updated.score_seo = pipeline.seo.score;
                        }
                        if (pipeline.pentest && typeof pipeline.pentest.risk_score === 'number') {
                            updated.score_pentest = pipeline.pentest.risk_score;
                        }
                        if (pipeline.technical && typeof pipeline.technical.security_score === 'number') {
                            // Sécurité globale, utile si elle n'est pas encore remontée via la colonne score_securite
                            if (typeof updated.score_securite === 'undefined' || updated.score_securite === null) {
                                updated.score_securite = pipeline.technical.security_score;
                            }
                        }
                    }
                }
            } catch (e) {
                // Non bloquant : si le pipeline échoue, on garde au moins les données de base
                console.warn('Erreur lors du chargement du pipeline audit pour la mise à jour de la ligne:', e);
            }
            if (!updated || !updated.id) return;

            const mergeEntrepriseObjects = (existing, updatedData) => {
                if (!existing) return updatedData;
                const merged = Object.assign({}, existing, updatedData);
                ['score_securite', 'score_seo', 'score_pentest'].forEach((key) => {
                    if ((updatedData[key] === null || typeof updatedData[key] === 'undefined') &&
                        typeof existing[key] !== 'undefined' && existing[key] !== null) {
                        merged[key] = existing[key];
                    }
                });
                return merged;
            };

            const mergeIntoArray = (arr) => {
                if (!Array.isArray(arr)) return;
                const idx = arr.findIndex(e => e && e.id === updated.id);
                if (idx !== -1) {
                    arr[idx] = mergeEntrepriseObjects(arr[idx], updated);
                }
            };

            mergeIntoArray(allEntreprises);
            mergeIntoArray(filteredEntreprises);

            if (currentModalEntrepriseData && currentModalEntrepriseData.id === updated.id) {
                currentModalEntrepriseData = mergeEntrepriseObjects(currentModalEntrepriseData, updated);
            }
            updateEntrepriseCardsInDom(updated, { animateOnlyMetric });
        } catch (e) {
            console.error('Erreur lors de la mise à jour temps réel de l\'entreprise:', e);
        }
    }
    
    function updateEntrepriseCardsInDom(entreprise, opts) {
        if (!entreprise || !entreprise.id) return;
        const fromFiltered = Array.isArray(filteredEntreprises)
            ? filteredEntreprises.find(e => e && e.id === entreprise.id)
            : null;
        const fromAll = Array.isArray(allEntreprises)
            ? allEntreprises.find(e => e && e.id === entreprise.id)
            : null;
        const displayEntreprise = fromFiltered || fromAll || entreprise;
        const id = displayEntreprise.id;
        const animateOnlyMetric = (opts && opts.animateOnlyMetric) || null;
        
        const replaceNode = (existingNode, newHtml, animateOnly) => {
            if (!existingNode || !existingNode.parentNode) return;
            const wrapper = document.createElement('div');
            wrapper.innerHTML = newHtml;
            const newNode = wrapper.firstElementChild;
            if (!newNode) return;
            existingNode.parentNode.replaceChild(newNode, existingNode);
            setupEntrepriseActions(id);
            
            const allCharts = newNode.querySelectorAll('.circular-chart-progress');
            const toAnimate = animateOnly
                ? newNode.querySelectorAll(`.score-chart-item[data-analysis-type="${animateOnly}"] .circular-chart-progress`)
                : allCharts;
            const toAnimateSet = new Set(Array.from(toAnimate));
            allCharts.forEach((chart) => {
                const targetOffset = chart.getAttribute('data-target-offset');
                if (!targetOffset) return;
                const shouldAnimate = toAnimateSet.has(chart);
                if (shouldAnimate) {
                    setTimeout(() => {
                        chart.style.strokeDashoffset = targetOffset;
                    }, 0);
                } else {
                    chart.style.transition = 'none';
                    chart.style.strokeDashoffset = targetOffset;
                }
            });
        };
        
        const card = document.querySelector(`.entreprise-card[data-id="${id}"]`);
        if (card) {
            replaceNode(card, createEntrepriseCard(displayEntreprise), animateOnlyMetric);
        }
        
        const row = document.querySelector(`.entreprise-row[data-id="${id}"]`);
        if (row) {
            replaceNode(row, createEntrepriseRow(displayEntreprise), animateOnlyMetric);
        }
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
    
    function buildOpportunityTagHtml(entreprise) {
        const niveau = entreprise && typeof entreprise.opportunite === 'string'
            ? entreprise.opportunite.trim()
            : '';
        if (!niveau) return '';

        // On ne met en avant que les opportunites interessantes.
        if (niveau === 'Très élevée') {
            return '<span class="tag tag-opportunity tag-opportunity-very-high" data-tag="opportunite:tres-elevee">Opportunité: Très élevée</span>';
        }
        if (niveau === 'Élevée') {
            return '<span class="tag tag-opportunity tag-opportunity-high" data-tag="opportunite:elevee">Opportunité: Élevée</span>';
        }
        return '';
    }

    function createEntrepriseCard(entreprise) {
        const opportunityTagHtml = buildOpportunityTagHtml(entreprise);
        const tagsHtml = entreprise.tags && entreprise.tags.length > 0
            ? entreprise.tags
                .slice() // ne pas muter l'array originale
                .sort((a, b) => {
                    const priority = (t) => {
                        if (!t) return 999;
                        if (t === 'fort_potentiel_refonte') return 1;
                        if (t === 'risque_cyber_eleve') return 2;
                        if (t === 'seo_a_ameliorer') return 3;
                        if (t === 'perf_lente' || t === 'perf:low') return 4;
                        if (t === 'perf:good') return 5;
                        if (t === 'site_sans_https') return 6;
                        if (t.startsWith('cms:')) return 7;
                        if (t.startsWith('framework:')) return 8;
                        if (t === 'blog' || t === 'contact_form' || t === 'ecommerce') return 9;
                        if (String(t).startsWith('lang_')) return 10;
                        return 50;
                    };
                    return priority(a) - priority(b);
                })
                .map(tag => {
                const base = 'tag';
                const isCms = typeof tag === 'string' && tag.startsWith('cms:');
                const isFramework = typeof tag === 'string' && tag.startsWith('framework:');
                const isPerf = typeof tag === 'string' && tag.startsWith('perf:');
                const extra =
                    tag === 'fort_potentiel_refonte' ? ' tag-refonte' :
                    tag === 'risque_cyber_eleve' ? ' tag-risk' :
                    tag === 'seo_a_ameliorer' ? ' tag-seo' :
                    tag === 'perf_lente' ? ' tag-perf' :
                    tag === 'site_sans_https' ? ' tag-https' :
                    tag === 'blog' ? ' tag-blog' :
                    tag === 'contact_form' ? ' tag-form' :
                    tag === 'ecommerce' ? ' tag-ecommerce' :
                    (isCms ? ' tag-cms' : '') +
                    (isFramework ? ' tag-framework' : '') +
                    (isPerf && tag.endsWith('good') ? ' tag-perf-good' : '') +
                    (isPerf && tag.endsWith('low') ? ' tag-perf-low' : '') +
                    '';

                let label;
                switch (tag) {
                    case 'fort_potentiel_refonte':
                        label = 'Fort potentiel refonte';
                        break;
                    case 'risque_cyber_eleve':
                        label = 'Risque cyber élevé';
                        break;
                    case 'seo_a_ameliorer':
                        label = 'SEO à améliorer';
                        break;
                    case 'perf_lente':
                        label = 'Site lent';
                        break;
                    case 'site_sans_https':
                        label = 'Sans HTTPS';
                        break;
                    case 'blog':
                        label = 'Blog';
                        break;
                    case 'contact_form':
                        label = 'Formulaire';
                        break;
                    case 'ecommerce':
                        label = 'E‑commerce';
                        break;
                    case 'lang_fr':
                        label = 'FR';
                        break;
                    case 'lang_en':
                        label = 'EN';
                        break;
                    case 'lang_de':
                        label = 'DE';
                        break;
                    case 'lang_es':
                        label = 'ES';
                        break;
                    case 'lang_it':
                        label = 'IT';
                        break;
                    case 'lang_nl':
                        label = 'NL';
                        break;
                    case 'lang_pt':
                        label = 'PT';
                        break;
                    case 'lang_autre':
                        label = 'Autre langue';
                        break;
                    default:
                        if (isCms) {
                            label = 'CMS: ' + tag.slice('cms:'.length);
                        } else if (isFramework) {
                            label = 'FW: ' + tag.slice('framework:'.length);
                        } else if (isPerf) {
                            const v = tag.slice('perf:'.length);
                            label = v === 'good' ? 'Perf OK' : v === 'low' ? 'Perf faible' : ('Perf: ' + v);
                        } else {
                            label = tag.replace(/_/g, ' ');
                        }
                }

                return `<span class="${base}${extra}" data-tag="${Formatters.escapeHtml(tag)}">${Formatters.escapeHtml(label)}</span>`;
            }).join('')
            : '';
        const visibleTagsHtml = [opportunityTagHtml, tagsHtml].filter(Boolean).join('');
        
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
        
        // Générer les graphiques circulaires pour Sécurité, SEO et Risque (Pentest),
        // avec emplacements « Lancer » pour les analyses non encore effectuées.
        const hasSecurityScore = typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null;
        const hasSeoScore = typeof entreprise.score_seo !== 'undefined' && entreprise.score_seo !== null;
        const hasPentestScore = typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null;

        function cardScoreSlot(type, label, hasScore, scoreValue, color, size = 60) {
            if (hasScore) {
                return `
                <div class="score-chart-item" data-analysis-type="${type}" data-entreprise-id="${entreprise.id}" style="position: relative; display: inline-flex; align-items: center; justify-content: center;">
                    <div class="score-chart-visual" style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center;">
                        ${createCircularChart(scoreValue, label, color, size)}
                        <div class="score-loader" style="position:absolute;inset:0;display:none;align-items:center;justify-content:center;background:rgba(15,23,42,0.35);border-radius:999px;">
                            <i class="fas fa-circle-notch fa-spin" style="font-size:1.1rem;color:#e5e7eb;"></i>
                        </div>
                    </div>
                    <button 
                        class="score-relaunch-btn"
                        type="button"
                        data-analysis-type="${type}"
                        data-entreprise-id="${entreprise.id}"
                        title="Relancer l'analyse ${label}"
                        style="position: absolute; right: -6px; bottom: -6px; width: 22px; height: 22px; border-radius: 999px; border: none; background: #1e293b; color: #e5e7eb; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 0 0 2px rgba(15,23,42,0.7); cursor: pointer; font-size: 0.7rem;"
                    >
                        <i class="fas fa-sync-alt"></i>
                    </button>
                </div>`;
            }
            return `
                <div class="score-chart-item row-score-item--empty" data-analysis-type="${type}" data-entreprise-id="${entreprise.id}" style="position: relative; display: inline-flex; align-items: center; justify-content: center;">
                    <div class="row-score-empty-visual">
                        <i class="fas fa-play" aria-hidden="true"></i>
                        <span class="row-score-empty-label">Lancer</span>
                        <div class="score-loader row-score-loader"><i class="fas fa-circle-notch fa-spin"></i></div>
                    </div>
                    <button 
                        class="score-relaunch-btn row-launch-btn"
                        type="button"
                        data-analysis-type="${type}"
                        data-entreprise-id="${entreprise.id}"
                        title="Lancer l'analyse ${label}"
                        style="position: absolute; right: -6px; bottom: -6px; width: 22px; height: 22px; border-radius: 999px; border: none; cursor: pointer;"
                    >
                        <i class="fas fa-play"></i>
                    </button>
                </div>`;
        }

        const scoresSection = `
            <div class="card-scores-section">
                ${cardScoreSlot('technique', 'technique', hasSecurityScore, entreprise.score_securite, null)}
                ${cardScoreSlot('seo', 'SEO', hasSeoScore, entreprise.score_seo, null)}
                ${cardScoreSlot('pentest', 'Pentest', hasPentestScore, entreprise.score_pentest, '#ef4444')}
            </div>
        `;
        
        const domain = getDisplayDomain(entreprise.website || mainImage || '');
        const initials = getInitials(entreprise.nom || '');
        const safeMainImage = mainImage ? normalizeToHttps(mainImage) : '';
        const fallbackGoogle = faviconFallbackUrl(domain, 'google');
        const fallbackDdg = faviconFallbackUrl(domain, 'ddg');

        const isSelected = selectedEntreprises.has(entreprise.id);

        return `
            <div class="entreprise-card${isSelected ? ' entreprise-selected' : ''}" data-id="${entreprise.id}">
                <div class="card-header-with-logo">
                    <div class="card-logo-container">
                        <img
                            src="${safeMainImage || fallbackGoogle}"
                            alt="${Formatters.escapeHtml(entreprise.nom || 'Logo')}"
                            class="card-logo"
                            loading="lazy"
                            referrerpolicy="no-referrer"
                            data-fallback-step="0"
                            onload="this.nextElementSibling && (this.nextElementSibling.style.display='none')"
                            onerror="
                                try {
                                    const step = (this.dataset && this.dataset.fallbackStep) ? String(this.dataset.fallbackStep) : '0';
                                    if (step === '0' && '${fallbackGoogle}') { this.dataset.fallbackStep = '1'; this.src='${fallbackGoogle}'; return; }
                                    if (step === '1' && '${fallbackDdg}') { this.dataset.fallbackStep = '2'; this.src='${fallbackDdg}'; return; }
                                } catch (e) {}
                                this.style.display='none';
                            "
                        >
                        <div class="card-logo-placeholder" aria-hidden="true">${Formatters.escapeHtml(initials)}</div>
                    </div>
                    <div class="card-header">
                        <div style="display:flex; align-items:center; gap:0.4rem; min-width:0;">
                            ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null && entreprise.score_pentest >= 40 ? `
                            <i class="fas fa-exclamation-triangle" style="color: ${entreprise.score_pentest >= 70 ? '#e74c3c' : '#f39c12'}; font-size: 1.1rem;" title="Score Pentest: ${entreprise.score_pentest}/100"></i>
                            ` : ''}
                            <h3 style="white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">${Formatters.escapeHtml(entreprise.nom || 'Sans nom')}</h3>
                        </div>
                        <div style="display:flex; align-items:center; gap:0.25rem;">
                            <input 
                                type="checkbox" 
                                class="entreprise-select-checkbox" 
                                data-entreprise-id="${entreprise.id}" 
                                ${isSelected ? 'checked' : ''} 
                                title="Sélectionner cette entreprise"
                            >
                        <button class="btn-favori ${entreprise.favori ? 'active' : ''}" data-id="${entreprise.id}" title="Favori">
                            <i class="fas fa-star"></i>
                        </button>
                        </div>
                    </div>
                </div>
                ${commercialTopMode && entreprise.priority_score != null ? `
                <div class="card-commercial-priority">
                    <span class="badge badge-secondary" title="Score pondéré + dernier contact">Priorité ${Math.round(Number(entreprise.priority_score))}</span>
                    ${entreprise.last_touchpoint_at
                        ? ` · Dernier contact ${Formatters.escapeHtml(String(entreprise.last_touchpoint_at).slice(0, 16))}`
                        : ' · Aucun contact enregistré'}
                </div>` : ''}
                <div class="card-body">
                    ${resumePreview ? `<p class="resume-preview" style="color: #666; font-size: 0.9rem; margin-bottom: 0.75rem; font-style: italic;">${Formatters.escapeHtml(resumePreview)}</p>` : ''}
                    ${entreprise.website ? `<p><strong>Site:</strong> <a href="${entreprise.website}" target="_blank">${Formatters.escapeHtml(getDisplayDomain(entreprise.website))}</a></p>` : ''}
                    ${entreprise.secteur ? `<p><strong>Secteur:</strong> ${Formatters.escapeHtml(entreprise.secteur)}</p>` : ''}
                    ${scoresSection}
                    ${visibleTagsHtml ? `<div class="tags-container">${visibleTagsHtml}</div>` : ''}
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
        const opportunityTagHtml = buildOpportunityTagHtml(entreprise);
        let langChipLabel = null;
        if (entreprise.tags && Array.isArray(entreprise.tags)) {
            for (const t of entreprise.tags) {
                switch (t) {
                    case 'lang_fr': langChipLabel = 'FR'; break;
                    case 'lang_en': langChipLabel = 'EN'; break;
                    case 'lang_de': langChipLabel = 'DE'; break;
                    case 'lang_es': langChipLabel = 'ES'; break;
                    case 'lang_it': langChipLabel = 'IT'; break;
                    case 'lang_nl': langChipLabel = 'NL'; break;
                    case 'lang_pt': langChipLabel = 'PT'; break;
                    case 'lang_autre': langChipLabel = 'Autre'; break;
                    default: break;
                }
                if (langChipLabel) break;
            }
        }

        const tagsHtml = entreprise.tags && entreprise.tags.length > 0
            ? entreprise.tags
                .slice()
                .sort((a, b) => {
                    const priority = (t) => {
                        if (!t) return 999;
                        if (t === 'fort_potentiel_refonte') return 1;
                        if (t === 'risque_cyber_eleve') return 2;
                        if (t === 'seo_a_ameliorer') return 3;
                        if (t === 'perf_lente' || t === 'perf:low') return 4;
                        if (t === 'perf:good') return 5;
                        if (t === 'site_sans_https') return 6;
                        if (t.startsWith('cms:')) return 7;
                        if (t.startsWith('framework:')) return 8;
                        if (t === 'blog' || t === 'contact_form' || t === 'ecommerce') return 9;
                        if (String(t).startsWith('lang_')) return 10;
                        return 50;
                    };
                    return priority(a) - priority(b);
                })
                .map(tag => {
                const base = 'tag';
                const isCms = typeof tag === 'string' && tag.startsWith('cms:');
                const isFramework = typeof tag === 'string' && tag.startsWith('framework:');
                const isPerf = typeof tag === 'string' && tag.startsWith('perf:');
                const extra =
                    tag === 'fort_potentiel_refonte' ? ' tag-refonte' :
                    tag === 'risque_cyber_eleve' ? ' tag-risk' :
                    tag === 'seo_a_ameliorer' ? ' tag-seo' :
                    tag === 'perf_lente' ? ' tag-perf' :
                    tag === 'site_sans_https' ? ' tag-https' :
                    tag === 'blog' ? ' tag-blog' :
                    tag === 'contact_form' ? ' tag-form' :
                    tag === 'ecommerce' ? ' tag-ecommerce' :
                    (isCms ? ' tag-cms' : '') +
                    (isFramework ? ' tag-framework' : '') +
                    (isPerf && tag.endsWith('good') ? ' tag-perf-good' : '') +
                    (isPerf && tag.endsWith('low') ? ' tag-perf-low' : '') +
                    '';

                let label;
                switch (tag) {
                    case 'fort_potentiel_refonte':
                        label = 'Fort potentiel refonte';
                        break;
                    case 'risque_cyber_eleve':
                        label = 'Risque cyber élevé';
                        break;
                    case 'seo_a_ameliorer':
                        label = 'SEO à améliorer';
                        break;
                    case 'perf_lente':
                        label = 'Site lent';
                        break;
                    case 'site_sans_https':
                        label = 'Sans HTTPS';
                        break;
                    case 'blog':
                        label = 'Blog';
                        break;
                    case 'contact_form':
                        label = 'Formulaire';
                        break;
                    case 'ecommerce':
                        label = 'E‑commerce';
                        break;
                    case 'lang_fr':
                        label = 'FR';
                        break;
                    case 'lang_en':
                        label = 'EN';
                        break;
                    case 'lang_de':
                        label = 'DE';
                        break;
                    case 'lang_es':
                        label = 'ES';
                        break;
                    case 'lang_it':
                        label = 'IT';
                        break;
                    case 'lang_nl':
                        label = 'NL';
                        break;
                    case 'lang_pt':
                        label = 'PT';
                        break;
                    case 'lang_autre':
                        label = 'Autre langue';
                        break;
                    default:
                        if (isCms) {
                            label = 'CMS: ' + tag.slice('cms:'.length);
                        } else if (isFramework) {
                            label = 'FW: ' + tag.slice('framework:'.length);
                        } else if (isPerf) {
                            const v = tag.slice('perf:'.length);
                            label = v === 'good' ? 'Perf OK' : v === 'low' ? 'Perf faible' : ('Perf: ' + v);
                        } else {
                            label = tag.replace(/_/g, ' ');
                        }
                }

                return `<span class="${base}${extra}" data-tag="${Formatters.escapeHtml(tag)}">${Formatters.escapeHtml(label)}</span>`;
            }).join('')
            : '';
        const visibleTagsHtml = [opportunityTagHtml, tagsHtml].filter(Boolean).join('');

        const hasSecurityScore = typeof entreprise.score_securite !== 'undefined' && entreprise.score_securite !== null;
        const hasSeoScore = typeof entreprise.score_seo !== 'undefined' && entreprise.score_seo !== null;
        const hasPentestScore = typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null;
        const chartSize = 44;

        function rowScoreSlot(type, label, hasScore, scoreValue, color) {
            if (hasScore) {
                return `
                <div class="score-chart-item row-score-item" data-analysis-type="${type}" data-entreprise-id="${entreprise.id}">
                    <div class="score-chart-visual row-score-visual">
                        ${createCircularChart(scoreValue, label, color, chartSize)}
                        <div class="score-loader row-score-loader"><i class="fas fa-circle-notch fa-spin"></i></div>
                    </div>
                    <button type="button" class="score-relaunch-btn row-relaunch-btn" data-analysis-type="${type}" data-entreprise-id="${entreprise.id}" title="Relancer l'analyse ${label}"><i class="fas fa-sync-alt"></i></button>
                </div>`;
            }
            return `
                <div class="score-chart-item row-score-item row-score-item--empty" data-analysis-type="${type}" data-entreprise-id="${entreprise.id}">
                    <div class="row-score-empty-visual">
                        <i class="fas fa-play" aria-hidden="true"></i>
                        <span class="row-score-empty-label">Lancer</span>
                        <div class="score-loader row-score-loader"><i class="fas fa-circle-notch fa-spin"></i></div>
                    </div>
                    <button type="button" class="score-relaunch-btn row-launch-btn" data-analysis-type="${type}" data-entreprise-id="${entreprise.id}" title="Lancer l'analyse ${label}"><i class="fas fa-play"></i></button>
                </div>`;
        }

        const rowScoresSection = `
            <div class="row-scores-section">
                ${rowScoreSlot('technique', 'technique', hasSecurityScore, entreprise.score_securite, null)}
                ${rowScoreSlot('seo', 'SEO', hasSeoScore, entreprise.score_seo, null)}
                ${rowScoreSlot('pentest', 'Pentest', hasPentestScore, entreprise.score_pentest, '#ef4444')}
            </div>
        `;

        let rowMainImage = entreprise.og_image || entreprise.logo || entreprise.favicon || null;
        if (!rowMainImage && entreprise.og_data) {
            const ogDataList = Array.isArray(entreprise.og_data) ? entreprise.og_data : [entreprise.og_data];
            for (const ogData of ogDataList) {
                if (ogData && ogData.images && ogData.images.length > 0 && ogData.images[0].image_url) {
                    rowMainImage = ogData.images[0].image_url;
                    break;
                }
            }
        }
        const rowDomain = getDisplayDomain(entreprise.website || rowMainImage || '');
        const rowInitials = getInitials(entreprise.nom || '');
        const rowSafeImage = rowMainImage ? normalizeToHttps(rowMainImage) : '';
        const rowFallbackGoogle = faviconFallbackUrl(rowDomain, 'google');
        const rowFallbackDdg = faviconFallbackUrl(rowDomain, 'ddg');

        const isSelected = selectedEntreprises.has(entreprise.id);

        return `
            <div class="entreprise-row${isSelected ? ' entreprise-selected' : ''}" data-id="${entreprise.id}">
                <div class="row-logo" aria-hidden="true">
                    <input 
                        type="checkbox" 
                        class="entreprise-select-checkbox" 
                        data-entreprise-id="${entreprise.id}" 
                        ${isSelected ? 'checked' : ''} 
                        title="Sélectionner cette entreprise"
                        style="position:absolute; top:-6px; left:-6px; width:16px; height:16px;"
                    >
                    <img
                        src="${rowSafeImage || rowFallbackGoogle}"
                        alt=""
                        class="row-logo-img"
                        loading="lazy"
                        referrerpolicy="no-referrer"
                        data-fallback-step="0"
                        onload="if (this.nextElementSibling) this.nextElementSibling.style.display='none';"
                        onerror="
                            var step = (this.dataset && this.dataset.fallbackStep) ? this.dataset.fallbackStep : '0';
                            if (step === '0' && '${rowFallbackGoogle}') { this.dataset.fallbackStep = '1'; this.src='${rowFallbackGoogle}'; return; }
                            if (step === '1' && '${rowFallbackDdg}') { this.dataset.fallbackStep = '2'; this.src='${rowFallbackDdg}'; return; }
                            this.style.display='none'; if (this.nextElementSibling) this.nextElementSibling.style.display='flex';
                        "
                    >
                    <div class="row-logo-placeholder" style="display: ${rowSafeImage || rowFallbackGoogle ? 'none' : 'flex'};">${Formatters.escapeHtml(rowInitials)}</div>
                </div>
                <div class="row-main">
                    <div class="row-name">
                        <div class="row-name-line">
                            <h3>${Formatters.escapeHtml(entreprise.nom || 'Sans nom')}</h3>
                            ${typeof entreprise.score_pentest !== 'undefined' && entreprise.score_pentest !== null && entreprise.score_pentest >= 40 ? `
                            <i class="fas fa-exclamation-triangle row-pentest-warn" style="color: ${entreprise.score_pentest >= 70 ? '#ef4444' : '#f59e0b'};" title="Score Pentest: ${entreprise.score_pentest}/100"></i>
                            ` : ''}
                        </div>
                        ${visibleTagsHtml ? `<div class="tags-container">${visibleTagsHtml}</div>` : ''}
                    </div>
                    <div class="row-meta">
                        ${entreprise.secteur ? `<span class="row-chip row-chip-sector" title="Secteur"><i class="fas fa-industry" aria-hidden="true"></i> ${Formatters.escapeHtml(entreprise.secteur)}</span>` : ''}
                        ${langChipLabel ? `<span class="row-chip row-chip-lang" title="Langue principale"><i class="fas fa-language" aria-hidden="true"></i> ${Formatters.escapeHtml(langChipLabel)}</span>` : ''}
                        ${commercialTopMode && entreprise.priority_score != null ? `
                        <span class="row-chip row-chip-priority" title="Priorité commerciale">
                            <i class="fas fa-sort-amount-down" aria-hidden="true"></i> ${Math.round(Number(entreprise.priority_score))}
                            ${entreprise.last_touchpoint_at ? ` · ${Formatters.escapeHtml(String(entreprise.last_touchpoint_at).slice(0, 16))}` : ' · —'}
                        </span>` : ''}
                        ${entreprise.statut ? (() => {
                            const statut = String(entreprise.statut || '').trim();
                            const cls = (Badges && typeof Badges.getStatusClass === 'function') ? Badges.getStatusClass(statut) : 'secondary';
                            const icon = statut === 'Nouveau' ? 'fa-bolt'
                                : statut === 'À qualifier' ? 'fa-question-circle'
                                : statut === 'Relance' ? 'fa-phone'
                                : statut === 'Gagné' ? 'fa-trophy'
                                : statut === 'Perdu' ? 'fa-times-circle'
                                : statut === 'Désabonné' ? 'fa-ban'
                                : statut === 'Réponse négative' ? 'fa-thumbs-down'
                                : statut === 'Réponse positive' ? 'fa-thumbs-up'
                                : statut === 'Bounce' ? 'fa-exclamation-triangle'
                                : statut === 'Plainte spam' ? 'fa-skull-crossbones'
                                : statut === 'Ne pas contacter' ? 'fa-user-slash'
                                : statut === 'À rappeler' ? 'fa-clock'
                                : 'fa-tag';
                            return `<span class="row-chip row-chip-status badge badge-${cls}" title="Statut"><i class="fas ${icon}" aria-hidden="true"></i> ${Formatters.escapeHtml(statut)}</span>`;
                        })() : ''}
                        ${entreprise.email_principal ? `<span class="row-meta-item row-meta-email">${Formatters.escapeHtml(entreprise.email_principal)}</span>` : ''}
                    </div>
                </div>
                ${rowScoresSection}
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
        const pagination = document.getElementById('pagination');
        if (!pagination) return;
        if (commercialTopMode) {
            pagination.innerHTML = '<p class="pagination-commercial-hint">Tri : score pondéré (SEO, sécu, perf, opportunité) puis entreprises sans contact récent en priorité.</p>';
            return;
        }
        const totalPages = Math.ceil(totalEntreprises / itemsPerPage);
        
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            pagination.style.display = 'none';
            return;
        }
        
        pagination.style.display = '';
        
        const start = (currentPage - 1) * itemsPerPage + 1;
        const end = Math.min(currentPage * itemsPerPage, totalEntreprises);
        
        let html = '<div class="pagination-info">';
        html += `${start}–${end} sur ${totalEntreprises}`;
        html += '</div>';
        html += '<div class="pagination-controls">';
        html += `<button class="btn-pagination btn-pagination-nav ${currentPage === 1 ? 'disabled' : ''}" data-page="${currentPage - 1}" title="Précédent (←)">← Précédent</button>`;
        
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
                html += `<button class="btn-pagination ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
            } else if (i === currentPage - 3 || i === currentPage + 3) {
                html += '<span class="pagination-ellipsis">...</span>';
            }
        }
        
        html += `<button class="btn-pagination btn-pagination-nav ${currentPage === totalPages ? 'disabled' : ''}" data-page="${currentPage + 1}" title="Suivant (→)">Suivant →</button>`;
        
        if (totalPages > 5) {
            html += '<div class="pagination-jump">';
            html += '<label for="pagination-jump-input">Aller à</label>';
            html += `<input type="number" id="pagination-jump-input" min="1" max="${totalPages}" value="${currentPage}" aria-label="Page">`;
            html += '</div>';
        }
        html += '<div class="pagination-page-size">';
        html += '<label for="page-size-select">Par page</label>';
        html += '<select id="page-size-select" class="form-select form-select-compact">';
        html += '<option value="20">20</option>';
        html += '<option value="50">50</option>';
        html += '<option value="100">100</option>';
        html += '</select>';
        html += '</div>';
        html += '</div>';
        pagination.innerHTML = html;
        
        pagination.querySelectorAll('.btn-pagination').forEach(btn => {
            btn.addEventListener('click', async () => {
                const page = parseInt(btn.dataset.page);
                if (page >= 1 && page <= totalPages && !btn.classList.contains('disabled')) {
                    currentPage = page;
                    try {
                        if (window.localStorage) {
                            window.localStorage.setItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY, String(currentPage));
                        }
                    } catch (e) {}
                    await loadEntreprises();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        });
        
        const jumpInput = document.getElementById('pagination-jump-input');
        if (jumpInput) {
            const goToPage = async () => {
                const page = parseInt(jumpInput.value, 10);
                if (page >= 1 && page <= totalPages) {
                    currentPage = page;
                    try {
                        if (window.localStorage) {
                            window.localStorage.setItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY, String(currentPage));
                        }
                    } catch (e) {}
                    await loadEntreprises();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                } else {
                    jumpInput.value = currentPage;
                }
            };
            jumpInput.addEventListener('change', goToPage);
            jumpInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    goToPage();
                }
            });
        }

        const pageSizeSelect = document.getElementById('page-size-select');
        if (pageSizeSelect) {
            try {
                const initial = itemsPerPage || 20;
                if ([...pageSizeSelect.options].some(o => parseInt(o.value, 10) === initial)) {
                    pageSizeSelect.value = String(initial);
                }
            } catch (e) {
                // ignore
            }
            pageSizeSelect.addEventListener('change', () => {
                const value = parseInt(pageSizeSelect.value, 10);
                if (!Number.isFinite(value)) return;
                itemsPerPage = Math.min(200, Math.max(10, value));
                try {
                    if (window.localStorage) {
                        window.localStorage.setItem('entreprises_page_size', String(itemsPerPage));
                    }
                } catch (e) {
                    // ignore
                }
                currentPage = 1;
                try {
                    if (window.localStorage) {
                        window.localStorage.setItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY, String(currentPage));
                    }
                } catch (e) {}
                loadEntreprises();
            });
        }
    }
    
    function setupPaginationKeyboard() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            const totalPages = Math.ceil(totalEntreprises / itemsPerPage);
            if (totalPages <= 1) return;
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                if (currentPage > 1) {
                    currentPage--;
                    try {
                        if (window.localStorage) {
                            window.localStorage.setItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY, String(currentPage));
                        }
                    } catch (e) {}
                    loadEntreprises().then(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
                }
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                if (currentPage < totalPages) {
                    currentPage++;
                    try {
                        if (window.localStorage) {
                            window.localStorage.setItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY, String(currentPage));
                        }
                    } catch (e) {}
                    loadEntreprises().then(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
                }
            }
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
        
        const selectCheckboxes = document.querySelectorAll(`.entreprise-select-checkbox[data-entreprise-id="${entrepriseId}"]`);
        if (selectCheckboxes.length) {
            selectCheckboxes.forEach(cb => {
                cb.addEventListener('change', (e) => {
                    e.stopPropagation();
                    const selected = cb.checked;
                    setEntrepriseSelected(entrepriseId, selected);
                });
            });
        }

        const scoreButtons = document.querySelectorAll(`.score-relaunch-btn[data-entreprise-id="${entrepriseId}"]`);
        if (scoreButtons.length) {
            scoreButtons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const analysisType = btn.getAttribute('data-analysis-type');
                    triggerAnalysisRelaunch(entrepriseId, analysisType);
                });
            });
        }
    }

    function setEntrepriseSelected(entrepriseId, selected) {
        if (selected) {
            selectedEntreprises.add(entrepriseId);
        } else {
            selectedEntreprises.delete(entrepriseId);
        }
        const nodes = document.querySelectorAll(`.entreprise-card[data-id="${entrepriseId}"], .entreprise-row[data-id="${entrepriseId}"]`);
        nodes.forEach(el => el.classList.toggle('entreprise-selected', selected));
        const checkboxes = document.querySelectorAll(`.entreprise-select-checkbox[data-entreprise-id="${entrepriseId}"]`);
        checkboxes.forEach(cb => { cb.checked = selected; });
        updateBulkSelectionUI();
    }

    function setupClickToSelectCards() {
        const container = document.getElementById('entreprises-container');
        if (!container) return;
        if (container.dataset.clickSelectSetup === '1') return;
        container.dataset.clickSelectSetup = '1';

        const isInteractiveTarget = (el) => {
            if (!el) return false;
            return Boolean(
                el.closest('button, a, input, select, textarea, label, details, summary, .btn, .btn-icon, .btn-view-details, .btn-delete-entreprise, .btn-favori, .btn-groups, .score-relaunch-btn')
            );
        };

        container.addEventListener('click', (e) => {
            const tagEl = e.target.closest('.tags-container .tag');
            if (tagEl) {
                const raw = tagEl.getAttribute('data-tag') || '';
                addTagToFilter(raw);
                const input = document.getElementById('filter-tags');
                if (input) input.focus();
                return;
            }
            if (isInteractiveTarget(e.target)) return;
            // Sélection uniquement en vue liste (ligne)
            if (typeof currentView !== 'undefined' && currentView !== 'list') return;
            const row = e.target.closest('.entreprise-row');
            if (!row) return;
            const rawId = row.getAttribute('data-id');
            const id = rawId ? parseInt(rawId, 10) : NaN;
            if (Number.isNaN(id)) return;
            const selected = selectedEntreprises.has(id);
            setEntrepriseSelected(id, !selected);
        });
    }

    function updateBulkSelectionUI() {
        const countEl = document.getElementById('bulk-selected-count');
        const bulkActionsEl = document.querySelector('.bulk-actions');
        const applyBtn = document.getElementById('bulk-apply-btn');
        const actionSelect = document.getElementById('bulk-action-select');
        if (!countEl) return;
        const count = selectedEntreprises.size;
        if (count === 0) {
            countEl.textContent = 'Aucune entreprise sélectionnée';
            if (bulkActionsEl) bulkActionsEl.classList.add('disabled');
            if (applyBtn) applyBtn.disabled = true;
        } else if (count === 1) {
            countEl.textContent = '1 entreprise sélectionnée';
            if (bulkActionsEl) bulkActionsEl.classList.remove('disabled');
            if (applyBtn) applyBtn.disabled = !actionSelect || !actionSelect.value;
        } else {
            countEl.textContent = `${count} entreprises sélectionnées`;
            if (bulkActionsEl) bulkActionsEl.classList.remove('disabled');
            if (applyBtn) applyBtn.disabled = !actionSelect || !actionSelect.value;
        }
    }

    async function triggerAnalysisRelaunch(entrepriseId, analysisType, options = {}) {
        const notify = options.notify !== false;
        const entreprise = allEntreprises.find(e => e && e.id === entrepriseId)
            || filteredEntreprises.find(e => e && e.id === entrepriseId);
        const url = entreprise && entreprise.website ? String(entreprise.website).trim() : '';
        if (!url) {
            if (notify) {
                Notifications.show('Aucune URL de site pour relancer l\'analyse.', 'warning');
            }
            return;
        }

        const socket = window.wsManager && window.wsManager.socket;
        if (!socket) {
            if (notify) {
                Notifications.show('Connexion temps réel non disponible. Rechargez la page.', 'warning');
            }
            return;
        }

        ensureModalWebSocketListeners();
        setScoreRelaunchLoading(entrepriseId, analysisType, true);

        const launchLabels = { technique: 'technique', seo: 'SEO', osint: 'OSINT', pentest: 'Pentest' };
        const nom = entreprise && entreprise.nom ? entreprise.nom : getEntrepriseNom(entrepriseId);
        if (notify) {
            Notifications.show(nom + ' — Analyse ' + (launchLabels[analysisType] || analysisType) + ' lancée...', 'info', 'fa-play-circle');
        }

        if (analysisType === 'technique') {
            socket.emit('start_technical_analysis', { url, entreprise_id: entrepriseId });
        } else if (analysisType === 'seo') {
            socket.emit('start_seo_analysis', { url, entreprise_id: entrepriseId, use_lighthouse: true });
        } else if (analysisType === 'osint') {
            socket.emit('start_osint_analysis', { url, entreprise_id: entrepriseId });
        } else if (analysisType === 'pentest') {
            socket.emit('start_pentest_analysis', { url, entreprise_id: entrepriseId });
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
        
        // Permet aux gestionnaires internes de fermer le menu après une action.
        dropdown.__close = closeDropdown;

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
                    // Forcer un rechargement des listes de groupes (filtre + bulk)
                    try {
                        await loadGroupFilter();
                    } catch (e) {
                        console.error('[entreprises] Erreur refresh filtre groupes après création:', e);
                    }
                    const bulkGroupSelectEl = document.getElementById('bulk-group-select');
                    if (bulkGroupSelectEl) {
                        bulkGroupSelectEl.dataset.loaded = '0';
                    }
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
                    
                    // Fermer le menu après création pour éviter de rester sur un état obsolète.
                    if (typeof dropdown.__close === 'function') {
                        dropdown.__close();
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
                        <button type="button" class="group-edit-btn" title="Renommer le groupe"><i class="fas fa-pen"></i></button>
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
                        
                        // Mettre à jour uniquement l'élément concerné (pas de rechargement complet).
                        // Note: on met à jour de façon "optimiste" le compteur si on a une valeur numérique.
                        const newIsActive = !isActive;
                        item.classList.toggle('active', newIsActive);
                        
                        const delta = newIsActive ? 1 : -1;
                        const countEl = item.querySelector('.group-count');
                        if (countEl) {
                            const oldCount = parseInt(countEl.textContent, 10);
                            if (!Number.isNaN(oldCount)) {
                                const newCount = Math.max(0, oldCount + delta);
                                countEl.textContent = String(newCount);
                            }
                        }
                        
                        const updateOptionCountInSelect = (selectId) => {
                            const selectEl = document.getElementById(selectId);
                            if (!selectEl) return;
                            const opt = selectEl.querySelector(`option[value="${groupId}"]`);
                            if (!opt) return;
                            const match = (opt.textContent || '').match(/\((\d+)\)/);
                            if (!match) return;
                            const oldCount = parseInt(match[1], 10);
                            if (Number.isNaN(oldCount)) return;
                            const newCount = Math.max(0, oldCount + delta);
                            opt.textContent = (opt.textContent || '').replace(/\(\d+\)/, `(${newCount})`);
                        };
                        
                        updateOptionCountInSelect('filter-groupe');
                        updateOptionCountInSelect('bulk-group-select');
                        
                        // Mettre à jour aussi le cache local pour le dropdown.
                        const cacheForEntreprise = entrepriseGroupsCache[entrepriseId];
                        if (Array.isArray(cacheForEntreprise)) {
                            const g = cacheForEntreprise.find(x => x && x.id === groupId);
                            if (g) {
                                g.is_member = newIsActive;
                                if (typeof g.entreprises_count === 'number') {
                                    g.entreprises_count = Math.max(0, g.entreprises_count + delta);
                                }
                            }
                        }
                        // Re-filtres (avec filtres avancés) pour que l'entreprise disparaisse si elle ne match plus.
                        scheduleApplyFilters();
                        
                        // Fermer le menu après ajout/retrait.
                        if (typeof dropdown.__close === 'function') {
                            dropdown.__close();
                        }
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
                        Notifications.show('Groupe supprimé', 'success');
                        
                        // Mettre à jour uniquement l'UI concernée (pas de rechargement complet).
                        try {
                            // Supprimer l'item du dropdown de l'entreprise courante.
                            if (item && typeof item.remove === 'function') {
                                item.remove();
                            }
                        } catch (e) {}
                        
                        // Mettre à jour le cache local du dropdown.
                        const cacheForEntreprise = entrepriseGroupsCache[entrepriseId];
                        if (Array.isArray(cacheForEntreprise)) {
                            entrepriseGroupsCache[entrepriseId] = cacheForEntreprise.filter(x => x && x.id !== groupId);
                        }
                        
                        // Mettre à jour le select global filtre + bulk.
                        const filterSelect = document.getElementById('filter-groupe');
                        if (filterSelect) {
                            const opt = filterSelect.querySelector(`option[value="${groupId}"]`);
                            if (opt) opt.remove();
                            const wasSelected = String(filterSelect.value) === String(groupId);
                            if (wasSelected) {
                                filterSelect.value = '';
                            }
                            if (typeof updateAdvancedFiltersBadge === 'function' && (wasSelected || !filterSelect.value)) {
                                updateAdvancedFiltersBadge();
                            }
                        }
                        const bulkGroupSelectEl = document.getElementById('bulk-group-select');
                        if (bulkGroupSelectEl) {
                            const opt = bulkGroupSelectEl.querySelector(`option[value="${groupId}"]`);
                            if (opt) opt.remove();
                            // Ne pas forcer la valeur si l'user a déjà choisi un autre groupe.
                        }
                        
                        // Rafraîchir la liste de résultats si les filtres avancés dépendent de l'appartenance/groupe.
                        scheduleApplyFilters();
                        
                        // Important: ne pas fermer le menu ici (ton cas: suppression de groupe).
                    } catch (error) {
                        console.error(error);
                        Notifications.show('Erreur lors de la suppression du groupe', 'error');
                    }
                });
            });

            // Renommer un groupe
            listEl.querySelectorAll('.group-edit-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const item = btn.closest('.group-item');
                    if (!item) return;
                    const groupId = parseInt(item.dataset.groupId, 10);
                    const nameEl = item.querySelector('.group-name');
                    const currentName = nameEl ? nameEl.textContent.trim() : '';
                    const newName = window.prompt('Nouveau nom du groupe :', currentName);
                    if (newName === null) {
                        return; // annulé
                    }
                    const trimmed = newName.trim();
                    if (!trimmed) {
                        Notifications.show('Le nom du groupe ne peut pas être vide.', 'warning');
                        return;
                    }
                    try {
                        await EntreprisesAPI.updateGroupe(groupId, { nom: trimmed });
                        
                        // Mettre à jour uniquement l'élément concerné.
                        if (nameEl) nameEl.textContent = trimmed;
                        
                        const cacheForEntreprise = entrepriseGroupsCache[entrepriseId];
                        if (Array.isArray(cacheForEntreprise)) {
                            const g = cacheForEntreprise.find(x => x && x.id === groupId);
                            if (g) g.nom = trimmed;
                        }
                        
                        // Mettre à jour les options dans les selects (filtre + bulk) sans recharger toute la liste.
                        const updateOptionNameInSelect = (selectId) => {
                            const selectEl = document.getElementById(selectId);
                            if (!selectEl) return;
                            const opt = selectEl.querySelector(`option[value="${groupId}"]`);
                            if (!opt) return;
                            const matchCount = (opt.textContent || '').match(/\((\d+)\)/);
                            const countPart = matchCount ? ` (${matchCount[1]})` : '';
                            opt.textContent = trimmed + countPart;
                        };
                        updateOptionNameInSelect('filter-groupe');
                        updateOptionNameInSelect('bulk-group-select');
                        
                        Notifications.show('Nom du groupe mis à jour', 'success');
                        
                        // Rafraîchir la liste de résultats (les filtres peuvent dépendre de l'existence du groupe).
                        scheduleApplyFilters();
                        
                        // Fermer le menu après renommage.
                        if (typeof dropdown.__close === 'function') {
                            dropdown.__close();
                        }
                    } catch (error) {
                        console.error(error);
                        Notifications.show('Erreur lors de la mise à jour du groupe', 'error');
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
            'filter-groupe',
            'filter-opportunite',
            'filter-statut',
            'filter-etape-prospection',
            'filter-commercial-profile',
            'filter-security-min',
            'filter-security-max',
            'filter-seo-min',
            'filter-seo-max',
            'filter-pentest-min',
            'filter-pentest-max',
            'filter-security-null',
            'filter-seo-null',
            'filter-pentest-null',
            'filter-has-email',
            'filter-cms',
            'filter-framework',
            'filter-has-blog',
            'filter-has-form',
            'filter-has-tunnel'
        ];
        const handledAdvancedFilterIds = new Set(advancedFilterIds);

        advancedFilterIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', () => {
                    if (id === 'filter-commercial-profile') {
                        updateCommercialProfileWeightsVisual();
                    }
                    if (id.endsWith('-null')) {
                        syncScoreNullSlidersDisabled();
                    }
                    updateAdvancedFiltersBadge();
                    debouncedApplyFilters();
                });
            }
        });

        // Filet de sécurité: tout nouveau filtre ajouté dans #advanced-filters
        // avec un id "filter-*" déclenche aussi le refresh auto, même s'il n'est
        // pas encore listé explicitement ci-dessus.
        const advancedFiltersRoot = document.getElementById('advanced-filters');
        if (advancedFiltersRoot) {
            advancedFiltersRoot.addEventListener('change', (e) => {
                const target = e.target;
                if (!target || !target.id || !String(target.id).startsWith('filter-')) return;
                if (handledAdvancedFilterIds.has(target.id)) return;
                updateAdvancedFiltersBadge();
                debouncedApplyFilters();
            });
        }

        // Pills de statut
        const statutPills = document.querySelectorAll('#filter-statut-pills .pill');
        if (statutPills.length) {
            statutPills.forEach(pill => {
                pill.addEventListener('click', () => {
                    const value = pill.dataset.value || '';
                    const hiddenInput = document.getElementById('filter-statut');
                    if (hiddenInput) {
                        hiddenInput.value = value;
                    }
                    statutPills.forEach(p => p.classList.remove('active'));
                    pill.classList.add('active');
                    updateAdvancedFiltersBadge();
                    debouncedApplyFilters();
                });
            });
        }

        const btnCommercialTop = document.getElementById('btn-commercial-top');
        const btnCommercialOff = document.getElementById('btn-commercial-top-off');
        if (btnCommercialTop) {
            btnCommercialTop.addEventListener('click', async () => {
                commercialTopMode = true;
                currentPage = 1;
                try {
                    if (window.localStorage) {
                        window.localStorage.setItem(ENTREPRISES_CURRENT_PAGE_STORAGE_KEY, String(currentPage));
                    }
                } catch (e) {}
                await loadEntreprises();
                if (window.Notifications && typeof Notifications.show === 'function') {
                    Notifications.show('Vue « Top 50 commercial » (pondération + dernier contact)', 'info');
                }
            });
        }
        if (btnCommercialOff) {
            btnCommercialOff.addEventListener('click', async () => {
                commercialTopMode = false;
                await loadEntreprises();
            });
        }

        // Mise à jour des labels des jauges
        const securitySliderMin = document.getElementById('filter-security-min');
        const securitySliderMax = document.getElementById('filter-security-max');
        const seoSliderMin = document.getElementById('filter-seo-min');
        const seoSliderMax = document.getElementById('filter-seo-max');
        const pentestSliderMin = document.getElementById('filter-pentest-min');
        const pentestSliderMax = document.getElementById('filter-pentest-max');
        const securityLabelMin = document.getElementById('filter-security-min-value');
        const securityLabelMax = document.getElementById('filter-security-max-value');
        const seoLabelMin = document.getElementById('filter-seo-min-value');
        const seoLabelMax = document.getElementById('filter-seo-max-value');
        const pentestLabelMin = document.getElementById('filter-pentest-min-value');
        const pentestLabelMax = document.getElementById('filter-pentest-max-value');

        if (securitySliderMin && securityLabelMin) {
            securityLabelMin.textContent = formatScoreMinLabel(securitySliderMin.value);
            securitySliderMin.addEventListener('input', () => {
                securityLabelMin.textContent = formatScoreMinLabel(securitySliderMin.value);
                updateAdvancedFiltersBadge();
                debouncedApplyFilters();
            });
        }

        if (securitySliderMax && securityLabelMax) {
            securityLabelMax.textContent = formatScoreMaxLabel(securitySliderMax.value);
            securitySliderMax.addEventListener('input', () => {
                securityLabelMax.textContent = formatScoreMaxLabel(securitySliderMax.value);
                updateAdvancedFiltersBadge();
                debouncedApplyFilters();
            });
        }

        if (seoSliderMin && seoLabelMin) {
            seoLabelMin.textContent = formatScoreMinLabel(seoSliderMin.value);
            seoSliderMin.addEventListener('input', () => {
                seoLabelMin.textContent = formatScoreMinLabel(seoSliderMin.value);
                updateAdvancedFiltersBadge();
                debouncedApplyFilters();
            });
        }

        if (seoSliderMax && seoLabelMax) {
            seoLabelMax.textContent = formatScoreMaxLabel(seoSliderMax.value);
            seoSliderMax.addEventListener('input', () => {
                seoLabelMax.textContent = formatScoreMaxLabel(seoSliderMax.value);
                updateAdvancedFiltersBadge();
                debouncedApplyFilters();
            });
        }

        if (pentestSliderMin && pentestLabelMin) {
            pentestLabelMin.textContent = formatScoreMinLabel(pentestSliderMin.value);
            pentestSliderMin.addEventListener('input', () => {
                pentestLabelMin.textContent = formatScoreMinLabel(pentestSliderMin.value);
                updateAdvancedFiltersBadge();
                debouncedApplyFilters();
            });
        }

        if (pentestSliderMax && pentestLabelMax) {
            pentestLabelMax.textContent = formatScoreMaxLabel(pentestSliderMax.value);
            pentestSliderMax.addEventListener('input', () => {
                pentestLabelMax.textContent = formatScoreMaxLabel(pentestSliderMax.value);
                updateAdvancedFiltersBadge();
                debouncedApplyFilters();
            });
        }

        syncScoreNullSlidersDisabled();

        // Actions de masse (sélection, relance, groupes)
        const bulkSelectAllBtn = document.getElementById('bulk-select-all');
        const bulkSelectNoneBtn = document.getElementById('bulk-select-none');
        const bulkActionSelect = document.getElementById('bulk-action-select');
        const bulkGroupSelect = document.getElementById('bulk-group-select');
        const bulkApplyBtn = document.getElementById('bulk-apply-btn');

        async function ensureBulkGroupsLoaded(forceRefresh) {
            if (!bulkGroupSelect) return;
            if (!forceRefresh && bulkGroupSelect.dataset.loaded === '1') return;
            try {
                const groupes = await EntreprisesAPI.loadGroupes();
                bulkGroupSelect.innerHTML = '<option value=\"\">Choisir un groupe...</option>';
                (groupes || []).forEach(g => {
                    const parts = [];
                    if (g.nom) {
                        parts.push(Formatters.escapeHtml(g.nom));
                    } else {
                        parts.push('Groupe #' + String(g.id));
                    }
                    if (typeof g.entreprises_count !== 'undefined' && g.entreprises_count !== null) {
                        parts.push(`(${g.entreprises_count})`);
                    }
                    bulkGroupSelect.insertAdjacentHTML(
                        'beforeend',
                        `<option value=\"${g.id}\">${parts.join(' ')}</option>`
                    );
                });
                bulkGroupSelect.dataset.loaded = '1';
            } catch (e) {
                console.error('Erreur chargement groupes (bulk):', e);
                Notifications.show('Erreur lors du chargement des groupes', 'error');
            }
        }

        if (bulkSelectAllBtn) {
            bulkSelectAllBtn.addEventListener('click', () => {
                if (!Array.isArray(filteredEntreprises)) return;
                filteredEntreprises.forEach(e => {
                    if (e && e.id != null) setEntrepriseSelected(e.id, true);
                });
            });
        }

        if (bulkSelectNoneBtn) {
            bulkSelectNoneBtn.addEventListener('click', () => {
                const ids = Array.from(selectedEntreprises);
                ids.forEach(id => setEntrepriseSelected(id, false));
            });
        }

        if (bulkActionSelect && bulkGroupSelect) {
            bulkActionSelect.addEventListener('change', async () => {
                const val = bulkActionSelect.value;
                const applyBtn = document.getElementById('bulk-apply-btn');
                if (val === 'group-add' || val === 'group-remove') {
                    bulkGroupSelect.style.display = 'inline-block';
                    await ensureBulkGroupsLoaded(true);
                } else {
                    bulkGroupSelect.style.display = 'none';
                }
                if (applyBtn) {
                    const hasSelection = selectedEntreprises.size > 0;
                    applyBtn.disabled = !val || !hasSelection;
                }
            });
        }

        if (bulkApplyBtn) {
            bulkApplyBtn.addEventListener('click', async () => {
                const action = bulkActionSelect ? bulkActionSelect.value : '';
                const ids = Array.from(selectedEntreprises);
                if (!ids.length) {
                    Notifications.show('Sélectionnez au moins une entreprise', 'warning');
                    return;
                }
                if (!action) {
                    Notifications.show('Choisissez une action à appliquer', 'warning');
                    return;
                }

                try {
                    if (action === 'launch-technique' || action === 'launch-seo' || action === 'launch-osint' || action === 'launch-pentest') {
                        const types = [action.replace('launch-', '')];
                        /** @type {{ id: number, t: string }[]} */
                        const jobs = [];
                        let skippedNoUrl = 0;
                        ids.forEach((id) => {
                            const entreprise = allEntreprises.find(e => e && e.id === id)
                                || filteredEntreprises.find(e => e && e.id === id);
                            const hasUrl = !!(entreprise && entreprise.website && String(entreprise.website).trim());
                            if (!hasUrl) {
                                skippedNoUrl++;
                                return;
                            }
                            types.forEach((t) => jobs.push({ id, t }));
                        });
                        const isOsint = action === 'launch-osint';
                        const staggerMs = isOsint
                            ? (jobs.length > 20 ? 1200 : 700)
                            : (jobs.length > 20 ? 700 : 300);
                        if (jobs.length === 0) {
                            Notifications.show(
                                'Aucune entreprise valide à relancer (URL manquante).',
                                'warning'
                            );
                            return;
                        }
                        if (jobs.length > 3) {
                            Notifications.show(
                                `${jobs.length} analyse(s) planifiées (lancement étalé ~${staggerMs} ms entre chaque pour ne pas saturer Celery).`,
                                'info',
                                'fa-layer-group'
                            );
                        }
                        if (skippedNoUrl > 0) {
                            Notifications.show(
                                `${skippedNoUrl} entreprise${skippedNoUrl > 1 ? 's' : ''} ignorée${skippedNoUrl > 1 ? 's' : ''} (URL manquante).`,
                                'warning'
                            );
                        }
                        jobs.forEach((job, i) => {
                            setTimeout(() => {
                                triggerAnalysisRelaunch(job.id, job.t, { notify: true });
                            }, i * staggerMs);
                        });
                    } else if (action === 'launch-scraping') {
                        const jobs = [];
                        let skippedNoUrl = 0;
                        ids.forEach((id) => {
                            const entreprise = allEntreprises.find(e => e && e.id === id)
                                || filteredEntreprises.find(e => e && e.id === id);
                            const hasUrl = !!(entreprise && entreprise.website && String(entreprise.website).trim());
                            if (!hasUrl) {
                                skippedNoUrl++;
                                return;
                            }
                            jobs.push({ id });
                        });
                        const staggerMs = jobs.length > 20 ? 900 : 450;
                        if (jobs.length === 0) {
                            Notifications.show(
                                'Aucune entreprise valide à relancer (URL manquante).',
                                'warning'
                            );
                            return;
                        }
                        if (jobs.length > 3) {
                            Notifications.show(
                                `${jobs.length} scraping(s) planifiés (lancement étalé ~${staggerMs} ms entre chaque pour ne pas saturer Celery).`,
                                'info',
                                'fa-layer-group'
                            );
                        }
                        if (skippedNoUrl > 0) {
                            Notifications.show(
                                `${skippedNoUrl} entreprise${skippedNoUrl > 1 ? 's' : ''} ignorée${skippedNoUrl > 1 ? 's' : ''} (URL manquante).`,
                                'warning'
                            );
                        }
                        jobs.forEach((job, i) => {
                            setTimeout(() => {
                                triggerScrapingRelaunch(job.id, { notify: true });
                            }, i * staggerMs);
                        });
                    } else if (action === 'delete-bulk') {
                        const count = ids.length;
                        if (!confirm(`Êtes-vous sûr de vouloir supprimer ${count} entreprise${count > 1 ? 's' : ''} ? Cette action est irréversible.`)) {
                            return;
                        }

                        let deletedCount = 0;
                        let failedCount = 0;
                        for (const id of ids) {
                            try {
                                await EntreprisesAPI.delete(id);
                                deletedCount++;
                                // Retirer du bloc sélectionné après suppression réussie.
                                setEntrepriseSelected(id, false);
                            } catch (e) {
                                failedCount++;
                                console.error('Erreur suppression entreprise (bulk):', id, e);
                            }
                        }

                        await applyFilters();
                        if (failedCount > 0) {
                            Notifications.show(
                                `Suppression terminée : ${deletedCount} supprimée${deletedCount > 1 ? 's' : ''}, ${failedCount} en échec.`,
                                'warning'
                            );
                        } else {
                            Notifications.show(
                                `${deletedCount} entreprise${deletedCount > 1 ? 's' : ''} supprimée${deletedCount > 1 ? 's' : ''}`,
                                'success'
                            );
                        }
                    } else if (action === 'group-add' || action === 'group-remove') {
                        const groupId = bulkGroupSelect && bulkGroupSelect.value ? parseInt(bulkGroupSelect.value, 10) : null;
                        if (!groupId) {
                            Notifications.show('Choisissez un groupe', 'warning');
                            return;
                        }
                        const isAdd = action === 'group-add';
                        for (const id of ids) {
                            try {
                                if (isAdd) {
                                    await EntreprisesAPI.addEntrepriseToGroupe(id, groupId);
                                } else {
                                    await EntreprisesAPI.removeEntrepriseFromGroupe(id, groupId);
                                }
                            } catch (e) {
                                console.error('Erreur mise à jour groupe pour entreprise', id, e);
                            }
                        }
                        Notifications.show(
                            `${ids.length} entreprise${ids.length > 1 ? 's' : ''} ${isAdd ? 'ajoutée(s) au' : 'retirée(s) du'} groupe`,
                            'success'
                        );
                        await applyFilters();
                        // Après une action de groupe en masse, rafraîchir immédiatement
                        // les compteurs dans le filtre et dans le select bulk
                        try {
                            await loadGroupFilter();
                        } catch (e) {
                            console.error('[entreprises] Erreur refresh filtre groupes après action de masse:', e);
                        }
                        try {
                            if (bulkGroupSelect) {
                                const groupes = await EntreprisesAPI.loadGroupes();
                                bulkGroupSelect.innerHTML = '<option value="">Choisir un groupe...</option>';
                                (groupes || []).forEach(g => {
                                    const parts = [];
                                    if (g.nom) {
                                        parts.push(Formatters.escapeHtml(g.nom));
                                    } else {
                                        parts.push('Groupe #' + String(g.id));
                                    }
                                    if (typeof g.entreprises_count !== 'undefined' && g.entreprises_count !== null) {
                                        parts.push(`(${g.entreprises_count})`);
                                    }
                                    bulkGroupSelect.insertAdjacentHTML(
                                        'beforeend',
                                        `<option value="${g.id}">${parts.join(' ')}</option>`
                                    );
                                });
                                bulkGroupSelect.dataset.loaded = '1';
                            }
                        } catch (e) {
                            console.error('[entreprises] Erreur refresh bulk groups après action de masse:', e);
                        }
                    } else if (action === 'recalculate-opportunity') {
                        Notifications.show(
                            `${ids.length} recalcul(s) d'opportunité en cours...`,
                            'info',
                            'fa-calculator'
                        );
                        const resp = await EntreprisesAPI.recalculateOpportunitiesBulk(ids);
                        const okCount = resp && typeof resp.ok === 'number' ? resp.ok : 0;
                        const failCount = resp && typeof resp.failed === 'number' ? resp.failed : 0;
                        await applyFilters();
                        if (failCount > 0) {
                            Notifications.show(
                                `Recalcul terminé: ${okCount} OK, ${failCount} en échec.`,
                                'warning'
                            );
                        } else {
                            Notifications.show(
                                `${okCount} opportunité${okCount > 1 ? 's' : ''} recalculée${okCount > 1 ? 's' : ''}`,
                                'success'
                            );
                        }
                    }
                } catch (e) {
                    console.error('Erreur action de masse:', e);
                    Notifications.show('Erreur lors de l\'action de masse', 'error');
                }
            });
        }

        // Sélection par clic sur la card / ligne
        setupClickToSelectCards();

        // Suggestions de tags + chips sélectionnés
        loadTagsSuggestions().then(() => {
            const suggestionsContainer = document.getElementById('filter-tags-suggestions');
            const tagsInput = document.getElementById('filter-tags');
            const chipsContainer = document.getElementById('filter-tags-chips');

            if (tagsInput) {
                tagsInput.addEventListener('input', () => {
                    const value = tagsInput.value || '';
                    if (!value.trim()) {
                        const container = document.getElementById('filter-tags-suggestions');
                        if (container) {
                            container.innerHTML = '';
                            container.classList.add('hidden');
                        }
                    } else {
                        renderTagSuggestions(value);
                    }
                });
                tagsInput.addEventListener('focus', () => {
                    const value = tagsInput.value || '';
                    if (value.trim()) {
                        renderTagSuggestions(value);
                    }
                });
                // On ne masque plus immédiatement sur blur pour laisser le clic fonctionner
            }

            if (suggestionsContainer) {
                suggestionsContainer.addEventListener('click', (e) => {
                    const btn = e.target.closest('.tag-suggestion');
                    if (!btn) return;
                    const tag = btn.getAttribute('data-tag') || '';
                    if (!tag) return;
                    addTagToFilter(tag);
                    if (tagsInput) {
                        tagsInput.focus();
                    }
                });
            }

            if (chipsContainer) {
                chipsContainer.addEventListener('click', (e) => {
                    const removeBtn = e.target.closest('.tags-filter-chip-remove');
                    if (!removeBtn) return;
                    const tag = removeBtn.getAttribute('data-remove-tag') || '';
                    if (!tag) return;
                    removeTagFromFilter(tag);
                    if (tagsInput) {
                        tagsInput.focus();
                    }
                });
            }
        }).catch((e) => {
            console.error('Erreur suggestions tags:', e);
        });
        
        // Ouverture / fermeture des filtres avancés
        const advancedFiltersEl = document.getElementById('advanced-filters');
        const toggleBtn = document.getElementById('btn-toggle-advanced-filters');
        if (advancedFiltersEl && toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                advancedFiltersEl.classList.toggle('collapsed');
                toggleBtn.classList.toggle('filters-toggle-open');
            });
        }

        // Accordéon intelligent pour réduire la hauteur
        function setupAdvancedFiltersSectionsAccordion() {
            const root = document.getElementById('advanced-filters');
            if (!root) return;
            if (root.dataset.accordionInit === '1') return;
            root.dataset.accordionInit = '1';

            const sections = Array.from(root.querySelectorAll('.filters-advanced-section'));

            sections.forEach((section, index) => {
                const header = section.querySelector('.filters-advanced-section-header');
                const body = section.querySelector('.filters-advanced-section-body');
                if (!header || !body) return;

                const initiallyCollapsed = true; // tout replié par défaut
                const rootCollapsed = root.classList.contains('collapsed');

                header.setAttribute('role', 'button');
                header.setAttribute('tabindex', '0');
                header.setAttribute('aria-expanded', String(!initiallyCollapsed));

                if (initiallyCollapsed) {
                    section.classList.add('collapsed');
                    body.style.maxHeight = '0px';
                } else {
                    section.classList.remove('collapsed');
                    // Si la zone globale est encore repliée, scrollHeight peut valoir 0.
                    // On laisse donc gérer la hauteur au moment du toggle.
                    body.style.maxHeight = rootCollapsed ? '' : body.scrollHeight + 'px';
                }

                const expand = () => {
                    section.classList.remove('collapsed');
                    header.setAttribute('aria-expanded', 'true');
                    body.style.maxHeight = body.scrollHeight + 'px';
                };

                const collapse = () => {
                    section.classList.add('collapsed');
                    header.setAttribute('aria-expanded', 'false');
                    body.style.maxHeight = body.scrollHeight + 'px';
                    body.offsetHeight; // forcer le recalcul
                    body.style.maxHeight = '0px';
                };

                const toggle = () => {
                    const shouldExpand = section.classList.contains('collapsed');
                    if (shouldExpand) {
                        // Fermer toutes les autres sections avant d'ouvrir celle-ci
                        sections.forEach((other) => {
                            if (other !== section) {
                                other.classList.add('collapsed');
                                const otherHeader = other.querySelector('.filters-advanced-section-header');
                                const otherBody = other.querySelector('.filters-advanced-section-body');
                                if (otherHeader) {
                                    otherHeader.setAttribute('aria-expanded', 'false');
                                }
                                if (otherBody) {
                                    otherBody.style.maxHeight = '0px';
                                }
                            }
                        });
                        expand();
                    } else {
                        // si on clique une section déjà ouverte: on la replie
                        collapse();
                    }
                };

                header.addEventListener('click', (e) => {
                    // Si jamais on clique sur un élément interactif dans le header, on ignore.
                    const interactive = e.target.closest('input, select, textarea, button, a, label');
                    if (interactive && interactive !== header) return;
                    toggle();
                });

                header.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggle();
                    }
                });
            });
        }

        setupAdvancedFiltersSectionsAccordion();
        
        document.getElementById('btn-view-grid').addEventListener('click', () => {
            currentView = 'grid';
            syncViewToggleButtons();
            persistEntreprisesViewMode();
            renderEntreprises();
        });
        
        document.getElementById('btn-view-list').addEventListener('click', () => {
            currentView = 'list';
            syncViewToggleButtons();
            persistEntreprisesViewMode();
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

        const secteur = document.getElementById('filter-secteur')?.value;
        const groupe = document.getElementById('filter-groupe')?.value;
        const opportunite = document.getElementById('filter-opportunite')?.value;
        const statut = document.getElementById('filter-statut')?.value;
        const etapeProspection = document.getElementById('filter-etape-prospection')?.value;
        const tagsInputValue = (document.getElementById('filter-tags')?.value || '').trim();
        const securityMin = document.getElementById('filter-security-min')?.value;
        const securityMax = document.getElementById('filter-security-max')?.value;
        const seoMin = document.getElementById('filter-seo-min')?.value;
        const seoMax = document.getElementById('filter-seo-max')?.value;
        const pentestMin = document.getElementById('filter-pentest-min')?.value;
        const pentestMax = document.getElementById('filter-pentest-max')?.value;
        const hasEmail = document.getElementById('filter-has-email')?.checked;

        const hasActiveTags = Array.isArray(activeTagFilters) && activeTagFilters.length > 0;
        const typedTags = tagsInputValue
            ? tagsInputValue.split(/[, ]+/).map((s) => s.trim()).filter(Boolean)
            : [];
        const tagCount = Array.from(new Set([...(hasActiveTags ? activeTagFilters : []), ...typedTags])).length;

        const segmentationCount =
            (secteur ? 1 : 0) +
            (groupe ? 1 : 0) +
            (opportunite ? 1 : 0) +
            (statut ? 1 : 0) +
            (etapeProspection ? 1 : 0) +
            (hasEmail ? 1 : 0);
        const commercialProfile = document.getElementById('filter-commercial-profile')?.value;
        const scoresCount =
            (commercialProfile ? 1 : 0) +
            ((securityMin && parseInt(securityMin, 10) > 0) ? 1 : 0) +
            ((securityMax && parseInt(securityMax, 10) < 100) ? 1 : 0) +
            ((seoMin && parseInt(seoMin, 10) > 0) ? 1 : 0) +
            ((seoMax && parseInt(seoMax, 10) < 100) ? 1 : 0) +
            ((pentestMin && parseInt(pentestMin, 10) > 0) ? 1 : 0) +
            ((pentestMax && parseInt(pentestMax, 10) < 100) ? 1 : 0) +
            (document.getElementById('filter-security-null')?.checked ? 1 : 0) +
            (document.getElementById('filter-seo-null')?.checked ? 1 : 0) +
            (document.getElementById('filter-pentest-null')?.checked ? 1 : 0);
        const techCount =
            ((document.getElementById('filter-cms')?.value ? 1 : 0)) +
            ((document.getElementById('filter-framework')?.value ? 1 : 0));
        const behaviorCount =
            tagCount +
            (document.getElementById('filter-has-blog')?.checked ? 1 : 0) +
            (document.getElementById('filter-has-form')?.checked ? 1 : 0) +
            (document.getElementById('filter-has-tunnel')?.checked ? 1 : 0);
        const count = segmentationCount + scoresCount + techCount + behaviorCount;

        const setSectionCount = (id, value) => {
            const el = document.getElementById(id);
            if (!el) return;
            if (value > 0) {
                el.textContent = String(value);
                el.style.display = 'inline-flex';
            } else {
                el.style.display = 'none';
            }
        };
        setSectionCount('section-filter-count-segmentation', segmentationCount);
        setSectionCount('section-filter-count-scores', scoresCount);
        setSectionCount('section-filter-count-tech', techCount);
        setSectionCount('section-filter-count-behavior', behaviorCount);

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
            loadAuditPipeline(entrepriseId);
            loadProspectionTab(entrepriseId);
            refreshOpportunityScore(entrepriseId);
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

    /**
     * Charge et affiche le pipeline d'audit (Scraping → Technique → SEO → OSINT → Pentest)
     * dans l'onglet dédié de la modale.
     * @param {number} entrepriseId
     */
    async function loadAuditPipeline(entrepriseId) {
        const container = document.getElementById('entreprise-pipeline-container');
        if (!container) return;
        try {
            container.innerHTML = '<p class="loading">Chargement du pipeline d\'audit...</p>';
            const data = await EntreprisesAPI.loadAuditPipeline(entrepriseId);
            const pipeline = data && data.pipeline ? data.pipeline : {};
            container.innerHTML = renderAuditPipeline(pipeline);
        } catch (e) {
            console.error('Erreur lors du chargement du pipeline d\'audit:', e);
            container.innerHTML = '<p class="error">Erreur lors du chargement du pipeline d\'audit.</p>';
        }
    }

    /**
     * Génère le HTML du pipeline d'audit à partir du résumé backend.
     * @param {Object} pipeline
     * @returns {string}
     */
    function renderAuditPipeline(pipeline) {
        if (!pipeline) {
            return '<p class="empty-state">Aucune donnée d\'audit disponible pour le moment.</p>';
        }

        const steps = [
            { key: 'scraping', label: 'Scraping', icon: 'fa-spider' },
            { key: 'technical', label: 'Analyse technique', icon: 'fa-microchip' },
            { key: 'seo', label: 'Analyse SEO', icon: 'fa-search' },
            { key: 'osint', label: 'Analyse OSINT', icon: 'fa-user-secret' },
            { key: 'pentest', label: 'Analyse Pentest', icon: 'fa-shield-alt' }
        ];

        const toDate = (value) => {
            if (!value) return null;
            try {
                const d = new Date(value);
                if (Number.isNaN(d.getTime())) return null;
                return d.toLocaleString();
            } catch {
                return null;
            }
        };

        const escape = (text) => Formatters && typeof Formatters.escapeHtml === 'function'
            ? Formatters.escapeHtml(text)
            : String(text || '');

        const rows = steps.map((step, idx) => {
            const item = pipeline[step.key] || { status: 'never' };
            const status = item.status || 'never';
            const dateStr = toDate(item.last_date);

            let statusLabel = 'Jamais lancée';
            let statusClass = 'secondary';
            if (status === 'done') {
                statusLabel = 'Terminé';
                statusClass = 'success';
            } else if (status === 'running') {
                statusLabel = 'En cours';
                statusClass = 'warning';
            }

            const metaParts = [];
            if (step.key === 'scraping' && status === 'done') {
                if (typeof item.emails_count === 'number') metaParts.push(`${item.emails_count} email(s)`);
                if (typeof item.people_count === 'number') metaParts.push(`${item.people_count} personne(s)`);
                if (typeof item.phones_count === 'number') metaParts.push(`${item.phones_count} téléphone(s)`);
            } else if (step.key === 'technical' && status === 'done') {
                if (typeof item.security_score === 'number') metaParts.push(`Sécurité: ${item.security_score}/100`);
                if (typeof item.performance_score === 'number') metaParts.push(`Perf: ${item.performance_score}/100`);
            } else if (step.key === 'seo' && status === 'done') {
                if (typeof item.score === 'number') metaParts.push(`Score SEO: ${item.score}/100`);
            } else if (step.key === 'osint' && status === 'done') {
                if (typeof item.emails_count === 'number') metaParts.push(`${item.emails_count} email(s) OSINT`);
                if (typeof item.people_count === 'number') metaParts.push(`${item.people_count} personne(s) enrichie(s)`);
            } else if (step.key === 'pentest' && status === 'done') {
                if (typeof item.risk_score === 'number') metaParts.push(`Risque: ${item.risk_score}/100`);
                if (typeof item.critical_count === 'number' && item.critical_count > 0) {
                    metaParts.push(`${item.critical_count} critique(s)`);
                } else if (typeof item.high_count === 'number' && item.high_count > 0) {
                    metaParts.push(`${item.high_count} haute(s)`);
                }
            }

            const metaHtml = metaParts.length
                ? `<div class="pipeline-meta">${metaParts.map(m => `<span>${escape(m)}</span>`).join('')}</div>`
                : '';

            return `
                <li class="pipeline-step">
                    <div class="pipeline-step-icon">
                        <span class="pipeline-step-index">${idx + 1}</span>
                        <i class="fas ${step.icon}"></i>
                    </div>
                    <div class="pipeline-step-body">
                        <div class="pipeline-step-header">
                            <h4>${escape(step.label)}</h4>
                            <span class="badge badge-${statusClass}">${escape(statusLabel)}</span>
                        </div>
                        ${dateStr ? `<div class="pipeline-date">Dernière exécution : ${escape(dateStr)}</div>` : ''}
                        ${metaHtml}
                    </div>
                </li>
            `;
        }).join('');

        return `
            <div class="pipeline-timeline">
                <ol class="pipeline-steps">
                    ${rows}
                </ol>
            </div>
        `;
    }

    /**
     * Rend la liste HTML des touchpoints (modale prospection).
     * @param {Array<Object>} items
     * @returns {string}
     */
    function renderTouchpointsListHtml(items) {
        if (!items || !items.length) {
            return '<p class="empty-state" style="margin:0;">Aucune interaction enregistrée.</p>';
        }
        const esc = (t) => (Formatters && Formatters.escapeHtml ? Formatters.escapeHtml(String(t ?? '')) : String(t ?? ''));
        return items.map((tp) => {
            const dateRaw = tp.happened_at || tp.created_at || '';
            const dateStr = dateRaw ? esc(dateRaw) : '';
            return `
                <div class="touchpoint-card">
                    <div class="touchpoint-card-main">
                        <div>
                            <strong>${esc(tp.canal)}</strong>
                            <span class="touchpoint-sujet"> — ${esc(tp.sujet)}</span>
                            ${dateStr ? `<div class="touchpoint-date">${dateStr}</div>` : ''}
                            ${tp.note ? `<div class="touchpoint-note">${esc(tp.note)}</div>` : ''}
                        </div>
                        <button type="button" class="btn btn-small btn-outline touchpoint-delete-btn" data-touchpoint-delete="${tp.id}" title="Supprimer"><i class="fas fa-trash"></i></button>
                    </div>
                </div>`;
        }).join('');
    }

    /**
     * Charge statut pipeline + touchpoints et branche les actions dans la modale.
     * @param {number} entrepriseId
     */
    async function loadProspectionTab(entrepriseId) {
        const container = document.getElementById('entreprise-prospection-container');
        if (!container || !window.EntreprisesAPI) return;
        container.innerHTML = '<p class="loading">Chargement de la prospection...</p>';
        try {
            const [statuts, crmEtapes, tpRes] = await Promise.all([
                EntreprisesAPI.loadStatutsPipeline(),
                EntreprisesAPI.loadCrmEtapes(),
                EntreprisesAPI.loadTouchpoints(entrepriseId, 100, 0)
            ]);
            const items = (tpRes && tpRes.items) ? tpRes.items : [];
            const currentStatut = (currentModalEntrepriseData && currentModalEntrepriseData.statut) ? String(currentModalEntrepriseData.statut) : '';
            const statutOptions = (statuts || []).map((s) => {
                const sel = s === currentStatut ? ' selected' : '';
                return `<option value="${Formatters.escapeHtml(s)}"${sel}>${Formatters.escapeHtml(s)}</option>`;
            }).join('');
            const rawEtape = (currentModalEntrepriseData && currentModalEntrepriseData.etape_prospection)
                ? String(currentModalEntrepriseData.etape_prospection).trim() : '';
            const currentEtape = rawEtape || 'À prospecter';
            const etapeList = Array.isArray(crmEtapes) && crmEtapes.length ? crmEtapes : ['À prospecter', 'Contacté', 'RDV', 'Proposition', 'Gagné', 'Perdu'];
            const etapeOptions = etapeList.map((s) => {
                const sel = s === currentEtape ? ' selected' : '';
                return `<option value="${Formatters.escapeHtml(s)}"${sel}>${Formatters.escapeHtml(s)}</option>`;
            }).join('');

            container.innerHTML = `
                <div class="prospection-panel">
                    <div class="prospection-statut-block">
                        <label for="modal-prospection-etape" class="prospection-label">Étape prospection (Kanban)</label>
                        <div class="prospection-statut-row">
                            <select id="modal-prospection-etape" class="form-select">${etapeOptions}</select>
                            <button type="button" class="btn btn-primary btn-small" id="modal-prospection-save-etape">Enregistrer</button>
                        </div>
                    </div>
                    <div class="prospection-statut-block">
                        <label for="modal-prospection-statut" class="prospection-label">Statut (campagnes / email)</label>
                        <div class="prospection-statut-row">
                            <select id="modal-prospection-statut" class="form-select">${statutOptions}</select>
                            <button type="button" class="btn btn-primary btn-small" id="modal-prospection-save-statut">Enregistrer</button>
                        </div>
                    </div>
                    <h4 class="prospection-journal-title"><i class="fas fa-comments"></i> Journal d'interactions</h4>
                    <div id="touchpoints-list" class="touchpoints-list">${renderTouchpointsListHtml(items)}</div>
                    <form id="touchpoint-form" class="touchpoint-form">
                        <div class="touchpoint-quick-actions" role="group" aria-label="Raccourcis canal">
                            <span class="touchpoint-quick-label">Ajouter un touchpoint :</span>
                            <button type="button" class="btn btn-small btn-outline touchpoint-preset" data-canal="Email">Email</button>
                            <button type="button" class="btn btn-small btn-outline touchpoint-preset" data-canal="Appel">Appel</button>
                            <button type="button" class="btn btn-small btn-outline touchpoint-preset" data-canal="RDV">RDV</button>
                            <button type="button" class="btn btn-small btn-outline touchpoint-preset" data-canal="Note">Note</button>
                        </div>
                        <div class="touchpoint-form-grid">
                            <div>
                                <label class="form-label">Canal</label>
                                <input type="text" name="canal" class="form-input" placeholder="Email, téléphone, LinkedIn…" required autocomplete="off">
                            </div>
                            <div>
                                <label class="form-label">Sujet</label>
                                <input type="text" name="sujet" class="form-input" placeholder="Objet court" required autocomplete="off">
                            </div>
                        </div>
                        <div class="touchpoint-form-note">
                            <label class="form-label">Note (optionnel)</label>
                            <textarea name="note" class="form-input" rows="2" placeholder="Détails"></textarea>
                        </div>
                        <div class="touchpoint-form-date">
                            <label class="form-label">Date de l'événement (optionnel)</label>
                            <input type="datetime-local" name="happened_at" class="form-input">
                        </div>
                        <button type="submit" class="btn btn-outline touchpoint-submit"><i class="fas fa-plus"></i> Ajouter l'interaction</button>
                    </form>
                </div>
            `;

            const saveEtapeBtn = document.getElementById('modal-prospection-save-etape');
            if (saveEtapeBtn) {
                saveEtapeBtn.onclick = async () => {
                    const sel = document.getElementById('modal-prospection-etape');
                    if (!sel || !currentModalEntrepriseId) return;
                    const etape = (sel.value || '').trim();
                    if (!etape) {
                        Notifications.show('Choisis une étape', 'warning');
                        return;
                    }
                    try {
                        await EntreprisesAPI.updateEtapeProspection(currentModalEntrepriseId, etape);
                        if (currentModalEntrepriseData) currentModalEntrepriseData.etape_prospection = etape;
                        const row = allEntreprises.find((e) => e.id === currentModalEntrepriseId);
                        if (row) row.etape_prospection = etape;
                        Notifications.show('Étape prospection mise à jour', 'success');
                        refreshKanbanStrip();
                        scheduleApplyFilters();
                    } catch (err) {
                        console.error(err);
                        Notifications.show(err.message || 'Erreur étape', 'error');
                    }
                };
            }

            const saveBtn = document.getElementById('modal-prospection-save-statut');
            if (saveBtn) {
                saveBtn.onclick = async () => {
                    const sel = document.getElementById('modal-prospection-statut');
                    if (!sel || !currentModalEntrepriseId) return;
                    const statut = (sel.value || '').trim();
                    if (!statut) {
                        Notifications.show('Choisis un statut', 'warning');
                        return;
                    }
                    try {
                        await EntreprisesAPI.updateStatutPipeline(currentModalEntrepriseId, statut);
                        if (currentModalEntrepriseData) currentModalEntrepriseData.statut = statut;
                        const badgeEl = document.getElementById('info-statut-value');
                        if (badgeEl && window.Badges) {
                            badgeEl.innerHTML = Badges.getStatusBadge(statut);
                        }
                        const row = allEntreprises.find((e) => e.id === currentModalEntrepriseId);
                        if (row) row.statut = statut;
                        Notifications.show('Statut mis à jour', 'success');
                        scheduleApplyFilters();
                    } catch (err) {
                        console.error(err);
                        Notifications.show(err.message || 'Erreur statut', 'error');
                    }
                };
            }

            container.querySelectorAll('.touchpoint-preset').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const canal = btn.getAttribute('data-canal') || '';
                    const tf = document.getElementById('touchpoint-form');
                    if (!tf) return;
                    const canalInput = tf.querySelector('[name="canal"]');
                    const sujetInput = tf.querySelector('[name="sujet"]');
                    if (canalInput) canalInput.value = canal;
                    if (sujetInput) sujetInput.focus();
                });
            });

            const form = document.getElementById('touchpoint-form');
            if (form) {
                form.onsubmit = async (ev) => {
                    ev.preventDefault();
                    if (!currentModalEntrepriseId) return;
                    const fd = new FormData(form);
                    const canal = (fd.get('canal') || '').trim();
                    const sujet = (fd.get('sujet') || '').trim();
                    const note = fd.get('note');
                    const ha = fd.get('happened_at');
                    const payload = { canal, sujet };
                    if (note !== null && String(note).trim() !== '') payload.note = String(note);
                    if (ha) {
                        try {
                            const d = new Date(String(ha));
                            if (!Number.isNaN(d.getTime())) payload.happened_at = d.toISOString();
                        } catch (_) { /* ignore */ }
                    }
                    try {
                        await EntreprisesAPI.createTouchpoint(currentModalEntrepriseId, payload);
                        form.reset();
                        Notifications.show('Interaction enregistrée', 'success');
                        const refreshed = await EntreprisesAPI.loadTouchpoints(currentModalEntrepriseId, 100, 0);
                        const list = document.getElementById('touchpoints-list');
                        if (list) {
                            const next = (refreshed && refreshed.items) ? refreshed.items : [];
                            list.innerHTML = renderTouchpointsListHtml(next);
                            list.querySelectorAll('.touchpoint-delete-btn').forEach((btn) => bindTouchpointDelete(btn));
                        }
                    } catch (err) {
                        console.error(err);
                        Notifications.show(err.message || 'Erreur à l\'enregistrement', 'error');
                    }
                };
            }

            function bindTouchpointDelete(btn) {
                btn.onclick = async () => {
                    const tid = btn.getAttribute('data-touchpoint-delete');
                    if (!tid || !currentModalEntrepriseId) return;
                    if (!confirm('Supprimer cette interaction ?')) return;
                    try {
                        await EntreprisesAPI.deleteTouchpoint(currentModalEntrepriseId, Number(tid));
                        Notifications.show('Interaction supprimée', 'success');
                        await loadProspectionTab(currentModalEntrepriseId);
                    } catch (err) {
                        console.error(err);
                        Notifications.show(err.message || 'Erreur suppression', 'error');
                    }
                };
            }
            container.querySelectorAll('.touchpoint-delete-btn').forEach((btn) => bindTouchpointDelete(btn));
        } catch (e) {
            console.error('Prospection:', e);
            container.innerHTML = '<p class="error">Impossible de charger la prospection.</p>';
        }
    }

    /**
     * Recalcule le score d'opportunité pour une entreprise et met à jour la modale.
     * Utilise l'endpoint /api/entreprise/<id>/recalculate-opportunity.
     */
    async function refreshOpportunityScore(entrepriseId) {
        if (!entrepriseId || !window.EntreprisesAPI || !window.Badges) return;
        const row = document.getElementById('opportunity-row');
        const valueEl = document.getElementById('opportunity-value');
        if (!row || !valueEl) return;

        try {
            valueEl.innerHTML = '<span class="badge badge-secondary"><i class="fas fa-spinner fa-spin"></i> Calcul en cours…</span>';
            const result = await EntreprisesAPI.recalculateOpportunity(entrepriseId);
            if (!result || result.success === false) {
                const message = (result && result.error) ? result.error : 'Impossible de calculer l\'opportunité';
                valueEl.innerHTML = `<span class="badge badge-secondary">${Formatters.escapeHtml(message)}</span>`;
                return;
            }

            const niveau = result.opportunity || (currentModalEntrepriseData && currentModalEntrepriseData.opportunite) || 'Non calculée';
            const score = (typeof result.score === 'number') ? result.score : null;
            valueEl.innerHTML = Badges.getOpportunityBadge(niveau, score, null);

            // Mettre à jour les données courantes en mémoire
            if (currentModalEntrepriseData) {
                currentModalEntrepriseData.opportunite = niveau;
                currentModalEntrepriseData.opportunity_score = score;
            }
        } catch (e) {
            console.error('Erreur lors du recalcul de l\'opportunité:', e);
            valueEl.innerHTML = '<span class="badge badge-secondary">Erreur lors du calcul</span>';
        }
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
                        <button class="tab-btn" data-tab="prospection">Prospection</button>
                        <button class="tab-btn" data-tab="images">Images (${nbImages})</button>
                        <button class="tab-btn" data-tab="pages">Pages (${nbPages})</button>
                        <button class="tab-btn" data-tab="scraping">Résultats scraping</button>
                        <button class="tab-btn" data-tab="pipeline">Pipeline d'audit</button>
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
                            <div class="info-row" id="info-statut-row">
                                <span class="info-label">Statut:</span>
                                <span class="info-value" id="info-statut-value">${Badges.getStatusBadge(entreprise.statut)}</span>
                            </div>
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
                            <div class="info-row" id="opportunity-row">
                                <span class="info-label">Opportunité:</span>
                                <span class="info-value" id="opportunity-value">
                                    ${entreprise.opportunite ? Badges.getOpportunityBadge(entreprise.opportunite, null) : 'Non calculée'}
                                </span>
                            </div>
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
                    
                    <div class="tab-panel" id="tab-prospection" style="display:none;">
                        <div id="entreprise-prospection-container" class="prospection-tab-content">
                            <p class="empty-state">Chargement de la prospection...</p>
                        </div>
                    </div>
                    
                    <div class="tab-panel" id="tab-scraping">
                        <div id="scraping-results" class="scraping-results" style="display: block;">
                            <div class="scraping-results-header">
                                <div class="scraping-results-title-row" style="display:flex;align-items:center;justify-content:space-between;gap:0.75rem;flex-wrap:wrap;">
                                    <h3 class="scraping-results-title">
                                        <i class="fas fa-spider"></i>
                                        Résultats du scraping
                                    </h3>
                                    <button type="button" class="btn btn-outline btn-relancer-scraping" data-entreprise-id="${entreprise.id}" title="Relancer le scraping"><i class="fas fa-sync-alt"></i> Relancer</button>
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
                            <div id="scraping-issues-content" class="scraping-issues-section"></div>
                        </div>
                    </div>
                    
                    <div class="tab-panel" id="tab-pipeline">
                        <div id="entreprise-pipeline-container" class="pipeline-tab-content">
                            <p class="empty-state">Chargement du pipeline d'audit...</p>
                        </div>
                    </div>
                    
                    <div class="tab-panel" id="tab-technique">
                        <div class="analysis-tab-toolbar" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:0.5rem;">
                            <span class="analysis-tab-label" style="font-weight:600;color:#334155;">Analyse technique</span>
                            <button type="button" class="btn btn-outline btn-relancer-analysis" data-analysis-type="technique" title="Relancer l\'analyse technique"><i class="fas fa-sync-alt"></i> Relancer</button>
                        </div>
                        <div id="technique-results" class="analysis-results">
                            <div id="technique-results-content">Chargement de l'analyse technique...</div>
                        </div>
                    </div>

                    <div class="tab-panel" id="tab-seo">
                        <div class="analysis-tab-toolbar" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:0.5rem;">
                            <span class="analysis-tab-label" style="font-weight:600;color:#334155;">Analyse SEO</span>
                            <button type="button" class="btn btn-outline btn-relancer-analysis" data-analysis-type="seo" title="Relancer l\'analyse SEO"><i class="fas fa-sync-alt"></i> Relancer</button>
                        </div>
                        <div id="seo-results" class="analysis-results">
                            <div id="seo-results-content">Chargement de l'analyse SEO...</div>
                        </div>
                    </div>
                    
                    <div class="tab-panel" id="tab-osint">
                        <div class="analysis-tab-toolbar" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:0.5rem;">
                            <span class="analysis-tab-label" style="font-weight:600;color:#334155;">Analyse OSINT</span>
                            <button type="button" class="btn btn-outline btn-relancer-analysis" data-analysis-type="osint" title="Relancer l\'analyse OSINT"><i class="fas fa-sync-alt"></i> Relancer</button>
                        </div>
                        <div id="osint-results" class="analysis-results">
                            <div id="osint-results-content">Chargement de l'analyse OSINT...</div>
                        </div>
                    </div>
                    
                    <div class="tab-panel" id="tab-pentest">
                        <div class="analysis-tab-toolbar" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:0.5rem;">
                            <span class="analysis-tab-label" style="font-weight:600;color:#334155;">Analyse Pentest</span>
                            <button type="button" class="btn btn-outline btn-relancer-analysis" data-analysis-type="pentest" title="Relancer l\'analyse Pentest"><i class="fas fa-sync-alt"></i> Relancer</button>
                        </div>
                        <div id="pentest-results" class="analysis-results">
                            <div id="pentest-results-content">Chargement de l'analyse Pentest...</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="modal-footer">
                <button class="btn btn-secondary" id="modal-close-footer-btn">Fermer</button>
                <button class="btn btn-danger" id="modal-delete-entreprise" data-id="${entreprise.id}">
                    <i class="fas fa-trash"></i> Supprimer
                </button>
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
    
    function ensureModalWebSocketListeners() {
        if (window._entrepriseModalWsListenersSetup || !window.wsManager || !window.wsManager.socket) return;
        const s = window.wsManager.socket;
        s.on('technical_analysis_complete', function(data) {
            if (!data || data.entreprise_id == null) return;
            setScoreRelaunchLoading(data.entreprise_id, 'technique', false);
            refreshEntrepriseFromServer(data.entreprise_id, { animateOnlyMetric: 'technique' });
            if (isEntrepriseCurrentlyRendered(data.entreprise_id)) {
                scheduleApplyFilters();
            }
            const nom = getEntrepriseNom(data.entreprise_id);
            Notifications.show(nom + ' — Analyse technique terminée', 'success', 'fa-check-circle');
            if (data.entreprise_id === currentModalEntrepriseId) {
                setTimeout(() => loadTechnicalAnalysis(currentModalEntrepriseId, { skipClear: true }), 400);
            }
        });
        s.on('technical_analysis_error', function(data) {
            if (data && data.entreprise_id != null) {
                setScoreRelaunchLoading(data.entreprise_id, 'technique', false);
                const nom = getEntrepriseNom(data.entreprise_id);
                Notifications.show(nom + ' — ' + (data.error || 'Erreur analyse technique'), 'error', 'fa-exclamation-circle');
            }
            if (data && data.entreprise_id != null && data.entreprise_id === currentModalEntrepriseId) {
                loadTechnicalAnalysis(currentModalEntrepriseId);
            }
        });
        s.on('seo_analysis_complete', function(data) {
            if (!data || data.entreprise_id == null) return;
            setScoreRelaunchLoading(data.entreprise_id, 'seo', false);
            refreshEntrepriseFromServer(data.entreprise_id, { animateOnlyMetric: 'seo' });
            if (isEntrepriseCurrentlyRendered(data.entreprise_id)) {
                scheduleApplyFilters();
            }
            const nom = getEntrepriseNom(data.entreprise_id);
            Notifications.show(nom + ' — Analyse SEO terminée', 'success', 'fa-check-circle');
            if (data.entreprise_id === currentModalEntrepriseId) {
                setTimeout(() => loadSEOAnalysis(currentModalEntrepriseId, { skipClear: true }), 400);
            }
        });
        s.on('seo_analysis_error', function(data) {
            if (data && data.entreprise_id != null) {
                setScoreRelaunchLoading(data.entreprise_id, 'seo', false);
                const nom = getEntrepriseNom(data.entreprise_id);
                Notifications.show(nom + ' — ' + (data.error || 'Erreur analyse SEO'), 'error', 'fa-exclamation-circle');
            }
            if (data && data.entreprise_id != null && data.entreprise_id === currentModalEntrepriseId) {
                loadSEOAnalysis(currentModalEntrepriseId);
            }
        });
        s.on('osint_analysis_complete', function(data) {
            if (data && data.entreprise_id != null) {
                const nom = getEntrepriseNom(data.entreprise_id);
                Notifications.show(nom + ' — Analyse OSINT terminée', 'success', 'fa-check-circle');
                if (isEntrepriseCurrentlyRendered(data.entreprise_id)) {
                    scheduleApplyFilters();
                }
            }
            if (data && data.entreprise_id === currentModalEntrepriseId) {
                loadOSINTAnalysis(currentModalEntrepriseId);
            }
        });
        s.on('osint_analysis_error', function(data) {
            if (data && data.entreprise_id != null) {
                const nom = getEntrepriseNom(data.entreprise_id);
                Notifications.show(nom + ' — ' + (data.error || 'Erreur analyse OSINT'), 'error', 'fa-exclamation-circle');
            }
            if (data && data.entreprise_id === currentModalEntrepriseId) {
                loadOSINTAnalysis(currentModalEntrepriseId);
            }
        });
        s.on('pentest_analysis_complete', function(data) {
            if (!data || data.entreprise_id == null) return;
            setScoreRelaunchLoading(data.entreprise_id, 'pentest', false);
            refreshEntrepriseFromServer(data.entreprise_id);
            if (isEntrepriseCurrentlyRendered(data.entreprise_id)) {
                scheduleApplyFilters();
            }
            const nom = getEntrepriseNom(data.entreprise_id);
            Notifications.show(nom + ' — Analyse Pentest terminée', 'success', 'fa-check-circle');
            if (data.entreprise_id === currentModalEntrepriseId) {
                setTimeout(() => loadPentestAnalysis(currentModalEntrepriseId, { skipClear: true }), 400);
            }
        });
        s.on('pentest_analysis_error', function(data) {
            if (data && data.entreprise_id != null) {
                setScoreRelaunchLoading(data.entreprise_id, 'pentest', false);
                const nom = getEntrepriseNom(data.entreprise_id);
                Notifications.show(nom + ' — ' + (data.error || 'Erreur analyse Pentest'), 'error', 'fa-exclamation-circle');
            }
            if (data && data.entreprise_id === currentModalEntrepriseId) {
                loadPentestAnalysis(currentModalEntrepriseId);
            }
        });

        s.on('scraping_started', function(data) {
            const entrepriseId = data && data.entreprise_id != null ? data.entreprise_id : currentModalEntrepriseId;
            if (entrepriseId == null) return;
            setScrapingRelaunchLoading(entrepriseId, true, 'Scraping démarré...');
        });

        s.on('scraping_progress', function(data) {
            const entrepriseId = data && data.entreprise_id != null ? data.entreprise_id : currentModalEntrepriseId;
            if (entrepriseId == null) return;
            setScrapingRelaunchLoading(entrepriseId, true, (data && data.message) ? data.message : 'Scraping en cours...');
        });

        s.on('scraping_complete', function(data) {
            const entrepriseId = data && data.entreprise_id != null ? data.entreprise_id : currentModalEntrepriseId;
            if (entrepriseId == null) return;
            setScrapingRelaunchLoading(entrepriseId, false);
            if (isEntrepriseCurrentlyRendered(entrepriseId)) {
                scheduleApplyFilters();
            }
            const nom = getEntrepriseNom(entrepriseId);
            Notifications.show(nom + ' — Scraping terminé', 'success', 'fa-check-circle');
            if (entrepriseId === currentModalEntrepriseId) {
                refreshEntrepriseFromServer(entrepriseId).then(() => {
                    try { loadScrapingResults(entrepriseId); } catch (e) {}
                    try { loadEntrepriseImages(entrepriseId); } catch (e) {}
                    try { if (currentModalEntrepriseData) loadEntreprisePages(currentModalEntrepriseData); } catch (e) {}
                });
            }
        });

        s.on('scraping_error', function(data) {
            const entrepriseId = data && data.entreprise_id != null ? data.entreprise_id : currentModalEntrepriseId;
            if (entrepriseId == null) return;
            setScrapingRelaunchLoading(entrepriseId, false);
            const nom = getEntrepriseNom(entrepriseId);
            Notifications.show(nom + ' — ' + (data && data.error ? data.error : 'Erreur scraping'), 'error', 'fa-exclamation-circle');
        });
        window._entrepriseModalWsListenersSetup = true;
    }
    
    function setupModalInteractions() {
        const closeBtn = document.getElementById('modal-close-btn');
        const closeFooterBtn = document.getElementById('modal-close-footer-btn');
        const modal = document.getElementById('entreprise-modal');
        const modalBody = document.getElementById('modal-entreprise-body');
        
        if (!window._entrepriseModalWsListenersSetup && window.wsManager && window.wsManager.socket) {
            ensureModalWebSocketListeners();
        }

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

        const deleteModalBtn = document.getElementById('modal-delete-entreprise');
        if (deleteModalBtn) {
            deleteModalBtn.addEventListener('click', async () => {
                if (!currentModalEntrepriseId) return;
                const name = currentModalEntrepriseData && currentModalEntrepriseData.nom
                    ? currentModalEntrepriseData.nom
                    : 'Cette entreprise';
                if (!confirm(`Êtes-vous sûr de vouloir supprimer "${name}" ?`)) {
                    return;
                }
                try {
                    await EntreprisesAPI.delete(currentModalEntrepriseId);
                    closeEntrepriseModal();
                    await applyFilters();
                    Notifications.show('Entreprise supprimée', 'success');
                } catch (error) {
                    console.error('Erreur:', error);
                    Notifications.show('Erreur lors de la suppression de l\'entreprise', 'error');
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
                
                const relancerBtn = e.target.closest('.btn-relancer-analysis');
                if (relancerBtn && currentModalEntrepriseId && currentModalEntrepriseData) {
                    const analysisType = relancerBtn.getAttribute('data-analysis-type');
                    const url = (currentModalEntrepriseData.website || '').trim();
                    if (!url) {
                        Notifications.show('Indiquez un site web pour cette entreprise pour relancer l\'analyse.', 'warning', 'fa-exclamation-triangle');
                        e.preventDefault();
                        return;
                    }
                    const socket = window.wsManager && window.wsManager.socket;
                    if (!socket) {
                        Notifications.show('Connexion temps réel non disponible. Rechargez la page.', 'warning', 'fa-wifi');
                        e.preventDefault();
                        return;
                    }
                    ensureModalWebSocketListeners();
                    const contentIds = { technique: 'technique-results-content', seo: 'seo-results-content', osint: 'osint-results-content', pentest: 'pentest-results-content' };
                    const contentEl = document.getElementById(contentIds[analysisType]);
                    if (contentEl) contentEl.innerHTML = '<p class="loading" style="padding:1.5rem;text-align:center;color:#64748b;"><i class="fas fa-spinner fa-spin"></i> Analyse en cours...</p>';
                    const launchLabels = { technique: 'technique', seo: 'SEO', osint: 'OSINT', pentest: 'Pentest' };
                    Notifications.show('Analyse ' + (launchLabels[analysisType] || analysisType) + ' lancée...', 'info', 'fa-play-circle');
                    if (analysisType === 'technique') {
                        socket.emit('start_technical_analysis', { url: url, entreprise_id: currentModalEntrepriseId });
                    } else if (analysisType === 'seo') {
                        socket.emit('start_seo_analysis', { url: url, entreprise_id: currentModalEntrepriseId, use_lighthouse: true });
                    } else if (analysisType === 'osint') {
                        socket.emit('start_osint_analysis', { url: url, entreprise_id: currentModalEntrepriseId });
                    } else if (analysisType === 'pentest') {
                        socket.emit('start_pentest_analysis', { url: url, entreprise_id: currentModalEntrepriseId });
                    }
                    e.preventDefault();
                    return;
                }

                const relancerScrapingBtn = e.target.closest('.btn-relancer-scraping');
                if (relancerScrapingBtn && currentModalEntrepriseId && currentModalEntrepriseData) {
                    const url = (currentModalEntrepriseData.website || '').trim();
                    if (!url) {
                        Notifications.show('Indiquez un site web pour cette entreprise pour relancer le scraping.', 'warning', 'fa-exclamation-triangle');
                        e.preventDefault();
                        return;
                    }
                    const socket = window.wsManager && window.wsManager.socket;
                    if (!socket) {
                        Notifications.show('Connexion temps réel non disponible. Rechargez la page.', 'warning', 'fa-wifi');
                        e.preventDefault();
                        return;
                    }
                    ensureModalWebSocketListeners();
                    setScrapingRelaunchLoading(currentModalEntrepriseId, true, 'Initialisation...');
                    Notifications.show('Scraping relancé...', 'info', 'fa-spider');
                    socket.emit('start_scraping', {
                        url: url,
                        max_depth: 3,
                        max_workers: 5,
                        max_time: 300,
                        max_pages: 50,
                        entreprise_id: currentModalEntrepriseId
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
    async function loadTechnicalAnalysis(entrepriseId, opts) {
        const resultsContent = document.getElementById('technique-results-content');
        if (!resultsContent) return;
        const skipClear = opts && opts.skipClear === true;
        
        try {
            if (!skipClear) resultsContent.innerHTML = 'Chargement...';
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
    async function loadSEOAnalysis(entrepriseId, opts) {
        const resultsContent = document.getElementById('seo-results-content');
        if (!resultsContent) return;
        const skipClear = opts && opts.skipClear === true;
        
        try {
            if (!skipClear) resultsContent.innerHTML = 'Chargement...';
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
                
                ${(() => {
                    if (issues.length === 0) return '';
                    const normalizeSeverity = (imp) => {
                        const i = (imp || 'info').toLowerCase();
                        if (i === 'critical' || i === 'critique') return 'critical';
                        if (i === 'high' || i === 'haute') return 'high';
                        if (i === 'medium' || i === 'moyen') return 'medium';
                        if (i === 'low' || i === 'faible') return 'low';
                        return 'info';
                    };
                    const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
                    issues.forEach(issue => { const s = normalizeSeverity(issue.impact || issue.type); counts[s]++; });
                    const getSeverityClass = normalizeSeverity;
                    const borderColors = { critical: '#e74c3c', high: '#e67e22', medium: '#f39c12', low: '#3498db', info: '#6b7280' };
                    return `
                <div class="seo-section seo-issues-section">
                    <h3><i class="fas fa-exclamation-triangle"></i> Problèmes SEO clés <span class="badge badge-danger">${issues.length}</span></h3>
                    <div class="seo-summary-chips">
                        ${counts.critical ? `<span class="seo-chip seo-chip-critical">${counts.critical} critique${counts.critical > 1 ? 's' : ''}</span>` : ''}
                        ${counts.high ? `<span class="seo-chip seo-chip-high">${counts.high} haute${counts.high > 1 ? 's' : ''}</span>` : ''}
                        ${counts.medium ? `<span class="seo-chip seo-chip-medium">${counts.medium} moyenne${counts.medium > 1 ? 's' : ''}</span>` : ''}
                        ${counts.low ? `<span class="seo-chip seo-chip-low">${counts.low} faible${counts.low > 1 ? 's' : ''}</span>` : ''}
                        ${counts.info ? `<span class="seo-chip seo-chip-info">${counts.info} info</span>` : ''}
                    </div>
                    <div class="seo-issues-list">
                        ${issues.map(issue => {
                            const sev = getSeverityClass(issue.impact || issue.type);
                            const color = borderColors[sev] || '#6b7280';
                            const category = Formatters.escapeHtml(issue.category || 'Général');
                            const message = Formatters.escapeHtml(issue.message || '');
                            const recommendation = issue.recommendation ? Formatters.escapeHtml(issue.recommendation) : '';
                            return `<div class="seo-issue-card" style="border-left: 4px solid ${color};">
                                <div class="seo-issue-header">
                                    <strong class="seo-issue-title">${category}</strong>
                                    <span class="seo-chip seo-chip-${sev}">${Formatters.escapeHtml(issue.impact || issue.type || 'info')}</span>
                                </div>
                                <div class="seo-issue-desc">${message}</div>
                                ${recommendation ? `<div class="seo-issue-reco"><strong><i class="fas fa-lightbulb"></i> Recommandation:</strong> ${recommendation}</div>` : ''}
                            </div>`;
                        }).join('')}
                    </div>
                </div>
                    `;
                })()}
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
    
    async function loadPentestAnalysis(entrepriseId, opts) {
        const resultsContent = document.getElementById('pentest-results-content');
        if (!resultsContent) return;
        const skipClear = opts && opts.skipClear === true;
        
        try {
            if (!skipClear) resultsContent.innerHTML = 'Chargement...';
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
            'metadata-list-modal': '<div class="empty-state">Aucune métadonnée extraite</div>',
            'scraping-issues-content': ''
        };
        
        Object.entries(containers).forEach(([id, html]) => {
            const el = document.getElementById(id);
            if (el) { el.innerHTML = html; if (id === 'scraping-issues-content') el.style.display = 'none'; }
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
    (async () => {
        try {
            syncViewToggleButtons();
        } catch (e) {
            // ignore
        }
        try {
            await loadSecteurs();
        } catch (e) {
            console.error('[entreprises] Erreur init secteurs:', e);
        }
        try {
            await loadOpportunites();
        } catch (e) {
            console.error('[entreprises] Erreur init opportunites:', e);
        }
        try {
            await loadGroupFilter();
        } catch (e) {
            console.error('[entreprises] Erreur init groupes filtre:', e);
        }
        try {
            await populateCommercialProfileSelect();
        } catch (e) {
            console.warn('[entreprises] init profils priorité:', e);
        }
        // Restaurer la recherche + filtres avancés depuis le memento (si disponible),
        // avant d'appliquer les filtres éventuellement présents dans l'URL.
        try {
            restoreFiltersFromMemento();
        } catch (e) {
            // ignore
        }
        try {
            updateCommercialProfileWeightsVisual();
        } catch (e) {
            /* ignore */
        }
        // Lire les filtres depuis l'URL (secteur, statut, tags_any, analyse_id...)
        applyInitialFiltersFromUrl();
        try {
            updateCommercialProfileWeightsVisual();
        } catch (e) {
            /* ignore */
        }
        try {
            await loadEntreprises();
        } catch (e) {
            console.error('[entreprises] Erreur init loadEntreprises (async):', e);
            const container = document.getElementById('entreprises-container');
            if (container) container.innerHTML = '<p class="error">Erreur lors du chargement des entreprises</p>';
        }
        try {
            setupEventListeners();
        } catch (e) {
            console.error('[entreprises] Erreur init event listeners:', e);
        }
        try {
            setupPaginationKeyboard();
        } catch (e) {
            console.error('[entreprises] Erreur init pagination keyboard:', e);
        }
    })();
}

// Initialisation lorsque le DOM est prêt (script chargé en defer)
let initDone = false;
function runInit() {
    if (initDone) return;
    initDone = true;
    init();
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runInit);
} else {
    runInit();
}
// Filet de sécurité : si après 500 ms init n'a pas tourné (event manqué), lancer quand même
setTimeout(function () {
    if (!initDone) {
        initDone = true;
        init();
    }
}, 500);
