#!/usr/bin/env python3
"""
Catalogue des echantillons / vitrines DanielCraft pour ProspectLab.

Charge ``Data/vitrines.json``, mappe un secteur entreprise vers un slug,
et expose les URLs locales des screenshots (copie sous static/danielcraft).
"""
from __future__ import annotations

import json
import random
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
    limit_related: int = 40,
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


def _email_screenshot_for_slug(slug: str, base_url: str = "") -> str:
    """
    URL screenshot pour une carte email (JPG local prioritaire).

    @param slug: Slug echantillon
    @param base_url: Base ProspectLab (optionnel)
    @returns: URL absolue ou relative danielcraft
    """
    needle = (slug or "").strip().lower()
    if not needle:
        return ""
    rel = f"static/email/danielcraft/pub/echantillons/{needle}.jpg"
    local = _APP_ROOT / rel
    base = (base_url or "").rstrip("/")
    if local.is_file() and base:
        return f"{base}/{rel}"
    if local.is_file():
        return f"/{rel}"
    return f"https://danielcraft.fr/echantillons/{needle}/screenshots/tablet_1024x2500.webp"


_CHAR_ROOT = "static/email/danielcraft/characters"
_CHAR_LOIC = f"{_CHAR_ROOT}/dc-character-loic.jpg"
_CHAR_COMMERCE = f"{_CHAR_ROOT}/dc-character-commerce.jpg"
_CHAR_SANTE = f"{_CHAR_ROOT}/dc-character-sante.jpg"
_CHAR_ARTISAN = f"{_CHAR_ROOT}/dc-character-artisan.jpg"
_CHAR_RESTO = f"{_CHAR_ROOT}/dc-character-resto.jpg"

# Tous les personnages generes (ordre catalogue)
CHARACTER_ROSTER_ALL: tuple[str, ...] = (
    _CHAR_LOIC,
    _CHAR_COMMERCE,
    _CHAR_SANTE,
    _CHAR_ARTISAN,
    _CHAR_RESTO,
)


def _normalize_secteur_label(secteur_label: Optional[str]) -> str:
    """
    Normalise un libelle secteur pour le matching personnages.

    @param secteur_label: Secteur FR brut
    @returns: Label minuscule sans accents legers
    """
    label = (secteur_label or "").strip().lower()
    return (
        label.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ô", "o")
    )


def _existing_character_rels() -> list[str]:
    """
    Liste les personnages presents sur disque.

    @returns: Chemins relatifs existants (ordre catalogue)
    """
    return [rel for rel in CHARACTER_ROSTER_ALL if (_APP_ROOT / rel).is_file()]


def characters_pair_for_secteur(secteur_label: Optional[str] = None) -> tuple[str, str]:
    """
    Tire un duo aleatoire de personnages (gauche / droite).

    Le secteur est ignore (conserve pour compat d'appel) : on veut varier
    d'un rendu a l'autre, pas toujours le meme couple.

    @param secteur_label: Ignoré (compat)
    @returns: Tuple (rel_gauche, rel_droite) sous static/email/...
    """
    _ = secteur_label
    roster = characters_roster_for_secteur(None, count=2)
    if len(roster) >= 2:
        return (roster[0], roster[1])
    if len(roster) == 1:
        return (roster[0], roster[0])
    return (_CHAR_LOIC, _CHAR_COMMERCE)


def characters_roster_for_secteur(
    secteur_label: Optional[str] = None,
    *,
    count: int = 2,
) -> list[str]:
    """
    Tire aleatoirement N personnages distincts pour un mail.

    @param secteur_label: Ignoré (compat d'appel)
    @param count: Nombre max de chemins relatifs (2 par modele)
    @returns: Liste de chemins relatifs existants, melanges
    @example
        characters_roster_for_secteur(count=2)
        # ex. [artisan, resto] puis [sante, loic] au prochain appel
    """
    _ = secteur_label
    existing = _existing_character_rels()
    if not existing:
        return []
    n = min(max(0, int(count)), len(existing))
    if n <= 0:
        return []
    return random.sample(existing, k=n)


