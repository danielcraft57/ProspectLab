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

# Importer la configuration
try:
    from config import WSL_DISTRO, WSL_USER
except ImportError:
    # Valeurs par défaut si config n'est pas disponible
    import os
    WSL_DISTRO = os.environ.get('WSL_DISTRO', 'kali-linux')
    WSL_USER = os.environ.get('WSL_USER', 'loupix')


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
            # Essayer d'abord avec l'utilisateur configuré
            try:
                test_result = subprocess.run(
                    ['wsl', '-d', WSL_DISTRO, '-u', WSL_USER, 'which', 'nmap'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if test_result.returncode == 0:
                    self.nmap_method = 'wsl'
                    self.nmap_cmd_base = ['wsl', '-d', WSL_DISTRO, '-u', WSL_USER, 'nmap']
                    return
            except:
                pass
            
            # Si ça échoue, essayer sans spécifier l'utilisateur
            try:
                test_result = subprocess.run(
                    ['wsl', '-d', WSL_DISTRO, 'nmap', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if test_result.returncode == 0 or 'Nmap version' in test_result.stdout:
                    self.nmap_method = 'wsl'
                    self.nmap_cmd_base = ['wsl', '-d', WSL_DISTRO, 'nmap']
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
            cmd = self.nmap_cmd_base + ['-F', '-sV', '--version-intensity', '0', '-O', '--osscan-guess', ip]
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
                dns_advanced = analyze_dns_advanced(domain_clean)
                results.update(dns_advanced)
            except Exception:
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
                        cms_name = cms_info.get('name') if isinstance(cms_info, dict) else cms_info
                        plugins = detect_cms_plugins(soup, html_content, cms_name)
                        if plugins:
                            results['cms_plugins'] = plugins
                    except Exception:
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
                    third_party = detect_third_party_services(soup, html_content)
                    results.update(third_party)
                except Exception:
                    pass
                
                # SEO
                try:
                    seo_info = analyze_seo_meta(soup)
                    results.update(seo_info)
                except Exception:
                    pass
                
                # Langage backend
                try:
                    backend_lang = detect_backend_language(headers, html_content)
                    if backend_lang:
                        results['backend_language'] = backend_lang
                except Exception:
                    pass
                
                # Performance
                try:
                    perf_info = analyze_performance_hints(headers, html_content)
                    results.update(perf_info)
                except Exception:
                    pass
                
                # WAF
                try:
                    waf = detect_waf(headers, html_content)
                    if waf:
                        results['waf'] = waf
                except Exception:
                    pass
                
                # Cookies
                try:
                    cookies_info = detect_cookies(headers)
                    results.update(cookies_info)
                except Exception:
                    pass
                
                # Security headers
                try:
                    security_info = analyze_security_headers(headers)
                    results.update(security_info)
                except Exception:
                    pass
                
                # Performance avancée
                if response:
                    try:
                        perf_advanced = analyze_performance_advanced(url, response, html_content)
                        results.update(perf_advanced)
                    except Exception:
                        pass
                
                # Frameworks modernes
                try:
                    modern_frameworks = detect_modern_frameworks(soup, html_content, headers)
                    results.update(modern_frameworks)
                except Exception:
                    pass
                
                # Structure du contenu
                try:
                    content_structure = analyze_content_structure(soup, html_content)
                    results.update(content_structure)
                except Exception:
                    pass
                
                # Sécurité avancée
                try:
                    security_advanced = analyze_security_advanced(url, headers, html_content)
                    results.update(security_advanced)
                except Exception:
                    pass
                
                # Mobilité et accessibilité
                try:
                    mobile_info = analyze_mobile_accessibility(soup, html_content)
                    results.update(mobile_info)
                except Exception:
                    pass
                
                # API endpoints
                try:
                    api_info = detect_api_endpoints(soup, html_content)
                    results.update(api_info)
                except Exception:
                    pass
                
                # Plus de services tiers
                try:
                    more_services = detect_more_services(soup, html_content)
                    results.update(more_services)
                except Exception:
                    pass
                
            except Exception as e:
                pass  # Continuer même si le HTML ne peut pas être récupéré
            
            # SSL/TLS
            try:
                ssl_info = analyze_ssl_certificate(domain_clean)
                results.update(ssl_info)
            except Exception:
                pass
            
            # Robots.txt
            try:
                robots_info = analyze_robots_txt(url)
                results.update(robots_info)
            except Exception:
                pass
            
            # Sitemap
            try:
                sitemap_info = analyze_sitemap(url)
                results.update(sitemap_info)
            except Exception:
                pass
            
            # Scan nmap (optionnel, peut être long)
            if enable_nmap:
                nmap_results = self.nmap_scan(domain_clean, ip)
                results.update(nmap_results)
            
            return results
        
        except Exception as e:
            return {'error': f'Erreur analyse technique: {str(e)[:100]}'}


def analyze_ssl_certificate(domain):
    """Analyse le certificat SSL/TLS (helper avancé)."""
    ssl_info = {}
    import ssl as _ssl
    try:
        context = _ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                ssl_info['ssl_issuer'] = dict(x[0] for x in cert.get('issuer', []))
                ssl_info['ssl_subject'] = dict(x[0] for x in cert.get('subject', []))
                ssl_info['ssl_version'] = ssock.version()
                if cert.get('notBefore'):
                    ssl_info['ssl_valid_from'] = cert['notBefore']
                if cert.get('notAfter'):
                    ssl_info['ssl_valid_until'] = cert['notAfter']
                    try:
                        from email.utils import parsedate_to_datetime
                        valid_until = parsedate_to_datetime(cert['notAfter'])
                        days_left = (valid_until - datetime.now()).days
                        ssl_info['ssl_days_until_expiry'] = days_left
                    except Exception:
                        pass
                ssl_info['ssl_cipher'] = ssock.cipher()
    except Exception as e:
        ssl_info['ssl_error'] = str(e)[:100]
    return ssl_info


def detect_cms_plugins(soup, html_content, cms_type):
    """Détecte les plugins/extensions selon le CMS."""
    plugins = []
    html_lower = html_content.lower()
    if cms_type == 'WordPress':
        wp_plugins = [
            'woocommerce', 'yoast', 'elementor', 'contact-form-7',
            'akismet', 'jetpack', 'wp-rocket', 'wp-super-cache',
            'wordfence', 'sucuri', 'all-in-one-seo', 'rank-math'
        ]
        for plugin in wp_plugins:
            if plugin in html_lower or f'/{plugin}/' in html_lower:
                plugins.append(plugin)
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
    """Détecte les services tiers utilisés."""
    services = {}
    html_lower = html_content.lower()
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
    """Analyse le fichier robots.txt."""
    robots_info = {}
    try:
        from urllib.parse import urljoin
        robots_url = urljoin(base_url, '/robots.txt')
        response = requests.get(robots_url, timeout=5)
        if response.status_code == 200:
            robots_info['robots_txt_exists'] = True
            content = response.text.lower()
            if 'user-agent' in content:
                robots_info['robots_has_rules'] = True
            sitemap_match = re.search(r'sitemap:\s*(.+)', content, re.I)
            if sitemap_match:
                robots_info['sitemap_url'] = sitemap_match.group(1).strip()
        else:
            robots_info['robots_txt_exists'] = False
    except Exception:
        robots_info['robots_txt_exists'] = False
    return robots_info


def analyze_sitemap(base_url):
    """Analyse le sitemap.xml."""
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
            except Exception:
                pass
        else:
            sitemap_info['sitemap_exists'] = False
    except Exception:
        sitemap_info['sitemap_exists'] = False
    return sitemap_info


def detect_waf(headers, html_content):
    """Détecte un WAF éventuel."""
    waf_detected = None
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
    html_lower = html_content.lower()
    if 'cloudflare' in html_lower and 'checking your browser' in html_lower:
        waf_detected = 'Cloudflare'
    elif 'sucuri' in html_lower:
        waf_detected = 'Sucuri'
    return waf_detected


def analyze_seo_meta(soup):
    """Analyse les meta tags SEO."""
    seo_info = {}
    title = soup.find('title')
    if title:
        seo_info['meta_title'] = title.get_text().strip()[:200]
        seo_info['meta_title_length'] = len(seo_info['meta_title'])
    meta_desc = soup.find('meta', {'name': 'description'})
    if meta_desc:
        seo_info['meta_description'] = meta_desc.get('content', '').strip()[:300]
        seo_info['meta_description_length'] = len(seo_info['meta_description'])
    meta_keywords = soup.find('meta', {'name': 'keywords'})
    if meta_keywords:
        seo_info['meta_keywords'] = meta_keywords.get('content', '').strip()[:200]
    og_tags = {}
    for tag in soup.find_all('meta', property=re.compile(r'^og:')):
        prop = tag.get('property', '').replace('og:', '')
        og_tags[prop] = tag.get('content', '')
    if og_tags:
        seo_info['open_graph'] = json.dumps(og_tags)
    twitter_tags = {}
    for tag in soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')}):
        name = tag.get('name', '').replace('twitter:', '')
        twitter_tags[name] = tag.get('content', '')
    if twitter_tags:
        seo_info['twitter_cards'] = json.dumps(twitter_tags)
    canonical = soup.find('link', {'rel': 'canonical'})
    if canonical:
        seo_info['canonical_url'] = canonical.get('href', '')
    hreflang_tags = []
    for tag in soup.find_all('link', {'rel': 'alternate', 'hreflang': True}):
        hreflang_tags.append(f"{tag.get('hreflang')}: {tag.get('href')}")
    if hreflang_tags:
        seo_info['hreflang'] = '; '.join(hreflang_tags[:5])
    return seo_info


def detect_backend_language(headers, html_content):
    """Détecte le langage backend probable."""
    languages = []
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
    if '<?php' in html_content:
        languages.append('PHP')
    return ', '.join(languages) if languages else None


def analyze_performance_hints(headers, html_content):
    """Analyse quelques indicateurs de performance."""
    perf_info = {}
    if headers.get('HTTP/2') or 'h2' in str(headers.get('Upgrade', '')).lower():
        perf_info['http_version'] = 'HTTP/2'
    elif 'HTTP/1.1' in str(headers):
        perf_info['http_version'] = 'HTTP/1.1'
    if 'gzip' in headers.get('Content-Encoding', '').lower():
        perf_info['compression'] = 'Gzip'
    elif 'br' in headers.get('Content-Encoding', '').lower():
        perf_info['compression'] = 'Brotli'
    if 'Cache-Control' in headers:
        perf_info['cache_control'] = headers['Cache-Control']
    if 'ETag' in headers:
        perf_info['etag'] = True
    if 'Last-Modified' in headers:
        perf_info['last_modified_header'] = True
    cdn_headers = ['cf-ray', 'x-cache', 'x-amz-cf-id', 'x-served-by']
    for header in cdn_headers:
        if header in headers:
            perf_info['cdn_detected'] = True
            break
    if 'loading="lazy"' in html_content or 'data-src=' in html_content:
        perf_info['lazy_loading'] = True
    if '.min.js' in html_content or '.min.css' in html_content:
        perf_info['minified_assets'] = True
    return perf_info


def detect_cookies(headers):
    """Analyse les cookies présents dans les headers."""
    cookies_info = {}
    if 'Set-Cookie' in headers:
        cookies = headers.get('Set-Cookie', [])
        if isinstance(cookies, str):
            cookies = [cookies]
        cookies_info['cookies_count'] = len(cookies)
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
    """Analyse les principaux headers de sécurité."""
    security = {}
    security_headers = {
        'X-Frame-Options': 'Clickjacking protection',
        'X-Content-Type-Options': 'MIME type sniffing protection',
        'X-XSS-Protection': 'XSS protection',
        'Strict-Transport-Security': 'HSTS',
        'Content-Security-Policy': 'CSP',
        'Referrer-Policy': 'Referrer policy',
        'Permissions-Policy': 'Permissions policy'
    }
    for header in security_headers.keys():
        if header in headers:
            security[header.lower().replace('-', '_')] = headers[header]
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
    """Analyse de performance avancée (taille, ressources...)."""
    perf_info = {}
    try:
        perf_info['response_time_ms'] = int(response.elapsed.total_seconds() * 1000)
        perf_info['page_size_bytes'] = len(response.content)
        perf_info['page_size_kb'] = round(perf_info['page_size_bytes'] / 1024, 2)
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')
        perf_info['images_count'] = len(images)
        images_without_alt = len([img for img in images if not img.get('alt')])
        if images_without_alt > 0:
            perf_info['images_missing_alt'] = images_without_alt
        scripts = soup.find_all('script')
        perf_info['scripts_count'] = len(scripts)
        external_scripts = len([s for s in scripts if s.get('src')])
        perf_info['external_scripts_count'] = external_scripts
        stylesheets = soup.find_all('link', {'rel': 'stylesheet'})
        perf_info['stylesheets_count'] = len(stylesheets)
        links = soup.find_all('a', href=True)
        perf_info['links_count'] = len(links)
        font_links = soup.find_all('link', {'rel': re.compile(r'font|preload', re.I)})
        perf_info['fonts_count'] = len(font_links)
        images_without_lazy = len([img for img in images if not img.get('loading') and not img.get('data-src')])
        if images_without_lazy > 0:
            perf_info['images_without_lazy_loading'] = images_without_lazy
        large_images = 0
        for img in images:
            if img.get('width') and img.get('height'):
                try:
                    width = int(img.get('width'))
                    height = int(img.get('height'))
                    if width > 1920 or height > 1080:
                        large_images += 1
                except Exception:
                    pass
        if large_images > 0:
            perf_info['potentially_large_images'] = large_images
    except Exception:
        pass
    return perf_info


def detect_modern_frameworks(soup, html_content, headers):
    """Détecte les frameworks modernes (Next, Nuxt, Svelte, etc.)."""
    frameworks = {}
    html_lower = html_content.lower()
    if '__next' in html_lower or '_next' in html_lower or 'next.js' in html_lower:
        frameworks['nextjs'] = True
        for script in soup.find_all('script', src=True):
            src = script.get('src', '')
            version_match = re.search(r'next[.-]?(\d+\.\d+(?:\.\d+)?)', src, re.I)
            if version_match:
                frameworks['nextjs_version'] = version_match.group(1)
                break
    if '__nuxt' in html_lower or 'nuxt' in html_lower:
        frameworks['nuxtjs'] = True
    if 'svelte' in html_lower or '__svelte' in html_lower:
        frameworks['svelte'] = True
    if 'gatsby' in html_lower or '__gatsby' in html_lower:
        frameworks['gatsby'] = True
    if 'remix' in html_lower:
        frameworks['remix'] = True
    if 'astro' in html_lower or '__astro' in html_lower:
        frameworks['astro'] = True
    if 'sveltekit' in html_lower:
        frameworks['sveltekit'] = True
    if 'webpack' in html_lower:
        frameworks['webpack'] = True
    if 'vite' in html_lower:
        frameworks['vite'] = True
    if 'parcel' in html_lower:
        frameworks['parcel'] = True
    return frameworks


def analyze_content_structure(soup, html_content):
    """Analyse la structure du contenu (balises, headings, liens...)."""
    content_info = {}
    try:
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            content_info['html_language'] = html_tag.get('lang')
        meta_charset = soup.find('meta', {'charset': True})
        if meta_charset:
            content_info['charset'] = meta_charset.get('charset')
        else:
            meta_http_equiv = soup.find('meta', attrs={'http-equiv': re.compile(r'content-type', re.I)})
            if meta_http_equiv:
                content_match = re.search(r'charset=([^;]+)', meta_http_equiv.get('content', ''), re.I)
                if content_match:
                    content_info['charset'] = content_match.group(1).strip()
        semantic_tags = ['header', 'nav', 'main', 'article', 'section', 'aside', 'footer']
        semantic_count = {}
        for tag in semantic_tags:
            count = len(soup.find_all(tag))
            if count > 0:
                semantic_count[tag] = count
        if semantic_count:
            content_info['semantic_html_tags'] = semantic_count
        headings = {}
        for i in range(1, 7):
            h_tags = soup.find_all(f'h{i}')
            if h_tags:
                headings[f'h{i}'] = len(h_tags)
        if headings:
            content_info['headings_structure'] = headings
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
        forms = soup.find_all('form')
        if forms:
            content_info['forms_count'] = len(forms)
        iframes = soup.find_all('iframe')
        if iframes:
            content_info['iframes_count'] = len(iframes)
    except Exception:
        pass
    return content_info


def analyze_dns_advanced(domain):
    """Analyse DNS avancée (SPF, DKIM, DMARC, MX, IPv6...)."""
    dns_info = {}
    try:
        if not dns:
            return dns_info
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_list = []
            for rdata in mx_records:
                mx_list.append(f"{rdata.preference} {rdata.exchange}")
            if mx_list:
                dns_info['mx_records'] = '; '.join(mx_list[:5])
        except Exception:
            pass
        try:
            txt_records = dns.resolver.resolve(domain, 'TXT')
            txt_list = []
            for rdata in txt_records:
                txt_string = ' '.join([s.decode() if isinstance(s, bytes) else s for s in rdata.strings])
                txt_list.append(txt_string)
            for txt in txt_list:
                if txt.startswith('v=spf1'):
                    dns_info['spf_record'] = txt[:200]
                    break
            try:
                dmarc_records = dns.resolver.resolve(f'_dmarc.{domain}', 'TXT')
                for rdata in dmarc_records:
                    dmarc_string = ' '.join([s.decode() if isinstance(s, bytes) else s for s in rdata.strings])
                    if 'v=DMARC1' in dmarc_string:
                        dns_info['dmarc_record'] = dmarc_string[:200]
                        break
            except Exception:
                pass
            dkim_domains = [f'default._domainkey.{domain}', f'_domainkey.{domain}']
            for dkim_domain in dkim_domains:
                try:
                    dkim_records = dns.resolver.resolve(dkim_domain, 'TXT')
                    for rdata in dkim_records:
                        dkim_string = ' '.join([s.decode() if isinstance(s, bytes) else s for s in rdata.strings])
                        if 'v=DKIM1' in dkim_string:
                            dns_info['dkim_record'] = 'Présent'
                            break
                except Exception:
                    pass
        except Exception:
            pass
        try:
            aaaa_records = dns.resolver.resolve(domain, 'AAAA')
            if aaaa_records:
                dns_info['ipv6_support'] = True
                dns_info['ipv6_addresses'] = [str(rdata) for rdata in aaaa_records[:3]]
        except Exception:
            dns_info['ipv6_support'] = False
        try:
            cname_records = dns.resolver.resolve(domain, 'CNAME')
            if cname_records:
                dns_info['cname_records'] = [str(rdata.target) for rdata in cname_records]
        except Exception:
            pass
    except Exception:
        pass
    return dns_info


def analyze_security_advanced(url, headers, html_content):
    """Analyse de sécurité avancée (mixed content, SRI, CORS...)."""
    security_info = {}
    try:
        if url.startswith('https://'):
            soup = BeautifulSoup(html_content, 'html.parser')
            mixed_content = []
            for img in soup.find_all('img', src=True):
                src = img.get('src', '')
                if src.startswith('http://'):
                    mixed_content.append('Images HTTP')
                    break
            for script in soup.find_all('script', src=True):
                src = script.get('src', '')
                if src.startswith('http://'):
                    mixed_content.append('Scripts HTTP')
                    break
            for link in soup.find_all('link', {'rel': 'stylesheet'}, href=True):
                href = link.get('href', '')
                if href.startswith('http://'):
                    mixed_content.append('Stylesheets HTTP')
                    break
            if mixed_content:
                security_info['mixed_content_detected'] = '; '.join(set(mixed_content))
            else:
                security_info['mixed_content_detected'] = False
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
        if 'Access-Control-Allow-Origin' in headers:
            security_info['cors_enabled'] = headers['Access-Control-Allow-Origin']
        if 'Server' in headers:
            server_header = headers['Server']
            if len(server_header) > 20:
                security_info['server_header_detailed'] = True
    except Exception:
        pass
    return security_info


def analyze_mobile_accessibility(soup, html_content):
    """Analyse mobilité / accessibilité basique (viewport, alt, ARIA...)."""
    mobile_info = {}
    try:
        viewport = soup.find('meta', {'name': 'viewport'})
        if viewport:
            mobile_info['viewport_meta'] = viewport.get('content', '')
        else:
            mobile_info['viewport_meta'] = 'Manquant'
        mobile_friendly_indicators = [
            'width=device-width' in html_content.lower(),
            'initial-scale=1' in html_content.lower(),
            'maximum-scale=1' in html_content.lower()
        ]
        mobile_info['mobile_friendly'] = all(mobile_friendly_indicators) if viewport else False
        apple_touch_icon = soup.find('link', {'rel': re.compile(r'apple-touch-icon', re.I)})
        if apple_touch_icon:
            mobile_info['apple_touch_icon'] = True
        theme_color = soup.find('meta', {'name': 'theme-color'})
        if theme_color:
            mobile_info['theme_color'] = theme_color.get('content', '')
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]
        if images_without_alt:
            mobile_info['images_missing_alt_count'] = len(images_without_alt)
        elements_with_aria = soup.find_all(attrs={'aria-label': True})
        mobile_info['aria_labels_count'] = len(elements_with_aria)
        skip_links = soup.find_all('a', href=re.compile(r'#(main|content|skip)', re.I))
        if skip_links:
            mobile_info['skip_links'] = True
    except Exception:
        pass
    return mobile_info


def detect_api_endpoints(soup, html_content):
    """Détecte des patterns d'API (REST, GraphQL, WebSocket...)."""
    api_info = {}
    try:
        if '/graphql' in html_content.lower() or 'graphql' in html_content.lower():
            api_info['graphql_detected'] = True
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
        if 'ws://' in html_content.lower() or 'wss://' in html_content.lower():
            api_info['websocket_detected'] = True
        json_ld = soup.find_all('script', {'type': 'application/ld+json'})
        if json_ld:
            api_info['json_ld_count'] = len(json_ld)
            structured_data_types = []
            for script in json_ld:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and '@type' in data:
                        structured_data_types.append(data['@type'])
                    elif isinstance(data, list) and len(data) > 0 and '@type' in data[0]:
                        structured_data_types.append(data[0]['@type'])
                except Exception:
                    pass
            if structured_data_types:
                api_info['structured_data_types'] = ', '.join(set(structured_data_types)[:5])
    except Exception:
        pass
    return api_info


def detect_more_services(soup, html_content):
    """Détecte d'autres services tiers (CRM, vidéo, maps, fonts, commentaires...)."""
    services = {}
    html_lower = html_content.lower()
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
    map_services = {
        'Google Maps': ['maps.google', 'googleapis.com/maps'],
        'Mapbox': ['mapbox'],
        'OpenStreetMap': ['openstreetmap', 'osm.org']
    }
    for service, keywords in map_services.items():
        if any(keyword in html_lower for keyword in keywords):
            services['map_service'] = service
            break
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

