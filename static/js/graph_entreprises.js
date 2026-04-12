/**
 * Graphe vis-network : entreprises ↔ domaines externes (API /api/entreprises/graph).
 * Filtres, carte détail flottante, export PNG, physique, autocomplétion périmètre, recherche sur le graphe.
 */
(function () {
    'use strict';

    const graphEl = document.getElementById('agences-graph');
    const wrapEl = document.getElementById('agences-graph-wrap');
    const emptyEl = document.getElementById('agences-graph-empty');
    const errEl = document.getElementById('agences-graph-error');
    const statsWrap = document.getElementById('agences-graph-stats-wrap');
    const loadingEl = document.getElementById('agences-graph-loading');
    const btnReload = document.getElementById('agences-graph-reload');
    const btnFit = document.getElementById('agences-graph-fit');
    const btnZoomIn = document.getElementById('agences-graph-zoom-in');
    const btnZoomOut = document.getElementById('agences-graph-zoom-out');
    const btnPhysics = document.getElementById('agences-graph-physics');
    const btnExport = document.getElementById('agences-graph-export');
    const nodeCard = document.getElementById('agences-node-card');
    const nodeCardClose = document.getElementById('agences-node-card-close');
    const nodeCardEyebrow = document.getElementById('agences-node-card-eyebrow');
    const nodeCardBody = document.getElementById('agences-node-card-body');
    const btnViewBack = document.getElementById('agences-graph-view-back');
    const btnViewFwd = document.getElementById('agences-graph-view-fwd');
    const btnClusterLeaves = document.getElementById('agences-graph-cluster-leaves');
    const btnClusterOpen = document.getElementById('agences-graph-cluster-open');

    if (!graphEl) return;

    const emptyElDefaultText =
        emptyEl && emptyEl.textContent ? emptyEl.textContent.trim() : '';

    const scopeHintEl = document.getElementById('agences-graph-scope-hint');
    const scopeSearchEl = document.getElementById('agences-scope-search');
    const scopeDomainEl = document.getElementById('agences-scope-domain');
    const scopeMaxRowsEl = document.getElementById('agences-scope-max-rows');
    const scopeMaxEntsEl = document.getElementById('agences-scope-max-ents');
    const scopeIdsEl = document.getElementById('agences-scope-ids');
    const scopeOnlyCreditEl = document.getElementById('agences-scope-only-credit');
    const scopePickQEl = document.getElementById('agences-scope-pick-q');
    const scopeAutocompleteEl = document.getElementById('agences-scope-autocomplete');
    const scopeApplyBtn = document.getElementById('agences-scope-apply');

    let scopeAutocompleteTimer = null;
    let scopeAutocompleteActiveIdx = -1;
    let graphResizeObserver = null;
    let graphResizeHandler = null;

    let network = null;
    let nodesDS = null;
    let edgesDS = null;
    let lastRaw = null;
    let apiNodeById = new Map();
    let physicsEnabled = false;
    let selectedNodeId = null;
    let filterDebounce = null;
    let viewPast = [];
    let viewFuture = [];
    let preDragView = null;

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
                target.image = null;
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
        } else if (k === 'light') {
            if (icon) icon.textContent = 'light_mode';
            if (label) label.textContent = 'Clair';
        } else {
            if (icon) icon.textContent = 'routine';
            if (label) label.textContent = 'Auto';
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

    function getClusteringMod() {
        if (!network) return null;
        if (network.clustering) return network.clustering;
        if (network.body && network.body.modules && network.body.modules.clustering) {
            return network.body.modules.clustering;
        }
        return null;
    }

    function clusterLeaves() {
        if (!network || !lastRaw) return;
        var deg = buildVisibleDegree();
        try {
            network.cluster({
                joinCondition: function (nodeOptions) {
                    if (nodeOptions.hidden) return false;
                    var raw = apiNodeById.get(nodeOptions.id);
                    if (!raw) return false;
                    var g = raw.group || 'external';
                    if (g === 'entreprise' || g === 'agency') return false;
                    return (deg[nodeOptions.id] || 0) <= 1;
                },
                processProperties: function (clusterOptions, childNodes) {
                    clusterOptions.label = String(childNodes.length) + ' feuilles';
                    clusterOptions.shape = 'database';
                    clusterOptions.color = { background: '#4f46e5', border: '#a5b4fc' };
                    clusterOptions.font = isLightTheme()
                        ? { color: '#f8fafc', size: 13 }
                        : { color: '#f8fafc', size: 13 };
                    clusterOptions.borderWidth = 2;
                    return clusterOptions;
                },
            });
        } catch (e) {
            /* Clustering indisponible selon version / options vis-network */
        }
    }

    function openAllClusters() {
        var cl = getClusteringMod();
        if (!cl || !network) return;
        var i = 0;
        while (i++ < 80) {
            var found = false;
            try {
                network.body.data.nodes.getIds().forEach(function (id) {
                    if (typeof cl.isCluster === 'function' && cl.isCluster(id)) {
                        network.openCluster(id);
                        found = true;
                    }
                });
            } catch (e) {
                break;
            }
            if (!found) break;
        }
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
        rawNodes.forEach(function (n) {
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
        const searchEl = document.getElementById('agences-graph-search');
        return {
            showEnt: chk('flt-nodes-ent', true),
            showAgency: chk('flt-nodes-agency', true),
            showOther: chk('flt-nodes-other', true),
            edgeCredit: chk('flt-edge-credit', true),
            edgeLien: chk('flt-edge-lien', true),
            edgeRef: chk('flt-edge-ref', true),
            edgeFiche: chk('flt-edge-fiche', true),
            compactLabels: chk('flt-compact-labels', true),
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
        const accent = st0.color || '#a855f7';
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
        const st = {
            color: st0.color,
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

    function buildVisEdges(rawEdges, visibleIds, state) {
        return (rawEdges || []).map(function (e, idx) {
            const show = edgeVisible(e, visibleIds, state);
            const k = edgeKind(e);
            const w = k === 'credit' ? 2.4 : k === 'fiche' ? 2.0 : k === 'ref' ? 1.85 : 1.9;
            return {
                id: 'e' + idx,
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

    function networkOptions(physicsOn) {
        var fa2 = getForceAtlas2Opts();
        return {
            physics: {
                enabled: !!physicsOn,
                stabilization: { iterations: physicsOn ? 400 : 80 },
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
            nodeUpdates.push(upd);
        });
        nodesDS.update(nodeUpdates);
        const edgeUpdates = [];
        lastRaw.edges.forEach(function (e, idx) {
            var k = edgeKind(e);
            var w = k === 'credit' ? 2.4 : k === 'fiche' ? 2.0 : k === 'ref' ? 1.85 : 1.9;
            edgeUpdates.push({
                id: 'e' + idx,
                hidden: !edgeVisible(e, visibleIds, state),
                label: state.compactLabels ? '' : e.label || '',
                width: w,
                font: visEdgeFont(),
            });
        });
        edgesDS.update(edgeUpdates);
        if (selectedNodeId && !visibleIds.has(selectedNodeId)) hideNodeCard();
    }

    function scheduleApplyFilters() {
        if (filterDebounce) clearTimeout(filterDebounce);
        filterDebounce = setTimeout(function () {
            filterDebounce = null;
            applyFilters();
        }, 120);
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
        ];
        ids.forEach(function (id) {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', scheduleApplyFilters);
        });
        const searchEl = document.getElementById('agences-graph-search');
        if (searchEl) {
            searchEl.addEventListener('input', scheduleApplyFilters);
        }
    }

    function render(data) {
        const st = data.stats || {};
        const scope = data.graph_scope || null;
        renderStats(st, scope);
        updateScopeHint(scope);

        if (!data.nodes || data.nodes.length === 0) {
            graphEl.style.display = 'none';
            emptyEl.style.display = 'block';
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
            if (noMatchScope) {
                emptyEl.textContent =
                    'Aucun lien ne correspond à ce périmètre. Élargissez la recherche ou les plafonds.';
            } else {
                emptyEl.textContent = emptyElDefaultText;
            }
            if (graphResizeObserver && wrapEl) {
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
            hideNodeCard();
            return;
        }

        graphEl.style.display = 'block';
        emptyEl.style.display = 'none';

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
        const vNodes = buildVisNodes(lastRaw.nodes, state, visibleIds);
        const vEdges = buildVisEdges(lastRaw.edges, visibleIds, state);

        nodesDS = new vis.DataSet(vNodes);
        edgesDS = new vis.DataSet(vEdges);

        if (network) network.destroy();
        if (graphResizeObserver && wrapEl) {
            try {
                graphResizeObserver.disconnect();
            } catch (e) {}
            graphResizeObserver = null;
        }
        if (graphResizeHandler) {
            window.removeEventListener('resize', graphResizeHandler);
            graphResizeHandler = null;
        }
        physicsEnabled = true;

        network = new vis.Network(graphEl, { nodes: nodesDS, edges: edgesDS }, networkOptions(true));

        function syncGraphSize() {
            if (!network || !wrapEl || !graphEl) return;
            const w = wrapEl.clientWidth;
            const h = wrapEl.clientHeight;
            if (w < 48 || h < 48) return;
            try {
                network.setSize(w + 'px', h + 'px');
                network.redraw();
            } catch (e) {}
        }
        syncGraphSize();
        if (typeof ResizeObserver !== 'undefined' && wrapEl) {
            graphResizeObserver = new ResizeObserver(function () {
                syncGraphSize();
            });
            graphResizeObserver.observe(wrapEl);
        }
        graphResizeHandler = function () {
            syncGraphSize();
        };
        window.addEventListener('resize', graphResizeHandler);

        let initialFitDone = false;
        function doInitialFit() {
            if (initialFitDone || !network) return;
            initialFitDone = true;
            physicsEnabled = false;
            network.setOptions({ physics: { enabled: false } });
            if (btnPhysics) btnPhysics.classList.remove('md-btn--filled');
            network.fit({
                animation: {
                    duration: 520,
                    easingFunction: 'easeInOutQuad',
                },
            });
        }
        network.once('stabilizationIterationsDone', doInitialFit);
        setTimeout(doInitialFit, 4000);

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
        });
    }

    function loadGraph() {
        setLoading(true);
        graphEl.style.display = 'block';
        emptyEl.style.display = 'none';
        errEl.style.display = 'none';
        errEl.textContent = '';
        if (statsWrap) statsWrap.innerHTML = '<span class="agences-chip">Chargement…</span>';

        const qp = buildGraphQueryParams();
        const qs = qp.toString();
        const url = '/api/entreprises/graph' + (qs ? '?' + qs : '');

        fetch(url, { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data.success && data.error) throw new Error(data.error);
                errEl.style.display = 'none';
                render(data);
            })
            .catch(function (err) {
                graphEl.style.display = 'none';
                emptyEl.style.display = 'none';
                errEl.style.display = 'block';
                errEl.textContent = 'Impossible de charger le graphe : ' + (err.message || err);
                if (statsWrap) statsWrap.innerHTML = '';
                if (graphResizeObserver && wrapEl) {
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
            network.fit({
                animation: { duration: 550, easingFunction: 'easeInOutQuad' },
            });
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
            physicsEnabled = !physicsEnabled;
            var fa2 = getForceAtlas2Opts();
            network.setOptions({
                    physics: {
                    enabled: physicsEnabled,
                    stabilization: { iterations: physicsEnabled ? 400 : 0 },
                    forceAtlas2Based: fa2,
                    solver: 'forceAtlas2Based',
                },
            });
            btnPhysics.classList.toggle('md-btn--filled', physicsEnabled);
            try {
                if (physicsEnabled) network.startSimulation();
                else network.stopSimulation();
            } catch (e) {
                /* vis-network versions */
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
    if (btnClusterLeaves) btnClusterLeaves.addEventListener('click', clusterLeaves);
    if (btnClusterOpen) btnClusterOpen.addEventListener('click', openAllClusters);

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
    if (nodeCardClose) nodeCardClose.addEventListener('click', hideNodeCard);
    document.addEventListener('keydown', function (ev) {
        if (ev.key !== 'Escape') return;
        if (scopeAutocompleteEl && scopeAutocompleteEl.classList.contains('is-open')) {
            hideScopeAutocomplete();
            return;
        }
        hideNodeCard();
    });

    bindFilterListeners();
    loadGraph();
})();
