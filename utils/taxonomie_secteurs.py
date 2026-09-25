#!/usr/bin/env python3
"""
Taxonomie hierarchique ProspectLab : groupe (secteur) + categorie (metier).

Niveau 1 - secteur : macro FR (Santé, Loisirs, Tourisme…).
Niveau 2 - categorie : metier fin FR (osteopathe, garage, theatre…).

Usage :
    from utils.taxonomie_secteurs import resolve_hierarchie
    resolve_hierarchie("car_repair", nom="Garage Dupont")
    # {"secteur": "Automobile", "categorie": "garage", ...}
"""
from __future__ import annotations

import unicodedata
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Groupes macros (niveau 1)
# ---------------------------------------------------------------------------

GROUPES = frozenset(
    {
        "Technologie",
        "Services",
        "Restauration",
        "Commerce",
        "Éducation",
        "Automobile",
        "Beauté",
        "Immobilier",
        "BTP",
        "Communication",
        "Santé",
        "Industrie",
        "Finance",
        "Hôtellerie",
        "Juridique",
        "Transport",
        "Artisanat",
        "Loisirs",
        "Tourisme",
    }
)

GROUPES_ORDERED = (
    "Artisanat",
    "Automobile",
    "Beauté",
    "BTP",
    "Commerce",
    "Communication",
    "Éducation",
    "Finance",
    "Hôtellerie",
    "Immobilier",
    "Industrie",
    "Juridique",
    "Loisirs",
    "Restauration",
    "Santé",
    "Services",
    "Technologie",
    "Tourisme",
    "Transport",
)

# Types Google / libelles generiques : on privilegie l'inference par nom
_GENERIC_RAW_KEYS = frozenset(
    {
        "establishment",
        "etablissement",
        "point of interest",
        "point d interet",
        "point d'interet",
    }
)


def normalize_key(value: str) -> str:
    """
    Normalise une cle de mapping (minuscule, sans accents, _ -> espace).

    @param value: Libelle brut
    @returns: Cle normalisee
    """
    s = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# Categorie FR (niveau 2) -> groupe
# ---------------------------------------------------------------------------

