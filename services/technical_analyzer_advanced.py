"""
Fonctions avancées d'analyse technique
"""

import ssl
import socket
from urllib.parse import urlparse, urljoin
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time

def analyze_ssl_certificate(domain):
    """Analyse le certificat SSL/TLS"""
    ssl_info = {}
    
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                
                # Informations du certificat
                ssl_info['ssl_issuer'] = dict(x[0] for x in cert.get('issuer', []))
                ssl_info['ssl_subject'] = dict(x[0] for x in cert.get('subject', []))
                ssl_info['ssl_version'] = ssock.version()
                
                # Dates
                if cert.get('notBefore'):
                    ssl_info['ssl_valid_from'] = cert['notBefore']
                if cert.get('notAfter'):
                    ssl_info['ssl_valid_until'] = cert['notAfter']
                    # Calculer les jours restants
                    try:
                        from email.utils import parsedate_to_datetime
                        valid_until = parsedate_to_datetime(cert['notAfter'])
                        days_left = (valid_until - datetime.now()).days
                        ssl_info['ssl_days_until_expiry'] = days_left
                    except:
                        pass
                
                # Algorithmes
                ssl_info['ssl_cipher'] = ssock.cipher()
                
    except Exception as e:
        ssl_info['ssl_error'] = str(e)[:100]
    
    return ssl_info

def detect_cms_plugins(soup, html_content, cms_type):
    """Détecte les plugins/extensions selon le CMS"""
    plugins = []
    html_lower = html_content.lower()
    
    if cms_type == 'WordPress':
        # Détecter les plugins WordPress
        wp_plugins = [
            'woocommerce', 'yoast', 'elementor', 'contact-form-7',
            'akismet', 'jetpack', 'wp-rocket', 'wp-super-cache',
            'wordfence', 'sucuri', 'all-in-one-seo', 'rank-math'
        ]
        for plugin in wp_plugins:
            if plugin in html_lower or f'/{plugin}/' in html_lower:
                plugins.append(plugin)
        
        # Chercher dans les chemins
        for link in soup.find_all(['link', 'script'], src=True):
            src = link.get('src', '') or link.get('href', '')
            if '/wp-content/plugins/' in src:
                plugin_name = src.split('/wp-content/plugins/')[1].split('/')[0]
                if plugin_name not in plugins:
                    plugins.append(plugin_name)
    
    elif cms_type == 'Drupal':
        drupal_modules = ['views', 'ctools', 'panels', 'pathauto']
        for module in drupal_modules:
            if module in html_lower:
                plugins.append(module)
    
    return ', '.join(plugins[:10]) if plugins else None

def detect_third_party_services(soup, html_content):
    """Détecte les services tiers utilisés"""
    services = {}
    html_lower = html_content.lower()
    
    # Chat/Live support
    chat_services = {
        'Intercom': ['intercom'],
        'Zendesk Chat': ['zendesk', 'zopim'],
        'LiveChat': ['livechatinc'],
        'Tawk.to': ['tawk'],
        'Drift': ['drift'],
        'Crisp': ['crisp']
    }
    
    for service, keywords in chat_services.items():
        if any(keyword in html_lower for keyword in keywords):
            services['chat_service'] = service
            break
    
    # Payment gateways
    payment_gateways = {
        'Stripe': ['stripe', 'stripe.com'],
        'PayPal': ['paypal'],
        'Square': ['square'],
        'Mollie': ['mollie'],
        'Lydia': ['lydia']
    }
    
    for gateway, keywords in payment_gateways.items():
        if any(keyword in html_lower for keyword in keywords):
            if 'payment_gateway' not in services:
                services['payment_gateway'] = []
            services['payment_gateway'].append(gateway)
    
    # Email services
    email_services = {
        'Mailchimp': ['mailchimp', 'mc-embedded-subscribe-form'],
        'SendGrid': ['sendgrid'],
        'Mandrill': ['mandrill'],
        'Sendinblue': ['sendinblue', 'sib-form']
    }
    
    for service, keywords in email_services.items():
        if any(keyword in html_lower for keyword in keywords):
            services['email_service'] = service
            break
    
    return services

