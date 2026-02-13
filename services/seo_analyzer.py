"""
Service d'analyse SEO
Analyse des métadonnées, structure HTML, sitemap, robots.txt, et audit Lighthouse si disponible
"""

import subprocess
import shutil
import json
import re
import os
import logging
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional, Callable
import requests
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)

# Importer la configuration
try:
    from config import SEO_TOOL_TIMEOUT
except ImportError:
    SEO_TOOL_TIMEOUT = int(os.environ.get('SEO_TOOL_TIMEOUT', '120'))


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
        use_lighthouse: bool = True
    ) -> Dict:
        """
        Analyse SEO complète d'un site web
        
        Args:
            url: URL à analyser
            progress_callback: Fonction de callback pour la progression
            use_lighthouse: Utiliser Lighthouse si disponible
            
        Returns:
            dict: Résultats de l'analyse SEO
        """
        results = {
            'url': url,
            'domain': urlparse(url).netloc,
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
            # Normaliser l'URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            parsed = urlparse(url)
            base_url = f'{parsed.scheme}://{parsed.netloc}'
            
            if progress_callback:
                progress_callback('Récupération de la page principale...')
            
            # Récupérer la page HTML
            try:
                response = requests.get(url, headers=self.headers, timeout=30, allow_redirects=True)
                response.raise_for_status()
                html_content = response.text
                final_url = response.url
            except Exception as e:
                results['error'] = f'Erreur lors de la récupération de la page: {str(e)}'
                logger.error(f'Erreur récupération {url}: {e}')
                return results
            
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
            
            # Audit Lighthouse si disponible
            if use_lighthouse and self.tools['lighthouse']:
                if progress_callback:
                    progress_callback('Audit Lighthouse (SEO/perfs)...')
                results['lighthouse'] = self._run_lighthouse(url)
            
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
            logger.error(f'Erreur analyse SEO pour {url}: {e}', exc_info=True)
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
            
            # Exécuter Lighthouse
            cmd = [
                'lighthouse',
                url,
                '--output=json',
                '--output-path=' + output_path,
                '--chrome-flags=--headless --no-sandbox',
                '--quiet',
                '--only-categories=seo,performance'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SEO_TOOL_TIMEOUT
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
