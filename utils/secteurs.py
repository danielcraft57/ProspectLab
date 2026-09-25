#!/usr/bin/env python3
"""
Taxonomie secteurs ProspectLab / DanielCraft.

Objectif :
- regrouper les types Google (anglais) et libelles heterogenes
  vers une petite liste de secteurs FR
- fournir des variables email (secteur_label, echantillon_*, accroche)

Usage :
    from utils.secteurs import normalize_secteur, enrich_secteur_template_vars
"""
from __future__ import annotations

import unicodedata
from typing import Dict, Optional

from utils.taxonomie_secteurs import (  # noqa: E402
    GROUPES as TARGET_SECTEURS,
    GROUPES_ORDERED as TARGET_SECTEURS_ORDERED,
    resolve_hierarchie,
)


# Alias historiques (imports existants)
GROUPES = TARGET_SECTEURS
GROUPES_ORDERED = TARGET_SECTEURS_ORDERED


# Types Google Places / libelles bruts -> secteur FR
# Cles normalisees via normalize_key() (minuscule, sans accents, _ -> espace)
RAW_TO_TARGET: Dict[str, str] = {
    # --- deja FR / proches ---
    "technologie": "Technologie",
    "services": "Services",
    "restauration": "Restauration",
    "commerce": "Commerce",
    "education": "Éducation",
    "automobile": "Automobile",
    "beaute": "Beauté",
    "immobilier": "Immobilier",
    "btp": "BTP",
    "communication": "Communication",
    "sante": "Santé",
    "industrie": "Industrie",
    "finance": "Finance",
    "hotellerie": "Hôtellerie",
    "juridique": "Juridique",
    "transport": "Transport",
    "artisanat": "Artisanat",
    "concessionnaire auto": "Automobile",
    # --- Google EN (prod) ---
    "establishment": "Services",
    "food": "Restauration",
    "restaurant": "Restauration",
    "general contractor": "BTP",
    "health": "Santé",
    "lodging": "Hôtellerie",
    "store": "Commerce",
    "clothing store": "Commerce",
    "car repair": "Automobile",
    "car dealer": "Automobile",
    "electrician": "BTP",
    "real estate agency": "Immobilier",
    "hair care": "Beauté",
    "school": "Éducation",
    "primary school": "Éducation",
    "bakery": "Commerce",
    "lawyer": "Juridique",
    "dentist": "Santé",
    "jewelry store": "Commerce",
    "home goods store": "Commerce",
    "moving company": "Transport",
    "accounting": "Finance",
    "travel agency": "Tourisme",
    "electronics store": "Commerce",
    "book store": "Commerce",
    "insurance agency": "Finance",
    "laundry": "Services",
    "church": "Services",
    "local government office": "Services",
    "pharmacy": "Santé",
    "drugstore": "Santé",
    "car rental": "Automobile",
    "doctor": "Santé",
    "veterinary care": "Santé",
    "painter": "BTP",
    "campground": "Hôtellerie",
    "cafe": "Restauration",
    "roofing contractor": "BTP",
    "plumber": "BTP",
    "car wash": "Automobile",
    "bicycle store": "Commerce",
    "hardware store": "Commerce",
    "gas station": "Automobile",
    "shoe store": "Commerce",
    "taxi stand": "Transport",
    "library": "Éducation",
    "bank": "Finance",
    "convenience store": "Commerce",
    "movie theater": "Loisirs",
    "train station": "Transport",
    "shopping mall": "Commerce",
    "funeral home": "Services",
    "atm": "Finance",
    "courthouse": "Services",
    "museum": "Loisirs",
    "place of worship": "Services",
    "art gallery": "Loisirs",
    "amusement park": "Loisirs",
    "tourist attraction": "Tourisme",
    "department store": "Commerce",
    "storage": "Services",
    "parking": "Services",
    "aquarium": "Loisirs",
    "stadium": "Loisirs",
    "park": "Loisirs",
    "loisirs": "Loisirs",
    "tourisme": "Tourisme",
    "gym": "Loisirs",
    # --- libelles divers / legacy mapping ---
    "etablissement": "Services",
    "alimentation": "Commerce",
    "entreprise de travaux": "BTP",
    "magasin": "Commerce",
    "demenageur": "Transport",
    "location de voiture": "Automobile",
    "association / organization": "Services",
    "coiffeur": "Beauté",
    "computer consultant": "Technologie",
    "florist": "Artisanat",
    "garage": "Automobile",
    "magasin vetements": "Commerce",
    "rugby club": "Loisirs",
    "training center": "Éducation",
    "advertising agency": "Communication",
    "agence de voyage": "Tourisme",
    "architecture": "BTP",
    "computer store": "Commerce",
    "ecole": "Éducation",
    "magasin maison": "Commerce",
    "veterinaire": "Santé",
    "adult education school": "Éducation",
    "agence immobiliere": "Immobilier",
    "apartment rental agency": "Hôtellerie",
    "assurance": "Finance",
    "bicycle club": "Loisirs",
    "board game club": "Loisirs",
    "chartered accountant": "Finance",
    "design agency": "Communication",
    "embassy": "Services",
    "equipment rental agency": "Services",
    "family counselor": "Santé",
    "graphic designer": "Communication",
    "handball club": "Loisirs",
    "handicraft": "Artisanat",
    "holiday apartment rental": "Hôtellerie",
    "lieu de culte": "Services",
    "liquor store": "Commerce",
    "magasin electronique": "Commerce",
    "mosque": "Services",
    "music instructor": "Éducation",
    "orthopedic shoe store": "Commerce",
    "parc d'attractions": "Loisirs",
    "pet trainer": "Artisanat",
    "pilates studio": "Loisirs",
    "plasterer": "BTP",
    "shoe repair shop": "Commerce",
    "temp agency": "Services",
    "tennis club": "Loisirs",
    "vacation rental": "Hôtellerie",
    "wedding planner": "Communication",
    "wholesaler": "Commerce",
    "gym": "Loisirs",
}


