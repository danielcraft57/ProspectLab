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

        nav.innerHTML = families.map(function(f, i) {
            return '<button type="button" class="api-doc-nav-item ' + (i === 0 ? 'is-active' : '') + '" data-family="' + f.id + '" role="tab">' + escapeHtml(f.name) + '</button>';
        }).join('');

        content.innerHTML = families.map(function(f, i) {
            var endpointsHtml = f.endpoints.map(function(ep) {
                var paramsHtml = '';
                if (ep.params && ep.params.length) {
                    paramsHtml = '<div class="api-doc-params"><strong>Paramètres</strong><table><thead><tr><th>Nom</th><th>Type</th><th>Description</th></tr></thead><tbody>' +
                        ep.params.map(function(p) { return '<tr><td><code>' + escapeHtml(p.name) + '</code></td><td>' + escapeHtml(p.type || '') + '</td><td>' + escapeHtml(p.desc || '') + '</td></tr>'; }).join('') +
                        '</tbody></table></div>';
                }
                if (ep.body) paramsHtml += '<div class="api-doc-params"><strong>Body</strong>: ' + escapeHtml(ep.body) + '</div>';
                var authHtml = f.auth ? '<div class="api-doc-auth"><i class="fas fa-lock"></i> ' + escapeHtml(f.auth) + '</div>' : '';
                var fullPath = f.basePath + (ep.path || '');
                return '<div class="api-doc-endpoint"><div class="api-doc-endpoint-header"><span class="api-doc-method ' + (ep.method || '').toLowerCase() + '">' + ep.method + '</span><span class="api-doc-path">' + escapeHtml(fullPath) + '</span></div><div class="api-doc-endpoint-desc">' + escapeHtml(ep.desc) + '</div>' + paramsHtml + authHtml + '</div>';
            }).join('');
            return '<section class="api-doc-section ' + (i === 0 ? 'is-visible' : '') + '" id="api-doc-page-' + f.id + '" role="tabpanel"><h3>' + escapeHtml(f.name) + '</h3><p class="section-desc">' + escapeHtml(f.description) + '</p><p class="section-desc"><strong>Base:</strong> <code>' + escapeHtml(f.basePath) + '</code></p>' + endpointsHtml + '</section>';
        }).join('');

        nav.querySelectorAll('.api-doc-nav-item').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var familyId = this.getAttribute('data-family');
                nav.querySelectorAll('.api-doc-nav-item').forEach(function(b) { b.classList.remove('is-active'); });
                this.classList.add('is-active');
                content.querySelectorAll('.api-doc-section').forEach(function(s) { s.classList.remove('is-visible'); });
                var panel = content.querySelector('#api-doc-page-' + familyId);
                if (panel) panel.classList.add('is-visible');
            });
        });
    }

    document.addEventListener('DOMContentLoaded', renderDocPage);
})();
