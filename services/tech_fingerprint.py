"""
Empreintes technologies (CMS, libs, analytics) + versions + risque connu.
"""

from __future__ import annotations

import re
from typing import Any

_VER = r'(\d+\.\d+(?:\.\d+)?)'
_LABEL_VERSION = re.compile(r'^(.+?)\s+(\d+\.\d+(?:\.\d+)?)$')


def parse_version_tuple(version: str | None) -> tuple[int, ...]:
    """
    Transforme "6.4.2" en (6, 4, 2).

    @param version: Version brute
    @returns: Tuple d'entiers (vide si rien de lisible)
    """
    if not version:
        return tuple()
    parts = []
    for chunk in re.split(r'\D+', str(version).strip()):
        if chunk.isdigit():
            parts.append(int(chunk))
    return tuple(parts)


def version_less_than(version: str | None, threshold: str) -> bool:
    """True si version < seuil (parties manquantes = 0)."""
    left = parse_version_tuple(version)
    right = parse_version_tuple(threshold)
    if not left or not right:
        return False
    size = max(len(left), len(right))
    left = left + (0,) * (size - len(left))
    right = right + (0,) * (size - len(right))
    return left < right


def version_at_least(version: str | None, threshold: str) -> bool:
    """True si version >= seuil."""
    if not parse_version_tuple(version):
        return False
    return not version_less_than(version, threshold)


def _first_version(text: str, patterns: list[str]) -> str | None:
    blob = text or ''
    for pattern in patterns:
        match = re.search(pattern, blob, re.I)
        if match:
            return match.group(1)
    return None


def _asset_urls(html: str) -> list[str]:
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html or '', re.I)
    hrefs = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html or '', re.I)
    return srcs + hrefs


def version_from_assets(html: str, needles: list[str], max_major: int | None = None) -> str | None:
    """
    Version dans les URL de scripts/CSS (jquery-3.7.1.min.js, ?ver=6.4.2).

    @param html: HTML brut
    @param needles: Sous-chaines a trouver dans l'URL
    @param max_major: Ignore une version trop haute (ex. ver= WP colle sur jQuery)
    @returns: Version ou None
    """
    for src in _asset_urls(html):
        low = src.lower()
        if not any(needle in low for needle in needles):
            continue
        match = re.search(rf'[?&](?:ver|version|v)={_VER}', src, re.I)
        if not match:
            match = re.search(rf'(?:^|[/._-]){_VER}(?:\.min)?\.(?:js|css)', src, re.I)
        if not match:
            continue
        found = match.group(1)
        major = parse_version_tuple(found)
        if max_major is not None and major and major[0] > max_major:
            continue
        return found
    return None


def generator_content(html: str) -> str:
    match = re.search(
        r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']',
        html or '',
        re.I,
    )
    if match:
        return match.group(1)
    match = re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']generator["\']',
        html or '',
        re.I,
    )
    if match:
        return match.group(1)
    match = re.search(r'<generator>([^<]+)</generator>', html or '', re.I)
    return match.group(1).strip() if match else ''


def _header(headers: dict[str, Any] | None, name: str) -> str:
    if not headers:
        return ''
    for key, val in headers.items():
        if str(key).lower() == name.lower():
            return str(val or '')
    return ''


def _add(found: dict[str, dict[str, str | None]], category: str, name: str, version: str | None) -> None:
    bucket = found.setdefault(category, {})
    previous = bucket.get(name)
    if not previous and version:
        bucket[name] = version
    elif name not in bucket:
        bucket[name] = version


def _wordpress_version(raw: str, gen: str) -> str | None:
    ver = _first_version(gen, [rf'wordpress(?:\.org)?[^\d]*{_VER}', rf'[?&]v={_VER}'])
    if ver:
        return ver
    return _first_version(
        raw,
        [
            rf'wp-includes/(?:css|js)/[^"\']+[?&]ver={_VER}',
            rf'<!--\s*wordpress\s+{_VER}',
            rf'<generator>[^<]*wordpress[^<]*[?&]v={_VER}',
        ],
    )


