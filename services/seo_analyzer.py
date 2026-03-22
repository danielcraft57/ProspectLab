"""
Service d'analyse SEO
Analyse des métadonnées, structure HTML, sitemap, robots.txt, et audit Lighthouse si disponible
"""

import subprocess
import shutil
import json
import re
import os
import sys
import logging
from urllib.parse import urlparse, urljoin, urlunparse
from typing import Dict, List, Optional, Callable, Tuple
from ipaddress import ip_address
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout, Timeout as RequestsTimeout
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)

# Importer la configuration
try:
    from config import (
        SEO_TOOL_TIMEOUT,
        SEO_FETCH_CONNECT_TIMEOUT,
        SEO_FETCH_READ_TIMEOUT,
        CHROME_PATH,
    )
except ImportError:
    SEO_TOOL_TIMEOUT = int(os.environ.get('SEO_TOOL_TIMEOUT', '120'))
    SEO_FETCH_CONNECT_TIMEOUT = float(os.environ.get('SEO_FETCH_CONNECT_TIMEOUT', '12'))
    SEO_FETCH_READ_TIMEOUT = float(os.environ.get('SEO_FETCH_READ_TIMEOUT', '25'))
    CHROME_PATH = (os.environ.get('CHROME_PATH') or os.environ.get('LIGHTHOUSE_CHROME_PATH') or '').strip() or None


def _lighthouse_chrome_executable() -> Optional[str]:
    """Binaire Chrome/Chromium pour Lighthouse (CHROME_PATH ou emplacements Linux courants)."""
    def _usable(path: str) -> bool:
        return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)

    if CHROME_PATH and _usable(CHROME_PATH):
        return CHROME_PATH
    if sys.platform == 'win32':
        return None
    for candidate in (
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/google-chrome',
    ):
        if _usable(candidate):
            return candidate
    return None


def _host_is_ip(hostname: Optional[str]) -> bool:
    if not hostname:
        return False
    try:
        ip_address(hostname)
        return True
    except ValueError:
        return False


def _netloc_variants_www(netloc: str) -> List[str]:
    """
    Retourne 1 ou 2 netloc (avec / sans www), en conservant port et auth si présents.
    Pas de variante www pour IP, IPv6 littérale, ou netloc vide.
    """
    if not netloc or not str(netloc).strip():
        return []
    p = urlparse('http://' + netloc)
    host = p.hostname
    if not host or _host_is_ip(host):
        return [netloc]
    # IPv6 dans l'URL : hostname peut être sans crochets
    if host.startswith('[') or ('%' in host and ':' in host):
        return [netloc]

    port = p.port
    username = p.username
    password = p.password
    hl = host.lower()
    if hl.startswith('www.'):
        hosts = [host, host[4:]]
    else:
        hosts = [host, f'www.{host}']

    seen = []
    for h in hosts:
        auth = ''
        if username is not None:
            auth = username
            if password is not None:
                auth += ':' + password
            auth += '@'
        if port:
            nl = f'{auth}{h}:{port}'
        else:
            nl = f'{auth}{h}'
        if nl not in seen:
            seen.append(nl)
    return seen


def build_seo_url_candidates(raw: str) -> List[str]:
    """
    Construit une liste ordonnée d'URL à essayer automatiquement :
    - saisie normalisée (https par défaut si pas de schéma) ;
    - variantes https puis http ;
    - variantes avec / sans www (même domaine, même chemin et query).
    Dédupliquée, ordre préservé.
    """
    s = (raw or '').strip()
    if not s:
        return []
    if not s.startswith(('http://', 'https://')):
        s = 'https://' + s

    parsed = urlparse(s)
    if not parsed.netloc:
        return []

    path = parsed.path if parsed.path else '/'
    variants_netloc = _netloc_variants_www(parsed.netloc)
    schemes_order = ['https', 'http']

    out: List[str] = []
    # 1) URL telle que normalisée (souvent https)
    first = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
    out.append(first)

    for scheme in schemes_order:
        for nl in variants_netloc:
            u = urlunparse((scheme, nl, path, parsed.params, parsed.query, parsed.fragment))
            if u not in out:
                out.append(u)

    return out


