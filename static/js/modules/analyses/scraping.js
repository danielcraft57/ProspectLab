/**
 * Module d'affichage des résultats de scraping
 */

(function(window) {
    'use strict';
    
    if (!window.Formatters) {
        console.error('Module Formatters requis');
        return;
    }
    
    const { Formatters } = window;
    
    /**
     * Met à jour le compteur dans l'onglet
     * @param {string} type - Type de données (emails, people, etc.)
     * @param {number} count - Nombre d'éléments
     */
    function updateModalCount(type, count) {
        const countElement = document.getElementById(`count-${type}-modal`);
        if (countElement) {
            countElement.textContent = count;
        }
    }
    
    /**
     * Affiche les statistiques de scraping (cliquables pour naviguer)
     * @param {Object} stats - Statistiques à afficher
     */
    function displayScrapingStats(stats) {
        const statsContainer = document.getElementById('scraping-stats');
        if (!statsContainer) return;
        
        const statCards = [
            { icon: 'fa-envelope', label: 'Emails', value: stats.emails, color: '#3b82f6', tab: 'emails' },
            { icon: 'fa-users', label: 'Personnes', value: stats.people, color: '#10b981', tab: 'people' },
            { icon: 'fa-phone', label: 'Téléphones', value: stats.phones, color: '#f59e0b', tab: 'phones' },
            { icon: 'fa-share-alt', label: 'Réseaux', value: stats.social, color: '#8b5cf6', tab: 'social' },
            { icon: 'fa-code', label: 'Technologies', value: stats.technologies, color: '#ef4444', tab: 'technologies' },
            { icon: 'fa-info-circle', label: 'Métadonnées', value: stats.metadata, color: '#64748b', tab: 'metadata' }
        ];

        // Vider le conteneur puis ajouter de vraies cartes DOM pour conserver les handlers
        statsContainer.innerHTML = '';
        statCards.forEach(stat => {
            const card = document.createElement('div');
            card.className = 'scraping-stat-card';
            card.setAttribute('data-tab', stat.tab);
            card.onclick = function() {
                const tabName = stat.tab;
                const panels = document.querySelectorAll('#scraping-results .tab-content');
                panels.forEach(p => {
                    p.classList.remove('active');
                    p.style.display = 'none';
                });
                const targetPanel = document.getElementById(`tab-${tabName}-modal`);
                if (targetPanel) {
                    targetPanel.classList.add('active');
                    targetPanel.style.display = 'block';
                }
                const searchContainer = document.getElementById('scraping-search-container');
                if (searchContainer) {
                    if (['emails', 'people', 'phones', 'social', 'technologies'].includes(tabName)) {
                        searchContainer.style.display = 'block';
                    } else {
                        searchContainer.style.display = 'none';
                    }
                }
            };
            card.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <div style="width: 40px; height: 40px; border-radius: 10px; background: ${stat.color}15; display: flex; align-items: center; justify-content: center; color: ${stat.color}; flex-shrink: 0;">
                        <i class="fas ${stat.icon}" style="font-size: 1.1rem;"></i>
                    </div>
                    <div style="flex: 1; min-width: 0;">
                        <div style="font-size: 1.5rem; font-weight: 700; color: #1e293b; line-height: 1.2;">${stat.value}</div>
                        <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.25rem;">${stat.label}</div>
                    </div>
                    ${stat.value > 0 ? '<i class="fas fa-chevron-right" style="color: #cbd5e1; font-size: 0.875rem;"></i>' : ''}
                </div>
            `;
            statsContainer.appendChild(card);
        });
    }
    
    /**
     * Affiche la liste des emails
     * @param {Array} emails - Liste des emails
     */
    function displayEmails(emails) {
        const emailsList = document.getElementById('emails-list-modal');
        if (!emailsList) return;
        
        emailsList.innerHTML = '';
        if (emails.length === 0) {
            emailsList.innerHTML = '<div class="empty-state" style="text-align: center; padding: 2rem; color: #94a3b8;"><i class="fas fa-envelope" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><p>Aucun email trouvé</p></div>';
        } else {
            emails.forEach(email => {
                const emailObj = (typeof email === 'object' && email !== null) ? email : null;
                const analysis = emailObj ? (emailObj.analysis || null) : null;
                const emailStr = typeof email === 'string' ? email : (emailObj?.email || emailObj?.value || '');
                if (emailStr) {
                    const metaParts = [];
                    if (analysis) {
                        if (analysis.provider) metaParts.push(`${analysis.provider}`);
                        if (analysis.type) metaParts.push(`${analysis.type}`);
                        if (analysis.mx_valid === true) metaParts.push('MX OK');
                        else if (analysis.mx_valid === false) metaParts.push('MX KO');
                        if (analysis.risk_score !== undefined && analysis.risk_score !== null && analysis.risk_score !== '') {
                            metaParts.push(`Score ${analysis.risk_score}`);
                        }
                    }
                    const metaLine = metaParts.length ? metaParts.slice(0, 3).join(' • ') : '';
                    const searchable = [emailStr, ...metaParts].join(' ').trim();
                    const item = document.createElement('div');
                    item.setAttribute('data-searchable', searchable);
                    item.style.cssText = 'background: white; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08); display: flex; align-items: center; gap: 1rem; transition: transform 0.2s, box-shadow 0.2s; border-left: 3px solid #3b82f6; position: relative;';
                    item.onmouseover = function() { this.style.transform = 'translateY(-2px)'; this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)'; };
                    item.onmouseout = function() { this.style.transform = 'translateY(0)'; this.style.boxShadow = '0 2px 6px rgba(0,0,0,0.08)'; };
                    item.innerHTML = `
                        <div style="width: 40px; height: 40px; border-radius: 10px; background: #3b82f615; display: flex; align-items: center; justify-content: center; color: #3b82f6; flex-shrink: 0;">
                            <i class="fas fa-envelope"></i>
                        </div>
                        <div style="flex: 1; min-width: 0;">
                            <a href="mailto:${Formatters.escapeHtml(emailStr)}" style="color: #1e293b; font-weight: 600; text-decoration: none; font-size: 1rem; word-break: break-all;">${Formatters.escapeHtml(emailStr)}</a>
                            ${metaLine ? `<div style="color: #64748b; font-size: 0.85rem; margin-top: 0.25rem; word-break: break-word;">${Formatters.escapeHtml(metaLine)}</div>` : ''}
                        </div>
                        <button data-copy-email="${Formatters.escapeHtml(emailStr)}" 
                                style="background: #f1f5f9; border: none; border-radius: 6px; padding: 0.5rem; color: #64748b; cursor: pointer; transition: all 0.2s; opacity: 0;"
                                onmouseover="this.style.background='#e2e8f0'; this.style.opacity='1';"
                                onmouseout="this.style.background='#f1f5f9'; this.style.opacity='0';"
                                title="Copier l'email">
                            <i class="fas fa-copy" style="font-size: 0.875rem;"></i>
                        </button>
                    `;
                    emailsList.appendChild(item);
                }
            });
        }
        updateModalCount('emails', emails.length);
    }
    
    /**
     * Affiche la liste des personnes
     * @param {Array} people - Liste des personnes
     */
    function displayPeople(people) {
        const peopleList = document.getElementById('people-list-modal');
        if (!peopleList) return;
        
        peopleList.innerHTML = '';
        if (people.length === 0) {
            peopleList.innerHTML = '<div class="empty-state" style="text-align: center; padding: 2rem; color: #94a3b8;"><i class="fas fa-users" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><p>Aucune personne trouvée</p></div>';
        } else {
            people.forEach(person => {
                const item = document.createElement('div');
                const name = person.name || person.full_name || 'Inconnu';
                const title = person.title || person.job_title || '';
                const email = person.email || '';
                const searchableText = `${name} ${title} ${email}`.trim();
                item.setAttribute('data-searchable', searchableText);
                item.style.cssText = 'background: white; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08); display: flex; align-items: flex-start; gap: 1rem; transition: transform 0.2s, box-shadow 0.2s; border-left: 3px solid #10b981; position: relative;';
                item.onmouseover = function() { this.style.transform = 'translateY(-2px)'; this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)'; };
                item.onmouseout = function() { this.style.transform = 'translateY(0)'; this.style.boxShadow = '0 2px 6px rgba(0,0,0,0.08)'; };
                item.innerHTML = `
                    <div style="width: 40px; height: 40px; border-radius: 10px; background: #10b98115; display: flex; align-items: center; justify-content: center; color: #10b981; flex-shrink: 0;">
                        <i class="fas fa-user"></i>
                    </div>
                    <div style="flex: 1; min-width: 0;">
                        <div style="color: #1e293b; font-weight: 600; font-size: 1rem; margin-bottom: 0.25rem;">${Formatters.escapeHtml(name)}</div>
                        ${title ? `<div style="color: #64748b; font-size: 0.9rem; margin-bottom: 0.25rem;"><i class="fas fa-briefcase" style="margin-right: 0.5rem;"></i>${Formatters.escapeHtml(title)}</div>` : ''}
                        ${email ? `<div style="color: #64748b; font-size: 0.9rem;"><a href="mailto:${Formatters.escapeHtml(email)}" style="color: #3b82f6; text-decoration: none;"><i class="fas fa-envelope" style="margin-right: 0.5rem;"></i>${Formatters.escapeHtml(email)}</a></div>` : ''}
                    </div>
                `;
                peopleList.appendChild(item);
            });
        }
        updateModalCount('people', people.length);
    }
    
    /**
     * Affiche la liste des téléphones
     * @param {Array} phones - Liste des téléphones
     */
    function displayPhones(phones) {
        const phonesList = document.getElementById('phones-list-modal');
        if (!phonesList) return;
        
        phonesList.innerHTML = '';
        if (phones.length === 0) {
            phonesList.innerHTML = '<div class="empty-state" style="text-align: center; padding: 2rem; color: #94a3b8;"><i class="fas fa-phone" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><p>Aucun téléphone trouvé</p></div>';
        } else {
            phones.forEach(phoneData => {
                const phoneObj = (typeof phoneData === 'object' && phoneData !== null) ? phoneData : null;
                const phoneStr = phoneObj && phoneObj.phone
                    ? phoneObj.phone
                    : (typeof phoneData === 'string' ? phoneData : String(phoneData));
                if (phoneStr) {
                    const phoneE164 = phoneObj?.phone_e164 || '';
                    const carrier = phoneObj?.carrier || '';
                    const location = phoneObj?.location || '';
                    const lineType = phoneObj?.line_type || '';
                    const valid = phoneObj?.valid;

                    const metaParts = [];
                    if (carrier) metaParts.push(carrier);
                    if (lineType) metaParts.push(lineType);
                    if (location) metaParts.push(location);
                    const metaLine = metaParts.length ? metaParts.slice(0, 3).join(' • ') : '';

                    const validBadge = (valid === true) ? 'Validé' : ((valid === false) ? 'Invalide' : '');
                    const e164Line = (phoneE164 && phoneE164 !== phoneStr) ? `E.164: ${phoneE164}` : '';

                    const searchable = [
                        phoneStr,
                        phoneE164,
                        carrier,
                        location,
                        lineType,
                    ].filter(Boolean).join(' ');

                    const item = document.createElement('div');
                    item.setAttribute('data-searchable', searchable);
                    item.style.cssText = 'background: white; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08); display: flex; align-items: center; gap: 1rem; transition: transform 0.2s, box-shadow 0.2s; border-left: 3px solid #f59e0b; position: relative;';
                    item.onmouseover = function() { this.style.transform = 'translateY(-2px)'; this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)'; };
                    item.onmouseout = function() { this.style.transform = 'translateY(0)'; this.style.boxShadow = '0 2px 6px rgba(0,0,0,0.08)'; };
                    item.innerHTML = `
                        <div style="width: 40px; height: 40px; border-radius: 10px; background: #f59e0b15; display: flex; align-items: center; justify-content: center; color: #f59e0b; flex-shrink: 0;">
                            <i class="fas fa-phone"></i>
                        </div>
                        <div style="flex: 1; min-width: 0;">
                            <a href="tel:${Formatters.escapeHtml(phoneStr)}" style="color: #1e293b; font-weight: 600; text-decoration: none; font-size: 1rem;">${Formatters.escapeHtml(phoneStr)}</a>
                            ${validBadge ? `<div style="display:inline-flex; align-items:center; gap:0.4rem; margin-top:0.35rem;"><span style="background: ${validBadge === 'Validé' ? '#10b98122' : '#ef444422'}; color:${validBadge === 'Validé' ? '#059669' : '#dc2626'}; font-size:0.8rem; font-weight:600; padding:0.15rem 0.5rem; border-radius:999px;">${Formatters.escapeHtml(validBadge)}</span></div>` : ''}
                            ${(e164Line || metaLine) ? `<div style="color: #64748b; font-size: 0.85rem; margin-top: 0.25rem; word-break: break-word;">${Formatters.escapeHtml([e164Line, metaLine].filter(Boolean).join(' • '))}</div>` : ''}
                        </div>
                        <button data-copy-phone="${Formatters.escapeHtml(phoneStr)}" 
                                style="background: #f1f5f9; border: none; border-radius: 6px; padding: 0.5rem; color: #64748b; cursor: pointer; transition: all 0.2s; opacity: 0;"
                                onmouseover="this.style.background='#e2e8f0'; this.style.opacity='1';"
                                onmouseout="this.style.background='#f1f5f9'; this.style.opacity='0';"
                                title="Copier le téléphone">
                            <i class="fas fa-copy" style="font-size: 0.875rem;"></i>
                        </button>
                    `;
                    phonesList.appendChild(item);
                }
            });
        }
        updateModalCount('phones', phones.length);
    }
    
    /**
     * Affiche la liste des réseaux sociaux
     * @param {Object} social - Objet contenant les réseaux sociaux par plateforme
     */
    function displaySocial(social) {
        const socialList = document.getElementById('social-list-modal');
        if (!socialList) return;
        
        socialList.innerHTML = '';
        const socialEntries = Object.entries(social);
        if (socialEntries.length === 0) {
            socialList.innerHTML = '<div class="empty-state" style="text-align: center; padding: 2rem; color: #94a3b8;"><i class="fas fa-share-alt" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><p>Aucun réseau social trouvé</p></div>';
        } else {
            const platformColors = {
                'facebook': '#1877f2',
                'twitter': '#1da1f2',
                'linkedin': '#0a66c2',
                'instagram': '#e4405f',
                'youtube': '#ff0000',
                'github': '#181717'
            };
            Object.entries(social).forEach(([platform, links]) => {
                const linkList = Array.isArray(links) ? links : [links];
                linkList.forEach(link => {
                        const url = typeof link === 'object' ? link.url : link;
                    if (url) {
                        const item = document.createElement('div');
                        const platformLower = platform.toLowerCase();
                        const color = platformColors[platformLower] || '#8b5cf6';
                        const platformIcons = {
                            'facebook': 'fab fa-facebook',
                            'twitter': 'fab fa-twitter',
                            'linkedin': 'fab fa-linkedin',
                            'instagram': 'fab fa-instagram',
                            'youtube': 'fab fa-youtube',
                            'github': 'fab fa-github'
                        };
                        const iconClass = platformIcons[platformLower] || 'fas fa-link';
                        const searchableText = `${platform} ${url}`;
                        item.setAttribute('data-searchable', searchableText);
                        item.style.cssText = `background: white; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08); display: flex; align-items: center; gap: 1rem; transition: transform 0.2s, box-shadow 0.2s; border-left: 3px solid ${color}; position: relative;`;
                        item.onmouseover = function() { this.style.transform = 'translateY(-2px)'; this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)'; };
                        item.onmouseout = function() { this.style.transform = 'translateY(0)'; this.style.boxShadow = '0 2px 6px rgba(0,0,0,0.08)'; };
                        item.innerHTML = `
                            <div style="width: 40px; height: 40px; border-radius: 10px; background: ${color}15; display: flex; align-items: center; justify-content: center; color: ${color}; flex-shrink: 0;">
                                <i class="${iconClass}"></i>
                            </div>
                            <div style="flex: 1; min-width: 0;">
                                <a href="${Formatters.escapeHtml(url)}" target="_blank" style="color: #1e293b; font-weight: 600; text-decoration: none; font-size: 1rem; word-break: break-all;">${Formatters.escapeHtml(platform)}</a>
                                <div style="color: #64748b; font-size: 0.85rem; margin-top: 0.25rem; word-break: break-all;">${Formatters.escapeHtml(url)}</div>
                            </div>
                        `;
                        socialList.appendChild(item);
                    }
                });
            });
        }
        updateModalCount('social', Object.keys(social).length);
    }
    
    /**
     * Affiche la liste des technologies
     * @param {Object} technologies - Objet contenant les technologies par catégorie
     */
    function displayTechnologies(technologies) {
        const techList = document.getElementById('technologies-list-modal');
        if (!techList) return;
        
        techList.innerHTML = '';
        if (!technologies || Object.keys(technologies).length === 0) {
            techList.innerHTML = '<div class="empty-state" style="text-align: center; padding: 2rem; color: #94a3b8;"><i class="fas fa-code" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><p>Aucune technologie détectée</p></div>';
        } else {
            Object.entries(technologies).forEach(([category, techs]) => {
                const techListStr = Array.isArray(techs) ? techs : [techs];
                const searchableText = `${category} ${techListStr.join(' ')}`;
                const categoryDiv = document.createElement('div');
                categoryDiv.setAttribute('data-searchable', searchableText);
                categoryDiv.style.cssText = 'background: white; border-radius: 10px; padding: 1.25rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08); border-left: 3px solid #ef4444;';
                categoryDiv.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                        <div style="width: 40px; height: 40px; border-radius: 10px; background: #ef444415; display: flex; align-items: center; justify-content: center; color: #ef4444; flex-shrink: 0;">
                            <i class="fas fa-cog"></i>
                        </div>
                        <div style="flex: 1;">
                            <strong style="color: #1e293b; font-size: 1.1rem; font-weight: 600;">${Formatters.escapeHtml(category.charAt(0).toUpperCase() + category.slice(1))}</strong>
                        </div>
                    </div>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${techListStr.map(tech => `<span style="background: #f1f5f9; color: #475569; padding: 0.4rem 0.75rem; border-radius: 6px; font-size: 0.875rem; font-weight: 500;">${Formatters.escapeHtml(tech)}</span>`).join('')}
                    </div>
                `;
                techList.appendChild(categoryDiv);
            });
        }
        updateModalCount('tech', Object.keys(technologies || {}).length);
    }
    
    /**
     * Affiche les métadonnées
     * @param {Object} metadata - Objet contenant les métadonnées
     */
    function displayMetadata(metadata) {
        const metadataList = document.getElementById('metadata-list-modal');
        if (!metadataList) return;
        
        metadataList.innerHTML = '';
        if (!metadata || Object.keys(metadata).length === 0) {
            metadataList.innerHTML = '<div class="empty-state" style="text-align: center; padding: 2rem; color: #94a3b8;"><i class="fas fa-info-circle" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i><p>Aucune métadonnée extraite</p></div>';
        } else {
            Object.entries(metadata).forEach(([key, value]) => {
                if (value === null || value === undefined) return;
                
                const item = document.createElement('div');
                item.style.cssText = 'background: white; border-radius: 10px; padding: 1.25rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08); border-left: 3px solid #64748b;';
                
                let displayValue = '';
                if (typeof value === 'object') {
                    if (Array.isArray(value)) {
                        displayValue = value.map(v => Formatters.escapeHtml(String(v))).join(', ');
                    } else {
                        displayValue = Object.entries(value).map(([k, v]) => 
                            `<div style="margin-left: 1rem; margin-top: 0.5rem;"><strong>${Formatters.escapeHtml(k)}:</strong> ${Formatters.escapeHtml(String(v))}</div>`
                        ).join('');
                    }
                } else {
                    displayValue = Formatters.escapeHtml(String(value));
                }
                
                item.innerHTML = `
                    <div style="display: flex; align-items: flex-start; gap: 1rem;">
                        <div style="width: 40px; height: 40px; border-radius: 10px; background: #64748b15; display: flex; align-items: center; justify-content: center; color: #64748b; flex-shrink: 0;">
                            <i class="fas fa-info-circle"></i>
                        </div>
                        <div style="flex: 1; min-width: 0;">
                            <div style="color: #1e293b; font-weight: 600; font-size: 1rem; margin-bottom: 0.5rem; text-transform: capitalize;">${Formatters.escapeHtml(key.replace(/_/g, ' '))}</div>
                            <div style="color: #64748b; font-size: 0.9rem; word-break: break-word;">${displayValue}</div>
                        </div>
                    </div>
                `;
                metadataList.appendChild(item);
            });
        }
    }
    
    /**
     * Affiche le bloc Issues / Points d'attention du scraping (chips + cartes, même pattern que Pentest/Technique/SEO)
     * @param {Object} stats - { emails, people, phones, social, technologies, metadata }
     */
    function displayScrapingIssues(stats) {
        const container = document.getElementById('scraping-issues-content');
        if (!container) return;
        const issues = [];
        if ((stats.emails || 0) === 0) {
            issues.push({ severity: 'info', title: 'Aucun email trouvé', description: 'Le scraping n\'a pas collecté d\'adresses email.', recommendation: 'Vérifier les pages contact / à propos ou lancer un scraping ciblé.' });
        }
        if ((stats.people || 0) === 0) {
            issues.push({ severity: 'info', title: 'Aucune personne identifiée', description: 'Aucun nom ou contact de personne n\'a été extrait.', recommendation: 'Enrichir avec une page équipe ou LinkedIn.' });
        }
        if ((stats.phones || 0) === 0) {
            issues.push({ severity: 'low', title: 'Aucun numéro de téléphone', description: 'Aucun numéro de téléphone trouvé sur le site.', recommendation: 'Vérifier la page contact et les pieds de page.' });
        }
        if ((stats.social || 0) === 0) {
            issues.push({ severity: 'info', title: 'Aucun lien réseau social', description: 'Aucun lien vers les réseaux sociaux n\'a été détecté.', recommendation: 'Rechercher manuellement les profils ou relancer le scraping.' });
        }
        if ((stats.technologies || 0) === 0) {
            issues.push({ severity: 'low', title: 'Aucune technologie détectée', description: 'Aucune technologie (CMS, framework) n\'a été identifiée.', recommendation: 'L\'analyse technique peut compléter cette donnée.' });
        }
        const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
        issues.forEach(i => { if (counts[i.severity] !== undefined) counts[i.severity]++; });
        const borderColors = { critical: '#e74c3c', high: '#e67e22', medium: '#f39c12', low: '#3498db', info: '#6b7280' };
        if (issues.length === 0) {
            container.innerHTML = '';
            container.style.display = 'none';
            return;
        }
        container.style.display = 'block';
        container.innerHTML = `
            <div class="scraping-issues-block">
                <h3 class="scraping-issues-title"><i class="fas fa-exclamation-triangle"></i> Points d'attention scraping <span class="badge badge-warning">${issues.length}</span></h3>
                <div class="scraping-summary-chips">
                    ${counts.critical ? `<span class="scraping-chip scraping-chip-critical">${counts.critical} critique${counts.critical > 1 ? 's' : ''}</span>` : ''}
                    ${counts.high ? `<span class="scraping-chip scraping-chip-high">${counts.high} haute${counts.high > 1 ? 's' : ''}</span>` : ''}
                    ${counts.medium ? `<span class="scraping-chip scraping-chip-medium">${counts.medium} moyenne${counts.medium > 1 ? 's' : ''}</span>` : ''}
                    ${counts.low ? `<span class="scraping-chip scraping-chip-low">${counts.low} faible${counts.low > 1 ? 's' : ''}</span>` : ''}
                    ${counts.info ? `<span class="scraping-chip scraping-chip-info">${counts.info} info</span>` : ''}
                </div>
                <div class="scraping-issues-list">
                    ${issues.map(issue => {
                        const color = borderColors[issue.severity] || '#6b7280';
                        return `<div class="scraping-issue-card" style="border-left: 4px solid ${color};">
                            <div class="scraping-issue-header">
                                <strong class="scraping-issue-title">${Formatters.escapeHtml(issue.title)}</strong>
                                <span class="scraping-chip scraping-chip-${issue.severity}">${Formatters.escapeHtml(issue.severity)}</span>
                            </div>
                            <div class="scraping-issue-desc">${Formatters.escapeHtml(issue.description)}</div>
                            ${issue.recommendation ? `<div class="scraping-issue-reco"><strong><i class="fas fa-lightbulb"></i> Recommandation:</strong> ${Formatters.escapeHtml(issue.recommendation)}</div>` : ''}
                        </div>`;
                    }).join('')}
                </div>
            </div>
        `;
    }
    
    /**
     * Affiche tous les résultats de scraping
     * @param {Object} data - Données de scraping complètes
     */
    function displayAllScrapingResults(data) {
        const emails = data.emails || [];
        const people = data.people || [];
        const phones = data.phones || [];
        const social = data.social_links || {};
        const technologies = data.technologies || {};
        const metadata = data.metadata || {};
        
        const stats = {
            emails: emails.length,
            people: people.length,
            phones: phones.length,
            social: Object.keys(social).length,
            technologies: Object.keys(technologies).length,
            metadata: Object.keys(metadata).length
        };
        
        // Afficher les statistiques
        displayScrapingStats(stats);
        
        // Afficher le bloc Issues (chips + cartes)
        displayScrapingIssues(stats);
        
        // Afficher chaque section
        displayEmails(emails);
        displayPeople(people);
        displayPhones(phones);
        displaySocial(social);
        displayTechnologies(technologies);
        displayMetadata(metadata);
    }
    
    // Exposer les fonctions globalement
    window.ScrapingAnalysisDisplay = {
        displayAll: displayAllScrapingResults,
        displayEmails,
        displayPeople,
        displayPhones,
        displaySocial,
        displayTechnologies,
        displayMetadata,
        displayStats: displayScrapingStats,
        displayScrapingIssues,
        updateCount: updateModalCount
    };
    
})(window);

