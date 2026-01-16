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
    
    // Initialisation
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            loadStatistics();
            loadRecentAnalyses();
        });
    } else {
        loadStatistics();
        loadRecentAnalyses();
    }
})();

