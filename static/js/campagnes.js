// Gestion des campagnes email

let selectedRecipients = [];
let entreprisesData = [];
let templatesData = [];
let objectifsCiblage = [];
let segmentsCiblage = [];
let groupesCiblage = [];
let socket = null;
/** ID de la campagne actuellement affichée dans la modale de résultats. */
let currentResultsCampagneId = null;
/** Timer pour le rafraîchissement périodique des résultats. */
let resultsRefreshTimer = null;
/** Liste complète des campagnes chargées depuis l'API. */
let campagnesData = [];
/** Données affichées après filtrage emails (étape 2). */
let displayedEntreprisesData = [];
/** IDs des entreprises sélectionnées à l'étape 1. */
let selectedEntrepriseIds = [];
/** Terme de recherche pour les entreprises (étape 1). */
let step1SearchTerm = '';
/** Debounce timer pour chargement auto critères. */
let ciblageDebounceTimer = null;
/** Token interne pour ignorer les réponses métriques obsolètes. */
let campagneMetricsRequestToken = 0;

// Étape courante du formulaire nouvelle campagne (1, 2 ou 3)
let campagneModalStep = 1;

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    loadCampagnes();
    loadTemplates();
    initTemplateSelectListener();
    loadEntreprises();
    loadObjectifsCiblage();
    loadSegmentsCiblage();
    loadGroupesCiblage();
    loadCiblageSuggestionsWithCounts();
    loadCommercialPriorityProfilesCiblage();
    initCiblageModeSwitch();
    initCiblageAutoLoad();
    initCiblageSaveSegment();
    initEmailFiltersToggle();
    initEmailFiltersListeners();
    initScheduleFields();
    initStep1Search();
    initCampagnesFilters();
    initWebSocket();
    initGenerateContactEmailButton();
});

// Charger les campagnes
async function loadCampagnes() {
    try {
        const response = await fetch('/api/campagnes');
        const campagnes = await response.json();
        campagnesData = Array.isArray(campagnes) ? campagnes : [];
        applyCampagnesFilters();
    } catch (error) {
        const grid = document.getElementById('campagnes-grid');
        if (grid) {
            grid.innerHTML =
            '<div class="empty-state"><p>Erreur lors du chargement des campagnes</p></div>';
        }
    }
}

/**
 * Initialise les filtres/recherche sur la liste des campagnes.
 * Recherche plein texte sur nom/sujet, filtre par statut et plage de dates.
 */
function initCampagnesFilters() {
    const searchInput = document.getElementById('campagnes-search');
    const statutSelect = document.getElementById('campagnes-statut-filter');
    const dateFromInput = document.getElementById('campagnes-date-from');
    const dateToInput = document.getElementById('campagnes-date-to');
    const resetBtn = document.getElementById('campagnes-filters-reset');

    if (!searchInput && !statutSelect && !dateFromInput && !dateToInput) {
        return;
    }

    if (searchInput) {
        searchInput.addEventListener('input', function() {
            applyCampagnesFilters();
        });
    }

    if (statutSelect) {
        statutSelect.addEventListener('change', function() {
            applyCampagnesFilters();
        });
    }

    const dateInputs = [dateFromInput, dateToInput];
    dateInputs.forEach(function(input) {
        if (input) {
            input.addEventListener('change', function() {
                applyCampagnesFilters();
            });
        }
    });

    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            if (searchInput) searchInput.value = '';
            if (statutSelect) statutSelect.value = '';
            if (dateFromInput) dateFromInput.value = '';
            if (dateToInput) dateToInput.value = '';
            applyCampagnesFilters();
        });
    }
}

/**
 * Applique les filtres en mémoire et rafraîchit l'affichage des campagnes.
 */
function applyCampagnesFilters() {
    if (!Array.isArray(campagnesData) || campagnesData.length === 0) {
        displayCampagnes([]);
        return;
    }

    const searchInput = document.getElementById('campagnes-search');
    const statutSelect = document.getElementById('campagnes-statut-filter');
    const dateFromInput = document.getElementById('campagnes-date-from');
    const dateToInput = document.getElementById('campagnes-date-to');

    const search = searchInput && searchInput.value
        ? searchInput.value.trim().toLowerCase()
        : '';
    const statut = statutSelect && statutSelect.value ? statutSelect.value : '';
    const dateFromVal = dateFromInput && dateFromInput.value ? dateFromInput.value : '';
    const dateToVal = dateToInput && dateToInput.value ? dateToInput.value : '';

    let filtered = campagnesData.slice();

    if (search) {
        filtered = filtered.filter(function(campagne) {
            const haystack = [
                campagne.nom || '',
                campagne.sujet || '',
                campagne.template_id || ''
            ].join(' ').toLowerCase();
            return haystack.indexOf(search) !== -1;
        });
    }

    if (statut) {
        filtered = filtered.filter(function(campagne) {
            return campagne.statut === statut;
        });
    }

    if (dateFromVal) {
        const fromDate = new Date(dateFromVal + 'T00:00:00');
        filtered = filtered.filter(function(campagne) {
            if (!campagne.date_creation) return false;
            return new Date(campagne.date_creation) >= fromDate;
        });
    }

    if (dateToVal) {
        const toDate = new Date(dateToVal + 'T23:59:59');
        filtered = filtered.filter(function(campagne) {
            if (!campagne.date_creation) return false;
            return new Date(campagne.date_creation) <= toDate;
        });
    }

    displayCampagnes(filtered);
}

