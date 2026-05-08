/**
 * Modale de prévisualisation (carousel + zoom) utilisée dans la fiche entreprise.
 * Expose: window.EntreprisePreviewModal
 */
(function (window) {
    'use strict';

    const state = {
        items: [],
        index: -1,
        modalId: 'screenshot-preview-modal',
        keydownBound: false,
    };

    function _ensureModal() {
        let modal = document.getElementById(state.modalId);
        if (modal) return modal;

        modal = document.createElement('div');
        modal.id = state.modalId;
        modal.className = 'screenshot-preview-modal';
        modal.innerHTML = `
            <div class="screenshot-preview-panel">
                <div class="screenshot-preview-header">
                    <h4 id="screenshot-preview-title">Aperçu</h4>
                    <div class="screenshot-preview-header-actions">
                        <button type="button" class="screenshot-preview-nav screenshot-preview-prev" aria-label="Précédent"><i class="fas fa-chevron-left"></i></button>
                        <button type="button" class="screenshot-preview-nav screenshot-preview-next" aria-label="Suivant"><i class="fas fa-chevron-right"></i></button>
                        <button type="button" class="screenshot-preview-close" aria-label="Fermer">×</button>
                    </div>
                </div>
                <div class="screenshot-preview-body">
                    <img id="screenshot-preview-image" src="" alt="Aperçu">
                </div>
            </div>
        `;

        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.remove('show');
        });

        const closeBtn = modal.querySelector('.screenshot-preview-close');
        if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.remove('show'));

        const prevBtn = modal.querySelector('.screenshot-preview-prev');
        if (prevBtn) prevBtn.addEventListener('click', () => openByIndex(state.index - 1));

        const nextBtn = modal.querySelector('.screenshot-preview-next');
        if (nextBtn) nextBtn.addEventListener('click', () => openByIndex(state.index + 1));

        if (!state.keydownBound) {
            state.keydownBound = true;
            document.addEventListener('keydown', (e) => {
                if (!modal.classList.contains('show')) return;
                if (e.key === 'Escape') {
                    modal.classList.remove('show');
                    return;
                }
                if (e.key === 'ArrowLeft') openByIndex(state.index - 1);
                if (e.key === 'ArrowRight') openByIndex(state.index + 1);
            });
        }

        document.body.appendChild(modal);
        return modal;
    }

    function _updateNav(modal) {
        const prevBtn = modal.querySelector('.screenshot-preview-prev');
        const nextBtn = modal.querySelector('.screenshot-preview-next');
        const has = Array.isArray(state.items) && state.items.length > 0;
        const canPrev = has && state.index > 0;
        const canNext = has && state.index < state.items.length - 1;
        if (prevBtn) prevBtn.disabled = !canPrev;
        if (nextBtn) nextBtn.disabled = !canNext;
    }

    function open(items, index) {
        if (!Array.isArray(items) || items.length === 0) return;
        state.items = items;
        openByIndex(index);
    }

    function openByIndex(index) {
        if (!Array.isArray(state.items) || state.items.length === 0) return;
        const bounded = Math.max(0, Math.min(state.items.length - 1, Number(index) || 0));
        state.index = bounded;
        const item = state.items[bounded] || {};
        openSingle(item.url, item.label);
    }

    function openSingle(url, label) {
        const modal = _ensureModal();
        const img = modal.querySelector('#screenshot-preview-image');
        const title = modal.querySelector('#screenshot-preview-title');

        const u = String(url || '');
        const l = String(label || '').trim();

        if (img) img.src = u;
        if (img) img.alt = l ? `Aperçu ${l}` : 'Aperçu';
        if (title) title.textContent = l || 'Aperçu';

        _updateNav(modal);
        modal.classList.add('show');
    }

    window.EntreprisePreviewModal = {
        open,
        openByIndex,
        openSingle,
    };
})(window);

