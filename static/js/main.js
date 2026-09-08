// Script principal ProspectLab

// Fonctions utilitaires
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }
}

// Gestion des formulaires et du thème
document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages
    const flashMessages = document.querySelectorAll('.alert');
    flashMessages.forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 300);
        }, 5000);
    });

    // Gestion du thème : auto (système) / sombre / clair
    const THEME_STORAGE_KEY = 'theme';
    const VALID_THEME_PREFS = new Set(['auto', 'dark', 'light']);

    /**
     * Lit la préférence utilisateur (auto par défaut).
     * @returns {'auto'|'dark'|'light'}
     */
    function loadThemePreference() {
        try {
            const stored = localStorage.getItem(THEME_STORAGE_KEY);
            if (stored && VALID_THEME_PREFS.has(stored)) return stored;
        } catch (e) {
            // Ignorer les erreurs de stockage
        }
        return 'auto';
    }

    /**
     * Résout auto → thème effectif selon le système.
     * @param {'auto'|'dark'|'light'} pref
     * @returns {'dark'|'light'}
     */
    function resolveTheme(pref) {
        if (pref === 'dark') return 'dark';
        if (pref === 'light') return 'light';
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    /**
     * Applique la préférence sur le document.
     * @param {'auto'|'dark'|'light'} pref
     */
    function applyThemePreference(pref) {
        const body = document.body;
        const html = document.documentElement;
        if (!body) return;

        const safePref = VALID_THEME_PREFS.has(pref) ? pref : 'auto';
        const resolved = resolveTheme(safePref);

        body.dataset.themePref = safePref;
        if (resolved === 'dark') {
            body.setAttribute('data-theme', 'dark');
        } else {
            body.removeAttribute('data-theme');
        }

        if (html) {
            html.style.colorScheme = resolved;
        }
    }

    /**
     * Passe au mode suivant : auto → sombre → clair → auto.
     * @param {'auto'|'dark'|'light'} current
     * @returns {'auto'|'dark'|'light'}
     */
    function cycleThemePreference(current) {
        if (current === 'auto') return 'dark';
        if (current === 'dark') return 'light';
        return 'auto';
    }

    let themePreference = loadThemePreference();
    applyThemePreference(themePreference);

    const toggleBtn = document.querySelector('.theme-toggle-btn');
    if (toggleBtn) {
        const icon = toggleBtn.querySelector('i');

        /**
         * Met à jour l'icône et les libellés du bouton thème.
         * @param {'auto'|'dark'|'light'} pref
         */
        function updateThemeToggleUi(pref) {
            if (!icon) return;
            icon.classList.remove('fa-moon', 'fa-sun', 'fa-circle-half-stroke');
            if (pref === 'dark') {
                icon.classList.add('fa-moon');
                toggleBtn.setAttribute('aria-label', 'Thème : sombre');
                toggleBtn.title = 'Thème sombre (cliquer pour clair)';
            } else if (pref === 'light') {
                icon.classList.add('fa-sun');
                toggleBtn.setAttribute('aria-label', 'Thème : clair');
                toggleBtn.title = 'Thème clair (cliquer pour auto)';
            } else {
                icon.classList.add('fa-circle-half-stroke');
                toggleBtn.setAttribute('aria-label', 'Thème : automatique');
                toggleBtn.title = 'Thème auto · suit le système (cliquer pour sombre)';
            }
        }

        updateThemeToggleUi(themePreference);

        toggleBtn.addEventListener('click', function() {
            themePreference = cycleThemePreference(themePreference);
            applyThemePreference(themePreference);
            updateThemeToggleUi(themePreference);
            try {
                localStorage.setItem(THEME_STORAGE_KEY, themePreference);
            } catch (e) {
                // Ignorer les erreurs de stockage
            }
        });

        if (window.matchMedia) {
            const mq = window.matchMedia('(prefers-color-scheme: dark)');
            const onSystemThemeChange = function() {
                if (themePreference === 'auto') {
                    applyThemePreference('auto');
                }
            };
            if (typeof mq.addEventListener === 'function') {
                mq.addEventListener('change', onSystemThemeChange);
            } else if (typeof mq.addListener === 'function') {
                mq.addListener(onSystemThemeChange);
            }
        }
    }

    // Menu burger (tablette & mobile)
    const navbar = document.querySelector('.navbar');
    const navToggle = document.querySelector('.nav-toggle-btn');
    const navBackdrop = document.querySelector('.nav-backdrop');
    const navLinks = document.querySelectorAll('.nav-links a');

    if (navbar && navToggle) {
        const closeMenu = () => {
            navbar.classList.remove('navbar--open');
        };

        navToggle.addEventListener('click', () => {
            navbar.classList.toggle('navbar--open');
        });

        if (navBackdrop) {
            navBackdrop.addEventListener('click', closeMenu);
        }

        navLinks.forEach(link => {
            link.addEventListener('click', closeMenu);
        });
    }

    // Centre de notifications global
    (function initNotificationsCenter() {
        const toggleBtn = document.querySelector('[data-notifications-toggle]');
        const badge = document.querySelector('[data-notifications-badge]');
        const panel = document.querySelector('[data-notifications-panel]');
        const list = document.querySelector('[data-notifications-list]');
        const clearBtn = document.querySelector('[data-notifications-clear]');

        if (!toggleBtn || !badge || !panel || !list) {
            return;
        }

        function formatTime(date) {
            try {
                const d = (date instanceof Date) ? date : new Date(date);
                return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
            } catch (e) {
                return '';
            }
        }

        function renderList() {
            const items = (window.Notifications && typeof window.Notifications.getAll === 'function')
                ? window.Notifications.getAll()
                : [];

            list.innerHTML = '';

            if (!items.length) {
                const empty = document.createElement('div');
                empty.className = 'notifications-empty';
                empty.textContent = 'Aucune notification pour le moment.';
                list.appendChild(empty);
                return;
            }

            items.forEach(item => {
                const el = document.createElement('div');
                el.className = 'notification-item notification-item--' + (item.type || 'info') + (item.read ? '' : ' notification-item-unread');

                const icon = document.createElement('div');
                icon.className = 'notification-item-icon';
                icon.innerHTML = `<i class="fas ${item.icon || window.Notifications.getDefaultIcon(item.type)}"></i>`;

                const body = document.createElement('div');
                body.className = 'notification-item-body';

                const msg = document.createElement('div');
                msg.className = 'notification-item-message';
                msg.textContent = item.message;

                const meta = document.createElement('div');
                meta.className = 'notification-item-meta';
                meta.textContent = formatTime(item.date);

                body.appendChild(msg);
                body.appendChild(meta);

                el.appendChild(icon);
                el.appendChild(body);

                list.appendChild(el);
            });
        }

        function updateBadge(unread) {
            const count = typeof unread === 'number'
                ? unread
                : (window.Notifications && typeof window.Notifications.getUnreadCount === 'function'
                    ? window.Notifications.getUnreadCount()
                    : 0);
            if (count > 0) {
                badge.textContent = String(count);
                badge.style.display = 'inline-flex';
            } else {
                badge.style.display = 'none';
            }
        }

        function openPanel() {
            panel.hidden = false;
            panel.style.display = 'block';
            if (window.Notifications && typeof window.Notifications.markAllAsRead === 'function') {
                window.Notifications.markAllAsRead();
            }
            updateBadge(0);
            renderList();
        }

        function closePanel() {
            panel.hidden = true;
            panel.style.display = 'none';
        }

        toggleBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (panel.hidden) {
                openPanel();
            } else {
                closePanel();
            }
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                if (window.Notifications && typeof window.Notifications.clearAll === 'function') {
                    window.Notifications.clearAll();
                }
                renderList();
                updateBadge(0);
            });
        }

        document.addEventListener('click', function (e) {
            if (!panel.hidden && !panel.contains(e.target) && !toggleBtn.contains(e.target)) {
                closePanel();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !panel.hidden) {
                closePanel();
            }
        });

        document.addEventListener('notifications:new', function (e) {
            const detail = e.detail || {};
            renderList();
            updateBadge(detail.unreadCount);
        });

        // Initial render (au cas où des notifs ont été générées très tôt)
        renderList();
        updateBadge();
        // Fermer le panneau par défaut au chargement (au cas où le CSS l’afficherait)
        closePanel();
    })();
});

