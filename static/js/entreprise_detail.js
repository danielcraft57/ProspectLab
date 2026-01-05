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
                        ${createInfoRow('Statut', entrepriseData.statut, false, getStatusBadge(entrepriseData.statut))}
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
            'Prospect intéressant': 'success',
            'À contacter': 'warning',
            'En cours': 'info',
            'Clos': 'secondary'
        };
        const class_name = classes[statut] || 'secondary';
        return `<span class="badge badge-${class_name}">${statut}</span>`;
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

