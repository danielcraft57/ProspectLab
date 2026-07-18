/**
 * Page liste des analyses UX (@clea_ux).
 */
(function () {
    let allAnalyses = [];

    document.addEventListener('DOMContentLoaded', () => {
        loadAnalyses();
        setupEventListeners();

        const urlParams = new URLSearchParams(window.location.search);
        const autoUrl = urlParams.get('url');
        const autoStart = urlParams.get('auto_start') === 'true';
        const entrepriseId = urlParams.get('entreprise_id');

        if (autoUrl) {
            const urlInput = document.getElementById('ux-url');
            if (urlInput) {
                urlInput.value = autoUrl;
            }
            if (autoStart) {
                setTimeout(() => {
                    if (urlInput && urlInput.value) {
                        handleFormSubmit(null, autoUrl, entrepriseId);
                    }
                }, 500);
            }
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    });

    /**
     * Charge la liste des analyses UX depuis l'API.
     * @returns {Promise<void>}
     */
    async function loadAnalyses() {
        try {
            const response = await fetch('/api/analyses-ux');
            allAnalyses = await response.json();
            if (!Array.isArray(allAnalyses)) {
                allAnalyses = [];
            }
            renderAnalyses();
        } catch (error) {
            console.error('Erreur chargement analyses UX:', error);
            document.getElementById('analyses-container').innerHTML =
                '<p class="error">Erreur lors du chargement des analyses</p>';
        }
    }

    /**
     * Affiche les cartes d'analyses.
     */
    function renderAnalyses() {
        const container = document.getElementById('analyses-container');
        const n = allAnalyses.length;
        document.getElementById('results-count').textContent =
            n + ' analyse' + (n > 1 ? 's' : '') + ' UX trouvée' + (n > 1 ? 's' : '');

        if (n === 0) {
            container.innerHTML = '<p class="no-results">Aucune analyse UX disponible</p>';
            return;
        }

        container.innerHTML = allAnalyses.map(createAnalysisCard).join('');

        container.querySelectorAll('.btn-view-details').forEach((btn) => {
            btn.addEventListener('click', function () {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'), 10);
                if (!Number.isNaN(analysisId)) {
                    openUXModal(analysisId);
                }
            });
        });

        container.querySelectorAll('.btn-delete-analysis').forEach((btn) => {
            btn.addEventListener('click', function () {
                const analysisId = parseInt(this.getAttribute('data-analysis-id'), 10);
                if (confirm('Supprimer cette analyse UX ?')) {
                    deleteUXAnalysis(analysisId);
                }
            });
        });
    }

    /**
     * Carte résumé d'une analyse UX.
     * @param {Object} analysis
     * @returns {string}
     */
    function createAnalysisCard(analysis) {
        const date = new Date(analysis.date_analyse).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
        const score = analysis.score || 0;
        const scoreClass =
            score >= 80 ? 'score-excellent' : score >= 60 ? 'score-good' : score >= 40 ? 'score-medium' : 'score-low';

        let findingsCount = 0;
        let verdict = '';
        try {
            const findings = analysis.findings || (
                typeof analysis.findings_json === 'string'
                    ? JSON.parse(analysis.findings_json)
                    : analysis.findings_json
            );
            findingsCount = Array.isArray(findings) ? findings.length : 0;
            const summary = analysis.summary || (
                typeof analysis.summary_json === 'string'
                    ? JSON.parse(analysis.summary_json)
                    : analysis.summary_json
            );
            if (summary && summary.verdict) {
                verdict = summary.verdict;
            }
        } catch (e) {
            // ignore
        }

        return `
            <div class="analysis-card">
                <div class="analysis-card-header">
                    <h3>${escapeHtml(analysis.url || 'N/A')}</h3>
                    <span class="analysis-date">${date}</span>
                </div>
                <div class="analysis-card-body">
                    <div class="analysis-metrics">
                        <div class="metric">
                            <span class="metric-label">Score UX</span>
                            <span class="metric-value ${scoreClass}">${score}/100</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Findings</span>
                            <span class="metric-value ${findingsCount > 0 ? 'has-issues' : ''}">${findingsCount}</span>
                        </div>
                    </div>
                    ${verdict ? `<p class="analysis-verdict" style="margin-top:0.75rem;color:#475569;font-size:0.9rem;">${escapeHtml(verdict)}</p>` : ''}
                </div>
                <div class="analysis-card-footer">
                    <button class="btn btn-secondary btn-view-details" data-analysis-id="${analysis.id}">
                        <i class="fas fa-eye"></i> Voir détails
                    </button>
                    <button class="btn btn-danger btn-delete-analysis" data-analysis-id="${analysis.id}">
                        <i class="fas fa-trash"></i> Supprimer
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * @param {string} text
     * @returns {string}
     */
    function escapeHtml(text) {
        if (window.Formatters && typeof Formatters.escapeHtml === 'function') {
            return Formatters.escapeHtml(text);
        }
        const d = document.createElement('div');
        d.textContent = text == null ? '' : String(text);
        return d.innerHTML;
    }

    function setupEventListeners() {
        const form = document.getElementById('form-new-ux');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const url = (document.getElementById('ux-url').value || '').trim();
                if (!url) {
                    alert('Veuillez saisir une URL');
                    return;
                }
                handleFormSubmit(e, url, null);
            });
        }
        document.getElementById('ux-modal-close')?.addEventListener('click', closeUXModal);
        document.querySelector('#ux-modal .modal-overlay')?.addEventListener('click', closeUXModal);
    }

    /**
     * Lance l'analyse UX via Socket.IO.
     * @param {Event|null} e
     * @param {string} url
     * @param {string|number|null} entrepriseId
     */
    function handleFormSubmit(e, url, entrepriseId) {
        if (e) e.preventDefault();
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            url = 'https://' + url;
        }

        const btn = document.getElementById('btn-start-ux');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        const progressSection = document.getElementById('ux-progress');
        const progressBar = document.getElementById('ux-progress-bar');
        const progressMessage = document.getElementById('ux-progress-message');

        if (btn) btn.disabled = true;
        if (btnText) btnText.style.display = 'none';
        if (btnLoading) btnLoading.style.display = 'inline';
        if (progressSection) progressSection.style.display = 'block';
        if (progressBar) progressBar.style.width = '5%';
        if (progressMessage) progressMessage.textContent = 'Connexion...';

        const socket = window.wsManager && window.wsManager.socket;
        if (!socket) {
            alert('Connexion temps réel indisponible. Rechargez la page.');
            resetFormUi();
            return;
        }

        const onProgress = (data) => {
            if (progressBar) progressBar.style.width = (data.progress || 0) + '%';
            if (progressMessage) progressMessage.textContent = data.message || '';
        };
        const onComplete = () => {
            cleanup();
            resetFormUi();
            if (progressBar) progressBar.style.width = '100%';
            if (progressMessage) progressMessage.textContent = 'Terminé';
            loadAnalyses();
            setTimeout(() => {
                if (progressSection) progressSection.style.display = 'none';
            }, 1500);
        };
        const onError = (data) => {
            cleanup();
            resetFormUi();
            alert((data && data.error) || 'Erreur analyse UX');
            if (progressSection) progressSection.style.display = 'none';
        };
        const cleanup = () => {
            socket.off('ux_analysis_progress', onProgress);
            socket.off('ux_analysis_complete', onComplete);
            socket.off('ux_analysis_error', onError);
        };

        socket.on('ux_analysis_progress', onProgress);
        socket.on('ux_analysis_complete', onComplete);
        socket.on('ux_analysis_error', onError);

        const payload = { url };
        if (entrepriseId) payload.entreprise_id = parseInt(entrepriseId, 10) || entrepriseId;
        socket.emit('start_ux_analysis', payload);
    }

    function resetFormUi() {
        const btn = document.getElementById('btn-start-ux');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        if (btn) btn.disabled = false;
        if (btnText) btnText.style.display = 'inline';
        if (btnLoading) btnLoading.style.display = 'none';
    }

    /**
     * @param {number} analysisId
     */
    async function openUXModal(analysisId) {
        const modal = document.getElementById('ux-modal');
        const body = document.getElementById('ux-modal-body');
        const title = document.getElementById('ux-modal-title');
        if (!modal || !body) return;
        modal.style.display = 'flex';
        body.innerHTML = '<div class="loading">Chargement...</div>';
        try {
            const response = await fetch('/api/analyse-ux/' + analysisId);
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const analysis = await response.json();
            if (title) title.textContent = 'UX — ' + (analysis.url || '');
            body.innerHTML = renderUXDetails(analysis);
        } catch (err) {
            body.innerHTML = '<p class="error">Impossible de charger les détails</p>';
        }
    }

    function closeUXModal() {
        const modal = document.getElementById('ux-modal');
        if (modal) modal.style.display = 'none';
    }

    /**
     * @param {Object} analysis
     * @returns {string}
     */
    function renderUXDetails(analysis) {
        const score = analysis.score || 0;
        const scoreClass =
            score >= 80 ? 'score-excellent' : score >= 60 ? 'score-good' : score >= 40 ? 'score-medium' : 'score-low';
        let findings = analysis.findings || [];
        let summary = analysis.summary || {};
        try {
            if (!findings.length && analysis.findings_json) {
                findings = typeof analysis.findings_json === 'string'
                    ? JSON.parse(analysis.findings_json)
                    : analysis.findings_json;
            }
            if ((!summary || !Object.keys(summary).length) && analysis.summary_json) {
                summary = typeof analysis.summary_json === 'string'
                    ? JSON.parse(analysis.summary_json)
                    : analysis.summary_json;
            }
        } catch (e) {
            findings = [];
        }
        if (!Array.isArray(findings)) findings = [];

        const findingsHtml = findings.map((f) => `
            <div class="ux-finding" style="border:1px solid #e2e8f0;border-radius:8px;padding:0.75rem 1rem;margin-bottom:0.5rem;">
                <div style="display:flex;justify-content:space-between;gap:0.5rem;flex-wrap:wrap;">
                    <strong>${escapeHtml(f.title || f.tool || 'Finding')}</strong>
                    <span class="badge badge-${f.severity === 'high' ? 'danger' : f.severity === 'medium' ? 'warning' : 'secondary'}">${escapeHtml(f.severity || '')}</span>
                </div>
                <p style="margin:0.4rem 0;color:#475569;">${escapeHtml(f.message || '')}</p>
                ${f.recommendation ? `<p style="margin:0;font-size:0.9rem;"><em>Reco :</em> ${escapeHtml(f.recommendation)}</p>` : ''}
                ${f.chapter_title ? `<p style="margin:0.35rem 0 0;font-size:0.8rem;color:#94a3b8;">Ch.${f.chapter || ''} — ${escapeHtml(f.chapter_title)}</p>` : ''}
            </div>
        `).join('');

        return `
            <div class="ux-details">
                <div class="seo-score-section">
                    <h3>Score UX (@clea_ux)</h3>
                    <div class="score-display ${scoreClass}"><span class="score-value">${score}/100</span></div>
                    ${summary.verdict ? `<p>${escapeHtml(summary.verdict)}</p>` : ''}
                </div>
                <div class="seo-section">
                    <h3>Findings (${findings.length})</h3>
                    ${findingsHtml || '<p class="empty-state">Aucun finding</p>'}
                </div>
            </div>
        `;
    }

    /**
     * @param {number} analysisId
     */
    async function deleteUXAnalysis(analysisId) {
        try {
            const response = await fetch('/api/analyse-ux/' + analysisId, { method: 'DELETE' });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Erreur suppression');
            }
            closeUXModal();
            loadAnalyses();
        } catch (error) {
            alert('Erreur : ' + error.message);
        }
    }
})();