// Afficher les campagnes
function displayCampagnes(campagnes) {
    const grid = document.getElementById('campagnes-grid');
    const countEl = document.getElementById('campagnes-results-count');

    if (!campagnes || campagnes.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📧</div>
                <h3>Aucune campagne</h3>
                <p>Créez votre première campagne pour commencer</p>
            </div>
        `;
        if (countEl) {
            countEl.textContent = '0 campagne';
            countEl.classList.remove('is-filtered');
        }
        return;
    }

    grid.innerHTML = campagnes.map(campagne => {
        const effectiveStatus = getEffectiveCampaignStatus(campagne);
        const failedCount = Math.max(0, Number(campagne.total_envoyes || 0) - Number(campagne.total_reussis || 0));
        const bouncedCount = Number(campagne.total_bounced || 0);
        return `
        <div class="campagne-card" data-campagne-id="${campagne.id}">
            <div class="campagne-header">
                <h3 class="campagne-title">${escapeHtml(campagne.nom)}</h3>
                <span class="campagne-statut statut-${effectiveStatus}">${getCampaignStatusLabel(effectiveStatus)}</span>
            </div>
            <div class="campagne-meta">
                <div class="campagne-meta-main">
                    <span class="campagne-meta-dot"></span>
                    <span>${formatRelativeDate(campagne.date_creation)}</span>
                </div>
                <div class="campagne-meta-timeline">
                    <span class="meta-pill ${effectiveStatus === 'scheduled' ? 'is-active' : ''}">Créée</span>
                    <span class="meta-pill ${(campagne.total_envoyes || 0) > 0 ? 'is-active' : ''}">Envoyés</span>
                    <span class="meta-pill ${(campagne.total_reussis || 0) > 0 ? 'is-active' : ''}">Réussis</span>
                    <span class="meta-pill ${failedCount > 0 ? 'is-active' : ''}">Échecs</span>
                    <span class="meta-pill ${bouncedCount > 0 ? 'is-active' : ''}">Bounces</span>
                </div>
            </div>
            <div class="campagne-stats">
                <div class="stat-item">
                    <div class="stat-value">${campagne.total_destinataires || 0}</div>
                    <div class="stat-label">Destinataires</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${campagne.total_envoyes || 0}</div>
                    <div class="stat-label">Envoyés</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${campagne.total_reussis || 0}</div>
                    <div class="stat-label">Réussis</div>
                </div>
            </div>
            <div class="campagne-kpi-grid">
                <div class="kpi-line">
                    <div class="kpi-label-row">
                    <span>Envoi</span>
                    <strong>${formatPercent(safeRate((campagne.total_delivered_strict != null ? campagne.total_delivered_strict : (campagne.total_delivered != null ? campagne.total_delivered : campagne.total_envoyes)), campagne.total_destinataires))}</strong>
                    </div>
                <div class="kpi-bar"><span style="width:${clampPercent(safeRate((campagne.total_delivered_strict != null ? campagne.total_delivered_strict : (campagne.total_delivered != null ? campagne.total_delivered : campagne.total_envoyes)), campagne.total_destinataires))}%"></span></div>
                </div>
                <div class="kpi-line">
                    <div class="kpi-label-row">
                        <span>Ouverture</span>
                    <strong data-metric="open-rate">${typeof campagne.open_rate === 'number' ? formatPercent(campagne.open_rate) : '-'}</strong>
                    </div>
                <div class="kpi-bar kpi-open"><span data-metric-bar="open-rate" style="width:${clampPercent(typeof campagne.open_rate === 'number' ? campagne.open_rate : 0)}%"></span></div>
                </div>
                <div class="kpi-line">
                    <div class="kpi-label-row">
                        <span>Clic</span>
                    <strong data-metric="click-rate">${typeof campagne.click_rate === 'number' ? formatPercent(campagne.click_rate) : '-'}</strong>
                    </div>
                <div class="kpi-bar kpi-click"><span data-metric-bar="click-rate" style="width:${clampPercent(typeof campagne.click_rate === 'number' ? campagne.click_rate : 0)}%"></span></div>
                </div>
            </div>
            <div class="campagne-actions">
                <button class="btn-action btn-view" onclick="viewCampagne(${campagne.id})">
                    Voir détails
                </button>
                ${shouldShowRelaunchButton(campagne) ? `
                <button class="btn-action btn-relaunch" onclick="relaunchCampagne(${campagne.id})" title="Relancer si envoi très faible ou campagne en échec">
                    Relancer
                </button>
                ` : ''}
                <button class="btn-action btn-delete" onclick="deleteCampagne(${campagne.id})">
                    Supprimer
                </button>
            </div>
            ${effectiveStatus === 'running' ? `
                <div class="progress-bar-container">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${Math.round((campagne.total_envoyes / Math.max(campagne.total_destinataires, 1)) * 100)}%">                                                                                           
                            ${Math.round((campagne.total_envoyes / Math.max(campagne.total_destinataires, 1)) * 100)}%      
                        </div>
                    </div>
                    <div class="progress-text">Envoi en cours...</div>
                </div>
            ` : ''}
        </div>
    `;}).join('');

    if (countEl) {
        const total = Array.isArray(campagnesData) ? campagnesData.length : campagnes.length;
        const current = campagnes.length;
        countEl.textContent = current + (current > 1 ? ' campagnes' : ' campagne');
        if (current < total) {
            countEl.classList.add('is-filtered');
        } else {
            countEl.classList.remove('is-filtered');
        }
    }

    // Si l'API /api/campagnes fournit déjà open_rate/click_rate, on évite de refaire 1 fetch par carte.
    const missingMetrics = (campagnes || []).filter(function(c) {
        return !(c && typeof c.open_rate === 'number' && typeof c.click_rate === 'number');
    });
    if (missingMetrics.length > 0) {
        hydrateCampagneCardsMetrics(missingMetrics);
    }
}

async function hydrateCampagneCardsMetrics(campagnes) {
    if (!Array.isArray(campagnes) || campagnes.length === 0) return;

    const token = Date.now();
    campagneMetricsRequestToken = token;

    const completed = campagnes.filter(function(campagne) {
        const s = (campagne && campagne.statut != null ? String(campagne.statut) : '').trim().toLowerCase();
        // Même si une campagne est "failed", on veut afficher open/click
        // (et surtout éviter des cartes à "-" partout).
        return ['completed', 'completed_with_errors', 'running', 'scheduled', 'failed'].indexOf(s) !== -1;
    });

    await Promise.allSettled(completed.map(async function(campagne) {
        try {
            const response = await fetch('/api/tracking/campagne/' + campagne.id);
            if (!response.ok) return;
            const stats = await response.json();
            if (campagneMetricsRequestToken !== token) return;
            updateCampagneCardMetrics(campagne.id, stats);
        } catch (error) {
            // Silence: métriques facultatives sur la carte
        }
    }));
}

function updateCampagneCardMetrics(campagneId, stats) {
    const card = document.querySelector('[data-campagne-id="' + campagneId + '"]');
    if (!card || !stats) return;

    const openRate = typeof stats.open_rate === 'number' ? stats.open_rate : 0;
    const clickRate = typeof stats.click_rate === 'number' ? stats.click_rate : 0;
    const openRateEl = card.querySelector('[data-metric="open-rate"]');
    const clickRateEl = card.querySelector('[data-metric="click-rate"]');
    const openBarEl = card.querySelector('[data-metric-bar="open-rate"]');
    const clickBarEl = card.querySelector('[data-metric-bar="click-rate"]');

    if (openRateEl) openRateEl.textContent = formatPercent(openRate);
    if (clickRateEl) clickRateEl.textContent = formatPercent(clickRate);
    if (openBarEl) openBarEl.style.width = clampPercent(openRate) + '%';
    if (clickBarEl) clickBarEl.style.width = clampPercent(clickRate) + '%';
}

// Charger les templates et remplir le select "Modèle de message" (étape 3)
async function loadTemplates() {
    var select = document.getElementById('campagne-template');
    if (!select) return;
    try {
        var response = await fetch('/api/templates');
        var data = await response.json();
        templatesData = Array.isArray(data) ? data : [];
        if (!response.ok) {
            templatesData = [];
        }
    } catch (e) {
        templatesData = [];
    }
    renderTemplateSelect();
}

function renderTemplateSelect() {
    var select = document.getElementById('campagne-template');
    if (!select) return;
    select.innerHTML = '<option value="">Aucun (message personnalisé)</option>';
    templatesData.forEach(function(template) {
        var option = document.createElement('option');
        option.value = template.id;
        option.textContent = template.name || template.id;
        select.appendChild(option);
    });
}

// Attacher une seule fois le listener "change" du select Modèle de message
function initTemplateSelectListener() {
    var select = document.getElementById('campagne-template');
    if (!select) return;
    select.addEventListener('change', onCampagneTemplateChange);
}

function onCampagneTemplateChange() {
    var select = document.getElementById('campagne-template');
    var value = select ? select.value : '';
    var template = templatesData.find(function(t) { return t.id === value; });
    var messageTextarea = document.getElementById('campagne-message');
    var previewDiv = document.getElementById('template-preview');
    if (!messageTextarea) return;
    if (template) {
        var sujetEl = document.getElementById('campagne-sujet');
        if (sujetEl) sujetEl.value = template.subject || '';
        if (template.is_html) {
            messageTextarea.style.display = 'none';
            if (!previewDiv) {
                previewDiv = document.createElement('div');
                previewDiv.id = 'template-preview';
                previewDiv.className = 'template-preview';
                messageTextarea.parentNode.insertBefore(previewDiv, messageTextarea.nextSibling);
            }
            previewDiv.style.display = 'block';
            var iframe = previewDiv.querySelector('iframe');
            if (!iframe) {
                iframe = document.createElement('iframe');
                iframe.style.width = '100%';
                iframe.style.border = 'none';
                iframe.style.minHeight = '400px';
                iframe.style.background = 'white';
                previewDiv.innerHTML = '';
                previewDiv.appendChild(iframe);
            }
            try {
                var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                iframeDoc.open();
                iframeDoc.write(template.content || '');
                iframeDoc.close();
            } catch (e) {
                previewDiv.innerHTML = '<div style="padding: 20px; max-height: 400px; overflow-y: auto;">' + (template.content || '') + '</div>';
            }
        } else {
            messageTextarea.style.display = 'block';
            messageTextarea.value = template.content || '';
            if (previewDiv) previewDiv.style.display = 'none';
        }
    } else {
        messageTextarea.style.display = 'block';
        messageTextarea.value = '';
        if (previewDiv) previewDiv.style.display = 'none';
    }
}

/**
 * Charge et affiche les suggestions de templates pour la sélection actuelle
 * (basé sur la première entreprise sélectionnée quand il y en a au moins une).
 */
async function loadTemplateSuggestionsForSelection() {
    const container = document.getElementById('template-suggestions');
    if (!container) return;

    // Nettoyer / état initial
    container.innerHTML = '';

    if (!Array.isArray(selectedEntrepriseIds) || selectedEntrepriseIds.length === 0) {
        container.innerHTML = '<p class="template-suggestions-hint">Sélectionnez au moins une entreprise à l\'étape 1 pour obtenir des suggestions de modèles adaptées.</p>';
        return;
    }

    // Utiliser la première entreprise sélectionnée comme "profil type"
    const targetId = selectedEntrepriseIds[0];
    const entreprise = entreprisesData.find(function (e) { return e.id === targetId; });
    const nom = entreprise && entreprise.nom ? entreprise.nom : ('Entreprise #' + targetId);

    try {
        container.innerHTML = '<div class="template-suggestions-loading"><i class="fa-solid fa-spinner fa-spin"></i> Analyse de vos données d\'audit…</div>';
        const response = await fetch('/api/entreprise/' + targetId + '/template-suggestions?limit=3');
        if (!response.ok) {
            container.innerHTML = '<p class="template-suggestions-error">Impossible de récupérer les suggestions pour le moment.</p>';
            return;
        }
        const suggestions = await response.json();
        if (!Array.isArray(suggestions) || suggestions.length === 0) {
            container.innerHTML = '<p class="template-suggestions-hint">Aucune suggestion spécifique. Vous pouvez choisir librement un modèle dans la liste.</p>';
            return;
        }

        const itemsHtml = suggestions.map(function (sug) {
            const title = sug.name || sug.id;
            const subject = sug.subject || '';
            const reason = sug.reason || '';
            return `
                <article class="template-suggestion-card" data-template-id="${sug.id}">
                    <div class="template-suggestion-header">
                        <h4>${escapeHtml(title)}</h4>
                        <span class="template-suggestion-score">${Math.round((sug.score || 0) * 100)}%</span>
                    </div>
                    ${subject ? `<p class="template-suggestion-subject">${escapeHtml(subject)}</p>` : ''}
                    ${reason ? `<p class="template-suggestion-reason">${escapeHtml(reason)}</p>` : ''}
                    <button type="button" class="template-suggestion-cta" data-template-id="${sug.id}">
                        Utiliser ce modèle pour ${escapeHtml(nom)}
                    </button>
                </article>
            `;
        }).join('');

        container.innerHTML = `
            <div class="template-suggestions-header">
                <span class="template-suggestions-title">Suggestions basées sur vos analyses</span>
                <button type="button" class="template-suggestions-refresh" id="template-suggestions-refresh">
                    <i class="fa-solid fa-rotate-right"></i> Rafraîchir
                </button>
            </div>
            <div class="template-suggestions-list">
                ${itemsHtml}
            </div>
        `;

        // Attacher les events sur les suggestions
        container.querySelectorAll('.template-suggestion-cta').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const tplId = this.getAttribute('data-template-id');
                const select = document.getElementById('campagne-template');
                if (select && tplId) {
                    select.value = tplId;
                    onCampagneTemplateChange();
                    // Animation visuelle rapide sur le select
                    select.classList.add('template-select-highlight');
                    setTimeout(function () { select.classList.remove('template-select-highlight'); }, 600);
                }
            });
        });

        const refreshBtn = document.getElementById('template-suggestions-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function () {
                loadTemplateSuggestionsForSelection();
            });
        }
    } catch (e) {
        console.error('Erreur lors du chargement des suggestions de templates:', e);
        container.innerHTML = '<p class="template-suggestions-error">Erreur lors de la récupération des suggestions.</p>';
    }
}

// Charger les objectifs de ciblage (pour le select)
async function loadObjectifsCiblage() {
    try {
        const response = await fetch('/api/ciblage/objectifs');
        objectifsCiblage = await response.json();
        const select = document.getElementById('ciblage-objectif');
        if (!select) return;
        select.innerHTML = '<option value="">Choisir un objectif...</option>';
        objectifsCiblage.forEach(function(obj) {
            const opt = document.createElement('option');
            opt.value = obj.id;
            opt.textContent = obj.nom;
            select.appendChild(opt);
        });
    } catch (e) {}
}

// Charger les segments sauvegardés
async function loadSegmentsCiblage() {
    try {
        const response = await fetch('/api/ciblage/segments');
        segmentsCiblage = await response.json();
        const select = document.getElementById('ciblage-segment');
        if (!select) return;
        select.innerHTML = '<option value="">Choisir un segment...</option>';
        segmentsCiblage.forEach(function(seg) {
            const opt = document.createElement('option');
            opt.value = seg.id;
            opt.textContent = seg.nom + (seg.description ? ' - ' + seg.description : '');
            opt.dataset.criteres = JSON.stringify(seg.criteres || {});
            select.appendChild(opt);
        });
    } catch (e) {}
}

// Charger les groupes d'entreprises pour le ciblage (affichage en pills cliquables)
async function loadGroupesCiblage() {
    try {
        const response = await fetch('/api/groupes-entreprises');
        groupesCiblage = await response.json();
        const container = document.getElementById('ciblage-groupes-pills');
        if (!container) return;
        container.innerHTML = '';
        if (!groupesCiblage || groupesCiblage.length === 0) {
            container.innerHTML = '<div class="ciblage-groupes-empty">Aucun groupe disponible</div>';
            updateCiblageGroupesCount();
            return;
        }
        groupesCiblage.forEach(function(groupe, index) {
            const pill = document.createElement('button');
            pill.type = 'button';
            pill.className = 'ciblage-groupe-pill';
            pill.dataset.groupeId = groupe.id;
            pill.setAttribute('role', 'checkbox');
            pill.setAttribute('aria-checked', 'false');
            const count = groupe.entreprises_count || 0;
            pill.title = (groupe.nom || '') + (count ? ' · ' + count + ' entreprise' + (count > 1 ? 's' : '') : '');
            pill.innerHTML = '<span class="ciblage-groupe-pill-name">' + escapeHtml(groupe.nom) + '</span>' +
                '<span class="ciblage-groupe-pill-count">' + count + '</span>' +
                '<i class="fas fa-check ciblage-groupe-pill-check" aria-hidden="true"></i>';
            pill.style.animationDelay = (index * 45) + 'ms';
            pill.addEventListener('click', function() {
                pill.classList.toggle('is-selected');
                pill.setAttribute('aria-checked', pill.classList.contains('is-selected'));
                loadByGroupes();
            });
            container.appendChild(pill);
        });
        updateCiblageGroupesCount();
    } catch (e) {
        console.error('Erreur lors du chargement des groupes:', e);
        const container = document.getElementById('ciblage-groupes-pills');
        if (container) container.innerHTML = '<div class="ciblage-groupes-empty ciblage-groupes-error">Erreur lors du chargement</div>';
    }
}

function escapeHtml(s) {
    if (!s) return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

function getSelectedGroupIds() {
    var pills = document.querySelectorAll('.ciblage-groupe-pill.is-selected');
    return Array.from(pills).map(function(p) { return parseInt(p.dataset.groupeId, 10); }).filter(function(id) { return !isNaN(id) && id > 0; });
}

function updateCiblageGroupesCount() {
    var countEl = document.getElementById('ciblage-groupes-count');
    if (!countEl) return;
    var ids = getSelectedGroupIds();
    if (ids.length === 0) {
        countEl.textContent = '';
        countEl.classList.remove('has-selection');
    } else {
        countEl.textContent = ids.length + ' groupe' + (ids.length > 1 ? 's' : '') + ' sélectionné' + (ids.length > 1 ? 's' : '');
        countEl.classList.add('has-selection');
    }
}

// Retire le suffixe " (123)" des valeurs d'autocomplétion pour l'API
function stripCountSuffix(val) {
    if (!val || typeof val !== 'string') return val;
    return val.replace(/\s*\(\d+\)\s*$/, '').trim();
}

// Charger les suggestions avec effectifs pour autocomplétion (affiche "Valeur (count)")
function loadCiblageSuggestionsWithCounts() {
    fetch('/api/ciblage/suggestions?with_counts=1')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            fillDatalistWithCounts('datalist-secteur', data.secteurs || []);
            fillDatalistWithCounts('datalist-opportunite', data.opportunites || []);
            fillDatalistWithCounts('datalist-statut', data.statuts || []);
            fillDatalistWithCounts('datalist-tags', data.tags || []);
        })
        .catch(function() {});
}

function fillDatalistWithCounts(id, items) {
    var el = document.getElementById(id);
    if (!el || !Array.isArray(items)) return;
    el.innerHTML = '';
    items.forEach(function(item) {
        var v = item && (item.value != null ? item.value : item);
        var c = item && item.count != null ? item.count : 0;
        if (v === undefined || v === null) return;
        var opt = document.createElement('option');
        opt.value = c > 0 ? v + ' (' + c + ')' : v;
        el.appendChild(opt);
    });
}

async function loadCommercialPriorityProfilesCiblage() {
    var sel = document.getElementById('ciblage-commercial-profile');
    if (!sel) return;
    var keep = sel.value;
    try {
        var response = await fetch('/api/commercial/priority-profiles');
        var data = await response.json();
        var items = (data && data.items) || [];
        sel.innerHTML = '<option value="">Défaut</option>';
        items.forEach(function(p) {
            var o = document.createElement('option');
            o.value = String(p.id);
            o.textContent = p.nom || ('#' + p.id);
            sel.appendChild(o);
        });
        if (keep && Array.prototype.some.call(sel.options, function(o) { return o.value === keep; })) {
            sel.value = keep;
        }
    } catch (e) {}
}

function clearCiblageSegmentMeta() {
    var sumEl = document.getElementById('ciblage-segment-summary');
    var metaEl = document.getElementById('ciblage-segment-preview-total');
    if (sumEl) {
        sumEl.textContent = '';
        sumEl.hidden = true;
    }
    if (metaEl) metaEl.textContent = '';
}

/** Texte lisible des critères (segment ou formulaire) pour l’UI. */
function formatCriteresSummary(criteres) {
    if (!criteres || typeof criteres !== 'object') return '';
    var parts = [];
    if (criteres.secteur_contains) parts.push('Secteur contient « ' + criteres.secteur_contains + ' »');
    if (criteres.secteur) parts.push('Secteur = ' + criteres.secteur);
    if (criteres.opportunite) {
        var opp = Array.isArray(criteres.opportunite) ? criteres.opportunite.join(', ') : String(criteres.opportunite);
        if (opp) parts.push('Opportunité : ' + opp);
    }
    if (criteres.statut) parts.push('Statut : ' + criteres.statut);
    if (criteres.tags_contains) parts.push('Tags contiennent « ' + criteres.tags_contains + ' »');
    if (criteres.score_securite_max != null && criteres.score_securite_max !== '') {
        parts.push('Score sécurité max ' + criteres.score_securite_max);
    }
    if (criteres.exclude_already_contacted) parts.push('Exclure déjà contactés');
    if (criteres.etape_prospection) parts.push('Étape CRM : ' + criteres.etape_prospection);
    if (criteres.sort_commercial) parts.push('Tri par priorité commerciale');
    if (criteres.priority_min != null && criteres.priority_min !== '') {
        parts.push('Score priorité min ≥ ' + criteres.priority_min);
    }
    if (criteres.commercial_profile_id != null && criteres.commercial_profile_id !== '') {
        parts.push('Profil de pondération #' + criteres.commercial_profile_id);
    }
    if (criteres.commercial_limit != null && criteres.commercial_limit !== '') {
        parts.push('Limite Top ' + criteres.commercial_limit);
    }
    if (criteres.cms) parts.push('CMS : ' + (Array.isArray(criteres.cms) ? criteres.cms.join(', ') : criteres.cms));
    if (criteres.framework) parts.push('Framework : ' + criteres.framework);
    if (criteres.has_blog) parts.push('Avec blog');
    if (criteres.has_form) parts.push('Avec formulaire');
    if (criteres.has_tunnel) parts.push('Avec tunnel e-commerce');
    if (criteres.performance_max != null) parts.push('Perf. max ' + criteres.performance_max);
    if (criteres.groupe_ids && criteres.groupe_ids.length) {
        parts.push('Groupes #' + criteres.groupe_ids.join(', #'));
    }
    return parts.join(' · ');
}

function collectCiblageCriteresFromForm() {
    var filters = {};
    var secteurEl = document.getElementById('ciblage-secteur');
    var secteur = secteurEl ? stripCountSuffix(secteurEl.value.trim()) : '';
    if (secteur) filters.secteur_contains = secteur;
    var oppEl = document.getElementById('ciblage-opportunite');
    var oppRaw = oppEl ? oppEl.value.trim() : '';
    var opp = oppRaw.split(',').map(function(s) { return stripCountSuffix(s.trim()); }).filter(Boolean);
    if (opp.length) filters.opportunite = opp;
    var statutEl = document.getElementById('ciblage-statut');
    var statut = statutEl ? stripCountSuffix(statutEl.value.trim()) : '';
    if (statut) filters.statut = statut;
    var tagsEl = document.getElementById('ciblage-tags');
    var tags = tagsEl ? stripCountSuffix(tagsEl.value.trim()) : '';
    if (tags) filters.tags_contains = tags;
    var scoreMaxEl = document.getElementById('ciblage-score-max');
    if (scoreMaxEl && scoreMaxEl.value) {
        var sm = parseInt(scoreMaxEl.value, 10);
        if (!isNaN(sm)) filters.score_securite_max = sm;
    }
    var excl = document.getElementById('ciblage-exclude-contactes');
    if (excl && excl.checked) filters.exclude_already_contacted = true;
    var etapeEl = document.getElementById('ciblage-etape-prospection');
    if (etapeEl && etapeEl.value) filters.etape_prospection = etapeEl.value;
    var sortC = document.getElementById('ciblage-sort-commercial');
    if (sortC && sortC.checked) filters.sort_commercial = true;
    var pminEl = document.getElementById('ciblage-priority-min');
    if (pminEl && pminEl.value !== '') {
        var pm = parseFloat(pminEl.value);
        if (!isNaN(pm)) filters.priority_min = pm;
    }
    var profEl = document.getElementById('ciblage-commercial-profile');
    if (profEl && profEl.value) {
        var pid = parseInt(profEl.value, 10);
        if (!isNaN(pid)) filters.commercial_profile_id = pid;
    }
    var limEl = document.getElementById('ciblage-commercial-limit');
    if (limEl && limEl.value !== '') {
        var lm = parseInt(limEl.value, 10);
        if (!isNaN(lm)) filters.commercial_limit = lm;
    }
    return filters;
}

function initCiblageSaveSegment() {
    var btn = document.getElementById('ciblage-save-segment-btn');
    if (!btn) return;
    btn.addEventListener('click', async function() {
        var nomEl = document.getElementById('ciblage-save-segment-nom');
        var descEl = document.getElementById('ciblage-save-segment-desc');
        var nom = nomEl ? nomEl.value.trim() : '';
        if (!nom) {
            window.alert('Indiquez un nom pour le segment.');
            return;
        }
        var criteres = collectCiblageCriteresFromForm();
        try {
            var response = await fetch('/api/ciblage/segments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({
                    nom: nom,
                    description: (descEl && descEl.value.trim()) || null,
                    criteres: criteres
                })
            });
            var data = await response.json().catch(function() { return {}; });
            if (!response.ok) {
                window.alert(data.error || 'Enregistrement impossible.');
                return;
            }
            if (nomEl) nomEl.value = '';
            if (descEl) descEl.value = '';
            await loadSegmentsCiblage();
            var sel = document.getElementById('ciblage-segment');
            var newId = data.id != null ? String(data.id) : '';
            if (sel && newId) {
                sel.value = newId;
                var modeSeg = document.querySelector('input[name="ciblage_mode"][value="segment"]');
                if (modeSeg) {
                    modeSeg.checked = true;
                    modeSeg.dispatchEvent(new Event('change', { bubbles: true }));
                }
                await loadBySegment();
            }
        } catch (e) {
            window.alert('Erreur réseau lors de l’enregistrement.');
        }
    });
}

// Chargement automatique : objectif/groupes/segment au change, critères en debounce
function initCiblageAutoLoad() {
    var objSel = document.getElementById('ciblage-objectif');
    var segSel = document.getElementById('ciblage-segment');
    if (objSel) objSel.addEventListener('change', function() { if (objSel.value) loadByObjectif(); });
    if (segSel) {
        segSel.addEventListener('change', function() {
            if (segSel.value) loadBySegment();
            else clearCiblageSegmentMeta();
        });
    }
    var debounceMs = 500;
    function scheduleCriteres() {
        if (ciblageDebounceTimer) clearTimeout(ciblageDebounceTimer);
        ciblageDebounceTimer = setTimeout(function() {
            ciblageDebounceTimer = null;
            var mode = document.querySelector('input[name="ciblage_mode"]:checked');
            if (mode && mode.value === 'criteres') loadByCriteres();
        }, debounceMs);
    }
    [
        'ciblage-secteur', 'ciblage-opportunite', 'ciblage-statut', 'ciblage-tags', 'ciblage-score-max',
        'ciblage-priority-min', 'ciblage-commercial-limit'
    ].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('input', scheduleCriteres);
    });
    var critSelectIds = ['ciblage-etape-prospection', 'ciblage-commercial-profile'];
    critSelectIds.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('change', scheduleCriteres);
    });
    var excludeCb = document.getElementById('ciblage-exclude-contactes');
    if (excludeCb) excludeCb.addEventListener('change', scheduleCriteres);
    var sortCb = document.getElementById('ciblage-sort-commercial');
    if (sortCb) sortCb.addEventListener('change', scheduleCriteres);
}

// Listeners sur les filtres emails (partie 2) : réafficher la liste
function initEmailFiltersListeners() {
    var ids = ['filter-email-person-only', 'filter-email-with-name', 'filter-email-exclude-domains', 'filter-email-exclude-contains'];
    ids.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('change', applyEmailFiltersAndDisplay);
        if (el) el.addEventListener('input', applyEmailFiltersAndDisplay);
    });
}

// Repli / dépli des filtres emails (pour réduire la hauteur du bloc)
function initEmailFiltersToggle() {
    var section = document.querySelector('.form-section-email-filters');
    if (!section) return;
    var row = section.querySelector('.email-filters-row');
    var btn = document.getElementById('email-filters-toggle');
    if (!row || !btn) return;

    // État initial : replié pour réduire la hauteur
    section.classList.add('is-collapsed');
    btn.setAttribute('aria-expanded', 'false');

    btn.addEventListener('click', function() {
        var collapsed = section.classList.toggle('is-collapsed');
        btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        btn.textContent = collapsed ? 'Filtres avancés' : 'Masquer les filtres';
    });
}

function applyEmailFiltersAndDisplay() {
    if (entreprisesData.length === 0) return;
    displayEntreprises();
}

// Recherche entreprise (étape 1) : filtre nom / secteur / email
function initStep1Search() {
    var input = document.getElementById('entreprise-search');
    var clearBtn = document.getElementById('entreprise-search-clear');
    if (!input) return;
    var debounce;
    input.addEventListener('input', function() {
        var value = this.value || '';
        if (debounce) clearTimeout(debounce);
        debounce = setTimeout(function() {
            step1SearchTerm = value.trim().toLowerCase();
            displayEntreprisesStep1();
        }, 250);
    });
    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            input.value = '';
            step1SearchTerm = '';
            displayEntreprisesStep1();
            input.focus();
        });
    }
}

// Applique les critères de filtrage emails et retourne une copie (source = liste d'entreprises)
function applyEmailFilters(sourceData) {
    var source = sourceData || entreprisesData || [];
    var personOnly = document.getElementById('filter-email-person-only') && document.getElementById('filter-email-person-only').checked;
    var withName = document.getElementById('filter-email-with-name') && document.getElementById('filter-email-with-name').checked;
    var excludeDomainsRaw = (document.getElementById('filter-email-exclude-domains') && document.getElementById('filter-email-exclude-domains').value) || '';
    var excludeContains = (document.getElementById('filter-email-exclude-contains') && document.getElementById('filter-email-exclude-contains').value.trim().toLowerCase()) || '';
    var excludeDomains = excludeDomainsRaw.split(',').map(function(s) { return s.trim().toLowerCase(); }).filter(Boolean);

    return source.map(function(ent) {
        var emails = (ent.emails || []).filter(function(em) {
            if (personOnly && !em.is_person) return false;
            if (withName && (!em.nom || em.nom === 'N/A' || !em.nom.trim())) return false;
            var domain = (em.domain || (em.email && em.email.split('@')[1]) || '').toLowerCase();
            if (domain && excludeDomains.some(function(d) { return domain === d || domain.endsWith('.' + d); })) return false;
            if (excludeContains && (em.email || '').toLowerCase().indexOf(excludeContains) !== -1) return false;
            return true;
        });
        return { id: ent.id, nom: ent.nom, secteur: ent.secteur, emails: emails };
    }).filter(function(ent) { return ent.emails.length > 0; });
}

// Indique si le template a 3 étapes (Entreprises, Emails, Message) ou 2 (Ciblage, Message)
function hasThreeSteps() {
    return !!document.getElementById('campagne-step-3');
}

// Affiche uniquement l'étape N (1, 2 ou 3), masque les autres. Gère template 2 ou 3 steps.
function showCampagneStep(stepNum) {
    var s1 = document.getElementById('campagne-step-1');
    var s2 = document.getElementById('campagne-step-2');
    var s3 = document.getElementById('campagne-step-3');
    var i1 = document.getElementById('step-indicator-1');
    var i2 = document.getElementById('step-indicator-2');
    var i3 = document.getElementById('step-indicator-3');
    if (s1) s1.style.display = stepNum === 1 ? 'block' : 'none';
    if (s2) s2.style.display = stepNum === 2 ? 'block' : 'none';
    if (s3) s3.style.display = stepNum === 3 ? 'block' : 'none';
    if (i1) i1.classList.toggle('step-active', stepNum === 1);
    if (i2) i2.classList.toggle('step-active', stepNum === 2);
    if (i3) i3.classList.toggle('step-active', stepNum === 3);
    var btnPrev = document.getElementById('btn-campagne-prev');
    var btnNext = document.getElementById('btn-campagne-next');
    var btnSubmit = document.getElementById('btn-campagne-submit');
    if (btnPrev) btnPrev.style.display = stepNum === 1 ? 'none' : 'inline-block';
    if (btnNext) btnNext.style.display = stepNum === 3 ? 'none' : 'inline-block';
    if (btnSubmit) btnSubmit.style.display = stepNum === 3 ? 'inline-block' : 'none';
    if (stepNum === 3) {
        loadTemplates();
        setScheduleDateTimeToNow();
        loadTemplateSuggestionsForSelection();
    }
}

// Clic sur l'en-tête d'étape (rond + label)
function goToStepFromHeader(step) {
    var threeSteps = hasThreeSteps();
    if (step === 1) {
        campagneModalStep = 1;
        showCampagneStep(1);
        return;
    }
    if (step === 2) {
        if (!threeSteps) {
            campagneModalStep = 2;
            showCampagneStep(2);
            return;
        }
        // En 3 steps, il faut au moins une entreprise sélectionnée
        if (!selectedEntrepriseIds || selectedEntrepriseIds.length === 0) return;
        campagneModalStep = 2;
        displayEntreprisesStep2();
        showCampagneStep(2);
        return;
    }
    if (step === 3 && threeSteps) {
        // Ne pas autoriser de sauter directement à 3 depuis 1
        if (campagneModalStep < 2) return;
        campagneModalStep = 3;
        showCampagneStep(3);
    }
}

// Passer à l'étape suivante
function campagneStepNext() {
    var threeSteps = hasThreeSteps();
    if (campagneModalStep === 1) {
        if (threeSteps && selectedEntrepriseIds.length === 0) {
            alert('Sélectionnez au moins une entreprise avant de continuer.');
            return;
        }
        if (threeSteps) {
            selectedRecipients = [];
            campagneModalStep = 2;
            displayEntreprisesStep2();
        } else {
            campagneModalStep = 2;
        }
        showCampagneStep(2);
    } else if (campagneModalStep === 2) {
        if (threeSteps) {
            campagneModalStep = 3;
            showCampagneStep(3);
        }
    }
}

// Revenir à l'étape précédente
function campagneStepPrev() {
    if (campagneModalStep === 2) {
        campagneModalStep = 1;
        showCampagneStep(1);
    } else if (campagneModalStep === 3) {
        campagneModalStep = 2;
        showCampagneStep(2);
    }
}

// Afficher/masquer les blocs ciblage selon le mode
function initCiblageModeSwitch() {
    const radios = document.querySelectorAll('input[name="ciblage_mode"]');
    const blockObjectif = document.getElementById('ciblage-objectif-block');
    const blockCriteres = document.getElementById('ciblage-criteres-block');
    const blockGroupes = document.getElementById('ciblage-groupes-block');
    const blockSegment = document.getElementById('ciblage-segment-block');
    if (!blockObjectif || !blockCriteres || !blockGroupes || !blockSegment) return;
    function updateBlocks() {
        const mode = document.querySelector('input[name="ciblage_mode"]:checked');
        const v = mode ? mode.value : 'toutes';
        blockObjectif.style.display = v === 'objectif' ? 'block' : 'none';
        blockCriteres.style.display = v === 'criteres' ? 'block' : 'none';
        blockGroupes.style.display = v === 'groupes' ? 'block' : 'none';
        blockSegment.style.display = v === 'segment' ? 'block' : 'none';
        if (v === 'objectif') {
            const sel = document.getElementById('ciblage-objectif');
            const desc = document.getElementById('ciblage-objectif-desc');
            const obj = objectifsCiblage.find(function(o) { return o.id === sel.value; });
            desc.textContent = obj ? obj.description : '';
        }
        if (v === 'groupes') {
            loadByGroupes();
        }
        if (v === 'criteres') {
            loadByCriteres();
        }
        if (v === 'segment') {
            var ss = document.getElementById('ciblage-segment');
            if (ss && ss.value) loadBySegment();
        }
    }
    radios.forEach(function(r) { r.addEventListener('change', updateBlocks); });
    const objSel = document.getElementById('ciblage-objectif');
    if (objSel) objSel.addEventListener('change', updateBlocks);
    updateBlocks();
}

/** Met les champs date et heure d'envoi à la date et l'heure actuelles (locale). */
function setScheduleDateTimeToNow() {
    const dateInput = document.getElementById('campagne-schedule-date');
    const timeInput = document.getElementById('campagne-schedule-time');
    if (!dateInput || !timeInput) return;
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    const hh = String(now.getHours()).padStart(2, '0');
    const min = String(now.getMinutes()).padStart(2, '0');
    dateInput.value = yyyy + '-' + mm + '-' + dd;
    timeInput.value = hh + ':' + min;
}

/** Jours fériés en France (métropole). Retourne des chaînes "YYYY-MM-DD". */
function getFrenchHolidays(year) {
    const pad = function(n) { return String(n).padStart(2, '0'); };
    const fixed = [
        year + '-01-01',
        year + '-05-01',
        year + '-05-08',
        year + '-07-14',
        year + '-08-15',
        year + '-11-01',
        year + '-11-11',
        year + '-12-25'
    ];
    // Pâques (algorithme anonyme grégorien)
    const a = year % 19;
    const b = Math.floor(year / 100);
    const c = year % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const month = Math.floor((h + l - 7 * m + 114) / 31);
    const day = ((h + l - 7 * m + 114) % 31) + 1;
    const easterStr = year + '-' + pad(month) + '-' + pad(day);
    const easter = new Date(easterStr);
    const addDays = function(d, n) {
        const x = new Date(d);
        x.setDate(x.getDate() + n);
        return x.getFullYear() + '-' + pad(x.getMonth() + 1) + '-' + pad(x.getDate());
    };
    return fixed.concat([
        addDays(easter, 1),
        addDays(easter, 39),
        addDays(easter, 50)
    ]);
}

/** Indique si une date (Date ou string YYYY-MM-DD) est un jour ouvré en France (pas week-end, pas férié). */
function isBusinessDay(date) {
    const d = typeof date === 'string' ? new Date(date + 'T12:00:00') : new Date(date);
    const day = d.getDay();
    if (day === 0 || day === 6) return false;
    const y = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const key = y + '-' + mm + '-' + dd;
    const holidays = getFrenchHolidays(y).concat(getFrenchHolidays(y + 1));
    return holidays.indexOf(key) === -1;
}

/** Prochain jour ouvré à partir de fromDate (inclut fromDate si déjà ouvré). Heures d'ouverture type 9h et 14h. */
function getNextBusinessDay(fromDate) {
    const d = new Date(fromDate);
    d.setHours(0, 0, 0, 0);
    for (var i = 0; i < 14; i++) {
        const y = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        if (isBusinessDay(y + '-' + mm + '-' + dd)) return d;
        d.setDate(d.getDate() + 1);
    }
    return d;
}

/**
 * Calcule un créneau d'envoi suggéré (jour ouvré, heures type bureau FR : 9h matin, 14h après-midi).
 * @param {string} type - 'tomorrow-morning' | 'tomorrow-afternoon' | 'monday-morning'
 * @returns {{ date: Date, hour: number, minute: number, label: string, timeLabel: string }}
 */
function getSuggestedScheduleSlot(type) {
    const now = new Date();
    const pad = function(n) { return String(n).padStart(2, '0'); };
    let start = new Date(now);
    start.setHours(0, 0, 0, 0);
    let hour = 9;
    let minute = 0;
    let label = '';
    let timeLabel = '09:00';

    if (type === 'tomorrow-morning') {
        start.setDate(start.getDate() + 1);
        start = getNextBusinessDay(start);
        hour = 9;
        minute = 0;
        timeLabel = '09:00';
        label = start.getDate() === now.getDate() + 1 ? 'Demain matin' : 'Prochain jour ouvré matin';
    } else if (type === 'tomorrow-afternoon') {
        start.setDate(start.getDate() + 1);
        start = getNextBusinessDay(start);
        hour = 14;
        minute = 0;
        timeLabel = '14:00';
        label = start.getDate() === now.getDate() + 1 ? 'Demain après-midi' : 'Prochain jour ouvré 14h';
    } else if (type === 'monday-morning') {
        const day = now.getDay();
        const daysUntilMonday = (1 - day + 7) % 7;
        if (daysUntilMonday === 0) start.setDate(now.getDate() + 7);
        else start.setDate(now.getDate() + daysUntilMonday);
        start = getNextBusinessDay(start);
        hour = 9;
        minute = 0;
        timeLabel = '09:00';
        label = 'Lundi matin';
    }

    return {
        date: start,
        hour: hour,
        minute: minute,
        label: label,
        timeLabel: timeLabel
    };
}

/** Met à jour les libellés des boutons de suggestion (date/heure calculées selon now). */
function updateScheduleSuggestionLabels() {
    const list = document.querySelector('.schedule-suggestions-list');
    if (!list) return;
    ['tomorrow-morning', 'tomorrow-afternoon', 'monday-morning'].forEach(function(type) {
        const btn = list.querySelector('.schedule-suggestion[data-suggestion="' + type + '"]');
        if (!btn) return;
        const slot = getSuggestedScheduleSlot(type);
        const labelEl = btn.querySelector('.schedule-suggestion-label');
        const timeEl = btn.querySelector('.schedule-suggestion-time');
        if (labelEl) labelEl.textContent = slot.label;
        if (timeEl) timeEl.textContent = slot.timeLabel;
    });
}

// Afficher/masquer le bloc programmation ; initialiser date/heure seulement quand l'utilisateur choisit "Programmer"
function initScheduleFields() {
    const radios = document.querySelectorAll('input[name="send_mode"]');
    const scheduleBlock = document.getElementById('schedule-block');
    const suggestions = document.querySelectorAll('.schedule-suggestion');
    if (!radios.length || !scheduleBlock) return;

    function updateScheduleVisibility() {
        const checked = document.querySelector('input[name="send_mode"]:checked');
        const mode = checked ? checked.value : 'now';
        const isScheduled = mode === 'scheduled';
        scheduleBlock.style.display = isScheduled ? 'block' : 'none';
        scheduleBlock.setAttribute('aria-hidden', isScheduled ? 'false' : 'true');
        if (isScheduled) updateScheduleSuggestionLabels();
    }

    radios.forEach(function(radio) {
        radio.addEventListener('change', function() {
            updateScheduleVisibility();
            if (document.querySelector('input[name="send_mode"]:checked').value === 'scheduled') {
                setScheduleDateTimeToNow();
            }
        });
    });

    suggestions.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const type = btn.getAttribute('data-suggestion');
            const dateInput = document.getElementById('campagne-schedule-date');
            const timeInput = document.getElementById('campagne-schedule-time');
            if (!dateInput || !timeInput) return;

            const slot = getSuggestedScheduleSlot(type);
            const d = slot.date;
            const yyyy = d.getFullYear();
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            const dd = String(d.getDate()).padStart(2, '0');
            dateInput.value = yyyy + '-' + mm + '-' + dd;
            timeInput.value = String(slot.hour).padStart(2, '0') + ':' + String(slot.minute).padStart(2, '0');

            const scheduledRadio = document.querySelector('input[name="send_mode"][value="scheduled"]');
            if (scheduledRadio) scheduledRadio.checked = true;
            updateScheduleVisibility();
        });
    });

    updateScheduleVisibility();
}

// Charger les prospects selon l'objectif sélectionné
async function loadByObjectif() {
    const objectifId = document.getElementById('ciblage-objectif').value;
    if (!objectifId) return;
    const obj = objectifsCiblage.find(function(o) { return o.id === objectifId; });
    if (!obj || !obj.filters) return;
    await loadEntreprisesWithFilters(obj.filters);
}

// Charger les prospects selon les critères saisis
async function loadByCriteres() {
    await loadEntreprisesWithFilters(collectCiblageCriteresFromForm());
}

// Charger les prospects selon les groupes sélectionnés
async function loadByGroupes() {
    var groupeIds = getSelectedGroupIds();
    updateCiblageGroupesCount();
    if (groupeIds.length === 0) {
        var container = getStep1Container();
        if (container) container.innerHTML = '<div class="empty-state"><p>Sélectionnez au moins un groupe</p></div>';
        return;
    }
    await loadEntreprisesWithFilters({ groupe_ids: groupeIds });
}

// Charger les prospects selon le segment sauvegardé
async function loadBySegment() {
    var select = document.getElementById('ciblage-segment');
    if (!select) return;
    var segId = select.value;
    if (!segId) {
        clearCiblageSegmentMeta();
        return;
    }
    var opt = select.options[select.selectedIndex];
    var criteres = {};
    if (opt && opt.dataset.criteres) {
        try {
            criteres = JSON.parse(opt.dataset.criteres) || {};
        } catch (e) {
            criteres = {};
        }
    }
    var sumEl = document.getElementById('ciblage-segment-summary');
    var summaryText = formatCriteresSummary(criteres);
    if (sumEl) {
        sumEl.textContent = summaryText;
        sumEl.hidden = !summaryText;
    }
    await loadEntreprisesWithFilters(criteres);
    var metaEl = document.getElementById('ciblage-segment-preview-total');
    if (metaEl) {
        var n = (entreprisesData || []).length;
        metaEl.textContent = n
            ? n + ' entreprise(s) avec au moins un email pour ce segment.'
            : 'Aucune entreprise ne correspond à ce segment.';
    }
}

// Conteneur étape 1 : priorité entreprises-selector (3 steps), sinon recipients-selector (ancienne structure)
function getStep1Container() {
    return document.getElementById('entreprises-selector') || document.getElementById('recipients-selector');
}

// Appel API ciblage et mise à jour de la liste (étape 1 : entreprises uniquement)
function loadEntreprisesWithFilters(filters) {
    const container = getStep1Container();
    if (!container) return;
    container.innerHTML = '<div class="loading">Chargement des prospects...</div>';
    const params = new URLSearchParams();
    if (filters.secteur) params.set('secteur', filters.secteur);
    if (filters.secteur_contains) params.set('secteur_contains', filters.secteur_contains);
    if (filters.opportunite && filters.opportunite.length) params.set('opportunite', filters.opportunite.join(','));
    if (filters.statut) params.set('statut', filters.statut);
    if (filters.tags_contains) params.set('tags_contains', filters.tags_contains);
    if (filters.favori) params.set('favori', '1');
    if (filters.search) params.set('search', filters.search);
    if (filters.score_securite_max != null) params.set('score_securite_max', String(filters.score_securite_max));
    if (filters.exclude_already_contacted) params.set('exclude_already_contacted', '1');
    if (filters.groupe_ids && Array.isArray(filters.groupe_ids) && filters.groupe_ids.length > 0) {
        params.set('groupe_ids', filters.groupe_ids.join(','));
    }
    if (filters.etape_prospection) params.set('etape_prospection', filters.etape_prospection);
    if (filters.sort_commercial) params.set('sort_commercial', '1');
    if (filters.priority_min != null && String(filters.priority_min) !== '') {
        params.set('priority_min', String(filters.priority_min));
    }
    if (filters.commercial_profile_id != null && String(filters.commercial_profile_id) !== '') {
        params.set('commercial_profile_id', String(filters.commercial_profile_id));
    }
    if (filters.commercial_limit != null && String(filters.commercial_limit) !== '') {
        params.set('commercial_limit', String(filters.commercial_limit));
    }
    const url = '/api/ciblage/entreprises?' + params.toString();
    return fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            entreprisesData = data;
            selectedEntrepriseIds = [];
            displayEntreprisesStep1();
        })
        .catch(function() {
            container.innerHTML = '<div class="empty-state"><p>Erreur lors du chargement des prospects</p></div>';
        });
}

// Charger les entreprises avec emails (toutes, pas de filtre) - étape 1
async function loadEntreprises() {
    const container = getStep1Container();
    if (!container) return;
    try {
        const response = await fetch('/api/entreprises/emails');
        entreprisesData = await response.json();
        selectedEntrepriseIds = [];
        displayEntreprisesStep1();
    } catch (error) {
        container.innerHTML = '<div class="empty-state"><p>Erreur lors du chargement des entreprises</p></div>';
    }
}

// Étape 1 : afficher la liste des entreprises (checkboxes, sans détail des emails)
function displayEntreprisesStep1() {
    const container = getStep1Container();
    const countEl = document.getElementById('step1-results-count');
    if (!container) return;

    var list = (entreprisesData || []).slice();

    if (step1SearchTerm) {
        list = list.filter(function(ent) {
            var nom = (ent.nom || '').toLowerCase();
            var secteur = (ent.secteur || '').toLowerCase();
            var hasEmailMatch = (ent.emails || []).some(function(em) {
                return (em.email || '').toLowerCase().indexOf(step1SearchTerm) !== -1;
            });
            return nom.indexOf(step1SearchTerm) !== -1 ||
                   secteur.indexOf(step1SearchTerm) !== -1 ||
                   hasEmailMatch;
        });
    }

    if (!list || list.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>Aucune entreprise avec email disponible</p></div>';
        if (countEl) countEl.style.display = 'none';
        return;
    }

    var totalEmails = list.reduce(function(sum, e) { return sum + (e.emails && e.emails.length); }, 0);
    if (countEl) {
        countEl.textContent = list.length + ' entreprise(s), ' + totalEmails + ' email(s)';
        countEl.style.display = 'block';
    }

    container.innerHTML = list.map(function(ent) {
        var nb = (ent.emails && ent.emails.length) || 0;
        if (nb === 0) return '';
        var prioHtml = (ent.priority_score != null && !isNaN(Number(ent.priority_score)))
            ? '<div class="entreprise-priority-score">Priorité ' + Math.round(Number(ent.priority_score)) + '</div>'
            : '';
        return '<div class="entreprise-item step1-ent-item step1-card-clickable" data-entreprise-id="' + ent.id + '" onclick="toggleEntrepriseStep1ByCard(event, ' + ent.id + ')">' +
            '<div class="entreprise-header">' +
            '<div><div class="entreprise-name">' + escapeHtml(ent.nom) + '</div>' +
            (ent.secteur ? '<div class="entreprise-secteur">' + escapeHtml(ent.secteur) + '</div>' : '') +
            prioHtml +
            '<div class="entreprise-email-count">' + nb + ' email(s)</div>' +
            '</div>' +
            '<div class="checkbox-wrapper">' +
            '<input type="checkbox" id="ent-' + ent.id + '" onchange="toggleEntrepriseStep1(' + ent.id + ', this.checked)">' +
            '<label for="ent-' + ent.id + '">Sélectionner</label>' +
            '</div></div></div>';
    }).filter(Boolean).join('');
}

// Clic sur tout le cadre entreprise (étape 1) : toggle la sélection sauf si clic sur la case/label
function toggleEntrepriseStep1ByCard(event, entrepriseId) {
    if (event.target.closest('input[type="checkbox"]') || event.target.closest('label')) return;
    var cb = document.getElementById('ent-' + entrepriseId);
    if (!cb) return;
    cb.checked = !cb.checked;
    toggleEntrepriseStep1(entrepriseId, cb.checked);
}

// Étape 2 : clic sur toute la ligne email pour cocher/décocher la case
function toggleEmailByRow(event, entrepriseId, emailIdx) {
    if (event.target.closest('input[type="checkbox"]') || event.target.closest('label')) return;
    var cb = document.getElementById('email-' + entrepriseId + '-' + emailIdx);
    if (!cb) return;
    cb.checked = !cb.checked;
    toggleEmail(entrepriseId, emailIdx, cb.checked);
}

function toggleEntrepriseStep1(entrepriseId, checked) {
    var idx = selectedEntrepriseIds.indexOf(entrepriseId);
    if (checked && idx === -1) selectedEntrepriseIds.push(entrepriseId);
    if (!checked && idx !== -1) selectedEntrepriseIds.splice(idx, 1);
    var item = document.querySelector('.step1-ent-item[data-entreprise-id="' + entrepriseId + '"]');
    if (item) item.classList.toggle('selected', checked);
}

// Étape 2 : filtre emails sur les entreprises choisies, puis afficher la liste des emails
function displayEntreprisesStep2() {
    var source = entreprisesData.filter(function(e) { return selectedEntrepriseIds.indexOf(e.id) !== -1; });
    displayedEntreprisesData = applyEmailFilters(source);
    var container = document.getElementById('recipients-selector');
    var countEl = document.getElementById('ciblage-results-count');
    if (!container) return;

    if (displayedEntreprisesData.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>Aucun email ne correspond aux filtres. Assouplissez les critères ou choisissez d\'autres entreprises.</p></div>';
        if (countEl) countEl.style.display = 'none';
        return;
    }

    var totalEmails = displayedEntreprisesData.reduce(function(sum, e) { return sum + (e.emails && e.emails.length); }, 0);
    if (countEl) {
        countEl.textContent = displayedEntreprisesData.length + ' entreprise(s), ' + totalEmails + ' email(s)';
        countEl.style.display = 'block';
    }

    container.innerHTML = displayedEntreprisesData.map(function(entreprise) {
        var emails = entreprise.emails || [];
        if (emails.length === 0) return '';
        return '<div class="entreprise-item step2-card-clickable" data-entreprise-id="' + entreprise.id + '" onclick="toggleEntrepriseStep2ByCard(event, ' + entreprise.id + ')">' +
            '<div class="entreprise-header">' +
            '<div><div class="entreprise-name">' + escapeHtml(entreprise.nom) + '</div>' +
            (entreprise.secteur ? '<div class="entreprise-secteur">' + escapeHtml(entreprise.secteur) + '</div>' : '') +
            '</div>' +
            '<div class="checkbox-wrapper">' +
            '<input type="checkbox" id="entreprise-' + entreprise.id + '" onchange="toggleEntreprise(' + entreprise.id + ', this.checked)">' +
            '<label for="entreprise-' + entreprise.id + '">Tout sélectionner</label>' +
            '</div></div>' +
            '<div class="emails-list">' +
            emails.map(function(email, idx) {
                var dataEmail = escapeHtml(JSON.stringify(email));
                return '<div class="email-item email-row-clickable" onclick="toggleEmailByRow(event, ' + entreprise.id + ', ' + idx + ')">' +
                    '<input type="checkbox" id="email-' + entreprise.id + '-' + idx + '" data-email="' + dataEmail + '" onchange="toggleEmail(' + entreprise.id + ', ' + idx + ', this.checked)">' +
                    '<span class="email-address">' + escapeHtml(email.email) + '</span>' +
                    (email.nom && email.nom !== 'N/A' ? '<span> (' + escapeHtml(email.nom) + ')</span>' : '') +
                    '<span class="email-source">' + escapeHtml(email.source || '') + '</span>' +
                    '</div>';
            }).join('') +
            '</div></div>';
    }).filter(Boolean).join('');
    updateSelectedCount();
}

// Étape 2 : clic sur le cadre entreprise (hors cases & lignes email) -> tout sélectionner / tout désélectionner
function toggleEntrepriseStep2ByCard(event, entrepriseId) {
    // Si on clique sur une case, un label ou une ligne email, on laisse leurs handlers dédiés gérer
    if (event.target.closest('input[type="checkbox"]') ||
        event.target.closest('label') ||
        event.target.closest('.email-item')) {
        return;
    }

    var entreprise = displayedEntreprisesData.find(function(e) { return e.id === entrepriseId; });
    if (!entreprise) return;
    var emails = entreprise.emails || [];
    if (!emails.length) return;

    // Vérifier si tous les emails visibles de cette entreprise sont déjà cochés
    var allChecked = emails.every(function(email, idx) {
        var cb = document.getElementById('email-' + entrepriseId + '-' + idx);
        return cb && cb.checked;
    });

    var newChecked = !allChecked;

    // Mettre à jour la checkbox "Tout sélectionner"
    var headerCb = document.getElementById('entreprise-' + entrepriseId);
    if (headerCb) {
        headerCb.checked = newChecked;
    }

    // Appliquer sur tous les emails via la fonction existante
    toggleEntreprise(entrepriseId, newChecked);
}

// Afficher les entreprises (étape 2 uniquement, utilisé aussi quand les filtres email changent)
function displayEntreprises() {
    if (campagneModalStep !== 2) return;
    displayEntreprisesStep2();
}

// Toggle entreprise (sélectionner/désélectionner tous les emails affichés)
function toggleEntreprise(entrepriseId, checked) {
    const entreprise = displayedEntreprisesData.find(function(e) { return e.id === entrepriseId; });
    if (!entreprise) return;

    (entreprise.emails || []).forEach(function(email, idx) {
        var checkbox = document.getElementById('email-' + entrepriseId + '-' + idx);
        if (checkbox) {
            checkbox.checked = checked;
            toggleEmail(entrepriseId, idx, checked);
        }
    });
    updateEntrepriseItemStyle(entrepriseId, checked);
}

// Toggle email individuel
function toggleEmail(entrepriseId, emailIdx, checked) {
    const entreprise = displayedEntreprisesData.find(function(e) { return e.id === entrepriseId; });
    if (!entreprise || !entreprise.emails[emailIdx]) return;

    const email = entreprise.emails[emailIdx];
    const emailKey = `${email.email}-${email.entreprise_id}`;

    if (checked) {
        // Ajouter le destinataire : nom du contact > responsable entreprise > null
        var nomDest = (email.nom && email.nom !== 'N/A' && String(email.nom).trim()) ? email.nom : (entreprise.responsable && String(entreprise.responsable).trim()) ? entreprise.responsable : null;
        if (!selectedRecipients.find(r => r.email === email.email && r.entreprise_id === email.entreprise_id)) {
            selectedRecipients.push({
                email: email.email,
                nom: nomDest,
                entreprise: entreprise.nom,
                entreprise_id: email.entreprise_id
            });
        }
    } else {
        // Retirer le destinataire
        selectedRecipients = selectedRecipients.filter(
            r => !(r.email === email.email && r.entreprise_id === email.entreprise_id)
        );
    }

    updateSelectedCount();
    updateEntrepriseItemStyle(entrepriseId);
}

// Mettre à jour le style de l'item entreprise
function updateEntrepriseItemStyle(entrepriseId, forceChecked) {
    const item = document.querySelector('.entreprise-item[data-entreprise-id="' + entrepriseId + '"]');
    if (!item) return;

    const entreprise = displayedEntreprisesData.find(function(e) { return e.id === entrepriseId; });
    if (!entreprise) return;

    const emails = entreprise.emails || [];
    const allChecked = emails.every(function(email, idx) {
        var checkbox = document.getElementById('email-' + entrepriseId + '-' + idx);
        return checkbox && checkbox.checked;
    });
    const someChecked = emails.some(function(email, idx) {
        var checkbox = document.getElementById('email-' + entrepriseId + '-' + idx);
        return checkbox && checkbox.checked;
    });

    if (typeof forceChecked === 'boolean') {
        item.classList.toggle('selected', forceChecked);
    } else {
        item.classList.toggle('selected', someChecked);
    }
}

// Mettre à jour le compteur de sélection
function updateSelectedCount() {
    const countDiv = document.getElementById('selected-count');
    const count = selectedRecipients.length;
    
    if (countDiv) {
        if (count > 0) {
            countDiv.style.display = 'block';
            countDiv.textContent = `${count} destinataire(s) sélectionné(s)`;
        } else {
            countDiv.style.display = 'none';
        }
    }
}

/**
 * Initialise le bouton "Générer un email de prise de contact" (étape 3).
 * Utilise la première entreprise des destinataires sélectionnés pour générer un brouillon.
 */
function initGenerateContactEmailButton() {
    const btn = document.getElementById('btn-generate-contact-email');
    if (!btn) return;

    btn.addEventListener('click', async function () {
        if (!selectedRecipients || selectedRecipients.length === 0) {
            alert('Sélectionne au moins un destinataire à l\'étape 2 pour générer un email personnalisé.');
            return;
        }
        const first = selectedRecipients[0];
        const entrepriseId = first.entreprise_id;
        if (!entrepriseId) {
            alert('Impossible d\'identifier l\'entreprise pour ce destinataire.');
            return;
        }

        btn.disabled = true;
        const originalText = btn.textContent;
        btn.textContent = 'Génération en cours...';

        try {
            const res = await fetch(`/api/entreprise/${entrepriseId}/generate-contact-email`);
            const data = await res.json();
            if (!res.ok || !data || data.error) {
                throw new Error(data && data.error ? data.error : 'Erreur lors de la génération');
            }
            const sujetInput = document.getElementById('campagne-sujet');
            const messageTextarea = document.getElementById('campagne-message');
            if (sujetInput && (!sujetInput.value || sujetInput.value.trim() === '')) {
                sujetInput.value = data.subject || '';
            }
            if (messageTextarea) {
                messageTextarea.value = data.body || '';
                messageTextarea.focus();
            }
        } catch (e) {
            alert('Erreur: ' + (e && e.message ? e.message : e));
        } finally {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    });
}

// Actions rapides sur la sélection d'entreprises (étape 1)
function entreprisesStep1QuickSelect(mode) {
    var container = getStep1Container();
    if (!container) return;
    var items = container.querySelectorAll('.step1-ent-item[data-entreprise-id]');
    if (!items.length) return;

    items.forEach(function(item) {
        var idAttr = item.getAttribute('data-entreprise-id');
        var entrepriseId = parseInt(idAttr, 10);
        if (!entrepriseId || isNaN(entrepriseId)) return;
        var cb = document.getElementById('ent-' + entrepriseId);
        if (!cb) return;

        var newChecked;
        if (mode === 'all') {
            newChecked = true;
        } else if (mode === 'none') {
            newChecked = false;
        } else if (mode === 'invert') {
            newChecked = !cb.checked;
        } else {
            return;
        }

        cb.checked = newChecked;
        toggleEntrepriseStep1(entrepriseId, newChecked);
    });
}

// Actions rapides sur les destinataires (étape 2)
function recipientsQuickSelect(mode) {
    if (campagneModalStep !== 2) return;
    if (!Array.isArray(displayedEntreprisesData) || displayedEntreprisesData.length === 0) return;

    if (mode === 'all' || mode === 'none') {
        var checked = (mode === 'all');
        displayedEntreprisesData.forEach(function(ent) {
            toggleEntreprise(ent.id, checked);
        });
    } else if (mode === 'invert') {
        displayedEntreprisesData.forEach(function(ent) {
            var emails = ent.emails || [];
            emails.forEach(function(email, idx) {
                var cb = document.getElementById('email-' + ent.id + '-' + idx);
                if (!cb) return;
                var newChecked = !cb.checked;
                cb.checked = newChecked;
                toggleEmail(ent.id, idx, newChecked);
            });
            updateEntrepriseItemStyle(ent.id);
        });
    }

    updateSelectedCount();
}

// Ouvrir le modal de nouvelle campagne (toujours à l'étape 1)
function openNewCampagneModal() {
    selectedRecipients = [];
    selectedEntrepriseIds = [];
    var form = document.getElementById('campagne-form');
    if (form) form.reset();
    var selCount = document.getElementById('selected-count');
    if (selCount) selCount.style.display = 'none';
    var modal = document.getElementById('campagne-modal');
    if (modal) modal.style.display = 'block';
    campagneModalStep = 1;
    showCampagneStep(1);
    var modeToutes = document.querySelector('input[name="ciblage_mode"][value="toutes"]');
    if (modeToutes) modeToutes.checked = true;
    var blkObj = document.getElementById('ciblage-objectif-block');
    var blkCrit = document.getElementById('ciblage-criteres-block');
    var blkSeg = document.getElementById('ciblage-segment-block');
    if (blkObj) blkObj.style.display = 'none';
    if (blkCrit) blkCrit.style.display = 'none';
    if (blkSeg) blkSeg.style.display = 'none';
    loadCiblageSuggestionsWithCounts();
    loadEntreprises();
}

/**
 * Remet le formulaire campagne à l'état initial (étape 1, champs par défaut, bloc programmation masqué,
 * sélection entreprises et destinataires vidée).
 * Appelé à la fermeture du modal (annuler ou après envoi) pour que la prochaine ouverture soit propre.
 */
function resetCampagneForm() {
    var form = document.getElementById('campagne-form');
    if (form) form.reset();
    campagneModalStep = 1;
    showCampagneStep(1);
    var scheduleBlock = document.getElementById('schedule-block');
    if (scheduleBlock) {
        scheduleBlock.style.display = 'none';
        scheduleBlock.setAttribute('aria-hidden', 'true');
    }
    var nowRadio = document.querySelector('input[name="send_mode"][value="now"]');
    if (nowRadio) nowRadio.checked = true;

    selectedRecipients = [];
    selectedEntrepriseIds = [];
    var step1Container = document.getElementById('entreprises-selector');
    if (step1Container) {
        step1Container.querySelectorAll('input[type="checkbox"]').forEach(function(cb) {
            cb.checked = false;
        });
        step1Container.querySelectorAll('.step1-ent-item').forEach(function(el) {
            el.classList.remove('selected');
        });
    }
    updateSelectedCount();
}

// Fermer le modal et réinitialiser le formulaire
function closeModal() {
    var modal = document.getElementById('campagne-modal');
    if (modal) modal.style.display = 'none';
    resetCampagneForm();
}

// Soumettre la campagne
// Générer un nom de campagne automatique
/**
 * Génère un nom de campagne lisible à partir du template
 * et du contexte (secteur principal / exemple d'entreprise).
 * 
 * Objectif: produire un nom texte simple du type
 * "Présence en ligne - Technologie" sans icônes ni compteur.
 *
 * @param {string|null} templateName Nom du template sélectionné
 * @param {number} recipientCount Nombre de destinataires
 * @param {string|null} sectorLabel Secteur principal (ou null)
 * @param {string|null} entrepriseLabel Nom d'entreprise représentatif (ou null)
 * @returns {string} Nom de campagne
 */
function generateCampagneName(templateName, recipientCount, sectorLabel, entrepriseLabel) {
    // Libellés plus explicites en fonction du template
    let templateLabel = '';
    if (templateName) {
        const lower = templateName.toLowerCase();
        const keywordLabels = {
            'modernisation': 'Modernisation présence',
            'optimisation': 'Optimisation conversion',
            'sécurité': 'Sécurité & fiabilité',
            'présence': 'Présence en ligne',
            'audit': 'Audit digital'
        };
        for (const key in keywordLabels) {
            if (Object.prototype.hasOwnProperty.call(keywordLabels, key) && lower.indexOf(key) !== -1) {
                templateLabel = keywordLabels[key];
                break;
            }
        }
        if (!templateLabel) {
            templateLabel = templateName.trim();
        }
    } else {
        templateLabel = 'Campagne email';
    }

    // Secteur ou nom d'entreprise (court) - sert de "deuxième nom" / contexte
    let contextPart = '';
    if (sectorLabel) {
        const s = sectorLabel.trim();
        contextPart = s.length > 16 ? s.split(' ')[0] : s;
    } else if (entrepriseLabel) {
        const n = entrepriseLabel.trim();
        contextPart = n.length > 18 ? n.split(' ')[0] : n;
    }
    
    // Construire le nom final, sans icônes ni compteur
    const parts = [
        templateLabel,
        contextPart
    ].filter(function(p) { return p && p !== ''; });
    
    return parts.join(' ');
}

async function submitCampagne() {
    const form = document.getElementById('campagne-form');
    const formData = new FormData(form);

    const templateId = formData.get('template_id') || null;
    const sujet = formData.get('sujet');
    const customMessage = formData.get('custom_message') || null;
    const delay = parseInt(formData.get('delay')) || 2;
    const sendMode = formData.get('send_mode') || 'now';
    const scheduleDate = formData.get('schedule_date') || null;
    const scheduleTime = formData.get('schedule_time') || null;
    let scheduledAtIso = null;

    if (!sujet) {
        alert('Veuillez remplir le sujet de l\'email');
        return;
    }

    if (sendMode === 'scheduled') {
        if (!scheduleDate || !scheduleTime) {
            alert('Choisis une date et une heure pour programmer l\'envoi.');
            return;
        }
        // Interpréter date/heure en heure locale, puis convertir en ISO UTC pour le serveur
        const planned = new Date(scheduleDate + 'T' + scheduleTime);
        const now = new Date();
        if (planned.getTime() <= now.getTime()) {
            alert('La date/heure d\'envoi doit être dans le futur.');
            return;
        }
        scheduledAtIso = planned.toISOString();
    }

    // Générer automatiquement le nom de la campagne (en tenant compte du secteur / nom)
    const template = templatesData.find(t => t.id === templateId);
    const templateName = template ? template.name : null;
    // Contexte: secteur principal + exemple d'entreprise
    const context = getCampagneContext();
    const nom = generateCampagneName(
        templateName,
        selectedRecipients.length,
        context.sectorLabel,
        context.entrepriseLabel
    );

    if (selectedRecipients.length === 0) {
        alert('Veuillez sélectionner au moins un destinataire');
        return;
    }

    if (!templateId && !customMessage) {
        alert('Veuillez sélectionner un modèle ou saisir un message personnalisé');
        return;
    }

    /**
     * Détermine le secteur principal et un exemple d'entreprise
     * à partir des entreprises sélectionnées (étape 1).
     *
     * @returns {{sectorLabel: string|null, entrepriseLabel: string|null}}
     */
    function getCampagneContext() {
        if (!entreprisesData || !selectedEntrepriseIds || selectedEntrepriseIds.length === 0) {
            return { sectorLabel: null, entrepriseLabel: null };
        }
        const map = entreprisesData.filter(e => selectedEntrepriseIds.indexOf(e.id) !== -1);
        if (map.length === 0) {
            return { sectorLabel: null, entrepriseLabel: null };
        }
        // Secteur le plus fréquent
        const counts = {};
        map.forEach(e => {
            const s = (e.secteur || '').trim();
            if (!s) return;
            counts[s] = (counts[s] || 0) + 1;
        });
        let sectorLabel = null;
        let maxCount = 0;
        Object.entries(counts).forEach(([s, c]) => {
            if (c > maxCount) {
                maxCount = c;
                sectorLabel = s;
            }
        });
        const entrepriseLabel = map[0].nom || null;
        return { sectorLabel, entrepriseLabel };
    }

    const submitBtn = document.querySelector('.btn-submit');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Création en cours...';
    
    try {
        const response = await fetch('/api/campagnes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nom,
                template_id: templateId,
                sujet,
                recipients: selectedRecipients,
                custom_message: customMessage,
                delay,
                send_mode: sendMode,
                scheduled_at_iso: scheduledAtIso
            })
        });

        const data = await response.json();

        if (data.success) {
            closeModal();
            loadCampagnes();

            // Démarrer le monitoring WebSocket uniquement pour envoi immédiat (task_id présent)
            if (data.task_id && socket && socket.connected) {
                socket.emit('monitor_campagne', {
                    task_id: data.task_id,
                    campagne_id: data.campagne_id
                });
            }
        } else {
            alert('Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('Erreur lors de la création de la campagne');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Lancer la campagne';
    }
}

// Voir les détails d'une campagne
async function viewCampagne(campagneId) {
    try {
        const response = await fetch(`/api/campagnes/${campagneId}`);
        const campagne = await response.json();

        // Ouvrir la modale de résultats avec le nom de la campagne
        openResultsModal(campagneId, campagne.nom);
    } catch (error) {
        alert('Erreur lors du chargement des détails');
    }
}

// Ouvrir la modale de résultats
function openResultsModal(campagneId, campagneName) {
    const modal = document.getElementById('results-modal');
    const campagneNameEl = document.getElementById('results-campagne-name');
    const body = document.getElementById('results-modal-body');

    if (campagneNameEl) {
        campagneNameEl.textContent = campagneName || `Campagne #${campagneId}`;
    }

    // Sauvegarder l'ID courant et annuler un éventuel ancien timer
    currentResultsCampagneId = campagneId;
    if (resultsRefreshTimer) {
        clearInterval(resultsRefreshTimer);
        resultsRefreshTimer = null;
    }

    // Afficher le loading
    body.innerHTML = `
        <div class="results-loading">
            <div class="loading-spinner"></div>
            <p>Chargement des résultats...</p>
        </div>
    `;

    modal.classList.add('show');

    // Charger les statistiques immédiatement
    loadCampagneResults(campagneId);

    // Mettre à jour les résultats en temps réel tant que la modale est ouverte
    resultsRefreshTimer = setInterval(function() {
        if (!document.body.contains(modal) || !modal.classList.contains('show')) {
            clearInterval(resultsRefreshTimer);
            resultsRefreshTimer = null;
            return;
        }
        if (currentResultsCampagneId) {
            loadCampagneResults(currentResultsCampagneId, true);
        }
    }, 8000);
}