CATEGORIE_TO_GROUPE: Dict[str, str] = {
    # BTP / artisanat batiment
    "plombier": "BTP",
    "electricien": "BTP",
    "serrurier": "BTP",
    "entreprise de travaux": "BTP",
    "couvreur": "BTP",
    "peintre": "BTP",
    "platrier": "BTP",
    "architecture": "BTP",
    # Restauration
    "restaurant": "Restauration",
    "bar": "Restauration",
    "cafe": "Restauration",
    "a emporter": "Restauration",
    "livraison de repas": "Restauration",
    "boite de nuit": "Loisirs",
    "traiteur": "Restauration",
    # Sante
    "medecin": "Santé",
    "dentiste": "Santé",
    "hopital": "Santé",
    "pharmacie": "Santé",
    "parapharmacie": "Santé",
    "kinesitherapeute": "Santé",
    "osteopathe": "Santé",
    "psychologue": "Santé",
    "veterinaire": "Santé",
    "salle de sport": "Loisirs",
    "pilates": "Loisirs",
    # Finance / juridique
    "expert-comptable": "Finance",
    "banque": "Finance",
    "distributeur": "Finance",
    "assurance": "Finance",
    "avocat": "Juridique",
    "notaire": "Juridique",
    "agence immobiliere": "Immobilier",
    # Beaute
    "coiffeur": "Beauté",
    "institut de beaute": "Beauté",
    "spa": "Beauté",
    "barbier": "Beauté",
    # Auto / transport
    "concessionnaire auto": "Automobile",
    "garage": "Automobile",
    "location de voiture": "Automobile",
    "lavage auto": "Automobile",
    "station service": "Automobile",
    "parking": "Services",
    "station taxi": "Transport",
    "gare routiere": "Transport",
    "gare": "Transport",
    "metro": "Transport",
    "tramway": "Transport",
    "station transport": "Transport",
    "aeroport": "Transport",
    "demenageur": "Transport",
    "taxi": "Transport",
    "vtc": "Transport",
    # Commerce
    "magasin": "Commerce",
    "supermarche": "Commerce",
    "epicerie": "Commerce",
    "grand magasin": "Commerce",
    "centre commercial": "Commerce",
    "quincaillerie": "Commerce",
    "magasin maison": "Commerce",
    "magasin meubles": "Commerce",
    "magasin electronique": "Commerce",
    "magasin vetements": "Commerce",
    "magasin chaussures": "Commerce",
    "bijouterie": "Commerce",
    "librairie": "Commerce",
    "fleuriste": "Artisanat",
    "animalerie": "Commerce",
    "caviste": "Commerce",
    "laverie": "Services",
    "garde-meubles": "Services",
    "boulangerie": "Commerce",
    "magasin de sport": "Commerce",
    # Loisirs / culture / tourisme
    "attraction touristique": "Tourisme",
    "musee": "Loisirs",
    "galerie d'art": "Loisirs",
    "cinema": "Loisirs",
    "bowling": "Loisirs",
    "parc d'attractions": "Loisirs",
    "parc de loisirs": "Loisirs",
    "aquarium": "Loisirs",
    "zoo": "Loisirs",
    "parc": "Loisirs",
    "stade": "Loisirs",
    "theatre": "Loisirs",
    "mjc": "Loisirs",
    "salle des fetes": "Loisirs",
    "club sportif": "Loisirs",
    # Education / petite enfance
    "ecole": "Éducation",
    "ecole primaire": "Éducation",
    "college/lycee": "Éducation",
    "lycee": "Éducation",
    "college": "Éducation",
    "universite": "Éducation",
    "bibliotheque": "Éducation",
    "centre de formation": "Éducation",
    "auto ecole": "Éducation",
    "creche": "Éducation",
    "halte garderie": "Éducation",
    # Admin / culte
    "mairie": "Services",
    "tribunal": "Services",
    "police": "Services",
    "pompiers": "Services",
    "poste": "Services",
    "administration": "Services",
    "eglise": "Services",
    "mosquee": "Services",
    "synagogue": "Services",
    "temple hindou": "Services",
    "lieu de culte": "Services",
    # Hebergement / voyage
    "hotel": "Hôtellerie",
    "agence de voyage": "Tourisme",
    "camping": "Hôtellerie",
    "location saisonniere": "Hôtellerie",
    # Services / conseil / tech / com
    "securite": "Services",
    "conseil": "Services",
    "interim": "Services",
    "nettoyage": "Services",
    "informatique": "Technologie",
    "imprimerie": "Communication",
    "photographe": "Communication",
    "agence de communication": "Communication",
    "agence marketing": "Communication",
    "agence web": "Technologie",
    "energie": "Industrie",
    "pompes funebres": "Services",
    "etablissement": "Services",
    "point d'interet": "Services",
}


# ---------------------------------------------------------------------------
# Brut Google / legacy -> categorie FR
# ---------------------------------------------------------------------------

