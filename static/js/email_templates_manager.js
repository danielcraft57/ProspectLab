// UI - Gestion des templates email (BDD via /api/templates)

(function () {
    const $ = (sel) => document.querySelector(sel);
    const listEl = $('#etm-list');
    const searchInput = $('#etm-search-input');
    const clearSearchBtn = $('#etm-clear-search');
    const categoryFilter = $('#etm-category');
    const sortFilter = $('#etm-sort');

    const newBtn = $('#etm-new-btn');
    const importBtn = $('#etm-import-btn');
    const saveBtn = $('#etm-save-btn');
    const deleteBtn = $('#etm-delete-btn');
    const previewToggleBtn = $('#etm-preview-toggle');
    const badgeEl = $('#etm-status-badge');
    const toastEl = $('#etm-toast');

    const idInput = $('#etm-id');
    const nameInput = $('#etm-name');
    const categoryInput = $('#etm-category-edit');
    const subjectInput = $('#etm-subject');
    const contentInput = $('#etm-content');
    const isHtmlInput = $('#etm-is-html');

    const previewWrap = $('#etm-preview');
    const previewIframe = $('#etm-preview-iframe');
    const previewText = $('#etm-preview-text');

    const chips = Array.from(document.querySelectorAll('.etm-chip'));

    let templates = [];
    let activeId = null;
    let dirty = false;
    let previewOpen = false;

    function setBadge(text, kind) {
        badgeEl.textContent = text;
        if (kind === 'warn') {
            badgeEl.style.background = 'rgba(234,179,8,0.12)';
            badgeEl.style.borderColor = 'rgba(234,179,8,0.22)';
            badgeEl.style.color = 'rgb(133,77,14)';
        } else if (kind === 'error') {
            badgeEl.style.background = 'rgba(239,68,68,0.12)';
            badgeEl.style.borderColor = 'rgba(239,68,68,0.22)';
            badgeEl.style.color = 'rgb(153,27,27)';
        } else {
            badgeEl.style.background = '';
            badgeEl.style.borderColor = '';
            badgeEl.style.color = '';
        }
    }

    function toast(message) {
        if (!toastEl) return;
        toastEl.textContent = message;
        toastEl.hidden = false;
        toastEl.classList.add('etm-toast--show');
        window.clearTimeout(toastEl.__t);
        toastEl.__t = window.setTimeout(() => {
            toastEl.classList.remove('etm-toast--show');
            window.setTimeout(() => {
                toastEl.hidden = true;
            }, 220);
        }, 2200);
    }

    function normalize(t) {
        const d = { ...t };
        d.is_html = !!d.is_html;
        return d;
    }

    async function loadTemplates() {
        setBadge('Chargement...', 'warn');
        const res = await fetch('/api/templates', { headers: { 'Accept': 'application/json' } });
        const data = await res.json();
        templates = (Array.isArray(data) ? data : []).map(normalize);
        setBadge('Prêt', 'ok');
        renderList();
        if (!activeId && templates.length) {
            selectTemplate(templates[0].id);
        } else {
            refreshEditorButtons();
        }
    }

    function formatUpdated(tpl) {
        const v = tpl.updated_at || tpl.created_at;
        if (!v) return '';
        try {
            const d = new Date(v);
            return d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
        } catch (e) {
            return '';
        }
    }

    function filteredTemplates() {
        const q = (searchInput.value || '').trim().toLowerCase();
        const cat = categoryFilter.value;

        let items = templates.slice();
        if (cat) {
            items = items.filter(t => (t.category || '') === cat);
        }
        if (q) {
            items = items.filter(t => {
                const hay = `${t.id || ''} ${t.name || ''} ${t.subject || ''}`.toLowerCase();
                return hay.includes(q);
            });
        }

        const sort = sortFilter.value;
        if (sort === 'name_asc') {
            items.sort((a, b) => (a.name || '').localeCompare((b.name || ''), 'fr', { sensitivity: 'base' }));
        } else {
            items.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
        }
        return items;
    }

    function renderList() {
        if (!listEl) return;
        const items = filteredTemplates();
        listEl.innerHTML = '';

        if (!items.length) {
            const empty = document.createElement('div');
            empty.className = 'etm-item';
            empty.style.cursor = 'default';
            empty.innerHTML = '<div class="etm-item-title"><strong>Aucun modèle</strong><span class="etm-pill">0</span></div><div class="etm-item-meta">Crée ton premier template.</div>';
            listEl.appendChild(empty);
            return;
        }

        items.forEach(t => {
            const el = document.createElement('div');
            el.className = 'etm-item' + (t.id === activeId ? ' etm-item--active' : '');
            el.dataset.templateId = t.id;
            el.innerHTML = `
                <div class="etm-item-title">
                    <strong>${escapeHtml(t.name || t.id)}</strong>
                    <span class="etm-pill">${escapeHtml(t.category || 'other')}${t.is_html ? ' · HTML' : ''}</span>
                </div>
                <div class="etm-item-meta">
                    <span>${escapeHtml(t.id)}</span>
                    <span>•</span>
                    <span>${escapeHtml(formatUpdated(t) || '')}</span>
                </div>
            `;
            el.addEventListener('click', () => selectTemplate(t.id));
            listEl.appendChild(el);
        });
    }

    function escapeHtml(str) {
        return String(str || '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    function currentEditorData() {
        return {
            id: (idInput.value || '').trim(),
            name: (nameInput.value || '').trim(),
            category: (categoryInput.value || 'cold_email').trim(),
            subject: (subjectInput.value || '').trim(),
            content: contentInput.value || '',
            is_html: !!isHtmlInput.checked
        };
    }

    function setEditorData(tpl) {
        const t = tpl ? normalize(tpl) : null;
        idInput.value = t?.id || '';
        nameInput.value = t?.name || '';
        categoryInput.value = t?.category || 'cold_email';
        subjectInput.value = t?.subject || '';
        contentInput.value = t?.content || '';
        isHtmlInput.checked = !!t?.is_html || categoryInput.value === 'html_email';
        dirty = false;
        refreshEditorButtons();
        refreshPreview();
    }

    function refreshEditorButtons() {
        const hasActive = !!activeId;
        saveBtn.disabled = !dirty || !(nameInput.value || '').trim() || !(contentInput.value || '').trim();
        deleteBtn.disabled = !hasActive;
        if (dirty) {
            setBadge('Modifié', 'warn');
        } else {
            setBadge('Prêt', 'ok');
        }
    }

    function markDirty() {
        dirty = true;
        refreshEditorButtons();
    }

    function selectTemplate(templateId) {
        if (dirty && templateId !== activeId) {
            const ok = window.confirm('Tu as des modifications non enregistrées. Continuer quand même ?');
            if (!ok) return;
        }
        activeId = templateId;
        const tpl = templates.find(t => t.id === templateId);
        setEditorData(tpl);
        renderList();
    }

    function newTemplate() {
        if (dirty) {
            const ok = window.confirm('Tu as des modifications non enregistrées. Créer un nouveau modèle quand même ?');
            if (!ok) return;
        }
        activeId = null;
        setEditorData({
            id: '',
            name: '',
            category: 'cold_email',
            subject: '',
            content: '',
            is_html: false
        });
        renderList();
        nameInput.focus();
    }

    async function saveTemplate() {
        const data = currentEditorData();
        if (!data.name || !data.content) {
            toast('Nom et contenu requis.');
            return;
        }

        const isUpdate = !!activeId;
        let templateId = activeId || data.id;

        try {
            saveBtn.disabled = true;
            setBadge('Enregistrement...', 'warn');

            if (isUpdate) {
                const res = await fetch(`/api/templates/${encodeURIComponent(activeId)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: data.name,
                        category: data.category,
                        subject: data.subject,
                        content: data.content
                    })
                });
                const payload = await res.json();
                if (!res.ok) throw new Error(payload?.error || 'Erreur sauvegarde');
                templateId = payload.template?.id || activeId;
            } else {
                // Création: si l'utilisateur renseigne un ID, on le passe à l'API
                const res = await fetch('/api/templates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                            id: data.id || undefined,
                        name: data.name,
                        category: data.category,
                        subject: data.subject,
                        content: data.content
                    })
                });
                const payload = await res.json();
                if (!res.ok) throw new Error(payload?.error || 'Erreur création');
                templateId = payload.template?.id || templateId;
            }

            await loadTemplates();
            selectTemplate(templateId);
            toast('Enregistré.');
            setBadge('Enregistré', 'ok');
            window.setTimeout(() => setBadge('Prêt', 'ok'), 800);
        } catch (e) {
            setBadge('Erreur', 'error');
            toast(e.message || 'Erreur');
        } finally {
            refreshEditorButtons();
        }
    }

    async function deleteTemplate() {
        if (!activeId) return;
        const ok = window.confirm('Supprimer ce modèle ?');
        if (!ok) return;
        try {
            setBadge('Suppression...', 'warn');
            const res = await fetch(`/api/templates/${encodeURIComponent(activeId)}`, { method: 'DELETE' });
            const payload = await res.json();
            if (!res.ok) throw new Error(payload?.error || 'Erreur suppression');
            toast('Supprimé.');
            activeId = null;
            await loadTemplates();
            if (templates.length) {
                selectTemplate(templates[0].id);
            } else {
                newTemplate();
            }
        } catch (e) {
            setBadge('Erreur', 'error');
            toast(e.message || 'Erreur');
        } finally {
            refreshEditorButtons();
        }
    }

    function refreshPreview() {
        if (!previewOpen) return;
        const data = currentEditorData();
        if (data.is_html || data.category === 'html_email') {
            previewText.hidden = true;
            previewIframe.hidden = false;
            const html = data.content || '';
            previewIframe.srcdoc = html;
        } else {
            previewIframe.hidden = true;
            previewText.hidden = false;
            previewText.textContent = data.content || '';
        }
    }

    function togglePreview() {
        previewOpen = !previewOpen;
        previewWrap.hidden = !previewOpen;
        previewToggleBtn.innerHTML = previewOpen
            ? '<i class="fa-regular fa-eye-slash"></i> Fermer'
            : '<i class="fa-regular fa-eye"></i> Aperçu';
        refreshPreview();
    }

    function insertAtCursor(textarea, text) {
        try {
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const value = textarea.value;
            textarea.value = value.slice(0, start) + text + value.slice(end);
            const pos = start + text.length;
            textarea.setSelectionRange(pos, pos);
            textarea.focus();
        } catch (e) {
            textarea.value += text;
            textarea.focus();
        }
    }

    function importJson() {
        const raw = window.prompt('Colle ici un JSON du style {"templates":[...]} ou juste un tableau de templates.');
        if (!raw) return;
        let parsed;
        try {
            parsed = JSON.parse(raw);
        } catch (e) {
            toast('JSON invalide.');
            return;
        }
        const items = Array.isArray(parsed) ? parsed : (parsed?.templates || []);
        if (!Array.isArray(items) || !items.length) {
            toast('Aucun template dans ce JSON.');
            return;
        }

        // Import léger: on crée les templates un par un via POST (id auto). Pour garder les ids, il faudrait un endpoint dédié.
        (async () => {
            let ok = 0;
            for (const t of items) {
                try {
                    const res = await fetch('/api/templates', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: t.name || t.id || 'Template importé',
                            category: t.category || (t.is_html ? 'html_email' : 'cold_email'),
                            subject: t.subject || '',
                            content: t.content || ''
                        })
                    });
                    if (res.ok) ok += 1;
                } catch (e) {}
            }
            await loadTemplates();
            toast(`Import terminé: ${ok}/${items.length}`);
        })();
    }

    // Bind events
    newBtn.addEventListener('click', newTemplate);
    saveBtn.addEventListener('click', saveTemplate);
    deleteBtn.addEventListener('click', deleteTemplate);
    previewToggleBtn.addEventListener('click', togglePreview);
    importBtn.addEventListener('click', importJson);

    [idInput, nameInput, categoryInput, subjectInput, contentInput, isHtmlInput].forEach(el => {
        el.addEventListener('input', () => {
            markDirty();
            if (el === categoryInput) {
                // auto switch HTML flag when category is html_email
                if (categoryInput.value === 'html_email') {
                    isHtmlInput.checked = true;
                }
            }
            refreshPreview();
        });
        el.addEventListener('change', () => {
            markDirty();
            refreshPreview();
        });
    });

    chips.forEach(ch => {
        ch.addEventListener('click', () => {
            const ins = ch.getAttribute('data-insert') || '';
            insertAtCursor(contentInput, ins);
            markDirty();
            refreshPreview();
        });
    });

    searchInput.addEventListener('input', renderList);
    categoryFilter.addEventListener('change', renderList);
    sortFilter.addEventListener('change', renderList);
    clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        renderList();
        searchInput.focus();
    });

    // Ctrl+S pour save
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            e.preventDefault();
            if (!saveBtn.disabled) saveTemplate();
        }
        if (e.key === 'Escape' && previewOpen) {
            togglePreview();
        }
    });

    // Init
    loadTemplates().catch(() => {
        setBadge('Erreur chargement', 'error');
        toast('Impossible de charger les templates.');
    });
})();