// Fermer la modale de résultats
function closeResultsModal() {
    const modal = document.getElementById('results-modal');
    modal.classList.remove('show');

    // Arrêter le rafraîchissement en temps réel
    if (resultsRefreshTimer) {
        clearInterval(resultsRefreshTimer);
        resultsRefreshTimer = null;
    }
    currentResultsCampagneId = null;
}

// Envoyer le rapport de la campagne courante par email
async function sendResultsReportByEmail() {
    if (!currentResultsCampagneId) {
        alert('Aucune campagne sélectionnée.');
        return;
    }

    const btn = document.querySelector('.btn-results-send-email');
    if (btn) {
        btn.disabled = true;
        const originalText = btn.textContent;
        btn.textContent = 'Envoi en cours...';
        try {
            const res = await fetch(`/api/campagnes/${currentResultsCampagneId}/send-report-email`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data && data.message ? data.message : 'Erreur lors de l\'envoi du rapport');
            }
            showNotification('Rapport envoyé par email à contact@danielcraft.fr', 'success');
        } catch (e) {
            showNotification('Erreur: ' + (e && e.message ? e.message : e), 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    }
}

// Charger les résultats de la campagne
async function loadCampagneResults(campagneId, silent) {
    try {
        const response = await fetch(`/api/tracking/campagne/${campagneId}`);
        const stats = await response.json();

        displayCampagneResults(stats, !!silent);
    } catch (error) {
        if (!silent) {
        const body = document.getElementById('results-modal-body');
        body.innerHTML = `
            <div class="results-loading">
                <p style="color: #e74c3c;">Erreur lors du chargement des résultats</p>
            </div>
        `;
        }
    }
}

// Afficher les résultats de la campagne
function displayCampagneResults(stats, silentRefresh) {
    const body = document.getElementById('results-modal-body');

    const openRate = stats.open_rate ? stats.open_rate.toFixed(1) : '0.0';
    const clickRate = stats.click_rate ? stats.click_rate.toFixed(1) : '0.0';
    const sentCount = stats.total_emails || 0;
    const openCount = stats.total_opens || 0;
    const clickCount = stats.total_clicks || 0;
    const bouncedCount = typeof stats.total_bounced === 'number'
        ? stats.total_bounced
        : (Array.isArray(stats.emails)
            ? stats.emails.filter(function(e) { return e && e.statut === 'bounced'; }).length
            : 0);
    const deliverability = typeof stats.deliverability_rate_strict === 'number'
        ? stats.deliverability_rate_strict
        : 0;
    const hasReadTime = stats.avg_read_time != null && !isNaN(stats.avg_read_time);
    const avgReadTime = hasReadTime ? Math.round(stats.avg_read_time) : null;

    // Fonction pour obtenir le badge de statut
    function getStatusBadge(statut, hasOpened, hasClicked) {
        if (statut === 'bounced') {
            return '<span class="status-badge status-bounced">Bounce</span>';
        }
        if (statut === 'failed') {
            return '<span class="status-badge status-failed">Échec</span>';
        }
        if (hasClicked) {
            return '<span class="status-badge status-clicked">Clic</span>';
        }
        if (hasOpened) {
            return '<span class="status-badge status-opened">Ouvert</span>';
        }
        return '<span class="status-badge status-sent">Envoyé</span>';
    }

    // Si on est en rafraîchissement silencieux et que la structure existe déjà,
    // on met à jour en place pour éviter un flash complet.
    if (silentRefresh) {
        const container = body.querySelector('.results-content');
        if (container) {
            // Mettre à jour le header de synthèse
            const sentEl = container.querySelector('[data-summary="sent"]');
            const delivEl = container.querySelector('[data-summary="deliv"]');
            const openEl = container.querySelector('[data-summary="open"]');
            const clickEl = container.querySelector('[data-summary="click"]');
            const readEl = container.querySelector('[data-summary="read"]');
            const bounceEl = container.querySelector('[data-summary="bounce"]');
            if (sentEl) sentEl.textContent = sentCount;
            if (delivEl) delivEl.textContent = `${(Number(deliverability) || 0).toFixed(1)}%`;
            if (openEl) openEl.textContent = `${openRate}%`;
            if (clickEl) clickEl.textContent = `${clickRate}%`;
            if (readEl) readEl.textContent = avgReadTime !== null ? `${avgReadTime}s` : 'Non mesuré';
            if (bounceEl) bounceEl.textContent = bouncedCount;

            // Mettre à jour le mini graphe de performance
            const miniChart = container.querySelector('.campaign-mini-chart');
            if (miniChart) {
                // Base du tunnel = délivrabilité stricte (réussis - bounces) / destinataires
                const sendRate = Number(deliverability) || 0;
                const openNum = Number(openRate) || 0;
                const clickNum = Number(clickRate) || 0;
                const bars = miniChart.querySelectorAll('.mini-chart-bar-fill');
                const labels = miniChart.querySelectorAll('.mini-chart-row strong');
                if (bars.length >= 3) {
                    bars[0].style.width = clampPercent(sendRate) + '%';
                    bars[1].style.width = clampPercent(openNum) + '%';
                    bars[2].style.width = clampPercent(clickNum) + '%';
                }
                if (labels.length >= 3) {
                    labels[0].textContent = `${(Number(deliverability) || 0).toFixed(1)}%`;
                    labels[1].textContent = `${openRate}%`;
                    labels[2].textContent = `${clickRate}%`;
                }
            }

            // Mettre à jour le donut d'engagement
            const openRing = container.querySelector('[data-donut="open"]');
            const clickRing = container.querySelector('[data-donut="click"]');
            if (openRing) {
                openRing.style.setProperty('--pct', clampPercent(Number(openRate)));
                openRing.querySelector('strong').textContent = `${openRate}%`;
            }
            if (clickRing) {
                clickRing.style.setProperty('--pct', clampPercent(Number(clickRate)));
                clickRing.querySelector('strong').textContent = `${clickRate}%`;
            }

            // Mettre à jour le tableau des emails
            const tbody = container.querySelector('.results-table tbody');
            if (tbody && stats.emails && stats.emails.length > 0) {
                tbody.innerHTML = stats.emails.map(function(email) {
                    const rowClass = (email && email.statut === 'bounced')
                        ? 'row-bounced'
                        : (email.has_clicked ? 'row-clicked' : (email.has_opened ? 'row-opened' : ''));
                    return (
                        '<tr class="' + rowClass + '">' +
                            '<td>' +
                                '<div class="contact-name">' + formatContactName(email.nom_destinataire) + '</div>' +
                                '<div class="contact-email">' + escapeHtml(email.email) + '</div>' +
                            '</td>' +
                            '<td>' + escapeHtml(email.entreprise || 'N/A') + '</td>' +
                            '<td class="text-center">' + getStatusBadge(email.statut, email.has_opened, email.has_clicked) + '</td>' +
                            '<td class="text-center">' +
                                (email.opens > 0
                                    ? '<span class="stat-value stat-opens">' + email.opens + '</span>'
                                    : '<span class="stat-value stat-zero">0</span>') +
                            '</td>' +
                            '<td class="text-center">' +
                                (email.clicks > 0
                                    ? '<span class="stat-value stat-clicks">' + email.clicks + '</span>'
                                    : '<span class="stat-value stat-zero">0</span>') +
                            '</td>' +
                            '<td class="text-muted">' + formatDate(email.date_envoi) + '</td>' +
                            '<td class="text-muted">' + formatDate(email.last_open) + '</td>' +
                            '<td class="text-center">' +
                                '<button type="button" class="btn-email-preview" onclick="openSentEmailPreview(' + email.id + ')">Voir l\'email</button>' +
                            '</td>' +
                        '</tr>'
                    );
                }).join('');
            }

            return;
        }
    }

    // Rendu complet (premier affichage ou fallback)
    // Tableau des emails
    let emailsTable = '';
    if (stats.emails && stats.emails.length > 0) {
        emailsTable = `
            <div class="results-section">
                <h3 class="results-section-title">Détails par contact (${stats.emails.length})</h3>
                <div class="results-table-container">
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th>Contact</th>
                                <th>Entreprise</th>
                                <th class="text-center">Statut</th>
                                <th class="text-center">Ouvertures</th>
                                <th class="text-center">Clics</th>
                                <th>Date envoi</th>
                                <th>Dernière ouverture</th>
                                <th class="text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${stats.emails.map(email => `
                                <tr class="${email && email.statut === 'bounced' ? 'row-bounced' : (email.has_clicked ? 'row-clicked' : email.has_opened ? 'row-opened' : '')}">    
                                    <td>
                                        <div class="contact-name">${formatContactName(email.nom_destinataire)}</div>      
                                        <div class="contact-email">${escapeHtml(email.email)}</div>
                                    </td>
                                    <td>${escapeHtml(email.entreprise || 'N/A')}</td>
                                    <td class="text-center">${getStatusBadge(email.statut, email.has_opened, email.has_clicked)}</td>                                                                                                                   
                                    <td class="text-center">
                                        ${email.opens > 0 ? `<span class="stat-value stat-opens">${email.opens}</span>` : '<span class="stat-value stat-zero">0</span>'}                                                                                
                                    </td>
                                    <td class="text-center">
                                        ${email.clicks > 0 ? `<span class="stat-value stat-clicks">${email.clicks}</span>` : '<span class="stat-value stat-zero">0</span>'}                                                                             
                                    </td>
                                    <td class="text-muted">${formatDate(email.date_envoi)}</td>
                                    <td class="text-muted">${formatDate(email.last_open)}</td>
                                    <td class="text-center">
                                        <button type="button" class="btn-email-preview" onclick="openSentEmailPreview(${email.id})">Voir l'email</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    body.innerHTML = `
        <div class="results-content">
            <h2 class="results-main-title">Statistiques de prospection</h2>

            <div class="results-summary-strip">
                <div class="summary-chip">
                    <span>Emails envoyés</span>
                    <strong data-summary="sent">${sentCount}</strong>
                </div>
                <div class="summary-chip">
                    <span>Envoi</span>
                    <strong data-summary="deliv">${(Number(deliverability) || 0).toFixed(1)}%</strong>
                </div>
                <div class="summary-chip">
                    <span>Bounces</span>
                    <strong data-summary="bounce">${bouncedCount}</strong>
                </div>
                <div class="summary-chip">
                    <span>Taux d'ouverture</span>
                    <strong data-summary="open">${openRate}%</strong>
                </div>
                <div class="summary-chip">
                    <span>Taux de clic</span>
                    <strong data-summary="click">${clickRate}%</strong>
                </div>
                <div class="summary-chip">
                    <span>Temps lecture moyen</span>
                    <strong data-summary="read">${avgReadTime !== null ? `${avgReadTime}s` : 'Non mesuré'}</strong>
                </div>
            </div>

            <div class="results-visual-grid">
                <div class="results-visual-card">
                    <h3>Tunnel de conversion</h3>
                    <div class="campaign-mini-chart">
                        <div class="mini-chart-row">
                            <span>Envoi</span>
                            <strong>${(Number(deliverability) || 0).toFixed(1)}%</strong>
                        </div>
                        <div class="mini-chart-bar"><span class="mini-chart-bar-fill" style="width:${clampPercent(Number(deliverability))}%"></span></div>
                        <div class="mini-chart-row">
                            <span>Ouverture</span>
                            <strong>${openRate}%</strong>
                        </div>
                        <div class="mini-chart-bar mini-chart-open"><span class="mini-chart-bar-fill" style="width:${clampPercent(Number(openRate))}%"></span></div>
                        <div class="mini-chart-row">
                            <span>Clic</span>
                            <strong>${clickRate}%</strong>
                        </div>
                        <div class="mini-chart-bar mini-chart-click"><span class="mini-chart-bar-fill" style="width:${clampPercent(Number(clickRate))}%"></span></div>
                        <div class="mini-chart-hint">Base = envoi (délivrabilité stricte)</div>
                    </div>
                </div>
                <div class="results-visual-card">
                    <h3>Engagement</h3>
                    <div class="engagement-donuts">
                        <div class="engagement-donut" data-donut="open" style="--pct:${clampPercent(Number(openRate))}">
                            <div class="donut-ring"></div>
                            <div class="donut-center">
                                <span>Ouverture</span>
                                <strong>${openRate}%</strong>
                            </div>
                        </div>
                        <div class="engagement-donut is-click" data-donut="click" style="--pct:${clampPercent(Number(clickRate))}">
                            <div class="donut-ring"></div>
                            <div class="donut-center">
                                <span>Clic</span>
                                <strong>${clickRate}%</strong>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            ${emailsTable}
        </div>
    `;
}

async function openSentEmailPreview(emailId) {
    if (!emailId) return;
    let previewModal = document.getElementById('sent-email-preview-modal');
    if (!previewModal) {
        previewModal = document.createElement('div');
        previewModal.id = 'sent-email-preview-modal';
        previewModal.className = 'sent-email-preview-modal';
        previewModal.innerHTML = `
            <div class="sent-email-preview-content">
                <div class="sent-email-preview-header">
                    <h3 id="sent-email-preview-title">Email envoyé</h3>
                    <button type="button" class="sent-email-preview-close" onclick="closeSentEmailPreview()">&times;</button>
                </div>
                <div class="sent-email-preview-body" id="sent-email-preview-body"></div>
            </div>
        `;
        previewModal.addEventListener('click', function(event) {
            if (event.target === previewModal) closeSentEmailPreview();
        });
        document.body.appendChild(previewModal);
    }

    previewModal.classList.add('show');
    const body = document.getElementById('sent-email-preview-body');
    if (body) {
        body.innerHTML = '<div class="results-loading"><p>Chargement de l\'email envoyé...</p></div>';
    }

    try {
        const response = await fetch('/api/emails-envoyes/' + emailId + '/preview');
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data && data.error ? data.error : 'Erreur lors du chargement');
        }
        const title = document.getElementById('sent-email-preview-title');
        if (title) {
            title.textContent = data.sujet ? ('Email envoyé - ' + data.sujet) : 'Email envoyé';
        }
        const sentContent = data.contenu_envoye || '';
        const looksLikeHtml = /<([a-z][\s\S]*?)>/i.test(sentContent);
        if (body) {
            body.innerHTML = `
                <div class="sent-email-meta">
                    <div><strong>Destinataire:</strong> ${escapeHtml(data.email || '-')}</div>
                    <div><strong>Entreprise:</strong> ${escapeHtml(data.entreprise || '-')}</div>
                    <div><strong>Envoyé:</strong> ${escapeHtml(formatDate(data.date_envoi))}</div>
                </div>
                ${looksLikeHtml
                    ? `<iframe class="sent-email-frame" title="Contenu email"></iframe>`
                    : `<pre class="sent-email-text">${escapeHtml(sentContent || 'Contenu indisponible')}</pre>`}
            `;
            if (looksLikeHtml) {
                const frame = body.querySelector('.sent-email-frame');
                if (frame) {
                    const frameDoc = frame.contentDocument || frame.contentWindow.document;
                    frameDoc.open();
                    frameDoc.write(sentContent);
                    frameDoc.close();
                }
            }
        }
    } catch (error) {
        if (body) {
            body.innerHTML = '<div class="results-loading"><p style="color:#dc2626;">Impossible de charger cet email.</p></div>';
        }
    }
}

function closeSentEmailPreview() {
    const previewModal = document.getElementById('sent-email-preview-modal');
    if (previewModal) previewModal.classList.remove('show');
}

// Fermer la modale en cliquant en dehors
document.addEventListener('click', function(event) {
    const modal = document.getElementById('results-modal');
    if (event.target === modal) {
        closeResultsModal();
    }
});

// Supprimer une campagne
async function deleteCampagne(campagneId) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette campagne ?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/campagnes/${campagneId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            loadCampagnes();
        } else {
            alert('Erreur lors de la suppression');
        }
    } catch (error) {
        alert('Erreur lors de la suppression');
    }
}

async function relaunchCampagne(campagneId) {
    if (!confirm('Relancer cette campagne avec les mêmes destinataires ?')) {
        return;
    }

    try {
        const response = await fetch(`/api/campagnes/${campagneId}/relaunch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data && data.error ? data.error : 'Relance impossible');
        }

        showNotification('Campagne relancée avec succès', 'success');
        loadCampagnes();
    } catch (error) {
        showNotification('Erreur de relance: ' + (error && error.message ? error.message : 'Erreur inconnue'), 'error');
    }
}

