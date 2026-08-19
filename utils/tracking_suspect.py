"""
Heuristiques tracking suspect (proxy mail, bots cloud, prefetch).

Objectif: ne pas compter comme ouverture un hit automatique du pixel
(Apple Mail Privacy Protection, scanners, prechargement client).
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Union

# Prefixe IP cloud frequents (scanners / bots). Approximation volontairement simple.
_CLOUD_IP_PREFIXES = (
    '3.', '13.', '18.', '34.', '35.', '44.', '52.', '54.',  # AWS approx
    '34.64.', '35.184.', '35.185.', '35.186.', '35.187.', '35.188.', '35.189.', '35.190.',  # GCP
    '20.', '40.', '51.', '52.149.', '104.40.', '104.41.', '104.42.',  # Azure approx
    '66.249.',  # Google image proxy /bot
)

_APPLE_NETWORKS = (
    ipaddress.ip_network('17.0.0.0/8'),
    ipaddress.ip_network('2620:149::/32'),
    ipaddress.ip_network('2a01:b740::/29'),
)

_PROXY_UA_MARKERS = (
    'googleimageproxy',
    'ggpht.com',
    'yahoomailproxy',
    'yahoomail',
    'proofpoint',
    'barracuda',
    'mimecast',
    'messagelabs',
    'outlook-android',
    'prefetch',
)

_SCANNER_UA_MARKERS = (
    'proofpoint',
    'barracuda',
    'mimecast',
    'messagelabs',
    'agari',
    'fireeye',
    'symantec',
    'broadcom',
    'forcepoint',
    'fortinet',
    'fortimail',
    'ironport',
    'cisco',
    'spamtitan',
    'sophos',
    'trend micro',
    'trendmicro',
    'mailscanner',
    'spamassassin',
    'antispam',
    'safelinks',
    'microsoft office existence',
    'ms-office',
    'protection.outlook.com',
    'microsoft-exchange',
    'exchange-antispam',
    'office365',
    'defender',
    'googlebot',
    'bingbot',
    'bytespider',
    'okhttp',
    'java/',
    'php/',
    'prefetch',
    'prerender',
    'python-requests',
    'python-urllib',
    'curl/',
    'wget/',
    'go-http-client',
    'axios/',
    'scrapy',
    'httpunit',
    'libwww',
    'scanner',
    'crawler',
    'spider',
    'bot/',
    'headless',
)

_GMAIL_YAHOO_PROXY_MARKERS = (
    'googleimageproxy',
    'ggpht.com',
    'yahoomailproxy',
    'yahoomail',
)

_PREFETCH_HEADER_NAMES = (
    'Purpose',
    'X-Purpose',
    'X-Moz',
    'Sec-Purpose',
    'Sec-Fetch-Purpose',
    'X-Moz-Prefetch',
    'Prefetch',
)

_PREFETCH_DEST_VALUES = frozenset(('empty', 'document', 'iframe', 'object', 'embed'))

_APPLE_SHORT_UA = re.compile(r'^mozilla/5\.0$', re.IGNORECASE)


def _get_env_int(name: str, default: int, min_value: int = 0, max_value: int = 86400) -> int:
    """
    Lit un entier depuis l'environnement.

    @param name: Nom de la variable
    @param default: Valeur par defaut
    @param min_value: Minimum inclus
    @param max_value: Maximum inclus
    @returns: Entier borne
    """
    raw = str(os.getenv(name, str(default)) or str(default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(value, max_value))


def get_prefetch_grace_seconds() -> int:
    """
    Delai minimum apres envoi avant de compter une ouverture.

    Trop court, les scanners ATP passent. Trop long, on rate les vrais lecteurs.
    Gmail/Yahoo ne sont pas soumis a ce delai (un hit proxy = affichage).

    @returns: Secondes (defaut 180)
    """
    return _get_env_int('TRACKING_PREFETCH_GRACE_SECONDS', 180, 0, 3600)


def get_open_confirm_seconds() -> int:
    """
    Delai minimum entre un premier hit (prefetch) et une confirmation.

    @returns: Secondes (defaut 45)
    """
    return _get_env_int('TRACKING_OPEN_CONFIRM_SECONDS', 45, 5, 3600)


def get_late_open_seconds() -> int:
    """
    Delai apres envoi a partir duquel un hit isole non suspect compte.

    @returns: Secondes (defaut 600)
    """
    return _get_env_int('TRACKING_LATE_OPEN_SECONDS', 600, 60, 86400)


def get_burst_window_seconds() -> int:
    """
    Fenetre pour detecter un scanner qui balaie plusieurs emails.

    @returns: Secondes (defaut 600)
    """
    return _get_env_int('TRACKING_BURST_WINDOW_SECONDS', 600, 60, 7200)


def get_burst_email_threshold() -> int:
    """
    Nombre d'emails distincts depuis la meme IP pour qualifier un burst.

    @returns: Seuil (defaut 3)
    """
    return _get_env_int('TRACKING_BURST_EMAIL_THRESHOLD', 3, 2, 50)


def get_request_client_ip(request_obj: Any) -> str:
    """
    IP cliente reelle derriere Nginx (X-Forwarded-For / X-Real-IP).

    @param request_obj: Objet Flask request
    @returns: IP du client, ou chaine vide
    """
    if request_obj is None:
        return ''
    headers = getattr(request_obj, 'headers', None)
    remote = getattr(request_obj, 'remote_addr', None) or ''
    raw = ''
    if headers is not None:
        raw = (
            headers.get('X-Forwarded-For')
            or headers.get('X-Real-IP')
            or ''
        )
    if not raw:
        raw = str(remote or '')
    if not raw:
        return ''
    return raw.split(',')[0].strip()


def _parse_ip(ip_address: Optional[str]) -> Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
    """
    Parse une adresse IP.

    @param ip_address: IP brute
    @returns: Objet IP ou None
    """
    ip = (ip_address or '').strip()
    if not ip:
        return None
    if ip.startswith('[') and ']' in ip:
        ip = ip[1:ip.index(']')]
    if '%' in ip:
        ip = ip.split('%', 1)[0]
    try:
        return ipaddress.ip_address(ip)
    except Exception:
        return None


def is_private_or_local_ip(ip_address: Optional[str]) -> bool:
    """
    Indique si l'IP est privee, loopback, ou inconnue (souvent Nginx).

    @param ip_address: Adresse IP client
    @returns: True si privee / inconnue
    """
    parsed = _parse_ip(ip_address)
    if parsed is None:
        return True
    return bool(
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_reserved
    )


def is_apple_privacy_ip(ip_address: Optional[str]) -> bool:
    """
    Indique si l'IP appartient a l'infra Apple (Mail Privacy Protection).

    @param ip_address: Adresse IP client
    @returns: True si IP Apple
    """
    parsed = _parse_ip(ip_address)
    if parsed is None:
        return False
    return any(parsed in network for network in _APPLE_NETWORKS)


def is_cloud_scanner_ip(ip_address: Optional[str]) -> bool:
    """
    Indique si l'IP ressemble a un scanner cloud (AWS/GCP/Azure/Googlebot).

    @param ip_address: Adresse IP client
    @returns: True si l'IP est suspecte
    """
    if is_apple_privacy_ip(ip_address):
        return True
    ip = (ip_address or '').strip()
    if not ip or ip in {'::', '::1', '127.0.0.1'}:
        return False
    return any(ip.startswith(prefix) for prefix in _CLOUD_IP_PREFIXES)


def is_proxy_or_bot_user_agent(user_agent: Optional[str]) -> bool:
    """
    Indique si le User-Agent ressemble a un proxy mail / prefetch.

    @param user_agent: UA HTTP
    @returns: True si suspect
    """
    ua = (user_agent or '').strip().lower()
    if not ua:
        return False
    if is_apple_mail_privacy_ua(user_agent):
        return True
    for marker in _PROXY_UA_MARKERS:
        if marker in ua:
            return True
    for marker in _SCANNER_UA_MARKERS:
        if marker in ua:
            return True
    return False


def is_gmail_or_yahoo_proxy_ua(user_agent: Optional[str]) -> bool:
    """
    Indique un proxy image Gmail/Yahoo (souvent un vrai affichage).

    @param user_agent: UA HTTP
    @returns: True si proxy Gmail/Yahoo
    """
    ua = (user_agent or '').strip().lower()
    if not ua:
        return False
    return any(marker in ua for marker in _GMAIL_YAHOO_PROXY_MARKERS)


def is_apple_mail_privacy_ua(user_agent: Optional[str]) -> bool:
    """
    Indique un UA typique Apple Mail / Safari (MPP).

    Chrome/Firefox/Edge iOS sont exclus.

    @param user_agent: UA HTTP
    @returns: True si UA Apple Mail / Safari
    """
    ua = (user_agent or '').strip()
    if not ua:
        return False
    if _APPLE_SHORT_UA.match(ua):
        return True
    low = ua.lower()
    if any(x in low for x in ('chrome', 'chromium', 'firefox', 'crios', 'fxios', 'edg/', 'opr/', 'android')):
        return False
    if 'applewebkit' not in low:
        return False
    return any(x in low for x in ('macintosh', 'iphone', 'ipad', 'ipod', 'mobile/'))


def is_prefetch_request(
    http_method: Optional[str] = None,
    headers: Optional[Mapping[str, Any]] = None,
) -> bool:
    """
    Indique un prechargement HTTP (HEAD, headers Purpose/prefetch).

    @param http_method: Methode HTTP
    @param headers: En-tetes de la requete
    @returns: True si prefetch
    """
    method = str(http_method or '').strip().upper()
    if method == 'HEAD':
        return True
    if not headers:
        return False
    dest = _header_value(headers, 'Sec-Fetch-Dest')
    if dest in _PREFETCH_DEST_VALUES:
        return True
    for name in _PREFETCH_HEADER_NAMES:
        low = _header_value(headers, name)
        if not low:
            continue
        if any(token in low for token in ('prefetch', 'preview', 'prerender', 'ads')):
            return True
    return False


def _header_value(headers: Optional[Mapping[str, Any]], name: str) -> str:
    """
    Lit un en-tete HTTP sans se soucier de la casse.

    @param headers: En-tetes
    @param name: Nom canonique
    @returns: Valeur minuscule, ou chaine vide
    """
    if not headers:
        return ''
    for candidate in (name, name.lower(), name.upper()):
        try:
            value = headers.get(candidate)
        except Exception:
            value = None
        if value is not None and str(value).strip():
            return str(value).strip().lower()
    return ''


def parse_tracking_datetime(value: Any) -> Optional[datetime]:
    """
    Parse une date de tracking (datetime ou texte SQL).

    @param value: Date brute
    @returns: datetime timezone-aware (UTC) ou None
    """
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    text = str(value).strip().replace('T', ' ')
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    for fmt in (
        '%Y-%m-%d %H:%M:%S.%f%z',
        '%Y-%m-%d %H:%M:%S%z',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
    ):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def seconds_since(start: Any, end: Any = None) -> Optional[float]:
    """
    Ecart en secondes entre deux dates.

    @param start: Date de debut
    @param end: Date de fin (defaut: maintenant UTC)
    @returns: Secondes ou None
    """
    start_dt = parse_tracking_datetime(start)
    if start_dt is None:
        return None
    end_dt = parse_tracking_datetime(end) if end is not None else datetime.now(timezone.utc)
    if end_dt is None:
        return None
    delta = (end_dt - start_dt).total_seconds()
    # Decalage de fuseau (date_envoi naive vs UTC): un hit "dans le futur"
    # de moins d'une heure est traite comme immediat.
    if -3600 < delta < 0:
        return 0.0
    return delta


def classify_open_hit(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    http_method: Optional[str] = None,
    headers: Optional[Mapping[str, Any]] = None,
    seconds_after_send: Optional[float] = None,
    grace_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Classe un hit pixel: vraie ouverture vs prechargement.

    @param ip_address: IP cliente reelle
    @param user_agent: User-Agent
    @param http_method: GET/HEAD
    @param headers: En-tetes HTTP
    @param seconds_after_send: Delai depuis l'envoi
    @param grace_seconds: Seuil anti-prefetch (defaut env)
    @returns: Dict prefetch/suspect/proxy/bot/reason
    """
    result: Dict[str, Any] = {
        'prefetch': False,
        'suspect': False,
        'proxy': False,
        'bot': False,
        'reason': '',
    }
    grace = get_prefetch_grace_seconds() if grace_seconds is None else int(grace_seconds)
    ua = (user_agent or '').strip()

    if is_prefetch_request(http_method, headers):
        result.update(prefetch=True, suspect=True, bot=True, reason='prefetch_http')
        return result

    if not ua:
        result.update(prefetch=True, suspect=True, bot=True, reason='empty_ua')
        return result

    if is_gmail_or_yahoo_proxy_ua(ua):
        # Gmail/Yahoo ne rechargent pas le pixel (cache proxy): un hit = affichage.
        result['proxy'] = True
        result['reason'] = 'gmail_yahoo_proxy'
        return result

    scanner_ua = False
    low = ua.lower()
    for marker in _SCANNER_UA_MARKERS:
        if marker in low:
            scanner_ua = True
            break
    if scanner_ua:
        result.update(prefetch=True, suspect=True, bot=True, reason='scanner_ua')
        return result

    apple_ip = is_apple_privacy_ip(ip_address)
    apple_ua = is_apple_mail_privacy_ua(ua)
    if apple_ip:
        result.update(prefetch=True, suspect=True, proxy=True, reason='apple_mpp')
        return result
    if apple_ua and is_private_or_local_ip(ip_address):
        # IP Nginx/privee + UA Apple = MPP historique ou proxy non vu
        result.update(prefetch=True, suspect=True, proxy=True, reason='apple_ua_via_proxy')
        return result

    if seconds_after_send is not None and 0 <= seconds_after_send < grace:
        result.update(prefetch=True, suspect=True, reason='too_soon')
        return result

    if is_cloud_scanner_ip(ip_address) and not apple_ua:
        result.update(bot=True, suspect=True, prefetch=True, reason='cloud_ip')
        return result

    return result


