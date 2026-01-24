#!/usr/bin/env python3
"""
Script pour remplacer tous les cursor.execute() avec placeholders ? 
par self.execute_sql(cursor, pour compatibilité PostgreSQL
"""

import re
import os
from pathlib import Path

def fix_file(filepath):
    """Remplace cursor.execute( par self.execute_sql(cursor, dans un fichier"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Remplacer toutes les occurrences de cursor.execute( par self.execute_sql(cursor,
    # La méthode execute_sql gère automatiquement la conversion des placeholders
    content = content.replace('cursor.execute(', 'self.execute_sql(cursor,')
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        changes = content.count('self.execute_sql(cursor,') - original_content.count('self.execute_sql(cursor,')
        print(f'✓ {filepath}: {changes} remplacements')
        return changes
    return 0

def main():
    """Parcourt tous les fichiers Python dans services/database/"""
    files_to_fix = [
        'services/database/entreprises.py',
        'services/database/campagnes.py',
        'services/database/scrapers.py',
        'services/database/personnes.py',
        'services/database/technical.py',
        'services/database/pentest.py',
        'services/database/osint.py',
        'services/database/analyses.py',
    ]
    
    total_changes = 0
    for filepath in files_to_fix:
        if os.path.exists(filepath):
            changes = fix_file(filepath)
            total_changes += changes
        else:
            print(f'✗ {filepath} (non trouvé)')
    
    print(f'\nTotal: {total_changes} remplacements effectués')

if __name__ == '__main__':
    main()



