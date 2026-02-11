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

    // Gestion du thème clair/sombre
    function applyTheme(theme) {
        const body = document.body;
        if (!body) return;
        if (theme === 'dark') {
            body.setAttribute('data-theme', 'dark');
        } else {
            body.removeAttribute('data-theme');
        }
    }

    // Choix initial: localStorage > préférence système > clair
    let currentTheme = localStorage.getItem('theme');
    if (!currentTheme) {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            currentTheme = 'dark';
        } else {
            currentTheme = 'light';
        }
    }
    applyTheme(currentTheme);

    const toggleBtn = document.querySelector('.theme-toggle-btn');
    if (toggleBtn) {
        const icon = toggleBtn.querySelector('i');

        function updateIcon(theme) {
            if (!icon) return;
            if (theme === 'dark') {
                icon.classList.remove('fa-moon');
                icon.classList.add('fa-sun');
            } else {
                icon.classList.remove('fa-sun');
                icon.classList.add('fa-moon');
            }
        }

        updateIcon(currentTheme);

        toggleBtn.addEventListener('click', function() {
            currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(currentTheme);
            updateIcon(currentTheme);
            try {
                localStorage.setItem('theme', currentTheme);
            } catch (e) {
                // Ignorer les erreurs de stockage
            }
        });
    }
});