// Initialiser WebSocket pour le suivi en temps réel
function initWebSocket() {
    if (typeof io === 'undefined') {
        return;
    }
    
    socket = io();

    socket.on('connect', function() {
        // Connexion WebSocket établie
    });

    socket.on('campagne_progress', function(data) {
        updateCampagneProgress(data);
    });

    socket.on('campagne_complete', function(data) {
        updateCampagneProgress({
            campagne_id: data.campagne_id,
            progress: 100,
            current: data.result?.total || 0,
            total: data.result?.total || 0,
            sent: data.result?.total_sent || 0,
            failed: data.result?.total_failed || 0,
            message: 'Terminé'
        });

        // Recharger pour mettre à jour le statut
        loadCampagnes();

        // Afficher une notification de succès
        const totalSent = data.result?.total_sent || 0;
        const totalFailed = data.result?.total_failed || 0;
        showNotification(`Campagne terminée ! ${totalSent} emails envoyés${totalFailed > 0 ? `, ${totalFailed} échecs` : ''}`, 'success');                                                                                                              
    });

    socket.on('campagne_error', function(data) {
        // Mettre à jour l'affichage pour montrer l'erreur
        const card = document.querySelector(`[data-campagne-id="${data.campagne_id}"]`);
        if (card) {
            const progressContainer = card.querySelector('.progress-bar-container');
            if (progressContainer) {
                progressContainer.innerHTML = `
                    <div class="error-message" style="color: #dc3545; padding: 8px; background: #f8d7da; border-radius: 4px; margin-top: 8px;">                                                                                                         
                        ❌ Erreur: ${escapeHtml(data.error || 'Erreur inconnue')}
                    </div>
                `;
            }
        }
        // Recharger pour mettre à jour le statut
        loadCampagnes();
        showNotification('Erreur lors de l\'envoi de la campagne: ' + (data.error || 'Erreur inconnue'), 'error');
    });
}