def analyze_robots_txt(base_url):
    """Analyse le fichier robots.txt"""
    robots_info = {}
    
    try:
        from urllib.parse import urljoin
        robots_url = urljoin(base_url, '/robots.txt')
        response = requests.get(robots_url, timeout=5)
        
        if response.status_code == 200:
            robots_info['robots_txt_exists'] = True
            content = response.text.lower()
            
            # Détecter les user-agents
            if 'user-agent' in content:
                robots_info['robots_has_rules'] = True
            
            # Détecter sitemap
            sitemap_match = re.search(r'sitemap:\s*(.+)', content, re.I)
            if sitemap_match:
                robots_info['sitemap_url'] = sitemap_match.group(1).strip()
        else:
            robots_info['robots_txt_exists'] = False
    
    except:
        robots_info['robots_txt_exists'] = False
    
    return robots_info

def analyze_sitemap(base_url):
    """Analyse le sitemap.xml"""
    sitemap_info = {}
    
    try:
        from urllib.parse import urljoin
        sitemap_url = urljoin(base_url, '/sitemap.xml')
        response = requests.get(sitemap_url, timeout=5)
        
        if response.status_code == 200:
            sitemap_info['sitemap_exists'] = True
            try:
                soup = BeautifulSoup(response.text, 'xml')
                urls = soup.find_all('url')
                sitemap_info['sitemap_url_count'] = len(urls)
            except:
                pass
        else:
            sitemap_info['sitemap_exists'] = False
    
    except:
        sitemap_info['sitemap_exists'] = False
    
    return sitemap_info

def detect_waf(headers, html_content):
    """Détecte un Web Application Firewall (WAF)"""
    waf_detected = None
    
    # Headers spécifiques aux WAF
    waf_headers = {
        'Cloudflare': ['cf-ray', 'cf-request-id', 'server: cloudflare'],
        'Sucuri': ['x-sucuri-id', 'x-sucuri-cache'],
        'Incapsula': ['x-iinfo', 'x-cdn'],
        'Akamai': ['x-akamai-transformed'],
        'AWS WAF': ['x-amzn-requestid'],
        'ModSecurity': ['x-modsec'],
        'Wordfence': ['x-wf-']
    }
    
    headers_str = ' '.join([f"{k}: {v}" for k, v in headers.items()]).lower()
    
    for waf, indicators in waf_headers.items():
        if any(ind.lower() in headers_str for ind in indicators):
            waf_detected = waf
            break
    
    # Détection dans le HTML (pages d'erreur WAF)
    html_lower = html_content.lower()
    if 'cloudflare' in html_lower and 'checking your browser' in html_lower:
        waf_detected = 'Cloudflare'
    elif 'sucuri' in html_lower:
        waf_detected = 'Sucuri'
    
    return waf_detected

def analyze_seo_meta(soup):
    """Analyse les meta tags SEO"""
    seo_info = {}
    
    # Title
    title = soup.find('title')
    if title:
        seo_info['meta_title'] = title.get_text().strip()[:200]
        seo_info['meta_title_length'] = len(seo_info['meta_title'])
    
    # Description
    meta_desc = soup.find('meta', {'name': 'description'})
    if meta_desc:
        seo_info['meta_description'] = meta_desc.get('content', '').strip()[:300]
        seo_info['meta_description_length'] = len(seo_info['meta_description'])
    
    # Keywords
    meta_keywords = soup.find('meta', {'name': 'keywords'})
    if meta_keywords:
        seo_info['meta_keywords'] = meta_keywords.get('content', '').strip()[:200]
    
    # Open Graph
    og_tags = {}
    for tag in soup.find_all('meta', property=re.compile(r'^og:')):
        prop = tag.get('property', '').replace('og:', '')
        og_tags[prop] = tag.get('content', '')
    if og_tags:
        seo_info['open_graph'] = json.dumps(og_tags)
    
    # Twitter Cards
    twitter_tags = {}
    for tag in soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')}):
        name = tag.get('name', '').replace('twitter:', '')
        twitter_tags[name] = tag.get('content', '')
    if twitter_tags:
        seo_info['twitter_cards'] = json.dumps(twitter_tags)
    
    # Canonical
    canonical = soup.find('link', {'rel': 'canonical'})
    if canonical:
        seo_info['canonical_url'] = canonical.get('href', '')
    
    # Hreflang (internationalisation)
    hreflang_tags = []
    for tag in soup.find_all('link', {'rel': 'alternate', 'hreflang': True}):
        hreflang_tags.append(f"{tag.get('hreflang')}: {tag.get('href')}")
    if hreflang_tags:
        seo_info['hreflang'] = '; '.join(hreflang_tags[:5])
    
    return seo_info

