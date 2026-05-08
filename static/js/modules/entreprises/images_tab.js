/**
 * Onglet Images de la fiche entreprise.
 * Expose: window.EntrepriseImagesTab
 */
(function (window) {
    'use strict';

    const state = {
        items: [],
    };

    function getItems() {
        return state.items;
    }

    async function load(entrepriseId, deps) {
        const Formatters = (deps && deps.Formatters) || window.Formatters;
        const updateModalTabCount = (deps && deps.updateModalTabCount) || window.updateModalTabCount;
        const container = document.getElementById('entreprise-images-container');
        if (!container) return;

        try {
            const response = await fetch(`/api/entreprise/${entrepriseId}/images`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const images = await response.json();

            if (!images || images.length === 0) {
                container.innerHTML = '<p class="empty-state">Aucune image trouvée pour ce site.</p>';
                if (typeof updateModalTabCount === 'function') updateModalTabCount('images', 0);
                state.items = [];
                return;
            }

            if (typeof updateModalTabCount === 'function') updateModalTabCount('images', images.length);

            const maxImages = 60;
            const limited = images.slice(0, maxImages);
            state.items = [];

            const esc = (t) => (Formatters && typeof Formatters.escapeHtml === 'function')
                ? Formatters.escapeHtml(String(t || ''))
                : String(t || '');

            let html = '<div class="entreprise-images-grid">';
            for (const img of limited) {
                const url = (img && img.url) ? img.url : img;
                const alt = (img && (img.alt_text || img.alt)) ? (img.alt_text || img.alt) : '';
                const idx = state.items.length;
                state.items.push({ url: String(url), label: alt ? String(alt) : 'Image' });
                html += `
                    <div class="entreprise-image-card">
                        <div class="entreprise-image-thumb">
                            <button
                                type="button"
                                data-image-open="1"
                                data-image-index="${idx}"
                                aria-label="Ouvrir image"
                                class="entreprise-image-thumb-btn"
                            >
                                <img src="${String(url)}" alt="${esc(alt)}" loading="lazy" onerror="this.style.display='none'" class="entreprise-image-thumb-img">
                            </button>
                        </div>
                        <div class="entreprise-image-meta">
                            ${alt
                                ? `<div class="entreprise-image-alt" title="${esc(alt)}">${esc(alt)}</div>`
                                : '<div class="entreprise-image-alt entreprise-image-alt--empty">Sans texte alternatif</div>'}
                        </div>
                    </div>
                `;
            }
            html += '</div>';
            container.innerHTML = html;
        } catch (e) {
            console.error('Erreur lors du chargement des images:', e);
            // On garde le contenu actuel si présent, sinon message simple
            if (!container.innerHTML || container.innerHTML.includes('Chargement')) {
                container.innerHTML = '<p class="empty-state">Impossible de charger les images.</p>';
            }
        }
    }

    window.EntrepriseImagesTab = {
        load,
        getItems,
    };
})(window);

