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

    const idInput = null;
    const nameInput = $('#etm-name');
    const categoryInput = $('#etm-category-edit');
    const subjectInput = $('#etm-subject');
    const contentInput = $('#etm-content');
    const isHtmlInput = $('#etm-is-html');

    const previewWrap = $('#etm-preview');
    const previewIframe = $('#etm-preview-iframe');
    const previewText = $('#etm-preview-text');

    const chips = Array.from(document.querySelectorAll('.etm-chip'));
    const catChipsEl = $('#etm-cat-chips');

    /** Categories ProspectLab (pub / audit) + classiques */
    const CORE_CATEGORIES = [
        'audit',
        'offres',
        'echantillons',
        'bouquins',
        'cold_email',
        'html_email',
        'linkedin',
        'malt',
        'other',
    ];

    const CATEGORY_LABELS = {
        audit: 'Audit',
        offres: 'Offres',
        echantillons: 'Échantillons',
        bouquins: 'Bouquins',
        cold_email: 'Cold Email',
        html_email: 'Email HTML',
        linkedin: 'LinkedIn',
        malt: 'Malt',
        other: 'Autre',
    };

    /** Couleurs Material par categorie (badges liste + chips) */
    const CATEGORY_STYLES = {
        audit: { bg: 'rgba(37, 99, 235, 0.12)', border: 'rgba(37, 99, 235, 0.35)', text: '#1d4ed8' },
        offres: { bg: 'rgba(22, 163, 74, 0.12)', border: 'rgba(22, 163, 74, 0.35)', text: '#15803d' },
        echantillons: { bg: 'rgba(147, 51, 234, 0.12)', border: 'rgba(147, 51, 234, 0.35)', text: '#7e22ce' },
        bouquins: { bg: 'rgba(234, 88, 12, 0.12)', border: 'rgba(234, 88, 12, 0.35)', text: '#c2410c' },
        html_email: { bg: 'rgba(100, 116, 139, 0.12)', border: 'rgba(100, 116, 139, 0.3)', text: '#475569' },
        cold_email: { bg: 'rgba(100, 116, 139, 0.12)', border: 'rgba(100, 116, 139, 0.3)', text: '#475569' },
        other: { bg: 'rgba(100, 116, 139, 0.1)', border: 'rgba(100, 116, 139, 0.25)', text: '#64748b' },
    };

    /**
     * Normalise la categorie affichee (html_dc_* legacy -> audit).
     * @param {object} tpl
     * @returns {string}
     */
    function displayCategory(tpl) {
        const raw = (tpl?.category || '').trim();
        if (raw && raw !== 'html_email') return raw;
        const id = String(tpl?.id || '');
        if (id.startsWith('html_dc_offres')) return 'offres';
        if (id.startsWith('html_dc_echantillons')) return 'echantillons';
        if (id.startsWith('html_dc_bouquins')) return 'bouquins';
        if (id.startsWith('html_dc_')) return 'audit';
        return raw || 'other';
    }

    function categoryStyle(cat) {
        return CATEGORY_STYLES[cat] || CATEGORY_STYLES.other;
    }

    // Import JSON avancé
    const importPanel = $('#etm-import-panel');
    const importFileInput = $('#etm-import-file');
    const importTextInput = $('#etm-import-text');
    const importParseBtn = $('#etm-import-parse-btn');
    const importApplyBtn = $('#etm-import-apply-btn');
    const importResultEl = $('#etm-import-result');

    let templates = [];
    let activeId = null;
    let dirty = false;
    let previewOpen = false;
    let importState = null;
    let importPanelOpen = false;

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

    function setImportResult(html, kind) {
        if (!importResultEl) return;
        importResultEl.innerHTML = html || '';
        importResultEl.dataset.kind = kind || '';
    }

    function toggleImportPanel() {
        if (!importPanel || !importBtn) return;
        importPanelOpen = !importPanelOpen;
        if (importPanelOpen) {
            importPanel.classList.add('etm-import-panel--open');
            importBtn.classList.add('btn-active');
            importBtn.setAttribute('aria-pressed', 'true');
            // Scroll doux pour amener le panneau dans le viewport
            importPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            // Focus sur la zone texte si présente
            if (importTextInput) {
                setTimeout(() => {
                    importTextInput.focus();
                }, 260);
            }
        } else {
            importPanel.classList.remove('etm-import-panel--open');
            importBtn.classList.remove('btn-active');
            importBtn.setAttribute('aria-pressed', 'false');
        }
    }

    function normalize(t) {
        const d = { ...t };
        d.is_html = !!d.is_html;
        return d;
    }

    function getDistinctCategories() {
        const set = new Set(CORE_CATEGORIES);
        templates.forEach(t => {
            const c = (t.category || '').trim();
            if (c) set.add(c);
        });
        return Array.from(set).sort((a, b) => {
            const ia = CORE_CATEGORIES.indexOf(a);
            const ib = CORE_CATEGORIES.indexOf(b);
            if (ia !== -1 || ib !== -1) {
                if (ia === -1) return 1;
                if (ib === -1) return -1;
                return ia - ib;
            }
            return a.localeCompare(b, 'fr', { sensitivity: 'base' });
        });
    }

    function formatCategoryLabel(value) {
        const v = (value || '').trim();
        if (!v) return '';
        if (CATEGORY_LABELS[v]) return CATEGORY_LABELS[v];
        const cleaned = v.replace(/_/g, ' ');
        return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
    }

    /**
     * Rend les chips Material de filtre categorie.
     */
    function renderCategoryChips() {
        if (!catChipsEl) return;
        const cats = getDistinctCategories();
        const current = categoryFilter ? categoryFilter.value : '';
        const counts = {};
        templates.forEach(t => {
            const c = displayCategory(t);
            counts[c] = (counts[c] || 0) + 1;
        });

        const parts = [];
        parts.push(
            `<button type="button" class="etm-cat-chip etm-cat-chip--all${current === '' ? ' is-active' : ''}" data-cat="" role="tab" aria-selected="${current === '' ? 'true' : 'false'}">Toutes <span class="etm-cat-count">${templates.length}</span></button>`
        );
        cats.forEach(c => {
            const n = counts[c] || 0;
            if (n === 0 && !CORE_CATEGORIES.slice(0, 4).includes(c)) return;
            const active = current === c;
            const st = categoryStyle(c);
            parts.push(
                `<button type="button" class="etm-cat-chip${active ? ' is-active' : ''}" data-cat="${escapeHtml(c)}" role="tab" aria-selected="${active ? 'true' : 'false'}" style="--chip-bg:${st.bg};--chip-border:${st.border};--chip-text:${st.text}">${escapeHtml(formatCategoryLabel(c))} <span class="etm-cat-count">${n}</span></button>`
            );
        });
        catChipsEl.innerHTML = parts.join('');
    }

    function refreshCategorySelectors() {
        const cats = getDistinctCategories();

        // Filtre (select cache, sync avec chips)
        if (categoryFilter) {
            const current = categoryFilter.value;
            categoryFilter.innerHTML = '';

            const optAll = document.createElement('option');
            optAll.value = '';
            optAll.textContent = 'Toutes';
            categoryFilter.appendChild(optAll);

            cats.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c;
                opt.textContent = formatCategoryLabel(c);
                categoryFilter.appendChild(opt);
            });

            if (current && cats.includes(current)) {
                categoryFilter.value = current;
            } else if (current && !cats.includes(current)) {
                categoryFilter.value = '';
            }
        }

        // Select de la fiche d’édition
        if (categoryInput) {
            const current = (categoryInput.value || '').trim() || 'cold_email';
            categoryInput.innerHTML = '';

            cats.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c;
                opt.textContent = formatCategoryLabel(c);
                categoryInput.appendChild(opt);
            });

            if (!cats.includes(current)) {
                const extra = document.createElement('option');
                extra.value = current;
                extra.textContent = formatCategoryLabel(current);
                categoryInput.appendChild(extra);
            }

            categoryInput.value = current;
        }

        renderCategoryChips();
    }

    async function loadTemplates() {
        setBadge('Chargement...', 'warn');
        const res = await fetch('/api/templates?for_editor=1', { headers: { 'Accept': 'application/json' } });
        const data = await res.json();
        templates = (Array.isArray(data) ? data : []).map(normalize);
        refreshCategorySelectors();
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
            items = items.filter(t => displayCategory(t) === cat);
        }
        if (q) {
            items = items.filter(t => {
                const hay = `${t.name || ''} ${t.subject || ''}`.toLowerCase();
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
            const cat = displayCategory(t);
            const st = categoryStyle(cat);
            const el = document.createElement('div');
            el.className = 'etm-item' + (t.id === activeId ? ' etm-item--active' : '');
            el.dataset.templateId = t.id;
            const subj = (t.subject || '').trim();
            const title = (t.name || '').trim() || 'Sans nom';
            el.innerHTML = `
                <div class="etm-item-title">
                    <strong>${escapeHtml(title)}</strong>
                    <span class="etm-pill etm-pill--cat" style="background:${st.bg};border-color:${st.border};color:${st.text}">${escapeHtml(formatCategoryLabel(cat))}${t.is_html ? ' · HTML' : ''}</span>
                </div>
                ${subj ? `<div class="etm-item-subject">${escapeHtml(subj)}</div>` : ''}
                <div class="etm-item-meta">
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
            id: '',
            name: (nameInput.value || '').trim(),
            category: (categoryInput.value || 'cold_email').trim(),
            subject: (subjectInput.value || '').trim(),
            content: contentInput.value || '',
            is_html: !!isHtmlInput.checked
        };
    }

    function setEditorData(tpl) {
        const t = tpl ? normalize(tpl) : null;
        if (idInput) {
            idInput.value = t?.id || '';
        }
        nameInput.value = t?.name || '';
        const cat = t ? (displayCategory(t) || t.category || 'cold_email') : 'cold_email';
        categoryInput.value = cat;
        subjectInput.value = t?.subject || '';
        contentInput.value = t?.content || '';
        isHtmlInput.checked = !!t?.is_html || cat === 'html_email';
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

    function applySavedTemplate(saved) {
        if (!saved || !saved.id) return;
        const idx = templates.findIndex(t => t.id === saved.id);
        const normalized = normalize(saved);
        if (idx >= 0) {
            templates[idx] = normalized;
        } else {
            templates.push(normalized);
        }
        activeId = saved.id;
        setEditorData(normalized);
        refreshCategorySelectors();
        renderList();
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
                        content: data.content,
                        is_html: data.is_html
                    })
                });
                const payload = await res.json();
                if (!res.ok) throw new Error(payload?.error || 'Erreur sauvegarde');
                templateId = payload.template?.id || activeId;
                if (payload.template) {
                    applySavedTemplate(payload.template);
                } else {
                    await loadTemplates();
                    selectTemplate(templateId);
                }
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
                        content: data.content,
                        is_html: data.is_html
                    })
                });
                const payload = await res.json();
                if (!res.ok) throw new Error(payload?.error || 'Erreur création');
                templateId = payload.template?.id || templateId;
                if (payload.template) {
                    applySavedTemplate(payload.template);
                } else {
                    await loadTemplates();
                    selectTemplate(templateId);
                }
            }

            if (!templates.find(t => t.id === templateId)) {
                await loadTemplates();
                selectTemplate(templateId);
            }
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
        // Ancienne méthode via prompt : on ouvre désormais le panneau dédié
        if (!importPanel) return;
        if (!importPanelOpen) {
            toggleImportPanel();
        }
        toast('Colle ton JSON dans la zone dédiée ci-dessous.');
    }

    async function applyImportState() {
        if (!importState || !Array.isArray(importState.items) || !importState.items.length) {
            toast('Rien à importer. Analyse d\'abord ton JSON.');
            return;
        }

        importApplyBtn && (importApplyBtn.disabled = true);
        setBadge('Importation...', 'warn');

        const existingIds = new Set(templates.map(t => t.id));
        let created = 0;
        let updated = 0;
        let errors = 0;

        for (const t of importState.items) {
            const hasId = !!(t.id && String(t.id).trim());
            const body = {
                name: t.name || t.id || 'Template importé',
                category: t.category || (t.is_html ? 'html_email' : 'cold_email'),
                subject: t.subject || '',
                content: t.content || ''
            };

            try {
                let res;
                if (hasId && existingIds.has(t.id)) {
                    // Mise à jour des modèles existants (doublons d'ID)
                    res = await fetch(`/api/templates/${encodeURIComponent(t.id)}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body)
                    });
                    if (res.ok) updated += 1;
                    else errors += 1;
                } else {
                    // Création (on passe l'ID si fourni pour le conserver)
                    const createBody = { ...body, id: hasId ? String(t.id).trim() : undefined };
                    res = await fetch('/api/templates', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(createBody)
                    });
                    if (res.ok) created += 1;
                    else errors += 1;
                }
            } catch (_e) {
                errors += 1;
            }
        }

        await loadTemplates();

        const total = importState.items.length;
        const summary = `Import terminé : ${created} créés, ${updated} mis à jour, ${errors} erreurs sur ${total}.`;
        toast(summary);
        const htmlSummary = `
            <div class="etm-import-success">
                ${summary}
            </div>
        `;
        setImportResult(htmlSummary, errors ? 'warn' : 'ok');
        setBadge('Prêt', 'ok');
        importState = null;
        if (importApplyBtn) {
            importApplyBtn.disabled = true;
        }
    }

    function parseImportFromTextarea() {
        if (!importTextInput) {
            toast('Zone d\'import introuvable.');
            return;
        }
        const raw = (importTextInput.value || '').trim();
        if (!raw) {
            toast('Colle un JSON dans la zone prévue.');
            return;
        }

        let parsed;
        try {
            parsed = JSON.parse(raw);
        } catch (e) {
            setImportResult(`<div class="etm-import-error">JSON invalide : ${String(e.message || e)}</div>`, 'error');
            importState = null;
            if (importApplyBtn) importApplyBtn.disabled = true;
            return;
        }

        const items = Array.isArray(parsed) ? parsed : (parsed && Array.isArray(parsed.templates) ? parsed.templates : []);
        if (!Array.isArray(items) || !items.length) {
            setImportResult('<div class="etm-import-warning">Aucun template trouvé dans ce JSON.</div>', 'warn');
            importState = null;
            if (importApplyBtn) importApplyBtn.disabled = true;
            return;
        }

        const existingIds = new Set(templates.map(t => t.id));
        const seenIds = new Set();
        const cleaned = [];
        const duplicateIds = new Set();
        const problems = [];

        items.forEach((t, index) => {
            const idx = index + 1;
            if (!t || typeof t !== 'object') {
                problems.push(`Entrée #${idx} : valeur non-objet, ignorée.`);
                return;
            }
            if (!t.content && !t.subject && !t.name && !t.id) {
                problems.push(`Entrée #${idx} : aucun champ utile (id, name, subject, content).`);
                return;
            }

            const rawId = (t.id || '').toString().trim();
            const hasId = !!rawId;

            if (hasId) {
                if (existingIds.has(rawId) || seenIds.has(rawId)) {
                    duplicateIds.add(rawId);
                }
                seenIds.add(rawId);
            }

            cleaned.push({
                id: hasId ? rawId : null,
                name: t.name || t.id || 'Template importé',
                category: t.category || (t.is_html ? 'html_email' : 'cold_email'),
                subject: t.subject || '',
                content: t.content || '',
                is_html: !!t.is_html || t.category === 'html_email'
            });
        });

        if (!cleaned.length) {
            setImportResult('<div class="etm-import-error">Aucun template exploitable après analyse.</div>', 'error');
            importState = null;
            if (importApplyBtn) importApplyBtn.disabled = true;
            return;
        }

        importState = {
            items: cleaned,
            duplicateIds: Array.from(duplicateIds),
            total: items.length
        };

        let html = `<div class="etm-import-success"><strong>${cleaned.length}</strong> modèle(s) prêts à être importés sur ${items.length} entrées.</div>`;
        if (duplicateIds.size) {
            html += `<div class="etm-import-warning">Doublons détectés sur les ID suivants : <code>${Array.from(duplicateIds).join(', ')}</code>.<br>Ces modèles seront <strong>mis à jour</strong> plutôt que recréés.</div>`;
        }
        if (problems.length) {
            html += `<ul class="etm-import-problems">${problems.map(p => `<li>${p}</li>`).join('')}</ul>`;
        }

        setImportResult(html, duplicateIds.size ? 'warn' : 'ok');
        if (importApplyBtn) {
            importApplyBtn.disabled = false;
        }
    }

    // Bind events
    newBtn.addEventListener('click', newTemplate);
    saveBtn.addEventListener('click', saveTemplate);
    deleteBtn.addEventListener('click', deleteTemplate);
    previewToggleBtn.addEventListener('click', togglePreview);
    importBtn.addEventListener('click', () => {
        toggleImportPanel();
    });

    if (importFileInput) {
        importFileInput.addEventListener('change', (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = () => {
                if (importTextInput) {
                    importTextInput.value = reader.result || '';
                }
                setImportResult(
                    `<div class="etm-import-info">Fichier <strong>${file.name}</strong> chargé (${file.size} octets). Clique sur "Analyser le JSON".</div>`,
                    'info'
                );
                importState = null;
                if (importApplyBtn) importApplyBtn.disabled = true;
            };
            reader.onerror = () => {
                setImportResult('<div class="etm-import-error">Erreur lors de la lecture du fichier.</div>', 'error');
            };
            reader.readAsText(file, 'utf-8');
        });
    }

    if (importParseBtn) {
        importParseBtn.addEventListener('click', parseImportFromTextarea);
    }

    if (importApplyBtn) {
        importApplyBtn.addEventListener('click', () => {
            applyImportState().catch(() => {
                setBadge('Erreur import', 'error');
                toast('Erreur lors de l\'import.');
            });
        });
    }

    [nameInput, categoryInput, subjectInput, contentInput, isHtmlInput].forEach(el => {
        if (!el) return;
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
    categoryFilter.addEventListener('change', () => {
        renderCategoryChips();
        renderList();
    });
    sortFilter.addEventListener('change', renderList);
    if (catChipsEl) {
        catChipsEl.addEventListener('click', (ev) => {
            const btn = ev.target.closest('.etm-cat-chip');
            if (!btn || !categoryFilter) return;
            const cat = btn.getAttribute('data-cat') || '';
            categoryFilter.value = cat;
            renderCategoryChips();
            renderList();
        });
    }
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