def detect_backend_language(headers, html_content):
    """Détecte le langage backend"""
    languages = []
    
    # Headers
    if 'X-Powered-By' in headers:
        powered_by = headers['X-Powered-By'].lower()
        if 'php' in powered_by:
            languages.append('PHP')
        elif 'asp.net' in powered_by or 'aspnet' in powered_by:
            languages.append('ASP.NET')
        elif 'python' in powered_by:
            languages.append('Python')
        elif 'ruby' in powered_by:
            languages.append('Ruby')
    
    # Extensions de fichiers dans les URLs
    url_patterns = {
        '.php': 'PHP',
        '.aspx': 'ASP.NET',
        '.jsp': 'Java',
        '.py': 'Python',
        '.rb': 'Ruby',
        '.pl': 'Perl'
    }
    
    for ext, lang in url_patterns.items():
        if ext in html_content and lang not in languages:
            languages.append(lang)
    
    # Patterns dans le HTML
    if '<?php' in html_content:
        languages.append('PHP')
    
    return ', '.join(languages) if languages else None

def analyze_performance_hints(headers, html_content):
    """Analyse les indicateurs de performance"""
    perf_info = {}
    
    # HTTP/2
    if headers.get('HTTP/2') or 'h2' in str(headers.get('Upgrade', '')).lower():
        perf_info['http_version'] = 'HTTP/2'
    elif 'HTTP/1.1' in str(headers):
        perf_info['http_version'] = 'HTTP/1.1'
    
    # Compression
    if 'gzip' in headers.get('Content-Encoding', '').lower():
        perf_info['compression'] = 'Gzip'
    elif 'br' in headers.get('Content-Encoding', '').lower():
        perf_info['compression'] = 'Brotli'
    
    # Cache headers
    if 'Cache-Control' in headers:
        perf_info['cache_control'] = headers['Cache-Control']
    if 'ETag' in headers:
        perf_info['etag'] = True
    if 'Last-Modified' in headers:
        perf_info['last_modified_header'] = True
    
    # CDN detection
    cdn_headers = ['cf-ray', 'x-cache', 'x-amz-cf-id', 'x-served-by']
    for header in cdn_headers:
        if header in headers:
            perf_info['cdn_detected'] = True
            break
    
    # Lazy loading
    if 'loading="lazy"' in html_content or 'data-src=' in html_content:
        perf_info['lazy_loading'] = True
    
    # Minification
    if '.min.js' in html_content or '.min.css' in html_content:
        perf_info['minified_assets'] = True
    
    return perf_info

def detect_cookies(headers):
    """Analyse les cookies"""
    cookies_info = {}
    
    if 'Set-Cookie' in headers:
        cookies = headers.get('Set-Cookie', [])
        if isinstance(cookies, str):
            cookies = [cookies]
        
        cookies_info['cookies_count'] = len(cookies)
        
        # Détecter les cookies de tracking
        tracking_cookies = []
        for cookie in cookies:
            cookie_lower = cookie.lower()
            if any(keyword in cookie_lower for keyword in ['_ga', '_gid', '_fbp', 'utm', 'tracking']):
                tracking_cookies.append('Tracking')
            if 'session' in cookie_lower:
                tracking_cookies.append('Session')
            if 'auth' in cookie_lower or 'login' in cookie_lower:
                tracking_cookies.append('Authentication')
        
        if tracking_cookies:
            cookies_info['cookie_types'] = ', '.join(set(tracking_cookies))
    
    return cookies_info

