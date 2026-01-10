"""
Service d'analyse OSINT (Open Source Intelligence)
Collecte d'informations depuis des sources publiques
"""

import subprocess
import shutil
import socket
import json
import re
import os
from urllib.parse import urlparse
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

# Importer la configuration
try:
    from config import SIRENE_API_KEY, SIRENE_API_URL, WSL_DISTRO, WSL_USER, OSINT_TOOL_TIMEOUT
except ImportError:
    # Valeurs par défaut si config n'est pas disponible
    SIRENE_API_KEY = os.environ.get('SIRENE_API_KEY', '')
    SIRENE_API_URL = os.environ.get('SIRENE_API_URL', 'https://recherche-entreprises.api.gouv.fr/search')
    WSL_DISTRO = os.environ.get('WSL_DISTRO', 'kali-linux')
    WSL_USER = os.environ.get('WSL_USER', 'loupix')
    OSINT_TOOL_TIMEOUT = int(os.environ.get('OSINT_TOOL_TIMEOUT', '60'))

try:
    import whois
except ImportError:
    whois = None

try:
    import dns.resolver
except ImportError:
    dns = None


class OSINTAnalyzer:
    """
    Analyseur OSINT pour collecter des informations publiques
    sur un domaine ou une entreprise
    """
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self._check_tools_availability()
    
    def _check_tools_availability(self):
        """Vérifie la disponibilité des outils OSINT"""
        # Vérifier WSL
        self.wsl_available = shutil.which('wsl') is not None
        # Utiliser les variables d'environnement pour WSL
        self.wsl_cmd_base = ['wsl', '-d', WSL_DISTRO, '-u', WSL_USER] if self.wsl_available else None
        
        # Vérifier les outils disponibles
        self.tools = {
            'dnsrecon': self._check_tool('dnsrecon'),
            'theharvester': self._check_tool('theharvester'),
            'sublist3r': self._check_tool('sublist3r'),
            'amass': self._check_tool('amass'),
            'whatweb': self._check_tool('whatweb'),
            'sslscan': self._check_tool('sslscan'),
            'sherlock': self._check_tool('sherlock'),
            'maigret': self._check_tool('maigret'),
        }
    
    def _check_tool(self, tool_name: str) -> bool:
        """Vérifie si un outil est disponible (natif ou via WSL)"""
        if shutil.which(tool_name):
            return True
        if self.wsl_available:
            # Essayer d'abord avec l'utilisateur configuré
            try:
                result = subprocess.run(
                    self.wsl_cmd_base + ['which', tool_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return True
            except:
                pass
            
            # Si ça échoue, essayer sans utilisateur
            try:
                result = subprocess.run(
                    ['wsl', '-d', WSL_DISTRO, 'which', tool_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return True
            except:
                pass
            
            # Pour theharvester, vérifier aussi theHarvester (nouveau nom)
            if tool_name == 'theharvester':
                try:
                    result = subprocess.run(
                        self.wsl_cmd_base + ['which', 'theHarvester'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return True
                except:
                    pass
        return False
    
    def _clean_ansi_codes(self, text: str) -> str:
        """
        Supprime les codes ANSI (couleurs) d'un texte
        """
        import re
        # Supprimer les codes ANSI (ESC[ ... m)
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def _run_wsl_command(self, command: List[str], timeout: int = 30) -> Dict:
        """
        Exécute une commande via WSL
        Optimisé pour réduire la surcharge de démarrage WSL
        Gère les cas où l'utilisateur spécifié ne fonctionne pas
        """
        if not self.wsl_available:
            return {'error': 'WSL non disponible'}
        
        # Remplacer theharvester par theHarvester si nécessaire
        if len(command) > 0 and command[0] == 'theharvester':
            # Vérifier si theHarvester existe
            try:
                result = subprocess.run(
                    self.wsl_cmd_base + ['which', 'theHarvester'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    command[0] = 'theHarvester'
            except:
                pass
        
        # Essayer d'abord avec l'utilisateur configuré
        try:
            cmd = self.wsl_cmd_base + command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=timeout,
                start_new_session=False
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {'error': 'Timeout'}
        except Exception as e:
            # Si ça échoue avec l'utilisateur, essayer sans
            try:
                cmd = ['wsl', '-d', WSL_DISTRO] + command
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=timeout,
                    start_new_session=False
                )
                return {
                    'success': result.returncode == 0,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }
            except subprocess.TimeoutExpired:
                return {'error': 'Timeout'}
            except Exception as e2:
                return {'error': str(e2)}
    
    def discover_subdomains(self, domain: str, progress_callback=None) -> List[str]:
        """
        Découvre les sous-domaines d'un domaine
        Utilise plusieurs outils : sublist3r, amass, dnsrecon
        """
        subdomains = set()
        
        # Vérifier si des outils sont disponibles
        available_tools = [k for k, v in self.tools.items() if v and k in ['sublist3r', 'amass', 'dnsrecon']]
        if not available_tools:
            if progress_callback:
                progress_callback('Aucun outil de découverte de sous-domaines disponible')
            return []
        
        # Sublist3r
        if self.tools['sublist3r']:
            if progress_callback:
                progress_callback('Recherche avec Sublist3r...')
            try:
                result = self._run_wsl_command(['sublist3r', '-d', domain, '-t', '10'], timeout=30)
                if result.get('success'):
                    for line in result['stdout'].split('\n'):
                        if domain in line and '.' in line:
                            subdomain = line.strip().split()[0] if ' ' in line else line.strip()
                            if subdomain.endswith(domain):
                                subdomains.add(subdomain)
                elif result.get('error') and 'Timeout' not in result['error']:
                    # Erreur autre que timeout, on continue
                    pass
            except Exception as e:
                # Erreur lors de l'exécution, on continue avec les autres outils
                pass
        
        # Amass (plus long, on le fait en dernier)
        if self.tools['amass']:
            if progress_callback:
                progress_callback('Recherche avec Amass...')
            try:
                result = self._run_wsl_command(['amass', 'enum', '-d', domain, '-passive'], timeout=45)
                if result.get('success'):
                    for line in result['stdout'].split('\n'):
                        if domain in line:
                            subdomain = line.strip()
                            if subdomain.endswith(domain):
                                subdomains.add(subdomain)
                elif result.get('error') and 'Timeout' not in result['error']:
                    pass
            except Exception as e:
                pass
        
        # DNSrecon
        if self.tools['dnsrecon']:
            if progress_callback:
                progress_callback('Recherche avec DNSrecon...')
            try:
                result = self._run_wsl_command(['dnsrecon', '-d', domain, '-t', 'brt'], timeout=30)
                if result.get('success'):
                    for line in result['stdout'].split('\n'):
                        if 'Found' in line or domain in line:
                            match = re.search(r'([a-zA-Z0-9.-]+\.' + domain.replace('.', r'\.') + ')', line)
                            if match:
                                subdomains.add(match.group(1))
                elif result.get('error') and 'Timeout' not in result['error']:
                    pass
            except Exception as e:
                pass
        
        if progress_callback:
            progress_callback(f'{len(subdomains)} sous-domaines trouvés')
        
        return sorted(list(subdomains))
    
    def get_dns_records(self, domain: str) -> Dict:
        """Récupère les enregistrements DNS d'un domaine"""
        records = {}
        
        if not dns:
            return {'error': 'dnspython non installé'}
        
        try:
            # Enregistrements A
            try:
                answers = dns.resolver.resolve(domain, 'A')
                records['A'] = [str(rdata) for rdata in answers]
            except:
                records['A'] = []
            
            # Enregistrements AAAA (IPv6)
            try:
                answers = dns.resolver.resolve(domain, 'AAAA')
                records['AAAA'] = [str(rdata) for rdata in answers]
            except:
                records['AAAA'] = []
            
            # Enregistrements MX
            try:
                answers = dns.resolver.resolve(domain, 'MX')
                records['MX'] = [str(rdata.exchange) for rdata in answers]
            except:
                records['MX'] = []
            
            # Enregistrements NS
            try:
                answers = dns.resolver.resolve(domain, 'NS')
                records['NS'] = [str(rdata) for rdata in answers]
            except:
                records['NS'] = []
            
            # Enregistrements TXT
            try:
                answers = dns.resolver.resolve(domain, 'TXT')
                records['TXT'] = [str(rdata) for rdata in answers]
            except:
                records['TXT'] = []
            
            # Enregistrements CNAME
            try:
                answers = dns.resolver.resolve(domain, 'CNAME')
                records['CNAME'] = [str(rdata) for rdata in answers]
            except:
                records['CNAME'] = []
        
        except Exception as e:
            records['error'] = str(e)
        
        return records
    
    def get_whois_info(self, domain: str) -> Dict:
        """Récupère les informations WHOIS d'un domaine"""
        if not whois:
            return {'error': 'python-whois non installé'}
        
        try:
            w = whois.whois(domain)
            return {
                'domain_name': w.domain_name,
                'registrar': w.registrar,
                'creation_date': str(w.creation_date) if w.creation_date else None,
                'expiration_date': str(w.expiration_date) if w.expiration_date else None,
                'updated_date': str(w.updated_date) if w.updated_date else None,
                'name_servers': w.name_servers,
                'emails': w.emails,
                'country': w.country,
                'org': w.org
            }
        except Exception as e:
            return {'error': str(e)}
    
    def harvest_emails(self, domain: str, progress_callback=None) -> List[str]:
        """
        Récupère des emails liés au domaine avec TheHarvester
        Retourne aussi les noms de personnes trouvés
        """
        emails = set()
        
        if not self.tools['theharvester']:
            return []
        
        # TheHarvester avec plusieurs sources incluant LinkedIn pour les personnes
        sources = ['google', 'bing', 'linkedin', 'twitter', 'github']
        for source in sources:
            if progress_callback:
                progress_callback(f'Recherche d\'emails via {source}...')
            
            result = self._run_wsl_command([
                'theHarvester',
                '-d', domain,
                '-b', source,
                '-l', '100'  # Augmenter le nombre de résultats
            ], timeout=60)
            
            if result.get('success'):
                for line in result['stdout'].split('\n'):
                    # Extraire les emails
                    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                    found_emails = re.findall(email_pattern, line)
                    for email in found_emails:
                        if domain in email:
                            emails.add(email.lower())
        
        return sorted(list(emails))
    
    def find_people_from_emails(self, emails: List[str], domain: str) -> List[Dict]:
        """
        Extrait les noms de personnes depuis les emails trouvés
        Retourne une liste de personnes avec leurs informations
        """
        people = []
        
        for email in emails:
            # Extraire le nom depuis l'email (ex: jean.dupont@domain.com -> Jean Dupont)
            local_part = email.split('@')[0]
            
            # Patterns courants
            name_parts = []
            if '.' in local_part:
                parts = local_part.split('.')
                # Filtrer les parties qui ressemblent à des noms (pas des chiffres, pas trop courtes)
                for part in parts:
                    if len(part) > 2 and part.isalpha():
                        name_parts.append(part.capitalize())
            
            person = {
                'email': email,
                'name': ' '.join(name_parts) if name_parts else local_part,
                'username': local_part,
                'domain': domain
            }
            
            if person['name']:
                people.append(person)
        
        return people
    
    def search_linkedin_people(self, domain: str, progress_callback=None) -> List[Dict]:
        """
        Recherche des personnes sur LinkedIn liées au domaine
        Utilise TheHarvester avec la source LinkedIn
        """
        people = []
        
        if not self.tools['theharvester']:
            return []
        
        if progress_callback:
            progress_callback('Recherche de personnes sur LinkedIn...')
        
        result = self._run_wsl_command([
            'theHarvester',
            '-d', domain,
            '-b', 'linkedin',
            '-l', '200'
        ], timeout=90)
        
        if result.get('success'):
            output = result['stdout']
            # Parser les résultats LinkedIn de TheHarvester
            # Format typique: "Name - Title - LinkedIn URL"
            linkedin_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*-\s*([^-]+?)\s*-\s*(https?://[^\s]+)'
            matches = re.findall(linkedin_pattern, output)
            
            for match in matches:
                name, title, url = match
                person = {
                    'name': name.strip(),
                    'title': title.strip(),
                    'linkedin_url': url.strip(),
                    'source': 'linkedin'
                }
                people.append(person)
        
        return people
    
    def search_social_media_profiles(self, usernames: List[str], progress_callback=None) -> Dict[str, List[Dict]]:
        """
        Recherche des profils sur les réseaux sociaux pour une liste d'utilisateurs
        Utilise Sherlock ou Maigret si disponibles
        """
        profiles = {}
        
        # Essayer d'abord Maigret (plus moderne)
        if self.tools['maigret']:
            for username in usernames[:5]:  # Limiter pour éviter les timeouts
                if progress_callback:
                    progress_callback(f'Recherche de profils pour {username}...')
                
                result = self._run_wsl_command([
                    'maigret',
                    username,
                    '--no-color',
                    '--print-found'
                ], timeout=60)
                
                if result.get('success'):
                    found_profiles = []
                    for line in result['stdout'].split('\n'):
                        if 'Found:' in line or 'http' in line:
                            # Parser les résultats Maigret
                            if 'http' in line:
                                url_match = re.search(r'(https?://[^\s]+)', line)
                                if url_match:
                                    found_profiles.append({
                                        'url': url_match.group(1),
                                        'source': 'maigret'
                                    })
                    if found_profiles:
                        profiles[username] = found_profiles
        
        # Sinon essayer Sherlock
        elif self.tools['sherlock']:
            for username in usernames[:5]:
                if progress_callback:
                    progress_callback(f'Recherche de profils pour {username}...')
                
                result = self._run_wsl_command([
                    'sherlock',
                    username,
                    '--no-color',
                    '--print-found'
                ], timeout=60)
                
                if result.get('success'):
                    found_profiles = []
                    for line in result['stdout'].split('\n'):
                        if 'Found:' in line or 'http' in line:
                            url_match = re.search(r'(https?://[^\s]+)', line)
                            if url_match:
                                found_profiles.append({
                                    'url': url_match.group(1),
                                    'source': 'sherlock'
                                })
                    if found_profiles:
                        profiles[username] = found_profiles
        
        return profiles
    
    def search_people_osint(self, domain: str, emails: List[str], progress_callback=None) -> Dict:
        """
        Recherche complète de personnes liées à l'entreprise
        Combine plusieurs sources et méthodes
        """
        people_data = {
            'people': [],
            'social_profiles': {},
            'linkedin_profiles': [],
            'summary': {}
        }
        
        # 1. Extraire les personnes depuis les emails
        if progress_callback:
            progress_callback('Extraction des personnes depuis les emails...')
        people_from_emails = self.find_people_from_emails(emails, domain)
        people_data['people'].extend(people_from_emails)
        
        # Note: Le scraping web profond de personnes a été déplacé dans le module people_scraper
        # Utilisez le scraper dédié depuis la page /scrapers pour scraper les personnes
        
        # 3. Rechercher sur LinkedIn
        linkedin_people = self.search_linkedin_people(domain, progress_callback)
        people_data['linkedin_profiles'] = linkedin_people
        
        # Fusionner les données LinkedIn avec les personnes trouvées
        for linkedin_person in linkedin_people:
            # Chercher si on a déjà cette personne par email
            found = False
            for person in people_data['people']:
                if linkedin_person['name'].lower() in person.get('name', '').lower():
                    person['linkedin_url'] = linkedin_person['linkedin_url']
                    if not person.get('title'):
                        person['title'] = linkedin_person.get('title', '')
                    found = True
                    break
            
            if not found:
                people_data['people'].append({
                    'name': linkedin_person['name'],
                    'title': linkedin_person.get('title', ''),
                    'linkedin_url': linkedin_person['linkedin_url'],
                    'source': 'linkedin'
                })
        
        # 4. Rechercher des profils sur les réseaux sociaux
        usernames = [p.get('username', '') for p in people_data['people'] if p.get('username')]
        if usernames:
            social_profiles = self.search_social_media_profiles(usernames, progress_callback)
            people_data['social_profiles'] = social_profiles
            
            # Ajouter les profils sociaux aux personnes
            for person in people_data['people']:
                username = person.get('username', '')
                if username and username in social_profiles:
                    person['social_profiles'] = social_profiles[username]
        
        # Résumé
        people_data['summary'] = {
            'total_people': len(people_data['people']),
            'with_emails': len([p for p in people_data['people'] if p.get('email')]),
            'with_linkedin': len([p for p in people_data['people'] if p.get('linkedin_url')]),
            'with_social_profiles': len([p for p in people_data['people'] if p.get('social_profiles')]),
            'from_website': len([p for p in people_data['people'] if 'website_scraping' in p.get('source', '')])
        }
        
        return people_data
    
    def search_company_financial_data(self, company_name: str, domain: str = None, progress_callback=None) -> Dict:
        """
        Recherche des données financières et juridiques d'une entreprise
        Utilise l'API Sirene (data.gouv.fr) et d'autres sources publiques
        """
        financial_data = {
            'sirene_data': {},
            'legal_info': {},
            'financial_info': {},
            'directors': [],
            'summary': {}
        }
        
        if progress_callback:
            progress_callback('Recherche des données financières et juridiques...')
        
        # 1. Recherche via API Sirene (data.gouv.fr)
        try:
            sirene_data = self._search_sirene_api(company_name, domain)
            if sirene_data:
                financial_data['sirene_data'] = sirene_data
                
                # Extraire les informations juridiques
                if sirene_data.get('uniteLegale'):
                    legal = sirene_data['uniteLegale']
                    financial_data['legal_info'] = {
                        'siren': legal.get('siren'),
                        'siret': legal.get('siret') or legal.get('siret_siege'),
                        'denomination': legal.get('nom_complet') or legal.get('nom') or legal.get('denomination'),
                        'forme_juridique': legal.get('forme_juridique') or legal.get('nature_juridique'),
                        'activite_principale': legal.get('activite_principale') or legal.get('section_activite_principale'),
                        'date_creation': legal.get('date_creation') or legal.get('date_debut_activite'),
                        'tranche_effectif': legal.get('tranche_effectif_salarie') or legal.get('effectif'),
                        'etat_administratif': legal.get('etat_administratif') or legal.get('etat'),
                        'capital_social': legal.get('capital_social'),
                        'adresse': self._format_sirene_address(legal.get('siege', {}) or legal.get('adresse', {}))
                    }
                    
                    # Dirigeants (si disponibles dans l'API)
                    if legal.get('dirigeants'):
                        financial_data['directors'] = legal.get('dirigeants', [])
                    elif legal.get('representants'):
                        financial_data['directors'] = legal.get('representants', [])
                
                # Informations financières (si disponibles)
                if sirene_data.get('bilans'):
                    financial_data['financial_info'] = {
                        'bilans': sirene_data.get('bilans', []),
                        'chiffre_affaires': self._extract_ca_from_bilans(sirene_data.get('bilans', []))
                    }
        except Exception as e:
            financial_data['sirene_error'] = str(e)
        
        # 2. Recherche sur d'autres sources publiques (Pappers, Societe.com via scraping)
        if progress_callback:
            progress_callback('Recherche sur les registres publics...')
        
        try:
            public_data = self._search_public_registers(company_name, domain)
            if public_data:
                financial_data['public_registers'] = public_data
        except Exception as e:
            financial_data['public_registers_error'] = str(e)
        
        # Résumé
        financial_data['summary'] = {
            'has_sirene_data': bool(financial_data.get('sirene_data')),
            'has_legal_info': bool(financial_data.get('legal_info')),
            'has_financial_info': bool(financial_data.get('financial_info')),
            'directors_count': len(financial_data.get('directors', []))
        }
        
        return financial_data
    
    def _search_sirene_api(self, company_name: str, domain: str = None) -> Optional[Dict]:
        """
        Recherche dans l'API Sirene (data.gouv.fr)
        Utilise l'API publique de recherche d'entreprises
        """
        try:
            # Nettoyer le nom de l'entreprise
            clean_name = company_name.strip()
            
            # API Sirene - utiliser l'URL depuis la config
            url = SIRENE_API_URL
            params = {
                'q': clean_name,
                'per_page': 5
            }
            headers = {
                'Accept': 'application/json',
                'User-Agent': self.headers['User-Agent']
            }
            
            # Ajouter la clé API si disponible
            if SIRENE_API_KEY:
                headers['Authorization'] = f'Bearer {SIRENE_API_KEY}'
                # Ou selon le format de l'API
                params['token'] = SIRENE_API_KEY
            
            # Utiliser le timeout depuis la config
            response = requests.get(url, params=params, headers=headers, timeout=OSINT_TOOL_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    # Prendre le premier résultat (le plus pertinent)
                    result = data['results'][0]
                    return {
                        'uniteLegale': result,
                        'total_results': data.get('total_results', 0)
                    }
            
        except Exception as e:
            # Si l'API ne fonctionne pas, on continue sans erreur
            # L'API peut nécessiter une clé API ou avoir des limitations
            pass
        
        return None
    
    def _format_sirene_address(self, address_data: Dict) -> str:
        """Formate l'adresse depuis les données Sirene"""
        if not address_data:
            return ''
        
        parts = []
        # Format nouveau API
        if address_data.get('numero_voie'):
            parts.append(address_data['numero_voie'])
        if address_data.get('type_voie'):
            parts.append(address_data['type_voie'])
        if address_data.get('libelle_voie'):
            parts.append(address_data['libelle_voie'])
        if address_data.get('code_postal'):
            parts.append(address_data['code_postal'])
        if address_data.get('ville'):
            parts.append(address_data['ville'])
        
        # Format ancien API (fallback)
        if not parts:
            if address_data.get('numeroVoieEtablissement'):
                parts.append(address_data['numeroVoieEtablissement'])
            if address_data.get('typeVoieEtablissement'):
                parts.append(address_data['typeVoieEtablissement'])
            if address_data.get('libelleVoieEtablissement'):
                parts.append(address_data['libelleVoieEtablissement'])
            if address_data.get('codePostalEtablissement'):
                parts.append(address_data['codePostalEtablissement'])
            if address_data.get('libelleCommuneEtablissement'):
                parts.append(address_data['libelleCommuneEtablissement'])
        
        return ', '.join(filter(None, parts))
    
    def _extract_ca_from_bilans(self, bilans: List[Dict]) -> Optional[float]:
        """Extrait le chiffre d'affaires depuis les bilans"""
        if not bilans:
            return None
        
        # Prendre le dernier bilan disponible
        dernier_bilan = bilans[-1] if bilans else {}
        
        # Le CA peut être dans différents champs selon le format
        ca_fields = ['chiffreAffaires', 'ca', 'chiffre_affaires', 'CA']
        for field in ca_fields:
            if field in dernier_bilan:
                return dernier_bilan[field]
        
        return None
    
    def _search_public_registers(self, company_name: str, domain: str = None) -> Optional[Dict]:
        """
        Recherche sur les registres publics (Pappers, Societe.com, etc.)
        Via scraping (à utiliser avec précaution et respect des CGU)
        """
        public_data = {}
        
        # Note: Le scraping de sites tiers nécessite une autorisation
        # Ici, on fait une recherche basique via leur API publique si disponible
        
        # Pour l'instant, on retourne None car ces sites nécessitent souvent
        # une API payante ou une autorisation spécifique
        # On pourrait utiliser des outils comme Scrapy ou BeautifulSoup
        # mais cela nécessiterait de respecter les robots.txt et CGU
        
        return None
    
    def analyze_ssl(self, domain: str) -> Dict:
        """Analyse SSL/TLS avec sslscan"""
        ssl_info = {}
        
        if not self.tools['sslscan']:
            return {'error': 'sslscan non disponible'}
        
        result = self._run_wsl_command(['sslscan', domain], timeout=30)
        
        if result.get('success'):
            output = result['stdout']
            # Parser les résultats sslscan
            if 'SSLv2' in output:
                ssl_info['ssl_v2'] = 'Désactivé' if 'disabled' in output.lower() else 'Activé'
            if 'SSLv3' in output:
                ssl_info['ssl_v3'] = 'Désactivé' if 'disabled' in output.lower() else 'Activé'
            if 'TLS 1.0' in output:
                ssl_info['tls_1_0'] = 'Désactivé' if 'disabled' in output.lower() else 'Activé'
            if 'TLS 1.1' in output:
                ssl_info['tls_1_1'] = 'Désactivé' if 'disabled' in output.lower() else 'Activé'
            if 'TLS 1.2' in output:
                ssl_info['tls_1_2'] = 'Activé' if 'enabled' in output.lower() else 'Désactivé'
            if 'TLS 1.3' in output:
                ssl_info['tls_1_3'] = 'Activé' if 'enabled' in output.lower() else 'Désactivé'
            
            # Certificat
            cert_match = re.search(r'Subject:\s*(.+)', output)
            if cert_match:
                ssl_info['certificate_subject'] = cert_match.group(1)
        
        return ssl_info
    
    def detect_technologies(self, url: str) -> Dict:
        """Détecte les technologies avec WhatWeb"""
        tech_info = {}
        
        if not self.tools['whatweb']:
            return {'error': 'whatweb non disponible'}
        
        result = self._run_wsl_command(['whatweb', '--no-errors', url], timeout=30)
        
        if result.get('success'):
            output = result['stdout']
            # Nettoyer les codes ANSI
            clean_output = self._clean_ansi_codes(output)
            # Parser les résultats whatweb
            tech_info['raw_output'] = clean_output
            # Extraire les technologies détectées
            if 'WordPress' in output:
                tech_info['cms'] = 'WordPress'
            if 'Drupal' in output:
                tech_info['cms'] = 'Drupal'
            if 'Joomla' in output:
                tech_info['cms'] = 'Joomla'
            if 'Apache' in output:
                tech_info['server'] = 'Apache'
            if 'nginx' in output.lower():
                tech_info['server'] = 'Nginx'
            if 'PHP' in output:
                tech_info['language'] = 'PHP'
        
        return tech_info
    
    def enrich_people_from_scrapers(self, people_list: List[Dict], domain: str, progress_callback=None) -> List[Dict]:
        """
        Enrichit les personnes trouvées par les scrapers avec des données OSINT
        
        Args:
            people_list: Liste des personnes trouvées par les scrapers
            domain: Domaine de l'entreprise
            progress_callback: Callback pour la progression
        
        Returns:
            List[Dict]: Liste des personnes enrichies
        """
        enriched_people = []
        
        for person in people_list:
            enriched_person = person.copy()
            
            # Extraire le nom complet
            name = person.get('name', '')
            if not name:
                continue
            
            # Rechercher sur LinkedIn si on a un nom
            if progress_callback:
                progress_callback(f'Recherche OSINT pour {name}...')
            
            # Rechercher le profil LinkedIn
            linkedin_url = person.get('linkedin_url')
            if not linkedin_url and name:
                # Essayer de trouver le profil LinkedIn
                try:
                    linkedin_results = self.search_linkedin_people(domain, progress_callback=None)
                    for linkedin_person in linkedin_results:
                        if name.lower() in linkedin_person.get('name', '').lower():
                            linkedin_url = linkedin_person.get('linkedin_url')
                            if not enriched_person.get('title'):
                                enriched_person['title'] = linkedin_person.get('title', '')
                            break
                except:
                    pass
            
            enriched_person['linkedin_url'] = linkedin_url
            
            # Rechercher les profils sociaux
            email = person.get('email', '')
            if email:
                username = email.split('@')[0]
                try:
                    social_profiles = self.search_social_media_profiles([username], progress_callback=None)
                    if username in social_profiles:
                        enriched_person['social_profiles'] = social_profiles[username]
                except:
                    pass
            
            # Déterminer le niveau hiérarchique basé sur le titre
            title = enriched_person.get('title', '').lower()
            niveau_hierarchique = None
            role = None
            
            if any(keyword in title for keyword in ['ceo', 'pdg', 'directeur général', 'président', 'founder']):
                niveau_hierarchique = 1
                role = 'Direction'
            elif any(keyword in title for keyword in ['directeur', 'directrice', 'director', 'head of']):
                niveau_hierarchique = 2
                role = 'Direction'
            elif any(keyword in title for keyword in ['manager', 'responsable', 'chef de', 'lead']):
                niveau_hierarchique = 3
                role = 'Management'
            elif any(keyword in title for keyword in ['senior', 'senior', 'expert']):
                niveau_hierarchique = 4
                role = 'Expert'
            else:
                niveau_hierarchique = 5
                role = 'Collaborateur'
            
            enriched_person['niveau_hierarchique'] = niveau_hierarchique
            enriched_person['role'] = role
            enriched_person['osint_enriched'] = True
            
            enriched_people.append(enriched_person)
        
        return enriched_people
    
    def analyze_osint(self, url: str, progress_callback=None, people_from_scrapers=None) -> Dict:
        """
        Analyse OSINT complète d'un domaine/URL
        Retourne toutes les informations collectées
        
        Args:
            url: URL à analyser
            progress_callback: Callback pour la progression
            people_from_scrapers: Liste des personnes trouvées par les scrapers (optionnel)
        """
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        domain = domain.replace('www.', '')
        
        results = {
            'domain': domain,
            'url': url,
            'subdomains': [],
            'dns_records': {},
            'whois_info': {},
            'emails': [],
            'people': {},
            'financial_data': {},
            'ssl_info': {},
            'technologies': {},
            'ip_info': {},
            'summary': {}
        }
        
        # Découverte de sous-domaines
        try:
            if progress_callback:
                progress_callback('Démarrage de la découverte de sous-domaines...')
            results['subdomains'] = self.discover_subdomains(domain, progress_callback)
        except Exception as e:
            results['subdomains_error'] = str(e)
            if progress_callback:
                progress_callback(f'Erreur lors de la découverte de sous-domaines: {str(e)}')
        
        # Enregistrements DNS
        if progress_callback:
            progress_callback('Récupération des enregistrements DNS...')
        try:
            results['dns_records'] = self.get_dns_records(domain)
        except Exception as e:
            results['dns_error'] = str(e)
        
        # Informations WHOIS
        if progress_callback:
            progress_callback('Récupération des informations WHOIS...')
        try:
            results['whois_info'] = self.get_whois_info(domain)
        except Exception as e:
            results['whois_error'] = str(e)
        
        # Emails
        if progress_callback:
            progress_callback('Collecte d\'emails...')
        try:
            results['emails'] = self.harvest_emails(domain, progress_callback)
        except Exception as e:
            results['emails_error'] = str(e)
        
        # Recherche de personnes et profils sociaux
        if progress_callback:
            progress_callback('Recherche de personnes liées à l\'entreprise...')
        try:
            people_data = self.search_people_osint(domain, results['emails'], progress_callback)
            results['people'] = people_data
        except Exception as e:
            results['people_error'] = str(e)
            results['people'] = {}
        
        # Recherche de données financières et juridiques
        # Extraire le nom de l'entreprise depuis le domaine ou WHOIS
        company_name = domain.split('.')[0].capitalize()
        if results.get('whois_info', {}).get('org'):
            company_name = results['whois_info']['org']
        
        if progress_callback:
            progress_callback('Recherche des données financières et juridiques...')
        try:
            financial_data = self.search_company_financial_data(company_name, domain, progress_callback)
            results['financial_data'] = financial_data
        except Exception as e:
            results['financial_data_error'] = str(e)
            results['financial_data'] = {}
        
        # Analyse SSL
        if progress_callback:
            progress_callback('Analyse SSL/TLS...')
        try:
            results['ssl_info'] = self.analyze_ssl(domain)
        except Exception as e:
            results['ssl_error'] = str(e)
        
        # Technologies
        if progress_callback:
            progress_callback('Détection des technologies...')
        try:
            results['technologies'] = self.detect_technologies(url)
        except Exception as e:
            results['tech_error'] = str(e)
        
        # Informations IP
        if progress_callback:
            progress_callback('Récupération des informations IP...')
        try:
            ip = socket.gethostbyname(domain)
            results['ip_info'] = {
                'ip': ip,
                'hostname': socket.gethostbyaddr(ip)[0] if ip else None
            }
        except Exception as e:
            results['ip_error'] = str(e)
        
        # Résumé
        people_count = results.get('people', {}).get('summary', {}).get('total_people', 0)
        results['summary'] = {
            'subdomains_count': len(results['subdomains']),
            'emails_count': len(results['emails']),
            'people_count': people_count,
            'dns_records_count': sum(len(v) for v in results['dns_records'].values() if isinstance(v, list)),
            'tools_used': [k for k, v in self.tools.items() if v]
        }
        
        return results
