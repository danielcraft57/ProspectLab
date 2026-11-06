/**
 * Tchatche virtuel : Q/R KB Messenger (UI v7).
 */
(function () {
    'use strict';

    /** @type {{role: string, text: string, meta?: string}[]} */
    let messages = [];
    /** @type {string[]} */
    let recentReplies = [];
    /** @type {string[]} */
    let recentTags = [];
    /** @type {string[]} */
    let recentUserTexts = [];
    /** @type {number|null} */
    let entrepriseId = null;
    /** @type {number} */
    let searchTimer = 0;
    /** @type {{text: string, intent?: string}[]} */
    let cachedOpenings = [];
    /** @type {object[]} */
    let cachedVarGroups = [];
    /** @type {number|null} */
    let sessionId = null;

    const INTENT_SUB_IDLE = 'Choisis une entreprise, puis envoie un message.';

    /**
     * True si une fiche CRM est liee.
     * @returns {boolean}
     */
    function hasEntreprise() {
        return entrepriseId != null && !Number.isNaN(entrepriseId);
    }

    /**
     * Active / desactive chat et scenarios selon la fiche.
     */
    function updateInteractionState() {
        const ready = hasEntreprise();
        const input = document.getElementById('tchatche-input');
        const sendBtn = document.getElementById('tchatche-send');
        const form = document.getElementById('tchatche-form');
        const composer = document.getElementById('tchatche-composer');
        const lockMsg = document.getElementById('tchatche-composer-lock');
        const prompts = document.getElementById('tchatche-prompts');
        const title = document.getElementById('tchatche-empty-title');
        const hint = document.getElementById('tchatche-empty-hint');
        const ctx = document.querySelector('.tc-context');

        if (input) {
            input.disabled = !ready;
            input.placeholder = ready
                ? 'Ecrire un message client… (Entree envoyer, Maj+Entree saut de ligne)'
                : 'Choisis une entreprise en haut…';
        }
        if (sendBtn) sendBtn.disabled = !ready;
        if (form) form.classList.toggle('tc-composer-form--locked', !ready);
        if (composer) composer.classList.toggle('tc-composer--locked', !ready);
        if (lockMsg) lockMsg.hidden = ready;
        if (prompts) prompts.hidden = !ready;
        if (ctx) ctx.classList.toggle('tc-context--highlight', !ready);

        if (!messages.length) {
            if (title) {
                title.textContent = ready ? 'Pret pour la conversation' : 'Commence par une entreprise';
            }
            if (hint) {
                hint.textContent = ready
                    ? 'Lance une ouverture DanielCraft ou reponds comme le client.'
                    : 'Recherche une fiche CRM (nom, ville). C est obligatoire pour des reponses utiles.';
            }
        }
    }

    /**
     * Bloque l envoi si pas de fiche.
     * @returns {boolean}
     */
    function requireEntreprise() {
        if (hasEntreprise()) return true;
        showContextError('Choisis une entreprise avant de tester la conversation.');
        const search = document.getElementById('tchatche-ent-search');
        if (search) search.focus();
        updateInteractionState();
        return false;
    }

    /**
     * Echappe le HTML.
     * @param {unknown} t Texte brut
     * @returns {string}
     */
    function esc(t) {
        return window.Formatters && Formatters.escapeHtml
            ? Formatters.escapeHtml(String(t ?? ''))
            : String(t ?? '');
    }

    /**
     * Echappe une valeur pour attribut HTML.
     * @param {unknown} t Texte brut
     * @returns {string}
     */
    function escAttr(t) {
        return String(t ?? '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
    }

    /**
     * Appel JSON authentifie.
     * @param {string} url Chemin API
     * @param {RequestInit} [options] Fetch
     * @returns {Promise<object>}
     */
    async function fetchJson(url, options) {
        const resp = await fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}));
        const data = await resp.json().catch(function () {
            return {};
        });
        if (!resp.ok || data.success === false) {
            const msg =
                data.error ||
                data.detail ||
                (resp.status === 404 ? 'Ressource introuvable (redemarre Flask si la route vient d etre ajoutee)' : resp.statusText) ||
                'Erreur API';
            throw new Error(msg);
        }
        return data;
    }

    /**
     * Active resume contexte et bouton enregistrer.
     */
    function updateContextControls() {
        const summary = document.getElementById('tchatche-context-summary');
        const saveBtn = document.getElementById('tchatche-context-save');
        const ready = hasEntreprise() && sessionId != null;
        if (summary) summary.disabled = !ready;
        if (saveBtn) saveBtn.disabled = !ready;
    }

    /**
     * Affiche la fenetre contexte (6 tours) cote debug.
     * @param {{recent_replies?: string[], recent_tags?: string[], recent_user_texts?: string[]}|null} win
     * @param {string|null|undefined} summary Resume long terme
     */
    function renderContextPanel(win, summary) {
        const box = document.getElementById('tchatche-context-window');
        const summaryEl = document.getElementById('tchatche-context-summary');
        if (summaryEl && summary !== undefined) {
            summaryEl.value = summary ? String(summary) : '';
        }
        if (!box) return;
        if (!win) {
            box.innerHTML =
                '<p class="tc-var-hint">Envoie un message ou charge une archive pour voir le contexte.</p>';
            return;
        }
        const blocks = [
            { label: 'Messages client', items: win.recent_user_texts || [] },
            { label: 'Reponses bot', items: win.recent_replies || [] },
            { label: 'Tags intent', items: win.recent_tags || [] },
        ];
        box.innerHTML = blocks
            .map(function (b) {
                if (!b.items.length) {
                    return (
                        '<div class="tc-context-row"><strong>' +
                        esc(b.label) +
                        '</strong><span class="tc-var-hint">—</span></div>'
                    );
                }
                return (
                    '<div class="tc-context-row"><strong>' +
                    esc(b.label) +
                    '</strong>' +
                    b.items
                        .map(function (line, idx) {
                            return '<div>' + esc(idx + 1) + '. ' + esc(line) + '</div>';
                        })
                        .join('') +
                    '</div>'
                );
            })
            .join('');
    }

    /**
     * Synchronise recent_* depuis le serveur.
     * @param {{recent_replies?: string[], recent_tags?: string[], recent_user_texts?: string[]}|null} win
     * @param {string|null|undefined} summary
     */
    function applyContextFromServer(win, summary) {
        if (win) {
            recentReplies = (win.recent_replies || []).slice();
            recentTags = (win.recent_tags || []).slice();
            recentUserTexts = (win.recent_user_texts || []).slice();
            renderContextPanel(win, summary);
        }
        updateContextControls();
    }

    /**
     * Reconstruit le fil depuis l'archive SQL.
     * @param {object[]} rows Messages API
     * @param {object|null} win Fenetre contexte
     * @param {object|null} sess Session
     */
    function hydrateFromArchive(rows, win, sess) {
        messages = [];
        recentReplies = [];
        recentTags = [];
        recentUserTexts = [];
        (rows || []).forEach(function (row) {
            const role = String(row.role || '').toLowerCase();
            const text = String(row.body_text || '').trim();
            if (!text) return;
            const metaBits = [];
            if (row.intent_tag) metaBits.push(String(row.intent_tag));
            if (row.engine) metaBits.push(String(row.engine));
            messages.push({
                role: role === 'user' ? 'user' : 'bot',
                text: text,
                meta: metaBits.length ? metaBits.join(' · ') : '',
            });
            if (role === 'user') {
                recentUserTexts.push(text);
            } else if (role === 'bot') {
                recentReplies.push(text);
                if (row.intent_tag) recentTags.push(String(row.intent_tag));
            }
        });
        const cap = 6;
        const builtWin = {
            recent_user_texts: recentUserTexts.slice(-cap),
            recent_replies: recentReplies.slice(-cap),
            recent_tags: recentTags.slice(-cap),
        };
        const sum = sess && sess.context_summary ? sess.context_summary : '';
        applyContextFromServer(win || builtWin, sum);
        renderMessages();
        highlightArchiveSession(sessionId);
    }

    /**
     * Marque la session active dans la liste archive.
     * @param {number|null} id Session
     */
    function highlightArchiveSession(id) {
        const list = document.getElementById('tchatche-archive-list');
        if (!list) return;
        list.querySelectorAll('.tc-archive-item').forEach(function (btn) {
            const sid = Number(btn.getAttribute('data-session-id'));
            btn.classList.toggle('is-active', id != null && sid === id);
        });
    }

    /**
     * Liste les sessions sandbox pour l'entreprise courante.
     */
    async function loadArchiveList() {
        const list = document.getElementById('tchatche-archive-list');
        if (!list) return;
        if (!hasEntreprise()) {
            list.innerHTML = '<li class="tc-var-hint">Choisis une entreprise pour lister l archive.</li>';
            return;
        }
        try {
            const data = await fetchJson(
                '/api/facebook-prospection/tchatche/sessions?entreprise_id=' +
                    encodeURIComponent(String(entrepriseId)) +
                    '&limit=25'
            );
            const items = data.items || [];
            if (!items.length) {
                list.innerHTML = '<li class="tc-var-hint">Aucun test enregistre pour cette fiche.</li>';
                return;
            }
            list.innerHTML = items
                .map(function (s) {
                    const title = s.title || 'Conversation sans titre';
                    const count = s.message_count != null ? s.message_count : '—';
                    const when = s.updated_at || s.created_at || '';
                    return (
                        '<li><button type="button" class="tc-archive-item" data-session-id="' +
                        escAttr(s.id) +
                        '"><span class="tc-archive-title">' +
                        esc(title) +
                        '</span><span class="tc-archive-meta">#' +
                        esc(s.id) +
                        ' · ' +
                        esc(count) +
                        ' messages' +
                        (when ? ' · ' + esc(when) : '') +
                        '</span></button></li>'
                    );
                })
                .join('');
            highlightArchiveSession(sessionId);
        } catch (err) {
            list.innerHTML =
                '<li class="tc-var-hint">' +
                esc(err && err.message ? err.message : 'Archive indisponible') +
                '</li>';
        }
    }

    /**
     * Charge une session archive dans le fil principal.
     * @param {string|number} id ID session
     */
    async function loadArchiveSession(id) {
        if (!requireEntreprise()) return;
        const data = await fetchJson(
            '/api/facebook-prospection/tchatche/sessions/' +
                encodeURIComponent(String(id)) +
                '?entreprise_id=' +
                encodeURIComponent(String(entrepriseId))
        );
        sessionId = Number(data.session && data.session.id ? data.session.id : id);
        hydrateFromArchive(data.messages, data.context_window, data.session);
        updateContextControls();
    }

    /**
     * Enregistre le resume contexte long.
     */
    async function saveContextSummary() {
        if (!sessionId || !hasEntreprise()) return;
        const summaryEl = document.getElementById('tchatche-context-summary');
        const text = summaryEl ? String(summaryEl.value || '') : '';
        const data = await fetchJson(
            '/api/facebook-prospection/tchatche/sessions/' +
                encodeURIComponent(String(sessionId)) +
                '/context',
            {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    entreprise_id: entrepriseId,
                    context_summary: text,
                }),
            }
        );
        applyContextFromServer(data.context_window, data.session && data.session.context_summary);
    }

    /**
     * Affiche ou masque l'indicateur de frappe.
     * @param {boolean} show Visible
     */
    function setTyping(show) {
        const el = document.getElementById('tchatche-typing');
        if (el) el.hidden = !show;
    }

    /**
     * Pulse la carte intent apres une reponse.
     */
    function pulseIntentPanel() {
        const panel = document.getElementById('tchatche-panel-intent');
        const hero = panel ? panel.querySelector('.tc-intent-hero') : null;
        if (!hero) return;
        hero.classList.add('tc-intent-hero--pulse');
        window.setTimeout(function () {
            hero.classList.remove('tc-intent-hero--pulse');
        }, 550);
    }

    /**
     * Affiche les bulles de conversation.
     */
    function renderMessages() {
        const box = document.getElementById('tchatche-messages');
        const empty = document.getElementById('tchatche-empty');
        if (!box) return;

        if (!messages.length) {
            if (empty) empty.hidden = false;
            box.hidden = true;
            box.innerHTML = '';
            return;
        }

        if (empty) empty.hidden = true;
        box.hidden = false;
        box.innerHTML = messages
            .map(function (m) {
                const cls = 'tc-bubble tc-bubble--' + (m.role === 'user' ? 'user' : 'bot');
                const meta = m.meta ? '<span class="tc-bubble-meta">' + esc(m.meta) + '</span>' : '';
                return '<div class="' + cls + '">' + esc(m.text) + meta + '</div>';
            })
            .join('');
        box.scrollTop = box.scrollHeight;
    }

    /**
     * Affiche tag + top predictions.
     * @param {object} turn Reponse API
     */
    function renderSide(turn) {
        const intentEl = document.getElementById('tchatche-intent');
        const subEl = document.getElementById('tchatche-intent-sub');
        const list = document.getElementById('tchatche-preds');
        const tag = turn.tag || '—';
        const score = turn.score != null ? turn.score : null;
        const src = turn.engine || turn.source || '';

        if (intentEl) {
            intentEl.textContent = tag;
            intentEl.classList.remove('tc-intent-tag--flash');
            void intentEl.offsetWidth;
            intentEl.classList.add('tc-intent-tag--flash');
        }
        if (subEl) {
            const bits = [];
            if (score != null) bits.push('confiance ' + score);
            if (src) bits.push(src);
            subEl.textContent = bits.length ? bits.join(' · ') : INTENT_SUB_IDLE;
        }
        if (!list) return;

        const preds = turn.top_predictions || [];
        if (!preds.length) {
            list.innerHTML = '<li class="tc-scores-empty">Pas de classement pour ce tour.</li>';
        } else {
            list.innerHTML = preds
                .slice(0, 8)
                .map(function (p, idx) {
                    const t = p.tag || p.intent_id || '—';
                    const s = Math.min(100, Math.round(Number(p.score || 0) * 100));
                    return (
                        '<li><span class="tc-score-rank">' +
                        esc(idx + 1) +
                        '</span><span class="tc-score-name">' +
                        esc(t) +
                        '</span><span class="tc-score-pct">' +
                        esc(s) +
                        '%</span><div class="tc-score-bar"><span style="width:' +
                        s +
                        '%"></span></div></li>'
                    );
                })
                .join('');
        }
        pulseIntentPanel();
    }

    /**
     * Cartes KPI statut KB.
     */
    async function loadStatus() {
        const bar = document.getElementById('tchatche-status-bar');
        if (!bar) return;
        try {
            const data = await fetchJson('/api/facebook-prospection/tchatche/status');
            const q = data.qdrant || {};
            const cards = [];

            cards.push({
                icon: q.ok ? 'fa-database' : 'fa-triangle-exclamation',
                ok: !!q.ok,
                label: 'Collection',
                value:
                    (data.collection || 'Qdrant') +
                    ' · ' +
                    (q.points_count != null ? q.points_count : 0) +
                    ' points',
            });

            cards.push({
                icon: 'fa-vector-square',
                ok: !!q.vector_size,
                label: 'Embeddings',
                value: q.vector_size ? q.vector_size + ' dimensions' : '—',
            });

            cards.push({
                icon: data.kb_chat_configured ? 'fa-plug-circle-check' : 'fa-microchip',
                ok: true,
                label: 'Moteur tchatche',
                value: data.kb_chat_configured
                    ? 'API catalogue connectee'
                    : 'Reponses via Qdrant + catalogue local',
            });

            bar.innerHTML = cards
                .map(function (c) {
                    const iconCls = c.ok ? 'tc-kpi-icon--ok' : 'tc-kpi-icon--warn';
                    return (
                        '<div class="tc-kpi-card"><span class="tc-kpi-icon ' +
                        iconCls +
                        '"><i class="fa-solid ' +
                        esc(c.icon) +
                        '" aria-hidden="true"></i></span><div class="tc-kpi-body"><span class="tc-kpi-label">' +
                        esc(c.label) +
                        '</span><span class="tc-kpi-value">' +
                        esc(c.value) +
                        '</span></div></div>'
                    );
                })
                .join('');

            if (!q.ok && q.detail) {
                bar.innerHTML +=
                    '<div class="tc-kpi-card"><span class="tc-kpi-icon tc-kpi-icon--warn"><i class="fa-solid fa-circle-info" aria-hidden="true"></i></span><div class="tc-kpi-body"><span class="tc-kpi-label">Qdrant</span><span class="tc-kpi-value">' +
                    esc(String(q.detail)) +
                    '</span></div></div>';
            }
        } catch (err) {
            bar.innerHTML =
                '<div class="tc-kpi-card"><span class="tc-kpi-icon tc-kpi-icon--warn"><i class="fa-solid fa-circle-exclamation" aria-hidden="true"></i></span><div class="tc-kpi-body"><span class="tc-kpi-label">Erreur</span><span class="tc-kpi-value">' +
                esc(err && err.message ? err.message : 'Statut indisponible') +
                '</span></div></div>';
        }
    }

    /**
     * Envoie un message utilisateur.
     * @param {string} text Saisie
     */
    async function sendTurn(text) {
        if (!requireEntreprise()) return;
        messages.push({ role: 'user', text: text });
        recentUserTexts.push(text);
        renderMessages();
        setTyping(true);
        const payload = {
            text: text,
            recent_replies: recentReplies.slice(-6),
            recent_tags: recentTags.slice(-6),
            recent_user_texts: recentUserTexts.slice(-6),
            entreprise_id: entrepriseId,
        };
        if (sessionId != null) payload.session_id = sessionId;
        try {
            const turn = await fetchJson('/api/facebook-prospection/tchatche', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (turn.session_id != null) sessionId = Number(turn.session_id);
            const reply = String(turn.reply || '').trim() || '(pas de reponse)';
            const meta = [turn.tag, turn.engine || turn.source].filter(Boolean).join(' · ');
            messages.push({ role: 'bot', text: reply, meta: meta });
            applyContextFromServer(turn.context_window, turn.context_summary);
            renderMessages();
            renderVars(turn.vars, turn.var_groups);
            if (turn.var_groups) cachedVarGroups = turn.var_groups;
            renderSide(turn);
            loadArchiveList().catch(function () {});
        } finally {
            setTyping(false);
        }
    }

    /**
     * Remet la conversation a zero.
     */
    function resetChat() {
        messages = [];
        recentReplies = [];
        recentTags = [];
        recentUserTexts = [];
        sessionId = null;
        renderMessages();
        renderContextPanel(null, '');
        updateContextControls();
        const intentEl = document.getElementById('tchatche-intent');
        if (intentEl) intentEl.textContent = '—';
        const sub = document.getElementById('tchatche-intent-sub');
        if (sub) sub.textContent = INTENT_SUB_IDLE;
        const preds = document.getElementById('tchatche-preds');
        if (preds) {
            preds.innerHTML =
                '<li class="tc-scores-empty">Aucun score tant que la conversation est vide.</li>';
        }
        if (hasEntreprise()) {
            loadArchiveList().catch(function () {});
        } else {
            renderVars(null);
            cachedVarGroups = [];
            clearFichePanel();
            entrepriseId = null;
            setPicked(null);
            const search = document.getElementById('tchatche-ent-search');
            if (search) search.value = '';
        }
        highlightArchiveSession(null);
        updateInteractionState();
    }

    /**
     * Affiche les variables injectees.
     * @param {Record<string, string>|null} varsMap Variables
     * @param {object[]|null} [varGroups] Groupes UI
     */
    function renderVars(varsMap, varGroups) {
        const list = document.getElementById('tchatche-vars');
        if (!list) return;
        const groups = varGroups || cachedVarGroups;
        if (!varsMap) {
            list.innerHTML = '<li class="tc-var-hint">Lie une fiche CRM pour remplir les placeholders.</li>';
            return;
        }
        if (groups && groups.length) {
            list.innerHTML = groups
                .map(function (g) {
                    const items = (g.items || [])
                        .map(function (it) {
                            return (
                                '<li class="tc-var-row"><code>{{' +
                                esc(it.key) +
                                '}}</code><span>' +
                                esc(it.value || '—') +
                                '</span></li>'
                            );
                        })
                        .join('');
                    return (
                        '<li class="tc-var-group"><span class="tc-var-group-title">' +
                        esc(g.label || '') +
                        '</span><ul class="tc-var-sublist">' +
                        items +
                        '</ul></li>'
                    );
                })
                .join('');
            return;
        }
        const keys = ['entreprise', 'nom', 'prenom', 'ville', 'website', 'telephone', 'secteur', 'metier', 'email'];
        list.innerHTML = keys
            .map(function (k) {
                const v = varsMap[k] || '';
                return (
                    '<li><code>{{' +
                    esc(k) +
                    '}}</code><span>' +
                    esc(v || '—') +
                    '</span></li>'
                );
            })
            .join('');
    }

    /**
     * Message d'erreur sous la recherche CRM.
     * @param {string} msg Texte ou vide pour effacer
     */
    function showContextError(msg) {
        let el = document.getElementById('tchatche-context-error');
        const field = document.querySelector('.tc-context-field');
        if (!field) return;
        if (!el) {
            el = document.createElement('p');
            el.id = 'tchatche-context-error';
            el.className = 'tc-context-error';
            el.setAttribute('role', 'alert');
            field.parentNode.appendChild(el);
        }
        if (!msg) {
            el.hidden = true;
            el.textContent = '';
            return;
        }
        el.hidden = false;
        el.textContent = msg;
    }

    /**
     * Masque le panneau fiche / ouvertures.
     */
    function clearFichePanel() {
        const panel = document.getElementById('tchatche-fiche');
        const openings = document.getElementById('tchatche-openings');
        if (panel) panel.hidden = true;
        if (openings) openings.innerHTML = '';
    }

    /**
     * Affiche la fiche CRM et les messages d'ouverture.
     * @param {{entreprise?: object, opening_messages?: object[]}} data Contexte API
     */
    function renderFichePanel(data) {
        const panel = document.getElementById('tchatche-fiche');
        const title = document.getElementById('tchatche-fiche-title');
        const meta = document.getElementById('tchatche-fiche-meta');
        const list = document.getElementById('tchatche-openings');
        const ent = data.entreprise || {};
        cachedOpenings = data.opening_messages || [];
        if (title) {
            title.textContent = ent.nom ? String(ent.nom) : 'Fiche CRM';
        }
        if (meta) {
            const bits = [];
            if (ent.ville) bits.push(String(ent.ville));
            if (ent.website) bits.push(String(ent.website));
            if (ent.telephone) bits.push(String(ent.telephone));
            if (ent.secteur) bits.push(String(ent.secteur));
            meta.textContent = bits.length ? bits.join(' · ') : 'Donnees CRM chargees.';
        }
        if (list) {
            if (!cachedOpenings.length) {
                list.innerHTML = '<p class="tc-var-hint">Aucune ouverture generee pour cette fiche.</p>';
            } else {
                list.innerHTML = cachedOpenings
                    .map(function (o, idx) {
                        return (
                            '<button type="button" class="tc-opening" data-opening-idx="' +
                            idx +
                            '"><span class="tc-opening-text">' +
                            esc(o.text) +
                            '</span><span class="tc-opening-action">Demarrer avec ce message</span></button>'
                        );
                    })
                    .join('');
            }
        }
        if (panel) panel.hidden = false;
    }

    /**
     * Charge fiche, variables et ouvertures depuis l'API.
     * @param {string|number} id ID entreprise
     * @returns {Promise<object>}
     */
    async function loadEntrepriseContext(id) {
        if (!id) {
            throw new Error('ID entreprise manquant');
        }
        const data = await fetchJson(
            '/api/facebook-prospection/tchatche/entreprise/' + encodeURIComponent(String(id))
        );
        if (!data.entreprise || data.entreprise.id == null) {
            throw new Error('Reponse API incomplete');
        }
        entrepriseId = Number(data.entreprise.id);
        setPicked(data.entreprise);
        renderVars(data.vars, data.var_groups);
        cachedVarGroups = data.var_groups || [];
        renderFichePanel(data);
        const search = document.getElementById('tchatche-ent-search');
        if (search && data.entreprise && data.entreprise.nom) {
            search.value = String(data.entreprise.nom);
        }
        showContextError('');
        updateInteractionState();
        loadArchiveList().catch(function () {});
        return data;
    }

    /**
     * Demarre la sandbox avec le message DanielCraft (bulle bot).
     * @param {string} text Message d'ouverture
     * @param {string} [intent] Tag intent
     */
    async function startWithOpening(text, intent) {
        if (!requireEntreprise()) return;
        const tag = intent || 'out_presentation';
        try {
            const data = await fetchJson('/api/facebook-prospection/tchatche/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    entreprise_id: entrepriseId,
                    opening: { text: text, intent: tag },
                }),
            });
            sessionId = Number(data.session_id);
            hydrateFromArchive(data.messages, data.context_window, data.session);
            const intentEl = document.getElementById('tchatche-intent');
            if (intentEl) {
                intentEl.textContent = tag;
            }
            const sub = document.getElementById('tchatche-intent-sub');
            if (sub) {
                sub.textContent = 'ouverture personnalisee · template CRM';
            }
            const preds = document.getElementById('tchatche-preds');
            if (preds) {
                preds.innerHTML =
                    '<li><span class="tc-score-rank">1</span><span class="tc-score-name">' +
                    esc(tag) +
                    '</span><span class="tc-score-pct">—</span><div class="tc-score-bar"><span style="width:100%"></span></div></li>';
            }
            loadArchiveList().catch(function () {});
        } catch (err) {
            showContextError(err && err.message ? err.message : 'Impossible de creer la session');
        }
    }

    /**
     * Affiche la fiche selectionnee.
     * @param {{id?: string|number, nom?: string, ville?: string}|null} ent Fiche
     */
    function setPicked(ent) {
        const el = document.getElementById('tchatche-ent-picked');
        if (!el) return;
        if (!ent || !ent.id) {
            entrepriseId = null;
            el.hidden = true;
            el.textContent = '';
            return;
        }
        entrepriseId = Number(ent.id);
        el.hidden = false;
        el.innerHTML =
            '<i class="fa-solid fa-link" aria-hidden="true"></i> #' +
            esc(ent.id) +
            ' · ' +
            esc(ent.nom || '') +
            (ent.ville ? ' · ' + esc(ent.ville) : '');
    }

    /**
     * Recherche entreprises pour autocomplete.
     * @param {string} q Texte
     */
    async function searchEntreprises(q) {
        const list = document.getElementById('tchatche-ent-list');
        if (!list) return;
        if (!String(q || '').trim()) {
            list.hidden = true;
            list.innerHTML = '';
            return;
        }
        const data = await fetchJson(
            '/api/facebook-prospection/tchatche/entreprises?q=' +
                encodeURIComponent(q) +
                '&limit=10'
        );
        const items = data.items || [];
        if (!items.length) {
            list.hidden = true;
            list.innerHTML = '';
            return;
        }
        list.hidden = false;
        list.innerHTML = items
            .map(function (e) {
                const label = (e.nom || '—') + (e.ville ? ' · ' + e.ville : '');
                return (
                    '<li><button type="button" data-id="' +
                    escAttr(e.id) +
                    '">' +
                    esc(label) +
                    '</button></li>'
                );
            })
            .join('');
    }

    /**
     * Onglets panneau debug.
     */
    function bindDebugTabs() {
        const tabs = document.querySelectorAll('.tc-debug-tab');
        const panels = document.querySelectorAll('.tc-debug-panel');
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                const name = tab.getAttribute('data-tc-tab');
                tabs.forEach(function (t) {
                    const active = t === tab;
                    t.classList.toggle('is-active', active);
                    t.setAttribute('aria-selected', active ? 'true' : 'false');
                });
                panels.forEach(function (p) {
                    const show = p.getAttribute('data-tc-panel') === name;
                    p.hidden = !show;
                    p.classList.toggle('is-active', show);
                });
            });
        });
    }

    /**
     * Lance un scenario ou un envoi avec feedback visuel.
     * @param {HTMLElement} btn Bouton scenario
     * @param {string} text Message
     * @param {HTMLButtonElement|null} sendBtn Bouton envoyer
     */
    function firePrompt(btn, text, sendBtn) {
        if (sendBtn) sendBtn.disabled = true;
        btn.classList.add('tc-scenario--used');
        window.setTimeout(function () {
            btn.classList.remove('tc-scenario--used');
        }, 450);
        sendTurn(text)
            .catch(function (err) {
                messages.push({
                    role: 'bot',
                    text: 'Erreur: ' + (err && err.message ? err.message : err),
                });
                renderMessages();
            })
            .finally(function () {
                if (sendBtn) sendBtn.disabled = false;
                const input = document.getElementById('tchatche-input');
                if (input) input.focus();
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        renderMessages();
        renderVars(null);
        renderContextPanel(null, '');
        updateContextControls();
        loadStatus();
        bindDebugTabs();

        const contextSave = document.getElementById('tchatche-context-save');
        if (contextSave) {
            contextSave.addEventListener('click', function () {
                saveContextSummary().catch(function (err) {
                    showContextError(err && err.message ? err.message : 'Enregistrement impossible');
                });
            });
        }

        const archiveRoot = document.getElementById('tchatche-archive-list');
        if (archiveRoot) {
            archiveRoot.addEventListener('click', function (ev) {
                const btn = ev.target && ev.target.closest ? ev.target.closest('[data-session-id]') : null;
                if (!btn) return;
                const id = btn.getAttribute('data-session-id');
                loadArchiveSession(id).catch(function (err) {
                    showContextError(err && err.message ? err.message : 'Chargement archive impossible');
                });
            });
        }

        const form = document.getElementById('tchatche-form');
        const input = document.getElementById('tchatche-input');
        const resetBtn = document.getElementById('tchatche-reset');
        const sendBtn = document.getElementById('tchatche-send');
        const prompts = document.getElementById('tchatche-prompts');

        /**
         * Envoie le texte du composer (form ou Entree).
         */
        function submitComposerMessage() {
            if (!requireEntreprise()) return;
            if (!input) return;
            const text = String(input.value || '').trim();
            if (!text) return;
            input.value = '';
            if (sendBtn) sendBtn.disabled = true;
            sendTurn(text)
                .catch(function (err) {
                    messages.push({
                        role: 'bot',
                        text: 'Erreur: ' + (err && err.message ? err.message : err),
                    });
                    renderMessages();
                })
                .finally(function () {
                    if (sendBtn) sendBtn.disabled = false;
                    input.focus();
                });
        }

        if (form && input) {
            form.addEventListener('submit', function (ev) {
                ev.preventDefault();
                submitComposerMessage();
            });
            input.addEventListener('keydown', function (ev) {
                if (ev.key !== 'Enter') return;
                if (ev.shiftKey || ev.ctrlKey || ev.altKey || ev.metaKey) return;
                ev.preventDefault();
                submitComposerMessage();
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', resetChat);
        }

        if (prompts) {
            prompts.addEventListener('click', function (ev) {
                if (!requireEntreprise()) return;
                const btn = ev.target && ev.target.closest ? ev.target.closest('[data-prompt]') : null;
                if (!btn) return;
                const text = String(btn.getAttribute('data-prompt') || '').trim();
                if (!text) return;
                firePrompt(btn, text, sendBtn);
            });
        }

        const search = document.getElementById('tchatche-ent-search');
        const list = document.getElementById('tchatche-ent-list');
        if (search) {
            search.addEventListener('input', function () {
                window.clearTimeout(searchTimer);
                const q = search.value;
                searchTimer = window.setTimeout(function () {
                    searchEntreprises(q).catch(function () {
                        if (list) list.hidden = true;
                    });
                }, 250);
            });
        }
        if (list) {
            list.addEventListener('click', function (ev) {
                const btn = ev.target && ev.target.closest ? ev.target.closest('button[data-id]') : null;
                if (!btn) return;
                const id = btn.getAttribute('data-id');
                list.hidden = true;
                loadEntrepriseContext(id).catch(function (err) {
                    showContextError(err && err.message ? err.message : 'Impossible de charger la fiche');
                });
            });
        }

        const openingsRoot = document.getElementById('tchatche-openings');
        if (openingsRoot) {
            openingsRoot.addEventListener('click', function (ev) {
                const btn = ev.target && ev.target.closest ? ev.target.closest('[data-opening-idx]') : null;
                if (!btn) return;
                const idx = Number(btn.getAttribute('data-opening-idx'));
                const item = cachedOpenings[idx];
                if (!item || !item.text) return;
                startWithOpening(String(item.text), item.intent);
            });
        }

        updateContextControls();
        const searchFocus = document.getElementById('tchatche-ent-search');
        if (searchFocus && !hasEntreprise()) {
            searchFocus.focus();
        }

        const params = new URLSearchParams(window.location.search);
        const prefillId = params.get('entreprise_id');
        if (prefillId) {
            loadEntrepriseContext(prefillId).catch(function (err) {
                showContextError(err && err.message ? err.message : 'Fiche introuvable');
            });
        }
    });
})();