RAW_TO_CATEGORIE: Dict[str, str] = {
    # Google EN (cles normalisees)
    "plumber": "plombier",
    "electrician": "electricien",
    "locksmith": "serrurier",
    "general contractor": "entreprise de travaux",
    "roofing contractor": "couvreur",
    "moving company": "demenageur",
    "painter": "peintre",
    "plasterer": "platrier",
    "restaurant": "restaurant",
    "food": "restaurant",
    "bar": "bar",
    "cafe": "cafe",
    "bakery": "boulangerie",
    "meal takeaway": "a emporter",
    "meal delivery": "livraison de repas",
    "night club": "boite de nuit",
    "doctor": "medecin",
    "dentist": "dentiste",
    "hospital": "hopital",
    "pharmacy": "pharmacie",
    "drugstore": "parapharmacie",
    "physiotherapist": "kinesitherapeute",
    "veterinary care": "veterinaire",
    "health": "medecin",
    "gym": "salle de sport",
    "pilates studio": "pilates",
    "accounting": "expert-comptable",
    "bank": "banque",
    "atm": "distributeur",
    "insurance agency": "assurance",
    "lawyer": "avocat",
    "real estate agency": "agence immobiliere",
    "hair care": "coiffeur",
    "beauty salon": "institut de beaute",
    "spa": "spa",
    "car dealer": "concessionnaire auto",
    "car repair": "garage",
    "car rental": "location de voiture",
    "car wash": "lavage auto",
    "gas station": "station service",
    "parking": "parking",
    "taxi stand": "station taxi",
    "bus station": "gare routiere",
    "train station": "gare",
    "subway station": "metro",
    "light rail station": "tramway",
    "transit station": "station transport",
    "airport": "aeroport",
    "store": "magasin",
    "supermarket": "supermarche",
    "convenience store": "epicerie",
    "department store": "grand magasin",
    "shopping mall": "centre commercial",
    "hardware store": "quincaillerie",
    "home goods store": "magasin maison",
    "furniture store": "magasin meubles",
    "electronics store": "magasin electronique",
    "clothing store": "magasin vetements",
    "shoe store": "magasin chaussures",
    "jewelry store": "bijouterie",
    "book store": "librairie",
    "bicycle store": "magasin",
    "florist": "fleuriste",
    "pet store": "animalerie",
    "liquor store": "caviste",
    "laundry": "laverie",
    "storage": "garde-meubles",
    "tourist attraction": "attraction touristique",
    "museum": "musee",
    "art gallery": "galerie d'art",
    "movie theater": "cinema",
    "bowling alley": "bowling",
    "amusement park": "parc d'attractions",
    "aquarium": "aquarium",
    "zoo": "zoo",
    "park": "parc",
    "stadium": "stade",
    "school": "ecole",
    "primary school": "ecole primaire",
    "secondary school": "college/lycee",
    "university": "universite",
    "library": "bibliotheque",
    "city hall": "mairie",
    "courthouse": "tribunal",
    "police": "police",
    "fire station": "pompiers",
    "post office": "poste",
    "local government office": "administration",
    "church": "eglise",
    "mosque": "mosquee",
    "synagogue": "synagogue",
    "hindu temple": "temple hindou",
    "place of worship": "lieu de culte",
    "lodging": "hotel",
    "campground": "camping",
    "travel agency": "agence de voyage",
    "funeral home": "pompes funebres",
    "establishment": "etablissement",
    "point of interest": "point d'interet",
    # Libelles FR deja fins
    "plombier": "plombier",
    "electricien": "electricien",
    "entreprise de travaux": "entreprise de travaux",
    "couvreur": "couvreur",
    "peintre": "peintre",
    "demenageur": "demenageur",
    "restaurant": "restaurant",
    "boulangerie": "boulangerie",
    "medecin": "medecin",
    "dentiste": "dentiste",
    "pharmacie": "pharmacie",
    "veterinaire": "veterinaire",
    "coiffeur": "coiffeur",
    "garage": "garage",
    "concessionnaire auto": "concessionnaire auto",
    "location de voiture": "location de voiture",
    "agence immobiliere": "agence immobiliere",
    "assurance": "assurance",
    "avocat": "avocat",
    "expert comptable": "expert-comptable",
    "expert-comptable": "expert-comptable",
    "magasin": "magasin",
    "magasin vetements": "magasin vetements",
    "magasin maison": "magasin maison",
    "magasin electronique": "magasin electronique",
    "bijouterie": "bijouterie",
    "librairie": "librairie",
    "fleuriste": "fleuriste",
    "caviste": "caviste",
    "hotel": "hotel",
    "agence de voyage": "agence de voyage",
    "parc d'attractions": "parc d'attractions",
    "cinema": "cinema",
    "musee": "musee",
    "ecole": "ecole",
    "administration": "administration",
    "etablissement": "etablissement",
}


# ---------------------------------------------------------------------------
# Heuristiques nom (fortes) : (needles, groupe, categorie)
# Ordre = priorite (premier match gagne)
# ---------------------------------------------------------------------------