def is_confident_human_open(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    http_method: Optional[str] = None,
    headers: Optional[Mapping[str, Any]] = None,
) -> bool:
    """
    Indique un hit qui ressemble a un affichage navigateur humain.

    Les clients mail natifs n'envoient souvent pas ces en-tetes: dans ce cas
    on prefere attendre une confirmation (2e hit) plutot que de compter trop tot.

    @param ip_address: IP cliente
    @param user_agent: User-Agent
    @param http_method: Methode HTTP
    @param headers: En-tetes HTTP
    @returns: True si le hit est suffisamment "humain"
    """
    method = str(http_method or 'GET').strip().upper()
    if method != 'GET':
        return False
    if is_prefetch_request(http_method, headers):
        return False
    if is_apple_privacy_ip(ip_address) or is_cloud_scanner_ip(ip_address):
        return False
    ua = (user_agent or '').strip()
    if not ua:
        return False
    if is_gmail_or_yahoo_proxy_ua(ua):
        return True
    if is_apple_mail_privacy_ua(ua):
        return False
    low = ua.lower()
    for marker in _SCANNER_UA_MARKERS:
        if marker in low:
            return False
    accept_language = _header_value(headers, 'Accept-Language')
    if len(accept_language) < 2:
        return False
    dest = _header_value(headers, 'Sec-Fetch-Dest')
    accept = _header_value(headers, 'Accept')
    if dest and dest != 'image':
        return False
    return dest == 'image' or 'image' in accept


