/**
 * Analyse concurrence & marché — vue type chiffres-clés (données /api/statistics).
 */
(function () {
    const charts = {};
    let currentDaysFilter = '';
    let currentRoadmapCategoryFilter = '';
    let currentRoadmapStatusFilter = '';
    let currentRoadmapPriorityFilter = '';
    let currentRoadmapSearchQuery = '';
    let roadmapRowsCache = [];

    function getChartTheme() {
        const isDark = document.body.getAttribute('data-theme') === 'dark';
        return {
            isDark,
            textColor: isDark ? '#e2e8f0' : '#334155',
            gridColor: isDark ? 'rgba(148, 163, 184, 0.16)' : 'rgba(148, 163, 184, 0.25)',
            legend: { labels: { color: isDark ? '#e2e8f0' : '#334155' } },
            navy: '#1e3a5f',
            navyLight: '#3b5a8a',
            muted: isDark ? '#94a3b8' : '#64748b',
        };
    }

    async function fetchStatistics() {
        const params = new URLSearchParams();
        const d = Number.parseInt(currentDaysFilter, 10);
        if (Number.isFinite(d) && d > 0) {
            params.set('days', String(d));
        }
        const qs = params.toString();
        const res = await fetch(`/api/statistics${qs ? `?${qs}` : ''}`);
        return res.json();
    }

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function setNumber(id, n) {
        setText(id, Number(n || 0).toLocaleString('fr-FR'));
    }

    function computeFriction(parStatut) {
        const g = Number(parStatut['Gagné'] || 0);
        const p = Number(parStatut['Perdu'] || 0);
        const t = g + p;
        if (t <= 0) return 0;
        return Math.min(100, Math.round((100 * p) / t));
    }

    function countHighOpportunity(parOpp) {
        const keys = Object.keys(parOpp || {});
        let n = 0;
        keys.forEach((k) => {
            if (!k) return;
            if (k === 'Très élevée' || k === 'Élevée') {
                n += Number(parOpp[k] || 0);
            }
        });
        return n;
    }

    function renderOpportunityBand(parOpp, totalEnt) {
        const wrap = document.getElementById('acm-opp-band');
        const legend = document.getElementById('acm-opp-band-legend');
        if (!wrap || !legend) return;

        const entries = Object.entries(parOpp || {}).filter(([k]) => k);
        entries.sort((a, b) => (b[1] || 0) - (a[1] || 0));
        const total = entries.reduce((s, [, v]) => s + (Number(v) || 0), 0) || 1;
        const palette = ['#1e3a5f', '#2563eb', '#0d9488', '#d97706', '#7c3aed', '#64748b', '#94a3b8'];

        wrap.innerHTML = entries.slice(0, 7).map(([label, val], i) => {
            const pct = Math.round((100 * Number(val || 0)) / total);
            const color = palette[i % palette.length];
            const safeTitle = `${label} : ${val} (${pct} %)`;
            return `<div class="acm-stack-seg" style="width:${pct}%;background:${color}" title="${escapeHtml(safeTitle)}"></div>`;
        }).join('');

        const highPct = totalEnt > 0
            ? Math.round((100 * countHighOpportunity(parOpp)) / totalEnt)
            : 0;
        setText('acm-opp-band-caption', `${highPct} % de la base classée « Élevée » ou « Très élevée »`);

        legend.innerHTML = entries.slice(0, 7).map(([label, val], i) => {
            const pct = Math.round((100 * Number(val || 0)) / total);
            const color = palette[i % palette.length];
            return `<span class="acm-legend-item"><i style="background:${color}"></i> ${label} (${pct} %)</span>`;
        }).join('');
    }

    function renderOpportunityTable(parOpp, totalEnt) {
        const tbody = document.querySelector('#acm-opp-table tbody');
        if (!tbody) return;
        const entries = Object.entries(parOpp || {}).filter(([k]) => k);
        entries.sort((a, b) => (b[1] || 0) - (a[1] || 0));
        const te = Number(totalEnt) || 1;

        if (!entries.length) {
            tbody.innerHTML = '<tr><td colspan="3">Aucune donnée d’opportunité.</td></tr>';
            return;
        }

        tbody.innerHTML = entries.map(([label, val]) => {
            const n = Number(val || 0);
            const pct = Math.round((100 * n) / te);
            return `<tr><td>${escapeHtml(label)}</td><td class="acm-num">${n.toLocaleString('fr-FR')}</td><td class="acm-num">${pct} %</td></tr>`;
        }).join('');
    }

    function renderHbarMotifs(containerId, sourceObj, limit, emptyMessage) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const entries = Object.entries(sourceObj || {}).filter(([k]) => k);
        entries.sort((a, b) => (b[1] || 0) - (a[1] || 0));
        const top = entries.slice(0, limit);
        const max = top.length ? Math.max(...top.map(([, v]) => Number(v) || 0), 1) : 1;

        if (!top.length) {
            container.innerHTML = `<p class="acm-muted">${emptyMessage}</p>`;
            return;
        }

        container.innerHTML = top.map(([name, val]) => {
            const n = Number(val || 0);
            const w = Math.round((100 * n) / max);
            return `
            <div class="acm-hbar-row">
                <span class="acm-hbar-label">${escapeHtml(name)}</span>
                <div class="acm-hbar-track"><div class="acm-hbar-fill" style="width:${w}%"></div></div>
                <span class="acm-hbar-val">${n.toLocaleString('fr-FR')}</span>
            </div>`;
        }).join('');
    }

    function renderSecteurMotifs(parSecteur) {
        renderHbarMotifs('acm-secteur-motifs', parSecteur, 8, 'Pas assez de secteurs renseignés.');
    }

    function renderPaysTable(parPays, totalEnt) {
        const tbody = document.querySelector('#acm-pays-table tbody');
        if (!tbody) return;
        const entries = Object.entries(parPays || {}).filter(([k]) => k);
        entries.sort((a, b) => (b[1] || 0) - (a[1] || 0));
        const te = Number(totalEnt) || 1;
        if (!entries.length) {
            tbody.innerHTML = '<tr><td colspan="3">Aucun pays renseigné sur les fiches.</td></tr>';
            return;
        }
        tbody.innerHTML = entries.map(([label, val]) => {
            const n = Number(val || 0);
            const pct = Math.round((100 * n) / te);
            return `<tr><td>${escapeHtml(label)}</td><td class="acm-num">${n.toLocaleString('fr-FR')}</td><td class="acm-num">${pct} %</td></tr>`;
        }).join('');
    }

    function renderGeoResume(geo) {
        const g = geo || {};
        setNumber('acm-geo-avec', g.avec_coords ?? 0);
        setNumber('acm-geo-sans', g.sans_coords ?? 0);
        setNumber('acm-geo-fr', g.france_metropole_approx ?? 0);
    }

    function renderRoadmapMetrics(ctx) {
        setNumber('acm-roadmap-kpi-opps', ctx.highOpp || 0);
        setNumber('acm-roadmap-kpi-priority', ctx.priorityCount || 0);
        setNumber('acm-roadmap-kpi-ab', ctx.emailsEnvoyes || 0);

        const setState = (id, text, tone) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.textContent = text;
            el.classList.remove('is-good', 'is-warn', 'is-neutral');
            el.classList.add(tone);
        };

        const battleReady = (ctx.secteurCount >= 5 && ctx.tagCount >= 8);
        setState(
            'acm-roadmap-state-battlecards',
            battleReady ? 'Prêt MVP' : 'À cadrer',
            battleReady ? 'is-good' : 'is-neutral',
        );

        const radarReady = (ctx.priorityCount >= 10);
        setState(
            'acm-roadmap-state-radar',
            radarReady ? 'Actionnable' : 'En préparation',
            radarReady ? 'is-good' : 'is-warn',
        );

        const alertUrgency = (ctx.highOpp >= 20 || ctx.friction >= 45);
        setState(
            'acm-roadmap-state-alerts',
            alertUrgency ? 'Prioritaire' : 'Prototype',
            alertUrgency ? 'is-warn' : 'is-neutral',
        );

        const abReady = (ctx.emailsEnvoyes >= 200);
        setState(
            'acm-roadmap-state-ab',
            abReady ? 'Prêt test' : 'À lancer',
            abReady ? 'is-good' : 'is-neutral',
        );
    }

    const ROADMAP_TEMPLATES = {
        battlecards: {
            title: 'MVP battlecards sur top 5 secteurs',
            description: 'Créer les battlecards concurrentes pour les secteurs les plus représentés avec pitch copiable.',
            priority: 'high',
        },
        radar: {
            title: 'Activer radar 7 jours actionnable',
            description: 'Publier le top 20 quotidien et répartir automatiquement les relances par équipe.',
            priority: 'high',
        },
        alerts: {
            title: 'Configurer alertes opportunités dormantes',
            description: 'Règles : opportunité élevée + absence d’action > X jours + digest quotidien.',
            priority: 'medium',
        },
        ab: {
            title: 'Lancer test A/B commercial pilote',
            description: 'Expérimenter 2 scripts d’approche et comparer réponses / RDV / gains.',
            priority: 'medium',
        },
        commercial_outreach: {
            pillar: 'radar',
            category: 'commercial',
            title: 'Relance commerciale prioritaire',
            description: 'Planifier les relances ciblées sur le top 20 de la semaine.',
            priority: 'high',
        },
        marketing_campaign: {
            pillar: 'alerts',
            category: 'marketing',
            title: 'Campagne marketing segmentée',
            description: 'Tester une campagne de contenu/offre par segment d’opportunité.',
            priority: 'medium',
        },
        product_packaging: {
            pillar: 'battlecards',
            category: 'produit',
            title: 'Pack offre segmenté',
            description: 'Formaliser une offre différenciante basée sur les objections du terrain.',
            priority: 'medium',
        },
        ops_process: {
            pillar: 'radar',
            category: 'ops',
            title: 'Routine équipe quotidienne',
            description: 'Instaurer un rituel d’assignation et suivi des relances gagnables.',
            priority: 'medium',
        },
        data_quality: {
            pillar: 'ab',
            category: 'data',
            title: 'Contrôle qualité données pipeline',
            description: 'Assainir les statuts et champs clés pour fiabiliser les décisions.',
            priority: 'low',
        },
    };

    async function fetchRoadmapActions() {
        const params = new URLSearchParams({ limit: '40' });
        if (currentRoadmapStatusFilter) params.set('status', currentRoadmapStatusFilter);
        if (currentRoadmapPriorityFilter) params.set('priority', currentRoadmapPriorityFilter);
        const res = await fetch(`/api/market-concurrence/roadmap-actions?${params.toString()}`);
        if (!res.ok) throw new Error('Erreur chargement backlog roadmap');
        return res.json();
    }

    async function createRoadmapAction(templateKey) {
        const tpl = ROADMAP_TEMPLATES[templateKey];
        if (!tpl) return;
        const pillar = tpl.pillar || templateKey;
        const res = await fetch('/api/market-concurrence/roadmap-actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pillar,
                category: tpl.category || 'commercial',
                title: tpl.title,
                description: tpl.description,
                priority: tpl.priority,
            }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || 'Création action impossible');
        }
        return res.json();
    }

    async function updateRoadmapAction(actionId, patch) {
        const res = await fetch(`/api/market-concurrence/roadmap-actions/${actionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(patch),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || 'Mise à jour action impossible');
        }
        return res.json();
    }

    function fmtPillar(p) {
        const map = {
            battlecards: 'Battlecards',
            radar: 'Radar',
            alerts: 'Alertes',
            ab: 'A/B',
        };
        return map[p] || p || 'Roadmap';
    }

    function fmtStatus(s) {
        const map = {
            todo: 'À faire',
            in_progress: 'En cours',
            done: 'Fait',
            blocked: 'Bloqué',
            cancelled: 'Annulée',
        };
        return map[s] || s || 'À faire';
    }

    function fmtCategory(c) {
        const map = {
            commercial: 'Commercial',
            marketing: 'Marketing',
            produit: 'Produit',
            ops: 'Ops',
            data: 'Data',
        };
        return map[c] || c || 'Commercial';
    }

    function fmtPriority(p) {
        const map = {
            high: 'Haute',
            medium: 'Moyenne',
            low: 'Basse',
        };
        const k = String(p || 'medium').toLowerCase();
        return map[k] || k;
    }

    function stripDiacritics(s) {
        return String(s).normalize('NFD').replace(/\p{M}/gu, '');
    }

    function normalizeSearch(s) {
        return stripDiacritics(String(s || '').toLowerCase()).trim();
    }

    function roadmapRowSearchText(r) {
        const parts = [
            r.title,
            r.description,
            r.pillar,
            fmtPillar(r.pillar),
            r.category,
            fmtCategory(r.category),
            r.status,
            fmtStatus(r.status),
            r.priority,
            fmtPriority(r.priority),
            'high',
            'medium',
            'low',
        ];
        return normalizeSearch(parts.filter(Boolean).join(' '));
    }

    function renderRoadmapCounters(rows) {
        const counts = {
            commercial: 0,
            marketing: 0,
            produit: 0,
            ops: 0,
            data: 0,
        };
        (rows || []).forEach((r) => {
            const c = String(r.category || 'commercial').toLowerCase();
            if (Object.prototype.hasOwnProperty.call(counts, c)) counts[c] += 1;
        });
        Object.keys(counts).forEach((k) => {
            const el = document.querySelector(`[data-roadmap-count="${k}"]`);
            if (el) el.textContent = String(counts[k]);
        });
    }

    function renderRoadmapActionsList(rows) {
        const container = document.getElementById('acm-roadmap-actions-list');
        if (!container) return;
        const allRows = rows || [];
        const qNorm = normalizeSearch(currentRoadmapSearchQuery);
        const byCategory = allRows.filter((r) => {
            if (currentRoadmapCategoryFilter && String(r.category || 'commercial').toLowerCase() !== currentRoadmapCategoryFilter) return false;
            return true;
        });
        const filtered = byCategory.filter((r) => {
            if (!qNorm) return true;
            return roadmapRowSearchText(r).includes(qNorm);
        });
        renderRoadmapCounters(allRows);
        if (!allRows.length) {
            container.innerHTML = '<p class="acm-muted">Aucune action roadmap. Utilise “Créer action” sur une brique.</p>';
            return;
        }
        if (!filtered.length) {
            let msg = 'Aucune action ne correspond aux filtres actuels.';
            if (qNorm) {
                msg = `Aucun résultat pour « ${escapeHtml(currentRoadmapSearchQuery.trim())} ». Essaie un autre mot-clé ou retire un filtre.`;
            } else if (currentRoadmapCategoryFilter) {
                msg = `Aucune action dans la catégorie « ${escapeHtml(fmtCategory(currentRoadmapCategoryFilter))} » avec les filtres chargés.`;
            }
            container.innerHTML = `<p class="acm-muted">${msg}</p>`;
            return;
        }
        container.innerHTML = filtered.map((r) => {
            const prio = String(r.priority || 'medium').toLowerCase();
            const prioClass = ['high', 'medium', 'low'].includes(prio) ? prio : 'medium';
            return `
            <article class="acm-roadmap-action-item">
                <div class="acm-roadmap-action-main">
                    <p class="acm-roadmap-action-title">${escapeHtml(r.title || 'Action')}</p>
                    <p class="acm-roadmap-action-meta">
                        <span class="acm-roadmap-chip">${escapeHtml(fmtPillar(r.pillar))}</span>
                        <span class="acm-roadmap-chip">${escapeHtml(fmtCategory(r.category))}</span>
                        <span class="acm-roadmap-chip">${escapeHtml(fmtStatus(r.status))}</span>
                        <span class="acm-roadmap-chip acm-roadmap-chip--prio acm-roadmap-chip--prio-${prioClass}">${escapeHtml(fmtPriority(r.priority))}</span>
                    </p>
                </div>
                <div class="acm-roadmap-action-cta">
                    <button type="button" class="acm-roadmap-btn acm-roadmap-btn--ghost" data-roadmap-status="${r.id}" data-next="in_progress">En cours</button>
                    <button type="button" class="acm-roadmap-btn" data-roadmap-status="${r.id}" data-next="done">Fait</button>
                    <button type="button" class="acm-roadmap-btn acm-roadmap-btn--ghost" data-roadmap-status="${r.id}" data-next="cancelled">Annuler</button>
                    <button type="button" class="acm-roadmap-btn acm-roadmap-btn--ghost acm-no-ripple" data-roadmap-menu="${r.id}">⋮</button>
                    <div class="acm-roadmap-menu" data-roadmap-menu-panel="${r.id}" hidden>
                        <button type="button" class="acm-roadmap-menu-item" data-roadmap-edit="${r.id}">Éditer</button>
                        <button type="button" class="acm-roadmap-menu-item" data-roadmap-duplicate="${r.id}">Dupliquer</button>
                        ${String(r.status) === 'cancelled' ? `<button type="button" class="acm-roadmap-menu-item" data-roadmap-reactivate="${r.id}">Réactiver</button>` : ''}
                    </div>
                </div>
            </article>
            `;
        }).join('');
    }

    async function refreshRoadmapActions() {
        try {
            const rows = await fetchRoadmapActions();
            roadmapRowsCache = rows || [];
            renderRoadmapActionsList(roadmapRowsCache);
        } catch (e) {
            const container = document.getElementById('acm-roadmap-actions-list');
            if (container) container.innerHTML = '<p class="acm-muted">Impossible de charger le backlog roadmap.</p>';
        }
    }

    function openActionEditor(actionId) {
        const item = (roadmapRowsCache || []).find((r) => Number(r.id) === Number(actionId));
        if (!item) return;
        const idEl = document.getElementById('acm-edit-action-id');
        const titleEl = document.getElementById('acm-edit-title');
        const catEl = document.getElementById('acm-edit-category');
        const prioEl = document.getElementById('acm-edit-priority');
        const statusEl = document.getElementById('acm-edit-status');
        if (!idEl || !titleEl || !catEl || !prioEl || !statusEl) return;
        idEl.value = String(item.id);
        titleEl.value = String(item.title || '');
        catEl.value = String(item.category || 'commercial');
        prioEl.value = String(item.priority || 'medium');
        statusEl.value = String(item.status || 'todo');
        openModal('action-editor');
    }

    function renderRankedList(containerId, items, labelKey, countKey) {
        const el = document.getElementById(containerId);
        if (!el) return;
        if (!items || !items.length) {
            el.innerHTML = '<li class="acm-muted">Aucune donnée.</li>';
            return;
        }
        el.innerHTML = items.slice(0, 15).map((row) => {
            const lab = row[labelKey] || '—';
            const c = Number(row[countKey] || 0);
            return `<li><span class="acm-rank-label">${escapeHtml(String(lab))}</span><span class="acm-rank-count">${c.toLocaleString('fr-FR')}</span></li>`;
        }).join('');
    }

    function renderSecteursFromPar(parSecteur) {
        const arr = Object.entries(parSecteur || {})
            .filter(([k]) => k)
            .map(([secteur, count]) => ({ secteur, count }))
            .sort((a, b) => (b.count || 0) - (a.count || 0));
        renderRankedList('acm-list-secteurs', arr, 'secteur', 'count');
    }

    function renderPriorityTable(rows) {
        const tbody = document.querySelector('#acm-priority-table tbody');
        if (!tbody) return;
        if (!rows || !rows.length) {
            tbody.innerHTML = '<tr><td colspan="5">Aucun prospect prioritaire (forte opportunité, hors gagné/perdu).</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map((r) => {
            const id = r.id;
            const nom = escapeHtml(r.nom || '—');
            const sec = escapeHtml(r.secteur || '—');
            const opp = escapeHtml(r.opportunite || '—');
            const st = escapeHtml(r.statut || '—');
            const url = id ? `/entreprise/${id}` : '#';
            return `<tr>
                <td><a href="${url}">${nom}</a></td>
                <td>${sec}</td>
                <td>${opp}</td>
                <td>${st}</td>
                <td><a class="acm-table-action" href="${url}">Fiche</a></td>
            </tr>`;
        }).join('');
    }

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function destroyChart(key) {
        if (charts[key]) {
            charts[key].destroy();
            charts[key] = null;
        }
    }

    function showSnackbar(message) {
        const el = document.getElementById('acm-snackbar');
        if (!el) return;
        el.textContent = message;
        el.hidden = false;
        el.classList.add('is-visible');
        window.clearTimeout(el._snackTimer);
        el._snackTimer = window.setTimeout(() => {
            el.classList.remove('is-visible');
            window.setTimeout(() => { el.hidden = true; }, 180);
        }, 2600);
    }

    function openModal(name) {
        const modal = document.querySelector(`[data-acm-modal="${name}"]`);
        const backdrop = document.querySelector('.acm-modal-backdrop');
        if (!modal || !backdrop) return;
        backdrop.hidden = false;
        modal.hidden = false;
        requestAnimationFrame(() => {
            backdrop.classList.add('is-visible');
            modal.classList.add('is-visible');
        });
        document.body.classList.add('acm-modal-open');
    }

    function closeModals() {
        const backdrop = document.querySelector('.acm-modal-backdrop');
        document.querySelectorAll('.acm-modal.is-visible').forEach((m) => m.classList.remove('is-visible'));
        if (backdrop) backdrop.classList.remove('is-visible');
        window.setTimeout(() => {
            if (backdrop) backdrop.hidden = true;
            document.querySelectorAll('.acm-modal').forEach((m) => { m.hidden = true; });
            document.body.classList.remove('acm-modal-open');
        }, 170);
    }

    function addRipple(evt) {
        const target = evt.currentTarget;
        if (!target || target.classList.contains('acm-no-ripple')) return;
        const rect = target.getBoundingClientRect();
        const r = document.createElement('span');
        r.className = 'acm-ripple';
        const size = Math.max(rect.width, rect.height);
        r.style.width = `${size}px`;
        r.style.height = `${size}px`;
        r.style.left = `${evt.clientX - rect.left - (size / 2)}px`;
        r.style.top = `${evt.clientY - rect.top - (size / 2)}px`;
        target.appendChild(r);
        window.setTimeout(() => r.remove(), 480);
    }

    function buildBarChart(canvasId, labels, data, label, color, onClickFilter) {
        const ctx = document.getElementById(canvasId);
        if (!ctx || typeof Chart === 'undefined') return;
        const theme = getChartTheme();
        destroyChart(canvasId);
        charts[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label,
                    data,
                    backgroundColor: color || theme.navy,
                    borderRadius: 6,
                    borderSkipped: false,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: true },
                },
                scales: {
                    x: {
                        ticks: { color: theme.textColor, maxRotation: 45, minRotation: 0 },
                        grid: { display: false },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: theme.textColor },
                        grid: { color: theme.gridColor },
                    },
                },
                onClick: onClickFilter
                    ? (e, elements) => {
                        if (!elements.length) return;
                        const idx = elements[0].index;
                        onClickFilter(labels[idx]);
                    }
                    : undefined,
            },
        });
    }

    function buildGaugeChart(canvasId, value0to100, label) {
        const ctx = document.getElementById(canvasId);
        if (!ctx || typeof Chart === 'undefined') return;
        const v = Math.max(0, Math.min(100, Number(value0to100) || 0));
        const rest = 100 - v;
        const theme = getChartTheme();
        destroyChart(canvasId);
        charts[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: [label, ''],
                datasets: [{
                    data: [v, rest],
                    backgroundColor: [theme.navy, theme.isDark ? 'rgba(51,65,85,0.55)' : '#e2e8f0'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                rotation: -90,
                circumference: 180,
                cutout: '72%',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label(ctx) {
                                if (ctx.dataIndex === 0) return ` ${v} % (friction pipeline)`;
                                return '';
                            },
                        },
                    },
                },
            },
        });
    }

    function buildDonut(canvasId, labels, data, colors) {
        const ctx = document.getElementById(canvasId);
        if (!ctx || typeof Chart === 'undefined') return;
        const theme = getChartTheme();
        destroyChart(canvasId);
        charts[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: theme.isDark ? '#0f172a' : '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: theme.textColor, boxWidth: 12 },
                    },
                },
            },
        });
    }

    function buildStackedEtapes(labels, data) {
        const ctx = document.getElementById('chart-acm-etapes');
        if (!ctx || typeof Chart === 'undefined') return;
        const theme = getChartTheme();
        destroyChart('chart-acm-etapes');
        charts['chart-acm-etapes'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Répartition'],
                datasets: labels.map((lab, i) => ({
                    label: lab,
                    data: [data[i]],
                    backgroundColor: ['#1e3a5f', '#2563eb', '#0d9488', '#d97706', '#7c3aed', '#64748b'][i % 6],
                    borderRadius: 4,
                })),
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: { color: theme.textColor },
                        grid: { color: theme.gridColor },
                    },
                    y: {
                        stacked: true,
                        ticks: { color: theme.textColor },
                        grid: { display: false },
                    },
                },
                plugins: {
                    legend: { position: 'bottom', labels: { color: theme.textColor } },
                },
            },
        });
    }

    function buildQuarterlyChart(rows) {
        const ctx = document.getElementById('chart-acm-trimestres');
        if (!ctx || typeof Chart === 'undefined') return;
        const sorted = [...(rows || [])]
            .filter((r) => r && r.periode)
            .sort((a, b) => String(a.periode).localeCompare(String(b.periode)));
        if (!sorted.length) {
            destroyChart('chart-acm-trimestres');
            return;
        }
        const labels = sorted.map((r) => r.periode);
        const nouvelles = sorted.map((r) => Number(r.nouvelles) || 0);
        const gagnes = sorted.map((r) => Number(r.gagnes) || 0);
        const theme = getChartTheme();
        destroyChart('chart-acm-trimestres');
        charts['chart-acm-trimestres'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Nouvelles fiches (date_analyse)',
                        data: nouvelles,
                        backgroundColor: theme.navy,
                        borderRadius: 6,
                        borderSkipped: false,
                    },
                    {
                        label: 'Gagnés',
                        data: gagnes,
                        backgroundColor: '#0d9488',
                        borderRadius: 6,
                        borderSkipped: false,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: theme.textColor },
                    },
                },
                scales: {
                    x: {
                        ticks: { color: theme.textColor, maxRotation: 45, minRotation: 0 },
                        grid: { display: false },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: theme.textColor },
                        grid: { color: theme.gridColor },
                    },
                },
            },
        });
    }

    async function load() {
        const root = document.querySelector('.acm-page');
        if (!root) return;

        document.body.classList.add('acm-loading');
        try {
            const stats = await fetchStatistics();
            if (!stats || stats.error) {
                // eslint-disable-next-line no-console
                console.error('Stats marché:', stats && stats.error);
                return;
            }

            const parStatut = stats.par_statut || {};
            const parOpp = stats.par_opportunite || {};
            const parSecteur = stats.par_secteur || {};
            const parEtape = stats.par_etape_prospection || {};
            const total = Number(stats.total_entreprises || 0);
            const actifs = Object.entries(parStatut)
                .filter(([s]) => s && s !== 'Perdu')
                .reduce((a, [, c]) => a + (Number(c) || 0), 0);
            const gagne = Number(parStatut['Gagné'] || 0);
            const conversion = total > 0 ? (100 * gagne) / total : 0;
            const friction = computeFriction(parStatut);
            const highOpp = countHighOpportunity(parOpp);

            setNumber('acm-kpi-total', total);
            setText('acm-kpi-conv', `${conversion.toFixed(1)} %`);
            setNumber('acm-kpi-highopp', highOpp);
            setText('acm-kpi-friction', `${friction} %`);
            setText('acm-kpi-friction-label', friction >= 50 ? 'Élevée' : friction >= 25 ? 'Modérée' : 'Faible');

            setNumber('acm-card-pipeline', actifs);
            setNumber('acm-card-email', Number(stats.entreprises_avec_email || 0));

            setNumber('acm-inline-emails', Number(stats.emails_envoyes || 0));
            setText('acm-inline-open', `${Number(stats.open_rate || 0).toFixed(1)} %`);
            setText('acm-inline-click', `${Number(stats.click_rate || 0).toFixed(1)} %`);

            setText('acm-src-label', currentDaysFilter
                ? `Période : ${currentDaysFilter} derniers jours (emails, campagnes, feuille Excel).`
                : 'Vue globale — toutes les données en base (export Excel = synthèse complète).');

            renderGeoResume(stats.geo_resume || {});
            renderHbarMotifs('acm-pays-motifs', stats.par_pays || {}, 12, 'Aucun pays renseigné sur les fiches.');
            renderPaysTable(stats.par_pays || {}, total);
            buildQuarterlyChart(stats.evolution_trimestrielle || []);

            const xlsxA = document.getElementById('acm-export-xlsx');
            if (xlsxA) {
                const q = currentDaysFilter ? `?days=${encodeURIComponent(currentDaysFilter)}` : '';
                xlsxA.href = `/api/market-concurrence/export${q}`;
            }

            renderOpportunityBand(parOpp, total);
            renderOpportunityTable(parOpp, total);
            renderSecteurMotifs(parSecteur);

            const theme = getChartTheme();
            buildGaugeChart('chart-acm-gauge', friction, 'Friction');

            const sectEntries = Object.entries(parSecteur).filter(([k]) => k).sort((a, b) => (b[1] || 0) - (a[1] || 0)).slice(0, 8);
            if (sectEntries.length) {
                buildBarChart(
                    'chart-acm-secteurs',
                    sectEntries.map(([k]) => k),
                    sectEntries.map(([, v]) => v),
                    'Prospects',
                    theme.navy,
                    (secteur) => {
                        window.location.href = `/entreprises?${new URLSearchParams({ secteur }).toString()}`;
                    },
                );
            } else {
                destroyChart('chart-acm-secteurs');
            }

            const oppEntries = Object.entries(parOpp).filter(([k]) => k).sort((a, b) => (b[1] || 0) - (a[1] || 0)).slice(0, 8);
            if (oppEntries.length) {
                buildBarChart(
                    'chart-acm-opportunites',
                    oppEntries.map(([k]) => k),
                    oppEntries.map(([, v]) => v),
                    'Effectifs',
                    theme.navyLight,
                    (opportunite) => {
                        window.location.href = `/entreprises?${new URLSearchParams({ opportunite }).toString()}`;
                    },
                );
            } else {
                destroyChart('chart-acm-opportunites');
            }

            const stEntries = Object.entries(parStatut).filter(([k]) => k).sort((a, b) => (b[1] || 0) - (a[1] || 0));
            const colors = ['#22c55e', '#3b82f6', '#f59e0b', '#a855f7', '#64748b', '#ef4444', '#06b6d4'];
            if (stEntries.length) {
                buildDonut(
                    'chart-acm-statuts',
                    stEntries.map(([k]) => k),
                    stEntries.map(([, v]) => v),
                    stEntries.map((_, i) => colors[i % colors.length]),
                );
            } else {
                destroyChart('chart-acm-statuts');
            }

            const env = Number(stats.emails_envoyes || 0);
            const opn = Number(stats.emails_ouverts || 0);
            const clk = Number(stats['emails_cliqués'] || stats.emails_cliques || 0);
            buildBarChart(
                'chart-acm-emails',
                ['Envoyés', 'Ouverts', 'Cliqués'],
                [env, opn, clk],
                'Emails',
                '#0d9488',
                null,
            );

            const etEntries = Object.entries(parEtape).filter(([k]) => k).sort((a, b) => (b[1] || 0) - (a[1] || 0)).slice(0, 6);
            const etCanvas = document.getElementById('chart-acm-etapes');
            const etFallback = document.querySelector('[data-acm-etapes-fallback]');
            if (etEntries.length) {
                if (etCanvas) etCanvas.style.display = 'block';
                if (etFallback) etFallback.hidden = true;
                buildStackedEtapes(etEntries.map(([k]) => k), etEntries.map(([, v]) => v));
            } else {
                destroyChart('chart-acm-etapes');
                if (etCanvas) etCanvas.style.display = 'none';
                if (etFallback) etFallback.hidden = false;
            }

            renderRankedList('acm-list-tags', stats.top_tags || [], 'tag', 'count');
            renderSecteursFromPar(parSecteur);
            renderPriorityTable(stats.priority_prospects || []);
            renderRoadmapMetrics({
                highOpp,
                friction,
                emailsEnvoyes: env,
                priorityCount: (stats.priority_prospects || []).length,
                secteurCount: Object.keys(parSecteur || {}).length,
                tagCount: (stats.top_tags || []).length,
            });
            await refreshRoadmapActions();
        } catch (e) {
            // eslint-disable-next-line no-console
            console.error(e);
        } finally {
            document.body.classList.remove('acm-loading');
        }
    }

    function bindPeriod() {
        document.querySelectorAll('.acm-period-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.acm-period-btn').forEach((b) => b.classList.remove('active'));
                btn.classList.add('active');
                currentDaysFilter = btn.getAttribute('data-days') || '';
                load();
            });
        });
    }

    function bindTabs() {
        const tabs = document.querySelectorAll('.acm-tab');
        const panels = document.querySelectorAll('.acm-tab-panel');
        tabs.forEach((tab) => {
            tab.addEventListener('click', () => {
                const target = tab.getAttribute('data-tab');
                tabs.forEach((t) => {
                    t.classList.toggle('active', t.getAttribute('data-tab') === target);
                    t.setAttribute('aria-selected', t.getAttribute('data-tab') === target ? 'true' : 'false');
                });
                panels.forEach((p) => {
                    p.hidden = p.getAttribute('data-tab-panel') !== target;
                });
            });
        });
    }

    function bindMaterialUX() {
        document.querySelectorAll('.acm-btn, .acm-roadmap-btn, .acm-step-card, .acm-tab, .acm-fab').forEach((btn) => {
            btn.classList.add('acm-ripple-host');
            btn.addEventListener('pointerdown', addRipple);
        });
    }

    function bindRoadmapSearch() {
        const input = document.getElementById('acm-roadmap-search');
        if (!input) return;
        input.addEventListener('input', () => {
            currentRoadmapSearchQuery = input.value;
            renderRoadmapActionsList(roadmapRowsCache);
        });
    }

    document.getElementById('acm-refresh')?.addEventListener('click', () => load());
    document.getElementById('acm-export-print')?.addEventListener('click', () => window.print());
    document.getElementById('acm-roadmap-refresh')?.addEventListener('click', () => refreshRoadmapActions());
    document.getElementById('acm-save-action-edit')?.addEventListener('click', async () => {
        const id = Number(document.getElementById('acm-edit-action-id')?.value || 0);
        const title = document.getElementById('acm-edit-title')?.value || '';
        const category = document.getElementById('acm-edit-category')?.value || 'commercial';
        const priority = document.getElementById('acm-edit-priority')?.value || 'medium';
        const status = document.getElementById('acm-edit-status')?.value || 'todo';
        if (!id || !title.trim()) {
            showSnackbar('Titre requis');
            return;
        }
        try {
            await updateRoadmapAction(id, { title: title.trim(), category, priority, status });
            closeModals();
            await refreshRoadmapActions();
            showSnackbar('Action mise à jour');
        } catch (e) {
            showSnackbar(e && e.message ? e.message : 'Erreur de mise à jour');
        }
    });

    document.addEventListener('click', async (evt) => {
        const modalOpenBtn = evt.target.closest('[data-acm-modal-open]');
        if (modalOpenBtn) {
            const name = modalOpenBtn.getAttribute('data-acm-modal-open');
            if (name) openModal(name);
            return;
        }
        if (evt.target.closest('[data-acm-modal-close]')) {
            closeModals();
            return;
        }

        const createBtn = evt.target.closest('[data-roadmap-create]');
        if (createBtn) {
            const pillar = createBtn.getAttribute('data-roadmap-create');
            try {
                createBtn.disabled = true;
                await createRoadmapAction(pillar);
                await refreshRoadmapActions();
                showSnackbar('Action roadmap créée');
            } catch (e) {
                showSnackbar(e && e.message ? e.message : 'Erreur de création');
            } finally {
                createBtn.disabled = false;
            }
            return;
        }

        const statusBtn = evt.target.closest('[data-roadmap-status]');
        if (statusBtn) {
            const actionId = Number(statusBtn.getAttribute('data-roadmap-status'));
            const next = statusBtn.getAttribute('data-next');
            if (!actionId || !next) return;
            try {
                statusBtn.disabled = true;
                await updateRoadmapAction(actionId, { status: next });
                await refreshRoadmapActions();
                showSnackbar('Statut action mis à jour');
            } catch (e) {
                showSnackbar(e && e.message ? e.message : 'Erreur de mise à jour');
            } finally {
                statusBtn.disabled = false;
            }
        }

        const menuBtn = evt.target.closest('[data-roadmap-menu]');
        if (menuBtn) {
            const id = menuBtn.getAttribute('data-roadmap-menu');
            const panel = document.querySelector(`[data-roadmap-menu-panel="${id}"]`);
            document.querySelectorAll('.acm-roadmap-menu').forEach((p) => { if (p !== panel) p.hidden = true; });
            if (panel) panel.hidden = !panel.hidden;
            return;
        }

        const editBtn = evt.target.closest('[data-roadmap-edit]');
        if (editBtn) {
            openActionEditor(editBtn.getAttribute('data-roadmap-edit'));
            return;
        }

        const dupBtn = evt.target.closest('[data-roadmap-duplicate]');
        if (dupBtn) {
            const actionId = Number(dupBtn.getAttribute('data-roadmap-duplicate'));
            const item = (roadmapRowsCache || []).find((r) => Number(r.id) === actionId);
            if (!item) return;
            try {
                await fetch('/api/market-concurrence/roadmap-actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        pillar: item.pillar,
                        category: item.category || 'commercial',
                        title: `${item.title || 'Action'} (copie)`,
                        description: item.description || '',
                        priority: item.priority || 'medium',
                    }),
                });
                await refreshRoadmapActions();
                showSnackbar('Action dupliquée');
            } catch (e) {
                showSnackbar('Duplication impossible');
            }
            return;
        }

        const reactBtn = evt.target.closest('[data-roadmap-reactivate]');
        if (reactBtn) {
            const actionId = Number(reactBtn.getAttribute('data-roadmap-reactivate'));
            if (!actionId) return;
            try {
                await updateRoadmapAction(actionId, { status: 'todo' });
                await refreshRoadmapActions();
                showSnackbar('Action réactivée');
            } catch (e) {
                showSnackbar('Réactivation impossible');
            }
            return;
        }

        const filterBtn = evt.target.closest('[data-roadmap-filter-category]');
        if (filterBtn) {
            currentRoadmapCategoryFilter = filterBtn.getAttribute('data-roadmap-filter-category') || '';
            document.querySelectorAll('[data-roadmap-filter-category]').forEach((b) => b.classList.remove('active'));
            filterBtn.classList.add('active');
            renderRoadmapActionsList(roadmapRowsCache);
        }

        const filterStatusBtn = evt.target.closest('[data-roadmap-filter-status]');
        if (filterStatusBtn) {
            currentRoadmapStatusFilter = filterStatusBtn.getAttribute('data-roadmap-filter-status') || '';
            document.querySelectorAll('[data-roadmap-filter-status]').forEach((b) => b.classList.remove('active'));
            filterStatusBtn.classList.add('active');
            await refreshRoadmapActions();
            return;
        }

        const filterPriorityBtn = evt.target.closest('[data-roadmap-filter-priority]');
        if (filterPriorityBtn) {
            currentRoadmapPriorityFilter = filterPriorityBtn.getAttribute('data-roadmap-filter-priority') || '';
            document.querySelectorAll('[data-roadmap-filter-priority]').forEach((b) => b.classList.remove('active'));
            filterPriorityBtn.classList.add('active');
            await refreshRoadmapActions();
            return;
        }

        if (!evt.target.closest('.acm-roadmap-menu')) {
            document.querySelectorAll('.acm-roadmap-menu').forEach((p) => { p.hidden = true; });
        }
    });

    document.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape') closeModals();
    });

    bindPeriod();
    bindTabs();
    bindMaterialUX();
    bindRoadmapSearch();

    document.addEventListener('DOMContentLoaded', () => {
        load();
    });

    document.querySelector('.theme-toggle-btn')?.addEventListener('click', () => {
        setTimeout(load, 280);
    });
})();
