/**
 * Utilitaires pour générer des badges et scores
 */

(function(window) {
    'use strict';
    
    const Badges = {
        /**
         * Calcule les infos de score de sécurité à partir d'un score numérique 0-100
         * @param {number|null|undefined} score
         * @returns {{label: string, className: string}}
         */
        getSecurityScoreInfo(score) {
            if (score === null || score === undefined || Number.isNaN(Number(score))) {
                return { label: 'Non analysé', className: 'secondary' };
            }
            const s = Math.max(0, Math.min(100, Number(score)));
            if (s >= 80) {
                return { label: `${s}/100 (Sécurisé)`, className: 'success' };
            }
            if (s >= 50) {
                return { label: `${s}/100 (Moyen)`, className: 'warning' };
            }
            return { label: `${s}/100 (Faible)`, className: 'danger' };
        },
        
        /**
         * Génère un badge HTML pour le score de sécurité
         * @param {number|null|undefined} score
         * @param {string|null} id
         * @returns {string}
         */
        getSecurityScoreBadge(score, id = null) {
            const info = this.getSecurityScoreInfo(score);
            const idAttr = id ? ` id="${id}"` : '';
            return `<span${idAttr} class="badge badge-${info.className}">${info.label}</span>`;
        },
        
        /**
         * Calcule un badge de performance simple (0-100)
         * @param {number|null|undefined} score
         * @returns {{label: string, className: string}}
         */
        getPerformanceScoreInfo(score) {
            if (score === null || score === undefined || Number.isNaN(Number(score))) {
                return { label: 'Non analysé', className: 'secondary' };
            }
            const s = Math.max(0, Math.min(100, Number(score)));
            if (s >= 80) return { label: `${s}/100 (Rapide)`, className: 'success' };
            if (s >= 50) return { label: `${s}/100 (Moyen)`, className: 'warning' };
            return { label: `${s}/100 (Lent)`, className: 'danger' };
        },
        
        /**
         * Génère un badge HTML pour le score de performance
         * @param {number|null|undefined} score
         * @returns {string}
         */
        getPerformanceScoreBadge(score) {
            const info = this.getPerformanceScoreInfo(score);
            return `<span class="badge badge-${info.className}">${info.label}</span>`;
        },
        
        /**
         * Génère un badge de statut
         * @param {string|null} statut
         * @returns {string}
         */
        getStatusBadge(statut) {
            if (!statut) return '';
            const classes = {
                'Nouveau': 'primary',
                'À qualifier': 'warning',
                'Relance': 'relance',
                'Gagné': 'success',
                'Perdu': 'danger',
                'Désabonné': 'danger',
                'Réponse négative': 'danger',
                'Réponse positive': 'success',
                'Bounce': 'warning',
                'Plainte spam': 'danger',
                'Ne pas contacter': 'danger',
                'À rappeler': 'relance',
            };
            const className = classes[statut] || 'secondary';
            return `<span class="badge badge-${className}">${statut}</span>`;
        },
        
        /**
         * Génère une classe CSS pour le statut
         * @param {string|null} statut
         * @returns {string}
         */
        getStatusClass(statut) {
            if (!statut) return '';
            const classes = {
                'Nouveau': 'primary',
                'À qualifier': 'warning',
                'Relance': 'relance',
                'Gagné': 'success',
                'Perdu': 'danger',
                'Désabonné': 'danger',
                'Réponse négative': 'danger',
                'Réponse positive': 'success',
                'Bounce': 'warning',
                'Plainte spam': 'danger',
                'Ne pas contacter': 'danger',
                'À rappeler': 'relance',
            };
            return classes[statut] || 'secondary';
        },

        /**
         * Calcule les infos pour un badge d'opportunité
         * @param {string|null} niveau - 'Très élevée', 'Élevée', 'Moyenne', 'Faible', 'Très faible'
         * @param {number|null|undefined} score - Score numérique 0-100 (facultatif)
         * @returns {{label: string, className: string}}
         */
        getOpportunityInfo(niveau, score) {
            const s = (score === null || score === undefined || Number.isNaN(Number(score)))
                ? null
                : Math.max(0, Math.min(100, Number(score)));

            let labelBase = niveau || 'Non calculée';
            if (s !== null) {
                labelBase = `${labelBase} (${s}/100)`;
            }

            let className = 'secondary';
            switch (niveau) {
                case 'Très élevée':
                    className = 'success';
                    break;
                case 'Élevée':
                    className = 'primary';
                    break;
                case 'Moyenne':
                    className = 'warning';
                    break;
                case 'Faible':
                case 'Très faible':
                    className = 'secondary';
                    break;
                default:
                    className = 'secondary';
            }

            return { label: labelBase, className };
        },

        /**
         * Génère un badge HTML pour l'opportunité
         * @param {string|null} niveau
         * @param {number|null|undefined} score
         * @param {string|null} id
         * @returns {string}
         */
        getOpportunityBadge(niveau, score, id = null) {
            const info = this.getOpportunityInfo(niveau, score);
            const idAttr = id ? ` id="${id}"` : '';
            return `<span${idAttr} class="badge badge-${info.className}">${info.label}</span>`;
        }
    };
    
    // Exposer globalement
    window.Badges = Badges;
})(window);