def character_rel_for_secteur(secteur_label: Optional[str] = None) -> str:
    """
    Compat : renvoie un personnage aleatoire (slot gauche).

    @param secteur_label: Ignoré (compat)
    @returns: Chemin relatif sous static/email/...
    """
    left, _right = characters_pair_for_secteur(secteur_label)
    return left


def build_character_email_vars(
    secteur_label: Optional[str],
    *,
    base_url: str = "",
    count: int = 2,
) -> Dict[str, Any]:
    """
    Variables email pour personnages par bloc (character_1..N + left/right).

    @param secteur_label: Secteur FR
    @param base_url: Base ProspectLab pour URLs absolues
    @param count: Nombre de slots (2 = un a gauche, un a droite)
    @returns: Dict placeholders character_*_url / has_character_*
    """
    base = (base_url or "").rstrip("/")
    roster = characters_roster_for_secteur(secteur_label, count=max(1, int(count)))
    out: Dict[str, Any] = {
        "character_count": len(roster),
        "has_character": bool(roster),
    }

    def _abs(rel: str) -> str:
        if not rel:
            return ""
        if base:
            return f"{base}/{rel}"
        return f"/{rel}"

    for idx in range(1, max(1, int(count)) + 1):
        rel = roster[idx - 1] if idx - 1 < len(roster) else ""
        url = _abs(rel) if rel else ""
        out[f"character_{idx}_rel"] = rel
        out[f"character_{idx}_url"] = url
        out[f"has_character_{idx}"] = bool(url)

    # Compat duo historique
    left_rel = roster[0] if roster else ""
    right_rel = roster[1] if len(roster) > 1 else (roster[0] if roster else "")
    out["character_left_rel"] = left_rel
    out["character_right_rel"] = right_rel
    out["character_left_url"] = _abs(left_rel) if left_rel else ""
    out["character_right_url"] = _abs(right_rel) if right_rel else ""
    out["has_character_left"] = bool(out["character_left_url"])
    out["has_character_right"] = bool(out["character_right_url"])
    out["character_rel"] = left_rel
    out["character_url"] = out["character_left_url"]
    return out


def _render_echantillon_email_card(
    *,
    titre: str,
    metier: str = "",
    demo_url: str = "",
    fiche_url: str = "",
    screenshot_url: str = "",
    cta_label: str = "Voir la démo",
    badge: str = "",
) -> str:
    """
    Carte email full-width : screenshot + titre + CTA.

    @param titre: Titre echantillon
    @param metier: Sous-titre / tagline
    @param demo_url: Lien demo principal
    @param fiche_url: Lien fiche (optionnel)
    @param screenshot_url: Image hero crop
    @param cta_label: Libelle du bouton
    @param badge: Pastille optionnelle (ex. Principale)
    @returns: HTML table email-safe
    """
    import html as html_mod

    titre_e = html_mod.escape((titre or "").strip() or "Exemple")
    metier_e = html_mod.escape((metier or "").strip())
    demo_e = html_mod.escape((demo_url or "#").strip() or "#")
    fiche_e = html_mod.escape((fiche_url or "").strip())
    shot_e = html_mod.escape((screenshot_url or "").strip())
    cta_e = html_mod.escape((cta_label or "Voir la démo").strip())
    badge_e = html_mod.escape((badge or "").strip())

    badge_html = ""
    if badge_e:
        badge_html = (
            f'<p style="margin:0 0 8px;"><span style="display:inline-block;'
            f'background:#c9f4f2;color:#0f3550;font-size:11px;font-weight:700;'
            f'letter-spacing:0.06em;text-transform:uppercase;padding:4px 8px;'
            f'border-radius:999px;">{badge_e}</span></p>'
        )

    img_html = ""
    if shot_e:
        img_html = (
            f'<a href="{demo_e}" style="text-decoration:none;">'
            f'<img src="{shot_e}" alt="{titre_e}" width="544" '
            f'style="display:block;width:100%;max-width:544px;height:auto;border:0;'
            f'background:#c9f4f2;aspect-ratio:1.618/1;" /></a>'
        )

    fiche_html = ""
    if fiche_e:
        fiche_html = (
            f'<p style="margin:10px 0 0;text-align:center;">'
            f'<a href="{fiche_e}" style="color:#4da9d6;text-decoration:underline;'
            f'font-size:13px;font-weight:600;">Voir la fiche</a></p>'
        )

    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="width:100%;border-collapse:collapse;margin:0 0 14px 0;'
        'border:1px solid #9fd4ea;border-radius:12px;overflow:hidden;background:#ffffff;">'
        f'<tr><td style="padding:0;line-height:0;font-size:0;">{img_html}</td></tr>'
        '<tr><td style="padding:14px 16px 16px;">'
        f"{badge_html}"
        f'<p style="margin:0 0 4px;color:#0f3550;font-size:16px;font-weight:700;'
        f'line-height:1.35;">{titre_e}</p>'
        f'<p style="margin:0 0 14px;color:#6b7280;font-size:13px;line-height:1.45;">'
        f'{metier_e or "Ouvrir la démo pour voir le rendu"}</p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        "<tr><td style=\"text-align:center;\">"
        f'<a href="{demo_e}" style="display:inline-block;background:linear-gradient('
        f'140deg,#9fd4ea 0%,#5faed8 28%,#2f78a6 62%,#184c70 100%);color:#ffffff;'
        f'text-decoration:none;font-size:15px;font-weight:700;padding:12px 22px;'
        f'border-radius:10px;line-height:1.2;box-shadow:0 8px 20px rgba(24,76,112,0.28);">'
        f"{cta_e}</a>"
        f"</td></tr></table>{fiche_html}"
        "</td></tr></table>"
    )


