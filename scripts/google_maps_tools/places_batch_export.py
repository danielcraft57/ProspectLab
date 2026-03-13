import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import requests

import importlib.util
from pathlib import Path


@dataclass(frozen=True)
class PlaceRef:
    place_id: str
    seed_query: str
    raw: Dict[str, Any]


PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def _load_places_search_module():
    here = Path(__file__).resolve()
    target = here.parent / "places_search.py"
    spec = importlib.util.spec_from_file_location("places_search", str(target))
    if spec is None or spec.loader is None:
        raise RuntimeError("Impossible de charger places_search.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ps = _load_places_search_module()


def _details(api_key: str, place_id: str, language: str, timeout_s: int) -> Dict[str, Any]:
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
    params: Dict[str, Any] = {"key": api_key, "place_id": place_id, "fields": fields, "language": language}
    data = ps._http_get(PLACES_DETAILS_URL, params=params, timeout_s=timeout_s)
    status = data.get("status")
    if status != "OK":
        raise RuntimeError(f"Details status={status} error={data.get('error_message')}")
    return data.get("result", {}) or {}


def _read_queries_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [x.strip() for x in f.readlines()]
    out = [x for x in lines if x and not x.startswith("#")]
    if not out:
        raise SystemExit("Le fichier de requetes est vide.")
    return out


def _load_cache(path: str) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(path):
        return {}
    cache: Dict[str, Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            pid = obj.get("place_id")
            if pid:
                cache[str(pid)] = obj
    return cache


def _append_cache(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False))
        f.write("\n")


def _collect_place_refs(
    api_key: str,
    queries: List[str],
    mode: str,
    location: Optional[Tuple[float, float]],
    radius: Optional[int],
    grid_step_m: int,
    grid_rings: int,
    language: str,
    region: Optional[str],
    timeout_s: int,
) -> List[PlaceRef]:
    refs: List[PlaceRef] = []
    seen: Set[str] = set()

    for q in queries:
        raw_results: List[Dict[str, Any]] = []
        if mode == "text":
            raw_results = ps._text_search(
                api_key=api_key,
                query=q,
                location=location,
                radius=radius,
                language=language,
                region=region,
                timeout_s=timeout_s,
            )
        else:
            if location is None or radius is None:
                raise SystemExit("Mode nearby-grid: donne --lat, --lng et --radius.")
            for c in ps._grid_centers(location, step_m=int(grid_step_m), rings=int(grid_rings)):
                raw_results.extend(
                    ps._nearby_search(
                        api_key=api_key,
                        keyword=q,
                        location=c,
                        radius=int(radius),
                        language=language,
                        timeout_s=timeout_s,
                    )
                )

        for r in raw_results:
            pid = r.get("place_id")
            if not pid:
                continue
            if pid in seen:
                continue
            seen.add(pid)
            refs.append(PlaceRef(place_id=str(pid), seed_query=q, raw=r))
    return refs


def _write_xlsx(path: str, rows: List[Dict[str, Any]]) -> None:
    try:
        from openpyxl import Workbook  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Export .xlsx impossible car openpyxl n'est pas installe. "
            "Installe-le avec: pip install openpyxl"
        ) from e
    wb = Workbook()
    ws = wb.active
    ws.title = "export"
    ws.append(ps.EXPORT_COLUMNS)
    for r in rows:
        ws.append([r.get(c) for c in ps.EXPORT_COLUMNS])
    wb.save(path)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Batch export Google Maps (API Places) - filtre website only.")
    p.add_argument("--out", required=True, help="Fichier .xlsx de sortie")
    p.add_argument("--query", action="append", default=[], help="Requete (tu peux en passer plusieurs)")
    p.add_argument("--queries-file", help="Fichier de requetes (1 par ligne)")
    p.add_argument(
        "--city",
        help="Ville a ajouter aux requetes (ex: Metz). Ca evite de dupliquer les fichiers de requetes.",
    )
    p.add_argument(
        "--mode",
        default="text",
        choices=["text", "nearby-grid"],
        help="text: textsearch (max ~60 par requete). nearby-grid: grille (plus large, plus cher).",
    )
    p.add_argument("--lat", type=float, help="Latitude (optionnel)")
    p.add_argument("--lng", type=float, help="Longitude (optionnel)")
    p.add_argument("--radius", type=int, help="Rayon en metres (requiert --lat et --lng)")
    p.add_argument("--grid-step-m", type=int, default=1500, help="Pas de la grille en metres (nearby-grid)")
    p.add_argument("--grid-rings", type=int, default=3, help="Nombre d'anneaux autour du centre (nearby-grid)")
    p.add_argument("--language", default="fr", help="Langue des champs (defaut: fr)")
    p.add_argument("--region", help="Code region (ex: fr)")
    p.add_argument("--timeout", type=int, default=25, help="Timeout reseau (secondes)")
    p.add_argument("--limit", type=int, default=300, help="Nb max de lignes exportees (website only)")
    p.add_argument(
        "--details-max",
        type=int,
        default=400,
        help="Nb max d'appels details (controle direct du cout).",
    )
    p.add_argument(
        "--cache",
        default="places_details_cache.jsonl",
        help="Fichier cache JSONL (place_id + champs).",
    )
    p.add_argument(
        "--category-translate",
        default="builtin",
        choices=["none", "builtin"],
        help="Traduction de category: none (type brut) ou builtin (petit mapping FR, gratuit).",
    )

    args = p.parse_args(argv)
    api_key = ps._require_api_key()

    queries: List[str] = []
    queries.extend([q.strip() for q in args.query if q and q.strip()])
    if args.queries_file:
        queries.extend(_read_queries_file(args.queries_file))
    queries = [q for q in queries if q]
    if not queries:
        raise SystemExit("Donne au moins --query ou --queries-file.")

    if args.city:
        city = args.city.strip()
        if city:
            queries = [f"{q} {city}".strip() for q in queries]

    location: Optional[Tuple[float, float]] = None
    if args.lat is not None or args.lng is not None or args.radius is not None:
        if args.lat is None or args.lng is None or args.radius is None:
            raise SystemExit("Si tu utilises --lat/--lng, donne aussi --radius (et inversement).")
        location = (float(args.lat), float(args.lng))

    cache_path = args.cache
    cache = _load_cache(cache_path)

    refs = _collect_place_refs(
        api_key=api_key,
        queries=queries,
        mode=args.mode,
        location=location,
        radius=args.radius,
        grid_step_m=int(args.grid_step_m),
        grid_rings=int(args.grid_rings),
        language=args.language,
        region=args.region,
        timeout_s=int(args.timeout),
    )

    rows: List[Dict[str, Any]] = []
    details_used = 0

    for ref in refs:
        if len(rows) >= max(0, int(args.limit)):
            break

        cached = cache.get(ref.place_id)
        if cached:
            item = cached
        else:
            if details_used >= max(0, int(args.details_max)):
                break
            d = _details(api_key=api_key, place_id=ref.place_id, language=args.language, timeout_s=int(args.timeout))
            item = ps._normalize(d)
            cache[ref.place_id] = item
            _append_cache(cache_path, item)
            details_used += 1

        website = (item.get("website") or "").strip() if isinstance(item.get("website"), str) else ""
        if not website:
            continue

        rows.append(ps._to_export_row(item, category_translate_mode=args.category_translate))

    _write_xlsx(args.out, rows)

    sys.stdout.write(
        json.dumps(
            {
                "queries_count": len(queries),
                "places_seen": len(refs),
                "exported": len(rows),
                "details_used": details_used,
                "cache_path": cache_path,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

