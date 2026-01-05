"""
Service d'analyse technique approfondie des sites web
Détection de versions, frameworks, hébergeur, scan serveur avec nmap
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
import socket
import subprocess
import shutil
import json
from datetime import datetime
try:
    import whois
except ImportError:
    whois = None

try:
    import dns.resolver
except ImportError:
    dns = None


class TechnicalAnalyzer:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Base de données de technologies
        self.cms_patterns = {
            'WordPress': [
                r'wp-content', r'wp-includes', r'/wp-admin', r'wordpress',
                r'wp-json', r'wp-embed'
            ],
            'Drupal': [
                r'/sites/default', r'drupal\.js', r'drupal\.css', r'Drupal\.settings'
            ],
            'Joomla': [
                r'/media/jui', r'/administrator', r'joomla', r'Joomla'
            ],
            'Magento': [
                r'/media/', r'/skin/', r'Mage\.', r'magento'
            ],
            'PrestaShop': [
                r'/themes/', r'/modules/', r'prestashop'
            ],
            'Shopify': [
                r'shopify', r'shopifycdn', r'cdn\.shopify'
            ],
            'WooCommerce': [
                r'woocommerce', r'wc-', r'/wp-content/plugins/woocommerce'
            ]
        }
        
        self.cdn_providers = {
            'Cloudflare': ['cloudflare', 'cf-'],
            'Amazon CloudFront': ['cloudfront', 'amazonaws'],
            'Fastly': ['fastly'],
            'KeyCDN': ['keycdn'],
            'MaxCDN': ['maxcdn'],
            'BunnyCDN': ['bunnycdn'],
            'StackPath': ['stackpath']
        }
        
        self.analytics_services = {
            'Google Analytics': ['google-analytics', 'ga.js', 'analytics.js', 'gtag.js', 'googletagmanager'],
            'Google Tag Manager': ['googletagmanager', 'gtm.js'],
            'Facebook Pixel': ['facebook.net', 'fbq', 'facebook.com/tr'],
            'Hotjar': ['hotjar'],
            'Mixpanel': ['mixpanel'],
            'Segment': ['segment'],
            'Adobe Analytics': ['omniture', 'adobe', 'adobedtm']
        }
        
        # Détecter la disponibilité de nmap (natif ou via WSL)
        self._check_nmap_availability()
    
    def _check_nmap_availability(self):
        """
        Vérifie si nmap est disponible (natif ou via WSL)
        Stocke le chemin et la méthode à utiliser
        """
        # Vérifier nmap natif
        nmap_path = shutil.which('nmap')
        if nmap_path:
            self.nmap_method = 'native'
            self.nmap_cmd_base = ['nmap']
            return
        
        # Vérifier WSL
        wsl_path = shutil.which('wsl')
        if wsl_path:
            # Tester si nmap est disponible dans WSL (Kali Linux)
            try:
                test_result = subprocess.run(
                    ['wsl', '-d', 'kali-linux', '-u', 'loupix', 'which', 'nmap'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if test_result.returncode == 0:
                    self.nmap_method = 'wsl'
                    self.nmap_cmd_base = ['wsl', '-d', 'kali-linux', '-u', 'loupix', 'nmap']
                    return
            except:
                pass
        
        # Aucune méthode disponible
        self.nmap_method = None
        self.nmap_cmd_base = None
    
    def get_server_headers(self, url):
        """Récupère les headers HTTP du serveur"""
        try:
            response = requests.head(url, headers=self.headers, timeout=10, allow_redirects=True)
            return dict(response.headers)
        except:
            try:
                response = requests.get(url, headers=self.headers, timeout=10, allow_redirects=True)
                return dict(response.headers)
            except:
                return {}
    
    def detect_server_software(self, headers):
        """Détecte le logiciel serveur depuis les headers"""
        server_info = {}
        
        # Server header
        if 'Server' in headers:
            server_header = headers['Server']
            server_info['server'] = server_header
            
            # Extraire la version
            version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', server_header)
            if version_match:
                server_info['server_version'] = version_match.group(1)
            
            # Détecter le type de serveur web (Apache, Nginx, IIS, etc.)
            server_header_lower = server_header.lower()
            if 'apache' in server_header_lower:
                server_info['server_type'] = 'Apache'
                # Extraire la version Apache plus précisément
                apache_version = re.search(r'apache[/\s](\d+\.\d+(?:\.\d+)?)', server_header_lower)
                if apache_version:
                    server_info['server_version'] = apache_version.group(1)
            elif 'nginx' in server_header_lower:
                server_info['server_type'] = 'Nginx'
            elif 'iis' in server_header_lower or 'microsoft-iis' in server_header_lower:
                server_info['server_type'] = 'IIS'
            elif 'lighttpd' in server_header_lower:
                server_info['server_type'] = 'Lighttpd'
            elif 'caddy' in server_header_lower:
                server_info['server_type'] = 'Caddy'
            elif 'cloudflare' in server_header_lower:
                server_info['server_type'] = 'Cloudflare'
            elif 'litespeed' in server_header_lower:
                server_info['server_type'] = 'LiteSpeed'
            
            # Détecter l'OS depuis le header Server
            if 'debian' in server_header_lower:
                server_info['os'] = 'Debian'
            elif 'ubuntu' in server_header_lower:
                server_info['os'] = 'Ubuntu'
            elif 'centos' in server_header_lower:
                server_info['os'] = 'CentOS'
            elif 'red hat' in server_header_lower or 'redhat' in server_header_lower:
                server_info['os'] = 'Red Hat'
            elif 'fedora' in server_header_lower:
                server_info['os'] = 'Fedora'
            elif 'linux' in server_header_lower and 'os' not in server_info:
                server_info['os'] = 'Linux'
            elif 'windows' in server_header_lower or 'win32' in server_header_lower:
                server_info['os'] = 'Windows'
            elif 'freebsd' in server_header_lower:
                server_info['os'] = 'FreeBSD'
            elif 'openbsd' in server_header_lower:
                server_info['os'] = 'OpenBSD'
        
        # X-Powered-By (PHP, ASP.NET, etc.)
        if 'X-Powered-By' in headers:
            server_info['powered_by'] = headers['X-Powered-By']
            version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', headers['X-Powered-By'])
            if version_match:
                server_info['powered_by_version'] = version_match.group(1)
        
        # X-AspNet-Version
        if 'X-AspNet-Version' in headers:
            server_info['aspnet_version'] = headers['X-AspNet-Version']
        
        # PHP Version
        if 'X-PHP-Version' in headers:
            server_info['php_version'] = headers['X-PHP-Version']
        
        return server_info
    
    def detect_framework_version(self, soup, html_content, headers):
        """Détecte le framework et sa version avec précision"""
        framework_info = {}
        html_lower = html_content.lower()
        
        # WordPress
        if 'wp-content' in html_lower or 'wordpress' in html_lower:
            framework_info['framework'] = 'WordPress'
            # Version dans meta generator
            meta_gen = soup.find('meta', {'name': 'generator'})
            if meta_gen:
                gen_content = meta_gen.get('content', '')
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', gen_content)
                if version_match:
                    framework_info['framework_version'] = version_match.group(1)
            # Version dans les commentaires HTML
            if not framework_info.get('framework_version'):
                version_match = re.search(r'wordpress\s+(\d+\.\d+(?:\.\d+)?)', html_content, re.I)
                if version_match:
                    framework_info['framework_version'] = version_match.group(1)
        
        # Drupal
        elif 'drupal' in html_lower:
            framework_info['framework'] = 'Drupal'
            meta_gen = soup.find('meta', {'name': 'generator'})
            if meta_gen:
                gen_content = meta_gen.get('content', '')
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', gen_content)
                if version_match:
                    framework_info['framework_version'] = version_match.group(1)
        
        # Joomla
        elif 'joomla' in html_lower:
            framework_info['framework'] = 'Joomla'
            meta_gen = soup.find('meta', {'name': 'generator'})
            if meta_gen:
                gen_content = meta_gen.get('content', '')
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', gen_content)
                if version_match:
                    framework_info['framework_version'] = version_match.group(1)
        
        # React
        elif 'react' in html_lower or 'reactjs' in html_lower:
            framework_info['framework'] = 'React'
            # Chercher dans les scripts
            for script in soup.find_all('script', src=True):
                src = script.get('src', '')
                version_match = re.search(r'react[.-]?(\d+\.\d+(?:\.\d+)?)', src, re.I)
                if version_match:
                    framework_info['framework_version'] = version_match.group(1)
                    break
        
        # Vue.js
        elif 'vue' in html_lower or 'vuejs' in html_lower:
            framework_info['framework'] = 'Vue.js'
            for script in soup.find_all('script', src=True):
                src = script.get('src', '')
                version_match = re.search(r'vue[.-]?(\d+\.\d+(?:\.\d+)?)', src, re.I)
                if version_match:
                    framework_info['framework_version'] = version_match.group(1)
                    break
        
        # Angular
        elif 'angular' in html_lower:
            framework_info['framework'] = 'Angular'
            for script in soup.find_all('script', src=True):
                src = script.get('src', '')
                version_match = re.search(r'angular[.-]?(\d+\.\d+(?:\.\d+)?)', src, re.I)
                if version_match:
                    framework_info['framework_version'] = version_match.group(1)
                    break
        
        # Bootstrap
        if 'bootstrap' in html_lower:
            version_match = re.search(r'bootstrap[.-]?(\d+\.\d+(?:\.\d+)?)', html_lower)
            if version_match:
                framework_info['css_framework'] = f"Bootstrap {version_match.group(1)}"
        
        # jQuery
        if 'jquery' in html_lower:
            version_match = re.search(r'jquery[.-]?(\d+\.\d+(?:\.\d+)?)', html_lower)
            if version_match:
                framework_info['js_library'] = f"jQuery {version_match.group(1)}"
        
        return framework_info
    
    def get_domain_info(self, domain):
        """Récupère les informations DNS et WHOIS du domaine"""
        info = {}
        
        # Résolution DNS
        try:
            ip = socket.gethostbyname(domain)
            info['ip_address'] = ip
        except:
            pass
        
        # WHOIS
        try:
            if whois:
                w = whois.whois(domain)
            else:
                w = None
            if w:
                if w.creation_date:
                    if isinstance(w.creation_date, list):
                        info['domain_creation_date'] = w.creation_date[0].strftime('%Y-%m-%d') if w.creation_date[0] else None
                    else:
                        info['domain_creation_date'] = w.creation_date.strftime('%Y-%m-%d') if w.creation_date else None
                
                if w.updated_date:
                    if isinstance(w.updated_date, list):
                        info['domain_updated_date'] = w.updated_date[0].strftime('%Y-%m-%d') if w.updated_date[0] else None
                    else:
                        info['domain_updated_date'] = w.updated_date.strftime('%Y-%m-%d') if w.updated_date else None
                
                if w.registrar:
                    info['domain_registrar'] = w.registrar
                
                if w.name_servers:
                    info['name_servers'] = ', '.join(w.name_servers[:3]) if isinstance(w.name_servers, list) else str(w.name_servers)
        except Exception as e:
            pass
        
        return info
    
    def detect_hosting_provider(self, domain, ip=None):
        """Détecte l'hébergeur via IP et domain"""
        hosting_info = {}
        
        if not ip:
            try:
                ip = socket.gethostbyname(domain)
            except:
                return hosting_info
        
        # Base de données simple d'hébergeurs (peut être étendue)
        hosting_providers = {
            'OVH': ['ovh', 'ovhcloud'],
            'OVHCloud': ['ovh', 'ovhcloud'],
            'Amazon AWS': ['amazon', 'aws', 'ec2', 'cloudfront'],
            'Google Cloud': ['google', 'gcp', 'cloud.google'],
            'Microsoft Azure': ['azure', 'microsoft', 'windows azure'],
            'Hetzner': ['hetzner'],
            'Scaleway': ['scaleway'],
            'Online.net': ['online.net', 'online'],
            '1&1 IONOS': ['1and1', 'ionos', '1&1'],
            'Gandi': ['gandi'],
            'Infomaniak': ['infomaniak'],
            'PlanetHoster': ['planethoster'],
        }
        
        # Reverse DNS lookup
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            hosting_info['hostname'] = hostname
            
            hostname_lower = hostname.lower()
            for provider, keywords in hosting_providers.items():
                if any(keyword in hostname_lower for keyword in keywords):
                    hosting_info['hosting_provider'] = provider
                    break
        except:
            pass
        
        # Si pas trouvé, chercher dans les name servers
        try:
            if dns:
                answers = dns.resolver.resolve(domain, 'NS')
                for rdata in answers:
                    ns = str(rdata.target).lower()
                    for provider, keywords in hosting_providers.items():
                        if any(keyword in ns for keyword in keywords):
                            hosting_info['hosting_provider'] = provider
                            break
                    if hosting_info.get('hosting_provider'):
                        break
        except:
            pass
        
        return hosting_info
    
    def nmap_scan(self, domain, ip=None):
        """
        Effectue un scan nmap du serveur (ports ouverts, services, OS)
        Supporte nmap natif Windows ou via WSL (Kali Linux)
        """
        scan_results = {}
        
        if not ip:
            try:
                ip = socket.gethostbyname(domain)
            except:
                return {'error': 'Impossible de résoudre le domaine'}
        
        # Vérifier si nmap est disponible
        if not self.nmap_cmd_base:
            scan_results['nmap_scan'] = 'Nmap non disponible (ni natif ni via WSL)'
            return scan_results
        
        # Construire la commande complète
        # Note: pour WSL, on doit passer les arguments après 'nmap'
        if self.nmap_method == 'wsl':
            cmd = ['wsl', '-d', 'kali-linux', '-u', 'loupix', 'nmap', '-F', '-sV', '--version-intensity', '0', '-O', '--osscan-guess', ip]
        else:
            cmd = self.nmap_cmd_base + ['-F', '-sV', '--version-intensity', '0', '-O', '--osscan-guess', ip]
        
        try:
            # Scan rapide des ports communs avec détection OS
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # Augmenté à 60s pour WSL qui peut être plus lent
            )
            
            if result.returncode == 0:
                output = result.stdout
                
                # Extraire les ports ouverts
                open_ports = []
                port_pattern = r'(\d+)/(tcp|udp)\s+open\s+(\S+)'
                for match in re.finditer(port_pattern, output):
                    port = match.group(1)
                    protocol = match.group(2)
                    service = match.group(3)
                    open_ports.append(f"{port}/{protocol} ({service})")
                
                scan_results['open_ports'] = ', '.join(open_ports[:10]) if open_ports else 'Aucun port ouvert détecté'
                scan_results['nmap_scan'] = 'Réussi'
                
                # Détecter le serveur web depuis nmap
                for line in output.split('\n'):
                    if 'http' in line.lower() or 'apache' in line.lower() or 'nginx' in line.lower():
                        if 'version' in line.lower():
                            version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', line)
                            if version_match:
                                scan_results['web_server_detected'] = line.strip()
                                break
                
                # Détecter l'OS depuis nmap
                os_lines = []
                in_os_section = False
                for line in output.split('\n'):
                    if 'OS details:' in line or 'OS CPE:' in line or 'Aggressive OS guesses:' in line:
                        in_os_section = True
                        continue
                    if in_os_section:
                        if line.strip() and not line.strip().startswith('Network Distance'):
                            # Extraire les informations OS
                            os_info = line.strip()
                            # Nettoyer et formater
                            if 'Linux' in os_info:
                                if 'Debian' in os_info:
                                    scan_results['os_detected'] = 'Debian'
                                elif 'Ubuntu' in os_info:
                                    scan_results['os_detected'] = 'Ubuntu'
                                elif 'CentOS' in os_info:
                                    scan_results['os_detected'] = 'CentOS'
                                elif 'Red Hat' in os_info or 'RHEL' in os_info:
                                    scan_results['os_detected'] = 'Red Hat'
                                elif 'Fedora' in os_info:
                                    scan_results['os_detected'] = 'Fedora'
                                else:
                                    scan_results['os_detected'] = 'Linux'
                            elif 'Windows' in os_info:
                                scan_results['os_detected'] = 'Windows'
                            elif 'FreeBSD' in os_info:
                                scan_results['os_detected'] = 'FreeBSD'
                            elif 'OpenBSD' in os_info:
                                scan_results['os_detected'] = 'OpenBSD'
                            
                            if 'os_detected' in scan_results:
                                break
                        elif line.strip().startswith('Network Distance') or line.strip().startswith('OS detection'):
                            break
            else:
                scan_results['nmap_scan'] = 'Échec'
                scan_results['nmap_error'] = result.stderr[:100]
        
        except FileNotFoundError:
            scan_results['nmap_scan'] = 'Nmap non installé'
        except subprocess.TimeoutExpired:
            scan_results['nmap_scan'] = 'Timeout'
        except Exception as e:
            scan_results['nmap_scan'] = f'Erreur: {str(e)[:50]}'
        
        return scan_results
    
    def get_http_dates(self, headers):
        """Extrait les dates depuis les headers HTTP"""
        dates = {}
        
        # Last-Modified
        if 'Last-Modified' in headers:
            try:
                from email.utils import parsedate_to_datetime
                last_modified = parsedate_to_datetime(headers['Last-Modified'])
                dates['last_modified'] = last_modified.strftime('%Y-%m-%d %H:%M:%S')
            except:
                dates['last_modified'] = headers['Last-Modified']
        
        # Date
        if 'Date' in headers:
            try:
                from email.utils import parsedate_to_datetime
                server_date = parsedate_to_datetime(headers['Date'])
                dates['server_date'] = server_date.strftime('%Y-%m-%d %H:%M:%S')
            except:
                dates['server_date'] = headers['Date']
        
        return dates
    
    def _detect_cdn(self, headers, html_content):
        """Détecte le CDN utilisé"""
        cdn_detected = None
        
        # Headers CDN
        headers_str = ' '.join([f"{k}: {v}" for k, v in headers.items()]).lower()
        html_lower = html_content.lower() if html_content else ''
        
        for cdn, keywords in self.cdn_providers.items():
            if any(keyword.lower() in headers_str or keyword.lower() in html_lower for keyword in keywords):
                cdn_detected = cdn
                break
        
        return cdn_detected
    
    def _detect_analytics(self, soup, html_content):
        """Détecte les services d'analytics"""
        analytics_detected = []
        html_lower = html_content.lower() if html_content else ''
        
        for service, keywords in self.analytics_services.items():
            if any(keyword.lower() in html_lower for keyword in keywords):
                analytics_detected.append(service)
        
        return analytics_detected if analytics_detected else None
    
    def detect_cms(self, soup, html_content):
        """Détecte le CMS utilisé et sa version"""
        html_lower = html_content.lower() if html_content else ''
        html_content_full = html_content if html_content else ''
        
        for cms, patterns in self.cms_patterns.items():
            for pattern in patterns:
                if re.search(pattern, html_lower, re.I):
                    # Détecter la version
                    version = None
                    
                    # WordPress
                    if cms == 'WordPress':
                        # Meta generator
                        meta_gen = soup.find('meta', {'name': 'generator'}) if soup else None
                        if meta_gen:
                            gen_content = meta_gen.get('content', '')
                            version_match = re.search(r'wordpress\s+(\d+\.\d+(?:\.\d+)?)', gen_content, re.I)
                            if version_match:
                                version = version_match.group(1)
                        # Commentaires HTML
                        if not version:
                            version_match = re.search(r'wordpress\s+(\d+\.\d+(?:\.\d+)?)', html_content_full, re.I)
                            if version_match:
                                version = version_match.group(1)
                        # Version dans les fichiers CSS/JS
                        if not version:
                            version_match = re.search(r'ver=(\d+\.\d+(?:\.\d+)?)', html_content_full)
                            if version_match:
                                version = version_match.group(1)
                    
                    # Drupal
                    elif cms == 'Drupal':
                        meta_gen = soup.find('meta', {'name': 'generator'}) if soup else None
                        if meta_gen:
                            gen_content = meta_gen.get('content', '')
                            version_match = re.search(r'drupal\s+(\d+\.\d+(?:\.\d+)?)', gen_content, re.I)
                            if version_match:
                                version = version_match.group(1)
                        # Version dans les fichiers
                        if not version:
                            version_match = re.search(r'drupal\.js\?v=(\d+\.\d+(?:\.\d+)?)', html_content_full, re.I)
                            if version_match:
                                version = version_match.group(1)
                    
                    # Joomla
                    elif cms == 'Joomla':
                        meta_gen = soup.find('meta', {'name': 'generator'}) if soup else None
                        if meta_gen:
                            gen_content = meta_gen.get('content', '')
                            version_match = re.search(r'joomla[!\s]+(\d+\.\d+(?:\.\d+)?)', gen_content, re.I)
                            if version_match:
                                version = version_match.group(1)
                        # Version dans les fichiers
                        if not version:
                            version_match = re.search(r'joomla[.\s]+(\d+\.\d+(?:\.\d+)?)', html_content_full, re.I)
                            if version_match:
                                version = version_match.group(1)
                    
                    # Magento
                    elif cms == 'Magento':
                        # Version dans les fichiers JS/CSS
                        version_match = re.search(r'magento[.\s]+(\d+\.\d+(?:\.\d+)?)', html_content_full, re.I)
                        if version_match:
                            version = version_match.group(1)
                        # Version dans les meta tags
                        if not version:
                            meta_version = soup.find('meta', {'name': 'generator'}) if soup else None
                            if meta_version:
                                gen_content = meta_version.get('content', '')
                                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', gen_content)
                                if version_match:
                                    version = version_match.group(1)
                    
                    # PrestaShop
                    elif cms == 'PrestaShop':
                        version_match = re.search(r'prestashop[.\s]+(\d+\.\d+(?:\.\d+)?)', html_content_full, re.I)
                        if version_match:
                            version = version_match.group(1)
                    
                    # Shopify
                    elif cms == 'Shopify':
                        # Shopify ne révèle généralement pas sa version, mais on peut chercher dans les scripts
                        version_match = re.search(r'shopify[.\s]+(\d+\.\d+(?:\.\d+)?)', html_content_full, re.I)
                        if version_match:
                            version = version_match.group(1)
                    
                    # Retourner le CMS avec sa version si trouvée
                    if version:
                        return {'name': cms, 'version': version}
                    else:
                        return {'name': cms, 'version': None}
        
        return None
    
    def analyze_technical_details(self, url, enable_nmap=False):
        """Analyse technique complète et approfondie d'un site web
        
        Args:
            url: URL du site à analyser
            enable_nmap: Si True, effectue un scan nmap (peut être long)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            
            if not domain:
                return {'error': 'Domaine invalide'}
            
            # Nettoyer le domaine
            domain_clean = domain.replace('www.', '')
            
            results = {}
            
            # Headers HTTP
            headers = self.get_server_headers(url)
            results.update(self.get_http_dates(headers))
            
            # Informations serveur
            server_info = self.detect_server_software(headers)
            results.update(server_info)
            
            # Informations domaine
            domain_info = self.get_domain_info(domain_clean)
            results.update(domain_info)
            
            # Analyse DNS avancée
            try:
                from technical_analyzer_advanced import analyze_dns_advanced
                dns_advanced = analyze_dns_advanced(domain_clean)
                results.update(dns_advanced)
            except:
                pass
            
            # Hébergeur
            ip = domain_info.get('ip_address')
            hosting_info = self.detect_hosting_provider(domain_clean, ip)
            results.update(hosting_info)
            
            # Récupérer le contenu HTML pour analyses approfondies
            response = None
            soup = None
            html_content = None
            try:
                response = requests.get(url, headers=self.headers, timeout=15, allow_redirects=True)
                soup = BeautifulSoup(response.text, 'html.parser')
                html_content = response.text
                
                # Framework et CMS
                framework_info = self.detect_framework_version(soup, html_content, headers)
                results.update(framework_info)
                
                # Détection CMS
                cms_info = self.detect_cms(soup, html_content)
                if cms_info:
                    if isinstance(cms_info, dict):
                        results['cms'] = cms_info.get('name')
                        results['cms_version'] = cms_info.get('version')
                    else:
                        # Compatibilité avec l'ancien format
                        results['cms'] = cms_info
                    # Détection de plugins
                    try:
                        from technical_analyzer_advanced import detect_cms_plugins
                        cms_name = cms_info.get('name') if isinstance(cms_info, dict) else cms_info
                        plugins = detect_cms_plugins(soup, html_content, cms_name)
                        if plugins:
                            results['cms_plugins'] = plugins
                    except:
                        pass
                
                # CDN
                cdn = self._detect_cdn(headers, html_content)
                if cdn:
                    results['cdn'] = cdn
                
                # Analytics
                analytics = self._detect_analytics(soup, html_content)
                if analytics:
                    results['analytics'] = analytics
                
                # Services tiers
                try:
                    from technical_analyzer_advanced import detect_third_party_services
                    third_party = detect_third_party_services(soup, html_content)
                    results.update(third_party)
                except:
                    pass
                
                # SEO
                try:
                    from technical_analyzer_advanced import analyze_seo_meta
                    seo_info = analyze_seo_meta(soup)
                    results.update(seo_info)
                except:
                    pass
                
                # Langage backend
                try:
                    from technical_analyzer_advanced import detect_backend_language
                    backend_lang = detect_backend_language(headers, html_content)
                    if backend_lang:
                        results['backend_language'] = backend_lang
                except:
                    pass
                
                # Performance
                try:
                    from technical_analyzer_advanced import analyze_performance_hints
                    perf_info = analyze_performance_hints(headers, html_content)
                    results.update(perf_info)
                except:
                    pass
                
                # WAF
                try:
                    from technical_analyzer_advanced import detect_waf
                    waf = detect_waf(headers, html_content)
                    if waf:
                        results['waf'] = waf
                except:
                    pass
                
                # Cookies
                try:
                    from technical_analyzer_advanced import detect_cookies
                    cookies_info = detect_cookies(headers)
                    results.update(cookies_info)
                except:
                    pass
                
                # Security headers
                try:
                    from technical_analyzer_advanced import analyze_security_headers
                    security_info = analyze_security_headers(headers)
                    results.update(security_info)
                except:
                    pass
                
                # Performance avancée
                if response:
                    try:
                        from technical_analyzer_advanced import analyze_performance_advanced
                        perf_advanced = analyze_performance_advanced(url, response, html_content)
                        results.update(perf_advanced)
                    except:
                        pass
                
                # Frameworks modernes
                try:
                    from technical_analyzer_advanced import detect_modern_frameworks
                    modern_frameworks = detect_modern_frameworks(soup, html_content, headers)
                    results.update(modern_frameworks)
                except:
                    pass
                
                # Structure du contenu
                try:
                    from technical_analyzer_advanced import analyze_content_structure
                    content_structure = analyze_content_structure(soup, html_content)
                    results.update(content_structure)
                except:
                    pass
                
                # Sécurité avancée
                try:
                    from technical_analyzer_advanced import analyze_security_advanced
                    security_advanced = analyze_security_advanced(url, headers, html_content)
                    results.update(security_advanced)
                except:
                    pass
                
                # Mobilité et accessibilité
                try:
                    from technical_analyzer_advanced import analyze_mobile_accessibility
                    mobile_info = analyze_mobile_accessibility(soup, html_content)
                    results.update(mobile_info)
                except:
                    pass
                
                # API endpoints
                try:
                    from technical_analyzer_advanced import detect_api_endpoints
                    api_info = detect_api_endpoints(soup, html_content)
                    results.update(api_info)
                except:
                    pass
                
                # Plus de services tiers
                try:
                    from technical_analyzer_advanced import detect_more_services
                    more_services = detect_more_services(soup, html_content)
                    results.update(more_services)
                except:
                    pass
                
            except Exception as e:
                pass  # Continuer même si le HTML ne peut pas être récupéré
            
            # SSL/TLS
            try:
                from technical_analyzer_advanced import analyze_ssl_certificate
                ssl_info = analyze_ssl_certificate(domain_clean)
                results.update(ssl_info)
            except:
                pass
            
            # Robots.txt
            try:
                from technical_analyzer_advanced import analyze_robots_txt
                robots_info = analyze_robots_txt(url)
                results.update(robots_info)
            except:
                pass
            
            # Sitemap
            try:
                from technical_analyzer_advanced import analyze_sitemap
                sitemap_info = analyze_sitemap(url)
                results.update(sitemap_info)
            except:
                pass
            
            # Scan nmap (optionnel, peut être long)
            if enable_nmap:
                nmap_results = self.nmap_scan(domain_clean, ip)
                results.update(nmap_results)
            
            return results
        
        except Exception as e:
            return {'error': f'Erreur analyse technique: {str(e)[:100]}'}