def analyze_security_headers(headers):
    """Analyse les headers de sécurité"""
    security = {}
    
    # Security headers
    security_headers = {
        'X-Frame-Options': 'Clickjacking protection',
        'X-Content-Type-Options': 'MIME type sniffing protection',
        'X-XSS-Protection': 'XSS protection',
        'Strict-Transport-Security': 'HSTS',
        'Content-Security-Policy': 'CSP',
        'Referrer-Policy': 'Referrer policy',
        'Permissions-Policy': 'Permissions policy'
    }
    
    for header, description in security_headers.items():
        if header in headers:
            security[header.lower().replace('-', '_')] = headers[header]
    
    # Calculer un score de sécurité
    score = 0
    if 'strict-transport-security' in security:
        score += 2
    if 'content-security-policy' in security:
        score += 2
    if 'x-frame-options' in security:
        score += 1
    if 'x-content-type-options' in security:
        score += 1
    
    security['security_score'] = score
    security['security_level'] = 'Élevé' if score >= 5 else 'Moyen' if score >= 3 else 'Faible'
    
    return security

def analyze_performance_advanced(url, response, html_content):
    """Analyse de performance avancée"""
    perf_info = {}
    
    try:
        # Temps de réponse
        perf_info['response_time_ms'] = int(response.elapsed.total_seconds() * 1000)
        
        # Taille de la réponse
        perf_info['page_size_bytes'] = len(response.content)
        perf_info['page_size_kb'] = round(perf_info['page_size_bytes'] / 1024, 2)
        
        # Nombre de ressources
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Images
        images = soup.find_all('img')
        perf_info['images_count'] = len(images)
        images_without_alt = len([img for img in images if not img.get('alt')])
        if images_without_alt > 0:
            perf_info['images_missing_alt'] = images_without_alt
        
        # Scripts
        scripts = soup.find_all('script')
        perf_info['scripts_count'] = len(scripts)
        external_scripts = len([s for s in scripts if s.get('src')])
        perf_info['external_scripts_count'] = external_scripts
        
        # Stylesheets
        stylesheets = soup.find_all('link', {'rel': 'stylesheet'})
        perf_info['stylesheets_count'] = len(stylesheets)
        
        # Liens
        links = soup.find_all('a', href=True)
        perf_info['links_count'] = len(links)
        
        # Fonts
        font_links = soup.find_all('link', {'rel': re.compile(r'font|preload', re.I)})
        perf_info['fonts_count'] = len(font_links)
        
        # Images non optimisées (sans lazy loading)
        images_without_lazy = len([img for img in images if not img.get('loading') and not img.get('data-src')])
        if images_without_lazy > 0:
            perf_info['images_without_lazy_loading'] = images_without_lazy
        
        # Large images (détection basique)
        large_images = 0
        for img in images:
            if img.get('width') and img.get('height'):
                try:
                    width = int(img.get('width'))
                    height = int(img.get('height'))
                    if width > 1920 or height > 1080:
                        large_images += 1
                except:
                    pass
        if large_images > 0:
            perf_info['potentially_large_images'] = large_images
        
    except Exception as e:
        pass
    
    return perf_info

def detect_modern_frameworks(soup, html_content, headers):
    """Détecte les frameworks modernes"""
    frameworks = {}
    html_lower = html_content.lower()
    
    # Next.js
    if '__next' in html_lower or '_next' in html_lower or 'next.js' in html_lower:
        frameworks['nextjs'] = True
        # Version dans les scripts
        for script in soup.find_all('script', src=True):
            src = script.get('src', '')
            version_match = re.search(r'next[.-]?(\d+\.\d+(?:\.\d+)?)', src, re.I)
            if version_match:
                frameworks['nextjs_version'] = version_match.group(1)
                break
    
    # Nuxt.js
    if '__nuxt' in html_lower or 'nuxt' in html_lower:
        frameworks['nuxtjs'] = True
    
    # Svelte
    if 'svelte' in html_lower or '__svelte' in html_lower:
        frameworks['svelte'] = True
    
    # Gatsby
    if 'gatsby' in html_lower or '__gatsby' in html_lower:
        frameworks['gatsby'] = True
    
    # Remix
    if 'remix' in html_lower:
        frameworks['remix'] = True
    
    # Astro
    if 'astro' in html_lower or '__astro' in html_lower:
        frameworks['astro'] = True
    
    # SvelteKit
    if 'sveltekit' in html_lower:
        frameworks['sveltekit'] = True
    
    # Build tools
    if 'webpack' in html_lower:
        frameworks['webpack'] = True
    if 'vite' in html_lower:
        frameworks['vite'] = True
    if 'parcel' in html_lower:
        frameworks['parcel'] = True
    
    return frameworks

