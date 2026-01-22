/**
 * Gestion des tokens API
 */

(function() {
    let tokens = [];
    
    // Charger les tokens au démarrage
    document.addEventListener('DOMContentLoaded', function() {
        loadTokens();
        setupForm();
    });
    
    /**
     * Charge la liste des tokens
     */
    async function loadTokens() {
        try {
            const response = await fetch('/api/tokens');
            const data = await response.json();
            
            if (data.success) {
                tokens = data.data;
                displayTokens(tokens);
            } else {
                showError('Erreur lors du chargement des tokens: ' + (data.error || 'Erreur inconnue'));
            }
        } catch (error) {
            console.error('Erreur:', error);
            showError('Erreur lors du chargement des tokens');
        }
    }
    
    /**
     * Affiche les tokens dans la liste
     */
    function displayTokens(tokensList) {
        const container = document.getElementById('tokensContainer');
        
        if (tokensList.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-key"></i>
                    <p>Aucun token créé pour le moment</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = tokensList.map(token => {
            const statusClass = token.is_active ? 'active' : 'revoked';
            const statusText = token.is_active ? 'Actif' : 'Révoqué';
            const dateCreated = new Date(token.date_creation).toLocaleDateString('fr-FR');
            const lastUsed = token.last_used 
                ? new Date(token.last_used).toLocaleDateString('fr-FR')
                : 'Jamais utilisé';
            
            const permissions = [];
            if (token.can_read_entreprises) {
                permissions.push('<span class="badge badge-success">Entreprises</span>');
            } else {
                permissions.push('<span class="badge badge-danger">Entreprises</span>');
            }
            if (token.can_read_emails) {
                permissions.push('<span class="badge badge-success">Emails</span>');
            } else {
                permissions.push('<span class="badge badge-danger">Emails</span>');
            }
            if (token.can_read_statistics) {
                permissions.push('<span class="badge badge-success">Statistiques</span>');
            } else {
                permissions.push('<span class="badge badge-danger">Statistiques</span>');
            }
            if (token.can_read_campagnes) {
                permissions.push('<span class="badge badge-success">Campagnes</span>');
            } else {
                permissions.push('<span class="badge badge-danger">Campagnes</span>');
            }
            
            // Échapper le token pour éviter les problèmes avec les guillemets
            const safeToken = token.token ? token.token.replace(/'/g, "\\'").replace(/"/g, '&quot;') : '';
            
            return `
                <div class="token-card ${statusClass}">
                    <div class="token-header">
                        <div>
                            <div class="token-name">${escapeHtml(token.name)}</div>
                            ${token.app_url ? `<div class="token-url"><i class="fas fa-link"></i> ${escapeHtml(token.app_url)}</div>` : ''}
                        </div>
                        <div class="token-actions">
                            ${token.is_active && safeToken ? `
                                <button class="btn-action btn-copy" onclick="copyToken('${safeToken}')" title="Copier le token">
                                    <i class="fas fa-copy"></i> Copier
                                </button>
                                <button class="btn-action btn-revoke" onclick="revokeToken(${token.id})" title="Révoquer le token">
                                    <i class="fas fa-ban"></i> Révoquer
                                </button>
                            ` : ''}
                            <button class="btn-action btn-delete" onclick="deleteToken(${token.id})" title="Supprimer définitivement">
                                <i class="fas fa-trash"></i> Supprimer
                            </button>
                        </div>
                    </div>
                    <div class="token-info">
                        <div class="info-item">
                            <span class="info-label">Statut</span>
                            <span class="info-value">${statusText}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Token</span>
                            <span class="info-value">${token.token || 'N/A'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Créé le</span>
                            <span class="info-value">${dateCreated}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Dernière utilisation</span>
                            <span class="info-value">${lastUsed}</span>
                        </div>
                    </div>
                    <div class="permissions-badges">
                        ${permissions.join('')}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    /**
     * Configure le formulaire de création
     */
    function setupForm() {
        const form = document.getElementById('createTokenForm');
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Générer automatiquement le nom du token
            const appUrl = document.getElementById('appUrl').value;
            const now = new Date();
            const dateStr = now.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
            const timeStr = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
            
            let tokenName = '';
            if (appUrl) {
                try {
                    const url = new URL(appUrl);
                    const domain = url.hostname.replace('www.', '');
                    tokenName = `${domain} - ${dateStr} ${timeStr}`;
                } catch (e) {
                    tokenName = `Token - ${dateStr} ${timeStr}`;
                }
            } else {
                tokenName = `Token - ${dateStr} ${timeStr}`;
            }
            
            const formData = {
                name: tokenName,
                app_url: appUrl || null,
                can_read_entreprises: document.getElementById('permEntreprises').checked,
                can_read_emails: document.getElementById('permEmails').checked,
                can_read_statistics: document.getElementById('permStatistics').checked,
                can_read_campagnes: document.getElementById('permCampagnes').checked
            };
            
            try {
                const response = await fetch('/api/tokens', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess('Token créé avec succès !');
                    showTokenCreated(data.data);
                    form.reset();
                    loadTokens();
                } else {
                    showError('Erreur: ' + (data.error || 'Erreur inconnue'));
                }
            } catch (error) {
                console.error('Erreur:', error);
                showError('Erreur lors de la création du token');
            }
        });
    }
    
    /**
     * Affiche le token créé avec un avertissement
     */
    function showTokenCreated(tokenData) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-warning';
        alert.innerHTML = `
            <strong><i class="fas fa-exclamation-triangle"></i> Important !</strong>
            <p>Votre token a été généré. <strong>Sauvegardez-le immédiatement</strong>, il ne sera plus affiché après fermeture de cette alerte.</p>
            <div class="token-display">
                <span class="token-value">${tokenData.token}</span>
                <button class="btn-action btn-copy" onclick="copyToken('${tokenData.token}')">
                    <i class="fas fa-copy"></i> Copier
                </button>
            </div>
        `;
        
        const container = document.querySelector('.create-token-section');
        container.insertBefore(alert, container.firstChild);
        
        // Supprimer l'alerte après 30 secondes
        setTimeout(() => {
            alert.remove();
        }, 30000);
    }
    
    /**
     * Révoque un token
     */
    window.revokeToken = async function(tokenId) {
        if (!confirm('Êtes-vous sûr de vouloir révoquer ce token ? Il ne pourra plus être utilisé.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/tokens/${tokenId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showSuccess('Token révoqué avec succès');
                loadTokens();
            } else {
                showError('Erreur: ' + (data.error || 'Erreur inconnue'));
            }
        } catch (error) {
            console.error('Erreur:', error);
            showError('Erreur lors de la révocation du token');
        }
    };
    
    /**
     * Supprime un token
     */
    window.deleteToken = async function(tokenId) {
        if (!confirm('Êtes-vous sûr de vouloir supprimer définitivement ce token ? Cette action est irréversible.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/tokens/${tokenId}/delete`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showSuccess('Token supprimé avec succès');
                loadTokens();
            } else {
                showError('Erreur: ' + (data.error || 'Erreur inconnue'));
            }
        } catch (error) {
            console.error('Erreur:', error);
            showError('Erreur lors de la suppression du token');
        }
    };
    
    /**
     * Copie un token dans le presse-papier
     */
    window.copyToken = async function(token) {
        try {
            await navigator.clipboard.writeText(token);
            showSuccess('Token copié dans le presse-papier !');
        } catch (error) {
            // Fallback pour les navigateurs plus anciens
            const textarea = document.createElement('textarea');
            textarea.value = token;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            showSuccess('Token copié dans le presse-papier !');
        }
    };
    
    /**
     * Affiche un message de succès
     */
    function showSuccess(message) {
        // Créer un conteneur de messages si nécessaire
        let flashContainer = document.querySelector('.flash-messages');
        if (!flashContainer) {
            flashContainer = document.createElement('div');
            flashContainer.className = 'flash-messages';
            const container = document.querySelector('.tokens-container');
            if (container) {
                container.insertBefore(flashContainer, container.firstChild);
            }
        }
        
        const alert = document.createElement('div');
        alert.className = 'alert alert-success';
        alert.style.cssText = 'background: #d4edda; color: #155724; padding: 12px; border-radius: 8px; margin-bottom: 10px;';
        alert.textContent = message;
        flashContainer.appendChild(alert);
        setTimeout(() => alert.remove(), 5000);
    }
    
    /**
     * Affiche un message d'erreur
     */
    function showError(message) {
        // Créer un conteneur de messages si nécessaire
        let flashContainer = document.querySelector('.flash-messages');
        if (!flashContainer) {
            flashContainer = document.createElement('div');
            flashContainer.className = 'flash-messages';
            const container = document.querySelector('.tokens-container');
            if (container) {
                container.insertBefore(flashContainer, container.firstChild);
            }
        }
        
        const alert = document.createElement('div');
        alert.className = 'alert alert-error';
        alert.style.cssText = 'background: #f8d7da; color: #721c24; padding: 12px; border-radius: 8px; margin-bottom: 10px;';
        alert.textContent = message;
        flashContainer.appendChild(alert);
        setTimeout(() => alert.remove(), 5000);
    }
    
    /**
     * Échappe le HTML pour éviter les injections XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
})();