def _seo_fetch_timeout_tuple() -> Tuple[float, float]:
    return (SEO_FETCH_CONNECT_TIMEOUT, SEO_FETCH_READ_TIMEOUT)


class SEOAnalyzer:
    """
    Analyseur SEO pour évaluer l'optimisation d'un site web
    """
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self._check_tools_availability()
    
    def _check_tools_availability(self):
        """Vérifie la disponibilité des outils SEO"""
        self.tools = {
            'lighthouse': self._check_tool('lighthouse'),
            'curl': self._check_tool('curl'),
            'wget': self._check_tool('wget'),
        }
    
    def _check_tool(self, tool_name: str) -> bool:
        """Vérifie si un outil est disponible (natif uniquement, pas de WSL pour SEO)"""
        return shutil.which(tool_name) is not None
    
    def get_diagnostic(self) -> Dict:
        """
        Retourne un résumé de l'environnement SEO (outils disponibles)
        
        Returns:
            dict: tools_available, tools_missing, message
        """
        available = [k for k, v in self.tools.items() if v]
        missing = [k for k, v in self.tools.items() if not v]
        
        if len(available) == 0:
            message = (
                'Aucun outil SEO détecté. Installez curl/wget (apt) et Lighthouse (npm install -g lighthouse). '
                'Les analyses basiques (meta tags, headers) fonctionnent avec Python + requests.'
            )
        else:
            message = f'{len(available)} outil(s) disponible(s), {len(missing)} manquant(s).'
            if 'lighthouse' not in available:
                message += ' Lighthouse non disponible (audit SEO/perfs limité).'
        
        return {
            'execution_mode': 'native',
            'tools_available': available,
            'tools_missing': missing,
            'message': message,
        }
    
    def analyze_seo(
        self,
        url: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        use_lighthouse: bool = False
    ) -> Dict:
        """
        Analyse SEO complète d'un site web
        
        Args:
            url: URL à analyser
            progress_callback: Fonction de callback pour la progression
            use_lighthouse: Si True, lance Lighthouse (désactivé par défaut)
            
        Returns:
            dict: Résultats de l'analyse SEO
        """
        url_initial = (url or '').strip()
        results = {
            'url': url_initial,
            'url_initial': url_initial,
            'domain': urlparse(url_initial if url_initial.startswith(('http://', 'https://')) else 'https://' + url_initial).netloc,
            'meta_tags': {},
            'headers': {},
            'structure': {},
            'sitemap': None,
            'robots': None,
            'lighthouse': None,
            'issues': [],
            'score': 0,
            'summary': {}
        }
        
        try:
            # Plusieurs stratégies automatiques : https/http, avec/sans www, même chemin
            candidates = build_seo_url_candidates(url_initial)
            if not candidates:
                results['error'] = 'URL vide ou invalide.'
                return results

            timeout_fetch = _seo_fetch_timeout_tuple()
            if progress_callback:
                n = len(candidates)
                if n > 1:
                    progress_callback(
                        f'Vérification automatique de l’URL ({n} variante(s) : protocole https/http, avec/sans www)...'
                    )
                else:
                    progress_callback('Récupération de la page principale...')

            response = None
            last_error: Optional[Exception] = None
            last_candidate_ok: Optional[str] = None
            fetch_log: List[Dict] = []

            for idx, candidate in enumerate(candidates):
                try:
                    if progress_callback and idx > 0:
                        short = candidate
                        if len(short) > 72:
                            short = short[:69] + '...'
                        progress_callback(f'Nouvel essai : {short}')
                    resp = requests.get(
                        candidate,
                        headers=self.headers,
                        timeout=timeout_fetch,
                        allow_redirects=True,
                    )
                    resp.raise_for_status()
                    response = resp
                    last_candidate_ok = candidate
                    fetch_log.append({'url': candidate, 'ok': True, 'status': resp.status_code})
                    break
                except requests.HTTPError as e:
                    last_error = e
                    status = e.response.status_code if e.response is not None else None
                    fetch_log.append({'url': candidate, 'ok': False, 'http_status': status})
                    logger.warning(f'HTTP {status} pour {candidate} lors de l\'analyse SEO')
                    if status in (401, 403) and idx + 1 < len(candidates):
                        if progress_callback:
                            progress_callback('Accès refusé, essai d’une autre variante d’URL...')
                        continue
                    if idx + 1 < len(candidates):
                        continue
                    break
                except Exception as e:
                    last_error = e
                    fetch_log.append({'url': candidate, 'ok': False, 'error': str(e)})
                    logger.error(f'Erreur récupération {candidate}: {e}')
                    if idx + 1 < len(candidates):
                        continue
                    break

            results['url_fetch_attempts'] = fetch_log

            if response is None:
                # Message plus lisible pour l’utilisateur
                if isinstance(last_error, requests.HTTPError):
                    status = last_error.response.status_code if last_error.response is not None else None
                    if status in (401, 403):
                        msg = (
                            f'Le site a refusé l\'accès (HTTP {status}). '
                            f'Certaines protections bloquent les robots : l’analyse SEO détaillée n’est pas possible.'
                        )
                    else:
                        msg = f'Erreur HTTP {status} lors de la récupération de la page.'
                else:
                    if isinstance(last_error, (ConnectTimeout, ReadTimeout, RequestsTimeout)):
                        msg = (
                            'Le site n\'a pas répondu à temps (connexion ou lecture trop lente). '
                            'Vérifiez l\'URL, que le site est joignable depuis le serveur, ou réessayez plus tard.'
                        )
                    else:
                        msg = f'Erreur lors de la récupération de la page: {str(last_error)}'
                results['error'] = msg
                logger.error(f'Erreur récupération (dernière URL essayée): {last_error}')
                return results

            html_content = response.text
            final_url = response.url
            parsed_final = urlparse(final_url)
            base_url = f'{parsed_final.scheme}://{parsed_final.netloc}'
            results['url'] = final_url
            results['domain'] = parsed_final.netloc
            if last_candidate_ok and last_candidate_ok.rstrip('/') != final_url.rstrip('/'):
                results['url_opened_with'] = last_candidate_ok

            if progress_callback:
                progress_callback('Analyse des meta tags...')
            
            # Analyser les meta tags
            results['meta_tags'] = self._analyze_meta_tags(html_content, final_url)
            
            if progress_callback:
                progress_callback('Analyse des headers HTTP...')
            
            # Analyser les headers HTTP
            results['headers'] = self._analyze_headers(response.headers)
            
            if progress_callback:
                progress_callback('Analyse de la structure HTML...')
            
            # Analyser la structure HTML
            results['structure'] = self._analyze_structure(html_content)
            
            if progress_callback:
                progress_callback('Recherche du sitemap...')
            
            # Chercher le sitemap
            results['sitemap'] = self._check_sitemap(base_url)
            
            if progress_callback:
                progress_callback('Recherche de robots.txt...')
            
            # Chercher robots.txt
            results['robots'] = self._check_robots(base_url)
            
            # Audit Lighthouse si disponible (URL finale après redirections)
            if use_lighthouse and self.tools['lighthouse']:
                if progress_callback:
                    progress_callback('Audit Lighthouse (SEO/perfs)...')
                results['lighthouse'] = self._run_lighthouse(final_url)
            
            # Calculer le score SEO
            results['score'] = self._calculate_seo_score(results)
            
            # Détecter les problèmes
            results['issues'] = self._detect_issues(results)
            
            # Résumé
            results['summary'] = {
                'has_title': bool(results['meta_tags'].get('title')),
                'has_description': bool(results['meta_tags'].get('description')),
                'has_og_tags': bool(results['meta_tags'].get('og:title')),
                'has_twitter_tags': bool(results['meta_tags'].get('twitter:card')),
                'has_sitemap': results['sitemap'] is not None,
                'has_robots': results['robots'] is not None,
                'h1_count': results['structure'].get('h1_count', 0),
                'images_without_alt': results['structure'].get('images_without_alt', 0),
                'lighthouse_score': results['lighthouse'].get('score') if results['lighthouse'] else None,
            }
            
        except Exception as e:
            logger.error(f'Erreur analyse SEO pour {url_initial}: {e}', exc_info=True)
            results['error'] = str(e)
        
        return results
    
    def _analyze_meta_tags(self, html_content: str, base_url: str) -> Dict:
        """Analyse les meta tags de la page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        meta_tags = {}
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            meta_tags['title'] = title_tag.get_text(strip=True)
        
        # Meta description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            meta_tags['description'] = desc_tag.get('content', '')
        
        # Meta keywords
        keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_tag:
            meta_tags['keywords'] = keywords_tag.get('content', '')
        
        # Open Graph
        og_tags = soup.find_all('meta', attrs={'property': re.compile(r'^og:')})
        for tag in og_tags:
            prop = tag.get('property', '')
            content = tag.get('content', '')
            if prop and content:
                meta_tags[prop] = content
        
        # Twitter Card
        twitter_tags = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')})
        for tag in twitter_tags:
            name = tag.get('name', '')
            content = tag.get('content', '')
            if name and content:
                meta_tags[name] = content
        
        # Canonical
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical:
            canonical_url = canonical.get('href', '')
            if canonical_url:
                meta_tags['canonical'] = urljoin(base_url, canonical_url)
        
        # Viewport
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        if viewport:
            meta_tags['viewport'] = viewport.get('content', '')
        
        # Charset
        charset = soup.find('meta', attrs={'charset': True})
        if charset:
            meta_tags['charset'] = charset.get('charset', '')
        else:
            # Chercher dans http-equiv
            charset_equiv = soup.find('meta', attrs={'http-equiv': re.compile(r'content-type', re.I)})
            if charset_equiv:
                content = charset_equiv.get('content', '')
                charset_match = re.search(r'charset=([^;]+)', content, re.I)
                if charset_match:
                    meta_tags['charset'] = charset_match.group(1)
        
        return meta_tags
    
    def _analyze_headers(self, headers: Dict) -> Dict:
        """Analyse les headers HTTP"""
        analyzed = {}
        
        # Headers de sécurité
        security_headers = [
            'X-Frame-Options',
            'X-Content-Type-Options',
            'X-XSS-Protection',
            'Strict-Transport-Security',
            'Content-Security-Policy',
            'Referrer-Policy',
            'Permissions-Policy',
        ]
        
        for header in security_headers:
            if header in headers:
                analyzed[header] = headers[header]
        
        # Autres headers utiles
        useful_headers = [
            'Server',
            'X-Powered-By',
            'Cache-Control',
            'ETag',
            'Last-Modified',
        ]
        
        for header in useful_headers:
            if header in headers:
                analyzed[header] = headers[header]
        
        return analyzed
    
    def _analyze_structure(self, html_content: str) -> Dict:
        """Analyse la structure HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        structure = {}
        
        # Titres
        structure['h1_count'] = len(soup.find_all('h1'))
        structure['h2_count'] = len(soup.find_all('h2'))
        structure['h3_count'] = len(soup.find_all('h3'))
        
        # Liste des h1 (pour vérifier qu'il n'y en a qu'un)
        h1_tags = soup.find_all('h1')
        structure['h1_texts'] = [h1.get_text(strip=True) for h1 in h1_tags]
        
        # Images sans alt
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]
        structure['images_total'] = len(images)
        structure['images_without_alt'] = len(images_without_alt)
        
        # Liens
        links = soup.find_all('a', href=True)
        internal_links = []
        external_links = []
        
        for link in links:
            href = link.get('href', '')
            if href.startswith(('http://', 'https://')):
                external_links.append(href)
            elif href.startswith('/') or not href.startswith(('mailto:', 'tel:', 'javascript:')):
                internal_links.append(href)
        
        structure['internal_links_count'] = len(internal_links)
        structure['external_links_count'] = len(external_links)
        
        # Langue
        html_tag = soup.find('html')
        if html_tag:
            structure['lang'] = html_tag.get('lang', '')
        
        return structure
    
    def _check_sitemap(self, base_url: str) -> Optional[Dict]:
        """Vérifie la présence d'un sitemap"""
        sitemap_urls = [
            f'{base_url}/sitemap.xml',
            f'{base_url}/sitemap_index.xml',
            f'{base_url}/sitemaps.xml',
        ]
        
        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    # Vérifier si c'est bien un XML de sitemap
                    if 'xml' in response.headers.get('Content-Type', '').lower():
                        return {
                            'url': sitemap_url,
                            'status': 'found',
                            'content_type': response.headers.get('Content-Type', '')
                        }
            except:
                continue
        
        # Chercher dans robots.txt
        robots_url = f'{base_url}/robots.txt'
        try:
            response = requests.get(robots_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                content = response.text
                sitemap_match = re.search(r'Sitemap:\s*(.+)', content, re.I)
                if sitemap_match:
                    sitemap_url = sitemap_match.group(1).strip()
                    return {
                        'url': sitemap_url,
                        'status': 'found_in_robots',
                        'source': 'robots.txt'
                    }
        except:
            pass
        
        return None
    
    def _check_robots(self, base_url: str) -> Optional[Dict]:
        """Vérifie la présence de robots.txt"""
        robots_url = f'{base_url}/robots.txt'
        
        try:
            response = requests.get(robots_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                content = response.text
                return {
                    'url': robots_url,
                    'status': 'found',
                    'content': content[:1000],  # Limiter la taille
                    'has_user_agent': 'User-agent:' in content,
                    'has_disallow': 'Disallow:' in content,
                    'has_allow': 'Allow:' in content,
                }
        except:
            pass
        
        return None
    
    def _run_lighthouse(self, url: str) -> Optional[Dict]:
        """Exécute Lighthouse pour un audit SEO/perfs"""
        if not self.tools['lighthouse']:
            return None
        
        try:
            # Créer un fichier temporaire pour le résultat JSON
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                output_path = f.name
            
            # Exécuter Lighthouse (chrome-launcher exige CHROME_PATH si Chrome n’est pas détecté, ex. Raspberry Pi)
            chrome_bin = _lighthouse_chrome_executable()
            cmd = [
                'lighthouse',
                url,
                '--output=json',
                '--output-path=' + output_path,
                '--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage',
                '--quiet',
                '--only-categories=seo,performance',
            ]
            if chrome_bin:
                cmd.insert(2, '--chrome-path=' + chrome_bin)

            run_env = os.environ.copy()
            if chrome_bin:
                run_env['CHROME_PATH'] = chrome_bin

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SEO_TOOL_TIMEOUT,
                env=run_env,
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'r', encoding='utf-8') as f:
                    lighthouse_data = json.load(f)
                
                # Extraire les scores SEO et performance
                categories = lighthouse_data.get('categories', {})
                seo_score = categories.get('seo', {}).get('score')
                perf_score = categories.get('performance', {}).get('score')
                
                # Extraire les audits SEO pertinents
                audits = lighthouse_data.get('audits', {})
                seo_audits = {}
                for key, audit in audits.items():
                    if audit.get('id', '').startswith('seo-') or key in ['meta-description', 'document-title']:
                        seo_audits[key] = {
                            'title': audit.get('title', ''),
                            'description': audit.get('description', ''),
                            'score': audit.get('score'),
                            'displayValue': audit.get('displayValue', '')
                        }
                
                os.unlink(output_path)
                
                return {
                    'score': seo_score,
                    'performance_score': perf_score,
                    'audits': seo_audits,
                    'raw_data': lighthouse_data  # Garder les données complètes
                }
            else:
                if os.path.exists(output_path):
                    os.unlink(output_path)
                logger.warning(f'Lighthouse a échoué: {result.stderr}')
                return None
                
        except subprocess.TimeoutExpired:
            logger.warning(f'Lighthouse timeout pour {url}')
            return None
        except Exception as e:
            logger.error(f'Erreur Lighthouse pour {url}: {e}')
            return None
    
    def _calculate_seo_score(self, results: Dict) -> int:
        """Calcule un score SEO basique (0-100)"""
        score = 0
        
        # Meta tags (40 points)
        if results['meta_tags'].get('title'):
            score += 10
        if results['meta_tags'].get('description'):
            score += 10
        if results['meta_tags'].get('canonical'):
            score += 5
        if results['meta_tags'].get('og:title'):
            score += 5
        if results['meta_tags'].get('viewport'):
            score += 5
        if results['meta_tags'].get('charset'):
            score += 5
        
        # Structure (20 points)
        h1_count = results['structure'].get('h1_count', 0)
        if h1_count == 1:
            score += 10
        elif h1_count > 1:
            score += 5  # Plusieurs h1, pas idéal mais mieux que rien
        
        images_without_alt = results['structure'].get('images_without_alt', 0)
        images_total = results['structure'].get('images_total', 0)
        if images_total > 0:
            alt_ratio = 1 - (images_without_alt / images_total)
            score += int(10 * alt_ratio)
        
        # Sitemap et robots (20 points)
        if results['sitemap']:
            score += 10
        if results['robots']:
            score += 10
        
        # Headers de sécurité (10 points)
        security_headers_count = len([
            k for k in results['headers'].keys()
            if k in ['X-Frame-Options', 'X-Content-Type-Options', 'Strict-Transport-Security']
        ])
        score += min(security_headers_count * 3, 10)
        
        # Lighthouse score si disponible (10 points bonus)
        if results['lighthouse'] and results['lighthouse'].get('score'):
            lighthouse_score = results['lighthouse']['score']
            if lighthouse_score:
                score += int(lighthouse_score * 10)
        
        return min(score, 100)
    
    def _detect_issues(self, results: Dict) -> List[Dict]:
        """Détecte les problèmes SEO"""
        issues = []
        
        # Pas de title
        if not results['meta_tags'].get('title'):
            issues.append({
                'type': 'critical',
                'category': 'meta_tags',
                'message': 'Balise <title> manquante',
                'impact': 'high'
            })
        
        # Pas de description
        if not results['meta_tags'].get('description'):
            issues.append({
                'type': 'warning',
                'category': 'meta_tags',
                'message': 'Meta description manquante',
                'impact': 'medium'
            })
        
        # Plusieurs h1
        h1_count = results['structure'].get('h1_count', 0)
        if h1_count > 1:
            issues.append({
                'type': 'warning',
                'category': 'structure',
                'message': f'{h1_count} balises <h1> trouvées (idéalement 1)',
                'impact': 'medium'
            })
        
        # Images sans alt
        images_without_alt = results['structure'].get('images_without_alt', 0)
        if images_without_alt > 0:
            issues.append({
                'type': 'warning',
                'category': 'accessibility',
                'message': f'{images_without_alt} image(s) sans attribut alt',
                'impact': 'medium'
            })
        
        # Pas de sitemap
        if not results['sitemap']:
            issues.append({
                'type': 'info',
                'category': 'sitemap',
                'message': 'Sitemap non trouvé',
                'impact': 'low'
            })
        
        # Pas de robots.txt
        if not results['robots']:
            issues.append({
                'type': 'info',
                'category': 'robots',
                'message': 'robots.txt non trouvé',
                'impact': 'low'
            })
        
        return issues
