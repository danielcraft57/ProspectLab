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
        const gridColor = isDark ? 'rgba(148, 163, 184, 0.16)' : 'rgba(148, 163, 184, 0.22)';
        return {
            textColor,
            gridColor,
            legend: {
                labels: { color: textColor }
            }
        };
    }

    function getStatutPalette(statut) {
        const map = {
            'À qualifier': '#facc15',
            'Relance': '#fb923c',
            'Gagné': '#22c55e',
            'Perdu': '#9ca3af',
            'Contacté': '#60a5fa',
            'En cours': '#a78bfa',
        };
        return map[statut] || '#60a5fa';
    }

    async function loadStatistics() {
        try {
            document.body.classList.add('dashboard-loading');
            const stats = await fetchStatistics(currentDaysFilter || '', 0);

            // Sécurité basique
            if (!stats || stats.error) {
                // eslint-disable-next-line no-console
                console.error('Erreur stats dashboard:', stats && stats.error);
                return;
            }

            const parStatut = stats.par_statut || {};
            const currentKpi = computeKpi(stats);
            let previousKpi = null;
            const compareDays = Number.parseInt(currentDaysFilter, 10);
            if (Number.isFinite(compareDays) && compareDays > 0) {
                try {
                    const previousStats = await fetchStatistics(compareDays, compareDays);
                    previousKpi = computeKpi(previousStats);
                } catch (e) {
                    // eslint-disable-next-line no-console
                    console.warn('Comparaison période précédente indisponible:', e);
                }
            }

            setNumber('stat-total-entreprises', currentKpi.totalEntreprises, true);
            setNumber('stat-actifs', currentKpi.actifs, true);
            setNumber('stat-avec-email', currentKpi.entreprisesAvecEmail, true);
            setNumber('stat-gagnes', currentKpi.totalGagnes, true);
            setPercent('stat-conversion', currentKpi.conversion, true);

            setNumber('stat-emails-envoyes', stats.emails_envoyes || 0, true);
            setPercent('stat-open-rate', stats.open_rate || 0, true);
            setPercent('stat-click-rate', stats.click_rate || 0, true);

            setNumber('stat-replies', stats.reponses || 0, true);
            setPercent('stat-reply-rate', stats.reply_rate || 0, true);
            setNumber('stat-rdv', stats.rdv || 0, true);
            setNumber('stat-hot', stats.hot_leads_count || 0, true);

            renderKpiDeltas(currentKpi, previousKpi);
            const insightContext = {
                totalEntreprises: currentKpi.totalEntreprises,
                actifs: currentKpi.actifs,
                totalGagnes: currentKpi.totalGagnes,
                conversion: currentKpi.conversion,
                emailsEnvoyes: stats.emails_envoyes || 0,
                emailsOuverts: stats.emails_ouverts || 0,
                emailsCliques: stats['emails_cliqués'] || stats.emails_cliques || 0,
                openRate: stats.open_rate || 0,
                clickRate: stats.click_rate || 0,
                replies: stats.reponses || 0,
                replyRate: stats.reply_rate || 0,
                rdv: stats.rdv || 0,
                hotLeadsCount: stats.hot_leads_count || 0,
                favoris: stats.favoris || 0,
                totalAnalyses: stats.total_analyses || 0,
                totalCampagnes: stats.total_campagnes || 0,
                parStatut,
                crmFunnel: stats.crm_funnel || [],
                hotLeads: stats.hot_leads || [],
                parOpportunite: stats.par_opportunite || {},
                parSecteur: stats.par_secteur || {},
                topTags: stats.top_tags || [],
                secteursGagnes: stats.secteurs_gagnes || [],
                recentCampagnes: stats.recent_campagnes || [],
                recentGagnes: stats.recent_gagnes || []
            };
            renderDashboardInsights(insightContext);
            renderDashboardAnalysis(insightContext);

            createStatutsChart(parStatut);
            createOpportunitesChart(stats.par_opportunite || {});
            createEmailsChart({
                envoyes: stats.emails_envoyes || 0,
                ouverts: stats.emails_ouverts || 0,
                cliques: stats['emails_cliqués'] || stats.emails_cliques || 0
            });
            createSecteursGagnesChart(stats.secteurs_gagnes || []);
            renderTopTags(stats.top_tags || []);

            renderRecentGagnes(stats.recent_gagnes || []);
            renderRecentCampagnes(stats.recent_campagnes || []);

            createCrmFunnelChart(stats.crm_funnel || []);
            renderHotLeads(stats.hot_leads || []);
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error('Erreur lors du chargement des statistiques:', error);
        } finally {
            document.body.classList.remove('dashboard-loading');
        }
    }

    async function fetchStatistics(days = '', offsetDays = 0) {
        const params = new URLSearchParams();
        const d = Number.parseInt(days, 10);
        if (Number.isFinite(d) && d > 0) {
            params.set('days', String(d));
        }
        const off = Number.parseInt(offsetDays, 10);
        if (Number.isFinite(off) && off > 0) {
            params.set('offset_days', String(off));
        }
        const qs = params.toString();
        const response = await fetch(`/api/statistics${qs ? `?${qs}` : ''}`);
        return await response.json();
    }

    function computeKpi(stats) {
        const parStatut = stats.par_statut || {};
        const totalEntreprises = Number(stats.total_entreprises || 0);
        const actifs = Object.entries(parStatut)
            .filter(([statut]) => statut && statut !== 'Perdu')
            .reduce((acc, [, count]) => acc + (count || 0), 0);
        const totalGagnes = Number(parStatut['Gagné'] || 0);
        const conversion = totalEntreprises > 0
            ? ((totalGagnes / totalEntreprises) * 100)
            : 0;
        return {
            totalEntreprises,
            actifs,
            entreprisesAvecEmail: Number(stats.entreprises_avec_email || 0),
            totalGagnes,
            conversion,
            emailsEnvoyes: Number(stats.emails_envoyes || 0),
            openRate: Number(stats.open_rate || 0),
            clickRate: Number(stats.click_rate || 0)
        };
    }

    function renderKpiDeltas(currentKpi, previousKpi) {
        const setDelta = (id, value, mode = 'number') => {
            const el = document.getElementById(`${id}-delta`);
            if (!el) return;
            if (value === null || value === undefined || Number.isNaN(value)) {
                el.textContent = '';
                el.classList.remove('is-positive', 'is-negative');
                return;
            }
            const sign = value > 0 ? '+' : '';
            const absValue = Math.abs(value);
            const formatted = mode === 'percent'
                ? `${sign}${value.toFixed(1)} pt`
                : `${sign}${value.toLocaleString('fr-FR')}`;
            el.textContent = `${formatted} vs période précédente`;
            el.classList.toggle('is-positive', value > 0);
            el.classList.toggle('is-negative', value < 0);
        };

        if (!previousKpi) {
            ['stat-total-entreprises', 'stat-actifs', 'stat-gagnes', 'stat-conversion', 'stat-emails-envoyes', 'stat-open-rate', 'stat-click-rate']
                .concat(['stat-avec-email'])
                .forEach((id) => setDelta(id, null));
            return;
        }

        setDelta('stat-total-entreprises', currentKpi.totalEntreprises - previousKpi.totalEntreprises);
        setDelta('stat-actifs', currentKpi.actifs - previousKpi.actifs);
        setDelta('stat-avec-email', currentKpi.entreprisesAvecEmail - previousKpi.entreprisesAvecEmail);
        setDelta('stat-gagnes', currentKpi.totalGagnes - previousKpi.totalGagnes);
        setDelta('stat-conversion', currentKpi.conversion - previousKpi.conversion, 'percent');
        setDelta('stat-emails-envoyes', currentKpi.emailsEnvoyes - previousKpi.emailsEnvoyes);
        setDelta('stat-open-rate', currentKpi.openRate - previousKpi.openRate, 'percent');
        setDelta('stat-click-rate', currentKpi.clickRate - previousKpi.clickRate, 'percent');
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
        const allEntries = Object.entries(parStatut || {})
            .filter(([label, count]) => !!label && (count || 0) > 0);
        // Par défaut on retire "Nouveau" pour mieux lire les statuts réellement travaillés.
        // Fallback: si cela vide le graphe, on réaffiche tout (incluant Nouveau).
        const entries = (allEntries.filter(([label]) => label !== 'Nouveau').length > 0
            ? allEntries.filter(([label]) => label !== 'Nouveau')
            : allEntries
        ).sort((a, b) => (b[1] || 0) - (a[1] || 0));
        const labels = entries.map(([label]) => label);
        const data = entries.map(([, count]) => count || 0);
        if (!labels.length) {
            ctx.parentElement.innerHTML += '<p>Aucune donnée de statut.</p>';
            return;
        }

        const theme = getChartThemeOptions();

        if (charts.statuts) charts.statuts.destroy();
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: labels.map(getStatutPalette),
                    borderWidth: 0,
                    borderRadius: 10,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false,
                        labels: theme.legend.labels
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { color: theme.textColor },
                        grid: { color: theme.gridColor }
                    },
                    y: {
                        ticks: { color: theme.textColor },
                        grid: { display: false }
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
                    backgroundColor: ['rgba(99, 102, 241, 0.9)', 'rgba(14, 165, 233, 0.9)', 'rgba(16, 185, 129, 0.9)'],
                    borderRadius: 10,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: theme.legend.labels
                    }
                },
                scales: {
                    x: { ticks: { color: theme.textColor }, grid: { display: false } },
                    y: {
                        beginAtZero: true,
                        ticks: { color: theme.textColor },
                        grid: { color: theme.gridColor }
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
                    backgroundColor: 'rgba(16, 185, 129, 0.9)',
                    borderRadius: 10,
                    borderSkipped: false
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: theme.legend.labels
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { color: theme.textColor },
                        grid: { color: theme.gridColor }
                    },
                    y: {
                        ticks: { color: theme.textColor },
                        grid: { display: false }
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

    function createCrmFunnelChart(funnel) {
        const ctx = document.getElementById('chart-crm-funnel');
        if (!ctx) return;
        const items = Array.isArray(funnel) ? funnel : [];
        if (!items.length || items.every(i => Number(i.count || 0) === 0)) {
            ctx.parentElement.innerHTML += '<p>Aucune donnée CRM (etape_prospection).</p>';
            return;
        }

        const labels = items.map(i => i.etape);
        const data = items.map(i => Number(i.count || 0));

        const theme = getChartThemeOptions();
        const colors = ['#64748b', '#2563eb', '#9333ea', '#ea580c', '#16a34a', '#dc2626'];

        if (charts.crmFunnel) charts.crmFunnel.destroy();
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Prospects',
                    data,
                    backgroundColor: labels.map((_, idx) => colors[idx] || 'rgba(99, 102, 241, 0.9)'),
                    borderRadius: 10,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: theme.legend.labels }
                },
                scales: {
                    x: { ticks: { color: theme.textColor }, grid: { display: false } },
                    y: { beginAtZero: true, ticks: { color: theme.textColor }, grid: { color: theme.gridColor } }
                }
            }
        });
        charts.crmFunnel = chart;
    }

    function renderHotLeads(list) {
        const container = document.getElementById('hot-leads');
        if (!container) return;
        const items = Array.isArray(list) ? list : [];
        if (!items.length) {
            container.innerHTML = '<p>Aucun clic récent à relancer.</p>';
            return;
        }

        container.innerHTML = items.slice(0, 12).map((it) => {
            const id = it.entreprise_id;
            const name = escapeHtml(it.nom || 'Sans nom');
            const secteur = escapeHtml(it.secteur || 'Secteur n/a');
            const statut = escapeHtml(it.statut || '');
            const etape = escapeHtml(it.etape_prospection || '');
            const clicks = Number(it.clicks || 0);
            const opens = Number(it.opens || 0);
            const lastClick = it.last_click_at ? new Date(it.last_click_at).toLocaleString('fr-FR') : '';
            const meta = [
                clicks ? `${clicks} clic${clicks > 1 ? 's' : ''}` : null,
                opens ? `${opens} ouverture${opens > 1 ? 's' : ''}` : null,
                lastClick ? `dernier clic: ${escapeHtml(lastClick)}` : null,
                statut ? `statut: ${statut}` : null,
                etape ? `CRM: ${etape}` : null
            ].filter(Boolean);

            return `
                <div class="dashboard-row">
                    <div class="dashboard-row-main">
                        <div class="dashboard-row-title"><a href="/entreprise/${encodeURIComponent(String(id))}">${name}</a></div>
                        <div class="dashboard-row-meta"><span>${secteur}</span></div>
                        ${meta.length ? `<div class="hot-lead-badges">${meta.slice(0, 4).map(m => `<span class="hot-lead-badge">${m}</span>`).join('')}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');
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
                    backgroundColor: 'rgba(139, 92, 246, 0.9)',
                    borderRadius: 10,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: theme.legend.labels }
                },
                scales: {
                    x: { ticks: { color: theme.textColor }, grid: { display: false } },
                    y: { beginAtZero: true, ticks: { color: theme.textColor }, grid: { color: theme.gridColor } }
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

    function renderDashboardInsights(metrics) {
        const container = document.getElementById('dashboard-insights-list');
        const section = document.getElementById('dashboard-insights');
        if (!container) return;

        const chips = [];
        const pushChip = (type, label, href, severity = 1) => {
            chips.push({ type, label, href, severity });
        };
        const total = Number(metrics.totalEntreprises || 0);
        const actifs = Number(metrics.actifs || 0);
        const conversion = Number(metrics.conversion || 0);
        const emails = Number(metrics.emailsEnvoyes || 0);
        const openRate = Number(metrics.openRate || 0);
        const clickRate = Number(metrics.clickRate || 0);
        const replies = Number(metrics.replies || 0);
        const replyRate = Number(metrics.replyRate || 0);
        const rdv = Number(metrics.rdv || 0);
        const hotLeadsCount = Number(metrics.hotLeadsCount || 0);
        const favoris = Number(metrics.favoris || 0);
        const totalCampagnes = Number(metrics.totalCampagnes || 0);
        const parStatut = metrics.parStatut || {};
        const parOpportunite = metrics.parOpportunite || {};
        const topTags = Array.isArray(metrics.topTags) ? metrics.topTags : [];
        const relance = Number(parStatut['Relance'] || 0);
        const aRappeler = Number(parStatut['À rappeler'] || 0);
        const percutifs = relance + aRappeler;
        const oppHigh = Number(parOpportunite['Très élevée'] || 0) + Number(parOpportunite['Élevée'] || 0);
        const oppLow = Number(parOpportunite['Très faible'] || 0) + Number(parOpportunite['Faible'] || 0);
        const topTag = topTags.length ? String(topTags[0].tag || '') : '';
        const topTagCount = topTags.length ? Number(topTags[0].count || 0) : 0;

        if (total === 0) {
            pushChip('warning', 'Aucune entreprise en base', '/entreprises', 100);
            pushChip('neutral', 'Ajouter vos premiers prospects', '/entreprises', 70);
        } else {
            pushChip('neutral', `${actifs.toLocaleString('fr-FR')} prospect${actifs > 1 ? 's' : ''} actif${actifs > 1 ? 's' : ''}`, '/entreprises?statut=Nouveau', 20);
            if (actifs > 0) {
                pushChip('neutral', 'Prioriser les statuts Relance et À rappeler', '/entreprises?statut=Relance', 45);
            }
            if (favoris > 0) {
                pushChip('neutral', `${favoris.toLocaleString('fr-FR')} prospects favoris à traiter en priorité`, '/entreprises?favori=true', 35);
            }
        }

        if (emails === 0) {
            pushChip('warning', 'Aucun email envoyé, lancer une campagne', '/campagnes', 95);
            pushChip('neutral', 'Préparer une séquence avec 2 relances', '/campagnes', 55);
        } else {
            pushChip('neutral', `${emails.toLocaleString('fr-FR')} emails envoyés sur la période`, '/campagnes', 20);
            if (openRate < 20) {
                pushChip('warning', `Ouverture faible (${openRate.toFixed(1)}%)`, '/campagnes', 80);
                pushChip('neutral', 'Tester de nouveaux objets d’email (A/B)', '/campagnes', 50);
            } else {
                pushChip('success', `Ouverture correcte (${openRate.toFixed(1)}%)`, '/campagnes', 10);
            }
            if (clickRate < 2) {
                pushChip('warning', `Clics à améliorer (${clickRate.toFixed(1)}%)`, '/campagnes', 75);
                pushChip('neutral', 'Renforcer le CTA et la promesse dans le corps', '/campagnes', 48);
            } else {
                pushChip('success', `Clics engagés (${clickRate.toFixed(1)}%)`, '/campagnes', 10);
            }
        }

        if (emails > 0 && replies === 0) {
            pushChip('warning', '0 réponse: renforcer l\'offre + relances', '/entreprises', 92);
        } else if (replies > 0) {
            pushChip('success', `${replies.toLocaleString('fr-FR')} réponse(s) sur la période`, '/entreprises', 18);
        }

        if (emails > 0 && replyRate > 0) {
            pushChip('neutral', `Taux de réponse ${replyRate.toFixed(1)}%`, '/entreprises', 26);
        }

        if (rdv > 0) {
            pushChip('success', `${rdv.toLocaleString('fr-FR')} RDV (CRM)`, '/entreprises', 18);
        }

        if (hotLeadsCount > 0) {
            pushChip('warning', `${hotLeadsCount.toLocaleString('fr-FR')} prospects chauds à relancer`, '/entreprises?statut=Relance', 74);
        }

        if (conversion <= 0 && total > 0) {
            pushChip('warning', '0 conversion: relancer les prospects chauds', '/entreprises?statut=Relance', 90);
            pushChip('neutral', 'Créer une task de suivi commercial sur les clics', '/entreprises?statut=À+rappeler', 52);
        } else if (conversion > 0) {
            pushChip('success', `Conversion ${conversion.toFixed(1)}%`, '/entreprises?statut=Gagné', 15);
            pushChip('neutral', 'Analyser les prospects gagnés pour dupliquer le pattern', '/entreprises?statut=Gagné', 25);
        }

        if (percutifs > 0) {
            pushChip('warning', `${percutifs.toLocaleString('fr-FR')} prospects chauds (Relance + À rappeler)`, '/entreprises?statut=Relance', 72);
        }

        if (oppHigh > 0) {
            pushChip('success', `${oppHigh.toLocaleString('fr-FR')} opportunités élevées à contacter vite`, '/entreprises?opportunite=Élevée', 22);
        }

        if (oppLow > 0 && oppLow >= oppHigh && total > 0) {
            pushChip('neutral', `Beaucoup d’opportunités faibles (${oppLow.toLocaleString('fr-FR')})`, '/entreprises?opportunite=Très+faible', 42);
        }

        if (topTag && topTagCount > 0) {
            pushChip('neutral', `Tag dominant: ${topTag} (${topTagCount.toLocaleString('fr-FR')})`, `/entreprises?tags_any=${encodeURIComponent(topTag)}`, 15);
        }

        if (totalCampagnes === 0 && total > 0) {
            pushChip('warning', 'Aucune campagne enregistrée: lancer une première séquence', '/campagnes', 88);
        }

        if (total > 0 && actifs === 0) {
            pushChip('warning', 'Aucun prospect actif: vérifier vos statuts pipeline', '/entreprises', 92);
        }

        if (total > 0 && emails > 0 && openRate === 0) {
            pushChip('warning', '0% ouverture: vérifier tracking et délivrabilité', '/campagnes', 94);
        }

        if (total > 0 && emails > 0 && clickRate === 0) {
            pushChip('warning', '0% clic: retravailler offre + CTA', '/campagnes', 90);
        }

        if (!chips.length) {
            container.innerHTML = '<p class="dashboard-muted">Aucun insight disponible.</p>';
            return;
        }

        const dedup = [];
        const seen = new Set();
        chips.forEach((c) => {
            const key = `${c.type}|${c.label}|${c.href}`;
            if (seen.has(key)) return;
            seen.add(key);
            dedup.push(c);
        });

        const topUrgent = dedup
            .filter((c) => (c.severity || 0) >= 70)
            .sort((a, b) => (b.severity || 0) - (a.severity || 0))
            .slice(0, 4);

        if (!topUrgent.length) {
            if (section) section.style.display = 'none';
            return;
        }
        if (section) section.style.display = '';

        container.innerHTML = topUrgent.map((chip) => {
            const tone = chip.type === 'success' ? 'is-success' : (chip.type === 'warning' ? 'is-warning' : 'is-neutral');
            const icon = chip.type === 'success' ? 'fa-check-circle' : (chip.type === 'warning' ? 'fa-triangle-exclamation' : 'fa-lightbulb');
            return `<a class="dashboard-insight-chip ${tone}" href="${chip.href}">
                <i class="fas ${icon}" aria-hidden="true"></i>
                <span>${escapeHtml(chip.label)}</span>
            </a>`;
        }).join('');
    }

    function renderDashboardAnalysis(metrics) {
        const container = document.getElementById('dashboard-analysis-grid');
        const section = document.getElementById('dashboard-analysis');
        if (!container) return;

        const total = Number(metrics.totalEntreprises || 0);
        const actifs = Number(metrics.actifs || 0);
        const conversion = Number(metrics.conversion || 0);
        const emails = Number(metrics.emailsEnvoyes || 0);
        const openRate = Number(metrics.openRate || 0);
        const clickRate = Number(metrics.clickRate || 0);
        const activeRate = total > 0 ? (actifs / total) * 100 : 0;
        const emailsOuverts = Number(metrics.emailsOuverts || 0);
        const emailsCliques = Number(metrics.emailsCliques || 0);
        const totalAnalyses = Number(metrics.totalAnalyses || 0);
        const totalCampagnes = Number(metrics.totalCampagnes || 0);
        const parStatut = metrics.parStatut || {};
        const parOpportunite = metrics.parOpportunite || {};
        const parSecteur = metrics.parSecteur || {};
        const topTags = Array.isArray(metrics.topTags) ? metrics.topTags : [];
        const secteursGagnes = Array.isArray(metrics.secteursGagnes) ? metrics.secteursGagnes : [];
        const relance = Number(parStatut['Relance'] || 0);
        const aRappeler = Number(parStatut['À rappeler'] || 0);
        const perdu = Number(parStatut['Perdu'] || 0);
        const perduRate = total > 0 ? (perdu / total) * 100 : 0;
        const oppHigh = Number(parOpportunite['Très élevée'] || 0) + Number(parOpportunite['Élevée'] || 0);
        const oppLow = Number(parOpportunite['Très faible'] || 0) + Number(parOpportunite['Faible'] || 0);
        const topSecteur = Object.entries(parSecteur).sort((a, b) => (b[1] || 0) - (a[1] || 0))[0];
        const topTag = topTags[0] || null;
        const topWonSector = secteursGagnes[0] || null;

        const blocks = [];
        const pushBlock = (title, text, next, severity = 1) => {
            blocks.push({ title, text, next, severity });
        };
        pushBlock(
            'Lecture du pipeline',
            total === 0
                ? 'Votre base est vide, le pipeline commercial ne peut pas alimenter les campagnes.'
                : `${actifs.toLocaleString('fr-FR')} prospects actifs sur ${total.toLocaleString('fr-FR')} (${activeRate.toFixed(1)}%).`,
            total === 0
                ? 'Action: importer une première liste qualifiée.'
                : activeRate < 25
                    ? 'Action: retravailler la qualification et les statuts.'
                    : 'Action: maintenir le rythme de qualification.',
            total === 0 ? 100 : (activeRate < 25 ? 70 : 20)
        );

        pushBlock(
            'Lecture emailing',
            emails === 0
                ? 'Aucun envoi sur la période: impossible de mesurer ouverture/clic.'
                : `${emails.toLocaleString('fr-FR')} envois, ${openRate.toFixed(1)}% d’ouverture et ${clickRate.toFixed(1)}% de clic.`,
            emails === 0
                ? 'Action: lancer une campagne test et vérifier le tracking.'
                : openRate < 20
                    ? 'Action: optimiser objet + nom expéditeur.'
                    : clickRate < 2
                        ? 'Action: renforcer la valeur perçue et le CTA.'
                        : 'Action: dupliquer la structure des meilleures campagnes.',
            emails === 0 ? 95 : (openRate < 20 || clickRate < 2 ? 78 : 15)
        );

        pushBlock(
            'Lecture conversion',
            conversion <= 0
                ? 'Aucune conversion détectée: le tunnel passe mal de l’intérêt à la décision.'
                : `Conversion actuelle: ${conversion.toFixed(1)}%. Les campagnes produisent des opportunités.`,
            conversion <= 0
                ? 'Action: relancer en priorité les statuts Relance / À rappeler.'
                : 'Action: analyser les prospects gagnés pour industrialiser le playbook.',
            conversion <= 0 ? 90 : 25
        );

        pushBlock(
            'Lecture statuts CRM',
            `${relance.toLocaleString('fr-FR')} en Relance, ${aRappeler.toLocaleString('fr-FR')} à rappeler, ${perdu.toLocaleString('fr-FR')} perdus (${perduRate.toFixed(1)}%).`,
            (relance + aRappeler) > 0
                ? 'Action: lancer un batch d’appels/emails sur ces statuts en priorité.'
                : 'Action: définir une cadence de relance pour nourrir le pipeline.',
            (relance + aRappeler) > 0 ? 75 : 30
        );

        pushBlock(
            'Lecture opportunités',
            `${oppHigh.toLocaleString('fr-FR')} opportunités élevées contre ${oppLow.toLocaleString('fr-FR')} faibles.`,
            oppHigh >= oppLow
                ? 'Action: concentrer la prospection sortante sur les opportunités élevées.'
                : 'Action: améliorer le ciblage amont pour réduire les opportunités faibles.',
            oppLow > oppHigh ? 62 : 26
        );

        pushBlock(
            'Lecture segmentation',
            `${topSecteur ? `Secteur dominant: ${topSecteur[0]} (${Number(topSecteur[1] || 0).toLocaleString('fr-FR')}).` : 'Aucun secteur dominant détecté.'} ${topTag ? `Tag leader: ${topTag.tag} (${Number(topTag.count || 0).toLocaleString('fr-FR')}).` : ''}`,
            topTag
                ? 'Action: créer une campagne dédiée sur ce segment dominant.'
                : 'Action: enrichir les tags pour segmenter vos campagnes.',
            22
        );

        pushBlock(
            'Lecture production',
            `${totalAnalyses.toLocaleString('fr-FR')} analyses exécutées, ${totalCampagnes.toLocaleString('fr-FR')} campagne(s) en base, ${emailsOuverts.toLocaleString('fr-FR')} ouvertures et ${emailsCliques.toLocaleString('fr-FR')} clics.`,
            totalCampagnes === 0
                ? 'Action: lancer une première campagne avec suivi complet.'
                : (emailsCliques === 0 && emails > 0)
                    ? 'Action: revoir le CTA et proposer une offre plus directe.'
                    : 'Action: monitorer hebdomadairement les tendances de réponse.',
            totalCampagnes === 0 ? 85 : (emailsCliques === 0 && emails > 0 ? 70 : 20)
        );

        pushBlock(
            'Lecture secteurs gagnants',
            topWonSector
                ? `Secteur gagnant actuel: ${topWonSector.secteur} (${Number(topWonSector.count || 0).toLocaleString('fr-FR')} gagnés).`
                : 'Aucun secteur gagnant notable sur la période.',
            topWonSector
                ? 'Action: prioriser ce secteur dans vos prochaines campagnes.'
                : 'Action: tester 2 à 3 verticales avec messages spécialisés.',
            topWonSector ? 18 : 45
        );

        const topBlocks = blocks
            .filter((b) => (b.severity || 0) >= 70)
            .sort((a, b) => (b.severity || 0) - (a.severity || 0))
            .slice(0, 3);

        if (!topBlocks.length) {
            if (section) section.style.display = 'none';
            return;
        }
        if (section) section.style.display = '';

        container.innerHTML = topBlocks.map((b) => `
            <article class="analysis-card">
                <h4>${escapeHtml(b.title)}</h4>
                <p>${escapeHtml(b.text)}</p>
                <p class="analysis-next">${escapeHtml(b.next)}</p>
            </article>
        `).join('');
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
            'stat-actifs': '#chart-opportunites',
            'stat-gagnes': '#chart-secteurs-gagnes',
            'stat-conversion': '#chart-secteurs-gagnes',
            'stat-emails-envoyes': '#chart-emails',
            'stat-open-rate': '#chart-emails',
            'stat-click-rate': '#chart-emails',
        };

        document.querySelectorAll('.stat-card').forEach((card) => {
            const numberEl = card.querySelector('.stat-number');
            if (!numberEl || !numberEl.id) return;
            const override = card.getAttribute('data-kpi-scroll');
            const targetSelector = override || mapping[numberEl.id];
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

