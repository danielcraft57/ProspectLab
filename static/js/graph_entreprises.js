/**
 * Graphe vis-network : entreprises ↔ domaines externes (API /api/entreprises/graph).
 * Filtres, carte détail flottante, export PNG, physique, autocomplétion périmètre, recherche sur le graphe.
 */
(function () {
    'use strict';

    const graphEl = document.getElementById('graph-entreprises-canvas');
    const wrapEl = document.getElementById('graph-entreprises-wrap');
    const canvasStackEl = document.getElementById('graph-entreprises-canvas-stack');
    const btnFullscreen = document.getElementById('graph-entreprises-fullscreen');
    const fsChrome = document.getElementById('agences-fs-chrome');
    const fsFiltersToggle = document.getElementById('agences-fs-filters-toggle');
    const fsFiltersDropdown = document.getElementById('agences-fs-filters-dropdown');
    const fsFiltersMount = document.getElementById('agences-fs-filters-mount');
    const fsTabHost = fsChrome && fsChrome.querySelector ? fsChrome.querySelector('.agences-fs-tab-host') : null;
    const emptyEl = document.getElementById('graph-entreprises-empty');
    const errEl = document.getElementById('graph-entreprises-error');
    const statsWrap = document.getElementById('graph-entreprises-stats-wrap');
    const loadingEl = document.getElementById('graph-entreprises-loading');
    const legacyLivePanelEl = document.getElementById('graph-entreprises-live-panel');
    const btnReload = document.getElementById('graph-entreprises-reload');
    const btnFit = document.getElementById('graph-entreprises-fit');
    const btnZoomIn = document.getElementById('graph-entreprises-zoom-in');
    const btnZoomOut = document.getElementById('graph-entreprises-zoom-out');
    const btnPhysics = document.getElementById('graph-entreprises-physics');
    const btnExport = document.getElementById('graph-entreprises-export');
    const nodeCard = document.getElementById('agences-node-card');
    const nodeCardClose = document.getElementById('agences-node-card-close');
    const nodeCardEyebrow = document.getElementById('agences-node-card-eyebrow');
    const nodeCardBody = document.getElementById('agences-node-card-body');
    const btnViewBack = document.getElementById('graph-entreprises-view-back');
    const btnViewFwd = document.getElementById('graph-entreprises-view-fwd');

    if (!graphEl) return;
    if (legacyLivePanelEl && legacyLivePanelEl.parentNode) {
        legacyLivePanelEl.parentNode.removeChild(legacyLivePanelEl);
    }

    const emptyElDefaultText =
        emptyEl && emptyEl.textContent ? emptyEl.textContent.trim() : '';

    /**
     * Corrige un cas courant de texte UTF-8 décodé comme Latin-1 (mojibake "Ã©", "Ã¨", etc.).
     * Exemple: "ResponsabilitÃ©" -> "Responsabilité"
     * On ne touche que les chaînes qui semblent concernées (heuristique).
     */
    function fixMojibake(s) {
        if (s == null) return s;
        if (typeof s !== 'string') return s;
        if (!/[ÃÂ]/.test(s)) return s;
        if (!/(Ã.|Â.|â€™|â€œ|â€\x9d|â€¦)/.test(s)) return s;
        try {
            if (typeof TextDecoder !== 'undefined') {
                var bytes = new Uint8Array(
                    s.split('').map(function (c) {
                        return c.charCodeAt(0) & 0xff;
                    })
                );
                return new TextDecoder('utf-8').decode(bytes);
            }
        } catch (e0) {}
        try {
            // Fallback historique (marche dans la majorité des navigateurs)
            // eslint-disable-next-line no-undef
            return decodeURIComponent(escape(s));
        } catch (e1) {
            return s;
        }
    }

    function fixMojibakeInObj(o) {
        if (!o || typeof o !== 'object') return o;
        var keys = [
            'label',
            'title',
            'domain',
            'domain_host',
            'site_title',
            'site_description',
            'resolved_url',
            'external_href',
            'sample_anchor_text',
        ];
        keys.forEach(function (k) {
            if (typeof o[k] === 'string') o[k] = fixMojibake(o[k]);
        });
        return o;
    }

    const scopeHintEl = document.getElementById('graph-entreprises-scope-hint');
    const scopeSearchEl = document.getElementById('agences-scope-search');
    const scopeDomainEl = document.getElementById('agences-scope-domain');
    const scopeMaxRowsEl = document.getElementById('agences-scope-max-rows');
    const scopeMaxEntsEl = document.getElementById('agences-scope-max-ents');
    const scopeIdsEl = document.getElementById('agences-scope-ids');
    const scopeOnlyCreditEl = document.getElementById('agences-scope-only-credit');
    const scopePickQEl = document.getElementById('agences-scope-pick-q');
    const scopeAutocompleteEl = document.getElementById('agences-scope-autocomplete');
    const scopeApplyBtn = document.getElementById('agences-scope-apply');

    // Garde-fous au tout premier chargement de page (évite le "mur de liens" sur gros volumes).
    const BOOTSTRAP_MAX_LINK_ROWS = 1200;
    const BOOTSTRAP_MAX_ENTERPRISES = 160;

    let scopeAutocompleteTimer = null;
    let scopeAutocompleteActiveIdx = -1;
    let graphResizeObserver = null;
    let graphResizeHandler = null;

    let graphFsPseudo = false;
    let graphFsFiltersDock = { parent: null, next: null };
    let graphFsDropdownOpen = false;
    var fsDropCloseTimer = null;

    var FILTERS_COLLAPSED_KEY = 'prospectlab_graph_filters_collapsed';
    var filtersPanelEl = document.getElementById('agences-filters-panel');
    var filtersCollapseToggleEl = document.getElementById('agences-filters-collapse-toggle');

    function readFiltersCollapsedPref() {
        var v = localStorage.getItem(FILTERS_COLLAPSED_KEY);
        if (v === null) return true;
        return v === 'true';
    }

    function applyFiltersCollapsed(collapsed) {
        if (!filtersPanelEl || !filtersCollapseToggleEl) return;
        filtersPanelEl.classList.toggle('agences-filters--collapsed', collapsed);
        filtersCollapseToggleEl.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }

    function syncFiltersCollapsedFromStorage() {
        applyFiltersCollapsed(readFiltersCollapsedPref());
    }

    function bindFiltersAccordion() {
        var root = document.getElementById('agences-filters-panel');
        if (!root) return;
        var acc = root.querySelectorAll('details.agences-accordion');
        if (!acc.length) return;
        acc.forEach(function (d) {
            d.addEventListener('toggle', function () {
                if (!d.open) return;
                acc.forEach(function (other) {
                    if (other !== d) other.removeAttribute('open');
                });
            });
        });
    }

    function graphFsActive() {
        if (!wrapEl) return false;
        if (graphFsPseudo) return wrapEl.classList.contains('graph-entreprises-wrap--fs');
        var el =
            document.fullscreenElement ||
            document.webkitFullscreenElement ||
            document.msFullscreenElement;
        return el === wrapEl;
    }

    function graphRequestFullscreen(el) {
        if (!el) return Promise.reject();
        if (el.requestFullscreen) return el.requestFullscreen();
        if (el.webkitRequestFullscreen) return el.webkitRequestFullscreen();
        if (el.msRequestFullscreen) return el.msRequestFullscreen();
        return Promise.reject();
    }

    function graphExitFullscreen() {
        if (document.exitFullscreen) return document.exitFullscreen();
        if (document.webkitExitFullscreen) return document.webkitExitFullscreen();
        if (document.msExitFullscreen) return document.msExitFullscreen();
        return Promise.reject();
    }

    function graphFsSupportsNative() {
        return !!(wrapEl && (wrapEl.requestFullscreen || wrapEl.webkitRequestFullscreen || wrapEl.msRequestFullscreen));
    }

    function graphFsUpdateBtnIcon() {
        if (!btnFullscreen) return;
        var ic = btnFullscreen.querySelector('.material-symbols-rounded');
        if (!ic) return;
        ic.textContent = graphFsActive() ? 'fullscreen_exit' : 'fullscreen';
        btnFullscreen.setAttribute(
            'title',
            graphFsActive() ? 'Quitter le plein écran' : 'Plein écran'
        );
        btnFullscreen.setAttribute(
            'aria-label',
            graphFsActive() ? 'Quitter le plein écran' : 'Afficher le graphe en plein écran'
        );
    }

    /** @param {boolean} [immediate] true = fermeture instantanée (sortie plein écran, etc.) */
    function graphFsCloseDropdown(immediate) {
        if (!fsFiltersDropdown || !fsFiltersToggle) return;
        graphFsDropdownOpen = false;
        fsFiltersToggle.setAttribute('aria-expanded', 'false');
        fsFiltersDropdown.classList.remove('agences-fs-dropdown--open');
        fsFiltersDropdown.setAttribute('aria-hidden', 'true');
        if (fsDropCloseTimer) {
            clearTimeout(fsDropCloseTimer);
            fsDropCloseTimer = null;
        }
        if (immediate) {
            fsFiltersDropdown.setAttribute('hidden', '');
            return;
        }
        fsDropCloseTimer = window.setTimeout(function () {
            fsDropCloseTimer = null;
            fsFiltersDropdown.setAttribute('hidden', '');
        }, 400);
    }

    function graphFsToggleDropdown() {
        if (!fsFiltersDropdown || !fsFiltersToggle || !graphFsActive()) return;
        if (graphFsDropdownOpen) {
            graphFsCloseDropdown(false);
            return;
        }
        graphFsDropdownOpen = true;
        fsFiltersToggle.setAttribute('aria-expanded', 'true');
        if (fsDropCloseTimer) {
            clearTimeout(fsDropCloseTimer);
            fsDropCloseTimer = null;
        }
        fsFiltersDropdown.removeAttribute('hidden');
        fsFiltersDropdown.setAttribute('aria-hidden', 'false');
        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(function () {
                fsFiltersDropdown.classList.add('agences-fs-dropdown--open');
            });
        });
    }

    function graphFsMoveFiltersIntoOverlay() {
        var panel = document.getElementById('agences-filters-panel');
        if (!panel || !fsFiltersMount) return;
        if (panel.parentNode === fsFiltersMount) return;
        graphFsFiltersDock.parent = panel.parentNode;
        graphFsFiltersDock.next = panel.nextSibling;
        panel.classList.add('agences-filters--in-overlay');
        fsFiltersMount.appendChild(panel);
    }

    function graphFsRestoreFilters() {
        var panel = document.getElementById('agences-filters-panel');
        if (!panel || !graphFsFiltersDock.parent) return;
        panel.classList.remove('agences-filters--in-overlay');
        graphFsFiltersDock.parent.insertBefore(panel, graphFsFiltersDock.next);
        graphFsFiltersDock.parent = null;
        graphFsFiltersDock.next = null;
        syncFiltersCollapsedFromStorage();
    }

    function graphFsOnEnter() {
        if (!wrapEl) return;
        wrapEl.classList.add('graph-entreprises-wrap--fs');
        if (fsChrome) fsChrome.hidden = false;
        graphFsMoveFiltersIntoOverlay();
        graphFsUpdateBtnIcon();
        graphFsCloseDropdown(true);
        window.setTimeout(function () {
            if (typeof graphResizeHandler === 'function') graphResizeHandler();
        }, 120);
    }

    function graphFsOnLeave() {
        if (!wrapEl) return;
        wrapEl.classList.remove('graph-entreprises-wrap--fs', 'graph-entreprises-wrap--pseudo-fs');
        graphFsPseudo = false;
        document.body.classList.remove('graph-entreprises-fs-body-lock');
        if (fsChrome) fsChrome.hidden = true;
        graphFsCloseDropdown(true);
        graphFsRestoreFilters();
        graphFsUpdateBtnIcon();
        window.setTimeout(function () {
            if (typeof graphResizeHandler === 'function') graphResizeHandler();
        }, 120);
    }

    function graphFsEnter() {
        if (graphFsActive()) return;
        if (graphFsSupportsNative()) {
            graphRequestFullscreen(wrapEl).catch(function () {
                graphFsPseudo = true;
                document.body.classList.add('graph-entreprises-fs-body-lock');
                wrapEl.classList.add('graph-entreprises-wrap--pseudo-fs');
                graphFsOnEnter();
            });
        } else {
            graphFsPseudo = true;
            document.body.classList.add('graph-entreprises-fs-body-lock');
            wrapEl.classList.add('graph-entreprises-wrap--pseudo-fs');
            graphFsOnEnter();
        }
    }

    function graphFsLeave() {
        if (!graphFsActive()) return;
        graphFsCloseDropdown(true);
        if (graphFsPseudo) {
            graphFsOnLeave();
            return;
        }
        graphExitFullscreen().catch(function () {
            graphFsOnLeave();
        });
    }

    function graphFsSyncFromDocument() {
        var el =
            document.fullscreenElement ||
            document.webkitFullscreenElement ||
            document.msFullscreenElement;
        var nativeOn = !!(wrapEl && el === wrapEl);
        if (nativeOn) {
            graphFsPseudo = false;
            graphFsOnEnter();
        } else if (wrapEl && wrapEl.classList.contains('graph-entreprises-wrap--fs') && !graphFsPseudo) {
            graphFsOnLeave();
        }
        graphFsUpdateBtnIcon();
    }

    let network = null;
    let nodesDS = null;
    let edgesDS = null;
    let lastRaw = null;
    let apiNodeById = new Map();
    let physicsEnabled = false;
    let selectedNodeId = null;
    let filterDebounce = null;
    let filterRafScheduled = false;
    let viewPast = [];
    let viewFuture = [];
    let preDragView = null;
    var pendingMiniScrapeDomainEvents = [];

    /** Miniatures : URL source → data URL PNG (vis-network ne doit pas recharger l’URL distante → évite CachedImage 0×0). */
    var THUMB_DATA_MAX_PX = 72;
    var THUMB_PROBE_MAX_PARALLEL = 5;
    var thumbUrlDataUrl = new Map();
    var thumbUrlBad = new Set();
    var thumbProbeInflight = new Set();
    /** URL de vignette → ids de nœuds (évite un scan O(n) du graphe à chaque onload/onerror). */
    var thumbUrlToNodeIds = new Map();
    var thumbProbeQueue = [];
    var thumbUrlQueued = new Set();
    var thumbProbeRunning = 0;
    var deptZonesCache = [];
    var deptZonesRebuildTimer = null;
    /** Sync API rare (mini-scrape, etc.) — ne pas enchaîner à chaque lien temps réel. */
    var graphCoalescedSyncTimer = null;
    var graphExternalAnalysisRun = null;
    var miniScrapeProgress = { active: false, shown: 0, total: 0 };
    // Promotion d'un nœud domaine `a:host` vers une fiche entreprise `e:id` (évite le "détachement" / doublon).
    // clé = a:host, valeur = e:id
    var domainPromotions = new Map();

    function entrepriseDisplayName(run) {
        if (!run) return 'Entreprise';
        var n = String(run.entrepriseName || '').trim();
        if (n) return n;
        var u = String(run.url || '').trim();
        if (u) return u;
        var eid = Number(run.entrepriseId || 0);
        return eid > 0 ? 'Entreprise #' + String(eid) : 'Entreprise';
    }

    function entrepriseLabelFromRun(run, fallbackId) {
        if (!run) return String(fallbackId || '').trim() || 'Entreprise';
        var n = String(run.entrepriseName || '').trim();
        if (n && !/^e:\d+$/i.test(n)) return n;
        var u = String(run.url || '').trim();
        if (u) {
            try {
                var parsed = new URL(u.indexOf('http') === 0 ? u : 'https://' + u);
                var host = String(parsed.hostname || '').replace(/^www\./i, '').trim();
                if (host) return host;
            } catch (eUrl) {}
            return u;
        }
        return String(fallbackId || '').trim() || 'Entreprise';
    }

    /** Activer : ?graph_analysis_debug=1 ou localStorage graph_analysis_debug=1 */
    function graphAnalysisDebugEnabled() {
        try {
            if (new URLSearchParams(window.location.search || '').get('graph_analysis_debug') === '1') {
                return true;
            }
            if (localStorage.getItem('graph_analysis_debug') === '1') return true;
        } catch (e) {}
        return false;
    }

    function graphAnalysisDbg() {
        if (!graphAnalysisDebugEnabled() || typeof console === 'undefined' || !console.info) return;
        try {
            console.info.apply(console, ['[graph][analyse]'].concat([].slice.call(arguments)));
        } catch (e) {}
    }

    function promoteDomainNodeToEntreprise(domainNodeId, entrepriseNodeId) {
        if (!domainNodeId || !entrepriseNodeId || !nodesDS || !edgesDS) return false;
        if (String(domainNodeId).slice(0, 2) !== 'a:') return false;
        if (String(entrepriseNodeId).slice(0, 2) !== 'e:') return false;
        var aNode = nodesDS.get(domainNodeId);
        var eNode = nodesDS.get(entrepriseNodeId);
        if (!aNode) return false;

        // La fiche entreprise peut ne pas encore être présente dans le graphe courant.
        // On l'injecte pour garantir la promotion immédiate après scraping.
        if (!eNode) {
            try {
                var rawE =
                    (apiNodeById && apiNodeById.get && apiNodeById.get(entrepriseNodeId)) || {
                        id: entrepriseNodeId,
                        label: String(entrepriseNodeId),
                        title: String(entrepriseNodeId),
                        group: 'entreprise',
                    };
                rawE.group = 'entreprise';
                if (!rawE.label || /^e:\d+$/i.test(String(rawE.label))) {
                    rawE.label = entrepriseLabelFromRun(graphExternalAnalysisRun, entrepriseNodeId);
                }
                if (!rawE.title || /^e:\d+$/i.test(String(rawE.title))) {
                    rawE.title = rawE.label;
                }
                if (apiNodeById && apiNodeById.set) apiNodeById.set(entrepriseNodeId, rawE);
                var stE = getFilterState();
                var vsE = nodeVisualStyle(rawE);
                var siE = vsE.si;
                var ePatch = {
                    id: rawE.id,
                    label: displayLabel(rawE, stE),
                    title: graphNodeTooltipEl(rawE),
                    color: {
                        background: vsE.st.color,
                        border: visNodeOutline(),
                        highlight: {
                            background: vsE.st.color,
                            border: isLightTheme() ? '#0f172a' : '#f8fafc',
                        },
                    },
                    font: visNodeFontForGroup('entreprise'),
                    shape: siE.shape,
                    size: siE.size,
                    value: siE.value,
                    borderWidth: 4,
                    hidden: false,
                };
                applyNodeImageFields(ePatch, siE, false);
                nodesDS.update(ePatch);
                eNode = nodesDS.get(entrepriseNodeId);
            } catch (eIns) {}
        }
        if (!eNode) return false;

        // Copier la position du domaine vers la fiche entreprise (getPositions plus fiable que le DataSet).
        try {
            var patch = { id: entrepriseNodeId };
            var px = null;
            var py = null;
            try {
                if (network && typeof network.getPositions === 'function') {
                    var pm = network.getPositions([domainNodeId, entrepriseNodeId]);
                    if (pm && pm[domainNodeId] && typeof pm[domainNodeId].x === 'number') {
                        px = pm[domainNodeId].x;
                        py = pm[domainNodeId].y;
                    }
                }
            } catch (eG) {}
            if (px == null && typeof aNode.x === 'number' && typeof aNode.y === 'number') {
                px = aNode.x;
                py = aNode.y;
            }
            if (px != null && py != null) {
                patch.x = px;
                patch.y = py;
            }
            if (Object.keys(patch).length > 1) nodesDS.update(patch);
        } catch (e0) {}

        // Réécrire les arêtes.
        try {
            var edges = edgesDS.get();
            var updates = [];
            for (var i = 0; i < edges.length; i++) {
                var ed = edges[i];
                if (!ed) continue;
                var changed = false;
                var next = Object.assign({}, ed);
                if (next.from === domainNodeId) {
                    next.from = entrepriseNodeId;
                    changed = true;
                }
                if (next.to === domainNodeId) {
                    next.to = entrepriseNodeId;
                    changed = true;
                }
                if (changed) {
                    // Recalcul id stable si possible (sinon update garde l'id actuel).
                    try {
                        var rid = edgeStableId(next);
                        if (rid && rid !== next.id) next.id = rid;
                    } catch (e1) {}
                    updates.push(next);
                }
            }
            if (updates.length) edgesDS.update(updates);
        } catch (e2) {}

        // Retirer le nœud domaine.
        try {
            nodesDS.remove([domainNodeId]);
        } catch (e3) {}

        return true;
    }

    /** Aligner lastRaw / apiNodeById après fusion domaine → entreprise (avant tout fetch API). */
    function syncLastRawAfterDomainPromotion(domainNodeId, entrepriseNodeId, run) {
        if (!lastRaw || !domainNodeId || !entrepriseNodeId) return;
        if (String(domainNodeId).slice(0, 2) !== 'a:') return;
        if (String(entrepriseNodeId).slice(0, 2) !== 'e:') return;
        try {
            domainPromotions.delete(domainNodeId);
        } catch (e0) {}
        lastRaw.nodes = (lastRaw.nodes || []).filter(function (n) {
            return n && n.id !== domainNodeId;
        });
        try {
            apiNodeById.delete(domainNodeId);
        } catch (e1) {}
        (lastRaw.edges || []).forEach(function (e) {
            if (!e) return;
            if (e.from === domainNodeId) e.from = entrepriseNodeId;
            if (e.to === domainNodeId) e.to = entrepriseNodeId;
        });
        dedupeLastRawEdges();
        var rawE = apiNodeById.get(entrepriseNodeId);
        var bestLabel = entrepriseLabelFromRun(run, entrepriseNodeId);
        if (!rawE) {
            rawE = {
                id: entrepriseNodeId,
                group: 'entreprise',
                label: bestLabel,
                title: bestLabel,
            };
            apiNodeById.set(entrepriseNodeId, rawE);
            lastRaw.nodes.push(rawE);
        } else {
            rawE.group = 'entreprise';
            rawE.label = String(bestLabel).slice(0, 52);
            rawE.title = String(bestLabel).slice(0, 300);
            if (run && String(run.url || '').trim()) {
                rawE.resolved_url = String(run.url).trim();
            }
            rawE.is_shared_external_hub = false;
        }
    }

    function dedupeLastRawEdges() {
        if (!lastRaw || !lastRaw.edges) return;
        var seen = new Set();
        var out = [];
        lastRaw.edges.forEach(function (e) {
            if (!e) return;
            try {
                var id = edgeStableId(e);
                if (seen.has(id)) return;
                seen.add(id);
                out.push(e);
            } catch (e2) {
                out.push(e);
            }
        });
        lastRaw.edges = out;
    }

    function seededOffsetForNewNode(nodeId) {
        var h = 0;
        var s = String(nodeId || '');
        for (var i = 0; i < s.length; i++) {
            h = (h * 31 + s.charCodeAt(i)) | 0;
        }
        var ang = (Math.abs(h) % 360) * (Math.PI / 180);
        var dist = 200 + (Math.abs(h >> 3) % 140);
        return { cos: Math.cos(ang), sin: Math.sin(ang), dist: dist };
    }

    /** Position initiale pour un nœud absent du graphe : près d'un voisin déjà placé. */
    function layoutSeedPositionForNewVisNode(nodeId, edges, posMap) {
        if (!nodeId || !edges || !posMap) return null;
        var neighbors = [];
        for (var i = 0; i < edges.length; i++) {
            var e = edges[i];
            if (!e) continue;
            if (e.from === nodeId) neighbors.push(e.to);
            else if (e.to === nodeId) neighbors.push(e.from);
        }
        var seed = null;
        for (var j = 0; j < neighbors.length; j++) {
            var p = posMap[neighbors[j]];
            if (p && typeof p.x === 'number' && typeof p.y === 'number') {
                seed = p;
                break;
            }
        }
        if (!seed) return null;
        var off = seededOffsetForNewNode(nodeId);
        return { x: seed.x + off.cos * off.dist, y: seed.y + off.sin * off.dist };
    }

    function applyPendingDomainPromotions() {
        if (!domainPromotions || domainPromotions.size === 0) return;
        var done = [];
        domainPromotions.forEach(function (eId, aId) {
            if (promoteDomainNodeToEntreprise(aId, eId)) done.push(aId);
        });
        done.forEach(function (aId) {
            try {
                domainPromotions.delete(aId);
            } catch (e0) {}
        });
    }

    function imageToGraphThumbDataUrl(img) {
        var w = img.naturalWidth;
        var h = img.naturalHeight;
        if (w < 1 || h < 1) return null;
        var tw = w;
        var th = h;
        if (w > THUMB_DATA_MAX_PX || h > THUMB_DATA_MAX_PX) {
            var s = THUMB_DATA_MAX_PX / Math.max(w, h);
            tw = Math.max(1, Math.round(w * s));
            th = Math.max(1, Math.round(h * s));
        }
        var c = document.createElement('canvas');
        c.width = tw;
        c.height = th;
        var ctx = c.getContext('2d');
        if (!ctx) return null;
        try {
            ctx.drawImage(img, 0, 0, tw, th);
            return c.toDataURL('image/png');
        } catch (e) {
            return null;
        }
    }

    function applyNodeImageFields(target, si, isDataSetUpdate) {
        if (si.image) {
            target.image = si.image;
            target.shapeProperties = { useBorderWithImage: true, borderDashes: false };
        } else {
            if (isDataSetUpdate) {
                // vis-network 9 : image === null entre dans la branche « objet » puis lit null.unselected → TypeError.
                // Chaîne vide repasse par la branche URL (comme une image manquante / fallback).
                target.image = '';
            }
            target.shapeProperties = { useBorderWithImage: false, borderDashes: false };
        }
    }

    function refreshNodesForThumbUrl(url) {
        if (!nodesDS || !lastRaw || !url) return;
        var ids = thumbUrlToNodeIds.get(url);
        if (!ids || !ids.length) return;
        var state = getFilterState();
        var visibleIds = computeVisibleNodeIds(lastRaw.nodes, lastRaw.edges, state);
        var posMap = null;
        try {
            if (network && !physicsEnabled && typeof network.getPositions === 'function') {
                posMap = network.getPositions(ids);
            }
        } catch (ePos) {
            posMap = null;
        }
        var updates = [];
        ids.forEach(function (nid) {
            var n = apiNodeById.get(nid);
            if (!n) return;
            var vs = nodeVisualStyle(n);
            var st = vs.st;
            var si = visNodeShapeAndImage(n, st);
            var grp = n.group || 'external';
            var upd = {
                id: n.id,
                hidden: !visibleIds.has(n.id),
                label: displayLabel(n, state),
                title: graphNodeTooltipEl(n),
                font: visNodeFontForGroup(grp),
                shape: si.shape,
                size: si.size,
                value: si.value,
                borderWidth: grp === 'entreprise' ? 4 : 2,
                color: {
                    background: st.color,
                    border: visNodeOutline(),
                    highlight: {
                        background: st.color,
                        border: isLightTheme() ? '#0f172a' : '#f8fafc',
                    },
                },
            };
            applyNodeImageFields(upd, si, true);
            if (posMap && posMap[n.id] && typeof posMap[n.id].x === 'number' && typeof posMap[n.id].y === 'number') {
                upd.x = posMap[n.id].x;
                upd.y = posMap[n.id].y;
            }
            updates.push(upd);
        });
        if (updates.length) {
            try {
                nodesDS.update(updates);
            } catch (e) {
                /* ignore */
            }
        }
    }

    function pumpThumbProbes() {
        while (thumbProbeRunning < THUMB_PROBE_MAX_PARALLEL && thumbProbeQueue.length) {
            var url = thumbProbeQueue.shift();
            thumbUrlQueued.delete(url);
            if (!url || thumbUrlDataUrl.has(url) || thumbUrlBad.has(url)) continue;
            if (thumbProbeInflight.has(url)) continue;
            thumbProbeInflight.add(url);
            thumbProbeRunning++;
            var img = new Image();
            img.onload = function (u) {
                return function () {
                    thumbProbeRunning--;
                    thumbProbeInflight.delete(u);
                    var dataUrl = imageToGraphThumbDataUrl(img);
                    if (dataUrl) {
                        thumbUrlDataUrl.set(u, dataUrl);
                    } else {
                        thumbUrlBad.add(u);
                    }
                    refreshNodesForThumbUrl(u);
                    pumpThumbProbes();
                };
            }(url);
            img.onerror = function (u) {
                return function () {
                    thumbProbeRunning--;
                    thumbProbeInflight.delete(u);
                    thumbUrlBad.add(u);
                    refreshNodesForThumbUrl(u);
                    pumpThumbProbes();
                };
            }(url);
            try {
                img.src = url;
            } catch (e) {
                thumbProbeRunning--;
                thumbProbeInflight.delete(url);
                thumbUrlBad.add(url);
                refreshNodesForThumbUrl(url);
                pumpThumbProbes();
            }
        }
    }

    function probeThumbnailUrl(url) {
        if (!url || thumbUrlDataUrl.has(url) || thumbUrlBad.has(url)) return;
        if (thumbProbeInflight.has(url) || thumbUrlQueued.has(url)) return;
        thumbUrlQueued.add(url);
        thumbProbeQueue.push(url);
        pumpThumbProbes();
    }

    function entrepriseUrl(id) {
        if (window.GRAPH_ENTREPRISES_PAGE && typeof window.GRAPH_ENTREPRISES_PAGE.entrepriseUrl === 'function') {
            return window.GRAPH_ENTREPRISES_PAGE.entrepriseUrl(id);
        }
        return '/entreprise/' + encodeURIComponent(id);
    }

    function clearGraphCoalescedSyncTimer() {
        if (graphCoalescedSyncTimer) {
            clearTimeout(graphCoalescedSyncTimer);
            graphCoalescedSyncTimer = null;
        }
    }

    /** Une seule fusion API après la fin d’activité (évite centaines de fetch pendant le crawl). */
    function scheduleGraphCoalescedApiSync(delayMs) {
        var d = delayMs == null ? 2400 : delayMs;
        if (graphCoalescedSyncTimer) clearTimeout(graphCoalescedSyncTimer);
        graphCoalescedSyncTimer = setTimeout(function () {
            graphCoalescedSyncTimer = null;
            refreshGraphIncremental();
        }, d);
    }

    function miniScrapeProgressSuffix() {
        if (!miniScrapeProgress.active) return '';
        var shown = Number(miniScrapeProgress.shown || 0);
        var total = Number(miniScrapeProgress.total || 0);
        if (total > 0) {
            return '  mini-scrape: ' + String(shown) + '/' + String(total);
        }
        return '  mini-scrape: ' + String(shown) + ' domaine(s)';
    }

    function renderExternalAnalysisStatus() {
        var box = document.getElementById('graph-external-analysis-status');
        if (!box) return;
        var base = String((box.dataset && box.dataset.baseMessage) || '').trim();
        var isError = !!(box.dataset && box.dataset.isError === '1');
        var msg = base;
        if (!isError && msg) {
            msg += miniScrapeProgressSuffix();
        }
        box.textContent = msg;
        box.hidden = !msg;
    }

    function startMiniScrapeProgress(totalHint) {
        miniScrapeProgress.active = true;
        miniScrapeProgress.shown = 0;
        miniScrapeProgress.total = Math.max(0, Number(totalHint || 0) || 0);
        renderExternalAnalysisStatus();
    }

    function bumpMiniScrapeProgress() {
        if (!miniScrapeProgress.active) miniScrapeProgress.active = true;
        miniScrapeProgress.shown = Math.max(0, Number(miniScrapeProgress.shown || 0) + 1);
        renderExternalAnalysisStatus();
    }

    function finishMiniScrapeProgress(finalTotal) {
        var t = Math.max(0, Number(finalTotal || 0) || 0);
        if (t > 0) {
            miniScrapeProgress.total = t;
            if (miniScrapeProgress.shown < t) miniScrapeProgress.shown = t;
        }
        miniScrapeProgress.active = false;
        renderExternalAnalysisStatus();
    }

    function setExternalAnalysisStatus(message, isError) {
        var box = document.getElementById('graph-external-analysis-status');
        if (!box) return;
        box.dataset.baseMessage = message || '';
        box.dataset.isError = isError ? '1' : '0';
        renderExternalAnalysisStatus();
        box.style.color = isError ? '#f87171' : '';
    }

    function setExternalAnalyzeButtonBusy(isBusy) {
        var btn = document.getElementById('graph-external-analyze-btn');
        if (!btn) return;
        btn.disabled = !!isBusy;
    }

    function upsertExternalLinkRealtime(link, sourceEntrepriseId) {
        if (!link || !sourceEntrepriseId || !lastRaw || !nodesDS || !edgesDS) return;
        fixMojibakeInObj(link);
        var host = String(link.domain_host || '').trim();
        if (!host) return;

        var sourceNodeId = 'e:' + String(sourceEntrepriseId);
        var domainNodeId = 'a:' + host;

        // Assurer la présence de la fiche entreprise source dans le graphe, sinon
        // les events "domain_complete" ne peuvent pas créer le lien immédiatement.
        if (!apiNodeById.has(sourceNodeId)) {
            try {
                var rawSrc = {
                    id: sourceNodeId,
                    group: 'entreprise',
                    label: entrepriseLabelFromRun(graphExternalAnalysisRun, sourceNodeId),
                    title: entrepriseLabelFromRun(graphExternalAnalysisRun, sourceNodeId),
                };
                lastRaw.nodes.push(rawSrc);
                apiNodeById.set(sourceNodeId, rawSrc);

                var stSrc = getFilterState();
                var vsSrc = nodeVisualStyle(rawSrc);
                var siSrc = vsSrc.si;
                var srcPos = null;
                try {
                    if (network && typeof network.getViewPosition === 'function') {
                        srcPos = network.getViewPosition();
                    }
                } catch (eVP) {}
                var nodeForDsSrc = {
                    id: rawSrc.id,
                    label: displayLabel(rawSrc, stSrc),
                    title: graphNodeTooltipEl(rawSrc),
                    color: {
                        background: vsSrc.st.color,
                        border: visNodeOutline(),
                        highlight: {
                            background: vsSrc.st.color,
                            border: isLightTheme() ? '#0f172a' : '#f8fafc',
                        },
                    },
                    font: visNodeFontForGroup('entreprise'),
                    shape: siSrc.shape,
                    size: siSrc.size,
                    value: siSrc.value,
                    borderWidth: 4,
                    hidden: false,
                };
                if (srcPos && typeof srcPos.x === 'number' && typeof srcPos.y === 'number') {
                    nodeForDsSrc.x = srcPos.x;
                    nodeForDsSrc.y = srcPos.y;
                }
                applyNodeImageFields(nodeForDsSrc, siSrc, false);
                nodesDS.update(nodeForDsSrc);
            } catch (eSrc) {
                return;
            }
        }

        var linkTitle = String(fixMojibake(link.site_title || '') || '').trim();
        var linkDesc = String(fixMojibake(link.site_description || '') || '').trim();
        var linkResolved = String(fixMojibake(link.resolved_url || link.external_href || '') || '').trim();
        var linkThumb = String(link.thumb_url || '').trim();

        // 1) Upsert node domaine externe.
        if (!apiNodeById.has(domainNodeId)) {
            var rawNode = {
                id: domainNodeId,
                label: linkTitle || host,
                group: 'external',
                title: linkTitle || host,
                domain: host,
            };
            if (linkResolved) rawNode.resolved_url = linkResolved;
            if (linkDesc) rawNode.site_description = linkDesc;
            if (linkThumb) {
                rawNode.thumb_url = linkThumb;
                rawNode.thumbnail_url = linkThumb;
            }
            var seedPos = null;
            try {
                var off = seededOffsetForNewNode(domainNodeId);
                // Couronne "molécule" plus large autour de l'entreprise.
                var dist = 170 + (Math.abs(Math.round((off.dist || 200) * 0.57)) % 130);
                var srcPos = null;
                if (network && typeof network.getPositions === 'function') {
                    var pm = network.getPositions([sourceNodeId]);
                    if (pm && pm[sourceNodeId] && typeof pm[sourceNodeId].x === 'number') {
                        srcPos = pm[sourceNodeId];
                    }
                }
                if (!srcPos && network && typeof network.getViewPosition === 'function') {
                    srcPos = network.getViewPosition();
                }
                if (srcPos && typeof srcPos.x === 'number' && typeof srcPos.y === 'number') {
                    seedPos = {
                        x: srcPos.x + off.cos * dist,
                        y: srcPos.y + off.sin * dist,
                    };
                    rawNode.x = seedPos.x;
                    rawNode.y = seedPos.y;
                }
            } catch (eSeed) {}
            lastRaw.nodes.push(rawNode);
            apiNodeById.set(domainNodeId, rawNode);

            var st = getFilterState();
            var vs = nodeVisualStyle(rawNode);
            var si = vs.si;
            var nodeForDs = {
                id: rawNode.id,
                label: displayLabel(rawNode, st),
                title: graphNodeTooltipEl(rawNode),
                color: {
                    background: vs.st.color,
                    border: visNodeOutline(),
                    highlight: {
                        background: vs.st.color,
                        border: isLightTheme() ? '#0f172a' : '#f8fafc',
                    },
                },
                font: visNodeFontForGroup(rawNode.group || 'external'),
                shape: si.shape,
                size: si.size,
                value: si.value,
                borderWidth: 2,
                hidden: false,
            };
            if (seedPos && typeof seedPos.x === 'number' && typeof seedPos.y === 'number') {
                nodeForDs.x = seedPos.x;
                nodeForDs.y = seedPos.y;
            }
            applyNodeImageFields(nodeForDs, si, false);
            nodesDS.update(nodeForDs);
        } else {
            // Si le mini-scrape apporte de nouvelles infos, on patch le nœud existant immédiatement.
            var curNode = apiNodeById.get(domainNodeId) || {};
            if (linkTitle) {
                curNode.label = linkTitle;
                curNode.title = linkTitle;
            }
            if (linkResolved) curNode.resolved_url = linkResolved;
            if (linkDesc) curNode.site_description = linkDesc;
            if (linkThumb) {
                curNode.thumb_url = linkThumb;
                curNode.thumbnail_url = linkThumb;
            }
            apiNodeById.set(domainNodeId, curNode);
            try {
                var st2 = getFilterState();
                var vs2 = nodeVisualStyle(curNode);
                var si2 = vs2.si;
                var upd2 = {
                    id: domainNodeId,
                    label: displayLabel(curNode, st2),
                    title: graphNodeTooltipEl(curNode),
                    color: {
                        background: vs2.st.color,
                        border: visNodeOutline(),
                        highlight: {
                            background: vs2.st.color,
                            border: isLightTheme() ? '#0f172a' : '#f8fafc',
                        },
                    },
                    font: visNodeFontForGroup(curNode.group || 'external'),
                    shape: si2.shape,
                    size: si2.size,
                    value: si2.value,
                    borderWidth: 2,
                    hidden: false,
                };
                applyNodeImageFields(upd2, si2, true);
                nodesDS.update(upd2);
            } catch (ePatchNode) {}
        }

        // 2) Upsert edge entreprise -> domaine (lien externe).
        var rawEdgeExt = {
            from: sourceNodeId,
            to: domainNodeId,
            label: 'lien',
            arrows: 'to',
            dashes: false,
            color: { color: '#a78bfa' },
        };
        var extId = edgeStableId(rawEdgeExt);
        var hasExt = !!edgesDS.get(extId);
        if (!hasExt) {
            lastRaw.edges.push(rawEdgeExt);
            edgesDS.update(
                Object.assign(
                    {
                        id: extId,
                        title: graphEdgeTooltipEl(rawEdgeExt),
                        font: visEdgeFont(),
                        hidden: false,
                        smooth: { type: 'continuous', roundness: 0.35 },
                        width: 1.9,
                    },
                    rawEdgeExt
                )
            );
        }

        // 3) Si la fiche cible existe déjà DANS LE GRAPHE, relier vers elle.
        var tid = Number(link.target_entreprise_id || 0);
        if (tid > 0) {
            var targetNodeId = 'e:' + String(tid);
            if (apiNodeById.has(targetNodeId)) {
                var rawEdgeToFiche = {
                    from: domainNodeId,
                    to: targetNodeId,
                    label: 'fiche en base',
                    arrows: 'to',
                    dashes: true,
                    color: { color: '#22c55e' },
                };
                var toFicheId = edgeStableId(rawEdgeToFiche);
                if (!edgesDS.get(toFicheId)) {
                    lastRaw.edges.push(rawEdgeToFiche);
                    edgesDS.update(
                        Object.assign(
                            {
                                id: toFicheId,
                                title: graphEdgeTooltipEl(rawEdgeToFiche),
                                font: visEdgeFont(),
                                hidden: false,
                                smooth: { type: 'continuous', roundness: 0.35 },
                                width: 2.0,
                            },
                            rawEdgeToFiche
                        )
                    );
                }
            }
        }

        // Recalcule les hidden/labels selon filtres actifs.
        scheduleApplyFiltersRaf();
        scheduleDeptZonesRebuild(40);
    }

    function showGraphNotification(message, type) {
        var t = type || 'info';
        try {
            if (window.Notifications && typeof window.Notifications.show === 'function') {
                window.Notifications.show(String(message || ''), t);
                return;
            }
        } catch (e) {}
        // Fallback minimal si le module global n'est pas chargé
        var n = document.createElement('div');
        n.className = 'notification notification-' + t;
        n.textContent = message;
        n.style.cssText =
            'position:fixed;top:20px;right:20px;padding:12px 16px;border-radius:8px;' +
            'box-shadow:0 4px 14px rgba(0,0,0,.25);z-index:10000;font-size:.9rem;' +
            'background:' + (t === 'success' ? '#d4edda' : t === 'error' ? '#f8d7da' : '#d1ecf1') + ';' +
            'color:' + (t === 'success' ? '#155724' : t === 'error' ? '#721c24' : '#0c5460') + ';';
        document.body.appendChild(n);
        setTimeout(function () {
            if (n && n.parentNode) n.parentNode.removeChild(n);
        }, 2600);
    }

    function ensureRealtimeFeedHost() {
        if (!wrapEl) return null;
        var host = document.getElementById('graph-realtime-feed');
        if (host) return host;
        host = document.createElement('div');
        host.id = 'graph-realtime-feed';
        host.style.cssText =
            'position:absolute;left:12px;bottom:12px;z-index:11;display:flex;flex-direction:column;' +
            'gap:6px;max-width:min(44rem,calc(100% - 7rem));pointer-events:none;';
        wrapEl.appendChild(host);
        return host;
    }

    function pushRealtimeFeedLine(message, isError) {
        var host = ensureRealtimeFeedHost();
        if (!host) return;
        var row = document.createElement('div');
        row.style.cssText =
            'padding:6px 9px;border-radius:8px;font-size:.78rem;line-height:1.3;' +
            'background:' + (isError ? 'rgba(127,29,29,.88)' : 'rgba(15,23,42,.86)') + ';' +
            'color:' + (isError ? '#fecaca' : '#cbd5e1') + ';' +
            'border:1px solid ' + (isError ? 'rgba(248,113,113,.45)' : 'rgba(148,163,184,.25)') + ';' +
            'box-shadow:0 4px 14px rgba(0,0,0,.35);';
        row.textContent = message;
        host.appendChild(row);
        while (host.children.length > 5) {
            host.removeChild(host.firstChild);
        }
        window.setTimeout(function () {
            try {
                row.style.opacity = '0';
                row.style.transition = 'opacity .35s ease';
                window.setTimeout(function () {
                    if (row.parentNode) row.parentNode.removeChild(row);
                }, 360);
            } catch (e) {}
        }, 5200);
    }

    function externalUrlFromNode(raw) {
        if (!raw) return '';
        var candidate =
            (raw.resolved_url || '').trim() ||
            (raw.sample_external_url || '').trim() ||
            (raw.domain || '').trim();
        if (!candidate) return '';
        if (/^https?:\/\//i.test(candidate)) return candidate;
        return 'https://' + candidate.replace(/^\/+/, '');
    }

    function parseJsonResponseSafe(response) {
        return response.text().then(function (txt) {
            var body = {};
            if (txt && txt.trim()) {
                try {
                    body = JSON.parse(txt);
                } catch (e) {
                    body = { error: 'Réponse serveur non JSON.' };
                }
            }
            return { ok: response.ok, status: response.status, body: body };
        });
    }

    function setLoading(on) {
        if (!loadingEl) return;
        loadingEl.classList.toggle('is-visible', !!on);
        loadingEl.setAttribute('aria-hidden', on ? 'false' : 'true');
    }

    var THEME_STORAGE_KEY = 'prospectlab_graph_entreprises_theme';

    function isLightTheme() {
        var k = localStorage.getItem(THEME_STORAGE_KEY);
        if (k === 'light') return true;
        if (k === 'dark') return false;
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
    }

    function syncTooltipThemeVars() {
        var r = document.documentElement;
        if (isLightTheme()) {
            r.style.setProperty('--agences-tip-surface', '#ffffff');
            r.style.setProperty('--agences-tip-on-surface', '#0f172a');
            r.style.setProperty('--agences-tip-muted', '#64748b');
            r.style.setProperty('--agences-tip-border', 'rgba(15, 23, 42, 0.12)');
            r.style.setProperty('--agences-tip-shadow', '0 12px 40px rgba(15, 23, 42, 0.14)');
            r.style.setProperty('--agences-tip-chip-bg', 'rgba(15, 23, 42, 0.07)');
            r.style.setProperty('--agences-tip-chip-border', 'rgba(15, 23, 42, 0.1)');
            r.style.setProperty('--agences-tip-link', '#2563eb');
        } else {
            r.style.setProperty('--agences-tip-surface', '#1e293b');
            r.style.setProperty('--agences-tip-on-surface', '#f1f5f9');
            r.style.setProperty('--agences-tip-muted', '#94a3b8');
            r.style.setProperty('--agences-tip-border', 'rgba(148, 163, 184, 0.22)');
            r.style.setProperty('--agences-tip-shadow', '0 16px 48px rgba(0, 0, 0, 0.55)');
            r.style.setProperty('--agences-tip-chip-bg', 'rgba(148, 163, 184, 0.12)');
            r.style.setProperty('--agences-tip-chip-border', 'rgba(148, 163, 184, 0.2)');
            r.style.setProperty('--agences-tip-link', '#8ab4ff');
        }
    }

    function syncThemeClasses() {
        var root = document.querySelector('.graph-entreprises-page');
        if (!root) return;
        root.classList.remove('agences-force-dark', 'agences-force-light');
        var k = localStorage.getItem(THEME_STORAGE_KEY);
        if (k === 'dark') root.classList.add('agences-force-dark');
        else if (k === 'light') root.classList.add('agences-force-light');
        syncTooltipThemeVars();
    }

    function updateThemeToggleUi() {
        var btn = document.getElementById('agences-theme-toggle');
        if (!btn) return;
        var icon = btn.querySelector('.material-symbols-rounded');
        var label = btn.querySelector('.agences-theme-label');
        var k = localStorage.getItem(THEME_STORAGE_KEY) || '';
        if (k === 'dark') {
            if (icon) icon.textContent = 'dark_mode';
            if (label) label.textContent = 'Sombre';
            btn.setAttribute('aria-label', 'Thème : sombre');
        } else if (k === 'light') {
            if (icon) icon.textContent = 'light_mode';
            if (label) label.textContent = 'Clair';
            btn.setAttribute('aria-label', 'Thème : clair');
        } else {
            if (icon) icon.textContent = 'routine';
            if (label) label.textContent = 'Auto';
            btn.setAttribute('aria-label', 'Thème : automatique');
        }
    }

    function cycleThemePreference() {
        var k = localStorage.getItem(THEME_STORAGE_KEY) || '';
        var next = k === '' ? 'dark' : k === 'dark' ? 'light' : '';
        if (next === '') localStorage.removeItem(THEME_STORAGE_KEY);
        else localStorage.setItem(THEME_STORAGE_KEY, next);
        syncThemeClasses();
        updateThemeToggleUi();
        if (nodesDS && lastRaw) applyFilters();
        if (network) {
            try {
                network.setOptions({
                    nodes: visNodesGlobalOptions(),
                });
            } catch (e) {}
        }
    }

    var graphBrokenImageDataUrl = null;

    /**
     * Image de secours pour vis-network (favicons / miniatures HS ou 0×0).
     * Sans cela, CachedImage peut tenter un drawImage sur un canvas vide → InvalidStateError.
     */
    function getGraphBrokenImageDataUrl() {
        if (graphBrokenImageDataUrl) return graphBrokenImageDataUrl;
        try {
            var c = document.createElement('canvas');
            c.width = 64;
            c.height = 64;
            var ctx = c.getContext('2d');
            if (!ctx) throw new Error('no ctx');
            ctx.fillStyle = '#4b5563';
            ctx.fillRect(0, 0, 64, 64);
            ctx.strokeStyle = 'rgba(255,255,255,0.22)';
            ctx.lineWidth = 2;
            ctx.strokeRect(2, 2, 60, 60);
            ctx.strokeStyle = 'rgba(255,255,255,0.35)';
            ctx.beginPath();
            ctx.moveTo(22, 32);
            ctx.lineTo(42, 32);
            ctx.moveTo(32, 22);
            ctx.lineTo(32, 42);
            ctx.stroke();
            graphBrokenImageDataUrl = c.toDataURL('image/png');
        } catch (e) {
            graphBrokenImageDataUrl =
                'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
        }
        return graphBrokenImageDataUrl;
    }

    function visNodesGlobalOptions() {
        return {
            brokenImage: getGraphBrokenImageDataUrl(),
            shadow: {
                enabled: true,
                color: isLightTheme() ? 'rgba(15,23,42,0.12)' : 'rgba(0,0,0,0.35)',
                size: 12,
                x: 2,
                y: 2,
            },
        };
    }

    function visNodeFont() {
        return isLightTheme()
            ? { color: '#0f172a', size: 14, face: 'Roboto', strokeWidth: 2, strokeColor: '#f8fafc' }
            : { color: '#f1f5f9', size: 14, face: 'Roboto', strokeWidth: 2, strokeColor: '#0f172a' };
    }

    function visNodeFontForGroup(grp) {
        var b = visNodeFont();
        if (grp === 'entreprise') {
            return { color: b.color, size: b.size + 6, face: b.face, strokeWidth: b.strokeWidth + 1, strokeColor: b.strokeColor };
        }
        return b;
    }

    function getForceAtlas2Opts() {
        return {
            gravitationalConstant: -178,
            centralGravity: 0.0058,
            springLength: 395,
            springConstant: 0.024,
            avoidOverlap: 0.988,
        };
    }

    function visEdgeFont() {
        return isLightTheme()
            ? { size: 12, color: '#475569', align: 'middle', strokeWidth: 0 }
            : { size: 12, color: '#e2e8f0', align: 'middle', strokeWidth: 0 };
    }

    function visNodeOutline() {
        return isLightTheme() ? '#e2e8f0' : '#1e293b';
    }

    function viewCapture() {
        if (!network) return null;
        var p = network.getViewPosition();
        return { scale: network.getScale(), x: p.x, y: p.y };
    }

    function viewApply(v) {
        if (!network || !v) return;
        network.moveTo({
            scale: v.scale,
            position: { x: v.x, y: v.y },
            animation: { duration: 380, easingFunction: 'easeInOutQuad' },
        });
    }

    function viewPushCurrent() {
        var c = viewCapture();
        if (!c) return;
        viewPast.push(c);
        if (viewPast.length > 20) viewPast.shift();
        viewFuture = [];
    }

    function viewBack() {
        if (!network || viewPast.length === 0) return;
        viewFuture.push(viewCapture());
        viewApply(viewPast.pop());
    }

    function viewFwd() {
        if (!network || viewFuture.length === 0) return;
        viewPast.push(viewCapture());
        viewApply(viewFuture.shift());
    }

    function viewDist(a, b) {
        if (!a || !b) return 999;
        return (
            Math.abs(a.scale - b.scale) +
            Math.abs(a.x - b.x) / 400 +
            Math.abs(a.y - b.y) / 400
        );
    }

    /** Options communes pour network.fit (même animation que « Cadrer »). */
    function graphFitOptions() {
        return {
            animation: { duration: 550, easingFunction: 'easeInOutQuad' },
        };
    }

    function buildVisibleDegree() {
        var d = {};
        if (!edgesDS || !nodesDS) return d;
        edgesDS.forEach(function (edge) {
            try {
                var fn = nodesDS.get(edge.from);
                var tn = nodesDS.get(edge.to);
                if (fn && fn.hidden) return;
                if (tn && tn.hidden) return;
            } catch (e) {
                return;
            }
            d[edge.from] = (d[edge.from] || 0) + 1;
            d[edge.to] = (d[edge.to] || 0) + 1;
        });
        return d;
    }

    function edgeKind(e) {
        const lbl = (e.label || '').toLowerCase();
        if (lbl.indexOf('crédit') !== -1 || lbl === 'crédit') return 'credit';
        if (lbl.indexOf('fiche') !== -1) return 'fiche';
        if (lbl.indexOf('réf') !== -1 || lbl.indexOf('ref') !== -1) return 'ref';
        return 'lien';
    }

    function nodeGroupVisible(n, state) {
        const g = n.group || 'external';
        if (g === 'entreprise') return state.showEnt;
        if (g === 'agency') return state.showAgency;
        return state.showOther;
    }

    function nodeMatchesQuery(n, q) {
        if (!q) return false;
        const hay = [
            n.label,
            n.title,
            n.domain,
            n.id,
            (n.categories || []).join(' '),
            (n.jsonld_types || []).join(' '),
            (n.shared_external_domains || []).join(' '),
        ]
            .filter(Boolean)
            .join(' ')
            .toLowerCase();
        return hay.indexOf(q) !== -1;
    }

    function computeVisibleNodeIds(rawNodes, rawEdges, state) {
        const base = new Set();
        (rawNodes || []).forEach(function (n) {
            if (nodeGroupVisible(n, state)) base.add(n.id);
        });
        const q = state.search;
        if (!q) return base;
        const matching = new Set();
        (rawNodes || []).forEach(function (n) {
            if (!base.has(n.id)) return;
            if (nodeMatchesQuery(n, q)) matching.add(n.id);
        });
        const out = new Set(matching);
        (rawEdges || []).forEach(function (e) {
            if (matching.has(e.from) || matching.has(e.to)) {
                if (base.has(e.from)) out.add(e.from);
                if (base.has(e.to)) out.add(e.to);
            }
        });
        return out;
    }

    function edgeVisible(e, visibleNodes, state) {
        if (!visibleNodes.has(e.from) || !visibleNodes.has(e.to)) return false;
        const k = edgeKind(e);
        if (k === 'credit') return state.edgeCredit;
        if (k === 'fiche') return state.edgeFiche;
        if (k === 'ref') return state.edgeRef;
        return state.edgeLien;
    }

    function getFilterState() {
        function chk(id, def) {
            const el = document.getElementById(id);
            return el ? el.checked : def;
        }
        const searchEl = document.getElementById('graph-entreprises-search');
        return {
            showEnt: chk('flt-nodes-ent', true),
            showAgency: chk('flt-nodes-agency', true),
            showOther: chk('flt-nodes-other', true),
            edgeCredit: chk('flt-edge-credit', true),
            edgeLien: chk('flt-edge-lien', true),
            edgeRef: chk('flt-edge-ref', true),
            edgeFiche: chk('flt-edge-fiche', true),
            compactLabels: chk('flt-compact-labels', true),
            colorByGeo: chk('flt-color-by-geo', false),
            search: (searchEl && searchEl.value ? searchEl.value : '').trim().toLowerCase(),
        };
    }

    function visNodeShapeAndImage(n, st) {
        const u = (n.thumb_url || n.thumbnail_url || '').trim();
        const grp = n.group || 'external';
        const minImg = grp === 'entreprise' ? 38 : grp === 'agency' ? 34 : 30;
        const minVal = grp === 'entreprise' ? 44 : grp === 'agency' ? 36 : 28;
        if (u && /^https?:\/\//i.test(u)) {
            if (thumbUrlBad.has(u)) {
                return { shape: st.shape, image: undefined, size: st.size, value: st.value };
            }
            if (thumbUrlDataUrl.has(u)) {
                return {
                    shape: 'circularImage',
                    image: thumbUrlDataUrl.get(u),
                    size: Math.max(st.size, minImg),
                    value: Math.max(st.value || 0, minVal),
                };
            }
            probeThumbnailUrl(u);
            return { shape: st.shape, image: undefined, size: st.size, value: st.value };
        }
        return { shape: st.shape, image: undefined, size: st.size, value: st.value };
    }

    /**
     * Couleur stable par clé géographique (département / ville / inconnu) — lisible en clair et sombre.
     */
    function geoPaletteColor(geoKey) {
        var s = String(geoKey || 'geo:unknown');
        var h = 2166136261;
        for (var i = 0; i < s.length; i++) {
            h ^= s.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        var hue = Math.abs(h) % 360;
        var sat = isLightTheme() ? '52%' : '56%';
        var light = isLightTheme() ? '40%' : '50%';
        return 'hsl(' + hue + ',' + sat + ',' + light + ')';
    }

    function clearDeptZonesCache() {
        deptZonesCache = [];
        if (deptZonesRebuildTimer) {
            clearTimeout(deptZonesRebuildTimer);
            deptZonesRebuildTimer = null;
        }
    }

    function convexHull(points) {
        if (!points || points.length < 3) return points ? points.slice() : [];
        var pts = points
            .map(function (p) { return { x: Number(p.x), y: Number(p.y) }; })
            .filter(function (p) { return isFinite(p.x) && isFinite(p.y); })
            .sort(function (a, b) { return a.x === b.x ? a.y - b.y : a.x - b.x; });
        if (pts.length < 3) return pts;
        function cross(o, a, b) {
            return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
        }
        var lower = [];
        for (var i = 0; i < pts.length; i++) {
            while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pts[i]) <= 0) {
                lower.pop();
            }
            lower.push(pts[i]);
        }
        var upper = [];
        for (var j = pts.length - 1; j >= 0; j--) {
            while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pts[j]) <= 0) {
                upper.pop();
            }
            upper.push(pts[j]);
        }
        lower.pop();
        upper.pop();
        return lower.concat(upper);
    }

    function expandPolygon(points, pad) {
        if (!points || !points.length) return [];
        var cx = 0;
        var cy = 0;
        points.forEach(function (p) {
            cx += p.x;
            cy += p.y;
        });
        cx /= points.length;
        cy /= points.length;
        return points.map(function (p) {
            var dx = p.x - cx;
            var dy = p.y - cy;
            var d = Math.hypot(dx, dy) || 1;
            return {
                x: p.x + (dx / d) * pad,
                y: p.y + (dy / d) * pad,
            };
        });
    }

    function drawSmoothPolygon(ctx, points, radius) {
        if (!points || points.length < 3) return;
        var r = Math.max(4, radius || 16);
        var n = points.length;
        ctx.beginPath();
        for (var i = 0; i < n; i++) {
            var p0 = points[(i - 1 + n) % n];
            var p1 = points[i];
            var p2 = points[(i + 1) % n];
            var inDx = p1.x - p0.x;
            var inDy = p1.y - p0.y;
            var inLen = Math.hypot(inDx, inDy) || 1;
            var outDx = p2.x - p1.x;
            var outDy = p2.y - p1.y;
            var outLen = Math.hypot(outDx, outDy) || 1;
            var rr = Math.min(r, inLen * 0.45, outLen * 0.45);
            var sx = p1.x - (inDx / inLen) * rr;
            var sy = p1.y - (inDy / inLen) * rr;
            var ex = p1.x + (outDx / outLen) * rr;
            var ey = p1.y + (outDy / outLen) * rr;
            if (i === 0) ctx.moveTo(sx, sy);
            else ctx.lineTo(sx, sy);
            ctx.quadraticCurveTo(p1.x, p1.y, ex, ey);
        }
        ctx.closePath();
    }

    function rebuildDeptZonesCache() {
        if (!network || !lastRaw || !lastRaw.nodes || !lastRaw.nodes.length) {
            deptZonesCache = [];
            return;
        }
        var state = getFilterState();
        if (!state.colorByGeo) {
            deptZonesCache = [];
            return;
        }
        var visibleIds = computeVisibleNodeIds(lastRaw.nodes, lastRaw.edges, state);
        var byDept = new Map();
        lastRaw.nodes.forEach(function (n) {
            if ((n.group || 'external') !== 'entreprise') return;
            if (!visibleIds.has(n.id)) return;
            var gk = String(n.geo_key || '');
            if (!gk || gk.indexOf('dept:') !== 0) return;
            var dept = gk.slice(5);
            if (!dept) return;
            if (!byDept.has(dept)) byDept.set(dept, []);
            byDept.get(dept).push(n.id);
        });
        var cache = [];
        byDept.forEach(function (ids, dept) {
            if (!ids || !ids.length) return;
            var pos = network.getPositions(ids);
            var points = [];
            var cx = 0;
            var cy = 0;
            ids.forEach(function (id) {
                var p = pos[id];
                if (!p) return;
                points.push({ x: p.x, y: p.y });
                cx += p.x;
                cy += p.y;
            });
            if (!points.length) return;
            var count = ids.length;
            cx /= points.length;
            cy /= points.length;
            var hull = convexHull(points);
            var pad = Math.max(46, Math.min(130, 34 + Math.sqrt(count) * 12));
            var expanded = expandPolygon(hull, pad);
            if (expanded.length < 3) {
                expanded = expandPolygon(
                    [
                        { x: cx - 90, y: cy - 60 },
                        { x: cx + 90, y: cy - 60 },
                        { x: cx + 90, y: cy + 60 },
                        { x: cx - 90, y: cy + 60 },
                    ],
                    Math.max(10, pad * 0.4)
                );
            }
            cache.push({
                dept: dept,
                count: count,
                cx: cx,
                cy: cy,
                points: expanded,
                color: geoPaletteColor('dept:' + dept),
            });
        });
        cache.sort(function (a, b) {
            return b.count - a.count;
        });
        deptZonesCache = cache;
    }

    function scheduleDeptZonesRebuild(delayMs) {
        if (deptZonesRebuildTimer) {
            clearTimeout(deptZonesRebuildTimer);
            deptZonesRebuildTimer = null;
        }
        deptZonesRebuildTimer = setTimeout(function () {
            deptZonesRebuildTimer = null;
            rebuildDeptZonesCache();
            if (network) {
                try {
                    network.redraw();
                } catch (e) {}
            }
        }, delayMs == null ? 220 : delayMs);
    }

    function drawDeptZones(ctx) {
        var state = getFilterState();
        if (!state.colorByGeo || !deptZonesCache.length) return;
        ctx.save();
        ctx.globalCompositeOperation = 'destination-over';
        deptZonesCache.forEach(function (z) {
            var fill = z.color.replace('hsl(', 'hsla(').replace(')', ',0.14)');
            var stroke = z.color.replace('hsl(', 'hsla(').replace(')', ',0.34)');
            drawSmoothPolygon(ctx, z.points, 22);
            ctx.fillStyle = fill;
            ctx.fill();
            ctx.lineWidth = 3;
            ctx.strokeStyle = stroke;
            ctx.stroke();
            var label = 'Dept ' + z.dept + ' - ' + z.count + ' entreprise' + (z.count > 1 ? 's' : '');
            ctx.font = '600 24px Roboto, sans-serif';
            ctx.fillStyle = stroke;
            var tw = 0;
            try {
                tw = ctx.measureText(label).width || 0;
            } catch (e) {}
            ctx.fillText(label, z.cx - tw / 2, z.cy - 18);
        });
        ctx.restore();
    }

    function visStyleForGroup(grp) {
        let color = '#a855f7';
        let shape = 'hexagon';
        let size = 27;
        let value = 22;
        if (grp === 'entreprise') {
            color = '#3b82f6';
            shape = 'dot';
            size = 36;
            value = 48;
        } else if (grp === 'agency') {
            color = '#f59e0b';
            shape = 'diamond';
            size = 30;
            value = 32;
        } else if (grp === 'saas_cms') {
            color = '#d946ef';
            shape = 'hexagon';
            size = 28;
            value = 26;
        } else if (grp === 'hosting') {
            color = '#06b6d4';
            shape = 'hexagon';
            size = 27;
            value = 24;
        } else if (grp === 'software') {
            color = '#6366f1';
            shape = 'hexagon';
            size = 27;
            value = 24;
        } else if (grp === 'ecommerce') {
            color = '#ea580c';
            shape = 'hexagon';
            size = 28;
            value = 26;
        } else if (grp === 'company') {
            color = '#64748b';
            shape = 'dot';
            size = 24;
            value = 20;
        } else if (grp === 'public') {
            color = '#94a3b8';
            shape = 'triangle';
            size = 26;
            value = 22;
        } else if (grp === 'nonprofit') {
            color = '#22c55e';
            shape = 'star';
            size = 26;
            value = 22;
        } else if (grp === 'education') {
            color = '#0d9488';
            shape = 'hexagon';
            size = 27;
            value = 23;
        } else if (grp === 'media') {
            color = '#e11d48';
            shape = 'hexagon';
            size = 27;
            value = 23;
        } else if (grp === 'finance') {
            color = '#eab308';
            shape = 'hexagon';
            size = 27;
            value = 23;
        } else if (grp === 'health') {
            color = '#f43f5e';
            shape = 'hexagon';
            size = 27;
            value = 23;
        } else if (grp === 'realestate') {
            color = '#b45309';
            shape = 'hexagon';
            size = 27;
            value = 23;
        } else if (grp === 'tourism') {
            color = '#14b8a6';
            shape = 'hexagon';
            size = 27;
            value = 23;
        } else if (grp === 'legal') {
            color = '#7c3aed';
            shape = 'hexagon';
            size = 27;
            value = 23;
        } else if (grp === 'person') {
            color = '#ec4899';
            shape = 'triangle';
            size = 25;
            value = 20;
        }
        return { color: color, shape: shape, size: size, value: value };
    }

    function displayLabel(n, state) {
        const full = (n.label || n.id || '').toString();
        const grp = n.group || 'external';
        const isCompact = state.compactLabels;
        const alwaysLabeled =
            grp === 'entreprise' ||
            grp === 'agency' ||
            grp === 'saas_cms' ||
            grp === 'hosting' ||
            grp === 'external' ||
            grp === 'company';
        if (isCompact && !alwaysLabeled) return '';
        return full.length > 42 ? full.slice(0, 40) + '…' : full;
    }

    function shortenUrlForTooltip(raw, maxLen) {
        var ml = maxLen != null ? maxLen : 56;
        var s = (raw || '').trim();
        if (!s) return '';
        var u = s.indexOf('http') === 0 ? s : 'https://' + s;
        try {
            var p = new URL(u);
            var host = p.hostname.replace(/^www\./, '');
            var tail = (p.pathname || '') + (p.search || '');
            if (tail === '/' || !tail) return host.length > ml ? host.slice(0, ml - 1) + '…' : host;
            var compact = host + tail;
            if (compact.length <= ml) return compact;
            return compact.slice(0, ml - 1) + '…';
        } catch (e) {
            return s.length > ml ? s.slice(0, ml - 1) + '…' : s;
        }
    }

    function tooltipGlyph(name) {
        return (
            '<span class="agences-vis-tooltip__ic material-symbols-rounded" aria-hidden="true">' +
            name +
            '</span>'
        );
    }

    function tooltipMetaRow(label, valueHtml) {
        return (
            '<div class="agences-vis-tooltip__kv">' +
            '<span class="agences-vis-tooltip__k">' +
            escapeHtml(label) +
            '</span>' +
            '<span class="agences-vis-tooltip__v">' +
            valueHtml +
            '</span></div>'
        );
    }

    function tooltipStatRow(glyph, label, valueHtml) {
        return (
            '<div class="agences-vis-tooltip__stat">' +
            tooltipGlyph(glyph) +
            '<div class="agences-vis-tooltip__stat-body">' +
            '<span class="agences-vis-tooltip__k">' +
            escapeHtml(label) +
            '</span>' +
            '<span class="agences-vis-tooltip__v">' +
            valueHtml +
            '</span></div></div>'
        );
    }

    function buildTooltipHtml(n) {
        const grp = n.group || 'external';
        const st0 = visStyleForGroup(grp);
        let accent = st0.color || '#a855f7';
        if (grp === 'entreprise' && getFilterState().colorByGeo && n.geo_key) {
            accent = geoPaletteColor(n.geo_key);
        }
        const eyebrow = escapeHtml(groupLabelFr(grp));
        let inner = '';

        if (grp === 'entreprise') {
            const title = escapeHtml((n.label || n.id || '').toString());
            const web = (n.title || '').trim();
            const thumb = (n.thumb_url || n.thumbnail_url || '').trim();
            let hero =
                '<div class="agences-vis-tooltip__row agences-vis-tooltip__row--hero">';
            if (thumb && /^https?:\/\//i.test(thumb)) {
                hero +=
                    '<img class="agences-vis-tooltip__fav" src="' +
                    escapeHtml(thumb) +
                    '" alt="" width="40" height="40" loading="lazy" decoding="async" referrerpolicy="no-referrer" />';
            }
            hero += '<div class="agences-vis-tooltip__hero-text">';
            hero += '<div class="agences-vis-tooltip__title agences-vis-tooltip__title--ent">' + title + '</div>';
            if (web) {
                const href = web.indexOf('http') === 0 ? web : 'https://' + web;
                const short = escapeHtml(shortenUrlForTooltip(web, 58));
                hero +=
                    '<a class="agences-vis-tooltip__link" href="' +
                    escapeHtml(href) +
                    '" target="_blank" rel="noopener noreferrer">' +
                    tooltipGlyph('open_in_new') +
                    short +
                    '</a>';
            }
            hero += '</div></div>';
            inner += hero;
            if (n.entreprise_id != null) {
                inner += tooltipStatRow('badge', 'ID fiche', escapeHtml('#' + String(n.entreprise_id)));
            }
            if (n.geo_label) {
                inner += tooltipStatRow('map', 'Localisation', escapeHtml(String(n.geo_label)));
            }
            const sh = n.shared_external_domains_count;
            if (sh != null && sh > 0) {
                inner += tooltipStatRow('share', 'Domaines communs (≥2 fiches)', escapeHtml(String(sh)));
                const doms = n.shared_external_domains || [];
                if (doms.length) {
                    inner += '<ul class="agences-vis-tooltip__list">';
                    doms.slice(0, 8).forEach(function (d) {
                        inner += '<li>' + escapeHtml(d) + '</li>';
                    });
                    inner += '</ul>';
                }
            }
        } else {
            const thumb = (n.thumb_url || n.thumbnail_url || '').trim();
            const dom = (n.domain || '').trim();
            const lab = (n.label || '').trim();
            const hasMedia = thumb && /^https?:\/\//i.test(thumb) && dom;

            if (hasMedia) {
                inner += '<div class="agences-vis-tooltip__media">';
                inner +=
                    '<img class="agences-vis-tooltip__fav agences-vis-tooltip__fav--domain" src="' +
                    escapeHtml(thumb) +
                    '" alt="" width="44" height="44" loading="lazy" decoding="async" referrerpolicy="no-referrer" />';
                inner += '<div class="agences-vis-tooltip__media-text">';
                inner += '<div class="agences-vis-tooltip__domain">' + escapeHtml(dom) + '</div>';
                if (lab && lab !== dom) {
                    inner += '<div class="agences-vis-tooltip__subtitle">' + escapeHtml(lab) + '</div>';
                }
                inner += '</div></div>';
            } else {
                if (dom) {
                    inner += '<div class="agences-vis-tooltip__domain">' + escapeHtml(dom) + '</div>';
                }
                if (lab && lab !== dom) {
                    inner += '<div class="agences-vis-tooltip__subtitle">' + escapeHtml(lab) + '</div>';
                }
                if (!dom && !lab) {
                    inner += '<div class="agences-vis-tooltip__title">' + escapeHtml((n.id || '').toString()) + '</div>';
                }
            }
            if (n.linked_enterprise_count != null) {
                inner += tooltipStatRow(
                    'account_tree',
                    'Entreprises liées',
                    escapeHtml(String(n.linked_enterprise_count))
                );
            }
            if (n.is_shared_external_hub) {
                inner +=
                    '<p class="agences-vis-tooltip__hub-note">' +
                    tooltipGlyph('hub') +
                    '<span>Hub partagé — plusieurs fiches sur ce domaine</span></p>';
            }
            if (n.categories && n.categories.length) {
                inner +=
                    '<div class="agences-vis-tooltip__block">' +
                    '<div class="agences-vis-tooltip__label-row">' +
                    tooltipGlyph('style') +
                    '<span>Schémas &amp; catégories</span></div>' +
                    '<div class="agences-vis-tooltip__chips">';
                n.categories.slice(0, 14).forEach(function (c) {
                    inner += '<span class="agences-vis-tooltip__chip agences-vis-tooltip__chip--schema">' + escapeHtml(c) + '</span>';
                });
                inner += '</div></div>';
            }
            if (n.jsonld_types && n.jsonld_types.length) {
                inner +=
                    '<div class="agences-vis-tooltip__block agences-vis-tooltip__block--jsonld">' +
                    '<div class="agences-vis-tooltip__label-row">' +
                    tooltipGlyph('data_object') +
                    '<span>Types JSON-LD</span></div>' +
                    '<div class="agences-vis-tooltip__chips agences-vis-tooltip__chips--dense">';
                n.jsonld_types.slice(0, 12).forEach(function (c) {
                    inner +=
                        '<span class="agences-vis-tooltip__chip agences-vis-tooltip__chip--jsonld">' + escapeHtml(c) + '</span>';
                });
                inner += '</div></div>';
            }
        }

        return (
            '<div class="agences-vis-tooltip" data-group="' +
            escapeHtml(grp) +
            '">' +
            '<span class="agences-vis-tooltip__accent" style="background:' +
            accent +
            '"></span>' +
            '<div class="agences-vis-tooltip__inner">' +
            '<div class="agences-vis-tooltip__eyebrow">' +
            tooltipGlyph('layers') +
            '<span>' +
            eyebrow +
            '</span></div>' +
            inner +
            '</div></div>'
        );
    }

    function buildEdgeTooltipHtml(e) {
        const k = edgeKind(e);
        const map = {
            credit: {
                ic: 'workspace_premium',
                t: 'Lien « crédit »',
                d: 'Le site met en avant cette ressource (crédit / réalisation).',
            },
            fiche: {
                ic: 'badge',
                t: 'Correspondance fiche',
                d: 'Ce domaine est associé à une fiche entreprise en base.',
            },
            ref: {
                ic: 'construction',
                t: 'Référence site',
                d: 'Exemple de site réalisé pour un client.',
            },
            lien: {
                ic: 'north_east',
                t: 'Lien sortant',
                d: 'Lien détecté depuis le site analysé.',
            },
        };
        const m = map[k] || map.lien;
        return (
            '<div class="agences-vis-tooltip agences-vis-tooltip--edge">' +
            '<span class="agences-vis-tooltip__accent agences-vis-tooltip__accent--edge" aria-hidden="true"></span>' +
            '<div class="agences-vis-tooltip__inner agences-vis-tooltip__inner--edge">' +
            '<div class="agences-vis-tooltip__edge-head">' +
            tooltipGlyph(m.ic) +
            '<div class="agences-vis-tooltip__edge-text">' +
            '<div class="agences-vis-tooltip__edge-title">' +
            escapeHtml(m.t) +
            '</div>' +
            '<p class="agences-vis-tooltip__edge-desc">' +
            escapeHtml(m.d) +
            '</p>' +
            '</div></div></div></div>'
        );
    }

    /**
     * vis-network n’interprète plus les chaînes HTML dans `title` (XSS) — il faut passer un nœud DOM.
     * @see https://visjs.github.io/vis-network/examples/network/other/html-in-titles.html
     */
    function graphTooltipElementFromHtml(htmlStr) {
        var raw = (htmlStr || '').trim();
        if (!raw) {
            var empty = document.createElement('div');
            empty.className = 'agences-vis-tooltip agences-vis-tooltip--empty';
            empty.setAttribute('aria-hidden', 'true');
            return empty;
        }
        var tpl = document.createElement('template');
        tpl.innerHTML = raw;
        var root = tpl.content.firstElementChild;
        if (root) {
            return root;
        }
        var fb = document.createElement('div');
        fb.className = 'agences-vis-tooltip agences-vis-tooltip--fallback';
        fb.textContent = raw.replace(/<[^>]*>/g, '');
        return fb;
    }

    function graphNodeTooltipEl(n) {
        return graphTooltipElementFromHtml(buildTooltipHtml(n));
    }

    function graphEdgeTooltipEl(e) {
        return graphTooltipElementFromHtml(buildEdgeTooltipHtml(e));
    }

    function nodeVisualStyle(n) {
        const grp = n.group || 'external';
        const st0 = visStyleForGroup(grp);
        let nodeColor = st0.color;
        if (grp === 'entreprise' && getFilterState().colorByGeo && n.geo_key) {
            nodeColor = geoPaletteColor(n.geo_key);
        }
        const st = {
            color: nodeColor,
            shape: st0.shape,
            size: st0.size,
            value: st0.value,
        };
        if (grp !== 'entreprise' && n.is_shared_external_hub) {
            st.shape = 'star';
            st.size = (st.size || 20) + 5;
            st.value = (st.value || 14) + 8;
        }
        const si = visNodeShapeAndImage(n, st);
        return { st, si };
    }

    function buildVisNodes(rawNodes, state, visibleIds) {
        return (rawNodes || []).map(function (n) {
            const vs = nodeVisualStyle(n);
            const st = vs.st;
            const si = vs.si;
            const grp = n.group || 'external';
            const o = {
                id: n.id,
                label: displayLabel(n, state),
                title: graphNodeTooltipEl(n),
                color: {
                    background: st.color,
                    border: visNodeOutline(),
                    highlight: {
                        background: st.color,
                        border: isLightTheme() ? '#0f172a' : '#f8fafc',
                    },
                },
                font: visNodeFontForGroup(grp),
                shape: si.shape,
                size: si.size,
                value: si.value,
                borderWidth: grp === 'entreprise' ? 4 : 2,
                hidden: !visibleIds.has(n.id),
            };
            applyNodeImageFields(o, si, false);
            if (typeof n.x === 'number' && typeof n.y === 'number') {
                o.x = n.x;
                o.y = n.y;
            }
            return o;
        });
    }

    function stableHash32(str) {
        var h = 2166136261;
        var s = String(str || '');
        for (var i = 0; i < s.length; i++) {
            h ^= s.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return (h >>> 0).toString(16);
    }

    function edgeStableId(e) {
        var raw =
            String(e.from || '') +
            '|' +
            String(e.to || '') +
            '|' +
            String(e.label || '') +
            '|' +
            String(e.arrows || 'to') +
            '|' +
            String(!!e.dashes) +
            '|' +
            String((e.color && e.color.color) || '');
        return 'eg:' + stableHash32(raw);
    }

    function buildVisEdges(rawEdges, visibleIds, state) {
        return (rawEdges || []).map(function (e) {
            const show = edgeVisible(e, visibleIds, state);
            const k = edgeKind(e);
            const w = k === 'credit' ? 2.4 : k === 'fiche' ? 2.0 : k === 'ref' ? 1.85 : 1.9;
            return {
                id: edgeStableId(e),
                from: e.from,
                to: e.to,
                label: state.compactLabels ? '' : e.label || '',
                title: graphEdgeTooltipEl(e),
                arrows: e.arrows || 'to',
                dashes: !!e.dashes,
                width: w,
                color: e.color && e.color.color ? e.color : { color: '#94a3b8' },
                font: visEdgeFont(),
                hidden: !show,
                smooth: { type: 'continuous', roundness: 0.35 },
            };
        });
    }

    function buildGraphQueryParams() {
        const p = new URLSearchParams();
        if (scopeSearchEl && scopeSearchEl.value.trim()) {
            p.set('search', scopeSearchEl.value.trim());
        }
        if (scopeDomainEl && scopeDomainEl.value.trim()) {
            p.set('domain', scopeDomainEl.value.trim());
        }
        if (scopeOnlyCreditEl && scopeOnlyCreditEl.checked) {
            p.set('only_credit', '1');
        }
        if (scopeMaxRowsEl && scopeMaxRowsEl.value.trim()) {
            const n = parseInt(scopeMaxRowsEl.value, 10);
            if (!isNaN(n) && n > 0) {
                p.set('max_link_rows', String(n));
            }
        }
        if (scopeMaxEntsEl && scopeMaxEntsEl.value.trim()) {
            const n = parseInt(scopeMaxEntsEl.value, 10);
            if (!isNaN(n) && n > 0) {
                p.set('max_enterprises', String(n));
            }
        }
        if (scopeIdsEl && scopeIdsEl.value.trim()) {
            const compact = scopeIdsEl.value.replace(/\s+/g, '');
            if (compact) {
                p.set('entreprise_ids', compact);
            }
        }
        return p;
    }

    function updateScopeHint(scope) {
        if (!scopeHintEl) return;
        if (scope && (scope.hit_link_row_cap || scope.hit_enterprise_cap)) {
            scopeHintEl.style.display = 'block';
            const parts = [];
            if (scope.hit_link_row_cap) {
                parts.push('plafond de lignes de liens');
            }
            if (scope.hit_enterprise_cap) {
                parts.push("plafond d'entreprises dans l'échantillon");
            }
            scopeHintEl.textContent =
                'Aperçu tronqué (' +
                parts.join(' et ') +
                '). Affinez la recherche, limitez les fiches par ID ou augmentez les plafonds.';
        } else {
            scopeHintEl.style.display = 'none';
            scopeHintEl.textContent = '';
        }
    }

    function hideScopeAutocomplete() {
        if (!scopeAutocompleteEl) return;
        scopeAutocompleteEl.classList.remove('is-open');
        scopeAutocompleteEl.innerHTML = '';
        scopeAutocompleteEl.setAttribute('hidden', '');
        scopeAutocompleteActiveIdx = -1;
        if (scopePickQEl) {
            scopePickQEl.setAttribute('aria-expanded', 'false');
            scopePickQEl.removeAttribute('aria-activedescendant');
        }
    }

    function autocompleteOptionButtons() {
        if (!scopeAutocompleteEl) return [];
        return scopeAutocompleteEl.querySelectorAll('.agences-scope-autocomplete__item');
    }

    function setAutocompleteActive(idx) {
        const buttons = autocompleteOptionButtons();
        if (!buttons.length) return;
        const n = buttons.length;
        let i = idx;
        if (i < 0) i = n - 1;
        if (i >= n) i = 0;
        scopeAutocompleteActiveIdx = i;
        buttons.forEach(function (b, j) {
            b.classList.toggle('is-active', j === scopeAutocompleteActiveIdx);
            b.setAttribute('aria-selected', j === scopeAutocompleteActiveIdx ? 'true' : 'false');
        });
        const cur = buttons[scopeAutocompleteActiveIdx];
        if (cur && scopePickQEl) {
            scopePickQEl.setAttribute('aria-activedescendant', cur.id);
            try {
                cur.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } catch (e) {
                cur.scrollIntoView(false);
            }
        }
    }

    function openScopeAutocompleteFromItems(items) {
        if (!scopeAutocompleteEl || !items || !items.length) {
            hideScopeAutocomplete();
            return;
        }
        scopeAutocompleteEl.classList.remove('is-open');
        scopeAutocompleteEl.innerHTML = items
            .map(function (it, i) {
                const nom = escapeHtml(it.nom || '#' + it.id);
                const web = escapeHtml((it.website || '').slice(0, 88) || 'ID ' + it.id);
                return (
                    '<button type="button" role="option" id="agences-autocomplete-opt-' +
                    i +
                    '" class="agences-scope-autocomplete__item" data-eid="' +
                    String(it.id) +
                    '" aria-selected="false"><strong>' +
                    nom +
                    '</strong><span class="agences-scope-autocomplete__sub">' +
                    web +
                    '</span></button>'
                );
            })
            .join('');
        scopeAutocompleteEl.removeAttribute('hidden');
        scopeAutocompleteActiveIdx = -1;
        if (scopePickQEl) scopePickQEl.setAttribute('aria-expanded', 'true');
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                if (scopeAutocompleteEl) scopeAutocompleteEl.classList.add('is-open');
            });
        });
    }

    function appendEntrepriseIdToScope(id) {
        if (!scopeIdsEl) return;
        const n = parseInt(String(id), 10);
        if (isNaN(n)) return;
        const raw = scopeIdsEl.value.trim();
        const parts = raw
            ? raw
                  .split(',')
                  .map(function (x) {
                      return x.trim();
                  })
                  .filter(Boolean)
            : [];
        const key = String(n);
        if (parts.indexOf(key) === -1) {
            parts.push(key);
        }
        scopeIdsEl.value = parts.join(', ');
        hideScopeAutocomplete();
        if (scopePickQEl) {
            scopePickQEl.value = '';
        }
    }

    function scheduleScopeAutocomplete() {
        if (scopeAutocompleteTimer) {
            clearTimeout(scopeAutocompleteTimer);
        }
        scopeAutocompleteTimer = setTimeout(runScopeAutocomplete, 280);
    }

    function runScopeAutocomplete() {
        scopeAutocompleteTimer = null;
        if (!scopePickQEl || !scopeAutocompleteEl) return;
        const q = scopePickQEl.value.trim();
        if (q.length < 2) {
            hideScopeAutocomplete();
            return;
        }
        fetch(
            '/api/entreprises/graph/entreprise-autocomplete?q=' +
                encodeURIComponent(q) +
                '&limit=12',
            { credentials: 'same-origin' }
        )
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data.success || !data.items || !data.items.length) {
                    hideScopeAutocomplete();
                    return;
                }
                openScopeAutocompleteFromItems(data.items);
            })
            .catch(function () {
                hideScopeAutocomplete();
            });
    }

    function renderStats(st, scope) {
        if (!statsWrap) return;
        const chips = [];
        if (st.agencies != null) {
            chips.push(
                '<span class="agences-chip"><span class="material-symbols-rounded">hub</span>' +
                    st.agencies +
                    ' agence(s)</span>'
            );
        }
        if (st.enterprises != null) {
            chips.push(
                '<span class="agences-chip"><span class="material-symbols-rounded">corporate_fare</span>' +
                    st.enterprises +
                    ' entreprise(s)</span>'
            );
        }
        if (st.external_domains != null) {
            chips.push(
                '<span class="agences-chip"><span class="material-symbols-rounded">language</span>' +
                    st.external_domains +
                    ' domaine(s)</span>'
            );
        }
        if (st.shared_external_hubs != null && st.shared_external_hubs > 0) {
            chips.push(
                '<span class="agences-chip agences-chip--accent" title="Domaines reliés à au moins deux fiches dans ce graphe"><span class="material-symbols-rounded">share</span>' +
                    st.shared_external_hubs +
                    ' hub(s) communs</span>'
            );
        }
        if (st.nodes != null && st.edges != null) {
            chips.push(
                '<span class="agences-chip agences-chip--accent"><span class="material-symbols-rounded">scatter_plot</span>' +
                    st.nodes +
                    ' nœuds · ' +
                    st.edges +
                    ' liens</span>'
            );
        }
        if (
            scope &&
            scope.total_link_rows_in_db != null &&
            st.external_link_rows != null &&
            scope.total_link_rows_in_db > st.external_link_rows
        ) {
            chips.push(
                '<span class="agences-chip" title="Lignes dans entreprise_external_links (base) vs échantillon affiché"><span class="material-symbols-rounded">database</span>' +
                    st.external_link_rows +
                    ' / ' +
                    scope.total_link_rows_in_db +
                    ' liens (base)</span>'
            );
        }
        statsWrap.innerHTML = chips.join('');
    }

    /**
     * Options physique seules : à utiliser au toggle Physique.
     * Ne pas repasser nodes/edges/interaction via setOptions (vis-network peut réinitialiser la vue).
     */
    function physicsOptionsOnly(physicsOn) {
        var fa2 = getForceAtlas2Opts();
        var stab = { iterations: physicsOn ? 520 : 80 };
        if (physicsOn) stab.fit = false;
        else stab.fit = true;
        return {
            physics: {
                enabled: !!physicsOn,
                stabilization: stab,
                forceAtlas2Based: fa2,
                solver: 'forceAtlas2Based',
            },
        };
    }

    function networkOptions(physicsOn) {
        var fa2 = getForceAtlas2Opts();
        // Sans physique : laisser le comportement par défaut (stabilization.fit true) pour un cadrage correct.
        // Avec physique : éviter le recadrage auto à la fin de la stabilisation (sinon la vue "saute").
        var stab = { iterations: physicsOn ? 520 : 80 };
        if (physicsOn) stab.fit = false;
        return {
            physics: {
                enabled: !!physicsOn,
                stabilization: stab,
                forceAtlas2Based: fa2,
                solver: 'forceAtlas2Based',
            },
            interaction: {
                hover: true,
                tooltipDelay: 220,
                multiselect: false,
                navigationButtons: false,
            },
            edges: {
                smooth: { type: 'continuous', roundness: 0.35 },
                width: 1.85,
                selectionWidth: 3,
            },
            nodes: visNodesGlobalOptions(),
        };
    }

    function computeInitialLayoutPositions(rawNodes, rawEdges) {
        var pos = {};
        var nodes = rawNodes || [];
        var edges = rawEdges || [];

        function isEntrepriseId(id) {
            return String(id || '').slice(0, 2) === 'e:';
        }

        var entrepriseIds = nodes
            .map(function (n) { return n && n.id; })
            .filter(function (id) { return isEntrepriseId(id); });

        // Placer les entreprises en cercle (layout stable, lisible).
        var nE = entrepriseIds.length;
        var radius = Math.max(520, Math.min(1150, 360 + nE * 16));
        for (var i = 0; i < nE; i++) {
            var idE = entrepriseIds[i];
            var ang = (i / Math.max(1, nE)) * Math.PI * 2;
            pos[idE] = { x: Math.cos(ang) * radius, y: Math.sin(ang) * radius };
        }

        // Adjacence (pour placer les domaines autour de leur(s) entreprise(s)).
        var neigh = {};
        edges.forEach(function (e) {
            if (!e || !e.from || !e.to) return;
            if (!neigh[e.from]) neigh[e.from] = [];
            if (!neigh[e.to]) neigh[e.to] = [];
            neigh[e.from].push(e.to);
            neigh[e.to].push(e.from);
        });

        // Placer les autres nœuds autour de leurs voisins déjà placés (effet "molécule").
        nodes.forEach(function (n) {
            if (!n || !n.id) return;
            if (pos[n.id]) return;
            if (typeof n.x === 'number' && typeof n.y === 'number') {
                pos[n.id] = { x: n.x, y: n.y };
                return;
            }
            var ns = neigh[n.id] || [];
            var seed = null;
            for (var j = 0; j < ns.length; j++) {
                if (pos[ns[j]]) {
                    seed = pos[ns[j]];
                    break;
                }
            }
            if (!seed) return;
            var off = seededOffsetForNewNode(n.id);
            var dist = 280 + (Math.abs(Math.round((off.dist || 200) * 0.72)) % 240);
            pos[n.id] = { x: seed.x + off.cos * dist, y: seed.y + off.sin * dist };
        });

        // Fallback pour isolés : spirale.
        var k = 0;
        nodes.forEach(function (n) {
            if (!n || !n.id) return;
            if (pos[n.id]) return;
            var ang = k * 0.85;
            var dist = 260 + k * 34;
            pos[n.id] = { x: Math.cos(ang) * dist, y: Math.sin(ang) * dist };
            k++;
        });
        return pos;
    }

    function neighborsOf(nodeId, rawEdges) {
        const out = [];
        (rawEdges || []).forEach(function (e) {
            if (e.from === nodeId) out.push({ other: e.to, edge: e, dir: '→' });
            if (e.to === nodeId) out.push({ other: e.from, edge: e, dir: '←' });
        });
        return out;
    }

    function escapeHtml(s) {
        if (s == null) return '';
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function hideNodeCard() {
        if (!nodeCard) return;
        nodeCard.hidden = true;
        nodeCard.setAttribute('aria-hidden', 'true');
        selectedNodeId = null;
        if (network) network.unselectAll();
    }

    function showNodeCard() {
        if (!nodeCard) return;
        nodeCard.hidden = false;
        nodeCard.setAttribute('aria-hidden', 'false');
    }

    function groupLabelFr(grp) {
        const map = {
            entreprise: 'Entreprise (fiche)',
            agency: 'Agence web',
            saas_cms: 'Plateforme / CMS',
            hosting: 'Hébergement / infra',
            software: 'Logiciel / SaaS',
            ecommerce: 'E-commerce',
            external: 'Domaine externe',
            company: 'Entreprise (site tiers)',
            public: 'Public / institution',
            nonprofit: 'Association',
            education: 'Éducation / recherche',
            media: 'Média / édition',
            finance: 'Finance / assurance',
            health: 'Santé',
            realestate: 'Immo / BTP',
            tourism: 'Tourisme / restauration',
            legal: 'Juridique',
            person: 'Personne / indépendant',
        };
        return map[grp] || map.external;
    }

    function fillNodeCard(nodeId) {
        if (!nodeCardBody || !nodeCardEyebrow) return;
        const raw = apiNodeById.get(nodeId);
        if (!raw) {
            nodeCardEyebrow.textContent = '—';
            nodeCardBody.innerHTML = '<p class="agences-node-card__empty">Données indisponibles.</p>';
            return;
        }
        const grp = raw.group || 'external';
        nodeCardEyebrow.textContent = groupLabelFr(grp);

        function cardSection(title, inner, iconName) {
            const ic = iconName
                ? '<span class="material-symbols-rounded agences-node-card__section-ic" aria-hidden="true">' +
                  iconName +
                  '</span>'
                : '';
            return (
                '<div class="agences-node-card__section">' +
                '<div class="agences-node-card__section-head">' +
                ic +
                '<div class="agences-node-card__section-title">' +
                escapeHtml(title) +
                '</div></div>' +
                inner +
                '</div>'
            );
        }
        function cardChips(items, max, variant) {
            const slice = (items || []).slice(0, max || 25);
            if (!slice.length) return '';
            const chipCls =
                variant === 'jsonld'
                    ? 'agences-node-card__chip agences-node-card__chip--jsonld'
                    : 'agences-node-card__chip';
            return (
                '<div class="agences-node-card__chips">' +
                slice
                    .map(function (c) {
                        return '<span class="' + chipCls + '">' + escapeHtml(String(c)) + '</span>';
                    })
                    .join('') +
                '</div>'
            );
        }

        let html = '';

        if (grp === 'entreprise') {
            html += '<h2 class="agences-node-card__title">' + escapeHtml(raw.label || raw.id) + '</h2>';
            const web = (raw.title || '').trim();
            if (web) {
                const href = web.indexOf('http') === 0 ? web : 'https://' + web;
                html +=
                    '<p class="agences-node-card__lead"><a href="' +
                    escapeHtml(href) +
                    '" target="_blank" rel="noopener" class="agences-node-card__link">' +
                    escapeHtml(web) +
                    ' <span class="material-symbols-rounded agences-node-card__link-ic" aria-hidden="true">open_in_new</span></a></p>';
            }
            const shm = raw.shared_external_domains_count;
            if (shm != null && shm > 0) {
                html +=
                    '<div class="agences-node-card__banner agences-node-card__banner--accent"><span class="material-symbols-rounded" aria-hidden="true">hub</span> <strong>' +
                    shm +
                    '</strong> domaine(s) en commun avec d’autres fiches (dans ce graphe)</div>';
                html += cardSection('Domaines (liens externes communs)', cardChips(raw.shared_external_domains, 24), 'share');
            } else {
                html +=
                    '<p class="agences-node-card__muted">Aucun domaine externe partagé avec une autre fiche dans ce graphe.</p>';
            }
            if (raw.geo_label) {
                html += cardSection(
                    'Localisation',
                    '<p class="agences-node-card__kv">' + escapeHtml(String(raw.geo_label)) + '</p>',
                    'map'
                );
            }
            if (raw.entreprise_id != null) {
                html += cardSection(
                    'Identifiant',
                    '<p class="agences-node-card__kv">ID fiche <code>' + raw.entreprise_id + '</code></p>',
                    'fingerprint'
                );
                html +=
                    '<div class="agences-node-card__actions"><a class="md-btn md-btn--filled" href="' +
                    entrepriseUrl(raw.entreprise_id) +
                    '"><span class="material-symbols-rounded" aria-hidden="true">open_in_new</span> Ouvrir la fiche</a></div>';
            }
        } else {
            const turl = (raw.thumb_url || raw.thumbnail_url || '').trim();
            html += '<div class="agences-node-card__hero">';
            if (turl && /^https?:\/\//i.test(turl)) {
                html +=
                    '<img class="agences-node-card__thumb" src="' +
                    escapeHtml(turl) +
                    '" alt="" referrerpolicy="no-referrer" loading="lazy" decoding="async" />';
            }
            html +=
                '<div class="agences-node-card__hero-text">' +
                '<h2 class="agences-node-card__title">' +
                escapeHtml(raw.label || raw.domain || raw.id) +
                '</h2>';
            if (raw.domain) {
                html += '<p class="agences-node-card__domain">' + escapeHtml(raw.domain) + '</p>';
            }
            html += '</div></div>';

            if (raw.is_shared_external_hub) {
                html +=
                    '<div class="agences-node-card__banner agences-node-card__banner--accent"><span class="material-symbols-rounded" aria-hidden="true">share</span> Hub partagé : lié à <strong>' +
                    (raw.linked_enterprise_count != null ? raw.linked_enterprise_count : 'plusieurs') +
                    '</strong> fiche(s)</div>';
            }

            const cnt = raw.linked_enterprise_count;
            if (cnt != null) {
                html += cardSection(
                    'Dans ce graphe',
                    '<p class="agences-node-card__kv">' + cnt + ' entreprise(s) reliée(s)</p>',
                    'analytics'
                );
            }

            if (raw.sample_external_url) {
                const u = raw.sample_external_url;
                const href = u.indexOf('http') === 0 ? u : 'https://' + u;
                html +=
                    cardSection(
                        'Exemple d’URL sortante',
                        '<p><a class="agences-node-card__link" href="' +
                            escapeHtml(href) +
                            '" target="_blank" rel="noopener">' +
                            escapeHtml(u.length > 140 ? u.slice(0, 140) + '…' : u) +
                            '</a></p>',
                        'outbound'
                    );
            }
            if (raw.sample_anchor_text) {
                html +=
                    cardSection(
                        'Texte d’ancrage (extrait)',
                        '<p class="agences-node-card__quote">' + escapeHtml(raw.sample_anchor_text) + '</p>',
                        'format_quote'
                    );
            }
            if (raw.resolved_url) {
                const fu = raw.resolved_url;
                const href = fu.indexOf('http') === 0 ? fu : 'https://' + fu;
                html +=
                    cardSection(
                        'URL finale (redirections)',
                        '<p><a class="agences-node-card__link" href="' +
                            escapeHtml(href) +
                            '" target="_blank" rel="noopener">' +
                            escapeHtml(fu.length > 140 ? fu.slice(0, 140) + '…' : fu) +
                            '</a></p>',
                        'conversion_path'
                    );
            }
            if (raw.site_description) {
                html +=
                    cardSection(
                        'Description (extrait)',
                        '<p class="agences-node-card__prose">' + escapeHtml(raw.site_description) + '</p>',
                        'article'
                    );
            }
            if (raw.categories && raw.categories.length) {
                html += cardSection('Catégories détectées', cardChips(raw.categories, 20), 'label');
            }
            if (raw.jsonld_types && raw.jsonld_types.length) {
                html += cardSection('Types JSON-LD', cardChips(raw.jsonld_types, 15, 'jsonld'), 'data_object');
            }
            var actUrl = externalUrlFromNode(raw);
            if (actUrl) {
                html +=
                    '<div class="agences-node-card__actions">' +
                    '<button type="button" class="md-btn md-btn--filled" id="graph-external-analyze-btn" data-url="' +
                    escapeHtml(actUrl) +
                    '">' +
                    '<span class="material-symbols-rounded" aria-hidden="true">play_arrow</span> ' +
                    'Scraping + technique</button></div>' +
                    '<p id="graph-external-analysis-status" class="agences-node-card__muted" hidden></p>';
            }
        }

        const neigh = neighborsOf(nodeId, lastRaw ? lastRaw.edges : []);
        if (neigh.length) {
            const lines = neigh.slice(0, 50).map(function (x) {
                const other = apiNodeById.get(x.other);
                const name = other ? other.label || x.other : x.other;
                const lk = (x.edge && x.edge.label) || '';
                return (
                    '<li><span class="agences-node-card__neighbor-name">' +
                    escapeHtml(name) +
                    '</span> <span class="agences-node-card__neighbor-edge">' +
                    escapeHtml(lk) +
                    '</span></li>'
                );
            });
            html +=
                cardSection(
                    'Voisinage (' + neigh.length + ')',
                    '<ul class="agences-node-card__neighbors">' +
                        lines.join('') +
                        (neigh.length > 50 ? '<li class="agences-node-card__muted">…</li>' : '') +
                        '</ul>',
                    'account_tree'
                );
        }

        nodeCardBody.innerHTML = html || '<p class="agences-node-card__empty">Pas de détail.</p>';
    }

    function applyFilters() {
        if (!lastRaw || !nodesDS || !edgesDS) return;
        const state = getFilterState();
        const visibleIds = computeVisibleNodeIds(lastRaw.nodes, lastRaw.edges, state);
        var posMap = null;
        try {
            if (network && !physicsEnabled && typeof network.getPositions === 'function') {
                posMap = network.getPositions();
            }
        } catch (ePos) {
            posMap = null;
        }
        const nodeUpdates = [];
        lastRaw.nodes.forEach(function (n) {
            var vs = nodeVisualStyle(n);
            var st = vs.st;
            var si = vs.si;
            var grp = n.group || 'external';
            var upd = {
                id: n.id,
                hidden: !visibleIds.has(n.id),
                label: displayLabel(n, state),
                title: graphNodeTooltipEl(n),
                font: visNodeFontForGroup(grp),
                shape: si.shape,
                size: si.size,
                value: si.value,
                borderWidth: grp === 'entreprise' ? 4 : 2,
                color: {
                    background: st.color,
                    border: visNodeOutline(),
                    highlight: {
                        background: st.color,
                        border: isLightTheme() ? '#0f172a' : '#f8fafc',
                    },
                },
            };
            applyNodeImageFields(upd, si, true);
            if (posMap && posMap[n.id] && typeof posMap[n.id].x === 'number' && typeof posMap[n.id].y === 'number') {
                upd.x = posMap[n.id].x;
                upd.y = posMap[n.id].y;
            }
            nodeUpdates.push(upd);
        });
        nodesDS.update(nodeUpdates);
        const edgeUpdates = [];
        lastRaw.edges.forEach(function (e) {
            var k = edgeKind(e);
            var w = k === 'credit' ? 2.4 : k === 'fiche' ? 2.0 : k === 'ref' ? 1.85 : 1.9;
            edgeUpdates.push({
                id: edgeStableId(e),
                hidden: !edgeVisible(e, visibleIds, state),
                label: state.compactLabels ? '' : e.label || '',
                width: w,
                font: visEdgeFont(),
            });
        });
        edgesDS.update(edgeUpdates);
        if (selectedNodeId && !visibleIds.has(selectedNodeId)) hideNodeCard();
        scheduleDeptZonesRebuild(80);
    }

    function scheduleApplyFilters() {
        if (filterDebounce) clearTimeout(filterDebounce);
        filterDebounce = setTimeout(function () {
            filterDebounce = null;
            applyFilters();
        }, 120);
    }

    /** Variante "temps réel" : 1 application max par frame (évite l'effet "tout d'un coup" du debounce). */
    function scheduleApplyFiltersRaf() {
        if (filterRafScheduled) return;
        filterRafScheduled = true;
        var raf =
            window.requestAnimationFrame ||
            function (cb) {
                return window.setTimeout(cb, 16);
            };
        raf(function () {
            filterRafScheduled = false;
            applyFilters();
        });
    }

    function flushPendingMiniScrapeDomainEvents() {
        if (!pendingMiniScrapeDomainEvents.length) return;
        if (!lastRaw || !nodesDS || !edgesDS) return;
        var batch = pendingMiniScrapeDomainEvents.slice(0);
        pendingMiniScrapeDomainEvents = [];
        batch.forEach(function (it) {
            if (!it) return;
            try {
                upsertExternalLinkRealtime(it.dom, it.entrepriseId);
            } catch (e) {}
        });
    }

    function bindFilterListeners() {
        const ids = [
            'flt-nodes-ent',
            'flt-nodes-agency',
            'flt-nodes-other',
            'flt-edge-credit',
            'flt-edge-lien',
            'flt-edge-ref',
            'flt-edge-fiche',
            'flt-compact-labels',
            'flt-color-by-geo',
        ];
        ids.forEach(function (id) {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', scheduleApplyFilters);
        });
        const searchEl = document.getElementById('graph-entreprises-search');
        if (searchEl) {
            searchEl.addEventListener('input', scheduleApplyFilters);
        }
    }

    function render(data) {
        if (!graphEl) return;
        try {
            if (data && Array.isArray(data.nodes)) data.nodes.forEach(fixMojibakeInObj);
            if (data && Array.isArray(data.edges)) data.edges.forEach(fixMojibakeInObj);
        } catch (eFix) {}
        const st = data.stats || {};
        const scope = data.graph_scope || null;
        renderStats(st, scope);
        updateScopeHint(scope);

        if (!data.nodes || data.nodes.length === 0) {
            graphEl.style.display = 'none';
            if (emptyEl) emptyEl.style.display = 'flex';
            const flt = (scope && scope.filters) || {};
            const hasFilter = !!(
                flt.search ||
                flt.domain_contains ||
                flt.only_credit ||
                (flt.entreprise_ids && flt.entreprise_ids.length)
            );
            const noMatchScope =
                hasFilter ||
                (scope &&
                    scope.sql_fetched_rows === 0 &&
                    (scope.total_link_rows_in_db || 0) > 0);
            if (emptyEl) {
                if (noMatchScope) {
                    emptyEl.textContent =
                        'Aucun lien ne correspond à ce périmètre. Élargissez la recherche ou les plafonds.';
                } else {
                    emptyEl.textContent = emptyElDefaultText;
                }
            }
            if (graphResizeObserver) {
                try {
                    graphResizeObserver.disconnect();
                } catch (e) {}
                graphResizeObserver = null;
            }
            if (graphResizeHandler) {
                window.removeEventListener('resize', graphResizeHandler);
                graphResizeHandler = null;
            }
            if (network) {
                network.destroy();
                network = null;
            }
            nodesDS = null;
            edgesDS = null;
            lastRaw = null;
            apiNodeById = new Map();
            clearDeptZonesCache();
            hideNodeCard();
            return;
        }

        graphEl.style.display = 'block';
        if (emptyEl) emptyEl.style.display = 'none';

        lastRaw = { nodes: data.nodes || [], edges: data.edges || [] };
        thumbUrlDataUrl.clear();
        thumbUrlBad.clear();
        thumbProbeInflight.clear();
        thumbUrlToNodeIds = new Map();
        thumbProbeQueue = [];
        thumbUrlQueued.clear();
        thumbProbeRunning = 0;
        apiNodeById = new Map();
        lastRaw.nodes.forEach(function (n) {
            apiNodeById.set(n.id, n);
            var u = (n.thumb_url || n.thumbnail_url || '').trim();
            if (!u || !/^https?:\/\//i.test(u)) return;
            if (!thumbUrlToNodeIds.has(u)) thumbUrlToNodeIds.set(u, []);
            thumbUrlToNodeIds.get(u).push(n.id);
        });

        const state = getFilterState();
        const visibleIds = computeVisibleNodeIds(lastRaw.nodes, lastRaw.edges, state);
        var initPos = computeInitialLayoutPositions(lastRaw.nodes, lastRaw.edges);
        const vNodes = buildVisNodes(lastRaw.nodes, state, visibleIds);
        vNodes.forEach(function (vn) {
            if (!vn || !vn.id) return;
            if (typeof vn.x === 'number' && typeof vn.y === 'number') return;
            var p = initPos[vn.id];
            if (p) {
                vn.x = p.x;
                vn.y = p.y;
            }
        });
        const vEdges = buildVisEdges(lastRaw.edges, visibleIds, state);

        nodesDS = new vis.DataSet(vNodes);
        edgesDS = new vis.DataSet(vEdges);

        if (network) network.destroy();
        clearDeptZonesCache();
        if (graphResizeObserver) {
            try {
                graphResizeObserver.disconnect();
            } catch (e) {}
            graphResizeObserver = null;
        }
        if (graphResizeHandler) {
            window.removeEventListener('resize', graphResizeHandler);
            graphResizeHandler = null;
        }
        physicsEnabled = false;
        if (btnPhysics) {
            btnPhysics.classList.remove('md-btn--filled');
            btnPhysics.classList.add('md-btn--outlined');
        }

        // Pas de physique ni de recadrage automatique : layout initial calculé ci-dessus.
        network = new vis.Network(graphEl, { nodes: nodesDS, edges: edgesDS }, networkOptions(false));
        network.on('beforeDrawing', function (ctx) {
            drawDeptZones(ctx);
        });

        function syncGraphSize() {
            if (!network || !graphEl) return;
            // Dimensions du conteneur vis-network (pas toute la stack) : cohérent avec la zone hors dock.
            const w = graphEl.clientWidth;
            const h = graphEl.clientHeight;
            if (w < 48 || h < 48) return;
            try {
                network.setSize(w + 'px', h + 'px');
                network.redraw();
            } catch (e) {}
        }
        syncGraphSize();
        if (typeof requestAnimationFrame === 'function') {
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    syncGraphSize();
                    // Sans fit initial, vis-network peut laisser la caméra par défaut → nœuds en coin / tout petits.
                    try {
                        network.fit(graphFitOptions());
                    } catch (eFit0) {}
                });
            });
        } else {
            try {
                network.fit(graphFitOptions());
            } catch (eFit1) {}
        }
        if (typeof ResizeObserver !== 'undefined' && graphEl) {
            graphResizeObserver = new ResizeObserver(function () {
                syncGraphSize();
            });
            graphResizeObserver.observe(graphEl);
        }
        graphResizeHandler = function () {
            syncGraphSize();
        };
        window.addEventListener('resize', graphResizeHandler);

        // Pas de stabilisation/fit auto : seulement rebuild zones.
        network.on('stabilized', function () {
            scheduleDeptZonesRebuild(100);
        });

        // Si des events mini-scrape arrivent pendant un reload, on les applique dès que le graphe est prêt.
        flushPendingMiniScrapeDomainEvents();

        network.on('click', function (params) {
            if (params.nodes && params.nodes.length) {
                selectedNodeId = params.nodes[0];
                fillNodeCard(selectedNodeId);
                showNodeCard();
                network.selectNodes([selectedNodeId]);
            } else if (!params.edges || params.edges.length === 0) {
                hideNodeCard();
            }
        });

        network.on('doubleClick', function (params) {
            if (params.nodes && params.nodes.length) {
                var nid = params.nodes[0];
                try {
                    var clm = getClusteringMod();
                    if (clm && typeof clm.isCluster === 'function' && clm.isCluster(nid)) {
                        network.openCluster(nid);
                        return;
                    }
                } catch (e) {}
                network.focus(nid, {
                    scale: 1.35,
                    animation: {
                        duration: 480,
                        easingFunction: 'easeInOutQuad',
                    },
                });
            }
        });

        network.on('dragStart', function () {
            preDragView = viewCapture();
        });
        network.on('dragEnd', function () {
            if (preDragView) {
                var now = viewCapture();
                if (now && viewDist(preDragView, now) > 0.08) {
                    viewPast.push(preDragView);
                    if (viewPast.length > 20) viewPast.shift();
                    viewFuture = [];
                }
                preDragView = null;
            }
            scheduleDeptZonesRebuild(90);
        });
        network.on('zoom', function () {
            scheduleDeptZonesRebuild(120);
        });
        network.on('animationFinished', function () {
            scheduleDeptZonesRebuild(120);
        });
        scheduleDeptZonesRebuild(120);
    }

    function buildGraphApiUrl() {
        const qp = buildGraphQueryParams();
        const qs = qp.toString();
        return '/api/entreprises/graph' + (qs ? '?' + qs : '');
    }

    function hasAnyScopeInput() {
        return !!(
            (scopeSearchEl && scopeSearchEl.value.trim()) ||
            (scopeDomainEl && scopeDomainEl.value.trim()) ||
            (scopeIdsEl && scopeIdsEl.value.trim()) ||
            (scopeOnlyCreditEl && scopeOnlyCreditEl.checked) ||
            (scopeMaxRowsEl && scopeMaxRowsEl.value.trim()) ||
            (scopeMaxEntsEl && scopeMaxEntsEl.value.trim())
        );
    }

    function applyBootstrapScopeDefaults() {
        // On applique uniquement si l'utilisateur n'a encore rien saisi.
        if (hasAnyScopeInput()) return;
        if (scopeMaxRowsEl) scopeMaxRowsEl.value = String(BOOTSTRAP_MAX_LINK_ROWS);
        if (scopeMaxEntsEl) scopeMaxEntsEl.value = String(BOOTSTRAP_MAX_ENTERPRISES);
    }

    function refreshGraphIncremental() {
        if (!network || !nodesDS || !edgesDS) {
            loadGraph();
            return;
        }
        var url;
        try {
            url = buildGraphApiUrl();
        } catch (e0) {
            return;
        }
        fetch(url, { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data.success && data.error) throw new Error(data.error);
                const st = data.stats || {};
                const scope = data.graph_scope || null;
                renderStats(st, scope);
                updateScopeHint(scope);
                if (!data.nodes || data.nodes.length === 0) {
                    graphAnalysisDbg('refreshGraphIncremental: réponse vide, on garde le graphe courant');
                    return;
                }
                var posMap = {};
                try {
                    if (network && typeof network.getPositions === 'function') {
                        posMap = network.getPositions() || {};
                    }
                } catch (ePos) {
                    posMap = {};
                }
                lastRaw = { nodes: data.nodes || [], edges: data.edges || [] };
                apiNodeById = new Map();
                lastRaw.nodes.forEach(function (n) {
                    apiNodeById.set(n.id, n);
                });
                const state = getFilterState();
                const visibleIds = computeVisibleNodeIds(lastRaw.nodes, lastRaw.edges, state);
                const vNodes = buildVisNodes(lastRaw.nodes, state, visibleIds);
                vNodes.forEach(function (vn) {
                    var existing = posMap[vn.id];
                    if (existing && typeof existing.x === 'number' && typeof existing.y === 'number') {
                        vn.x = existing.x;
                        vn.y = existing.y;
                        return;
                    }
                    var lay = layoutSeedPositionForNewVisNode(vn.id, lastRaw.edges, posMap);
                    if (lay) {
                        vn.x = lay.x;
                        vn.y = lay.y;
                        posMap[vn.id] = { x: lay.x, y: lay.y };
                    }
                });
                const vEdges = buildVisEdges(lastRaw.edges, visibleIds, state);

                var newNodeIds = new Set(
                    vNodes.map(function (n) {
                        return n.id;
                    })
                );
                var curNodeIds = nodesDS.getIds();
                var nodeToRemove = curNodeIds.filter(function (id) {
                    return !newNodeIds.has(id);
                });
                if (nodeToRemove.length) nodesDS.remove(nodeToRemove);
                if (vNodes.length) nodesDS.update(vNodes);

                var newEdgeIds = new Set(
                    vEdges.map(function (e) {
                        return e.id;
                    })
                );
                var curEdgeIds = edgesDS.getIds();
                var edgeToRemove = curEdgeIds.filter(function (id) {
                    return !newEdgeIds.has(id);
                });
                if (edgeToRemove.length) edgesDS.remove(edgeToRemove);
                if (vEdges.length) edgesDS.update(vEdges);
                applyPendingDomainPromotions();
                if (selectedNodeId && !newNodeIds.has(selectedNodeId)) hideNodeCard();
                scheduleDeptZonesRebuild(80);
            })
            .catch(function () {
                /* silencieux pendant le suivi */
            });
    }

    function loadGraph() {
        clearGraphCoalescedSyncTimer();
        var url;
        try {
            setLoading(true);
            if (graphEl) graphEl.style.display = 'block';
            if (emptyEl) emptyEl.style.display = 'none';
            if (errEl) {
                errEl.style.display = 'none';
                errEl.textContent = '';
            }
            if (statsWrap) statsWrap.innerHTML = '<span class="agences-chip">Chargement…</span>';

            url = buildGraphApiUrl();
        } catch (e0) {
            try {
                if (errEl) {
                    errEl.style.display = 'flex';
                    errEl.textContent =
                        'Erreur avant chargement : ' + (e0 && e0.message ? e0.message : String(e0));
                }
            } catch (e1) {}
            setLoading(false);
            return;
        }

        fetch(url, { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data.success && data.error) throw new Error(data.error);
                if (errEl) errEl.style.display = 'none';
                render(data);
            })
            .catch(function (err) {
                if (graphEl) graphEl.style.display = 'none';
                if (emptyEl) emptyEl.style.display = 'none';
                if (errEl) {
                    errEl.style.display = 'flex';
                    errEl.textContent = 'Impossible de charger le graphe : ' + (err.message || err);
                }
                if (statsWrap) statsWrap.innerHTML = '';
                if (graphResizeObserver) {
                    try {
                        graphResizeObserver.disconnect();
                    } catch (e) {}
                    graphResizeObserver = null;
                }
                if (graphResizeHandler) {
                    window.removeEventListener('resize', graphResizeHandler);
                    graphResizeHandler = null;
                }
                if (network) {
                    network.destroy();
                    network = null;
                }
            })
            .finally(function () {
                setLoading(false);
            });
    }

    if (btnReload) btnReload.addEventListener('click', loadGraph);
    if (scopeApplyBtn) scopeApplyBtn.addEventListener('click', loadGraph);
    if (scopePickQEl) {
        scopePickQEl.addEventListener('input', scheduleScopeAutocomplete);
        scopePickQEl.addEventListener('focus', scheduleScopeAutocomplete);
    }
    if (scopeAutocompleteEl) {
        scopeAutocompleteEl.addEventListener('click', function (ev) {
            const t = ev.target;
            const btn = t && t.closest ? t.closest('button.agences-scope-autocomplete__item[data-eid]') : null;
            if (!btn) return;
            const id = btn.getAttribute('data-eid');
            if (id) appendEntrepriseIdToScope(id);
        });
    }
    document.addEventListener('click', function (ev) {
        if (!scopeAutocompleteEl || !scopePickQEl) return;
        if (!scopeAutocompleteEl.classList.contains('is-open')) return;
        const t = ev.target;
        if (scopeAutocompleteEl.contains(t) || scopePickQEl.contains(t)) return;
        hideScopeAutocomplete();
    });

    if (scopePickQEl) {
        scopePickQEl.addEventListener('keydown', function (ev) {
            const open = scopeAutocompleteEl && scopeAutocompleteEl.classList.contains('is-open');
            const buttons = autocompleteOptionButtons();
            if (ev.key === 'ArrowDown') {
                if (!open || !buttons.length) return;
                ev.preventDefault();
                if (scopeAutocompleteActiveIdx < 0) setAutocompleteActive(0);
                else setAutocompleteActive(scopeAutocompleteActiveIdx + 1);
            } else if (ev.key === 'ArrowUp') {
                if (!open || !buttons.length) return;
                ev.preventDefault();
                if (scopeAutocompleteActiveIdx < 0) setAutocompleteActive(buttons.length - 1);
                else setAutocompleteActive(scopeAutocompleteActiveIdx - 1);
            } else if (ev.key === 'Enter') {
                if (!open || scopeAutocompleteActiveIdx < 0) return;
                const b = buttons[scopeAutocompleteActiveIdx];
                const id = b && b.getAttribute('data-eid');
                if (id) {
                    ev.preventDefault();
                    appendEntrepriseIdToScope(id);
                }
            } else if (ev.key === 'Escape') {
                if (open) {
                    ev.preventDefault();
                    hideScopeAutocomplete();
                }
            }
        });
    }
    if (btnFit) {
        btnFit.addEventListener('click', function () {
            if (!network) return;
            viewPushCurrent();
            network.fit(graphFitOptions());
        });
    }
    if (btnZoomIn) {
        btnZoomIn.addEventListener('click', function () {
            if (!network) return;
            const s = network.getScale();
            network.moveTo({ scale: s * 1.25, animation: { duration: 220, easingFunction: 'easeInOutQuad' } });
        });
    }
    if (btnZoomOut) {
        btnZoomOut.addEventListener('click', function () {
            if (!network) return;
            const s = network.getScale();
            network.moveTo({ scale: s * 0.8, animation: { duration: 220, easingFunction: 'easeInOutQuad' } });
        });
    }
    if (btnPhysics) {
        btnPhysics.addEventListener('click', function () {
            if (!network) return;
            function syncPhysicsBtnUi(on) {
                try {
                    btnPhysics.classList.toggle('md-btn--filled', !!on);
                    btnPhysics.classList.toggle('md-btn--outlined', !on);
                    btnPhysics.disabled = false;
                    btnPhysics.setAttribute('aria-busy', 'false');
                    btnPhysics.setAttribute(
                        'title',
                        on
                            ? 'Désactiver la physique (fige le layout actuel)'
                            : 'Activer la physique pour réorganiser les nœuds'
                    );
                } catch (e) {}
            }

            var next = !physicsEnabled;
            physicsEnabled = next;
            syncPhysicsBtnUi(next);

            function fitGraphFull() {
                if (!network) return;
                try {
                    network.fit(graphFitOptions());
                } catch (eFit) {}
            }

            try {
                // Uniquement la section physics : évite de re-pousser nodes/edges et de casser zoom / centre.
                network.setOptions(physicsOptionsOnly(next));
                if (!next && typeof network.stopSimulation === 'function') {
                    try {
                        network.stopSimulation();
                    } catch (eStop) {}
                }
            } catch (e2) {
                physicsEnabled = false;
                syncPhysicsBtnUi(false);
                return;
            }

            // Un seul cadrage, juste après que vis-network ait appliqué les options (1 frame).
            // Pas de setTimeout ni de fit sur « stabilized » : ça recadrait plus tard et donnait l’impression d’un double saut.
            if (typeof requestAnimationFrame === 'function') {
                requestAnimationFrame(function () {
                    fitGraphFull();
                });
            } else {
                fitGraphFull();
            }
        });
    }
    if (btnExport) {
        btnExport.addEventListener('click', function () {
            const canvas = graphEl.querySelector('canvas');
            if (!canvas) return;
            try {
                const a = document.createElement('a');
                a.download = 'prospectlab-graph-entreprises-' + new Date().toISOString().slice(0, 10) + '.png';
                a.href = canvas.toDataURL('image/png');
                a.click();
            } catch (e) {
                /* Canvas export bloqué (tainted canvas, navigateur) */
            }
        });
    }
    if (btnViewBack) btnViewBack.addEventListener('click', viewBack);
    if (btnViewFwd) btnViewFwd.addEventListener('click', viewFwd);

    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function () {
            if (localStorage.getItem(THEME_STORAGE_KEY)) return;
            syncThemeClasses();
            if (nodesDS && lastRaw) applyFilters();
            if (network) {
                try {
                    network.setOptions({
                        nodes: visNodesGlobalOptions(),
                    });
                } catch (e) {}
            }
        });
    }

    var btnTheme = document.getElementById('agences-theme-toggle');
    if (btnTheme) btnTheme.addEventListener('click', cycleThemePreference);
    syncThemeClasses();
    updateThemeToggleUi();
    graphFsUpdateBtnIcon();
    syncFiltersCollapsedFromStorage();
    bindFiltersAccordion();
    if (filtersCollapseToggleEl && filtersPanelEl) {
        filtersCollapseToggleEl.addEventListener('click', function () {
            var isCollapsed = filtersPanelEl.classList.contains('agences-filters--collapsed');
            var next = !isCollapsed;
            applyFiltersCollapsed(next);
            try {
                localStorage.setItem(FILTERS_COLLAPSED_KEY, next ? 'true' : 'false');
            } catch (e) {}
        });
    }
    if (nodeCardClose) nodeCardClose.addEventListener('click', hideNodeCard);

    if (btnFullscreen && wrapEl) {
        btnFullscreen.addEventListener('click', function (e) {
            e.stopPropagation();
            if (graphFsActive()) graphFsLeave();
            else graphFsEnter();
        });
    }
    if (fsFiltersToggle) {
        fsFiltersToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            graphFsToggleDropdown();
        });
        fsFiltersToggle.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowDown' && graphFsActive()) {
                e.preventDefault();
                if (!graphFsDropdownOpen) graphFsToggleDropdown();
            }
        });
    }
    if (fsTabHost) {
        fsTabHost.addEventListener('mouseenter', function () {
            if (!graphFsActive() || graphFsDropdownOpen) return;
            graphFsToggleDropdown();
        });
        fsTabHost.addEventListener('mouseleave', function () {
            if (!graphFsDropdownOpen) return;
            graphFsCloseDropdown(false);
        });
    }
    document.addEventListener('click', function (ev) {
        if (!graphFsDropdownOpen || !fsFiltersDropdown || !fsFiltersToggle) return;
        var t = ev.target;
        if (fsFiltersDropdown.contains(t) || fsFiltersToggle.contains(t)) return;
        graphFsCloseDropdown(false);
    });
    document.addEventListener('fullscreenchange', graphFsSyncFromDocument);
    document.addEventListener('webkitfullscreenchange', graphFsSyncFromDocument);
    document.addEventListener('MSFullscreenChange', graphFsSyncFromDocument);

    document.addEventListener('keydown', function (ev) {
        if (ev.key !== 'Escape') return;
        if (scopeAutocompleteEl && scopeAutocompleteEl.classList.contains('is-open')) {
            hideScopeAutocomplete();
            return;
        }
        if (graphFsDropdownOpen) {
            graphFsCloseDropdown(false);
            return;
        }
        if (graphFsPseudo) {
            graphFsLeave();
            return;
        }
        hideNodeCard();
    });

    bindFilterListeners();

    function bindExternalCardActions() {
        if (!nodeCardBody) return;
        nodeCardBody.addEventListener('click', function (ev) {
            var t = ev.target;
            var btn = t && t.closest ? t.closest('#graph-external-analyze-btn') : null;
            if (!btn) return;
            var rawUrl = (btn.getAttribute('data-url') || '').trim();
            if (!rawUrl) {
                setExternalAnalysisStatus('URL externe introuvable.', true);
                return;
            }
            if (!window.wsManager || !window.wsManager.socket || !window.wsManager.socket.connected) {
                setExternalAnalysisStatus('WebSocket non connecté. Rechargez la page.', true);
                return;
            }
            setExternalAnalyzeButtonBusy(true);
            setExternalAnalysisStatus('Préparation de la fiche entreprise…', false);
            fetch('/api/website-analysis/ensure-entreprise', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({ website: rawUrl }),
            })
                .then(parseJsonResponseSafe)
                .then(function (out) {
                    if (!out.ok || !out.body || !out.body.success || !out.body.entreprise_id) {
                        throw new Error(
                            (out.body && (out.body.error || out.body.message)) ||
                                ("Impossible de préparer l'entreprise (HTTP " + out.status + ').')
                        );
                    }
                    var eid = Number(out.body.entreprise_id);
                    var sourceNode = selectedNodeId && String(selectedNodeId).slice(0, 2) === 'a:' ? selectedNodeId : null;
                    var fallbackRunName = '';
                    try {
                        if (sourceNode && apiNodeById && apiNodeById.get(sourceNode)) {
                            fallbackRunName = String(apiNodeById.get(sourceNode).label || '').trim();
                        }
                    } catch (eNm) {}
                    graphExternalAnalysisRun = {
                        entrepriseId: eid,
                        entrepriseName: String(out.body.entreprise_name || fallbackRunName || '').trim(),
                        url: out.body.website || rawUrl,
                        taskId: null,
                        domainPromotedEarly: false,
                        lastStepNotified: '',
                        stepState: {
                            scrapingStarted: false,
                            scrapingDone: false,
                            technicalStarted: false,
                            technicalDone: false,
                        },
                        sourceDomainNodeId: sourceNode,
                        targetEntrepriseNodeId: 'e:' + String(eid),
                    };
                    if (sourceNode) {
                        domainPromotions.set(sourceNode, graphExternalAnalysisRun.targetEntrepriseNodeId);
                    }
                    try {
                        sessionStorage.setItem('graph_last_analysis_eid', String(eid));
                    } catch (eSs) {}
                    // Évite de rester bloqué sur un ancien scope "ID entreprise" injecté automatiquement.
                    if (scopeIdsEl && String(scopeIdsEl.value || '').trim() === String(eid)) {
                        scopeIdsEl.value = '';
                    }
                    setExternalAnalysisStatus('Démarrage du pack (scraping + technique)…', false);
                    return fetch('/api/website-full-analysis/start', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                        body: JSON.stringify({
                            website: graphExternalAnalysisRun.url,
                            enable_technical: true,
                            enable_seo: false,
                            enable_osint: false,
                            enable_pentest: false,
                            enable_nmap: false,
                            max_depth: 2,
                            max_workers: 5,
                            max_time: 240,
                            max_pages: 40,
                        }),
                    })
                        .then(parseJsonResponseSafe)
                        .then(function (out2) {
                            if (!out2.ok || !out2.body || !out2.body.success || !out2.body.task_id) {
                                throw new Error(
                                    (out2.body && (out2.body.error || out2.body.message)) ||
                                        ("Démarrage du pack impossible (HTTP " + out2.status + ').')
                                );
                            }
                            graphExternalAnalysisRun.taskId = String(out2.body.task_id);
                            try {
                                window.wsManager.socket.emit('monitor_full_website_analysis', {
                                    task_id: graphExternalAnalysisRun.taskId,
                                });
                                graphAnalysisDbg(
                                    'monitor_full_website_analysis émis, task_id=',
                                    graphExternalAnalysisRun.taskId
                                );
                            } catch (eEmit) {
                                throw new Error('Émission WebSocket impossible.');
                            }
                            setExternalAnalysisStatus('Scraping + technique en cours…', false);
                        });
                })
                .catch(function (err) {
                    setExternalAnalyzeButtonBusy(false);
                    setExternalAnalysisStatus(err.message || String(err), true);
                    showGraphNotification(err.message || String(err), 'error');
                });
        });
    }

    function bindExternalMiniScrapeEvents() {
        document.addEventListener('external_mini_scrape:started', function (ev) {
            var d = ev.detail || {};
            graphAnalysisDbg('external_mini_scrape:started', d);
            var last = null;
            try {
                last = sessionStorage.getItem('graph_last_analysis_eid');
            } catch (e0) {}
            if (last && String(d.entreprise_id || '') !== String(last)) return;
            var nm =
                graphExternalAnalysisRun &&
                Number(graphExternalAnalysisRun.entrepriseId) === Number(d.entreprise_id)
                    ? entrepriseDisplayName(graphExternalAnalysisRun)
                    : 'Entreprise #' + String(d.entreprise_id || '?');
            startMiniScrapeProgress(Number(d.external_links_count || 0));
            showGraphNotification(nm + ' : mini-scrape domaines externes en cours…', 'info');
        });
        document.addEventListener('external_mini_scrape:domain_complete', function (ev) {
            var d = ev.detail || {};
            graphAnalysisDbg('external_mini_scrape:domain_complete', d);
            var last = null;
            try {
                last = sessionStorage.getItem('graph_last_analysis_eid');
            } catch (e0) {}
            if (last && String(d.entreprise_id || '') !== String(last)) return;
            var entrepriseId = Number(d.entreprise_id || 0);
            var dom = d.domain || {};
            if (!entrepriseId || !dom || !dom.domain_host) return;
            if (!lastRaw || !nodesDS || !edgesDS) {
                pendingMiniScrapeDomainEvents.push({ dom: dom, entrepriseId: entrepriseId });
            } else {
                upsertExternalLinkRealtime(dom, entrepriseId);
            }
            bumpMiniScrapeProgress();
        });
        document.addEventListener('external_mini_scrape:complete', function (ev) {
            var d = ev.detail || {};
            graphAnalysisDbg('external_mini_scrape:complete', d);
            var last = null;
            try {
                last = sessionStorage.getItem('graph_last_analysis_eid');
            } catch (e0) {}
            if (last && String(d.entreprise_id || '') !== String(last)) return;
            if (d.skipped) {
                finishMiniScrapeProgress(0);
                showGraphNotification(
                    'Mini-scrape ignoré' + (d.reason ? ' (' + d.reason + ')' : ''),
                    'warning'
                );
                return;
            }
            if (d.ok === false) {
                finishMiniScrapeProgress(0);
                showGraphNotification(d.error ? String(d.error) : 'Mini-scrape en erreur', 'error');
                return;
            }
            var n = d.domains_scanned != null ? String(d.domains_scanned) : '?';
            finishMiniScrapeProgress(Number(d.domains_scanned || 0));
            showGraphNotification('Mini-scrape terminé (' + n + ' domaine(s)), graphe mis à jour…', 'success');
            // Les nœuds/liens sont désormais créés un par un via external_mini_scrape:domain_complete.
            // Ce refresh API sert uniquement de réconciliation finale.
            scheduleGraphCoalescedApiSync(2200);
        });
    }

    function bindExternalAnalysisRealtime() {
        function tryPromoteCurrentRunDomainNode() {
            if (!graphExternalAnalysisRun || graphExternalAnalysisRun.domainPromotedEarly) return false;
            var dDom = graphExternalAnalysisRun.sourceDomainNodeId;
            var eEnt = graphExternalAnalysisRun.targetEntrepriseNodeId;
            if (!dDom || !eEnt) return false;
            if (!promoteDomainNodeToEntreprise(dDom, eEnt)) return false;
            graphExternalAnalysisRun.domainPromotedEarly = true;
            syncLastRawAfterDomainPromotion(dDom, eEnt, graphExternalAnalysisRun);
            if (selectedNodeId === dDom) {
                selectedNodeId = eEnt;
                try {
                    if (network) network.selectNodes([eEnt], false);
                } catch (eSel0) {}
                fillNodeCard(eEnt);
            }
            try {
                applyFilters();
            } catch (eFlt0) {}
            return true;
        }

        document.addEventListener('full_website_analysis:progress', function (ev) {
            var d = ev.detail || {};
            if (!graphExternalAnalysisRun || !graphExternalAnalysisRun.taskId) return;
            if (String(d.task_id || '') !== String(graphExternalAnalysisRun.taskId)) return;
            graphAnalysisDbg('progress', d.meta || {});
            var meta = d.meta || {};
            if (meta.message) setExternalAnalysisStatus(String(meta.message), false);
            var step = String(meta.step || '');
            var stepState = graphExternalAnalysisRun.stepState || {};
            var entName = entrepriseDisplayName(graphExternalAnalysisRun);
            if (
                step === 'scraping' &&
                !stepState.scrapingStarted
            ) {
                stepState.scrapingStarted = true;
                showGraphNotification(entName + ' : scraping en cours', 'info');
            }
            if (
                step === 'technical' &&
                !stepState.technicalStarted
            ) {
                stepState.technicalStarted = true;
                if (!stepState.scrapingDone) {
                    stepState.scrapingDone = true;
                    showGraphNotification(entName + ' : scraping terminé', 'success');
                }
                showGraphNotification(entName + ' : analyse technique en cours', 'info');
                // Fin scraping : fusion domaine → fiche entreprise tout de suite (avant les events lien à flot).
                tryPromoteCurrentRunDomainNode();
            }
            if (
                step === 'scraping' &&
                !stepState.scrapingDone &&
                /scraping\s+termin/i.test(String(meta.message || ''))
            ) {
                stepState.scrapingDone = true;
                showGraphNotification(entName + ' : scraping terminé', 'success');
                tryPromoteCurrentRunDomainNode();
            }
            graphExternalAnalysisRun.stepState = stepState;
            if (step && step !== graphExternalAnalysisRun.lastStepNotified) {
                graphExternalAnalysisRun.lastStepNotified = step;
            }
        });
        document.addEventListener('full_website_analysis:external_link_found', function (ev) {
            var d = ev.detail || {};
            if (!graphExternalAnalysisRun || !graphExternalAnalysisRun.taskId) return;
            if (String(d.task_id || '') !== String(graphExternalAnalysisRun.taskId)) return;
            graphAnalysisDbg('external_link_found', d.link || {});
            var lk = d.link || {};
            var host = String(lk.domain_host || '').trim();
            var srcTxt = 'e:' + String(graphExternalAnalysisRun.entrepriseId || '?');
            var tgtId = Number(lk.target_entreprise_id || 0);
            var tgtTxt = tgtId > 0 ? 'e:' + String(tgtId) : '—';
            if (host) {
                setExternalAnalysisStatus('Nouveau lien externe : ' + host, false);
            }
            pushRealtimeFeedLine('+1 lien ' + srcTxt + ' -> a:' + (host || '?') + ' -> ' + tgtTxt, false);
            // Ne pas créer les nœuds ici: on ne veut que le flux mini-scrape (un domaine fini = un emit).
        });
        document.addEventListener('full_website_analysis:external_domain_enriched', function (ev) {
            var d = ev.detail || {};
            if (!graphExternalAnalysisRun || !graphExternalAnalysisRun.taskId) return;
            if (String(d.task_id || '') !== String(graphExternalAnalysisRun.taskId)) return;
            var dom = d.domain || {};
            var host = String(dom.domain_host || '').trim();
            if (!host) return;

            // Notif + mise à jour du nœud domaine (thumbnail / label / groupe).
            showGraphNotification('Domaine enrichi : ' + host, 'info');
            var nodeId = 'a:' + host;
            try {
                var cur = apiNodeById && apiNodeById.get ? apiNodeById.get(nodeId) : null;
                if (cur) {
                    if (dom.site_title) cur.label = String(dom.site_title).slice(0, 52);
                    if (dom.site_title) cur.title = String(dom.site_title).slice(0, 300);
                    if (dom.site_description) cur.site_description = String(dom.site_description).slice(0, 800);
                    if (dom.thumb_url) {
                        cur.thumb_url = String(dom.thumb_url).slice(0, 2000);
                        cur.thumbnail_url = cur.thumb_url;
                    }
                    if (dom.graph_group) cur.group = String(dom.graph_group);
                }
            } catch (e0) {}
            try {
                if (nodesDS && nodesDS.get(nodeId)) {
                    var st = getFilterState();
                    var raw = (apiNodeById && apiNodeById.get && apiNodeById.get(nodeId)) || { id: nodeId, label: host, group: 'external', title: host };
                    var vs = nodeVisualStyle(raw);
                    var si = vs.si;
                    var patch = {
                        id: nodeId,
                        label: displayLabel(raw, st),
                        title: graphNodeTooltipEl(raw),
                        color: {
                            background: vs.st.color,
                            border: visNodeOutline(),
                            highlight: {
                                background: vs.st.color,
                                border: isLightTheme() ? '#0f172a' : '#f8fafc',
                            },
                        },
                        font: visNodeFontForGroup(raw.group || 'external'),
                        shape: si.shape,
                        size: si.size,
                        value: si.value,
                        borderWidth: 2,
                        hidden: false,
                    };
                    applyNodeImageFields(patch, si, false);
                    nodesDS.update(patch);
                }
            } catch (e1) {}
        });
        document.addEventListener('full_website_analysis:complete', function (ev) {
            var d = ev.detail || {};
            if (!graphExternalAnalysisRun || !graphExternalAnalysisRun.taskId) return;
            if (String(d.task_id || '') !== String(graphExternalAnalysisRun.taskId)) return;
            graphAnalysisDbg('complete', d.result || {});
            var res = d.result || {};
            var domNode = graphExternalAnalysisRun.sourceDomainNodeId;
            var entNode = graphExternalAnalysisRun.targetEntrepriseNodeId;
            var stepState = graphExternalAnalysisRun.stepState || {};
            var entName = entrepriseDisplayName(graphExternalAnalysisRun);
            setExternalAnalysisStatus(
                res.message ? String(res.message) : 'Scraping + technique terminé. Graphe mis à jour.',
                false
            );
            if (stepState.scrapingStarted && !stepState.scrapingDone) {
                stepState.scrapingDone = true;
                showGraphNotification(entName + ' : scraping terminé', 'success');
            }
            if (stepState.technicalStarted && !stepState.technicalDone) {
                stepState.technicalDone = true;
                showGraphNotification(entName + ' : analyse technique terminée', 'success');
            }
            graphExternalAnalysisRun.stepState = stepState;
            // Promotion déjà faite au passage « technical » ; sinon (sans carte domaine) on tente ici.
            if (domNode && entNode && !graphExternalAnalysisRun.domainPromotedEarly) {
                tryPromoteCurrentRunDomainNode();
            }
            graphExternalAnalysisRun = null;
            setExternalAnalyzeButtonBusy(false);
        });
        document.addEventListener('full_website_analysis:error', function (ev) {
            var d = ev.detail || {};
            graphAnalysisDbg('error', d);
            if (!graphExternalAnalysisRun) return;
            if (
                graphExternalAnalysisRun.taskId &&
                d.task_id &&
                String(d.task_id) !== String(graphExternalAnalysisRun.taskId)
            ) {
                return;
            }
            setExternalAnalysisStatus(d.error ? String(d.error) : 'Erreur analyse.', true);
            finishMiniScrapeProgress(0);
            showGraphNotification(d.error ? String(d.error) : 'Erreur analyse.', 'error');
            pushRealtimeFeedLine(d.error ? String(d.error) : 'Erreur analyse.', true);
            graphExternalAnalysisRun = null;
            setExternalAnalyzeButtonBusy(false);
        });
    }

    bindExternalCardActions();
    bindExternalMiniScrapeEvents();
    bindExternalAnalysisRealtime();
    applyBootstrapScopeDefaults();
    loadGraph();
})();
