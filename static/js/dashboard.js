/**
 * Dashboard JavaScript
 * Chargement et affichage des statistiques
 */

(function() {
    // Charger les statistiques
    async function loadStatistics() {
        try {
            const response = await fetch('/api/statistics');
            const stats = await response.json();
            
            // Mettre à jour les stats
            document.getElementById('stat-total-analyses').textContent = stats.total_analyses || 0;
            document.getElementById('stat-total-entreprises').textContent = stats.total_entreprises || 0;
            document.getElementById('stat-prospects').textContent = stats.par_statut?.['Prospect intéressant'] || 0;
            document.getElementById('stat-favoris').textContent = stats.favoris || 0;
            
            // Graphiques
            if (stats.par_secteur && Object.keys(stats.par_secteur).length > 0) {
                createSecteursChart(stats.par_secteur);
            }
            
            if (stats.par_opportunite && Object.keys(stats.par_opportunite).length > 0) {
                createOpportunitesChart(stats.par_opportunite);
            }
        } catch (error) {
            console.error('Erreur lors du chargement des statistiques:', error);
        }
    }
    
    function createSecteursChart(data) {
        const ctx = document.getElementById('chart-secteurs');
        if (!ctx) return;
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(data),
                datasets: [{
                    data: Object.values(data),
                    backgroundColor: [
                        '#3498db', '#e74c3c', '#2ecc71', '#f39c12',
                        '#9b59b6', '#1abc9c', '#34495e', '#e67e22'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    function createOpportunitesChart(data) {
        const ctx = document.getElementById('chart-opportunites');
        if (!ctx) return;
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(data),
                datasets: [{
                    label: 'Nombre d\'entreprises',
                    data: Object.values(data),
                    backgroundColor: '#3498db'
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
    
    // Charger les analyses récentes
    async function loadRecentAnalyses() {
        try {
            const response = await fetch('/api/analyses?limit=10');
            const analyses = await response.json();
            
            const listDiv = document.getElementById('analyses-list');
            if (analyses.length === 0) {
                listDiv.innerHTML = '<p>Aucune analyse pour le moment.</p>';
                return;
            }
            
            listDiv.innerHTML = analyses.map(analysis => `
                <div class="analysis-item">
                    <h4>${analysis.filename}</h4>
                    <p>${analysis.total_entreprises} entreprises - ${new Date(analysis.date_creation).toLocaleDateString('fr-FR')}</p>
                    <a href="/download/${analysis.output_filename}" class="btn btn-small">Télécharger</a>
                </div>
            `).join('');
        } catch (error) {
            console.error('Erreur lors du chargement des analyses:', error);
        }
    }
    
    // Gestion du bouton pour vider la base de données
    function setupClearDatabase() {
        const btnClear = document.getElementById('btn-clear-db');
        if (btnClear) {
            btnClear.addEventListener('click', async () => {
                if (!confirm('⚠️ ATTENTION : Cette action va supprimer TOUTES les données de la base de données !\n\nCela inclut :\n- Toutes les analyses\n- Toutes les entreprises\n- Toutes les analyses techniques\n- Tous les emails envoyés\n\nCette action est IRRÉVERSIBLE !\n\nÊtes-vous absolument sûr de vouloir continuer ?')) {
                    return;
                }
                
                // Double confirmation
                if (!confirm('Dernière confirmation : Voulez-vous vraiment TOUT supprimer ?')) {
                    return;
                }
                
                btnClear.disabled = true;
                btnClear.textContent = 'Suppression en cours...';
                
                try {
                    const response = await fetch('/api/database/clear', {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok && data.success) {
                        showNotification('Base de données vidée avec succès ! Rechargement...', 'success');
                        
                        // Recharger les données sans recharger toute la page
                        setTimeout(async () => {
                            await loadStatistics();
                            await loadRecentAnalyses();
                            btnClear.disabled = false;
                            btnClear.textContent = '🗑️ Vider la BDD';
                            showNotification('Données mises à jour', 'success');
                        }, 500);
                    } else {
                        showNotification('Erreur : ' + (data.error || 'Erreur inconnue'), 'error');
                        btnClear.disabled = false;
                        btnClear.textContent = '🗑️ Vider la BDD';
                    }
                } catch (error) {
                    console.error('Erreur lors de la suppression:', error);
                    showNotification('Erreur lors de la suppression de la base de données', 'error');
                    btnClear.disabled = false;
                    btnClear.textContent = '🗑️ Vider la BDD';
                }
            });
        }
    }
    
    // Fonction utilitaire pour afficher des notifications
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'success' ? '#d4edda' : type === 'error' ? '#f8d7da' : '#d1ecf1'};
            color: ${type === 'success' ? '#155724' : type === 'error' ? '#721c24' : '#0c5460'};
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    
    // Initialisation
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            loadStatistics();
            loadRecentAnalyses();
            setupClearDatabase();
        });
    } else {
        loadStatistics();
        loadRecentAnalyses();
        setupClearDatabase();
    }
})();

