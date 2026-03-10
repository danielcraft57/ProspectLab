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

            root.innerHTML = `
                <section class="audit-report">
                    <header class="audit-report-header">
                        <div>
                            <h2 class="audit-report-company">${escapeHtml(entreprise.nom || 'Entreprise')}</h2>
                            ${website ? `<p class="audit-report-website"><a href="${escapeHtml(website)}" target="_blank" rel="noopener">${escapeHtml(website)}</a></p>` : ''}
                            ${secteur ? `<p class="audit-report-sector">${escapeHtml(secteur)}</p>` : ''}
                        </div>
                        <div class="audit-report-opportunity">
                            <span class="label">Opportunité</span>
                            <div>${oppBadgeHtml}</div>
                        </div>
                    </header>

                    <section class="audit-report-section">
                        <h3>Résumé exécutif</h3>
                        <ul class="audit-report-bullets">
                            ${execLines.map(l => `<li>${l}</li>`).join('')}
                        </ul>
                    </section>

                    <section class="audit-report-section">
                        <h3>Quick wins prioritaires</h3>
                        ${
                            quickWins.length
                                ? `<ul class="audit-report-bullets">
                                        ${quickWins.map(w => `<li>${escapeHtml(w)}</li>`).join('')}
                                   </ul>`
                                : '<p class="empty-state">Aucun quick win spécifique n\'a encore été identifié.</p>'
                        }
                    </section>

                    <section class="audit-report-section audit-report-grid">
                        <div class="audit-report-card">
                            <h4>Technique & performance</h4>
                            <p>Voir les onglets « Analyse technique » et « Pipeline d\'audit » pour le détail des performances, sécurité, et technologies utilisées.</p>
                        </div>
                        <div class="audit-report-card">
                            <h4>SEO & visibilité</h4>
                            <p>Le score SEO et les problèmes détectés (balises, structure, Lighthouse) orientent les actions d\'amélioration de la visibilité.</p>
                        </div>
                        <div class="audit-report-card">
                            <h4>Sécurité & Pentest</h4>
                            <p>Les vulnérabilités identifiées (Pentest) ainsi que la configuration SSL/headers guident les priorités de correction.</p>
                        </div>
                        <div class="audit-report-card">
                            <h4>Données OSINT & contacts</h4>
                            <p>Les données personnes/emails issues de l\'OSINT et du scraping facilitent la prise de contact ciblée.</p>
                        </div>
                    </section>

                    <footer class="audit-report-footer">
                        <p>Rapport généré automatiquement par ProspectLab. Utilisez la fonction d\'impression du navigateur pour l\'exporter en PDF.</p>
                    </footer>
                </section>
            `;
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

