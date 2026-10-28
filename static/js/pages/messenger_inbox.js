/**
 * Page Messagerie Facebook : liste, lecture, suggestions Qdrant, envoi serv1.
 */
(function () {
    'use strict';

    let activeThreadId = null;
    let unreadOnly = false;
    let pollTaskTimer = null;

    const esc = (t) =>
        window.Formatters && Formatters.escapeHtml
            ? Formatters.escapeHtml(String(t ?? ''))
            : String(t ?? '');

    async function fetchJson(url, options) {
        const resp = await fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}));
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || data.success === false) {
            throw new Error(data.error || resp.statusText || 'Erreur API');
        }
        return data;
    }

    function setListStatus(text) {
        const el = document.getElementById('messenger-list-status');
        if (el) el.textContent = text;
    }

    function setComposeStatus(text, isError) {
        const el = document.getElementById('messenger-compose-status');
        if (!el) return;
        el.textContent = text || '';
        el.className = 'messenger-compose-hint' + (isError ? ' messenger-compose-hint--err' : '');
    }

    function renderThreadList(threads) {
        const list = document.getElementById('messenger-thread-list');
        if (!list) return;
        if (!threads.length) {
            list.innerHTML = '';
            setListStatus('Aucune conversation — lance une sync.');
            return;
        }
        setListStatus(threads.length + ' conversation(s)');
        list.innerHTML = threads
            .map(function (t) {
                const unread = Number(t.unread_count) || 0;
                const active = Number(t.id) === Number(activeThreadId);
                return (
                    '<li><button type="button" class="messenger-thread-btn' +
                    (active ? ' is-active' : '') +
                    (unread ? ' is-unread' : '') +
                    '" data-thread-id="' +
                    esc(t.id) +
                    '">' +
                    '<span class="messenger-thread-name">' +
                    esc(t.contact_name || 'Contact') +
                    (unread ? '<span class="messenger-thread-badge">' + unread + '</span>' : '') +
                    '</span>' +
                    '<span class="messenger-thread-preview">' +
                    esc(String(t.preview || '').slice(0, 100)) +
                    '</span>' +
                    '</button></li>'
                );
            })
            .join('');
        list.querySelectorAll('.messenger-thread-btn').forEach(function (btn) {
            btn.onclick = function () {
                openThread(parseInt(btn.getAttribute('data-thread-id'), 10));
            };
        });
    }

    async function loadThreads() {
        const q = unreadOnly ? '?unread_only=1&limit=80' : '?limit=80';
        const data = await fetchJson('/api/facebook-prospection/messenger/conversations' + q);
        renderThreadList(data.threads || []);
    }

    function renderMessages(messages) {
        const box = document.getElementById('messenger-messages');
        if (!box) return;
        box.innerHTML = (messages || [])
            .map(function (m) {
                const out = String(m.direction) === 'outbound';
                return (
                    '<div class="messenger-bubble messenger-bubble--' +
                    (out ? 'out' : 'in') +
                    '">' +
                    esc(m.body_text || '') +
                    '</div>'
                );
            })
            .join('');
        box.scrollTop = box.scrollHeight;
    }

    function renderSuggestions(suggestions) {
        const wrap = document.getElementById('messenger-suggestions-wrap');
        const chips = document.getElementById('messenger-suggestion-chips');
        if (!wrap || !chips) return;
        if (!suggestions || !suggestions.length) {
            wrap.hidden = true;
            chips.innerHTML = '';
            return;
        }
        wrap.hidden = false;
        chips.innerHTML = suggestions
            .map(function (s, idx) {
                return (
                    '<button type="button" class="messenger-suggestion-chip" data-sidx="' +
                    idx +
                    '" title="Score ' +
                    esc(s.score) +
                    '">' +
                    esc(String(s.text || '').slice(0, 160)) +
                    '</button>'
                );
            })
            .join('');
        chips.querySelectorAll('.messenger-suggestion-chip').forEach(function (btn) {
            btn.onclick = function () {
                const idx = parseInt(btn.getAttribute('data-sidx'), 10);
                const s = suggestions[idx];
                const ta = document.getElementById('messenger-reply-text');
                if (ta && s) ta.value = s.text || '';
            };
        });
    }

    async function loadSuggestions(threadId) {
        try {
            const data = await fetchJson(
                '/api/facebook-prospection/messenger/conversations/' + threadId + '/suggestions',
                { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
            );
            renderSuggestions(data.suggestions || []);
            if (!(data.suggestions || []).length) {
                setComposeStatus('Qdrant : aucune proposition (seed ou GEMINI_API_KEY).', true);
            }
        } catch (e) {
            setComposeStatus(e.message || 'Suggestions indisponibles', true);
        }
    }

    async function openThread(threadId) {
        if (!threadId) return;
        activeThreadId = threadId;
        document.getElementById('messenger-empty').hidden = true;
        document.getElementById('messenger-conv').hidden = false;
        setComposeStatus('');

        await fetchJson('/api/facebook-prospection/messenger/conversations/' + threadId + '/read', {
            method: 'POST',
        }).catch(function () {});

        const threads = await fetchJson('/api/facebook-prospection/messenger/conversations?limit=80');
        const thread = (threads.threads || []).find(function (t) {
            return Number(t.id) === Number(threadId);
        });
        document.getElementById('messenger-conv-title').textContent =
            (thread && thread.contact_name) || 'Conversation';
        document.getElementById('messenger-conv-meta').textContent = thread && thread.entreprise_id
            ? 'Liée entreprise #' + thread.entreprise_id
            : '';

        const msgData = await fetchJson(
            '/api/facebook-prospection/messenger/conversations/' + threadId + '/messages',
        );
        renderMessages(msgData.messages || []);
        renderThreadList(threads.threads || []);
        await loadSuggestions(threadId);
        if (window.ProspectLabMessengerPoll && ProspectLabMessengerPoll.refresh) {
            ProspectLabMessengerPoll.refresh();
        }
    }

    async function pollCeleryTask(taskId, onDone) {
        clearTimeout(pollTaskTimer);
        let tries = 0;
        async function tick() {
            tries += 1;
            try {
                const st = await fetchJson('/api/celery-task/' + encodeURIComponent(taskId));
                if (st.state === 'SUCCESS' || st.state === 'FAILURE') {
                    onDone(st);
                    return;
                }
            } catch (_) {
                /* retry */
            }
            if (tries > 120) {
                setComposeStatus('Timeout suivi Celery.', true);
                return;
            }
            pollTaskTimer = setTimeout(tick, 2000);
        }
        tick();
    }

    async function sendReply(send) {
        if (!activeThreadId) return;
        const ta = document.getElementById('messenger-reply-text');
        const text = ta ? String(ta.value || '').trim() : '';
        if (!text) {
            setComposeStatus('Écris un message ou choisis une proposition.', true);
            return;
        }
        setComposeStatus(send ? 'Envoi en file Celery (serv2)…' : 'Dry-run en file (serv2)…');
        const data = await fetchJson(
            '/api/facebook-prospection/messenger/conversations/' + activeThreadId + '/reply',
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message_text: text, send: send, async: true }),
            },
        );
        pollCeleryTask(data.celery_task_id, function (st) {
            const ok = st.state === 'SUCCESS' && st.result && st.result.ok !== false;
            setComposeStatus(
                ok
                    ? send
                        ? 'Message envoyé (vérifie sur Facebook).'
                        : 'Dry-run OK (composeur serv1, pas d’envoi).'
                    : 'Échec : ' + ((st.result && st.result.error) || st.state),
                !ok,
            );
            if (ok) {
                openThread(activeThreadId);
            }
        });
    }

    async function syncInbox() {
        setListStatus('Sync en cours…');
        const data = await fetchJson('/api/facebook-prospection/messenger/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ async: true }),
        });
        pollCeleryTask(data.celery_task_id, function () {
            loadThreads();
            if (window.Notifications) {
                Notifications.show('Inbox Messenger synchronisée.', 'success', 'fab fa-facebook-messenger');
            }
        });
    }

    function bindUi() {
        const syncBtn = document.getElementById('messenger-sync-btn');
        if (syncBtn) syncBtn.onclick = syncInbox;

        document.getElementById('messenger-filter-all').onclick = function () {
            unreadOnly = false;
            loadThreads();
        };
        document.getElementById('messenger-filter-unread').onclick = function () {
            unreadOnly = true;
            loadThreads();
        };
        document.getElementById('messenger-suggest-btn').onclick = function () {
            if (activeThreadId) loadSuggestions(activeThreadId);
        };
        document.getElementById('messenger-dry-btn').onclick = function () {
            sendReply(false);
        };
        document.getElementById('messenger-send-btn').onclick = function () {
            sendReply(true);
        };

        document.addEventListener('prospectlab:messenger-unread', function () {
            loadThreads();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (!document.getElementById('messenger-app')) return;
        bindUi();
        loadThreads().catch(function (e) {
            setListStatus(e.message || 'Erreur chargement');
        });
    });
})();