// Mettre à jour la progression d'une campagne en temps réel
function updateCampagneProgress(data) {
    const campagneId = data.campagne_id;
    const progress = data.progress || 0;
    const current = data.current || 0;
    const total = data.total || 0;
    const sent = data.sent || 0;
    const failed = data.failed || 0;
    const message = data.message || 'Envoi en cours...';

    // Trouver la carte de campagne correspondante
    const card = document.querySelector(`[data-campagne-id="${campagneId}"]`);
    if (!card) {
        // Si la carte n'existe pas, recharger les campagnes
        loadCampagnes();
        return;
    }

    // Mettre à jour les stats
    const statItems = card.querySelectorAll('.stat-item');
    if (statItems.length >= 3) {
        // Destinataires
        statItems[0].querySelector('.stat-value').textContent = total;
        // Envoyés
        statItems[1].querySelector('.stat-value').textContent = sent;
        // Réussis
        statItems[2].querySelector('.stat-value').textContent = sent - failed;
    }

    // Mettre à jour la barre de progression
    let progressContainer = card.querySelector('.progress-bar-container');
    if (!progressContainer) {
        // Créer le conteneur de progression s'il n'existe pas
        const actionsDiv = card.querySelector('.campagne-actions');
        if (actionsDiv) {
            progressContainer = document.createElement('div');
            progressContainer.className = 'progress-bar-container';
            actionsDiv.parentNode.insertBefore(progressContainer, actionsDiv.nextSibling);
        } else {
            return;
        }
    }

    // Construire un message propre
    let progressMessage;
    if (message && message.trim() !== '') {
        // Utiliser le message du backend tel quel
        progressMessage = message;
    } else if (current > 0 && total > 0) {
        // Construire un message si aucun n'est fourni
        progressMessage = `Envoi ${current}/${total}`;
    } else {
        progressMessage = 'Envoi en cours...';
    }
    
    // S'assurer que le message n'est jamais vide
    if (!progressMessage || progressMessage.trim() === '') {
        progressMessage = `Envoi ${current || 0}/${total || 0}`;
    }
    
    // Créer les éléments séparément pour s'assurer qu'ils sont bien insérés
    progressContainer.innerHTML = `
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${progress}%">
                ${progress}%
            </div>
        </div>
    `;
    
    // Ajouter le texte dans un élément séparé pour forcer l'affichage
    const textElement = document.createElement('div');
    textElement.className = 'progress-text';
    textElement.style.cssText = 'color: #333 !important; display: block !important; visibility: visible !important; opacity: 1 !important; text-align: center; margin-top: 10px; padding: 5px; font-size: 0.9em; line-height: 1.4;';
    textElement.textContent = progressMessage;
    progressContainer.appendChild(textElement);

    // Mettre à jour le statut si nécessaire
    const statutBadge = card.querySelector('.campagne-statut');
    if (statutBadge && progress < 100) {
        statutBadge.textContent = 'running';
        statutBadge.className = 'campagne-statut statut-running';
    }
}

