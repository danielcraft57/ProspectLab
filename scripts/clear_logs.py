#!/usr/bin/env python3
"""
Script pour nettoyer les fichiers de logs de ProspectLab

Ce script permet de vider tous les fichiers de logs ou seulement certains fichiers spécifiques.
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_all_log_files(logs_dir='logs'):
    """Récupère la liste de tous les fichiers de logs"""
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        return []
    
    log_files = []
    for file in logs_path.glob('*.log'):
        log_files.append(file)
    
    return sorted(log_files)


def get_log_file_size(file_path):
    """Récupère la taille d'un fichier de log en Ko"""
    try:
        size_bytes = file_path.stat().st_size
        return size_bytes / 1024  # Ko
    except Exception:
        return 0


def clear_log_file(file_path, delete=False):
    """
    Vide un fichier de log spécifique
    
    Args:
        file_path: Chemin vers le fichier de log
        delete: Si True, supprime le fichier, sinon le vide
    
    Returns:
        bool: True si succès, False sinon
    """
    try:
        if delete:
            file_path.unlink()
            return True
        else:
            file_path.write_text('')
            return True
    except Exception as e:
        print(f'  Erreur lors du traitement de {file_path.name}: {e}')
        return False


def clear_all_logs(logs_dir='logs', delete=False, confirm=True):
    """
    Vide tous les fichiers de logs
    
    Args:
        logs_dir: Répertoire contenant les logs
        delete: Si True, supprime les fichiers, sinon les vide
        confirm: Demander confirmation avant de supprimer (défaut: True)
    """
    log_files = get_all_log_files(logs_dir)
    
    if not log_files:
        print(f'Aucun fichier de log trouvé dans {logs_dir}/')
        return
    
    print(f'Répertoire des logs: {logs_dir}/')
    print(f'Fichiers de logs trouvés: {len(log_files)}')
    print('\nFichiers à traiter:')
    
    total_size = 0
    for log_file in log_files:
        size_kb = get_log_file_size(log_file)
        total_size += size_kb
        size_str = f'{size_kb:.2f} Ko' if size_kb < 1024 else f'{size_kb/1024:.2f} Mo'
        print(f'  - {log_file.name}: {size_str}')
    
    total_size_str = f'{total_size:.2f} Ko' if total_size < 1024 else f'{total_size/1024:.2f} Mo'
    print(f'\nTaille totale: {total_size_str}')
    
    action = 'supprimer' if delete else 'vider'
    
    if confirm:
        print(f'\n⚠️  ATTENTION: Cette opération va {action} tous les fichiers de logs!')
        response = input('Êtes-vous sûr de vouloir continuer? (oui/non): ')
        if response.lower() not in ['oui', 'o', 'yes', 'y']:
            print('Opération annulée.')
            return
    
    print(f'\nNettoyage en cours...')
    
    success_count = 0
    for log_file in log_files:
        if clear_log_file(log_file, delete):
            action_done = 'supprimé' if delete else 'vidé'
            print(f'  ✓ {log_file.name}: {action_done}')
            success_count += 1
    
    print(f'\n✓ Nettoyage terminé: {success_count}/{len(log_files)} fichiers traités.')


