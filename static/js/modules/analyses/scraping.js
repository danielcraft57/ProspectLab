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
    
    const TECH_PRETTY = {
        wordpress: 'WordPress', woocommerce: 'WooCommerce', jquery: 'jQuery', php: 'PHP',
        nginx: 'Nginx', apache: 'Apache', iis: 'IIS', drupal: 'Drupal', joomla: 'Joomla',
        prestashop: 'PrestaShop', magento: 'Magento', shopify: 'Shopify', angular: 'Angular',
        angularjs: 'AngularJS', react: 'React', vue: 'Vue.js', 'vue.js': 'Vue.js', vuejs: 'Vue.js',
        bootstrap: 'Bootstrap', 'next.js': 'Next.js', nextjs: 'Next.js', cloudflare: 'Cloudflare',
        spip: 'SPIP', typo3: 'TYPO3', recaptcha: 'reCAPTCHA'
    };

    const TECH_CAT_META = {
        cms: { label: 'CMS', icon: 'fa-globe' },
        ecommerce: { label: 'E-commerce', icon: 'fa-shopping-cart' },
        framework: { label: 'Framework', icon: 'fa-cubes' },
        library: { label: 'Librairies', icon: 'fa-book' },
        css: { label: 'CSS', icon: 'fa-paint-brush' },
        language: { label: 'Langage', icon: 'fa-code' },
        server: { label: 'Serveur', icon: 'fa-server' },
        plugin: { label: 'Plugins', icon: 'fa-puzzle-piece' },
        builder: { label: 'Builder', icon: 'fa-th-large' },
        seo: { label: 'SEO', icon: 'fa-search' },
        analytics: { label: 'Analytics', icon: 'fa-chart-line' },
        cdn: { label: 'CDN', icon: 'fa-cloud' },
        security: { label: 'Sécurité', icon: 'fa-shield-alt' },
        consent: { label: 'Cookies', icon: 'fa-cookie-bite' },
        payment: { label: 'Paiement', icon: 'fa-credit-card' },
        marketing: { label: 'Marketing', icon: 'fa-bullhorn' },
        hosting: { label: 'Hébergeur', icon: 'fa-building' },
        cache: { label: 'Cache', icon: 'fa-bolt' }
    };

    const TECH_CAT_ORDER = [
        'cms', 'ecommerce', 'framework', 'library', 'css', 'language', 'server',
        'plugin', 'builder', 'seo', 'analytics', 'cdn', 'security', 'consent',
        'payment', 'marketing', 'hosting', 'cache'
    ];

    /**
     * Compare deux versions dotted (3.4.1 < 3.5.0).
     * @param {string} left
     * @param {string} right
     * @returns {boolean}
     */
    function versionLessThan(left, right) {
        const pa = String(left || '').split('.').map((n) => parseInt(n, 10) || 0);
        const pb = String(right || '').split('.').map((n) => parseInt(n, 10) || 0);
        const size = Math.max(pa.length, pb.length);
        for (let i = 0; i < size; i += 1) {
            const a = pa[i] || 0;
            const b = pb[i] || 0;
            if (a < b) return true;
            if (a > b) return false;
        }
        return false;
    }

    /**
     * Guess le risque si l'API n'a pas encore annoté (vieux scrapes).
     * @param {string} name
     * @param {string|null} version
     * @returns {{status: string|null, note: string}}
     */
    function guessTechRisk(name, version) {
        const key = String(name || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
        if (key === 'angularjs') {
            return { status: 'vulnerable', note: 'AngularJS 1.x abandonne' };
        }
        if (!version) return { status: null, note: '' };
        if (key === 'wordpress' && versionLessThan(version, '5.9')) {
            return { status: 'vulnerable', note: 'Branche WordPress abandonnee' };
        }
        if (key === 'wordpress' && versionLessThan(version, '6.5')) {
            return { status: 'outdated', note: 'WordPress hors branches maintenues' };
        }
        if (key === 'jquery' && versionLessThan(version, '3.5.0')) {
            return { status: 'vulnerable', note: 'jQuery XSS CVE-2020-11022' };
        }
        if (key === 'php' && versionLessThan(version, '8.1')) {
            return { status: 'vulnerable', note: 'PHP en fin de vie' };
        }
        if (key === 'php' && versionLessThan(version, '8.3')) {
            return { status: 'outdated', note: 'PHP 8.1/8.2 en fin de support' };
        }
        if (key === 'bootstrap' && versionLessThan(version, '4.0')) {
            return { status: 'vulnerable', note: 'Bootstrap 3 EOL' };
        }
        if (key === 'bootstrap' && versionLessThan(version, '5.0')) {
            return { status: 'outdated', note: 'Bootstrap 4 plus maintenu' };
        }
        return { status: 'ok', note: '' };
    }

    /**
     * Nom lisible (wordpress -> WordPress).
     * @param {string} name
     * @returns {string}
     */
    function prettyTechName(name) {
        const raw = String(name || '').trim();
        if (!raw) return '';
        const mapped = TECH_PRETTY[raw.toLowerCase()];
        if (mapped) return mapped;
        return raw.charAt(0).toUpperCase() + raw.slice(1);
    }

    /**
     * Normalise une techno (string historique ou objet avec version / risque).
     * @param {string|Object} tech
     * @returns {{name: string, version: string|null, label: string, vuln_status: string|null, vuln_note: string|null}}
     */
    function normalizeTechItem(tech) {
        let name = '';
        let version = null;
        let status = null;
        let note = '';
        if (tech && typeof tech === 'object') {
            name = tech.name || tech.label || '';
            version = tech.version || null;
            status = tech.vuln_status || null;
            note = tech.vuln_note || '';
            if (!version && tech.label) {
                const match = String(tech.label).match(/^(.*)\s+(\d+\.\d+(?:\.\d+)?)$/);
                if (match) {
                    name = match[1];
                    version = match[2];
                }
            }
        } else {
            const text = String(tech || '');
            const match = text.match(/^(.*)\s+(\d+\.\d+(?:\.\d+)?)$/);
            name = match ? match[1] : text;
            version = match ? match[2] : null;
        }
        name = prettyTechName(name);
        if (!status) {
            const guessed = guessTechRisk(name, version);
            status = guessed.status;
            note = note || guessed.note;
        }
        return {
            name: name,
            version: version,
            label: version ? `${name} ${version}` : name,
            vuln_status: status,
            vuln_note: note
        };
    }

    /**
     * Badge HTML d'une techno, avec version et statut faillible.
     * @param {string|Object} tech
     * @returns {string}
     */
    function techChipHtml(tech) {
        const item = normalizeTechItem(tech);
        let modifier = 'unknown';
        let badge = 'version ?';
        if (item.vuln_status === 'vulnerable') {
            modifier = 'vulnerable';
            badge = 'faillible';
        } else if (item.vuln_status === 'outdated') {
            modifier = 'outdated';
            badge = 'obsolete';
        } else if (item.vuln_status === 'ok') {
            modifier = 'ok';
            badge = 'ok';
        }
        const verHtml = item.version
            ? `<span class="tech-chip__ver">${Formatters.escapeHtml(item.version)}</span>`
            : '<span class="tech-chip__ver tech-chip__ver--missing">version masquée</span>';
        const title = item.vuln_note || item.label;
        return `<span class="tech-chip tech-chip--${modifier}" title="${Formatters.escapeHtml(title)}">
            <span class="tech-chip__name">${Formatters.escapeHtml(item.name)}</span>
            <span class="tech-chip__meta">${verHtml}<span class="tech-chip__badge">${Formatters.escapeHtml(badge)}</span></span>
        </span>`;
    }

    /**
     * Compte les technos (pas les catégories).
     * @param {Object} technologies
     * @returns {number}
     */
    function countTechItems(technologies) {
        return Object.values(technologies || {}).reduce((sum, techs) => {
            return sum + (Array.isArray(techs) ? techs.length : 1);
        }, 0);
    }

    /**
     * True s'il manque une version sur une techno "utile" (CMS, lib, langage...).
     * @param {Object} technologies
     * @returns {boolean}
     */
    function needsTechVersions(technologies) {
        const watch = { cms: 1, library: 1, css: 1, language: 1, server: 1, framework: 1, plugin: 1 };
        return Object.entries(technologies || {}).some(([category, techs]) => {
            if (!watch[category]) return false;
            return (Array.isArray(techs) ? techs : [techs]).some((tech) => !normalizeTechItem(tech).version);
        });
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
            updateModalCount('tech', 0);
            return;
        }

        const allItems = [];
        Object.values(technologies).forEach((techs) => {
            (Array.isArray(techs) ? techs : [techs]).forEach((tech) => allItems.push(normalizeTechItem(tech)));
        });
        const vulnCount = allItems.filter((item) => item.vuln_status === 'vulnerable').length;
        const outdatedCount = allItems.filter((item) => item.vuln_status === 'outdated').length;
        const missingVersion = allItems.filter((item) => !item.version).length;

        const wrap = document.createElement('div');
        wrap.className = 'tech-stack';
        wrap.innerHTML = `
            <div class="tech-stack-summary">
                <span class="tech-stack-summary__item">${allItems.length} techno${allItems.length > 1 ? 's' : ''}</span>
                ${vulnCount ? `<span class="tech-stack-summary__item tech-stack-summary__item--bad">${vulnCount} faillible${vulnCount > 1 ? 's' : ''}</span>` : ''}
                ${outdatedCount ? `<span class="tech-stack-summary__item tech-stack-summary__item--warn">${outdatedCount} obsolete${outdatedCount > 1 ? 's' : ''}</span>` : ''}
                ${missingVersion ? `<span class="tech-stack-summary__item">${missingVersion} sans version</span>` : ''}
            </div>
            ${missingVersion ? '<div class="tech-stack-hint" id="tech-stack-hint">Les versions n\'étaient pas dans le scrape. On les cherche sur le site...</div>' : ''}
        `;

        const categories = Object.keys(technologies).sort((a, b) => {
            const ia = TECH_CAT_ORDER.indexOf(a);
            const ib = TECH_CAT_ORDER.indexOf(b);
            return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
        });

        const statusRank = { vulnerable: 0, outdated: 1, unknown: 2, ok: 3 };
        categories.forEach((category) => {
            const techListStr = Array.isArray(technologies[category]) ? technologies[category] : [technologies[category]];
            const normalized = techListStr.map(normalizeTechItem).sort((a, b) => {
                const ra = statusRank[a.vuln_status] ?? 2;
                const rb = statusRank[b.vuln_status] ?? 2;
                return ra - rb || a.name.localeCompare(b.name);
            });
            const meta = TECH_CAT_META[category] || { label: category.charAt(0).toUpperCase() + category.slice(1), icon: 'fa-cog' };
            const searchableText = `${meta.label} ${normalized.map((item) => `${item.label} ${item.vuln_status || ''}`).join(' ')}`;
            const categoryDiv = document.createElement('div');
            categoryDiv.className = 'tech-cat';
            categoryDiv.setAttribute('data-searchable', searchableText);
            categoryDiv.innerHTML = `
                <div class="tech-cat__head">
                    <div class="tech-cat__icon"><i class="fas ${meta.icon}"></i></div>
                    <div>
                        <div class="tech-cat__title">${Formatters.escapeHtml(meta.label)}</div>
                        <div class="tech-cat__count">${normalized.length} détectée${normalized.length > 1 ? 's' : ''}</div>
                    </div>
                </div>
                <div class="tech-cat__list">
                    ${normalized.map((item) => techChipHtml(item)).join('')}
                </div>
            `;
            wrap.appendChild(categoryDiv);
        });

        techList.appendChild(wrap);
        updateModalCount('tech', allItems.length);
    }
    
    /**
     * Rend une valeur de metadonnees (string, lien, tableau d'objets).
     * @param {*} value
     * @param {number} depth
     * @returns {string}
     */
    function formatMetadataValue(value, depth) {
        const level = depth || 0;
        if (value === null || value === undefined || value === '') return '';
        if (typeof value !== 'object') {
            const text = String(value);
            if (/^https?:\/\//i.test(text)) {
                return (
                    '<a href="' +
                    Formatters.escapeHtml(text) +
                    '" target="_blank" rel="noopener" style="color:#60a5fa;word-break:break-all;">' +
                    Formatters.escapeHtml(text) +
                    '</a>'
                );
            }
            return Formatters.escapeHtml(text);
        }
        if (Array.isArray(value)) {
            if (!value.length) return '<span style="opacity:.6;">(vide)</span>';
            const shown = value.slice(0, 40);
            const extra = value.length - shown.length;
            const items = shown
                .map(function (item) {
                    return '<li style="margin:0.2rem 0;">' + formatMetadataValue(item, level + 1) + '</li>';
                })
                .join('');
            return (
                '<ul style="margin:0.25rem 0 0;padding-left:1.1rem;">' +
                items +
                '</ul>' +
                (extra > 0 ? '<div style="margin-top:0.35rem;opacity:.75;">+' + extra + ' de plus</div>' : '')
            );
        }
        const url = value.url || value.href || value.src || value.link || '';
        const label = value.text || value.alt || value.title || value.domain || url;
        if (url) {
            let html =
                '<a href="' +
                Formatters.escapeHtml(String(url)) +
                '" target="_blank" rel="noopener" style="color:#60a5fa;word-break:break-all;">' +
                Formatters.escapeHtml(String(label || url)) +
                '</a>';
            if (value.domain && String(value.domain) !== String(label)) {
                html +=
                    ' <span style="opacity:.7;">(' +
                    Formatters.escapeHtml(String(value.domain)) +
                    ')</span>';
            }
            return html;
        }
        if (level > 3) return Formatters.escapeHtml(JSON.stringify(value).slice(0, 180));
        return Object.entries(value)
            .filter(function (pair) {
                return pair[1] !== null && pair[1] !== undefined && pair[1] !== '';
            })
            .map(function (pair) {
                return (
                    '<div style="margin-top:0.35rem;"><strong>' +
                    Formatters.escapeHtml(String(pair[0]).replace(/_/g, ' ')) +
                    ':</strong> ' +
                    formatMetadataValue(pair[1], level + 1) +
                    '</div>'
                );
            })
            .join('');
    }

    const META_LINK_KIND = {
        contact: { icon: 'fa-envelope', label: 'Contact' },
        quote: { icon: 'fa-file-invoice', label: 'Devis / tarifs' },
        jobs: { icon: 'fa-user-plus', label: 'Recrutement' },
        about: { icon: 'fa-building', label: 'A propos' },
        blog: { icon: 'fa-newspaper', label: 'Blog' },
        legal: { icon: 'fa-balance-scale', label: 'Legal' },
        login: { icon: 'fa-lock', label: 'Espace client' },
        rss: { icon: 'fa-rss', label: 'RSS' }
    };

    /**
     * Classifie un lien (contact, devis, jobs...).
     * @param {string} url
     * @param {string} text
     * @returns {string|null}
     */
    function classifyMetaLink(url, text) {
        const blob = `${url || ''} ${text || ''}`.toLowerCase();
        const rules = [
            ['contact', /contact|nous.contacter|ecrire/],
            ['quote', /devis|tarif|prix|reservation|rdv|rendez-vous/],
            ['jobs', /recrut|carriere|career|jobs|nous-rejoindre|emploi/],
            ['about', /a-propos|about|qui-sommes|presentation/],
            ['blog', /blog|actualit|news|magazine/],
            ['legal', /mention|legal|cgu|cgv|confidential|privacy|rgpd|cookies/],
            ['login', /connexion|login|espace-client|mon-compte/]
        ];
        for (let i = 0; i < rules.length; i += 1) {
            if (rules[i][1].test(blob)) return rules[i][0];
        }
        return null;
    }

    /**
     * Recupere une orga depuis le JSON-LD (vieux scrapes).
     * @param {*} jsonLd
     * @returns {Object}
     */
    function orgFromJsonLd(jsonLd) {
        const found = [];
        function walk(node) {
            if (!node) return;
            if (Array.isArray(node)) {
                node.forEach(walk);
                return;
            }
            if (typeof node !== 'object') return;
            if (node['@graph']) walk(node['@graph']);
            const types = node['@type'] || node.type || '';
            const blob = Array.isArray(types) ? types.join(' ') : String(types);
            if (/Organization|LocalBusiness|Store|Corporation/.test(blob)) found.push(node);
            Object.keys(node).forEach((key) => {
                if (key !== '@context') walk(node[key]);
            });
        }
        walk(jsonLd);
        if (!found.length) return {};
        const node = found[0];
        let address = node.address || {};
        if (Array.isArray(address)) address = address[0] || {};
        if (typeof address !== 'object' || !address) address = {};
        let sameAs = node.sameAs || [];
        if (typeof sameAs === 'string') sameAs = [sameAs];
        return {
            name: node.name || node.legalName || '',
            telephone: node.telephone || node.phone || '',
            email: String(node.email || '').replace(/^mailto:/i, ''),
            url: node.url || '',
            street: address.streetAddress || '',
            city: address.addressLocality || '',
            postal_code: address.postalCode || '',
            country: address.addressCountry || '',
            same_as: sameAs.filter(Boolean)
        };
    }

    /**
     * Normalise un lien externe scrape.
     * @param {Object|string} item
     * @returns {Object|null}
     */
    function normalizeExternalLink(item) {
        if (!item) return null;
        if (typeof item === 'string') {
            return { url: item, domain: '', text: '', likely_credit: false, context_snippet: '' };
        }
        let domain = item.domain || '';
        const url = item.url || '';
        if (!domain && url) {
            try {
                domain = new URL(url).hostname.replace(/^www\./, '');
            } catch (e) {
                domain = '';
            }
        }
        return {
            url: url,
            domain: domain,
            text: item.text || '',
            likely_credit: !!item.likely_credit,
            context_snippet: item.context_snippet || '',
            page_url: item.page_url || '',
            site_title: item.site_title || '',
            site_description: item.site_description || '',
            thumb_url: item.thumb_url || '',
            resolved_url: item.resolved_url || '',
            graph_group: item.graph_group || '',
            mini_scraped_at: item.mini_scraped_at || '',
            mini_scrape_error: item.mini_scrape_error || '',
            target_entreprise_id: item.target_entreprise_id || null,
            target_nom: item.target_nom || '',
            target_website: item.target_website || '',
            known_in_db: !!(item.known_in_db || item.target_entreprise_id)
        };
    }

    /**
     * Fusionne liens externes (metadata + header) sans doublons.
     * @param {Object} meta
     * @returns {{credits: Array, partners: Array, other: Array}}
     */
    function buildExternalLinkGroups(meta) {
        const enriched = Array.isArray(meta.external_links_enriched) ? meta.external_links_enriched : null;
        const raw = enriched && enriched.length
            ? enriched.slice().concat(meta.header_external || [])
            : []
                .concat(meta.external_links || [])
                .concat(meta.header_external || []);
        const byUrl = {};
        raw.forEach((item) => {
            const row = normalizeExternalLink(item);
            if (!row || !row.url) return;
            const prev = byUrl[row.url];
            if (!prev || (row.likely_credit && !prev.likely_credit)) {
                byUrl[row.url] = row;
            }
        });
        const all = Object.values(byUrl);
        const credits = all.filter((row) => row.likely_credit);
        const partnerRe = /doctolib|planity|treatwell|reserv|booking|calendly|helloasso|stripe|paypal|amazon|leboncoin|pagesjaunes|societe\.com|infogreffe|annuaire|google\.com\/maps|maps\.app/i;
        const partners = all.filter((row) => !row.likely_credit && partnerRe.test(`${row.url} ${row.text} ${row.domain}`));
        const tagged = {};
        credits.concat(partners).forEach((row) => { tagged[row.url] = true; });
        const other = all.filter((row) => !tagged[row.url]);
        other.sort((a, b) => (a.domain || '').localeCompare(b.domain || ''));
        return { credits: credits, partners: partners, other: other };
    }

    /**
     * Prepare une vue lisible des metadonnees (vieux + nouveaux scrapes).
     * @param {Object} metadata
     * @returns {Object}
     */
    function buildMetadataView(metadata) {
        const meta = metadata || {};
        const og = meta.open_graph || {};
        const tags = meta.meta_tags || {};
        const icons = meta.icons || {};
        const org = (meta.organization && meta.organization.name) ? meta.organization : orgFromJsonLd(meta.json_ld);
        const title = og.title || tags.title || org.name || '';
        const description = og.description || tags.description || '';
        const links = Array.isArray(meta.header_links) ? meta.header_links.slice() : [];
        const seen = {};
        links.forEach((link) => {
            if (link && link.url) seen[link.url] = true;
        });
        function addLink(url, text, kind) {
            if (!url || seen[url]) return;
            const resolved = kind || classifyMetaLink(url, text || '');
            if (!resolved) return;
            seen[url] = true;
            links.push({ url: url, text: text || resolved, kind: resolved, label: (META_LINK_KIND[resolved] || {}).label || resolved });
        }
        Object.keys(og).forEach((key) => {
            if (/url$/i.test(key) || key === 'see_also') addLink(og[key], key);
        });
        (org.same_as || []).forEach((url) => addLink(url, url));
        const feeds = Array.isArray(meta.feeds) ? meta.feeds.slice() : [];
        (meta.identity_links || []).forEach((item) => {
            if (item && item.url) addLink(item.url, item.label || item.rel, item.rel === 'manifest' ? null : null);
        });
        let signals = Array.isArray(meta.prospect_signals) ? meta.prospect_signals.slice() : [];
        const kinds = {};
        links.forEach((link) => { kinds[link.kind] = true; });
        if (!signals.length) {
            if (kinds.quote) signals.push({ kind: 'quote', label: 'Page devis / tarifs', detail: 'Ils vendent deja en ligne' });
            if (kinds.jobs) signals.push({ kind: 'jobs', label: 'Ils recrutent', detail: 'Boite en mouvement' });
            if (kinds.blog) signals.push({ kind: 'blog', label: 'Blog / actus', detail: 'Ils publient du contenu' });
            if (!kinds.contact && !org.email && !org.telephone) {
                signals.push({ kind: 'no-contact', label: 'Contact peu visible', detail: 'Pas de page contact claire' });
            }
        }
        const navMenu = Array.isArray(meta.nav_menu) && meta.nav_menu.length
            ? meta.nav_menu
            : links.map((link) => ({
                text: link.label || link.text || link.url,
                url: link.url,
                external: false
            }));
        const externalGroups = buildExternalLinkGroups(meta);
        if (!signals.some((s) => s.kind === 'agency') && externalGroups.credits.length) {
            signals.push({ kind: 'agency', label: 'Credit agence', detail: 'Prestataire ou hebergeur detecte' });
        }
        return {
            title: title,
            description: description,
            language: meta.language || og.locale || tags.language || '',
            keywords: Array.isArray(meta.keywords) ? meta.keywords : [],
            icons: icons,
            org: org,
            links: links,
            navMenu: navMenu,
            external: externalGroups,
            feeds: feeds,
            canonical: meta.canonical || og.url || tags.canonical || '',
            hreflang: meta.hreflang || [],
            seo: meta.seo_setup || [],
            signals: signals
        };
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
            return;
        }

        const view = buildMetadataView(metadata);
        const wrap = document.createElement('div');
        wrap.className = 'meta-stack';

        const logo = view.icons.logo || view.icons.favicon || '';
        const cover = view.icons.og_image || view.icons.twitter_image || view.icons.main_image || '';
        const title = view.title || 'Sans titre';
        wrap.innerHTML += `
            <div class="meta-hero" data-searchable="${Formatters.escapeHtml([title, view.description, view.language].join(' '))}">
                ${cover ? `<div class="meta-hero__cover"><img src="${Formatters.escapeHtml(cover)}" alt=""></div>` : ''}
                <div class="meta-hero__body">
                    <div class="meta-hero__brand">
                        ${logo ? `<img class="meta-hero__logo" src="${Formatters.escapeHtml(logo)}" alt="">` : '<div class="meta-hero__logo meta-hero__logo--empty"><i class="fas fa-globe"></i></div>'}
                        <div>
                            <div class="meta-hero__title">${Formatters.escapeHtml(title)}</div>
                            ${view.language ? `<div class="meta-hero__lang">${Formatters.escapeHtml(String(view.language))}</div>` : ''}
                        </div>
                    </div>
                    ${view.description ? `<p class="meta-hero__desc">${Formatters.escapeHtml(view.description)}</p>` : ''}
                    ${view.keywords.length ? `<div class="meta-chips">${view.keywords.slice(0, 12).map((kw) => `<span class="meta-chip">${Formatters.escapeHtml(String(kw).trim())}</span>`).join('')}</div>` : ''}
                </div>
            </div>
        `;

        if (view.signals.length) {
            wrap.innerHTML += `<div class="meta-signals">${view.signals.map((sig) => {
                let cls = '';
                if (sig.kind === 'jobs' || sig.kind === 'quote') cls = 'meta-signal--hot';
                if (sig.kind === 'no-contact' || sig.kind === 'thin-meta') cls = 'meta-signal--warn';
                if (sig.kind === 'agency') cls = 'meta-signal--agency';
                return `<span class="meta-signal ${cls}" title="${Formatters.escapeHtml(sig.detail || '')}">${Formatters.escapeHtml(sig.label)}</span>`;
            }).join('')}</div>`;
        }

        if (view.navMenu && view.navMenu.length) {
            wrap.innerHTML += `
                <div class="meta-card">
                    <div class="meta-card__title"><i class="fas fa-bars"></i> Menu du site (header)</div>
                    <div class="meta-nav-strip">
                        ${view.navMenu.map((item) => {
                            const ext = item.external ? ' meta-nav-pill--external' : '';
                            const icon = item.external ? 'fa-external-link-alt' : 'fa-link';
                            return `<a class="meta-nav-pill${ext}" href="${Formatters.escapeHtml(item.url)}" target="_blank" rel="noopener" data-searchable="${Formatters.escapeHtml([item.text, item.url].join(' '))}">
                                <i class="fas ${icon}"></i>${Formatters.escapeHtml(item.text)}
                            </a>`;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        const ext = view.external || { credits: [], partners: [], other: [] };
        const extTotal = ext.credits.length + ext.partners.length + ext.other.length;
        const extStats = metadata.external_links_stats || {};
        const skipRawKeys = new Set([
            'external_links_enriched',
            'external_links_stats',
        ]);
        if (extTotal) {
            skipRawKeys.add('external_links');
            skipRawKeys.add('header_external');
        }
        if (view.navMenu && view.navMenu.length) {
            skipRawKeys.add('nav_menu');
            skipRawKeys.add('header_links');
        }
        if (view.signals.length) {
            skipRawKeys.add('prospect_signals');
        }
        if (extTotal) {
            let extHtml = `
                <div class="meta-card">
                    <div class="meta-card__title"><i class="fas fa-globe-americas"></i> Liens externes (${extTotal})</div>
            `;
            if (extStats.enriched_domains != null || extStats.known_in_db != null) {
                const bits = [];
                if (extStats.enriched_domains != null) {
                    bits.push(`${extStats.enriched_domains} domaine(s) enrichi(s)`);
                }
                if (extStats.known_in_db != null && extStats.known_in_db > 0) {
                    bits.push(`${extStats.known_in_db} deja en base ProspectLab`);
                }
                if (bits.length) {
                    extHtml += `<div class="meta-stack-hint">${Formatters.escapeHtml(bits.join(' · '))}</div>`;
                }
            }
            /**
             * Carte lien externe (titre OG, thumb, fiche entreprise connue).
             * @param {Object} row
             * @param {string} badge
             * @returns {string}
             */
            function externalRow(row, badge) {
                const host = row.domain || String(row.url).replace(/^https?:\/\//, '').split('/')[0];
                const title = row.site_title || host;
                const href = row.resolved_url || row.url;
                const desc = row.site_description || row.context_snippet || '';
                const thumb = row.thumb_url || '';
                const pending = !row.mini_scraped_at && !row.site_title && !row.mini_scrape_error;
                let dbHtml = '';
                if (row.target_entreprise_id) {
                    dbHtml = `<button type="button" class="meta-external-db" data-open-entreprise-id="${Formatters.escapeHtml(String(row.target_entreprise_id))}" title="${Formatters.escapeHtml(row.target_website || '')}">Deja en base : ${Formatters.escapeHtml(row.target_nom || ('#' + row.target_entreprise_id))}</button>`;
                }
                const err = row.mini_scrape_error
                    ? `<span class="meta-external-card__err">${Formatters.escapeHtml(String(row.mini_scrape_error).slice(0, 120))}</span>`
                    : '';
                const pendingHtml = pending
                    ? '<span class="meta-external-card__pending">Enrichissement en cours…</span>'
                    : '';
                return `<div class="meta-external-card" data-searchable="${Formatters.escapeHtml([title, row.text, row.url, host, desc, row.target_nom].join(' '))}">
                    <a class="meta-external-card__hit" href="${Formatters.escapeHtml(href)}" target="_blank" rel="noopener">
                        ${thumb ? `<img class="meta-external-card__thumb" src="${Formatters.escapeHtml(thumb)}" alt="">` : '<div class="meta-external-card__thumb meta-external-card__thumb--empty"><i class="fas fa-globe"></i></div>'}
                        <div class="meta-external-card__body">
                            <div class="meta-external-card__title">${Formatters.escapeHtml(title)}</div>
                            <div class="meta-external-card__host">${Formatters.escapeHtml(host)}</div>
                            ${row.text ? `<div class="meta-external-card__anchor">${Formatters.escapeHtml(row.text)}</div>` : ''}
                            ${desc ? `<div class="meta-external-card__desc">${Formatters.escapeHtml(desc)}</div>` : ''}
                        </div>
                    </a>
                    <div class="meta-external-card__meta">
                        ${badge ? `<span class="meta-external-badge">${Formatters.escapeHtml(badge)}</span>` : ''}
                        ${row.graph_group && row.graph_group !== 'external' ? `<span class="meta-external-badge meta-external-badge--muted">${Formatters.escapeHtml(row.graph_group)}</span>` : ''}
                        ${dbHtml}
                        ${pendingHtml}
                        ${err}
                    </div>
                </div>`;
            }
            if (ext.credits.length) {
                extHtml += `<div class="meta-external-group"><div class="meta-external-group__title">Agence / prestataire</div>${ext.credits.map((row) => externalRow(row, 'credit')).join('')}</div>`;
            }
            if (ext.partners.length) {
                extHtml += `<div class="meta-external-group"><div class="meta-external-group__title">Resa / annuaire / paiement</div>${ext.partners.map((row) => externalRow(row, 'partenaire')).join('')}</div>`;
            }
            if (ext.other.length) {
                extHtml += `<div class="meta-external-group"><div class="meta-external-group__title">Autres domaines (${ext.other.length})</div>${ext.other.map((row) => externalRow(row, '')).join('')}</div>`;
            }
            extHtml += '</div>';
            wrap.innerHTML += extHtml;
        }

        const org = view.org || {};
        const orgBits = [];
        if (org.telephone) orgBits.push(`<a href="tel:${Formatters.escapeHtml(String(org.telephone).replace(/\s/g, ''))}">${Formatters.escapeHtml(org.telephone)}</a>`);
        if (org.email) orgBits.push(`<a href="mailto:${Formatters.escapeHtml(org.email)}">${Formatters.escapeHtml(org.email)}</a>`);
        const addr = [org.street, org.postal_code, org.city, org.country].filter(Boolean).join(', ');
        if (addr) orgBits.push(Formatters.escapeHtml(addr));
        const orgCardShown = orgBits.length || (org.same_as && org.same_as.length);
        if (orgCardShown) {
            skipRawKeys.add('organization');
            if (metadata.json_ld) {
                skipRawKeys.add('json_ld');
            }
        }
        if (orgCardShown) {
            wrap.innerHTML += `
                <div class="meta-card" data-searchable="${Formatters.escapeHtml([org.name, org.telephone, org.email, addr].join(' '))}">
                    <div class="meta-card__title"><i class="fas fa-id-card"></i> Fiche (schema.org)</div>
                    ${org.name ? `<div class="meta-card__name">${Formatters.escapeHtml(org.name)}</div>` : ''}
                    <div class="meta-card__facts">${orgBits.join(' · ')}</div>
                    ${org.same_as && org.same_as.length ? `<div class="meta-link-list">${org.same_as.map((url) => `<a class="meta-link" href="${Formatters.escapeHtml(url)}" target="_blank" rel="noopener">${Formatters.escapeHtml(url.replace(/^https?:\/\//, ''))}</a>`).join('')}</div>` : ''}
                </div>
            `;
        }

        const navUrls = new Set(
            (view.navMenu || [])
                .map(function (item) { return item && item.url; })
                .filter(Boolean)
        );
        const pageLinks = view.links.filter(function (link) {
            return link && link.url && !navUrls.has(link.url);
        });
        if (pageLinks.length) {
            skipRawKeys.add('identity_links');
        }
        if (pageLinks.length) {
            wrap.innerHTML += `
                <div class="meta-card">
                    <div class="meta-card__title"><i class="fas fa-compass"></i> Pages cles detectees</div>
                    <div class="meta-link-grid">
                        ${pageLinks.map((link) => {
                            const kind = META_LINK_KIND[link.kind] || { icon: 'fa-external-link-alt', label: link.label || 'Lien' };
                            const label = link.label || kind.label;
                            const extra = link.text && link.text !== label ? link.text : '';
                            return `<a class="meta-page" href="${Formatters.escapeHtml(link.url)}" target="_blank" rel="noopener" data-searchable="${Formatters.escapeHtml([label, extra, link.url].join(' '))}">
                                <i class="fas ${kind.icon}"></i>
                                <span>
                                    <strong>${Formatters.escapeHtml(label)}</strong>
                                    ${extra ? `<small>${Formatters.escapeHtml(extra)}</small>` : ''}
                                </span>
                            </a>`;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        const extras = [];
        if (view.canonical) extras.push({ label: 'Canonique', url: view.canonical });
        (view.feeds || []).forEach((feed) => extras.push({ label: feed.title || 'RSS', url: feed.url || feed }));
        (view.hreflang || []).forEach((row) => extras.push({ label: row.lang || 'hreflang', url: row.url }));
        if (extras.length) {
            skipRawKeys.add('canonical');
            skipRawKeys.add('feeds');
            skipRawKeys.add('hreflang');
            wrap.innerHTML += `
                <div class="meta-card">
                    <div class="meta-card__title"><i class="fas fa-sitemap"></i> Head (canonical, RSS, langues)</div>
                    <div class="meta-link-list">
                        ${extras.map((row) => `<a class="meta-link" href="${Formatters.escapeHtml(typeof row.url === 'string' ? row.url : '')}" target="_blank" rel="noopener"><strong>${Formatters.escapeHtml(row.label)}</strong> ${Formatters.escapeHtml(String(row.url || '').replace(/^https?:\/\//, ''))}</a>`).join('')}
                    </div>
                </div>
            `;
        }

        if (view.seo && view.seo.length) {
            skipRawKeys.add('seo_setup');
            wrap.innerHTML += `<div class="meta-chips">${view.seo.map((item) => `<span class="meta-chip">${Formatters.escapeHtml(String(item))}</span>`).join('')}</div>`;
        }

        if (view.title || view.description) {
            skipRawKeys.add('open_graph');
            skipRawKeys.add('meta_tags');
        }
        if (view.keywords && view.keywords.length) {
            skipRawKeys.add('keywords');
        }
        if (view.language) {
            skipRawKeys.add('language');
        }
        if (logo || cover) {
            skipRawKeys.add('icons');
        }

        appendMetadataRawInventory(wrap, metadata, skipRawKeys);

        metadataList.appendChild(wrap);
    }

    /** Libelles des blocs metadata bruts */
    const META_RAW_LABELS = {
        meta_tags: 'Meta tags (head)',
        open_graph: 'Open Graph',
        twitter_cards: 'Twitter Cards',
        json_ld: 'JSON-LD / schema.org',
        icons: 'Icones et images principales',
        images: 'Images detectees (HTML)',
        keywords: 'Mots-cles',
        language: 'Langue',
        canonical: 'URL canonique',
        feeds: 'Flux RSS / Atom',
        hreflang: 'Hreflang',
        header_links: 'Pages cles (header)',
        nav_menu: 'Menu header (brut)',
        header_external: 'Liens externes header',
        identity_links: 'Liens identity (author, me...)',
        organization: 'Organisation (schema)',
        seo_setup: 'SEO / verification',
        prospect_signals: 'Signaux prospect',
        external_links: 'Liens externes (scrape complet)',
        scraped_location: 'Localisation scrapee'
    };

    /**
     * Affiche toutes les metadonnees brutes (comportement historique).
     * @param {HTMLElement} parent
     * @param {Object} metadata
     */
    function appendMetadataRawInventory(parent, metadata, skipKeys) {
        const skip = skipKeys instanceof Set
            ? skipKeys
            : new Set(Array.isArray(skipKeys) ? skipKeys : []);
        const entries = Object.entries(metadata || {}).filter(function (pair) {
            if (skip.has(pair[0])) return false;
            return pair[1] !== null && pair[1] !== undefined && pair[1] !== '';
        });
        if (!entries.length) return;

        const block = document.createElement('details');
        block.className = 'meta-raw-block';
        block.open = false;
        block.innerHTML = '<summary class="meta-raw-block__summary"><i class="fas fa-database"></i> Donnees brutes restantes (' + entries.length + ')</summary>';

        const grid = document.createElement('div');
        grid.className = 'meta-raw-grid';

        entries.forEach(function (pair) {
            const key = pair[0];
            const value = pair[1];
            const label = META_RAW_LABELS[key] || key.replace(/_/g, ' ');
            const searchable = typeof value === 'object'
                ? label + ' ' + JSON.stringify(value).slice(0, 500)
                : label + ' ' + String(value);
            const item = document.createElement('div');
            item.className = 'meta-card meta-raw-item';
            item.setAttribute('data-searchable', searchable);
            item.innerHTML =
                '<div class="meta-card__title"><i class="fas fa-list"></i> ' +
                Formatters.escapeHtml(label) +
                '</div>' +
                '<div class="meta-raw-item__body">' +
                formatMetadataValue(value, 0) +
                '</div>';
            grid.appendChild(item);
        });

        block.appendChild(grid);
        parent.appendChild(block);
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
        const metadata = { ...(data.metadata || {}) };
        if (Array.isArray(data.external_links) && data.external_links.length && !metadata.external_links) {
            metadata.external_links = data.external_links;
        }
        if (Array.isArray(data.external_links_enriched) && data.external_links_enriched.length) {
            metadata.external_links_enriched = data.external_links_enriched;
        }
        if (data.external_links_stats && typeof data.external_links_stats === 'object') {
            metadata.external_links_stats = data.external_links_stats;
        }
        
        const stats = {
            emails: emails.length,
            people: people.length,
            phones: phones.length,
            social: Object.keys(social).length,
            technologies: countTechItems(technologies),
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
        updateCount: updateModalCount,
        needsVersions: needsTechVersions
    };
    
})(window);

