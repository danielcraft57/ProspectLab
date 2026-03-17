/**
 * Nouveau dashboard ProspectLab
 * KPIs pipeline + performance emailing + campagnes récentes
 */

(function() {
    let currentDaysFilter = '';
    const charts = {};

    function getChartThemeOptions() {
        const isDark = document.body.getAttribute('data-theme') === 'dark';
        const textColor = isDark ? '#e2e8f0' : '#666';
        return {
            textColor,
            legend: {
                labels: { color: textColor }
            }
        };
    }

    async function loadStatistics() {
        try {
            document.body.classList.add('dashboard-loading');
            const query = currentDaysFilter ? `?days=${encodeURIComponent(currentDaysFilter)}` : '';
            const response = await fetch(`/api/statistics${query}`);
            const stats = await response.json();

            // Sécurité basique
            if (!stats || stats.error) {
                // eslint-disable-next-line no-console
                console.error('Erreur stats dashboard:', stats && stats.error);
                return;
            }

            const parStatut = stats.par_statut || {};
            const totalEntreprises = stats.total_entreprises || 0;

            const actifs = Object.entries(parStatut)
                .filter(([statut]) => statut && statut !== 'Perdu')
                .reduce((acc, [, count]) => acc + (count || 0), 0);
            const totalGagnes = parStatut['Gagné'] || 0;
            const conversion = totalEntreprises > 0
                ? ((totalGagnes / totalEntreprises) * 100)
                : 0;

            setNumber('stat-total-entreprises', totalEntreprises, true);
            setNumber('stat-actifs', actifs, true);
            setNumber('stat-gagnes', totalGagnes, true);
            setPercent('stat-conversion', conversion, true);

            setNumber('stat-emails-envoyes', stats.emails_envoyes || 0, true);
            setPercent('stat-open-rate', stats.open_rate || 0, true);
            setPercent('stat-click-rate', stats.click_rate || 0, true);

            createStatutsChart(parStatut);
            createSecteursChart(stats.par_secteur || {});
            createEmailsChart({
                envoyes: stats.emails_envoyes || 0,
                ouverts: stats.emails_ouverts || 0,
                cliques: stats['emails_cliqués'] || stats.emails_cliques || 0
            });
            createSecteursGagnesChart(stats.secteurs_gagnes || []);
            createOpportunitesChart(stats.par_opportunite || {});
            renderTopTags(stats.top_tags || []);

            renderRecentGagnes(stats.recent_gagnes || []);
            renderRecentCampagnes(stats.recent_campagnes || []);
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error('Erreur lors du chargement des statistiques:', error);
        } finally {
            document.body.classList.remove('dashboard-loading');
        }
    }

    function setNumber(id, value, animate = false) {
        const el = document.getElementById(id);
        if (!el) return;
        const v = Number(value || 0);
        if (!animate) {
            el.textContent = v.toLocaleString('fr-FR');
            el.dataset.value = String(v);
            return;
        }
        animateValue(el, Number(el.dataset.value || 0), v, (n) => n.toLocaleString('fr-FR'));
    }

    function setPercent(id, value, animate = false) {
        const el = document.getElementById(id);
        if (!el) return;
        const v = Number.isFinite(value) ? value : 0;
        if (!animate) {
            el.textContent = `${v.toFixed(1)} %`;
            el.dataset.value = String(v);
            return;
        }
        animateValue(el, Number(el.dataset.value || 0), v, (n) => `${n.toFixed(1)} %`);
    }

    function animateValue(el, from, to, format) {
        const duration = 480;
        const start = performance.now();
        const diff = to - from;
        const isBig = Math.abs(diff) > 2000;
        const rounding = isBig ? 1 : 10; // limiter le jitter sur gros nombres
        const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

        function tick(now) {
            const t = Math.min(1, (now - start) / duration);
            const eased = easeOutCubic(t);
            let current = from + diff * eased;
            if (rounding > 1) current = Math.round(current * rounding) / rounding;
            el.textContent = format(current);
            if (t < 1) requestAnimationFrame(tick);
            else el.dataset.value = String(to);
        }
        requestAnimationFrame(tick);
    }

    function createStatutsChart(parStatut) {
        const ctx = document.getElementById('chart-statuts');
        if (!ctx) return;
        const labels = Object.keys(parStatut || {});
        const data = Object.values(parStatut || {});
        if (!labels.length) {
            ctx.parentElement.innerHTML += '<p>Aucune donnée de statut.</p>';
            return;
        }

        const theme = getChartThemeOptions();

        if (charts.statuts) charts.statuts.destroy();
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: [
                        '#3b82f6', // Nouveau
                        '#facc15', // À qualifier
                        '#fb923c', // Relance
                        '#22c55e', // Gagné
                        '#9ca3af'  // Perdu
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: theme.legend.labels
                    }
                }
            }
        });
        charts.statuts = chart;

        // Clic sur une tranche de statut -> redirection vers la liste filtrée
        ctx.onclick = (evt) => {
            const points = chart.getElementsAtEventForMode(evt, 'nearest', { intersect: true }, true);
            if (!points.length) return;
            const idx = points[0].index;
            const statut = labels[idx];
            if (!statut) return;
            const params = new URLSearchParams({ statut });
            window.location.href = `/entreprises?${params.toString()}`;
        };
    }

    function createSecteursChart(parSecteur) {
        const ctx = document.getElementById('chart-secteurs');
        if (!ctx) return;
        const entries = Object.entries(parSecteur || {});
        if (!entries.length) {
            ctx.parentElement.innerHTML += '<p>Aucune donnée de secteur.</p>';
            return;
        }
        // Garder les 8 principaux secteurs
        const top = entries
            .sort((a, b) => (b[1] || 0) - (a[1] || 0))
            .slice(0, 8);
        const labels = top.map(([label]) => label);
        const data = top.map(([, count]) => count || 0);

        const theme = getChartThemeOptions();

        if (charts.secteurs) charts.secteurs.destroy();
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Entreprises',
                    data,
                    backgroundColor: '#3b82f6'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        labels: theme.legend.labels
                    }
                },
                scales: {
                    x: {
                        ticks: { color: theme.textColor }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: theme.textColor }
                    }
                }
            }
        });
        charts.secteurs = chart;

        // Clic sur une barre de secteur -> liste des entreprises filtrée par secteur
        ctx.onclick = (evt) => {
            const points = chart.getElementsAtEventForMode(evt, 'nearest', { intersect: true }, true);
            if (!points.length) return;
            const idx = points[0].index;
            const secteur = labels[idx];
            if (!secteur) return;
            const params = new URLSearchParams({ secteur });
            window.location.href = `/entreprises?${params.toString()}`;
        };
    }

    function createEmailsChart(values) {
        const ctx = document.getElementById('chart-emails');
        if (!ctx) return;

        const data = [
            Number(values.envoyes || 0),
            Number(values.ouverts || 0),
            Number(values.cliques || 0)
        ];

        if (data.every(v => v === 0)) {
            ctx.parentElement.innerHTML += '<p>Aucune donnée d\'emailing pour le moment.</p>';
            return;
        }

        const theme = getChartThemeOptions();

        if (charts.emails) charts.emails.destroy();
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Envoyés', 'Ouverts', 'Cliqués'],
                datasets: [{
                    label: 'Emails',
                    data,
                    backgroundColor: ['#3b82f6', '#22c55e', '#f97316']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        labels: theme.legend.labels
                    }
                },
                scales: {
                    x: { ticks: { color: theme.textColor } },
                    y: {
                        beginAtZero: true,
                        ticks: { color: theme.textColor }
                    }
                }
            }
        });
        charts.emails = chart;
    }

    function createSecteursGagnesChart(list) {
        const ctx = document.getElementById('chart-secteurs-gagnes');
        if (!ctx) return;
        if (!list || !list.length) {
            ctx.parentElement.innerHTML += '<p>Aucun prospect gagné ne contient de secteur.</p>';
            return;
        }

        const labels = list.map(item => item.secteur || 'Non renseigné');
        const data = list.map(item => item.count || 0);

        const theme = getChartThemeOptions();

        if (charts.secteursGagnes) charts.secteursGagnes.destroy();
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Prospects gagnés',
                    data,
                    backgroundColor: '#22c55e'
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: {
                        labels: theme.legend.labels
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { color: theme.textColor }
                    },
                    y: {
                        ticks: { color: theme.textColor }
                    }
                }
            }
        });
        charts.secteursGagnes = chart;

        // Clic sur secteur gagné -> liste filtrée secteur + statut=Gagné
        ctx.onclick = (evt) => {
            const points = chart.getElementsAtEventForMode(evt, 'nearest', { intersect: true }, true);
            if (!points.length) return;
            const idx = points[0].index;
            const secteur = labels[idx];
            if (!secteur) return;
            const params = new URLSearchParams({ secteur, statut: 'Gagné' });
            window.location.href = `/entreprises?${params.toString()}`;
        };
    }

    function createOpportunitesChart(parOpportunite) {
        const ctx = document.getElementById('chart-opportunites');
        if (!ctx) return;
        const entries = Object.entries(parOpportunite || {});
        if (!entries.length) {
            ctx.parentElement.innerHTML += '<p>Aucune donnée d\'opportunité.</p>';
            return;
        }

        const ordered = entries.sort((a, b) => (b[1] || 0) - (a[1] || 0));
        const labels = ordered.map(([k]) => k);
        const data = ordered.map(([, v]) => v || 0);

        const theme = getChartThemeOptions();

        if (charts.opportunites) charts.opportunites.destroy();
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Prospects',
                    data,
                    backgroundColor: '#8b5cf6'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { labels: theme.legend.labels }
                },
                scales: {
                    x: { ticks: { color: theme.textColor } },
                    y: { beginAtZero: true, ticks: { color: theme.textColor } }
                }
            }
        });
        charts.opportunites = chart;

        ctx.onclick = (evt) => {
            const points = chart.getElementsAtEventForMode(evt, 'nearest', { intersect: true }, true);
            if (!points.length) return;
            const idx = points[0].index;
            const opportunite = labels[idx];
            if (!opportunite) return;
            const params = new URLSearchParams({ opportunite });
            window.location.href = `/entreprises?${params.toString()}`;
        };
    }

    function renderTopTags(list) {
        const container = document.getElementById('top-tags');
        if (!container) return;
        if (!list || !list.length) {
            container.innerHTML = '<p class="dashboard-muted">Aucun tag pour le moment.</p>';
            return;
        }

        container.innerHTML = list.map((item, idx) => {
            const tag = (item && item.tag) ? String(item.tag) : '';
            const count = Number(item && item.count ? item.count : 0);
            const delay = Math.min(240, idx * 18);
            const safeTag = escapeHtml(tag);
            return `
                <button type="button" class="tag-chip" style="animation-delay:${delay}ms" data-tag="${safeTag}">
                    <span class="tag-chip-label">${safeTag}</span>
                    <span class="tag-chip-count">${count.toLocaleString('fr-FR')}</span>
                </button>
            `;
        }).join('');

        container.querySelectorAll('.tag-chip').forEach((btn) => {
            btn.addEventListener('click', () => {
                const tag = btn.dataset.tag || '';
                if (!tag) return;
                const params = new URLSearchParams({ tags_any: tag });
                window.location.href = `/entreprises?${params.toString()}`;
            });
        });
    }

    function escapeHtml(str) {
        return String(str)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function renderRecentGagnes(list) {
        const container = document.getElementById('recent-gagnes');
        if (!container) return;
        if (!list.length) {
            container.innerHTML = '<p>Aucun prospect gagné pour le moment.</p>';
            return;
        }
        container.innerHTML = list.map(item => {
            const date = item.date_analyse
                ? new Date(item.date_analyse).toLocaleDateString('fr-FR')
                : '';
            const secteur = item.secteur || 'Non renseigné';
            const website = item.website
                ? `<a href="${item.website}" target="_blank" rel="noopener noreferrer">${item.website}</a>`
                : '';
            return `
                <div class="dashboard-row">
                    <div class="dashboard-row-main">
                        <div class="dashboard-row-title">${item.nom || 'Sans nom'}</div>
                        <div class="dashboard-row-meta">
                            <span>${secteur}</span>
                            ${date ? `<span>Gagné le ${date}</span>` : ''}
                        </div>
                    </div>
                    <div class="dashboard-row-side">
                        ${website}
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderRecentCampagnes(list) {
        const container = document.getElementById('recent-campagnes');
        if (!container) return;
        if (!list.length) {
            container.innerHTML = '<p>Aucune campagne pour le moment.</p>';
            return;
        }
        container.innerHTML = list.map(item => {
            const date = item.date_creation
                ? new Date(item.date_creation).toLocaleDateString('fr-FR')
                : '';
            const env = item.total_envoyes || item.total_destinataires || 0;
            const reussis = item.total_reussis || 0;
            const taux = env > 0 ? ((reussis / env) * 100).toFixed(1) : '0.0';

            return `
                <div class="dashboard-row">
                    <div class="dashboard-row-main">
                        <div class="dashboard-row-title">${item.nom || 'Sans nom'}</div>
                        <div class="dashboard-row-meta">
                            ${date ? `<span>${date}</span>` : ''}
                            <span>${env} envoyés</span>
                            <span>${reussis} réussis (${taux}%)</span>
                        </div>
                    </div>
                    <div class="dashboard-row-side">
                        <span class="badge badge-secondary">${item.statut || 'N/A'}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    function setupPeriodSwitch() {
        const container = document.querySelector('.dashboard-period-switch');
        if (!container) return;

        container.addEventListener('click', (e) => {
            const btn = e.target.closest('.period-btn');
            if (!btn) return;
            currentDaysFilter = btn.dataset.days || '';

            container.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            loadStatistics();
        });
    }

    function setupStatCards() {
        const mapping = {
            'stat-total-entreprises': '#chart-statuts',
            'stat-actifs': '#chart-statuts',
            'stat-gagnes': '#chart-secteurs-gagnes',
            'stat-conversion': '#chart-secteurs-gagnes',
            'stat-emails-envoyes': '#chart-emails',
            'stat-open-rate': '#chart-emails',
            'stat-click-rate': '#chart-emails',
        };

        document.querySelectorAll('.stat-card').forEach((card) => {
            const numberEl = card.querySelector('.stat-number');
            if (!numberEl || !numberEl.id) return;
            const targetSelector = mapping[numberEl.id];
            if (!targetSelector) return;

            card.classList.add('stat-card-clickable');
            card.addEventListener('click', () => {
                const target = document.querySelector(targetSelector);
                if (!target) return;

                const rect = target.getBoundingClientRect();
                const offset = 90;
                const top = window.scrollY + rect.top - offset;

                window.scrollTo({ top, behavior: 'smooth' });
                target.classList.add('dashboard-highlight');
                setTimeout(() => {
                    target.classList.remove('dashboard-highlight');
                }, 800);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setupPeriodSwitch();
            setupStatCards();
            loadStatistics();
        });
    } else {
        setupPeriodSwitch();
        setupStatCards();
        loadStatistics();
    }
})();