def clear_specific_logs(logs_dir='logs', log_names=None, delete=False, confirm=True):
    """
    Vide uniquement certains fichiers de logs spécifiques
    
    Args:
        logs_dir: Répertoire contenant les logs
        log_names: Liste des noms de fichiers à vider (sans extension)
        delete: Si True, supprime les fichiers, sinon les vide
        confirm: Demander confirmation avant de supprimer (défaut: True)
    """
    if not log_names:
        print('Aucun fichier spécifié.')
        return
    
    all_log_files = get_all_log_files(logs_dir)
    
    # Créer un dictionnaire nom -> fichier
    log_files_dict = {f.stem: f for f in all_log_files}
    
    # Filtrer les fichiers demandés
    selected_files = []
    invalid_names = []
    
    for name in log_names:
        # Enlever l'extension .log si elle est présente
        name_clean = name.replace('.log', '')
        
        if name_clean in log_files_dict:
            selected_files.append(log_files_dict[name_clean])
        else:
            invalid_names.append(name)
    
    if invalid_names:
        print(f'⚠️  Fichiers introuvables: {", ".join(invalid_names)}')
    
    if not selected_files:
        print('Aucun fichier valide à traiter.')
        return
    
    print(f'Répertoire des logs: {logs_dir}/')
    print(f'\nFichiers à traiter:')
    
    total_size = 0
    for log_file in selected_files:
        size_kb = get_log_file_size(log_file)
        total_size += size_kb
        size_str = f'{size_kb:.2f} Ko' if size_kb < 1024 else f'{size_kb/1024:.2f} Mo'
        print(f'  - {log_file.name}: {size_str}')
    
    action = 'supprimer' if delete else 'vider'
    
    if confirm:
        print(f'\n⚠️  ATTENTION: Cette opération va {action} les fichiers de logs sélectionnés!')
        response = input('Êtes-vous sûr de vouloir continuer? (oui/non): ')
        if response.lower() not in ['oui', 'o', 'yes', 'y']:
            print('Opération annulée.')
            return
    
    print(f'\nNettoyage en cours...')
    
    success_count = 0
    for log_file in selected_files:
        if clear_log_file(log_file, delete):
            action_done = 'supprimé' if delete else 'vidé'
            print(f'  ✓ {log_file.name}: {action_done}')
            success_count += 1
    
    print(f'\n✓ Nettoyage terminé: {success_count}/{len(selected_files)} fichiers traités.')


def show_stats(logs_dir='logs'):
    """Affiche les statistiques des fichiers de logs"""
    log_files = get_all_log_files(logs_dir)
    
    if not log_files:
        print(f'Aucun fichier de log trouvé dans {logs_dir}/')
        return
    
    print(f'Répertoire des logs: {logs_dir}/')
    print(f'\nStatistiques des logs:\n')
    
    total_size = 0
    for log_file in log_files:
        size_kb = get_log_file_size(log_file)
        total_size += size_kb
        size_str = f'{size_kb:.2f} Ko' if size_kb < 1024 else f'{size_kb/1024:.2f} Mo'
        print(f'  {log_file.name:40} {size_str:>15}')
    
    total_size_str = f'{total_size:.2f} Ko' if total_size < 1024 else f'{total_size/1024:.2f} Mo'
    print(f'\n{"Total":40} {total_size_str:>15}')


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Script pour nettoyer les fichiers de logs de ProspectLab',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemples d'utilisation:
  python scripts/clear_logs.py                              # Affiche les statistiques
  python scripts/clear_logs.py --clear                      # Vide tous les logs (avec confirmation)
  python scripts/clear_logs.py --clear --no-confirm         # Vide tous les logs (sans confirmation)
  python scripts/clear_logs.py --clear --delete             # Supprime tous les logs
  python scripts/clear_logs.py --clear --files prospectlab scraping_tasks  # Vide uniquement certains logs
  python scripts/clear_logs.py --stats                      # Affiche les statistiques
        '''
    )
    
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Vider ou supprimer les fichiers de logs'
    )
    
    parser.add_argument(
        '--files',
        nargs='+',
        help='Liste des fichiers de logs spécifiques à traiter (ex: prospectlab scraping_tasks)'
    )
    
    parser.add_argument(
        '--delete',
        action='store_true',
        help='Supprimer les fichiers au lieu de les vider'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Ne pas demander de confirmation avant de traiter'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Afficher les statistiques des fichiers de logs'
    )
    
    parser.add_argument(
        '--logs-dir',
        type=str,
        default='logs',
        help='Répertoire contenant les logs (par défaut: logs/)'
    )
    
    args = parser.parse_args()
    
    # Si aucune option n'est spécifiée, afficher les stats
    if not args.clear and not args.stats:
        show_stats(logs_dir=args.logs_dir)
    elif args.stats:
        show_stats(logs_dir=args.logs_dir)
    elif args.clear:
        if args.files:
            clear_specific_logs(
                logs_dir=args.logs_dir,
                log_names=args.files,
                delete=args.delete,
                confirm=not args.no_confirm
            )
        else:
            clear_all_logs(
                logs_dir=args.logs_dir,
                delete=args.delete,
                confirm=not args.no_confirm
            )

