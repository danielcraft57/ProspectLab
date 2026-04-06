/**
 * API pour les entreprises
 */

(function(window) {
    'use strict';
    
    const EntreprisesAPI = {
        /**
         * Charge les entreprises avec pagination serveur.
         * @param {Object} [filters] - Filtres (secteur, statut, opportunite, favori, search, security_min, security_max, pentest_min, pentest_max, seo_min, seo_max)
         * @param {number} [page] - Numéro de page (1-based)
         * @param {number} [pageSize] - Taille de page
         * @param {boolean} [includeOg] - Inclure ou non les données OpenGraph (par défaut false pour la liste)
         * @param {number|null} [analyseId] - Filtrer par ID d'analyse (optionnel)
         * @returns {Promise<{items: Array, total: number, page: number, page_size: number}>}
         */
        async loadAll(filters = {}, page = 1, pageSize = 20, includeOg = false, analyseId = null) {
            const params = new URLSearchParams();
            Object.keys(filters).forEach(key => {
                const v = filters[key];
                if (v === undefined || v === null || v === '') return;
                if (Array.isArray(v)) {
                    if (!v.length) return;
                    if (key === 'tags_any' || key === 'tags_all') {
                        params.set(key, v.join(','));
                        return;
                    }
                }
                params.set(key, String(v));
            });
            if (analyseId !== null && analyseId !== undefined) {
                const id = Number(analyseId);
                if (!Number.isNaN(id)) {
                    params.set('analyse_id', String(id));
                }
            }
            params.set('page', String(page));
            params.set('page_size', String(pageSize));
            if (includeOg) {
                params.set('include_og', '1');
            }
            const qs = params.toString();
            const url = `/api/entreprises?${qs}`;
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erreur lors du chargement des entreprises');
            return await response.json();
        },
        
        /**
         * Charge les secteurs disponibles
         * @returns {Promise<Array>}
         */
        async loadSecteurs() {
            const response = await fetch('/api/secteurs');
            if (!response.ok) throw new Error('Erreur lors du chargement des secteurs');
            return await response.json();
        },

        /**
         * Charge les opportunites disponibles (valeurs distinctes en base).
         * @returns {Promise<Array>}
         */
        async loadOpportunites() {
            const response = await fetch('/api/opportunites');
            if (!response.ok) throw new Error('Erreur lors du chargement des opportunites');
            return await response.json();
        },
        
        /**
         * Charge les détails d'une entreprise
         * @param {number} id
         * @returns {Promise<Object>}
         */
        async loadDetails(id) {
            const response = await fetch(`/api/entreprise/${id}`);
            if (!response.ok) throw new Error('Erreur lors du chargement des détails');
            return await response.json();
        },

        /**
         * Recalcule le score d'opportunité d'une entreprise et retourne le détail.
         * @param {number} id
         * @returns {Promise<{success: boolean, opportunity?: string, score?: number, breakdown?: Object, indicators?: Array}>}
         */
        async recalculateOpportunity(id) {
            const response = await fetch(`/api/entreprise/${id}/recalculate-opportunity`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Erreur lors du recalcul de l\'opportunité');
            return await response.json();
        },

        /**
         * Recalcule les opportunités en bulk (une requête).
         * @param {Array<number>} ids
         * @returns {Promise<{success: boolean, total: number, ok: number, failed: number, results?: Array}>}
         */
        async recalculateOpportunitiesBulk(ids) {
            const response = await fetch('/api/entreprises/recalculate-opportunities', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids || [] })
            });
            if (!response.ok) throw new Error('Erreur lors du recalcul des opportunités');
            return await response.json();
        },
        
        /**
         * Toggle le statut favori d'une entreprise
         * @param {number} id
         * @returns {Promise<Object>}
         */
        async toggleFavori(id) {
            const response = await fetch(`/api/entreprise/${id}/favori`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Erreur lors de la mise à jour du favori');
            return await response.json();
        },
        
        /**
         * Met à jour les tags d'une entreprise
         * @param {number} id
         * @param {Array<string>} tags
         * @returns {Promise<Object>}
         */
        async updateTags(id, tags) {
            const response = await fetch(`/api/entreprise/${id}/tags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tags })
            });
            if (!response.ok) throw new Error('Erreur lors de la mise à jour des tags');
            return await response.json();
        },
        
        /**
         * Supprime une entreprise
         * @param {number} id
         * @returns {Promise<void>}
         */
        async delete(id) {
            const response = await fetch(`/api/entreprise/${id}`, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error('Erreur lors de la suppression');
        },
        
        /**
         * Charge l'analyse technique
         * @param {number} id
         * @returns {Promise<Object|null>}
         */
        async loadTechnicalAnalysis(id) {
            const response = await fetch(`/api/entreprise/${id}/analyse-technique`);
            if (!response.ok) return null;
            return await response.json();
        },
        
        /**
         * Charge l'analyse OSINT
         * @param {number} id
         * @returns {Promise<Object|null>}
         */
        async loadOSINTAnalysis(id) {
            const response = await fetch(`/api/entreprise/${id}/analyse-osint`);
            if (!response.ok) return null;
            return await response.json();
        },
        
        /**
         * Charge l'analyse Pentest
         * @param {number} id
         * @returns {Promise<Object|null>}
         */
        async loadPentestAnalysis(id) {
            const response = await fetch(`/api/entreprise/${id}/analyse-pentest`);
            if (!response.ok) return null;
            return await response.json();
        },
        
        /**
         * Charge les résultats de scraping
         * @param {number} id
         * @returns {Promise<Array>}
         */
        async loadScrapingResults(id) {
            const response = await fetch(`/api/entreprise/${id}/scrapers`);
            if (!response.ok) return [];
            return await response.json();
        },

        /**
         * Charge le résumé du pipeline d'audit pour une entreprise.
         * @param {number} id
         * @returns {Promise<{entreprise_id: number, pipeline: Object}>}
         */
        async loadAuditPipeline(id) {
            const response = await fetch(`/api/entreprise/${id}/audit-pipeline`);
            if (!response.ok) throw new Error('Erreur lors du chargement du pipeline d\'audit');
            return await response.json();
        },

        /**
         * Liste des statuts pipeline supportés (référentiel).
         * @returns {Promise<string[]>}
         */
        async loadStatutsPipeline() {
            const response = await fetch('/api/entreprise/statuts');
            if (!response.ok) throw new Error('Erreur lors du chargement des statuts');
            return await response.json();
        },

        /**
         * Met à jour le statut pipeline d'une entreprise.
         * @param {number} id
         * @param {string} statut
         */
        async updateStatutPipeline(id, statut) {
            const response = await fetch(`/api/entreprise/${id}/statut`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ statut })
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Erreur lors de la mise à jour du statut');
            }
            return await response.json();
        },

        /**
         * Liste les touchpoints d'une entreprise.
         * @param {number} id
         * @param {number} [limit]
         * @param {number} [offset]
         */
        async loadTouchpoints(id, limit = 50, offset = 0) {
            const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
            const response = await fetch(`/api/entreprise/${id}/touchpoints?${params}`);
            if (!response.ok) throw new Error('Erreur lors du chargement des interactions');
            return await response.json();
        },

        /**
         * Crée un touchpoint.
         * @param {number} id
         * @param {{canal: string, sujet: string, note?: string, happened_at?: string|null}} payload
         */
        async createTouchpoint(id, payload) {
            const response = await fetch(`/api/entreprise/${id}/touchpoints`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Erreur lors de la création');
            }
            return await response.json();
        },

        /**
         * Met à jour un touchpoint (PATCH partiel).
         */
        async patchTouchpoint(entrepriseId, touchpointId, payload) {
            const response = await fetch(`/api/entreprise/${entrepriseId}/touchpoints/${touchpointId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Erreur lors de la mise à jour');
            }
            return await response.json();
        },

        /**
         * Supprime un touchpoint.
         */
        async deleteTouchpoint(entrepriseId, touchpointId) {
            const response = await fetch(`/api/entreprise/${entrepriseId}/touchpoints/${touchpointId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Erreur lors de la suppression');
            }
            return await response.json();
        },

        /**
         * Agrégation Kanban (effectifs par statut), mêmes query params que loadAll.
         * @param {Object} filters
         * @param {number|null} analyseId
         */
        _pipelineKanbanQueryString(filters = {}, analyseId = null) {
            const params = new URLSearchParams();
            Object.keys(filters).forEach(key => {
                const v = filters[key];
                if (v === undefined || v === null || v === '') return;
                if (Array.isArray(v)) {
                    if (!v.length) return;
                    if (key === 'tags_any' || key === 'tags_all') {
                        params.set(key, v.join(','));
                        return;
                    }
                }
                params.set(key, String(v));
            });
            if (analyseId !== null && analyseId !== undefined) {
                const id = Number(analyseId);
                if (!Number.isNaN(id)) {
                    params.set('analyse_id', String(id));
                }
            }
            return params.toString();
        },

        /**
         * Agrégation Kanban (effectifs par statut campagne), mêmes query params que loadAll.
         */
        async loadPipelineKanban(filters = {}, analyseId = null) {
            const qs = this._pipelineKanbanQueryString(filters, analyseId);
            const url = qs ? `/api/entreprise/pipeline/kanban?${qs}` : '/api/entreprise/pipeline/kanban';
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erreur lors du chargement du pipeline Kanban');
            return await response.json();
        },

        /**
         * Kanban prospection CRM (étape_prospection), mêmes filtres que loadPipelineKanban.
         */
        async loadPipelineKanbanCrm(filters = {}, analyseId = null) {
            const qs = this._pipelineKanbanQueryString(filters, analyseId);
            const url = qs ? `/api/entreprise/pipeline/kanban-crm?${qs}` : '/api/entreprise/pipeline/kanban-crm';
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erreur lors du chargement du Kanban prospection');
            return await response.json();
        },

        /**
         * Étapes CRM ordonnées (référentiel Kanban).
         * @returns {Promise<string[]>}
         */
        async loadCrmEtapes() {
            const response = await fetch('/api/entreprise/crm/etapes');
            if (!response.ok) throw new Error('Erreur lors du chargement des étapes CRM');
            return await response.json();
        },

        /**
         * Met à jour l'étape de prospection (Kanban CRM).
         * @param {number} id
         * @param {string} etape
         */
        async updateEtapeProspection(id, etape) {
            const response = await fetch(`/api/entreprise/${id}/etape-prospection`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ etape })
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Erreur lors de la mise à jour de l\'étape');
            }
            return await response.json();
        },

        /**
         * Profils de pondération (priorité commerciale).
         * @returns {Promise<{success: boolean, items: Array}>}
         */
        async loadCommercialPriorityProfiles() {
            const response = await fetch('/api/commercial/priority-profiles');
            if (!response.ok) throw new Error('Erreur lors du chargement des profils');
            return await response.json();
        },

        /**
         * Historique des snapshots de métriques (analyse technique / SEO).
         * @param {number} id
         * @param {{ limit?: number, source?: string }} [opts]
         */
        async loadMetricSnapshots(id, opts) {
            const o = opts || {};
            const params = new URLSearchParams();
            if (o.limit != null) params.set('limit', String(o.limit));
            if (o.source) params.set('source', String(o.source));
            const qs = params.toString();
            const url = qs
                ? `/api/entreprise/${id}/metric-snapshots?${qs}`
                : `/api/entreprise/${id}/metric-snapshots`;
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erreur lors du chargement des snapshots');
            return await response.json();
        },

        /**
         * Compare les deux derniers snapshots d'une source.
         * @param {number} id
         * @param {string} [source] technical | seo
         */
        async loadMetricSnapshotsCompare(id, source) {
            const s = source || 'technical';
            const response = await fetch(
                `/api/entreprise/${id}/metric-snapshots/compare?source=${encodeURIComponent(s)}`
            );
            if (!response.ok) throw new Error('Erreur lors de la comparaison des snapshots');
            return await response.json();
        },

        /**
         * Enfile un re-scan technique / SEO (nouveaux snapshots métriques).
         * @param {number} id
         * @param {{ run_technical?: boolean, run_seo?: boolean, enable_nmap?: boolean, use_lighthouse?: boolean }} [opts]
         */
        async requestMetricRescan(id, opts) {
            const body = opts && typeof opts === 'object' ? opts : {};
            const response = await fetch(`/api/entreprise/${id}/metric-snapshots/rescan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                const msg = data.error || data.message || 'Erreur lors du lancement du re-scan';
                throw new Error(msg);
            }
            return data;
        },

        /**
         * Top entreprises par score pondéré + ancienneté du dernier touchpoint.
         * @param {Object} filters - mêmes clés que loadAll
         * @param {number|null} analyseId
         * @param {{ limit?: number, profile_id?: number, priority_min?: number, w_seo?: number, w_secu?: number, w_perf?: number, w_opp?: number }} [opts]
         */
        async loadCommercialTop(filters = {}, analyseId = null, opts = {}) {
            const params = this._pipelineKanbanQueryString(filters, analyseId);
            const sp = new URLSearchParams(params);
            const lim = opts.limit != null ? Number(opts.limit) : 50;
            if (!Number.isNaN(lim)) sp.set('limit', String(Math.min(200, Math.max(1, lim))));
            if (opts.profile_id != null) sp.set('profile_id', String(opts.profile_id));
            if (opts.priority_min != null) sp.set('priority_min', String(opts.priority_min));
            ['w_seo', 'w_secu', 'w_perf', 'w_opp'].forEach((k) => {
                if (opts[k] != null && !Number.isNaN(Number(opts[k]))) sp.set(k, String(opts[k]));
            });
            const qs = sp.toString();
            const url = qs ? `/api/entreprises/commercial/top?${qs}` : '/api/entreprises/commercial/top';
            const response = await fetch(url);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Erreur vue commerciale');
            }
            return await response.json();
        },
        
        /**
         * Lance le scraping
         * @param {number} id
         * @param {string} url
         * @returns {Promise<Object>}
         */
        async launchScraping(id, url) {
            const response = await fetch('/api/scraper/unified', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ entreprise_id: id, url })
            });
            if (!response.ok) throw new Error('Erreur lors du lancement du scraping');
            return await response.json();
        },
        
        /**
         * Exporte les entreprises en CSV
         * @returns {Promise<Blob>}
         */
        async exportCSV() {
            const response = await fetch('/api/entreprises/export');
            if (!response.ok) throw new Error('Erreur lors de l\'export');
            return await response.blob();
        },

        /**
         * Charge les groupes d'entreprises, éventuellement avec l'information
         * d'appartenance pour une entreprise donnée.
         * @param {number} [entrepriseId]
         * @returns {Promise<Array>}
         */
        async loadGroupes(entrepriseId) {
            const params = new URLSearchParams();
            const id = entrepriseId != null ? Number(entrepriseId) : null;
            if (id !== null && !Number.isNaN(id)) {
                params.set('entreprise_id', String(id));
            }
            const qs = params.toString();
            const url = qs ? `/api/groupes-entreprises?${qs}` : '/api/groupes-entreprises';
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erreur lors du chargement des groupes');
            return await response.json();
        },

        /**
         * Crée un nouveau groupe d'entreprises.
         * @param {{nom: string, description?: string, couleur?: string}} payload
         * @returns {Promise<Object>}
         */
        async createGroupe(payload) {
            const response = await fetch('/api/groupes-entreprises', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error('Erreur lors de la création du groupe');
            return await response.json();
        },

        /**
         * Ajoute une entreprise à un groupe.
         * @param {number} entrepriseId
         * @param {number} groupeId
         * @returns {Promise<void>}
         */
        /**
         * Ajoute une entreprise à un groupe.
         * @param {number} entrepriseId
         * @param {number} groupeId
         * @returns {Promise<{added: boolean}>} added indique si l'association a bien été faite
         */
        async addEntrepriseToGroupe(entrepriseId, groupeId) {
            const response = await fetch(`/api/entreprise/${entrepriseId}/groupes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ groupe_id: groupeId })
            });
            if (!response.ok) throw new Error('Erreur lors de l\'ajout au groupe');
            const data = await response.json();
            return { added: data.added !== false };
        },

        /**
         * Retire une entreprise d'un groupe.
         * @param {number} entrepriseId
         * @param {number} groupeId
         * @returns {Promise<void>}
         */
        async removeEntrepriseFromGroupe(entrepriseId, groupeId) {
            const response = await fetch(`/api/entreprise/${entrepriseId}/groupes/${groupeId}`, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error('Erreur lors du retrait du groupe');
        },

        /**
         * Supprime un groupe d'entreprises.
         * @param {number} groupeId
         * @returns {Promise<void>}
         */
        async deleteGroupe(groupeId) {
            const response = await fetch(`/api/groupes-entreprises/${groupeId}`, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error('Erreur lors de la suppression du groupe');
        },

        /**
         * Met à jour un groupe d'entreprises (nom / description / couleur).
         * @param {number} groupeId
         * @param {{nom?: string, description?: string, couleur?: string}} payload
         * @returns {Promise<Object>}
         */
        async updateGroupe(groupeId, payload) {
            const response = await fetch(`/api/groupes-entreprises/${groupeId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload || {})
            });
            if (!response.ok) throw new Error('Erreur lors de la mise à jour du groupe');
            return await response.json();
        }
    };
    
    // Exposer globalement
    window.EntreprisesAPI = EntreprisesAPI;
})(window);

