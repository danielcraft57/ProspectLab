"""
Extraction d'adresse / CP / ville / téléphone / geo depuis le HTML (JSON-LD, microdonnées, heuristiques FR).
Géocodage optionnel via geopy + Nominatim (désactivé par défaut, voir SCRAPING_GEOCODE_NOMINATIM).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_INTERESTING_LD_TYPES: Set[str] = {
    'organization', 'localbusiness', 'store', 'place', 'foodestablishment',
    'professionalservice', 'corporation', 'governmentorganization', 'lodgingbusiness',
    'automotivebusiness', 'homegoodsstore', 'sportsgoodsstore', 'touristattraction',
}

_CONTACT_PATH_FRAGMENTS = (
    'contact', 'nous-contacter', 'mentions', 'legal', 'imprint', 'adresse',
    'localisation', 'locaux', 'siege', 'siege-social', 'about', 'qui-sommes',
)

_FR_CP_LINE = re.compile(
    r"\b(\d{5})\s+([A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇa-zàâäéèêëîïôöùûüç][A-Za-zÀ-ÿ0-9'\-\s]{1,42})\b",
    re.UNICODE,
)


def _env_truthy(name: str, default: bool = False) -> bool:
    v = (os.environ.get(name) or '').strip().lower()
    if not v:
        return default
    return v in ('1', 'true', 'yes', 'on')


def _types_of(node: dict) -> Set[str]:
    t = node.get('@type')
    if isinstance(t, list):
        return {str(x).lower() for x in t if x}
    if isinstance(t, str):
        return {t.lower()}
    return set()


def _flatten_jsonld_nodes(data: Any) -> List[dict]:
    out: List[dict] = []
    if isinstance(data, list):
        for x in data:
            out.extend(_flatten_jsonld_nodes(x))
        return out
    if isinstance(data, dict):
        if '@graph' in data:
            out.extend(_flatten_jsonld_nodes(data['@graph']))
        else:
            out.append(data)
    return out


def _as_address_dict(addr: Any) -> Optional[dict]:
    if isinstance(addr, dict):
        return addr
    if isinstance(addr, str) and addr.strip():
        return {'streetAddress': addr.strip()}
    if isinstance(addr, list) and addr:
        first = addr[0]
        if isinstance(first, dict):
            return first
        if isinstance(first, str) and first.strip():
            return {'streetAddress': first.strip()}
    return None


def _norm_phone(raw: Optional[str]) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    s = re.sub(r'[\s.\-]', '', raw.strip())
    if len(s) < 8:
        return None
    return raw.strip()[:80]


def _geo_from_node(node: dict) -> tuple[Optional[float], Optional[float]]:
    geo = node.get('geo')
    if isinstance(geo, list) and geo:
        geo = geo[0]
    if not isinstance(geo, dict):
        return None, None
    lat = geo.get('latitude') or geo.get('lat')
    lng = geo.get('longitude') or geo.get('lng')
    try:
        la = float(lat) if lat is not None else None
    except (TypeError, ValueError):
        la = None
    try:
        lo = float(lng) if lng is not None else None
    except (TypeError, ValueError):
        lo = None
    if la is not None and lo is not None and (-90 <= la <= 90) and (-180 <= lo <= 180):
        return la, lo
    return None, None


def _phones_from_node(node: dict) -> List[str]:
    found: List[str] = []
    for key in ('telephone', 'phone', 'faxNumber'):
        v = node.get(key)
        if isinstance(v, str):
            p = _norm_phone(v)
            if p:
                found.append(p)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, str):
                    p = _norm_phone(x)
                    if p:
                        found.append(p)
    cps = node.get('contactPoint')
    if isinstance(cps, dict):
        cps = [cps]
    if isinstance(cps, list):
        for cp in cps:
            if isinstance(cp, dict):
                for key in ('telephone', 'phone'):
                    v = cp.get(key)
                    if isinstance(v, str):
                        p = _norm_phone(v)
                        if p and p not in found:
                            found.append(p)
    return found


def _hit_from_postal_dict(
    d: dict,
    page_url: str,
    depth: int,
    *,
    source: str,
    parent_phone: Optional[str] = None,
    parent_geo: tuple[Optional[float], Optional[float]] = (None, None),
) -> Optional[Dict[str, Any]]:
    street = d.get('streetAddress') or d.get('streetaddress')
    pc = d.get('postalCode') or d.get('postalcode')
    locality = d.get('addressLocality') or d.get('addresslocality')
    country = d.get('addressCountry') or d.get('addresscountry')
    if isinstance(country, dict):
        country = country.get('name') or country.get('@id')
    if isinstance(country, str):
        country = country.strip()[:80] or None

    if isinstance(street, str):
        street = street.strip() or None
    else:
        street = None
    if isinstance(pc, str):
        pc = pc.strip()
        if not re.match(r'^\d{5}$', pc):
            pc = None
    else:
        pc = None
    if isinstance(locality, str):
        locality = re.sub(r'\s+', ' ', locality.strip())
        if len(locality) < 2:
            locality = None
    else:
        locality = None

    if not (street or pc or locality):
        return None

    score = 35
    if pc and locality:
        score += 40
    elif pc or locality:
        score += 15
    if street:
        score += 12
    if any(x in page_url.lower() for x in _CONTACT_PATH_FRAGMENTS):
        score += 18
    if depth <= 1:
        score += 6
    if source.startswith('json_ld'):
        score += 10

    la, lo = parent_geo
    tel = parent_phone

    hit: Dict[str, Any] = {
        'source': source,
        'page_url': page_url,
        'depth': depth,
        'street_address': street,
        'postal_code': pc,
        'locality': locality,
        'country': country,
        'telephone': tel,
        'latitude': la,
        'longitude': lo,
        'score': score,
    }
    return hit


def _location_from_jsonld_node(node: dict, page_url: str, depth: int) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    types = _types_of(node)
    la, lo = _geo_from_node(node)
    phones = _phones_from_node(node)
    parent_phone = phones[0] if phones else None

    if 'postaladdress' in types:
        h = _hit_from_postal_dict(
            node, page_url, depth, source='json_ld_postal',
            parent_phone=parent_phone, parent_geo=(la, lo),
        )
        if h:
            hits.append(h)
        return hits

    addr_raw = node.get('address')
    if addr_raw:
        addr_dict = _as_address_dict(addr_raw)
        if addr_dict:
            inner_types = _types_of(addr_dict)
            if 'postaladdress' in inner_types or addr_dict.get('postalCode') or addr_dict.get('streetAddress'):
                h = _hit_from_postal_dict(
                    addr_dict, page_url, depth, source='json_ld_org_address',
                    parent_phone=parent_phone, parent_geo=(la, lo),
                )
                if h:
                    hits.append(h)
            elif isinstance(addr_raw, str) and addr_raw.strip():
                h = _hit_from_postal_dict(
                    {'streetAddress': addr_raw.strip()}, page_url, depth, source='json_ld_org_address_str',
                    parent_phone=parent_phone, parent_geo=(la, lo),
                )
                if h:
                    hits.append(h)

    if types & _INTERESTING_LD_TYPES and (la is not None or parent_phone):
        # Adresse déjà gérée ci-dessus ; si seulement geo/tel, créer une entrée minimale
        if not hits and (la is not None and lo is not None or parent_phone):
            score = 25 + (20 if la is not None else 0) + (10 if parent_phone else 0)
            if any(x in page_url.lower() for x in _CONTACT_PATH_FRAGMENTS):
                score += 15
            hits.append({
                'source': 'json_ld_org_geo',
                'page_url': page_url,
                'depth': depth,
                'street_address': None,
                'postal_code': None,
                'locality': None,
                'country': None,
                'telephone': parent_phone,
                'latitude': la,
                'longitude': lo,
                'score': score,
            })
    return hits


def _location_from_microdata(soup, page_url: str, depth: int) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    street_el = soup.find(attrs={'itemprop': re.compile(r'^streetAddress$', re.I)})
    pc_el = soup.find(attrs={'itemprop': re.compile(r'^postalCode$', re.I)})
    loc_el = soup.find(attrs={'itemprop': re.compile(r'^addressLocality$', re.I)})
    country_el = soup.find(attrs={'itemprop': re.compile(r'^addressCountry$', re.I)})
    if not (street_el or pc_el or loc_el):
        return hits
    d: dict = {}
    if street_el:
        d['streetAddress'] = street_el.get_text(' ', strip=True)
    if pc_el:
        d['postalCode'] = pc_el.get_text(strip=True)
    if loc_el:
        d['addressLocality'] = loc_el.get_text(strip=True)
    if country_el:
        d['addressCountry'] = country_el.get_text(strip=True)
    h = _hit_from_postal_dict(d, page_url, depth, source='microdata', parent_phone=None, parent_geo=(None, None))
    if h:
        h['score'] = h.get('score', 0) + 5
        hits.append(h)
    return hits


def _meta_first_content(soup, matchers: List[tuple]) -> Optional[str]:
    """matchers: list of (attr_name, value_or_regex) pour <meta>."""
    for attr, val in matchers:
        if hasattr(val, 'match'):
            m = soup.find('meta', attrs={attr: val})
        else:
            m = soup.find('meta', attrs={attr: val})
        if m and m.get('content'):
            s = str(m['content']).strip()
            if s:
                return s
    return None


def _parse_lat_lng_pair(raw: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    if not raw or not isinstance(raw, str):
        return None, None
    s = raw.strip()
    for sep in (';', ','):
        if sep in s:
            parts = [p.strip() for p in s.split(sep, 1)]
            if len(parts) == 2:
                try:
                    la, lo = float(parts[0]), float(parts[1])
                    if -90 <= la <= 90 and -180 <= lo <= 180:
                        return la, lo
                except (TypeError, ValueError):
                    pass
    return None, None


def _location_from_og_geo_rdfa(soup, page_url: str, depth: int) -> List[Dict[str, Any]]:
    """Open Graph (lieu), méta geo classiques, RDFa schema.org sur adresse."""
    hits: List[Dict[str, Any]] = []

    street = _meta_first_content(soup, [
        ('property', re.compile(r'^og:street-address$', re.I)),
        ('property', re.compile(r'^business:contact_data:street_address$', re.I)),
    ])
    locality = _meta_first_content(soup, [
        ('property', re.compile(r'^og:locality$', re.I)),
    ])
    pc = _meta_first_content(soup, [
        ('property', re.compile(r'^og:postal-code$', re.I)),
    ])
    country = _meta_first_content(soup, [
        ('property', re.compile(r'^og:country-name$', re.I)),
    ])
    region = _meta_first_content(soup, [
        ('property', re.compile(r'^og:region$', re.I)),
    ])

    og_lat = _meta_first_content(soup, [('property', re.compile(r'^og:latitude$', re.I))])
    og_lng = _meta_first_content(soup, [('property', re.compile(r'^og:longitude$', re.I))])
    la, lo = None, None
    if og_lat and og_lng:
        try:
            la, lo = float(og_lat), float(og_lng)
            if not (-90 <= la <= 90 and -180 <= lo <= 180):
                la, lo = None, None
        except (TypeError, ValueError):
            la, lo = None, None

    placename = _meta_first_content(soup, [('name', re.compile(r'^geo\.placename$', re.I))])
    geo_region = _meta_first_content(soup, [('name', re.compile(r'^geo\.region$', re.I))])
    geo_pos = _meta_first_content(soup, [
        ('name', re.compile(r'^geo\.position$', re.I)),
        ('name', re.compile(r'^ICBM$', re.I)),
    ])
    if la is None:
        la, lo = _parse_lat_lng_pair(geo_pos)

    d: Dict[str, Any] = {}
    if street:
        d['streetAddress'] = street
    if pc:
        pc_s = re.sub(r'\s+', '', str(pc))[:12]
        if re.match(r'^\d{5}$', pc_s):
            d['postalCode'] = pc_s
        else:
            m = re.search(r'\d{5}', str(pc))
            if m:
                d['postalCode'] = m.group(0)
    loc_val = locality or placename
    if loc_val:
        d['addressLocality'] = loc_val
    if country:
        d['addressCountry'] = country
    if geo_region and 'addressLocality' not in d:
        gr = geo_region.strip()
        if gr and not re.match(r'^[A-Z]{2}(-[A-Z0-9]+)?$', gr.replace(' ', '')):
            d['addressLocality'] = gr
    if region and not d.get('addressLocality'):
        d['addressLocality'] = region

    if d.get('streetAddress') or d.get('postalCode') or d.get('addressLocality'):
        h = _hit_from_postal_dict(
            dict(d),
            page_url,
            depth,
            source='og_geo_meta',
            parent_phone=None,
            parent_geo=(la, lo),
        )
        if h:
            h['score'] = int(h.get('score', 0)) + 12
            hits.append(h)
    elif la is not None and lo is not None:
        hits.append({
            'source': 'og_geo_meta',
            'page_url': page_url,
            'depth': depth,
            'street_address': None,
            'postal_code': None,
            'locality': placename,
            'country': None,
            'telephone': None,
            'latitude': la,
            'longitude': lo,
            'score': 38,
        })

    # RDFa / microformats : property contenant streetAddress, etc. (héritage schema.org)
    rdfa_bucket: Dict[str, str] = {}
    for el in soup.find_all(True, attrs={'property': True}):
        prop = el.get('property')
        if isinstance(prop, list):
            prop = prop[0] if prop else ''
        p = str(prop).strip()
        if not p:
            continue
        tail = p.split(':')[-1].lower().replace('-', '')
        txt = el.get_text(' ', strip=True)
        if not txt:
            continue
        if tail == 'streetaddress':
            rdfa_bucket['streetAddress'] = txt
        elif tail == 'postalcode':
            rdfa_bucket['postalCode'] = txt
        elif tail == 'addresslocality':
            rdfa_bucket['addressLocality'] = txt
        elif tail == 'addresscountry':
            rdfa_bucket['addressCountry'] = txt

    if rdfa_bucket and (rdfa_bucket.get('streetAddress') or rdfa_bucket.get('postalCode') or rdfa_bucket.get('addressLocality')):
        h2 = _hit_from_postal_dict(
            rdfa_bucket,
            page_url,
            depth,
            source='rdfa_address',
            parent_phone=None,
            parent_geo=(None, None),
        )
        if h2:
            h2['score'] = int(h2.get('score', 0)) + 8
            hits.append(h2)

    return hits


def _location_from_text_regex(page_url: str, depth: int, text: str) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    if not text:
        return hits
    best = None
    best_score = 0
    for m in _FR_CP_LINE.finditer(text):
        pc, city = m.group(1), m.group(2).strip()
        if len(city) > 45 or any(c.isdigit() for c in city):
            continue
        score = 22
        if any(x in page_url.lower() for x in _CONTACT_PATH_FRAGMENTS):
            score += 25
        if depth <= 1:
            score += 8
        if score > best_score:
            best_score = score
            best = {'postal_code': pc, 'locality': city, 'score': score}
    if best:
        hits.append({
            'source': 'regex_fr_cp',
            'page_url': page_url,
            'depth': depth,
            'street_address': None,
            'postal_code': best['postal_code'],
            'locality': best['locality'],
            'country': 'France',
            'telephone': None,
            'latitude': None,
            'longitude': None,
            'score': best['score'],
        })
    return hits


def harvest_locations_from_page(soup, page_url: str, depth: int) -> List[Dict[str, Any]]:
    """Retourne 0..n indices de localisation pour une page."""
    hits: List[Dict[str, Any]] = []

    for script in soup.find_all('script', attrs={'type': lambda x: x and 'ld+json' in x.lower()}):
        raw = (script.string or script.get_text() or '').strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _flatten_jsonld_nodes(data):
            if isinstance(node, dict):
                hits.extend(_location_from_jsonld_node(node, page_url, depth))

    hits.extend(_location_from_microdata(soup, page_url, depth))
    hits.extend(_location_from_og_geo_rdfa(soup, page_url, depth))

    text = soup.get_text('\n', strip=True)
    hits.extend(_location_from_text_regex(page_url, depth, text))

    return hits


def _build_geocode_query(loc: Dict[str, Any]) -> Optional[str]:
    parts: List[str] = []
    if loc.get('street_address'):
        parts.append(str(loc['street_address']))
    tail = ' '.join(x for x in (loc.get('postal_code'), loc.get('locality')) if x)
    if tail:
        parts.append(tail)
    country = loc.get('country') or 'France'
    parts.append(country)
    q = ', '.join(p for p in parts if p)
    return q if len(q) >= 8 else None


def _nominatim_geocode(query: str) -> tuple[Optional[float], Optional[float]]:
    if not _env_truthy('SCRAPING_GEOCODE_NOMINATIM', False):
        return None, None
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    except ImportError:
        logger.warning('geopy non installé : impossible de géocoder (pip install geopy)')
        return None, None

    ua = (os.environ.get('PROSPECTLAB_NOMINATIM_UA') or '').strip() or 'ProspectLab/1.0 (contact: dev@localhost)'
    time.sleep(1.05)  # politique d’usage Nominatim : ~1 req/s
    try:
        nom = Nominatim(user_agent=ua, timeout=12)
        location = nom.geocode(query, language='fr')
        if location:
            return float(location.latitude), float(location.longitude)
    except (GeocoderTimedOut, GeocoderServiceError, OSError) as e:
        logger.info('Géocodage Nominatim ignoré: %s', e)
    except Exception as e:
        logger.warning('Géocodage Nominatim erreur: %s', e)
    return None, None


def finalize_scraped_location(hits: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Choisit le meilleur indice, fusionne geo/tél des autres, géocode si activé.
    Retourne un dict normalisé pour la BDD / metadata (sans champ score).
    """
    if not hits:
        return None

    def sort_key(h: Dict[str, Any]):
        return (-int(h.get('score') or 0), -len(h.get('street_address') or ''))

    ordered = sorted(hits, key=sort_key)
    best = dict(ordered[0])
    for h in ordered[1:]:
        if not best.get('latitude') and h.get('latitude') is not None:
            best['latitude'] = h.get('latitude')
            best['longitude'] = h.get('longitude')
        if not best.get('telephone') and h.get('telephone'):
            best['telephone'] = h['telephone']
        if not best.get('street_address') and h.get('street_address'):
            best['street_address'] = h['street_address']
        if not best.get('postal_code') and h.get('postal_code'):
            best['postal_code'] = h['postal_code']
        if not best.get('locality') and h.get('locality'):
            best['locality'] = h['locality']
        if not best.get('country') and h.get('country'):
            best['country'] = h['country']

    if best.get('latitude') is None:
        q = _build_geocode_query(best)
        if q:
            la, lo = _nominatim_geocode(q)
            if la is not None:
                best['latitude'] = la
                best['longitude'] = lo
                best['geocoded'] = True

    out = {
        'source': best.get('source'),
        'page_url': best.get('page_url'),
        'street_address': best.get('street_address'),
        'postal_code': best.get('postal_code'),
        'locality': best.get('locality'),
        'country': best.get('country'),
        'telephone': best.get('telephone'),
        'latitude': best.get('latitude'),
        'longitude': best.get('longitude'),
    }
    if best.get('geocoded'):
        out['geocoded'] = True
    # Retirer valeurs vides
    return {k: v for k, v in out.items() if v is not None}
