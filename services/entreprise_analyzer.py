"""
Service d'analyse d'entreprises
Adaptation du script analyze_entreprises_metz.py pour Flask
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys
from pathlib import Path

# Importer l'analyseur technique
sys.path.insert(0, str(Path(__file__).parent))
try:
    from technical_analyzer import TechnicalAnalyzer
except ImportError:
    TechnicalAnalyzer = None

# Importer l'analyseur OSINT
try:
    from osint_analyzer import OSINTAnalyzer
except ImportError:
    OSINTAnalyzer = None


class EntrepriseAnalyzer:
    def __init__(self, excel_file, output_file=None, max_workers=3, delay=2):
        """
        Initialise l'analyseur
        
        Args:
            excel_file: Chemin vers le fichier Excel
            output_file: Fichier de sortie (défaut: ajoute _analyzed au nom)
            max_workers: Nombre de threads parallèles
            delay: Délai entre les requêtes (secondes)
        """
        self.excel_file = excel_file
        self.output_file = output_file or excel_file.replace('.xlsx', '_analyzed.xlsx')
        self.max_workers = max_workers
        self.delay = delay
        self.lock = threading.Lock()
        
        # Headers pour éviter les blocages
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # Technologies obsolètes à détecter
        self.old_technologies = [
            'jquery-1.', 'jquery-2.', 'jquery-3.0', 'jquery-3.1',
            'bootstrap-3', 'bootstrap-2',
            'php-5', 'php-7.0', 'php-7.1',
            'wordpress-3.', 'wordpress-4.0', 'wordpress-4.1',
            'angularjs', 'angular-1.',
            'flash', 'shockwave'
        ]
        
        # Patterns pour détecter l'âge du site
        self.age_patterns = [
            r'copyright.*20(0[0-9]|1[0-5])',
            r'©.*20(0[0-9]|1[0-5])',
            r'créé.*en.*20(0[0-9]|1[0-5])',
            r'fondé.*en.*20(0[0-9]|1[0-5])'
        ]
        
        # Initialiser l'analyseur technique (désactivé par défaut pour l'import Excel)
        # L'analyse technique peut être lancée manuellement depuis l'interface
        self.technical_analyzer = None
        
        # Initialiser l'analyseur OSINT (optionnel)
        try:
            self.osint_analyzer = OSINTAnalyzer() if OSINTAnalyzer else None
        except:
            self.osint_analyzer = None
    
    def load_excel(self):
        """
        Charge le fichier Excel avec gestion des erreurs et nettoyage des données
        
        Returns:
            DataFrame nettoyé avec les données valides
        """
        try:
            # Charger le fichier Excel avec gestion des erreurs
            df = pd.read_excel(
                self.excel_file,
                engine='openpyxl',  # Utiliser openpyxl pour meilleure compatibilité
                na_values=['', ' ', 'NULL', 'null', 'None', 'N/A', 'n/a', '#NOM?', '#REF!', '#VALEUR!', '#DIV/0!', '#N/A'],
                keep_default_na=True
            )
            
            # Nettoyer les données
            df = self.clean_dataframe(df)
            
            return df
        except FileNotFoundError:
            raise Exception(f"Fichier introuvable : {self.excel_file}")
        except Exception as e:
            raise Exception(f"Erreur lors du chargement du fichier Excel : {str(e)}")
    
    def clean_dataframe(self, df):
        """
        Nettoie le DataFrame en gérant les erreurs et valeurs vides
        
        Args:
            df: DataFrame pandas à nettoyer
            
        Returns:
            DataFrame nettoyé
        """
        if df is None or df.empty:
            return df
        
        # Créer une copie pour éviter les modifications sur l'original
        df_clean = df.copy()
        
        # Remplacer les erreurs Excel par NaN
        error_patterns = ['#NOM?', '#REF!', '#VALEUR!', '#DIV/0!', '#N/A', '#NULL!', '#NUM!']
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':  # Seulement pour les colonnes texte
                df_clean[col] = df_clean[col].replace(error_patterns, pd.NA)
        
        # Nettoyer les chaînes de caractères
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                # Convertir en string et nettoyer
                df_clean[col] = df_clean[col].astype(str).replace(['nan', 'None', 'NULL', 'null', 'N/A', 'n/a'], pd.NA)
                # Supprimer les espaces en début/fin
                df_clean[col] = df_clean[col].str.strip() if df_clean[col].dtype == 'object' else df_clean[col]
                # Remplacer les chaînes vides par NaN
                df_clean[col] = df_clean[col].replace(['', ' '], pd.NA)
        
        # Convertir les colonnes numériques en gérant les erreurs
        numeric_columns = ['rating', 'reviews_count', 'longitude', 'latitude']
        for col in numeric_columns:
            if col in df_clean.columns:
                try:
                    # Remplacer les virgules par des points pour les nombres français
                    if df_clean[col].dtype == 'object':
                        df_clean[col] = df_clean[col].str.replace(',', '.', regex=False)
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                except:
                    pass  # Garder la colonne telle quelle si la conversion échoue
        
        return df_clean
    
    def validate_row(self, row, row_index):
        """
        Valide une ligne de données et retourne les erreurs éventuelles
        
        Args:
            row: Ligne du DataFrame (Series)
            row_index: Index de la ligne dans le DataFrame original
            
        Returns:
            tuple: (is_valid, errors_list)
        """
        errors = []
        
        # Vérifier que le nom existe (champ minimum requis)
        name = row.get('name', '')
        if pd.isna(name) or str(name).strip() == '' or str(name).strip().lower() in ['nan', 'none', 'null']:
            errors.append(f"Ligne {row_index + 2}: Nom manquant (champ obligatoire)")
            return False, errors
        
        # Vérifier les erreurs Excel dans les champs importants
        important_fields = ['name', 'website', 'category']
        for field in important_fields:
            if field in row:
                value = row[field]
                if pd.notna(value) and isinstance(value, str):
                    if value.startswith('#'):
                        errors.append(f"Ligne {row_index + 2}: Erreur Excel dans '{field}': {value}")
        
        # Valider l'URL si présente
        website = row.get('website', '')
        if pd.notna(website) and str(website).strip():
            website_str = str(website).strip()
            if not website_str.startswith(('http://', 'https://', 'www.')) and '.' in website_str:
                # URL valide mais sans protocole, sera corrigée par normalize_url
                pass
            elif website_str.startswith('#'):
                errors.append(f"Ligne {row_index + 2}: Erreur Excel dans 'website': {website_str}")
        
        # Valider les coordonnées géographiques si présentes
        if 'longitude' in row and pd.notna(row['longitude']):
            try:
                lon = float(row['longitude'])
                if not (-180 <= lon <= 180):
                    errors.append(f"Ligne {row_index + 2}: Longitude invalide: {lon}")
            except (ValueError, TypeError):
                errors.append(f"Ligne {row_index + 2}: Longitude non numérique: {row['longitude']}")
        
        if 'latitude' in row and pd.notna(row['latitude']):
            try:
                lat = float(row['latitude'])
                if not (-90 <= lat <= 90):
                    errors.append(f"Ligne {row_index + 2}: Latitude invalide: {lat}")
            except (ValueError, TypeError):
                errors.append(f"Ligne {row_index + 2}: Latitude non numérique: {row['latitude']}")
        
        return len(errors) == 0, errors
    
    def normalize_url(self, url):
        """
        Normalise une URL en gérant les erreurs et valeurs vides
        
        Args:
            url: URL à normaliser (peut être NaN, None, ou une erreur Excel)
            
        Returns:
            URL normalisée ou None si invalide
        """
        if pd.isna(url) or not url:
            return None
        
        # Convertir en string et nettoyer
        url_str = str(url).strip()
        
        # Ignorer les erreurs Excel
        if url_str.startswith('#'):
            return None
        
        # Ignorer les valeurs invalides
        if url_str.lower() in ['nan', 'none', 'null', 'n/a', '']:
            return None
        
        # Ajouter le protocole si manquant
        if not url_str.startswith(('http://', 'https://')):
            url_str = 'https://' + url_str
        
        return url_str
    
    def extract_emails(self, text, domain=None):
        """Extrait les emails d'un texte"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = set(re.findall(email_pattern, text, re.IGNORECASE))
        
        # Filtrer les emails du domaine si spécifié
        if domain:
            emails = {e for e in emails if domain.lower() in e.lower()}
        
        return list(emails)
    
    def find_contact_page(self, base_url, soup):
        """Trouve la page de contact"""
        contact_keywords = ['contact', 'nous-contacter', 'about', 'a-propos', 'equipe', 'team']
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.get_text().lower()
            
            for keyword in contact_keywords:
                if keyword in href or keyword in text:
                    absolute_url = urljoin(base_url, link['href'])
                    return absolute_url
        
        return None
    
    def extract_logo(self, soup, base_url):
        """Extrait le logo du site"""
        logo_urls = []
        
        # Chercher dans les balises img avec des attributs communs pour les logos
        logo_selectors = [
            {'class': re.compile(r'logo', re.I)},
            {'id': re.compile(r'logo', re.I)},
            {'alt': re.compile(r'logo', re.I)},
        ]
        
        for selector in logo_selectors:
            for img in soup.find_all('img', selector):
                src = img.get('src') or img.get('data-src')
                if src:
                    logo_url = urljoin(base_url, src)
                    logo_urls.append(logo_url)
        
        # Chercher dans les liens avec des classes logo
        for link in soup.find_all('a', {'class': re.compile(r'logo', re.I)}):
            img = link.find('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src:
                    logo_url = urljoin(base_url, src)
                    logo_urls.append(logo_url)
        
        # Chercher dans le header/navbar
        header = soup.find('header') or soup.find('nav')
        if header:
            for img in header.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    logo_url = urljoin(base_url, src)
                    logo_urls.append(logo_url)
        
        # Retourner le premier logo trouvé
        return logo_urls[0] if logo_urls else None
    
    def extract_responsable_name(self, soup, text, base_url=None):
        """Extrait le nom du responsable depuis la page (amélioré)"""
        patterns = [
            r'(?:directeur|dirigeant|fondateur|gérant|CEO|CTO|CFO|CMO|responsable|manager|président|PDG)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+).*?(?:directeur|dirigeant|fondateur|gérant|CEO|CTO|président|PDG)',
            r'(?:M\.|Mme|Monsieur|Madame|Mr|Mrs|Ms)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+).*?(?:gère|dirige|fondé|créé)',
        ]
        
        # Chercher dans les sections spécifiques
        search_areas = []
        
        # Section équipe/about
        for section in soup.find_all(['section', 'div'], {'class': re.compile(r'equipe|team|about|a-propos|contact', re.I)}):
            search_areas.append(section.get_text())
        
        # Balises spécifiques
        for tag in ['h1', 'h2', 'h3', 'h4', 'p', 'div', 'span']:
            for elem in soup.find_all(tag):
                text_elem = elem.get_text().strip()
                if text_elem and len(text_elem) < 200:  # Éviter les textes trop longs
                    search_areas.append(text_elem)
        
        search_areas.append(text)
        
        # Chercher les noms
        found_names = []
        for text_to_search in search_areas:
            for pattern in patterns:
                matches = re.finditer(pattern, text_to_search, re.IGNORECASE)
                for match in matches:
                    name = match.group(1) if match.lastindex else match.group(0)
                    name = name.strip()
                    words = name.split()
                    # Filtrer les noms valides (2-4 mots, pas trop longs, commence par majuscule)
                    if 2 <= len(words) <= 4 and len(name) < 60 and name[0].isupper():
                        # Éviter les faux positifs
                        if not any(word.lower() in ['directeur', 'dirigeant', 'fondateur', 'gérant', 'entreprise', 'société'] for word in words):
                            found_names.append(name)
        
        # Retourner le nom le plus fréquent ou le premier
        if found_names:
            # Compter les occurrences
            from collections import Counter
            name_counts = Counter(found_names)
            return name_counts.most_common(1)[0][0]
        
        return None
    
    def detect_technologies(self, soup, html_content):
        """Détecte les technologies utilisées"""
        technologies = []
        html_lower = html_content.lower()
        
        if 'bootstrap' in html_lower:
            version = re.search(r'bootstrap[-\s]?([0-9.]+)', html_lower)
            technologies.append(f"Bootstrap {version.group(1) if version else ''}")
        
        if 'react' in html_lower or 'reactjs' in html_lower:
            technologies.append('React')
        if 'vue' in html_lower or 'vuejs' in html_lower:
            technologies.append('Vue.js')
        if 'angular' in html_lower:
            technologies.append('Angular')
        
        if 'wp-content' in html_lower or 'wordpress' in html_lower:
            technologies.append('WordPress')
        if 'joomla' in html_lower:
            technologies.append('Joomla')
        if 'drupal' in html_lower:
            technologies.append('Drupal')
        
        meta_generator = soup.find('meta', {'name': 'generator'})
        if meta_generator:
            gen_content = meta_generator.get('content', '').lower()
            if 'wordpress' in gen_content:
                technologies.append('WordPress')
            elif 'joomla' in gen_content:
                technologies.append('Joomla')
        
        return ', '.join(technologies) if technologies else 'Non détecté'
    
    def analyze_site_age(self, soup, html_content):
        """Analyse l'âge du site"""
        score = 0
        indicators = []
        
        for pattern in self.age_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                score += 2
                indicators.append('Copyright ancien')
        
        html_lower = html_content.lower()
        for tech in self.old_technologies:
            if tech in html_lower:
                score += 1
                indicators.append(f'Technologie obsolète: {tech}')
        
        if soup.find('embed') or soup.find('object'):
            score += 1
            indicators.append('Flash/Plugins obsolètes')
        
        if soup.find('table', {'cellpadding': True}) or soup.find('font'):
            score += 1
            indicators.append('HTML ancien (tables/font)')
        
        if score >= 4:
            status = 'Très obsolète'
            opportunity = 'Élevée'
        elif score >= 2:
            status = 'Obsolète'
            opportunity = 'Moyenne'
        elif score >= 1:
            status = 'À moderniser'
            opportunity = 'Faible'
        else:
            status = 'Moderne'
            opportunity = 'Très faible'
        
        return {
            'status': status,
            'score': score,
            'indicators': '; '.join(indicators) if indicators else 'Aucun',
            'opportunity': opportunity
        }
    
    def estimate_company_size(self, soup, text, category):
        """Estime la taille de l'entreprise avec extraction précise du nombre de salariés"""
        text_lower = (text or '').lower()
        category = category or ''
        
        # Patterns pour extraire le nombre exact de salariés
        size_patterns = [
            r'(\d+)\s*(?:employés|salariés|collaborateurs|personnes|équipe)',
            r'(?:équipe de|équipe|nous sommes)\s+(\d+)',
            r'(\d+)\s*(?:personnes|collaborateurs)\s+(?:dans|au sein de)',
            r'plus de\s+(\d+)\s*(?:employés|salariés)',
            r'(\d+)\s*à\s*(\d+)\s*(?:employés|salariés)',
        ]
        
        extracted_numbers = []
        for pattern in size_patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                # Si le pattern contient deux groupes (ex: "10 à 20")
                if len(match.groups()) == 2:
                    num1, num2 = match.groups()
                    if num1 and num2:
                        # Prendre la moyenne
                        avg = (int(num1) + int(num2)) // 2
                        extracted_numbers.append(avg)
                elif match.group(1):
                    extracted_numbers.append(int(match.group(1)))
        
        # Si on a trouvé des nombres, utiliser le plus grand (souvent le plus récent)
        if extracted_numbers:
            max_count = max(extracted_numbers)
            if max_count >= 250:
                return f'Grande entreprise ({max_count}+ employés)'
            elif max_count >= 50:
                return f'PME moyenne-grande ({max_count} employés)'
            elif max_count >= 10:
                return f'PME ({max_count} employés)'
            else:
                return f'Petite entreprise ({max_count} employés)'
        
        # Indicateurs textuels pour grandes entreprises
        large_indicators = [
            'groupe', 'filiale', 'siège social', 'plusieurs sites', 'multinational',
            'plusieurs bureaux', 'réseau', 'groupe international', 'filiales'
        ]
        if any(ind in text_lower for ind in large_indicators):
            return 'Grande entreprise (50+ employés)'
        
        # Estimation basée sur la catégorie
        if any(word in category.lower() for word in ['restaurant', 'café', 'boutique', 'artisan', 'commerce']):
            return 'Très petite entreprise (1-5 employés)'
        elif any(word in category.lower() for word in ['agence', 'consulting', 'service', 'cabinet']):
            return 'Petite entreprise (5-15 employés)'
        elif any(word in category.lower() for word in ['industrie', 'production', 'fabrication']):
            return 'PME/Grande entreprise (variable)'
        else:
            return 'PME (10-50 employés)'
    
    def extract_sector(self, category, text, soup=None):
        """Extrait le secteur d'activité (amélioré avec plus de secteurs)"""
        text_lower = text.lower()
        category_lower = category.lower() if category else ''
        
        # Chercher dans les meta tags
        sector_from_meta = None
        if soup:
            meta_description = soup.find('meta', {'name': 'description'})
            if meta_description:
                desc = meta_description.get('content', '').lower()
                text_lower = desc + ' ' + text_lower
            
            # Chercher dans les structured data
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict) and '@type' in data:
                        if data.get('@type') == 'Organization' and 'industry' in data:
                            sector_from_meta = data['industry']
                except:
                    pass
        
        sectors = {
            'Restauration': ['restaurant', 'café', 'boulangerie', 'pizzeria', 'brasserie', 'bar', 'snack', 'fast-food', 'traiteur', 'catering'],
            'Commerce': ['boutique', 'magasin', 'commerce', 'retail', 'vente', 'e-commerce', 'ecommerce', 'détaillant', 'distributeur'],
            'Services': ['service', 'consulting', 'conseil', 'assistance', 'prestation', 'cabinet'],
            'Technologie': ['tech', 'informatique', 'développement', 'software', 'digital', 'it', 'système', 'solutions informatiques', 'sas', 'saas'],
            'Immobilier': ['immobilier', 'agence immobilière', 'vente', 'location', 'biens immobiliers', 'promoteur'],
            'Santé': ['médecin', 'dentiste', 'pharmacie', 'santé', 'médical', 'clinique', 'cabinet médical', 'hôpital', 'laboratoire'],
            'Beauté': ['coiffeur', 'esthétique', 'beauté', 'salon', 'institut', 'spa', 'bien-être'],
            'Automobile': ['garage', 'automobile', 'voiture', 'réparation', 'concessionnaire', 'véhicule', 'auto'],
            'BTP': ['construction', 'bâtiment', 'travaux', 'maçonnerie', 'charpente', 'plomberie', 'électricité', 'rénovation'],
            'Éducation': ['école', 'formation', 'enseignement', 'cours', 'université', 'lycée', 'collège', 'centre de formation'],
            'Finance': ['banque', 'assurance', 'finance', 'courtier', 'conseil financier', 'gestion de patrimoine'],
            'Industrie': ['industrie', 'production', 'fabrication', 'manufacturing', 'usine', 'atelier'],
            'Transport': ['transport', 'logistique', 'livraison', 'messagerie', 'fret'],
            'Communication': ['communication', 'marketing', 'publicité', 'agence de communication', 'media'],
            'Juridique': ['avocat', 'juridique', 'droit', 'cabinet d\'avocats', 'notaire'],
            'Architecture': ['architecture', 'architecte', 'bureau d\'études', 'ingénierie'],
            'Hôtellerie': ['hôtel', 'hôtellerie', 'tourisme', 'hébergement', 'gîte', 'chambre d\'hôte'],
            'Artisanat': ['artisan', 'artisanat', 'artisan d\'art', 'métier d\'art'],
        }
        
        search_text = category_lower + ' ' + text_lower
        
        # Score par secteur
        sector_scores = {}
        for sector, keywords in sectors.items():
            score = 0
            for keyword in keywords:
                if keyword in search_text:
                    score += 1
            if score > 0:
                sector_scores[sector] = score
        
        # Retourner le secteur avec le score le plus élevé
        if sector_scores:
            best_sector = max(sector_scores.items(), key=lambda x: x[1])[0]
            return best_sector
        
        # Si on a trouvé dans les meta tags
        if sector_from_meta:
            return sector_from_meta
        
        # Sinon utiliser la catégorie originale
        return category if category else 'Non spécifié'
    
    def extract_social_media(self, soup, base_url):
        """Extrait les liens vers les réseaux sociaux"""
        social_links = {}
        social_patterns = {
            'linkedin': ['linkedin.com', 'linkedin'],
            'facebook': ['facebook.com', 'fb.com', 'facebook'],
            'twitter': ['twitter.com', 'x.com', 'twitter'],
            'instagram': ['instagram.com', 'instagram'],
            'youtube': ['youtube.com', 'youtu.be', 'youtube'],
        }
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            for platform, patterns in social_patterns.items():
                if any(pattern in href for pattern in patterns):
                    if platform not in social_links:
                        social_links[platform] = urljoin(base_url, link['href'])
        
        return social_links
    
    def extract_description(self, soup):
        """Extrait la description de l'entreprise"""
        # Chercher dans les meta tags
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            desc = meta_desc.get('content', '').strip()
            if desc and len(desc) > 20:
                return desc[:300]  # Limiter à 300 caractères
        
        # Chercher dans les balises spécifiques
        for selector in [{'class': re.compile(r'description|about|presentation', re.I)}, 
                        {'id': re.compile(r'description|about|presentation', re.I)}]:
            elem = soup.find('div', selector) or soup.find('section', selector)
            if elem:
                text = elem.get_text().strip()
                if text and len(text) > 20:
                    return text[:300]
        
        # Chercher dans le premier paragraphe significatif
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if len(text) > 50 and len(text) < 500:
                return text[:300]
        
        return None
    
    def extract_founded_year(self, soup, text):
        """Extrait l'année de création/fondation"""
        patterns = [
            r'(?:fondé|créé|établi|depuis)\s+(?:en\s+)?(19\d{2}|20[0-2]\d)',
            r'(?:depuis|en)\s+(19\d{2}|20[0-2]\d)',
            r'©\s*(19\d{2}|20[0-2]\d)',
            r'copyright\s+(19\d{2}|20[0-2]\d)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                year = int(match.group(1))
                if 1900 <= year <= 2025:
                    return year
        
        return None
    
    def scrape_website(self, url, max_pages=3, use_global_scraper=True):
        """Scrape un site web et extrait les informations (amélioré)
        
        Cette méthode peut utiliser un callback de progression optionnel
        stocké dans self.progress_callback (utilisé notamment pour remonter
        l'avancement en temps réel via Celery/WebSocket).
        
        Note: Si use_global_scraper=False, seul un scraping basique est effectué
        (pour l'analyse initiale). Le scraping complet est fait séparément via scrape_analysis_task.
        """
        if not url:
            return None
        
        try:
            url = self.normalize_url(url)
            if not url:
                return None
            
            # Utiliser le scraper unifié si demandé
            # Si use_global_scraper=False, on fait juste un scraping basique pour l'analyse initiale
            if use_global_scraper:
                try:
                    from services.unified_scraper import UnifiedScraper
                    # Callback de progression optionnel (peut être défini par un wrapper)
                    progress_callback = getattr(self, 'progress_callback', None)
                    unified_scraper = UnifiedScraper(
                        base_url=url,
                        max_workers=min(5, max_pages),
                        max_depth=2,
                        max_time=300,
                        progress_callback=progress_callback
                    )
                    scraper_results = unified_scraper.scrape()
                    
                    # Construire le résultat au format attendu
                    result = {
                        'url': url,
                        'emails': [e.get('email', e) if isinstance(e, dict) else e for e in scraper_results.get('emails', [])],
                        'people': scraper_results.get('people', []),
                        'phones': [p.get('phone', p) if isinstance(p, dict) else p for p in scraper_results.get('phones', [])],
                        'social_media': scraper_results.get('social_links', {}),
                        'technologies': scraper_results.get('technologies', {}),
                        'metadata': scraper_results.get('metadata', {}),
                        'resume': scraper_results.get('resume', ''),
                        'scraper_data': scraper_results  # Garder les données brutes pour la sauvegarde BDD
                    }
                    
                    # Extraire les informations de base du site
                    response = requests.get(url, headers=self.headers, timeout=10, allow_redirects=True)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    text = soup.get_text()
                    
                    result.update({
                        'description': self.extract_description(soup),
                        'founded_year': self.extract_founded_year(soup, text),
                        'sector': self.extract_sector(None, text, soup),
                        'company_size': self.estimate_company_size(soup, text, None),
                        'website_age': self.analyze_website_age(soup, text)
                    })
                    
                    return result
                except Exception as e:
                    # En cas d'erreur, continuer avec le scraping classique
                    pass
            
            # Scraping classique (fallback)
            response = requests.get(url, headers=self.headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            html_content = response.text
            
            domain = urlparse(url).netloc
            emails = self.extract_emails(response.text, domain)
            
            # Chercher sur la page contact si pas d'emails
            contact_soup = None
            contact_text = ''
            if not emails:
                contact_url = self.find_contact_page(url, soup)
                if contact_url and contact_url != url:
                    try:
                        time.sleep(self.delay)
                        contact_response = requests.get(contact_url, headers=self.headers, timeout=10)
                        if contact_response.status_code == 200:
                            emails.extend(self.extract_emails(contact_response.text, domain))
                            # Mettre à jour le soup pour chercher le responsable sur la page contact
                            contact_soup = BeautifulSoup(contact_response.text, 'html.parser')
                            contact_text = contact_soup.get_text()
                    except Exception as e:
                        contact_soup = None
                        contact_text = ''
            
            # Extraire toutes les informations
            logo = self.extract_logo(soup, url)
            responsable = self.extract_responsable_name(soup, text, url)
            if not responsable and contact_soup:
                responsable = self.extract_responsable_name(contact_soup, contact_text, url)
            
            technologies = self.detect_technologies(soup, html_content)
            age_analysis = self.analyze_site_age(soup, html_content)
            social_media = self.extract_social_media(soup, url)
            description = self.extract_description(soup)
            founded_year = self.extract_founded_year(soup, text)
            
            # Analyse technique approfondie (désactivée par défaut lors de l'import Excel)
            # L'analyse technique peut être lancée manuellement depuis l'interface
            technical_info = {}
            # if self.technical_analyzer:
            #     try:
            #         tech_details = self.technical_analyzer.analyze_technical_details(url, enable_nmap=False)
            #         if tech_details and not tech_details.get('error'):
            #             technical_info = tech_details
            #     except Exception as e:
            #         pass  # Ne pas bloquer si l'analyse technique échoue
            
            result = {
                'emails': '; '.join(emails[:5]) if emails else None,
                'email_principal': emails[0] if emails else None,
                'logo_url': logo,
                'responsable': responsable,
                'technologies': technologies,
                'site_status': age_analysis['status'],
                'site_opportunity': age_analysis['opportunity'],
                'site_indicators': age_analysis['indicators'],
                'social_linkedin': social_media.get('linkedin'),
                'social_facebook': social_media.get('facebook'),
                'social_twitter': social_media.get('twitter'),
                'social_instagram': social_media.get('instagram'),
                'social_youtube': social_media.get('youtube'),
                'description': description,
                'annee_creation': founded_year,
                'html_content_sample': text[:1000] if text else None
            }
            
            # Ajouter toutes les informations techniques (beaucoup plus de colonnes maintenant)
            technical_columns = {
                # Framework et CMS
                'framework': technical_info.get('framework'),
                'framework_version': technical_info.get('framework_version'),
                'cms': technical_info.get('cms'),
                'cms_plugins': technical_info.get('cms_plugins'),
                'css_framework': technical_info.get('css_framework'),
                'js_library': technical_info.get('js_library'),
                'backend_language': technical_info.get('backend_language'),
                
                # Serveur
                'server': technical_info.get('server'),
                'server_version': technical_info.get('server_version'),
                'php_version': technical_info.get('php_version'),
                'aspnet_version': technical_info.get('aspnet_version'),
                'powered_by': technical_info.get('powered_by'),
                
                # Infrastructure
                'hosting_provider': technical_info.get('hosting_provider'),
                'cdn': technical_info.get('cdn'),
                'ip_address': technical_info.get('ip_address'),
                'hostname': technical_info.get('hostname'),
                'waf': technical_info.get('waf'),
                
                # Domaine
                'domain_creation_date': technical_info.get('domain_creation_date'),
                'domain_updated_date': technical_info.get('domain_updated_date'),
                'domain_registrar': technical_info.get('domain_registrar'),
                'name_servers': technical_info.get('name_servers'),
                
                # SSL/TLS
                'ssl_issuer': str(technical_info.get('ssl_issuer', {}).get('organizationName', '')) if technical_info.get('ssl_issuer') else None,
                'ssl_version': technical_info.get('ssl_version'),
                'ssl_valid_from': technical_info.get('ssl_valid_from'),
                'ssl_valid_until': technical_info.get('ssl_valid_until'),
                'ssl_days_until_expiry': technical_info.get('ssl_days_until_expiry'),
                
                # Dates
                'last_modified': technical_info.get('last_modified'),
                'server_date': technical_info.get('server_date'),
                
                # Analytics et services
                'analytics': technical_info.get('analytics'),
                'chat_service': technical_info.get('chat_service'),
                'email_service': technical_info.get('email_service'),
                'payment_gateway': ', '.join(technical_info.get('payment_gateway', [])) if isinstance(technical_info.get('payment_gateway'), list) else technical_info.get('payment_gateway'),
                
                # SEO
                'meta_title': technical_info.get('meta_title'),
                'meta_title_length': technical_info.get('meta_title_length'),
                'meta_description': technical_info.get('meta_description'),
                'meta_description_length': technical_info.get('meta_description_length'),
                'meta_keywords': technical_info.get('meta_keywords'),
                'canonical_url': technical_info.get('canonical_url'),
                'hreflang': technical_info.get('hreflang'),
                
                # Performance
                'http_version': technical_info.get('http_version'),
                'compression': technical_info.get('compression'),
                'cache_control': technical_info.get('cache_control'),
                'lazy_loading': technical_info.get('lazy_loading'),
                'minified_assets': technical_info.get('minified_assets'),
                
                # Sécurité
                'security_score': technical_info.get('security_score'),
                'security_level': technical_info.get('security_level'),
                'strict_transport_security': technical_info.get('strict_transport_security'),
                'content_security_policy': technical_info.get('content_security_policy'),
                'x_frame_options': technical_info.get('x_frame_options'),
                
                # Cookies
                'cookies_count': technical_info.get('cookies_count'),
                'cookie_types': technical_info.get('cookie_types'),
                
                # Robots et Sitemap
                'robots_txt_exists': technical_info.get('robots_txt_exists'),
                'robots_has_rules': technical_info.get('robots_has_rules'),
                'sitemap_url': technical_info.get('sitemap_url'),
                'sitemap_exists': technical_info.get('sitemap_exists'),
                'sitemap_url_count': technical_info.get('sitemap_url_count'),
            }
            
            result.update(technical_columns)
            
            return result
            
        except requests.exceptions.RequestException as e:
            return {'error': f'Erreur requête: {str(e)[:50]}'}
        except Exception as e:
            return {'error': f'Erreur: {str(e)[:50]}'}
    
    def analyze_entreprise(self, row):
        """Analyse une entreprise complète"""
        name = row.get('name', '')
        website = row.get('website', '')
        category = row.get('category', '')
        address = row.get('address_1', '')
        phone = row.get('phone_number', '')
        
        result = {
            'name': name,
            'website': website,
            'category': category,
            'address': address,
            'phone': phone
        }
        
        soup = None
        text_for_sector = ''
        
        if website:
            # Désactiver le scraping complet ici car il sera fait séparément via scrape_analysis_task
            # On fait juste un scraping basique pour obtenir les infos essentielles (titre, description, etc.)
            site_data = self.scrape_website(website, use_global_scraper=False)
            if site_data and not site_data.get('error'):
                # Garder les données brutes du scraper pour la sauvegarde BDD
                result['scraper_data'] = site_data.get('scraper_data', site_data)
                # Formater les résultats du scraper global
                if 'emails' in site_data and isinstance(site_data['emails'], list):
                    emails_list = [e.get('email', e) if isinstance(e, dict) else e for e in site_data['emails']]
                    result['emails'] = '; '.join(emails_list[:5]) if emails_list else None
                    result['email_principal'] = emails_list[0] if emails_list else None
                
                if 'people' in site_data and isinstance(site_data['people'], list):
                    people_list = site_data['people']
                    people_names = [p.get('name', '') for p in people_list if isinstance(p, dict) and p.get('name')]
                    result['personnes_trouvees'] = '; '.join(people_names[:5]) if people_names else None
                    result['nombre_personnes'] = len(people_names)
                    
                    # Enrichir avec les détails des personnes
                    people_details = []
                    for person in people_list[:10]:  # Limiter à 10 personnes pour éviter la surcharge
                        if isinstance(person, dict) and person.get('name'):
                            person_info = {
                                'name': person.get('name', ''),
                                'email': person.get('email', ''),
                                'title': person.get('title', ''),
                                'phone': person.get('phone', ''),
                                'linkedin': person.get('linkedin_url', '')
                            }
                            people_details.append(person_info)
                    
                    # Stocker les détails complets des personnes
                    result['personnes_detaillees'] = people_details
                    
                    # Extraire les emails des personnes
                    people_emails = [p.get('email', '') for p in people_details if p.get('email')]
                    if people_emails:
                        if 'emails' in result and result['emails']:
                            all_emails = result['emails'].split('; ') + people_emails
                            result['emails'] = '; '.join(list(dict.fromkeys(all_emails))[:10])  # Éviter les doublons
                        else:
                            result['emails'] = '; '.join(people_emails[:5])
                    
                    # Extraire les téléphones des personnes
                    people_phones = [p.get('phone', '') for p in people_details if p.get('phone')]
                    if people_phones:
                        if 'telephones' in result and result['telephones']:
                            all_phones = result['telephones'].split('; ') + people_phones
                            result['telephones'] = '; '.join(list(dict.fromkeys(all_phones))[:10])
                        else:
                            result['telephones'] = '; '.join(people_phones[:5])
                    
                    # Extraire les LinkedIn des personnes
                    people_linkedin = [p.get('linkedin', '') for p in people_details if p.get('linkedin')]
                    if people_linkedin:
                        result['linkedin_personnes'] = '; '.join(people_linkedin[:5])
                
                if 'phones' in site_data and isinstance(site_data['phones'], list):
                    phones_list = [p.get('phone', p) if isinstance(p, dict) else p for p in site_data['phones']]
                    result['telephones'] = '; '.join(phones_list[:5]) if phones_list else None
                    result['nombre_telephones'] = len(phones_list)
                
                if 'social_media' in site_data and isinstance(site_data['social_media'], dict):
                    social = site_data['social_media']
                    result['social_linkedin'] = social.get('linkedin', [{}])[0].get('url') if isinstance(social.get('linkedin'), list) and social.get('linkedin') else social.get('linkedin')
                    result['social_facebook'] = social.get('facebook', [{}])[0].get('url') if isinstance(social.get('facebook'), list) and social.get('facebook') else social.get('facebook')
                    result['social_twitter'] = social.get('twitter', [{}])[0].get('url') if isinstance(social.get('twitter'), list) and social.get('twitter') else social.get('twitter')
                    result['social_instagram'] = social.get('instagram', [{}])[0].get('url') if isinstance(social.get('instagram'), list) and social.get('instagram') else social.get('instagram')
                
                # Mettre à jour avec les autres données (en excluant resume pour le gérer séparément)
                result.update({k: v for k, v in site_data.items() if k not in ['emails', 'people', 'phones', 'social_media', 'resume']})
                
                # Toujours inclure le résumé généré par le scraper (même s'il est vide)
                result['resume'] = site_data.get('resume', '')
                
                # Récupérer le soup pour les analyses suivantes
                try:
                    response = requests.get(website, headers=self.headers, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        text_for_sector = soup.get_text()
                except:
                    pass
                time.sleep(self.delay)
            elif site_data:
                result.update(site_data)  # Inclure l'erreur
        else:
            result['error'] = 'Pas de site web'
        
        # Utiliser le texte extrait pour les analyses
        if not text_for_sector:
            text_for_sector = result.get('html_content_sample', '') or ''
        
        result['secteur'] = self.extract_sector(category, text_for_sector, soup)
        
        result['taille_estimee'] = self.estimate_company_size(
            soup,
            text_for_sector,
            category
        )
        
        if result.get('site_opportunity'):
            if result['site_opportunity'] in ['Élevée', 'Moyenne']:
                result['statut'] = 'Prospect intéressant'
            else:
                result['statut'] = 'À suivre'
        else:
            result['statut'] = 'À analyser'
        
        return result
    
    def process_all(self):
        """Traite toutes les entreprises"""
        df = self.load_excel()
        if df is None:
            return None
        
        results = []
        
        # Vérifier si la méthode avec progression existe
        use_progress = hasattr(self, 'analyze_entreprise_with_progress')
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            if use_progress:
                # Utiliser la méthode avec progression qui prend (row, idx)
                futures = {executor.submit(self.analyze_entreprise_with_progress, row, idx): idx 
                          for idx, row in df.iterrows()}
            else:
                # Utiliser la méthode standard qui prend seulement (row)
                futures = {executor.submit(self.analyze_entreprise, row): idx 
                        for idx, row in df.iterrows()}
            
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({'name': df.iloc[idx].get('name', 'Erreur'), 'error': str(e)})
        
        results_df = pd.DataFrame(results)
        
        final_df = df.merge(results_df, on='name', how='left', suffixes=('', '_new'))
        
        original_cols = list(df.columns)
        new_cols = [col for col in results_df.columns if col not in original_cols]
        final_df = final_df[original_cols + new_cols]
        
        # Ne plus exporter en Excel (retourne simplement le DataFrame)
        return final_df

