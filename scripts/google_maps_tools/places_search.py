import argparse
import json
import os
import sys
import math
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import requests


PLACES_TEXTSEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_NEARBYSEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

RETRYABLE_STATUSES = {"OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED", "UNKNOWN_ERROR"}

EXPORT_COLUMNS = [
    "name",
    "website",
    "category",
    "phone_number",
    "country",
    "address_1",
    "address_2",
    "longitude",
    "latitude",
    "rating",
    "reviews_count",
    "category_translate",
]

TYPE_FR_MAP: Dict[str, str] = {
    # --- Services / artisans ---
    "plumber": "plombier",
    "electrician": "electricien",
    "locksmith": "serrurier",
    "general_contractor": "entreprise de travaux",
    "roofing_contractor": "couvreur",
    "moving_company": "demenageur",
    "painter": "peintre",

    # --- Restauration / sorties ---
    "restaurant": "restaurant",
    "bar": "bar",
    "cafe": "cafe",
    "bakery": "boulangerie",
    "meal_takeaway": "a emporter",
    "meal_delivery": "livraison de repas",
    "night_club": "boite de nuit",

    # --- Sante ---
    "doctor": "medecin",
    "dentist": "dentiste",
    "hospital": "hopital",
    "pharmacy": "pharmacie",
    "drugstore": "parapharmacie",
    "physiotherapist": "kinesitherapeute",
    "veterinary_care": "veterinaire",

    # --- Finance / juridique / pro ---
    "accounting": "expert-comptable",
    "bank": "banque",
    "atm": "distributeur",
    "insurance_agency": "assurance",
    "lawyer": "avocat",
    "real_estate_agency": "agence immobiliere",

    # --- Beaute / bien-etre ---
    "hair_care": "coiffeur",
    "beauty_salon": "institut de beaute",
    "spa": "spa",
    "gym": "salle de sport",

    # --- Auto / transport ---
    "car_dealer": "concessionnaire auto",
    "car_repair": "garage",
    "car_rental": "location de voiture",
    "car_wash": "lavage auto",
    "gas_station": "station service",
    "parking": "parking",
    "taxi_stand": "station taxi",
    "bus_station": "gare routiere",
    "train_station": "gare",
    "subway_station": "metro",
    "light_rail_station": "tramway",
    "transit_station": "station transport",
    "airport": "aeroport",

    # --- Commerces ---
    "store": "magasin",
    "supermarket": "supermarche",
    "convenience_store": "epicerie",
    "department_store": "grand magasin",
    "shopping_mall": "centre commercial",
    "hardware_store": "quincaillerie",
    "home_goods_store": "magasin maison",
    "furniture_store": "magasin meubles",
    "electronics_store": "magasin electronique",
    "clothing_store": "magasin vetements",
    "shoe_store": "magasin chaussures",
    "jewelry_store": "bijouterie",
    "book_store": "librairie",
    "florist": "fleuriste",
    "pet_store": "animalerie",
    "liquor_store": "caviste",
    "laundry": "laverie",
    "storage": "garde-meubles",

    # --- Culture / loisirs / tourisme ---
    "tourist_attraction": "attraction touristique",
    "museum": "musee",
    "art_gallery": "galerie d'art",
    "movie_theater": "cinema",
    "bowling_alley": "bowling",
    "amusement_park": "parc d'attractions",
    "aquarium": "aquarium",
    "zoo": "zoo",
    "park": "parc",
    "stadium": "stade",

    # --- Education ---
    "school": "ecole",
    "primary_school": "ecole primaire",
    "secondary_school": "college/lycee",
    "university": "universite",
    "library": "bibliotheque",

    # --- Administration / services publics ---
    "city_hall": "mairie",
    "courthouse": "tribunal",
    "police": "police",
    "fire_station": "pompiers",
    "post_office": "poste",
    "local_government_office": "administration",

    # --- Culte ---
    "church": "eglise",
    "mosque": "mosquee",
    "synagogue": "synagogue",
    "hindu_temple": "temple hindou",

    # --- Hebergement / voyage ---
    "lodging": "hotel",
    "travel_agency": "agence de voyage",

    # --- Generiques ---
    "point_of_interest": "point d'interet",
    "establishment": "etablissement",
}


def _require_api_key() -> str:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Il manque GOOGLE_MAPS_API_KEY dans tes variables d'environnement.")
    return api_key


