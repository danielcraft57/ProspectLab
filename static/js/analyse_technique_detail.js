/**
 * JavaScript pour la page de détail d'une analyse technique
 */

(function() {
    let analysisId = null;
    let analysisData = null;
    
    // Fonctions utilitaires pour les scores
    function getSecurityScoreInfo(score) {
        if (score === null || score === undefined || Number.isNaN(Number(score))) {
            return { label: 'Non analysé', className: 'secondary' };
        }
        const s = Math.max(0, Math.min(100, Number(score)));
        if (s >= 80) {
            return { label: `${s}/100 (Sécurisé)`, className: 'success' };
        }
        if (s >= 50) {
            return { label: `${s}/100 (Moyen)`, className: 'warning' };
        }
        return { label: `${s}/100 (Faible)`, className: 'danger' };
    }
    
    function getSecurityScoreBadge(score, id = null) {
        const info = getSecurityScoreInfo(score);
        const idAttr = id ? ` id="${id}"` : '';
        return `<span${idAttr} class="badge badge-${info.className}">${info.label}</span>`;
    }

    function getPerformanceScoreInfo(score) {
        if (score === null || score === undefined || Number.isNaN(Number(score))) {
            return { label: 'Non analysé', className: 'secondary' };
        }
        const s = Math.max(0, Math.min(100, Number(score)));
        if (s >= 80) return { label: `${s}/100 (Rapide)`, className: 'success' };
        if (s >= 50) return { label: `${s}/100 (Moyen)`, className: 'warning' };
        return { label: `${s}/100 (Lent)`, className: 'danger' };
    }

    function getPerformanceScoreBadge(score) {
        const info = getPerformanceScoreInfo(score);
        return `<span class="badge badge-${info.className}">${info.label}</span>`;
    }

    function formatMs(ms) {
        if (!ms && ms !== 0) return 'N/A';
        return `${ms} ms`;
    }

    function formatBytesShort(bytes) {
        if (!bytes && bytes !== 0) return 'N/A';
        const kb = bytes / 1024;
        if (kb < 1024) return `${kb.toFixed(1)} Ko`;
        return `${(kb / 1024).toFixed(2)} Mo`;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Récupérer l'ID depuis la variable globale ou l'URL
    if (typeof ANALYSIS_ID !== 'undefined') {
        analysisId = ANALYSIS_ID;
    } else {
        const pathParts = window.location.pathname.split('/');
        analysisId = parseInt(pathParts[pathParts.length - 1]);
    }
    
    document.addEventListener('DOMContentLoaded', () => {
        if (analysisId) {
            loadAnalysisDetail();
        }
    });
    
    async function loadAnalysisDetail() {
        try {
            const response = await fetch(`/api/analyse-technique/${analysisId}`);
            if (!response.ok) {
                throw new Error('Analyse introuvable');
            }
            
            analysisData = await response.json();
            renderDetail();
        } catch (error) {
            console.error('Erreur lors du chargement:', error);
            document.getElementById('analyse-detail').innerHTML = 
                '<div class="error">Erreur lors du chargement des détails</div>';
        }
    }
    
    function renderDetail() {
        if (!analysisData) return;
        
        const date = new Date(analysisData.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        document.getElementById('analyse-title').textContent = 
            `Analyse technique - ${analysisData.entreprise_nom || analysisData.url || 'Site web'}`;
        
        const detailDiv = document.getElementById('analyse-detail');
        detailDiv.innerHTML = createDetailHTML(date);
        
        // Ajouter le bouton de suppression
        setupDeleteButton();
    }
    
    function createDetailHTML(date) {
        const techDetails = analysisData.technical_details || {};
        
        // Calculer le score de sécurité
        let securityScore = typeof analysisData.security_score === 'number'
            ? analysisData.security_score
            : (analysisData.pages_summary?.security_score !== undefined ? analysisData.pages_summary.security_score : null);

        if (securityScore === null || securityScore === undefined) {
            securityScore = 0;
            if (analysisData.ssl_valid) {
                securityScore += 40;
            }
            if (analysisData.waf) {
                securityScore += 25;
            }
            if (analysisData.cdn) {
                securityScore += 10;
            }
            if (analysisData.security_headers && typeof analysisData.security_headers === 'object' && !Array.isArray(analysisData.security_headers)) {
                const headers = analysisData.security_headers;
                const importantHeaders = [
                    'Content-Security-Policy',
                    'Strict-Transport-Security',
                    'X-Frame-Options',
                    'X-Content-Type-Options',
                    'Referrer-Policy'
                ];
                let count = 0;
                importantHeaders.forEach(name => {
                    if (headers[name]) {
                        count += 1;
                    }
                });
                securityScore += Math.min(count * 5, 25);
            }
            if (securityScore > 100) {
                securityScore = 100;
            }
        }
        const securityInfo = getSecurityScoreInfo(securityScore);
        
        const pagesSummary = analysisData.pages_summary || {};
        const pagesList = Array.isArray(analysisData.pages) ? analysisData.pages : [];
        const perfScore = typeof analysisData.performance_score === 'number'
            ? analysisData.performance_score
            : (pagesSummary.performance_score !== undefined ? pagesSummary.performance_score : null);
        
        const serverLabel = analysisData.server_software || 'Inconnu';
        const frameworkLabel = analysisData.framework ? `${analysisData.framework}${analysisData.framework_version ? ' ' + analysisData.framework_version : ''}` : 'Aucun détecté';
        const cmsLabel = analysisData.cms ? `${analysisData.cms}${analysisData.cms_version ? ' ' + analysisData.cms_version : ''}` : 'Aucun détecté';
        const sslLabel = analysisData.ssl_valid ? 'SSL valide' : 'SSL non valide';
        const wafLabel = analysisData.waf || 'Aucun détecté';
        const cdnLabel = analysisData.cdn || 'Aucun détecté';
        const analyticsCount = analysisData.analytics && Array.isArray(analysisData.analytics) ? analysisData.analytics.length : 0;
        const analyticsLabel = analyticsCount > 0 ? `${analyticsCount} outil(s)` : 'Aucun outil détecté';
        
        return `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- En-tête avec informations générales -->
                <div class="detail-section" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 8px;">
                    <h3 style="margin: 0 0 1rem 0; color: white;">📊 Informations générales</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; color: white;">
                        <div><strong>📅 Date:</strong> ${date}</div>
                        <div><strong>🌐 URL:</strong> <a href="${analysisData.url}" target="_blank" style="color: #ffd700; text-decoration: underline;">${analysisData.url}</a></div>
                        <div><strong>🏷️ Domaine:</strong> ${analysisData.domain || 'N/A'}</div>
                        <div><strong>🔢 IP:</strong> ${analysisData.ip_address || 'N/A'}</div>
                    </div>
                </div>
                
                <!-- Résumé rapide -->
                <div class="detail-section" style="padding: 0; border-radius: 8px; overflow: hidden;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0; border: 1px solid #e5e7eb;">
                        <div style="padding: 1rem; border-right: 1px solid #e5e7eb; background: #f9fafb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Stack</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>Serveur:</strong> ${escapeHtml(serverLabel)}</div>
                                <div><strong>Framework:</strong> ${escapeHtml(frameworkLabel)}</div>
                                <div><strong>CMS:</strong> ${escapeHtml(cmsLabel)}</div>
                            </div>
                        </div>
                        <div style="padding: 1rem; border-right: 1px solid #e5e7eb; background: #fdfdfb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Sécurité</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>SSL:</strong> ${escapeHtml(sslLabel)}</div>
                                <div><strong>WAF:</strong> ${escapeHtml(wafLabel)}</div>
                                <div><strong>CDN:</strong> ${escapeHtml(cdnLabel)}</div>
                                <div><strong>Score global:</strong> ${getSecurityScoreBadge(securityScore)}</div>
                            </div>
                        </div>
                        <div style="padding: 1rem; background: #f9fafb;">
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #6b7280; letter-spacing: 0.08em; margin-bottom: 0.35rem;">Suivi & analytics</div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <div><strong>Outils d'analyse:</strong> ${escapeHtml(analyticsLabel)}</div>
                                ${perfScore !== null ? `<div><strong>Score performance:</strong> ${getPerformanceScoreBadge(perfScore)}</div>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
                
                ${(() => {
                    const pagesCount = pagesSummary.pages_count || pagesSummary.pages_scanned || pagesList.length || 0;
                    if (!pagesCount) return '';
                    const pagesOk = pagesSummary.pages_ok || 0;
                    const pagesError = pagesSummary.pages_error || 0;
                    const trackersCount = pagesSummary.trackers_count || analysisData.trackers_count || 0;
                    const avgResp = pagesSummary.avg_response_time_ms ? formatMs(pagesSummary.avg_response_time_ms) : 'N/A';
                    const avgWeight = pagesSummary.avg_weight_bytes ? formatBytesShort(pagesSummary.avg_weight_bytes) : 'N/A';
                    const perfBadge = getPerformanceScoreBadge(perfScore);

                    const rows = pagesList.slice(0, 20).map(page => {
                        const pageSecBadge = getSecurityScoreBadge(page.security_score);
                        const pagePerfBadge = getPerformanceScoreBadge(page.performance_score);
                        const statusLabel = page.status_code ? page.status_code : 'N/A';
                        return `
                            <tr>
                                <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis;">
                                    <a href="${page.final_url || page.url}" target="_blank" rel="noopener">${page.url || 'Page'}</a>
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
                            <h3 style="margin: 0 0 0.75rem 0; color: #1f2937;">🛰️ Analyse multi-pages (${pagesCount} page${pagesCount > 1 ? 's' : ''})</h3>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-bottom: 0.75rem;">
                                <div><strong>Score sécurité:</strong> ${getSecurityScoreBadge(securityScore)}</div>
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
                
                <!-- Serveur et infrastructure -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🖥️ Serveur et infrastructure</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${analysisData.server_software ? `<div class="info-row"><span class="info-label">Logiciel serveur:</span><span class="info-value"><span class="badge badge-info">${analysisData.server_software}</span></span></div>` : ''}
                        ${analysisData.framework ? `<div class="info-row"><span class="info-label">Framework:</span><span class="info-value"><span class="badge badge-primary">${analysisData.framework}${analysisData.framework_version ? ' ' + analysisData.framework_version : ''}</span></span></div>` : ''}
                        ${analysisData.cms ? `<div class="info-row"><span class="info-label">CMS:</span><span class="info-value"><span class="badge badge-success">${analysisData.cms}${analysisData.cms_version ? ' ' + analysisData.cms_version : ''}</span></span></div>` : ''}
                        ${analysisData.hosting_provider ? `<div class="info-row"><span class="info-label">Hébergeur:</span><span class="info-value">${analysisData.hosting_provider}</span></div>` : ''}
                        ${analysisData.cdn ? `<div class="info-row"><span class="info-label">CDN:</span><span class="info-value"><span class="badge badge-secondary">${analysisData.cdn}</span></span></div>` : ''}
                        ${analysisData.waf ? `<div class="info-row"><span class="info-label">WAF:</span><span class="info-value"><span class="badge badge-warning">${analysisData.waf}</span></span></div>` : ''}
                    </div>
                </div>
                
                ${analysisData.cms_plugins && Array.isArray(analysisData.cms_plugins) && analysisData.cms_plugins.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔌 Plugins CMS <span class="badge badge-info">${analysisData.cms_plugins.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysisData.cms_plugins.map(plugin => `<span class="badge badge-outline">${escapeHtml(plugin)}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                <!-- Domaine et DNS -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🌍 Domaine et DNS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${analysisData.domain_creation_date ? `<div class="info-row"><span class="info-label">Date de création:</span><span class="info-value">${analysisData.domain_creation_date}</span></div>` : ''}
                        ${analysisData.domain_updated_date ? `<div class="info-row"><span class="info-label">Dernière mise à jour:</span><span class="info-value">${analysisData.domain_updated_date}</span></div>` : ''}
                        ${analysisData.domain_registrar ? `<div class="info-row"><span class="info-label">Registrar:</span><span class="info-value">${analysisData.domain_registrar}</span></div>` : ''}
                    </div>
                </div>
                
                <!-- SSL/TLS -->
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔒 SSL/TLS</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        <div class="info-row">
                            <span class="info-label">SSL valide:</span>
                            <span class="info-value">
                                <span class="badge ${analysisData.ssl_valid ? 'badge-success' : 'badge-danger'}">${analysisData.ssl_valid ? '✓ Oui' : '✗ Non'}</span>
                            </span>
                        </div>
                        ${analysisData.ssl_expiry_date ? `<div class="info-row"><span class="info-label">Date d'expiration:</span><span class="info-value">${analysisData.ssl_expiry_date}</span></div>` : ''}
                    </div>
                </div>
                
                ${analysisData.security_headers && typeof analysisData.security_headers === 'object' && !Array.isArray(analysisData.security_headers) && Object.keys(analysisData.security_headers).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🛡️ En-têtes de sécurité</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem;">
                        ${Object.entries(analysisData.security_headers).map(([key, value]) => {
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
                            return `<div class="info-row"><span class="info-label">${escapeHtml(key)}:</span><span class="info-value"><code style="background: #f5f5f5; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem;">${escapeHtml(display)}</code></span></div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.analytics && Array.isArray(analysisData.analytics) && analysisData.analytics.length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">📈 Outils d'analyse <span class="badge badge-info">${analysisData.analytics.length}</span></h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${analysisData.analytics.map(tool => {
                            let label = '';
                            if (tool && typeof tool === 'object') {
                                const name = tool.name || tool.tool || tool.id || tool.tracking_id || '';
                                const extra = tool.id && tool.id !== name ? ` (${tool.id})` :
                                              tool.tracking_id && tool.tracking_id !== name ? ` (${tool.tracking_id})` : '';
                                label = (name || '[Inconnu]') + extra;
                            } else {
                                label = String(tool);
                            }
                            return `<span class="badge badge-secondary">${escapeHtml(label)}</span>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.seo_meta && typeof analysisData.seo_meta === 'object' && !Array.isArray(analysisData.seo_meta) ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔍 SEO et métadonnées</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: 1fr; gap: 1rem;">
                        ${analysisData.seo_meta.meta_title ? `<div class="info-row"><span class="info-label">Titre:</span><span class="info-value">${escapeHtml(analysisData.seo_meta.meta_title)}</span></div>` : ''}
                        ${analysisData.seo_meta.meta_description ? `<div class="info-row"><span class="info-label">Description:</span><span class="info-value">${escapeHtml(analysisData.seo_meta.meta_description)}</span></div>` : ''}
                        ${analysisData.seo_meta.canonical_url ? `<div class="info-row"><span class="info-label">URL canonique:</span><span class="info-value"><a href="${analysisData.seo_meta.canonical_url}" target="_blank" style="color: #667eea;">${escapeHtml(analysisData.seo_meta.canonical_url)}</a></span></div>` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.performance_metrics && typeof analysisData.performance_metrics === 'object' && !Array.isArray(analysisData.performance_metrics) && Object.keys(analysisData.performance_metrics).length > 0 ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">⚡ Métriques de performance</h3>
                    <div class="info-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${Object.entries(analysisData.performance_metrics).map(([key, value]) => 
                            `<div class="info-row"><span class="info-label">${escapeHtml(key)}:</span><span class="info-value"><strong>${escapeHtml(String(value || 'N/A'))}</strong></span></div>`
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.nmap_scan ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔍 Scan Nmap</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir les détails du scan</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${escapeHtml(JSON.stringify(analysisData.nmap_scan, null, 2))}</pre>
                    </details>
                </div>
                ` : ''}
                
                ${analysisData.technical_details ? `
                <div class="detail-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;">🔧 Détails techniques</h3>
                    <details style="cursor: pointer;">
                        <summary style="padding: 0.5rem; background: #f8f9fa; border-radius: 4px; margin-bottom: 0.5rem;">Voir tous les détails</summary>
                        <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; margin-top: 0.5rem; font-size: 0.85rem; max-height: 400px; overflow-y: auto;">${escapeHtml(JSON.stringify(analysisData.technical_details, null, 2))}</pre>
                    </details>
                </div>
                ` : ''}
            </div>
        `;
                
                ${analysisData.server_software ? `
                <div class="detail-section">
                    <h2>Serveur</h2>
                    <div class="info-grid">
                        ${createInfoRow('Logiciel serveur', analysisData.server_software)}
                        ${createInfoRow('Powered By', techDetails.powered_by)}
                        ${createInfoRow('Version PHP', techDetails.php_version)}
                        ${createInfoRow('Version ASP.NET', techDetails.aspnet_version)}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.framework || analysisData.cms ? `
                <div class="detail-section">
                    <h2>Framework & CMS</h2>
                    <div class="info-grid">
                        ${createInfoRow('Framework', analysisData.framework)}
                        ${createInfoRow('Version framework', analysisData.framework_version)}
                        ${createInfoRow('CMS', analysisData.cms)}
                        ${createInfoRow('Version CMS', analysisData.cms_version)}
                        ${analysisData.cms_plugins && analysisData.cms_plugins.length > 0 ? `
                            <div class="info-row">
                                <span class="info-label">Plugins CMS:</span>
                                <span class="info-value">
                                    ${Array.isArray(analysisData.cms_plugins) 
                                        ? analysisData.cms_plugins.map(p => `<span class="tag">${p}</span>`).join('')
                                        : analysisData.cms_plugins}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.hosting_provider ? `
                <div class="detail-section">
                    <h2>Hébergement</h2>
                    <div class="info-grid">
                        ${createInfoRow('Hébergeur', analysisData.hosting_provider)}
                        ${createInfoRow('Date création domaine', analysisData.domain_creation_date)}
                        ${createInfoRow('Date mise à jour', analysisData.domain_updated_date)}
                        ${createInfoRow('Registrar', analysisData.domain_registrar)}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.ssl_valid !== null ? `
                <div class="detail-section">
                    <h2>Sécurité SSL/TLS</h2>
                    <div class="info-grid">
                        ${createInfoRow('Certificat valide', analysisData.ssl_valid ? 'Oui ✓' : 'Non ✗', false, 
                            analysisData.ssl_valid ? '<span class="badge badge-success">Valide</span>' : '<span class="badge badge-error">Invalide</span>')}
                        ${createInfoRow('Date d\'expiration', analysisData.ssl_expiry_date)}
                        ${createInfoRow('Version SSL', techDetails.ssl_version)}
                        ${createInfoRow('Cipher', techDetails.ssl_cipher)}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.security_headers ? `
                <div class="detail-section">
                    <h2>En-têtes de sécurité</h2>
                    <div class="info-grid">
                        ${Object.entries(analysisData.security_headers).map(([key, value]) => 
                            createInfoRow(key.replace(/_/g, ' '), value ? '✓ Présent' : '✗ Absent', false,
                                value ? '<span class="badge badge-success">Oui</span>' : '<span class="badge badge-error">Non</span>')
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.waf ? `
                <div class="detail-section">
                    <h2>WAF (Web Application Firewall)</h2>
                    <div class="info-grid">
                        ${createInfoRow('WAF détecté', analysisData.waf)}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.cdn ? `
                <div class="detail-section">
                    <h2>CDN</h2>
                    <div class="info-grid">
                        ${createInfoRow('CDN', analysisData.cdn)}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.analytics && analysisData.analytics.length > 0 ? `
                <div class="detail-section">
                    <h2>Analytics & Tracking</h2>
                    <div class="info-grid">
                        ${analysisData.analytics.map(a => createInfoRow('Service', a)).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.seo_meta ? `
                <div class="detail-section full-width">
                    <h2>SEO</h2>
                    <div class="info-grid">
                        ${Object.entries(analysisData.seo_meta).slice(0, 10).map(([key, value]) => 
                            createInfoRow(key.replace(/_/g, ' '), value)
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.performance_metrics ? `
                <div class="detail-section full-width">
                    <h2>Performance</h2>
                    <div class="info-grid">
                        ${Object.entries(analysisData.performance_metrics).map(([key, value]) => 
                            createInfoRow(key.replace(/_/g, ' '), value)
                        ).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${analysisData.nmap_scan ? `
                <div class="detail-section full-width">
                    <h2>Scan Nmap</h2>
                    <div class="info-grid">
                        ${typeof analysisData.nmap_scan === 'object' 
                            ? Object.entries(analysisData.nmap_scan).map(([key, value]) => 
                                createInfoRow(key.replace(/_/g, ' '), value)
                            ).join('')
                            : createInfoRow('Résultat', analysisData.nmap_scan)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['response_time_ms', 'page_size_kb', 'images_count', 'scripts_count']) ? `
                <div class="detail-section">
                    <h2>Performance avancée</h2>
                    <div class="info-grid">
                        ${createInfoRow('Temps de réponse', techDetails.response_time_ms ? `${techDetails.response_time_ms} ms` : null)}
                        ${createInfoRow('Taille de la page', techDetails.page_size_kb ? `${techDetails.page_size_kb} KB` : null)}
                        ${createInfoRow('Nombre d\'images', techDetails.images_count)}
                        ${createInfoRow('Images sans alt', techDetails.images_missing_alt ? `${techDetails.images_missing_alt} images` : null)}
                        ${createInfoRow('Nombre de scripts', techDetails.scripts_count)}
                        ${createInfoRow('Scripts externes', techDetails.external_scripts_count)}
                        ${createInfoRow('Feuilles de style', techDetails.stylesheets_count)}
                        ${createInfoRow('Polices', techDetails.fonts_count)}
                        ${createInfoRow('Liens', techDetails.links_count)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['nextjs', 'nuxtjs', 'svelte', 'gatsby', 'remix', 'astro', 'webpack', 'vite']) ? `
                <div class="detail-section">
                    <h2>Frameworks modernes</h2>
                    <div class="info-grid">
                        ${createInfoRow('Next.js', techDetails.nextjs ? '✓ Détecté' + (techDetails.nextjs_version ? ` (v${techDetails.nextjs_version})` : '') : null)}
                        ${createInfoRow('Nuxt.js', techDetails.nuxtjs ? '✓ Détecté' : null)}
                        ${createInfoRow('Svelte', techDetails.svelte ? '✓ Détecté' : null)}
                        ${createInfoRow('Gatsby', techDetails.gatsby ? '✓ Détecté' : null)}
                        ${createInfoRow('Remix', techDetails.remix ? '✓ Détecté' : null)}
                        ${createInfoRow('Astro', techDetails.astro ? '✓ Détecté' : null)}
                        ${createInfoRow('SvelteKit', techDetails.sveltekit ? '✓ Détecté' : null)}
                        ${createInfoRow('Webpack', techDetails.webpack ? '✓ Détecté' : null)}
                        ${createInfoRow('Vite', techDetails.vite ? '✓ Détecté' : null)}
                        ${createInfoRow('Parcel', techDetails.parcel ? '✓ Détecté' : null)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['html_language', 'charset', 'semantic_html_tags', 'headings_structure']) ? `
                <div class="detail-section">
                    <h2>Structure du contenu</h2>
                    <div class="info-grid">
                        ${createInfoRow('Langue HTML', techDetails.html_language)}
                        ${createInfoRow('Encodage', techDetails.charset)}
                        ${techDetails.semantic_html_tags ? `
                            <div class="info-row">
                                <span class="info-label">Tags sémantiques:</span>
                                <span class="info-value">
                                    ${Object.entries(techDetails.semantic_html_tags).map(([tag, count]) => 
                                        `<span class="tag">${tag}: ${count}</span>`
                                    ).join('')}
                                </span>
                            </div>
                        ` : ''}
                        ${techDetails.headings_structure ? `
                            <div class="info-row">
                                <span class="info-label">Structure des titres:</span>
                                <span class="info-value">
                                    ${Object.entries(techDetails.headings_structure).map(([tag, count]) => 
                                        `<span class="tag">${tag}: ${count}</span>`
                                    ).join('')}
                                </span>
                            </div>
                        ` : ''}
                        ${createInfoRow('Liens externes', techDetails.external_links_count)}
                        ${createInfoRow('Liens internes', techDetails.internal_links_count)}
                        ${createInfoRow('Formulaires', techDetails.forms_count)}
                        ${createInfoRow('Iframes', techDetails.iframes_count)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['mx_records', 'spf_record', 'dmarc_record', 'dkim_record', 'ipv6_support']) ? `
                <div class="detail-section">
                    <h2>DNS avancé</h2>
                    <div class="info-grid">
                        ${createInfoRow('Enregistrements MX', techDetails.mx_records ? '✓ Présents' : null)}
                        ${createInfoRow('SPF', techDetails.spf_record ? '✓ Configuré' : '✗ Non configuré')}
                        ${createInfoRow('DMARC', techDetails.dmarc_record ? '✓ Configuré' : '✗ Non configuré')}
                        ${createInfoRow('DKIM', techDetails.dkim_record ? '✓ Configuré' : '✗ Non configuré')}
                        ${createInfoRow('Support IPv6', techDetails.ipv6_support ? '✓ Oui' : '✗ Non')}
                        ${techDetails.ipv6_addresses ? `
                            <div class="info-row">
                                <span class="info-label">Adresses IPv6:</span>
                                <span class="info-value">
                                    ${techDetails.ipv6_addresses.map(ip => `<span class="tag">${ip}</span>`).join('')}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['mixed_content_detected', 'scripts_without_sri', 'scripts_with_sri', 'cors_enabled']) ? `
                <div class="detail-section">
                    <h2>Sécurité avancée</h2>
                    <div class="info-grid">
                        ${createInfoRow('Contenu mixte', techDetails.mixed_content_detected ? 
                            `<span class="badge badge-error">${techDetails.mixed_content_detected}</span>` : 
                            '<span class="badge badge-success">Aucun</span>')}
                        ${createInfoRow('Scripts sans SRI', techDetails.scripts_without_sri ? 
                            `<span class="badge badge-warning">${techDetails.scripts_without_sri} scripts</span>` : 
                            '<span class="badge badge-success">Tous protégés</span>')}
                        ${createInfoRow('Scripts avec SRI', techDetails.scripts_with_sri ? `${techDetails.scripts_with_sri} scripts` : null)}
                        ${createInfoRow('CORS activé', techDetails.cors_enabled ? techDetails.cors_enabled : null)}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['viewport_meta', 'mobile_friendly', 'apple_touch_icon', 'images_missing_alt_count']) ? `
                <div class="detail-section">
                    <h2>Mobilité & Accessibilité</h2>
                    <div class="info-grid">
                        ${createInfoRow('Viewport meta', techDetails.viewport_meta ? 
                            (techDetails.viewport_meta === 'Manquant' ? 
                                '<span class="badge badge-error">Manquant</span>' : 
                                techDetails.viewport_meta) : null)}
                        ${createInfoRow('Mobile-friendly', techDetails.mobile_friendly ? 
                            '<span class="badge badge-success">Oui</span>' : 
                            '<span class="badge badge-error">Non</span>')}
                        ${createInfoRow('Apple Touch Icon', techDetails.apple_touch_icon ? '✓ Présent' : '✗ Absent')}
                        ${createInfoRow('Theme color', techDetails.theme_color)}
                        ${createInfoRow('Images sans alt', techDetails.images_missing_alt_count ? 
                            `<span class="badge badge-warning">${techDetails.images_missing_alt_count} images</span>` : 
                            '<span class="badge badge-success">Toutes ont un alt</span>')}
                        ${createInfoRow('ARIA labels', techDetails.aria_labels_count ? `${techDetails.aria_labels_count} éléments` : null)}
                        ${createInfoRow('Skip links', techDetails.skip_links ? '✓ Présents' : '✗ Absents')}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['graphql_detected', 'api_endpoints_detected', 'websocket_detected', 'json_ld_count']) ? `
                <div class="detail-section">
                    <h2>API & Endpoints</h2>
                    <div class="info-grid">
                        ${createInfoRow('GraphQL', techDetails.graphql_detected ? '✓ Détecté' : null)}
                        ${createInfoRow('Endpoints API', techDetails.api_endpoints_detected)}
                        ${createInfoRow('WebSocket', techDetails.websocket_detected ? '✓ Détecté' : null)}
                        ${createInfoRow('JSON-LD', techDetails.json_ld_count ? `${techDetails.json_ld_count} schémas` : null)}
                        ${techDetails.structured_data_types ? `
                            <div class="info-row">
                                <span class="info-label">Types de données structurées:</span>
                                <span class="info-value">
                                    ${techDetails.structured_data_types.split(', ').map(type => 
                                        `<span class="tag">${type}</span>`
                                    ).join('')}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${hasData(techDetails, ['crm_service', 'video_service', 'map_service', 'font_service', 'comment_system']) ? `
                <div class="detail-section">
                    <h2>Services tiers supplémentaires</h2>
                    <div class="info-grid">
                        ${createInfoRow('CRM', techDetails.crm_service)}
                        ${techDetails.video_service ? `
                            <div class="info-row">
                                <span class="info-label">Services vidéo:</span>
                                <span class="info-value">
                                    ${Array.isArray(techDetails.video_service) 
                                        ? techDetails.video_service.map(s => `<span class="tag">${s}</span>`).join('')
                                        : `<span class="tag">${techDetails.video_service}</span>`}
                                </span>
                            </div>
                        ` : ''}
                        ${createInfoRow('Service de cartes', techDetails.map_service)}
                        ${techDetails.font_service ? `
                            <div class="info-row">
                                <span class="info-label">Services de polices:</span>
                                <span class="info-value">
                                    ${Array.isArray(techDetails.font_service) 
                                        ? techDetails.font_service.map(s => `<span class="tag">${s}</span>`).join('')
                                        : `<span class="tag">${techDetails.font_service}</span>`}
                                </span>
                            </div>
                        ` : ''}
                        ${createInfoRow('Système de commentaires', techDetails.comment_system)}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    function hasData(obj, keys) {
        if (!obj) return false;
        return keys.some(key => obj[key] !== undefined && obj[key] !== null && obj[key] !== '');
    }
    
    function createInfoRow(label, value, isLink = false, customContent = null) {
        if (!value && !customContent) return '';
        
        const content = customContent || (isLink ? `<a href="${value}" target="_blank">${value}</a>` : value);
        
        return `
            <div class="info-row">
                <span class="info-label">${label}:</span>
                <span class="info-value">${content}</span>
            </div>
        `;
    }
    
    function setupDeleteButton() {
        const pageHeader = document.querySelector('.page-header');
        if (pageHeader && !document.getElementById('btn-delete-analysis')) {
            const headerActions = pageHeader.querySelector('.header-actions');
            if (headerActions) {
                // Bouton "Refaire l'analyse"
                const reanalyzeBtn = document.createElement('button');
                reanalyzeBtn.id = 'btn-reanalyze-analysis';
                reanalyzeBtn.className = 'btn btn-primary';
                reanalyzeBtn.textContent = '🔄 Refaire l\'analyse';
                reanalyzeBtn.onclick = handleReanalyze;
                headerActions.appendChild(reanalyzeBtn);
                
                // Bouton "Supprimer"
                const deleteBtn = document.createElement('button');
                deleteBtn.id = 'btn-delete-analysis';
                deleteBtn.className = 'btn btn-danger';
                deleteBtn.textContent = '🗑️ Supprimer cette analyse';
                deleteBtn.onclick = handleDeleteAnalysis;
                headerActions.appendChild(deleteBtn);
            }
        }
    }
    
    async function handleReanalyze() {
        if (!analysisData || !analysisData.url) {
            showNotification('Impossible de relancer l\'analyse : URL introuvable', 'error');
            return;
        }
        
        if (!confirm(`Voulez-vous relancer l'analyse technique pour "${analysisData.url}" ?\n\nL'analyse existante sera mise à jour avec les nouvelles données.`)) {
            return;
        }
        
        // Afficher un indicateur de progression
        const existingProgress = document.getElementById('reanalysis-progress');
        if (existingProgress) {
            existingProgress.remove();
        }
        
        const progressDiv = document.createElement('div');
        progressDiv.id = 'reanalysis-progress';
        progressDiv.className = 'analysis-progress';
        progressDiv.style.cssText = 'margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #dee2e6;';
        progressDiv.innerHTML = `
            <div class="progress-bar-container">
                <div class="progress-bar" id="reanalysis-progress-bar" style="width: 0%"></div>
            </div>
            <p id="reanalysis-message" class="progress-message">Démarrage de l'analyse...</p>
        `;
        document.getElementById('analyse-detail').prepend(progressDiv);
        
        // Initialiser WebSocket si nécessaire
        if (typeof ProspectLabWebSocket !== 'undefined' && window.wsManager) {
            // Écouter les événements de progression
            window.wsManager.socket.on('technical_analysis_progress', (data) => {
                const progressBar = document.getElementById('reanalysis-progress-bar');
                const progressMessage = document.getElementById('reanalysis-message');
                if (progressBar) {
                    progressBar.style.width = `${data.progress}%`;
                }
                if (progressMessage) {
                    progressMessage.textContent = data.message || 'Analyse en cours...';
                }
            });
            
            window.wsManager.socket.on('technical_analysis_complete', (data) => {
                const progressBar = document.getElementById('reanalysis-progress-bar');
                const progressMessage = document.getElementById('reanalysis-message');
                if (progressBar) {
                    progressBar.style.width = '100%';
                    progressBar.classList.add('success');
                }
                if (progressMessage) {
                    progressMessage.textContent = data.updated ? 'Analyse mise à jour avec succès !' : 'Analyse terminée avec succès !';
                }
                showNotification(data.updated ? 'Analyse mise à jour avec succès !' : 'Analyse terminée avec succès !', 'success');
                setTimeout(() => {
                    if (data.analysis_id) {
                        window.location.href = `/analyse-technique/${data.analysis_id}`;
                    } else {
                        location.reload();
                    }
                }, 1500);
            });
            
            window.wsManager.socket.on('technical_analysis_error', (data) => {
                showNotification(data.error || 'Erreur lors de l\'analyse', 'error');
                document.getElementById('reanalysis-progress')?.remove();
            });
            
            // Lancer l'analyse avec force=true
            window.wsManager.socket.emit('start_technical_analysis', {
                url: analysisData.url,
                enable_nmap: false,
                force: true
            });
        } else {
            showNotification('Erreur : WebSocket non disponible', 'error');
            document.getElementById('reanalysis-progress')?.remove();
        }
    }
    
    async function handleDeleteAnalysis() {
        const analysisName = analysisData.entreprise_nom || analysisData.url || 'cette analyse';
        
        if (!confirm(`Êtes-vous sûr de vouloir supprimer l'analyse technique "${analysisName}" ?\n\nCette action est irréversible.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/analyse-technique/${analysisId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                showNotification('Analyse technique supprimée avec succès', 'success');
                setTimeout(() => {
                    window.location.href = '/analyses-techniques';
                }, 1500);
            } else {
                showNotification(data.error || 'Erreur lors de la suppression', 'error');
            }
        } catch (error) {
            console.error('Erreur lors de la suppression:', error);
            showNotification('Erreur lors de la suppression de l\'analyse', 'error');
        }
    }
    
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
            color: white;
            border-radius: 4px;
            z-index: 10000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
})();

