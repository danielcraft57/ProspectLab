/**
 * Système de notifications (Originator du pattern Memento).
 * L'état est sauvegardé/restauré via MementoCaretaker.
 * Sons courts via Web Audio (succès, erreur, attente, warning) + volume réglable.
 */

(function(window) {
    'use strict';

    const CARETAKER_KEY = 'notifications';
    const SOUND_SETTINGS_KEY = 'prospectlab_notification_sounds_v1';
    const MAX_ITEMS = 100;
    const BULK_SESSION_TIMEOUT_MS = 45 * 60 * 1000;

    /**
     * Moteur audio léger (beeps synthétisés, pas de fichiers externes).
     */
    const NotificationSoundEngine = {
        _ctx: null,
        _unlocked: false,

        /**
         * @returns {AudioContext|null}
         */
        _getContext() {
            if (this._ctx) return this._ctx;
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return null;
            try {
                this._ctx = new Ctx();
            } catch (e) {
                return null;
            }
            return this._ctx;
        },

        /**
         * Débloque l'audio après un geste utilisateur (politique navigateur).
         * @returns {Promise<void>}
         */
        async unlock() {
            const ctx = this._getContext();
            if (!ctx) return;
            if (ctx.state === 'suspended') {
                try {
                    await ctx.resume();
                } catch (e) {}
            }
            this._unlocked = ctx.state === 'running';
        },

        /**
         * Joue une note sinusoïdale amortie.
         * @param {number} frequency
         * @param {number} startTime
         * @param {number} durationSec
         * @param {number} gainPeak
         * @param {AudioContext} ctx
         * @param {GainNode} master
         */
        _tone(frequency, startTime, durationSec, gainPeak, ctx, master) {
            const osc = ctx.createOscillator();
            const g = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(frequency, startTime);
            g.gain.setValueAtTime(0.0001, startTime);
            g.gain.exponentialRampToValueAtTime(Math.max(gainPeak, 0.0001), startTime + 0.012);
            g.gain.exponentialRampToValueAtTime(0.0001, startTime + durationSec);
            osc.connect(g);
            g.connect(master);
            osc.start(startTime);
            osc.stop(startTime + durationSec + 0.02);
        },

        /**
         * Profils sonores par catégorie.
         * @param {'success'|'error'|'warning'|'waiting'|'info'} category
         * @param {number} volume01
         */
        play(category, volume01) {
            if (!NotificationsSoundSettings.isEnabled()) return;
            const ctx = this._getContext();
            if (!ctx) return;
            const vol = Math.max(0, Math.min(1, Number(volume01) || 0));
            if (vol <= 0) return;

            const run = () => {
                const t0 = ctx.currentTime + 0.01;
                const master = ctx.createGain();
                master.gain.setValueAtTime(vol * 0.22, t0);
                master.connect(ctx.destination);

                if (category === 'success') {
                    this._tone(523.25, t0, 0.11, 1, ctx, master);
                    this._tone(659.25, t0 + 0.1, 0.14, 0.85, ctx, master);
                    this._tone(783.99, t0 + 0.2, 0.18, 0.7, ctx, master);
                } else if (category === 'error') {
                    this._tone(220, t0, 0.16, 1, ctx, master);
                    this._tone(185, t0 + 0.12, 0.22, 0.9, ctx, master);
                } else if (category === 'warning') {
                    this._tone(440, t0, 0.09, 1, ctx, master);
                    this._tone(392, t0 + 0.11, 0.09, 0.85, ctx, master);
                    this._tone(440, t0 + 0.22, 0.12, 0.75, ctx, master);
                } else if (category === 'waiting') {
                    this._tone(330, t0, 0.08, 0.7, ctx, master);
                    this._tone(392, t0 + 0.14, 0.1, 0.55, ctx, master);
                } else {
                    this._tone(880, t0, 0.06, 0.45, ctx, master);
                }
            };

            if (ctx.state === 'suspended') {
                ctx.resume().then(run).catch(function() {});
            } else {
                run();
            }
        }
    };

    const NotificationsSoundSettings = {
        _enabled: true,
        _volume: 0.35,

        load() {
            try {
                const raw = window.localStorage.getItem(SOUND_SETTINGS_KEY);
                if (!raw) return;
                const data = JSON.parse(raw);
                if (typeof data.enabled === 'boolean') this._enabled = data.enabled;
                if (typeof data.volume === 'number') {
                    this._volume = Math.max(0, Math.min(1, data.volume));
                }
            } catch (e) {}
        },

        persist() {
            try {
                window.localStorage.setItem(SOUND_SETTINGS_KEY, JSON.stringify({
                    enabled: this._enabled,
                    volume: this._volume
                }));
            } catch (e) {}
        },

        isEnabled() {
            return !!this._enabled;
        },

        setEnabled(value) {
            this._enabled = !!value;
            this.persist();
            try {
                document.dispatchEvent(new CustomEvent('notifications:sound-settings', {
                    detail: { enabled: this._enabled, volume: this._volume }
                }));
            } catch (e) {}
        },

        getVolume() {
            return this._volume;
        },

        /**
         * @param {number} volume01 - entre 0 et 1
         */
        setVolume(volume01) {
            this._volume = Math.max(0, Math.min(1, Number(volume01) || 0));
            this.persist();
            try {
                document.dispatchEvent(new CustomEvent('notifications:sound-settings', {
                    detail: { enabled: this._enabled, volume: this._volume }
                }));
            } catch (e) {}
        },

        getVolumePercent() {
            return Math.round(this._volume * 100);
        },

        setVolumePercent(percent) {
            this.setVolume(Math.max(0, Math.min(100, Number(percent) || 0)) / 100);
        }
    };

    NotificationsSoundSettings.load();

    const Notifications = {
        _items: [],
        _counter: 0,
        /** @type {{ pending: number, errors: number, ids: Set<number>, timeoutId: number|null, initialTotal: number }|null} */
        _bulkSoundSession: null,

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
         * Catégorie sonore dérivée du type et de l'icône (attente = spinners / sabliers).
         * @param {string} type
         * @param {string|null} icon
         * @returns {'success'|'error'|'warning'|'waiting'|'info'}
         */
        _soundCategoryFor(type, icon) {
            const t = String(type || 'info');
            if (t === 'success') return 'success';
            if (t === 'error') return 'error';
            if (t === 'warning') return 'warning';
            const ic = String(icon || '');
            if (/fa-spinner|fa-hourglass|fa-clock|fa-list-ol|fa-play-circle|fa-camera|fa-spider|fa-layer-group/i.test(ic)) {
                return 'waiting';
            }
            return 'info';
        },

        /**
         * Joue un son si autorisé par les options.
         * @param {string} type
         * @param {string|null} icon
         * @param {object} options
         */
        _maybePlaySound(type, icon, options) {
            const opts = options || {};
            if (opts.sound === false) return;
            const category = opts.soundCategory || this._soundCategoryFor(type, icon);
            NotificationSoundEngine.play(category, NotificationsSoundSettings.getVolume());
        },

        /**
         * Démarre une session bulk : un son d'attente au lancement, un seul son de synthèse à la fin.
         * @param {{ total: number, entrepriseIds: number[] }} config
         */
        startBulkSoundSession(config) {
            const total = Math.max(0, Number(config && config.total) || 0);
            if (total <= 3) return;
            const ids = Array.isArray(config && config.entrepriseIds)
                ? config.entrepriseIds.map(function(x) { return Number(x); }).filter(function(n) { return n > 0; })
                : [];
            if (this._bulkSoundSession && this._bulkSoundSession.timeoutId) {
                clearTimeout(this._bulkSoundSession.timeoutId);
            }
            this._bulkSoundSession = {
                pending: total,
                errors: 0,
                ids: new Set(ids),
                initialTotal: total,
                timeoutId: null
            };
            const self = this;
            this._bulkSoundSession.timeoutId = window.setTimeout(function() {
                if (!self._bulkSoundSession) return;
                NotificationSoundEngine.play('warning', NotificationsSoundSettings.getVolume());
                self._bulkSoundSession = null;
            }, BULK_SESSION_TIMEOUT_MS);
            NotificationSoundEngine.unlock();
            NotificationSoundEngine.play('waiting', NotificationsSoundSettings.getVolume());
        },

        /**
         * Applique les options son bulk sur une notif liée à une entreprise.
         * @param {number|null|undefined} entrepriseId
         * @param {object} options - objet muté sur place
         */
        applyBulkSoundOptions(entrepriseId, options) {
            const session = this._bulkSoundSession;
            if (!session) return;
            const eid = Number(entrepriseId);
            if (!eid || !session.ids.has(eid)) return;
            options.sound = false;
        },

        /**
         * À appeler sur les événements terminaux (succès / erreur) d'une entreprise en bulk.
         * @param {number|null|undefined} entrepriseId
         * @param {string} type
         */
        notifyBulkTerminalEvent(entrepriseId, type) {
            const session = this._bulkSoundSession;
            if (!session) return;
            const eid = Number(entrepriseId);
            if (!eid || !session.ids.has(eid)) return;
            if (String(type) === 'error') session.errors += 1;
            session.pending -= 1;
            if (session.pending > 0) return;
            if (session.timeoutId) {
                clearTimeout(session.timeoutId);
            }
            let finalCategory = 'success';
            if (session.errors >= session.initialTotal) {
                finalCategory = 'error';
            } else if (session.errors > 0) {
                finalCategory = 'warning';
            }
            NotificationSoundEngine.play(finalCategory, NotificationsSoundSettings.getVolume());
            this._bulkSoundSession = null;
        },

        /**
         * Prévisualisation depuis le panneau réglages.
         * @param {string} [category]
         */
        playTestSound(category) {
            NotificationSoundEngine.unlock();
            NotificationSoundEngine.play(category || 'success', NotificationsSoundSettings.getVolume());
        },

        /**
         * Affiche une notification (toast)
         * @param {string} message
         * @param {string} type - 'info', 'success', 'error', 'warning'
         * @param {string} [icon] - classe FontAwesome (ex: 'fa-play-circle') ou null pour l'icône par défaut
         * @param {object} [options] - sound, soundCategory, bulkTerminal, entrepriseId
         */
        show(message, type = 'info', icon = null, options = null) {
            let opts = options && typeof options === 'object' ? options : {};
            const iconClass = icon || this.getDefaultIcon(type);

            if (opts.entrepriseId != null) {
                this.applyBulkSoundOptions(opts.entrepriseId, opts);
            }
            if (opts.bulkTerminal && opts.entrepriseId != null) {
                this.notifyBulkTerminalEvent(opts.entrepriseId, type);
            }

            this._maybePlaySound(type, iconClass, opts);

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
        },

        /** Réglages sonores (volume, activation). */
        soundSettings: NotificationsSoundSettings,

        /** Moteur audio (tests avancés). */
        soundEngine: NotificationSoundEngine
    };

    if (window.MementoCaretaker) {
        const memento = window.MementoCaretaker.load(CARETAKER_KEY);
        if (memento) {
            Notifications.restoreFromMemento(memento);
        } else {
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
