/**
 * Gestionnaire WebSocket pour ProspectLab
 * Communication en temps réel entre le frontend et le backend
 */

class ProspectLabWebSocket {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this._connecting = false;
        this._forcePollingOnly = this._detectForcePollingOnly();
        this._wsErrorBurst = 0;
        this._lastForcePollingTs = 0;
        this._connectSeq = 0;
        this._debug = this._readDebugFlag();
    }

    _detectForcePollingOnly() {
        try {
            const host = (window.location.hostname || '').toLowerCase();
            const looksLocal =
                host === '127.0.0.1' ||
                host === 'localhost' ||
                host === '[::1]';
            if (!looksLocal) {
                return false;
            }
            // Réactiver l’upgrade WebSocket : ?ws_upgrade=1 ou localStorage ws_force_websocket=1
            try {
                const qs = new URLSearchParams(window.location.search || '');
                if (qs.get('ws_upgrade') === '1') {
                    return false;
                }
            } catch (e) {}
            try {
                if (localStorage.getItem('ws_force_websocket') === '1') {
                    return false;
                }
            } catch (e) {}
            // Werkzeug + Flask-SocketIO (threading) : l’upgrade WS casse souvent sous Windows
            // (« WebSocket is closed before the connection is established ») → polling HTTP stable.
            // Ancien cas /preview : inchangé, mais tout l’hôte local en bénéficie en dev.
            return true;
        } catch (e) {
            return false;
        }
    }

    _readDebugFlag() {
        try {
            const qs = new URLSearchParams(window.location.search || '');
            if (qs.get('ws_debug') === '1') return true;
        } catch (e) {}
        try {
            return (localStorage.getItem('ws_debug') === '1');
        } catch (e) {
            return false;
        }
    }

    _dbg(...args) {
        if (!this._debug) return;
        try {
            console.debug('[WS]', ...args);
        } catch (e) {}
    }

    _dbgWarn(...args) {
        if (!this._debug) return;
        try {
            console.warn('[WS]', ...args);
        } catch (e) {}
    }

    _dbgError(...args) {
        if (!this._debug) return;
        try {
            console.error('[WS]', ...args);
        } catch (e) {}
    }

    _safeErrObj(error) {
        try {
            if (!error) return null;
            const out = {};
            if (typeof error === 'string') return { message: error };
            if (typeof error.message === 'string') out.message = error.message;
            if (typeof error.description === 'string') out.description = error.description;
            if (typeof error.type === 'string') out.type = error.type;
            if (typeof error.code !== 'undefined') out.code = error.code;
            if (typeof error.context !== 'undefined') out.context = error.context;
            // Socket.IO v4 met parfois des infos dans `error.data`
            if (typeof error.data !== 'undefined') out.data = error.data;
            return out;
        } catch (e) {
            return { message: String(error) };
        }
    }

    _buildSocketOptions() {
        // En dev (notamment Windows + eventlet), le transport websocket peut être instable.
        // On bascule automatiquement en "polling only" si on détecte une rafale d'erreurs websocket.
        const base = {
            path: '/socket.io/',
            // Origine explicite (évite les résolutions bizarres selon le navigateur)
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: Infinity,
            timeout: 60000,
            // Tolérance aux pics de charge / latence
            pingInterval: 25000,
            pingTimeout: 60000,
            forceNew: false,
            rememberUpgrade: true
        };
        if (this._forcePollingOnly) {
            return {
                ...base,
                transports: ['polling'],
                upgrade: false
            };
        }
        return {
            ...base,
            // Plus robuste : démarrer en polling puis upgrade websocket si possible
            transports: ['polling', 'websocket'],
            upgrade: true
        };
    }

    _maybeForcePollingOnly(error) {
        // Heuristique : si le websocket échoue plusieurs fois de suite, on force polling only
        const msg = (error && (error.message || error.description || String(error))) || '';
        const looksLikeWsFailure =
            msg.toLowerCase().includes('websocket') ||
            msg.toLowerCase().includes('closed before') ||
            msg.toLowerCase().includes('transport close') ||
            msg.toLowerCase().includes('ping timeout');

        // Socket.IO peut aussi renvoyer "timeout" (connect_error) sans mention explicite.
        const looksLikeTimeout = msg.toLowerCase().includes('timeout');
        const isWsLike = looksLikeWsFailure || looksLikeTimeout;

        if (!isWsLike) {
            // reset progressif
            this._wsErrorBurst = Math.max(0, this._wsErrorBurst - 1);
            return false;
        }

        // Ping timeout : bascule immédiate (évite les boucles de reconnexion websocket)
        if (msg.toLowerCase().includes('ping timeout') || msg.toLowerCase() === 'timeout') {
            if (!this._forcePollingOnly) {
                this._forcePollingOnly = true;
                this._lastForcePollingTs = Date.now();
                this._dbgWarn('ping timeout détecté : polling-only immédiat');
            }
            return true;
        }

        this._wsErrorBurst += 1;
        this._dbgWarn('wsErrorBurst', this._wsErrorBurst, 'error=', this._safeErrObj(error));
        // Après 3 erreurs rapprochées, on force polling-only (pendant un moment)
        if (this._wsErrorBurst < 3) return false;

        const now = Date.now();
        // éviter de flip-flop en boucle : max 1 bascule / 30s
        if (now - this._lastForcePollingTs < 30000) return false;

        this._lastForcePollingTs = now;
        this._forcePollingOnly = true;
        this._dbgWarn('WebSocket instable détecté : bascule en polling-only');
        return true;
    }

    connect() {
        // Ne pas essayer de se connecter sur la page d'accès restreint
        if (document.body && document.body.classList.contains('restricted-page')) {
            return;
        }

        // Vérifier le titre de la page (détection supplémentaire)
        const pageTitle = document.title || '';
        if (pageTitle.includes('Accès restreint') || pageTitle.includes('restreint')) {
            return;
        }

        // Vérifier si on est sur une page qui nécessite WebSocket
        const currentPath = window.location.pathname;
        if (currentPath === '/restricted' || currentPath.includes('restricted')) {
            return;
        }

        // Vérifier si le body contient la carte d'accès restreint (détection par contenu)
        const restrictedCard = document.querySelector('.restricted-card');
        if (restrictedCard) {
            return;
        }

        // Détecter si Socket.IO est disponible
        if (typeof io === 'undefined') {
            this.loadSocketIO();
            return;
        }

        // Éviter de recréer une connexion en boucle (sinon tempête de sockets/handlers).
        if (this.socket) {
            try {
                if (this.socket.connected) {
                    return;
                }
                // Si déjà en cours de connexion, ne rien faire
                if (this._connecting) {
                    return;
                }
                this._connecting = true;
                this._connectSeq += 1;
                this._dbg('connect() reuse existing socket', { seq: this._connectSeq, forcePollingOnly: this._forcePollingOnly });
                this.socket.connect();
                return;
            } catch (e) {
                // Si on a un socket corrompu, on repart de zéro.
                try { this.socket.close(); } catch (e2) {}
                this.socket = null;
            }
        }

        this._connecting = true;
        this._connectSeq += 1;
        const opts = this._buildSocketOptions();
        this._dbg('connect() create new socket', { seq: this._connectSeq, opts });
        let origin = '';
        try {
            origin = window.location.origin || '';
        } catch (e) {}
        // io(origin, opts) : même origine que la page (obligatoire si path personnalisé)
        this.socket = origin ? io(origin, opts) : io(opts);

        this.setupEventHandlers();
    }

    loadSocketIO() {
        const script = document.createElement('script');
        script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js';
        script.onload = () => {
            this.connect();
        };
        script.onerror = () => {
            console.error('Impossible de charger Socket.IO');
            this.showError('Impossible de charger Socket.IO. Vérifiez votre connexion.');
        };
        document.head.appendChild(script);
    }

    setupEventHandlers() {
        this.socket.on('connect', () => {
            this.connected = true;
            this.reconnectAttempts = 0;
            this._connecting = false;
            this._wsErrorBurst = 0;
            try {
                const tname = this.socket && this.socket.io && this.socket.io.engine && this.socket.io.engine.transport
                    ? this.socket.io.engine.transport.name
                    : null;
                this._dbg('connected', { transport: tname, id: this.socket && this.socket.id });
            } catch (e) {}
            this.onConnect();
        });

        this.socket.on('disconnect', (reason) => {
            this.connected = false;
            this._connecting = false;
            try {
                const tname = this.socket && this.socket.io && this.socket.io.engine && this.socket.io.engine.transport
                    ? this.socket.io.engine.transport.name
                    : null;
                this._dbgWarn('disconnected', { reason, transport: tname });
            } catch (e) {}
            this.onDisconnect();
            // En polling-only on reste stable, donc si on est déconnecté c'est autre chose.
            // En mode normal, si le serveur ferme l'upgrade websocket, on peut passer en polling-only.
            if (!this._forcePollingOnly && typeof reason === 'string') {
                const r = reason.toLowerCase();
                if (r.includes('transport') || r.includes('ping timeout') || r.includes('timeout')) {
                    this._maybeForcePollingOnly(reason);
                }
            }
        });

        this.socket.on('connect_error', (error) => {
            // Ne pas spammer la console si on est sur une page qui n'a pas besoin de websocket
            const currentPath = window.location.pathname;
            if (currentPath === '/restricted' || currentPath.includes('restricted')) {
                return;
            }

            // Réduire le bruit : ne logger que si vraiment nécessaire
            if (this.reconnectAttempts === 0) {
                console.warn('Connexion WebSocket échouée, tentative de reconnexion...');
            }
            this._dbgWarn('connect_error', this._safeErrObj(error));
            this.onConnectionError(error);
            // IMPORTANT: Socket.IO gère déjà la reconnexion (reconnectionAttempts=Infinity).
            // Ne pas rappeler connect() ici, sinon on multiplie les sockets/handlers.
            this._connecting = false;

            // Fallback automatique : si websocket instable, recréer une connexion polling-only.
            if (this._maybeForcePollingOnly(error)) {
                try { this.socket.close(); } catch (e) {}
                this.socket = null;
                // Petite pause pour éviter une boucle serrée
                setTimeout(() => this.connect(), 250);
            }
        });

        this.socket.on('reconnect', (attemptNumber) => {
            this.reconnectAttempts = 0;
            this._dbg('reconnect', { attemptNumber });
        });

        this.socket.on('reconnect_error', (error) => {
            this._dbgWarn('reconnect_error', this._safeErrObj(error));
            console.error('Erreur lors de la reconnexion:', error);
        });

        this.socket.on('reconnect_failed', () => {
            this._dbgError('reconnect_failed');
            console.error('Échec de la reconnexion après toutes les tentatives');
            this.showError('Impossible de se reconnecter au serveur. Veuillez recharger la page.');
        });

        // Log bas niveau Engine.IO (utile pour diagnostiquer upgrade websocket)
        try {
            if (this.socket && this.socket.io && this.socket.io.engine) {
                this.socket.io.engine.on('upgrade', (transport) => {
                    this._dbg('engine upgrade', { transport: transport && transport.name });
                });
                this.socket.io.engine.on('close', (reason) => {
                    this._dbgWarn('engine close', { reason });
                });
                this.socket.io.engine.on('error', (err) => {
                    this._dbgWarn('engine error', this._safeErrObj(err));
                });
            }
        } catch (e) {}

        // Événements d'analyse
        this.socket.on('analysis_started', (data) => {
            this.onAnalysisStarted(data);
        });

        this.socket.on('analysis_progress', (data) => {
            this.onAnalysisProgress(data);
        });

        this.socket.on('analysis_complete', (data) => {
            // Cacher les messages finis côté front (demande utilisateur)
            data.message = '';
            this.onAnalysisComplete(data);
        });

        this.socket.on('analysis_error', (data) => {
            this.onAnalysisError(data);
        });

        this.socket.on('analysis_error_item', (data) => {
            this.onAnalysisErrorItem(data);
        });

        this.socket.on('analysis_stopping', (data) => {
            this.onAnalysisStopping(data);
        });

        this.socket.on('analysis_stopped', (data) => {
            this.onAnalysisStopped(data);
        });

        // Événements Pentest
        this.socket.on('pentest_analysis_started', (data) => {
            this.onPentestAnalysisStarted(data);
        });
        this.socket.on('pentest_analysis_progress', (data) => {
            this.onPentestAnalysisProgress(data);
        });
        this.socket.on('pentest_analysis_complete', (data) => {
            this.onPentestAnalysisComplete(data);
        });
        this.socket.on('pentest_analysis_error', (data) => {
            this.onPentestAnalysisError(data);
        });

        // Événements de scraping
        this.socket.on('scraping_started', (data) => {
            this.onScrapingStarted(data);
        });

        this.socket.on('scraping_progress', (data) => {
            this.onScrapingProgress(data);
        });

        this.socket.on('scraping_email_found', (data) => {
            this.onScrapingEmailFound(data);
        });

        this.socket.on('scraping_stopping', (data) => {
            this.onScrapingStopping(data);
        });

        this.socket.on('scraping_stopped', (data) => {
            this.onScrapingStopped(data);
        });

        this.socket.on('scraping_complete', (data) => {
            this.onScrapingComplete(data);
        });

        this.socket.on('scraping_error', (data) => {
            this.onScrapingError(data);
        });

        // Pack analyse site complet (Celery full_website_analysis_task), suivi via monitor_full_website_analysis
        this.socket.on('full_website_analysis_progress', (data) => {
            document.dispatchEvent(new CustomEvent('full_website_analysis:progress', { detail: data }));
        });
        this.socket.on('full_website_analysis_complete', (data) => {
            document.dispatchEvent(new CustomEvent('full_website_analysis:complete', { detail: data }));
        });
        this.socket.on('full_website_analysis_error', (data) => {
            document.dispatchEvent(new CustomEvent('full_website_analysis:error', { detail: data }));
        });
        this.socket.on('full_website_analysis_external_link_found', (data) => {
            document.dispatchEvent(
                new CustomEvent('full_website_analysis:external_link_found', { detail: data })
            );
        });
        this.socket.on('full_website_analysis_external_domain_enriched', (data) => {
            document.dispatchEvent(
                new CustomEvent('full_website_analysis:external_domain_enriched', { detail: data })
            );
        });
        // Mini-scrape des liens externes (tâche Celery séparée, émise via Redis message_queue)
        this.socket.on('external_mini_scrape_started', (data) => {
            document.dispatchEvent(new CustomEvent('external_mini_scrape:started', { detail: data }));
            try {
                if (localStorage.getItem('graph_analysis_debug') === '1') {
                    console.info('[WS] external_mini_scrape_started', data);
                }
            } catch (e) {}
        });
        this.socket.on('external_mini_scrape_complete', (data) => {
            document.dispatchEvent(new CustomEvent('external_mini_scrape:complete', { detail: data }));
            try {
                if (localStorage.getItem('graph_analysis_debug') === '1') {
                    console.info('[WS] external_mini_scrape_complete', data);
                }
            } catch (e) {}
        });
        this.socket.on('external_mini_scrape_domain_complete', (data) => {
            document.dispatchEvent(
                new CustomEvent('external_mini_scrape:domain_complete', { detail: data })
            );
            try {
                if (localStorage.getItem('graph_analysis_debug') === '1') {
                    console.info('[WS] external_mini_scrape_domain_complete', data);
                }
            } catch (e) {}
        });
    }

    // Méthodes de connexion
    onConnect() {
        const event = new CustomEvent('websocket:connected');
        document.dispatchEvent(event);
    }

    onDisconnect() {
        const event = new CustomEvent('websocket:disconnected');
        document.dispatchEvent(event);
    }

    onConnectionError(error) {
        const event = new CustomEvent('websocket:error', { detail: error });
        document.dispatchEvent(event);
    }

    // Méthodes d'analyse
    startAnalysis(filename, options) {
        if (!this.connected) {
            this.showError('WebSocket non connecté. Reconnexion...');
            this.connect(); // (safe: ne recrée pas de socket en boucle)
            return;
        }

        // Valeurs optimisées pour Celery avec --pool=threads --concurrency=4
        this.socket.emit('start_analysis', {
            filename: filename,
            max_workers: options.max_workers || 4,  // Optimisé pour Celery concurrency=4
            delay: options.delay || 0.1,             // Délai minimal, Celery gère la concurrence
            enable_osint: options.enable_osint || false
        });
    }

    stopAnalysis() {
        if (!this.connected) {
            this.showError('WebSocket non connecté');
            return;
        }

        this.socket.emit('stop_analysis');
    }

    onAnalysisStarted(data) {
        const event = new CustomEvent('analysis:started', { detail: data });
        document.dispatchEvent(event);
    }

    onAnalysisProgress(data) {
        const event = new CustomEvent('analysis:progress', { detail: data });
        document.dispatchEvent(event);
    }

    onAnalysisComplete(data) {
        const event = new CustomEvent('analysis:complete', { detail: data });
        document.dispatchEvent(event);
    }

    onAnalysisError(data) {
        const event = new CustomEvent('analysis:error', { detail: data });
        document.dispatchEvent(event);
    }

    onAnalysisErrorItem(data) {
        const event = new CustomEvent('analysis:error_item', { detail: data });
        document.dispatchEvent(event);
    }

    onAnalysisStopping(data) {
        const event = new CustomEvent('analysis:stopping', { detail: data });
        document.dispatchEvent(event);
    }

    onAnalysisStopped(data) {
        const event = new CustomEvent('analysis:stopped', { detail: data });
        document.dispatchEvent(event);
    }

    // Méthodes Pentest
    onPentestAnalysisStarted(data) {
        const event = new CustomEvent('pentest_analysis:started', { detail: data });
        document.dispatchEvent(event);
    }

    onPentestAnalysisProgress(data) {
        const event = new CustomEvent('pentest_analysis:progress', { detail: data });
        document.dispatchEvent(event);
    }

    onPentestAnalysisComplete(data) {
        const event = new CustomEvent('pentest_analysis:complete', { detail: data });
        document.dispatchEvent(event);
    }

    onPentestAnalysisError(data) {
        const event = new CustomEvent('pentest_analysis:error', { detail: data });
        document.dispatchEvent(event);
    }

    // Méthodes de scraping
    startScraping(url, options) {
        if (!this.connected) {
            this.showError('WebSocket non connecté. Reconnexion...');
            this.connect();
            return;
        }

        this.socket.emit('start_scraping', {
            url: url,
            max_depth: options.max_depth || 3,
            max_workers: options.max_workers || 5,
            max_time: options.max_time || 300
        });
    }

    stopScraping() {
        if (!this.connected) {
            this.showError('WebSocket non connecté');
            return;
        }

        this.socket.emit('stop_scraping');
    }

    onScrapingStarted(data) {
        const event = new CustomEvent('scraping:started', { detail: data });
        document.dispatchEvent(event);
    }

    onScrapingProgress(data) {
        const event = new CustomEvent('scraping:progress', { detail: data });
        document.dispatchEvent(event);
    }

    onScrapingEmailFound(data) {
        const event = new CustomEvent('scraping:email_found', { detail: data });
        document.dispatchEvent(event);
    }

    onScrapingStopping(data) {
        const event = new CustomEvent('scraping:stopping', { detail: data });
        document.dispatchEvent(event);
    }

    onScrapingStopped(data) {
        const event = new CustomEvent('scraping:stopped', { detail: data });
        document.dispatchEvent(event);
    }

    onScrapingComplete(data) {
        const event = new CustomEvent('scraping:complete', { detail: data });
        document.dispatchEvent(event);
    }

    onScrapingError(data) {
        const event = new CustomEvent('scraping:error', { detail: data });
        document.dispatchEvent(event);
    }

    // Utilitaires
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }

    showError(message) {
        console.error(message);
        // Créer une notification d'erreur
        const notification = document.createElement('div');
        notification.className = 'notification error';
        notification.textContent = message;
        notification.style.cssText = 'position: fixed; top: 20px; right: 20px; padding: 15px 20px; background: #f8d7da; color: #721c24; border-radius: 4px; z-index: 10000; box-shadow: 0 2px 8px rgba(0,0,0,0.2);';
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// Instance globale
const wsManager = new ProspectLabWebSocket();
window.wsManager = wsManager; // Exposer sur window pour utilisation globale

// Fonction pour vérifier si on est sur la page d'accès restreint
function isRestrictedPage() {
    // Vérifier la classe CSS
    if (document.body && document.body.classList.contains('restricted-page')) {
        return true;
    }
    // Vérifier le titre
    const pageTitle = document.title || '';
    if (pageTitle.includes('Accès restreint') || pageTitle.includes('restreint')) {
        return true;
    }
    // Vérifier le path
    const currentPath = window.location.pathname;
    if (currentPath === '/restricted' || currentPath.includes('restricted')) {
        return true;
    }
    // Vérifier le contenu (carte d'accès restreint)
    const restrictedCard = document.querySelector('.restricted-card');
    if (restrictedCard) {
        return true;
    }
    // Vérifier si le body contient le texte "Accès restreint au réseau local"
    const bodyText = document.body ? document.body.innerText || document.body.textContent || '' : '';
    if (bodyText.includes('Accès restreint au réseau local')) {
        return true;
    }
    return false;
}

// Attendre que le DOM soit complètement chargé avant de vérifier
function checkAndConnect() {
    // Attendre un peu pour que le DOM soit complètement chargé
    setTimeout(() => {
        // Ne pas se connecter sur la page d'accès restreint
        if (!isRestrictedPage()) {
            wsManager.connect();
        } else {
            // Page restreinte détectée, ne pas se connecter
            console.debug('Page d\'accès restreint détectée, WebSocket désactivé');
        }
    }, 100);
}

// Connexion automatique au chargement (uniquement si nécessaire)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkAndConnect);
} else {
    // DOM déjà chargé, vérifier immédiatement
    checkAndConnect();
}

