"""
Script pour nettoyer Redis et arrêter toutes les tâches Celery en cours
"""
import subprocess
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def clear_redis():
    """Nettoie toutes les données Celery dans Redis"""
    try:
        print("Nettoyage de Redis...")
        
        # Essayer d'utiliser redis-cli directement
        try:
            # Flush DB 0 (broker)
            result = subprocess.run(['redis-cli', 'FLUSHDB'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✓ Queue broker nettoyée")
            else:
                print(f"⚠ Erreur redis-cli: {result.stderr}")
        except FileNotFoundError:
            print("⚠ redis-cli non trouvé, tentative avec Python redis...")
            try:
                import redis
                from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
                
                broker_client = redis.from_url(CELERY_BROKER_URL)
                backend_client = redis.from_url(CELERY_RESULT_BACKEND)
                
                broker_client.flushdb()
                print("✓ Queue broker nettoyée")
                
                backend_client.flushdb()
                print("✓ Backend résultats nettoyé")
            except ImportError:
                print("❌ redis-cli et module redis non disponibles")
                print("Installe redis-cli ou le module redis: pip install redis")
                return False
        
        print("\n✓ Redis complètement nettoyé !")
        print("Tu peux maintenant redémarrer Celery.")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage: {e}")
        print("Assure-toi que Redis est démarré.")
        return False

if __name__ == '__main__':
    success = clear_redis()
    sys.exit(0 if success else 1)

