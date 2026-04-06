'use strict';

(function () {
    function getRoot() {
        return document.getElementById('audit-report-root');
    }

    function getEntrepriseId() {
        const root = getRoot();
        if (!root) return null;
        const raw = root.getAttribute('data-entreprise-id');
        if (!raw) return null;
        const id = parseInt(raw, 10);
        return Number.isNaN(id) ? null : id;
    }

    function escapeHtml(text) {
        if (window.Formatters && typeof window.Formatters.escapeHtml === 'function') {
            return window.Formatters.escapeHtml(text);
        }
        const div = document.createElement('div');
        div.textContent = String(text || '');
        return div.innerHTML;
    }

    function buildExecutiveSummary(entreprise, opportunity, pipeline) {
        const lines = [];
        const oppLevel = opportunity && opportunity.opportunity;
        const oppScore = opportunity && typeof opportunity.score === 'number' ? opportunity.score : null;

        if (oppLevel && oppScore !== null) {
            lines.push(
                `L'opportunité est <strong>${escapeHtml(oppLevel.toLowerCase())}</strong> `
                + `avec un score global d'environ <strong>${oppScore}/100</strong>.`
            );
        } else {
            lines.push(`L'opportunité n'a pas encore été calculée pour cette entreprise.`);
        }

        const tech = pipeline && pipeline.technical;
        if (tech && typeof tech.security_score === 'number') {
            if (tech.security_score < 50) {
                lines.push(`La sécurité technique actuelle est <strong>faible</strong> (score ~${tech.security_score}/100).`);
            } else if (tech.security_score < 70) {
                lines.push(`La sécurité technique est <strong>moyenne</strong> (score ~${tech.security_score}/100).`);
            }
        }

        const seo = pipeline && pipeline.seo;
        if (seo && typeof seo.score === 'number') {
            if (seo.score < 50) {
                lines.push(`Le score SEO est <strong>faible</strong> (environ ${seo.score}/100), avec un fort potentiel d'amélioration.`);
            } else if (seo.score < 70) {
                lines.push(`Le SEO est <strong>perfectible</strong> (environ ${seo.score}/100).`);
            }
        }

        const pentest = pipeline && pipeline.pentest;
        if (pentest && typeof pentest.risk_score === 'number') {
            if (pentest.risk_score >= 70) {
                lines.push(`Le risque de sécurité est <strong>élevé</strong> (score Pentest ~${pentest.risk_score}/100).`);
            } else if (pentest.risk_score >= 40) {
                lines.push(`Le risque de sécurité est <strong>modéré</strong> (score Pentest ~${pentest.risk_score}/100).`);
            }
        }

        if (!lines.length) {
            lines.push(`Les données d'analyse sont encore incomplètes pour cette entreprise.`);
        }

        return lines;
    }

    function buildQuickWins(opportunity) {
        const items = [];
        if (opportunity && Array.isArray(opportunity.indicators)) {
            for (let i = 0; i < opportunity.indicators.length && items.length < 5; i++) {
                const ind = String(opportunity.indicators[i] || '').trim();
                if (!ind) continue;
                items.push(ind);
            }
        }
        return items;
    }

    function buildMetricsHtml(oppData, pipeline) {
        const parts = [];
        if (oppData && typeof oppData.score === 'number') {
            parts.push(
                `<div class="audit-metric"><span class="audit-metric-label">Opportunité</span>`
                + `<span class="audit-metric-value">${oppData.score}/100</span></div>`
            );
        }
        const tech = pipeline && pipeline.technical;
        if (tech && typeof tech.security_score === 'number') {
            let cls = 'audit-metric';
            if (tech.security_score < 50) cls += ' is-warn';
            parts.push(
                `<div class="${cls}"><span class="audit-metric-label">Sécurité technique</span>`
                + `<span class="audit-metric-value">${tech.security_score}/100</span></div>`
            );
        }
        const seo = pipeline && pipeline.seo;
        if (seo && typeof seo.score === 'number') {
            let cls = 'audit-metric';
            if (seo.score < 50) cls += ' is-warn';
            parts.push(
                `<div class="${cls}"><span class="audit-metric-label">SEO</span>`
                + `<span class="audit-metric-value">${seo.score}/100</span></div>`
            );
        }
        const pentest = pipeline && pipeline.pentest;
        if (pentest && typeof pentest.risk_score === 'number') {
            let cls = 'audit-metric';
            if (pentest.risk_score >= 70) cls += ' is-risk-high';
            else if (pentest.risk_score >= 40) cls += ' is-risk-mid';
            parts.push(
                `<div class="${cls}"><span class="audit-metric-label">Risque pentest</span>`
                + `<span class="audit-metric-value">${pentest.risk_score}/100</span></div>`
            );
        }
        if (!parts.length) return '';
        return `<div class="audit-metrics">${parts.join('')}</div>`;
    }

    function initExclusiveAccordion(mountRoot) {
        const accRoot = mountRoot.querySelector('.audit-report-accordion');
        if (!accRoot) return;
        accRoot.querySelectorAll('details.audit-acc-item').forEach((det) => {
            det.addEventListener('toggle', () => {
                if (!det.open) return;
                accRoot.querySelectorAll('details.audit-acc-item').forEach((other) => {
                    if (other !== det) other.open = false;
                });
            });
        });
    }

    function revealAuditReport(mountRoot) {
        const section = mountRoot.querySelector('.audit-report');
        if (!section) return;
        requestAnimationFrame(() => {
            requestAnimationFrame(() => section.classList.add('audit-report--visible'));
        });
    }

    async function initReport() {
        const root = getRoot();
        if (!root) return;

        const id = getEntrepriseId();
        if (!id) {
            root.innerHTML = '<p class="error">ID entreprise invalide.</p>';
            return;
        }

        if (!window.EntreprisesAPI) {
            root.innerHTML = '<p class="error">API entreprises non disponible.</p>';
            return;
        }

        try {
            root.innerHTML = '<div class="loading">Chargement des données d\'audit...</div>';

            const [entreprise, pipelineResp, opportunity] = await Promise.all([
                window.EntreprisesAPI.loadDetails(id),
                window.EntreprisesAPI.loadAuditPipeline(id),
                window.EntreprisesAPI.recalculateOpportunity(id).catch(() => null)
            ]);

            const pipeline = pipelineResp && pipelineResp.pipeline ? pipelineResp.pipeline : {};
            const oppData = opportunity && opportunity.success !== false ? opportunity : null;

            const execLines = buildExecutiveSummary(entreprise, oppData, pipeline);
            const quickWins = buildQuickWins(oppData);

            const oppLevel = oppData && oppData.opportunity;
            const oppScore = oppData && typeof oppData.score === 'number' ? oppData.score : null;
            let oppBadgeHtml = '';
            if (window.Badges && typeof window.Badges.getOpportunityBadge === 'function') {
                oppBadgeHtml = window.Badges.getOpportunityBadge(oppLevel || 'Non calculée', oppScore, 'report-opportunity-badge');
            } else {
                oppBadgeHtml = escapeHtml(oppLevel || 'Non calculée') + (oppScore != null ? ` (${oppScore}/100)` : '');
            }

            const website = entreprise.website || '';
            const secteur = entreprise.secteur || '';
            const metricsHtml = buildMetricsHtml(oppData, pipeline);

            const execInsightsHtml = execLines.map((line) => (
                `<div class="audit-insight">`
                + `<i class="fa-solid fa-circle-check" aria-hidden="true"></i>`
                + `<div>${line}</div></div>`
            )).join('');

            const quickWinsHtml = quickWins.length
                ? `<div class="audit-tags">${quickWins.map((w) => (
                    `<span class="audit-tag">${escapeHtml(w)}</span>`
                )).join('')}</div>`
                : '<p class="empty-state">Aucun quick win spécifique n\'a encore été identifié.</p>';

            root.innerHTML = `
                <section class="audit-report" aria-label="Rapport d'audit">
                    <header class="audit-report-hero">
                        <div class="audit-report-hero-main">
                            <h2 class="audit-report-company">${escapeHtml(entreprise.nom || 'Entreprise')}</h2>
                            ${website ? `<p class="audit-report-website"><a href="${escapeHtml(website)}" target="_blank" rel="noopener">${escapeHtml(website)}</a></p>` : ''}
                            ${secteur ? `<p class="audit-report-sector">${escapeHtml(secteur)}</p>` : ''}
                        </div>
                        <div class="audit-report-hero-actions">
                            <a href="/entreprise/${id}" class="btn btn-secondary btn-small">← Fiche entreprise</a>
                            <a href="/entreprises" class="btn btn-outline btn-small">← Liste des entreprises</a>
                        </div>
                        <div class="audit-report-opportunity">
                            <span class="label">Opportunité</span>
                            <div>${oppBadgeHtml}</div>
                        </div>
                    </header>

                    ${metricsHtml}

                    <div class="audit-report-accordion" role="region" aria-label="Détail du rapport">
                        <details class="audit-acc-item" open>
                            <summary class="audit-acc-summary">
                                <span class="audit-acc-icon" aria-hidden="true"><i class="fa-solid fa-clipboard-list"></i></span>
                                Résumé exécutif
                            </summary>
                            <div class="audit-acc-panel">
                                <div class="audit-insights">${execInsightsHtml}</div>
                            </div>
                        </details>
                        <details class="audit-acc-item">
                            <summary class="audit-acc-summary">
                                <span class="audit-acc-icon" aria-hidden="true"><i class="fa-solid fa-bolt"></i></span>
                                Quick wins prioritaires
                            </summary>
                            <div class="audit-acc-panel">${quickWinsHtml}</div>
                        </details>
                        <details class="audit-acc-item">
                            <summary class="audit-acc-summary">
                                <span class="audit-acc-icon" aria-hidden="true"><i class="fa-solid fa-microchip"></i></span>
                                Technique &amp; performance
                            </summary>
                            <div class="audit-acc-panel">
                                <div class="audit-report-card">
                                    <h4>Scraping &amp; stack</h4>
                                    <p>Voir les onglets « Analyse technique » et « Pipeline d’audit » pour les performances, la sécurité applicative et les technologies détectées sur le site.</p>
                                </div>
                            </div>
                        </details>
                        <details class="audit-acc-item">
                            <summary class="audit-acc-summary">
                                <span class="audit-acc-icon" aria-hidden="true"><i class="fa-solid fa-magnifying-glass-chart"></i></span>
                                SEO &amp; visibilité
                            </summary>
                            <div class="audit-acc-panel">
                                <div class="audit-report-card">
                                    <h4>SEO</h4>
                                    <p>Le score SEO et les anomalies (balises, structure, Lighthouse) servent de base aux actions pour améliorer la visibilité organique.</p>
                                </div>
                            </div>
                        </details>
                        <details class="audit-acc-item">
                            <summary class="audit-acc-summary">
                                <span class="audit-acc-icon" aria-hidden="true"><i class="fa-solid fa-shield-halved"></i></span>
                                Sécurité &amp; pentest
                            </summary>
                            <div class="audit-acc-panel">
                                <div class="audit-report-card">
                                    <h4>Pentest &amp; posture</h4>
                                    <p>Les vulnérabilités Pentest et la configuration SSL / en-têtes HTTP guident les priorités de durcissement.</p>
                                </div>
                            </div>
                        </details>
                        <details class="audit-acc-item">
                            <summary class="audit-acc-summary">
                                <span class="audit-acc-icon" aria-hidden="true"><i class="fa-solid fa-user-secret"></i></span>
                                OSINT &amp; contacts
                            </summary>
                            <div class="audit-acc-panel">
                                <div class="audit-report-card">
                                    <h4>Contacts &amp; résilience</h4>
                                    <p>Les personnes et e-mails issus de l’OSINT et du scraping permettent une prospection ciblée et un suivi des points de contact.</p>
                                </div>
                            </div>
                        </details>
                    </div>

                    <footer class="audit-report-footer">
                        <p>Rapport généré automatiquement par ProspectLab. Utilisez la fonction d’impression du navigateur pour l’exporter en PDF.</p>
                    </footer>
                </section>
            `;
            initExclusiveAccordion(root);
            revealAuditReport(root);
        } catch (e) {
            console.error('Erreur lors de la génération du rapport:', e);
            root.innerHTML = '<p class="error">Erreur lors de la génération du rapport d\'audit.</p>';
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReport);
    } else {
        initReport();
    }
})();