def detect_site_technologies(html: str, headers: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """
    Detecte CMS / frameworks / analytics et colle la version si elle est visible.

    @param html: HTML de la page
    @param headers: Headers HTTP (Server, X-Powered-By, cookies)
    @returns: {categorie: ["Nom 1.2.3", ...]}
    """
    raw = html or ''
    low = raw.lower()
    gen = generator_content(raw)
    gen_low = gen.lower()
    cookies = _header(headers, 'set-cookie').lower()
    server = _header(headers, 'server')
    powered = _header(headers, 'x-powered-by')
    x_gen = _header(headers, 'x-generator')
    found: dict[str, dict[str, str | None]] = {}

    if re.search(r'/wp-content/|/wp-includes/|wp-json', low) or 'wordpress' in gen_low:
        _add(found, 'cms', 'WordPress', _wordpress_version(raw, gen))
    if re.search(r'/wp-content/plugins/woocommerce|woocommerce', low):
        _add(found, 'ecommerce', 'WooCommerce', version_from_assets(raw, ['woocommerce']))
    if re.search(r'/wp-content/plugins/elementor|elementor', low):
        _add(found, 'builder', 'Elementor', version_from_assets(raw, ['elementor']))
    if re.search(r'yoast|wordpress-seo', low):
        _add(found, 'seo', 'Yoast SEO', version_from_assets(raw, ['yoast', 'wordpress-seo']))
    if 'rank-math' in low or 'rankmath' in low:
        _add(found, 'seo', 'Rank Math', version_from_assets(raw, ['rank-math', 'rankmath']))
    if re.search(r'contact-form-7|wpcf7', low):
        _add(found, 'plugin', 'Contact Form 7', version_from_assets(raw, ['contact-form-7', 'wpcf7']))
    if 'jetpack' in low:
        _add(found, 'plugin', 'Jetpack', version_from_assets(raw, ['jetpack']))
    if re.search(r'revslider|rev-slider|revolution-slider', low):
        _add(found, 'plugin', 'Slider Revolution', version_from_assets(raw, ['revslider', 'rev-slider']))
    if 'gravityforms' in low or 'gravity-forms' in low:
        _add(found, 'plugin', 'Gravity Forms', version_from_assets(raw, ['gravityforms']))
    if 'wpml' in low or 'sitepress' in low:
        _add(found, 'plugin', 'WPML', version_from_assets(raw, ['wpml', 'sitepress']))
    if 'wordfence' in low:
        _add(found, 'security', 'Wordfence', version_from_assets(raw, ['wordfence']))
    if 'litespeed-cache' in low or 'litespeed' in low and 'wp-content' in low:
        _add(found, 'cache', 'LiteSpeed Cache', version_from_assets(raw, ['litespeed']))
    if 'wp-rocket' in low:
        _add(found, 'cache', 'WP Rocket', version_from_assets(raw, ['wp-rocket']))
    if 'divi' in low and ('et-builder' in low or 'et_pb' in low):
        _add(found, 'builder', 'Divi', version_from_assets(raw, ['divi']))
    if 'wp-block-library' in low or 'wp-includes/css/dist/block-library' in low:
        _add(found, 'builder', 'Gutenberg', None)

    if (
        re.search(r'drupal\.js|sites/default/files|/core/misc/drupal', low)
        or 'drupal' in gen_low
        or _header(headers, 'x-drupal-cache')
        or _header(headers, 'x-generator').lower().find('drupal') >= 0
    ):
        _add(
            found,
            'cms',
            'Drupal',
            _first_version(gen or x_gen, [rf'drupal\s+{_VER}']) or version_from_assets(raw, ['drupal']),
        )
    if ('option=com_' in low or 'joomla' in gen_low or '/media/system/js/' in low) and (
        'joomla' in low or '/media/jui/' in low or '/administrator/' in low
    ):
        _add(found, 'cms', 'Joomla', _first_version(gen, [rf'joomla[!?\s]+{_VER}']))
    if 'cdn.shopify.com' in low or 'myshopify.com' in low or _header(headers, 'x-shopify-stage'):
        _add(found, 'cms', 'Shopify', None)
    if 'wixstatic.com' in low or 'parastorage.com' in low or 'x-wix-' in str(headers).lower():
        _add(found, 'cms', 'Wix', None)
    if 'sqspcdn.com' in low or 'squarespace.com' in low:
        _add(found, 'cms', 'Squarespace', None)
    if 'webflow.com' in low or 'data-wf-page' in low or 'data-wf-site' in low:
        _add(found, 'cms', 'Webflow', None)
    if 'jimdo' in low or 'jimcdn.com' in low:
        _add(found, 'cms', 'Jimdo', None)
    if 'weebly' in low:
        _add(found, 'cms', 'Weebly', None)
    if 'duda.co' in low or 'dudamobile' in low:
        _add(found, 'cms', 'Duda', None)
    if re.search(r'prestashop|/modules/ps_|prestashop\.js', low) or 'prestashop' in gen_low:
        _add(found, 'cms', 'PrestaShop', _first_version(gen, [rf'prestashop\s+{_VER}']))
    if 'mage-init' in low or 'mage/cookies' in low or ('magento' in low and '/static/version' in low):
        _add(found, 'cms', 'Magento', _first_version(raw, [rf'magento[^\d]{_VER}']))
    if 'typo3conf' in low or 'typo3temp' in low or 'typo3' in gen_low:
        _add(found, 'cms', 'TYPO3', _first_version(gen, [rf'typo3\s+{_VER}']))
    if re.search(r'\bspip\b', gen_low) or 'spip.php' in low or '/squelettes/' in low and 'spip' in low:
        _add(found, 'cms', 'SPIP', _first_version(gen, [rf'spip\s+{_VER}']))
    if 'ghost' in gen_low or 'ghost.org' in low:
        _add(found, 'cms', 'Ghost', _first_version(gen, [rf'ghost\s+{_VER}']))
    if 'hubspot' in low and ('hs-scripts' in low or 'hs-analytics' in low or 'hs-banner' in low):
        _add(found, 'cms', 'HubSpot CMS', None)
    if 'opencart' in low or 'catalog/view/theme' in low and 'opencart' in low:
        _add(found, 'cms', 'OpenCart', None)
    if 'concrete5' in low or 'concrete cms' in gen_low:
        _add(found, 'cms', 'Concrete CMS', _first_version(gen, [_VER]))
    if 'grav-admin' in low or 'grav cms' in gen_low:
        _add(found, 'cms', 'Grav', None)
    if 'doku.php' in low or 'dokuwiki' in low:
        _add(found, 'cms', 'DokuWiki', None)

    if re.search(r'__NEXT_DATA__|/_next/static/', raw) or 'next.js' in powered.lower():
        _add(found, 'framework', 'Next.js', _first_version(powered, [rf'next\.js[_/ ]?{_VER}']))
    if '__NUXT__' in raw or '/_nuxt/' in low:
        _add(found, 'framework', 'Nuxt', None)
    if '___gatsby' in raw or 'gatsby-chunk-mapping' in low:
        _add(found, 'framework', 'Gatsby', None)
    if 'svelte' in low and ('sveltekit' in low or '__svelte' in low):
        _add(found, 'framework', 'SvelteKit', None)
    if re.search(r'react-dom|__REACT_DEVTOOLS|data-reactroot|data-reactid', raw):
        _add(found, 'framework', 'React', version_from_assets(raw, ['react-dom', 'react.'], max_major=19))
    if re.search(r'__VUE__|vue\.runtime|vue\.global', raw):
        _add(found, 'framework', 'Vue.js', version_from_assets(raw, ['vue'], max_major=4))
    if re.search(r'ng-version=|@angular/core', raw):
        ver = _first_version(raw, [r'ng-version=["\']' + _VER])
        _add(found, 'framework', 'Angular', ver)
    if re.search(r'angular\.js|angular\.min\.js', low):
        _add(found, 'framework', 'AngularJS', version_from_assets(raw, ['angular'], max_major=1))
    if re.search(r'jquery(?:\.min)?\.js|jquery[._-]' + _VER, low):
        _add(found, 'library', 'jQuery', version_from_assets(raw, ['jquery'], max_major=4))
    if 'jquery-migrate' in low:
        _add(found, 'library', 'jQuery Migrate', version_from_assets(raw, ['jquery-migrate'], max_major=4))
    if re.search(r'bootstrap(?:\.min)?\.(?:css|js)|bootstrap[._-]' + _VER, low):
        _add(found, 'css', 'Bootstrap', version_from_assets(raw, ['bootstrap'], max_major=5))
    if 'tailwindcss' in low or 'cdn.tailwindcss.com' in low:
        _add(found, 'css', 'Tailwind', None)
    if re.search(r'font-awesome|fontawesome', low):
        _add(found, 'css', 'Font Awesome', version_from_assets(raw, ['font-awesome', 'fontawesome']))
    if 'lodash' in low:
        _add(found, 'library', 'Lodash', version_from_assets(raw, ['lodash'], max_major=4))
    if re.search(r'moment(?:\.min)?\.js', low):
        _add(found, 'library', 'Moment.js', version_from_assets(raw, ['moment'], max_major=2))
    if 'ckeditor' in low:
        _add(found, 'library', 'CKEditor', version_from_assets(raw, ['ckeditor']))
    if 'tinymce' in low:
        _add(found, 'library', 'TinyMCE', version_from_assets(raw, ['tinymce']))
    if 'swiper' in low:
        _add(found, 'library', 'Swiper', version_from_assets(raw, ['swiper']))
    if 'modernizr' in low:
        _add(found, 'library', 'Modernizr', version_from_assets(raw, ['modernizr']))
    if 'gsap' in low or 'TweenMax' in raw:
        _add(found, 'library', 'GSAP', version_from_assets(raw, ['gsap', 'tweenmax']))
    if 'chart.js' in low or 'chart.min.js' in low:
        _add(found, 'library', 'Chart.js', version_from_assets(raw, ['chart']))
    if 'leaflet' in low:
        _add(found, 'library', 'Leaflet', version_from_assets(raw, ['leaflet']))

    if 'google-analytics.com' in low or 'gtag(' in low or 'googletagmanager.com/gtag' in low:
        _add(found, 'analytics', 'Google Analytics', None)
    if 'googletagmanager.com' in low or re.search(r'GTM-[A-Z0-9]+', raw):
        _add(found, 'analytics', 'Google Tag Manager', None)
    if 'connect.facebook.net' in low or 'fbq(' in low:
        _add(found, 'analytics', 'Facebook Pixel', None)
    if 'hotjar.com' in low or 'hjid' in low:
        _add(found, 'analytics', 'Hotjar', None)
    if 'matomo' in low or 'piwik' in low:
        _add(found, 'analytics', 'Matomo', None)
    if 'plausible.io' in low:
        _add(found, 'analytics', 'Plausible', None)
    if 'clarity.ms' in low:
        _add(found, 'analytics', 'Microsoft Clarity', None)
    if 'static.hotjar.com' in low:
        _add(found, 'analytics', 'Hotjar', None)
    if 'snap.licdn.com' in low or 'linkedin.com/px' in low:
        _add(found, 'analytics', 'LinkedIn Insight', None)

    if 'www.google.com/recaptcha' in low or 'grecaptcha' in low:
        _add(found, 'security', 'reCAPTCHA', None)
    if 'hcaptcha.com' in low:
        _add(found, 'security', 'hCaptcha', None)
    if 'challenges.cloudflare.com/turnstile' in low:
        _add(found, 'security', 'Turnstile', None)
    if 'cookiebot' in low:
        _add(found, 'consent', 'Cookiebot', None)
    if 'tarteaucitron' in low:
        _add(found, 'consent', 'Tarteaucitron', None)
    if 'axeptio' in low:
        _add(found, 'consent', 'Axeptio', None)
    if 'didomi' in low:
        _add(found, 'consent', 'Didomi', None)
    if 'onetrust' in low or 'optanon' in low:
        _add(found, 'consent', 'OneTrust', None)

    if 'js.stripe.com' in low:
        _add(found, 'payment', 'Stripe', None)
    if 'paypal.com/sdk' in low or 'paypalobjects.com' in low:
        _add(found, 'payment', 'PayPal', None)
    if 'js.mollie.com' in low or 'mollie' in low and 'payment' in low:
        _add(found, 'payment', 'Mollie', None)
    if 'paybox' in low:
        _add(found, 'payment', 'Paybox', None)

    if 'js.hs-scripts.com' in low or 'js.hsforms.net' in low:
        _add(found, 'marketing', 'HubSpot', None)
    if 'widget.intercom.io' in low:
        _add(found, 'marketing', 'Intercom', None)
    if 'list-manage.com' in low or 'mailchimp' in low:
        _add(found, 'marketing', 'Mailchimp', None)
    if 'brevo' in low or 'sendinblue' in low:
        _add(found, 'marketing', 'Brevo', None)
    if 'crisp.chat' in low:
        _add(found, 'marketing', 'Crisp', None)
    if 'tawk.to' in low:
        _add(found, 'marketing', 'Tawk.to', None)
    if 'static.cloudflareinsights.com' in low or _header(headers, 'cf-ray'):
        _add(found, 'cdn', 'Cloudflare', None)
    if 'cloudfront.net' in low:
        _add(found, 'cdn', 'CloudFront', None)
    if 'fastly' in low or _header(headers, 'x-served-by').lower().find('cache-') >= 0:
        if 'fastly' in low or 'fastly' in _header(headers, 'via').lower():
            _add(found, 'cdn', 'Fastly', None)
    if 'akamai' in low:
        _add(found, 'cdn', 'Akamai', None)
    if 'fonts.googleapis.com' in low or 'fonts.gstatic.com' in low:
        _add(found, 'cdn', 'Google Fonts', None)
    if _header(headers, 'x-vercel-id') or 'vercel' in powered.lower():
        _add(found, 'hosting', 'Vercel', None)
    if _header(headers, 'x-nf-request-id') or 'netlify' in server.lower():
        _add(found, 'hosting', 'Netlify', None)
    if 'ovh' in server.lower() or 'ovh.net' in low:
        _add(found, 'hosting', 'OVH', None)
    if 'o2switch' in low or 'o2switch' in server.lower():
        _add(found, 'hosting', 'o2switch', None)

    server_low = server.lower()
    if 'nginx' in server_low:
        _add(found, 'server', 'Nginx', _first_version(server, [rf'nginx[/ ]{_VER}']))
    elif 'apache' in server_low:
        _add(found, 'server', 'Apache', _first_version(server, [rf'apache[/ ]{_VER}']))
    elif 'iis' in server_low or 'microsoft-iis' in server_low:
        _add(found, 'server', 'IIS', _first_version(server, [rf'iis[/ ]{_VER}']))
    elif 'litespeed' in server_low:
        _add(found, 'server', 'LiteSpeed', _first_version(server, [rf'litespeed[/ ]{_VER}']))
    elif 'caddy' in server_low:
        _add(found, 'server', 'Caddy', None)

    powered_low = powered.lower()
    if 'php' in powered_low:
        _add(found, 'language', 'PHP', _first_version(powered, [rf'php[/ ]{_VER}']))
    php_header = _header(headers, 'x-php-version')
    if php_header:
        _add(found, 'language', 'PHP', _first_version(php_header, [_VER]) or php_header.strip())
    if 'asp.net' in powered_low:
        _add(found, 'language', 'ASP.NET', _first_version(powered, [_VER]))
    if 'express' in powered_low:
        _add(found, 'framework', 'Express', None)
    if 'phpsessid' in cookies:
        _add(found, 'language', 'PHP', found.get('language', {}).get('PHP'))
    if 'laravel_session' in cookies or 'xsrf-token' in cookies and 'laravel' in low:
        _add(found, 'framework', 'Laravel', None)
    if 'wordpress_test_cookie' in cookies or 'wp-settings' in cookies:
        _add(found, 'cms', 'WordPress', found.get('cms', {}).get('WordPress'))
    if 'prestashop' in cookies:
        _add(found, 'cms', 'PrestaShop', found.get('cms', {}).get('PrestaShop'))

    out: dict[str, list[str]] = {}
    for category, techs in found.items():
        labels = []
        for name, version in techs.items():
            labels.append(f'{name} {version}'.strip() if version else name)
        if labels:
            out[category] = labels
    return out


def split_tech_label(label: str) -> tuple[str, str | None]:
    """
    Separe "WordPress 6.4.2" en nom + version.

    @param label: Libelle stocke
    @returns: (nom, version ou None)
    """
    text = (label or '').strip()
    match = _LABEL_VERSION.match(text)
    if match:
        return match.group(1).strip(), match.group(2)
    return text, None


def merge_technology_maps(
    base: dict[str, list[str]] | None,
    extra: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    """
    Fusionne deux cartes de technologies en gardant la version la plus precise.

    @param base: Detections deja connues
    @param extra: Nouvelles detections
    @returns: Carte fusionnee
    """
    merged: dict[str, dict[str, tuple[str | None, str]]] = {}
    for source in (base or {}, extra or {}):
        for category, items in source.items():
            bucket = merged.setdefault(category, {})
            for raw in items or []:
                if isinstance(raw, dict):
                    name = str(raw.get('name') or '').strip()
                    version = raw.get('version')
                    label = name if not version else f'{name} {version}'
                else:
                    name, version = split_tech_label(str(raw))
                    label = name if not version else f'{name} {version}'
                if not name:
                    continue
                previous = bucket.get(name)
                if not previous:
                    bucket[name] = (version, label)
                    continue
                prev_ver, _label = previous
                if version and (not prev_ver or len(str(version)) > len(str(prev_ver))):
                    bucket[name] = (version, f'{name} {version}')
    return {
        category: [pair[1] for pair in techs.values()]
        for category, techs in merged.items()
        if techs
    }


_PRETTY_NAMES = {
    'wordpress': 'WordPress',
    'woocommerce': 'WooCommerce',
    'jquery': 'jQuery',
    'php': 'PHP',
    'nginx': 'Nginx',
    'apache': 'Apache',
    'iis': 'IIS',
    'drupal': 'Drupal',
    'joomla': 'Joomla',
    'prestashop': 'PrestaShop',
    'magento': 'Magento',
    'shopify': 'Shopify',
    'angular': 'Angular',
    'angularjs': 'AngularJS',
    'react': 'React',
    'vue': 'Vue.js',
    'vue.js': 'Vue.js',
    'vuejs': 'Vue.js',
    'bootstrap': 'Bootstrap',
    'next.js': 'Next.js',
    'nextjs': 'Next.js',
    'cloudflare': 'Cloudflare',
    'spip': 'SPIP',
    'typo3': 'TYPO3',
    'recaptcha': 'reCAPTCHA',
}


def pretty_tech_name(name: str) -> str:
    """
    Affiche un nom propre (wordpress -> WordPress).

    @param name: Nom brut
    @returns: Nom a afficher
    """
    raw = (name or '').strip()
    if not raw:
        return ''
    mapped = _PRETTY_NAMES.get(raw.lower())
    if mapped:
        return mapped
    if raw.isupper() or (len(raw) > 1 and raw[0].isupper()):
        return raw
    return raw[:1].upper() + raw[1:]


def canonical_tech_key(name: str) -> str:
    """Nom normalise pour le matching des risques."""
    key = re.sub(r'[^a-z0-9]+', '', (name or '').lower())
    aliases = {
        'wp': 'wordpress',
        'vuejs': 'vuejs',
        'vue': 'vuejs',
        'nextjs': 'nextjs',
        'next': 'nextjs',
        'angularjs': 'angularjs',
        'yostseo': 'yoastseo',
        'revslider': 'sliderrevolution',
        'sliderrevolution': 'sliderrevolution',
        'microsoftiis': 'iis',
        'aspnet': 'aspnet',
    }
    return aliases.get(key, key)


def assess_tech_risk(name: str, version: str | None) -> dict[str, Any]:
    """
    Dit si une version connue est faillible / EOL. Pas un scan CVE live:
    plages publiques documentees (maj 2026-10).

    @param name: Nom de la techno
    @param version: Version detectee
    @returns: status, severity, note, cves
    """
    key = canonical_tech_key(name)
    if not version:
        if key == 'angularjs':
            return {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'AngularJS 1.x abandonne, meme sans numero de version',
                'cves': ['CVE-2023-26116'],
            }
        return {
            'status': 'unknown',
            'severity': None,
            'note': 'Version non visible',
            'cves': [],
        }

    # (cle, test) -> resultat. Premier match gagne.
    rules: list[tuple[str, callable, dict[str, Any]]] = [
        (
            'wordpress',
            lambda v: version_less_than(v, '5.9'),
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'Branche WordPress abandonnee, correctifs core arretes',
                'cves': ['CVE-2024-31211'],
            },
        ),
        (
            'wordpress',
            lambda v: version_less_than(v, '6.5'),
            {
                'status': 'outdated',
                'severity': 'medium',
                'note': 'Version hors des branches encore maintenues (viser 6.6+)',
                'cves': [],
            },
        ),
        (
            'jquery',
            lambda v: version_less_than(v, '3.5.0'),
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'XSS prototype pollution / htmlPrefilter (CVE-2020-11022 / 11023)',
                'cves': ['CVE-2020-11022', 'CVE-2020-11023'],
            },
        ),
        (
            'jquery',
            lambda v: version_less_than(v, '3.7.0'),
            {
                'status': 'outdated',
                'severity': 'low',
                'note': 'jQuery 3.5-3.6, mieux de passer en 3.7+',
                'cves': [],
            },
        ),
        (
            'php',
            lambda v: version_less_than(v, '8.1'),
            {
                'status': 'vulnerable',
                'severity': 'critical',
                'note': 'PHP 7 / 8.0 en fin de vie, plus aucun patch secu',
                'cves': ['CVE-2024-1874'],
            },
        ),
        (
            'php',
            lambda v: version_less_than(v, '8.2'),
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'PHP 8.1 EOL depuis novembre 2025',
                'cves': [],
            },
        ),
        (
            'php',
            lambda v: version_less_than(v, '8.3'),
            {
                'status': 'outdated',
                'severity': 'medium',
                'note': 'PHP 8.2 arrive en fin de support secu (decembre 2026)',
                'cves': [],
            },
        ),
        (
            'drupal',
            lambda v: version_less_than(v, '10'),
            {
                'status': 'vulnerable',
                'severity': 'critical',
                'note': 'Drupal 7/8/9 en fin de vie',
                'cves': ['CVE-2022-25271'],
            },
        ),
        (
            'drupal',
            lambda v: version_less_than(v, '10.3'),
            {
                'status': 'outdated',
                'severity': 'medium',
                'note': 'Drupal 10 ancien mineur',
                'cves': [],
            },
        ),
        (
            'joomla',
            lambda v: version_less_than(v, '4.0'),
            {
                'status': 'vulnerable',
                'severity': 'critical',
                'note': 'Joomla 3 EOL, nombreuses failles d authentification',
                'cves': ['CVE-2023-23752'],
            },
        ),
        (
            'joomla',
            lambda v: version_less_than(v, '5.0'),
            {
                'status': 'outdated',
                'severity': 'medium',
                'note': 'Joomla 4, viser 5.x',
                'cves': [],
            },
        ),
        (
            'bootstrap',
            lambda v: version_less_than(v, '4.0'),
            {
                'status': 'vulnerable',
                'severity': 'medium',
                'note': 'Bootstrap 3 EOL (XSS XSS-via-tooltip / data attributes)',
                'cves': ['CVE-2019-8331'],
            },
        ),
        (
            'bootstrap',
            lambda v: version_less_than(v, '5.0'),
            {
                'status': 'outdated',
                'severity': 'low',
                'note': 'Bootstrap 4 plus maintenu',
                'cves': [],
            },
        ),
        (
            'angularjs',
            lambda v: True,
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'AngularJS 1.x abandonne (XSS sandbox)',
                'cves': ['CVE-2023-26116'],
            },
        ),
        (
            'angular',
            lambda v: version_less_than(v, '15'),
            {
                'status': 'outdated',
                'severity': 'medium',
                'note': 'Angular < 15 hors support long terme',
                'cves': [],
            },
        ),
        (
            'prestashop',
            lambda v: version_less_than(v, '8.0'),
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'PrestaShop 1.6 / 1.7, branches expirees',
                'cves': ['CVE-2023-30838'],
            },
        ),
        (
            'magento',
            lambda v: version_less_than(v, '2.4'),
            {
                'status': 'vulnerable',
                'severity': 'critical',
                'note': 'Magento 1 / 2.3 plus patches',
                'cves': ['CVE-2022-24086'],
            },
        ),
        (
            'woocommerce',
            lambda v: version_less_than(v, '8.0'),
            {
                'status': 'outdated',
                'severity': 'medium',
                'note': 'WooCommerce < 8, beaucoup de CVE plugins/core',
                'cves': [],
            },
        ),
        (
            'sliderrevolution',
            lambda v: version_less_than(v, '6.6'),
            {
                'status': 'vulnerable',
                'severity': 'critical',
                'note': 'Slider Revolution ancien = RCE / upload tres courant',
                'cves': ['CVE-2014-9734'],
            },
        ),
        (
            'apache',
            lambda v: version_less_than(v, '2.4'),
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'Apache 2.2 EOL',
                'cves': ['CVE-2017-15715'],
            },
        ),
        (
            'nginx',
            lambda v: version_less_than(v, '1.20'),
            {
                'status': 'outdated',
                'severity': 'medium',
                'note': 'Nginx ancien, viser une branche stable recente',
                'cves': ['CVE-2021-23017'],
            },
        ),
        (
            'iis',
            lambda v: version_less_than(v, '10'),
            {
                'status': 'outdated',
                'severity': 'medium',
                'note': 'IIS < 10 (Windows ancien)',
                'cves': [],
            },
        ),
        (
            'ckeditor',
            lambda v: version_less_than(v, '4.22'),
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'CKEditor 4 XSS connus, 4.22+ ou passer a 5',
                'cves': ['CVE-2023-4771'],
            },
        ),
        (
            'momentjs',
            lambda v: version_less_than(v, '2.29.4'),
            {
                'status': 'vulnerable',
                'severity': 'medium',
                'note': 'Moment.js ReDoS, lib plus recommendee',
                'cves': ['CVE-2022-31129'],
            },
        ),
        (
            'lodash',
            lambda v: version_less_than(v, '4.17.21'),
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'Lodash prototype pollution',
                'cves': ['CVE-2021-23337'],
            },
        ),
        (
            'spip',
            lambda v: version_less_than(v, '4.2'),
            {
                'status': 'vulnerable',
                'severity': 'high',
                'note': 'SPIP < 4.2, RCE historiques',
                'cves': ['CVE-2023-27372'],
            },
        ),
    ]

    for rule_key, test, payload in rules:
        if key == rule_key and test(version):
            return dict(payload)

    return {
        'status': 'ok',
        'severity': None,
        'note': 'Pas de plage faillible connue pour cette version',
        'cves': [],
    }


