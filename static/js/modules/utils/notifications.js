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
         * Affiche une notification (toast)
         * @param {string} message
         * @param {string} type - 'info', 'success', 'error', 'warning'
         * @param {string} [icon] - classe FontAwesome (ex: 'fa-play-circle') ou null pour l'icône par défaut
         */
        show(message, type = 'info', icon = null) {
            const iconClass = icon || this.getDefaultIcon(type);
            let container = document.getElementById('notifications-toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'notifications-toast-container';
                document.body.appendChild(container);
            }

            const toast = document.createElement('div');
            toast.className = `notification-toast notification-toast--${type}`;
            toast.setAttribute('role', 'alert');
            toast.innerHTML = `
                <div class="notification-toast__icon">
                    <i class="fas ${iconClass}"></i>
                </div>
                <div class="notification-toast__content">
                    <div class="notification-toast__message">${this.escapeHtml(message)}</div>
                </div>
            `;

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
            } catch (e) {}

            this._persist();

            container.appendChild(toast);

            setTimeout(() => {
                toast.classList.add('toast-exit');
                setTimeout(() => {
                    if (toast.parentNode) toast.remove();
                }, 250);
            }, 3500);
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
        },

        /**
         * Efface toutes les notifications (vide la liste et réinitialise le compteur).
         */
        clearAll() {
            this._items = [];
            this._counter = 0;
            this._persist();
            try {
                document.dispatchEvent(new CustomEvent('notifications:cleared'));
            } catch (e) {}
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

