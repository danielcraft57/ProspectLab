/**
 * Nouveau dashboard ProspectLab
 * KPIs pipeline + performance emailing + campagnes récentes
 */

(function() {
    let currentDaysFilter = '';
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

            setNumber('stat-total-entreprises', totalEntreprises);
            setNumber('stat-actifs', actifs);
            setNumber('stat-gagnes', totalGagnes);
            setPercent('stat-conversion', conversion);

            setNumber('stat-emails-envoyes', stats.emails_envoyes || 0);
            setPercent('stat-open-rate', stats.open_rate || 0);
            setPercent('stat-click-rate', stats.click_rate || 0);

            createStatutsChart(parStatut);
            createSecteursChart(stats.par_secteur || {});
            createEmailsChart({
                envoyes: stats.emails_envoyes || 0,
                ouverts: stats.emails_ouverts || 0,
                cliques: stats['emails_cliqués'] || stats.emails_cliques || 0
            });
            createSecteursGagnesChart(stats.secteurs_gagnes || []);

            renderRecentGagnes(stats.recent_gagnes || []);
            renderRecentCampagnes(stats.recent_campagnes || []);
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error('Erreur lors du chargement des statistiques:', error);
        }
    }

    function setNumber(id, value) {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = (value || 0).toLocaleString('fr-FR');
    }

    function setPercent(id, value) {
        const el = document.getElementById(id);
        if (!el) return;
        const v = Number.isFinite(value) ? value : 0;
        el.textContent = `${v.toFixed(1)} %`;
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

        new Chart(ctx, {
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

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setupPeriodSwitch();
            loadStatistics();
        });
    } else {
        setupPeriodSwitch();
        loadStatistics();
    }
})();

