(function () {
    'use strict';

    function notify(message, type = 'info') {
        try {
            if (window.Notifications && typeof window.Notifications.show === 'function') {
                window.Notifications.show(message, type);
                return;
            }
        } catch (e) {}
        alert(message);
    }

    const tableWrap = document.getElementById('mac-accounts-table-wrap');
    const emptyEl = document.getElementById('mac-accounts-empty');
    const statsWrap = document.getElementById('mac-stats');
    const searchInput = document.getElementById('mac-search-input');
    const pillsWrap = document.getElementById('mac-filter-pills');
    const form = document.getElementById('mac-create-form');
    const statusBox = document.getElementById('mac-create-status');
    const titleEl = document.getElementById('mac-form-title');
    const subtitleEl = document.getElementById('mac-form-subtitle');
    const submitBtn = document.getElementById('mac-submit-btn');
    const cancelEditBtn = document.getElementById('mac-cancel-edit-btn');
    const resetFormBtn = document.getElementById('mac-reset-form-btn');
    const deleteCurrentBtn = document.getElementById('mac-delete-current-btn');
    const deleteZone = document.getElementById('mac-edit-danger-zone');
    const newBtn = document.getElementById('mac-new-account-btn');

    const fields = {
        accountId: document.getElementById('mac-account-id'),
        slug: document.getElementById('mac-slug'),
        label: document.getElementById('mac-label'),
        domainName: document.getElementById('mac-domain-name'),
        smtpHost: document.getElementById('mac-smtp-host'),
        smtpPort: document.getElementById('mac-smtp-port'),
        smtpUsername: document.getElementById('mac-smtp-username'),
        smtpPassword: document.getElementById('mac-smtp-password'),
        defaultSender: document.getElementById('mac-default-sender'),
        replyTo: document.getElementById('mac-reply-to'),
        smtpUseTls: document.getElementById('mac-smtp-use-tls'),
        smtpUseSsl: document.getElementById('mac-smtp-use-ssl'),
        isActive: document.getElementById('mac-is-active'),
    };

    let accountsCache = [];
    let editingAccountId = null;
    let currentFilter = 'all';
    let currentSearch = '';

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatDate(value) {
        if (!value) return 'Jamais';
        try {
            return new Date(value).toLocaleString('fr-FR');
        } catch (_) {
            return String(value);
        }
    }

    function currentNextUrl() {
        return window.location.pathname + window.location.search;
    }

    function badgeClass(ok, missingLabelClass = 'mac-badge') {
        if (ok === true || ok === 1) return 'mac-badge mac-badge--ok';
        if (ok === false || ok === 0) return 'mac-badge mac-badge--no';
        return missingLabelClass;
    }

    function setStatus(message, kind) {
        if (!statusBox) return;
        statusBox.textContent = message || '';
        statusBox.className = 'mac-inline-status';
        if (!message) return;
        statusBox.classList.add('is-visible');
        if (kind === 'error') statusBox.classList.add('is-error');
        if (kind === 'success') statusBox.classList.add('is-success');
    }

    function clearStatus() {
        setStatus('', null);
    }

    function resetForm() {
        editingAccountId = null;
        if (form) form.reset();
        if (fields.accountId) fields.accountId.value = '';
        if (fields.smtpPort) fields.smtpPort.value = '587';
        if (fields.smtpUseTls) fields.smtpUseTls.checked = true;
        if (fields.smtpUseSsl) fields.smtpUseSsl.checked = false;
        if (fields.isActive) fields.isActive.checked = true;
        if (fields.smtpPassword) fields.smtpPassword.value = '';
        if (titleEl) titleEl.textContent = 'Ajouter un compte';
        if (subtitleEl) subtitleEl.textContent = 'Crée un nouvel expéditeur pour un domaine.';
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Créer le compte';
        }
        if (cancelEditBtn) cancelEditBtn.style.display = 'none';
        if (deleteZone) deleteZone.style.display = 'none';
        clearStatus();
    }

    function fillForm(acc) {
        editingAccountId = acc.id;
        if (fields.accountId) fields.accountId.value = String(acc.id);
        if (fields.slug) fields.slug.value = acc.slug || '';
        if (fields.label) fields.label.value = acc.label || '';
        if (fields.domainName) fields.domainName.value = acc.domain_name || '';
        if (fields.smtpHost) fields.smtpHost.value = acc.smtp_host || '';
        if (fields.smtpPort) fields.smtpPort.value = acc.smtp_port || 587;
        if (fields.smtpUsername) fields.smtpUsername.value = acc.smtp_username || '';
        if (fields.smtpPassword) fields.smtpPassword.value = '';
        if (fields.defaultSender) fields.defaultSender.value = acc.default_sender || '';
        if (fields.replyTo) fields.replyTo.value = acc.reply_to || '';
        if (fields.smtpUseTls) fields.smtpUseTls.checked = !!acc.smtp_use_tls;
        if (fields.smtpUseSsl) fields.smtpUseSsl.checked = !!acc.smtp_use_ssl;
        if (fields.isActive) fields.isActive.checked = !!acc.is_active;
        if (titleEl) titleEl.textContent = `Modifier ${acc.label || acc.slug || 'le compte'}`;
        if (subtitleEl) subtitleEl.textContent = 'Mets à jour la configuration SMTP, le domaine et l’identité affichée.';
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Enregistrer les modifications';
        }
        if (cancelEditBtn) cancelEditBtn.style.display = 'inline-flex';
        if (deleteZone) deleteZone.style.display = 'block';
        clearStatus();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function accountCard(acc) {
        const isSelected = editingAccountId === acc.id;
        const activeClass = acc.is_active ? 'mac-badge mac-badge--ok' : 'mac-badge mac-badge--no';
        const pwClass = acc.has_password ? 'mac-badge mac-badge--ok' : 'mac-badge mac-badge--no';
        const dnsClass = acc.last_dns_check_at ? 'mac-badge mac-badge--info' : 'mac-badge';
        const smtpStateClass = badgeClass(acc.last_test_ok);

        return `
            <article class="mac-account ${isSelected ? 'is-selected' : ''}">
                <div class="mac-account-top">
                    <div>
                        <div class="mac-account-title">
                            <span class="mac-domain-dot"></span>
                            <div>
                                <strong>${escapeHtml(acc.label || acc.slug || 'Compte')}</strong>
                                <div class="mac-hint">${escapeHtml(acc.domain_name || 'Domaine non renseigné')}</div>
                            </div>
                        </div>
                        <div class="mac-badges">
                            <span class="${activeClass}">${acc.is_active ? 'Actif' : 'Inactif'}</span>
                            <span class="${pwClass}">${acc.has_password ? 'Mot de passe OK' : 'Pas de mot de passe'}</span>
                            <span class="${smtpStateClass}">SMTP: ${acc.last_test_at ? (acc.last_test_ok ? 'OK' : 'KO') : 'Jamais testé'}</span>
                            <span class="${dnsClass}">DNS: ${acc.last_dns_check_at ? 'Vérifié' : 'Non vérifié'}</span>
                        </div>
                    </div>
                    <div class="mac-account-toolbar">
                        <div class="mac-toggle">
                            <span class="mac-toggle-label">${acc.is_active ? 'Actif' : 'Inactif'}</span>
                            <label class="mac-switch" aria-label="Basculer l'état du domaine ${escapeHtml(acc.label || acc.slug || 'compte')}">
                                <input type="checkbox" data-action="toggle-active" data-account-id="${acc.id}" ${acc.is_active ? 'checked' : ''}>
                                <span class="mac-switch-slider"></span>
                            </label>
                        </div>
                        <div class="mac-menu" data-menu>
                            <button class="mac-btn mac-btn--soft mac-menu-toggle" type="button" data-action="toggle-menu" data-account-id="${acc.id}" aria-label="Actions ${escapeHtml(acc.label || acc.slug || 'compte')}">
                                <i class="fa-solid fa-ellipsis"></i>
                            </button>
                            <div class="mac-menu-panel">
                                <button class="mac-menu-item" type="button" data-action="edit" data-account-id="${acc.id}">
                                    <i class="fa-solid fa-pen"></i>
                                    Modifier
                                </button>
                                <button class="mac-menu-item" type="button" data-action="toggle-active" data-account-id="${acc.id}" data-next-active="${acc.is_active ? '0' : '1'}">
                                    <i class="fa-solid ${acc.is_active ? 'fa-toggle-off' : 'fa-toggle-on'}"></i>
                                    ${acc.is_active ? 'Désactiver' : 'Activer'}
                                </button>
                                <button class="mac-menu-item" type="button" data-action="probe" data-account-id="${acc.id}">
                                    <i class="fa-solid fa-plug-circle-check"></i>
                                    Probe SMTP
                                </button>
                                <button class="mac-menu-item" type="button" data-action="check-dns" data-account-id="${acc.id}">
                                    <i class="fa-solid fa-diagram-project"></i>
                                    Check DNS
                                </button>
                                <button class="mac-menu-item" type="button" data-action="send-test" data-account-id="${acc.id}">
                                    <i class="fa-solid fa-paper-plane"></i>
                                    Envoyer test
                                </button>
                                <div class="mac-menu-sep"></div>
                                <button class="mac-menu-item mac-menu-item--danger" type="button" data-action="delete" data-account-id="${acc.id}">
                                    <i class="fa-solid fa-trash"></i>
                                    Supprimer
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="mac-account-meta">
                    <div class="mac-kv">
                        <div class="mac-kv-label">SMTP</div>
                        <div class="mac-kv-value">${escapeHtml(acc.smtp_host || '-')} : ${escapeHtml(acc.smtp_port || 587)}</div>
                    </div>
                    <div class="mac-kv">
                        <div class="mac-kv-label">Sécurité</div>
                        <div class="mac-kv-value">${acc.smtp_use_ssl ? 'SSL implicite' : (acc.smtp_use_tls ? 'STARTTLS' : 'Sans chiffrement')}</div>
                    </div>
                    <div class="mac-kv">
                        <div class="mac-kv-label">Username</div>
                        <div class="mac-kv-value">${escapeHtml(acc.smtp_username || '-')}</div>
                    </div>
                    <div class="mac-kv">
                        <div class="mac-kv-label">From</div>
                        <div class="mac-kv-value">${escapeHtml(acc.default_sender || '-')}</div>
                    </div>
                    <div class="mac-kv">
                        <div class="mac-kv-label">Dernier test SMTP</div>
                        <div class="mac-kv-value">${escapeHtml(formatDate(acc.last_test_at))}</div>
                    </div>
                    <div class="mac-kv">
                        <div class="mac-kv-label">Dernier check DNS</div>
                        <div class="mac-kv-value">${escapeHtml(formatDate(acc.last_dns_check_at))}</div>
                    </div>
                </div>

                <div class="mac-actions">
                    <button class="mac-btn mac-btn--soft" type="button" data-action="probe" data-account-id="${acc.id}">
                        <i class="fa-solid fa-plug-circle-check"></i>
                        Probe SMTP
                    </button>
                    <button class="mac-btn mac-btn--soft" type="button" data-action="check-dns" data-account-id="${acc.id}">
                        <i class="fa-solid fa-diagram-project"></i>
                        Check DNS
                    </button>
                    <button class="mac-btn mac-btn--primary" type="button" data-action="send-test" data-account-id="${acc.id}">
                        <i class="fa-solid fa-paper-plane"></i>
                        Envoyer test
                    </button>
                </div>
            </article>
        `;
    }

    function renderStats(accounts) {
        if (!statsWrap) return;
        const total = accounts.length;
        const active = accounts.filter(acc => !!acc.is_active).length;
        const dnsPending = accounts.filter(acc => !acc.last_dns_check_at).length;
        statsWrap.innerHTML = `
            <div class="mac-stat">
                <div class="mac-stat-label">Comptes</div>
                <div class="mac-stat-value">${total}</div>
            </div>
            <div class="mac-stat">
                <div class="mac-stat-label">Actifs</div>
                <div class="mac-stat-value">${active}</div>
            </div>
            <div class="mac-stat">
                <div class="mac-stat-label">DNS à vérifier</div>
                <div class="mac-stat-value">${dnsPending}</div>
            </div>
        `;
    }

    function filterAccounts(accounts) {
        return accounts.filter(acc => {
            if (currentFilter === 'active' && !acc.is_active) return false;
            if (currentFilter === 'inactive' && acc.is_active) return false;
            if (currentFilter === 'dns-missing' && acc.last_dns_check_at) return false;

            if (!currentSearch) return true;
            const haystack = [
                acc.label,
                acc.slug,
                acc.domain_name,
                acc.smtp_host,
                acc.smtp_username,
                acc.default_sender,
            ].join(' ').toLowerCase();
            return haystack.includes(currentSearch);
        });
    }

    function closeMenus() {
        document.querySelectorAll('.mac-menu.is-open').forEach(el => el.classList.remove('is-open'));
    }

    async function fetchJson(url, options) {
        const res = await fetch(url, options);
        const data = await res.json().catch(() => ({}));
        return { res, data };
    }

    async function loadAccounts() {
        if (!tableWrap) return;
        const { data } = await fetchJson('/api/mail-accounts', { headers: { Accept: 'application/json' } });
        const accounts = Array.isArray(data && data.accounts) ? data.accounts : [];
        accountsCache = accounts;
        renderStats(accounts);

        const filteredAccounts = filterAccounts(accounts);

        if (!filteredAccounts.length) {
            tableWrap.innerHTML = '';
            if (emptyEl) {
                emptyEl.style.display = 'block';
                emptyEl.textContent = accounts.length
                    ? 'Aucun domaine ne correspond à ta recherche ou à ce filtre.'
                    : 'Aucun compte configuré pour le moment.';
            }
            return;
        }

        if (emptyEl) emptyEl.style.display = 'none';

        if (editingAccountId && !accounts.some(acc => String(acc.id) === String(editingAccountId))) {
            resetForm();
        }

        tableWrap.innerHTML = filteredAccounts.map(accountCard).join('');
    }

    function payloadFromForm(isEditMode) {
        const smtpPort = parseInt(fields.smtpPort?.value || '587', 10);
        const password = fields.smtpPassword?.value || '';

        const payload = {
            slug: fields.slug?.value?.trim() || '',
            label: fields.label?.value?.trim() || '',
            domain_name: fields.domainName?.value?.trim() || null,
            smtp_host: fields.smtpHost?.value?.trim() || '',
            smtp_port: Number.isNaN(smtpPort) ? 587 : smtpPort,
            smtp_use_tls: fields.smtpUseTls?.checked ?? true,
            smtp_use_ssl: fields.smtpUseSsl?.checked ?? false,
            smtp_username: fields.smtpUsername?.value?.trim() || null,
            default_sender: fields.defaultSender?.value?.trim() || '',
            reply_to: fields.replyTo?.value?.trim() || null,
            is_active: fields.isActive?.checked ?? true,
        };

        if (!isEditMode || String(password).trim()) {
            payload.smtp_password = String(password).trim() ? password : null;
        }

        return payload;
    }

    async function postJson(url, payload) {
        const { data } = await fetchJson(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {}),
        });
        return data;
    }

    async function removeAccount(id) {
        const account = accountsCache.find(acc => String(acc.id) === String(id));
        const name = account ? (account.label || account.slug || `#${id}`) : `#${id}`;
        const ok = window.confirm(`Supprimer définitivement le domaine "${name}" ?`);
        if (!ok) return;

        const { res, data } = await fetchJson(`/api/mail-accounts/${id}`, { method: 'DELETE' });
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Suppression impossible');
        }

        if (String(editingAccountId) === String(id)) {
            resetForm();
        }
        notify('Domaine supprimé.', 'success');
        await loadAccounts();
    }

    document.addEventListener('click', async (e) => {
        const btn = e.target && e.target.closest ? e.target.closest('[data-action][data-account-id]') : null;
        const menuHost = e.target && e.target.closest ? e.target.closest('[data-menu]') : null;
        if (!menuHost) closeMenus();
        if (!btn) return;

        const action = btn.getAttribute('data-action');
        const id = btn.getAttribute('data-account-id');
        if (!action || !id) return;

        try {
            if (action === 'toggle-menu') {
                const menu = btn.closest('[data-menu]');
                const isOpen = menu && menu.classList.contains('is-open');
                closeMenus();
                if (menu && !isOpen) menu.classList.add('is-open');
                return;
            }

            if (action === 'toggle-active') {
                closeMenus();
                const account = accountsCache.find(item => String(item.id) === String(id));
                if (!account) {
                    notify('Compte introuvable.', 'error');
                    return;
                }
                const nextActiveAttr = btn.getAttribute('data-next-active');
                const nextActive = nextActiveAttr !== null
                    ? nextActiveAttr === '1'
                    : !(!!account.is_active);
                const { res, data } = await fetchJson(`/api/mail-accounts/${id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_active: nextActive }),
                });
                if (!res.ok || !data.success) {
                    notify(data.error || 'Impossible de modifier l’état du compte.', 'error');
                    await loadAccounts();
                    return;
                }
                notify(nextActive ? 'Compte activé.' : 'Compte désactivé.', 'success');
                if (String(editingAccountId) === String(id) && fields.isActive) {
                    fields.isActive.checked = nextActive;
                }
                await loadAccounts();
                return;
            }

            if (action === 'edit') {
                closeMenus();
                const acc = accountsCache.find(item => String(item.id) === String(id));
                if (!acc) {
                    notify('Compte introuvable.', 'error');
                    return;
                }
                fillForm(acc);
                await loadAccounts();
                return;
            }

            if (action === 'delete') {
                closeMenus();
                await removeAccount(id);
                return;
            }

            if (action === 'probe') {
                closeMenus();
                notify('Test SMTP en cours...', 'info');
                const data = await postJson(`/api/mail-accounts/${id}/probe`);
                if (data && data.success) {
                    notify(`Probe OK: ${data.message || 'Connexion OK'}`, 'success');
                } else {
                    notify(`Probe KO: ${data.message || data.detail || 'Erreur'}`, 'error');
                }
                await loadAccounts();
                return;
            }

            if (action === 'check-dns') {
                closeMenus();
                notify('Vérification DNS en cours...', 'info');
                const data = await postJson(`/api/mail-accounts/${id}/check-dns`, {});
                if (data && data.success) {
                    const report = data.report || {};
                    const mxCount = Array.isArray(report.mx_records) ? report.mx_records.length : 0;
                    const spfCount = Array.isArray(report.spf_txt) ? report.spf_txt.length : 0;
                    notify(`DNS OK: MX=${mxCount}, SPF=${spfCount}`, 'success');
                } else {
                    notify(`DNS KO: ${data.error || 'Erreur'}`, 'error');
                }
                await loadAccounts();
                return;
            }

            if (action === 'send-test') {
                closeMenus();
                const to = prompt('Adresse destinataire du test (to):');
                if (!to) return;

                const subject = prompt('Sujet du test (optionnel):', '[ProspectLab] Test SMTP');
                const body = prompt('Corps du test (optionnel):', `Test d’envoi depuis ProspectLab (account=${id}).`);
                const payload = { to, subject: subject || null, body: body || null };

                notify('Envoi test en cours...', 'info');
                const data = await postJson(`/api/mail-accounts/${id}/send-test`, payload);
                if (data && data.success) {
                    notify(`Test envoyé: ${data.message || ''}`, 'success');
                } else {
                    notify(`Test KO: ${data.message || data.error || 'Erreur'}`, 'error');
                }
                await loadAccounts();
            }
        } catch (err) {
            notify(`Erreur action ${action}: ${err && err.message ? err.message : String(err)}`, 'error');
        }
    });

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const isEditMode = !!editingAccountId;

            try {
                clearStatus();
                const payload = payloadFromForm(isEditMode);
                const url = isEditMode ? `/api/mail-accounts/${editingAccountId}` : '/api/mail-accounts';
                const method = isEditMode ? 'PATCH' : 'POST';

                setStatus(isEditMode ? 'Mise à jour du compte...' : 'Création du compte...', null);
                const { res, data } = await fetchJson(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!res.ok || !data.success) {
                    setStatus(data.error || 'Erreur lors de l’enregistrement', 'error');
                    notify(data.error || 'Erreur lors de l’enregistrement', 'error');
                    return;
                }

                notify(isEditMode ? 'Compte mis à jour.' : 'Compte créé.', 'success');
                setStatus(isEditMode ? 'Modifications enregistrées avec succès.' : 'Compte créé avec succès.', 'success');
                resetForm();
                await loadAccounts();
            } catch (err) {
                const msg = err && err.message ? err.message : String(err);
                setStatus(msg, 'error');
                notify(msg, 'error');
            }
        });
    }

    if (cancelEditBtn) {
        cancelEditBtn.addEventListener('click', () => {
            resetForm();
            loadAccounts().catch(() => {});
        });
    }

    if (resetFormBtn) {
        resetFormBtn.addEventListener('click', () => {
            resetForm();
            loadAccounts().catch(() => {});
        });
    }

    if (deleteCurrentBtn) {
        deleteCurrentBtn.addEventListener('click', async () => {
            if (!editingAccountId) return;
            try {
                await removeAccount(editingAccountId);
            } catch (err) {
                const msg = err && err.message ? err.message : String(err);
                setStatus(msg, 'error');
                notify(msg, 'error');
            }
        });
    }

    if (newBtn) {
        newBtn.addEventListener('click', () => {
            resetForm();
            if (fields.slug) fields.slug.focus();
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            currentSearch = String(searchInput.value || '').trim().toLowerCase();
            loadAccounts().catch(() => {});
        });
    }

    if (pillsWrap) {
        pillsWrap.addEventListener('click', (e) => {
            const pill = e.target && e.target.closest ? e.target.closest('[data-filter]') : null;
            if (!pill) return;
            currentFilter = pill.getAttribute('data-filter') || 'all';
            pillsWrap.querySelectorAll('[data-filter]').forEach(el => el.classList.toggle('is-active', el === pill));
            loadAccounts().catch(() => {});
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        resetForm();
        loadAccounts().catch(err => {
            notify(`Erreur lors du chargement des comptes: ${err && err.message ? err.message : String(err)}`, 'error');
        });
    });
})();

