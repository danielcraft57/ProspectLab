"""
Module de validation des noms et prénoms humains.
Filtre les noms invalides (lieux, entreprises, tech, UI, etc.).

Dépendances optionnelles (pour une meilleure détection) :
- probablepeople : détection Person vs Corporation
- nameparser : parsing prénom / nom
- gender-guesser : exige que le prénom soit un prénom connu (rejette "React", "Choisir", etc.)
  Installer avec : pip install gender-guesser
"""

import re
from typing import Optional, Tuple

# Essayer d'importer les bibliothèques optionnelles
try:
    import probablepeople
    PROBABLEPEOPLE_AVAILABLE = True
except ImportError:
    PROBABLEPEOPLE_AVAILABLE = False

try:
    from nameparser import HumanName
    NAMEPARSER_AVAILABLE = True
except ImportError:
    NAMEPARSER_AVAILABLE = False


# Mots-clés à exclure (lieux, entreprises, fonctions, tech, UI, etc.)
EXCLUDED_KEYWORDS = {
    # Lieux géographiques
    'nord', 'sud', 'est', 'ouest', 'centre', 'lorraine', 'metz', 'longwy', 'thionville',
    'nancy', 'strasbourg', 'paris', 'lyon', 'marseille', 'toulouse', 'nice', 'nantes',
    'bordeaux', 'lille', 'rennes', 'reims', 'saint', 'sainte', 'ville', 'rue', 'avenue',
    'boulevard', 'place', 'quartier', 'zone', 'region', 'departement', 'pays', 'france',
    'talange', 'jarny', 'carlo', 'chanzy', 'behren', 'ferry', 'magny', 'bar', 'mis',
    # Types d'entreprises/organisations
    'greta', 'cfa', 'afpa', 'formation', 'academie', 'ecole', 'universite', 'institut',
    'centre', 'organisme', 'association', 'entreprise', 'societe', 'sarl', 'sas', 'sa',
    'eurl', 'auto', 'business', 'company', 'corp', 'ltd', 'inc', 'groupe',
    # Formation/éducation
    'adultes', 'jeune', 'particulier', 'publics', 'coiffure', 'tourisme', 'industrie',
    'educatif', 'petite', 'routiers', 'retrouvez', 'bilan', 'orientation', 'humaines',
    'titre', 'lieu', 'aucune', 'eiffel', 'zay', 'reiser', 'mondon', 'schuman',
    'sergent', 'blandan', 'emile', 'levassor', 'bois', 'jules', 'lemagny',
    # Fonctions/titres
    'directeur', 'directrice', 'manager', 'responsable', 'chef', 'secretaire', 'comptable',
    'webmaster', 'community', 'dessinateur', 'projeteur', 'formateur', 'formatrice',
    'enseignant', 'enseignante', 'professeur', 'professeure', 'docteur', 'docteure',
    'madame', 'monsieur', 'mme', 'm.', 'mr', 'mrs', 'ms',
    # Tech / dev / UI (faux positifs fréquents dans les scrapers)
    'application', 'mobile', 'web', 'site', 'distanciel', 'hybride', 'presentiel',
    'nom', 'prenom', 'envoyer', 'envoyez', 'contact', 'info', 'information',
    'service', 'client', 'support', 'aide', 'help', 'assistance',
    'react', 'vue', 'angular', 'node', 'python', 'javascript', 'typescript', 'laravel',
    'php', 'java', 'ruby', 'rails', 'django', 'flask', 'frontend', 'backend', 'dev',
    'data', 'machine', 'learning', 'deep', 'engine', 'console', 'search', 'optimization',
    'mesure', 'rate', 'policy', 'premiers', 'sain', 'choisir', 'des', 'dans', 'pas',
    'lien', 'aller', 'sur', 'like', 'page', 'section', 'article', 'menu', 'nav',
    'click', 'submit', 'button', 'input', 'form', 'login', 'signup', 'cookie',
    'analytics', 'tracking', 'dashboard', 'api', 'sdk', 'framework', 'library',
    # Couleurs
    'cyan', 'magenta', 'black', 'white', 'red', 'blue', 'green', 'yellow',
    # Autres
    'plan', 'plans', 'drem', 'autre', 'autres', 'divers', 'misc', 'general', 'generale',
    'admin', 'administrateur', 'administratrice', 'system', 'systeme', 'tech', 'technique',
    'test', 'demo', 'exemple', 'sample', 'default', 'defaut', 'null', 'none', 'vide',
    'espace', 'jean', 'pierre', 'marie', 'paul', 'sophie'
}