def decide_pixel_event(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    http_method: Optional[str] = None,
    headers: Optional[Mapping[str, Any]] = None,
    seconds_after_send: Optional[float] = None,
    prior_open_count: int = 0,
    prior_prefetch_count: int = 0,
    seconds_since_first_hit: Optional[float] = None,
    distinct_emails_same_ip: int = 0,
) -> Dict[str, Any]:
    """
    Decide si un hit pixel compte comme ouverture ou comme prefetch.

    Regles (prod):
    - Gmail/Yahoo proxy: ouverture (ils ne prefetchent pas les emails non lus)
    - HEAD / Apple MPP / scanners / IP cloud / trop tot: prefetch
    - Meme IP sur plusieurs emails en peu de temps: prefetch (scanner de campagne)
    - Premier hit ambigu: prefetch; un 2e hit plus tard confirme l'ouverture
    - Hit isole tardif, non suspect: ouverture

    @param ip_address: IP cliente
    @param user_agent: User-Agent
    @param http_method: GET/HEAD
    @param headers: En-tetes HTTP
    @param seconds_after_send: Secondes depuis l'envoi
    @param prior_open_count: Opens deja enregistres pour cet email
    @param prior_prefetch_count: Prefetch deja enregistres pour cet email
    @param seconds_since_first_hit: Secondes depuis le premier hit pixel
    @param distinct_emails_same_ip: Emails distincts vus depuis cette IP (fenetre burst)
    @returns: Dict avec event_type ('open'|'prefetch') et marqueurs
    @example:
        decided = decide_pixel_event(ip_address='203.0.113.10', user_agent='...')
        # decided['event_type'] == 'prefetch' ou 'open'
    """
    classified = classify_open_hit(
        ip_address=ip_address,
        user_agent=user_agent,
        http_method=http_method,
        headers=headers,
        seconds_after_send=seconds_after_send,
    )
    result: Dict[str, Any] = dict(classified)
    result['event_type'] = 'open'

    burst_threshold = get_burst_email_threshold()
    if int(distinct_emails_same_ip or 0) >= burst_threshold:
        result.update(
            prefetch=True,
            suspect=True,
            bot=True,
            reason='ip_burst',
            event_type='prefetch',
        )
        return result

    if classified.get('prefetch') or classified.get('suspect'):
        result['event_type'] = 'prefetch'
        return result

    if is_gmail_or_yahoo_proxy_ua(user_agent):
        result['event_type'] = 'open'
        result['reason'] = result.get('reason') or 'gmail_yahoo_proxy'
        return result

    if int(prior_open_count or 0) > 0:
        result['event_type'] = 'open'
        result['reason'] = 'repeat_open'
        return result

    confirm_after = get_open_confirm_seconds()
    if (
        int(prior_prefetch_count or 0) > 0
        and seconds_since_first_hit is not None
        and seconds_since_first_hit >= confirm_after
    ):
        result['event_type'] = 'open'
        result['reason'] = 'confirmed_after_prefetch'
        return result

    delay = seconds_after_send
    if delay is not None and delay >= get_late_open_seconds():
        result['event_type'] = 'open'
        result['reason'] = 'late_single_hit'
        return result

    if is_confident_human_open(ip_address, user_agent, http_method, headers):
        result['event_type'] = 'open'
        result['reason'] = 'human_headers'
        return result

    result.update(
        prefetch=True,
        suspect=True,
        reason='unconfirmed_first_hit',
        event_type='prefetch',
    )
    return result


