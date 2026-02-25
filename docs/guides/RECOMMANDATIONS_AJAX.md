# Recommandations d'utilisation d'AJAX/XHR dans ProspectLab

## État actuel

### ✅ Déjà implémenté avec AJAX/fetch

1. **Templates** (`templates.html`)
   - Création/modification de templates via `fetch()`
   - ✅ Bien fait, pas de rechargement de page

2. **Envoi d'emails** (`send_emails.html`)
   - Envoi via `fetch()` avec feedback en temps réel
   - ✅ Bien fait, affichage des résultats sans rechargement

3. **Actions sur entreprises** (`entreprises.refactored.js`, `entreprise_detail.js`)
   - Toggle favori via `fetch()`
   - Ajout/suppression de tags via `fetch()`
   - Sauvegarde de notes via `fetch()`
   - ✅ Bien fait, mise à jour dynamique

4. **Suppression d'analyses techniques** (`analyse_technique_detail.js`)
   - Suppression via `fetch()` avec confirmation
   - ✅ Bien fait, redirection après succès

5. **Chargement de données** (`entreprises.refactored.js`, `analyses_techniques.js`, `analyses_seo.js`, `campagnes.js`)
   - Chargement des entreprises via `fetch()` (liste, filtres avancés et ciblage par groupes dans l'assistant de campagne)
   - Chargement des analyses via `fetch()` : listes d'analyses techniques/OSINT/Pentest/SEO, détail d'une analyse (`/api/analyse-.../<id>`) et vues intégrées dans la modale entreprise (`/api/entreprise/<id>/analyse-technique`, `/analyse-osint`, `/analyse-pentest`, `/analyse-seo`)
   - ✅ Bien fait, pas de rechargement de page

### ⚠️ Points à améliorer avec AJAX

## 1. Upload de fichier Excel (Priorité: Élevée)

**Situation actuelle** :
- Formulaire POST classique avec `redirect()` après upload
- Rechargement complet de la page

**Amélioration proposée** :
```javascript
// Utiliser FormData et fetch avec progress
const form = document.querySelector('.upload-form');
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(form);
    const xhr = new XMLHttpRequest();
    
    // Barre de progression
    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            updateProgressBar(percentComplete);
        }
    });
    
    xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
            const data = JSON.parse(xhr.responseText);
            // Rediriger vers preview sans rechargement complet
            window.location.href = `/preview/${data.filename}`;
        }
    });
    
    xhr.open('POST', form.action);
    xhr.send(formData);
});
```

**Bénéfices** :
- Barre de progression pour les gros fichiers
- Pas de rechargement de page pendant l'upload
- Meilleure expérience utilisateur

## 2. Export CSV (Priorité: Moyenne)

**Situation actuelle** :
```javascript
window.location.href = `/export/csv?${params.toString()}`;
```

**Amélioration proposée** :
```javascript
async function exportCSV() {
    const params = new URLSearchParams({
        secteur: selectedSecteur,
        statut: selectedStatut,
        // ...
    });
    
    try {
        const response = await fetch(`/api/export/csv?${params}`, {
            method: 'GET'
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `entreprises_${new Date().toISOString()}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            showNotification('Export réussi', 'success');
        }
    } catch (error) {
        showNotification('Erreur lors de l\'export', 'error');
    }
}
```

**Bénéfices** :
- Pas de rechargement de page
- Feedback immédiat (succès/erreur)
- Téléchargement direct du fichier

## 3. Vidage de la base de données (Priorité: Moyenne)

**Situation actuelle** :
- Formulaire POST avec redirect après action

**Amélioration proposée** :
```javascript
async function clearDatabase() {
    if (!confirm('Êtes-vous sûr de vouloir vider toute la base de données ? Cette action est irréversible.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/database/clear', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('Base de données vidée avec succès', 'success');
            // Recharger les données sans recharger toute la page
            await loadEntreprises();
            await loadAnalyses();
        } else {
            showNotification(data.error || 'Erreur lors du vidage', 'error');
        }
    } catch (error) {
        showNotification('Erreur lors du vidage de la base de données', 'error');
    }
}
```

**Bénéfices** :
- Confirmation avant action
- Feedback immédiat
- Mise à jour des données sans rechargement complet

## 4. Suppression d'entreprises (Priorité: Moyenne)

**Situation actuelle** :
- Pas de fonctionnalité de suppression visible dans le code

**Amélioration proposée** :
```javascript
async function deleteEntreprise(entrepriseId, entrepriseName) {
    if (!confirm(`Êtes-vous sûr de vouloir supprimer "${entrepriseName}" ?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/entreprise/${entrepriseId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('Entreprise supprimée avec succès', 'success');
            // Retirer de la liste sans rechargement
            allEntreprises = allEntreprises.filter(e => e.id !== entrepriseId);
            applyFilters();
        } else {
            showNotification(data.error || 'Erreur lors de la suppression', 'error');
        }
    } catch (error) {
        showNotification('Erreur lors de la suppression', 'error');
    }
}
```

**Bénéfices** :
- Suppression immédiate sans rechargement
- Feedback visuel
- Meilleure UX

## 5. Filtres avec pagination serveur (Priorité: Faible)

**Situation actuelle** :
- Filtres côté client (déjà bien fait pour petits volumes)
- Toutes les données chargées en mémoire

**Amélioration proposée** (si volume important) :
```javascript
async function loadEntreprisesWithFilters(page = 1) {
    const params = new URLSearchParams({
        page: page,
        per_page: itemsPerPage,
        secteur: selectedSecteur,
        statut: selectedStatut,
        search: searchTerm
    });
    
    try {
        const response = await fetch(`/api/entreprises?${params}`);
        const data = await response.json();
        
        renderEntreprises(data.entreprises);
        renderPagination(data.total, data.page, data.pages);
    } catch (error) {
        console.error('Erreur lors du chargement:', error);
    }
}
```

**Bénéfices** :
- Meilleure performance pour gros volumes
- Moins de données en mémoire
- Pagination serveur

**Note** : À implémenter seulement si le nombre d'entreprises devient très important (>1000)

## 6. Mise à jour de statut/opportunité (Priorité: Faible)

**Situation actuelle** :
- Pas de fonctionnalité visible dans le code

**Amélioration proposée** :
```javascript
async function updateEntrepriseField(entrepriseId, field, value) {
    try {
        const response = await fetch(`/api/entreprise/${entrepriseId}/${field}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ value: value })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Mettre à jour l'affichage sans rechargement
            updateEntrepriseInList(entrepriseId, field, value);
            showNotification('Mise à jour réussie', 'success');
        }
    } catch (error) {
        showNotification('Erreur lors de la mise à jour', 'error');
    }
}
```

## Points à NE PAS changer (WebSocket)

### ✅ Garder WebSocket pour :

1. **Analyses en temps réel**
   - Progress bars
   - Mises à jour en direct
   - ✅ Parfait tel quel

2. **Scraping d'emails**
   - Affichage en temps réel des emails trouvés
   - ✅ Parfait tel quel

3. **Analyses techniques/OSINT/Pentest**
   - Progress et résultats en temps réel
   - ✅ Parfait tel quel

## Recommandations de priorité

### Priorité 1 (À faire rapidement)
1. **Upload Excel avec AJAX** - Améliore significativement l'UX
2. **Export CSV avec AJAX** - Simple et efficace

### Priorité 2 (À faire si temps disponible)
3. **Vidage BDD avec AJAX** - Améliore l'UX
4. **Suppression d'entreprises** - Fonctionnalité manquante

### Priorité 3 (Optionnel)
5. **Filtres serveur** - Seulement si volume important
6. **Mise à jour de champs** - Nice to have

## Exemple d'implémentation : Upload Excel avec AJAX

### Backend (`app.py`)
```python
@app.route('/api/upload', methods=['POST'])
def api_upload_file():
    """API: Upload de fichier Excel avec retour JSON"""
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Valider le fichier
        try:
            analyzer = EntrepriseAnalyzer(excel_file=filepath)
            df = analyzer.load_excel()
            
            return jsonify({
                'success': True,
                'filename': filename,
                'total_rows': len(df),
                'columns': list(df.columns)
            })
        except Exception as e:
            return jsonify({'error': f'Erreur lors de la lecture: {str(e)}'}), 400
    
    return jsonify({'error': 'Fichier invalide'}), 400
