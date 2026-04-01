/**
 * Page Documentation API - rendu in-page
 */
(function() {
    function escapeHtml(text) {
        if (text == null) return '';
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function renderDocPage() {
        var families = typeof API_DOC_FAMILIES !== 'undefined' ? API_DOC_FAMILIES : [];
        var nav = document.getElementById('apiDocPageNav');
        var content = document.getElementById('apiDocPageContent');
        if (!nav || !content || !families.length) return;

        // Aplatit les familles -> sous-catégories pour réduire une liste trop longue
        var items = [];
        families.forEach(function(f) {
            if (Array.isArray(f.categories) && f.categories.length) {
                f.categories.forEach(function(c) {
                    items.push({
                        key: f.id + '__' + (c.id || c.name || 'all'),
                        family: f,
                        category: c
                    });
                });
            } else {
                items.push({
                    key: f.id + '__all',
                    family: f,
                    category: { id: 'all', name: f.name, endpoints: f.endpoints || [] }
                });
            }
        });

        if (!items.length) return;

        nav.innerHTML = items.map(function(item, i) {
            // Afficher uniquement le nom de sous-catégorie (pas le nom de famille).
            var label = item.category && item.category.name ? item.category.name : '';
            return '<button type="button" class="api-doc-nav-item ' + (i === 0 ? 'is-active' : '') + '" data-target="' + escapeHtml(item.key) + '" role="tab">' +
                escapeHtml(label) + '</button>';
        }).join('');

        function renderEndpointHtml(ep, f) {
            var paramsHtml = '';
            if (ep.params && ep.params.length) {
                paramsHtml = '<div class="api-doc-params"><strong>Paramètres</strong><table><thead><tr><th>Nom</th><th>Type</th><th>Description</th></tr></thead><tbody>' +
                    ep.params.map(function(p) { return '<tr><td><code>' + escapeHtml(p.name) + '</code></td><td>' + escapeHtml(p.type || '') + '</td><td>' + escapeHtml(p.desc || '') + '</td></tr>'; }).join('') +
                    '</tbody></table></div>';
            }
            if (ep.body) paramsHtml += '<div class="api-doc-params"><strong>Body</strong> : ' + escapeHtml(ep.body) + '</div>';
            var permHtml = ep.permission ? '<div class="api-doc-params" style="margin-top:6px"><strong>Permission(s)</strong> : ' + escapeHtml(ep.permission) + '</div>' : '';
            var authHtml = f.auth ? '<div class="api-doc-auth"><i class="fas fa-lock"></i> ' + escapeHtml(f.auth) + '</div>' : '';
            var fullPath = f.basePath + (ep.path || '');
            return '<div class="api-doc-endpoint"><div class="api-doc-endpoint-header"><span class="api-doc-method ' + (ep.method || '').toLowerCase() + '">' + ep.method + '</span><span class="api-doc-path">' + escapeHtml(fullPath) + '</span></div><div class="api-doc-endpoint-desc">' + escapeHtml(ep.desc) + '</div>' + permHtml + paramsHtml + authHtml + '</div>';
        }

        content.innerHTML = items.map(function(item, i) {
            var f = item.family;
            var c = item.category;
            var endpoints = Array.isArray(c.endpoints) ? c.endpoints : (f.endpoints || []);
            var endpointsHtml = endpoints.map(function(ep) { return renderEndpointHtml(ep, f); }).join('');
            var catExtra = c.categoryDesc ? '<p class="section-desc">' + escapeHtml(c.categoryDesc) + '</p>' : '';
            return '<section class="api-doc-section ' + (i === 0 ? 'is-visible' : '') + '" id="api-doc-page-' + escapeHtml(item.key) + '" role="tabpanel">' +
                '<h3>' + escapeHtml(item.category.name) + '</h3>' +
                '<p class="section-desc">' + escapeHtml(f.description) + '</p>' +
                '<p class="section-desc"><strong>Base :</strong> <code>' + escapeHtml(f.basePath) + '</code></p>' +
                catExtra +
                endpointsHtml +
                '</section>';
        }).join('');

        nav.querySelectorAll('.api-doc-nav-item').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var targetKey = this.getAttribute('data-target');
                nav.querySelectorAll('.api-doc-nav-item').forEach(function(b) { b.classList.remove('is-active'); });
                this.classList.add('is-active');
                content.querySelectorAll('.api-doc-section').forEach(function(s) { s.classList.remove('is-visible'); });
                var panel = content.querySelector('#api-doc-page-' + targetKey);
                if (panel) panel.classList.add('is-visible');
            });
        });
    }

    document.addEventListener('DOMContentLoaded', renderDocPage);
})();