def build_tracking_event_meta(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    http_method: Optional[str] = None,
    headers: Optional[Mapping[str, Any]] = None,
    seconds_after_send: Optional[float] = None,
    prior_open_count: int = 0,
    prior_prefetch_count: int = 0,
    seconds_since_first_hit: Optional[float] = None,
    distinct_emails_same_ip: int = 0,
    confirm: bool = False,
) -> Dict[str, Any]:
    """
    Construit un dict ``event_data`` avec marqueurs suspect si besoin.

    @param ip_address: IP client
    @param user_agent: UA client
    @param extra: Champs additionnels a fusionner
    @param http_method: Methode HTTP
    @param headers: En-tetes HTTP
    @param seconds_after_send: Delai depuis l'envoi
    @param prior_open_count: Opens deja stockes (si confirm=True)
    @param prior_prefetch_count: Prefetch deja stockes (si confirm=True)
    @param seconds_since_first_hit: Age du premier hit (si confirm=True)
    @param distinct_emails_same_ip: Burst IP (si confirm=True)
    @param confirm: Si True, applique la confirmation anti-prefetch
    @returns: Dict serialisable pour ``event_data``
    """
    meta: Dict[str, Any] = dict(extra or {})
    if confirm:
        classified = decide_pixel_event(
            ip_address=ip_address,
            user_agent=user_agent,
            http_method=http_method,
            headers=headers,
            seconds_after_send=seconds_after_send,
            prior_open_count=prior_open_count,
            prior_prefetch_count=prior_prefetch_count,
            seconds_since_first_hit=seconds_since_first_hit,
            distinct_emails_same_ip=distinct_emails_same_ip,
        )
        meta['event_type'] = classified.get('event_type') or 'open'
    else:
        classified = classify_open_hit(
            ip_address=ip_address,
            user_agent=user_agent,
            http_method=http_method,
            headers=headers,
            seconds_after_send=seconds_after_send,
        )
    if classified.get('proxy'):
        meta['proxy'] = True
    if classified.get('bot'):
        meta['bot'] = True
    if classified.get('prefetch'):
        meta['prefetch'] = True
    if classified.get('suspect'):
        meta['suspect'] = True
    if classified.get('reason'):
        meta['reason'] = meta.get('reason') or classified.get('reason')
    return meta