```

### Frontend (`upload.html`)
```javascript
const form = document.querySelector('.upload-form');
const progressContainer = document.createElement('div');
progressContainer.className = 'upload-progress';
progressContainer.style.display = 'none';

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(form);
    const xhr = new XMLHttpRequest();
    
    // Afficher la barre de progression
    progressContainer.style.display = 'block';
    form.after(progressContainer);
    
    // Progress
    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            progressContainer.innerHTML = `
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percent}%"></div>
                </div>
                <p>Upload en cours... ${Math.round(percent)}%</p>
            `;
        }
    });
    
    // Succès
    xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
            const data = JSON.parse(xhr.responseText);
            if (data.success) {
                window.location.href = `/preview/${data.filename}`;
            } else {
                showError(data.error || 'Erreur lors de l\'upload');
                progressContainer.style.display = 'none';
            }
        } else {
            showError('Erreur lors de l\'upload');
            progressContainer.style.display = 'none';
        }
    });
    
    // Erreur
    xhr.addEventListener('error', () => {
        showError('Erreur de connexion');
        progressContainer.style.display = 'none';
    });
    
    xhr.open('POST', '/api/upload');
    xhr.send(formData);
});
```

## Conclusion

L'utilisation d'AJAX est **déjà bien implémentée** pour la plupart des actions interactives. Les améliorations proposées concernent principalement :

1. **Upload de fichiers** - Pour une meilleure UX avec progress bar
2. **Exports** - Pour éviter les rechargements de page
3. **Actions destructives** - Pour un feedback immédiat

Les **WebSockets restent la meilleure solution** pour les opérations longues avec mises à jour en temps réel (analyses, scraping).

**Recommandation globale** : Implémenter les priorités 1 et 2 pour une meilleure expérience utilisateur, sans surcharger le code.

