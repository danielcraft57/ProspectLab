#!/usr/bin/env python3
"""
Script pour nettoyer la base de données ProspectLab

Ce script permet de vider toutes les tables de la base de données
ou de supprimer uniquement certaines tables spécifiques.
"""

import sys
import logging
from pathlib import Path
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import Database

# Configurer le logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_env_if_present() -> None:
    """
    Charge les variables d'environnement depuis un fichier .env si présent.

    En prod, quand on lance ce script à la main (hors systemd), `DATABASE_URL`
    n'est souvent pas dans l'environnement. Sans ça, `Database()` retombe sur
    SQLite (prospectlab.db), ce qui donne l'impression que PostgreSQL n'est pas nettoyée.
    """
    project_root = Path(__file__).parent.parent
    candidates = [
        project_root / '.env',
        Path('/opt/prospectlab/.env'),
    ]

    env_path = next((p for p in candidates if p.exists()), None)
    if not env_path:
        return

    # 1) Essayer python-dotenv si dispo
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=str(env_path), override=False)
        logger.info(f'.env chargé: {env_path}')
        return
    except Exception:
        pass

    # 2) Fallback minimaliste (sans dépendance)
    try:
        for raw in env_path.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
        logger.info(f'.env chargé (fallback): {env_path}')
    except Exception as exc:
        logger.warning(f'Impossible de charger le .env ({env_path}): {exc}')


