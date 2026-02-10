"""
Objectifs de ciblage prédéfinis pour les campagnes email.

Chaque objectif correspond à un segment métier (formations, modernisation, etc.)
et définit des critères de filtrage réutilisables pour la prospection.
"""

# Liste des objectifs : id, nom, description, filtres appliqués
OBJECTIFS_CIBLAGE = [
    {
        "id": "formations",
        "nom": "Formations et organismes de formation",
        "description": "Organismes de formation, centres de formation, OPCO, acteurs Qualiopi",
        "filters": {
            "secteur_contains": "Formation",
            "tags_contains": "formation",
        },
    },
    {
        "id": "formations_education",
        "nom": "Formation continue et éducation",
        "description": "Formation professionnelle, continue, entreprise, coaching",
        "filters": {
            "secteur_contains": "Éducation",
            "tags_contains": "formation",
        },
    },
    {
        "id": "sites_moderniser",
        "nom": "Sites à moderniser",
        "description": "Prospects avec score sécurité faible ou opportunité élevée (besoin technique)",
        "filters": {
            "opportunite": ["Très élevée", "Élevée"],
            "score_securite_max": 50,
        },
    },
    {
        "id": "haute_opportunite",
        "nom": "Haute opportunité",
        "description": "Prospects classés très élevée ou élevée (tous secteurs)",
        "filters": {
            "opportunite": ["Très élevée", "Élevée"],
        },
    },
    {
        "id": "tech_web",
        "nom": "Secteur tech et web",
        "description": "Développement web, agences digitales, SEO, e-commerce",
        "filters": {
            "secteur_contains": "Technologie",
            "tags_contains": "web",
        },
    },
    {
        "id": "non_contactes",
        "nom": "Jamais contactés",
        "description": "Entreprises avec email qui n'ont jamais reçu de campagne",
        "filters": {
            "exclude_already_contacted": True,
        },
    },
    {
        "id": "favoris",
        "nom": "Favoris uniquement",
        "description": "Entreprises marquées comme favoris",
        "filters": {
            "favori": True,
        },
    },
    {
        "id": "securite_faible",
        "nom": "Sécurité à renforcer",
        "description": "Score sécurité faible (potentiel audit / mise en conformité)",
        "filters": {
            "score_securite_max": 40,
        },
    },
]


def get_objectifs():
    """
    Retourne la liste des objectifs de ciblage.

    Returns:
        list: Liste des dicts (id, nom, description, filters)
    """
    return list(OBJECTIFS_CIBLAGE)


def get_objectif_by_id(objectif_id):
    """
    Retourne un objectif par son id.

    Args:
        objectif_id: Identifiant de l'objectif

    Returns:
        dict|None: Objectif ou None
    """
    for obj in OBJECTIFS_CIBLAGE:
        if obj["id"] == objectif_id:
            return obj
    return None
