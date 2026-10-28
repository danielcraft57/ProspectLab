"""
Construction des payloads Facebook a partir d'une fiche entreprise.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def default_prospect_message(nom: str) -> str:
    """
    Message d'ouverture Messenger par defaut.

    @param nom: Nom commercial de l'entreprise
    @returns: Texte court personnalise
    """
    label = (nom or 'votre etablissement').strip()
    return (
        f"Bonjour, je suis Loic chez DanielCraft. "
        f"Je me permets de vous ecrire au sujet de {label}. "
        f"On accompagne des commerces locaux sur leur site et leur visibilite en ligne. "
        f"Si vous avez 2 minutes, je peux vous faire un retour gratuit sur votre presence web."
    )


def _is_facebook_page_url(url: str) -> bool:
    """True si le lien ressemble a une page Facebook (pas pixel / share)."""
    low = (url or '').strip().lower()
    if not low:
        return False
    if not any(host in low for host in ('facebook.com', 'fb.com', 'fb.me')):
        return False
    junk = ('/sharer', '/dialog/', '/plugins/', 'facebook.com/tr', '/tr?', '/wix/')
    return not any(part in low for part in junk)


def _url_from_unknown(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ('url', 'href', 'src', 'link'):
            val = str(item.get(key) or '').strip()
            if val:
                return val
    return ''


def _website_domain(website: str) -> str:
    raw = (website or '').strip()
    if not raw:
        return ''
    if '://' not in raw:
        raw = 'https://' + raw
    try:
        host = (urlparse(raw).netloc or '').lower()
    except ValueError:
        return ''
    if host.startswith('www.'):
        host = host[4:]
    return host


def _add_og_title(titles: list[str], val: str) -> None:
    """Ajoute un titre OG sans doublon."""
    v = (val or '').strip()[:120]
    if v and v not in titles:
        titles.append(v)


def _register_facebook_url(facebook_urls: list[str], href: str) -> None:
    """Enregistre une URL page Facebook si valide."""
    url = (href or '').strip()
    if _is_facebook_page_url(url) and url not in facebook_urls:
        facebook_urls.append(url)


def _harvest_meta_scrape_hints(
    meta: dict[str, Any],
    facebook_urls: list[str],
    og_titles: list[str],
) -> None:
    """
    Extrait titres, org schema et liens FB depuis metadata unified_scraper.

    @param meta: metadata scraper
    @param facebook_urls: Liste URLs FB a enrichir
    @param og_titles: Titres / noms commerciaux detectes
    """
    for key in ('external_links', 'header_external', 'identity_links'):
        for item in meta.get(key) or []:
            _register_facebook_url(facebook_urls, _url_from_unknown(item))
    og = meta.get('open_graph') if isinstance(meta.get('open_graph'), dict) else {}
    for key in ('title', 'site_name', 'description'):
        _add_og_title(og_titles, str(og.get(key) or ''))
    for key in ('url', 'see_also'):
        _register_facebook_url(facebook_urls, str(og.get(key) or ''))
    org = meta.get('organization') if isinstance(meta.get('organization'), dict) else {}
    _add_og_title(og_titles, str(org.get('name') or org.get('legalName') or ''))
    same_as = org.get('same_as') or []
    if isinstance(same_as, str):
        same_as = [same_as]
    for href in same_as:
        _register_facebook_url(facebook_urls, str(href or ''))
    tags = meta.get('meta_tags') if isinstance(meta.get('meta_tags'), dict) else {}
    for key in ('title', 'og:title', 'og:site_name', 'description'):
        _add_og_title(og_titles, str(tags.get(key) or ''))


def build_facebook_search_queries(nom: str, hints: dict[str, Any]) -> list[str]:
    """
    Variantes de requete Facebook a partir du CRM + scrape site.

    @param nom: Nom entreprise
    @param hints: Sortie collect_website_search_hints
    @returns: Requetes ordonnees (plus specifique d'abord)
    """
    queries: list[str] = []

    def add(q: str) -> None:
        text = (q or '').strip()[:120]
        if text and text not in queries:
            queries.append(text)

    ville = (hints.get('ville') or '').strip()
    if nom and ville:
        add(f'{nom} {ville}')
    add(nom)
    for title in hints.get('og_titles') or []:
        t = (title or '').strip()
        if t and t.lower() != (nom or '').lower():
            add(t)
            if ville:
                add(f'{t} {ville}')
    domain = (hints.get('website_domain') or '').strip()
    if domain:
        slug = domain.split('.')[0].replace('-', ' ').strip()
        if len(slug) >= 4 and slug.lower() != (nom or '').lower():
            add(slug)
    return queries[:6]

def collect_website_search_hints(entreprise: dict[str, Any], db: Any = None) -> dict[str, Any]:
    """
    Recupere ce que le scrape site a deja donne pour aider la recherche Facebook.

    @param entreprise: Fiche CRM
    @param db: Database optionnelle (OG, emails scraper)
    @returns: Hints (domaine, tel, mots-cles, website_scraped)
    """
    emails: list[str] = []
    facebook_urls: list[str] = []
    phone_hint = (entreprise.get('telephone') or '').strip()
    principal = (entreprise.get('email_principal') or '').strip()
    if principal and '@' in principal:
        emails.append(principal.lower())
    og_titles: list[str] = []
    has_og = False
    ville = (entreprise.get('ville') or '').strip()
    eid = entreprise.get('id') or entreprise.get('entreprise_id')
    if db and eid:
        try:
            og = db.get_og_data(int(eid))
            if og:
                has_og = True
                rows = og if isinstance(og, list) else [og]
                for item in rows[:8]:
                    if not isinstance(item, dict):
                        continue
                    title = (item.get('og_title') or item.get('title') or '').strip()
                    if title:
                        og_titles.append(title[:120])
        except Exception:
            has_og = False
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            db.execute_sql(
                cursor,
                '''
                SELECT email FROM scraper_emails
                WHERE entreprise_id = ? AND email IS NOT NULL
                LIMIT 8
                ''',
                (int(eid),),
            )
            for row in cursor.fetchall() or []:
                mail = row.get('email') if isinstance(row, dict) else row[0]
                mail = str(mail or '').strip().lower()
                if mail and '@' in mail and mail not in emails:
                    emails.append(mail)
            conn.close()
        except Exception:
            pass
        try:
            scrapers = db.get_scrapers_by_entreprise(int(eid), latest_only=True, include_images=False)
            scraper = scrapers[0] if scrapers else None
            if scraper:
                social = scraper.get('social_profiles') or {}
                if isinstance(social, dict):
                    for urls in social.values():
                        rows = urls if isinstance(urls, list) else [urls]
                        for item in rows:
                            href = _url_from_unknown(item)
                            if _is_facebook_page_url(href) and href not in facebook_urls:
                                facebook_urls.append(href)
                meta = scraper.get('metadata')
                if isinstance(meta, dict):
                    has_og = has_og or bool(meta.get('open_graph') or meta.get('meta_tags'))
                    _harvest_meta_scrape_hints(meta, facebook_urls, og_titles)
                    loc = meta.get('scraped_location')
                    if isinstance(loc, dict) and not ville:
                        ville = (loc.get('ville') or loc.get('city') or '').strip()
                sid = scraper.get('id')
                if sid and hasattr(db, 'get_external_links_for_scraper'):
                    try:
                        ext_payload = db.get_external_links_for_scraper(int(eid), int(sid))
                        for link in ext_payload.get('links') or []:
                            if not isinstance(link, dict):
                                continue
                            for key in ('url', 'resolved_url'):
                                _register_facebook_url(facebook_urls, str(link.get(key) or ''))
                    except Exception:
                        pass
                for phone_row in scraper.get('phones') or []:
                    num = ''
                    if isinstance(phone_row, dict):
                        num = str(phone_row.get('phone_e164') or phone_row.get('phone') or '').strip()
                    else:
                        num = str(phone_row).strip()
                    if num and not phone_hint:
                        phone_hint = num
        except Exception:
            pass

    resume = (entreprise.get('resume') or '').strip()
    blob = ' '.join(
        p
        for p in (
            resume,
            entreprise.get('secteur'),
            entreprise.get('categorie'),
            ' '.join(og_titles),
        )
        if p
    )
    keywords = []
    for token in blob.replace(',', ' ').split():
        word = token.strip('.,;:()[]').lower()
        if len(word) >= 4 and word not in keywords and word.isalpha():
            keywords.append(word)
        if len(keywords) >= 12:
            break

    has_shots = bool(entreprise.get('has_screenshots'))
    website_scraped = bool(
        has_og
        or resume
        or has_shots
        or emails
        or phone_hint
        or facebook_urls
    )
    return {
        'website_scraped': website_scraped,
        'website_domain': _website_domain(str(entreprise.get('website') or '')),
        'phone_hint': phone_hint,
        'email_hints': emails[:8],
        'keywords': keywords,
        'og_titles': og_titles[:6],
        'ville': ville,
        'known_facebook_urls': facebook_urls[:6],
        'has_og': has_og,
        'has_resume': bool(resume),
        'has_screenshots': has_shots,
    }


def build_facebook_search_payload_from_entreprise(
    entreprise: dict[str, Any],
    *,
    headless: bool = False,
    db: Any = None,
) -> dict[str, Any]:
    """
    Payload pour job search (nom + adresse pour scoring serv1).

    @param entreprise: Fiche entreprise
    @param headless: Navigateur sur serv1
    @returns: Dict payload JSON
    """
    built = build_prospect_payload_from_entreprise(
        entreprise,
        send=False,
        headless=headless,
        db=db,
    )
    return {
        'query': built.get('query'),
        'search_queries': built.get('search_queries') or [],
        'target_name': built.get('target_name'),
        'address_hint': built.get('address_hint'),
        'phone_hint': built.get('phone_hint'),
        'website_domain': built.get('website_domain'),
        'keywords': built.get('keywords'),
        'ville': built.get('ville'),
        'website_scraped': built.get('website_scraped'),
        'known_facebook_urls': built.get('known_facebook_urls') or [],
        'headless': built.get('headless'),
    }


def build_prospect_payload_from_entreprise(
    entreprise: dict[str, Any],
    *,
    message_text: str | None = None,
    send: bool = False,
    headless: bool = False,
    db: Any = None,
) -> dict[str, Any]:
    """
    Payload pour job prospect_flow (serv1).

    @param entreprise: Ligne entreprises (nom, adresses, etc.)
    @param message_text: Message Messenger (optionnel)
    @param send: True = envoi reel, False = dry-run composeur
    @param headless: Navigateur sur serv1
    @returns: Dict payload JSON
    """
    nom = (entreprise.get('nom') or entreprise.get('name') or '').strip()
    addr1 = (entreprise.get('address_1') or '').strip()
    addr2 = (entreprise.get('address_2') or '').strip()
    if not addr2:
        cp = (entreprise.get('code_postal') or '').strip()
        ville = (entreprise.get('ville') or '').strip()
        addr2 = ' '.join(p for p in (cp, ville) if p)
    address_hint = ', '.join(p for p in (addr1, addr2) if p)
    hints = collect_website_search_hints(entreprise, db)
    search_queries = build_facebook_search_queries(nom, hints)
    primary_query = search_queries[0] if search_queries else nom
    target_name = nom
    for title in hints.get('og_titles') or []:
        if title and len(title) >= len(nom or '') + 2:
            target_name = title
            break
    return {
        'query': primary_query,
        'search_queries': search_queries,
        'target_name': target_name,
        'address_hint': address_hint,
        'phone_hint': hints.get('phone_hint'),
        'website_domain': hints.get('website_domain'),
        'keywords': hints.get('keywords') or [],
        'ville': hints.get('ville'),
        'website_scraped': bool(hints.get('website_scraped')),
        'known_facebook_urls': hints.get('known_facebook_urls') or [],
        'email_hints': hints.get('email_hints') or [],
        'message_text': (message_text or '').strip() or default_prospect_message(nom),
        'send': bool(send),
        'headless': bool(headless),
    }
