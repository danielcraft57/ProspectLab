#!/usr/bin/env python3
"""
Catalogue des echantillons / vitrines DanielCraft pour ProspectLab.

Charge ``Data/vitrines.json``, mappe un secteur entreprise vers un slug,
et expose les URLs locales des screenshots (copie sous static/danielcraft).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.secteurs import (
    echantillon_slug_for_secteur,
    enrich_secteur_template_vars,
    normalize_secteur,
)

# Racine projet ProspectLab
_APP_ROOT = Path(__file__).resolve().parent.parent
_SCREENSHOTS_DIR = _APP_ROOT / "static" / "danielcraft" / "echantillons"
_SCREENSHOTS_BASE_URL = "/static/danielcraft/echantillons"
# Catalogue versionne (prod) + fallback local Data/
_CATALOG_CANDIDATES = (
    _APP_ROOT / "static" / "danielcraft" / "vitrines.json",
    _APP_ROOT / "Data" / "vitrines.json",
)


def _resolve_catalog_path() -> Path:
    """
    Retrouve le fichier vitrines.json (static versionne ou Data local).

    @returns: Chemin absolu du catalogue
    @raises FileNotFoundError: Si aucun fichier n'existe
    """
    for path in _CATALOG_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "Catalogue vitrines introuvable "
        "(attendu: static/danielcraft/vitrines.json ou Data/vitrines.json)"
    )


@lru_cache(maxsize=1)
def load_vitrines_catalog() -> Dict[str, Any]:
    """
    Charge le catalogue vitrines.json (cache processus).

    @returns: Dict brut du fichier (currency, items, ...)
    @raises FileNotFoundError: Si le fichier est absent
    @raises json.JSONDecodeError: Si le JSON est invalide
    """
    catalog_path = _resolve_catalog_path()
    with catalog_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("vitrines.json doit etre un objet JSON")
    return data


def invalidate_catalog_cache() -> None:
    """Vide le cache du catalogue (utile apres mise a jour du JSON)."""
    load_vitrines_catalog.cache_clear()


def _local_screenshot_urls(slug: str) -> Dict[str, str]:
    """
    Construit les URLs publiques des screenshots locaux pour un slug.

    @param slug: Slug echantillon (ex: restauration)
    @returns: Dict device/variant -> URL relative (/static/...)
    """
    folder = _SCREENSHOTS_DIR / slug
    out: Dict[str, str] = {}
    if not folder.is_dir():
        return out
    mapping = {
        "catalog_16x10.webp": "catalog",
        "tablet_1024x2500.webp": "tablet",
        "desktop_1920x2400.webp": "desktop",
        "mobile_430x2500.webp": "mobile",
    }
    for filename, key in mapping.items():
        path = folder / filename
        if path.is_file():
            out[key] = f"{_SCREENSHOTS_BASE_URL}/{slug}/{filename}"
    return out


def _primary_screenshot_url(shots: Dict[str, str]) -> str:
    """
    Choisit l'image principale a afficher en carte.

    @param shots: URLs par variante
    @returns: URL ou chaine vide
    """
    for key in ("catalog", "tablet", "desktop", "mobile"):
        if shots.get(key):
            return shots[key]
    return ""


def list_echantillon_items() -> List[Dict[str, Any]]:
    """
    Liste les echantillons du catalogue, enrichis des screenshots locaux.

    @returns: Liste d'items normalises
    """
    raw = load_vitrines_catalog()
    items = raw.get("items") or []
    result: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        shots = _local_screenshot_urls(slug)
        result.append(
            {
                "slug": slug,
                "category": str(item.get("category") or "").strip(),
                "title": str(item.get("title") or slug).strip(),
                "tagline": str(item.get("tagline") or "").strip(),
                "excerpt": str(item.get("excerpt") or "").strip(),
                "features": list(item.get("features") or []),
                "stack": list(item.get("stack") or []),
                "demo_url": f"https://danielcraft.fr/echantillons/{slug}/demo/index.html",
                "fiche_url": f"https://danielcraft.fr/echantillons/{slug}/",
                "screenshots": shots,
                "screenshot_url": _primary_screenshot_url(shots),
                "has_local_screenshot": bool(shots),
            }
        )
    return result


def get_echantillon_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Retrouve un echantillon par slug.

    @param slug: Slug recherche
    @returns: Item ou None
    """
    needle = (slug or "").strip().lower()
    if not needle:
        return None
    for item in list_echantillon_items():
        if item["slug"] == needle:
            return item
    return None


def match_echantillons_for_secteur(
    secteur: Optional[str],
    *,
    limit_related: int = 8,
) -> Dict[str, Any]:
    """
    Associe un secteur entreprise a un echantillon principal + proches.

    @param secteur: Secteur brut ou canonique de la fiche
    @param limit_related: Nombre max d'echantillons de la meme categorie
    @returns: Dict match (primary, related, secteur_label, slug)
    @example
        match_echantillons_for_secteur("restaurant")
        # primary.slug == "restauration"
    """
    vars_secteur = enrich_secteur_template_vars(secteur)
    label = str(vars_secteur.get("secteur_label") or "").strip()
    slug = echantillon_slug_for_secteur(secteur) or str(
        vars_secteur.get("echantillon_slug") or ""
    ).strip()

    items = list_echantillon_items()
    by_slug = {it["slug"]: it for it in items}
    primary = by_slug.get(slug) if slug else None

    # Fallback: si le slug mappe n'existe plus, garde le premier item du catalogue
    if not primary and slug:
        # Alias historiques eventuels
        aliases = {
            "sante": "osteo",
            "hotel": "etablissement",
            "chocolatier": "chocolaterie",
        }
        alt = aliases.get(slug)
        if alt:
            primary = by_slug.get(alt)
            slug = alt if primary else slug

    related: List[Dict[str, Any]] = []
    if primary:
        cat = primary.get("category") or ""
        for it in items:
            if it["slug"] == primary["slug"]:
                continue
            if cat and it.get("category") == cat:
                related.append(it)
            if len(related) >= limit_related:
                break

    return {
        "secteur": label or (secteur or ""),
        "secteur_label": label,
        "matched_slug": (primary or {}).get("slug") or slug or "",
        "primary": primary,
        "related": related,
        "has_match": bool(primary and primary.get("has_local_screenshot")),
    }


def build_maquettes_payload_for_entreprise(
    entreprise: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Payload API pour l'onglet Maquettes d'une fiche entreprise.

    @param entreprise: Dict entreprise (id, nom, secteur, ...)
    @returns: Payload pret pour jsonify
    """
    ent = entreprise or {}
    secteur = ent.get("secteur") or ent.get("categorie") or ""
    match = match_echantillons_for_secteur(str(secteur or ""))
    catalog = list_echantillon_items()
    with_shots = sum(1 for it in catalog if it.get("has_local_screenshot"))

    return {
        "success": True,
        "entreprise_id": ent.get("id"),
        "entreprise_nom": ent.get("nom"),
        "secteur": match.get("secteur"),
        "secteur_label": match.get("secteur_label"),
        "matched_slug": match.get("matched_slug"),
        "primary": match.get("primary"),
        "related": match.get("related") or [],
        "has_match": bool(match.get("has_match")),
        "catalog_count": len(catalog),
        "screenshots_ready": with_shots,
        "catalog": catalog,
        "normalize_secteur": normalize_secteur(str(secteur or "")),
    }
