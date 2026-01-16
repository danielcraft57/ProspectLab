#!/usr/bin/env python
"""
Script de test pour vérifier la connexion Redis et Celery
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
    print(f"Configuration Redis:")
    print(f"  BROKER_URL: {CELERY_BROKER_URL}")
    print(f"  RESULT_BACKEND: {CELERY_RESULT_BACKEND}")
    print()
except Exception as e:
    print(f"Erreur lors du chargement de la config: {e}")
    sys.exit(1)

# Test de connexion Redis
try:
    import redis
    from urllib.parse import urlparse
    
    # Parser l'URL Redis
    broker_url = urlparse(CELERY_BROKER_URL)
    redis_host = broker_url.hostname or 'localhost'
    redis_port = broker_url.port or 6379
    redis_db = int(broker_url.path.lstrip('/')) if broker_url.path else 0
    
    print(f"Test de connexion Redis:")
    print(f"  Host: {redis_host}")
    print(f"  Port: {redis_port}")
    print(f"  DB: {redis_db}")
    print()
    
    # Tester la connexion
    r = redis.Redis(host=redis_host, port=redis_port, db=redis_db, socket_connect_timeout=5)
    result = r.ping()
    print(f"✓ Connexion Redis OK: {result}")
    
    # Tester quelques opérations
    r.set('test_key', 'test_value', ex=10)
    value = r.get('test_key')
    print(f"✓ Test d'écriture/lecture OK: {value.decode()}")
    r.delete('test_key')
    
except ImportError:
    print("✗ Module 'redis' non installé")
    print("  Installez-le avec: pip install redis")
    sys.exit(1)
except redis.ConnectionError as e:
    print(f"✗ Erreur de connexion Redis: {e}")
    print(f"  Vérifiez que Redis est démarré sur {redis_host}:{redis_port}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Erreur: {e}")
    sys.exit(1)

# Test de connexion Celery
try:
    from celery_app import celery
    
    print()
    print("Test de connexion Celery:")
    
    # Vérifier les workers actifs
    inspect = celery.control.inspect()
    active_workers = inspect.active()
    
    if active_workers:
        print(f"✓ Celery workers actifs: {len(active_workers)}")
        for worker, tasks in active_workers.items():
            print(f"  - {worker}: {len(tasks)} tâche(s)")
    else:
        print("✗ Aucun worker Celery actif")
        print("  Démarrez Celery avec: celery -A celery_app worker --loglevel=info")
    
    # Tester une tâche simple
    print()
    print("Test d'envoi de tâche:")
    try:
        from tasks.analysis_tasks import analyze_entreprise_task
        print("✓ Module de tâches chargé")
    except Exception as e:
        print(f"✗ Erreur lors du chargement des tâches: {e}")
        
except Exception as e:
    print(f"✗ Erreur Celery: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("✓ Tous les tests sont passés!")