// Afficher une notification
function showNotification(message, type = 'info') {
    // Créer un élément de notification
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: ${type === 'success' ? '#d4edda' : type === 'error' ? '#f8d7da' : '#d1ecf1'};
        color: ${type === 'success' ? '#155724' : type === 'error' ? '#721c24' : '#0c5460'};
        border: 1px solid ${type === 'success' ? '#c3e6cb' : type === 'error' ? '#f5c6cb' : '#bee5eb'};
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        z-index: 10000;
        max-width: 400px;
        animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    // Supprimer après 5 secondes
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}

// Ajouter les styles d'animation si pas déjà présents
if (!document.getElementById('notification-styles')) {
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}

// Utilitaires
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = parseDateLoose(dateString);
    if (Number.isNaN(date.getTime())) return dateString;
    return date.toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
}

function formatRelativeDate(dateString) {
    if (!dateString) return 'Date inconnue';
    const date = parseDateLoose(dateString);
    if (Number.isNaN(date.getTime())) return 'Date inconnue';

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    if (diffMs < 0) return 'Dans quelques instants';
    const minute = 60 * 1000;
    const hour = 60 * minute;
    const day = 24 * hour;

    if (diffMs < minute) return 'A l\'instant';
    if (diffMs < hour) {
        const m = Math.floor(diffMs / minute);
        return 'Il y a ' + m + ' min';
    }
    if (diffMs < day) {
        const h = Math.floor(diffMs / hour);
        return 'Il y a ' + h + ' h';
    }
    const d = Math.floor(diffMs / day);
    if (d < 7) return 'Il y a ' + d + ' jour' + (d > 1 ? 's' : '');
    return 'Il y a ' + Math.floor(d / 7) + ' sem';
}

