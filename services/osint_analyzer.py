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
import logging
from urllib.parse import urlparse
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Importer la configuration
try:
    from config import (
        SIRENE_API_KEY,
        SIRENE_API_URL,
        WSL_DISTRO,
        WSL_USER,
        OSINT_TOOL_TIMEOUT,
        PHONE_DEFAULT_REGION,
        PHONE_OSINT_MAX_NUMBERS,
    )
except ImportError:
    # Valeurs par défaut si config n'est pas disponible
    SIRENE_API_KEY = os.environ.get('SIRENE_API_KEY', '')
    SIRENE_API_URL = os.environ.get('SIRENE_API_URL', 'https://recherche-entreprises.api.gouv.fr/search')
    WSL_DISTRO = os.environ.get('WSL_DISTRO', 'kali-linux')
    WSL_USER = os.environ.get('WSL_USER', 'loupix')
    OSINT_TOOL_TIMEOUT = int(os.environ.get('OSINT_TOOL_TIMEOUT', '60'))
    PHONE_DEFAULT_REGION = os.environ.get('PHONE_DEFAULT_REGION', 'FR')
    PHONE_OSINT_MAX_NUMBERS = int(os.environ.get('PHONE_OSINT_MAX_NUMBERS', '8'))

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
            # Reconnaissance de domaines
            'dnsrecon': self._check_tool('dnsrecon'),
            'theharvester': self._check_tool('theharvester'),
            'sublist3r': self._check_tool('sublist3r'),
            'amass': self._check_tool('amass'),
            'subfinder': self._check_tool('subfinder'),
            'findomain': self._check_tool('findomain'),
            'dnsenum': self._check_tool('dnsenum'),
            'fierce': self._check_tool('fierce'),
            # Analyse web
            'whatweb': self._check_tool('whatweb'),
            'sslscan': self._check_tool('sslscan'),
            'testssl': self._check_tool('testssl.sh'),
            'wafw00f': self._check_tool('wafw00f'),
            'nikto': self._check_tool('nikto'),
            'gobuster': self._check_tool('gobuster'),
            # Recherche de personnes
            'sherlock': self._check_tool('sherlock'),
            'maigret': self._check_tool('maigret'),
            'phoneinfoga': self._check_tool('phoneinfoga'),
            'holehe': self._check_tool('holehe'),
            # Métadonnées
            'metagoofil': self._check_tool('metagoofil'),
            'exiftool': self._check_tool('exiftool'),
            # Frameworks OSINT
            'recon-ng': self._check_tool('recon-ng'),
            # APIs CLI
            'shodan': self._check_tool('shodan'),
            'censys': self._check_tool('censys'),
            'social_analyzer': self._check_social_analyzer(),
        }
    
    def _check_social_analyzer(self) -> bool:
        """Vérifie si Social Analyzer est disponible (python3 -m social-analyzer)."""
        for cmd in (['python3', '-m', 'social-analyzer', '--help'], ['python', '-m', 'social-analyzer', '--help']):
            try:
                if self.wsl_available:
                    r = subprocess.run(
                        self.wsl_cmd_base + cmd,
                        capture_output=True,
                        text=True,
                        timeout=8,
                    )
                else:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if r.returncode == 0 or 'username' in (r.stdout or '') + (r.stderr or ''):
                    return True
            except Exception:
                pass
        return False
    
    def get_diagnostic(self) -> Dict:
        """
        Retourne un résumé de l'environnement OSINT (WSL + outils) pour expliquer
        pourquoi une analyse peut échouer ou être partielle.
        
        Returns:
            dict: wsl_available, wsl_distro, wsl_user, tools_available (liste),
                  tools_missing (liste), message (explicatif)
        """
        try:
            from config import WSL_DISTRO, WSL_USER
        except ImportError:
            WSL_DISTRO = os.environ.get('WSL_DISTRO', 'kali-linux')
            WSL_USER = os.environ.get('WSL_USER', 'loupix')
        available = [k for k, v in self.tools.items() if v]
        missing = [k for k, v in self.tools.items() if not v]
        # En prod (Linux) : pas de WSL, les outils sont exécutés en natif (shutil.which)
        if not self.wsl_available:
            if len(available) == 0:
                message = (
                    'Exécution native (pas de WSL). Aucun outil OSINT détecté sur le système. '
                    'Installez-les (apt, pip, scripts dans docs/INSTALL_OSINT_TOOLS.md).'
                )
            else:
                message = f'Exécution native (pas de WSL). {len(available)} outil(s) disponible(s), {len(missing)} manquant(s).'
        elif len(available) == 0:
            message = (
                'Aucun outil OSINT détecté dans WSL. Exécutez le script d\'installation dans votre '
                f'distro WSL: wsl -d {WSL_DISTRO} bash scripts/linux/install_osint_tools_kali.sh'
            )
        else:
            message = f'{len(available)} outil(s) disponible(s), {len(missing)} manquant(s).'
        return {
            'wsl_available': self.wsl_available,
            'execution_mode': 'wsl' if self.wsl_available else 'native',
            'wsl_distro': WSL_DISTRO,
            'wsl_user': WSL_USER,
            'tools_available': available,
            'tools_missing': missing,
            'message': message,
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
    
    def _run_osint_cli(self, command: List[str], timeout: int = 30) -> Dict:
        """
        Exécute un outil CLI OSINT : WSL si disponible (Windows), sinon processus natif (Linux worker).
        """
        if not command:
            return {'error': 'Commande vide'}
        if self.wsl_available:
            return self._run_wsl_command(command, timeout=timeout)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=timeout,
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout or '',
                'stderr': result.stderr or '',
                'returncode': result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {'error': 'Timeout'}
        except Exception as e:
            return {'error': str(e)}
    
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
    
    def harvest_emails(self, domain: str, progress_callback=None, names: List[Dict] = None) -> List[str]:
        """
        Récupère des emails liés au domaine avec TheHarvester
        Optimisé avec les noms de personnes si disponibles
        
        Args:
            domain: Domaine à analyser
            progress_callback: Callback pour la progression
            names: Liste de dictionnaires avec first_name, last_name, full_name (optionnel)
        
        Returns:
            Liste d'emails trouvés
        """
        emails = set()
        
        if not self.tools['theharvester']:
            return []
        
        # Si on a des noms, utiliser une recherche plus ciblée et rapide
        if names and len(names) > 0:
            # Utiliser seulement les sources les plus rapides et efficaces avec les noms
            sources = ['google', 'bing']  # Sources rapides pour recherche avec noms
            
            for name_data in names[:5]:  # Limiter à 5 noms pour éviter trop de requêtes
                first_name = name_data.get('first_name', '')
                last_name = name_data.get('last_name', '')
                full_name = name_data.get('full_name', f'{first_name} {last_name}'.strip())
                
                if not first_name or not last_name:
                    continue
                
                for source in sources:
                    if progress_callback:
                        progress_callback(f'Recherche d\'emails pour {full_name} via {source}...')
                    
                    # Recherche ciblée avec le nom complet
                    result = self._run_wsl_command([
                        'theHarvester',
                        '-d', domain,
                        '-b', source,
                        '-l', '50',  # Réduire le nombre de résultats pour aller plus vite
                        '-s', '0'  # Start à 0
                    ], timeout=30)  # Réduire le timeout
                    
                    if result.get('success'):
                        for line in result['stdout'].split('\n'):
                            # Vérifier si le nom apparaît dans la ligne (recherche ciblée)
                            if first_name.lower() in line.lower() or last_name.lower() in line.lower():
                                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                                found_emails = re.findall(email_pattern, line)
                                for email in found_emails:
                                    if domain in email:
                                        emails.add(email.lower())
        else:
            # Recherche générique sans noms (plus lente)
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
        Retourne une liste de personnes avec leurs informations (filtrées pour ne garder que les noms valides)
        """
        from services.name_validator import is_valid_human_name
        
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
            
            person_name = ' '.join(name_parts) if name_parts else local_part
            
            # Filtrer les noms invalides (lieux, entreprises, fonctions, etc.)
            if not person_name or not is_valid_human_name(person_name):
                continue
            
            person = {
                'email': email,
                'name': person_name,
                'username': local_part,
                'domain': domain
            }
            
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
    
    def _run_social_analyzer(self, username: str, timeout: int = 90) -> Dict:
        """Exécute Social Analyzer pour un pseudo (WSL ou local). Retourne le résultat subprocess."""
        if self.wsl_available:
            return self._run_wsl_command(
                ['python3', '-m', 'social-analyzer', '--username', username, '--output', 'json'],
                timeout=timeout
            )
        try:
            r = subprocess.run(
                ['python', '-m', 'social-analyzer', '--username', username, '--output', 'json'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=timeout,
            )
            return {
                'success': r.returncode == 0,
                'stdout': r.stdout,
                'stderr': r.stderr,
                'returncode': r.returncode,
            }
        except Exception as e:
            return {'error': str(e)}
    
    def search_social_media_profiles(self, usernames: List[str], progress_callback=None) -> Dict[str, List[Dict]]:
        """
        Recherche des profils sur les réseaux sociaux pour une liste d'utilisateurs
        Utilise Social Analyzer, Maigret ou Sherlock si disponibles
        """
        profiles = {}
        
        # Social Analyzer (1000+ sites, priorité si disponible)
        if self.tools.get('social_analyzer'):
            for username in usernames[:5]:
                if progress_callback:
                    progress_callback(f'Recherche de profils pour {username} (Social Analyzer)...')
                result = self._run_social_analyzer(username, timeout=90)
                if result.get('success') and result.get('stdout'):
                    try:
                        data = json.loads(result['stdout'])
                        found_profiles = []
                        if isinstance(data, list):
                            for item in data:
                                if not isinstance(item, dict):
                                    continue
                                url = item.get('url') or item.get('link') or item.get('profile_url')
                                if url and item.get('found', True):
                                    found_profiles.append({'url': url, 'source': 'social_analyzer'})
                        elif isinstance(data, dict):
                            for key, val in data.items():
                                if isinstance(val, dict) and (val.get('url') or val.get('link')):
                                    found_profiles.append({
                                        'url': val.get('url') or val.get('link'),
                                        'source': 'social_analyzer'
                                    })
                        if found_profiles:
                            profiles[username] = found_profiles
                    except (json.JSONDecodeError, TypeError):
                        for url_match in re.finditer(r'https?://[^\s"\'<>]+', result['stdout']):
                            if username not in profiles:
                                profiles[username] = []
                            profiles[username].append({'url': url_match.group(0), 'source': 'social_analyzer'})
        
        # Maigret (si pas déjà rempli par Social Analyzer ou en complément)
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
                        existing = profiles.get(username, [])
                        existing.extend(found_profiles)
                        profiles[username] = existing
        
        # Sherlock (en complément)
        if self.tools['sherlock']:
            for username in usernames[:5]:
                if progress_callback:
                    progress_callback(f'Recherche de profils pour {username} (Sherlock)...')
                
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
                        existing = profiles.get(username, [])
                        existing.extend(found_profiles)
                        profiles[username] = existing
        
        return profiles
    
    def _phone_libphonenumber_meta(self, raw_phone: str) -> Dict:
        """Métadonnées localement dérivées (pas d'appel réseau) via la lib Google libphonenumber."""
        try:
            import phonenumbers
            from phonenumbers import geocoder, carrier
            from phonenumbers.phonenumberutil import NumberParseException
        except ImportError:
            return {}
        try:
            num = phonenumbers.parse(raw_phone, PHONE_DEFAULT_REGION)
        except NumberParseException:
            return {'valid': False, 'libphonenumber_parse_ok': False}
        nt = phonenumbers.number_type(num)
        labels = {
            phonenumbers.PhoneNumberType.FIXED_LINE: 'FIXED_LINE',
            phonenumbers.PhoneNumberType.MOBILE: 'MOBILE',
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: 'FIXED_LINE_OR_MOBILE',
            phonenumbers.PhoneNumberType.TOLL_FREE: 'TOLL_FREE',
            phonenumbers.PhoneNumberType.PREMIUM_RATE: 'PREMIUM_RATE',
            phonenumbers.PhoneNumberType.SHARED_COST: 'SHARED_COST',
            phonenumbers.PhoneNumberType.VOIP: 'VOIP',
            phonenumbers.PhoneNumberType.PERSONAL_NUMBER: 'PERSONAL_NUMBER',
            phonenumbers.PhoneNumberType.PAGER: 'PAGER',
            phonenumbers.PhoneNumberType.UAN: 'UAN',
            phonenumbers.PhoneNumberType.VOICEMAIL: 'VOICEMAIL',
            phonenumbers.PhoneNumberType.UNKNOWN: 'UNKNOWN',
        }
        line_label = labels.get(nt, str(nt))
        carrier_name = carrier.name_for_number(num, 'fr') or carrier.name_for_number(num, 'en')
        loc = geocoder.description_for_number(num, 'fr') or geocoder.description_for_number(num, 'en')
        return {
            'valid': phonenumbers.is_valid_number(num),
            'possible': phonenumbers.is_possible_number(num),
            'e164': phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164),
            'country_calling_code': num.country_code,
            'location': loc or None,
            'line_type': line_label,
            'carrier': carrier_name or None,
            'sources': ['libphonenumber'],
            'libphonenumber_parse_ok': True,
        }
    
    def _run_phoneinfoga_scan(self, phone: str) -> Optional[Dict]:
        """Exécute PhoneInfoga v2 (`scan -n`) ou ancienne CLI (`--number`) sur WSL ou Linux natif."""
        if not self.tools.get('phoneinfoga'):
            return None
        timeout = max(OSINT_TOOL_TIMEOUT, 45)
        last_text = ''
        for cmd in (
            ['phoneinfoga', 'scan', '-n', phone],
            ['phoneinfoga', 'scan', '--number', phone],
        ):
            result = self._run_osint_cli(cmd, timeout=timeout)
            out = (result.get('stdout') or '').strip()
            if not out:
                out = (result.get('stderr') or '').strip()
            if not out:
                continue
            last_text = self._clean_ansi_codes(out)
            text = last_text
            try:
                if text.lstrip().startswith('{'):
                    data = json.loads(text)
                    if isinstance(data, dict):
                        data.setdefault('sources', [])
                        if 'phoneinfoga' not in data['sources']:
                            data['sources'].append('phoneinfoga')
                        return data
            except json.JSONDecodeError:
                pass
            m = re.search(r'\{[\s\S]{2,120000}\}', text)
            if m:
                try:
                    data = json.loads(m.group(0))
                    if isinstance(data, dict):
                        data.setdefault('sources', [])
                        if 'phoneinfoga' not in data['sources']:
                            data['sources'].append('phoneinfoga')
                        return data
                except json.JSONDecodeError:
                    pass
            parsed: Dict = {'raw_output': text[:12000], 'sources': ['phoneinfoga']}
            if 'Carrier:' in text:
                cm = re.search(r'Carrier:\s*([^\n]+)', text)
                if cm:
                    parsed['carrier'] = cm.group(1).strip()
            if 'Location:' in text:
                lm = re.search(r'Location:\s*([^\n]+)', text)
                if lm:
                    parsed['location'] = lm.group(1).strip()
            return parsed
        return None

    def _fetch_phone_external_apis(self, phone: str, libmeta: Optional[Dict] = None) -> Dict:
        """Numverify (APILayer) et Abstract Phone — optionnels, clés dans .env."""
        out: Dict = {}
        try:
            from config import NUMVERIFY_API_KEY, ABSTRACT_PHONE_API_KEY
        except ImportError:
            NUMVERIFY_API_KEY = os.environ.get('NUMVERIFY_API_KEY', '')
            ABSTRACT_PHONE_API_KEY = os.environ.get('ABSTRACT_PHONE_API_KEY', '')

        dial = phone
        if libmeta and libmeta.get('e164'):
            dial = libmeta['e164']

        if NUMVERIFY_API_KEY:
            try:
                r = requests.get(
                    'https://apilayer.net/api/validate',
                    params={'access_key': NUMVERIFY_API_KEY, 'number': dial},
                    timeout=12,
                )
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, dict):
                        if j.get('success') is False:
                            err = j.get('error') or {}
                            out['numverify_error'] = str(err.get('info') or err.get('type') or err)[:200]
                        else:
                            out['numverify'] = {
                                'valid': j.get('valid'),
                                'number': j.get('number'),
                                'local_format': j.get('local_format'),
                                'international_format': j.get('international_format'),
                                'country_prefix': j.get('country_prefix'),
                                'country_code': j.get('country_code'),
                                'country_name': j.get('country_name'),
                                'location': j.get('location'),
                                'carrier': j.get('carrier'),
                                'line_type': j.get('line_type'),
                                'sources': ['numverify'],
                            }
            except Exception as e:
                out['numverify_error'] = str(e)[:200]

        if ABSTRACT_PHONE_API_KEY:
            try:
                r = requests.get(
                    'https://phonevalidation.abstractapi.com/v1/',
                    params={'api_key': ABSTRACT_PHONE_API_KEY, 'phone': dial},
                    timeout=12,
                )
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, dict):
                        country = j.get('country')
                        if isinstance(country, dict):
                            country_name = country.get('name')
                        else:
                            country_name = country
                        fmt = j.get('format')
                        if isinstance(fmt, dict):
                            intl_fmt = fmt.get('international')
                        else:
                            intl_fmt = fmt
                        out['abstract_phone'] = {
                            'is_valid': j.get('is_valid'),
                            'country': country_name,
                            'carrier': j.get('carrier'),
                            'line_type': j.get('type') or j.get('line_type'),
                            'location': j.get('location'),
                            'format': intl_fmt,
                            'sources': ['abstractapi.com'],
                        }
            except Exception as e:
                out['abstract_phone_error'] = str(e)[:200]

        return out
    
    def analyze_phones_osint(self, phones: List[str], progress_callback=None) -> Dict:
        """
        Analyse OSINT des numéros : libphonenumber, APIs optionnelles (Numverify, Abstract),
        PhoneInfoga si installé, recherche web légère.
        """
        phone_data = {}
        max_n = max(1, min(PHONE_OSINT_MAX_NUMBERS, 20))
        
        for phone in phones[:max_n]:
            if progress_callback:
                progress_callback(f'Analyse OSINT du téléphone {phone}...')
            
            phone_info: Dict = {
                'phone': phone,
                'carrier': None,
                'location': None,
                'line_type': None,
                'valid': None,
                'social_profiles': [],
                'data_breaches': [],
                'sources': [],
            }
            
            libmeta = self._phone_libphonenumber_meta(phone)
            phone_info['libphonenumber'] = libmeta
            if libmeta:
                if libmeta.get('carrier'):
                    phone_info['carrier'] = libmeta['carrier']
                if libmeta.get('location'):
                    phone_info['location'] = libmeta['location']
                if libmeta.get('line_type'):
                    phone_info['line_type'] = libmeta['line_type']
                if libmeta.get('valid') is not None:
                    phone_info['valid'] = libmeta['valid']
                for s in libmeta.get('sources') or []:
                    if s and s not in phone_info['sources']:
                        phone_info['sources'].append(s)

            try:
                ext = self._fetch_phone_external_apis(phone, libmeta or None)
                if ext.get('numverify'):
                    nv = ext['numverify']
                    phone_info['numverify'] = nv
                    if nv.get('carrier') and not phone_info.get('carrier'):
                        phone_info['carrier'] = nv['carrier']
                    if nv.get('location') and not phone_info.get('location'):
                        phone_info['location'] = nv['location']
                    if nv.get('line_type') and not phone_info.get('line_type'):
                        phone_info['line_type'] = nv['line_type']
                    if nv.get('valid') is not None and phone_info.get('valid') is None:
                        phone_info['valid'] = nv['valid']
                    if 'numverify' not in phone_info['sources']:
                        phone_info['sources'].append('numverify')
                if ext.get('numverify_error'):
                    phone_info['numverify_error'] = ext['numverify_error']
                if ext.get('abstract_phone'):
                    ap = ext['abstract_phone']
                    phone_info['abstract_phone'] = ap
                    if ap.get('carrier') and not phone_info.get('carrier'):
                        phone_info['carrier'] = ap['carrier']
                    if ap.get('location') and not phone_info.get('location'):
                        phone_info['location'] = ap['location']
                    if ap.get('line_type') and not phone_info.get('line_type'):
                        phone_info['line_type'] = ap['line_type']
                    if 'abstractapi.com' not in str(phone_info['sources']):
                        phone_info['sources'].append('abstract_phone')
                if ext.get('abstract_phone_error'):
                    phone_info['abstract_phone_error'] = ext['abstract_phone_error']
            except Exception as e:
                logger.debug(f'APIs téléphone externes pour {phone}: {e}')
            
            try:
                pi = self._run_phoneinfoga_scan(phone)
                if pi:
                    phone_info['phoneinfoga'] = pi
                    if pi.get('carrier'):
                        phone_info['carrier'] = pi['carrier']
                    if pi.get('location'):
                        phone_info['location'] = pi['location']
                    if pi.get('line_type'):
                        phone_info['line_type'] = pi['line_type']
                    if pi.get('valid') is not None:
                        phone_info['valid'] = pi['valid']
                    if 'phoneinfoga' not in phone_info['sources']:
                        phone_info['sources'].append('phoneinfoga')
            except Exception as e:
                logger.debug(f'Erreur PhoneInfoga pour {phone}: {e}')
            
            try:
                search_results = self._search_phone_online(phone)
                if search_results:
                    phone_info.update(search_results)
                    if search_results.get('web_mentions') is not None and 'duckduckgo_html' not in phone_info['sources']:
                        phone_info['sources'].append('duckduckgo_html')
            except Exception as e:
                logger.debug(f'Erreur recherche web pour {phone}: {e}')
            
            phone_data[phone] = phone_info
        
        return phone_data
    
    def _search_phone_online(self, phone: str) -> Dict:
        """
        Recherche basique d'un téléphone en ligne
        Utilise des moteurs de recherche publics
        """
        results = {}
        
        try:
            clean_phone = re.sub(r'[^\d+]', '', phone)
            search_query = f'"{clean_phone}"'
            search_url = f'https://html.duckduckgo.com/html/?q={search_query}'
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results['web_mentions'] = len(soup.find_all('a', href=True))
        except Exception as e:
            logger.debug(f'Erreur recherche web téléphone: {e}')
        
        return results
    
    def analyze_people_osint(self, people: List[Dict], domain: str, progress_callback=None) -> Dict:
        """
        Analyse OSINT approfondie sur les personnes
        Recherche famille, localisation, historique, photos, hobbies, etc.
        
        Args:
            people: Liste des personnes à analyser (dict avec name, email, etc.)
            domain: Domaine de l'entreprise
            progress_callback: Callback pour la progression
        
        Returns:
            Dictionnaire avec les informations enrichies pour chaque personne
        """
        from services.name_validator import is_valid_human_name
        
        enriched_people = {}
        
        # Filtrer les personnes avec des noms invalides avant l'analyse
        valid_people = [
            person for person in people
            if person.get('name') and is_valid_human_name(person.get('name', ''))
        ]
        
        for person in valid_people[:5]:  # Limiter à 5
            person_name = person.get('name', '')
            person_email = person.get('email', '')
            person_linkedin = person.get('linkedin_url', '')
            
            if progress_callback:
                progress_callback(f'Analyse OSINT approfondie pour {person_name}...')
            
            person_data = {
                'original': person,
                'location': None,
                'location_city': None,
                'location_country': None,
                'location_address': None,
                'location_latitude': None,
                'location_longitude': None,
                'age_range': None,
                'birth_date': None,
                'family_members': [],
                'social_profiles': {},
                'data_breaches': [],
                'professional_history': [],
                'addresses': [],
                'photos': [],
                'hobbies': [],
                'interests': [],
                'education': None,
                'bio': None,
                'languages': [],
                'skills': [],
                'certifications': [],
                'sources': []
            }
            
            # Recherche via Holehe pour les emails (comptes sur différents sites)
            if person_email and self.tools.get('holehe'):
                try:
                    if progress_callback:
                        progress_callback(f'Recherche de comptes pour {person_email}...')
                    result = self._run_wsl_command([
                        'holehe',
                        person_email,
                        '--only-used'
                    ], timeout=30)
                    
                    if result.get('success'):
                        output = result['stdout']
                        accounts = []
                        for line in output.split('\n'):
                            if '[' in line and ']' in line:
                                site_match = re.search(r'\[\*\]\s*([^\s]+)', line)
                                if site_match:
                                    accounts.append(site_match.group(1).strip())
                        
                        if accounts:
                            person_data['social_profiles']['holehe'] = accounts
                            person_data['sources'].append('holehe')
                except Exception as e:
                    logger.debug(f'Erreur Holehe pour {person_email}: {e}')
            
            # Recherche de photos
            if person_name or person_email:
                try:
                    if progress_callback:
                        progress_callback(f'Recherche de photos pour {person_name}...')
                    photos = self._search_person_photos(person_name, person_email, domain)
                    if photos:
                        person_data['photos'] = photos
                        person_data['sources'].append('photo_search')
                except Exception as e:
                    logger.debug(f'Erreur recherche photos: {e}')
            
            # Recherche de localisation
            if person_name:
                try:
                    if progress_callback:
                        progress_callback(f'Recherche de localisation pour {person_name}...')
                    location_info = self._search_person_location(person_name, domain)
                    if location_info:
                        person_data.update(location_info)
                        person_data['sources'].append('location_search')
                except Exception as e:
                    logger.debug(f'Erreur recherche localisation: {e}')
            
            # Recherche de hobbies et intérêts
            if person_name or person_linkedin:
                try:
                    if progress_callback:
                        progress_callback(f'Recherche de hobbies pour {person_name}...')
                    hobbies_info = self._search_person_hobbies(person_name, person_linkedin)
                    if hobbies_info:
                        person_data['hobbies'] = hobbies_info.get('hobbies', [])
                        person_data['interests'] = hobbies_info.get('interests', [])
                        person_data['sources'].append('hobbies_search')
                except Exception as e:
                    logger.debug(f'Erreur recherche hobbies: {e}')
            
            # Recherche de fuites de données (data breaches)
            if person_email:
                try:
                    if progress_callback:
                        progress_callback(f'Vérification des fuites de données pour {person_email}...')
                    breaches = self._check_data_breaches(person_email)
                    if breaches:
                        person_data['data_breaches'] = breaches
                        person_data['sources'].append('data_breaches')
                except Exception as e:
                    logger.debug(f'Erreur vérification fuites: {e}')
            
            # Recherche web pour trouver des informations publiques
            if person_name:
                try:
                    web_info = self._search_person_online(person_name, domain)
                    if web_info:
                        person_data.update(web_info)
                except Exception as e:
                    logger.debug(f'Erreur recherche web pour {person_name}: {e}')
            
            enriched_people[person_name or person_email] = person_data
        
        return enriched_people
    
    def _search_person_photos(self, name: str, email: str, domain: str) -> List[str]:
        """
        Recherche de photos d'une personne
        Utilise des moteurs de recherche d'images
        """
        photos = []
        
        try:
            # Recherche via Google Images (via DuckDuckGo)
            search_query = f'"{name}"'
            if domain:
                search_query += f' "{domain}"'
            
            search_url = f'https://html.duckduckgo.com/html/?q={search_query}'
            response = requests.get(search_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Chercher des liens d'images
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                        if src.startswith('http'):
                            photos.append(src)
                        elif src.startswith('//'):
                            photos.append('https:' + src)
        except Exception as e:
            logger.debug(f'Erreur recherche photos: {e}')
        
        return photos[:10]  # Limiter à 10 photos
    
    def _search_person_location(self, name: str, domain: str) -> Dict:
        """
        Recherche de localisation d'une personne
        """
        location_data = {}
        
        try:
            # Recherche web pour trouver des indices de localisation
            search_query = f'"{name}" location address'
            if domain:
                search_query += f' "{domain}"'
            
            search_url = f'https://html.duckduckgo.com/html/?q={search_query}'
            response = requests.get(search_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text().lower()
                
                # Chercher des indices de localisation (ville, pays)
                # Note: Cette méthode est basique, peut être améliorée avec des APIs
                city_patterns = ['paris', 'lyon', 'marseille', 'toulouse', 'nice', 'nantes']
                for city in city_patterns:
                    if city in text:
                        location_data['location_city'] = city.capitalize()
                        break
        except Exception as e:
            logger.debug(f'Erreur recherche localisation: {e}')
        
        return location_data
    
    def _search_person_hobbies(self, name: str, linkedin_url: str) -> Dict:
        """
        Recherche de hobbies et intérêts d'une personne
        """
        hobbies_data = {
            'hobbies': [],
            'interests': []
        }
        
        try:
            # Recherche web pour trouver des hobbies mentionnés
            search_query = f'"{name}" hobbies interests'
            if linkedin_url:
                search_query += f' "{linkedin_url}"'
            
            search_url = f'https://html.duckduckgo.com/html/?q={search_query}'
            response = requests.get(search_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text().lower()
                
                # Hobbies communs à chercher
                common_hobbies = ['photography', 'reading', 'traveling', 'music', 'sports', 
                                'cooking', 'gaming', 'hiking', 'cycling', 'swimming',
                                'photographie', 'lecture', 'voyage', 'musique', 'sport',
                                'cuisine', 'jeux', 'randonnée', 'vélo', 'natation']
                
                found_hobbies = []
                for hobby in common_hobbies:
                    if hobby in text:
                        found_hobbies.append(hobby.capitalize())
                
                hobbies_data['hobbies'] = found_hobbies[:10]  # Limiter à 10
        except Exception as e:
            logger.debug(f'Erreur recherche hobbies: {e}')
        
        return hobbies_data
    
    def _check_data_breaches(self, email: str) -> List[Dict]:
        """
        Vérifie si un email a été compromis dans des fuites de données
        Utilise Have I Been Pwned API (gratuite)
        """
        breaches = []
        
        try:
            # API Have I Been Pwned (gratuite, pas besoin de clé API pour la recherche)
            response = requests.get(
                f'https://haveibeenpwned.com/api/v3/breachedaccount/{email}',
                headers={'User-Agent': 'ProspectLab-OSINT'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    for breach in data:
                        breaches.append({
                            'name': breach.get('Name', ''),
                            'domain': breach.get('Domain', ''),
                            'breach_date': breach.get('BreachDate', ''),
                            'data_classes': breach.get('DataClasses', [])
                        })
        except Exception as e:
            # L'API peut retourner 404 si l'email n'a pas été compromis
            if '404' not in str(e):
                logger.debug(f'Erreur vérification fuites: {e}')
        
        return breaches
    
    def _search_person_online(self, name: str, domain: str) -> Dict:
        """
        Recherche web basique d'une personne
        Utilise des moteurs de recherche publics
        """
        results = {}
        
        try:
            search_query = f'"{name}" "{domain}"'
            search_url = f'https://html.duckduckgo.com/html/?q={search_query}'
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                social_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if any(platform in href.lower() for platform in ['linkedin', 'twitter', 'facebook', 'github']):
                        social_links.append(href)
                
                if social_links:
                    results['social_profiles'] = {'web_search': social_links}
                    results['sources'] = ['web_search']
        except Exception as e:
            logger.debug(f'Erreur recherche web personne: {e}')
        
        return results
    
    def get_ip_geolocation(self, ip: str) -> Dict:
        """
        Récupère la géolocalisation d'une adresse IP
        Utilise des APIs publiques gratuites
        
        Args:
            ip: Adresse IP à géolocaliser
        
        Returns:
            Dictionnaire avec les informations de géolocalisation
        """
        geolocation = {
            'ip': ip,
            'country': None,
            'region': None,
            'city': None,
            'latitude': None,
            'longitude': None,
            'isp': None,
            'timezone': None
        }
        
        # Essayer ipapi.co (gratuit, 1000 requêtes/jour)
        try:
            response = requests.get(f'https://ipapi.co/{ip}/json/', headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'error' not in data:
                    geolocation['country'] = data.get('country_name')
                    geolocation['region'] = data.get('region')
                    geolocation['city'] = data.get('city')
                    geolocation['latitude'] = data.get('latitude')
                    geolocation['longitude'] = data.get('longitude')
                    geolocation['isp'] = data.get('org')
                    geolocation['timezone'] = data.get('timezone')
                    geolocation['source'] = 'ipapi.co'
                    return geolocation
        except Exception as e:
            logger.debug(f'Erreur ipapi.co: {e}')
        
        # Fallback: ip-api.com (gratuit, 45 requêtes/min)
        try:
            response = requests.get(f'http://ip-api.com/json/{ip}', headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    geolocation['country'] = data.get('country')
                    geolocation['region'] = data.get('regionName')
                    geolocation['city'] = data.get('city')
                    geolocation['latitude'] = data.get('lat')
                    geolocation['longitude'] = data.get('lon')
                    geolocation['isp'] = data.get('isp')
                    geolocation['timezone'] = data.get('timezone')
                    geolocation['source'] = 'ip-api.com'
                    return geolocation
        except Exception as e:
            logger.debug(f'Erreur ip-api.com: {e}')
        
        return geolocation if geolocation.get('country') else None
    
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
            # Retourner un dict vide au lieu d'une erreur pour éviter l'affichage
            return {}
        
        result = self._run_wsl_command(['whatweb', '--no-errors', url], timeout=30)
        
        if result.get('success'):
            output = result['stdout']
            # Nettoyer les codes ANSI
            clean_output = self._clean_ansi_codes(output)
            # Ne pas sauvegarder raw_output dans technologies, seulement parser les infos utiles
            # tech_info['raw_output'] = clean_output  # Commenté pour éviter l'affichage
            # Extraire les technologies détectées
            if 'WordPress' in output:
                tech_info['cms'] = ['WordPress']
            if 'Drupal' in output:
                tech_info['cms'] = ['Drupal']
            if 'Joomla' in output:
                tech_info['cms'] = ['Joomla']
            if 'Apache' in output:
                tech_info['server'] = ['Apache']
            if 'nginx' in output.lower():
                tech_info['server'] = ['Nginx']
            if 'PHP' in output:
                tech_info['language'] = ['PHP']
            # Extraire d'autres technologies courantes
            if 'Vercel' in output:
                tech_info['hosting'] = ['Vercel']
            if 'Next.js' in output or 'X-Powered-By[Next.js]' in output:
                tech_info['framework'] = ['Next.js']
            if 'React' in output:
                tech_info['framework'] = ['React']
            if 'Vue' in output:
                tech_info['framework'] = ['Vue']
            if 'jQuery' in output:
                tech_info['library'] = ['jQuery']
            if 'Google Analytics' in output or 'gtag' in output.lower():
                tech_info['analytics'] = ['Google Analytics']
        
        return tech_info
    
    def _analyze_ssl_details(self, domain: str, progress_callback=None) -> List[Dict]:
        """
        Analyse SSL/TLS détaillée avec testssl.sh
        Retourne une liste de dictionnaires avec les détails SSL
        """
        ssl_details = []
        
        if not self.tools['testssl']:
            return ssl_details
        
        if progress_callback:
            progress_callback('Analyse SSL/TLS détaillée avec testssl.sh...')
        
        try:
            result = self._run_wsl_command(['testssl.sh', '--json', domain], timeout=60)
            if result.get('success'):
                output = result['stdout']
                # Parser le JSON de testssl.sh
                try:
                    json_data = json.loads(output)
                    if isinstance(json_data, list):
                        for item in json_data:
                            ssl_details.append({
                                'host': domain,
                                'port': item.get('port', 443),
                                'certificate_valid': item.get('severity') != 'CRITICAL',
                                'certificate_issuer': item.get('finding'),
                                'certificate_subject': item.get('id'),
                                'certificate_expiry': item.get('expiry'),
                                'protocol_version': item.get('protocol'),
                                'cipher_suites': item.get('cipher'),
                                'vulnerabilities': item.get('severity'),
                                'grade': item.get('grade'),
                                'details_json': json.dumps(item)
                            })
                except json.JSONDecodeError:
                    # Si ce n'est pas du JSON, parser le texte
                    if 'TLS 1.3' in output:
                        ssl_details.append({
                            'host': domain,
                            'port': 443,
                            'protocol_version': 'TLS 1.3',
                            'certificate_valid': True,
                            'details_json': output[:1000]  # Limiter la taille
                        })
        except Exception as e:
            logger.debug(f'Erreur analyse SSL détaillée: {e}')
        
        return ssl_details
    
    def _detect_waf(self, url: str, progress_callback=None) -> List[Dict]:
        """
        Détecte les WAF (Web Application Firewall) avec wafw00f
        """
        waf_detections = []
        
        if not self.tools['wafw00f']:
            return waf_detections
        
        if progress_callback:
            progress_callback('Détection des WAF avec wafw00f...')
        
        try:
            result = self._run_wsl_command(['wafw00f', url], timeout=30)
            if result.get('success'):
                output = result['stdout']
                # Parser les résultats wafw00f
                if 'is behind' in output.lower() or 'is protected by' in output.lower():
                    waf_match = re.search(r'(?:is behind|is protected by)\s+([A-Za-z0-9\s-]+)', output, re.IGNORECASE)
                    if waf_match:
                        waf_name = waf_match.group(1).strip()
                        waf_detections.append({
                            'url': url,
                            'waf_name': waf_name,
                            'waf_vendor': waf_name.split()[0] if waf_name else None,
                            'detected': True,
                            'detection_method': 'wafw00f',
                            'details_json': json.dumps({'output': output[:500]})
                        })
                elif 'no waf detected' in output.lower():
                    waf_detections.append({
                        'url': url,
                        'waf_name': None,
                        'waf_vendor': None,
                        'detected': False,
                        'detection_method': 'wafw00f',
                        'details_json': json.dumps({'output': output[:500]})
                    })
        except Exception as e:
            logger.debug(f'Erreur détection WAF: {e}')
        
        return waf_detections
    
    def _discover_directories(self, url: str, progress_callback=None) -> List[Dict]:
        """
        Découvre les répertoires avec Gobuster
        """
        directories = []
        
        if not self.tools['gobuster']:
            return directories
        
        if progress_callback:
            progress_callback('Découverte des répertoires avec Gobuster...')
        
        try:
            # Utiliser une wordlist commune
            result = self._run_wsl_command([
                'gobuster', 'dir', '-u', url, '-w', '/usr/share/wordlists/dirb/common.txt', 
                '--no-error', '-q', '-t', '10'
            ], timeout=60)
            
            if result.get('success'):
                output = result['stdout']
                for line in output.split('\n'):
                    if line.strip() and not line.startswith('='):
                        # Parser les résultats gobuster
                        parts = line.split()
                        if len(parts) >= 2:
                            path = parts[0] if parts[0].startswith('/') else '/' + parts[0]
                            status_code = parts[1] if parts[1].isdigit() else None
                            directories.append({
                                'path': path,
                                'status_code': int(status_code) if status_code else None,
                                'size': parts[2] if len(parts) > 2 else None,
                                'discovered_by': 'gobuster'
                            })
        except Exception as e:
            logger.debug(f'Erreur découverte répertoires: {e}')
        
        return directories
    
    def _scan_ports_and_services(self, domain: str, ip: str = None, progress_callback=None) -> Dict:
        """
        Scanne les ports et services avec Shodan et Censys
        Retourne un dictionnaire avec open_ports, services et certificates
        """
        result = {
            'open_ports': [],
            'services': [],
            'certificates': []
        }
        
        if not ip:
            try:
                ip = socket.gethostbyname(domain)
            except:
                return result
        
        # Shodan
        if self.tools['shodan']:
            if progress_callback:
                progress_callback('Scan Shodan...')
            try:
                shodan_result = self._run_wsl_command(['shodan', 'host', ip], timeout=30)
                if shodan_result.get('success'):
                    output = shodan_result['stdout']
                    # Parser les résultats Shodan
                    port_pattern = r'(\d+)\s+([^\s]+)\s+(.+)'
                    for match in re.finditer(port_pattern, output):
                        port = int(match.group(1))
                        service = match.group(2)
                        banner = match.group(3)
                        result['open_ports'].append({
                            'ip': ip,
                            'port': port,
                            'protocol': 'tcp',
                            'state': 'open',
                            'discovered_by': 'shodan'
                        })
                        result['services'].append({
                            'ip': ip,
                            'port': port,
                            'service_name': service,
                            'banner': banner[:500],
                            'discovered_by': 'shodan'
                        })
            except Exception as e:
                logger.debug(f'Erreur scan Shodan: {e}')
        
        # Censys
        if self.tools['censys']:
            if progress_callback:
                progress_callback('Scan Censys...')
            try:
                censys_result = self._run_wsl_command(['censys', 'search', f'ip:{ip}'], timeout=30)
                if censys_result.get('success'):
                    output = censys_result['stdout']
                    # Parser les résultats Censys (format JSON possible)
                    try:
                        data = json.loads(output)
                        if isinstance(data, list):
                            for item in data:
                                port = item.get('port', 443)
                                result['open_ports'].append({
                                    'ip': ip,
                                    'port': port,
                                    'protocol': 'tcp',
                                    'state': 'open',
                                    'discovered_by': 'censys'
                                })
                    except json.JSONDecodeError:
                        # Parser texte
                        port_pattern = r'port[:\s]+(\d+)'
                        for match in re.finditer(port_pattern, output, re.IGNORECASE):
                            port = int(match.group(1))
                            result['open_ports'].append({
                                'ip': ip,
                                'port': port,
                                'protocol': 'tcp',
                                'state': 'open',
                                'discovered_by': 'censys'
                            })
            except Exception as e:
                logger.debug(f'Erreur scan Censys: {e}')
        
        return result
    
    def _search_document_metadata(self, domain: str, progress_callback=None) -> List[Dict]:
        """
        Recherche les métadonnées de documents avec Metagoofil
        """
        document_metadata = []
        
        if not self.tools['metagoofil']:
            return document_metadata
        
        if progress_callback:
            progress_callback('Recherche des métadonnées de documents avec Metagoofil...')
        
        try:
            result = self._run_wsl_command(['metagoofil', '-d', domain, '-t', 'pdf,doc,docx,xls,xlsx', '-l', '20'], timeout=60)
            if result.get('success'):
                output = result['stdout']
                # Parser les résultats Metagoofil
                current_doc = {}
                for line in output.split('\n'):
                    if 'File:' in line:
                        if current_doc:
                            document_metadata.append(current_doc)
                        current_doc = {'file_name': line.replace('File:', '').strip()}
                    elif ':' in line and current_doc:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip()
                        current_doc[key] = value
                
                if current_doc:
                    document_metadata.append(current_doc)
        except Exception as e:
            logger.debug(f'Erreur recherche métadonnées documents: {e}')
        
        return document_metadata
    
    def _search_image_metadata(self, url: str, progress_callback=None) -> List[Dict]:
        """
        Recherche les métadonnées d'images avec ExifTool
        """
        image_metadata = []
        
        if not self.tools['exiftool']:
            return image_metadata
        
        if progress_callback:
            progress_callback('Recherche des métadonnées d\'images avec ExifTool...')
        
        try:
            # Télécharger la page et extraire les URLs d'images
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                img_urls = []
                for img in soup.find_all('img', src=True):
                    img_url = img['src']
                    if not img_url.startswith('http'):
                        img_url = url + img_url if img_url.startswith('/') else url + '/' + img_url
                    img_urls.append(img_url)
                
                # Analyser les 5 premières images avec ExifTool
                for img_url in img_urls[:5]:
                    try:
                        result = self._run_wsl_command(['exiftool', '-j', img_url], timeout=10)
                        if result.get('success'):
                            output = result['stdout']
                            try:
                                exif_data = json.loads(output)
                                if isinstance(exif_data, list) and len(exif_data) > 0:
                                    exif = exif_data[0]
                                    image_metadata.append({
                                        'image_url': img_url,
                                        'camera_make': exif.get('Make'),
                                        'camera_model': exif.get('Model'),
                                        'date_taken': exif.get('DateTimeOriginal') or exif.get('CreateDate'),
                                        'gps_latitude': exif.get('GPSLatitude'),
                                        'gps_longitude': exif.get('GPSLongitude'),
                                        'gps_altitude': exif.get('GPSAltitude'),
                                        'location_description': exif.get('Location'),
                                        'software': exif.get('Software'),
                                        'metadata_json': json.dumps(exif)
                                    })
                            except json.JSONDecodeError:
                                pass
                    except:
                        continue
        except Exception as e:
            logger.debug(f'Erreur recherche métadonnées images: {e}')
        
        return image_metadata
    
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
    
    def analyze_osint(self, url: str, progress_callback=None, people_from_scrapers=None,
                     emails_from_scrapers=None, social_profiles_from_scrapers=None,
                     phones_from_scrapers=None, names_from_scraper_emails=None,
                     phone_osint_premerge: Optional[Dict] = None) -> Dict:
        """
        Analyse OSINT complète d'un domaine/URL
        Retourne toutes les informations collectées
        
        Args:
            url: URL à analyser
            progress_callback: Callback pour la progression
            people_from_scrapers: Liste des personnes trouvées par les scrapers (optionnel)
            emails_from_scrapers: Liste des emails trouvés par les scrapers (optionnel)
            social_profiles_from_scrapers: Liste des profils sociaux trouvés par les scrapers (optionnel)
            phones_from_scrapers: Liste des téléphones trouvés par les scrapers (optionnel)
            phone_osint_premerge: Résultat de tasks.phone_tasks.analyze_phones_task (dict numéro -> infos), sans relancer l'analyse ici.
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
            'summary': {},
            'from_scrapers': {
                'emails_count': len(emails_from_scrapers or []),
                'people_count': len(people_from_scrapers or []),
                'social_profiles_count': len(social_profiles_from_scrapers or []),
                'phones_count': len(phones_from_scrapers or [])
            }
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
        
        # Emails : utiliser ceux du scraper si disponibles, sinon chercher avec optimisation
        try:
            if emails_from_scrapers:
                # 1) On part des emails trouvés par le scraper
                if progress_callback:
                    progress_callback(f'Utilisation de {len(emails_from_scrapers)} email(s) du scraper...')
                results['emails'] = list(set(emails_from_scrapers))  # Dédupliquer
                results['emails_from_scrapers'] = True
                
                # 2) Si on a des noms extraits des emails, chercher des emails supplémentaires avec ces noms
                if names_from_scraper_emails and len(names_from_scraper_emails) > 0:
                    if progress_callback:
                        progress_callback(
                            f'Recherche d\'emails supplémentaires avec {len(names_from_scraper_emails)} nom(s) trouvé(s)...'
                        )
                    try:
                        additional_emails = self.harvest_emails(
                            domain,
                            progress_callback,
                            names=names_from_scraper_emails
                        )
                        existing_emails_set = set(e.lower() for e in results['emails'])
                        for email in additional_emails:
                            email_lower = email.lower()
                            if email_lower not in existing_emails_set:
                                results['emails'].append(email)
                                existing_emails_set.add(email_lower)
                    except Exception as e:
                        logger.warning(
                            f'Erreur lors de la recherche d\'emails supplémentaires avec les noms: {e}'
                        )
            else:
                # Pas d'emails du scraper -> on fait une collecte classique
                if progress_callback:
                    progress_callback('Collecte d\'emails...')
                harvested_emails = self.harvest_emails(
                    domain,
                    progress_callback,
                    names=names_from_scraper_emails
                )
                results['emails'] = harvested_emails
                results['emails_from_scrapers'] = False
        except Exception as e:
            # En cas d'erreur, ne pas écraser complètement mais au pire laisser la liste existante
            logger.warning(f'Erreur lors de la collecte d\'emails: {e}')
            results['emails_error'] = str(e)
            if not isinstance(results.get('emails'), list):
                results['emails'] = []
        
        # Recherche de personnes et profils sociaux : enrichir celles du scraper
        if progress_callback:
            progress_callback('Enrichissement des personnes avec OSINT...')
        try:
            if people_from_scrapers:
                # Si on a des personnes du scraper, les enrichir puis construire le résumé
                enriched_people = self.enrich_people_from_scrapers(
                    people_from_scrapers,
                    domain,
                    progress_callback
                )
                results['people'] = {
                    'from_scrapers': enriched_people,
                    'people': enriched_people,
                    'summary': {
                        'total_people': len(enriched_people),
                        'with_emails': len([p for p in enriched_people if p.get('email')]),
                        'with_linkedin': len([p for p in enriched_people if p.get('linkedin_url')]),
                        'with_social_profiles': len([p for p in enriched_people if p.get('social_profiles')]),
                        'from_website': len(
                            [p for p in enriched_people if 'website_scraping' in p.get('source', '')]
                        )
                    }
                }
            else:
                # Sinon, chercher avec OSINT classique (emails récoltés ci-dessus)
                people_data = self.search_people_osint(domain, results['emails'], progress_callback)
                results['people'] = people_data
        except Exception as e:
            results['people_error'] = str(e)
            results['people'] = {}
        
        # Ajouter les profils sociaux du scraper si disponibles
        if social_profiles_from_scrapers:
            if progress_callback:
                progress_callback(f'Ajout de {len(social_profiles_from_scrapers)} profil(s) social/social du scraper...')
            if 'people' not in results or not isinstance(results['people'], dict):
                results['people'] = {}
            if 'social_profiles_from_scrapers' not in results['people']:
                results['people']['social_profiles_from_scrapers'] = social_profiles_from_scrapers
        
        # Ajouter les téléphones du scraper si disponibles
        if phones_from_scrapers:
            if progress_callback:
                progress_callback(f'Ajout de {len(phones_from_scrapers)} téléphone(s) du scraper...')
            results['phones_from_scrapers'] = phones_from_scrapers
        
        # Analyse téléphone : effectuée par la tâche Celery analyze_phones_task (pas ici)
        if phone_osint_premerge is not None:
            results['phone_osint'] = phone_osint_premerge
        else:
            results['phone_osint'] = {}
        
        # Recherche OSINT avancée sur les personnes (famille, localisation, etc.)
        if people_from_scrapers and len(people_from_scrapers) > 0:
            if progress_callback:
                progress_callback('Recherche OSINT approfondie sur les personnes...')
            try:
                people_osint_data = self.analyze_people_osint(people_from_scrapers[:5], domain, progress_callback)
                results['people_osint'] = people_osint_data
            except Exception as e:
                logger.warning(f'Erreur lors de l\'analyse OSINT approfondie des personnes: {e}')
                results['people_osint_error'] = str(e)
        
        # Géolocalisation depuis les IPs trouvées
        if results.get('ip_info', {}).get('ip'):
            if progress_callback:
                progress_callback('Géolocalisation des adresses IP...')
            try:
                ip_geolocation = self.get_ip_geolocation(results['ip_info'].get('ip'))
                if ip_geolocation:
                    results['ip_geolocation'] = ip_geolocation
            except Exception as e:
                logger.warning(f'Erreur lors de la géolocalisation IP: {e}')
        
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
        
        # Analyse SSL basique
        if progress_callback:
            progress_callback('Analyse SSL/TLS...')
        try:
            results['ssl_info'] = self.analyze_ssl(domain)
        except Exception as e:
            results['ssl_error'] = str(e)
        
        # Analyse SSL détaillée avec testssl.sh
        try:
            ssl_details = self._analyze_ssl_details(domain, progress_callback)
            if ssl_details:
                results['ssl_details'] = ssl_details
        except Exception as e:
            logger.debug(f'Erreur analyse SSL détaillée: {e}')
        
        # Détection WAF
        try:
            waf_detections = self._detect_waf(url, progress_callback)
            if waf_detections:
                results['waf_detections'] = waf_detections
        except Exception as e:
            logger.debug(f'Erreur détection WAF: {e}')
        
        # Découverte de répertoires
        try:
            directories = self._discover_directories(url, progress_callback)
            if directories:
                results['directories'] = directories
        except Exception as e:
            logger.debug(f'Erreur découverte répertoires: {e}')
        
        # Informations IP
        if progress_callback:
            progress_callback('Récupération des informations IP...')
        ip = None
        try:
            ip = socket.gethostbyname(domain)
            results['ip_info'] = {
                'ip': ip,
                'hostname': socket.gethostbyaddr(ip)[0] if ip else None
            }
        except Exception as e:
            results['ip_error'] = str(e)
        
        # Scan des ports et services (Shodan/Censys)
        if ip:
            try:
                port_scan_results = self._scan_ports_and_services(domain, ip, progress_callback)
                if port_scan_results.get('open_ports'):
                    results['open_ports'] = port_scan_results['open_ports']
                if port_scan_results.get('services'):
                    results['services'] = port_scan_results['services']
                if port_scan_results.get('certificates'):
                    results['certificates'] = port_scan_results['certificates']
            except Exception as e:
                logger.debug(f'Erreur scan ports/services: {e}')
        
        # Recherche de métadonnées de documents
        try:
            document_metadata = self._search_document_metadata(domain, progress_callback)
            if document_metadata:
                results['document_metadata'] = document_metadata
        except Exception as e:
            logger.debug(f'Erreur recherche métadonnées documents: {e}')
        
        # Recherche de métadonnées d'images
        try:
            image_metadata = self._search_image_metadata(url, progress_callback)
            if image_metadata:
                results['image_metadata'] = image_metadata
        except Exception as e:
            logger.debug(f'Erreur recherche métadonnées images: {e}')
        
        # Technologies
        if progress_callback:
            progress_callback('Détection des technologies...')
        try:
            results['technologies'] = self.detect_technologies(url)
        except Exception as e:
            results['tech_error'] = str(e)
        
        # Diagnostic (pour expliquer pourquoi l'analyse peut être partielle)
        try:
            results['diagnostic'] = self.get_diagnostic()
            diag = results['diagnostic']
            if not diag['wsl_available'] or len(diag['tools_available']) == 0:
                results['summary_warning'] = diag['message']
        except Exception as e:
            logger.debug(f'Diagnostic OSINT: {e}')
        
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
