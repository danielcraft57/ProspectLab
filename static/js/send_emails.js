/**
 * Poste d'envoi rapide (/send-emails)
 * Composer, aperçu live, historique, KPI et panneau détail (timeline).
 */
(function () {
    'use strict';

    /** @type {{email: string, nom: string, entreprise: string}[]} */
    let recipients = [];
    let currentDays = 7;
    let currentFilter = 'all';
    let previewTimer = null;
    let historyPollTimer = null;
    let selectedEmailId = null;

    /**
     * Échappe le HTML pour éviter les injections XSS dans le DOM.
     * @param {unknown} value
     * @returns {string}
     */
    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /**
     * Affiche une date relative courte (ex: "il y a 12 min").
     * @param {string|null|undefined} dateStr
     * @returns {string}
     */
    function formatRelativeDate(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        if (Number.isNaN(date.getTime())) return String(dateStr);
        const diffMs = Date.now() - date.getTime();
        const mins = Math.floor(diffMs / 60000);
        if (mins < 1) return "à l'instant";
        if (mins < 60) return 'il y a ' + mins + ' min';
        const hours = Math.floor(mins / 60);
        if (hours < 24) return 'il y a ' + hours + ' h';
        const days = Math.floor(hours / 24);
        if (days < 7) return 'il y a ' + days + ' j';
        return date.toLocaleString('fr-FR', {
            day: '2-digit',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * Formate une date complète pour la timeline.
     * @param {string|null|undefined} dateStr
     * @returns {string}
     */
    function formatDateTime(dateStr) {
        if (!dateStr) return 'Pas encore';
        const date = new Date(dateStr);
        if (Number.isNaN(date.getTime())) return String(dateStr);
        return date.toLocaleString('fr-FR', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * Met à jour le compteur de destinataires.
     * @returns {void}
     */
    function updateRecipientsCount() {
        const el = document.getElementById('recipients-count');
        if (!el) return;
        const n = recipients.length;
        el.textContent = n + (n > 1 ? ' destinataires' : ' destinataire');
    }

    /**
     * Affiche les chips destinataires.
     * @returns {void}
     */
    function renderRecipients() {
        const box = document.getElementById('recipients-chips');
        if (!box) return;
        if (!recipients.length) {
            box.innerHTML = '';
            updateRecipientsCount();
            return;
        }
        box.innerHTML = recipients.map(function (r, idx) {
            const label = r.nom ? escapeHtml(r.nom) + ' <small>&lt;' + escapeHtml(r.email) + '&gt;</small>' : escapeHtml(r.email);
            return (
                '<span class="recipient-chip" data-idx="' + idx + '">' +
                    '<span>' + label + '</span>' +
                    '<button type="button" data-remove="' + idx + '" aria-label="Retirer">&times;</button>' +
                '</span>'
            );
        }).join('');
        updateRecipientsCount();
        schedulePreview();
    }

    /**
     * Ajoute un destinataire s'il est valide et pas déjà présent.
     * @param {{email?: string, nom?: string, entreprise?: string}} raw
     * @returns {boolean}
     */
    function addRecipient(raw) {
        const email = String(raw.email || '').trim().toLowerCase();
        if (!email || email.indexOf('@') < 1) return false;
        if (recipients.some(function (r) { return r.email.toLowerCase() === email; })) return false;
        recipients.push({
            email: email,
            nom: String(raw.nom || '').trim(),
            entreprise: String(raw.entreprise || '').trim()
        });
        return true;
    }

    /**
     * Parse une liste collée (lignes email[,nom[,entreprise]]).
     * @param {string} text
     * @returns {number} Nombre ajouté
     */
    function parsePasteList(text) {
        let added = 0;
        String(text || '').split(/\r?\n/).forEach(function (line) {
            const trimmed = line.trim();
            if (!trimmed) return;
            const parts = trimmed.split(/[;,|\t]/).map(function (p) { return p.trim(); });
            if (addRecipient({ email: parts[0], nom: parts[1] || '', entreprise: parts[2] || '' })) {
                added += 1;
            }
        });
        return added;
    }

    /**
     * Insère une variable dans un champ texte à la position du curseur.
     * @param {string} targetId
     * @param {string} variable
     * @returns {void}
     */
    function insertVariable(targetId, variable) {
        const el = document.getElementById(targetId);
        if (!el) return;
        const start = el.selectionStart || 0;
        const end = el.selectionEnd || 0;
        const value = el.value || '';
        el.value = value.slice(0, start) + variable + value.slice(end);
        el.focus();
        const pos = start + variable.length;
        el.setSelectionRange(pos, pos);
        schedulePreview();
    }

    /**
     * Anime un KPI quand la valeur change.
     * @param {string} id
     * @param {number|string} value
     * @returns {void}
     */
    function setKpiValue(id, value) {
        const el = document.getElementById(id);
        if (!el) return;
        const next = String(value);
        if (el.textContent !== next) {
            el.textContent = next;
            el.classList.remove('is-bump');
            void el.offsetWidth;
            el.classList.add('is-bump');
        }
    }

    /**
     * Charge les KPI de la période courante.
     * @returns {Promise<void>}
     */
    async function loadStats() {
        try {
            const response = await fetch('/api/send-emails/stats?days=' + encodeURIComponent(String(currentDays)));
            const data = await response.json();
            if (!response.ok) return;
            setKpiValue('kpi-sent', data.total_sent || 0);
            setKpiValue('kpi-opened', data.total_opened || 0);
            setKpiValue('kpi-clicked', data.total_clicked || 0);
            setKpiValue('kpi-failed', data.total_failed || 0);
            const openRate = typeof data.open_rate === 'number' ? data.open_rate : 0;
            const clickRate = typeof data.click_rate === 'number' ? data.click_rate : 0;
            const openRateEl = document.getElementById('kpi-open-rate');
            const clickRateEl = document.getElementById('kpi-click-rate');
            if (openRateEl) openRateEl.textContent = openRate + '%';
            if (clickRateEl) clickRateEl.textContent = clickRate + '%';
            const openBar = document.getElementById('kpi-open-bar');
            const clickBar = document.getElementById('kpi-click-bar');
            if (openBar) openBar.style.width = Math.max(0, Math.min(100, openRate)) + '%';
            if (clickBar) clickBar.style.width = Math.max(0, Math.min(100, clickRate)) + '%';
        } catch (err) {
            // silencieux: la page reste utilisable sans KPI
        }
    }

    /**
     * Détermine le libellé / classe de statut pour une ligne d'historique.
     * @param {object} email
     * @returns {{label: string, cls: string}}
     */
    function resolveStatus(email) {
        if (!email) return { label: 'Inconnu', cls: 'sent' };
        if (email.statut === 'failed') return { label: 'Échec', cls: 'failed' };
        if (email.has_clicked || (email.clicks || 0) > 0) return { label: 'Cliqué', cls: 'clicked' };
        if (email.has_opened || (email.opens || 0) > 0) return { label: 'Ouvert', cls: 'opened' };
        return { label: 'Envoyé', cls: 'sent' };
    }

    /**
     * Charge et affiche l'historique filtré.
     * @returns {Promise<void>}
     */
    async function loadHistory() {
        const list = document.getElementById('history-list');
        if (!list) return;
        try {
            const url = '/api/send-emails/history?days=' + encodeURIComponent(String(currentDays)) +
                '&filter=' + encodeURIComponent(currentFilter) +
                '&limit=50';
            const response = await fetch(url);
            const data = await response.json();
            if (!response.ok) {
                list.innerHTML = '<div class="history-empty">Impossible de charger l\'historique</div>';
                return;
            }
            const emails = Array.isArray(data.emails) ? data.emails : [];
            if (!emails.length) {
                list.innerHTML = '<div class="history-empty">Aucun envoi rapide sur cette période. Compose ton premier email à gauche.</div>';
                return;
            }
            list.innerHTML = emails.map(function (email) {
                const status = resolveStatus(email);
                const active = selectedEmailId === email.id ? ' is-active' : '';
                return (
                    '<article class="history-item' + active + '" data-email-id="' + email.id + '" tabindex="0">' +
                        '<div class="history-item-top">' +
                            '<div>' +
                                '<div class="history-email">' + escapeHtml(email.email || '') + '</div>' +
                                '<div class="history-subject">' + escapeHtml(email.sujet || '(sans sujet)') + '</div>' +
                            '</div>' +
                            '<span class="status-pill ' + status.cls + '">' + status.label + '</span>' +
                        '</div>' +
                        '<div class="history-item-bottom">' +
                            '<div class="history-metrics">' +
                                '<span class="m-open">' + (email.opens || 0) + ' ouv.</span>' +
                                '<span class="m-click">' + (email.clicks || 0) + ' clic' + ((email.clicks || 0) > 1 ? 's' : '') + '</span>' +
                            '</div>' +
                            '<div class="history-time">' + escapeHtml(formatRelativeDate(email.date_envoi)) + '</div>' +
                        '</div>' +
                    '</article>'
                );
            }).join('');
        } catch (err) {
            list.innerHTML = '<div class="history-empty">Erreur réseau</div>';
        }
    }

    /**
     * Construit le HTML de la timeline pour le tiroir détail.
     * @param {object} email
     * @param {object} tracking
     * @returns {string}
     */
    function buildTimelineHtml(email, tracking) {
        const events = (tracking && Array.isArray(tracking.events)) ? tracking.events : [];
        const firstOpen = tracking && tracking.first_open;
        const firstClick = events.find(function (e) { return e.event_type === 'click'; });
        const failed = email && email.statut === 'failed';

        const steps = [
            {
                title: failed ? 'Échec d\'envoi' : 'Envoyé',
                time: email && email.date_envoi,
                done: true,
                cls: failed ? 'is-fail' : 'is-done'
            },
            {
                title: firstOpen ? 'Ouvert' : 'En attente d\'ouverture',
                time: firstOpen || null,
                done: !!firstOpen,
                cls: firstOpen ? 'is-open is-done' : ''
            },
            {
                title: firstClick ? 'Lien cliqué' : 'En attente de clic',
                time: firstClick ? firstClick.date_event : null,
                done: !!firstClick,
                cls: firstClick ? 'is-click is-done' : ''
            }
        ];

        return (
            '<ul class="timeline">' +
            steps.map(function (step) {
                return (
                    '<li class="' + step.cls + '">' +
                        '<div class="timeline-title">' + escapeHtml(step.title) + '</div>' +
                        '<div class="timeline-time">' + escapeHtml(formatDateTime(step.time)) + '</div>' +
                    '</li>'
                );
            }).join('') +
            '</ul>'
        );
    }

    /**
     * Ouvre le tiroir de détail pour un email envoyé.
     * @param {number} emailId
     * @returns {Promise<void>}
     */
    async function openEmailDetail(emailId) {
        selectedEmailId = emailId;
        const drawer = document.getElementById('email-detail-drawer');
        const body = document.getElementById('drawer-body');
        if (!drawer || !body) return;
        drawer.classList.add('is-open');
        drawer.setAttribute('aria-hidden', 'false');
        body.innerHTML = '<div class="history-empty">Chargement du détail...</div>';

        try {
            const [previewRes, trackRes] = await Promise.all([
                fetch('/api/emails-envoyes/' + emailId + '/preview'),
                fetch('/api/tracking/email/' + emailId)
            ]);
            const preview = await previewRes.json();
            const tracking = await trackRes.json();
            if (!previewRes.ok) {
                body.innerHTML = '<div class="history-empty">' + escapeHtml(preview.error || 'Email introuvable') + '</div>';
                return;
            }

            const opens = tracking.total_opens || 0;
            const clicks = tracking.total_clicks || 0;
            const emailStub = {
                date_envoi: preview.date_envoi,
                statut: opens === 0 && clicks === 0 && !preview.contenu_envoye ? 'sent' : 'sent'
            };

            // Recharger le statut depuis l'historique affiché si possible
            const card = document.querySelector('.history-item[data-email-id="' + emailId + '"]');
            if (card) {
                const pill = card.querySelector('.status-pill');
                if (pill && pill.classList.contains('failed')) {
                    emailStub.statut = 'failed';
                }
            }

            const clickedUrls = [];
            const events = Array.isArray(tracking.events) ? tracking.events : [];
            events.forEach(function (ev) {
                if (!ev || ev.event_type !== 'click') return;
                let url = '';
                try {
                    const raw = ev.event_data;
                    const data = typeof raw === 'string' ? JSON.parse(raw) : (raw || {});
                    url = (data && data.url) ? String(data.url) : '';
                } catch (parseErr) {
                    url = '';
                }
                if (url && clickedUrls.indexOf(url) === -1) clickedUrls.push(url);
            });

            const linksHtml = clickedUrls.length
                ? (
                    '<div class="drawer-links">' +
                        '<h3>Liens cliqués</h3>' +
                        '<ul>' +
                        clickedUrls.map(function (url) {
                            return '<li><a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">' +
                                escapeHtml(url) + '</a></li>';
                        }).join('') +
                        '</ul>' +
                    '</div>'
                )
                : '';

            const contentHtml = preview.contenu_envoye
                ? (
                    '<div class="drawer-mail-preview">' +
                        '<h3>Contenu envoyé</h3>' +
                        '<iframe class="drawer-preview-iframe" title="Contenu envoyé" sandbox=""></iframe>' +
                    '</div>'
                )
                : '<p class="drawer-no-content">Pas de snapshot du contenu pour cet envoi.</p>';

            body.innerHTML =
                '<div class="drawer-meta">' +
                    '<div><strong>À</strong> ' + escapeHtml(preview.email || '') + '</div>' +
                    '<div><strong>Nom</strong> ' + escapeHtml(preview.nom_destinataire || '-') + '</div>' +
                    '<div><strong>Entreprise</strong> ' + escapeHtml(preview.entreprise || '-') + '</div>' +
                    '<div><strong>Sujet</strong> ' + escapeHtml(preview.sujet || '') + '</div>' +
                    '<div><strong>Envoyé</strong> ' + escapeHtml(formatDateTime(preview.date_envoi)) + '</div>' +
                '</div>' +
                '<div class="drawer-stats">' +
                    '<div class="drawer-stat"><div class="n">' + opens + '</div><div class="l">Ouvertures</div></div>' +
                    '<div class="drawer-stat"><div class="n">' + clicks + '</div><div class="l">Clics</div></div>' +
                '</div>' +
                '<h3 class="drawer-section-title">Timeline</h3>' +
                buildTimelineHtml(Object.assign({}, preview, emailStub), tracking) +
                linksHtml +
                contentHtml +
                '<div class="drawer-actions">' +
                    '<button type="button" class="btn btn-secondary btn-sm" id="drawer-reuse">' +
                        '<i class="fa-solid fa-reply"></i> Réutiliser le destinataire' +
                    '</button>' +
                    '<button type="button" class="btn btn-secondary btn-sm" id="drawer-copy">' +
                        '<i class="fa-solid fa-copy"></i> Copier l\'email' +
                    '</button>' +
                '</div>';

            const drawerIframe = body.querySelector('.drawer-preview-iframe');
            if (drawerIframe && preview.contenu_envoye) {
                const html = String(preview.contenu_envoye);
                const looksHtml = /<\/?[a-z][\s\S]*>/i.test(html);
                drawerIframe.srcdoc = looksHtml
                    ? html
                    : '<pre style="font-family:inherit;white-space:pre-wrap;padding:12px;">' +
                        escapeHtml(html) + '</pre>';
            }

            const reuseBtn = document.getElementById('drawer-reuse');
            if (reuseBtn) {
                reuseBtn.addEventListener('click', function () {
                    addRecipient({
                        email: preview.email,
                        nom: preview.nom_destinataire,
                        entreprise: preview.entreprise
                    });
                    renderRecipients();
                    closeDrawer();
                });
            }
            const copyBtn = document.getElementById('drawer-copy');
            if (copyBtn && navigator.clipboard) {
                copyBtn.addEventListener('click', function () {
                    navigator.clipboard.writeText(preview.email || '');
                    copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copié';
                });
            }
            loadHistory();
        } catch (err) {
            body.innerHTML = '<div class="history-empty">Erreur de chargement</div>';
        }
    }

    /**
     * Ferme le tiroir détail.
     * @returns {void}
     */
    function closeDrawer() {
        const drawer = document.getElementById('email-detail-drawer');
        if (!drawer) return;
        drawer.classList.remove('is-open');
        drawer.setAttribute('aria-hidden', 'true');
        selectedEmailId = null;
        loadHistory();
    }

    /**
     * Met à jour l'aperçu iframe (debounce).
     * @returns {void}
     */
    function schedulePreview() {
        if (previewTimer) clearTimeout(previewTimer);
        previewTimer = setTimeout(refreshPreview, 350);
    }

    /**
     * Appelle l'API d'aperçu et injecte le HTML dans l'iframe.
     * @returns {Promise<void>}
     */
    async function refreshPreview() {
        const iframe = document.getElementById('preview-iframe');
        const empty = document.getElementById('preview-empty');
        const subjectEl = document.getElementById('preview-subject');
        const toEl = document.getElementById('preview-to');
        const templateId = (document.getElementById('template-select') || {}).value || '';
        const subject = (document.getElementById('subject') || {}).value || '';
        const customMessage = (document.getElementById('custom-message') || {}).value || '';
        const sample = recipients[0] || {
            email: 'destinataire@exemple.com',
            nom: 'Jean Dupont',
            entreprise: 'Example Corp'
        };

        if (!templateId && !String(customMessage).trim()) {
            if (iframe) {
                iframe.classList.remove('is-visible');
                iframe.srcdoc = '';
            }
            if (empty) empty.style.display = 'block';
            if (subjectEl) subjectEl.textContent = subject || 'Votre sujet';
            if (toEl) toEl.textContent = sample.email;
            return;
        }

        try {
            const response = await fetch('/api/send-emails/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    template_id: templateId || null,
                    subject: subject,
                    custom_message: customMessage || null,
                    recipient: sample
                })
            });
            const data = await response.json();
            if (!response.ok) {
                if (empty) {
                    empty.style.display = 'block';
                    empty.querySelector('p').textContent = data.error || 'Aperçu indisponible';
                }
                if (iframe) iframe.classList.remove('is-visible');
                return;
            }
            if (subjectEl) subjectEl.textContent = data.subject || subject || 'Votre sujet';
            if (toEl) toEl.textContent = data.to || sample.email;
            if (iframe) {
                iframe.srcdoc = data.html || '';
                iframe.classList.add('is-visible');
            }
            if (empty) empty.style.display = 'none';
        } catch (err) {
            // ignore
        }
    }

    /**
     * Affiche / masque le champ message selon le template.
     * @returns {void}
     */
    function syncMessageVisibility() {
        const templateId = (document.getElementById('template-select') || {}).value || '';
        const group = document.getElementById('custom-message-group');
        if (!group) return;
        group.style.opacity = templateId ? '0.55' : '1';
        const label = group.querySelector('label');
        if (label) {
            label.textContent = templateId
                ? 'Message libre (ignoré si un modèle est sélectionné)'
                : 'Message';
        }
    }

    /**
     * Envoie les emails un par un côté UX (une requête unique côté API).
     * @param {SubmitEvent} e
     * @returns {Promise<void>}
     */
    async function handleSubmit(e) {
        e.preventDefault();
        const statusDiv = document.getElementById('send-status');
        const progress = document.getElementById('send-progress');
        const progressFill = document.getElementById('send-progress-fill');
        const progressLabel = document.getElementById('send-progress-label');
        const btnSend = document.getElementById('btn-send');
        const subject = (document.getElementById('subject') || {}).value || '';
        const templateId = (document.getElementById('template-select') || {}).value || '';
        const customMessage = (document.getElementById('custom-message') || {}).value || '';

        if (!recipients.length) {
            if (statusDiv) {
                statusDiv.hidden = false;
                statusDiv.className = 'status-message status-error';
                statusDiv.textContent = 'Ajoute au moins un destinataire.';
            }
            return;
        }
        if (!subject.trim()) {
            if (statusDiv) {
                statusDiv.hidden = false;
                statusDiv.className = 'status-message status-error';
                statusDiv.textContent = 'Le sujet est obligatoire.';
            }
            return;
        }
        if (!templateId && !customMessage.trim()) {
            if (statusDiv) {
                statusDiv.hidden = false;
                statusDiv.className = 'status-message status-error';
                statusDiv.textContent = 'Choisis un modèle ou écris un message.';
            }
            return;
        }

        if (btnSend) btnSend.disabled = true;
        if (progress) progress.hidden = false;
        if (progressFill) progressFill.style.width = '15%';
        if (progressLabel) progressLabel.textContent = 'Envoi en cours (' + recipients.length + ')...';
        if (statusDiv) {
            statusDiv.hidden = false;
            statusDiv.className = 'status-message status-info';
            statusDiv.textContent = 'Envoi en cours...';
        }

        try {
            if (progressFill) progressFill.style.width = '55%';
            const response = await fetch('/send-emails', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    recipients: recipients,
                    template_id: templateId || null,
                    subject: subject,
                    custom_message: customMessage || null
                })
            });
            const data = await response.json();
            if (progressFill) progressFill.style.width = '100%';

            if (data.success) {
                if (statusDiv) {
                    statusDiv.className = 'status-message status-success';
                    statusDiv.textContent = 'Terminé : ' + data.total_sent + ' envoyé(s), ' + data.total_failed + ' échec(s).';
                }
                if (progressLabel) {
                    progressLabel.textContent = 'Envoi terminé';
                }
                await Promise.all([loadStats(), loadHistory()]);
            } else {
                if (statusDiv) {
                    statusDiv.className = 'status-message status-error';
                    statusDiv.textContent = 'Erreur : ' + (data.error || 'inconnue');
                }
            }
        } catch (err) {
            if (statusDiv) {
                statusDiv.className = 'status-message status-error';
                statusDiv.textContent = 'Erreur : ' + (err && err.message ? err.message : 'réseau');
            }
        } finally {
            if (btnSend) btnSend.disabled = false;
            setTimeout(function () {
                if (progress) progress.hidden = true;
                if (progressFill) progressFill.style.width = '0%';
            }, 1200);
        }
    }

    /**
     * Branche tous les écouteurs UI.
     * @returns {void}
     */
    function bindEvents() {
        const form = document.getElementById('send-emails-form');
        if (form) form.addEventListener('submit', handleSubmit);

        const addBtn = document.getElementById('btn-add-recipient');
        if (addBtn) {
            addBtn.addEventListener('click', function () {
                const email = (document.getElementById('recipient-email') || {}).value || '';
                const nom = (document.getElementById('recipient-nom') || {}).value || '';
                const entreprise = (document.getElementById('recipient-entreprise') || {}).value || '';
                if (addRecipient({ email: email, nom: nom, entreprise: entreprise })) {
                    renderRecipients();
                    const emailInput = document.getElementById('recipient-email');
                    const nomInput = document.getElementById('recipient-nom');
                    const entInput = document.getElementById('recipient-entreprise');
                    if (emailInput) emailInput.value = '';
                    if (nomInput) nomInput.value = '';
                    if (entInput) entInput.value = '';
                    if (emailInput) emailInput.focus();
                }
            });
        }

        ['recipient-email', 'recipient-nom', 'recipient-entreprise'].forEach(function (id) {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('keydown', function (ev) {
                if (ev.key === 'Enter') {
                    ev.preventDefault();
                    if (addBtn) addBtn.click();
                }
            });
        });

        const chips = document.getElementById('recipients-chips');
        if (chips) {
            chips.addEventListener('click', function (ev) {
                const btn = ev.target.closest('[data-remove]');
                if (!btn) return;
                const idx = Number(btn.getAttribute('data-remove'));
                if (!Number.isNaN(idx)) {
                    recipients.splice(idx, 1);
                    renderRecipients();
                }
            });
        }

        const parseBtn = document.getElementById('btn-parse-paste');
        if (parseBtn) {
            parseBtn.addEventListener('click', function () {
                const area = document.getElementById('recipients-paste');
                const added = parsePasteList(area ? area.value : '');
                renderRecipients();
                if (area && added) area.value = '';
            });
        }

        document.querySelectorAll('.var-chip').forEach(function (chip) {
            chip.addEventListener('click', function () {
                insertVariable(chip.getAttribute('data-target'), chip.getAttribute('data-var'));
            });
        });

        const templateSelect = document.getElementById('template-select');
        if (templateSelect) {
            templateSelect.addEventListener('change', function () {
                const opt = templateSelect.options[templateSelect.selectedIndex];
                const subjectInput = document.getElementById('subject');
                if (opt && opt.dataset && opt.dataset.subject && subjectInput && !subjectInput.value.trim()) {
                    subjectInput.value = opt.dataset.subject;
                }
                syncMessageVisibility();
                schedulePreview();
            });
        }

        ['subject', 'custom-message'].forEach(function (id) {
            const el = document.getElementById(id);
            if (el) el.addEventListener('input', schedulePreview);
        });

        const previewBtn = document.getElementById('btn-preview');
        if (previewBtn) previewBtn.addEventListener('click', refreshPreview);

        document.querySelectorAll('.viewport-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                document.querySelectorAll('.viewport-btn').forEach(function (b) { b.classList.remove('is-active'); });
                btn.classList.add('is-active');
                const frame = document.getElementById('mail-frame');
                if (frame) frame.setAttribute('data-viewport', btn.getAttribute('data-viewport') || 'desktop');
            });
        });

        document.querySelectorAll('.period-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                document.querySelectorAll('.period-btn').forEach(function (b) { b.classList.remove('is-active'); });
                btn.classList.add('is-active');
                currentDays = Number(btn.getAttribute('data-days') || 7);
                loadStats();
                loadHistory();
            });
        });

        /**
         * Active un filtre d'historique et synchronise les boutons + KPI.
         * @param {string} filter
         * @returns {void}
         */
        function setHistoryFilter(filter) {
            currentFilter = filter || 'all';
            document.querySelectorAll('.hist-filter').forEach(function (b) {
                b.classList.toggle('is-active', b.getAttribute('data-filter') === currentFilter);
            });
            document.querySelectorAll('.kpi-card[data-filter]').forEach(function (card) {
                card.classList.toggle('is-filter-active', card.getAttribute('data-filter') === currentFilter);
            });
            loadHistory();
        }

        document.querySelectorAll('.hist-filter').forEach(function (btn) {
            btn.addEventListener('click', function () {
                setHistoryFilter(btn.getAttribute('data-filter') || 'all');
            });
        });

        document.querySelectorAll('.kpi-card[data-filter]').forEach(function (card) {
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.addEventListener('click', function () {
                const next = card.getAttribute('data-filter') || 'all';
                setHistoryFilter(currentFilter === next ? 'all' : next);
            });
            card.addEventListener('keydown', function (ev) {
                if (ev.key !== 'Enter' && ev.key !== ' ') return;
                ev.preventDefault();
                card.click();
            });
        });

        const refreshBtn = document.getElementById('btn-refresh-history');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function () {
                loadStats();
                loadHistory();
            });
        }

        const historyList = document.getElementById('history-list');
        if (historyList) {
            historyList.addEventListener('click', function (ev) {
                const item = ev.target.closest('.history-item');
                if (!item) return;
                const id = Number(item.getAttribute('data-email-id'));
                if (!Number.isNaN(id)) openEmailDetail(id);
            });
            historyList.addEventListener('keydown', function (ev) {
                if (ev.key !== 'Enter' && ev.key !== ' ') return;
                const item = ev.target.closest('.history-item');
                if (!item) return;
                ev.preventDefault();
                const id = Number(item.getAttribute('data-email-id'));
                if (!Number.isNaN(id)) openEmailDetail(id);
            });
        }

        const backdrop = document.getElementById('drawer-backdrop');
        const closeBtn = document.getElementById('drawer-close');
        if (backdrop) backdrop.addEventListener('click', closeDrawer);
        if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
        document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape') closeDrawer();
        });
    }

    /**
     * Point d'entrée de la page.
     * @returns {void}
     */
    function init() {
        const root = document.getElementById('senddesk');
        if (!root) return;
        const activePeriod = document.querySelector('.period-btn.is-active');
        currentDays = Number(
            (activePeriod && activePeriod.getAttribute('data-days')) ||
            root.getAttribute('data-days') ||
            7
        );
        root.setAttribute('data-days', String(currentDays));
        bindEvents();
        syncMessageVisibility();
        renderRecipients();
        loadStats();
        loadHistory();
        schedulePreview();
        historyPollTimer = setInterval(function () {
            loadStats();
            loadHistory();
        }, 45000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