function parseDateLoose(value) {
    if (!value) return new Date('invalid');
    const raw = String(value).trim();

    // 1) Tentative directe (gère RFC1123 type "Fri, 27 Mar 2026 10:00:36 GMT")
    let d = new Date(raw);
    if (!Number.isNaN(d.getTime())) return d;

    // 2) Normalisation simple des formats DB "YYYY-MM-DD HH:MM:SS"
    let s = raw.replace(/\s+GMT$/i, 'Z').replace(/\s+UTC$/i, 'Z');
    s = s.replace(' ', 'T');
    d = new Date(s);
    if (!Number.isNaN(d.getTime())) return d;

    // 3) Dernier essai: enlever un suffixe timezone texte (ex: "GMT+0000 (UTC)")
    s = raw.replace(/\s+GMT[+-]\d{4}.*$/i, '').trim().replace(' ', 'T');
    d = new Date(s);
    return d;
}

function getCampaignStatusLabel(statut) {
    const s = String(statut || '').trim().toLowerCase();
    if (s === 'completed_with_errors') return 'Terminée avec erreurs';
    if (s === 'completed') return 'Terminée';
    if (s === 'running') return 'En cours';
    if (s === 'scheduled') return 'Programmée';
    if (s === 'failed') return 'Échec';
    if (s === 'draft') return 'Brouillon';
    return statut || 'Inconnu';
}