def build_echantillons_cards_html(cards: List[Dict[str, Any]]) -> str:
    """
    Assemble une galerie verticale de cartes echantillons.

    @param cards: Liste de dicts (titre, metier, demo_url, fiche_url, screenshot_url, cta_label, badge)
    @returns: HTML concatene (string vide si aucune carte)
    """
    parts: List[str] = []
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        titre = str(card.get("titre") or card.get("title") or "").strip()
        demo = str(card.get("demo_url") or "").strip()
        shot = str(card.get("screenshot_url") or "").strip()
        if not titre and not shot and not demo:
            continue
        parts.append(
            _render_echantillon_email_card(
                titre=titre,
                metier=str(card.get("metier") or card.get("tagline") or "").strip(),
                demo_url=demo,
                fiche_url=str(card.get("fiche_url") or "").strip(),
                screenshot_url=shot,
                cta_label=str(card.get("cta_label") or "Voir la démo").strip(),
                badge=str(card.get("badge") or "").strip(),
            )
        )
    return "".join(parts)


def build_related_email_vars(
    secteur: Optional[str],
    *,
    limit: int = 4,
    base_url: str = "",
) -> Dict[str, Any]:
    """
    Variables email pour echantillons proches + HTML cartes related.

    @param secteur: Secteur entreprise
    @param limit: Nombre max de related (4 par defaut pour galerie mail)
    @param base_url: Base ProspectLab pour les JPG locaux
    @returns: Dict placeholders (echantillon_2_*, related_cards_html, character_*)
    @example
        build_related_email_vars("Santé")
        # has_related_echantillons, echantillon_2_titre=...
    """
    max_related = max(0, min(int(limit), 6))
    match = match_echantillons_for_secteur(secteur, limit_related=max_related)
    related = list(match.get("related") or [])[:max_related]
    label = str(match.get("secteur_label") or "").strip()

    out: Dict[str, Any] = {
        "related_count": len(related),
        "has_related_echantillons": bool(related),
        "related_cards_html": "",
    }

    for idx in range(2, 8):
        prefix = f"echantillon_{idx}_"
        out[f"{prefix}slug"] = ""
        out[f"{prefix}titre"] = ""
        out[f"{prefix}metier"] = ""
        out[f"{prefix}demo_url"] = ""
        out[f"{prefix}fiche_url"] = ""
        out[f"{prefix}screenshot_url"] = ""
        out[f"has_echantillon_{idx}"] = False

    out.update(build_character_email_vars(label, base_url=base_url, count=2))

    related_cards: List[Dict[str, Any]] = []
    for idx, item in enumerate(related, start=2):
        slug = str(item.get("slug") or "").strip()
        titre = str(item.get("title") or slug).strip()
        metier = str(item.get("tagline") or "").strip()
        demo = str(item.get("demo_url") or "").strip()
        fiche = str(item.get("fiche_url") or "").strip()
        shot = _email_screenshot_for_slug(slug, base_url=base_url)
        prefix = f"echantillon_{idx}_"
        out[f"{prefix}slug"] = slug
        out[f"{prefix}titre"] = titre
        out[f"{prefix}metier"] = metier
        out[f"{prefix}demo_url"] = demo
        out[f"{prefix}fiche_url"] = fiche
        out[f"{prefix}screenshot_url"] = shot
        out[f"has_echantillon_{idx}"] = bool(slug)
        related_cards.append(
            {
                "titre": titre,
                "metier": metier,
                "demo_url": demo,
                "fiche_url": fiche,
                "screenshot_url": shot,
                "cta_label": "Voir la démo",
            }
        )

    out["related_cards_html"] = build_echantillons_cards_html(related_cards)
    return out


