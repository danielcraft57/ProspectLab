"""
Tâches de debug pour vérifier le bon fonctionnement du cluster Celery.
"""

from celery_app import celery


@celery.task(name="debug.ping")
def debug_ping(x: int, y: int) -> int:
    """
    Tâche de test très simple pour vérifier qu'un worker peut exécuter une tâche.

    Args:
        x (int): Première valeur.
        y (int): Deuxième valeur.

    Returns:
        int: Somme de x et y.
    """
    return x + y