_NOM_RULES: Tuple[Tuple[Tuple[str, ...], str, str], ...] = (
    (("creche", "micro creche", "micro-creche", "halte garderie", "multi accueil", "multi-accueil"), "Éducation", "creche"),
    (("mjc", "maison des jeunes"), "Loisirs", "mjc"),
    (("theatre", "théâtre"), "Loisirs", "theatre"),
    (("cinema", "cinéma"), "Loisirs", "cinema"),
    (("parc de loisirs", "parc d attractions", "parc d'attractions", "forêt de haye", "foret de haye"), "Loisirs", "parc de loisirs"),
    (("musee", "musée"), "Loisirs", "musee"),
    (("bowling",), "Loisirs", "bowling"),
    (("salle des fetes", "salle des fêtes", "salle des fetes"), "Loisirs", "salle des fetes"),
    (("osteopathe", "ostéopathe", "osteo "), "Santé", "osteopathe"),
    (("kine", "kiné", "kinesitherapeute", "kinésithérapeute"), "Santé", "kinesitherapeute"),
    (("psychologue", "psychologie"), "Santé", "psychologue"),
    (("dentiste", "dental", "odontolog"), "Santé", "dentiste"),
    (("pharmacie",), "Santé", "pharmacie"),
    (("veterinaire", "vétérinaire"), "Santé", "veterinaire"),
    (("medecin", "médecin", "docteur "), "Santé", "medecin"),
    (("avocat", "avocats"), "Juridique", "avocat"),
    (("notaire",), "Juridique", "notaire"),
    (("assurance", "assurances"), "Finance", "assurance"),
    (("comptable", "expert comptable", "fiducial compta"), "Finance", "expert-comptable"),
    (("agence immobiliere", "immobilier", "immo "), "Immobilier", "agence immobiliere"),
    (("garage", "carrosserie", "auto repair"), "Automobile", "garage"),
    (("concessionnaire",), "Automobile", "concessionnaire auto"),
    (("auto ecole", "auto-ecole", "autoécole", "permis "), "Éducation", "auto ecole"),
    (("lycee", "lycée"), "Éducation", "lycee"),
    (("college", "collège"), "Éducation", "college"),
    (("universite", "université", "faculte", "faculté"), "Éducation", "universite"),
    (("centre de formation", "organisme de formation", "cfa "), "Éducation", "centre de formation"),
    (("coiffeur", "coiffure", "hair "), "Beauté", "coiffeur"),
    (("institut de beaute", "esthetique", "esthétique"), "Beauté", "institut de beaute"),
    (("pizzeria", "pizza ", "restaurant", "brasserie", "traiteur"), "Restauration", "restaurant"),
    (("boulangerie", "patisserie", "pâtisserie"), "Commerce", "boulangerie"),
    (("bijouterie", "joaill"), "Commerce", "bijouterie"),
    (("librairie",), "Commerce", "librairie"),
    (("magasin de sport", "sport store", "pays du sport"), "Commerce", "magasin de sport"),
    (("imprimerie", "print ", "pixcolor"), "Communication", "imprimerie"),
    (("photographe", "photo "), "Communication", "photographe"),
    (("agence de communication", "agence marketing", "agence web"), "Communication", "agence de communication"),
    (("securite", "sécurité", "security"), "Services", "securite"),
    (("conseil", "consulting", "consultant"), "Services", "conseil"),
    (("informatique", "infogerance", "infogérance"), "Technologie", "informatique"),
    (("engie", "edf ", "energie", "énergie", "electricite", "électricité"), "Industrie", "energie"),
    (("voyage", "vacances", "tourisme", "travel"), "Tourisme", "agence de voyage"),
    (("hotel", "hôtel", "camping"), "Hôtellerie", "hotel"),
    (("plombier", "plomberie"), "BTP", "plombier"),
    (("electricien", "électricien"), "BTP", "electricien"),
    (("couvreur", "toiture"), "BTP", "couvreur"),
    (("taxi", "vtc "), "Transport", "taxi"),
    (("demenage", "déménage"), "Transport", "demenageur"),
    (("club ", "athletic", "football", "rugby", "handball", "tennis club", "triathlon", "natation"), "Loisirs", "club sportif"),
    (("salle de sport", "fitness", "gym "), "Loisirs", "salle de sport"),
)