# Détection optionnelle des prénoms connus (pip install gender-guesser)
try:
    import gender_guesser.detector as gender_detector
    _gender_detector = gender_detector.Detector()
    GENDER_GUESSER_AVAILABLE = True
except ImportError:
    _gender_detector = None
    GENDER_GUESSER_AVAILABLE = False


def is_valid_human_name(name: str) -> bool:
    """
    Valide si un nom/prénom ressemble à un nom humain valide
    
    Utilise probablepeople et nameparser si disponibles pour une meilleure détection.
    
    Args:
        name: Le nom à valider
        
    Returns:
        True si le nom semble être un nom humain valide, False sinon
    """
    if not name or not isinstance(name, str):
        return False
    
    # Nettoyer le nom
    name = name.strip()
    
    # Vérifier la longueur minimale (au moins 2 caractères)
    if len(name) < 2:
        return False
    
    # Vérifier la longueur maximale (les noms humains dépassent rarement 30 caractères)
    if len(name) > 30:
        return False
    
    # Vérifier qu'il n'y a pas de chiffres
    if re.search(r'\d', name):
        return False
    
    # Vérifier qu'il n'y a pas de caractères spéciaux (sauf apostrophes, tirets, espaces)
    if re.search(r'[^a-zA-ZàâäéèêëïîôöùûüÿçÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ\'\-\s]', name):
        return False
    
    # Vérifier qu'il n'y a pas de mots-clés exclus (vérifier chaque mot individuellement)
    name_lower = name.lower()
    words = name_lower.split()
    for word in words:
        # Vérifier si le mot entier est dans les mots-clés exclus
        if word in EXCLUDED_KEYWORDS:
            return False
        # Vérifier si le mot contient un mot-clé exclu (pour détecter "formation-adultes", etc.)
        for keyword in EXCLUDED_KEYWORDS:
            if keyword in word and len(keyword) >= 4:  # Éviter les faux positifs avec des mots courts
                return False
    
    # Vérifier qu'il n'y a pas trop de mots (les noms/prénoms ont généralement 1-3 mots)
    words = name.split()
    if len(words) > 3:
        return False
    
    # Vérifier que chaque mot a au moins 2 caractères
    if any(len(word) < 2 for word in words):
        return False
    
    # Vérifier qu'il y a au moins une lettre majuscule (les noms propres commencent par une majuscule)
    # Mais on accepte aussi les noms en minuscules (cas où ils ne sont pas capitalisés)
    if not re.search(r'[a-zA-ZàâäéèêëïîôöùûüÿçÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ]', name):
        return False
    
    # Vérifier qu'il n'y a pas de répétitions suspectes (ex: "aaaa", "testtest")
    if re.search(r'(.)\1{3,}', name.lower()):
        return False
    
    # Vérifier qu'il n'y a pas de patterns suspects (ex: "abc", "123", "aaa")
    if re.search(r'(abc|xyz|aaa|test|demo|admin)', name_lower):
        return False
    
    # Vérifier qu'il n'y a pas de combinaisons suspectes (ex: "Formation Adultes", "Espace Jean")
    # Ces combinaisons sont souvent des titres de sections, pas des noms
    suspicious_patterns = [
        r'\b(formation|espace|bilan|orientation|lieu|jeune|publics|tourisme|industrie|educatif|routiers|humaines)\s+\w+',
        r'\w+\s+(adultes|particulier|coiffure|industrie|petite|retrouvez|aucune|titre)',
        r'\b(madame|monsieur|mme|m\.|mr|mrs|ms)\s+\w+',  # Titres seuls sans nom valide après
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, name_lower):
            return False
    
    # Utiliser probablepeople si disponible pour détecter si c'est une Person vs Corporation
    if PROBABLEPEOPLE_AVAILABLE:
        try:
            tagged, label = probablepeople.tag(name)
            # Si probablepeople détecte que ce n'est PAS une Person, rejeter
            # Les labels possibles sont généralement 'Person' ou 'Corporation'
            if label and label != 'Person':
                return False
        except Exception:
            # Si probablepeople échoue, continuer avec les autres vérifications
            pass
    
    # Utiliser nameparser si disponible pour vérifier la structure
    if NAMEPARSER_AVAILABLE:
        try:
            parsed = HumanName(name)
            # Si nameparser ne trouve ni prénom ni nom, c'est suspect
            if not parsed.first and not parsed.last:
                return False
            # Si le nom contient trop de composants suspects (titre, suffixe, etc.), rejeter
            if parsed.title and parsed.title.lower() in ['mr', 'mrs', 'ms', 'dr', 'prof']:
                # Les titres sont OK, mais vérifier qu'il y a bien un nom/prénom
                if not parsed.first and not parsed.last:
                    return False
        except Exception:
            pass

    # Si gender_guesser est dispo et que le nom est un seul mot (prénom), exiger un prénom reconnu
    if GENDER_GUESSER_AVAILABLE and _gender_detector:
        words = name.split()
        if len(words) == 1:
            gender = _gender_detector.get_gender(words[0])
            if gender == 'unknown':
                return False
        elif len(words) >= 2:
            # Pour une paire prénom nom, le premier mot doit être un prénom connu
            gender = _gender_detector.get_gender(words[0])
            if gender == 'unknown':
                return False

    return True


