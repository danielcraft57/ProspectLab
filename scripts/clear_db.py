#!/usr/bin/env python3
"""
Script pour nettoyer la base de données ProspectLab

Ce script permet de vider toutes les tables de la base de données
ou de supprimer uniquement certaines tables spécifiques.
"""

import sqlite3
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import Database


def get_all_tables(cursor):
    """Récupère la liste de toutes les tables de la base de données"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [row[0] for row in cursor.fetchall()]


def clear_table(cursor, table_name):
    """Vide une table spécifique"""
    try:
        cursor.execute(f'DELETE FROM {table_name}')
        count = cursor.rowcount
        return count
    except sqlite3.OperationalError as e:
        print(f'  Erreur lors de la suppression de {table_name}: {e}')
        return 0


def clear_all_tables(db_path=None, confirm=True):
    """
    Vide toutes les tables de la base de données
    
    Args:
        db_path: Chemin vers la base de données (None pour utiliser le chemin par défaut)
        confirm: Demander confirmation avant de supprimer (défaut: True)
    """
    db = Database(db_path=db_path)
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Récupérer toutes les tables
    tables = get_all_tables(cursor)
    
    if not tables:
        print('Aucune table trouvée dans la base de données.')
        conn.close()
        return
    
    print(f'Base de données: {db.db_path}')
    print(f'Tables trouvées: {len(tables)}')
    print('\nTables à vider:')
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'  - {table}: {count} enregistrements')
    
    if confirm:
        print('\n⚠️  ATTENTION: Cette opération va supprimer TOUTES les données de la base de données!')
        response = input('Êtes-vous sûr de vouloir continuer? (oui/non): ')
        if response.lower() not in ['oui', 'o', 'yes', 'y']:
            print('Opération annulée.')
            conn.close()
            return
    
    print('\nNettoyage en cours...')
    
    # Désactiver temporairement les foreign keys pour éviter les problèmes de contraintes
    cursor.execute('PRAGMA foreign_keys = OFF')
    
    total_deleted = 0
    for table in tables:
        deleted = clear_table(cursor, table)
        total_deleted += deleted
        if deleted > 0:
            print(f'  ✓ {table}: {deleted} enregistrements supprimés')
    
    # Réactiver les foreign keys
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # Valider les changements
    conn.commit()
    
    print(f'\n✓ Nettoyage terminé: {total_deleted} enregistrements supprimés au total.')
    
    # Réinitialiser les séquences AUTOINCREMENT
    print('\nRéinitialisation des séquences AUTOINCREMENT...')
    for table in tables:
        try:
            cursor.execute(f'DELETE FROM sqlite_sequence WHERE name = ?', (table,))
        except sqlite3.OperationalError:
            pass  # Certaines tables n'ont pas de séquence
    
    conn.commit()
    conn.close()
    print('✓ Base de données nettoyée avec succès!')


def clear_specific_tables(db_path=None, table_names=None, confirm=True):
    """
    Vide uniquement certaines tables spécifiques
    
    Args:
        db_path: Chemin vers la base de données (None pour utiliser le chemin par défaut)
        table_names: Liste des noms de tables à vider
        confirm: Demander confirmation avant de supprimer (défaut: True)
    """
    if not table_names:
        print('Aucune table spécifiée.')
        return
    
    db = Database(db_path=db_path)
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Vérifier que les tables existent
    all_tables = get_all_tables(cursor)
    invalid_tables = [t for t in table_names if t not in all_tables]
    
    if invalid_tables:
        print(f'⚠️  Tables introuvables: {", ".join(invalid_tables)}')
        table_names = [t for t in table_names if t in all_tables]
    
    if not table_names:
        print('Aucune table valide à vider.')
        conn.close()
        return
    
    print(f'Base de données: {db.db_path}')
    print(f'\nTables à vider:')
    for table in table_names:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'  - {table}: {count} enregistrements')
    
    if confirm:
        print('\n⚠️  ATTENTION: Cette opération va supprimer les données des tables sélectionnées!')
        response = input('Êtes-vous sûr de vouloir continuer? (oui/non): ')
        if response.lower() not in ['oui', 'o', 'yes', 'y']:
            print('Opération annulée.')
            conn.close()
            return
    
    print('\nNettoyage en cours...')
    
    # Désactiver temporairement les foreign keys
    cursor.execute('PRAGMA foreign_keys = OFF')
    
    total_deleted = 0
    for table in table_names:
        deleted = clear_table(cursor, table)
        total_deleted += deleted
        if deleted > 0:
            print(f'  ✓ {table}: {deleted} enregistrements supprimés')
    
    # Réactiver les foreign keys
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # Valider les changements
    conn.commit()
    conn.close()
    
    print(f'\n✓ Nettoyage terminé: {total_deleted} enregistrements supprimés au total.')


def show_stats(db_path=None):
    """Affiche les statistiques de la base de données"""
    db = Database(db_path=db_path)
    conn = db.get_connection()
    cursor = conn.cursor()
    
    tables = get_all_tables(cursor)
    
    if not tables:
        print('Aucune table trouvée dans la base de données.')
        conn.close()
        return
    
    print(f'Base de données: {db.db_path}')
    print(f'\nStatistiques des tables:\n')
    
    total_records = 0
    for table in sorted(tables):
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        total_records += count
        print(f'  {table:40} {count:>10} enregistrements')
    
    print(f'\n{"Total":40} {total_records:>10} enregistrements')
    
    conn.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Script pour nettoyer la base de données ProspectLab',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemples d'utilisation:
  python scripts/clear_db.py                    # Affiche les statistiques
  python scripts/clear_db.py --clear            # Vide toutes les tables (avec confirmation)
  python scripts/clear_db.py --clear --no-confirm  # Vide toutes les tables (sans confirmation)
  python scripts/clear_db.py --clear --tables entreprises analyses  # Vide uniquement certaines tables
  python scripts/clear_db.py --stats            # Affiche les statistiques
        '''
    )
    
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Vider les tables de la base de données'
    )
    
    parser.add_argument(
        '--tables',
        nargs='+',
        help='Liste des tables spécifiques à vider (ex: entreprises analyses)'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Ne pas demander de confirmation avant de supprimer'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Afficher les statistiques de la base de données'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        help='Chemin vers la base de données (par défaut: prospectlab.db)'
    )
    
    args = parser.parse_args()
    
    # Si aucune option n'est spécifiée, afficher les stats
    if not args.clear and not args.stats:
        show_stats(db_path=args.db_path)
    elif args.stats:
        show_stats(db_path=args.db_path)
    elif args.clear:
        if args.tables:
            clear_specific_tables(
                db_path=args.db_path,
                table_names=args.tables,
                confirm=not args.no_confirm
            )
        else:
            clear_all_tables(
                db_path=args.db_path,
                confirm=not args.no_confirm
            )