def analyze_content_structure(soup, html_content):
    """Analyse la structure du contenu"""
    content_info = {}
    
    try:
        # Langue
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            content_info['html_language'] = html_tag.get('lang')
        
        # Encodage
        meta_charset = soup.find('meta', {'charset': True})
        if meta_charset:
            content_info['charset'] = meta_charset.get('charset')
        else:
            meta_http_equiv = soup.find('meta', attrs={'http-equiv': re.compile(r'content-type', re.I)})
            if meta_http_equiv:
                content_match = re.search(r'charset=([^;]+)', meta_http_equiv.get('content', ''), re.I)
                if content_match:
                    content_info['charset'] = content_match.group(1).strip()
        
        # Structure sémantique
        semantic_tags = ['header', 'nav', 'main', 'article', 'section', 'aside', 'footer']
        semantic_count = {}
        for tag in semantic_tags:
            count = len(soup.find_all(tag))
            if count > 0:
                semantic_count[tag] = count
        if semantic_count:
            content_info['semantic_html_tags'] = semantic_count
        
        # Headings
        headings = {}
        for i in range(1, 7):
            h_tags = soup.find_all(f'h{i}')
            if h_tags:
                headings[f'h{i}'] = len(h_tags)
        if headings:
            content_info['headings_structure'] = headings
        
        # Liens externes vs internes
        links = soup.find_all('a', href=True)
        external_count = 0
        internal_count = 0
        for link in links:
            href = link.get('href', '')
            if href.startswith('http://') or href.startswith('https://'):
                external_count += 1
            elif href.startswith('/') or href.startswith('#'):
                internal_count += 1
        
        content_info['external_links_count'] = external_count
        content_info['internal_links_count'] = internal_count
        
        # Formulaires
        forms = soup.find_all('form')
        if forms:
            content_info['forms_count'] = len(forms)
        
        # Iframes
        iframes = soup.find_all('iframe')
        if iframes:
            content_info['iframes_count'] = len(iframes)
        
    except Exception as e:
        pass
    
    return content_info

def analyze_dns_advanced(domain):
    """Analyse DNS avancée"""
    dns_info = {}
    
    try:
        if not dns:
            return dns_info
        
        # MX Records (email)
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_list = []
            for rdata in mx_records:
                mx_list.append(f"{rdata.preference} {rdata.exchange}")
            if mx_list:
                dns_info['mx_records'] = '; '.join(mx_list[:5])
        except:
            pass
        
        # TXT Records (SPF, DKIM, DMARC)
        try:
            txt_records = dns.resolver.resolve(domain, 'TXT')
            txt_list = []
            for rdata in txt_records:
                txt_string = ' '.join([s.decode() if isinstance(s, bytes) else s for s in rdata.strings])
                txt_list.append(txt_string)
            
            # Détecter SPF
            for txt in txt_list:
                if txt.startswith('v=spf1'):
                    dns_info['spf_record'] = txt[:200]
                    break
            
            # Détecter DMARC
            try:
                dmarc_records = dns.resolver.resolve(f'_dmarc.{domain}', 'TXT')
                for rdata in dmarc_records:
                    dmarc_string = ' '.join([s.decode() if isinstance(s, bytes) else s for s in rdata.strings])
                    if 'v=DMARC1' in dmarc_string:
                        dns_info['dmarc_record'] = dmarc_string[:200]
                        break
            except:
                pass
            
            # Détecter DKIM (généralement dans un sous-domaine)
            dkim_domains = [f'default._domainkey.{domain}', f'_domainkey.{domain}']
            for dkim_domain in dkim_domains:
                try:
                    dkim_records = dns.resolver.resolve(dkim_domain, 'TXT')
                    for rdata in dkim_records:
                        dkim_string = ' '.join([s.decode() if isinstance(s, bytes) else s for s in rdata.strings])
                        if 'v=DKIM1' in dkim_string:
                            dns_info['dkim_record'] = 'Présent'
                            break
                except:
                    pass
        except:
            pass
        
        # IPv6
        try:
            aaaa_records = dns.resolver.resolve(domain, 'AAAA')
            if aaaa_records:
                dns_info['ipv6_support'] = True
                dns_info['ipv6_addresses'] = [str(rdata) for rdata in aaaa_records[:3]]
        except:
            dns_info['ipv6_support'] = False
        
        # CNAME
        try:
            cname_records = dns.resolver.resolve(domain, 'CNAME')
            if cname_records:
                dns_info['cname_records'] = [str(rdata.target) for rdata in cname_records]
        except:
            pass
        
    except Exception as e:
        pass
    
    return dns_info

