/**
 * Système de notifications
 */

(function(window) {
    'use strict';
    
    const Notifications = {
        /**
         * Icônes par défaut selon le type
         */
        getDefaultIcon(type) {
            const icons = {
                'info': 'fa-info-circle',
                'success': 'fa-check-circle',
                'error': 'fa-exclamation-circle',
                'warning': 'fa-exclamation-triangle'
            };
            return icons[type] || icons.info;
        },
        /**
         * Affiche une notification
         * @param {string} message
         * @param {string} type - 'info', 'success', 'error', 'warning'
         * @param {string} [icon] - classe FontAwesome (ex: 'fa-play-circle') ou null pour l'icône par défaut
         */
        show(message, type = 'info', icon = null) {
            const iconClass = icon || this.getDefaultIcon(type);
            const iconHtml = `<i class="fas ${iconClass}" style="margin-right: 0.5rem; opacity: 0.95;"></i>`;
            const notification = document.createElement('div');
            notification.className = `notification notification-${type}`;
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 1rem 1.5rem;
                background: ${this.getColor(type)};
                color: white;
                border-radius: 6px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                z-index: 10000;
                animation: slideIn 0.3s ease;
                max-width: 400px;
                display: flex;
                align-items: center;
            `;
            notification.innerHTML = iconHtml + '<span>' + this.escapeHtml(message) + '</span>';
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        },
        
        /**
         * Retourne la couleur selon le type
         * @param {string} type
         * @returns {string}
         */
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        getColor(type) {
            const colors = {
                'info': '#3498db',
                'success': '#27ae60',
                'error': '#e74c3c',
                'warning': '#f39c12'
            };
            return colors[type] || colors.info;
        }
    };
    
    // Exposer globalement
    window.Notifications = Notifications;
})(window);

