"""
Service d'analyse et d'enrichissement des emails
Validation, vérification MX, détection du type, OSINT

Ce module fournit une classe EmailAnalyzer qui permet d'analyser en profondeur
les adresses email trouvées lors du scraping. Il extrait des informations
techniques (validation format, MX records) et personnelles (nom, type, fournisseur)
pour enrichir les données collectées.
"""

import re
import socket
try:
    import dns.resolver
except ImportError:
    dns = None
import requests
from urllib.parse import urlparse
import time
from datetime import datetime


class EmailAnalyzer:
    """
    Analyseur d'emails pour extraire des informations techniques et personnelles.
    
    Cette classe permet de :
    - Valider le format des emails
    - Détecter le fournisseur d'email (Gmail, Outlook, etc.)
    - Déterminer le type d'email (personnel, professionnel, générique)
    - Extraire le nom/prénom depuis la partie locale de l'email
    - Vérifier les enregistrements MX pour valider le domaine
    - Calculer un score de risque basé sur plusieurs critères
    """
    
    def __init__(self):
        """
        Initialise l'analyseur avec la liste des fournisseurs d'email connus.
        
        Les fournisseurs sont organisés par nom avec leurs domaines associés.
        Cela permet de détecter rapidement le type de service utilisé.
        """
        # Dictionnaire des fournisseurs d'email majeurs avec leurs domaines
        # Clé : nom du fournisseur, Valeur : liste des domaines associés
        self.email_providers = {
            'Gmail': ['gmail.com', 'googlemail.com'],
            'Outlook': ['outlook.com', 'hotmail.com', 'live.com', 'msn.com'],
            'Yahoo': ['yahoo.com', 'yahoo.fr', 'ymail.com'],
            'ProtonMail': ['protonmail.com', 'proton.me'],
            'Orange': ['orange.fr'],
            'Free': ['free.fr'],
            'SFR': ['sfr.fr'],
            'Bouygues': ['bbox.fr'],
            'Laposte': ['laposte.net'],
            'AOL': ['aol.com'],
            'iCloud': ['icloud.com', 'me.com', 'mac.com'],
            'Zoho': ['zoho.com'],
            'Mail.com': ['mail.com']
        }
    
    def extract_name_from_email(self, email):
        """
        Extrait un nom/prénom potentiel depuis la partie locale de l'email.
        
        Analyse la partie avant le @ pour tenter d'extraire un nom et un prénom.
        Supporte plusieurs formats courants : prenom.nom, prenom_nom, prenom-nom.
        
        Args:
            email (str): L'adresse email à analyser
            
        Returns:
            dict or None: Dictionnaire contenant :
                - first_name (str): Prénom détecté (peut être None)
                - last_name (str): Nom détecté
                - full_name (str): Nom complet reconstitué
            Retourne None si aucun nom ne peut être extrait
            
        Example:
            >>> analyzer = EmailAnalyzer()
            >>> analyzer.extract_name_from_email('jean.dupont@example.com')
            {'first_name': 'Jean', 'last_name': 'Dupont', 'full_name': 'Jean Dupont'}
        """
        # Vérification de base : l'email doit contenir un @
        if not email or '@' not in email:
            return None
        
        # Extraire la partie locale (avant le @)
        local_part = email.split('@')[0]
        
        # Patterns courants pour séparer prénom et nom
        # Format : prenom.nom, prenom_nom, prenom-nom
        if '.' in local_part:
            parts = local_part.split('.')
            if len(parts) >= 2:
                return {
                    'first_name': parts[0].capitalize(),
                    'last_name': parts[-1].capitalize(),
                    'full_name': ' '.join([p.capitalize() for p in parts])
                }
        
        if '_' in local_part:
            parts = local_part.split('_')
            if len(parts) >= 2:
                return {
                    'first_name': parts[0].capitalize(),
                    'last_name': parts[-1].capitalize(),
                    'full_name': ' '.join([p.capitalize() for p in parts])
                }
        
        if '-' in local_part:
            parts = local_part.split('-')
            if len(parts) >= 2:
                return {
                    'first_name': parts[0].capitalize(),
                    'last_name': parts[-1].capitalize(),
                    'full_name': ' '.join([p.capitalize() for p in parts])
                }
        
        # Si c'est juste un nom
        if len(local_part) > 2:
            return {
                'first_name': None,
                'last_name': local_part.capitalize(),
                'full_name': local_part.capitalize()
            }
        
        return None
    
    def detect_email_provider(self, email):
        """
        Détecte le fournisseur d'email à partir du domaine.
        
        Compare le domaine de l'email avec la liste des fournisseurs connus.
        Si le domaine n'est pas reconnu mais contient un point, il est considéré
        comme un domaine personnalisé (entreprise).
        
        Args:
            email (str): L'adresse email à analyser
            
        Returns:
            str or None: Le nom du fournisseur détecté :
                - Nom d'un fournisseur connu (Gmail, Outlook, etc.)
                - 'Personnalisé' pour les domaines d'entreprise
                - 'Inconnu' si le domaine n'est pas reconnu
                - None si l'email est invalide
                
        Example:
            >>> analyzer = EmailAnalyzer()
            >>> analyzer.detect_email_provider('user@gmail.com')
            'Gmail'
            >>> analyzer.detect_email_provider('contact@example.com')
            'Personnalisé'
        """
        # Vérification de base
        if not email or '@' not in email:
            return None
        
        # Extraire et normaliser le domaine (minuscules)
        domain = email.split('@')[1].lower()
        
        # Parcourir les fournisseurs connus pour trouver une correspondance
        for provider, domains in self.email_providers.items():
            if domain in domains:
                return provider
        
        # Si le domaine contient un point mais n'est pas dans la liste,
        # c'est probablement un domaine personnalisé (entreprise)
        if '.' in domain:
            return 'Personnalisé'
        
        # Domaine non reconnu
        return 'Inconnu'
    
    def detect_email_type(self, email):
        """
        Détermine le type d'email : personnel, professionnel ou générique.
        
        Analyse la partie locale et le domaine pour classifier l'email :
        - Générique : contient des mots-clés comme 'contact', 'info', 'support'
        - Professionnel : domaine personnalisé (pas un fournisseur grand public)
        - Personnel : domaine d'un fournisseur grand public (Gmail, Outlook, etc.)
        
        Args:
            email (str): L'adresse email à analyser
            
        Returns:
            str: Le type d'email détecté :
                - 'Générique' : emails de contact/service
                - 'Professionnel' : domaine d'entreprise
                - 'Personnel' : fournisseur grand public
                - 'Inconnu' : impossible à déterminer
                
        Example:
            >>> analyzer = EmailAnalyzer()
            >>> analyzer.detect_email_type('contact@example.com')
            'Générique'
            >>> analyzer.detect_email_type('jean.dupont@company.fr')
            'Professionnel'
        """
        # Vérification de base
        if not email or '@' not in email:
            return 'Inconnu'
        
        # Extraire la partie locale et le domaine
        local_part = email.split('@')[0].lower()
        domain = email.split('@')[1].lower()
        
        # Liste des patterns indiquant un email générique (non personnel)
        # Ces emails sont généralement utilisés pour le support, contact, etc.
        generic_patterns = [
            'contact', 'info', 'hello', 'bonjour', 'salut',
            'support', 'help', 'assistance', 'service',
            'noreply', 'no-reply', 'donotreply',
            'admin', 'administrator', 'webmaster',
            'postmaster', 'abuse', 'security'
        ]
        
        if any(pattern in local_part for pattern in generic_patterns):
            return 'Générique'
        
        # Emails professionnels (domaines personnalisés)
        if domain not in [d for domains in self.email_providers.values() for d in domains]:
            return 'Professionnel'
        
        # Sinon, probablement personnel
        return 'Personnel'
    
    def validate_email_format(self, email):
        """
        Valide le format de l'adresse email selon les standards RFC.
        
        Vérifie que l'email respecte le format standard :
        - Partie locale : caractères alphanumériques, points, tirets, underscores, +
        - @ obligatoire
        - Domaine : caractères alphanumériques, points, tirets
        - Extension : au moins 2 caractères alphabétiques
        
        Args:
            email (str): L'adresse email à valider
            
        Returns:
            bool: True si le format est valide, False sinon
            
        Example:
            >>> analyzer = EmailAnalyzer()
            >>> analyzer.validate_email_format('user@example.com')
            True
            >>> analyzer.validate_email_format('invalid-email')
            False
        """
        # Email vide = invalide
        if not email:
            return False
        
        # Pattern regex pour valider le format email standard
        # Format : local@domain.extension
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def check_mx_record(self, domain):
        """
        Vérifie si le domaine possède des enregistrements MX valides.
        
        Les enregistrements MX (Mail Exchange) indiquent quels serveurs
        acceptent les emails pour ce domaine. Un domaine sans MX ne peut
        pas recevoir d'emails, ce qui indique un email invalide ou un domaine
        non configuré.
        
        Args:
            domain (str): Le domaine à vérifier (sans le @)
            
        Returns:
            dict: Dictionnaire contenant :
                - valid (bool or None): True si MX valides, False si invalides,
                  None si dnspython n'est pas installé
                - mx_records (list): Liste des enregistrements MX triés par priorité
                  (seulement si valid=True)
                - error (str): Message d'erreur (seulement si valid=False)
                
        Note:
            Nécessite le module dnspython pour fonctionner.
            Si non installé, retourne valid=None avec un message d'erreur.
            
        Example:
            >>> analyzer = EmailAnalyzer()
            >>> analyzer.check_mx_record('example.com')
            {'valid': True, 'mx_records': [{'priority': 10, 'exchange': 'mail.example.com'}]}
        """
        # Vérifier si dnspython est disponible
        if not dns:
            return {'valid': None, 'error': 'dnspython non installé'}
        
        try:
            # Résoudre les enregistrements MX du domaine
            answers = dns.resolver.resolve(domain, 'MX')
            mx_records = []
            
            # Extraire les informations de chaque enregistrement MX
            for rdata in answers:
                mx_records.append({
                    'priority': rdata.preference,  # Priorité (plus bas = prioritaire)
                    'exchange': str(rdata.exchange)  # Serveur mail
                })
            
            # Retourner les enregistrements triés par priorité
            return {
                'valid': True,
                'mx_records': sorted(mx_records, key=lambda x: x['priority'])
            }
        except dns.resolver.NXDOMAIN:
            # Le domaine n'existe pas
            return {'valid': False, 'error': 'Domaine inexistant'}
        except dns.resolver.NoAnswer:
            # Le domaine existe mais n'a pas d'enregistrement MX
            return {'valid': False, 'error': 'Pas d\'enregistrement MX'}
        except Exception as e:
            # Autre erreur (timeout, réseau, etc.)
            return {'valid': False, 'error': str(e)[:50]}
    
    def analyze_email(self, email, source_url=None):
        """
        Effectue une analyse complète d'une adresse email.
        
        Cette méthode centralise toutes les analyses disponibles :
        - Validation du format
        - Détection du fournisseur
        - Classification du type
        - Extraction du nom/prénom
        - Vérification MX (pour domaines personnalisés)
        - Calcul du score de risque
        
        Args:
            email (str): L'adresse email à analyser
            source_url (str, optional): URL où l'email a été trouvé
            
        Returns:
            dict or None: Dictionnaire contenant toutes les informations analysées :
                - email (str): L'adresse email originale
                - source_url (str): URL source (si fournie)
                - analyzed_at (str): Date/heure de l'analyse (ISO format)
                - format_valid (bool): True si le format est valide
                - provider (str): Fournisseur détecté
                - type (str): Type d'email (Personnel/Professionnel/Générique)
                - domain (str): Domaine extrait
                - mx_valid (bool or None): Validité des enregistrements MX
                - mx_records (list): Liste des enregistrements MX (si disponibles)
                - name_info (dict): Informations sur le nom extrait
                - risk_score (int): Score de risque (0-100)
            Retourne None si l'email est vide
            
        Example:
            >>> analyzer = EmailAnalyzer()
            >>> result = analyzer.analyze_email('jean.dupont@example.com', 'https://example.com/contact')
            >>> result['type']
            'Professionnel'
            >>> result['name_info']['full_name']
            'Jean Dupont'
        """
        # Vérification de base
        if not email:
            return None
        
        # Initialiser le dictionnaire de résultats avec les valeurs par défaut
        analysis = {
            'email': email,
            'source_url': source_url,
            'analyzed_at': datetime.now().isoformat(),  # Timestamp de l'analyse
            'format_valid': self.validate_email_format(email),
            'provider': None,
            'type': None,
            'domain': None,
            'mx_valid': None,
            'name_info': None,
            'risk_score': 0
        }
        
        # Si l'email ne contient pas de @, retourner l'analyse basique
        if '@' not in email:
            return analysis
        
        # Extraire le domaine
        domain = email.split('@')[1]
        analysis['domain'] = domain
        
        # Détecter le fournisseur d'email
        analysis['provider'] = self.detect_email_provider(email)
        
        # Classifier le type d'email
        analysis['type'] = self.detect_email_type(email)
        
        # Tenter d'extraire le nom/prénom
        analysis['name_info'] = self.extract_name_from_email(email)
        
        # Vérifier les enregistrements MX uniquement pour les domaines personnalisés
        # (les fournisseurs connus ont toujours des MX valides)
        if analysis['provider'] == 'Personnalisé':
            mx_check = self.check_mx_record(domain)
            analysis['mx_valid'] = mx_check.get('valid', False)
            analysis['mx_records'] = mx_check.get('mx_records', [])
        else:
            # Pour les providers connus (Gmail, Outlook, etc.), on assume que MX est valide
            analysis['mx_valid'] = True
        
        # Calculer un score de risque basé sur plusieurs critères
        # Score max = 100, chaque critère ajoute des points
        risk_score = 0
        
        # Email générique = risque plus élevé (peut être du spam ou non personnel)
        if analysis['type'] == 'Générique':
            risk_score += 30
        
        # Format invalide = email probablement incorrect
        if not analysis['format_valid']:
            risk_score += 50
        
        # MX invalide = domaine ne peut pas recevoir d'emails
        if analysis['mx_valid'] is False:
            risk_score += 40
        
        # Provider inconnu = domaine suspect
        if analysis['provider'] == 'Inconnu':
            risk_score += 10
        
        # Limiter le score à 100 maximum
        analysis['risk_score'] = min(risk_score, 100)
        
        return analysis
    
    def analyze_emails_batch(self, emails, source_url=None):
        """
        Analyse une liste d'emails en lot.
        
        Parcourt une liste d'emails et applique l'analyse complète à chacun.
        Inclut une petite pause entre chaque analyse pour éviter de surcharger
        les serveurs DNS ou les ressources système.
        
        Args:
            emails (list): Liste des adresses email à analyser
            source_url (str, optional): URL source commune pour tous les emails
            
        Returns:
            list: Liste des dictionnaires d'analyse pour chaque email valide
            
        Note:
            Les erreurs individuelles sont ignorées pour ne pas interrompre
            le traitement de la liste complète.
            
        Example:
            >>> analyzer = EmailAnalyzer()
            >>> emails = ['user1@example.com', 'user2@example.com']
            >>> results = analyzer.analyze_emails_batch(emails, 'https://example.com')
            >>> len(results)
            2
        """
        results = []
        
        # Parcourir chaque email de la liste
        for email in emails:
            try:
                # Analyser l'email
                analysis = self.analyze_email(email, source_url)
                
                # Ajouter le résultat si l'analyse a réussi
                if analysis:
                    results.append(analysis)
                
                # Petite pause pour éviter de surcharger les serveurs DNS
                # et respecter les limites de taux
                time.sleep(0.1)
            except Exception as e:
                # En cas d'erreur, continuer avec l'email suivant
                # pour ne pas interrompre le traitement de la liste
                pass
        
        return results