def infer_from_nom(nom: Optional[str]) -> Optional[Tuple[str, str]]:
    """
    Inferre (groupe, categorie) a partir du nom (regles fortes).

    @param nom: Nom de l'entreprise
    @returns: Tuple (groupe, categorie) ou None
    """
    key = normalize_key(nom or "")
    if not key:
        return None
    for needles, groupe, categorie in _NOM_RULES:
        for needle in needles:
            if normalize_key(needle) in key:
                return (groupe, categorie)
    return None


def categorie_from_raw(raw: Optional[str]) -> str:
    """
    Mappe une valeur brute vers une categorie FR.

    @param raw: Type Google / libelle legacy
    @returns: Categorie FR ou chaine vide
    """
    src = (raw or "").strip()
    if not src:
        return ""
    key = normalize_key(src)
    if key in RAW_TO_CATEGORIE:
        return RAW_TO_CATEGORIE[key]
    # Deja une categorie connue
    if key in CATEGORIE_TO_GROUPE:
        return key
    # Alias accents / apostrophes
    for cat in CATEGORIE_TO_GROUPE:
        if normalize_key(cat) == key:
            return cat
    return ""


def groupe_from_categorie(categorie: Optional[str]) -> str:
    """
    Retourne le groupe macro d'une categorie.

    @param categorie: Metier FR
    @returns: Groupe ou chaine vide
    """
    cat = (categorie or "").strip()
    if not cat:
        return ""
    if cat in CATEGORIE_TO_GROUPE:
        return CATEGORIE_TO_GROUPE[cat]
    return CATEGORIE_TO_GROUPE.get(normalize_key(cat), "")


def is_groupe(value: Optional[str]) -> bool:
    """
    Indique si la valeur est deja un groupe macro.

    @param value: Libelle
    @returns: True si groupe canonique
    """
    return (value or "").strip() in GROUPES


def is_generic_raw(raw: Optional[str]) -> bool:
    """
    Indique si le brut est trop generique (establishment…).

    @param raw: Valeur brute
    @returns: True si generique
    """
    return normalize_key(raw or "") in _GENERIC_RAW_KEYS


def list_categories_for_groupe(groupe: Optional[str] = None) -> List[str]:
    """
    Liste les categories connues, optionnellement filtrees par groupe.

    @param groupe: Groupe macro (optionnel)
    @returns: Liste triee de categories
    """
    g = (groupe or "").strip()
    cats = []
    for cat, grp in CATEGORIE_TO_GROUPE.items():
        if g and grp != g:
            continue
        # Masquer les categories purement generiques dans les selects
        if cat in ("etablissement", "point d'interet"):
            continue
        cats.append(cat)
    return sorted(set(cats), key=lambda x: normalize_key(x))