def event_data_is_suspect(event_data: Any) -> bool:
    """
    Indique si un ``event_data`` stocke marque l'evenement comme suspect.

    @param event_data: JSON string, dict, ou None
    @returns: True si proxy/bot/suspect
    """
    data = event_data
    if data is None or data == '':
        return False
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            low = data.lower()
            return 'suspect' in low or '"proxy"' in low or '"bot"' in low or '"prefetch"' in low
    if not isinstance(data, dict):
        return False
    return bool(
        data.get('suspect')
        or data.get('prefetch')
        or data.get('bot')
        or (data.get('reason') in {
            'apple_mpp',
            'apple_ua_via_proxy',
            'prefetch_http',
            'too_soon',
            'scanner_ua',
            'empty_ua',
            'cloud_ip',
            'ip_burst',
            'unconfirmed_first_hit',
            'classify_error',
        })
    )


def _sql_not_flagged_clause(is_postgresql: bool, alias: str, field: str) -> str:
    """
    Clause SQL: event_data sans flag JSON true.

    @param is_postgresql: True si PostgreSQL
    @param alias: Alias de table
    @param field: Nom du champ JSON (suspect, prefetch)
    @returns: Fragment SQL
    """
    prefix = f'{alias}.' if alias else ''
    if is_postgresql:
        return f"""(
            {prefix}event_data IS NULL OR btrim({prefix}event_data) = ''
            OR COALESCE({prefix}event_data::json->>'{field}', 'false') NOT IN ('true', 'True', '1')
        )"""
    return f"""(
        {prefix}event_data IS NULL OR trim({prefix}event_data) = ''
        OR json_extract({prefix}event_data, '$.{field}') IS NULL
        OR json_extract({prefix}event_data, '$.{field}') IN (0, '0', 'false', 'False')
    )"""


