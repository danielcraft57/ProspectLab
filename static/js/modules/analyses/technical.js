/**
 * Module d'affichage des analyses techniques
 */

(function(window) {
    'use strict';
    
    if (!window.Formatters || !window.Badges) {
        console.error('Modules Formatters et Badges requis');
        return;
    }
    
    const { Formatters, Badges } = window;
    
    /**
     * Affiche une analyse technique
     * @param {Object} analysis - Données de l'analyse technique
     * @param {HTMLElement} container - Élément DOM où afficher les résultats
     */
    function displayTechnicalAnalysis(analysis, container) {
        if (!container) return;
        
        const date = new Date(analysis.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const serverLabel = analysis.server_software || 'Inconnu';
        const frameworkLabel = analysis.framework ? `${analysis.framework}${analysis.framework_version ? ' ' + analysis.framework_version : ''}` : 'Aucun détecté';
        const cmsLabel = analysis.cms ? `${analysis.cms}${analysis.cms_version ? ' ' + analysis.cms_version : ''}` : 'Aucun détecté';
        const sslLabel = analysis.ssl_valid ? 'SSL valide' : 'SSL non valide';
        const wafLabel = analysis.waf || 'Aucun détecté';
        const cdnLabel = analysis.cdn || 'Aucun détecté';
        const analyticsCount = analysis.analytics && Array.isArray(analysis.analytics) ? analysis.analytics.length : 0;
        const analyticsLabel = analyticsCount > 0 ? `${analyticsCount} outil(s)` : 'Aucun outil détecté';
        
        const pagesSummary = analysis.pages_summary || {};
        const pagesList = Array.isArray(analysis.pages) ? analysis.pages : [];
        const perfScore = typeof analysis.performance_score === 'number'
            ? analysis.performance_score
            : (pagesSummary.performance_score !== undefined ? pagesSummary.performance_score : null);
        
        let securityScore = typeof analysis.security_score === 'number'
            ? analysis.security_score
            : (pagesSummary.security_score !== undefined ? pagesSummary.security_score : null);
        
        if (securityScore === null || securityScore === undefined) {
            securityScore = 0;
            if (analysis.ssl_valid) securityScore += 40;
            if (analysis.waf) securityScore += 25;
            if (analysis.cdn) securityScore += 10;
            if (analysis.security_headers && typeof analysis.security_headers === 'object' && !Array.isArray(analysis.security_headers)) {
                const headers = analysis.security_headers;
                const importantHeaders = ['Content-Security-Policy', 'Strict-Transport-Security', 'X-Frame-Options', 'X-Content-Type-Options', 'Referrer-Policy'];
                let count = 0;
                importantHeaders.forEach(name => {
                    if (headers[name]) count += 1;
                });
                securityScore += Math.min(count * 5, 25);
            }
            if (securityScore > 100) securityScore = 100;
        }
        const securityInfo = Badges.getSecurityScoreInfo(securityScore);
        
        // Construire la liste d'issues techniques (alignée sur le pattern Pentest)
        const importantHeaders = ['Content-Security-Policy', 'Strict-Transport-Security', 'X-Frame-Options', 'X-Content-Type-Options', 'Referrer-Policy'];
        const technicalIssues = [];
        if (!analysis.ssl_valid) {
            technicalIssues.push({ severity: 'critical', title: 'SSL non valide', description: 'Le certificat SSL est absent ou invalide.', recommendation: 'Configurer un certificat SSL valide (ex. Let\'s Encrypt) et forcer HTTPS.' });
        }
        if (analysis.security_headers && typeof analysis.security_headers === 'object') {
            const missing = importantHeaders.filter(name => !analysis.security_headers[name] || (analysis.security_headers[name] && typeof analysis.security_headers[name] === 'object' && !analysis.security_headers[name].value && analysis.security_headers[name].status !== 'present'));
            if (missing.length) {
                technicalIssues.push({ severity: 'high', title: 'En-têtes de sécurité manquants', description: `En-têtes absents ou non configurés : ${missing.join(', ')}.`, recommendation: 'Ajouter les en-têtes de sécurité recommandés (CSP, HSTS, X-Frame-Options, etc.) dans la configuration du serveur.' });
            }
        }
        if (!analysis.waf) {
            technicalIssues.push({ severity: 'medium', title: 'Aucun WAF détecté', description: 'Aucun Web Application Firewall n\'a été détecté.', recommendation: 'Envisager un WAF (Cloudflare, AWS WAF, ModSecurity) pour renforcer la protection.' });
        }
        const perfNum = typeof perfScore === 'number' ? perfScore : (analysis.performance_grade ? parseInt(analysis.performance_grade, 10) : null);
        if (perfNum !== null && perfNum < 50) {
            technicalIssues.push({ severity: 'medium', title: 'Performance faible', description: `Score performance ${perfNum}/100. Le site peut être lent pour les utilisateurs.`, recommendation: 'Optimiser les ressources (images, cache, compression), réduire le JavaScript et les requêtes.' });
        }
        if (analysis.seo_meta && typeof analysis.seo_meta === 'object') {
            if (!analysis.seo_meta.meta_title || !analysis.seo_meta.meta_title.trim()) {
                technicalIssues.push({ severity: 'low', title: 'Meta titre manquant', description: 'La balise meta title est absente ou vide.', recommendation: 'Ajouter un titre unique et descriptif (50–60 caractères) sur chaque page.' });
            }
            if (!analysis.seo_meta.meta_description || !analysis.seo_meta.meta_description.trim()) {
                technicalIssues.push({ severity: 'low', title: 'Meta description manquante', description: 'La balise meta description est absente ou vide.', recommendation: 'Ajouter une description concise (150–160 caractères) pour le référencement.' });
            }
        }
        const techIssueCounts = { critical: 0, high: 0, medium: 0, low: 0 };
        technicalIssues.forEach(i => { if (techIssueCounts[i.severity] !== undefined) techIssueCounts[i.severity]++; });
        const hasTechnicalIssues = technicalIssues.length > 0;
        
        let html = `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <div class="detail-section" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 8px;">
                    <h3 style="margin: 0 0 1rem 0; color: white;"><i class="fas fa-chart-bar"></i> Informations générales</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; color: white;">
                        <div><strong><i class="fas fa-calendar"></i> Date:</strong> ${date}</div>
                        <div><strong><i class="fas fa-globe"></i> URL:</strong> <a href="${analysis.url}" target="_blank" style="color: #ffd700; text-decoration: underline;">${Formatters.escapeHtml(analysis.url)}</a></div>
                        <div><strong><i class="fas fa-tag"></i> Domaine:</strong> ${Formatters.escapeHtml(analysis.domain || 'N/A')}</div>
                        <div><strong><i class="fas fa-hashtag"></i> IP:</strong> ${Formatters.escapeHtml(analysis.ip_address || 'N/A')}</div>
                    </div>
                </div>
                
                <div class="detail-section" style="padding: 0; border-radius: 8px; overflow: hidden;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0; border: 1px solid #e5e7eb;">
                        <div style="padding: 1rem; border-right: 1px solid #e5e7eb; background: #f9fafb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Stack</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>Serveur:</strong> ${Formatters.escapeHtml(serverLabel)}</div>
                                <div><strong>Framework:</strong> ${Formatters.escapeHtml(frameworkLabel)}</div>
                                <div><strong>CMS:</strong> ${Formatters.escapeHtml(cmsLabel)}</div>
                            </div>
                        </div>
                        <div style="padding: 1rem; border-right: 1px solid #e5e7eb; background: #fdfdfb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Sécurité</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>SSL:</strong> ${Formatters.escapeHtml(sslLabel)}</div>
                                <div><strong>WAF:</strong> ${Formatters.escapeHtml(wafLabel)}</div>
                                <div><strong>CDN:</strong> ${Formatters.escapeHtml(cdnLabel)}</div>
                                <div><strong>Score global:</strong> <span class="badge badge-${securityInfo.className}">${securityInfo.label}</span></div>
                            </div>
                        </div>
                        <div style="padding: 1rem; background: #f9fafb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Suivi & analytics</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>Outils d'analyse:</strong> ${Formatters.escapeHtml(analyticsLabel)}</div>
                                ${analysis.performance_grade ? `<div><strong>Score performance:</strong> ${Formatters.escapeHtml(String(analysis.performance_grade))}</div>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
                
                ${hasTechnicalIssues ? `
                <div class="detail-section technical-issues-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-exclamation-triangle"></i> Issues techniques <span class="badge badge-danger">${technicalIssues.length}</span></h3>
                    <div class="technical-summary-chips">
                        ${techIssueCounts.critical ? `<span class="technical-chip technical-chip-critical">${techIssueCounts.critical} critique${techIssueCounts.critical > 1 ? 's' : ''}</span>` : ''}
                        ${techIssueCounts.high ? `<span class="technical-chip technical-chip-high">${techIssueCounts.high} haute${techIssueCounts.high > 1 ? 's' : ''}</span>` : ''}
                        ${techIssueCounts.medium ? `<span class="technical-chip technical-chip-medium">${techIssueCounts.medium} moyenne${techIssueCounts.medium > 1 ? 's' : ''}</span>` : ''}
                        ${techIssueCounts.low ? `<span class="technical-chip technical-chip-low">${techIssueCounts.low} faible${techIssueCounts.low > 1 ? 's' : ''}</span>` : ''}
                    </div>
                    <div class="technical-issues-list" style="display: flex; flex-direction: column; gap: 0.75rem; margin-top: 1rem;">
                        ${technicalIssues.map(issue => {
                            const borderColors = { critical: '#e74c3c', high: '#e67e22', medium: '#f39c12', low: '#3498db' };
                            const color = borderColors[issue.severity] || '#6b7280';
                            return `<div class="technical-issue-card" style="border-left: 4px solid ${color};">
                                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem;">
                                    <strong class="technical-issue-title">${Formatters.escapeHtml(issue.title)}</strong>
                                    <span class="technical-chip technical-chip-${issue.severity}" style="font-size: 0.75rem;">${Formatters.escapeHtml(issue.severity)}</span>
                                </div>
                                ${issue.description ? `<div class="technical-issue-desc">${Formatters.escapeHtml(issue.description)}</div>` : ''}
                                ${issue.recommendation ? `<div class="technical-issue-reco"><strong><i class="fas fa-lightbulb"></i> Recommandation:</strong> ${Formatters.escapeHtml(issue.recommendation)}</div>` : ''}
                            </div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${(() => {
                    const pagesCount = pagesSummary.pages_count || pagesSummary.pages_scanned || pagesList.length || 0;
                    if (!pagesCount) return '';
                    const pagesOk = pagesSummary.pages_ok || 0;
                    const pagesError = pagesSummary.pages_error || 0;
                    const trackersCount = pagesSummary.trackers_count || analysis.trackers_count || 0;
                    const avgResp = pagesSummary.avg_response_time_ms ? Formatters.formatMs(pagesSummary.avg_response_time_ms) : 'N/A';
                    const avgWeight = pagesSummary.avg_weight_bytes ? Formatters.formatBytesShort(pagesSummary.avg_weight_bytes) : 'N/A';
                    const perfBadge = Badges.getPerformanceScoreBadge(perfScore);
                    
                    const rows = pagesList.slice(0, 20).map(page => {
                        const pageSecBadge = Badges.getSecurityScoreBadge(page.security_score);
                        const pagePerfBadge = Badges.getPerformanceScoreBadge(page.performance_score);
                        const statusLabel = page.status_code ? page.status_code : 'N/A';
                        return `
                            <tr>
                                <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis;">
                                    <a href="${page.final_url || page.url}" target="_blank" rel="noopener">${Formatters.escapeHtml(page.url || 'Page')}</a>
                                </td>
                                <td>${statusLabel}</td>
                                <td>${pageSecBadge}</td>
                                <td>${pagePerfBadge}</td>
                                <td>${page.trackers_count || 0}</td>
                            </tr>
                        `;
                    }).join('');
                    
                    return `
                        <div class="detail-section" style="padding: 1rem; background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px;">
                            <h3 style="margin: 0 0 0.75rem 0; color: #1f2937;"><i class="fas fa-satellite"></i> Analyse multi-pages (${pagesCount} page${pagesCount > 1 ? 's' : ''})</h3>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-bottom: 0.75rem;">
                                <div><strong>Score sécurité:</strong> ${Badges.getSecurityScoreBadge(securityScore)}</div>
                                <div><strong>Score perf:</strong> ${perfBadge}</div>
                                <div><strong>Pages OK/Erreur:</strong> <span class="badge badge-success">${pagesOk}</span> / <span class="badge badge-danger">${pagesError}</span></div>
                                <div><strong>Trackers trouvés:</strong> <span class="badge badge-info">${trackersCount}</span></div>
                                <div><strong>Temps moyen:</strong> ${avgResp}</div>
                                <div><strong>Poids moyen:</strong> ${avgWeight}</div>
                            </div>
                            ${rows ? `
                            <div style="overflow-x: auto;">
                                <table class="table" style="width: 100%; border-collapse: collapse;">
                                    <thead>
                                        <tr style="text-align: left; border-bottom: 1px solid #e5e7eb;">
                                            <th style="padding: 0.5rem 0.25rem;">Page</th>
                                            <th style="padding: 0.5rem 0.25rem;">Statut</th>
                                            <th style="padding: 0.5rem 0.25rem;">Sécurité</th>
                                            <th style="padding: 0.5rem 0.25rem;">Perf</th>
                                            <th style="padding: 0.5rem 0.25rem;">Trackers</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${rows}
                                    </tbody>
                                </table>
                            </div>` : ''}
                        </div>
                    `;
                })()}
                
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-server"></i> Serveur et infrastructure</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${analysis.server_software ? `<div class="info-row"><span class="info-label">Logiciel serveur:</span><span class="info-value"><span class="badge badge-info">${Formatters.escapeHtml(analysis.server_software)}</span></span></div>` : ''}
                        ${analysis.framework ? `<div class="info-row"><span class="info-label">Framework:</span><span class="info-value"><span class="badge badge-primary">${Formatters.escapeHtml(analysis.framework)}${analysis.framework_version ? ' ' + analysis.framework_version : ''}</span></span></div>` : ''}
                        ${analysis.cms ? `<div class="info-row"><span class="info-label">CMS:</span><span class="info-value"><span class="badge badge-success">${Formatters.escapeHtml(analysis.cms)}${analysis.cms_version ? ' ' + analysis.cms_version : ''}</span></span></div>` : ''}
                        ${analysis.hosting_provider ? `<div class="info-row"><span class="info-label">Hébergeur:</span><span class="info-value">${Formatters.escapeHtml(analysis.hosting_provider)}</span></div>` : ''}
                        ${analysis.cdn ? `<div class="info-row"><span class="info-label">CDN:</span><span class="info-value"><span class="badge badge-secondary">${Formatters.escapeHtml(analysis.cdn)}</span></span></div>` : ''}
                        ${analysis.waf ? `<div class="info-row"><span class="info-label">WAF:</span><span class="info-value"><span class="badge badge-warning">${Formatters.escapeHtml(analysis.waf)}</span></span></div>` : ''}
                    </div>
                </div>
                
                ${analysis.cms_plugins && Array.isArray(analysis.cms_plugins) && analysis.cms_plugins.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-plug"></i> Plugins CMS <span class="badge badge-info">${analysis.cms_plugins.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysis.cms_plugins.map(plugin => `<span class="badge badge-outline">${Formatters.escapeHtml(plugin)}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-globe-europe"></i> Domaine et DNS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${analysis.domain_creation_date ? `<div class="info-row"><span class="info-label">Date de création:</span><span class="info-value">${Formatters.escapeHtml(analysis.domain_creation_date)}</span></div>` : ''}
                        ${analysis.domain_updated_date ? `<div class="info-row"><span class="info-label">Dernière mise à jour:</span><span class="info-value">${Formatters.escapeHtml(analysis.domain_updated_date)}</span></div>` : ''}
                        ${analysis.domain_registrar ? `<div class="info-row"><span class="info-label">Registrar:</span><span class="info-value">${Formatters.escapeHtml(analysis.domain_registrar)}</span></div>` : ''}
                    </div>
                </div>
                
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-lock"></i> SSL/TLS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        <div class="info-row">
                            <span class="info-label">SSL valide:</span>
                            <span class="info-value">
                                <span class="badge ${analysis.ssl_valid ? 'badge-success' : 'badge-danger'}">${analysis.ssl_valid ? '<i class="fas fa-check"></i> Oui' : '<i class="fas fa-times"></i> Non'}</span>
                            </span>
                        </div>
                        ${analysis.ssl_expiry_date ? `<div class="info-row"><span class="info-label">Date d'expiration:</span><span class="info-value">${Formatters.escapeHtml(analysis.ssl_expiry_date)}</span></div>` : ''}
                    </div>
                </div>
                
                ${analysis.security_headers && typeof analysis.security_headers === 'object' && !Array.isArray(analysis.security_headers) && Object.keys(analysis.security_headers).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-shield-alt"></i> En-têtes de sécurité</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem;">
                        ${Object.entries(analysis.security_headers).map(([key, value]) => {
                            let display = '';
                            if (value && typeof value === 'object') {
                                const v = value.value || value.header || '';
                                const status = value.status || value.present;
                                display = v ? v : '';
                                if (status !== undefined && status !== null && status !== '') {
                                    display = display ? `${display} (${status})` : String(status);
                                }
                            } else {
                                display = value || 'N/A';
                            }
                            return `<div class="info-row"><span class="info-label">${Formatters.escapeHtml(key)}:</span><span class="info-value"><code style="background: #f5f5f5; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem;">${Formatters.escapeHtml(display)}</code></span></div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.analytics && Array.isArray(analysis.analytics) && analysis.analytics.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-chart-line"></i> Outils d'analyse <span class="badge badge-info">${analysis.analytics.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysis.analytics.map(tool => {
                            let label = '';
                            if (tool && typeof tool === 'object') {
                                const name = tool.name || tool.tool || tool.id || tool.tracking_id || '';
                                const extra = tool.id && tool.id !== name ? ` (${tool.id})` :
                                              tool.tracking_id && tool.tracking_id !== name ? ` (${tool.tracking_id})` : '';
                                label = (name || '[Inconnu]') + extra;
                            } else {
                                label = String(tool);
                            }
                            return `<span class="badge badge-secondary">${Formatters.escapeHtml(label)}</span>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.seo_meta && typeof analysis.seo_meta === 'object' && !Array.isArray(analysis.seo_meta) ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-search"></i> SEO et métadonnées</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: 1fr; gap: 1rem;">
                        ${analysis.seo_meta.meta_title ? `<div class="info-row"><span class="info-label">Titre:</span><span class="info-value">${Formatters.escapeHtml(analysis.seo_meta.meta_title)}</span></div>` : ''}
                        ${analysis.seo_meta.meta_description ? `<div class="info-row"><span class="info-label">Description:</span><span class="info-value">${Formatters.escapeHtml(analysis.seo_meta.meta_description)}</span></div>` : ''}
                        ${analysis.seo_meta.canonical_url ? `<div class="info-row"><span class="info-label">URL canonique:</span><span class="info-value"><a href="${analysis.seo_meta.canonical_url}" target="_blank" style="color: #667eea;">${Formatters.escapeHtml(analysis.seo_meta.canonical_url)}</a></span></div>` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.performance_metrics && typeof analysis.performance_metrics === 'object' && !Array.isArray(analysis.performance_metrics) && Object.keys(analysis.performance_metrics).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-bolt"></i> Métriques de performance</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${Object.entries(analysis.performance_metrics).map(([key, value]) => 
                            `<div class="info-row"><span class="info-label">${Formatters.escapeHtml(key)}:</span><span class="info-value"><strong>${Formatters.escapeHtml(String(value || 'N/A'))}</strong></span></div>`
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysis.nmap_scan ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-search"></i> Scan Nmap</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les détails du scan</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${Formatters.escapeHtml(JSON.stringify(analysis.nmap_scan, null, 2))}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysis.technical_details ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-tools"></i> Détails techniques</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir tous les détails</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${Formatters.escapeHtml(JSON.stringify(analysis.technical_details, null, 2))}</pre>
                    </details>
                </div>
                ` : ''}
            </div>
        `;
        
        container.innerHTML = html;
        
        // Mettre à jour le score sécurité dans la fiche info si possible
        try {
            if (typeof securityScore !== 'undefined') {
                if (window.currentModalEntrepriseData) {
                    window.currentModalEntrepriseData.score_securite = securityScore;
                }
                const badge = document.getElementById('security-score-badge');
                if (badge) {
                    const info = Badges.getSecurityScoreInfo(securityScore);
                    badge.className = `badge badge-${info.className}`;
                    badge.textContent = info.label;
                }
            }
        } catch (e) {
            // Erreur silencieuse
        }
    }
    
    // Exposer globalement
    window.TechnicalAnalysisDisplay = { displayTechnicalAnalysis };
})(window);