function getEffectiveCampaignStatus(campagne) {
    const raw = String((campagne && campagne.statut) || '').trim().toLowerCase();
    const totalReussis = Number(campagne && campagne.total_reussis) || 0;
    const totalEnvoyes = Number(campagne && campagne.total_envoyes) || 0;
    // Compat historique: certaines campagnes anciennes restent en "failed"
    // alors qu'il y a eu des envois réussis.
    if (raw === 'failed' && totalReussis > 0 && totalEnvoyes > 0) {
        return 'completed_with_errors';
    }
    return raw || 'draft';
}

function shouldShowRelaunchButton(campagne) {
    const status = String((campagne && campagne.statut) || '').trim().toLowerCase();
    if (status === 'failed') return true;

    const dest = Number(campagne && campagne.total_destinataires) || 0;
    if (dest < 10) return false;

    // On utilise la même base que l'UI "Envoi" pour éviter tout écart.
    // Priorité: total_delivered_strict (API) -> sinon total_delivered -> sinon total_envoyes.
    const delivered = (campagne && campagne.total_delivered_strict != null)
        ? Number(campagne.total_delivered_strict)
        : (campagne && campagne.total_delivered != null)
            ? Number(campagne.total_delivered)
            : Number(campagne && campagne.total_envoyes);

    if (!Number.isFinite(delivered)) return false;
    const rate = safeRate(delivered, dest);

    // "Envoi très faible" : on évite d'afficher le bouton si c'est juste une campagne avec quelques bounces.
    // Seuil volontairement strict (relancer uniquement quand ça a vraiment foiré).
    return rate < 40;
}

function safeRate(part, total) {
    const num = Number(part) || 0;
    const den = Number(total) || 0;
    if (den <= 0) return 0;
    return (num / den) * 100;
}

function formatPercent(value) {
    const v = Number.isFinite(value) ? value : 0;
    return v.toFixed(1) + '%';
}

function clampPercent(value) {
    const v = Number.isFinite(value) ? value : 0;
    return Math.max(0, Math.min(100, Math.round(v)));
}

function formatContactName(nomDestinataire) {
    if (!nomDestinataire || nomDestinataire === 'N/A') return 'N/A';
    
    // Si c'est déjà formaté (pas de JSON), retourner tel quel
    if (!nomDestinataire.startsWith('{') && !nomDestinataire.startsWith('[')) {
        return escapeHtml(nomDestinataire);
    }
    
    // Si c'est une chaîne JSON, essayer de la parser
    try {
        const parsed = JSON.parse(nomDestinataire);
        if (parsed && typeof parsed === 'object') {
            if (parsed.full_name) {
                return escapeHtml(parsed.full_name);
            }
            if (parsed.first_name || parsed.last_name) {
                const parts = [parsed.first_name, parsed.last_name].filter(Boolean);
                return escapeHtml(parts.join(' ') || 'N/A');
            }
        }
    } catch (e) {
        // Si le parsing échoue, retourner tel quel
    }
    
    // Sinon, retourner tel quel
    return escapeHtml(nomDestinataire);
}

