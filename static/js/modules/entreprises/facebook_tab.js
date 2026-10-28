/**
 * Onglet Facebook de la modale entreprise (prospection serv1).
 */
(function () {
    'use strict';

    const JOB_LABELS = {
        search: 'Recherche',
        prospect_flow: 'Prospection',
        scrape_page: 'Scrape',
        messenger_inbox: 'Messenger',
    };

    const STATUS_LABELS = {
        pending: 'En file',
        running: 'En cours',
        completed: 'Terminé',
        partial: 'Partiel',
        failed: 'Échec',
    };

    let pollTimer = null;
    let pollToken = 0;

    const esc = (t) =>
        window.Formatters && Formatters.escapeHtml
            ? Formatters.escapeHtml(String(t ?? ''))
            : String(t ?? '');

    function parseJson(raw) {
        if (!raw) return {};
        if (typeof raw === 'object') return raw;
        try {
            return JSON.parse(raw);
        } catch (_) {
            return {};
        }
    }

    function parseProfileJson(row) {
        return parseJson(row && row.profile_json);
    }

    async function fetchJson(url, options) {
        const resp = await fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}));
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || data.success === false) {
            throw new Error(data.error || resp.statusText || 'Erreur API');
        }
        return data;
    }

    function stopPoll() {
        if (pollTimer) {
            clearTimeout(pollTimer);
            pollTimer = null;
        }
        pollToken += 1;
    }

    function jobTypeLabel(type) {
        return JOB_LABELS[type] || type || 'Job';
    }

    function statusLabel(status) {
        const s = String(status || '').toLowerCase();
        return STATUS_LABELS[s] || status || '—';
    }

    function statusClass(status) {
        const s = String(status || '').toLowerCase();
        if (s === 'completed') return 'ok';
        if (s === 'partial' || s === 'running' || s === 'pending') return 'warn';
        if (s === 'failed') return 'bad';
        return 'muted';
    }

    /**
     * Titre lisible pour un job (type seulement, pas d'identifiant technique).
     * @param {object} job
     * @returns {string}
     */
    function jobHeading(job) {
        return jobTypeLabel(job && job.job_type);
    }

    /**
     * Nom entreprise pour les toasts (hook liste).
     * @param {number} entrepriseId
     * @returns {string}
     */
    function resolveEntrepriseNom(entrepriseId) {
        if (typeof window.getEntrepriseDisplayName === 'function') {
            const n = window.getEntrepriseDisplayName(entrepriseId);
            if (n) return String(n);
        }
        return 'Entreprise';
    }

    /**
     * Noeud renvoye par l'API (affectation auto serv1 ou alt).
     * @param {object|null|undefined} apiData
     * @returns {string}
     */
    function assignedRemoteNode(apiData) {
        const n = apiData && apiData.remote_node != null ? String(apiData.remote_node).trim() : '';
        return n === 'serv2' ? 'serv2' : n === 'alt' ? 'alt' : 'serv1';
    }

    /**
     * Texte toast / statut pour la file Celery + Chrome distant.
     * @param {object|null|undefined} queue
     * @param {string} remoteNode
     * @returns {string}
     */
    function formatQueueNotice(queue, remoteNode) {
        if (!queue) {
            return '';
        }
        const pending = Number(queue.pending) || 0;
        const running = Number(queue.running) || 0;
        const pos = Number(queue.position) || 1;
        const host = remoteNode === 'alt' ? 'alt (Windows)' : 'serv1';
        const parts = [];
        if (running > 0) {
            parts.push(running + ' déjà en cours');
        }
        if (pending > 1 || pos > 1) {
            parts.push('file ' + pos + '/' + pending);
        } else if (pending === 1 && running > 0) {
            parts.push('en attente (Chrome ' + host + ' occupé)');
        }
        if (!parts.length) {
            return ' — prise en charge sur ' + host;
        }
        return ' — ' + parts.join(', ') + ' sur ' + host + ' (un seul navigateur à la fois)';
    }

    /**
     * @param {number} entrepriseId
     * @param {string} jobType
     * @param {object} apiData
     * @param {string} remoteNode
     */
    function notifyFacebookQueued(entrepriseId, jobType, apiData, remoteNode) {
        if (!window.Notifications) {
            return;
        }
        const nom = resolveEntrepriseNom(entrepriseId);
        Notifications.show(
            nom +
                ' — ' +
                jobTypeLabel(jobType) +
                ' ajoutée à la file' +
                formatQueueNotice(apiData.queue, remoteNode),
            'info',
            'fab fa-facebook',
        );
    }

    /**
     * Affiche le statut / journal d'action sous les boutons Facebook.
     * @param {HTMLElement|null} statusEl
     * @param {object|string} jobOrMessage
     */
    function setActionStatus(statusEl, jobOrMessage) {
        if (!statusEl) return;
        if (typeof jobOrMessage === 'string') {
            statusEl.className = 'fb-log-panel fb-log-panel--idle';
            statusEl.innerHTML = '<p class="fb-log-msg">' + esc(jobOrMessage) + '</p>';
            return;
        }
        const job = jobOrMessage;
        const last = jobProgress(job);
        const lastLine = last.length ? last[last.length - 1].detail : '';
        const active = isActiveStatus(job.status);
        statusEl.className = 'fb-log-panel' + (active ? ' fb-log-panel--live' : ' fb-log-panel--idle');
        statusEl.innerHTML =
            '<div class="fb-log-head">' +
            '<span class="fb-log-title">' +
            esc(jobHeading(job)) +
            '</span>' +
            pill(job.status) +
            '</div>' +
            (lastLine ? '<p class="fb-log-detail">' + esc(lastLine) + '</p>' : '');
    }

    function isActiveStatus(status) {
        const s = String(status || '').toLowerCase();
        return s === 'pending' || s === 'running';
    }

    function pill(status, extra) {
        return (
            '<span class="fb-pill fb-pill-' +
            statusClass(status) +
            '">' +
            esc(extra || statusLabel(status)) +
            '</span>'
        );
    }

    function stepState(ok, labelOk, labelKo) {
        if (ok) {
            return { cls: 'ok', text: labelOk };
        }
        return { cls: 'muted', text: labelKo };
    }

    async function loadSummary(entrepriseId) {
        const [pageRes, jobsRes] = await Promise.all([
            fetchJson('/api/facebook-prospection/entreprise/' + entrepriseId + '/page'),
            fetchJson('/api/facebook-prospection/entreprise/' + entrepriseId + '/jobs'),
        ]);
        let messages = [];
        const convs = pageRes.conversations || [];
        const latest = convs[0];
        if (latest && latest.id) {
            const msgRes = await fetchJson(
                '/api/facebook-prospection/entreprise/' +
                    entrepriseId +
                    '/conversations/' +
                    latest.id +
                    '/messages',
            );
            messages = msgRes.messages || [];
        }
        return {
            pageUrl: pageRes.facebook_page_url || '',
            page: pageRes.facebook_page,
            jobs: jobsRes.jobs || [],
            conversations: convs,
            messages: messages,
        };
    }

    function latestResult(jobs) {
        for (let i = 0; i < jobs.length; i++) {
            const parsed = parseJson(jobs[i].result_json);
            if (parsed && (parsed.selected || parsed.candidates || parsed.steps)) {
                return parsed;
            }
        }
        return {};
    }

    function followLabel(follow) {
        const st = String((follow && follow.status) || '').toLowerCase();
        if (st === 'already') return 'Déjà suivi';
        if (st === 'dry-run') return 'Prêt (dry-run)';
        if (st === 'followed' || st === 'clicked') return 'Suivi';
        if (!st) return 'Pas encore';
        return st;
    }

    function messageLabel(message) {
        if (!message) return 'Pas encore';
        if (message.ok && message.dry_run) return 'Rédigé (non envoyé)';
        if (message.ok) return 'Envoyé';
        const step = String(message.step || '');
        if (step === 'type' || step === 'no-editor') return 'Composeur introuvable';
        if (step === 'no-message-button') return 'Pas de bouton Message';
        if (step) return 'Échec (' + step + ')';
        return 'Pas encore';
    }

    /**
     * Journal d'etapes stocke dans result_json.progress.
     * @param {object} job
     * @returns {Array<object>}
     */
    function jobProgress(job) {
        const parsed = parseJson(job && job.result_json);
        return Array.isArray(parsed.progress) ? parsed.progress : [];
    }

    /**
     * Journal visuel (recherche, suivre, Messenger).
     * @param {object} job
     * @returns {string}
     */
    function renderProgressLog(job) {
        const items = jobProgress(job).slice(-14);
        if (!items.length) return '';
        return (
            '<ul class="fb-journal" id="fb-live-journal">' +
            items
                .map(function (item) {
                    return (
                        '<li><span class="fb-journal-step">' +
                        esc(item.step || 'log') +
                        '</span><span>' +
                        esc(item.detail || '') +
                        '</span></li>'
                    );
                })
                .join('') +
            '</ul>'
        );
    }

    function renderLiveBanner(job) {
        if (!job) return '';
        const status = String(job.status || '').toLowerCase();
        const active = isActiveStatus(status);
        const cls = active ? 'is-live' : status === 'failed' ? 'is-bad' : 'is-idle';
        const items = jobProgress(job);
        const last = items.length ? items[items.length - 1] : null;
        let hint = '';
        if (status === 'pending') {
            hint =
                'En file Celery. S’il reste bloqué, ferme les fenêtres Celery en trop, redémarre start_dev, puis Relancer.';
        } else if (status === 'running') {
            hint = last && last.detail ? last.detail : 'Playwright tourne sur serv1.';
        } else if (job.error_message) {
            hint = job.error_message;
        } else if (last && last.detail) {
            hint = last.detail;
        }
        const canRetry = status === 'pending' || status === 'failed';
        return (
            '<div class="fb-live ' +
            cls +
            '" id="fb-live-banner">' +
            '<div class="fb-live-top">' +
            '<strong>' +
            esc(jobHeading(job)) +
            '</strong> ' +
            pill(job.status) +
            '</div>' +
            (hint ? '<p class="fb-live-hint">' + esc(hint) + '</p>' : '') +
            renderProgressLog(job) +
            (canRetry
                ? '<div class="fb-live-actions"><button type="button" class="btn btn-outline btn-small" id="fb-tab-retry">Relancer ce job</button></div>'
                : '') +
            '</div>'
        );
    }

    /**
     * Prefere les colonnes normalisees (page + contacts + posts), JSON en secours.
     * @param {object} profile
     * @param {object} selected
     * @param {object} page
     * @returns {object}
     */
    function pageFacts(profile, selected, page) {
        const scrape = parseJson(profile && profile.scrape);
        const src = Object.assign({}, scrape, profile || {});
        const row = page || {};
        const contacts = Array.isArray(row.contacts) ? row.contacts : [];
        function contactValues(kind) {
            return contacts
                .filter(function (c) {
                    return c && c.kind === kind && c.value;
                })
                .map(function (c) {
                    return c.value;
                });
        }
        const websitesFromJson = Array.isArray(src.websites)
            ? src.websites
            : Array.isArray(src.external_links)
              ? src.external_links.map(function (l) {
                    return typeof l === 'string' ? l : l && l.href;
                })
              : [];
        const postsFromPage = Array.isArray(row.posts)
            ? row.posts.map(function (p) {
                  return p && p.body_text;
              }).filter(Boolean)
            : [];
        const address = [row.address_1, row.code_postal, row.ville].filter(Boolean).join(' ');
        const media = Array.isArray(row.media) ? row.media : [];
        const photos = media
            .filter(function (m) {
                return m && m.kind === 'photo' && m.url;
            })
            .map(function (m) {
                return m.url;
            });
        const cover =
            (media.filter(function (m) {
                return m.kind === 'cover';
            })[0] || {}).url ||
            row.cover_url ||
            src.cover_url ||
            '';
        const logo =
            (media.filter(function (m) {
                return m.kind === 'logo';
            })[0] || {}).url ||
            row.logo_url ||
            src.logo_url ||
            '';
        return {
            title: decodeUnicodeText(row.page_name || src.title || (selected && selected.name) || ''),
            category: decodeUnicodeText(row.category || src.category || ''),
            likes: row.likes_text || row.likes_count || src.likes || '',
            followers: row.followers_text || row.followers_count || src.followers || '',
            rating: row.rating || src.rating || '',
            reviews: row.reviews_count || src.reviews_count || '',
            username: row.username || src.username || '',
            creation: row.creation_text || src.creation_text || '',
            price: row.price_range || src.price_range || '',
            phones: contactValues('phone').length ? contactValues('phone') : Array.isArray(src.phones) ? src.phones : [],
            emails: contactValues('email').length ? contactValues('email') : Array.isArray(src.emails) ? src.emails : [],
            websites: filterWebsiteUrls(
                contactValues('website').length ? contactValues('website') : websitesFromJson.filter(Boolean),
            ),
            socials: contactValues('social'),
            address: address || cleanScrapedBlob(src.address || ''),
            hours: row.hours_text || src.hours || '',
            intro: cleanScrapedBlob(row.intro || src.intro || ''),
            about: cleanScrapedBlob(row.about_text || src.about_preview || (selected && selected.snippet) || ''),
            posts: postsFromPage.length ? postsFromPage : Array.isArray(src.posts) ? src.posts : [],
            photos: photos.length ? photos : Array.isArray(src.photos) ? src.photos : [],
            cover: cover,
            logo: logo,
            score: row.match_score || src.match_score || (selected && selected.score),
        };
    }

    function decodeUnicodeText(str) {
        if (str == null || str === '') return '';
        return String(str).replace(/\\u([0-9a-fA-F]{4})/g, function (_, hex) {
            return String.fromCharCode(parseInt(hex, 16));
        });
    }

    /**
     * Nettoie le texte scrape Facebook (labels UI, repetitions).
     * @param {string} text
     * @returns {string}
     */
    function cleanScrapedBlob(text) {
        let t = decodeUnicodeText(text);
        t = t.replace(/\s+/g, ' ').trim();
        t = t.replace(
            /^(Intro\s+Cat[ée]gorie\s+D[ée]tails\s+Liens\s+Coordonn[ée]es\s+Bio\s*)+/i,
            '',
        );
        t = t.replace(/(\bFacebook\b\s*){3,}/gi, ' ');
        t = t.replace(/\bFacebook\b(\s+\bFacebook\b)+/gi, 'Facebook');
        t = t.replace(/\s+Liens\s+frankrimerman/gi, ' frankrimerman');
        return t.trim();
    }

    /**
     * Affichage court d'une URL (sans query fbclid).
     * @param {string} url
     * @returns {string}
     */
    function displayHost(url) {
        const raw = String(url || '').trim();
        if (!raw) return '';
        try {
            const u = new URL(raw.indexOf('://') >= 0 ? raw : 'https://' + raw);
            const host = u.hostname.replace(/^www\./, '');
            let path = u.pathname.replace(/\/$/, '');
            if (path.length > 28) {
                path = path.slice(0, 25) + '…';
            }
            return host + path;
        } catch (e) {
            return raw.split('?')[0].slice(0, 42);
        }
    }

    /**
     * Filtre liens site (pas Bing Maps / redirect FB).
     * @param {Array<string>} urls
     * @returns {Array<string>}
     */
    function filterWebsiteUrls(urls) {
        const out = [];
        const seen = new Set();
        (urls || []).forEach(function (raw) {
            const u = String(raw || '').trim();
            if (!u) return;
            const low = u.toLowerCase();
            if (low.includes('fbclid=') || low.includes('l.facebook.com/l.php')) return;
            if (low.includes('bing.com/maps') || low.includes('google.com/maps')) return;
            const clean = u.split('?')[0].split('#')[0];
            const key = clean.toLowerCase();
            if (seen.has(key)) return;
            seen.add(key);
            out.push(clean);
        });
        return out.slice(0, 5);
    }

    /**
     * Separe horaires et adresse quand FB les melange.
     * @param {string} hoursRaw
     * @param {string} addressRaw
     * @returns {{hours: string, address: string}}
     */
    function normalizeHoursAddress(hoursRaw, addressRaw) {
        let hours = cleanScrapedBlob(hoursRaw);
        let address = cleanScrapedBlob(addressRaw);
        if (hours && hours.length > 60 && !address) {
            const idx = hours.search(/\d{1,5}\s+[A-Za-z].{8,}/);
            if (idx > 8) {
                address = hours.slice(idx).trim();
                hours = hours.slice(0, idx).trim();
            }
        }
        return { hours: hours, address: address };
    }

    function linkList(items, mailOrTel) {
        if (!items || !items.length) return '';
        return (
            '<div class="fb-link-list">' +
            items
                .slice(0, 6)
                .map(function (item) {
                    const href =
                        mailOrTel === 'mail'
                            ? 'mailto:' + item
                            : mailOrTel === 'tel'
                              ? 'tel:' + String(item).replace(/\s+/g, '')
                              : item;
                    const label =
                        mailOrTel === 'tel' || mailOrTel === 'mail'
                            ? item
                            : displayHost(item) || item;
                    return (
                        '<a class="fb-link-chip" href="' +
                        esc(href) +
                        '" target="_blank" rel="noopener" title="' +
                        esc(item) +
                        '">' +
                        esc(label) +
                        '</a>'
                    );
                })
                .join('') +
            '</div>'
        );
    }

    /**
     * Statistique compacte (abonnes, avis…).
     * @param {string} label
     * @param {string|number} value
     * @returns {string}
     */
    function renderStat(label, value) {
        if (value == null || value === '') return '';
        return (
            '<div class="fb-stat">' +
            '<span class="fb-stat__v">' +
            esc(String(value)) +
            '</span>' +
            '<span class="fb-stat__k">' +
            esc(label) +
            '</span></div>'
        );
    }

    /**
     * Bloc detaille de la page Facebook scrapee.
     * @param {string} pageName
     * @param {string} pageUrl
     * @param {object} facts
     * @param {*} scrapeHint
     * @returns {string}
     */
    function renderPageDetails(pageName, pageUrl, facts, scrapeHint) {
        const loc = normalizeHoursAddress(facts.hours, facts.address);
        const title = facts.title || pageName || displayHost(pageUrl);
        let aboutText = facts.about || '';
        const introText = facts.intro || '';
        if (introText && aboutText.indexOf(introText.slice(0, Math.min(40, introText.length))) < 0) {
            aboutText = introText + (aboutText ? ' ' + aboutText : '');
        } else if (!aboutText) {
            aboutText = introText;
        }
        aboutText = cleanScrapedBlob(aboutText);

        const statsHtml =
            renderStat('Abonnés', facts.followers) +
            renderStat("J'aime", facts.likes) +
            renderStat('Avis', facts.reviews) +
            renderStat('Note', facts.rating) +
            (facts.score != null && facts.score !== '' ? renderStat('Match', facts.score) : '');

        const contactBlocks = [];
        if (facts.phones && facts.phones.length) {
            contactBlocks.push(
                '<div class="fb-contact"><span class="fb-contact__k"><i class="fas fa-phone"></i> Téléphone</span>' +
                    linkList(facts.phones, 'tel') +
                    '</div>',
            );
        }
        if (facts.emails && facts.emails.length) {
            contactBlocks.push(
                '<div class="fb-contact"><span class="fb-contact__k"><i class="fas fa-envelope"></i> Email</span>' +
                    linkList(facts.emails, 'mail') +
                    '</div>',
            );
        }
        if (facts.websites && facts.websites.length) {
            contactBlocks.push(
                '<div class="fb-contact"><span class="fb-contact__k"><i class="fas fa-globe"></i> Site web</span>' +
                    linkList(facts.websites) +
                    '</div>',
            );
        }
        if (loc.address) {
            contactBlocks.push(
                '<div class="fb-contact"><span class="fb-contact__k"><i class="fas fa-map-marker-alt"></i> Adresse</span>' +
                    '<p class="fb-contact__v">' +
                    esc(loc.address) +
                    '</p></div>',
            );
        }
        if (loc.hours) {
            contactBlocks.push(
                '<div class="fb-contact"><span class="fb-contact__k"><i class="fas fa-clock"></i> Horaires</span>' +
                    '<p class="fb-contact__v">' +
                    esc(loc.hours) +
                    '</p></div>',
            );
        }

        const posts = facts.posts.length
            ? '<ul class="fb-posts">' +
              facts.posts
                  .slice(0, 4)
                  .map(function (p) {
                      return '<li>' + esc(cleanScrapedBlob(String(p)).slice(0, 260)) + '</li>';
                  })
                  .join('') +
              '</ul>'
            : '';
        const photos = facts.photos.length
            ? '<div class="fb-photos">' +
              facts.photos
                  .slice(0, 12)
                  .map(function (src) {
                      return (
                          '<a class="fb-photo" href="' +
                          esc(src) +
                          '" target="_blank" rel="noopener"><img src="' +
                          esc(src) +
                          '" alt=""></a>'
                      );
                  })
                  .join('') +
              '</div>'
            : '';

        const metaChips = [];
        if (facts.category) {
            metaChips.push('<span class="fb-chip">' + esc(facts.category) + '</span>');
        }
        if (facts.username) {
            metaChips.push('<span class="fb-chip fb-chip--muted">@' + esc(facts.username) + '</span>');
        }
        if (facts.price) {
            metaChips.push('<span class="fb-chip fb-chip--muted">' + esc(facts.price) + '</span>');
        }
        if (facts.creation) {
            metaChips.push('<span class="fb-chip fb-chip--muted">' + esc(facts.creation) + '</span>');
        }

        const aboutBlock = aboutText
            ? aboutText.length > 280
                ? '<details class="fb-about-fold"><summary>À propos</summary><p>' +
                  esc(aboutText.slice(0, 1200)) +
                  '</p></details>'
                : '<div class="fb-section"><div class="fb-section__title">À propos</div><p class="fb-about">' +
                  esc(aboutText) +
                  '</p></div>'
            : '';

        return (
            '<div class="fb-page-card">' +
            (facts.cover
                ? '<div class="fb-page-hero"><img class="fb-cover" src="' +
                  esc(facts.cover) +
                  '" alt=""><div class="fb-page-hero__shade"></div></div>'
                : '') +
            '<div class="fb-page-hero__body">' +
            (facts.logo
                ? '<img class="fb-logo fb-logo--lg" src="' + esc(facts.logo) + '" alt="">'
                : '<div class="fb-logo fb-logo--lg fb-logo--empty"><i class="fab fa-facebook"></i></div>') +
            '<div class="fb-page-hero__text">' +
            '<h4 class="fb-page-title">' +
            esc(title) +
            '</h4>' +
            (metaChips.length ? '<div class="fb-chip-row">' + metaChips.join('') + '</div>' : '') +
            '<a class="fb-page-hero__link" href="' +
            esc(pageUrl) +
            '" target="_blank" rel="noopener">' +
            '<i class="fas fa-external-link-alt"></i> ' +
            esc(displayHost(pageUrl) || 'Ouvrir sur Facebook') +
            '</a></div></div>' +
            (statsHtml ? '<div class="fb-stats">' + statsHtml + '</div>' : '') +
            (contactBlocks.length
                ? '<div class="fb-contact-grid">' + contactBlocks.join('') + '</div>'
                : '') +
            aboutBlock +
            (photos ? '<div class="fb-section"><div class="fb-section__title">Photos</div>' + photos + '</div>' : '') +
            (posts ? '<div class="fb-section"><div class="fb-section__title">Publications</div>' + posts + '</div>' : '') +
            (scrapeHint ? '' : '<p class="fb-muted">Page liée, scrape en cours ou incomplet.</p>') +
            '</div>'
        );
    }

    function renderPanel(summary, entrepriseId) {
        const page = summary.page;
        const profile = parseProfileJson(page);
        const result = latestResult(summary.jobs);
        const selected = result.selected || {};
        const pageUrl = summary.pageUrl || (page && page.page_url) || selected.url || '';
        const pageName = (page && page.page_name) || selected.name || '';
        const hasPage = !!pageUrl;
        const follow = profile.follow || result.follow || {};
        const message = profile.message || result.message || {};
        const conv = summary.conversations[0];
        const lastMsg = summary.messages.length
            ? summary.messages[summary.messages.length - 1]
            : null;
        const latestJob = summary.jobs[0];

        const pageStep = stepState(hasPage, hasPage ? 'Trouvée' : 'Manquante', 'Pas encore');
        const followOk = ['already', 'dry-run', 'followed', 'clicked'].indexOf(follow.status) >= 0;
        const followStep = {
            cls: followOk ? 'ok' : 'muted',
            text: followLabel(follow),
        };
        const msgOk = !!message.ok;
        const msgStep = {
            cls: msgOk ? 'ok' : message.step ? 'warn' : 'muted',
            text: messageLabel(message),
        };

        const facts = pageFacts(profile, selected, page);
        const scrapeHint = facts.title || facts.about;

        return (
            '<div class="fb-panel">' +
            '<header class="fb-head">' +
            '<div>' +
            '<h3 class="fb-title">Facebook</h3>' +
            '<p class="fb-sub">Chrome sur serv1 via Celery (file d attente)</p>' +
            '</div>' +
            '<button type="button" class="btn btn-outline btn-small" id="fb-tab-refresh">Actualiser</button>' +
            '</header>' +
            renderLiveBanner(latestJob) +
            '<div class="fb-steps">' +
            '<div class="fb-step fb-step-' +
            pageStep.cls +
            '"><span class="fb-step-k">Page</span><span class="fb-step-v">' +
            esc(pageStep.text) +
            '</span></div>' +
            '<div class="fb-step fb-step-' +
            followStep.cls +
            '"><span class="fb-step-k">Suivre</span><span class="fb-step-v">' +
            esc(followStep.text) +
            '</span></div>' +
            '<div class="fb-step fb-step-' +
            msgStep.cls +
            '"><span class="fb-step-k">Message</span><span class="fb-step-v">' +
            esc(msgStep.text) +
            '</span></div>' +
            '</div>' +
            '<section class="fb-card">' +
            '<div class="fb-card-head">Page retenue</div>' +
            (hasPage
                ? renderPageDetails(pageName, pageUrl, facts, scrapeHint)
                : '<p class="fb-muted">Aucune page enregistrée. Lance une recherche ou une prospection.</p>') +
            '</section>' +
            (conv || lastMsg
                ? '<section class="fb-card"><div class="fb-card-head">Messenger</div><p>' +
                  pill(conv && conv.status, statusLabel(conv && conv.status)) +
                  '</p>' +
                  (lastMsg
                      ? '<blockquote class="fb-quote">' +
                        esc(String(lastMsg.body_text || '').slice(0, 280)) +
                        '</blockquote>'
                      : '') +
                  '</section>'
                : '') +
            '<section class="fb-card fb-actions-card">' +
            '<div class="fb-card-head">Actions</div>' +
            '<p class="fb-muted fb-actions-hint">Recherche, suivi et message Messenger. Par defaut dry-run (aucun envoi). Jobs files sur serv1 Windows.</p>' +
            '<label class="fb-check"><input type="checkbox" id="fb-send-real"> Envoyer vraiment le message</label>' +
            '<textarea id="fb-message-text" class="form-input fb-message" rows="3" placeholder="Message (optionnel, sinon texte DanielCraft)"></textarea>' +
            '<div class="fb-actions">' +
            '<button type="button" class="btn btn-primary" id="fb-tab-prospect">Prospecter</button>' +
            '<button type="button" class="btn btn-outline" id="fb-tab-search">Rechercher</button>' +
            '<button type="button" class="btn btn-outline" id="fb-tab-scrape"' +
            (hasPage ? '' : ' disabled title="Lie une page d’abord"') +
            '>Scraper</button>' +
            '</div>' +
            '<div class="fb-log-panel fb-log-panel--idle" id="fb-tab-action-status" role="status" aria-live="polite"></div>' +
            '</section>' +
            '<section class="fb-card">' +
            '<div class="fb-card-head">Historique</div>' +
            renderJobs(summary.jobs) +
            '</section>' +
            '</div>'
        );
    }

    function renderJobs(jobs) {
        if (!jobs.length) {
            return '<p class="fb-muted">Aucun job pour l’instant.</p>';
        }
        return (
            '<table class="fb-jobs"><thead><tr><th>Type</th><th>Statut</th><th>Détail</th></tr></thead><tbody>' +
            jobs
                .slice(0, 10)
                .map(function (j) {
                    const detail = j.error_message || j.search_query || '';
                    return (
                        '<tr class="fb-job-' +
                        statusClass(j.status) +
                        '"><td>' +
                        esc(jobTypeLabel(j.job_type)) +
                        '</td><td>' +
                        pill(j.status) +
                        '</td><td class="fb-job-detail">' +
                        esc(String(detail).slice(0, 120)) +
                        '</td></tr>'
                    );
                })
                .join('') +
            '</tbody></table>'
        );
    }

    function setBusy(container, busy) {
        ['fb-tab-prospect', 'fb-tab-search', 'fb-tab-scrape'].forEach(function (id) {
            const btn = container.querySelector('#' + id);
            if (btn && !btn.hasAttribute('data-keep-disabled')) {
                if (busy && id === 'fb-tab-scrape' && btn.disabled) return;
                btn.disabled = busy;
            }
        });
    }

    /**
     * Relance un job pending/failed via l'API retry.
     * @param {HTMLElement} container
     * @param {number} entrepriseId
     * @param {object} job
     */
    function bindRetry(container, entrepriseId, job) {
        const retryBtn = container.querySelector('#fb-tab-retry');
        if (!retryBtn || !job || !job.id) return;
        retryBtn.onclick = function () {
            startAction(container, entrepriseId, function () {
                return fetchJson('/api/facebook-prospection/jobs/' + job.id + '/retry', {
                    method: 'POST',
                }).then(function (d) {
                    d.job_type = job.job_type;
                    return d;
                });
            });
        };
    }

    function updateLiveFromJob(container, job, entrepriseId) {
        const banner = container.querySelector('#fb-live-banner');
        const statusEl = container.querySelector('#fb-tab-action-status');
        const html = renderLiveBanner(job);
        if (banner && html) {
            const wrap = document.createElement('div');
            wrap.innerHTML = html;
            banner.replaceWith(wrap.firstElementChild);
        }
        if (statusEl) {
            setActionStatus(statusEl, job);
        }
        if (entrepriseId) bindRetry(container, entrepriseId, job);
    }

    async function pollUntilDone(entrepriseId, jobId, container, options) {
        options = options || {};
        stopPoll();
        const token = pollToken;
        const statusEl = container ? container.querySelector('#fb-tab-action-status') : null;
        let waited = 0;
        const maxMs = 180000;
        const step = 1500;

        async function tick() {
            if (token !== pollToken) return;
            try {
                const data = await fetchJson('/api/facebook-prospection/jobs/' + jobId);
                const job = data.job || {};
                if (container) {
                    updateLiveFromJob(container, job, entrepriseId);
                }
                if (!isActiveStatus(job.status)) {
                    const nom = resolveEntrepriseNom(entrepriseId);
                    const typeLbl = jobTypeLabel(job.job_type);
                    if (options.notify !== false && window.Notifications) {
                        const kind = job.status === 'failed' ? 'error' : 'success';
                        Notifications.show(
                            nom + ' — ' + typeLbl + ' terminée : ' + statusLabel(job.status),
                            kind,
                            job.status === 'failed' ? 'fa-exclamation-circle' : 'fa-check-circle',
                        );
                    }
                    if (typeof options.onLoading === 'function') {
                        options.onLoading(false);
                    }
                    if (typeof options.onDone === 'function') {
                        options.onDone(job);
                    }
                    if (container) {
                        setBusy(container, false);
                        await loadFacebookTab(entrepriseId);
                    }
                    return;
                }
                waited += step;
                if (waited >= maxMs) {
                    if (statusEl) {
                        setActionStatus(
                            statusEl,
                            'Toujours en file. Relance le job ou redémarre Celery (une seule fenêtre).',
                        );
                    }
                    if (typeof options.onLoading === 'function') {
                        options.onLoading(false);
                    }
                    if (container) {
                        setBusy(container, false);
                    }
                    if (options.notify !== false && window.Notifications) {
                        Notifications.show(
                            resolveEntrepriseNom(entrepriseId) +
                                ' — Facebook : toujours en file (timeout suivi).',
                            'warning',
                            'fa-hourglass-end',
                        );
                    }
                    return;
                }
                pollTimer = setTimeout(tick, step);
            } catch (e) {
                if (statusEl) setActionStatus(statusEl, e.message || 'Erreur suivi job');
                if (typeof options.onLoading === 'function') {
                    options.onLoading(false);
                }
                if (container) {
                    setBusy(container, false);
                }
                if (options.notify !== false && window.Notifications) {
                    Notifications.show(
                        resolveEntrepriseNom(entrepriseId) + ' — ' + (e.message || 'Erreur suivi Facebook'),
                        'error',
                    );
                }
            }
        }

        pollTimer = setTimeout(tick, 1200);
    }

    async function postJob(entrepriseId, body) {
        return fetchJson('/api/facebook-prospection/jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    }

    async function startAction(container, entrepriseId, runner, options) {
        options = options || {};
        const statusEl = container ? container.querySelector('#fb-tab-action-status') : null;
        if (container) {
            setBusy(container, true);
        }
        if (typeof options.onLoading === 'function') {
            options.onLoading(true);
        }
        if (statusEl) setActionStatus(statusEl, 'Mise en file Celery…');
        try {
            const data = await runner();
            if (!data.job_id) throw new Error('Pas de job_id');
            const jobType = data.job_type || 'prospect_flow';
            const remoteNode = assignedRemoteNode(data);
            if (options.notify !== false) {
                notifyFacebookQueued(entrepriseId, jobType, data, remoteNode);
            }
            if (statusEl && data.queue) {
                setActionStatus(
                    statusEl,
                    'En file' + formatQueueNotice(data.queue, remoteNode).replace(/^ — /, ' · '),
                );
            }
            if (container) {
                updateLiveFromJob(
                    container,
                    {
                        id: data.job_id,
                        job_type: jobType,
                        status: 'pending',
                    },
                    entrepriseId,
                );
            }
            await pollUntilDone(entrepriseId, data.job_id, container, options);
        } catch (e) {
            if (statusEl) setActionStatus(statusEl, e.message || 'Erreur');
            if (typeof options.onLoading === 'function') {
                options.onLoading(false);
            }
            if (container) {
                setBusy(container, false);
            }
            if (options.notify !== false && window.Notifications) {
                Notifications.show(
                    resolveEntrepriseNom(entrepriseId) + ' — ' + (e.message || 'Erreur Facebook'),
                    'error',
                );
            }
        }
    }

    /**
     * Lance une recherche Facebook depuis la liste (chip), sans ouvrir l'onglet.
     * @param {number} entrepriseId
     * @param {object} [options]
     * @returns {Promise<void>}
     */
    function launchSearchFromList(entrepriseId, options) {
        options = options || {};
        return startAction(null, entrepriseId, function () {
            return postJob(entrepriseId, {
                entreprise_id: entrepriseId,
                job_type: 'search',
            }).then(function (d) {
                d.job_type = 'search';
                return d;
            });
        }, options);
    }

    function bindActions(container, entrepriseId, summary) {
        const refreshBtn = container.querySelector('#fb-tab-refresh');
        if (refreshBtn) {
            refreshBtn.onclick = function () {
                loadFacebookTab(entrepriseId);
            };
        }

        const searchBtn = container.querySelector('#fb-tab-search');
        if (searchBtn) {
            searchBtn.onclick = function () {
                startAction(container, entrepriseId, function () {
                    return postJob(entrepriseId, {
                        entreprise_id: entrepriseId,
                        job_type: 'search',
                    }).then(function (d) {
                        d.job_type = 'search';
                        return d;
                    });
                });
            };
        }

        const prospectBtn = container.querySelector('#fb-tab-prospect');
        if (prospectBtn) {
            prospectBtn.onclick = function () {
                const send = !!(container.querySelector('#fb-send-real') && container.querySelector('#fb-send-real').checked);
                const messageText = (container.querySelector('#fb-message-text') || {}).value || '';
                const body = { send: send };
                if (String(messageText).trim()) body.message_text = String(messageText).trim();
                startAction(container, entrepriseId, function () {
                    return fetchJson('/api/facebook-prospection/entreprise/' + entrepriseId + '/prospect', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body),
                    }).then(function (d) {
                        d.job_type = 'prospect_flow';
                        return d;
                    });
                });
            };
        }

        bindRetry(container, entrepriseId, summary.jobs && summary.jobs[0]);

        const scrapeBtn = container.querySelector('#fb-tab-scrape');
        if (scrapeBtn) {
            scrapeBtn.onclick = function () {
                startAction(container, entrepriseId, function () {
                    return postJob(entrepriseId, {
                        entreprise_id: entrepriseId,
                        job_type: 'scrape_page',
                    }).then(function (d) {
                        d.job_type = 'scrape_page';
                        return d;
                    });
                });
            };
        }

        const latest = summary.jobs && summary.jobs[0];
        if (latest && isActiveStatus(latest.status)) {
            setBusy(container, true);
            pollUntilDone(entrepriseId, latest.id, container);
        }
    }

    async function loadFacebookTab(entrepriseId) {
        const container = document.getElementById('entreprise-facebook-container');
        if (!container) return;
        stopPoll();
        const keepScroll = container.parentElement ? container.parentElement.scrollTop : 0;
        if (!container.querySelector('.fb-panel')) {
            container.innerHTML = '<p class="loading">Chargement Facebook…</p>';
        }
        try {
            const summary = await loadSummary(entrepriseId);
            container.innerHTML = renderPanel(summary, entrepriseId);
            bindActions(container, entrepriseId, summary);
            if (container.parentElement) container.parentElement.scrollTop = keepScroll;
        } catch (e) {
            const msg = e.message || 'Erreur';
            if (msg.indexOf('desactive') !== -1 || msg.indexOf('503') !== -1) {
                container.innerHTML =
                    '<div class="fb-panel"><p class="fb-muted">Prospection Facebook désactivée. Ajoute FACEBOOK_PROSPECTION_ENABLED=true dans .env puis redémarre Flask et Celery.</p></div>';
                return;
            }
            container.innerHTML = '<p class="error">' + esc(msg) + '</p>';
        }
    }

    window.EntrepriseFacebookTab = {
        load: loadFacebookTab,
        launchSearch: launchSearchFromList,
    };
})();