def _http_get(
    url: str,
    params: Dict[str, Any],
    timeout_s: int,
    max_retries: int = 6,
    backoff_s: float = 2.0,
) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(max(1, int(max_retries))):
        try:
            r = requests.get(url, params=params, timeout=timeout_s)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            last_error = e
            sleep_s = backoff_s * (2**attempt)
            time.sleep(min(60.0, sleep_s))
            continue

        status = data.get("status")
        if status in RETRYABLE_STATUSES:
            sleep_s = backoff_s * (2**attempt)
            time.sleep(min(90.0, sleep_s))
            last_error = RuntimeError(f"Google status={status} error={data.get('error_message')}")
            continue

        return data

    if last_error:
        raise last_error
    raise RuntimeError("Echec requete Google Places (raison inconnue).")


def _paginated_search(url: str, params: Dict[str, Any], timeout_s: int, max_pages: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    page = 0
    next_token: Optional[str] = None
    while page < max_pages:
        page_params = dict(params)
        if next_token:
            time.sleep(2.0)
            page_params["pagetoken"] = next_token

        data = _http_get(url, params=page_params, timeout_s=timeout_s)
        status = data.get("status")
        if status == "INVALID_REQUEST" and next_token:
            time.sleep(2.0)
            data = _http_get(url, params=page_params, timeout_s=timeout_s)
            status = data.get("status")

        if status in {"OK", "ZERO_RESULTS"}:
            out.extend(data.get("results", []) or [])
        else:
            raise RuntimeError(f"Search status={status} error={data.get('error_message')}")

        next_token = data.get("next_page_token")
        page += 1
        if not next_token:
            break
    return out


def _text_search(
    api_key: str,
    query: str,
    location: Optional[Tuple[float, float]],
    radius: Optional[int],
    language: str,
    region: Optional[str],
    timeout_s: int,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "key": api_key,
        "query": query,
        "language": language,
    }
    if region:
        params["region"] = region
    if location and radius:
        params["location"] = f"{location[0]},{location[1]}"
        params["radius"] = int(radius)
    return _paginated_search(PLACES_TEXTSEARCH_URL, params=params, timeout_s=timeout_s, max_pages=3)


def _nearby_search(
    api_key: str,
    keyword: str,
    location: Tuple[float, float],
    radius: int,
    language: str,
    timeout_s: int,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "key": api_key,
        "keyword": keyword,
        "location": f"{location[0]},{location[1]}",
        "radius": int(radius),
        "language": language,
    }
    return _paginated_search(PLACES_NEARBYSEARCH_URL, params=params, timeout_s=timeout_s, max_pages=3)


def _details(
    api_key: str,
    place_id: str,
    language: str,
    timeout_s: int,
) -> Dict[str, Any]:
    fields = ",".join(
        [
            "place_id",
            "name",
            "formatted_address",
            "geometry",
            "international_phone_number",
            "website",
            "rating",
            "user_ratings_total",
            "types",
            "opening_hours",
            "url",
        ]
    )
    params: Dict[str, Any] = {
        "key": api_key,
        "place_id": place_id,
        "fields": fields,
        "language": language,
    }
    data = _http_get(PLACES_DETAILS_URL, params=params, timeout_s=timeout_s)
    status = data.get("status")
    if status != "OK":
        raise RuntimeError(f"Details status={status} error={data.get('error_message')}")
    return data.get("result", {}) or {}


def _normalize(details: Dict[str, Any]) -> Dict[str, Any]:
    geo = (details.get("geometry") or {}).get("location") or {}
    opening = details.get("opening_hours") or {}
    return {
        "name": details.get("name"),
        "place_id": details.get("place_id"),
        "formatted_address": details.get("formatted_address"),
        "location": {"lat": geo.get("lat"), "lng": geo.get("lng")},
        "phone": details.get("international_phone_number"),
        "website": details.get("website"),
        "rating": details.get("rating"),
        "user_ratings_total": details.get("user_ratings_total"),
        "types": details.get("types") or [],
        "opening_hours": opening.get("weekday_text") or None,
        "google_maps_url": details.get("url"),
    }


def _normalize_search_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    geo = (raw.get("geometry") or {}).get("location") or {}
    return {
        "name": raw.get("name"),
        "place_id": raw.get("place_id"),
        "formatted_address": raw.get("formatted_address") or raw.get("vicinity"),
        "location": {"lat": geo.get("lat"), "lng": geo.get("lng")},
        "phone": None,
        "website": None,
        "rating": raw.get("rating"),
        "user_ratings_total": raw.get("user_ratings_total"),
        "types": raw.get("types") or [],
        "opening_hours": None,
        "google_maps_url": None,
    }


def _grid_centers(center: Tuple[float, float], step_m: int, rings: int) -> Iterable[Tuple[float, float]]:
    lat0, lng0 = center
    m_per_deg_lat = 111_320.0
    m_per_deg_lng = 111_320.0 * max(0.2, math.cos(math.radians(lat0)))
    step_lat = float(step_m) / m_per_deg_lat
    step_lng = float(step_m) / m_per_deg_lng

    for dy in range(-rings, rings + 1):
        for dx in range(-rings, rings + 1):
            yield (lat0 + dy * step_lat, lng0 + dx * step_lng)


def _parse_address(formatted_address: Optional[str]) -> Dict[str, Optional[str]]:
    if not formatted_address:
        return {"country": None, "address_1": None, "address_2": None}
    parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
    if not parts:
        return {"country": None, "address_1": formatted_address.strip(), "address_2": None}
    if len(parts) == 1:
        return {"country": None, "address_1": parts[0], "address_2": None}
    country = parts[-1]
    address_1 = parts[0]
    address_2 = ", ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
    return {"country": country, "address_1": address_1, "address_2": address_2}


def _category_from_types(types_list: List[str]) -> Optional[str]:
    if not types_list:
        return None
    for t in types_list:
        if t not in {"point_of_interest", "establishment"}:
            return t
    return types_list[0]


def _translate_category(category: Optional[str], mode: str) -> Optional[str]:
    if not category:
        return None
    if mode == "none":
        return category
    direct = TYPE_FR_MAP.get(category)
    if direct:
        return direct
    # Heuristique: couvre la majorité des Place Types Google en évitant une liste infinie.
    t = str(category).strip().lower()
    if not t:
        return category

    # Types génériques (Table B / tags)
    generic_map = {
        "food": "alimentation",
        "health": "sante",
        "finance": "finance",
        "place_of_worship": "lieu de culte",
        "natural_feature": "site naturel",
        "landmark": "monument",
        "geocode": "adresse",
        "political": "zone administrative",
    }
    if t in generic_map:
        return generic_map[t]

    # Suffixes / patterns fréquents
    if t.endswith("_restaurant"):
        base = t[: -len("_restaurant")].replace("_", " ").strip()
        if not base:
            return "restaurant"
        # Ex: "mexican restaurant" -> "restaurant mexicain"
        return f"restaurant {base}"

    if t.endswith("_store") or t.endswith("_shop"):
        base = t.rsplit("_", 1)[0].replace("_", " ").strip()
        return f"magasin {base}" if base else "magasin"

    if t.endswith("_clinic"):
        base = t[: -len("_clinic")].replace("_", " ").strip()
        return f"clinique {base}" if base else "clinique"

    if t.endswith("_hospital"):
        base = t[: -len("_hospital")].replace("_", " ").strip()
        return f"hopital {base}" if base else "hopital"

    if t.endswith("_school"):
        base = t[: -len("_school")].replace("_", " ").strip()
        return f"ecole {base}" if base else "ecole"

    if t.endswith("_station"):
        base = t[: -len("_station")].replace("_", " ").strip()
        return f"station {base}" if base else "station"

    if t.endswith("_office"):
        base = t[: -len("_office")].replace("_", " ").strip()
        return f"bureau {base}" if base else "bureau"

    if t.endswith("_center") or t.endswith("_centre"):
        base = t.rsplit("_", 1)[0].replace("_", " ").strip()
        return f"centre {base}" if base else "centre"

    if t.endswith("_service"):
        base = t[: -len("_service")].replace("_", " ").strip()
        return f"service {base}" if base else "service"

    # Fallback lisible (au lieu de l'anglais brut avec underscores)
    return t.replace("_", " ")


def _to_export_row(item: Dict[str, Any], category_translate_mode: str) -> Dict[str, Any]:
    loc = item.get("location") or {}
    types_list = item.get("types") or []
    category = _category_from_types(types_list)
    addr = _parse_address(item.get("formatted_address"))
    return {
        "name": item.get("name"),
        "website": item.get("website"),
        "category": category,
        "phone_number": item.get("phone"),
        "country": addr.get("country"),
        "address_1": addr.get("address_1"),
        "address_2": addr.get("address_2"),
        "longitude": loc.get("lng"),
        "latitude": loc.get("lat"),
        "rating": item.get("rating"),
        "reviews_count": item.get("user_ratings_total"),
        "category_translate": _translate_category(category, mode=category_translate_mode),
    }


def _write_xlsx(path: str, rows: List[Dict[str, Any]]) -> None:
    try:
        from openpyxl import Workbook  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Export .xlsx impossible car openpyxl n'est pas installe. "
            "Installe-le ou exporte en .json. Exemple: pip install openpyxl"
        ) from e
    wb = Workbook()
    ws = wb.active
    ws.title = "export"
    ws.append(EXPORT_COLUMNS)
    for r in rows:
        ws.append([r.get(c) for c in EXPORT_COLUMNS])
    wb.save(path)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="POC: recuperer des champs Google Maps via l'API Places (stable).")
    p.add_argument("--query", required=True, help="Requete de recherche (ex: 'plombier lyon')")
    p.add_argument("--limit", type=int, default=10, help="Nombre max de resultats")
    p.add_argument("--out", help="Fichier de sortie (.json ou .xlsx). Sinon: stdout (json).")
    p.add_argument(
        "--mode",
        default="text",
        choices=["text", "nearby-grid"],
        help="text: textsearch (max 60). nearby-grid: decoupe la zone en grille (pour depasser 60).",
    )
    p.add_argument(
        "--details",
        default="none",
        choices=["none", "all", "limit"],
        help="none: pas d'appel details (moins cher). all: details pour tout. limit: details pour les N premiers.",
    )
    p.add_argument(
        "--details-limit",
        type=int,
        default=50,
        help="En mode --details limit, nombre max d'appels details.",
    )
    p.add_argument(
        "--category-translate",
        default="builtin",
        choices=["none", "builtin"],
        help="Traduction de category: none (type brut) ou builtin (petit mapping FR, gratuit).",
    )
    p.add_argument("--lat", type=float, help="Latitude (optionnel)")
    p.add_argument("--lng", type=float, help="Longitude (optionnel)")
    p.add_argument("--radius", type=int, help="Rayon en metres (requiert --lat et --lng)")
    p.add_argument("--grid-step-m", type=int, default=1500, help="Pas de la grille en metres (nearby-grid)")
    p.add_argument("--grid-rings", type=int, default=3, help="Nombre d'anneaux autour du centre (nearby-grid)")
    p.add_argument("--language", default="fr", help="Langue des champs (defaut: fr)")
    p.add_argument("--region", help="Code region (ex: fr)")
    p.add_argument("--timeout", type=int, default=25, help="Timeout reseau (secondes)")

    args = p.parse_args(argv)
    api_key = _require_api_key()

    location: Optional[Tuple[float, float]] = None
    if args.lat is not None or args.lng is not None or args.radius is not None:
        if args.lat is None or args.lng is None or args.radius is None:
            raise SystemExit("Si tu utilises --lat/--lng, donne aussi --radius (et inversement).")
        location = (float(args.lat), float(args.lng))

    raw_results: List[Dict[str, Any]] = []
    if args.mode == "text":
        raw_results = _text_search(
            api_key=api_key,
            query=args.query,
            location=location,
            radius=args.radius,
            language=args.language,
            region=args.region,
            timeout_s=args.timeout,
        )
    else:
        if location is None or args.radius is None:
            raise SystemExit("Mode nearby-grid: donne --lat, --lng et --radius.")
        for c in _grid_centers(location, step_m=int(args.grid_step_m), rings=int(args.grid_rings)):
            raw_results.extend(
                _nearby_search(
                    api_key=api_key,
                    keyword=args.query,
                    location=c,
                    radius=int(args.radius),
                    language=args.language,
                    timeout_s=args.timeout,
                )
            )

    items: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    details_budget = 0
    max_details = 0
    if args.details == "all":
        max_details = 10**9
    elif args.details == "limit":
        max_details = max(0, int(args.details_limit))

    for r in raw_results:
        place_id = r.get("place_id")
        if not place_id:
            continue
        if place_id in seen:
            continue
        seen.add(place_id)

        if max_details > 0 and details_budget < max_details:
            d = _details(api_key=api_key, place_id=place_id, language=args.language, timeout_s=args.timeout)
            items.append(_normalize(d))
            details_budget += 1
        else:
            items.append(_normalize_search_item(r))
        if len(items) >= max(0, int(args.limit)):
            break

    payload = {
        "query": args.query,
        "mode": args.mode,
        "details": args.details,
        "details_used": details_budget,
        "raw_count": len(raw_results),
        "unique_count": len(seen),
        "count": len(items),
        "items": items,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.out:
        if args.out.lower().endswith(".xlsx"):
            rows = [_to_export_row(x, category_translate_mode=args.category_translate) for x in items]
            _write_xlsx(args.out, rows)
        else:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
                f.write("\n")
        return 0

    sys.stdout.write(text)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

