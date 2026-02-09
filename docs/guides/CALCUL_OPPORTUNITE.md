# Calcul du score d'opportunité

Le système calcule automatiquement un score d'opportunité pour chaque entreprise en combinant plusieurs facteurs provenant des différentes analyses.

## Facteurs pris en compte

### 1. Âge du site (0-25 points)
- **Score d'obsolescence** : Détecte les technologies obsolètes, HTML ancien, Flash/Plugins
- Plus le site est obsolète, plus l'opportunité est élevée
- Calculé lors de l'analyse initiale de l'entreprise

### 2. Sécurité technique (0-20 points)
- **Score de sécurité** : Basé sur l'analyse technique (SSL, headers de sécurité, WAF, etc.)
- Plus la sécurité est faible, plus l'opportunité est élevée
- Score inversé : `(100 - security_score) / 5`

### 3. Performance technique (0-15 points)
- **Score de performance** : Basé sur les temps de réponse, taille des pages, etc.
- Plus les performances sont faibles, plus l'opportunité est élevée
- Score inversé : `(100 - performance_score) / 6.67`

### 4. Analyse Pentest (0-20 points)
- **Score de risque** : Basé sur les vulnérabilités trouvées
- Plus le risque est élevé, plus l'opportunité est élevée
- Prend en compte les vulnérabilités critiques et hautes

### 5. Analyse OSINT (0-10 points)
- **Données trouvées** : Nombre de personnes et emails identifiés
- Plus on trouve de données, plus l'entreprise est active (opportunité élevée)
- Points pour les personnes : max 5 points
- Points pour les emails : max 5 points

### 6. Données de scraping (0-10 points)
- **Contacts trouvés** : Emails, personnes, téléphones
- Plus on trouve de contacts, plus l'opportunité est élevée
- Points pour les emails : max 4 points
- Points pour les personnes : max 3 points
- Points pour les téléphones : max 3 points

## Niveaux d'opportunité

Le score final (0-100) détermine le niveau :

- **Très élevée** : Score ≥ 80
- **Élevée** : Score ≥ 60
- **Moyenne** : Score ≥ 40
- **Faible** : Score ≥ 20
- **Très faible** : Score < 20

## Recalcul automatique

L'opportunité est recalculée automatiquement après :
- L'analyse technique
- L'analyse Pentest
- L'analyse OSINT
- Le scraping (si données importantes trouvées)

## Recalcul manuel

Pour recalculer manuellement l'opportunité d'une entreprise :

```bash
POST /api/entreprise/<id>/recalculate-opportunity
```

La réponse inclut le breakdown détaillé :

```json
{
  "success": true,
  "opportunity": "Élevée",
  "score": 65,
  "breakdown": {
    "age": 20,
    "security": 12,
    "performance": 8,
    "pentest": 15,
    "osint": 5,
    "scraping": 5
  },
  "indicators": [
    "Site obsolète",
    "Sécurité faible détectée",
    "2 vulnérabilité(s) haute(s)",
    "5 personne(s) identifiée(s)"
  ]
}
```
