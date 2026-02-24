/**
 * API pour les entreprises
 */

(function(window) {
    'use strict';
    
    const EntreprisesAPI = {
        /**
         * Charge les entreprises, optionnellement filtrées par les paramètres fournis.
         * @param {Object} [filters] - Filtres (secteur, statut, opportunite, favori, search, security_min, security_max, pentest_min, pentest_max)
         * @returns {Promise<Array>}
         */
        async loadAll(filters = {}) {
            const params = new URLSearchParams();
            Object.keys(filters).forEach(key => {
                const v = filters[key];
                if (v !== undefined && v !== null && v !== '') params.set(key, String(v));
            });
            const qs = params.toString();
            const url = qs ? `/api/entreprises?${qs}` : '/api/entreprises';
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
        }
    };
    
    // Exposer globalement
    window.EntreprisesAPI = EntreprisesAPI;
})(window);