def get_all_tables(db, cursor):
    """Récupère la liste de toutes les tables de la base de données"""
    if db.is_sqlite():
        db.execute_sql(cursor, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    else:
        # PostgreSQL
        db.execute_sql(cursor, """
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """)
    # Gérer les deux formats de retour (dict pour PostgreSQL avec RealDictCursor, tuple pour SQLite)
    rows = cursor.fetchall()
    tables = []
    for row in rows:
        if isinstance(row, dict):
            # Avec RealDictCursor, la clé est le nom de colonne: tablename
            tables.append(row.get('tablename'))
        else:
            tables.append(row[0])
    return [t for t in tables if t]


def clear_table(db, cursor, table_name):
    """Vide une table spécifique"""
    try:
        if db.is_postgresql():
            # Pour PostgreSQL, utiliser TRUNCATE qui est plus rapide et réinitialise les séquences
            # Mais TRUNCATE nécessite des privilèges, donc on utilise DELETE si ça échoue
            try:
                db.execute_sql(cursor, f'TRUNCATE TABLE {table_name} CASCADE')
                # TRUNCATE ne retourne pas de rowcount, donc on retourne -1 pour indiquer "vidé"
                return -1  # -1 signifie "vidé mais nombre inconnu"
            except Exception as truncate_error:
                # Si TRUNCATE échoue (pas de privilèges), utiliser DELETE
                logger.debug(f'TRUNCATE échoué pour {table_name}, utilisation de DELETE: {truncate_error}')
                db.execute_sql(cursor, f'DELETE FROM {table_name}')
                count = cursor.rowcount
                return count
        else:
            # SQLite
            db.execute_sql(cursor, f'DELETE FROM {table_name}')
            count = cursor.rowcount
            return count
    except Exception as e:
        print(f'  Erreur lors de la suppression de {table_name}: {e}')
        logger.error(f'Erreur lors de la suppression de {table_name}: {e}', exc_info=True)
        return 0


def clear_all_tables(db_path=None, confirm=True):
    """
    Vide toutes les tables de la base de données
    
    Args:
        db_path: Chemin vers la base de données (None pour utiliser le chemin par défaut)
        confirm: Demander confirmation avant de supprimer (défaut: True)
    """
    _load_env_if_present()
    # Database() accepte db_path mais utilise DATABASE_URL si présent
    db = Database(db_path=db_path)
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Pour PostgreSQL, s'assurer que autocommit est activé si nécessaire
    if db.is_postgresql() and not getattr(conn, 'autocommit', False):
        conn.autocommit = True
    
    # Récupérer toutes les tables
    tables = get_all_tables(db, cursor)
    
    if not tables:
        print('Aucune table trouvée dans la base de données.')
        conn.close()
        return
    
    db_info = str(db.db_path) if db.is_sqlite() else 'PostgreSQL'
    print(f'Base de données: {db_info}')
    print(f'Tables trouvées: {len(tables)}')
    print('\nTables à vider:')
    for table in tables:
        db.execute_sql(cursor, f'SELECT COUNT(*) as count FROM {table}')
        result = cursor.fetchone()
        if isinstance(result, dict):
            count = result.get('count', list(result.values())[0] if result else 0)
        else:
            count = result[0] if result else 0
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
    if db.is_sqlite():
        db.execute_sql(cursor, 'PRAGMA foreign_keys = OFF')
    else:
        # PostgreSQL: désactiver les contraintes de clés étrangères temporairement
        # Note: session_replication_role nécessite des privilèges superuser
        # Alternative: utiliser TRUNCATE CASCADE qui gère automatiquement les dépendances
        try:
            db.execute_sql(cursor, 'SET session_replication_role = replica')
        except Exception as e:
            logger.warning(f'Impossible de désactiver les contraintes FK (peut nécessiter superuser): {e}')
            logger.info('Utilisation de DELETE/TRUNCATE CASCADE à la place...')
    
    total_deleted = 0
    for table in tables:
        deleted = clear_table(db, cursor, table)
        if deleted == -1:
            # TRUNCATE utilisé (PostgreSQL)
            print(f'  ✓ {table}: table vidée (TRUNCATE)')
            total_deleted += 1  # On compte 1 pour indiquer qu'elle a été vidée
        elif deleted > 0:
            print(f'  ✓ {table}: {deleted} enregistrements supprimés')
            total_deleted += deleted
        else:
            print(f'  ✓ {table}: déjà vide ou erreur')
    
    # Réactiver les foreign keys
    if db.is_sqlite():
        db.execute_sql(cursor, 'PRAGMA foreign_keys = ON')
    else:
        try:
            db.execute_sql(cursor, 'SET session_replication_role = DEFAULT')
        except Exception as e:
            # Si on n'a pas les droits superuser, on a déjà nettoyé via TRUNCATE/DELETE,
            # donc on peut continuer sans bloquer le script.
            logger.warning(f'Impossible de rétablir session_replication_role (droits insuffisants): {e}')
    
    # Valider les changements
    conn.commit()
    
    print(f'\n✓ Nettoyage terminé: {total_deleted} enregistrements supprimés au total.')
    
    # Réinitialiser les séquences AUTOINCREMENT/SERIAL
    print('\nRéinitialisation des séquences...')
    for table in tables:
        try:
            if db.is_sqlite():
                db.execute_sql(cursor, 'DELETE FROM sqlite_sequence WHERE name = ?', (table,))
            else:
                # PostgreSQL: réinitialiser les séquences SERIAL
                # Chercher toutes les colonnes de type SERIAL/BIGSERIAL dans la table
                db.execute_sql(cursor, """
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = %s 
                    AND column_default LIKE 'nextval%'
                """, (table,))
                sequences = cursor.fetchall()
                for seq_info in sequences:
                    column_name = seq_info['column_name'] if isinstance(seq_info, dict) else seq_info[0]
                    # Récupérer le nom de la séquence
                    db.execute_sql(cursor, """
                        SELECT pg_get_serial_sequence(%s, %s)
                    """, (table, column_name))
                    seq_result = cursor.fetchone()
                    if seq_result:
                        if isinstance(seq_result, dict):
                            # Le nom de la colonne dépend du driver, on prend la première valeur.
                            seq_name = next(iter(seq_result.values()))
                        else:
                            seq_name = seq_result[0]
                        if seq_name:
                            # Réinitialiser la séquence à 1
                            db.execute_sql(cursor, f"SELECT setval('{seq_name}', 1, false)")
        except Exception as e:
            # Certaines tables n'ont pas de séquence ou d'autres erreurs
            logger.debug(f'Pas de séquence pour {table} ou erreur: {e}')
            pass
    
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
    
    _load_env_if_present()
    # Database() accepte db_path mais utilise DATABASE_URL si présent
    db = Database(db_path=db_path)
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Pour PostgreSQL, s'assurer que autocommit est activé si nécessaire
    if db.is_postgresql() and not getattr(conn, 'autocommit', False):
        conn.autocommit = True
    
    # Vérifier que les tables existent
    all_tables = get_all_tables(db, cursor)
    invalid_tables = [t for t in table_names if t not in all_tables]
    
    if invalid_tables:
        print(f'⚠️  Tables introuvables: {", ".join(invalid_tables)}')
        table_names = [t for t in table_names if t in all_tables]
    
    if not table_names:
        print('Aucune table valide à vider.')
        conn.close()
        return
    
    db_info = str(db.db_path) if db.is_sqlite() else 'PostgreSQL'
    print(f'Base de données: {db_info}')
    print(f'\nTables à vider:')
    for table in table_names:
        db.execute_sql(cursor, f'SELECT COUNT(*) as count FROM {table}')
        result = cursor.fetchone()
        if isinstance(result, dict):
            count = result.get('count', list(result.values())[0] if result else 0)
        else:
            count = result[0] if result else 0
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
    if db.is_sqlite():
        db.execute_sql(cursor, 'PRAGMA foreign_keys = OFF')
    else:
        db.execute_sql(cursor, 'SET session_replication_role = replica')
    
    total_deleted = 0
    for table in table_names:
        deleted = clear_table(db, cursor, table)
        if deleted == -1:
            # TRUNCATE utilisé (PostgreSQL)
            print(f'  ✓ {table}: table vidée (TRUNCATE)')
            total_deleted += 1  # On compte 1 pour indiquer qu'elle a été vidée
        elif deleted > 0:
            print(f'  ✓ {table}: {deleted} enregistrements supprimés')
            total_deleted += deleted
        else:
            print(f'  ✓ {table}: déjà vide ou erreur')
    
    # Réactiver les foreign keys
    if db.is_sqlite():
        db.execute_sql(cursor, 'PRAGMA foreign_keys = ON')
    else:
        db.execute_sql(cursor, 'SET session_replication_role = DEFAULT')
    
    # Valider les changements
    conn.commit()
    conn.close()
    
    print(f'\n✓ Nettoyage terminé: {total_deleted} enregistrements supprimés au total.')


def show_stats(db_path=None):
    """Affiche les statistiques de la base de données"""
    _load_env_if_present()
    # Database() accepte db_path mais utilise DATABASE_URL si présent
    db = Database(db_path=db_path)
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Pour PostgreSQL, s'assurer que autocommit est activé si nécessaire
    if db.is_postgresql() and not getattr(conn, 'autocommit', False):
        conn.autocommit = True
    
    tables = get_all_tables(db, cursor)
    
    if not tables:
        print('Aucune table trouvée dans la base de données.')
        conn.close()
        return
    
    db_info = str(db.db_path) if db.is_sqlite() else 'PostgreSQL'
    print(f'Base de données: {db_info}')
    print(f'\nStatistiques des tables:\n')
    
    total_records = 0
    for table in sorted(tables):
        db.execute_sql(cursor, f'SELECT COUNT(*) as count FROM {table}')
        result = cursor.fetchone()
        if isinstance(result, dict):
            count = result.get('count', list(result.values())[0] if result else 0)
        else:
            count = result[0] if result else 0
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

