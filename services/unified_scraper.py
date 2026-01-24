"""
Service de scraping qui combine toutes les fonctionnalités
Extrait emails, personnes, téléphones, réseaux sociaux, technologies et métadonnées en une seule passe
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import threading
import queue
import time
import json
import logging
from typing import Dict, List, Optional, Callable, Set
from datetime import datetime
from functools import lru_cache
from services.logging_config import setup_logger

# Configurer le logger pour écrire dans scraping_tasks.log
logger = setup_logger(__name__, 'scraping_tasks.log', level=logging.INFO)


class UnifiedScraper:
    """
    Scraper unifié qui extrait toutes les données en une seule passe
    """
    
    def __init__(self, base_url: str, max_workers: int = 5, max_depth: int = 3, 
                 max_time: int = 300, max_pages: int = 50, progress_callback: Optional[Callable] = None,
                 on_email_found: Optional[Callable] = None,
                 on_person_found: Optional[Callable] = None,
                 on_phone_found: Optional[Callable] = None,
                 on_social_found: Optional[Callable] = None):
        """
        Initialise le scraper unifié
        
        Args:
            base_url: URL de base à scraper
            max_workers: Nombre maximum de workers parallèles
            max_depth: Profondeur maximale de scraping
            max_time: Temps maximum de scraping en secondes
            max_pages: Nombre maximum de pages à scraper (limite pour éviter les sites trop volumineux)
            progress_callback: Fonction de callback pour les mises à jour de progression
            on_email_found: Callback appelé à chaque nouvel email trouvé
            on_person_found: Callback appelé à chaque nouvelle personne trouvée
            on_phone_found: Callback appelé à chaque nouveau téléphone trouvé
            on_social_found: Callback appelé à chaque nouveau réseau social trouvé
        """
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.max_workers = max_workers
        self.max_depth = max_depth
        self.max_time = max_time
        self.max_pages = max_pages  # Limite du nombre de pages à scraper
        self.progress_callback = progress_callback
        self.on_email_found = on_email_found
        self.on_person_found = on_person_found
        self.on_phone_found = on_phone_found
        self.on_social_found = on_social_found
        
        # Délai entre les requêtes pour éviter de surcharger les serveurs
        self.request_delay = 0.3  # 300ms entre chaque requête HTTP
        self.last_request_time = {}  # Dernière requête par domaine pour éviter de surcharger un même serveur
        
        # Données collectées
        self.links: Set[str] = set()
        self.emails: Dict[str, str] = {}  # email -> page_url (pour garder la trace de la page où l'email a été trouvé)
        self.people: List[Dict] = []
        self.people_by_name: Dict[str, Dict] = {}
        self.phones: Set[str] = set()
        self.social_links: Dict[str, List[Dict]] = {}
        self.technologies: Dict[str, List[str]] = {}
        self.metadata: Dict = {}  # Métadonnées de la page d'accueil (pour compatibilité)
        self.og_data_by_page: Dict[str, Dict] = {}  # OG de toutes les pages scrapées {page_url: og_tags}
        self.images: List[Dict] = []  # Liste des images trouvées avec {url, alt, page_url, width, height}
        self.forms: List[Dict] = []  # Points d'entrée (formulaires) trouvés sur les pages
        
        # État du scraping
        self.visited_urls: Set[str] = set()
        self.lock = threading.Lock()
        self.url_queue = queue.Queue()
        self.urls_in_progress = 0
        self.start_time: Optional[float] = None
        self.should_stop = False
        
        # Headers HTTP
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        # Compiler les regex pour de meilleures performances
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_patterns = [
            re.compile(r'0[1-9](?:[.\s-]?\d{2}){4}'),
            re.compile(r'\+33[.\s-]?[1-9](?:[.\s-]?\d{2}){4}'),
            re.compile(r'\(\d{2}\)[.\s-]?\d{2}[.\s-]?\d{2}[.\s-]?\d{2}[.\s-]?\d{2}')
        ]
        self.name_patterns = [
            re.compile(r'\b(M\.|Mme|Mr\.|Mrs\.|Dr\.|Prof\.|Monsieur|Madame)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'),
            re.compile(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\b')
        ]
        self.title_pattern = re.compile(r'[-–—]\s*([^,\n]+)')
        self.clean_phone_pattern = re.compile(r'[.\s-]')
        
        # Cache pour les URLs normalisées
        self._url_cache: Dict[str, Optional[str]] = {}
        
        # Réseaux sociaux à chercher
        self.social_platforms = {
            'facebook': ['facebook.com', 'fb.com', 'fb.me'],
            'twitter': ['twitter.com', 'x.com', 't.co'],
            'linkedin': ['linkedin.com', 'linked.in'],
            'instagram': ['instagram.com', 'instagr.am'],
            'youtube': ['youtube.com', 'youtu.be'],
            'tiktok': ['tiktok.com'],
            'pinterest': ['pinterest.com', 'pin.it'],
            'snapchat': ['snapchat.com'],
            'whatsapp': ['wa.me', 'whatsapp.com'],
            'telegram': ['t.me', 'telegram.org'],
            'github': ['github.com'],
            'gitlab': ['gitlab.com'],
            'bitbucket': ['bitbucket.org'],
            'medium': ['medium.com'],
            'reddit': ['reddit.com'],
            'discord': ['discord.gg', 'discord.com']
        }
        
        # Patterns de détection de technologies
        self.technology_patterns = {
            'cms': {
                'wordpress': [r'/wp-content/', r'/wp-includes/', r'wp-json', r'wordpress'],
                'drupal': [r'/sites/', r'/modules/', r'/themes/', r'drupal'],
                'joomla': [r'/administrator/', r'/components/', r'/templates/', r'joomla'],
                'prestashop': [r'/prestashop/', r'/modules/', r'prestashop'],
                'magento': [r'/magento/', r'/skin/', r'magento'],
                'shopify': [r'shopify', r'cdn.shopify.com'],
                'wix': [r'wix.com', r'wixstatic.com'],
                'squarespace': [r'squarespace.com', r'sqspcdn.com']
            },
            'framework': {
                'react': [r'react', r'__REACT_DEVTOOLS', r'ReactDOM'],
                'vue': [r'vue', r'__VUE__', r'Vue.js'],
                'angular': [r'angular', r'ng-', r'@angular'],
                'jquery': [r'jquery', r'jQuery'],
                'bootstrap': [r'bootstrap', r'bs-'],
                'tailwind': [r'tailwindcss']
            },
            'analytics': {
                'google_analytics': [r'google-analytics.com', r'ga.js', r'gtag'],
                'google_tag_manager': [r'googletagmanager.com', r'GTM-'],
                'facebook_pixel': [r'facebook.net', r'fbq'],
                'hotjar': [r'hotjar.com'],
                'mixpanel': [r'mixpanel.com']
            },
            'cdn': {
                'cloudflare': [r'cloudflare.com', r'cf-ray'],
                'cloudfront': [r'cloudfront.net'],
                'fastly': [r'fastly.com'],
                'akamai': [r'akamai.net']
            }
        }
    
    def is_same_domain(self, url: str) -> bool:
        """Vérifie si l'URL appartient au même domaine"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.domain
        except:
            return False
    
    def normalize_url(self, url: str, base_url: str) -> Optional[str]:
        """Normalise une URL en URL absolue (avec cache)"""
        cache_key = f"{url}|{base_url}"
        if cache_key in self._url_cache:
            return self._url_cache[cache_key]
        
        try:
            if url.startswith(('http://', 'https://')):
                absolute_url = url
            else:
                absolute_url = urljoin(base_url, url)
            
            parsed = urlparse(absolute_url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            
            if '#' in clean_url:
                clean_url = clean_url.split('#')[0]
            
            self._url_cache[cache_key] = clean_url
            return clean_url
        except Exception:
            self._url_cache[cache_key] = None
            return None
    
    def extract_emails(self, text: str) -> Set[str]:
        """Extrait les emails d'un texte (optimisé avec regex compilée)"""
        return set(self.email_pattern.findall(text))
    
    def extract_phones(self, text: str) -> Set[str]:
        """Extrait les numéros de téléphone d'un texte (optimisé avec regex compilées)"""
        phones = set()
        
        for pattern in self.phone_patterns:
            matches = pattern.findall(text)
            for match in matches:
                # Nettoyer le numéro
                cleaned = self.clean_phone_pattern.sub('', match)
                if len(cleaned) >= 10:
                    phones.add(cleaned)
        
        return phones
    
    def extract_people_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        """
        Extrait les personnes d'une page HTML avec validation des noms
        
        Utilise name_validator pour s'assurer que les noms trouvés sont des personnes réelles.
        """
        people = []
        
        # Importer name_validator pour valider les noms
        try:
            from services.name_validator import is_valid_human_name, validate_name_pair
            VALIDATOR_AVAILABLE = True
        except ImportError:
            VALIDATOR_AVAILABLE = False
        
        # Mots-clés à exclure (titres de sections, navigation, etc.)
        excluded_keywords = [
            'habiter', 'mieux', 'sommes', 'nous', 'contact', 'accueil', 'services',
            'produits', 'actualités', 'blog', 'mentions', 'légal', 'politique',
            'confidentialité', 'cookies', 'cgv', 'qui', 'quoi', 'comment', 'pourquoi',
            'bienvenue', 'découvrir', 'en savoir', 'plus', 'lire', 'voir', 'tous',
            'nos', 'votre', 'notre', 'leurs', 'leurs', 'page', 'section', 'article'
        ]
        
        # Patterns améliorés pour trouver les noms (compilés pour de meilleures performances)
        name_patterns = [
            # Titre + Nom complet (M. Jean Dupont, Mme Marie Martin)
            re.compile(r'\b(M\.|Mme|Mr\.|Mrs\.|Dr\.|Prof\.|Monsieur|Madame|Monsieur|Madame)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'),
            # Prénom + Nom (2 mots minimum, commençant par majuscule)
            re.compile(r'\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b'),
            # Format "Nom, Prénom" ou "Prénom Nom"
            re.compile(r'\b([A-Z][a-z]{2,}),\s*([A-Z][a-z]{2,})\b'),
        ]
        
        # Chercher dans les sections spécifiques (équipe, contact, etc.)
        sections = soup.find_all(['section', 'div', 'article'], 
                                class_=re.compile(r'team|staff|member|person|contact|equipe|dirigeant|management', re.I))
        
        # Si pas de sections spécifiques, chercher dans les liens mailto et tel
        if not sections:
            # Chercher les personnes via leurs emails
            email_links = soup.find_all('a', href=re.compile(r'mailto:', re.I))
            for email_link in email_links:
                email = email_link['href'].replace('mailto:', '').strip()
                # Extraire le nom depuis le texte du lien ou le parent
                name_text = email_link.get_text().strip()
                parent = email_link.find_parent(['div', 'section', 'article', 'p'])
                
                if parent:
                    parent_text = parent.get_text()
                    # Chercher un nom dans le texte parent
                    for pattern in name_patterns:
                        matches = pattern.finditer(parent_text)
                        for match in matches:
                            name = match.group(2) if len(match.groups()) > 1 else match.group(1)
                            name = name.strip()
                            
                            # Filtrer les faux positifs avec name_validator
                            name_lower = name.lower()
                            if (len(name.split()) >= 2 and len(name) >= 5 and 
                                not any(kw in name_lower for kw in excluded_keywords) and
                                not name_lower.startswith(('page', 'section', 'article', 'menu', 'nav'))):
                                
                                # Valider avec name_validator si disponible
                                is_valid = True
                                if VALIDATOR_AVAILABLE:
                                    if not is_valid_human_name(name):
                                        is_valid = False
                                    else:
                                        # Valider aussi la paire prénom/nom si possible
                                        name_parts = name.split()
                                        if len(name_parts) >= 2:
                                            first_name = name_parts[0]
                                            last_name = ' '.join(name_parts[1:])
                                            validated = validate_name_pair(first_name, last_name)
                                            if not validated:
                                                is_valid = False
                                
                                if is_valid:
                                    # Chercher le titre/fonction
                                    title = None
                                    title_elem = parent.find(['h3', 'h4', 'p', 'span'], 
                                                             class_=re.compile(r'title|role|position|fonction|job', re.I))
                                    if title_elem:
                                        title = title_elem.get_text().strip()
                                    
                                    # Chercher le LinkedIn
                                    linkedin_url = None
                                    linkedin_elem = parent.find('a', href=re.compile(r'linkedin\.com', re.I))
                                    if linkedin_elem:
                                        linkedin_url = linkedin_elem['href']
                                    
                                    # Chercher le téléphone
                                    phone = None
                                    phone_elem = parent.find('a', href=re.compile(r'tel:', re.I))
                                    if phone_elem:
                                        phone = phone_elem['href'].replace('tel:', '').strip()
                                    
                                    person_id = name.lower()
                                    if not any(p.get('name', '').lower() == person_id for p in people):
                                        person_data = {
                                            'name': name,
                                            'email': email,
                                            'title': title,
                                            'linkedin_url': linkedin_url,
                                            'phone': phone,
                                            'page_url': page_url,
                                            'source': 'website_scraping'
                                        }
                                        people.append(person_data)
                                        break
                elif name_text and '@' not in name_text and len(name_text.split()) >= 2:
                    # Le texte du lien lui-même pourrait être un nom
                    name_lower = name_text.lower()
                    if (len(name_text) >= 5 and 
                        not any(kw in name_lower for kw in excluded_keywords)):
                        # Valider avec name_validator si disponible
                        is_valid = True
                        if VALIDATOR_AVAILABLE:
                            if not is_valid_human_name(name_text):
                                is_valid = False
                            else:
                                # Valider aussi la paire prénom/nom si possible
                                name_parts = name_text.split()
                                if len(name_parts) >= 2:
                                    first_name = name_parts[0]
                                    last_name = ' '.join(name_parts[1:])
                                    validated = validate_name_pair(first_name, last_name)
                                    if not validated:
                                        is_valid = False
                        
                        if is_valid:
                            person_id = name_text.lower()
                            if not any(p.get('name', '').lower() == person_id for p in people):
                                person_data = {
                                    'name': name_text,
                                    'email': email,
                                    'title': None,
                                    'linkedin_url': None,
                                    'phone': None,
                                    'page_url': page_url,
                                    'source': 'website_scraping'
                                }
                                people.append(person_data)
        
        # Chercher aussi dans les sections trouvées
        for section in sections:
            section_text = section.get_text()
            
            # Chercher les noms dans les sections
            for pattern in name_patterns:
                matches = pattern.finditer(section_text)
                for match in matches:
                    name = match.group(2) if len(match.groups()) > 1 else match.group(1)
                    name = name.strip()
                    
                    # Filtrer les faux positifs
                    name_lower = name.lower()
                    if (len(name.split()) >= 2 and len(name) >= 5 and 
                        not any(kw in name_lower for kw in excluded_keywords) and
                        not name_lower.startswith(('page', 'section', 'article', 'menu', 'nav'))):
                        
                        # Chercher l'email associé
                        email = None
                        email_elem = section.find('a', href=re.compile(r'mailto:', re.I))
                        if email_elem:
                            email = email_elem['href'].replace('mailto:', '').strip()
                        
                        # Chercher le titre/fonction
                        title = None
                        title_elem = section.find(['h3', 'h4', 'p', 'span'], 
                                                 class_=re.compile(r'title|role|position|fonction|job', re.I))
                        if title_elem:
                            title = title_elem.get_text().strip()
                        
                        # Chercher le LinkedIn
                        linkedin_url = None
                        linkedin_elem = section.find('a', href=re.compile(r'linkedin\.com', re.I))
                        if linkedin_elem:
                            linkedin_url = linkedin_elem['href']
                        
                        # Chercher le téléphone
                        phone = None
                        phone_elem = section.find('a', href=re.compile(r'tel:', re.I))
                        if phone_elem:
                            phone = phone_elem['href'].replace('tel:', '').strip()
                        
                        # Créer un identifiant unique pour éviter les doublons
                        person_id = name.lower()
                        if not any(p.get('name', '').lower() == person_id for p in people):
                            # Valider le nom avec name_validator si disponible
                            is_valid = True
                            first_name = None
                            last_name = None
                            
                            if VALIDATOR_AVAILABLE:
                                # Essayer de séparer prénom et nom
                                name_parts = name.split()
                                if len(name_parts) >= 2:
                                    first_name = name_parts[0]
                                    last_name = ' '.join(name_parts[1:])
                                    validated = validate_name_pair(first_name, last_name)
                                    if validated:
                                        first_name, last_name = validated
                                        name = f'{first_name} {last_name}'
                                    else:
                                        # Si la paire n'est pas valide, vérifier le nom complet
                                        if not is_valid_human_name(name):
                                            is_valid = False
                                else:
                                    # Nom complet seul
                                    if not is_valid_human_name(name):
                                        is_valid = False
                            
                            if is_valid:
                                person_data = {
                                    'name': name,
                                    'first_name': first_name,
                                    'last_name': last_name,
                                    'email': email,
                                    'title': title,
                                    'linkedin_url': linkedin_url,
                                    'phone': phone,
                                    'page_url': page_url,
                                    'source': 'website_scraping'
                                }
                                people.append(person_data)
        
        # Chercher aussi dans tout le texte de la page (recherche approfondie)
        if not people or len(people) < 5:  # Si peu de personnes trouvées, chercher plus largement
            page_text = soup.get_text()
            # Nettoyer le texte (supprimer les espaces multiples, sauts de ligne)
            page_text = re.sub(r'\s+', ' ', page_text)
            
            # Chercher les patterns de noms dans tout le texte
            for pattern in name_patterns:
                matches = pattern.finditer(page_text)
                for match in matches:
                    # Extraire le nom (groupe 2 si titre présent, sinon groupe 1)
                    if len(match.groups()) >= 2 and match.group(2):
                        name = match.group(2).strip()
                    else:
                        name = match.group(1).strip() if match.group(1) else None
                    
                    if not name:
                        continue
                    
                    # Valider le nom
                    name_lower = name.lower()
                    if (len(name.split()) >= 2 and len(name) >= 5 and 
                        not any(kw in name_lower for kw in excluded_keywords) and
                        not name_lower.startswith(('page', 'section', 'article', 'menu', 'nav'))):
                        
                        # Valider avec name_validator
                        is_valid = True
                        first_name = None
                        last_name = None
                        
                        if VALIDATOR_AVAILABLE:
                            name_parts = name.split()
                            if len(name_parts) >= 2:
                                first_name = name_parts[0]
                                last_name = ' '.join(name_parts[1:])
                                validated = validate_name_pair(first_name, last_name)
                                if validated:
                                    first_name, last_name = validated
                                    name = f'{first_name} {last_name}'
                                else:
                                    if not is_valid_human_name(name):
                                        is_valid = False
                            else:
                                if not is_valid_human_name(name):
                                    is_valid = False
                        
                        if is_valid:
                            # Chercher l'email associé dans le contexte (50 caractères avant/après)
                            match_start = match.start()
                            context_start = max(0, match_start - 50)
                            context_end = min(len(page_text), match_start + len(name) + 50)
                            context = page_text[context_start:context_end]
                            
                            # Chercher un email dans le contexte
                            email = None
                            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', context)
                            if email_match:
                                email = email_match.group(0)
                            
                            # Chercher le titre dans le contexte
                            title = None
                            title_match = re.search(r'(directeur|manager|responsable|chef|coordinateur|coordonnatrice)', context, re.I)
                            if title_match:
                                title = title_match.group(0)
                            
                            person_id = name.lower()
                            if not any(p.get('name', '').lower() == person_id for p in people):
                                person_data = {
                                    'name': name,
                                    'first_name': first_name,
                                    'last_name': last_name,
                                    'email': email,
                                    'title': title,
                                    'linkedin_url': None,
                                    'phone': None,
                                    'page_url': page_url,
                                    'source': 'website_text_scraping'
                                }
                                people.append(person_data)
                                
                                # Limiter à 10 personnes par page pour éviter trop de faux positifs
                                if len(people) >= 10:
                                    break
                
                if len(people) >= 10:
                    break
        
        return people
    
    def detect_social_platform(self, url: str) -> Optional[str]:
        """Détecte le réseau social depuis une URL"""
        url_lower = url.lower()
        for platform, domains in self.social_platforms.items():
            for domain in domains:
                if domain in url_lower:
                    return platform
        return None
    
    def extract_images_from_page(self, soup: BeautifulSoup, page_url: str) -> List[Dict]:
        """
        Extrait toutes les images depuis les balises <img> du HTML
        
        Args:
            soup: BeautifulSoup de la page
            page_url: URL de la page où les images sont trouvées
            
        Returns:
            Liste d'objets {url, alt, page_url, width, height}
        """
        images = []
        
        try:
            # Base URL pour normaliser les URLs relatives
            parsed_base = urlparse(page_url)
            base_root = f"{parsed_base.scheme}://{parsed_base.netloc}" if parsed_base.scheme and parsed_base.netloc else page_url
            
            # Parcourir toutes les balises <img>
            for img in soup.find_all('img'):
                # Récupérer src ou data-src (lazy loading)
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if not src:
                    continue
                
                # Ignorer les images data: ou vides
                if src.startswith('data:') or not src.strip():
                    continue
                
                # Normaliser l'URL (relative -> absolue)
                try:
                    normalized_url = self.normalize_url(src, base_root) or src
                except Exception:
                    normalized_url = src
                
                # Récupérer les attributs
                alt = img.get('alt', '').strip()
                width = img.get('width')
                height = img.get('height')
                
                # Convertir width/height en int si possible
                try:
                    width_val = int(width) if width else None
                except (ValueError, TypeError):
                    width_val = None
                
                try:
                    height_val = int(height) if height else None
                except (ValueError, TypeError):
                    height_val = None
                
                # Ajouter l'image à la liste
                images.append({
                    'url': normalized_url,
                    'alt': alt,
                    'page_url': page_url,
                    'width': width_val,
                    'height': height_val
                })
        except Exception:
            pass
        
        return images
    
    def detect_technologies(self, html: str, headers: Dict) -> None:
        """Détecte les technologies depuis le HTML et les headers"""
        html_lower = html.lower()
        
        # Détecter depuis le HTML
        for category, techs in self.technology_patterns.items():
            for tech_name, patterns in techs.items():
                for pattern in patterns:
                    if re.search(pattern, html_lower, re.IGNORECASE):
                        if category not in self.technologies:
                            self.technologies[category] = []
                        if tech_name not in self.technologies[category]:
                            self.technologies[category].append(tech_name)
                        break
        
        # Détecter depuis les headers
        server = headers.get('Server', '').lower()
        powered_by = headers.get('X-Powered-By', '').lower()
        
        if 'nginx' in server:
            self.technologies.setdefault('server', []).append('nginx')
        elif 'apache' in server:
            self.technologies.setdefault('server', []).append('apache')
        elif 'iis' in server:
            self.technologies.setdefault('server', []).append('iis')
        
        if 'php' in powered_by:
            self.technologies.setdefault('language', []).append('php')
        elif 'asp.net' in powered_by or 'aspnet' in powered_by:
            self.technologies.setdefault('language', []).append('asp.net')
        elif 'express' in powered_by:
            self.technologies.setdefault('framework', []).append('express')
    
    def extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """
        Extrait les métadonnées d'une page, y compris OpenGraph et les icônes (favicon, logo, image principale).
        """
        metadata = {}
        
        # Meta tags standards
        meta_tags = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property') or meta.get('itemprop')
            content = meta.get('content')
            if name and content:
                meta_tags[name] = content
        
        # Title
        title = soup.find('title')
        if title:
            meta_tags['title'] = title.get_text().strip()
        
        # Description
        description = soup.find('meta', attrs={'name': 'description'})
        if description:
            meta_tags['description'] = description.get('content', '')
        
        # Open Graph
        og_tags = {}
        for meta in soup.find_all('meta', attrs={'property': lambda x: x and x.startswith('og:')}):
            property_name = meta.get('property', '').replace('og:', '')
            content = meta.get('content', '')
            if property_name and content:
                og_tags[property_name] = content
        
        # Twitter Cards
        twitter_tags = {}
        for meta in soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')}):
            name = meta.get('name', '').replace('twitter:', '')
            content = meta.get('content', '')
            if name and content:
                twitter_tags[name] = content
        
        # Schema.org / JSON-LD
        json_ld = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                json_ld.append(data)
            except:
                pass
        
        # Langue
        lang = soup.find('html', attrs={'lang': True})
        language = lang.get('lang') if lang else None
        
        # Keywords
        keywords = soup.find('meta', attrs={'name': 'keywords'})
        keywords_content = keywords.get('content', '') if keywords else ''
        
        # Détection des icônes et images principales
        icons: Dict[str, Optional[str]] = {
            'favicon': None,
            'apple_touch_icon': None,
            'og_image': None,
            'twitter_image': None,
            'logo': None,
            'main_image': None
        }
        
        # Base du site pour construire les URLs absolues
        try:
            parsed_base = urlparse(self.base_url)
            base_root = f"{parsed_base.scheme}://{parsed_base.netloc}" if parsed_base.scheme and parsed_base.netloc else self.base_url
        except Exception:
            base_root = self.base_url
        
        # 1) Favicon via <link rel="icon"> ou équivalents
        favicon_link = None
        try:
            for link in soup.find_all('link', href=True):
                rel = ' '.join(link.get('rel', [])).lower() if link.get('rel') else ''
                if 'icon' in rel and 'apple-touch-icon' not in rel:
                    favicon_link = link
                    break
        except Exception:
            favicon_link = None
        
        if favicon_link:
            href = favicon_link.get('href')
            if href:
                try:
                    icons['favicon'] = self.normalize_url(href, base_root) or href
                except Exception:
                    icons['favicon'] = href
        else:
            # Favicon par défaut /favicon.ico
            try:
                icons['favicon'] = f"{base_root.rstrip('/')}/favicon.ico"
            except Exception:
                pass
        
        # 2) Apple touch icon
        try:
            apple_link = soup.find('link', rel=lambda x: x and 'apple-touch-icon' in ' '.join(x).lower())
        except Exception:
            apple_link = None
        if apple_link:
            href = apple_link.get('href')
            if href:
                try:
                    icons['apple_touch_icon'] = self.normalize_url(href, base_root) or href
                except Exception:
                    icons['apple_touch_icon'] = href
        
        # 3) Image OpenGraph (prioritaire)
        og_image = og_tags.get('image') or og_tags.get('image:url') or og_tags.get('image_secure_url')
        if og_image:
            try:
                icons['og_image'] = self.normalize_url(og_image, base_root) or og_image
            except Exception:
                icons['og_image'] = og_image
        
        # 4) Image Twitter Card (fallback)
        twitter_image = twitter_tags.get('image') or twitter_tags.get('image:src')
        if twitter_image:
            try:
                icons['twitter_image'] = self.normalize_url(twitter_image, base_root) or twitter_image
            except Exception:
                icons['twitter_image'] = twitter_image
        
        # 5) Logo depuis les balises <img> avec classe/id/alt "logo" + header/navbar
        logo_url = None
        try:
            # Sélecteurs classiques de logo
            logo_selectors = [
                {'class': re.compile(r'logo', re.I)},
                {'id': re.compile(r'logo', re.I)},
                {'alt': re.compile(r'logo', re.I)},
            ]
            for selector in logo_selectors:
                for img in soup.find_all('img', selector):
                    src = img.get('src') or img.get('data-src')
                    if src:
                        logo_url = self.normalize_url(src, base_root) or src
                        break
                if logo_url:
                    break
            
            # Si pas trouvé, chercher dans le header/nav
            if not logo_url:
                header = soup.find('header') or soup.find('nav')
                if header:
                    for img in header.find_all('img'):
                        src = img.get('src') or img.get('data-src')
                        if src:
                            logo_url = self.normalize_url(src, base_root) or src
                            break
        except Exception:
            logo_url = None
        
        if logo_url:
            icons['logo'] = logo_url
        
        # 6) Collecte des images trouvées sur la page (pour l'onglet Images)
        images: List[Dict[str, Optional[str]]] = []
        large_image = None
        try:
            for img in soup.find_all('img'):
                # Récupérer src ou data-src (lazy loading) - comme dans extract_images_from_page
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if not src:
                    continue
                
                # Ignorer les images data: ou vides (comme dans extract_images_from_page)
                if src.startswith('data:') or not src.strip():
                    continue
                
                # Normaliser l'URL de l'image
                try:
                    img_url = self.normalize_url(src, base_root) or src
                except Exception:
                    img_url = src
                
                alt = img.get('alt') or ''
                
                # Récupérer les dimensions si disponibles
                width_attr = img.get('width')
                height_attr = img.get('height')
                try:
                    width_val = int(width_attr) if width_attr else None
                    height_val = int(height_attr) if height_attr else None
                except ValueError:
                    width_val = None
                    height_val = None
                
                images.append({
                    'url': img_url,
                    'alt': alt,
                    'width': width_val,
                    'height': height_val
                })
                
                # Garder une "grande" image comme fallback d'image principale
                if not large_image and ((width_val and width_val >= 200) or (height_val and height_val >= 200)):
                    large_image = img_url
        except Exception:
            pass
        
        # Construire l'image principale en respectant les priorités
        main_image_candidates = [
            icons.get('og_image'),
            icons.get('twitter_image'),
            icons.get('apple_touch_icon'),
            icons.get('logo'),
            large_image,
            icons.get('favicon'),
        ]
        for candidate in main_image_candidates:
            if candidate:
                icons['main_image'] = candidate
                break
        
        metadata = {
            'meta_tags': meta_tags,
            'open_graph': og_tags,
            'twitter_cards': twitter_tags,
            'json_ld': json_ld,
            'language': language,
            'keywords': keywords_content.split(',') if keywords_content else [],
            'icons': icons,
            # Liste des images trouvées (optimisation BDD: uniquement les URLs + quelques infos, pas les binaires)
            'images': images
        }
        
        return metadata
    
    def generate_company_summary(self) -> str:
        """
        Génère un résumé de l'entreprise à partir des métadonnées et données scrapées
        
        Returns:
            str: Résumé de l'entreprise (max 500 caractères)
        """
        resume_parts = []
        
        # Récupérer les métadonnées
        meta_tags = self.metadata.get('meta_tags', {}) if self.metadata else {}
        og_tags = self.metadata.get('open_graph', {}) if self.metadata else {}
        
        # 1. Titre de l'entreprise (depuis title ou og:title)
        title = og_tags.get('title') or meta_tags.get('title') or ''
        if title:
            # Nettoyer le titre (enlever les suffixes comme " - Accueil", " | Home", etc.)
            title = re.sub(r'\s*[-–—|]\s*(Accueil|Home|Accueil|.*)$', '', title, flags=re.IGNORECASE).strip()
            if title:
                resume_parts.append(f"{title}")
        
        # 2. Description (depuis meta description ou og:description)
        description = og_tags.get('description') or meta_tags.get('description') or ''
        if description:
            # Limiter à 200 caractères pour la description
            if len(description) > 200:
                description = description[:197] + '...'
            resume_parts.append(description)
        
        # 3. Informations supplémentaires depuis les technologies détectées
        tech_info = []
        if self.technologies:
            if self.technologies.get('cms'):
                cms_list = self.technologies.get('cms', [])
                if cms_list:
                    tech_info.append(f"utilise {cms_list[0]}")
            
            if self.technologies.get('framework'):
                framework_list = self.technologies.get('framework', [])
                if framework_list:
                    tech_info.append(f"basé sur {framework_list[0]}")
        
        # 4. Informations sur les personnes trouvées
        if self.people:
            people_count = len(self.people)
            if people_count > 0:
                # Essayer d'extraire des rôles clés
                key_roles = ['directeur', 'ceo', 'fondateur', 'manager', 'responsable']
                found_roles = []
                for person in self.people[:5]:
                    title = person.get('title', '').lower() if person.get('title') else ''
                    for role in key_roles:
                        if role in title and role not in found_roles:
                            found_roles.append(role)
                            break
                
                if found_roles:
                    tech_info.append(f"équipe avec {', '.join(found_roles[:2])}")
        
        # Construire le résumé final
        if resume_parts:
            resume = '. '.join(resume_parts)
            
            # Ajouter les infos techniques si on a de la place
            if tech_info and len(resume) < 400:
                tech_text = ', '.join(tech_info[:2])
                resume += f". {tech_text.capitalize()}."
            
            # Limiter à 500 caractères au total
            if len(resume) > 500:
                resume = resume[:497] + '...'
            
            return resume.strip()
        
        # Si on n'a rien trouvé, créer un résumé minimal
        if self.domain:
            return f"Entreprise présente sur le web avec le domaine {self.domain}."
        
        return ""
    
    def scrape_page(self, url: str, depth: int = 0) -> None:
        """Scrape une page et extrait toutes les données"""
        if depth > self.max_depth:
            logger.info(f'[UnifiedScraper] Page {url}: Profondeur {depth} > max_depth {self.max_depth}, ignorée')
            return
        if url in self.visited_urls:
            logger.info(f'[UnifiedScraper] Page {url}: Déjà visitée, ignorée')
            return
        if self.should_stop:
            logger.info(f'[UnifiedScraper] Page {url}: Scraping arrêté, ignorée')
            return

        # Valider l'URL
        if not url or not isinstance(url, str):
            logger.error(f'[UnifiedScraper] URL invalide: {url} (type: {type(url)})')
            return

        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.error(f'[UnifiedScraper] URL invalide (pas de scheme ou netloc): {url}')
                return
        except Exception as e:
            logger.error(f'[UnifiedScraper] Erreur lors de la validation de l\'URL {url}: {e}')
            return

        # Vérifier la limite du nombre de pages avant de commencer
        with self.lock:
            if len(self.visited_urls) >= self.max_pages:
                self.should_stop = True
                logger.info(f'[UnifiedScraper] Page {url}: Limite de {self.max_pages} pages atteinte')
                return
            self.visited_urls.add(url)
            self.urls_in_progress += 1
        
        logger.info(f'[UnifiedScraper] Scraping de la page {url} (profondeur {depth})')
        
        try:
            # Délai entre les requêtes pour éviter de surcharger les serveurs et permettre le chargement complet
            # Utiliser un délai par domaine pour éviter de surcharger un même serveur
            domain = urlparse(url).netloc
            current_time = time.time()
            
            with self.lock:
                if domain in self.last_request_time:
                    time_since_last = current_time - self.last_request_time[domain]
                    if time_since_last < self.request_delay:
                        sleep_time = self.request_delay - time_since_last
                        time.sleep(sleep_time)
                
                self.last_request_time[domain] = time.time()
            
            response = requests.get(url, headers=self.headers, timeout=15)  # Timeout augmenté à 15s
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = response.text
            
            # 1. Extraire les emails
            page_emails = self.extract_emails(text)
            with self.lock:
                old_emails = set(self.emails.keys())
                # Stocker chaque email avec sa page_url
                for email in page_emails:
                    if email not in self.emails:
                        self.emails[email] = url
                new_emails = set(self.emails.keys()) - old_emails
                
                if new_emails and self.on_email_found:
                    for email in sorted(new_emails):
                        try:
                            self.on_email_found(email, url)
                        except Exception:
                            pass
            
            # 2. Extraire les téléphones
            page_phones = self.extract_phones(text)
            # Chercher aussi dans les liens tel: (optimisé)
            tel_links = soup.find_all('a', href=re.compile(r'^tel:', re.I))
            for link in tel_links:
                href = link['href']
                phone = href.replace('tel:', '').strip()
                cleaned = self.clean_phone_pattern.sub('', phone)
                if len(cleaned) >= 10:
                    page_phones.add(cleaned)
            
            with self.lock:
                old_phones = self.phones.copy()
                self.phones.update(page_phones)
                new_phones = self.phones - old_phones
                
                if new_phones and self.on_phone_found:
                    for phone in sorted(new_phones):
                        try:
                            self.on_phone_found(phone, url)
                        except Exception:
                            pass
            
            # 3. Extraire les personnes
            # Recherche approfondie sur les pages de niveau 0-1 ou pages spécifiques (équipe, contact, etc.)
            # Recherche basique sur toutes les pages pour trouver des personnes dans les textes
            search_people = False
            search_mode = 'basic'  # 'basic' ou 'deep'
            
            if depth <= 1 or any(keyword in url.lower() for keyword in ['about', 'contact', 'team', 'equipe', 'nous', 'staff', 'dirigeant', 'management']):
                search_people = True
                search_mode = 'deep'  # Recherche approfondie sur ces pages
            elif depth <= 2:  # Recherche basique jusqu'à la profondeur 2
                search_people = True
                search_mode = 'basic'
            
            if search_people:
                page_people = self.extract_people_from_page(soup, url)
                logger.info(f'[UnifiedScraper] Page {url}: {len(page_people)} personnes extraites')
                with self.lock:
                    new_people = []
                    for person in page_people:
                        person_id = person.get('name', '').lower()
                        if person_id and person_id not in self.people_by_name:
                            self.people.append(person)
                            self.people_by_name[person_id] = person
                            new_people.append(person)
                            
                            if self.on_person_found:
                                try:
                                    self.on_person_found(person, url)
                                except Exception as e:
                                    pass
                    if new_people:
                        logger.info(f'[UnifiedScraper] Page {url}: {len(new_people)} nouvelles personnes ajoutées (total: {len(self.people)})')
            
            # 4. Extraire les formulaires / points d'entrée (pour un usage futur pentest)
            page_forms = []
            try:
                forms = soup.find_all('form')
                seen_forms = set()  # Pour dédupliquer les formulaires
                for form in forms:
                    action = form.get('action', '')
                    method = form.get('method', 'get').upper()
                    enctype = form.get('enctype', 'application/x-www-form-urlencoded')
                    
                    # Construire l'URL complète de l'action
                    if action:
                        if not action.startswith(('http://', 'https://')):
                            action_url = urljoin(url, action)
                        else:
                            action_url = action
                    else:
                        action_url = url
                    
                    # Créer une clé unique pour dédupliquer (action + method)
                    form_key = f"{action_url}|{method}"
                    if form_key in seen_forms:
                        continue  # Ignorer les doublons
                    seen_forms.add(form_key)
                    
                    inputs = form.find_all(['input', 'textarea', 'select', 'button'])
                    fields = []
                    has_password = False
                    has_file_upload = False
                    has_csrf = False
                    
                    for field in inputs:
                        f_type = field.get('type', field.name or '').lower()
                        name = field.get('name', '')
                        field_info = {
                            'name': name,
                            'type': f_type,
                            'required': field.has_attr('required'),
                            'placeholder': field.get('placeholder', ''),
                            'id': field.get('id', ''),
                            'class': ' '.join(field.get('class', []))
                        }
                        if f_type == 'password':
                            has_password = True
                        if f_type == 'file':
                            has_file_upload = True
                        
                        # Détecter les tokens CSRF (patterns courants)
                        name_lower = name.lower()
                        if any(token in name_lower for token in ['csrf', 'token', '_token', 'authenticity', 'nonce']):
                            has_csrf = True
                            field_info['is_csrf'] = True
                        
                        # Extraire les options pour les select
                        if field.name == 'select':
                            options = []
                            for option in field.find_all('option'):
                                options.append({
                                    'value': option.get('value', ''),
                                    'text': option.get_text(strip=True)
                                })
                            field_info['options'] = options
                        
                        fields.append(field_info)
                    
                    # Détecter les protections CSRF dans les meta tags
                    csrf_meta = soup.find('meta', {'name': re.compile(r'csrf', re.I)})
                    if csrf_meta:
                        has_csrf = True
                    
                    form_data = {
                        'page_url': url,
                        'action': action,
                        'action_url': action_url,
                        'method': method,
                        'enctype': enctype,
                        'fields': fields,
                        'has_password': has_password,
                        'has_file_upload': has_file_upload,
                        'has_csrf': has_csrf
                    }
                    page_forms.append(form_data)
            except Exception:
                pass
            if page_forms:
                with self.lock:
                    self.forms.extend(page_forms)
            
            # 5. Extraire les réseaux sociaux
            new_social_links = []
            all_links = soup.find_all('a', href=True)
            logger.info(f'[UnifiedScraper] Page {url}: {len(all_links)} liens trouvés pour détection réseaux sociaux')
            for link in all_links:
                href = link['href']
                full_url = self.normalize_url(href, url)
                
                if full_url:
                    platform = self.detect_social_platform(full_url)
                    if platform:
                        with self.lock:
                            if platform not in self.social_links:
                                self.social_links[platform] = []
                            
                            existing_urls = [item.get('url') for item in self.social_links[platform]]
                            if full_url not in existing_urls:
                                link_data = {
                                    'url': full_url,
                                    'text': link.get_text().strip(),
                                    'page_url': url
                                }
                                self.social_links[platform].append(link_data)
                                new_social_links.append((platform, link_data))
                                
                                if self.on_social_found:
                                    try:
                                        self.on_social_found(platform, full_url, url)
                                    except Exception:
                                        pass
            if new_social_links:
                logger.info(f'[UnifiedScraper] Page {url}: {len(new_social_links)} nouveaux réseaux sociaux trouvés: {[p for p, _ in new_social_links]}')
            
            # 6. Détecter les technologies (seulement sur la page d'accueil)
            if depth == 0:
                logger.info(f'[UnifiedScraper] Page {url}: Détection des technologies')
                self.detect_technologies(text, response.headers)
                logger.info(f'[UnifiedScraper] Page {url}: Technologies détectées: {self.technologies}')
            
            # 7. Extraire les métadonnées de toutes les pages
            page_metadata = self.extract_metadata(soup)
            
            with self.lock:
                # Garder les métadonnées de la page d'accueil pour compatibilité
                if depth == 0:
                    self.metadata = page_metadata
                    icons = page_metadata.get('icons', {})
                    logger.info(f'[UnifiedScraper] Page {url} (accueil): Métadonnées extraites - favicon={bool(icons.get("favicon"))}, logo={bool(icons.get("logo"))}, og_tags={len(page_metadata.get("open_graph", {}))}')
                
                # Collecter les OG de toutes les pages (même si vides pour la page d'accueil)
                og_tags = page_metadata.get('open_graph', {})
                # Toujours stocker les OG, même si vides (pour la page d'accueil au minimum)
                # Cela permet de récupérer au moins les métadonnées de base
                self.og_data_by_page[url] = og_tags
                if og_tags:
                    logger.info(f'[UnifiedScraper] Page {url}: {len(og_tags)} tags OG collectés')
                elif depth == 0:
                    logger.info(f'[UnifiedScraper] Page {url} (accueil): Aucun tag OG trouvé, mais métadonnées de base stockées')
            
            # 8. Extraire les images depuis les balises <img> du HTML
            page_images = self.extract_images_from_page(soup, url)
            logger.info(f'[UnifiedScraper] Page {url}: {len(page_images)} images extraites depuis extract_images_from_page')
            
            # 9. Fusionner aussi les images de extract_metadata (pour s'assurer de ne rien manquer)
            metadata_images = page_metadata.get('images', [])
            logger.info(f'[UnifiedScraper] Page {url}: {len(metadata_images)} images dans metadata')
            if metadata_images:
                # Convertir le format des images de metadata vers le format standard
                for img_meta in metadata_images:
                    if isinstance(img_meta, dict) and img_meta.get('url'):
                        # Vérifier si l'image n'est pas déjà dans page_images
                        if not any(img.get('url') == img_meta.get('url') for img in page_images):
                            # Ajouter page_url si manquant
                            img_data = {
                                'url': img_meta.get('url'),
                                'alt': img_meta.get('alt', ''),
                                'page_url': url,
                                'width': img_meta.get('width'),
                                'height': img_meta.get('height')
                            }
                            page_images.append(img_data)
            
            with self.lock:
                # Éviter les doublons en vérifiant l'URL
                existing_image_urls = {img.get('url') for img in self.images}
                new_images_count = 0
                for img_data in page_images:
                    if img_data.get('url') and img_data['url'] not in existing_image_urls:
                        self.images.append(img_data)
                        existing_image_urls.add(img_data['url'])
                        new_images_count += 1
                    if new_images_count > 0:
                        logger.info(f'[UnifiedScraper] Page {url}: {new_images_count} nouvelles images ajoutées (total: {len(self.images)})')
            
            # Extraire les liens vers d'autres pages
            links = []
            all_page_links = soup.find_all('a', href=True)
            for link in all_page_links:
                href = link['href']
                
                if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                    continue
                
                normalized_url = self.normalize_url(href, url)
                if normalized_url and self.is_same_domain(normalized_url):
                    links.append(normalized_url)
            
            with self.lock:
                valid_links = []
                # Limiter le nombre de pages à scraper
                pages_remaining = max(0, self.max_pages - len(self.visited_urls))
                
                for link in links:
                    if link not in self.links and link not in self.visited_urls:
                        if len(valid_links) < pages_remaining:
                            valid_links.append(link)
                        else:
                            # On a atteint la limite, arrêter d'ajouter des liens
                            break
                
                self.links.update(valid_links)
                
                for new_link in valid_links:
                    if not self.should_stop and len(self.visited_urls) < self.max_pages:
                        self.url_queue.put((new_link, depth + 1))
                    else:
                        # Limite atteinte, arrêter
                        break
            
            # Mise à jour de progression (seulement toutes les 5 pages pour éviter le spam)
            visited = len(self.visited_urls)
            if visited % 5 == 0 or visited == 1:  # Afficher à la première page et toutes les 5 pages
                if self.progress_callback:
                    try:
                        with self.lock:
                            total_emails = len(self.emails)
                            total_people = len(self.people)
                            total_phones = len(self.phones)
                            # Compter le nombre total de liens sociaux (pas juste le nombre de plateformes)
                            total_social = sum(len(v) if isinstance(v, list) else 1 for v in self.social_links.values()) if self.social_links else 0
                        
                        self.progress_callback(
                            f'{visited} page(s) - {total_emails} emails, {total_people} personnes, '
                            f'{total_phones} téléphones, {total_social} réseaux sociaux'
                        )
                    except Exception:
                        pass
        
        except Exception as e:
            logger.error(f'[UnifiedScraper] Erreur lors du scraping de {url}: {e}', exc_info=True)
        finally:
            with self.lock:
                self.urls_in_progress -= 1
    
    def worker(self) -> None:
        """Worker thread pour traiter les URLs"""
        worker_name = threading.current_thread().name
        
        while not self.should_stop:
            try:
                url, depth = self.url_queue.get(timeout=2)
                if self.should_stop:
                    break
                
                self.scrape_page(url, depth)
                self.url_queue.task_done()
                
            except queue.Empty:
                time.sleep(0.5)
                if self.should_stop:
                    break
                continue
            except Exception as e:
                logger.error(f'[UnifiedScraper] Erreur dans worker {worker_name}: {e}', exc_info=True)
                self.url_queue.task_done()
    
    def scrape(self) -> Dict:
        """
        Lance le scraping avec multithreading
        
        Returns:
            Dictionnaire contenant tous les résultats
        """
        self.start_time = time.time()
        if self.progress_callback:
            self.progress_callback('Initialisation du scraping...')
        
        self.url_queue.put((self.base_url, 0))
        
        threads = []
        for i in range(self.max_workers):
            thread = threading.Thread(target=self.worker, name=f'Worker-{i}')
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        time.sleep(1)
        
        try:
            iteration = 0
            consecutive_empty_checks = 0
            while not self.should_stop:
                iteration += 1
                elapsed = time.time() - self.start_time
                
                if elapsed >= self.max_time:
                    self.should_stop = True
                    break
                
                active_threads = sum(1 for t in threads if t.is_alive())
                queue_size = self.url_queue.qsize()
                
                # Vérifier si tout est terminé
                if (self.url_queue.empty() and 
                    self.urls_in_progress == 0):
                    consecutive_empty_checks += 1
                    if consecutive_empty_checks >= 2:  # 2 vérifications consécutives (1 seconde)
                        self.should_stop = True
                        break
                else:
                    consecutive_empty_checks = 0
                
                time.sleep(0.5)
        
        except KeyboardInterrupt:
            self.should_stop = True
        except Exception as e:
            logger.error(f'[UnifiedScraper] Erreur dans scrape(): {e}', exc_info=True)
        
        for thread in threads:
            thread.join(timeout=2)
        
        end_time = time.time()
        duration = end_time - self.start_time
        
        # Convertir les sets en listes pour le retour
        phones_list = [{'phone': phone, 'page_url': None} for phone in self.phones]
        
        if self.progress_callback:
            total_social = sum(len(v) if isinstance(v, list) else 1 for v in self.social_links.values()) if self.social_links else 0
            self.progress_callback(
                f'Scraping terminé: {len(self.emails)} emails, {len(self.people)} personnes, '
                f'{len(phones_list)} téléphones, {total_social} réseaux sociaux'
            )
        
        # Générer le résumé de l'entreprise
        resume = self.generate_company_summary()
        
        # Log final du nombre de pages avec OG collectées
        logger.info(f'[UnifiedScraper] Scraping terminé pour {self.base_url}: {len(self.og_data_by_page)} page(s) avec OG collectées sur {len(self.visited_urls)} page(s) visitées')
        
        # Log détaillé des résultats
        logger.info(f'[UnifiedScraper] Résultats finaux: {len(self.emails)} emails, {len(self.people)} personnes, {len(phones_list)} téléphones, '
                   f'{sum(len(v) if isinstance(v, list) else 1 for v in self.social_links.values()) if self.social_links else 0} réseaux sociaux, '
                   f'{sum(len(v) if isinstance(v, list) else 1 for v in self.technologies.values()) if self.technologies else 0} technologies, '
                   f'{len(self.images)} images, {len(self.forms)} formulaires')
        
        # Formater les emails avec leur page_url
        emails_list = []
        for email, page_url in self.emails.items():
            emails_list.append({
                'email': email,
                'page_url': page_url
            })
        
        return {
            'emails': emails_list,
            'people': self.people,
            'phones': phones_list,
            'social_links': self.social_links,
            'technologies': self.technologies,
            'metadata': self.metadata,
            'og_data_by_page': self.og_data_by_page,  # OG de toutes les pages scrapées
            'images': self.images,  # Images extraites depuis les balises <img>
            'forms': self.forms,    # Formulaires / points d'entrée collectés
            'visited_urls': list(self.visited_urls),
            'duration': duration,
            'total_emails': len(self.emails),
            'total_people': len(self.people),
            'total_phones': len(phones_list),
            # Compter le nombre total de liens sociaux (pas juste le nombre de plateformes)
            'total_social_platforms': sum(len(v) if isinstance(v, list) else 1 for v in self.social_links.values()) if self.social_links else 0,
            'total_technologies': sum(len(v) if isinstance(v, list) else 1 for v in self.technologies.values()) if self.technologies else 0,
            'total_images': len(self.images),
            'total_forms': len(self.forms),  # Nombre de formulaires trouvés
            'total_og_pages': len(self.og_data_by_page),  # Nombre de pages avec OG
            'people_with_email': len([p for p in self.people if p.get('email')]),
            'people_with_linkedin': len([p for p in self.people if p.get('linkedin_url')]),
            'people_with_title': len([p for p in self.people if p.get('title')]),
            'resume': resume
        }

