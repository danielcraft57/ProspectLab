/**
 * Design pattern Memento — sauvegarde et restauration d'état sans exposer l'interne.
 *
 * Rôles :
 * - Originator : objet dont on capture/restaure l'état (ex. Notifications, formulaire).
 * - Memento : snapshot sérialisable de l'état (opaque pour le Caretaker).
 * - Caretaker : stocke et récupère les mementos (localStorage).
 *
 * Usage :
 *   const memento = originator.createMemento();
 *   caretaker.save('notifications', memento);
 *   const restored = caretaker.load('notifications');
 *   if (restored) originator.restoreFromMemento(restored);
 */

(function (window) {
    'use strict';

    const STORAGE_PREFIX = 'prospectlab_memento_';

    /**
     * Représente un snapshot d'état à un instant t.
     * Le contenu de `state` est défini par l'Originator.
     */
    function Memento(state, metadata = {}) {
        this._state = state;
        this._metadata = Object.assign({ timestamp: Date.now() }, metadata);
    }

    Memento.prototype.getState = function () {
        return this._state;
    };

    Memento.prototype.getMetadata = function () {
        return Object.assign({}, this._metadata);
    };

    /**
     * Caretaker : persiste et charge les mementos (localStorage).
     * Ne connaît pas la structure de state, seulement sérialisation JSON.
     */
    const Caretaker = {
        _prefix: STORAGE_PREFIX,

        /**
         * Sauvegarde un memento sous une clé.
         * @param {string} key - Clé (ex. 'notifications', 'gmap_last_search')
         * @param {Memento} memento - Instance de Memento
         */
        save(key, memento) {
            if (!key || !memento || !(memento instanceof Memento)) return;
            try {
                const payload = {
                    state: memento.getState(),
                    metadata: memento.getMetadata()
                };
                window.localStorage.setItem(this._prefix + key, JSON.stringify(payload));
            } catch (e) {
                // best-effort
            }
        },

        /**
         * Charge un memento par clé.
         * @param {string} key
         * @returns {Memento|null}
         */
        load(key) {
            if (!key) return null;
            try {
                const raw = window.localStorage.getItem(this._prefix + key);
                if (!raw) return null;
                const payload = JSON.parse(raw);
                if (!payload || payload.state === undefined) return null;
                return new Memento(payload.state, payload.metadata || {});
            } catch (e) {
                return null;
            }
        },

        /**
         * Supprime un memento persisté.
         * @param {string} key
         */
        clear(key) {
            if (!key) return;
            try {
                window.localStorage.removeItem(this._prefix + key);
            } catch (e) {}
        }
    };

    window.Memento = Memento;
    window.MementoCaretaker = Caretaker;
})(window);
