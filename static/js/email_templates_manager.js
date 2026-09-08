// UI - Gestion des templates email (BDD via /api/templates)
// Layout type galerie maquettes : onglets Modèles / Paramètres / Contenu + preview live.

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
    const badgeEl = $('#etm-status-badge');
    const toastEl = $('#etm-toast');

    const nameInput = $('#etm-name');
    const categoryInput = $('#etm-category-edit');
    const subjectInput = $('#etm-subject');
    const contentInput = $('#etm-content');
    const isHtmlInput = $('#etm-is-html');

    const previewIframe = $('#etm-preview-iframe');
    const previewText = $('#etm-preview-text');
    const previewTitle = $('#etm-preview-title');
    const previewStatus = $('#etm-preview-status');
    const frameWrap = $('#etm-frame-wrap');
    const subjectLiveEl = $('#etm-subject-live');
    const metaChipsEl = $('#etm-meta-chips');
    const varsLiveEl = $('#etm-vars-live');

    const pNom = $('#etm-p-nom');
    const pEntreprise = $('#etm-p-entreprise');
    const pEmail = $('#etm-p-email');
    const pWebsite = $('#etm-p-website');
    const pSecteur = $('#etm-p-secteur');
    const paramsResetBtn = $('#etm-params-reset');
    const paramsRefreshBtn = $('#etm-params-refresh');

    const sideTabsEl = $('#etm-side-tabs');
    const panelModels = $('#etm-panel-models');
    const panelParams = $('#etm-panel-params');
    const tabModels = $('#etm-tab-models');
    const tabParams = $('#etm-tab-params');

    const previewRenderEl = $('#etm-preview-render');
    const sourceEditorEl = $('#etm-source-editor');
    const previewEditHint = $('#etm-preview-edit-hint');
    const modeRenderBtn = $('#etm-mode-render');
    const modeSourceBtn = $('#etm-mode-source');

    const chips = Array.from(document.querySelectorAll('.etm-chip'));
    const catChipsEl = $('#etm-cat-chips');

    const PREVIEW_DEFAULTS = {
        nom: 'Claire',
        entreprise: 'Atelier Nord-Est',
        email: 'claire@atelier-nord.fr',
        website: 'atelier-nord.fr',
        secteur: 'Commerce',
    };

    const CORE_CATEGORIES = [
        'audit', 'offres', 'echantillons', 'bouquins',
        'cold_email', 'html_email', 'linkedin', 'malt', 'other',
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

    const CATEGORY_STYLES = {
        audit: { bg: 'rgba(37, 99, 235, 0.12)', border: 'rgba(37, 99, 235, 0.35)', text: '#1d4ed8' },
        offres: { bg: 'rgba(22, 163, 74, 0.12)', border: 'rgba(22, 163, 74, 0.35)', text: '#15803d' },
        echantillons: { bg: 'rgba(147, 51, 234, 0.12)', border: 'rgba(147, 51, 234, 0.35)', text: '#7e22ce' },
        bouquins: { bg: 'rgba(234, 88, 12, 0.12)', border: 'rgba(234, 88, 12, 0.35)', text: '#c2410c' },
        html_email: { bg: 'rgba(100, 116, 139, 0.12)', border: 'rgba(100, 116, 139, 0.3)', text: '#475569' },
        cold_email: { bg: 'rgba(100, 116, 139, 0.12)', border: 'rgba(100, 116, 139, 0.3)', text: '#475569' },
        other: { bg: 'rgba(100, 116, 139, 0.1)', border: 'rgba(100, 116, 139, 0.25)', text: '#64748b' },
    };

    const importPanel = $('#etm-import-panel');
    const importFileInput = $('#etm-import-file');
    const importTextInput = $('#etm-import-text');
    const importParseBtn = $('#etm-import-parse-btn');
    const importApplyBtn = $('#etm-import-apply-btn');
    const importResultEl = $('#etm-import-result');

    let templates = [];
    let activeId = null;
    let dirty = false;
    let importState = null;
    let importPanelOpen = false;
    let renderTimer = null;
    let previewRequestId = 0;
    let previewMode = 'render';
    let visualEditActive = false;
    let visualEditSyncTimer = null;

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

    function formatCategoryLabel(value) {
        const v = (value || '').trim();
        if (!v) return '';
        if (CATEGORY_LABELS[v]) return CATEGORY_LABELS[v];
        const cleaned = v.replace(/_/g, ' ');
        return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
    }

    function templateAngle(t) {
        const subj = (t.subject || '').trim().replace(/^objet:\s*/i, '');
        if (subj) {
            return subj.length > 72 ? `${subj.slice(0, 69)}…` : subj;
        }
        return formatCategoryLabel(displayCategory(t));
    }

    function setBadge(text, kind) {
        if (!badgeEl) return;
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
            window.setTimeout(() => { toastEl.hidden = true; }, 220);
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
        importPanel.classList.toggle('etm-import-panel--open', importPanelOpen);
        importBtn.classList.toggle('btn-active', importPanelOpen);
        importBtn.setAttribute('aria-pressed', importPanelOpen ? 'true' : 'false');
        if (importPanelOpen) {
            importPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            if (importTextInput) setTimeout(() => importTextInput.focus(), 260);
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
            `<button type="button" class="etm-cat-chip etm-cat-chip--all${current === '' ? ' is-active' : ''}" data-cat="" role="tab">Toutes <span class="etm-cat-count">${templates.length}</span></button>`
        );
        cats.forEach(c => {
            const n = counts[c] || 0;
            if (n === 0 && !CORE_CATEGORIES.slice(0, 4).includes(c)) return;
            const active = current === c;
            const st = categoryStyle(c);
            parts.push(
                `<button type="button" class="etm-cat-chip${active ? ' is-active' : ''}" data-cat="${escapeHtml(c)}" role="tab" style="--chip-bg:${st.bg};--chip-border:${st.border};--chip-text:${st.text}">${escapeHtml(formatCategoryLabel(c))} <span class="etm-cat-count">${n}</span></button>`
            );
        });
        catChipsEl.innerHTML = parts.join('');
    }

    function refreshCategorySelectors() {
        const cats = getDistinctCategories();
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
            if (current && cats.includes(current)) categoryFilter.value = current;
            else if (current) categoryFilter.value = '';
        }
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
            scheduleRenderPreview(true);
        }
    }

    function filteredTemplates() {
        const q = (searchInput?.value || '').trim().toLowerCase();
        const cat = categoryFilter?.value || '';
        let items = templates.slice();
        if (cat) items = items.filter(t => displayCategory(t) === cat);
        if (q) {
            items = items.filter(t => {
                const hay = `${t.name || ''} ${t.subject || ''}`.toLowerCase();
                return hay.includes(q);
            });
        }
        const sort = sortFilter?.value || 'updated_desc';
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
            listEl.innerHTML = '<div class="etm-tpl etm-tpl--empty"><strong>Aucun modèle</strong><span class="etm-tpl-angle">Ajuste le filtre ou crée un nouveau modèle.</span></div>';
            return;
        }
        items.forEach(t => {
            const cat = displayCategory(t);
            const title = (t.name || '').trim() || 'Sans nom';
            const row = document.createElement('div');
            row.className = 'etm-tpl-row' + (t.id === activeId ? ' is-active' : '');

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'etm-tpl' + (t.id === activeId ? ' is-active' : '');
            btn.innerHTML = `
                <strong>${escapeHtml(title)}</strong>
                <span class="etm-tpl-angle">${escapeHtml(templateAngle(t))}</span>
                <span class="etm-tpl-badge">${escapeHtml(formatCategoryLabel(cat))}</span>
            `;
            btn.addEventListener('click', () => selectTemplate(t.id));

            const actions = document.createElement('div');
            actions.className = 'etm-tpl-actions';

            const editBtn = document.createElement('button');
            editBtn.type = 'button';
            editBtn.className = 'etm-tpl-action etm-tpl-action--edit';
            editBtn.title = 'Modifier le contenu';
            editBtn.setAttribute('aria-label', 'Modifier le contenu');
            editBtn.innerHTML = '<i class="fa-solid fa-pen" aria-hidden="true"></i>';
            editBtn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                openContentEditor(t.id, 'source');
            });

            const delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.className = 'etm-tpl-action etm-tpl-action--delete';
            delBtn.title = 'Supprimer';
            delBtn.setAttribute('aria-label', 'Supprimer');
            delBtn.innerHTML = '<i class="fa-regular fa-trash-can" aria-hidden="true"></i>';
            delBtn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                deleteTemplate(t.id);
            });

            actions.appendChild(editBtn);
            actions.appendChild(delBtn);
            row.appendChild(btn);
            row.appendChild(actions);
            listEl.appendChild(row);
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

    function previewParams() {
        return {
            nom: (pNom?.value || '').trim() || PREVIEW_DEFAULTS.nom,
            entreprise: (pEntreprise?.value || '').trim() || PREVIEW_DEFAULTS.entreprise,
            email: (pEmail?.value || '').trim() || PREVIEW_DEFAULTS.email,
            website: (pWebsite?.value || '').trim() || PREVIEW_DEFAULTS.website,
            secteur: (pSecteur?.value || '').trim() || PREVIEW_DEFAULTS.secteur,
        };
    }

    function resetPreviewParams() {
        if (pNom) pNom.value = PREVIEW_DEFAULTS.nom;
        if (pEntreprise) pEntreprise.value = PREVIEW_DEFAULTS.entreprise;
        if (pEmail) pEmail.value = PREVIEW_DEFAULTS.email;
        if (pWebsite) pWebsite.value = PREVIEW_DEFAULTS.website;
        if (pSecteur) pSecteur.value = PREVIEW_DEFAULTS.secteur;
        scheduleRenderPreview(false);
    }

    function currentEditorData() {
        return {
            id: '',
            name: (nameInput?.value || '').trim(),
            category: (categoryInput?.value || 'cold_email').trim(),
            subject: (subjectInput?.value || '').trim(),
            content: contentInput?.value || '',
            is_html: !!isHtmlInput?.checked,
        };
    }

    function setEditorData(tpl) {
        const t = tpl ? normalize(tpl) : null;
        disableVisualEdit();
        if (nameInput) nameInput.value = t?.name || '';
        const cat = t ? (displayCategory(t) || t.category || 'cold_email') : 'cold_email';
        if (categoryInput) categoryInput.value = cat;
        if (subjectInput) subjectInput.value = t?.subject || '';
        if (contentInput) contentInput.value = t?.content || '';
        if (isHtmlInput) isHtmlInput.checked = !!t?.is_html || cat === 'html_email';
        dirty = false;
        refreshEditorButtons();
        updatePreviewTitle();
        if (previewMode === 'render') scheduleRenderPreview(true);
    }

    function updatePreviewTitle() {
        if (!previewTitle) return;
        const data = currentEditorData();
        const cat = formatCategoryLabel(data.category);
        const name = data.name || 'Nouveau modèle';
        previewTitle.textContent = `${name} · ${cat}`;
    }

    function refreshEditorButtons() {
        const hasActive = !!activeId;
        if (saveBtn) {
            saveBtn.disabled = !dirty || !(nameInput?.value || '').trim() || !(contentInput?.value || '').trim();
        }
        if (deleteBtn) deleteBtn.disabled = !hasActive;
        setBadge(dirty ? 'Modifié' : 'Prêt', dirty ? 'warn' : 'ok');
    }

    function markDirty() {
        dirty = true;
        refreshEditorButtons();
        updatePreviewTitle();
        if (previewMode === 'render' && !visualEditActive) {
            scheduleRenderPreview(false);
        }
    }

    function selectTemplate(templateId, afterSelect) {
        if (dirty && templateId !== activeId) {
            const ok = window.confirm('Tu as des modifications non enregistrées. Continuer quand même ?');
            if (!ok) return;
        }
        activeId = templateId;
        const tpl = templates.find(t => t.id === templateId);
        disableVisualEdit();
        setEditorData(tpl);
        renderList();
        if (typeof afterSelect === 'function') afterSelect();
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
            is_html: true,
        });
        renderList();
        setSideTab('params');
        setPreviewMode('source');
        if (nameInput) nameInput.focus();
    }

    function applySavedTemplate(saved) {
        if (!saved || !saved.id) return;
        const idx = templates.findIndex(t => t.id === saved.id);
        const normalized = normalize(saved);
        if (idx >= 0) templates[idx] = normalized;
        else templates.push(normalized);
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
        let templateId = activeId;
        try {
            if (saveBtn) saveBtn.disabled = true;
            setBadge('Enregistrement...', 'warn');
            let payload;
            if (isUpdate) {
                const res = await fetch(`/api/templates/${encodeURIComponent(activeId)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: data.name,
                        category: data.category,
                        subject: data.subject,
                        content: data.content,
                        is_html: data.is_html,
                    }),
                });
                payload = await res.json();
                if (!res.ok) throw new Error(payload?.error || 'Erreur sauvegarde');
                templateId = payload.template?.id || activeId;
            } else {
                const res = await fetch('/api/templates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: data.name,
                        category: data.category,
                        subject: data.subject,
                        content: data.content,
                        is_html: data.is_html,
                    }),
                });
                payload = await res.json();
                if (!res.ok) throw new Error(payload?.error || 'Erreur création');
                templateId = payload.template?.id || templateId;
            }
            if (payload.template) applySavedTemplate(payload.template);
            else {
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

    async function deleteTemplate(templateId) {
        const id = templateId || activeId;
        if (!id) return;
        const tpl = templates.find(t => t.id === id);
        const label = (tpl?.name || '').trim() || id;
        const ok = window.confirm(`Supprimer le modèle « ${label} » ?`);
        if (!ok) return;
        try {
            setBadge('Suppression...', 'warn');
            const res = await fetch(`/api/templates/${encodeURIComponent(id)}`, { method: 'DELETE' });
            const payload = await res.json();
            if (!res.ok) throw new Error(payload?.error || 'Erreur suppression');
            toast('Supprimé.');
            if (activeId === id) activeId = null;
            await loadTemplates();
            if (templates.length) selectTemplate(templates[0].id);
            else newTemplate();
        } catch (e) {
            setBadge('Erreur', 'error');
            toast(e.message || 'Erreur');
        } finally {
            refreshEditorButtons();
        }
    }

    function setSideTab(tab) {
        const key = tab === 'params' ? 'params' : 'models';
        if (sideTabsEl) sideTabsEl.dataset.active = key;
        const isModels = key === 'models';
        const isParams = key === 'params';
        [tabModels, tabParams].forEach((el, i) => {
            if (!el) return;
            const active = (i === 0 && isModels) || (i === 1 && isParams);
            el.classList.toggle('is-active', active);
            el.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        [panelModels, panelParams].forEach((el, i) => {
            if (!el) return;
            const active = (i === 0 && isModels) || (i === 1 && isParams);
            el.classList.toggle('is-active', active);
        });
    }

    /**
     * Bascule entre aperçu rendu et éditeur code source.
     * @param {'render'|'source'} mode
     */
    function setPreviewMode(mode) {
        const next = mode === 'source' ? 'source' : 'render';
        previewMode = next;
        visualEditActive = false;
        if (previewRenderEl) previewRenderEl.hidden = next === 'source';
        if (sourceEditorEl) sourceEditorEl.hidden = next !== 'source';
        if (previewEditHint) previewEditHint.hidden = next !== 'render';
        document.querySelectorAll('[data-preview-mode]').forEach(btn => {
            btn.classList.toggle('is-active', btn.getAttribute('data-preview-mode') === next);
        });
        if (frameWrap) {
            frameWrap.classList.toggle('etm-frame-wrap--source', next === 'source');
            frameWrap.classList.toggle('etm-frame-wrap--visual-edit', false);
        }
        if (next === 'source' && contentInput) {
            contentInput.focus();
        } else {
            scheduleRenderPreview(true);
        }
        updatePreviewStatusLabel();
    }

    function updatePreviewStatusLabel() {
        if (!previewStatus) return;
        if (previewMode === 'source') {
            previewStatus.textContent = 'Mode code source · modifie le HTML directement';
            previewStatus.classList.remove('is-error');
        } else if (visualEditActive) {
            previewStatus.textContent = 'Édition visuelle · les variables {nom} sont conservées';
        }
    }

    /**
     * Ouvre l'éditeur de contenu pour un modèle (depuis l'icône crayon).
     * @param {string} templateId
     * @param {'source'|'render'} [mode='source']
     */
    function openContentEditor(templateId, mode) {
        const open = () => {
            setPreviewMode(mode || 'source');
            if (contentInput) contentInput.focus();
        };
        if (templateId !== activeId) {
            selectTemplate(templateId, open);
            return;
        }
        open();
    }

    /**
     * Remplace le contenu du body dans un document HTML complet.
     * @param {string} html
     * @param {string} newBodyInner
     * @returns {string}
     */
    function replaceBodyInHtml(html, newBodyInner) {
        const source = String(html || '');
        if (!source.trim()) return newBodyInner || '';
        if (/<body[\s>]/i.test(source)) {
            return source.replace(/<body([^>]*)>[\s\S]*<\/body>/i, `<body$1>${newBodyInner}</body>`);
        }
        return newBodyInner || source;
    }

    function disableVisualEdit() {
        visualEditActive = false;
        if (frameWrap) frameWrap.classList.remove('etm-frame-wrap--visual-edit');
        if (previewEditHint) previewEditHint.hidden = previewMode !== 'render';
        updatePreviewStatusLabel();
    }

    /**
     * Synchronise le body édité vers le textarea (HTML brut).
     */
    function syncVisualEditToContent() {
        if (!visualEditActive || !previewIframe || !contentInput) return;
        try {
            const doc = previewIframe.contentDocument;
            if (!doc || !doc.body) return;
            const bodyHtml = doc.body.innerHTML;
            const updated = replaceBodyInHtml(contentInput.value, bodyHtml);
            if (updated !== contentInput.value) {
                contentInput.value = updated;
                dirty = true;
                refreshEditorButtons();
                updatePreviewTitle();
            }
        } catch (_e) {
            /* ignore cross-origin / doc détruit */
        }
    }

    /**
     * Active l'édition visuelle dans l'iframe (modèle brut, pas le rendu API).
     */
    function enableVisualEdit() {
        if (!previewIframe || !contentInput) return;
        const raw = contentInput.value || '';
        if (!raw.trim()) {
            toast('Aucun contenu à modifier.');
            return;
        }
        visualEditActive = true;
        if (frameWrap) frameWrap.classList.add('etm-frame-wrap--visual-edit');
        if (previewEditHint) previewEditHint.hidden = true;
        updatePreviewStatusLabel();

        previewIframe.onload = () => {
            try {
                const doc = previewIframe.contentDocument;
                if (!doc || !doc.body) return;
                doc.body.contentEditable = 'true';
                doc.body.setAttribute('data-etm-editing', '1');
                doc.body.focus();

                // Rebind à chaque srcdoc : l'ancien contentDocument est détruit.
                doc.addEventListener('input', () => {
                    clearTimeout(visualEditSyncTimer);
                    visualEditSyncTimer = window.setTimeout(syncVisualEditToContent, 350);
                });
            } catch (_e) {
                toast('Édition visuelle indisponible pour ce modèle.');
                disableVisualEdit();
                scheduleRenderPreview(true);
            }
        };
        previewIframe.srcdoc = raw;
    }

    /**
     * Clic zone aperçu : l'édition visuelle ne part que via le bouton hint
     * (un clic direct sur l'iframe cassait le rendu live / includes).
     * @param {MouseEvent} ev
     */
    function handlePreviewAreaClick(ev) {
        if (previewMode !== 'render' || visualEditActive) return;
        if (!contentInput || !(contentInput.value || '').trim()) return;
        if (ev.target.closest('.etm-preview-edit-hint')) {
            enableVisualEdit();
        }
    }

    function updateMetaChips(cat) {
        if (!metaChipsEl) return;
        const label = formatCategoryLabel(cat);
        metaChipsEl.innerHTML = label
            ? `<span class="etm-meta-chip">${escapeHtml(label)}</span>`
            : '';
    }

    async function renderLivePreview() {
        if (previewMode === 'source') {
            if (previewStatus) {
                previewStatus.textContent = 'Mode code source · modifie le HTML directement';
                previewStatus.classList.remove('is-error');
            }
            return;
        }
        if (visualEditActive) return;

        const reqId = ++previewRequestId;
        const data = currentEditorData();
        const params = previewParams();

        if (previewStatus) {
            previewStatus.textContent = 'Rendu…';
            previewStatus.classList.remove('is-error');
        }

        if (!data.content && !activeId) {
            if (previewIframe) previewIframe.srcdoc = '<p style="font-family:sans-serif;padding:24px;color:#64748b">Sélectionne un modèle ou saisis du contenu.</p>';
            if (subjectLiveEl) subjectLiveEl.textContent = '—';
            if (varsLiveEl) varsLiveEl.innerHTML = '';
            if (previewStatus) previewStatus.textContent = 'Aucun contenu';
            return;
        }

        try {
            const res = await fetch('/api/templates/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    template_id: activeId || undefined,
                    content: data.content,
                    subject: data.subject,
                    ...params,
                }),
            });
            const payload = await res.json();
            if (reqId !== previewRequestId) return;
            if (!res.ok) throw new Error(payload?.error || 'Erreur preview');

            const isHtml = !!payload.is_html;
            if (isHtml) {
                if (previewText) previewText.hidden = true;
                if (previewIframe) {
                    previewIframe.hidden = false;
                    let html = payload.content || '';
                    html = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
                    previewIframe.srcdoc = html;
                }
            } else {
                if (previewIframe) previewIframe.hidden = true;
                if (previewText) {
                    previewText.hidden = false;
                    previewText.textContent = payload.content || '';
                }
            }

            if (subjectLiveEl) subjectLiveEl.textContent = payload.subject || '—';
            updateMetaChips(data.category);

            const vars = payload.variables || {};
            if (varsLiveEl) {
                varsLiveEl.innerHTML =
                    '<strong>Variables live</strong><br>' +
                    `{secteur_label} = ${escapeHtml(vars.secteur_label || '')}<br>` +
                    `{echantillon_slug} = ${escapeHtml(vars.echantillon_slug || '')}<br>` +
                    `{secteur_accroche} = ${escapeHtml(vars.secteur_accroche || '')}`;
            }
            if (previewStatus) previewStatus.textContent = 'OK · aperçu à jour';
            if (previewEditHint && isHtml && (data.content || '').trim()) {
                previewEditHint.hidden = false;
            }
        } catch (e) {
            if (reqId !== previewRequestId) return;
            if (previewStatus) {
                previewStatus.textContent = e.message || 'Erreur preview';
                previewStatus.classList.add('is-error');
            }
        }
    }

    function scheduleRenderPreview(force) {
        clearTimeout(renderTimer);
        renderTimer = window.setTimeout(() => renderLivePreview(), force ? 40 : 220);
    }

    function insertAtCursor(textarea, text) {
        if (!textarea) return;
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

    async function applyImportState() {
        if (!importState || !Array.isArray(importState.items) || !importState.items.length) {
            toast('Rien à importer. Analyse d\'abord ton JSON.');
            return;
        }
        if (importApplyBtn) importApplyBtn.disabled = true;
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
                content: t.content || '',
            };
            try {
                let res;
                if (hasId && existingIds.has(t.id)) {
                    res = await fetch(`/api/templates/${encodeURIComponent(t.id)}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body),
                    });
                    if (res.ok) updated += 1;
                    else errors += 1;
                } else {
                    const createBody = { ...body, id: hasId ? String(t.id).trim() : undefined };
                    res = await fetch('/api/templates', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(createBody),
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
        setImportResult(`<div class="etm-import-success">${summary}</div>`, errors ? 'warn' : 'ok');
        setBadge('Prêt', 'ok');
        importState = null;
        if (importApplyBtn) importApplyBtn.disabled = true;
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
        const items = Array.isArray(parsed) ? parsed : (parsed?.templates || []);
        if (!Array.isArray(items) || !items.length) {
            setImportResult('<div class="etm-import-warning">Aucun template trouvé.</div>', 'warn');
            importState = null;
            if (importApplyBtn) importApplyBtn.disabled = true;
            return;
        }
        const existingIds = new Set(templates.map(t => t.id));
        const seenIds = new Set();
        const cleaned = [];
        const duplicateIds = new Set();
        items.forEach((t) => {
            if (!t || typeof t !== 'object') return;
            const rawId = (t.id || '').toString().trim();
            if (rawId) {
                if (existingIds.has(rawId) || seenIds.has(rawId)) duplicateIds.add(rawId);
                seenIds.add(rawId);
            }
            cleaned.push({
                id: rawId || null,
                name: t.name || rawId || 'Template importé',
                category: t.category || (t.is_html ? 'html_email' : 'cold_email'),
                subject: t.subject || '',
                content: t.content || '',
                is_html: !!t.is_html || t.category === 'html_email',
            });
        });
        importState = { items: cleaned };
        setImportResult(`<div class="etm-import-success"><strong>${cleaned.length}</strong> modèle(s) prêts.</div>`, duplicateIds.size ? 'warn' : 'ok');
        if (importApplyBtn) importApplyBtn.disabled = false;
    }

    // Events
    if (newBtn) newBtn.addEventListener('click', newTemplate);
    if (saveBtn) saveBtn.addEventListener('click', saveTemplate);
    if (deleteBtn) deleteBtn.addEventListener('click', deleteTemplate);
    if (importBtn) importBtn.addEventListener('click', toggleImportPanel);
    if (paramsResetBtn) paramsResetBtn.addEventListener('click', resetPreviewParams);
    if (paramsRefreshBtn) paramsRefreshBtn.addEventListener('click', () => scheduleRenderPreview(true));

    [pNom, pEntreprise, pEmail, pWebsite, pSecteur].forEach(el => {
        if (!el) return;
        el.addEventListener('input', () => scheduleRenderPreview(false));
        el.addEventListener('change', () => scheduleRenderPreview(false));
    });

    [nameInput, categoryInput, subjectInput, contentInput, isHtmlInput].forEach(el => {
        if (!el) return;
        el.addEventListener('input', () => {
            markDirty();
            if (el === categoryInput && categoryInput.value === 'html_email' && isHtmlInput) {
                isHtmlInput.checked = true;
            }
        });
        el.addEventListener('change', markDirty);
    });

    chips.forEach(ch => {
        ch.addEventListener('click', () => {
            insertAtCursor(contentInput, ch.getAttribute('data-insert') || '');
            markDirty();
        });
    });

    if (searchInput) searchInput.addEventListener('input', renderList);
    if (categoryFilter) {
        categoryFilter.addEventListener('change', () => {
            renderCategoryChips();
            renderList();
        });
    }
    if (sortFilter) sortFilter.addEventListener('change', renderList);
    if (catChipsEl) {
        catChipsEl.addEventListener('click', (ev) => {
            const btn = ev.target.closest('.etm-cat-chip');
            if (!btn || !categoryFilter) return;
            categoryFilter.value = btn.getAttribute('data-cat') || '';
            renderCategoryChips();
            renderList();
        });
    }
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            renderList();
            searchInput.focus();
        });
    }

    [tabModels, tabParams].forEach(btn => {
        if (!btn) return;
        btn.addEventListener('click', () => setSideTab(btn.dataset.tab || 'models'));
    });

    document.querySelectorAll('[data-preview-mode]').forEach(btn => {
        btn.addEventListener('click', () => {
            setPreviewMode(btn.getAttribute('data-preview-mode') || 'render');
        });
    });

    if (previewRenderEl) {
        previewRenderEl.addEventListener('click', handlePreviewAreaClick);
    }
    if (previewEditHint) {
        previewEditHint.addEventListener('click', (ev) => {
            ev.preventDefault();
            enableVisualEdit();
        });
    }

    document.querySelectorAll('.etm-seg--width button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.etm-seg--width button').forEach(b => b.classList.remove('is-active'));
            btn.classList.add('is-active');
            if (frameWrap) frameWrap.classList.toggle('is-mobile', btn.dataset.width === 'mobile');
        });
    });

    if (importFileInput) {
        importFileInput.addEventListener('change', (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = () => {
                if (importTextInput) importTextInput.value = reader.result || '';
                setImportResult(`<div class="etm-import-info">Fichier <strong>${escapeHtml(file.name)}</strong> chargé.</div>`, 'info');
                importState = null;
                if (importApplyBtn) importApplyBtn.disabled = true;
            };
            reader.readAsText(file, 'utf-8');
        });
    }
    if (importParseBtn) importParseBtn.addEventListener('click', parseImportFromTextarea);
    if (importApplyBtn) {
        importApplyBtn.addEventListener('click', () => {
            applyImportState().catch(() => {
                setBadge('Erreur import', 'error');
                toast('Erreur lors de l\'import.');
            });
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && visualEditActive) {
            disableVisualEdit();
            scheduleRenderPreview(true);
        }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            e.preventDefault();
            if (saveBtn && !saveBtn.disabled) saveTemplate();
        }
    });

    loadTemplates().then(() => {
        setPreviewMode('render');
    }).catch(() => {
        setBadge('Erreur chargement', 'error');
        toast('Impossible de charger les templates.');
    });
})();
