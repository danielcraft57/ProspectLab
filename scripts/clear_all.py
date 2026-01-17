#!/usr/bin/env python3
"""
Script pour nettoyer TOUT: base de données, Redis et logs

Ce script exécute les trois scripts de nettoyage:
- clear_db.py: Vide la base de données
- clear_redis.py: Nettoie Redis
- clear_logs.py: Vide les fichiers de logs
"""

import sys
import subprocess
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_clear_script(script_name, args=None):
    """
    Exécute un script de nettoyage
    
    Args:
        script_name: Nom du script à exécuter (ex: 'clear_db.py')
        args: Liste d'arguments supplémentaires
    
    Returns:
        bool: True si succès, False sinon
    """
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f'❌ Script {script_name} introuvable!')
        return False
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f'❌ Erreur lors de l\'exécution de {script_name}: {e}')
        return False


def clear_all(confirm=True):
    """
    Nettoie tout: base de données, Redis et logs
    
    Args:
        confirm: Demander confirmation avant de supprimer (défaut: True)
    """
    print('=' * 70)
    print('NETTOYAGE COMPLET DE PROSPECTLAB')
    print('=' * 70)
    print('\nCe script va nettoyer:')
    print('  1. Base de données (toutes les tables)')
    print('  2. Redis (queue broker et résultats)')
    print('  3. Fichiers de logs')
    
    if confirm:
        print('\n⚠️  ATTENTION: Cette opération est IRRÉVERSIBLE!')
        print('Toutes les données seront perdues.')
        response = input('\nÊtes-vous sûr de vouloir continuer? (oui/non): ')
        if response.lower() not in ['oui', 'o', 'yes', 'y']:
            print('\nOpération annulée.')
            return False
    
    success_count = 0
    total_count = 3
    
    # 1. Nettoyer la base de données
    print('\n' + '=' * 70)
    print('1/3 - NETTOYAGE DE LA BASE DE DONNÉES')
    print('=' * 70)
    args_db = ['--clear', '--no-confirm']
    if run_clear_script('clear_db.py', args_db):
        success_count += 1
    
    # 2. Nettoyer Redis
    print('\n' + '=' * 70)
    print('2/3 - NETTOYAGE DE REDIS')
    print('=' * 70)
    if run_clear_script('clear_redis.py'):
        success_count += 1
    
    # 3. Nettoyer les logs
    print('\n' + '=' * 70)
    print('3/3 - NETTOYAGE DES LOGS')
    print('=' * 70)
    args_logs = ['--clear', '--no-confirm']
    if run_clear_script('clear_logs.py', args_logs):
        success_count += 1
    
    # Résumé
    print('\n' + '=' * 70)
    print('RÉSUMÉ DU NETTOYAGE')
    print('=' * 70)
    
    if success_count == total_count:
        print(f'\n✓ Nettoyage complet terminé avec succès!')
        print(f'  {success_count}/{total_count} opérations réussies')
        print('\nProspectLab est maintenant complètement nettoyé.')
        print('Tu peux redémarrer l\'application avec des données vierges.')
        return True
    else:
        print(f'\n⚠️  Nettoyage partiellement terminé')
        print(f'  {success_count}/{total_count} opérations réussies')
        print('\nCertaines opérations ont échoué. Vérifie les messages d\'erreur ci-dessus.')
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Script pour nettoyer TOUT: base de données, Redis et logs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemples d'utilisation:
  python scripts/clear_all.py                    # Nettoie tout (avec confirmation)
  python scripts/clear_all.py --no-confirm       # Nettoie tout (sans confirmation)
        '''
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Ne pas demander de confirmation avant de supprimer'
    )
    
    args = parser.parse_args()
    
    success = clear_all(confirm=not args.no_confirm)
    sys.exit(0 if success else 1)

