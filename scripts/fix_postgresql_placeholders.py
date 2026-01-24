#!/usr/bin/env python3
"""
Script pour remplacer tous les cursor.execute() avec placeholders ? 
par self.execute_sql() pour compatibilité PostgreSQL
"""

import re
import os
from pathlib import Path

def fix_file(filepath):
    """Remplace cursor.execute( par self.execute_sql(cursor, dans un fichier"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes = 0
    
    # Pattern 1: cursor.execute('...', (params))
    # Pattern 2: cursor.execute('''...''', (params))
    # Pattern 3: cursor.execute("...", (params))
    
    # Remplacer cursor.execute( par self.execute_sql(cursor,
    # Mais seulement si la ligne contient un ?
    lines = content.split('\n')
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        original_line = line
        
        # Si la ligne contient cursor.execute( et un ?
        if 'cursor.execute(' in line and '?' in line:
            # Remplacer cursor.execute( par self.execute_sql(cursor,
            line = line.replace('cursor.execute(', 'self.execute_sql(cursor,')
            if line != original_line:
                changes += 1
        
        # Gérer les cas multi-lignes avec '''
        if 'cursor.execute(' in line and "'''" in line:
            # Chercher la fin de la requête sur plusieurs lignes
            j = i
            quote_count = line.count("'''")
            while quote_count % 2 == 1 and j < len(lines) - 1:
                j += 1
                quote_count += lines[j].count("'''")
            
            # Si on trouve un ? dans cette plage, remplacer
            block = '\n'.join(lines[i:j+1])
            if '?' in block and 'cursor.execute(' in block:
                block = block.replace('cursor.execute(', 'self.execute_sql(cursor,')
                if block != '\n'.join(lines[i:j+1]):
                    changes += 1
                    new_lines.extend(block.split('\n'))
                    i = j + 1
                    continue
        
        new_lines.append(line)
        i += 1
    
    new_content = '\n'.join(new_lines)
    
    if new_content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'✓ {filepath}: {changes} remplacements')
        return changes
    return 0

def main():
    """Parcourt tous les fichiers Python dans services/database/"""
    db_dir = Path('services/database')
    total_changes = 0
    
    for filepath in db_dir.glob('*.py'):
        if filepath.name == '__init__.py' or filepath.name == 'base.py':
            continue  # Ne pas modifier ces fichiers
        
        changes = fix_file(filepath)
        total_changes += changes
    
    print(f'\nTotal: {total_changes} remplacements effectués')

if __name__ == '__main__':
    main()



