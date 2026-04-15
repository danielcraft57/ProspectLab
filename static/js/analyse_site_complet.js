/**
 * Page « Analyse site complet » : POST start + polling Celery + rapport + graphiques.
 * Persistance : localStorage (dernière URL + métadonnées de la dernière analyse réussie).
 */
(function () {
    let chartScores = null;
    let chartScrape = null;

    const LS_KEY = 'prospectlab_full_analysis_v1';

    function getExternalAnalyseShareBase() {
        const root = el('full-analysis-results');
        const raw = root && root.getAttribute('data-external-analyse-base');
        return (raw && raw.trim()) || 'https://danielcraft.fr/analyse';
    }

    function buildExternalAnalyseShareUrl(website) {
        const base = getExternalAnalyseShareBase().replace(/\/$/, '');
        return `${base}?website=${encodeURIComponent(String(website || '').trim())}&full=1`;
    }

    function readStoredState() {
        try {
            const raw = localStorage.getItem(LS_KEY);
            if (!raw) return null;
            const o = JSON.parse(raw);
            return o && typeof o === 'object' ? o : null;
        } catch {
            return null;
        }
    }

    function writeStoredState(patch) {
        try {
            const base = readStoredState() || {};
            const next = { ...base, ...patch, updatedAt: new Date().toISOString() };
            localStorage.setItem(LS_KEY, JSON.stringify(next));
        } catch (e) {
            console.warn('prospectlab_full_analysis: localStorage', e);
        }
    }

    function debounce(fn, ms) {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn(...args), ms);
        };
    }

    function el(id) {
        return document.getElementById(id);
    }

    function setProgress(pct) {
        const v = Math.min(100, Math.max(0, Math.round(Number(pct) || 0)));
        const bar = el('full-analysis-progress-bar');
        const pctEl = el('full-analysis-progress-pct');
        const track = document.querySelector('#full-analysis-progress .full-analysis-progress-track');
        if (bar) bar.style.width = `${v}%`;
        if (pctEl) pctEl.textContent = `${v}\u00a0%`;
        if (track) {
            track.setAttribute('aria-valuenow', String(v));
        }
    }

    function clearProgressError() {
        const box = el('full-analysis-progress-error');
        if (box) {
            box.hidden = true;
            box.textContent = '';
        }
    }

    function showProgressError(text) {
        const box = el('full-analysis-progress-error');
        if (box) {
            box.textContent = text || '';
            box.hidden = !text;
        }
    }

    function resetStepsRenderCache() {
        const ul = el('full-analysis-steps');
        if (ul) delete ul._plLastStepsHtml;
    }

    function renderSteps(meta) {
        const ul = el('full-analysis-steps');
        if (!ul) return;
        const labels = {
            scraping: 'Scraping',
            technical: 'Analyse technique',
            seo: 'SEO',
            phone_osint: 'OSINT téléphones',
            osint: 'OSINT',
            pentest: 'Pentest',
            init: 'Initialisation',
            done: 'Terminé',
        };
        const parts = [];
        // Statut courant / résumé : uniquement dans la liste (plus de doublon avec un paragraphe au-dessus).
        if (meta && meta.message) {
            if (meta.step === 'done') {
                parts.push(`<li class="step-summary">${meta.message}</li>`);
            } else if (meta.step && meta.step !== 'done') {
                parts.push(`<li class="step-current">${meta.message}</li>`);
            }
        }
        const steps = (meta && meta.steps) || {};
        Object.keys(labels).forEach((key) => {
            if (key === 'init' || key === 'done') return;
            const raw = steps[key];
            if (raw === undefined) return;
            const ok = raw === 'ok';
            const rawLower = raw && String(raw).toLowerCase();
            const cls = ok
                ? 'done'
                : rawLower && rawLower.includes('erreur')
                  ? 'err'
                  : rawLower && rawLower.includes('désactiv')
                    ? 'skip'
                    : '';
            parts.push(`<li class="${cls}"><strong>${labels[key]} :</strong> ${raw}</li>`);
        });
        const html = parts.join('') || '<li>…</li>';
        // Évite de remplacer le DOM à chaque poll si rien n’a changé : sinon innerHTML recrée le <li>
        // et relance les @keyframes sur .step-current → effet « clignotement ».
        if (ul._plLastStepsHtml === html) {
            return;
        }
        ul._plLastStepsHtml = html;
        ul.innerHTML = html;
    }

    async function pollTask(taskId, opts = {}) {
        const intervalMs = 1500;
        const maxPolls = 4800;
        const entrepriseName = String(opts.entrepriseName || '').trim() || 'Entreprise';
        const announced = {
            scraping: { started: false, done: false, skipped: false, error: false },
            technical: { started: false, done: false, skipped: false, error: false },
            seo: { started: false, done: false, skipped: false, error: false },
            phone_osint: { started: false, done: false, skipped: false, error: false },
            osint: { started: false, done: false, skipped: false, error: false },
            pentest: { started: false, done: false, skipped: false, error: false },
        };
        for (let i = 0; i < maxPolls; i++) {
            const res = await fetch(`/api/celery-task/${encodeURIComponent(taskId)}`, {
                credentials: 'same-origin',
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.error || `Erreur HTTP ${res.status} lors du suivi de la tâche.`);
            }
            if (data.state === 'PENDING') {
                setProgress(5);
                const pendingHint =
                    i >= 40
                        ? ' Vérifiez côté serveur que le worker Celery écoute la file indiquée par CELERY_FULL_ANALYSIS_QUEUE (souvent « technical », dans CELERY_WORKER_QUEUES).'
                        : '';
                renderSteps({ step: 'init', message: `Tâche en file…${pendingHint}` });
            } else if (data.state === 'PROGRESS' && data.meta) {
                const m = data.meta;
                setProgress(m.progress != null ? m.progress : 10);
                renderSteps(m);
                const currentStep = String(m.step || '').trim();
                if (announced[currentStep] && !announced[currentStep].started) {
                    announced[currentStep].started = true;
                    notifyFullAnalysis(
                        `${entrepriseName} : ${moduleLabel(currentStep)} en cours`,
                        'info'
                    );
                }
                const steps = (m && m.steps) || {};
                Object.keys(announced).forEach((key) => {
                    const raw = steps[key];
                    if (raw == null) return;
                    const st = parseStepStatus(raw);
                    if (st === 'done' && !announced[key].done) {
                        announced[key].done = true;
                        notifyFullAnalysis(`${entrepriseName} : ${moduleLabel(key)} terminé`, 'success');
                    } else if (st === 'skipped' && !announced[key].skipped) {
                        announced[key].skipped = true;
                        notifyFullAnalysis(`${entrepriseName} : ${moduleLabel(key)} désactivé`, 'warning');
                    } else if (st === 'error' && !announced[key].error) {
                        announced[key].error = true;
                        notifyFullAnalysis(`${entrepriseName} : ${moduleLabel(key)} en erreur`, 'error');
                    }
                });
            } else if (data.state === 'SUCCESS') {
                setProgress(100);
                const result = data.result || {};
                renderSteps({
                    step: 'done',
                    message:
                        result.message ||
                        'Tous les modules sélectionnés ont été exécutés (voir le détail ci-dessous).',
                    steps: result.steps,
                });
                notifyFullAnalysis(`${entrepriseName} : analyse complète terminée`, 'success');
                return result;
            } else if (
                data.state === 'FAILURE' ||
                data.state === 'REVOKED' ||
                data.state === 'REJECTED'
            ) {
                notifyFullAnalysis(`${entrepriseName} : analyse complète en erreur`, 'error');
                throw new Error(data.error || 'La tâche a échoué ou a été annulée.');
            }
            await new Promise((r) => setTimeout(r, intervalMs));
        }
        throw new Error('Délai d’attente dépassé pour la tâche d’analyse.');
    }

    function chartThemeColors() {
        const dark = document.body && document.body.getAttribute('data-theme') === 'dark';
        return {
            text: dark ? '#cbd5e1' : '#64748b',
            grid: dark ? 'rgba(148, 163, 184, 0.15)' : 'rgba(0, 0, 0, 0.06)',
        };
    }

    function buildCharts(taskSummary, report) {
        const theme = chartThemeColors();
        let scores = (taskSummary && taskSummary.scores) || {};
        const hasScores = Object.values(scores).some((v) => v != null && v !== '');
        if (!hasScores && report) {
            const tech = report.technical && report.technical.latest;
            const seoRow = report.seo && report.seo.latest;
            const pent = report.pentest && report.pentest.latest;
            scores = {
                technical_security_score: tech && tech.security_score,
                technical_performance_score: tech && tech.performance_score,
                seo_score: seoRow && seoRow.score,
                pentest_risk_score: pent && pent.risk_score,
            };
        }
        const techSec = scores.technical_security_score;
        const techPerf = scores.technical_performance_score;
        const seo = scores.seo_score;
        const pentestRisk = scores.pentest_risk_score;

        const ctxS = el('chart-scores');
        if (ctxS && typeof Chart !== 'undefined') {
            if (chartScores) chartScores.destroy();
            chartScores = new Chart(ctxS, {
                type: 'bar',
                data: {
                    labels: ['Sécurité (tech)', 'Performance', 'Score SEO', 'Risque pentest'],
                    datasets: [
                        {
                            label: 'Valeur',
                            data: [
                                techSec != null ? techSec : 0,
                                techPerf != null ? techPerf : 0,
                                seo != null ? seo : 0,
                                pentestRisk != null ? pentestRisk : 0,
                            ],
                            backgroundColor: ['#6366f1', '#0ea5e9', '#22c55e', '#f97316'],
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        subtitle: {
                            display: true,
                            text: 'Risque pentest : plus la valeur est élevée, plus le risque est fort.',
                            padding: { bottom: 8 },
                            color: theme.text,
                        },
                    },
                    scales: {
                        x: {
                            ticks: { color: theme.text },
                            grid: { color: theme.grid },
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: { color: theme.text },
                            grid: { color: theme.grid },
                        },
                    },
                },
            });
        }

        const sc =
            (taskSummary && taskSummary.scrape_counts) ||
            (report && report.scraping && report.scraping.latest && {
                emails: report.scraping.latest.total_emails,
                people: report.scraping.latest.total_people,
                phones: report.scraping.latest.total_phones,
                images: report.scraping.latest.total_images,
            }) ||
            {};

        const ctxC = el('chart-scrape');
        if (ctxC && typeof Chart !== 'undefined') {
            if (chartScrape) chartScrape.destroy();
            chartScrape = new Chart(ctxC, {
                type: 'doughnut',
                data: {
                    labels: ['Emails', 'Personnes', 'Téléphones', 'Images'],
                    datasets: [
                        {
                            data: [
                                Number(sc.emails) || 0,
                                Number(sc.people) || 0,
                                Number(sc.phones) || 0,
                                Number(sc.images) || 0,
                            ],
                            backgroundColor: ['#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b'],
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '58%',
                    layout: { padding: 6 },
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: theme.text,
                                boxWidth: 12,
                                padding: 10,
                            },
                        },
                    },
                },
            });
        }
    }

    function showGallery(urls) {
        const box = el('full-analysis-gallery');
        const empty = el('full-analysis-gallery-empty');
        if (!box) return;
        box.innerHTML = '';
        const list = urls && urls.length ? urls : [];
        if (!list.length) {
            if (empty) empty.style.display = 'block';
            return;
        }
        if (empty) empty.style.display = 'none';
        list.forEach((u) => {
            const img = document.createElement('img');
            img.src = u;
            img.alt = 'Aperçu image scrapée';
            img.loading = 'lazy';
            // Ne pas forcer no-referrer : beaucoup de sites WordPress / CDN refusent sans Referer → échec chargement.
            img.onload = function () {
                this.classList.remove('gallery-img-error');
            };
            img.onerror = function () {
                this.classList.add('gallery-img-error');
                this.alt = 'Image non affichable (blocage distant ou URL invalide)';
            };
            box.appendChild(img);
        });
    }

    function safeStringify(obj) {
        try {
            return JSON.stringify(obj, null, 2);
        } catch (e) {
            return String(obj);
        }
    }

    function escapeHtml(text) {
        if (text == null || text === '') return '';
        const span = document.createElement('span');
        span.textContent = String(text);
        return span.innerHTML;
    }

    function setTextContent(id, text) {
        const node = el(id);
        if (node) node.textContent = text || '';
    }

    function notifyFullAnalysis(message, type = 'info') {
        try {
            if (window.Notifications && typeof window.Notifications.show === 'function') {
                window.Notifications.show(message, type);
            }
        } catch (e) {}
    }

    function parseStepStatus(raw) {
        const s = String(raw == null ? '' : raw).trim().toLowerCase();
        if (!s) return 'unknown';
        if (s === 'ok') return 'done';
        if (s.includes('erreur')) return 'error';
        if (s.includes('désactiv') || s.includes('desactiv')) return 'skipped';
        return 'running';
    }

    function moduleLabel(stepKey) {
        const map = {
            scraping: 'scraping',
            technical: 'analyse technique',
            seo: 'analyse SEO',
            phone_osint: 'OSINT téléphones',
            osint: 'analyse OSINT',
            pentest: 'analyse pentest',
        };
        return map[stepKey] || stepKey;
    }

    function initExclusiveReportAccordion() {
        const root = el('full-analysis-report-accordion');
        if (!root) return;
        const items = root.querySelectorAll('details.report-accordion-item');
        items.forEach((det) => {
            det.addEventListener('toggle', () => {
                if (!det.open) return;
                items.forEach((other) => {
                    if (other !== det) other.open = false;
                });
            });
        });
    }

    function statPill(label, value) {
        if (value === undefined || value === null || value === '') return '';
        return `<span class="report-stat"><strong>${escapeHtml(String(value))}</strong> ${escapeHtml(label)}</span>`;
    }

    function kv(label, value) {
        if (value === undefined || value === null || value === '') return '';
        return `<div class="report-kv"><span class="report-k">${escapeHtml(label)}</span><span class="report-v">${escapeHtml(String(value))}</span></div>`;
    }

    function subtitle(title) {
        return `<h4 class="report-subtitle">${escapeHtml(title)}</h4>`;
    }

    function scrapedLocationRows(loc) {
        if (!loc || typeof loc !== 'object') return [];
        const rows = [];
        if (loc.street_address) rows.push(['Adresse', String(loc.street_address)]);
        const cityLine = [loc.postal_code, loc.locality].filter(Boolean).join(' ').trim();
        if (cityLine) rows.push(['Code postal / ville', cityLine]);
        if (loc.country) rows.push(['Pays', String(loc.country)]);
        if (loc.telephone) rows.push(['Téléphone (lieu)', String(loc.telephone)]);
        if (loc.latitude != null && loc.longitude != null) {
            rows.push(['Coordonnées', `${loc.latitude}, ${loc.longitude}`]);
        }
        if (loc.source) rows.push(['Source lieu', String(loc.source)]);
        return rows;
    }

    function socialProfileEntries(social) {
        if (!social || typeof social !== 'object') return [];
        const out = [];
        Object.keys(social).forEach((platform) => {
            const urls = social[platform];
            const arr = Array.isArray(urls) ? urls : urls ? [urls] : [];
            arr.forEach((item) => {
                const u = typeof item === 'object' && item ? item.url : item;
                if (u) out.push({ platform: String(platform), url: String(u) });
            });
        });
        return out;
    }

    function safeExternalLink(href, label) {
        const h = String(href || '').trim();
        if (!h) return '';
        const schemeOk = /^https?:\/\//i.test(h);
        if (!schemeOk) return escapeHtml(label || h);
        return `<a href="${escapeHtml(h)}" target="_blank" rel="noopener noreferrer">${escapeHtml(
            label || h
        )}</a>`;
    }

    function renderScrapingHuman(container, data) {
        if (!container) return;
        if (!data) {
            container.innerHTML = '<p class="report-empty">Aucun scraping en base pour cette entreprise.</p>';
            setTextContent('full-analysis-badge-scraping', 'Non disponible');
            return;
        }
        const emails = data.emails || [];
        const people = data.people || [];
        const phones = data.phones || [];
        const imgs = data.images || [];
        const forms = data.forms || [];
        const meta = data.metadata && typeof data.metadata === 'object' ? data.metadata : {};
        const scrapedLoc = meta.scraped_location;
        const og = meta.open_graph && typeof meta.open_graph === 'object' ? meta.open_graph : {};
        const te = Number(data.total_emails != null ? data.total_emails : emails.length) || 0;
        const tp = Number(data.total_people != null ? data.total_people : people.length) || 0;
        const tph = Number(data.total_phones != null ? data.total_phones : phones.length) || 0;
        const tim = Number(data.total_images != null ? data.total_images : imgs.length) || 0;
        const tf = Number(data.total_forms != null ? data.total_forms : forms.length) || 0;
        const dur = data.duration != null ? `${Math.round(Number(data.duration))} s` : null;
        const visited = data.visited_urls;
        const parts = [];
        parts.push('<div class="report-block report-block--head">');
        parts.push('<div class="report-stats">');
        parts.push(statPill('emails', te));
        parts.push(statPill('personnes', tp));
        parts.push(statPill('téléphones', tph));
        parts.push(statPill('images', tim));
        if (tf) parts.push(statPill('formulaires', tf));
        if (dur) parts.push(statPill('durée', dur));
        parts.push('</div>');
        parts.push('<div class="report-kv-grid report-kv-grid--stack">');
        if (data.url) parts.push(kv('URL scrapée', data.url));
        if (visited != null && visited !== '') {
            const disp = Array.isArray(visited) ? `${visited.length} URL collectée(s)` : String(visited);
            parts.push(kv('Pages / URLs', disp));
        }
        if (data.date_modification || data.date_creation)
            parts.push(kv('Dernière mise à jour', data.date_modification || data.date_creation));
        parts.push('</div></div>');

        const locRows = scrapedLocationRows(scrapedLoc);
        const socialEntries = socialProfileEntries(data.social_profiles);
        const hasContactBlock =
            locRows.length ||
            og.site_name ||
            og.title ||
            socialEntries.length ||
            forms.length ||
            phones.length;

        if (hasContactBlock) {
            parts.push('<div class="report-block report-block--panel">');
            parts.push(subtitle('Contact & lieu'));
            parts.push('<div class="report-kv-grid report-kv-grid--stack">');
            if (og.site_name) parts.push(kv('Site (meta)', og.site_name));
            if (og.title && og.title !== og.site_name) parts.push(kv('Titre page', og.title));
            if (og.description) {
                const desc =
                    String(og.description).length > 220
                        ? `${String(og.description).slice(0, 217)}…`
                        : og.description;
                parts.push(kv('Description', desc));
            }
            locRows.forEach(([k, v]) => {
                parts.push(kv(k, v));
            });
            parts.push('</div>');

            if (socialEntries.length) {
                parts.push('<div class="report-subsection">');
                parts.push(subtitle('Réseaux sociaux'));
                parts.push('<ul class="report-list report-list-compact">');
                socialEntries.slice(0, 14).forEach(({ platform, url }) => {
                    parts.push(
                        `<li><span class="report-social-plat">${escapeHtml(platform)}</span> — ${safeExternalLink(
                            url,
                            url
                        )}</li>`
                    );
                });
                parts.push('</ul></div>');
            }

            if (phones.length) {
                parts.push('<div class="report-subsection">');
                parts.push(subtitle('Téléphones (détail)'));
                parts.push('<ul class="report-list report-list-compact">');
                phones.slice(0, 12).forEach((row) => {
                    const ph =
                        typeof row === 'object' && row
                            ? row.phone || row.phone_e164 || row.value
                            : String(row);
                    const locHint =
                        typeof row === 'object' && row && (row.location || row.carrier || row.line_type)
                            ? [row.location, row.carrier, row.line_type].filter(Boolean).join(' · ')
                            : '';
                    const page =
                        typeof row === 'object' && row && row.page_url ? String(row.page_url) : '';
                    let line = ph ? `<strong>${escapeHtml(String(ph))}</strong>` : '—';
                    if (locHint) line += ` <span class="report-phone-meta">${escapeHtml(locHint)}</span>`;
                    if (page)
                        line += `<div class="report-phone-page">${safeExternalLink(page, 'Page source')}</div>`;
                    parts.push(`<li>${line}</li>`);
                });
                parts.push('</ul></div>');
            }

            if (forms.length) {
                parts.push('<div class="report-subsection">');
                parts.push(subtitle('Formulaires repérés'));
                parts.push('<ul class="report-list report-list-compact">');
                forms.slice(0, 10).forEach((f) => {
                    if (!f || typeof f !== 'object') return;
                    const method = (f.method || 'GET').toUpperCase();
                    const fc = f.fields_count != null ? `${f.fields_count} champ(s)` : '';
                    const bits = [method, fc].filter(Boolean).join(' · ');
                    let line = bits ? `<strong>${escapeHtml(bits)}</strong>` : '';
                    if (f.page_url) {
                        line += `<div class="report-form-url">${safeExternalLink(
                            f.page_url,
                            f.page_url.length > 72 ? `${f.page_url.slice(0, 69)}…` : f.page_url
                        )}</div>`;
                    }
                    if (f.action_url && f.action_url !== f.page_url) {
                        line += `<div class="report-form-action">${escapeHtml(String(f.action_url))}</div>`;
                    }
                    parts.push(`<li>${line}</li>`);
                });
                parts.push('</ul></div>');
            }
            parts.push('</div>');
        }

        if (emails.length) {
            parts.push('<div class="report-block report-block--list">');
            parts.push(subtitle('Extraits d’emails'));
            parts.push('<ul class="report-list report-list-chips">');
            emails.slice(0, 12).forEach((row) => {
                const addr = typeof row === 'object' && row ? row.email || row.adresse || '' : String(row);
                if (addr) parts.push(`<li>${escapeHtml(addr)}</li>`);
            });
            parts.push('</ul></div>');
        }
        if (people.length) {
            parts.push('<div class="report-block report-block--list">');
            parts.push(subtitle('Personnes repérées'));
            parts.push('<ul class="report-list">');
            people.slice(0, 10).forEach((p) => {
                const name =
                    (p && (p.name || [p.prenom, p.nom].filter(Boolean).join(' '))) || '—';
                const metaBits = [];
                if (p && p.title) metaBits.push(escapeHtml(String(p.title)));
                if (p && p.email) {
                    const em = String(p.email).trim();
                    metaBits.push(
                        `<a href="mailto:${escapeHtml(em)}" class="report-inline-link">${escapeHtml(em)}</a>`
                    );
                }
                if (p && p.linkedin_url) {
                    metaBits.push(
                        safeExternalLink(String(p.linkedin_url).trim(), 'LinkedIn')
                    );
                }
                const sub =
                    metaBits.length > 0
                        ? `<div class="report-person-meta">${metaBits.join(' · ')}</div>`
                        : '';
                const pageLn =
                    p && p.page_url
                        ? `<div class="report-person-page">${safeExternalLink(
                              String(p.page_url),
                              'Page source'
                          )}</div>`
                        : '';
                parts.push(
                    `<li><span class="report-person-name">${escapeHtml(name)}</span>${sub}${pageLn}</li>`
                );
            });
            parts.push('</ul></div>');
        }
        container.innerHTML = parts.join('');
        const bits = [];
        if (te) bits.push(`${te} email(s)`);
        if (tp) bits.push(`${tp} pers.`);
        if (tf) bits.push(`${tf} formulaire${tf > 1 ? 's' : ''}`);
        setTextContent('full-analysis-badge-scraping', bits.length ? bits.join(' · ') : 'Données présentes');
    }

    function renderTechnicalHuman(container, data) {
        if (!container) return;
        if (!data) {
            container.innerHTML = '<p class="report-empty">Pas d’analyse technique en base.</p>';
            setTextContent('full-analysis-badge-technical', 'Non disponible');
            return;
        }
        const parts = ['<div class="report-stats">'];
        if (data.security_score != null && data.security_score !== '')
            parts.push(statPill('/100 sécurité', data.security_score));
        if (data.performance_score != null && data.performance_score !== '')
            parts.push(statPill('/100 perfs', data.performance_score));
        parts.push('</div><div class="report-kv-grid">');
        [
            ['Stack / CMS', data.cms],
            ['Version CMS', data.cms_version],
            ['CDN / hébergeur', data.cdn || data.hosting_provider],
            ['Domaine', data.domain],
            ['Registrar', data.domain_registrar],
            ['Création domaine', data.domain_creation_date],
            ['Serveur web', data.server],
            ['Date d’analyse', data.date_analyse],
        ].forEach(([k, v]) => {
            if (v != null && v !== '') parts.push(kv(k, v));
        });
        parts.push('</div>');
        container.innerHTML = parts.join('');
        const cms = data.cms ? String(data.cms) : '';
        const sec = data.security_score != null ? `Sec. ${data.security_score}` : '';
        setTextContent('full-analysis-badge-technical', [cms, sec].filter(Boolean).join(' · ') || 'Voir le détail');
    }

    function renderSeoHuman(container, data) {
        if (!container) return;
        if (!data) {
            container.innerHTML = '<p class="report-empty">Pas d’analyse SEO en base.</p>';
            setTextContent('full-analysis-badge-seo', 'Non disponible');
            return;
        }
        const parts = ['<div class="report-stats">'];
        if (data.score != null && data.score !== '') parts.push(statPill('/100 score', data.score));
        parts.push('</div><div class="report-kv-grid">');
        if (data.url) parts.push(kv('URL analysée', data.url));
        if (data.date_analyse) parts.push(kv('Date', data.date_analyse));
        if (data.error || data.erreur) parts.push(kv('Message', data.error || data.erreur));
        parts.push('</div>');
        const sum = data.summary;
        if (sum && typeof sum === 'object' && Object.keys(sum).length) {
            parts.push(subtitle('Synthèse'));
            parts.push('<div class="report-kv-grid">');
            Object.entries(sum).slice(0, 12).forEach(([k, v]) => {
                if (v != null && typeof v !== 'object') parts.push(kv(k.replace(/_/g, ' '), v));
            });
            parts.push('</div>');
        }
        container.innerHTML = parts.join('');
        const sc = data.score != null ? `Score ${data.score}` : '';
        setTextContent('full-analysis-badge-seo', sc || 'SEO en base');
    }

    function renderGenericHuman(container, data, badgeId, emptyMsg, labelMap) {
        if (!container) return;
        if (!data) {
            container.innerHTML = `<p class="report-empty">${escapeHtml(emptyMsg)}</p>`;
            if (badgeId) setTextContent(badgeId, 'Non disponible');
            return;
        }
        const skip = new Set([
            'id',
            'entreprise_id',
            'raw',
            'result_json',
            'details_json',
            'metadata_json',
        ]);
        const parts = ['<div class="report-kv-grid">'];
        const prim = [];
        let rowCount = 0;
        Object.keys(data).forEach((key) => {
            if (skip.has(key)) return;
            const v = data[key];
            if (v == null || v === '') return;
            if (typeof v === 'object') return;
            rowCount += 1;
            const lbl = (labelMap && labelMap[key]) || key.replace(/_/g, ' ');
            const cap = lbl.charAt(0).toUpperCase() + lbl.slice(1);
            parts.push(kv(cap, v));
            prim.push(String(v).slice(0, 40));
        });
        parts.push('</div>');
        if (rowCount === 0) {
            container.innerHTML =
                '<p class="report-empty">Données surtout structurées (listes, objets). Utilisez « JSON brut » ci-dessous pour tout voir.</p>';
        } else {
            container.innerHTML = parts.join('');
        }
        if (badgeId) {
            const b =
                data.risk_score != null
                    ? `Risque ${data.risk_score}`
                    : data.status
                      ? String(data.status)
                      : prim.slice(0, 2).join(' · ');
            setTextContent(badgeId, b || 'Voir le détail');
        }
    }

    function fillReportPanels(report) {
        const setPre = (id, val) => {
            const n = el(id);
            if (n) n.textContent = val ? safeStringify(val) : '—';
        };
        if (!report) return;

        const scraping = report.scraping && report.scraping.latest;
        const technical = report.technical && report.technical.latest;
        const seo = report.seo && report.seo.latest;
        const osint = report.osint && report.osint.latest;
        const pentest = report.pentest && report.pentest.latest;

        renderScrapingHuman(el('full-analysis-human-scraping'), scraping);
        renderTechnicalHuman(el('full-analysis-human-technical'), technical);
        renderSeoHuman(el('full-analysis-human-seo'), seo);
        renderGenericHuman(
            el('full-analysis-human-osint'),
            osint,
            'full-analysis-badge-osint',
            'Pas d’analyse OSINT en base.',
            {
                domain: 'Domaine',
                date_analyse: "Date d'analyse",
                date_creation: 'Création',
            }
        );
        renderGenericHuman(
            el('full-analysis-human-pentest'),
            pentest,
            'full-analysis-badge-pentest',
            'Pas d’analyse pentest en base.',
            {
                risk_score: 'Score de risque',
                risk_level: 'Niveau de risque',
                date_analyse: "Date d'analyse",
            }
        );

        setPre('full-analysis-json-scraping', scraping);
        setPre('full-analysis-json-technical', technical);
        setPre('full-analysis-json-seo', seo);
        setPre('full-analysis-json-osint', osint);
        setPre('full-analysis-json-pentest', pentest);
    }

    async function loadReport(website, taskSummary) {
        const q = encodeURIComponent(website);
        const res = await fetch(`/api/website-analysis?website=${q}&full=1`, { credentials: 'same-origin' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || `Rapport HTTP ${res.status}`);
        }
        const report = await res.json();
        fillReportPanels(report);
        buildCharts(taskSummary, report);
        return report;
    }

    function taskSummaryFromSnapshot(st) {
        if (!st || !st.snapshot) return { entreprise_id: st && st.entreprise_id };
        return {
            entreprise_id: st.entreprise_id,
            scores: st.snapshot.scores || {},
            scrape_counts: st.snapshot.scrape_counts || {},
            image_urls_sample: st.snapshot.image_urls_sample || [],
            steps: st.snapshot.steps || {},
        };
    }

    async function showFullResults(website, entrepriseId, analyseId, taskSummary) {
        const summaryLine = el('full-analysis-summary-line');
        if (summaryLine) {
            summaryLine.textContent = `Entreprise #${entrepriseId} — analyse pack #${analyseId || ''} — ${website}`;
        }
        const linkEnt = el('full-analysis-link-entreprise');
        if (linkEnt && entrepriseId) linkEnt.href = `/entreprise/${entrepriseId}`;
        const linkRapport = el('full-analysis-link-rapport');
        if (linkRapport && entrepriseId) {
            linkRapport.href = `/entreprise/${entrepriseId}/rapport-audit`;
            linkRapport.style.display = 'inline-block';
        }
        const copyShare = el('full-analysis-copy-share-link');
        if (copyShare) {
            copyShare.dataset.shareWebsite = String(website || '').trim();
        }
        showGallery((taskSummary && taskSummary.image_urls_sample) || []);
        await loadReport(website, taskSummary);
        const results = el('full-analysis-results');
        if (results) {
            results.style.display = 'block';
            results.classList.remove('full-analysis-results--visible');
            void results.offsetWidth;
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    results.classList.add('full-analysis-results--visible');
                });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        initExclusiveReportAccordion();

        const copyShareBtn = el('full-analysis-copy-share-link');
        if (copyShareBtn && !copyShareBtn._plCopyBound) {
            copyShareBtn._plCopyBound = true;
            copyShareBtn.addEventListener('click', async () => {
                const w =
                    (copyShareBtn.dataset.shareWebsite || '').trim() ||
                    ((el('full-analysis-url') && el('full-analysis-url').value) || '').trim();
                if (!w) return;
                const url = buildExternalAnalyseShareUrl(w);
                try {
                    await navigator.clipboard.writeText(url);
                    const html = copyShareBtn.innerHTML;
                    copyShareBtn.innerHTML =
                        '<i class="fa-solid fa-check" aria-hidden="true"></i> Lien copié';
                    copyShareBtn.disabled = true;
                    setTimeout(() => {
                        copyShareBtn.innerHTML = html;
                        copyShareBtn.disabled = false;
                    }, 2200);
                } catch (err) {
                    console.warn('Clipboard:', err);
                    window.prompt('Copiez ce lien :', url);
                }
            });
        }

        const form = el('full-analysis-form');
        if (!form) return;

        function syncFullAnalysisAdvancedOptions() {
            const tech = el('full-analysis-enable-technical');
            const nmapWrap = el('full-analysis-nmap-wrap');
            const nmap = el('full-analysis-nmap');
            const intro = el('full-analysis-suboptions-intro');
            const lhWrap = el('full-analysis-lighthouse-wrap');
            const showNmap = tech && tech.checked;
            const showLh = lhWrap && !lhWrap.hidden;
            if (nmapWrap) {
                nmapWrap.hidden = !showNmap;
                if (nmap) {
                    nmap.disabled = !showNmap;
                    if (!showNmap) nmap.checked = false;
                }
            }
            if (intro) intro.hidden = !showNmap && !showLh;
        }

        const techCb = el('full-analysis-enable-technical');
        if (techCb) techCb.addEventListener('change', syncFullAnalysisAdvancedOptions);
        syncFullAnalysisAdvancedOptions();

        const urlInput = el('full-analysis-url');
        if (urlInput) {
            urlInput.addEventListener(
                'input',
                debounce(() => {
                    const v = (urlInput.value || '').trim();
                    if (!v) {
                        writeStoredState({
                            website: '',
                            entreprise_id: null,
                            analyse_id: null,
                            completedWebsite: null,
                            snapshot: null,
                        });
                        return;
                    }
                    const st = readStoredState();
                    const patch = { website: v };
                    if (st && st.completedWebsite && v !== st.completedWebsite) {
                        patch.entreprise_id = null;
                        patch.analyse_id = null;
                        patch.completedWebsite = null;
                        patch.snapshot = null;
                    }
                    writeStoredState(patch);
                }, 400)
            );
        }

        (async function tryRestoreFromStorage() {
            const st = readStoredState();
            if (!st) return;
            if (urlInput && st.website) urlInput.value = st.website;
            if (!st.entreprise_id || !st.completedWebsite) return;
            if ((urlInput && urlInput.value.trim()) !== st.completedWebsite) return;
            const prog = el('full-analysis-progress');
            if (prog) {
                prog.style.display = 'block';
                prog.classList.remove('full-analysis-progress--animate-in');
                void prog.offsetWidth;
                prog.classList.add('full-analysis-progress--animate-in');
            }
            setProgress(100);
            try {
                const taskSummary = taskSummaryFromSnapshot(st);
                await showFullResults(st.completedWebsite, st.entreprise_id, st.analyse_id, taskSummary);
                renderSteps({
                    step: 'done',
                    message: 'Dernière analyse rechargée (navigateur). Affichage restauré depuis ce navigateur.',
                    steps: taskSummary.steps || {},
                });
            } catch (e) {
                console.warn('Restauration analyse (localStorage):', e);
            }
        })();

        form.addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const urlInput = el('full-analysis-url');
            const website = (urlInput && urlInput.value || '').trim();
            if (!website) return;

            clearProgressError();
            resetStepsRenderCache();

            const launchBtn = el('full-analysis-launch');
            const launchIcon = form.querySelector('.full-analysis-launch-icon-i');
            const prog = el('full-analysis-progress');
            const results = el('full-analysis-results');

            if (launchBtn) {
                launchBtn.disabled = true;
                launchBtn.classList.add('is-loading');
                launchBtn.setAttribute('aria-busy', 'true');
                launchBtn.setAttribute('aria-label', 'Analyse en cours, veuillez patienter');
                launchBtn.title = 'Analyse en cours…';
            }
            if (launchIcon) {
                launchIcon.classList.remove('fa-play');
                launchIcon.classList.add('fa-spinner', 'fa-spin');
            }
            if (prog) {
                prog.style.display = 'block';
                prog.classList.remove('full-analysis-progress--animate-in');
                void prog.offsetWidth;
                prog.classList.add('full-analysis-progress--animate-in');
            }
            if (results) {
                results.classList.remove('full-analysis-results--visible');
                results.style.display = 'none';
            }
            setProgress(2);
            renderSteps({ step: 'init', message: 'Démarrage…' });

            try {
                const startRes = await fetch('/api/website-full-analysis/start', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        website,
                        enable_technical:
                            el('full-analysis-enable-technical') &&
                            el('full-analysis-enable-technical').checked,
                        enable_osint:
                            el('full-analysis-enable-osint') && el('full-analysis-enable-osint').checked,
                        enable_pentest:
                            el('full-analysis-enable-pentest') &&
                            el('full-analysis-enable-pentest').checked,
                        enable_nmap: el('full-analysis-nmap') && el('full-analysis-nmap').checked,
                        use_lighthouse:
                            el('full-analysis-lighthouse') && el('full-analysis-lighthouse').checked,
                    }),
                });
                const startData = await startRes.json();
                if (!startRes.ok || !startData.success) {
                    throw new Error(startData.error || 'Impossible de démarrer');
                }

                const entrepriseName = String(startData.entreprise_name || website).trim();
                notifyFullAnalysis(`${entrepriseName} : analyse complète lancée`, 'info');
                const taskSummary = await pollTask(startData.task_id, { entrepriseName });

                const entrepriseId = (taskSummary && taskSummary.entreprise_id) || startData.entreprise_id;

                await showFullResults(website, entrepriseId, startData.analyse_id, taskSummary);

                writeStoredState({
                    website,
                    completedWebsite: website,
                    entreprise_id: entrepriseId,
                    analyse_id: startData.analyse_id,
                    snapshot: {
                        scores: (taskSummary && taskSummary.scores) || {},
                        scrape_counts: (taskSummary && taskSummary.scrape_counts) || {},
                        image_urls_sample: (taskSummary && taskSummary.image_urls_sample) || [],
                        steps: (taskSummary && taskSummary.steps) || {},
                    },
                });
            } catch (e) {
                console.error(e);
                setProgress(0);
                showProgressError(e.message || String(e));
            } finally {
                if (launchBtn) {
                    launchBtn.disabled = false;
                    launchBtn.classList.remove('is-loading');
                    launchBtn.setAttribute('aria-busy', 'false');
                    launchBtn.setAttribute('aria-label', 'Lancer l’analyse complète');
                    launchBtn.title = 'Lancer l’analyse';
                }
                if (launchIcon) {
                    launchIcon.classList.add('fa-play');
                    launchIcon.classList.remove('fa-spinner', 'fa-spin');
                }
            }
        });
    });
})();
