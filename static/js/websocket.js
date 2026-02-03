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

        this.socket = io({
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: Infinity, // Reconnexion infinie
            timeout: 20000,
            forceNew: false
        });

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
            this.onConnect();
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            this.onDisconnect();
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
            this.onConnectionError(error);
            // Tentative de reconnexion automatique
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                setTimeout(() => {
                    this.connect();
                }, this.reconnectDelay);
            }
        });

        this.socket.on('reconnect', (attemptNumber) => {
            this.reconnectAttempts = 0;
        });

        this.socket.on('reconnect_error', (error) => {
            console.error('Erreur lors de la reconnexion:', error);
        });

        this.socket.on('reconnect_failed', () => {
            console.error('Échec de la reconnexion après toutes les tentatives');
            this.showError('Impossible de se reconnecter au serveur. Veuillez recharger la page.');
        });

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
            this.connect();
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