# Secteur FR -> slug echantillon danielcraft.fr (priorite metier)
SECTEUR_TO_ECHANTILLON: Dict[str, str] = {
    "Technologie": "technologie",
    "Services": "services",
    "Restauration": "restauration",
    "Commerce": "commerce",
    "Éducation": "education",
    "Automobile": "automobile",
    "Beauté": "beaute",
    "Immobilier": "immobilier",
    "BTP": "architecture",
    "Communication": "photographie",
    "Santé": "osteo",
    "Industrie": "industrie",
    "Finance": "comptable",
    "Hôtellerie": "etablissement",
    "Juridique": "juridique",
    "Transport": "automobile",
    "Artisanat": "artisan",
    "Loisirs": "services",
    "Tourisme": "etablissement",
}


# Accroches courtes pour emails (ton simple)
SECTEUR_ACCROCHES: Dict[str, str] = {
    "Technologie": "un site produit clair, qui rassure avant la demo",
    "Services": "un site qui explique ton offre sans jargon",
    "Restauration": "carte, photos et reservation visibles sur telephone",
    "Commerce": "rayons, horaires et click & collect lisibles",
    "Éducation": "parcours, inscriptions et contact simples",
    "Automobile": "atelier, RDV et devis qui rassurent",
    "Beauté": "soins, tarifs et prise de RDV sans friction",
    "Immobilier": "biens, estimation et contact vendeur / acquereur",
    "BTP": "chantiers, devis express et preuves terrain",
    "Communication": "portfolio et demande de devis en un clic",
    "Santé": "tarifs, creneaux et rappel telephonique",
    "Industrie": "machines, qualite et devis B2B",
    "Finance": "forfaits, bilan flash et contact dirigeant",
    "Hôtellerie": "chambres, spa et reservation bien visibles",
    "Juridique": "expertises, forfaits et prise de contact",
    "Transport": "zones, delais et demande de devis",
    "Artisanat": "depannage, zones d'intervention et devis rapide",
    "Loisirs": "horaires, tarifs et reservation visibles sur telephone",
    "Tourisme": "offres, disponibilites et demande de devis simples",
}


def resolve_secteur(raw: Optional[str], nom: Optional[str] = None) -> str:
    """
    Resolut le groupe macro (secteur) a partir du brut et du nom.

    @param raw: Valeur BDD / type Google
    @param nom: Nom entreprise (optionnel, pour establishment)
    @returns: Secteur FR canonique ou chaine vide
    """
    resolved = resolve_hierarchie(raw, nom=nom)
    return str(resolved.get("secteur") or "")


def normalize_key(value: str) -> str:
    """
    Normalise une cle de mapping (minuscule, sans accents, _ -> espace).

    @param value: Libelle brut
    @returns: Cle normalisee
    """
    s = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def normalize_secteur(raw: Optional[str]) -> str:
    """
    Mappe un secteur brut vers un secteur FR canonique.

    @param raw: Valeur BDD (FR, EN Google, etc.)
    @returns: Secteur FR ou chaine vide si inconnu
    """
    src = (raw or "").strip()
    if not src:
        return ""
    if src in TARGET_SECTEURS:
        return src
    return RAW_TO_TARGET.get(normalize_key(src), "")


