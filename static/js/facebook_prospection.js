/**
 * UI prospection Facebook (API /api/facebook-prospection).
 */
(function () {
    'use strict';

    const form = document.getElementById('fb-prospection-form');
    const statusEl = document.getElementById('fb-prospection-status');
    const resultsEl = document.getElementById('fb-prospection-results');
    const jobsList = document.getElementById('fb-jobs-list');

    const params = new URLSearchParams(window.location.search);
    const presetEntreprise = params.get('entreprise_id');
    if (presetEntreprise) {
        const input = document.getElementById('fb-entreprise-id');
        if (input) input.value = presetEntreprise;
    }

    function showStatus(message, kind) {
        if (!statusEl) return;
        statusEl.style.display = 'block';
        statusEl.className = 'status-message status-' + (kind || 'info');
        statusEl.textContent = message;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    async function loadJobs(entrepriseId) {
        if (!jobsList || !entrepriseId) return;
        const resp = await fetch('/api/facebook-prospection/entreprise/' + entrepriseId + '/jobs');
        const data = await resp.json();
        if (!data.success) {
            jobsList.innerHTML = '<p>' + escapeHtml(data.error || 'Erreur chargement') + '</p>';
            return;
        }
        resultsEl.style.display = 'block';
        const rows = (data.jobs || [])
            .map(function (j) {
                return (
                    '<div class="fb-job-row">' +
                    '<strong>#' +
                    j.id +
                    '</strong> ' +
                    escapeHtml(j.job_type) +
                    ' — ' +
                    escapeHtml(j.status) +
                    (j.search_query ? ' — ' + escapeHtml(j.search_query) : '') +
                    '</div>'
                );
            })
            .join('');
        jobsList.innerHTML = rows || '<p>Aucun job pour cette entreprise.</p>';
    }

    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const entrepriseId = parseInt(document.getElementById('fb-entreprise-id').value, 10);
            const query = document.getElementById('fb-search-query').value.trim();
            const jobType = document.getElementById('fb-job-type').value;
            const btn = document.getElementById('fb-submit-btn');
            btn.disabled = true;
            showStatus('Envoi du job…', 'info');
            try {
                const resp = await fetch('/api/facebook-prospection/jobs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        entreprise_id: entrepriseId,
                        job_type: jobType,
                        query: query || null,
                    }),
                });
                const data = await resp.json();
                if (!resp.ok || !data.success) {
                    showStatus(data.error || 'Echec API', 'error');
                    return;
                }
                showStatus(
                    'Job #' + data.job_id + ' en file Celery (' + (data.celery_task_id || '') + ')',
                    'success'
                );
                await loadJobs(entrepriseId);
            } catch (err) {
                showStatus(String(err), 'error');
            } finally {
                btn.disabled = false;
            }
        });
    }

    if (presetEntreprise) {
        loadJobs(parseInt(presetEntreprise, 10));
    }
})();
