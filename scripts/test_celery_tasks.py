#!/usr/bin/env python
"""
Script pour tester que les tâches Celery sont bien enregistrées
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from celery_app import celery
    
    print("Tâches Celery enregistrées:")
    print("=" * 50)
    
    # Lister toutes les tâches enregistrées
    registered_tasks = list(celery.tasks.keys())
    
    if registered_tasks:
        for task_name in sorted(registered_tasks):
            # Ignorer les tâches système
            if not task_name.startswith('celery.'):
                print(f"  ✓ {task_name}")
    else:
        print("  ✗ Aucune tâche enregistrée!")
        print()
        print("Les tâches doivent être importées pour être enregistrées.")
        print("Vérifiez que les imports sont corrects dans celery_app.py")
        sys.exit(1)
    
    # Vérifier les tâches spécifiques
    print()
    print("Vérification des tâches principales:")
    print("=" * 50)
    
    required_tasks = [
        'tasks.analysis_tasks.analyze_entreprise_task',
        'tasks.scraping_tasks.scrape_emails_task',
    ]
    
    missing_tasks = []
    for task_name in required_tasks:
        if task_name in celery.tasks:
            print(f"  ✓ {task_name}")
        else:
            print(f"  ✗ {task_name} - MANQUANTE")
            missing_tasks.append(task_name)
    
    if missing_tasks:
        print()
        print("ERREUR: Certaines tâches ne sont pas enregistrées!")
        print("Redémarre Celery après avoir corrigé les imports.")
        sys.exit(1)
    else:
        print()
        print("✓ Toutes les tâches sont correctement enregistrées!")
        
except Exception as e:
    print(f"ERREUR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

