/**
 * UI "Variantes de landing" (onglet fiche entreprise).
 * Expose: window.EntrepriseLandingVariants
 */
(function (window) {
    'use strict';

    function _esc(Formatters, txt) {
        if (Formatters && typeof Formatters.escapeHtml === 'function') return Formatters.escapeHtml(String(txt || ''));
        return String(txt || '');
    }

    function setStatus(message, isError) {
        const status = document.getElementById('landing-variants-status');
        if (!status) return;
        if (!message) {
            status.style.display = 'none';
            status.textContent = '';
            status.classList.remove('is-error');
            return;
        }
        status.style.display = 'block';
        status.textContent = message;
        status.classList.toggle('is-error', !!isError);
    }

    function render(latest, deps) {
        const Formatters = (deps && deps.Formatters) || window.Formatters;
        const esc = (t) => _esc(Formatters, t);
        const variants = latest && Array.isArray(latest.variants) ? latest.variants : [];
        if (!variants.length) {
            return '<p class="empty-state">Aucun landing variant disponible pour le moment.</p>';
        }
        return variants.map((variant) => {
            const name = variant.variant_name || 'variant';
            const indexUrl = variant.index_url || '';
            const screenshots = variant.screenshots || {};
            const desktop = screenshots.desktop || '';
            const tablet = screenshots.tablet || '';
            const mobile = screenshots.mobile || '';
            const openAttrs = indexUrl
                ? `href="${esc(indexUrl)}" target="_blank" rel="noopener" aria-label="Ouvrir ${esc(name)}"`
                : 'aria-disabled="true"';
            return (
                `<section class="landing-variant-set">` +
                    `<div class="landing-variant-set-head">` +
                        `<strong class="landing-variant-set-title">${esc(name)}</strong>` +
                        (indexUrl
                            ? `<a class="landing-variant-set-link" ${openAttrs}>Ouvrir la variante</a>`
                            : `<span class="landing-variant-set-link is-disabled">Index indisponible</span>`) +
                    `</div>` +
                    `<div class="info-screenshots-grid landing-variant-grid">` +
                        _renderBigDeviceCard({ device: 'desktop', label: 'Desktop', url: desktop, name, esc }) +
                        _renderBigDeviceCard({ device: 'tablet', label: 'Tablette', url: tablet, name, esc }) +
                        _renderBigDeviceCard({ device: 'mobile', label: 'Mobile', url: mobile, name, esc }) +
                    `</div>` +
                `</section>`
            );
        }).join('');
    }

    function _renderBigDeviceCard({ device, label, url, name, esc }) {
        const has = !!url;
        const disabled = has ? '' : 'aria-disabled="true"';
        return (
            `<div class="info-screenshots-card ${has ? '' : 'info-screenshots-card--empty'}">` +
                `<div class="info-screenshots-card-head">` +
                    `<strong>${esc(label)}</strong>` +
                `</div>` +
                (has
                    ? `<button type="button" class="info-screenshot-thumb-btn landing-variant-preview-btn" data-lv-device="${device}" data-lv-url="${esc(url)}" ${disabled}>` +
                        `<img class="info-screenshots-img" src="${esc(url)}" alt="${esc(name)} ${esc(label)}" loading="lazy">` +
                      `</button>`
                    : `<div class="landing-variant-empty">Aucune capture</div>`) +
            `</div>`
        );
    }

    async function load(entrepriseId, deps) {
        const container = document.getElementById('landing-variants-content');
        if (!container) return;
        try {
            const res = await fetch(`/api/entreprise/${entrepriseId}/landing-variants`);
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error((data && data.error) || `HTTP ${res.status}`);
            }
            container.innerHTML = render(data.latest || {}, deps);
            setStatus('');
            _wireDevicePreviews(container);
        } catch (e) {
            console.error('Erreur chargement landing variants:', e);
            container.innerHTML = '<p class="empty-state">Impossible de charger les variantes.</p>';
            setStatus(e && e.message ? e.message : 'Erreur de chargement', true);
        }
    }

    function _wireDevicePreviews(root) {
        if (!root) return;
        root.addEventListener('click', (e) => {
            const btn = e.target && e.target.closest ? e.target.closest('[data-lv-url]') : null;
            if (!btn) return;
            const url = btn.getAttribute('data-lv-url') || '';
            if (!url) return;
            // Ouvre en zoom via la modale preview commune si dispo
            if (window.EntreprisePreviewModal && typeof window.EntreprisePreviewModal.openSingle === 'function') {
                const device = btn.getAttribute('data-lv-device') || 'device';
                window.EntreprisePreviewModal.openSingle(url, device);
                return;
            }
            window.open(url, '_blank');
        }, { passive: true });
    }

    async function start(entrepriseId, deps) {
        const Notifications = (deps && deps.Notifications) || window.Notifications;
        try {
            setStatus('Lancement de la génération...', false);
            const btn = document.getElementById('landing-variants-start-btn');
            if (btn) btn.disabled = true;
            const response = await fetch(`/api/entreprise/${entrepriseId}/landing-variants/start`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ variants: 4, free_mode: true }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success) {
                const errCode = (data && (data.error || data.code)) ? String(data.error || data.code) : '';
                const isAlreadyRunning =
                    response.status === 409 ||
                    errCode.toLowerCase() === 'already_running' ||
                    (data && typeof data.message === 'string' && data.message.toLowerCase().includes('déjà en cours'));
                const isUnreachableSite =
                    response.status === 400 &&
                    errCode.toLowerCase() === 'unreachable_site';

                if (isAlreadyRunning) {
                    const msg = (data && data.message) ? String(data.message) : 'Une génération est déjà en cours. Attendez la fin avant de relancer.';
                    setStatus(msg, false);
                    if (Notifications && typeof Notifications.show === 'function') Notifications.show(msg, 'warning');
                    return;
                }
                if (isUnreachableSite) {
                    const msg = (data && data.message) ? String(data.message) : 'Le site ne semble pas exister ou n’est pas résolvable.';
                    const btnRestore = document.getElementById('landing-variants-start-btn');
                    if (btnRestore) btnRestore.disabled = false;
                    setStatus(msg, true);
                    if (Notifications && typeof Notifications.show === 'function') Notifications.show(msg, 'warning');
                    return;
                }

                if (btn) btn.disabled = false;
                throw new Error((data && (data.message || data.error)) ? String(data.message || data.error) : `HTTP ${response.status}`);
            }
            setStatus('Génération lancée. Suivi en temps réel actif...', false);
        } catch (e) {
            setStatus(e && e.message ? e.message : 'Erreur de lancement', true);
            if (Notifications && typeof Notifications.show === 'function') {
                Notifications.show('Impossible de lancer la génération de landing variants', 'error');
            }
        }
    }

    window.EntrepriseLandingVariants = {
        setStatus,
        render,
        load,
        start,
    };
})(window);