def validate_name_pair(first_name: str, last_name: str) -> Optional[Tuple[str, str]]:
    """
    Valide une paire prénom/nom et retourne les versions validées
    
    Args:
        first_name: Le prénom
        last_name: Le nom de famille
        
    Returns:
        Tuple (first_name, last_name) si valide, None sinon
    """
    if not first_name or not last_name:
        return None
    
    first_name = first_name.strip()
    last_name = last_name.strip()
    
    # Valider chaque partie
    if not is_valid_human_name(first_name):
        return None
    
    if not is_valid_human_name(last_name):
        return None
    
    # Vérifier que le prénom et le nom ne sont pas identiques (souvent une erreur)
    if first_name.lower() == last_name.lower():
        return None
    
    # Capitaliser correctement
    first_name = first_name.capitalize()
    last_name = last_name.capitalize()
    
    return (first_name, last_name)


def filter_valid_names(names: list) -> list:
    """
    Filtre une liste de noms pour ne garder que les noms valides
    
    Args:
        names: Liste de dictionnaires avec 'first_name', 'last_name', 'full_name'
        
    Returns:
        Liste filtrée avec seulement les noms valides
    """
    valid_names = []
    
    for name_data in names:
        if not isinstance(name_data, dict):
            continue
        
        first_name = name_data.get('first_name', '')
        last_name = name_data.get('last_name', '')
        
        if not first_name or not last_name:
            continue
        
        validated = validate_name_pair(first_name, last_name)
        if validated:
            valid_first, valid_last = validated
            full_name = f'{valid_first} {valid_last}'
            
            # Éviter les doublons
            if not any(n.get('full_name') == full_name for n in valid_names):
                valid_names.append({
                    'first_name': valid_first,
                    'last_name': valid_last,
                    'full_name': full_name
                })
    
    return valid_names

