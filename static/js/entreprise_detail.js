/**
 * JavaScript pour la page de détail d'une entreprise
 * Affichage complet avec tags et notes
 */

(function() {
    let entrepriseId = null;
    let entrepriseData = null;
    
    // Récupérer l'ID depuis l'URL
    const pathParts = window.location.pathname.split('/');
    entrepriseId = parseInt(pathParts[pathParts.length - 1]);
    
    // Initialisation
    document.addEventListener('DOMContentLoaded', () => {
        if (entrepriseId) {
            loadEntrepriseDetail();
            setupEventListeners();
        }
    });
    
    async function loadEntrepriseDetail() {
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}`);
            if (!response.ok) {
                throw new Error('Entreprise introuvable');
            }
            
            entrepriseData = await response.json();
            
            // Charger les scrapers
            try {
                const scrapersResponse = await fetch(`/api/entreprise/${entrepriseId}/scrapers`);
                if (scrapersResponse.ok) {
                    entrepriseData.scrapers = await scrapersResponse.json();
                } else {
                    entrepriseData.scrapers = [];
                }
            } catch (e) {
                // Erreur silencieuse lors du chargement des scrapers
                entrepriseData.scrapers = [];
            }
            
            renderDetail();
        } catch (error) {
            console.error('Erreur lors du chargement:', error);
            document.getElementById('entreprise-detail').innerHTML = 
                '<div class="error">Erreur lors du chargement des détails</div>';
        }
    }
    
    function renderDetail() {
        if (!entrepriseData) return;
        
        document.getElementById('entreprise-nom').textContent = entrepriseData.nom || 'Sans nom';
        
        const favoriBtn = document.getElementById('btn-toggle-favori');
        if (entrepriseData.favori) {
            favoriBtn.classList.add('active');
            favoriBtn.textContent = '⭐ Favori';
        } else {
            favoriBtn.textContent = '☆ Ajouter aux favoris';
        }
        
        const detailDiv = document.getElementById('entreprise-detail');
        detailDiv.innerHTML = createDetailHTML();
        
        // Setup des interactions
        setupDetailInteractions();
    }
    
    function createDetailHTML() {
        const tags = entrepriseData.tags || [];
        const notes = entrepriseData.notes || '';
        
        return `
            <div class="detail-grid">
                <div class="detail-section">
                    <h2>Informations générales</h2>
                    <div class="info-grid">
                        ${createInfoRow('Nom', entrepriseData.nom)}
                        ${createInfoRow('Site web', entrepriseData.website, true)}
                        ${createInfoRow('Secteur', entrepriseData.secteur)}
                        ${createInfoRow('Statut', entrepriseData.statut, false, getStatusBadge(entrepriseData.statut) + createStatutActionsHTML())}
                        ${createInfoRow('Opportunité', entrepriseData.opportunite)}
                        ${createInfoRow('Taille estimée', entrepriseData.taille_estimee)}
                    </div>
                </div>
                
                <div class="detail-section">
                    <h2>Contact</h2>
                    <div class="info-grid">
                        ${createInfoRow('Email principal', entrepriseData.email_principal, true)}
                        ${createInfoRow('Responsable', entrepriseData.responsable)}
                    </div>
                </div>
                
                ${entrepriseData.hosting_provider || entrepriseData.framework ? `
                <div class="detail-section">
                    <h2>Informations techniques</h2>
                    <div class="info-grid">
                        ${createInfoRow('Hébergeur', entrepriseData.hosting_provider)}
                        ${createInfoRow('Framework', entrepriseData.framework)}
                        ${createInfoRow('Score sécurité', entrepriseData.score_securite)}
                    </div>
                    <div style="margin-top: 1rem;">
                        <button id="btn-load-tech-analysis" class="btn btn-primary">Voir l'analyse technique complète</button>
                    </div>
                </div>
                ` : ''}
                
                ${entrepriseData.scrapers && entrepriseData.scrapers.length > 0 ? `
                <div class="detail-section full-width">
                    <h2>Données scrapées</h2>
                    ${createScrapersHTML(entrepriseData.scrapers)}
                </div>
                ` : ''}
                
                <div class="detail-section full-width">
                    <h2>Tags</h2>
                    <div id="tags-container" class="tags-editable">
                        ${tags.map(tag => `<span class="tag editable" data-tag="${tag}">${tag} <button class="tag-remove">×</button></span>`).join('')}
                        <input type="text" id="tag-input" placeholder="Ajouter un tag (Entrée pour valider)" class="tag-input">
                    </div>
                </div>
                
                <div class="detail-section full-width">
                    <h2>Notes</h2>
                    <textarea id="notes-textarea" class="notes-textarea" placeholder="Ajoutez vos notes sur cette entreprise...">${notes}</textarea>
                    <button id="btn-save-notes" class="btn btn-primary">Enregistrer les notes</button>
                </div>
            </div>
        `;
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
    
    function getStatusBadge(statut) {
        if (!statut) return '';
        const classes = {
            'Nouveau': 'primary',
            'À qualifier': 'warning',
            'Relance': 'relance',
            'Gagné': 'success',
            'Perdu': 'danger'
        };
        const class_name = classes[statut] || 'secondary';
        return `<span class="badge badge-${class_name}">${statut}</span>`;
    }
    
    function createStatutActionsHTML() {
        return `
            <span class="statut-actions" style="margin-left:0.5rem;">
                <button type="button" class="btn btn-small btn-success btn-statut" data-statut="Gagné" title="Prospect converti">Marquer comme gagné</button>
                <button type="button" class="btn btn-small btn-secondary btn-statut" data-statut="Perdu" title="Prospect non converti">Marquer comme perdu</button>
            </span>
        `;
    }
    
    function createScrapersHTML(scrapers) {
        if (!scrapers || scrapers.length === 0) {
            return '<p>Aucune donnée scrapée disponible</p>';
        }
        
        // Prendre le scraper le plus récent
        const scraper = scrapers[0];
        
        let html = '<div class="scraper-data">';
        
        // Emails
        if (scraper.emails && scraper.emails.length > 0) {
            html += '<div class="scraper-section"><h3>Emails (' + scraper.emails.length + ')</h3><ul>';
            scraper.emails.slice(0, 10).forEach(email => {
                const emailData = typeof email === 'string' ? { email: email } : email;
                const emailStr = emailData.email || emailData.value || '';
                const analysis = emailData.analysis;
                
                let emailHtml = `<li><a href="mailto:${emailStr}">${emailStr}</a>`;
                
                // Afficher les analyses si disponibles
                if (analysis) {
                    emailHtml += ' <span class="email-analysis">';
                    
                    // Badge type
                    if (analysis.type) {
                        const typeClass = analysis.type === 'Professionnel' ? 'badge-success' : 
                                        analysis.type === 'Personnel' ? 'badge-info' : 'badge-warning';
                        emailHtml += `<span class="badge ${typeClass}" title="Type d'email">${analysis.type}</span> `;
                    }
                    
                    // Badge provider
                    if (analysis.provider) {
                        emailHtml += `<span class="badge badge-secondary" title="Fournisseur">${analysis.provider}</span> `;
                    }
                    
                    // Badge format
                    if (analysis.format_valid !== null) {
                        const formatClass = analysis.format_valid ? 'badge-success' : 'badge-danger';
                        const formatText = analysis.format_valid ? 'Format OK' : 'Format invalide';
                        emailHtml += `<span class="badge ${formatClass}" title="Validité du format">${formatText}</span> `;
                    }
                    
                    // Badge MX
                    if (analysis.mx_valid !== null) {
                        const mxClass = analysis.mx_valid ? 'badge-success' : 'badge-danger';
                        const mxText = analysis.mx_valid ? 'MX OK' : 'MX invalide';
                        emailHtml += `<span class="badge ${mxClass}" title="Validité MX">${mxText}</span> `;
                    }
                    
                    // Badge risque
                    if (analysis.risk_score !== null && analysis.risk_score !== undefined) {
                        const riskClass = analysis.risk_score < 30 ? 'badge-success' : 
                                         analysis.risk_score < 70 ? 'badge-warning' : 'badge-danger';
                        emailHtml += `<span class="badge ${riskClass}" title="Score de risque (0-100)">Risque: ${analysis.risk_score}</span> `;
                    }
                    
                    // Nom extrait
                    if (analysis.name_info && analysis.name_info.full_name) {
                        emailHtml += `<span class="badge badge-info" title="Nom extrait de l'email">${analysis.name_info.full_name}</span> `;
                    }
                    
                    emailHtml += '</span>';
                }
                
                emailHtml += '</li>';
                html += emailHtml;
            });
            if (scraper.emails.length > 10) {
                html += `<li><em>... et ${scraper.emails.length - 10} autres</em></li>`;
            }
            html += '</ul></div>';
        }
        
        // Personnes
        if (scraper.people && scraper.people.length > 0) {
            html += '<div class="scraper-section"><h3>Personnes (' + scraper.people.length + ')</h3><ul>';
            scraper.people.slice(0, 10).forEach(person => {
                const name = person.name || 'Inconnu';
                const title = person.title ? ` - ${person.title}` : '';
                const email = person.email ? ` (<a href="mailto:${person.email}">${person.email}</a>)` : '';
                html += `<li>${name}${title}${email}</li>`;
            });
            if (scraper.people.length > 10) {
                html += `<li><em>... et ${scraper.people.length - 10} autres</em></li>`;
            }
            html += '</ul></div>';
        }
        
        // Téléphones
        if (scraper.phones && scraper.phones.length > 0) {
            html += '<div class="scraper-section"><h3>Téléphones (' + scraper.phones.length + ')</h3><ul>';
            scraper.phones.slice(0, 10).forEach(phone => {
                const phoneStr = typeof phone === 'string' ? phone : (phone.phone || phone.value || '');
                html += `<li><a href="tel:${phoneStr}">${phoneStr}</a></li>`;
            });
            if (scraper.phones.length > 10) {
                html += `<li><em>... et ${scraper.phones.length - 10} autres</em></li>`;
            }
            html += '</ul></div>';
        }
        
        // Réseaux sociaux
        if (scraper.social_profiles && Object.keys(scraper.social_profiles).length > 0) {
            html += '<div class="scraper-section"><h3>Réseaux sociaux</h3><ul>';
            for (const [platform, urls] of Object.entries(scraper.social_profiles)) {
                const urlList = Array.isArray(urls) ? urls : [urls];
                urlList.forEach(urlData => {
                    const url = typeof urlData === 'string' ? urlData : (urlData.url || '');
                    html += `<li><strong>${platform}:</strong> <a href="${url}" target="_blank">${url}</a></li>`;
                });
            }
            html += '</ul></div>';
        }
        
        // Technologies
        if (scraper.technologies && Object.keys(scraper.technologies).length > 0) {
            html += '<div class="scraper-section"><h3>Technologies</h3><ul>';
            for (const [category, techs] of Object.entries(scraper.technologies)) {
                const techList = Array.isArray(techs) ? techs : [techs];
                html += `<li><strong>${category}:</strong> ${techList.join(', ')}</li>`;
            }
            html += '</ul></div>';
        }
        
        // Images
        if (scraper.total_images && scraper.total_images > 0) {
            html += `<div class="scraper-section"><h3>Images (${scraper.total_images})</h3>`;
            html += `<p>${scraper.total_images} image(s) trouvée(s) sur le site</p></div>`;
        }
        
        html += '</div>';
        return html;
    }
    
    function setupDetailInteractions() {
        // Favori
        document.getElementById('btn-toggle-favori').addEventListener('click', async () => {
            await toggleFavori();
        });
        
        // Tags
        const tagInput = document.getElementById('tag-input');
        if (tagInput) {
            tagInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag(tagInput.value.trim());
                    tagInput.value = '';
                }
            });
        }
        
        // Suppression de tags
        document.querySelectorAll('.tag-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tag = e.target.closest('.tag').dataset.tag;
                removeTag(tag);
            });
        });
        
        // Notes
        const notesBtn = document.getElementById('btn-save-notes');
        if (notesBtn) {
            notesBtn.addEventListener('click', () => {
                saveNotes();
            });
        }
        
        // Statut (Marquer comme gagné / perdu)
        document.getElementById('entreprise-detail').addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-statut');
            if (btn) {
                e.preventDefault();
                updateStatut(btn.dataset.statut);
            }
        });
        
        // Analyse technique
        const techBtn = document.getElementById('btn-load-tech-analysis');
        if (techBtn) {
            techBtn.addEventListener('click', async () => {
                await loadTechnicalAnalysis();
            });
        }
    }
    
    async function loadTechnicalAnalysis() {
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/analyse-technique`);
            if (response.ok) {
                const analysis = await response.json();
                // Rediriger vers la page de détail de l'analyse technique
                window.location.href = `/analyse-technique/${analysis.id}`;
            } else {
                alert('Aucune analyse technique disponible pour cette entreprise');
            }
        } catch (error) {
            console.error('Erreur lors du chargement de l\'analyse technique:', error);
            alert('Erreur lors du chargement de l\'analyse technique');
        }
    }
    
    async function updateStatut(statut) {
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/statut`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ statut: statut })
            });
            const data = await response.json();
            if (data.success) {
                entrepriseData.statut = data.statut;
                renderDetail();
            } else {
                alert(data.error || 'Erreur lors de la mise à jour du statut');
            }
        } catch (err) {
            console.error(err);
            alert('Erreur lors de la mise à jour du statut');
        }
    }
    
    async function toggleFavori() {
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/favori`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                entrepriseData.favori = data.favori;
                const favoriBtn = document.getElementById('btn-toggle-favori');
                if (data.favori) {
                    favoriBtn.classList.add('active');
                    favoriBtn.textContent = '⭐ Favori';
                } else {
                    favoriBtn.classList.remove('active');
                    favoriBtn.textContent = '☆ Ajouter aux favoris';
                }
            }
        } catch (error) {
            console.error('Erreur lors du toggle favori:', error);
            alert('Erreur lors de la mise à jour du favori');
        }
    }
    
    async function addTag(tagText) {
        if (!tagText) return;
        
        const tags = entrepriseData.tags || [];
        if (tags.includes(tagText)) return;
        
        tags.push(tagText);
        await updateTags(tags);
    }
    
    async function removeTag(tagText) {
        const tags = (entrepriseData.tags || []).filter(t => t !== tagText);
        await updateTags(tags);
    }
    
    async function updateTags(tags) {
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/tags`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tags })
            });
            const data = await response.json();
            
            if (data.success) {
                entrepriseData.tags = tags;
                renderDetail();
            }
        } catch (error) {
            console.error('Erreur lors de la mise à jour des tags:', error);
            alert('Erreur lors de la mise à jour des tags');
        }
    }
    
    async function saveNotes() {
        const notes = document.getElementById('notes-textarea').value;
        
        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/notes`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes })
            });
            const data = await response.json();
            
            if (data.success) {
                entrepriseData.notes = notes;
                const btn = document.getElementById('btn-save-notes');
                const originalText = btn.textContent;
                btn.textContent = '✓ Enregistré !';
                btn.classList.add('success');
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.classList.remove('success');
                }, 2000);
            }
        } catch (error) {
            console.error('Erreur lors de la sauvegarde des notes:', error);
            alert('Erreur lors de la sauvegarde des notes');
        }
    }
})();

