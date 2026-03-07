/**
 * Système de notifications (Originator du pattern Memento).
 * L'état est sauvegardé/restauré via MementoCaretaker.
 */

(function(window) {
    'use strict';

    const CARETAKER_KEY = 'notifications';
    const MAX_ITEMS = 100;

    const Notifications = {
        _items: [],
        _counter: 0,

        /** Crée un Memento de l'état actuel (Originator). */
        createMemento() {
            const state = {
                items: this._items.map(n => ({
                    id: n.id,
                    message: n.message,
                    type: n.type,
                    icon: n.icon,
                    date: n.date instanceof Date ? n.date.toISOString() : (n.date || null),
                    read: !!n.read
                })),
                unreadCount: this._counter
            };
            return window.Memento ? new window.Memento(state) : null;
        },

        /** Restaure l'état depuis un Memento (Originator). */
        restoreFromMemento(memento) {
            if (!memento || !memento.getState) return;
            const state = memento.getState();
            if (!state || !Array.isArray(state.items)) return;

            this._items = state.items.map(n => ({
                id: n.id || (Date.now() + '-' + Math.random().toString(36).slice(2)),
                message: n.message || '',
                type: n.type || 'info',
                icon: n.icon || this.getDefaultIcon(n.type || 'info'),
                date: n.date ? new Date(n.date) : new Date(),
                read: !!n.read
            }));
            this._counter = typeof state.unreadCount === 'number' ? state.unreadCount : this._items.filter(n => !n.read).length;
        },

        _persist() {
            if (window.MementoCaretaker) {
                const m = this.createMemento();
                if (m) window.MementoCaretaker.save(CARETAKER_KEY, m);
            }
        },
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
            
            // Enregistrer dans l'historique
            const item = {
                id: Date.now() + '-' + Math.random().toString(36).slice(2),
                message: String(message),
                type,
                icon: iconClass,
                date: new Date(),
                read: false
            };
            this._items.unshift(item);
            if (this._items.length > MAX_ITEMS) {
                this._items.length = MAX_ITEMS;
            }
            this._counter += 1;

            try {
                document.dispatchEvent(new CustomEvent('notifications:new', { detail: { item, unreadCount: this._counter } }));
            } catch (e) {
                // best-effort
            }

            this._persist();

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
        },

        getAll() {
            return this._items.slice();
        },

        getUnreadCount() {
            return this._counter;
        },

        markAllAsRead() {
            this._items = this._items.map(n => Object.assign({}, n, { read: true }));
            this._counter = 0;
            this._persist();
        }
    };
    
    // Restauration d'état via le Caretaker (pattern Memento)
    if (window.MementoCaretaker) {
        const memento = window.MementoCaretaker.load(CARETAKER_KEY);
        if (memento) {
            Notifications.restoreFromMemento(memento);
        } else {
            // Migration depuis l'ancienne clé
            try {
                const raw = window.localStorage.getItem('prospectlab_notifications_v1');
                if (raw) {
                    const data = JSON.parse(raw);
                    if (data && Array.isArray(data.items)) {
                        const state = { items: data.items, unreadCount: data.unreadCount };
                        Notifications.restoreFromMemento(new window.Memento(state));
                        Notifications._persist();
                        window.localStorage.removeItem('prospectlab_notifications_v1');
                    }
                }
            } catch (e) {}
        }
    }

    window.Notifications = Notifications;
})(window);