def echantillon_slug_for_secteur(secteur: Optional[str]) -> str:
    """
    Choisit un slug echantillon DanielCraft pour un secteur.

    @param secteur: Secteur brut ou canonique
    @returns: Slug (ex: restauration) ou vide
    """
    key = normalize_key(secteur or "")
    # D'abord le detail metier (dentist -> odontologie, pas osteo generique)
    rules = (
        ("restauration", ("restaur", "food", "brasser", "cafe", "pizza", "traiteur")),
        ("beaute", ("beaute", "spa", "coiff", "hair", "institut")),
        ("automobile", ("auto", "garage", "car repair", "car dealer", "car rental", "car wash", "vehicule")),
        ("boulangerie", ("bakery", "boulang", "patiss")),
        ("commerce", ("commerce", "store", "magasin", "retail", "shopping")),
        ("immobilier", ("immo", "real estate")),
        ("juridique", ("lawyer", "avocat", "jurid")),
        ("comptable", ("compta", "account")),
        ("odontologie", ("dent", "odont")),
        ("osteo", ("osteo", "kine", "physiother")),
        ("industrie", ("industr", "usin")),
        ("education", ("ecole", "school", "form", "education", "training")),
        ("etablissement", ("hotel", "lodging", "heberg", "campground")),
        ("technologie", ("tech", "saas", "software", "informatique")),
        ("artisan", ("plomb", "plumber", "electric", "artisan", "painter", "roofing")),
        ("fleuriste", ("fleur", "florist")),
        ("fitness", ("gym", "fitness", "sport")),
        ("association", ("associ", "ong", "church", "worship")),
        ("photographie", ("photo", "graphiste", "design agency", "advertising")),
        ("architecture", ("architect", "btp", "contractor", "general contractor")),
        ("caviste", ("wine", "cave", "liquor")),
        ("services", ("service", "facility", "laundry", "establishment")),
        ("sante", ("health", "doctor", "veterinary", "pharmacy", "sante")),
    )
    for slug, needles in rules:
        if any(n in key for n in needles):
            # Alias slug sante -> osteo (pas de /echantillons/sante/)
            if slug == "sante":
                return "osteo"
            return slug

    label = normalize_secteur(secteur) or (secteur or "").strip()
    if label in SECTEUR_TO_ECHANTILLON:
        return SECTEUR_TO_ECHANTILLON[label]
    return ""


def enrich_secteur_template_vars(secteur_raw: Optional[str]) -> Dict[str, object]:
    """
    Variables email liees au secteur / echantillon.

    @param secteur_raw: Champ entreprises.secteur
    @returns: Dict de placeholders pour TemplateManager
    @example
        enrich_secteur_template_vars("car_repair")
        # secteur_label=Automobile, echantillon_slug=automobile, ...
    """
    brut = (secteur_raw or "").strip()
    label = normalize_secteur(brut)
    slug = echantillon_slug_for_secteur(brut or label)
    root = "https://danielcraft.fr/echantillons"
    catalog = f"{root}/"
    accroche = SECTEUR_ACCROCHES.get(label, "un site clair, adapte a ton metier")

    out: Dict[str, object] = {
        "secteur": label or brut,
        "secteur_brut": brut,
        "secteur_label": label or brut,
        "secteur_groupe": label,
        "has_secteur": bool(label or brut),
        "has_secteur_groupe": bool(label),
        "secteur_accroche": accroche,
        "echantillon_slug": slug,
        "echantillon_catalog_url": catalog,
        "has_echantillon": bool(slug),
    }
    if slug:
        out.update(
            {
                "echantillon_url": f"{root}/{slug}/",
                "echantillon_demo_url": f"{root}/{slug}/demo/index.html",
                # Screenshot tablet brut (danielcraft) - fallback / preview full
                "echantillon_screenshot_full_url": f"{root}/{slug}/screenshots/tablet_1024x2500.webp",
                # Hero email (crop nombre d'or) - remplace par URL absolue dans TemplateManager
                "echantillon_screenshot_url": f"{root}/{slug}/screenshots/tablet_1024x2500.webp",
                "echantillon_email_hero_rel": f"static/email/danielcraft/pub/echantillons/{slug}.jpg",
            }
        )
    else:
        out.update(
            {
                "echantillon_url": catalog,
                "echantillon_demo_url": catalog,
                "echantillon_screenshot_url": "",
                "echantillon_screenshot_full_url": "",
                "echantillon_email_hero_rel": "",
            }
        )
    return out
