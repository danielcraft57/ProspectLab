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

    const INTENT_SUB_IDLE = 'Envoie un message pour lancer la classification.';

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
            throw new Error(data.error || data.detail || resp.statusText || 'Erreur API');
        }
        return data;
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
        messages.push({ role: 'user', text: text });
        renderMessages();
        setTyping(true);
        const payload = {
            text: text,
            recent_replies: recentReplies.slice(-6),
            recent_tags: recentTags.slice(-6),
            recent_user_texts: recentUserTexts.slice(-6),
            entreprise_id: entrepriseId,
        };
        try {
            const turn = await fetchJson('/api/facebook-prospection/tchatche', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const reply = String(turn.reply || '').trim() || '(pas de reponse)';
            const meta = [turn.tag, turn.engine || turn.source].filter(Boolean).join(' · ');
            messages.push({ role: 'bot', text: reply, meta: meta });
            recentUserTexts.push(text);
            recentReplies.push(reply);
            if (turn.tag) recentTags.push(String(turn.tag));
            renderMessages();
            renderVars(turn.vars);
            renderSide(turn);
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
        renderMessages();
        const intentEl = document.getElementById('tchatche-intent');
        if (intentEl) intentEl.textContent = '—';
        const sub = document.getElementById('tchatche-intent-sub');
        if (sub) sub.textContent = INTENT_SUB_IDLE;
        const preds = document.getElementById('tchatche-preds');
        if (preds) {
            preds.innerHTML =
                '<li class="tc-scores-empty">Aucun score tant que la conversation est vide.</li>';
        }
        renderVars(null);
    }

    /**
     * Affiche les variables injectees.
     * @param {Record<string, string>|null} varsMap Variables
     */
    function renderVars(varsMap) {
        const list = document.getElementById('tchatche-vars');
        if (!list) return;
        const keys = ['entreprise', 'nom', 'ville', 'website', 'telephone', 'secteur'];
        if (!varsMap) {
            list.innerHTML = '<li class="tc-var-hint">Lie une fiche CRM pour remplir les placeholders.</li>';
            return;
        }
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
                    esc(e.id) +
                    '" data-nom="' +
                    esc(e.nom || '') +
                    '" data-ville="' +
                    esc(e.ville || '') +
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
        loadStatus();
        bindDebugTabs();

        const form = document.getElementById('tchatche-form');
        const input = document.getElementById('tchatche-input');
        const resetBtn = document.getElementById('tchatche-reset');
        const sendBtn = document.getElementById('tchatche-send');
        const prompts = document.getElementById('tchatche-prompts');

        if (form && input) {
            form.addEventListener('submit', function (ev) {
                ev.preventDefault();
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
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', resetChat);
        }

        if (prompts) {
            prompts.addEventListener('click', function (ev) {
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
                setPicked({
                    id: btn.getAttribute('data-id'),
                    nom: btn.getAttribute('data-nom'),
                    ville: btn.getAttribute('data-ville'),
                });
                list.hidden = true;
                if (search) search.value = btn.getAttribute('data-nom') || '';
            });
        }
    });
})();
