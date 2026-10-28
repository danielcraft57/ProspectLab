/**
 * Surveillance inbox Messenger (non lus + toast nouveau message).
 */
(function () {
    'use strict';

    const POLL_MS = 45000;
    const STORAGE_KEY = 'pl_fb_messenger_unread';

    let timer = null;
    let polling = false;

    function readStoredCount() {
        try {
            return parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10) || 0;
        } catch (_) {
            return 0;
        }
    }

    function writeStoredCount(n) {
        try {
            localStorage.setItem(STORAGE_KEY, String(n));
        } catch (_) {
            /* ignore */
        }
    }

    async function fetchSummary() {
        const resp = await fetch('/api/facebook-prospection/messenger/summary', {
            credentials: 'same-origin',
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || data.success === false) {
            return null;
        }
        return data;
    }

    function notifyNewMessages(summary, latest) {
        const unread = Number((summary && summary.unread_messages) || 0);
        const prev = readStoredCount();
        if (unread <= prev) {
            writeStoredCount(unread);
        } else {
            const delta = unread - prev;
            writeStoredCount(unread);
            const first = (latest && latest[0]) || {};
            const who = first.contact_name || 'Messenger';
            const preview = String(first.preview || '').slice(0, 120);
            if (window.Notifications && typeof Notifications.show === 'function') {
                Notifications.show(
                    (delta > 1 ? delta + ' nouveaux messages' : 'Nouveau message Messenger') +
                        ' — ' +
                        who +
                        (preview ? ' : ' + preview : ''),
                    'info',
                    'fab fa-facebook-messenger',
                );
            }
        }
        document.dispatchEvent(
            new CustomEvent('prospectlab:messenger-unread', {
                detail: { summary: summary, latest: latest },
            }),
        );
    }

    function updateNavBadge(summary) {
        const unread = Number((summary && summary.unread_threads) || 0);
        const el = document.getElementById('nav-messenger-unread');
        if (!el) return;
        if (unread > 0) {
            el.textContent = unread > 99 ? '99+' : String(unread);
            el.hidden = false;
        } else {
            el.hidden = true;
        }
    }

    async function tick() {
        if (polling) return;
        polling = true;
        try {
            const data = await fetchSummary();
            if (!data) return;
            const summary = data.summary || {};
            updateNavBadge(summary);
            notifyNewMessages(summary, data.latest_unread || []);
        } catch (_) {
            /* reseau / feature off */
        } finally {
            polling = false;
        }
    }

    function start() {
        if (timer) return;
        tick();
        timer = setInterval(tick, POLL_MS);
    }

    function stop() {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
    }

    window.ProspectLabMessengerPoll = {
        start: start,
        stop: stop,
        refresh: tick,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