def assemble_echantillons_gallery_vars(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit la galerie complete (primaire + related + maquette) pour les mails.

    Ordre attendu dans le HTML : texte d'abord, puis ces cartes screenshot+CTA.

    @param variables: Variables template deja enrichies
    @returns: Dict has_echantillons_cards / echantillons_cards_html
    """
    cards: List[Dict[str, Any]] = []
    primary_titre = str(variables.get("echantillon_titre") or "").strip()
    primary_demo = str(
        variables.get("echantillon_demo_url") or variables.get("echantillon_url") or ""
    ).strip()
    primary_shot = str(variables.get("echantillon_screenshot_url") or "").strip()
    if primary_titre or primary_shot or primary_demo:
        cards.append(
            {
                "titre": primary_titre or "Exemple",
                "metier": str(variables.get("echantillon_metier") or "").strip(),
                "demo_url": primary_demo,
                "fiche_url": str(variables.get("echantillon_fiche_url") or "").strip(),
                "screenshot_url": primary_shot,
                "cta_label": "Voir la démo",
                "badge": "Exemple principal",
            }
        )

    for idx in range(2, 8):
        if not variables.get(f"has_echantillon_{idx}") and not variables.get(
            f"echantillon_{idx}_titre"
        ):
            continue
        cards.append(
            {
                "titre": str(variables.get(f"echantillon_{idx}_titre") or "").strip(),
                "metier": str(variables.get(f"echantillon_{idx}_metier") or "").strip(),
                "demo_url": str(variables.get(f"echantillon_{idx}_demo_url") or "").strip(),
                "fiche_url": str(variables.get(f"echantillon_{idx}_fiche_url") or "").strip(),
                "screenshot_url": str(
                    variables.get(f"echantillon_{idx}_screenshot_url") or ""
                ).strip(),
                "cta_label": "Voir la démo",
            }
        )

    # Maquette landing personnalisee (si dispo) en derniere carte
    landing_url = str(variables.get("landing_variant_url") or "").strip()
    landing_shot = str(
        variables.get("landing_variant_screenshot")
        or variables.get("landing_variant_screenshot_desktop")
        or ""
    ).strip()
    if landing_url or landing_shot:
        cards.append(
            {
                "titre": "Maquette pour votre enseigne",
                "metier": "Projection plus proche de votre site actuel",
                "demo_url": landing_url or "#",
                "fiche_url": "",
                "screenshot_url": landing_shot,
                "cta_label": "Voir la maquette",
                "badge": "Sur-mesure",
            }
        )

    html = build_echantillons_cards_html(cards)
    return {
        "echantillons_cards_html": html,
        "has_echantillons_cards": bool(html),
        "echantillons_cards_count": len(cards),
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
