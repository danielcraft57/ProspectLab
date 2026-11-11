/**
 * Système de notifications (Originator du pattern Memento).
 * L'état est sauvegardé/restauré via MementoCaretaker.
 */

(function(window) {
    'use strict';

    const CARETAKER_KEY = 'notifications';
    const MAX_ITEMS = 100;
    const LS_SOUND_ENABLED = 'prospectlab_notification_sounds_enabled';
    const LS_SOUND_VOLUME = 'prospectlab_notification_sounds_volume';

    /**
     * Bips Web Audio (pas de fichiers externes).
     */
    const NotificationSoundEngine = {
        _ctx: null,

        /**
         * @returns {AudioContext|null}
         */
        _getContext() {
            if (typeof window === 'undefined') return null;
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return null;
            if (!this._ctx) {
                try {
                    this._ctx = new Ctx();
                } catch (e) {
                    return null;
                }
            }
            if (this._ctx.state === 'suspended') {
                this._ctx.resume().catch(() => {});
            }
            return this._ctx;
        },

        /**
         * @param {number} freq Hz
         * @param {number} start s
         * @param {number} duration s
         * @param {number} volume 0-1
         * @param {string} [waveform]
         */
        _tone(freq, start, duration, volume, waveform) {
            const ctx = this._getContext();
            if (!ctx) return;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = waveform || 'sine';
            osc.frequency.setValueAtTime(freq, ctx.currentTime + start);
            gain.gain.setValueAtTime(0.0001, ctx.currentTime + start);
            gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, volume), ctx.currentTime + start + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + duration);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(ctx.currentTime + start);
            osc.stop(ctx.currentTime + start + duration + 0.05);
        },

        /**
         * Joue un motif selon le type de notification.
         * @param {string} kind success|error|warning|info|pending
         * @param {number} volume 0-1
         */
        play(kind, volume) {
            const vol = typeof volume === 'number' ? volume : 0.7;
            const k = kind || 'info';
            if (k === 'success') {
                this._tone(523.25, 0, 0.12, vol);
                this._tone(659.25, 0.13, 0.12, vol);
                this._tone(783.99, 0.26, 0.16, vol);
            } else if (k === 'error') {
                this._tone(220, 0, 0.18, vol, 'square');
                this._tone(165, 0.2, 0.22, vol * 0.9, 'square');
            } else if (k === 'warning') {
                this._tone(440, 0, 0.08, vol * 0.85, 'triangle');
                this._tone(440, 0.11, 0.08, vol * 0.85, 'triangle');
                this._tone(440, 0.22, 0.1, vol * 0.85, 'triangle');
            } else if (k === 'pending') {
                this._tone(392, 0, 0.1, vol * 0.75);
                this._tone(523.25, 0.12, 0.14, vol * 0.7);
            } else {
                this._tone(880, 0, 0.09, vol * 0.55);
            }
        }
    };

    const soundSettings = {
        /**
         * @returns {boolean}
         */
        isEnabled() {
            try {
                const raw = window.localStorage.getItem(LS_SOUND_ENABLED);
                if (raw === null) return true;
                return raw === '1' || raw === 'true';
            } catch (e) {
                return true;
            }
        },
        /**
         * @param {boolean} enabled
         */
        setEnabled(enabled) {
            try {
                window.localStorage.setItem(LS_SOUND_ENABLED, enabled ? '1' : '0');
            } catch (e) {}
        },
        /**
         * @returns {number} 0-1
         */
        getVolume() {
            try {
                const raw = window.localStorage.getItem(LS_SOUND_VOLUME);
                const n = raw != null ? parseFloat(raw) : 0.7;
                if (!Number.isFinite(n)) return 0.7;
                return Math.max(0, Math.min(1, n));
            } catch (e) {
                return 0.7;
            }
        },
        /**
         * @returns {number} 0-100
         */
        getVolumePercent() {
            return Math.round(this.getVolume() * 100);
        },
        /**
         * @param {number} percent 0-100
         */
        setVolumePercent(percent) {
            const p = Math.max(0, Math.min(100, Number(percent) || 0));
            try {
                window.localStorage.setItem(LS_SOUND_VOLUME, String(p / 100));
            } catch (e) {}
        }
    };

    /** @type {{ pending: Set<string>, success: number, errors: number, total: number, kind: string }|null} */
    let activeBulkSoundSession = null;

    /**
     * @param {string} type
     * @param {string|null} icon
     * @returns {string}
     */
    function resolveSoundKind(type, icon) {
        const ic = String(icon || '');
        if (/fa-(spinner|hourglass|play-circle|layer-group|spider|camera)\b/.test(ic)) {
            return 'pending';
        }
        return type || 'info';
    }

    const bulkSound = {
        /**
         * Enregistre un lot (>3 jobs) pour un seul bip de fin.
         * @param {string[]} keys ex. "12:seo"
         * @param {string} kind analysis|scraping|screenshots
         */
        register(keys, kind) {
            const list = (keys || []).filter(Boolean);
            if (!list.length) return;
            activeBulkSoundSession = {
                pending: new Set(list),
                success: 0,
                errors: 0,
                total: list.length,
                kind: kind || 'analysis'
            };
        },
        /**
         * @param {string} key
         * @returns {boolean} true si le son du toast doit etre muet
         */
        isTracked(key) {
            return !!(activeBulkSoundSession && activeBulkSoundSession.pending.has(key));
        },
        /**
         * Fin d'un job du lot : compte et joue le son de synthese si terminé.
         * @param {string} key
         * @param {boolean} ok
         * @returns {boolean} true si fait partie du lot (son individuel a couper)
         */
        noteJobComplete(key, ok) {
            if (!activeBulkSoundSession || !activeBulkSoundSession.pending.has(key)) {
                return false;
            }
            activeBulkSoundSession.pending.delete(key);
            if (ok) {
                activeBulkSoundSession.success += 1;
            } else {
                activeBulkSoundSession.errors += 1;
            }
            if (activeBulkSoundSession.pending.size > 0) {
                return true;
            }
            const session = activeBulkSoundSession;
            activeBulkSoundSession = null;
            let summaryType = 'success';
            if (session.errors >= session.total) {
                summaryType = 'error';
            } else if (session.errors > 0) {
                summaryType = 'warning';
            }
            const labels = {
                analysis: 'Analyses',
                scraping: 'Scrapings',
                screenshots: 'Captures screenshots'
            };
            const label = labels[session.kind] || 'Tâches';
            Notifications.playSoundForType(
                summaryType,
                `${label} : ${session.success} OK` + (session.errors ? `, ${session.errors} en échec` : '')
            );
            return true;
        }
    };

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
        soundSettings,
        bulkSound,

        /**
         * Joue un bip (hors toast) si les sons sont activés.
         * @param {string} type
         * @param {string} [message] toast optionnel de synthese
         */
        playSoundForType(type, message) {
            if (!soundSettings.isEnabled()) return;
            NotificationSoundEngine.play(resolveSoundKind(type, null), soundSettings.getVolume());
            if (message) {
                this.show(message, type, null, { skipSound: true });
            }
        },

        /**
         * Son de test (navbar).
         * @param {string} [type]
         */
        playTestSound(type) {
            NotificationSoundEngine.play(resolveSoundKind(type || 'success', null), soundSettings.getVolume());
        },

        /**
         * Affiche une notification (toast)
         * @param {string} message
         * @param {string} type - 'info', 'success', 'error', 'warning'
         * @param {string|Object} [icon] - classe FontAwesome ou options { silent, skipSound }
         * @param {Object} [options] - { silent: pas de son, skipSound: pas de son (toast seulement) }
         */
        show(message, type = 'info', icon = null, options = null) {
            let iconClass;
            let opts = options || {};
            if (icon && typeof icon === 'object' && !Array.isArray(icon)) {
                opts = icon;
                iconClass = this.getDefaultIcon(type);
            } else {
                iconClass = icon || this.getDefaultIcon(type);
            }

            if (!opts.skipSound && !opts.silent && soundSettings.isEnabled()) {
                NotificationSoundEngine.play(resolveSoundKind(type, iconClass), soundSettings.getVolume());
            }
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