def resolve_hierarchie(
    raw: Optional[str],
    nom: Optional[str] = None,
    categorie_actuelle: Optional[str] = None,
    secteur_raw: Optional[str] = None,
    reclasser_macro: bool = True,
) -> Dict[str, object]:
    """
    Resolut secteur (groupe) + categorie a partir du brut et du nom.

    Regles :
    1. Brut Google / categorie fine connue -> categorie + groupe
    2. Brut deja groupe macro -> garder, categorie via raw/nom
    3. Generique (establishment) -> inference nom, sinon Services
    4. Si reclasser_macro et heuristique nom forte contredit le groupe -> reclasser

    @param raw: Valeur secteur actuelle (ou type Google)
    @param nom: Nom entreprise
    @param categorie_actuelle: Categorie deja en BDD (optionnel)
    @param secteur_raw: Backup brut (optionnel)
    @param reclasser_macro: Autoriser le reclassement des macros fausses via le nom
    @returns: Dict secteur, categorie, changed, reason, source_raw
    @example
        resolve_hierarchie("travel_agency", "Oxygene Vacances")
        # secteur=Tourisme, categorie=agence de voyage
    """
    src = (raw or "").strip()
    cat_cur = (categorie_actuelle or "").strip()
    backup_src = (secteur_raw or "").strip() or src
    inferred = infer_from_nom(nom)

    # --- Cas 1 : brut = type Google / categorie fine ---
    if src and not is_groupe(src):
        if is_generic_raw(src):
            if inferred:
                return {
                    "secteur": inferred[0],
                    "categorie": inferred[1],
                    "changed": True,
                    "reason": "generic_raw_nom",
                    "source_raw": backup_src,
                }
            return {
                "secteur": "Services",
                "categorie": cat_cur or "",
                "changed": True,
                "reason": "generic_raw_fallback",
                "source_raw": backup_src,
            }

        cat = categorie_from_raw(src) or cat_cur
        grp = groupe_from_categorie(cat) if cat else ""
        if not grp and inferred:
            return {
                "secteur": inferred[0],
                "categorie": inferred[1],
                "changed": True,
                "reason": "raw_unknown_nom",
                "source_raw": backup_src,
            }
        if grp:
            # Reclassement fort meme sur un type Google si le nom est tres clair
            if reclasser_macro and inferred and inferred[0] != grp:
                return {
                    "secteur": inferred[0],
                    "categorie": inferred[1],
                    "changed": True,
                    "reason": "raw_reclass_nom",
                    "source_raw": backup_src,
                }
            # Affiner la categorie si le nom est plus precis dans le meme groupe
            # (ex: health + "Osteopathe X" -> osteopathe, pas medecin generique)
            if inferred and inferred[0] == grp and inferred[1] and inferred[1] != cat:
                generic_cats = {
                    "medecin",
                    "magasin",
                    "ecole",
                    "restaurant",
                    "etablissement",
                    "point d'interet",
                }
                if cat in generic_cats or not cat:
                    cat = inferred[1]
            return {
                "secteur": grp,
                "categorie": cat,
                "changed": True,
                "reason": "raw_to_hierarchie",
                "source_raw": backup_src,
            }

    # --- Cas 2 : deja un groupe macro ---
    if is_groupe(src):
        cat = cat_cur
        # Reconstruire categorie depuis secteur_raw si present
        if not cat and backup_src and backup_src != src and not is_groupe(backup_src):
            if not is_generic_raw(backup_src):
                cat = categorie_from_raw(backup_src)

        if reclasser_macro and inferred and inferred[0] != src:
            return {
                "secteur": inferred[0],
                "categorie": inferred[1],
                "changed": True,
                "reason": "macro_reclass_nom",
                "source_raw": backup_src if backup_src != inferred[0] else src,
            }

        if not cat and inferred:
            # Remplir categorie sans changer le groupe si coherent, sinon garder groupe
            if inferred[0] == src:
                cat = inferred[1]
                return {
                    "secteur": src,
                    "categorie": cat,
                    "changed": bool(cat != cat_cur),
                    "reason": "macro_fill_categorie",
                    "source_raw": backup_src,
                }
            # Nom suggere autre chose mais reclasser_macro off / deja gere plus haut
            cat = inferred[1] if inferred[0] == src else cat

        return {
            "secteur": src,
            "categorie": cat or "",
            "changed": (cat or "") != cat_cur,
            "reason": "macro_keep",
            "source_raw": backup_src,
        }

    # --- Cas 3 : vide / inconnu ---
    if inferred:
        return {
            "secteur": inferred[0],
            "categorie": inferred[1],
            "changed": True,
            "reason": "empty_nom",
            "source_raw": backup_src,
        }

    if cat_cur:
        grp = groupe_from_categorie(cat_cur)
        if grp:
            return {
                "secteur": grp,
                "categorie": cat_cur,
                "changed": True,
                "reason": "categorie_actuelle",
                "source_raw": backup_src,
            }

    # Brut inconnu : ne pas laisser un type EN comme "groupe"
    return {
        "secteur": "Services",
        "categorie": "",
        "changed": True,
        "reason": "fallback",
        "source_raw": backup_src or src,
    }