def annotate_tech_entry(name: str, version: str | None) -> dict[str, Any]:
    """
    Entree complete pour la BDD / l'UI.

    @param name: Nom
    @param version: Version eventuelle
    @returns: Dict serialisable
    """
    display = pretty_tech_name(name)
    risk = assess_tech_risk(display, version)
    label = f'{display} {version}'.strip() if version else display
    return {
        'name': display,
        'version': version,
        'label': label,
        'vuln_status': risk['status'],
        'vuln_severity': risk['severity'],
        'vuln_note': risk['note'],
        'cves': risk['cves'],
    }


def annotate_technology_map(technologies: dict[str, list] | None) -> dict[str, list[dict[str, Any]]]:
    """
    Ajoute le risque sur chaque techno d'une carte {categorie: [labels]}.

    @param technologies: Sortie de detect_site_technologies
    @returns: Carte annotee
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for category, items in (technologies or {}).items():
        rows = []
        for raw in items or []:
            if isinstance(raw, dict):
                name = str(raw.get('name') or '').strip()
                version = raw.get('version')
                if not version and raw.get('label'):
                    name, version = split_tech_label(str(raw.get('label')))
            else:
                name, version = split_tech_label(str(raw))
            if name:
                rows.append(annotate_tech_entry(name, version))
        if rows:
            out[category] = rows
    return out


def technology_map_to_labels(technologies: dict[str, list] | None) -> dict[str, list[str]]:
    """
    Repasse une carte annotee ou mixte en labels "Nom 1.2".

    @param technologies: Carte UI ou scrape
    @returns: Carte de labels
    """
    out: dict[str, list[str]] = {}
    for category, items in (technologies or {}).items():
        labels = []
        for raw in items or []:
            if isinstance(raw, dict):
                label = raw.get('label')
                if not label:
                    name = raw.get('name') or ''
                    version = raw.get('version')
                    label = f'{name} {version}'.strip() if version else name
                if label:
                    labels.append(str(label))
            elif raw:
                labels.append(str(raw))
        if labels:
            out[category] = labels
    return out


def map_has_missing_versions(technologies: dict[str, list] | None, categories: tuple[str, ...] | None = None) -> bool:
    """
    True s'il manque une version sur CMS / libs / langage / serveur.

    @param technologies: Carte actuelle
    @param categories: Categories a verifier
    @returns: True si une version manque
    """
    watch = set(categories or ('cms', 'library', 'css', 'language', 'server', 'framework'))
    for category, items in (technologies or {}).items():
        if category not in watch:
            continue
        for raw in items or []:
            if isinstance(raw, dict):
                if raw.get('name') and not raw.get('version'):
                    return True
            else:
                _name, version = split_tech_label(str(raw))
                if _name and not version:
                    return True
    return False


def versions_from_file_banner(url: str, text: str) -> dict[str, list[str]]:
    """
    Lit le commentaire en tete d'un JS/CSS (/*! jQuery v3.7.1).

    @param url: URL du fichier
    @param text: Debut du fichier
    @returns: Mini carte techno
    """
    blob = (text or '')[:4000]
    low = (url or '').lower()
    found: dict[str, list[str]] = {}
    rules = [
        ('jquery', r'jQuery(?: JavaScript Library)?[^\n\d]{0,20}v?' + _VER, 'library', 'jQuery'),
        ('bootstrap', r'Bootstrap[^\n\d]{0,16}v?' + _VER, 'css', 'Bootstrap'),
        ('vue', r'Vue\.js v' + _VER, 'framework', 'Vue.js'),
        ('react', r'React(?:DOM)? v' + _VER, 'framework', 'React'),
        ('drupal', r'Drupal [Vv]?' + _VER, 'cms', 'Drupal'),
    ]
    for needle, pattern, category, name in rules:
        if needle not in low and needle not in blob.lower():
            continue
        match = re.search(pattern, blob, re.I)
        if match:
            found.setdefault(category, []).append(f'{name} {match.group(1)}')
    return found
