"""
Script pour créer le premier utilisateur administrateur
Usage: python scripts/create_admin_user.py
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.auth import AuthManager
from services.database import Database


def main():
    """Crée le premier utilisateur administrateur"""
    print('=' * 60)
    print('Création du premier utilisateur administrateur')
    print('=' * 60)
    print()
    
    # Initialiser la base de données (créer les tables si nécessaire)
    db = Database()
    db.init_database()
    print('✓ Base de données initialisée')
    
    # Demander les informations
    username = input('Nom d\'utilisateur: ').strip()
    if not username:
        print('❌ Le nom d\'utilisateur est requis')
        return
    
    email = input('Email: ').strip()
    if not email:
        print('❌ L\'email est requis')
        return
    
    password = input('Mot de passe: ').strip()
    if not password:
        print('❌ Le mot de passe est requis')
        return
    
    if len(password) < 8:
        print('⚠️  Attention: Le mot de passe fait moins de 8 caractères')
        confirm = input('Continuer quand même ? (o/N): ').strip().lower()
        if confirm != 'o':
            print('❌ Création annulée')
            return
    
    # Créer l'utilisateur
    auth_manager = AuthManager()
    
    try:
        user_id = auth_manager.create_user(
            username=username,
            email=email,
            password=password,
            is_admin=True
        )
        
        print()
        print('=' * 60)
        print('✓ Utilisateur administrateur créé avec succès !')
        print('=' * 60)
        print(f'ID: {user_id}')
        print(f'Nom d\'utilisateur: {username}')
        print(f'Email: {email}')
        print(f'Rôle: Administrateur')
        print()
        print('Vous pouvez maintenant vous connecter avec ces identifiants.')
        print('=' * 60)
        
    except ValueError as e:
        print()
        print('❌ Erreur:', str(e))
        print()
    except Exception as e:
        print()
        print('❌ Erreur inattendue:', str(e))
        print()


if __name__ == '__main__':
    main()

