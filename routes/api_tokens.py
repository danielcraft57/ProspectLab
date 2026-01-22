"""
Blueprint pour la gestion des tokens API (admin)
Permet de créer, lister et révoquer les tokens API
"""

from flask import Blueprint, request, jsonify
from services.api_auth import APITokenManager
from services.auth import login_required, admin_required

api_tokens_bp = Blueprint('api_tokens', __name__, url_prefix='/api/tokens')


@api_tokens_bp.route('', methods=['GET'])
@login_required
@admin_required
def list_tokens():
    """
    Liste tous les tokens API (admin uniquement).
    
    Returns:
        JSON: Liste des tokens API
    """
    try:
        token_manager = APITokenManager()
        user_id = request.args.get('user_id', type=int)
        tokens = token_manager.list_tokens(user_id=user_id)
        
        return jsonify({
            'success': True,
            'count': len(tokens),
            'data': tokens
        })
    except Exception as e:
        import traceback
        print(f"Erreur dans list_tokens: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_tokens_bp.route('', methods=['POST'])
@login_required
@admin_required
def create_token():
    """
    Crée un nouveau token API (admin uniquement).
    
    Body (JSON):
        name (str): Nom/description du token (requis)
        app_url (str): URL de l'application (optionnel)
        user_id (int): ID de l'utilisateur propriétaire (optionnel)
        can_read_entreprises (bool): Permission de lire les entreprises (défaut: true)
        can_read_emails (bool): Permission de lire les emails (défaut: true)
        can_read_statistics (bool): Permission de lire les statistiques (défaut: true)
        
    Returns:
        JSON: Token créé avec son token complet (à sauvegarder immédiatement)
    """
    try:
        from flask import session
        import traceback
        
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type doit être application/json'
            }), 400
        
        data = request.get_json() or {}
        name = data.get('name')
        
        # Générer automatiquement le nom si non fourni
        if not name:
            from datetime import datetime
            app_url = data.get('app_url', '')
            now = datetime.now()
            date_str = now.strftime('%d.%m.%Y %H:%M')
            
            if app_url:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(app_url)
                    domain = parsed.netloc.replace('www.', '')
                    name = f'{domain} - {date_str}'
                except Exception as e:
                    print(f"Erreur parsing URL: {e}")
                    name = f'Token - {date_str}'
            else:
                name = f'Token - {date_str}'
        
        app_url = data.get('app_url') or None
        user_id = data.get('user_id')
        if not user_id:
            try:
                user_id = session.get('user_id')
            except:
                user_id = None
        
        can_read_entreprises = data.get('can_read_entreprises', True)
        can_read_emails = data.get('can_read_emails', True)
        can_read_statistics = data.get('can_read_statistics', True)
        can_read_campagnes = data.get('can_read_campagnes', True)
        
        token_manager = APITokenManager()
        token_data = token_manager.create_token(
            name=name,
            app_url=app_url,
            user_id=user_id,
            can_read_entreprises=can_read_entreprises,
            can_read_emails=can_read_emails,
            can_read_statistics=can_read_statistics,
            can_read_campagnes=can_read_campagnes
        )
        
        return jsonify({
            'success': True,
            'message': 'Token créé avec succès. Sauvegardez-le immédiatement, il ne sera plus affiché.',
            'data': token_data
        }), 201
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Erreur dans create_token: {str(e)}")
        print(error_trace)
        return jsonify({
            'success': False,
            'error': str(e),
            'trace': error_trace if app.debug else None
        }), 500


@api_tokens_bp.route('/<int:token_id>', methods=['DELETE'])
@login_required
@admin_required
def revoke_token(token_id):
    """
    Révoque un token API (admin uniquement).
    
    Args:
        token_id (int): ID du token à révoquer
        
    Returns:
        JSON: Confirmation de révocation
    """
    try:
        token_manager = APITokenManager()
        revoked = token_manager.revoke_token(token_id)
        
        if revoked:
            return jsonify({
                'success': True,
                'message': 'Token révoqué avec succès'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Token introuvable'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_tokens_bp.route('/<int:token_id>/delete', methods=['DELETE'])
@login_required
@admin_required
def delete_token(token_id):
    """
    Supprime définitivement un token API (admin uniquement).
    
    Args:
        token_id (int): ID du token à supprimer
        
    Returns:
        JSON: Confirmation de suppression
    """
    try:
        token_manager = APITokenManager()
        deleted = token_manager.delete_token(token_id)
        
        if deleted:
            return jsonify({
                'success': True,
                'message': 'Token supprimé définitivement'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Token introuvable'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

