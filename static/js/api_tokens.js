/**
 * Gestion des tokens API
 */

(function() {
    let tokens = [];
    let modalState = { token: '', site: '', subtitle: '' };
    
    // Charger les tokens au démarrage
    document.addEventListener('DOMContentLoaded', function() {
        setupPermissionsBadgeClick();
        loadTokens();
        setupForm();
        setupTokenModal();
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
    
    function permBadgeHtml(token, field, label, titleExtra) {
        const on = !!token[field];
        const tone = on ? 'badge-success' : 'badge-danger';
        const clickable = token.is_active ? 'badge--perm' : '';
        const title = token.is_active
            ? ('Cliquer pour activer ou désactiver' + (titleExtra ? ' — ' + titleExtra : ''))
            : 'Token révoqué — modification impossible';
        return `<span role="button" tabindex="0" class="badge ${tone} ${clickable}" data-token-id="${token.id}" data-perm="${field}" title="${escapeHtml(title)}">${escapeHtml(label)}</span>`;
    }

    /**
     * Clic sur les tags de permissions (délégation sur #tokensContainer).
     */
    function setupPermissionsBadgeClick() {
        const container = document.getElementById('tokensContainer');
        if (!container || container.dataset.badgeClickInit === '1') return;
        container.dataset.badgeClickInit = '1';
        container.addEventListener('click', function (e) {
            const badge = e.target.closest('.badge--perm');
            if (!badge || badge.classList.contains('is-busy')) return;
            const id = parseInt(badge.dataset.tokenId, 10);
            const perm = badge.dataset.perm;
            if (!id || !perm) return;
            const tok = tokens.find(function (t) { return t.id === id; });
            if (!tok || !tok.is_active) return;
            void toggleTokenPermission(id, perm, badge);
        });
    }

    /**
     * Bascule une permission puis PATCH /api/tokens/:id
     */
    async function toggleTokenPermission(tokenId, perm, badgeEl) {
        const tok = tokens.find(function (t) { return t.id === tokenId; });
        if (!tok) return;
        if (perm === 'can_delete_entreprises' && !tok.can_read_entreprises) {
            showError('Activez d’abord la permission « Entreprises » pour autoriser la suppression.');
            return;
        }
        const next = {
            can_read_entreprises: !!tok.can_read_entreprises,
            can_read_emails: !!tok.can_read_emails,
            can_read_statistics: !!tok.can_read_statistics,
            can_read_campagnes: !!tok.can_read_campagnes,
            can_delete_entreprises: !!(tok.can_read_entreprises && tok.can_delete_entreprises),
        };
        next[perm] = !next[perm];
        if (perm === 'can_read_entreprises' && !next.can_read_entreprises) {
            next.can_delete_entreprises = false;
        }

        badgeEl.classList.add('is-busy');
        try {
            const response = await fetch('/api/tokens/' + tokenId, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(next),
            });
            const data = await response.json();
            if (!data.success) {
                showError(data.error || 'Mise à jour impossible');
                await loadTokens();
                return;
            }
            var idx = tokens.findIndex(function (t) { return t.id === tokenId; });
            if (idx !== -1 && data.data) {
                tokens[idx] = data.data;
            }
            displayTokens(tokens);
            showSuccess('Permission mise à jour.');
        } catch (err) {
            console.error(err);
            showError('Erreur réseau lors de la mise à jour des permissions');
            await loadTokens();
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
            
            const permissions = [
                permBadgeHtml(token, 'can_read_entreprises', 'Entreprises', 'liste et détail API'),
                permBadgeHtml(token, 'can_read_emails', 'Emails'),
                permBadgeHtml(token, 'can_read_statistics', 'Statistiques'),
                permBadgeHtml(token, 'can_read_campagnes', 'Campagnes'),
                permBadgeHtml(token, 'can_delete_entreprises', 'Suppr. entreprises', 'DELETE /api/public/entreprises/<id>'),
            ];

            return `
                <div class="token-card ${statusClass}">
                    <div class="token-header">
                        <div>
                            <div class="token-name">${escapeHtml(token.name)}</div>
                            ${token.app_url ? `<div class="token-url"><i class="fas fa-link"></i> ${escapeHtml(token.app_url)}</div>` : ''}
                        </div>
                        <div class="token-actions">
                            ${token.is_active ? `
                                <button class="btn-action btn-view" onclick="openTokenModal(${token.id})" title="Voir le token">
                                    <i class="fas fa-eye"></i> Voir
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
     * La suppression entreprises n'a de sens qu'avec la lecture entreprises (formulaire de création).
     */
    function wireDeleteEntreprisesPermission() {
        const pe = document.getElementById('permEntreprises');
        const pd = document.getElementById('permDeleteEntreprises');
        if (!pe || !pd) return;

        function sync() {
            const wrap = pd.closest('.permission-item');
            if (!pe.checked) {
                pd.checked = false;
                pd.disabled = true;
                if (wrap) wrap.classList.remove('is-active');
            } else {
                pd.disabled = false;
                if (wrap) wrap.classList.toggle('is-active', pd.checked);
            }
        }

        if (pe.dataset.deletePermWired === '1') {
            sync();
            return;
        }
        pe.dataset.deletePermWired = '1';
        pe.addEventListener('change', sync);
        pd.addEventListener('change', function () {
            const wrap = pd.closest('.permission-item');
            if (wrap) wrap.classList.toggle('is-active', pd.checked);
        });
        sync();
    }

    function setupPermissionTiles() {
        const items = document.querySelectorAll('.permissions-group .permission-item');
        if (!items.length) return;

        items.forEach(item => {
            if (item.dataset.permissionTileInit === '1') return;
            const checkbox = item.querySelector('input[type="checkbox"]');
            if (!checkbox) return;

            // État initial
            if (checkbox.checked) {
                item.classList.add('is-active');
            }

            // Synchroniser l'état visuel dès que la checkbox change (click clavier, click souris, etc.)
            checkbox.addEventListener('change', function () {
                item.classList.toggle('is-active', checkbox.checked);
            });

            item.dataset.permissionTileInit = '1';
        });
    }

    /**
     * Configure le formulaire de création
     */
    function setupForm() {
        const form = document.getElementById('createTokenForm');
        if (!form) return;

        // Initialiser les tuiles de permissions (visuel + clic)
        setupPermissionTiles();
        wireDeleteEntreprisesPermission();

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
                can_read_campagnes: document.getElementById('permCampagnes').checked,
                can_delete_entreprises: document.getElementById('permDeleteEntreprises').checked
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
                    // Réinitialiser l'état visuel des tuiles après reset
                    setupPermissionTiles();
                    wireDeleteEntreprisesPermission();
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
        openTokenModalWithData({
            token: tokenData.token || '',
            site: tokenData.app_url || '',
            subtitle: "Token créé. Copie-le maintenant, il ne sera plus affiché automatiquement ensuite."
        });
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
    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            showSuccess('Copié dans le presse-papier !');
        } catch (error) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            showSuccess('Copié dans le presse-papier !');
        }
    }

    window.copyToken = async function(token) {
        return copyToClipboard(token);
    };

    function setupTokenModal() {
        const modal = document.getElementById('tokenModal');
        if (!modal) return;

        modal.querySelectorAll('[data-close-modal="1"]').forEach((el) => {
            el.addEventListener('click', closeTokenModal);
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeTokenModal();
        });

        const siteInput = document.getElementById('tokenModalSite');
        const tokenInput = document.getElementById('tokenModalValue');
        const copySiteBtn = document.getElementById('tokenModalCopySite');
        const copyTokenBtn = document.getElementById('tokenModalCopyToken');

        if (copySiteBtn && siteInput) {
            copySiteBtn.addEventListener('click', async () => {
                await copyToClipboard(modalState.site || siteInput.value || '');
            });
        }
        if (copyTokenBtn && tokenInput) {
            copyTokenBtn.addEventListener('click', async () => {
                await copyToClipboard(modalState.token || tokenInput.value || '');
            });
        }
    }

    function renderTokenQr(token) {
        const el = document.getElementById('tokenModalQr');
        if (!el) return;
        el.innerHTML = '';
        const t = (token || '').trim();
        if (!t || typeof QRCode === 'undefined') {
            if (!t) {
                el.innerHTML = '<span style="color:#64748b;font-size:12px;">—</span>';
            } else {
                el.innerHTML = '<span style="color:#b45309;font-size:11px;">QR indisponible (script bloqué)</span>';
            }
            return;
        }
        try {
            new QRCode(el, {
                text: t,
                width: 196,
                height: 196,
                colorDark: '#0f172a',
                colorLight: '#ffffff',
                correctLevel: QRCode.CorrectLevel.M,
            });
        } catch (e) {
            console.error(e);
            el.innerHTML = '<span style="color:#b45309;font-size:11px;">QR erreur</span>';
        }
    }

    function openTokenModalWithData({ token, site, subtitle }) {
        const modal = document.getElementById('tokenModal');
        if (!modal) return;

        modalState = { token: token || '', site: site || '', subtitle: subtitle || '' };

        const subtitleEl = document.getElementById('tokenModalSubtitle');
        const siteInput = document.getElementById('tokenModalSite');
        const tokenInput = document.getElementById('tokenModalValue');
        const copySiteBtn = document.getElementById('tokenModalCopySite');
        const copyTokenBtn = document.getElementById('tokenModalCopyToken');

        if (subtitleEl) subtitleEl.textContent = modalState.subtitle || 'Vérifie le site et copie le token.';
        if (siteInput) siteInput.value = modalState.site || '';
        if (tokenInput) tokenInput.value = modalState.token || '';

        if (copySiteBtn) copySiteBtn.disabled = !(modalState.site || '').trim();
        if (copyTokenBtn) copyTokenBtn.disabled = !(modalState.token || '').trim();

        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');

        renderTokenQr(modalState.token);
    }

    function closeTokenModal() {
        const modal = document.getElementById('tokenModal');
        if (!modal) return;
        const qr = document.getElementById('tokenModalQr');
        if (qr) qr.innerHTML = '';
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
    }

    window.openTokenModal = async function(tokenId) {
        try {
            const res = await fetch(`/api/tokens/${tokenId}/reveal`);
            const data = await res.json();
            if (!data.success) {
                showError(data.error || "Impossible d'afficher le token");
                return;
            }
            const d = data.data || {};
            openTokenModalWithData({
                token: d.token || '',
                site: d.app_url || '',
                subtitle: d.name ? `Token: ${d.name}` : 'Token API',
            });
        } catch (e) {
            showError("Impossible d'afficher le token");
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