def analyze_security_advanced(url, headers, html_content):
    """Analyse de sécurité avancée"""
    security_info = {}
    
    try:
        # Mixed Content (HTTP sur HTTPS)
        if url.startswith('https://'):
            soup = BeautifulSoup(html_content, 'html.parser')
            mixed_content = []
            
            # Images HTTP
            for img in soup.find_all('img', src=True):
                src = img.get('src', '')
                if src.startswith('http://'):
                    mixed_content.append('Images HTTP')
                    break
            
            # Scripts HTTP
            for script in soup.find_all('script', src=True):
                src = script.get('src', '')
                if src.startswith('http://'):
                    mixed_content.append('Scripts HTTP')
                    break
            
            # Stylesheets HTTP
            for link in soup.find_all('link', {'rel': 'stylesheet'}, href=True):
                href = link.get('href', '')
                if href.startswith('http://'):
                    mixed_content.append('Stylesheets HTTP')
                    break
            
            if mixed_content:
                security_info['mixed_content_detected'] = '; '.join(set(mixed_content))
            else:
                security_info['mixed_content_detected'] = False
        
        # Subresource Integrity (SRI)
        soup = BeautifulSoup(html_content, 'html.parser')
        scripts_with_sri = 0
        scripts_without_sri = 0
        
        for script in soup.find_all('script', src=True):
            if script.get('integrity'):
                scripts_with_sri += 1
            else:
                scripts_without_sri += 1
        
        if scripts_without_sri > 0:
            security_info['scripts_without_sri'] = scripts_without_sri
        if scripts_with_sri > 0:
            security_info['scripts_with_sri'] = scripts_with_sri
        
        # Cross-Origin Resource Sharing (CORS)
        if 'Access-Control-Allow-Origin' in headers:
            security_info['cors_enabled'] = headers['Access-Control-Allow-Origin']
        
        # Server header disclosure
        if 'Server' in headers:
            server_header = headers['Server']
            if len(server_header) > 20:  # Headers trop détaillés peuvent révéler des infos
                security_info['server_header_detailed'] = True
        
    except Exception as e:
        pass
    
    return security_info

def analyze_mobile_accessibility(soup, html_content):
    """Analyse de mobilité et accessibilité basique"""
    mobile_info = {}
    
    try:
        # Viewport meta tag
        viewport = soup.find('meta', {'name': 'viewport'})
        if viewport:
            mobile_info['viewport_meta'] = viewport.get('content', '')
        else:
            mobile_info['viewport_meta'] = 'Manquant'
        
        # Mobile-friendly
        mobile_friendly_indicators = [
            'width=device-width' in html_content.lower(),
            'initial-scale=1' in html_content.lower(),
            'maximum-scale=1' in html_content.lower()
        ]
        mobile_info['mobile_friendly'] = all(mobile_friendly_indicators) if viewport else False
        
        # Touch icons
        apple_touch_icon = soup.find('link', {'rel': re.compile(r'apple-touch-icon', re.I)})
        if apple_touch_icon:
            mobile_info['apple_touch_icon'] = True
        
        # Theme color
        theme_color = soup.find('meta', {'name': 'theme-color'})
        if theme_color:
            mobile_info['theme_color'] = theme_color.get('content', '')
        
        # Accessibilité basique
        # Alt text manquant
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]
        if images_without_alt:
            mobile_info['images_missing_alt_count'] = len(images_without_alt)
        
        # ARIA labels
        elements_with_aria = soup.find_all(attrs={'aria-label': True})
        mobile_info['aria_labels_count'] = len(elements_with_aria)
        
        # Skip links
        skip_links = soup.find_all('a', href=re.compile(r'#(main|content|skip)', re.I))
        if skip_links:
            mobile_info['skip_links'] = True
        
    except Exception as e:
        pass
    
    return mobile_info