def sql_real_open_clause(is_postgresql: bool, alias: str = '') -> str:
    """
    Clause SQL des ouvertures humaines (hors prefetch / Apple / suspect).

    @param is_postgresql: True si PostgreSQL
    @param alias: Alias de table optionnel (ex: ``et``)
    @returns: Fragment SQL
    @example:
        clause = sql_real_open_clause(True, 'et')
        # et.event_type = 'open' AND ...
    """
    prefix = f'{alias}.' if alias else ''
    type_sql = f"{prefix}event_type = 'open'"
    apple_sql = f"({prefix}ip_address IS NULL OR {prefix}ip_address NOT LIKE '17.%')"
    suspect_sql = _sql_not_flagged_clause(is_postgresql, alias, 'suspect')
    prefetch_sql = _sql_not_flagged_clause(is_postgresql, alias, 'prefetch')
    return f"{type_sql} AND {apple_sql} AND {suspect_sql} AND {prefetch_sql}"


def sql_countable_event_clause(is_postgresql: bool, alias: str = '') -> str:
    """
    Clause SQL open humain OU clic non suspect.

    @param is_postgresql: True si PostgreSQL
    @param alias: Alias de table optionnel
    @returns: Fragment SQL
    """
    prefix = f'{alias}.' if alias else ''
    real_open = sql_real_open_clause(is_postgresql, alias)
    click_ok = (
        f"{prefix}event_type = 'click' AND "
        + _sql_not_flagged_clause(is_postgresql, alias, 'suspect')
    )
    return f"(({real_open}) OR ({click_ok}))"
