/**
 * JavaScript pour la page de carte des entreprises
 * Utilise Leaflet pour la visualisation cartographique
 */

(function() {
    let map;
    let markers = [];
    let currentLayer = null;
    
    document.addEventListener('DOMContentLoaded', () => {
        initMap();
        loadSecteurs();
        setupEventListeners();
        loadAllEntreprises();
    });
    
    function initMap() {
        // Initialiser la carte centrée sur la France (Metz par défaut)
        map = L.map('map').setView([49.1193, 6.1757], 6);
        
        // Ajouter la couche de tuiles OpenStreetMap
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);
        
        // Permettre de cliquer sur la carte pour définir un point de recherche
        map.on('click', function(e) {
            document.getElementById('search-lat').value = e.latlng.lat.toFixed(6);
            document.getElementById('search-lng').value = e.latlng.lng.toFixed(6);
        });
    }
    
    async function loadSecteurs() {
        try {
            const response = await fetch('/api/entreprises');
            const entreprises = await response.json();
            
            const secteurs = [...new Set(entreprises.map(e => e.secteur).filter(Boolean))].sort();
            const select = document.getElementById('filter-secteur');
            
            secteurs.forEach(secteur => {
                const option = document.createElement('option');
                option.value = secteur;
                option.textContent = secteur;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Erreur lors du chargement des secteurs:', error);
        }
    }
    
    function setupEventListeners() {
        document.getElementById('btn-search-nearby').addEventListener('click', searchNearby);
        document.getElementById('btn-load-all').addEventListener('click', loadAllEntreprises);
        document.getElementById('filter-secteur').addEventListener('change', filterBySecteur);
    }
    
    async function searchNearby() {
        const lat = parseFloat(document.getElementById('search-lat').value);
        const lng = parseFloat(document.getElementById('search-lng').value);
        const radius = parseFloat(document.getElementById('search-radius').value);
        const secteur = document.getElementById('filter-secteur').value;
        
        if (!lat || !lng) {
            alert('Veuillez définir un point de recherche (cliquez sur la carte ou saisissez les coordonnées)');
            return;
        }
        
        try {
            let url = `/api/entreprises/nearby?latitude=${lat}&longitude=${lng}&radius_km=${radius}`;
            if (secteur) {
                url += `&secteur=${encodeURIComponent(secteur)}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                displayEntreprises(data.entreprises, lat, lng);
                
                // Centrer la carte sur le point de recherche
                map.setView([lat, lng], 12);
                
                // Ajouter un marqueur pour le point de recherche
                if (currentLayer) {
                    map.removeLayer(currentLayer);
                }
                currentLayer = L.circle([lat, lng], {
                    radius: radius * 1000, // Convertir en mètres
                    color: '#667eea',
                    fillColor: '#667eea',
                    fillOpacity: 0.2
                }).addTo(map);
            }
        } catch (error) {
            console.error('Erreur lors de la recherche:', error);
            alert('Erreur lors de la recherche des entreprises proches');
        }
    }
    
    async function loadAllEntreprises() {
        try {
            const response = await fetch('/api/entreprises');
            const entreprises = await response.json();
            
            // Filtrer celles qui ont des coordonnées
            const entreprisesWithCoords = entreprises.filter(e => e.latitude && e.longitude);
            
            displayEntreprises(entreprisesWithCoords);
            
            // Ajuster la vue pour afficher toutes les entreprises
            if (entreprisesWithCoords.length > 0) {
                const group = new L.featureGroup(markers);
                map.fitBounds(group.getBounds().pad(0.1));
            }
        } catch (error) {
            console.error('Erreur lors du chargement:', error);
        }
    }
    
    function filterBySecteur() {
        const secteur = document.getElementById('filter-secteur').value;
        
        // Filtrer les marqueurs affichés
        markers.forEach(marker => {
            const entreprise = marker.entreprise;
            if (!secteur || entreprise.secteur === secteur) {
                marker.addTo(map);
            } else {
                map.removeLayer(marker);
            }
        });
    }
    
    function displayEntreprises(entreprises) {
        // Supprimer les anciens marqueurs
        clearMarkers();
        
        if (entreprises.length === 0) {
            document.getElementById('results-info').style.display = 'none';
            return;
        }
        
        // Afficher les résultats
        document.getElementById('results-count').textContent = 
            entreprises.length + ' entreprise' + (entreprises.length > 1 ? 's' : '') + ' trouvée' + (entreprises.length > 1 ? 's' : '');
        document.getElementById('results-info').style.display = 'block';
        
        // Créer la liste des résultats
        const resultsList = document.getElementById('results-list');
        resultsList.innerHTML = entreprises.map(e => createEntrepriseCard(e)).join('');
        
        // Ajouter les marqueurs sur la carte
        entreprises.forEach(entreprise => {
            const marker = L.marker([entreprise.latitude, entreprise.longitude])
                .bindPopup(createPopupContent(entreprise))
                .addTo(map);
            
            marker.entreprise = entreprise;
            markers.push(marker);
        });
        
        // Ajuster la vue si nécessaire
        if (markers.length > 0) {
            const group = new L.featureGroup(markers);
            if (markers.length === 1) {
                map.setView([entreprises[0].latitude, entreprises[0].longitude], 13);
            } else {
                map.fitBounds(group.getBounds().pad(0.1));
            }
        }
    }
    
    function createPopupContent(entreprise) {
        const distance = entreprise.distance_km ? 
            '<p class="distance-badge">Distance: ' + entreprise.distance_km + ' km</p>' : '';
        
        return `
            <div class="info-popup">
                <h4>${escapeHtml(entreprise.nom || 'Sans nom')}</h4>
                ${entreprise.secteur ? '<p><strong>Secteur:</strong> ' + escapeHtml(entreprise.secteur) + '</p>' : ''}
                ${entreprise.website ? '<p><strong>Site:</strong> <a href="' + escapeHtml(entreprise.website) + '" target="_blank">' + escapeHtml(entreprise.website) + '</a></p>' : ''}
                ${entreprise.telephone ? '<p><strong>Tél:</strong> ' + escapeHtml(entreprise.telephone) + '</p>' : ''}
                ${(entreprise.address_1 || entreprise.address_2) ? '<p><strong>Adresse:</strong> ' + escapeHtml([entreprise.address_1, entreprise.address_2].filter(Boolean).join(', ')) + '</p>' : ''}
                ${entreprise.note_google ? '<p><strong>Note Google:</strong> ' + entreprise.note_google + '/5 (' + (entreprise.nb_avis_google || 0) + ' avis)</p>' : ''}
                ${distance}
            </div>
        `;
    }
    
    function createEntrepriseCard(entreprise) {
        const distance = entreprise.distance_km ? 
            '<span class="badge badge-info" style="margin-left: 0.5rem;">' + entreprise.distance_km + ' km</span>' : '';
        
        return `
            <div style="padding: 0.75rem; border-bottom: 1px solid #e9ecef; cursor: pointer;" 
                 onclick="focusOnEntreprise(${entreprise.latitude}, ${entreprise.longitude})">
                <strong>${escapeHtml(entreprise.nom || 'Sans nom')}</strong>${distance}
                ${entreprise.secteur ? '<br><small style="color: #6c757d;">' + escapeHtml(entreprise.secteur) + '</small>' : ''}
                ${entreprise.website ? '<br><a href="' + escapeHtml(entreprise.website) + '" target="_blank" style="font-size: 0.85rem;">' + escapeHtml(entreprise.website) + '</a>' : ''}
            </div>
        `;
    }
    
    function focusOnEntreprise(lat, lng) {
        map.setView([lat, lng], 15);
        
        // Trouver et ouvrir le popup du marqueur correspondant
        markers.forEach(marker => {
            if (marker.getLatLng().lat === lat && marker.getLatLng().lng === lng) {
                marker.openPopup();
            }
        });
    }
    
    function clearMarkers() {
        markers.forEach(marker => {
            map.removeLayer(marker);
        });
        markers = [];
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Exposer la fonction globalement pour les onclick
    window.focusOnEntreprise = focusOnEntreprise;
})();