def detect_api_endpoints(soup, html_content):
    """Détecte les endpoints API"""
    api_info = {}
    
    try:
        # GraphQL
        if '/graphql' in html_content.lower() or 'graphql' in html_content.lower():
            api_info['graphql_detected'] = True
        
        # REST API patterns
        api_patterns = {
            '/api/': 'REST API',
            '/rest/': 'REST API',
            '/v1/': 'API v1',
            '/v2/': 'API v2',
            '/json': 'JSON API',
            '/xml': 'XML API'
        }
        
        detected_apis = []
        for pattern, api_type in api_patterns.items():
            if pattern in html_content.lower():
                detected_apis.append(api_type)
        
        if detected_apis:
            api_info['api_endpoints_detected'] = ', '.join(set(detected_apis))
        
        # WebSockets
        if 'ws://' in html_content.lower() or 'wss://' in html_content.lower():
            api_info['websocket_detected'] = True
        
        # JSON-LD (structured data)
        json_ld = soup.find_all('script', {'type': 'application/ld+json'})
        if json_ld:
            api_info['json_ld_count'] = len(json_ld)
            # Détecter le type de structured data
            structured_data_types = []
            for script in json_ld:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and '@type' in data:
                        structured_data_types.append(data['@type'])
                    elif isinstance(data, list) and len(data) > 0 and '@type' in data[0]:
                        structured_data_types.append(data[0]['@type'])
                except:
                    pass
            if structured_data_types:
                api_info['structured_data_types'] = ', '.join(set(structured_data_types)[:5])
        
    except Exception as e:
        pass
    
    return api_info

def detect_more_services(soup, html_content):
    """Détecte plus de services tiers"""
    services = {}
    html_lower = html_content.lower()
    
    # CRM
    crm_services = {
        'Salesforce': ['salesforce', 'sfdc'],
        'HubSpot': ['hubspot'],
        'Pipedrive': ['pipedrive'],
        'Zoho': ['zoho']
    }
    
    for service, keywords in crm_services.items():
        if any(keyword in html_lower for keyword in keywords):
            services['crm_service'] = service
            break
    
    # Video services
    video_services = {
        'YouTube': ['youtube.com', 'youtu.be', 'youtube-nocookie'],
        'Vimeo': ['vimeo.com'],
        'Dailymotion': ['dailymotion'],
        'Wistia': ['wistia']
    }
    
    for service, keywords in video_services.items():
        if any(keyword in html_lower for keyword in keywords):
            if 'video_service' not in services:
                services['video_service'] = []
            services['video_service'].append(service)
    
    # Maps
    map_services = {
        'Google Maps': ['maps.google', 'googleapis.com/maps'],
        'Mapbox': ['mapbox'],
        'OpenStreetMap': ['openstreetmap', 'osm.org']
    }
    
    for service, keywords in map_services.items():
        if any(keyword in html_lower for keyword in keywords):
            services['map_service'] = service
            break
    
    # Font services
    font_services = {
        'Google Fonts': ['fonts.googleapis.com', 'fonts.gstatic.com'],
        'Adobe Fonts': ['use.typekit.net', 'adobe fonts'],
        'Font Awesome': ['fontawesome', 'font-awesome'],
        'Font Awesome CDN': ['cdnjs.cloudflare.com/ajax/libs/font-awesome']
    }
    
    for service, keywords in font_services.items():
        if any(keyword in html_lower for keyword in keywords):
            if 'font_service' not in services:
                services['font_service'] = []
            services['font_service'].append(service)
    
    # Comment systems
    comment_services = {
        'Disqus': ['disqus.com'],
        'Facebook Comments': ['facebook.com/plugins/comments'],
        'Livefyre': ['livefyre']
    }
    
    for service, keywords in comment_services.items():
        if any(keyword in html_lower for keyword in keywords):
            services['comment_system'] = service
            break
    
    return services

