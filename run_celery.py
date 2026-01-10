"""
Script wrapper pour démarrer Celery avec une meilleure gestion de Ctrl+C sur Windows

Usage:
    python run_celery.py
"""

import signal
import sys
import os
import threading
import time
import subprocess

def signal_handler(sig, frame):
    """Gère Ctrl+C proprement"""
    print('\n\n[!] Arrêt de Celery demandé...')
    # Arrêter le processus Celery si il existe
    global celery_process
    if celery_process and celery_process.poll() is None:
        celery_process.terminate()
        try:
            celery_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            celery_process.kill()
    # Arrêt forcé immédiat sur Windows
    os._exit(0)

# Variable globale pour le processus Celery
celery_process = None

def run_celery_worker():
    """Lance le worker Celery via subprocess"""
    global celery_process
    try:
        # Lancer Celery comme une commande système
        celery_process = subprocess.Popen(
            [sys.executable, '-m', 'celery', '-A', 'celery_app', 'worker', '--loglevel=info', '--pool=solo'],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        celery_process.wait()
    except KeyboardInterrupt:
        print('\n\n[!] Arrêt de Celery...')
        if celery_process:
            celery_process.terminate()
        os._exit(0)
    except Exception as e:
        print(f'Erreur lors du lancement de Celery: {e}')
        import traceback
        traceback.print_exc()
        if celery_process:
            celery_process.terminate()
        os._exit(1)

def main():
    """Point d'entrée principal"""
    # Variable globale pour contrôler l'arrêt
    shutdown_event = threading.Event()
    
    # Enregistrer le gestionnaire de signal AVANT de lancer Celery
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform == 'win32':
        signal.signal(signal.SIGTERM, signal_handler)
    
    print('Démarrage du worker Celery...')
    print('Appuyez sur Ctrl+C pour arrêter Celery\n')
    
    # Lancer Celery dans un thread séparé (non-daemon pour qu'il reste actif)
    celery_thread = threading.Thread(target=run_celery_worker, daemon=False)
    celery_thread.start()
    
    # Attendre que le thread démarre
    time.sleep(0.5)
    
    # Surveiller l'arrêt dans le thread principal
    try:
        # Sur Windows, surveiller l'entrée standard dans le thread principal
        if sys.platform == 'win32':
            try:
                import msvcrt
                while celery_thread.is_alive() and not shutdown_event.is_set():
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\x03':  # Ctrl+C
                            print('\n\n[!] Ctrl+C détecté - Arrêt de Celery...')
                            os._exit(0)
                    time.sleep(0.1)
            except ImportError:
                # msvcrt non disponible, attendre simplement
                celery_thread.join()
        else:
            # Sur Linux/Mac, attendre normalement
            celery_thread.join()
    except KeyboardInterrupt:
        print('\n\n[!] Arrêt de Celery...')
        os._exit(0)

if __name__ == '__main__':
    main()

