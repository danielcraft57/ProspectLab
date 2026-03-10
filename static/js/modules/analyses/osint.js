/**
 * Module d'affichage des analyses OSINT
 */

(function(window) {
    'use strict';
    
    if (!window.Formatters) {
        console.error('Module Formatters requis');
        return;
    }
    
    const { Formatters } = window;
    
    /**
     * Affiche une analyse OSINT
     * @param {Object} analysis - Données de l'analyse OSINT
     * @param {HTMLElement} container - Élément DOM où afficher les résultats
     */
    function displayOSINTAnalysis(analysis, container) {
        if (!container) return;
        
        const date = new Date(analysis.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const subdomains = analysis.subdomains || [];
        const emails = analysis.emails || analysis.emails_found || [];
        const socialMedia = analysis.social_media || {};
        const technologies = analysis.technologies_detected || analysis.technologies || {};
        const dnsRecords = analysis.dns_records || {};
        const whoisInfo = analysis.whois_data || analysis.whois_info || {};
        
        const emailCount = Array.isArray(emails) ? emails.length : 0;
        const socialCount = Object.keys(socialMedia).reduce((sum, platform) => {
            const urls = Array.isArray(socialMedia[platform]) ? socialMedia[platform] : [];
            return sum + urls.length;
        }, 0);
        const techCount = Object.keys(technologies).reduce((sum, category) => {
            const techs = Array.isArray(technologies[category]) ? technologies[category] : [];
            return sum + techs.length;
        }, 0);
        
        // Points d'attention OSINT (même pattern que Pentest / Technique / SEO)
        const osintIssues = [];
        if (subdomains.length === 0) {
            osintIssues.push({ severity: 'info', title: 'Aucun sous-domaine détecté', description: 'Aucun sous-domaine n\'a été trouvé pour ce domaine.', recommendation: 'Vérifier la configuration DNS ou étendre la recherche.' });
        } else if (subdomains.length > 10) {
            osintIssues.push({ severity: 'medium', title: 'Surface d\'attaque étendue', description: `${subdomains.length} sous-domaines exposés. Chaque sous-domaine peut être un point d'entrée.`, recommendation: 'Auditer la nécessité de chaque sous-domaine et sécuriser les services exposés.' });
        }
        if (emailCount === 0) {
            osintIssues.push({ severity: 'info', title: 'Aucun email collecté', description: 'Aucune adresse email trouvée en open source.', recommendation: 'Enrichir avec d\'autres sources (scraping site, LinkedIn, etc.).' });
        }
        if (socialCount === 0) {
            osintIssues.push({ severity: 'info', title: 'Aucun réseau social lié', description: 'Aucun profil réseau social identifié pour ce domaine.', recommendation: 'Rechercher manuellement le nom de l\'entreprise sur les plateformes sociales.' });
        }
        if (techCount === 0 && (subdomains.length > 0 || emailCount > 0)) {
            osintIssues.push({ severity: 'low', title: 'Technologies non identifiées', description: 'Aucune technologie détectée malgré des données présentes.', recommendation: 'Relancer une analyse avec détection technologies activée.' });
        }
        const whoisKeys = Object.keys(whoisInfo).filter(k => whoisInfo[k] && typeof whoisInfo[k] !== 'object');
        if (whoisKeys.length === 0 && (analysis.domain || analysis.url)) {
            osintIssues.push({ severity: 'low', title: 'WHOIS non disponible', description: 'Les données WHOIS n\'ont pas été récupérées.', recommendation: 'Vérifier la disponibilité WHOIS du TLD ou utiliser un autre outil.' });
        }
        const osintCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
        osintIssues.forEach(i => { if (osintCounts[i.severity] !== undefined) osintCounts[i.severity]++; });
        const hasOsintIssues = osintIssues.length > 0;
        
        const createStatCard = (icon, label, value, color = '#9333ea') => `
            <div style="background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <div style="width: 40px; height: 40px; border-radius: 8px; background: ${color}15; display: flex; align-items: center; justify-content: center; font-size: 1.25rem;">
                        ${icon}
                    </div>
                    <div>
                        <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 0.25rem;">${label}</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #111827;">${value}</div>
                    </div>
                </div>
            </div>
        `;
        
        let html = `
            <div class="analysis-details" style="display: flex; flex-direction: column; gap: 1.5rem;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(103, 116, 222, 0.35);">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1.5rem;">
                        <div>
                            <h3 style="margin: 0 0 0.5rem 0; color: white; font-size: 1.5rem; font-weight: 700;">Analyse OSINT</h3>
                            <div style="font-size: 0.9rem; opacity: 0.9;">${date}</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.2); padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem;">
                            ${Formatters.escapeHtml(analysis.domain || 'N/A')}
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem;">
                        ${createStatCard('<i class="fas fa-globe"></i>', 'Sous-domaines', subdomains.length, '#9333ea')}
                        ${createStatCard('<i class="fas fa-envelope"></i>', 'Emails', emailCount, '#3b82f6')}
                        ${createStatCard('<i class="fas fa-users"></i>', 'Réseaux sociaux', socialCount, '#10b981')}
                        ${createStatCard('<i class="fas fa-cog"></i>', 'Technologies', techCount, '#f59e0b')}
                    </div>
                    ${analysis.url ? `
                        <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.2);">
                            <a href="${analysis.url}" target="_blank" style="color: white; text-decoration: none; font-weight: 500; display: inline-flex; align-items: center; gap: 0.5rem;">
                                <i class="fas fa-globe"></i>
                                <span>${Formatters.escapeHtml(analysis.url)}</span>
                                <i class="fas fa-external-link-alt" style="font-size: 0.75rem;"></i>
                            </a>
                        </div>
                    ` : ''}
                </div>
                
                ${hasOsintIssues ? `
                <div class="detail-section osint-issues-section">
                    <h3 style="margin: 0 0 1rem 0; color: #2c3e50; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;"><i class="fas fa-exclamation-triangle"></i> Points d'attention OSINT <span class="badge badge-warning">${osintIssues.length}</span></h3>
                    <div class="osint-summary-chips">
                        ${osintCounts.critical ? `<span class="osint-chip osint-chip-critical">${osintCounts.critical} critique${osintCounts.critical > 1 ? 's' : ''}</span>` : ''}
                        ${osintCounts.high ? `<span class="osint-chip osint-chip-high">${osintCounts.high} haute${osintCounts.high > 1 ? 's' : ''}</span>` : ''}
                        ${osintCounts.medium ? `<span class="osint-chip osint-chip-medium">${osintCounts.medium} moyenne${osintCounts.medium > 1 ? 's' : ''}</span>` : ''}
                        ${osintCounts.low ? `<span class="osint-chip osint-chip-low">${osintCounts.low} faible${osintCounts.low > 1 ? 's' : ''}</span>` : ''}
                        ${osintCounts.info ? `<span class="osint-chip osint-chip-info">${osintCounts.info} info</span>` : ''}
                    </div>
                    <div class="osint-issues-list" style="display: flex; flex-direction: column; gap: 0.75rem; margin-top: 1rem;">
                        ${osintIssues.map(issue => {
                            const borderColors = { critical: '#e74c3c', high: '#e67e22', medium: '#f39c12', low: '#3498db', info: '#6b7280' };
                            const color = borderColors[issue.severity] || '#6b7280';
                            return `<div class="osint-issue-card" style="border-left: 4px solid ${color};">
                                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem;">
                                    <strong class="osint-issue-title">${Formatters.escapeHtml(issue.title)}</strong>
                                    <span class="osint-chip osint-chip-${issue.severity}" style="font-size: 0.75rem;">${Formatters.escapeHtml(issue.severity)}</span>
                                </div>
                                ${issue.description ? `<div class="osint-issue-desc">${Formatters.escapeHtml(issue.description)}</div>` : ''}
                                ${issue.recommendation ? `<div class="osint-issue-reco"><strong><i class="fas fa-lightbulb"></i> Recommandation:</strong> ${Formatters.escapeHtml(issue.recommendation)}</div>` : ''}
                            </div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${subdomains.length > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-globe"></i>
                        <span>Sous-domaines</span>
                        <span style="background: #e9d5ff; color: #6b21a8; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">${subdomains.length}</span>
                    </h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${subdomains.map(sub => `
                            <div style="background: #f3f4f6; padding: 0.5rem 0.75rem; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.9rem; color: #374151; border: 1px solid #e5e7eb;">
                                ${Formatters.escapeHtml(sub)}
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${emailCount > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-envelope"></i>
                        <span>Emails trouvés</span>
                        <span style="background: #dbeafe; color: #1e40af; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">${emailCount}</span>
                    </h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${emails.map(emailData => {
                            const email = typeof emailData === 'string' ? emailData : (emailData.email || emailData.value || '');
                            const source = typeof emailData === 'object' && emailData.source ? emailData.source : null;
                            return `
                                <a href="mailto:${email}" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 0.5rem 0.75rem; border-radius: 6px; text-decoration: none; font-size: 0.9rem; display: inline-flex; align-items: center; gap: 0.5rem; box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3); transition: transform 0.2s;">
                                    <i class="fas fa-envelope"></i>
                                    <span>${Formatters.escapeHtml(email)}</span>
                                    ${source ? `<span style="font-size: 0.75rem; opacity: 0.8;">(${Formatters.escapeHtml(source)})</span>` : ''}
                                </a>
                            `;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${socialCount > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-users"></i>
                        <span>Réseaux sociaux</span>
                        <span style="background: #d1fae5; color: #065f46; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">${socialCount}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${Object.entries(socialMedia).map(([platform, urls]) => {
                            const urlList = Array.isArray(urls) ? urls : [urls];
                            return `
                                <div>
                                    <div style="font-weight: 600; color: #374151; margin-bottom: 0.5rem; text-transform: capitalize;">${Formatters.escapeHtml(platform)}</div>
                                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                        ${urlList.map(url => `
                                            <a href="${url}" target="_blank" style="background: #f3f4f6; padding: 0.5rem 0.75rem; border-radius: 6px; text-decoration: none; color: #2563eb; font-size: 0.9rem; border: 1px solid #e5e7eb; display: inline-flex; align-items: center; gap: 0.5rem; transition: background 0.2s;" onmouseover="this.style.background='#e5e7eb'" onmouseout="this.style.background='#f3f4f6'">
                                                <i class="fas fa-link"></i>
                                                <span>${Formatters.escapeHtml(url)}</span>
                                                <i class="fas fa-external-link-alt" style="font-size: 0.75rem;"></i>
                                            </a>
                                        `).join('')}
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${techCount > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-cog"></i>
                        <span>Technologies détectées</span>
                        <span style="background: #fef3c7; color: #92400e; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">${techCount}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 1rem;">
                        ${Object.entries(technologies)
                            .filter(([category]) => {
                                const lowerCategory = category.toLowerCase();
                                return !lowerCategory.includes('raw_output') && 
                                       !lowerCategory.includes('error') && 
                                       !lowerCategory.includes('non disponible') &&
                                       category !== 'raw_output' &&
                                       category !== 'error';
                            })
                            .map(([category, techs]) => {
                            const techList = Array.isArray(techs) ? techs : [techs];
                            const validTechs = techList.filter(tech => {
                                if (!tech) return false;
                                const techStr = String(tech).toLowerCase();
                                return !techStr.includes('non disponible') && 
                                       !techStr.includes('error') &&
                                       techStr.trim().length > 0;
                            });
                            
                            if (validTechs.length === 0) return '';
                            
                            return `
                                <div>
                                    <div style="font-weight: 600; color: #374151; margin-bottom: 0.5rem; text-transform: capitalize; font-size: 0.95rem;">
                                        ${Formatters.escapeHtml(category.replace(/_/g, ' '))}
                                    </div>
                                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                        ${validTechs.map(tech => `
                                            <div style="background: #fef3c7; padding: 0.5rem 0.75rem; border-radius: 6px; font-size: 0.9rem; color: #92400e; border: 1px solid #fde68a; font-weight: 500;">
                                                ${Formatters.escapeHtml(String(tech))}
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                            `;
                        })
                        .filter(html => html !== '')
                        .join('')}
                    </div>
                </div>
                ` : ''}
                
                ${Object.keys(dnsRecords).length > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-satellite-dish"></i>
                        <span>Enregistrements DNS</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${Object.entries(dnsRecords).map(([type, records]) => {
                            const recordList = Array.isArray(records) ? records : [records];
                            return `
                                <div>
                                    <div style="font-weight: 600; color: #374151; margin-bottom: 0.5rem; font-family: 'Courier New', monospace;">${Formatters.escapeHtml(type)}</div>
                                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                        ${recordList.map(record => `
                                            <div style="background: #f3f4f6; padding: 0.5rem 0.75rem; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; color: #374151; border: 1px solid #e5e7eb;">
                                                ${Formatters.escapeHtml(String(record))}
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${Object.keys(whoisInfo).length > 0 ? `
                <div class="detail-section" style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h3 style="margin: 0 0 1rem 0; color: #111827; font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-clipboard"></i>
                        <span>Informations WHOIS</span>
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                        ${Object.entries(whoisInfo).filter(([key, value]) => value && typeof value !== 'object').map(([key, value]) => `
                            <div>
                                <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 0.25rem; text-transform: capitalize;">${Formatters.escapeHtml(key.replace(/_/g, ' '))}</div>
                                <div style="font-weight: 500; color: #111827;">${Formatters.escapeHtml(String(value))}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${(!subdomains.length && !emailCount && !socialCount && !techCount && !Object.keys(dnsRecords).length && !Object.keys(whoisInfo).length) ? `
                <div style="text-align: center; padding: 3rem; color: #6b7280;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;"><i class="fas fa-search"></i></div>
                    <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">Aucune donnée OSINT disponible</div>
                    <div style="font-size: 0.9rem;">Lancez une analyse OSINT pour collecter des informations.</div>
                </div>
                ` : ''}
            </div>
        `;
        
        container.innerHTML = html;
    }
    
    // Exposer globalement
    window.OSINTAnalysisDisplay = { displayOSINTAnalysis };
})(window);

